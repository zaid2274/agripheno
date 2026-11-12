"""Interface Streamlit ; les calculs sont exclusivement dans src.analysis."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

from src.analysis import Settings, analyze_image, analyze_real, load_real_catalog
from src.segmentation import overlay

ROOT = Path(__file__).resolve().parents[1]
MODES = ["Importer mes images", "Utiliser les scènes synthétiques de démonstration",
         "Tester avec des images réelles de drone"]


def main() -> None:
    st.set_page_config(page_title="AgriPheno · Couverture RGB", page_icon="🌱", layout="wide")
    st.title("🌱 AgriPheno")
    st.write("Couverture végétale apparente à partir d’images RGB et de l’indice Excess Green.")
    st.caption("Prototype pédagogique · La couverture seule ne mesure ni LAI, ni biomasse, ni rendement, ni stress hydrique.")
    with st.sidebar:
        st.header("Segmentation")
        threshold = st.slider("Seuil ExG (strictement supérieur)", -1.0, 2.0, 0.10, 0.01)
        cleanup = st.checkbox("Nettoyage morphologique", value=False, key="cleanup")
        kernel = st.select_slider("Taille du noyau (pixels)", options=[1, 3, 5, 7, 9], value=3, disabled=not cleanup)
        iterations = st.number_input("Itérations", min_value=1, max_value=5, value=1, disabled=not cleanup)
        alpha = st.slider("Opacité de la superposition", 0.0, 1.0, 0.45, 0.05)
        st.caption("ExG = 2g − r − b ; r, g, b = R, G, B / (R+G+B). Les pixels noirs sont exclus.")
    settings = Settings(threshold, cleanup, int(kernel), int(iterations))
    mode = st.radio("Source des images", MODES, key="source_mode")
    demo, real = mode == MODES[1], mode == MODES[2]
    inputs, references, catalog = [], {}, []
    if real:
        st.info("Photographies RGB acquises par drone. Les tuiles ne représentent pas nécessairement une parcelle entière ; ce petit échantillon n’est pas un benchmark représentatif.")
        try:
            catalog = load_real_catalog(ROOT / "data")
        except (ValueError, OSError) as exc:
            st.error(f"Catalogue inaccessible : {exc}")
            return
        if not catalog:
            st.info("Aucune donnée réelle installée. Exécutez : python -m scripts.acquire_real_images")
            return
        chosen = st.multiselect("Images réelles à comparer", [m["image_id"] for m in catalog],
                                default=[m["image_id"] for m in catalog], key="real_images")
        catalog = [m for m in catalog if m["image_id"] in chosen]
        with st.expander("Sources, licences et transformations"):
            st.dataframe(pd.DataFrame(catalog), hide_index=True)
            st.caption("CC BY 4.0 : créditer les auteurs, conserver le lien de licence et indiquer les transformations. Les attributions sont également incluses dans le CSV.")
        st.caption("Les boîtes de détection et masques d’adventices seuls ne permettent pas d’évaluer la végétation totale. Les références non vérifiées ne produisent aucun score.")
    elif demo:
        st.warning("DONNÉES SYNTHÉTIQUES : elles vérifient le fonctionnement du logiciel, sans établir de performance sur le terrain.")
        inputs = [(p.name, p.read_bytes()) for p in sorted((ROOT / "data/images").glob("synthetic_*.png"))]
        references = {p.stem: p.read_bytes() for p in sorted((ROOT / "data/masks").glob("synthetic_*.png"))}
        if not inputs:
            st.info("Générez les données avec : python -m scripts.generate_synthetic")
    else:
        uploads = st.file_uploader("Images RGB PNG / JPEG (plusieurs fichiers possibles)", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
        masks = st.file_uploader("Références facultatives : végétation totale, PNG monochromes 0/255, mêmes noms de base et dimensions", type=["png"], accept_multiple_files=True)
        inputs = [(f.name, f.getvalue()) for f in uploads]
        for f in masks:
            stem = Path(f.name).stem
            if stem in references:
                st.error(f"Référence ambiguë : {stem}. Gardez un seul masque par nom de base.")
                return
            references[stem] = f.getvalue()
    if not inputs and not catalog:
        st.info("Importez des images, choisissez une démonstration ou sélectionnez des images réelles.")
        return
    stems = [Path(name).stem for name, _ in inputs]
    if len(set(stems)) != len(stems):
        st.error("Les noms de base des images doivent être uniques pour associer les références.")
        return
    unmatched = set(references)-set(stems)
    if unmatched:
        st.warning("Références sans image correspondante : " + ", ".join(sorted(unmatched)))

    def process(identifier):
        if real:
            return analyze_real(ROOT / "data", next(m for m in catalog if m["image_id"] == identifier), settings)
        name, content = next(item for item in inputs if item[0] == identifier)
        return analyze_image(name, content, settings, source="synthetique" if demo else "import_utilisateur",
                             reference=references.get(Path(name).stem))

    identifiers = [m["image_id"] for m in catalog] if real else [name for name, _ in inputs]
    rows, preview_ids = [], []
    with st.spinner("Calcul de la couverture…"):
        for identifier in identifiers:
            result = process(identifier)
            rows.append(result.row)
            if result.rgb is not None:
                preview_ids.append(identifier)
            del result  # Libère les grands tableaux entre deux images.
    frame = pd.DataFrame(rows)
    st.subheader("Résultats par image")
    st.caption("Couverture du cadrage visible. Les observations visuelles proviennent de la revue du jeu installé ; elles ne sont pas un diagnostic automatique.")
    st.dataframe(frame, hide_index=True)
    st.download_button("Télécharger le CSV", frame.to_csv(index=False, na_rep="", float_format="%.6f").encode("utf-8-sig"),
                       "agripheno_results.csv", "text/csv")
    st.caption("Valeur vide = absente ou indéfinie. IoU et F1 sont compris entre 0 et 1. Une alerte de masque vide ou saturé demande une inspection ; elle ne prouve pas une erreur.")
    measured = frame.dropna(subset=["couverture_pct"])
    if not measured.empty:
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.bar(measured["image_id"], measured["couverture_pct"], color="#31834b")
        ax.set(ylabel="Couverture végétale apparente (%)", ylim=(0, 100), xlabel="Image / tuile")
        ax.tick_params(axis="x", labelrotation=35)
        fig.tight_layout()
        st.pyplot(fig)
        plt.close(fig)
    if preview_ids:
        st.subheader("Inspection visuelle")
        selected = st.selectbox("Image à inspecter", preview_ids, key="preview")
        result = process(selected)
        rgb, mask = result.rgb, result.mask
        views = [(rgb, "Image RGB"), (mask.astype(np.uint8)*255, "Masque prédit : végétation en blanc"),
                 (overlay(rgb, mask, alpha), "Superposition : végétation en magenta")]
        if result.reference is not None:
            views.append((result.reference.astype(np.uint8)*255, "Référence fournie et vérifiée"))
        for column, (picture, caption) in zip(st.columns(len(views)), views):
            column.image(picture, caption=caption, width="stretch")
        if real:
            meta = next(m for m in catalog if m["image_id"] == selected)
            st.write(meta.get("visual_observations", ""))
            st.caption(meta.get("attribution", ""))
            st.markdown(f"[Dataset original]({meta['dataset_url']}) · [Licence]({meta['license_url']})")
        with st.expander("Indice ExG du cadrage"):
            fig, ax = plt.subplots(figsize=(7, 4))
            colors = plt.get_cmap("RdYlGn").with_extremes(bad="black")
            index = np.ma.masked_where(result.rgb.sum(axis=2) == 0, result.exg)
            artist = ax.imshow(index, cmap=colors, vmin=-1, vmax=2)
            ax.set_axis_off()
            fig.colorbar(artist, ax=ax, label="ExG (pixels noirs exclus des mesures)")
            st.pyplot(fig)
            plt.close(fig)


if __name__ == "__main__":
    main()
