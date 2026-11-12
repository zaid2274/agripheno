"""Applique les décisions humaines de provenance/visual_review.json aux mêmes pixels.

Ce script ne produit aucune annotation ni décision agronomique automatique.
"""

from email.utils import parsedate_to_datetime
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from src.analysis import load_real_catalog

ROOT = Path(__file__).resolve().parents[1]


def apply_review(root: Path = ROOT):
    data = root / "data"
    review = json.loads((data / "provenance/visual_review.json").read_text(encoding="utf-8"))
    catalog = load_real_catalog(data)
    for meta in catalog:
        decision = review["images"][meta["image_id"]]
        content = (data / meta["image_path"]).read_bytes()
        if hashlib.sha256(content).hexdigest() != decision["prepared_sha256"] or meta["prepared_sha256"] != decision["prepared_sha256"]:
            raise ValueError(f"Image modifiée depuis la revue : {meta['image_id']}")
        meta.update(visual_observations=decision["observations"],
                    reference_review=decision["reference_review"],
                    annotation_scope=decision["annotation_scope"],
                    reference_status=decision["reference_status"], review_date=review["review_date"])
        if meta["reference_status"] != "VERIFIEE":
            meta["reference_path"] = ""
            meta["reference_sha256"] = ""
        meta["access_date"] = parsedate_to_datetime(meta["access_date_http"]).date().isoformat()
        original_label = meta.get("original_label_path") or f"reference_masks/original_labels/{meta['image_id']}.png"
        if decision.get("annotation_prepared_sha256") and not (data / original_label).exists():
            raise ValueError(f"Annotation examinée manquante : {meta['image_id']}")
        if (data / original_label).exists():
            annotation = (data / original_label).read_bytes()
            if hashlib.sha256(annotation).hexdigest() != decision["annotation_prepared_sha256"]:
                raise ValueError(f"Annotation modifiée depuis la revue : {meta['image_id']}")
            meta["original_label_path"] = original_label
            meta["annotation_prepared_sha256"] = decision["annotation_prepared_sha256"]
            label = cv2.imdecode(np.frombuffer(annotation, np.uint8), cv2.IMREAD_UNCHANGED)
            meta["annotation_values"] = json.dumps(np.unique(label).tolist())
            rgb = cv2.imdecode(np.frombuffer(content, np.uint8), cv2.IMREAD_COLOR)
            valid = rgb.sum(axis=2) > 0
            meta["annotation_dimensions_match"] = label.shape == rgb.shape[:2]
            if label.shape == valid.shape:
                meta["annotation_foreground_pct_valid"] = float(100*np.count_nonzero((label > 0) & valid)/valid.sum())
    pd.DataFrame(catalog).to_csv(data / "sources.csv", index=False, encoding="utf-8-sig")
    print(f"Revue appliquée à {len(catalog)} images identiques aux fichiers inspectés.")


if __name__ == "__main__":
    apply_review()
