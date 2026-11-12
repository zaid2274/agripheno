"""Lecture explicite des images et références, sans dépendance Streamlit."""

import cv2
import numpy as np
from src.segmentation import binary_mask


def _decode(content: bytes) -> np.ndarray:
    if not content:
        raise ValueError("Fichier vide ou illisible.")
    try:
        image = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    except cv2.error as exc:
        raise ValueError("Image illisible.") from exc
    if image is None:
        raise ValueError("Image illisible.")
    if image.shape[0] * image.shape[1] > 25_000_000:
        raise ValueError("Image trop grande : limite de traitement de 25 mégapixels.")
    return image


def decode_rgb(content: bytes) -> np.ndarray:
    """Lit une image couleur 8 bits ; refuse gris, alpha et 16 bits.

    IMREAD_UNCHANGED conserve l'orientation encodée, sans rotation EXIF.
    """
    image = _decode(content)
    if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Une image couleur RGB 8 bits sans canal alpha est requise.")
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def decode_reference(content: bytes) -> np.ndarray:
    """Référence PNG monochrome binaire 0/1/255, sans seuil implicite."""
    return binary_mask(_decode(content))
