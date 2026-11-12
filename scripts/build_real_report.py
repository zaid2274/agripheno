"""Reproduit le rapport et les figures hors ligne, avec le pipeline de Streamlit."""

import argparse
import json
from pathlib import Path
import textwrap

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.analysis import Settings, analyze_real, load_real_catalog
from src.segmentation import overlay

ROOT = Path(__file__).resolve().parents[1]


def small(image, max_side=1000):
    factor = min(1., max_side/max(image.shape[:2]))
    return cv2.resize(image, (max(1, round(image.shape[1]*factor)), max(1, round(image.shape[0]*factor))), interpolation=cv2.INTER_NEAREST)


def contact_sheet(root: Path = ROOT):
    """Planche des originaux préparés pour la revue visuelle, sans inventer de labels."""
    catalog = load_real_catalog(root / "data")
    if not catalog:
        raise ValueError("Aucune image réelle installée.")
    figure, axes = plt.subplots((len(catalog)+2)//3, 3, figsize=(15, 3.7*((len(catalog)+2)//3)), squeeze=False)
    for ax in axes.flat:
        ax.set_axis_off()
    for ax, meta in zip(axes.flat, catalog):
        picture = cv2.imdecode(np.frombuffer((root / "data" / meta["image_path"]).read_bytes(), np.uint8), cv2.IMREAD_COLOR)
        ax.imshow(small(cv2.cvtColor(picture, cv2.COLOR_BGR2RGB)))
        ax.set_title(f"{meta['image_id']} · {meta['dataset'][:25]}", fontsize=9)
    figure.suptitle("AgriPheno — photographies RGB réelles acquises par drone", fontsize=15)
    figure.tight_layout()
    folder = root / "docs/figures"
    folder.mkdir(parents=True, exist_ok=True)
    figure.savefig(folder / "real_drone_contact_sheet.jpg", dpi=110)
    plt.close(figure)


def markdown_table(frame):
    """Petit export Markdown sans ajouter tabulate aux dépendances."""
    def cell(value):
        if isinstance(value, (float, np.floating)):
            return "—" if np.isnan(value) else f"{value:.3f}"
        return str(value).replace("|", "/").replace("\n", " ")
    return "\n".join(["| " + " | ".join(frame.columns) + " |",
                      "| " + " | ".join(["---"]*len(frame.columns)) + " |"] +
                     ["| " + " | ".join(cell(v) for v in row) + " |" for row in frame.itertuples(index=False, name=None)])


def build_report(root: Path = ROOT):
    data, docs = root / "data", root / "docs"
    catalog = load_real_catalog(data)
    if len(catalog) != 10 or any(m.get("visual_observations", "").startswith("Inspection visuelle en attente") for m in catalog):
        raise ValueError("Le rapport final exige dix images revues visuellement.")
    rows = []
    folder = docs / "figures"
    folder.mkdir(parents=True, exist_ok=True)
    for meta in catalog:
        result = analyze_real(data, meta)
        rows.append(result.row)
        if result.rgb is None:
            raise ValueError(f"Image invalide dans le jeu final : {meta['image_id']}")
        views = [(small(result.rgb), "RGB"), (small(result.mask.astype(np.uint8)*255), "Prédiction ExG > 0,10"),
                 (small(overlay(result.rgb, result.mask)), "Superposition")]
        if result.reference is not None:
            views.append((small(result.reference.astype(np.uint8)*255), "Référence fournie"))
        figure, axes = plt.subplots(1, len(views), figsize=(4*len(views), 4.5))
        for ax, (picture, title) in zip(axes, views):
            ax.imshow(picture, cmap="gray", vmin=0, vmax=255)
            ax.set_title(title)
            ax.set_axis_off()
        figure.suptitle(f"{meta['image_id']} · couverture apparente {result.row['couverture_pct']:.2f} %")
        credit = f"{meta['authors']} | DOI:{meta['doi']} | CC BY 4.0 https://creativecommons.org/licenses/by/4.0/ | Conversion RGB, masque et superposition : AgriPheno."
        figure.text(0.01, 0.01, textwrap.fill(credit, width=150), fontsize=6)
        figure.tight_layout(rect=(0, 0.15, 1, 0.96))
        figure.savefig(folder / f"{meta['image_id']}_analysis.jpg", dpi=100)
        plt.close(figure)
        if meta["image_id"].startswith("agri_") and meta.get("original_label_path"):
            label = cv2.imdecode(np.frombuffer((data / meta["original_label_path"]).read_bytes(), np.uint8), cv2.IMREAD_UNCHANGED)
            figure, axes = plt.subplots(1, 2, figsize=(12, 4.5))
            axes[0].imshow(small(result.rgb))
            axes[0].set_title("RGB fourni")
            axes[1].imshow(small(label), cmap="gray", vmin=0, vmax=255)
            axes[1].set_title("Masque source — cible non compatible")
            for ax in axes:
                ax.set_axis_off()
            figure.text(0.01, 0.01, textwrap.fill(credit, width=150), fontsize=6)
            figure.tight_layout(rect=(0, 0.15, 1, 1))
            figure.savefig(folder / f"{meta['image_id']}_reference_review.jpg", dpi=100)
            plt.close(figure)
        del result
    frame = pd.DataFrame(rows)
    (data / "results").mkdir(exist_ok=True)
    frame.to_csv(data / "results/real_drone_results.csv", index=False, encoding="utf-8-sig", float_format="%.6f")
    sensitivity = []
    for threshold in [0.0, 0.2]:
        for meta in catalog:
            result = analyze_real(data, meta, Settings(threshold=threshold))
            sensitivity.append({"image_id": meta["image_id"], "seuil_exg": threshold, "couverture_pct": result.row["couverture_pct"]})
            del result
    sensitivity += [{"image_id": r["image_id"], "seuil_exg": 0.1, "couverture_pct": r["couverture_pct"]} for r in rows]
    pd.DataFrame(sensitivity).sort_values(["image_id", "seuil_exg"]).to_csv(data / "results/real_drone_thresholds.csv", index=False, float_format="%.6f")
    figure, ax = plt.subplots(figsize=(10, 4))
    ax.bar(frame.image_id, frame.couverture_pct, color="#31834b")
    ax.set(ylabel="Couverture végétale apparente (%)", ylim=(0, 100))
    ax.tick_params(axis="x", labelrotation=35)
    figure.tight_layout()
    figure.savefig(folder / "real_drone_coverage.png", dpi=150)
    plt.close(figure)
    contact_sheet(root)
    source_lines = []
    for dataset in sorted({m["dataset"] for m in catalog}):
        meta = next(m for m in catalog if m["dataset"] == dataset)
        source_lines.append(f"- [{dataset}]({meta['dataset_url']}) — {meta['authors']}. {meta['drone']}. Licence [{meta['license']}]({meta['license_url']}). Attribution obligatoire, transformations indiquées dans le catalogue.")
    table = frame[["image_id", "couverture_pct", "couverture_reference_pct", "erreur_couverture_pp", "iou", "f1", "evaluation"]]
    details = []
    for meta in catalog:
        details.append(f"### {meta['image_id']}\n\n{meta['visual_observations']}\n\nTransformation : {meta['transformations']}. Annotations : {meta['annotation_scope']}. {meta.get('reference_review', '')}\n\n![RGB, masque et superposition](figures/{meta['image_id']}_analysis.jpg)\n")
        if meta["image_id"].startswith("agri_") and meta.get("original_label_path"):
            details.append(f"![Audit du masque fourni, blanc également sur le sol nu](figures/{meta['image_id']}_reference_review.jpg)\n")
    compatible = int(frame.iou.notna().sum())
    evaluation_note = (f"{compatible} image(s) disposent d'une IoU définie contre une référence compatible."
                       if compatible else "**Aucune des dix images ne dispose d'une référence validée de végétation totale. Aucun score IoU/F1 terrain n'est donc publié pour ce jeu.** Les masques fournis ont été examinés ; leur présence dans un dépôt ne garantit pas qu'ils annotent la cible recherchée.")
    validation_path = docs / "validation.json"
    validation = json.loads(validation_path.read_text(encoding="utf-8")) if validation_path.exists() else {}
    validation_note = "\n\n## Vérification logicielle\n\n" + (
        f"Recette du {validation['date']} : {validation['pytest']}. {validation['pip_check']}. {validation['offline_application']} {validation['limits']}\n"
        if validation else "Exécuter `python -m pytest -q` pour vérifier le logiciel dans votre environnement.\n")
    text = """# AgriPheno : dix images RGB réelles de drone

## Objectif et protocole

Ce rapport décrit un échantillon pédagogique choisi pour une démonstration d'entretien, pas un benchmark représentatif. Les images viennent de photographies RGB de drone ; aucune image satellite, terrestre, artificielle ou composition multispectrale n'est utilisée. Les tuiles ne représentent pas nécessairement une parcelle entière. La sélection a été effectuée dans l'ordre des identifiants, avant tout examen des scores. Le catalogue permet d'identifier chaque photographie source ; des vues d'un même vol restent corrélées et ne sont pas dix essais indépendants.

Le calcul est exactement celui de Streamlit (`src.analysis`) : conversion RGB documentée ; S=R+G+B ; r=R/S, g=G/S, b=B/S ; ExG=2g−r−b ; végétation si ExG>0,10. Le nettoyage morphologique est désactivé pour tous les résultats principaux. Les pixels exactement noirs sont exclus de la couverture et de l'évaluation. Les pixels sombres non noirs restent valides. La couverture est le pourcentage de pixels valides classés végétation.

IoU=TP/(TP+FP+FN) et F1=2TP/(2TP+FP+FN), calculés sur la même zone valide, uniquement avec une référence de végétation compatible et vérifiée. Les deux métriques sont indéfinies si les deux masques sont vides. Les annotations d'adventices seules ou les boîtes ne constituent pas une vérité terrain de végétation totale. Une référence fournie peut être imparfaite : une inspection visuelle ne prouve pas son exactitude agronomique ni son indépendance.

## Sources et réutilisation

""" + "\n".join(source_lines) + """

Les licences sont vérifiées depuis les métadonnées des dépôts, conservées dans `data/provenance/`. Le catalogue `data/sources.csv` contient les auteurs, DOI, URLs exactes, membres ZIP, date HTTP d'accès, SHA-256 des fichiers source et préparés, dimensions, conversions et commentaires de revue. Les archives originales et les blocs HTTP sont conservés dans un cache local ignoré par Git. Les membres sont extraits sélectivement avec validation HTTP Range et CRC ZIP.

## Résultats observés

Paramètres communs : seuil 0,10 ; aucune morphologie ; aucune optimisation sur les références. Les couvertures sont des pourcentages ; l'erreur de couverture est en points de pourcentage, signée prédiction moins référence. IoU et F1 sont des fractions entre 0 et 1. Un tiret indique une métrique absente ou indéfinie. Les décimales sont des résultats numériques, pas une garantie de précision scientifique.

""" + evaluation_note + "\n\n" + markdown_table(table) + """

![Comparaison des couvertures](figures/real_drone_coverage.png)

Les résultats complets sont dans [le CSV](../data/results/real_drone_results.csv). La [sensibilité au seuil](../data/results/real_drone_thresholds.csv) compare 0,00, 0,10 et 0,20, avec tous les autres paramètres fixes : elle montre la dépendance au réglage sans choisir un seuil gagnant. Les résultats recalculés dans Streamlit peuvent différer si l'utilisateur change les paramètres.

## Revue visuelle par image

Les descriptions ci-dessous sont des observations humaines sur ce jeu installé. Les mentions de couleur, sol et ombre ne sont pas des diagnostics d'espèce, de maladie ou de stress.

""" + "\n".join(details) + """
## Limites et améliorations

- ExG sépare des couleurs, sans reconnaître les cultures : végétation cultivée et adventices peuvent toutes deux être incluses ; des objets ou sols verdâtres peuvent créer des faux positifs. Les feuilles pâles, jaunies, desséchées et certains pixels d'ombre peuvent être manqués.
- La normalisation réduit l'effet d'un facteur lumineux identique sur RGB. Elle ne corrige pas une balance des blancs variable, les ombres colorées, le sol humide, les saturations ou la compression. Un seuil n'est pas universel.
- La morphologie peut supprimer de petites feuilles et combler des espaces. Son noyau est en pixels : la résolution physique et la hauteur de vol doivent être prises en compte avant une comparaison entre acquisitions.
- Exclure les pixels noirs ne résout pas l'ombre. La vue, le cadrage, l'échelle, la présence d'inter-rangs et les organes masqués influencent la couverture. Des images de plusieurs capteurs ne sont pas radiométriquement interchangeables.
- La couverture apparente n'est une mesure directe ni de biomasse, ni de rendement, ni de LAI, ni de stress hydrique. Les observations de couleur ne permettent pas de conclure à une carence ou un stress.
- Une amélioration RGB serait une annotation indépendante avec un protocole clair, des régions d'intérêt de parcelles, une maîtrise de l'acquisition, puis une validation sur des champs et dates distincts. Des méthodes adaptatives de seuillage ou un modèle appris pourraient ensuite être comparés sur un jeu réservé.
- Un capteur multispectral disposant de rouge et de proche infrarouge permettrait NDVI=(NIR−R)/(NIR+R), après alignement des bandes et calibration radiométrique en réflectance, avec gestion du dénominateur nul. Le NDVI n'est jamais calculé ici. Il peut fournir une information complémentaire, mais reste sensible au sol et peut saturer sur les couverts denses ; il ne donne pas directement un diagnostic de stress, de rendement ou de LAI sans validation spécifique.

Références pour cette extension : [définition du NDVI, USGS](https://www.usgs.gov/landsat-missions/landsat-normalized-difference-vegetation-index) ; [sensibilité au sol et saturation, USGS](https://www.usgs.gov/special-topics/remote-sensing-phenology/science/ndvi-foundation-remote-sensing-phenology). Ces pages expliquent l'indice ; aucune image satellitaire de ces sources n'est intégrée au jeu AgriPheno.

## Expliquer le code à l'entretien

1. `scripts.acquire_real_images` télécharge seulement les membres nécessaires des ZIP, contrôle la licence et conserve la provenance. La conversion en PNG prépare les photos sans inventer de contenu.
2. `src.segmentation` convertit les canaux en flottants, normalise RGB, calcule ExG et applique le seuil. La morphologie optionnelle agit sur le masque binaire.
3. `src.analysis` appelle ce moteur, compte les pixels, produit les contrôles qualité et autorise ou refuse les références selon leur cible. `src.metrics` calcule couverture, IoU et F1.
4. `src.ui` affiche ces résultats et les exporte. Le même pipeline alimente ce rapport : il n'existe pas de deuxième formule de couverture réservée à la démonstration.
5. Pour commenter un résultat : montrer le cadrage et le masque, annoncer les paramètres et la couverture, examiner les faux positifs/négatifs visibles puis expliquer ce que les annotations permettent réellement de vérifier.

## Reproduire hors ligne

Depuis la racine : `python -m scripts.build_real_report`, puis `python -m streamlit run app.py`. Les fichiers préparés, leurs références et le catalogue suffisent ; le rapport et l'application n'accèdent pas au réseau. Pour réacquérir les originaux, utiliser `python -m scripts.acquire_real_images` avec Internet. Les tests automatiques utilisent des réponses réseau simulées.
"""
    docs.mkdir(exist_ok=True)
    (docs / "rapport_images_reelles.md").write_text(text + validation_note, encoding="utf-8")
    print(frame[["image_id", "couverture_pct", "iou", "f1", "evaluation"]].to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contact-only", action="store_true")
    args = parser.parse_args()
    contact_sheet() if args.contact_only else build_report()
