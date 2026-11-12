"""Métriques pixel à pixel ; NaN indique une mesure indéfinie."""

import numpy as np
from src.segmentation import binary_mask


def _aligned(mask: np.ndarray, valid: np.ndarray | None):
    mask = binary_mask(mask)
    valid = np.ones_like(mask) if valid is None else binary_mask(valid)
    if mask.shape != valid.shape:
        raise ValueError("Les masques doivent avoir la même forme.")
    return mask & valid, valid


def vegetation_coverage(mask: np.ndarray, valid: np.ndarray | None = None) -> float:
    """Pourcentage de végétation parmi les seuls pixels valides."""
    selected, valid = _aligned(mask, valid)
    denominator = np.count_nonzero(valid)
    return float(100 * np.count_nonzero(selected) / denominator) if denominator else float("nan")


def intersection_over_union(predicted: np.ndarray, reference: np.ndarray,
                            valid: np.ndarray | None = None) -> float:
    """IoU sur les pixels valides ; union vide => NaN (pas de preuve positive)."""
    predicted, valid = _aligned(predicted, valid)
    reference = binary_mask(reference)
    if reference.shape != predicted.shape:
        raise ValueError("Prédiction et référence doivent avoir la même forme.")
    reference = reference & valid
    union = np.count_nonzero(predicted | reference)
    return float(np.count_nonzero(predicted & reference) / union) if union else float("nan")


def segmentation_f1(predicted: np.ndarray, reference: np.ndarray,
                    valid: np.ndarray | None = None) -> float:
    """F1/Dice = 2 TP / (2 TP + FP + FN) ; deux masques vides => NaN."""
    predicted, valid = _aligned(predicted, valid)
    reference = binary_mask(reference)
    if reference.shape != predicted.shape:
        raise ValueError("Prédiction et référence doivent avoir la même forme.")
    reference = reference & valid
    denominator = np.count_nonzero(predicted) + np.count_nonzero(reference)
    return float(2*np.count_nonzero(predicted & reference)/denominator) if denominator else float("nan")
