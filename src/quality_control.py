"""Alertes techniques, sans décision agronomique automatique."""

import numpy as np
from src.segmentation import binary_mask, validate_rgb


def quality_flags(rgb: np.ndarray, mask: np.ndarray, valid: np.ndarray,
                  min_side: int = 256) -> list[str]:
    """Signale petite résolution, absence de validité et masques extrêmes."""
    validate_rgb(rgb)
    mask, valid = binary_mask(mask), binary_mask(valid)
    if mask.shape != rgb.shape[:2] or valid.shape != mask.shape:
        raise ValueError("Image et masques doivent être alignés.")
    flags = []
    if min(rgb.shape[:2]) < min_side:
        flags.append("FAIBLE_RESOLUTION")
    count = np.count_nonzero(valid)
    if not count:
        flags.append("AUCUN_PIXEL_VALIDE")
    else:
        vegetation = np.count_nonzero(mask & valid)
        if vegetation == 0:
            flags.append("MASQUE_VIDE")
        elif vegetation == count:
            flags.append("MASQUE_SATURE")
    return flags
