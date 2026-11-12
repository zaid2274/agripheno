import numpy as np
import pytest
from src.segmentation import clean_mask, excess_green, overlay, segment
from src.quality_control import quality_flags


def test_exg_primary_colors_black_and_gray():
    rgb = np.array([[[255, 0, 0], [0, 255, 0], [0, 0, 255], [0, 0, 0], [60, 60, 60]]], dtype=np.uint8)
    exg, valid = excess_green(rgb)
    np.testing.assert_allclose(exg, [[-1, 2, -1, 0, 0]], atol=1e-7)
    np.testing.assert_array_equal(valid, [[1, 1, 1, 0, 1]])
    _, mask, _ = segment(rgb, threshold=-0.1)
    assert not mask[0, 3]  # Black remains invalid even at negative thresholds.


def test_normalization_and_strict_threshold():
    rgb = np.array([[[20, 40, 20], [40, 80, 40], [60, 60, 60]]], dtype=np.uint8)
    exg, mask, _ = segment(rgb, threshold=0.5)
    np.testing.assert_allclose(exg, [[0.5, 0.5, 0]])
    assert not mask.any()


@pytest.mark.parametrize("rgb", [np.zeros((2, 2)), np.zeros((0, 2, 3), dtype=np.uint8), np.ones((2, 2, 3))])
def test_invalid_rgb(rgb):
    with pytest.raises(ValueError):
        excess_green(rgb)


@pytest.mark.parametrize("threshold", [-2, 3, np.nan, np.inf])
def test_invalid_threshold(threshold):
    with pytest.raises(ValueError):
        segment(np.ones((2, 2, 3), dtype=np.uint8), threshold)


def test_cleanup_removes_isolated_pixel_and_preserves_invalidity():
    mask = np.zeros((15, 15), dtype=bool)
    mask[3:12, 3:12] = True
    mask[1, 1] = True
    valid = np.ones_like(mask)
    valid[7, 7] = False
    result = clean_mask(mask, valid)
    assert not result[1, 1]
    assert not result[7, 7]
    assert result[5, 5]
    with pytest.raises(ValueError):
        clean_mask(mask, valid, kernel_size=2)


def test_overlay_and_quality():
    rgb = np.full((3, 4, 3), 50, dtype=np.uint8)
    mask = np.zeros((3, 4), dtype=bool)
    mask[0, 0] = True
    output = overlay(rgb, mask)
    np.testing.assert_array_equal(output[~mask], rgb[~mask])
    assert output[0, 0, 0] > rgb[0, 0, 0]
    valid = np.ones_like(mask)
    assert quality_flags(rgb, np.zeros_like(mask), valid) == ["FAIBLE_RESOLUTION", "MASQUE_VIDE"]
    assert "MASQUE_SATURE" in quality_flags(rgb, valid, valid)
    assert "AUCUN_PIXEL_VALIDE" in quality_flags(rgb, mask, ~valid)
