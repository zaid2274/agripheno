"""Pipeline commun à Streamlit et aux résultats du rapport, sans interface."""

from dataclasses import dataclass
from pathlib import Path
import hashlib

import numpy as np
import pandas as pd

from src.io_utils import decode_reference, decode_rgb
from src.metrics import intersection_over_union, segmentation_f1, vegetation_coverage
from src.quality_control import quality_flags
from src.segmentation import segment


@dataclass(frozen=True)
class Settings:
    threshold: float = 0.1
    cleanup: bool = False
    kernel_size: int = 3
    iterations: int = 1


@dataclass
class Analysis:
    row: dict
    rgb: np.ndarray | None = None
    exg: np.ndarray | None = None
    mask: np.ndarray | None = None
    reference: np.ndarray | None = None


def analyze_image(name: str, content: bytes, settings: Settings = Settings(), *,
                  source: str = "import_utilisateur", reference: bytes | None = None,
                  metadata: dict | None = None) -> Analysis:
    """Une entrée invalide conserve une ligne ; les références sont contrôlées séparément."""
    meta = metadata or {}
    row = {"image": name, "image_id": meta.get("image_id", Path(name).stem),
           "parcelle": Path(name).stem, "source": source,
           "dataset": meta.get("dataset", ""), "source_url": meta.get("dataset_url", ""),
           "licence": meta.get("license", ""), "attribution": meta.get("attribution", ""),
           "culture": meta.get("crop", ""), "observations_visuelles": meta.get("visual_observations", ""),
           "annotations": meta.get("annotation_scope", ""),
           "seuil_exg": settings.threshold, "nettoyage": settings.cleanup,
           "noyau_px": settings.kernel_size if settings.cleanup else 0,
           "iterations": settings.iterations if settings.cleanup else 0,
           "largeur_px": None, "hauteur_px": None, "pixels_valides": None,
           "pixels_vegetation": None, "couverture_pct": np.nan,
           "couverture_reference_pct": np.nan, "erreur_couverture_pp": np.nan,
           "exg_moyen_valide": np.nan, "iou": np.nan, "f1": np.nan,
           "controle_qualite": "", "evaluation": "SANS_REFERENCE"}
    result = Analysis(row)
    try:
        rgb = decode_rgb(content)
        exg, mask, valid = segment(rgb, settings.threshold, cleanup=settings.cleanup,
                                  kernel_size=settings.kernel_size, iterations=settings.iterations)
        row.update(largeur_px=rgb.shape[1], hauteur_px=rgb.shape[0],
                   pixels_valides=int(valid.sum()), pixels_vegetation=int(mask.sum()),
                   couverture_pct=vegetation_coverage(mask, valid),
                   exg_moyen_valide=float(exg[valid].mean()) if valid.any() else np.nan,
                   controle_qualite=" | ".join(quality_flags(rgb, mask, valid)) or "OK")
        result.rgb, result.exg, result.mask = rgb, exg, mask
        allowed = source != "drone_reel" or (meta.get("reference_status") == "VERIFIEE"
                                             and meta.get("annotation_scope") == "vegetation_totale")
        if not allowed:
            row["evaluation"] = "REFERENCE_NON_COMPATIBLE_OU_NON_VERIFIEE"
        elif reference is not None:
            try:
                ref = decode_reference(reference)
                row["iou"] = intersection_over_union(mask, ref, valid)
                row["f1"] = segmentation_f1(mask, ref, valid)
                row["couverture_reference_pct"] = vegetation_coverage(ref, valid)
                row["erreur_couverture_pp"] = row["couverture_pct"]-row["couverture_reference_pct"]
                row["evaluation"] = "OK" if np.isfinite(row["iou"]) else "IOU_INDEFINIE"
                result.reference = ref
            except ValueError as exc:
                row["evaluation"] = f"REFERENCE_INVALIDE : {exc}"
        elif meta.get("reference_path"):
            row["evaluation"] = "REFERENCE_MANQUANTE"
    except ValueError as exc:
        row["controle_qualite"] = f"IMAGE_REJETEE : {exc}"
    return result


def load_real_catalog(data: Path) -> list[dict]:
    """Lit le catalogue ; aucun accès réseau, aucune découverte par glob implicite."""
    path = data / "sources.csv"
    if not path.exists():
        return []
    frame = pd.read_csv(path, keep_default_na=False)
    if not {"image_id", "image_path", "dataset", "license", "prepared_sha256"}.issubset(frame.columns):
        raise ValueError("Catalogue sources.csv incomplet.")
    if frame.image_id.duplicated().any():
        raise ValueError("Identifiants dupliqués dans sources.csv.")
    return frame.to_dict("records")


def _local_bytes(data: Path, relative: str) -> bytes:
    path = (data / relative).resolve()
    if not path.is_relative_to(data.resolve()):
        raise ValueError("Chemin hors du dossier de données.")
    return path.read_bytes()


def analyze_real(data: Path, meta: dict, settings: Settings = Settings()) -> Analysis:
    """Vérifie l'intégrité du PNG préparé et ne charge que les références autorisées."""
    name = Path(meta["image_path"]).name
    try:
        content = _local_bytes(data, meta["image_path"])
        if hashlib.sha256(content).hexdigest() != meta["prepared_sha256"]:
            raise ValueError("SHA-256 de l'image différent du catalogue.")
    except (OSError, ValueError) as exc:
        result = analyze_image(name, b"", settings, source="drone_reel", metadata=meta)
        result.row["controle_qualite"] = f"IMAGE_REJETEE : {exc}"
        return result
    reference = None
    reference_error = None
    if meta.get("reference_path") and meta.get("reference_status") == "VERIFIEE":
        try:
            reference = _local_bytes(data, meta["reference_path"])
            if hashlib.sha256(reference).hexdigest() != meta.get("reference_sha256"):
                raise ValueError("SHA-256 de la référence différent du catalogue.")
        except (OSError, ValueError) as exc:
            reference_error = str(exc)
            reference = None
    result = analyze_image(name, content, settings, source="drone_reel", reference=reference, metadata=meta)
    if reference_error:
        result.row["evaluation"] = f"REFERENCE_INVALIDE : {reference_error}"
    return result
