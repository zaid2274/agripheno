"""Acquisition reproductible de photographies RGB depuis les archives Zenodo.

python -m scripts.acquire_real_images
Les originaux et blocs HTTP restent dans data/.cache, ignoré par Git.
"""

import argparse
import hashlib
import json
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.request import urlopen
import zipfile

import cv2
import numpy as np
import pandas as pd

from src.acquisition import RemoteZip, cached_member

ROOT = Path(__file__).resolve().parents[1]
DATASETS = {
    "cofly": ("6697343", "CoFly-WeedDB.zip", "CoFly-WeedDB", "cotonnier", "DJI Phantom 4 Pro", "quasi-nadir -87°", "adventices_uniquement"),
    "corn": ("20044178", "USU-Corn-WeedDB.zip", "USU-Corn-WeedDB", "maïs", "Autel EVO II Dual 640T V2", "à vérifier visuellement", "boites_adventices"),
    "agri": ("12607112", "Dataset.zip", "High-Resolution RGB Images and Corresponding Masks of Agricultural Fields", "non identifiée au niveau image", "DJI Air 2S", "à vérifier visuellement", "masque_fourni_cible_a_verifier"),
}


def prepare_rgb(array: np.ndarray) -> tuple[np.ndarray, str]:
    """Conversion commune aux trois canaux ; aucun réétalonnage par image."""
    if array is None or array.ndim != 3 or array.shape[2] != 3:
        raise ValueError("Le fichier n'est pas une photographie couleur à trois canaux.")
    if array.dtype == np.uint8:
        return cv2.cvtColor(array, cv2.COLOR_BGR2RGB), "RGB uint8 conservé"
    if array.dtype == np.uint16:
        converted = np.rint(array.astype(np.float32)/257).astype(np.uint8)
        return cv2.cvtColor(converted, cv2.COLOR_BGR2RGB), "uint16 /257 puis arrondi uint8, échelle commune RGB"
    # Les TIFF flottants demandent une vérification explicite de l'échelle source.
    raise ValueError(f"Échelle TIFF à vérifier : dtype={array.dtype}, min={array.min()}, max={array.max()}")


def save_png(path: Path, image: np.ndarray):
    path.parent.mkdir(parents=True, exist_ok=True)
    success, content = cv2.imencode(".png", image)
    if not success:
        raise OSError(f"Encodage PNG impossible : {path}")
    path.write_bytes(content.tobytes())


