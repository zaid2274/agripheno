"""Lecture ZIP distante sélective, reprise locale et vérification d'intégrité."""

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import io
from pathlib import Path
import re
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import zipfile
import zlib


def fetch_range(url: str, start: int, end: int, size: int) -> bytes:
    """Exige HTTP 206 et Content-Range exact ; ne charge jamais l'archive entière."""
    separator = "&" if "?" in url else "?"
    # Une URL distincte par plage évite les réponses partielles périmées de CDN.
    request = Request(url + separator + urlencode({"agripheno_range": f"{start}-{end}"}),
                      headers={"Range": f"bytes={start}-{end}", "Accept-Encoding": "identity"})
    started = time.monotonic()
    with urlopen(request, timeout=20) as response:
        match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", response.headers.get("Content-Range", ""))
        if response.status != 206 or not match or tuple(map(int, match.groups())) != (start, end, size):
            raise OSError("Réponse HTTP Range incohérente ; téléchargement interrompu.")
        chunks, count = [], 0
        while count <= end-start+1:
            if time.monotonic()-started > 90:
                raise OSError("Délai maximal de téléchargement du bloc dépassé.")
            # read1 permet de contrôler le délai même si le serveur envoie peu.
            read = getattr(response, "read1", response.read)
            piece = read(min(65536, end-start+2-count))
            if not piece:
                break
            chunks.append(piece)
            count += len(piece)
        data = b"".join(chunks)
    if len(data) != end-start+1:
        raise OSError("Plage HTTP tronquée ou trop longue.")
    return data


class RemoteZip(io.RawIOBase):
    """Fichier seekable pour zipfile ; seuls les blocs demandés sont téléchargés.

    Les blocs repris sont vérifiés par SHA-256 ; zipfile vérifie ensuite le CRC
    des membres décompressés. Les fichiers restent dans un cache dédié.
    """

    def __init__(self, url: str, size: int, cache: Path, fetcher=fetch_range, progress=None):
        super().__init__()
        self.url, self.size, self.pos = url, size, 0
        self.cache = cache / hashlib.sha256(url.encode()).hexdigest()[:16]
        self.cache.mkdir(parents=True, exist_ok=True)
        self.fetcher = fetcher
        self.progress = progress

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        target = offset if whence == 0 else self.pos+offset if whence == 1 else self.size+offset
        if target < 0:
            raise ValueError("Position négative.")
        self.pos = target
        return target

    def _block(self, bounds):
        start, end = bounds
        path = self.cache / f"{start}-{end}.bin"
        checksum = path.with_suffix(".sha256")
        if path.exists() and checksum.exists():
            data = path.read_bytes()
            if len(data) == end-start+1 and hashlib.sha256(data).hexdigest() == checksum.read_text():
                return data
        for attempt in range(3):
            try:
                data = self.fetcher(self.url, start, end, self.size)
                break
            except OSError:
                if attempt == 2:
                    raise
                time.sleep(attempt+1)
        if len(data) != end-start+1:
            raise OSError("Bloc incomplet.")
        temporary = path.with_suffix(".part")
        temporary.write_bytes(data)
        temporary.replace(path)
        checksum.write_text(hashlib.sha256(data).hexdigest())
        return data

    def read(self, n=-1):
        n = min(n if n >= 0 else self.size-self.pos, max(0, self.size-self.pos))
        if n <= 0:
            return b""
        start = self.pos
        block_size = 1024*1024
        bounds = [(i, min(i+block_size, start+n)-1) for i in range(start, start+n, block_size)]
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(self._block, item): i for i, item in enumerate(bounds)}
            pieces = {}
            for completed, future in enumerate(as_completed(futures), 1):
                pieces[futures[future]] = future.result()
                if self.progress and len(bounds) > 8 and (completed % 16 == 0 or completed == len(bounds)):
                    self.progress(f"{completed}/{len(bounds)} blocs validés")
            data = b"".join(pieces[i] for i in range(len(bounds)))
        self.pos += len(data)
        return data


def cached_member(archive: zipfile.ZipFile, member: str, cache: Path) -> bytes:
    """Ne construit aucun chemin local à partir du nom potentiellement externe."""
    info = archive.getinfo(member)
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / (hashlib.sha256(member.encode()).hexdigest() + ".original")
    if path.exists():
        data = path.read_bytes()
        if len(data) == info.file_size and zlib.crc32(data) == info.CRC:
            return data
    data = archive.read(member)  # Décompression + contrôle CRC par zipfile.
    temporary = path.with_suffix(".part")
    temporary.write_bytes(data)
    temporary.replace(path)
    return data
