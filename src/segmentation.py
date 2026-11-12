"""Indice Excess Green et segmentation de tableaux RGB uint8."""

import cv2
import numpy as np


def validate_rgb(rgb: np.ndarray) -> None:
    """Exige une image RGB 8 bits, non vide (pas de conversion implicite)."""
    if (not isinstance(rgb, np.ndarray) or rgb.ndim != 3
            or rgb.shape[2] != 3 or rgb.size == 0 or rgb.dtype != np.uint8):
        raise ValueError("Image attendue : tableau RGB uint8 non vide (H, W, 3).")


def excess_green(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Renvoie ExG=2g-r-b et la validité R+G+B>0 ; ExG noir vaut 0.

    r, g, b sont divisés par R+G+B. L'indice appartient à [-1, 2].
    """
    validate_rgb(rgb)
    # Trois buffers 2D remplacent deux copies RGB flottantes : mêmes opérations
    # float32, avec un pic mémoire plus faible pour les grandes images du cloud.
    total = rgb.sum(axis=2, dtype=np.float32)
    valid = total > 0
    exg = np.zeros_like(total)
    channel = np.zeros_like(total)
    np.divide(rgb[..., 1], total, out=exg, where=valid)
    exg *= 2
    for index in (0, 2):
        np.divide(rgb[..., index], total, out=channel, where=valid)
        exg -= channel
    return exg, valid


def binary_mask(mask: np.ndarray) -> np.ndarray:
    """Accepte uniquement les masques 2D booléens ou codés 0/1/255."""
    array = np.asarray(mask)
    if array.ndim != 2 or array.size == 0:
        raise ValueError("Le masque doit être 2D et non vide.")
    if not np.isin(array, [0, 1, 255]).all():
        raise ValueError("Le masque doit contenir uniquement 0, 1 ou 255.")
    return array != 0


def clean_mask(mask: np.ndarray, valid: np.ndarray, kernel_size: int = 3,
               iterations: int = 1) -> np.ndarray:
    """Ouverture puis fermeture elliptiques ; réexclut les pixels invalides."""
    mask, valid = binary_mask(mask), binary_mask(valid)
    if mask.shape != valid.shape:
        raise ValueError("Masque et validité doivent avoir la même forme.")
    if (not isinstance(kernel_size, int) or kernel_size < 1 or kernel_size % 2 == 0
            or not isinstance(iterations, int) or iterations < 1):
        raise ValueError("Noyau impair positif et itérations entières positives requis.")
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    result = (mask & valid).astype(np.uint8)
    for operation in (cv2.MORPH_OPEN, cv2.MORPH_CLOSE):
        result = cv2.morphologyEx(result, operation, kernel, iterations=iterations,
                                  borderType=cv2.BORDER_CONSTANT, borderValue=0)
        result[~valid] = 0
    return result.astype(bool)


def segment(rgb: np.ndarray, threshold: float = 0.1, *, cleanup: bool = False,
            kernel_size: int = 3, iterations: int = 1
            ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Seuil strict ExG > threshold, puis nettoyage optionnel."""
    if not np.isfinite(threshold) or not -1 <= threshold <= 2:
        raise ValueError("Le seuil ExG doit être fini et compris entre -1 et 2.")
    exg, valid = excess_green(rgb)
    mask = (exg > threshold) & valid
    if cleanup:
        mask = clean_mask(mask, valid, kernel_size, iterations)
    return exg, mask, valid


def overlay(rgb: np.ndarray, mask: np.ndarray, alpha: float = 0.45) -> np.ndarray:
    """Superpose du magenta à la végétation détectée sans changer les autres pixels."""
    validate_rgb(rgb)
    mask = binary_mask(mask)
    if mask.shape != rgb.shape[:2] or not np.isfinite(alpha) or not 0 <= alpha <= 1:
        raise ValueError("Forme du masque ou transparence invalide.")
    result = rgb.copy()
    result[mask] = np.rint((1-alpha) * rgb[mask] + alpha * np.array([255, 0, 255])).astype(np.uint8)
    return result