def _acquire_sources(output: Path, only: list[str], extra: int = 0):
    sources_path = output / "sources.csv"
    records = pd.read_csv(sources_path, keep_default_na=False).to_dict("records") if sources_path.exists() else []
    for key in (only or ["cofly", "corn", "agri"]):
        rid, filename, title, crop, platform, orientation, annotation = DATASETS[key]
        with urlopen(f"https://zenodo.org/api/records/{rid}", timeout=30) as response:
            metadata = json.load(response)
        if metadata["metadata"]["license"]["id"] != "cc-by-4.0":
            raise ValueError(f"Licence modifiée ou non autorisée : {rid}")
        (output / "provenance").mkdir(parents=True, exist_ok=True)
        (output / "provenance" / f"zenodo_{rid}.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        file_info = next(f for f in metadata["files"] if f["key"] == filename)
        authors = "; ".join(c["name"] for c in metadata["metadata"].get("creators", []))
        date = response.headers.get("Date", "")
        remote = RemoteZip(file_info["links"]["self"], file_info["size"], output / ".cache" / key,
                           progress=lambda message: print(f"  {message}", flush=True))
        with zipfile.ZipFile(remote) as archive:
            names = archive.namelist()
            if key == "agri":
                selected = [f"img/c{i}.tif" for i in [0, 108, 217]]
                candidates = sorted(n for n in names if n.startswith("img/") and n.endswith(".tif"))
            else:
                candidates = sorted(n for n in names if "/images/" in "/"+n.lower() and n.lower().endswith((".png", ".jpg", ".jpeg")))
                if not candidates:
                    raise ValueError(f"Dossier images introuvable pour {key}. Exemples : {names[:15]}")
                # Espacement dans l'ordre des identifiants, indépendant des scores.
                selected = [candidates[i] for i in np.linspace(0, len(candidates)-1, 3 if key == "cofly" else 4, dtype=int)]
            target = len(selected) + extra
            selected += [n for n in candidates if n not in selected]
            successful = 0
            for index, member in enumerate(selected):
                if successful >= target:
                    break
                image_id = f"{key}_{Path(member).stem}" if key == "agri" else f"{key}_{index+1:02d}"
                print(f"{image_id}: {member}", flush=True)
                original = cached_member(archive, member, output / ".cache" / key / "originals")
                decoded = cv2.imdecode(np.frombuffer(original, np.uint8), cv2.IMREAD_UNCHANGED)
                try:
                    rgb, conversion = prepare_rgb(decoded)
                except ValueError as exc:
                    log = output / "provenance/substitutions.jsonl"
                    with log.open("a", encoding="utf-8") as stream:
                        stream.write(json.dumps({"dataset": key, "member": member, "reason": str(exc)}, ensure_ascii=False)+"\n")
                    print(f"  Image refusée : {exc}. Candidat suivant.", flush=True)
                    continue
                height, width = rgb.shape[:2]
                scale = min(1., (25_000_000/(height*width))**0.5)
                if scale < 1:
                    rgb = cv2.resize(rgb, (int(width*scale), int(height*scale)), interpolation=cv2.INTER_AREA)
                local = output / "real_drone_images" / f"{image_id}.png"
                save_png(local, cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
                reference_member = ""
                reference_source_sha256 = ""
                original_label_path = ""
                if key == "agri":
                    reference_member = f"mask/m{Path(member).stem[1:]}.tif"
                elif key == "cofly":
                    reference_member = member.replace("/images/", "/labels_1d/")
                    if reference_member not in names:
                        reference_member = ""
                if reference_member:
                    ref_bytes = cached_member(archive, reference_member, output / ".cache" / key / "originals")
                    ref = cv2.imdecode(np.frombuffer(ref_bytes, np.uint8), cv2.IMREAD_UNCHANGED)
                    if ref is None:
                        raise ValueError("Masque source illisible.")
                    original_label_path = f"reference_masks/original_labels/{image_id}.png"
                    save_png(output / original_label_path, ref)
                    reference_source_sha256 = hashlib.sha256(ref_bytes).hexdigest()
                row = {"image_id": image_id, "image_path": f"real_drone_images/{image_id}.png",
                       "dataset": title, "dataset_title": metadata["metadata"].get("title", title),
                       "authors": authors, "dataset_url": f"https://zenodo.org/records/{rid}",
                       "doi": f"10.5281/zenodo.{rid}", "archive_url": file_info["links"]["self"],
                       "archive_member": member, "license": "CC BY 4.0",
                       "license_url": "https://creativecommons.org/licenses/by/4.0/", "attribution": f"{authors}. {metadata['metadata'].get('title', title)}. DOI:10.5281/zenodo.{rid}. CC BY 4.0.",
                       "access_date": parsedate_to_datetime(date).date().isoformat() if date else "inconnue",
                       "access_date_http": date, "source_sha256": hashlib.sha256(original).hexdigest(),
                       "prepared_sha256": hashlib.sha256(local.read_bytes()).hexdigest(),
                       "original_width": width, "original_height": height,
                       "width": rgb.shape[1], "height": rgb.shape[0], "transformations": conversion + (f"; réduction facteur {scale}" if scale < 1 else "; aucune réduction"),
                       "crop": crop, "drone": platform, "orientation": orientation,
                       "annotation_scope": annotation, "reference_member": reference_member,
                       "reference_source_sha256": reference_source_sha256,
                       "original_label_path": original_label_path,
                       "reference_path": "", "reference_status": "NON_COMPATIBLE" if key != "agri" else "A_VERIFIER",
                       "visual_observations": "Inspection visuelle en attente"}
                previous = next((r for r in records if r["image_id"] == image_id), None)
                if (previous and previous["prepared_sha256"] == row["prepared_sha256"]
                        and previous.get("reference_source_sha256", "") == reference_source_sha256):
                    for column in ["reference_path", "reference_sha256", "reference_status", "annotation_scope",
                                   "visual_observations", "orientation", "reference_review", "review_date",
                                   "annotation_prepared_sha256", "annotation_values", "annotation_dimensions_match",
                                   "annotation_foreground_pct_valid"]:
                        if column in previous:
                            row[column] = previous[column]
                records = [r for r in records if r["image_id"] != image_id] + [row]
                pd.DataFrame(records).to_csv(sources_path, index=False, encoding="utf-8-sig")
                successful += 1
                print(f"  PNG prêt ({rgb.shape[1]} x {rgb.shape[0]}), provenance enregistrée", flush=True)
            if successful < target:
                raise ValueError(f"Seulement {successful}/{target} images exploitables dans {key}.")


def acquire(output: Path = ROOT / "data", only: list[str] | None = None):
    """Complète avec les sources légères vérifiées si une source est inaccessible."""
    failures = []
    failed_keys = set()
    def run(key, extra=0):
        try:
            _acquire_sources(output, [key], extra)
        except (OSError, ValueError, KeyError, zipfile.BadZipFile, cv2.error) as exc:
            failed_keys.add(key)
            failures.append({"dataset": key, "error": str(exc)})
            print(f"Source {key} interrompue : {exc}", flush=True)
    for key in only or DATASETS:
        run(key)
    def count():
        path = output / "sources.csv"
        return len(pd.read_csv(path)) if path.exists() else 0
    if not only:
        for key in ["cofly", "corn"]:
            missing = 10-count()
            if missing <= 0:
                break
            if key not in failed_keys:
                run(key, missing)
    (output / "provenance").mkdir(parents=True, exist_ok=True)
    (output / "provenance/acquisition_status.json").write_text(
        json.dumps({"count": count(), "failures": failures}, ensure_ascii=False, indent=2), encoding="utf-8")
    if (only and failures) or (not only and count() < 10):
        raise RuntimeError("Acquisition incomplète ; voir data/provenance/acquisition_status.json. Les fichiers validés sont conservés.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="+", choices=list(DATASETS))
    parser.add_argument("--output", type=Path, default=ROOT / "data")
    args = parser.parse_args()
    acquire(args.output, args.only)
