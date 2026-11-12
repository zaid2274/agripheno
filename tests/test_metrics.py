import numpy as np
import pytest
from src.metrics import intersection_over_union, vegetation_coverage


def test_coverage_excludes_invalid_pixels():
    mask = np.array([[1, 1], [0, 1]])
    valid = np.array([[1, 0], [1, 0]])
    assert vegetation_coverage(mask, valid) == 50


@pytest.mark.parametrize("value,expected", [(0, 0), (1, 100), (255, 100)])
def test_coverage_extremes(value, expected):
    assert vegetation_coverage(np.full((2, 2), value)) == expected


def test_no_valid_pixels():
    assert np.isnan(vegetation_coverage(np.ones((2, 2)), np.zeros((2, 2))))


def test_iou_known_intersection():
    assert intersection_over_union(np.array([[1, 1, 0]]), np.array([[0, 1, 1]])) == pytest.approx(1/3)


def test_iou_validity_and_empty_union():
    assert intersection_over_union(np.array([[1, 1]]), np.array([[1, 0]]), np.array([[1, 0]])) == 1
    assert np.isnan(intersection_over_union(np.zeros((2, 2)), np.zeros((2, 2))))
    assert intersection_over_union(np.ones((2, 2)), np.zeros((2, 2))) == 0


@pytest.mark.parametrize("bad", [np.array([]), np.ones((2, 2, 3)), np.array([[0.5]]), np.array([[np.nan]])])
def test_invalid_masks_rejected(bad):
    with pytest.raises(ValueError):
        vegetation_coverage(bad)


def test_shapes_rejected():
    with pytest.raises(ValueError):
        vegetation_coverage(np.zeros((2, 2)), np.zeros((3, 2)))
    with pytest.raises(ValueError):
        intersection_over_union(np.zeros((2, 2)), np.zeros((2, 3)))
