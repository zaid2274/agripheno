import io
import zipfile
from unittest.mock import patch

import cv2
import numpy as np
import pytest

from src.acquisition import RemoteZip, cached_member, fetch_range
from scripts.acquire_real_images import prepare_rgb
from scripts.acquire_real_images import acquire
import pandas as pd


def archive_bytes():
    content = io.BytesIO()
    with zipfile.ZipFile(content, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("images/plot.png", b"agricultural-photo-content")
    return content.getvalue()


def test_remote_zip_resumes_and_checks_cache(tmp_path):
    data, calls = archive_bytes(), []

    def fetch(url, start, end, size):
        calls.append((start, end))
        assert size == len(data)
        return data[start:end+1]

    def read_member():
        with zipfile.ZipFile(RemoteZip("https://example.test/data.zip", len(data), tmp_path, fetch)) as archive:
            return cached_member(archive, "images/plot.png", tmp_path / "originals")

    assert read_member() == b"agricultural-photo-content"
    assert calls
    calls.clear()
    assert read_member() == b"agricultural-photo-content"
    assert calls == []
    # Un original local altéré est réextrait depuis les blocs intacts.
    next((tmp_path / "originals").glob("*.original")).write_bytes(b"corrupt")
    assert read_member() == b"agricultural-photo-content"
    # Un bloc altéré est retéléchargé, pas accepté sur sa seule taille.
    block = next(tmp_path.rglob(f"{len(data)-22}-{len(data)-1}.bin"))
    block.write_bytes(b"x" * block.stat().st_size)
    assert read_member() == b"agricultural-photo-content"
    assert calls


def test_archive_corruption_rejected(tmp_path):
    data = bytearray(archive_bytes())
    data[data.index(b"agricultural-photo-content")] ^= 1
    with zipfile.ZipFile(RemoteZip("https://example.test/corrupt.zip", len(data), tmp_path,
                                 lambda u, s, e, n: bytes(data[s:e+1]))) as archive:
        with pytest.raises(zipfile.BadZipFile, match="CRC"):
            cached_member(archive, "images/plot.png", tmp_path / "originals")


@pytest.mark.parametrize("status,content_range,content", [
    (200, "", b"abc"), (206, "bytes 1-3/10", b"abc"),
    (206, "bytes 0-2/11", b"abc"), (206, "bytes 0-2/10", b"ab")])
def test_invalid_http_ranges(status, content_range, content):
    response = io.BytesIO(content)
    response.status = status
    response.headers = {"Content-Range": content_range}
    with patch("src.acquisition.urlopen", return_value=response):
        with pytest.raises(OSError):
            fetch_range("https://example.test/data.zip", 0, 2, 10)


def test_valid_http_range():
    response = io.BytesIO(b"abc")
    response.status = 206
    response.headers = {"Content-Range": "bytes 0-2/10"}
    with patch("src.acquisition.urlopen", return_value=response):
        assert fetch_range("https://example.test/data.zip", 0, 2, 10) == b"abc"


def test_uint16_conversion_uses_common_scale_and_rgb_order():
    bgr = np.array([[[0, 25700, 65535]]], dtype=np.uint16)
    rgb, description = prepare_rgb(bgr)
    np.testing.assert_array_equal(rgb, [[[255, 100, 0]]])
    assert "/257" in description
    with pytest.raises(ValueError):
        prepare_rgb(np.ones((2, 2, 3), dtype=np.float32))


def test_acquisition_fallback_is_explicit_and_reaches_ten(tmp_path):
    calls = []

    def source(output, only, extra=0):
        key = only[0]
        calls.append((key, extra))
        if key == "agri":
            raise OSError("Source temporairement inaccessible")
        path = output / "sources.csv"
        rows = pd.read_csv(path).to_dict("records") if path.exists() else []
        rows = [r for r in rows if not r["image_id"].startswith(key)]
        rows += [{"image_id": f"{key}_{i}"} for i in range((3 if key == "cofly" else 4)+extra)]
        pd.DataFrame(rows).to_csv(path, index=False)

    with patch("scripts.acquire_real_images._acquire_sources", side_effect=source):
        acquire(tmp_path)
    assert len(pd.read_csv(tmp_path / "sources.csv")) == 10
    assert calls == [("cofly", 0), ("corn", 0), ("agri", 0), ("cofly", 3)]
    assert "Source temporairement inaccessible" in (tmp_path / "provenance/acquisition_status.json").read_text(encoding="utf-8")
