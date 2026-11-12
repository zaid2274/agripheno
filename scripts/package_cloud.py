"""Prépare un dossier GitHub/Streamlit Cloud sans environnement ni archives ZIP."""

import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {".venv", "venv", "__pycache__", ".pytest_cache", ".cache", ".git"}


def package_cloud(destination: Path):
    """Copie le projet ; garde les PNG natifs et toutes les attributions."""
    destination = destination.resolve()
    if destination == ROOT or destination.is_relative_to(ROOT):
        raise ValueError("Le dossier de publication doit être extérieur au projet source.")
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Utiliser un dossier de publication neuf ou vide.")
    destination.mkdir(parents=True, exist_ok=True)
    count = 0
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if set(relative.parts) & EXCLUDED or not path.is_file():
            continue
        if path.suffix in {".log", ".pid", ".pyc", ".pyo", ".zip"}:
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        count += 1
    # L'écoute localhost demeure configurée pour l'application locale. Le cloud
    # reçoit son propre fichier, sans imposer de réseau ou port au conteneur.
    (destination / ".streamlit/config.toml").write_text(
        '[browser]\ngatherUsageStats = false\n\n[server]\nheadless = true\n', encoding="utf-8")
    print(f"Dossier prêt pour GitHub : {destination} ({count} fichiers)")
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    package_cloud(args.destination)
