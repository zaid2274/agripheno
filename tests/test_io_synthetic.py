import cv2
import numpy as np
import pytest
from scripts.generate_synthetic import generate_dataset, make_scene
from src.io_utils import decode_reference, decode_rgb
from src.metrics import vegetation_coverage


def encoded(image, extension=".png"):
    ok, buffer = cv2.imencode(extension, image)
    assert ok
    return buffer.tobytes()


@pytest.mark.parametrize("extension", [".png", ".jpg"])
def test_color_channel_order(extension):
    bgr = np.full((20, 20, 3), [10, 30, 200], dtype=np.uint8)
    rgb = decode_rgb(encoded(bgr, extension))
    np.testing.assert_allclose(rgb[0, 0], [200, 30, 10], atol=3)


@pytest.mark.parametrize("content", [b"", b"not an image"])
def test_unreadable(content):
    with pytest.raises(ValueError):
        decode_rgb(content)


@pytest.mark.parametrize("image", [np.zeros((3, 4), dtype=np.uint8), np.zeros((3, 4, 4), dtype=np.uint8), np.zeros((3, 4, 3), dtype=np.uint16)])
def test_unsupported_images(image):
    with pytest.raises(ValueError):
        decode_rgb(encoded(image))


def test_reference_requires_binary_monochrome():
    np.testing.assert_array_equal(decode_reference(encoded(np.array([[0, 255]], dtype=np.uint8))), [[False, True]])
    with pytest.raises(ValueError):
        decode_reference(encoded(np.array([[0, 128]], dtype=np.uint8)))


def test_synthetic_reproducibility_and_manifest(tmp_path):
    rgb1, truth1 = make_scene(42, 20)
    rgb2, truth2 = make_scene(42, 20)
    np.testing.assert_array_equal(rgb1, rgb2)
    np.testing.assert_array_equal(truth1, truth2)
    manifest = generate_dataset(tmp_path)
    assert len(manifest) == 7
    for row in manifest.to_dict("records"):
        rgb = decode_rgb((tmp_path / "images" / row["image"]).read_bytes())
        truth = decode_reference((tmp_path / "masks" / row["image"]).read_bytes())
        coverage = vegetation_coverage(truth, rgb.sum(axis=2) > 0)
        if np.isnan(row["couverture_reference_pct"]):
            assert np.isnan(coverage)
        else:
            assert coverage == pytest.approx(row["couverture_reference_pct"])
