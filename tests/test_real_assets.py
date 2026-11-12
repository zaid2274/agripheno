"""Contrôle hors ligne des assets distribués ; ignoré si le jeu n'est pas installé."""

import hashlib
from pathlib import Path

import pytest

from src.analysis import load_real_catalog
from src.io_utils import decode_rgb

DATA = Path(__file__).resolve().parents[1] / "data"


def test_installed_assets_provenance_and_integrity():
    catalog = load_real_catalog(DATA)
    if not catalog:
        pytest.skip("Le jeu réel facultatif n'est pas installé.")
    assert len(catalog) == 10
    for meta in catalog:
        assert meta["license"] == "CC BY 4.0"
        assert meta["authors"] and meta["attribution"] and meta["archive_member"]
        assert meta["dataset_url"].startswith("https://zenodo.org/records/")
        assert meta["visual_observations"] and "en attente" not in meta["visual_observations"]
        content = (DATA / meta["image_path"]).read_bytes()
        assert hashlib.sha256(content).hexdigest() == meta["prepared_sha256"]
        rgb = decode_rgb(content)
        assert rgb.shape[:2] == (int(meta["height"]), int(meta["width"]))
        if meta["reference_status"] == "VERIFIEE":
            assert meta["annotation_scope"] == "vegetation_totale"
            reference = (DATA / meta["reference_path"]).read_bytes()
            assert hashlib.sha256(reference).hexdigest() == meta["reference_sha256"]
        else:
            assert not meta["reference_path"]
