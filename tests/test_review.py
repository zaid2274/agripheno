import hashlib
import json

import pandas as pd
import pytest

from scripts.apply_real_review import apply_review


def reviewed_fixture(root):
    data = root / "data"
    (data / "real_drone_images").mkdir(parents=True)
    (data / "provenance").mkdir()
    # Le contrôle d'empreinte précède tout décodage ; ces octets ne sont pas diffusés comme photo.
    content = b"fixture-bytes-reviewed-by-test"
    path = data / "real_drone_images/plot.png"
    path.write_bytes(content)
    fingerprint = hashlib.sha256(content).hexdigest()
    pd.DataFrame([{"image_id": "plot", "image_path": "real_drone_images/plot.png",
                   "dataset": "Fixture", "license": "CC BY 4.0", "prepared_sha256": fingerprint,
                   "access_date_http": "Thu, 12 Nov 2026 10:00:00 GMT"}]).to_csv(data / "sources.csv", index=False)
    decision = {"prepared_sha256": fingerprint, "observations": "Observation du test",
                "reference_review": "Cible incompatible", "annotation_scope": "adventices_uniquement",
                "reference_status": "NON_COMPATIBLE"}
    review = {"review_date": "2026-11-12", "images": {"plot": decision}}
    (data / "provenance/visual_review.json").write_text(json.dumps(review), encoding="utf-8")
    return path, review


def test_review_cannot_be_reused_on_changed_pixels(tmp_path):
    path, _ = reviewed_fixture(tmp_path)
    path.write_bytes(b"modified-pixels")
    with pytest.raises(ValueError, match="Image modifiée"):
        apply_review(tmp_path)


def test_missing_reviewed_annotation_rejected(tmp_path):
    _, review = reviewed_fixture(tmp_path)
    review["images"]["plot"]["annotation_prepared_sha256"] = "expected-hash"
    (tmp_path / "data/provenance/visual_review.json").write_text(json.dumps(review), encoding="utf-8")
    with pytest.raises(ValueError, match="Annotation examinée manquante"):
        apply_review(tmp_path)


def test_review_preserves_incompatible_target_without_reference(tmp_path):
    reviewed_fixture(tmp_path)
    apply_review(tmp_path)
    row = pd.read_csv(tmp_path / "data/sources.csv", keep_default_na=False).iloc[0]
    assert row["annotation_scope"] == "adventices_uniquement"
    assert row["reference_status"] == "NON_COMPATIBLE"
    assert row["reference_path"] == ""
    assert row["access_date"] == "2026-11-12"
