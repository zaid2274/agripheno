from pathlib import Path
from unittest.mock import patch

import numpy as np
import cv2
from streamlit.testing.v1 import AppTest

from scripts.generate_synthetic import generate_dataset
import hashlib
import pandas as pd

APP = Path(__file__).resolve().parents[1] / "app.py"


def test_startup():
    app = AppTest.from_file(str(APP)).run(timeout=30)
    assert not app.exception
    assert len(app.dataframe) == 0
    assert app.info


def test_demo_and_morphology():
    generate_dataset(APP.parent / "data")
    app = AppTest.from_file(str(APP)).run(timeout=30)
    app.radio(key="source_mode").set_value("Utiliser les scènes synthétiques de démonstration").run(timeout=30)
    assert not app.exception
    results = app.dataframe[0].value.set_index("parcelle")
    assert len(results) == 7
    assert np.isnan(results.loc["synthetic_black", "couverture_pct"])
    assert results.loc["synthetic_green", "couverture_pct"] == 100
    assert results.loc["synthetic_soil", "couverture_pct"] == 0
    assert "FAIBLE_RESOLUTION" in results.loc["synthetic_small", "controle_qualite"]
    app.checkbox(key="cleanup").check().run(timeout=30)
    assert not app.exception
    assert app.dataframe[0].value["nettoyage"].all()


def test_unreadable_upload_keeps_result_row():
    class Upload:
        name = "broken.png"

        def getvalue(self):
            return b"not a png"

    def uploader(label, **kwargs):
        return [] if label.startswith("Références") else [Upload()]

    with patch("streamlit.file_uploader", side_effect=uploader):
        app = AppTest.from_file(str(APP)).run(timeout=30)
    assert not app.exception
    row = app.dataframe[0].value.iloc[0]
    assert "IMAGE_REJETEE" in row["controle_qualite"]
    assert np.isnan(row["couverture_pct"])


def test_uploaded_rgb_and_reference():
    class Upload:
        name = "plot.png"

        def __init__(self, array):
            success, content = cv2.imencode(".png", array)
            assert success
            self.content = content.tobytes()

        def getvalue(self):
            return self.content

    image = Upload(np.array([[[0, 255, 0], [0, 0, 255]]], dtype=np.uint8))
    reference = Upload(np.array([[255, 0]], dtype=np.uint8))

    def uploader(label, **kwargs):
        return [reference] if label.startswith("Références") else [image]

    with patch("streamlit.file_uploader", side_effect=uploader):
        app = AppTest.from_file(str(APP)).run(timeout=30)
    assert not app.exception
    row = app.dataframe[0].value.iloc[0]
    assert row["couverture_pct"] == 50
    assert row["iou"] == 1
    assert row["evaluation"] == "OK"


def test_real_mode_selection_and_missing_file(tmp_path):
    (tmp_path / "data/real_drone_images").mkdir(parents=True)
    success, content = cv2.imencode(".png", np.full((8, 8, 3), [0, 255, 0], np.uint8))
    assert success
    (tmp_path / "data/real_drone_images/test.png").write_bytes(content.tobytes())
    rows = [{"image_id": key, "image_path": f"real_drone_images/{key}.png",
             "dataset": "Fixture de test", "license": "CC BY 4.0",
             "license_url": "https://creativecommons.org/licenses/by/4.0/",
             "dataset_url": "https://example.test/fixture", "attribution": "Fixture",
             "prepared_sha256": hashlib.sha256(content.tobytes()).hexdigest(),
             "annotation_scope": "boites_adventices", "reference_status": "NON_COMPATIBLE"}
            for key in ["test", "missing"]]
    pd.DataFrame(rows).to_csv(tmp_path / "data/sources.csv", index=False)
    with patch("src.ui.ROOT", tmp_path):
        app = AppTest.from_file(str(APP)).run(timeout=30)
        app.radio(key="source_mode").set_value("Tester avec des images réelles de drone").run(timeout=30)
        assert not app.exception
        results = next(d.value for d in app.dataframe if "couverture_pct" in d.value.columns)
        assert len(results) == 2
        assert results.iloc[0]["couverture_pct"] == 100
        assert np.isnan(results.iloc[0]["iou"])
        assert "IMAGE_REJETEE" in results.iloc[1]["controle_qualite"]
        assert app.get("download_button")
        app.multiselect(key="real_images").set_value(["test"]).run(timeout=30)
        assert not app.exception
        results = next(d.value for d in app.dataframe if "couverture_pct" in d.value.columns)
        assert len(results) == 1
        app.multiselect(key="real_images").set_value([]).run(timeout=30)
        assert not app.exception


def test_real_mode_without_installed_data(tmp_path):
    with patch("src.ui.ROOT", tmp_path):
        app = AppTest.from_file(str(APP)).run(timeout=30)
        app.radio(key="source_mode").set_value("Tester avec des images réelles de drone").run(timeout=30)
        assert not app.exception
        assert any("Aucune donnée réelle" in item.value for item in app.info)
