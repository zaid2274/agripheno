import hashlib

import cv2
import numpy as np
import pytest

from src.analysis import analyze_image, analyze_real, load_real_catalog
from src.metrics import segmentation_f1


def png(array):
    success, content = cv2.imencode(".png", array)
    assert success
    return content.tobytes()


def test_f1_known_values_and_validity():
    assert segmentation_f1(np.array([[1, 1, 0]]), np.array([[0, 1, 1]])) == 0.5
    assert segmentation_f1(np.array([[1, 1]]), np.array([[1, 0]]), np.array([[1, 0]])) == 1
    assert segmentation_f1(np.ones((2, 2)), np.zeros((2, 2))) == 0
    assert np.isnan(segmentation_f1(np.zeros((2, 2)), np.zeros((2, 2))))
    assert np.isnan(segmentation_f1(np.ones((2, 2)), np.ones((2, 2)), np.zeros((2, 2))))
    with pytest.raises(ValueError):
        segmentation_f1(np.ones((2, 2)), np.ones((3, 2)))


@pytest.mark.parametrize("meta", [{}, {"reference_status": "VERIFIEE", "annotation_scope": "adventices_uniquement"},
                                  {"reference_status": "A_VERIFIER", "annotation_scope": "vegetation_totale"}])
def test_real_references_require_matching_semantics(meta):
    rgb = png(np.full((3, 3, 3), [0, 255, 0], dtype=np.uint8))
    ref = png(np.full((3, 3), 255, dtype=np.uint8))
    result = analyze_image("test.png", rgb, source="drone_reel", reference=ref, metadata=meta)
    assert result.row["couverture_pct"] == 100
    assert np.isnan(result.row["iou"])
    assert result.reference is None


def test_verified_reference_and_alignment():
    rgb = png(np.full((3, 3, 3), [0, 255, 0], dtype=np.uint8))
    meta = {"reference_status": "VERIFIEE", "annotation_scope": "vegetation_totale"}
    result = analyze_image("a.png", rgb, source="drone_reel", reference=png(np.full((3, 3), 255, np.uint8)), metadata=meta)
    assert result.row["iou"] == result.row["f1"] == 1
    assert result.row["erreur_couverture_pp"] == 0
    result = analyze_image("a.png", rgb, source="drone_reel", reference=png(np.full((4, 3), 255, np.uint8)), metadata=meta)
    assert "REFERENCE_INVALIDE" in result.row["evaluation"]


def test_real_missing_file_and_checksum(tmp_path):
    meta = {"image_id": "plot", "image_path": "real_drone_images/plot.png", "prepared_sha256": "bad"}
    assert "IMAGE_REJETEE" in analyze_real(tmp_path, meta).row["controle_qualite"]
    (tmp_path / "real_drone_images").mkdir()
    image = png(np.full((2, 2, 3), 60, np.uint8))
    (tmp_path / meta["image_path"]).write_bytes(image)
    assert "SHA-256" in analyze_real(tmp_path, meta).row["controle_qualite"]
    meta["prepared_sha256"] = hashlib.sha256(image).hexdigest()
    assert analyze_real(tmp_path, meta).row["couverture_pct"] == 0
    assert load_real_catalog(tmp_path) == []
