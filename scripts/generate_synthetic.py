"""Crée des scènes artificielles annotées par construction, pas par ExG.

Exécution depuis la racine : python -m scripts.generate_synthetic --seed 42
"""

import argparse
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def make_scene(seed: int, plants: int, size: tuple[int, int] = (384, 512)
               ) -> tuple[np.ndarray, np.ndarray]:
    """Sol brun, feuilles elliptiques, bruit RGB et gradient d'éclairage."""
    if plants < 0 or min(size) < 32:
        raise ValueError("Nombre de plantes positif ou nul et dimensions >=32 requis.")
    rng = np.random.default_rng(seed)
    height, width = size
    truth = np.zeros(size, dtype=np.uint8)
    rgb = np.broadcast_to([120., 85., 55.], (height, width, 3)).copy()
    for _ in range(plants):
        cx, cy = int(rng.integers(15, width-15)), int(rng.integers(15, height-15))
        leaf = np.zeros(size, dtype=np.uint8)
        cv2.ellipse(leaf, (cx, cy), (int(rng.integers(8, 24)), int(rng.integers(5, 15))),
                    float(rng.uniform(0, 180)), 0, 360, 255, -1)
        truth[leaf > 0] = 255
        # Some pale leaves intentionally overlap the soil's color distribution.
        color = [135., 125., 55.] if rng.random() < 0.18 else [45., 125., 40.]
        rgb[leaf > 0] = color
    lighting = np.linspace(0.55, 1.1, width)[None, :, None]
    rgb = rgb * lighting + rng.normal(0, 9, rgb.shape)
    rgb = np.clip(rgb, 1, 255).astype(np.uint8)
    # Known invalid black border: truth is outside the evaluation area there.
    rgb[:5] = 0
    truth[:5] = 0
    return rgb, truth


def generate_dataset(output: Path = ROOT / "data", seed: int = 42) -> pd.DataFrame:
    """Écrit uniquement les noms synthetic_* connus et un manifeste explicite."""
    images, masks = output / "images", output / "masks"
    images.mkdir(parents=True, exist_ok=True)
    masks.mkdir(parents=True, exist_ok=True)
    scenes = [("sparse", *make_scene(seed, 20)),
              ("medium", *make_scene(seed+1, 90)),
              ("dense", *make_scene(seed+2, 250)),
              ("small", *make_scene(seed+3, 8, (96, 128)))]
    shape = (384, 512)
    scenes.extend([
        ("soil", np.full((*shape, 3), [120, 85, 55], dtype=np.uint8), np.zeros(shape, dtype=np.uint8)),
        ("green", np.full((*shape, 3), [40, 130, 40], dtype=np.uint8), np.full(shape, 255, dtype=np.uint8)),
        ("black", np.zeros((*shape, 3), dtype=np.uint8), np.zeros(shape, dtype=np.uint8)),
    ])
    records = []
    for label, rgb, truth in scenes:
        name = f"synthetic_{label}.png"
        for path, array in [(images / name, cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)), (masks / name, truth)]:
            success, encoded = cv2.imencode(".png", array)
            if not success:
                raise OSError(f"Encodage impossible : {path}")
            path.write_bytes(encoded.tobytes())
        valid = rgb.sum(axis=2) > 0
        count = int(valid.sum())
        records.append({"image": name, "source": "SYNTHETIQUE_NON_REELLE", "seed": seed,
                        "pixels_valides": count,
                        "couverture_reference_pct": 100 * np.count_nonzero((truth > 0) & valid) / count if count else np.nan})
    frame = pd.DataFrame(records)
    frame.to_csv(output / "synthetic_manifest.csv", index=False, float_format="%.6f")
    return frame


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=ROOT / "data")
    args = parser.parse_args()
    print(generate_dataset(args.output, args.seed).to_string(index=False))
