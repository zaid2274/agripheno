# AgriPheno

Prototype local de phénotypage digital : convertir des images RGB de parcelles en **couverture végétale apparente** avec Excess Green (ExG). Projet pédagogique pour une démonstration en entretien, sans affiliation ni validation par Hiphen.

## Installation et lancement

Python 3.11 recommandé. Dans PowerShell, depuis ce dossier :

```powershell
cd C:\agripheno\agripheno
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m scripts.generate_synthetic --seed 42
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Si `.venv` existe déjà, inutile de le recréer. Ouvrir l'adresse locale affichée par Streamlit (habituellement http://localhost:8501). L'activation de l'environnement n'est pas nécessaire avec ces commandes. Sous Linux/macOS, remplacer `.venv\Scripts\python.exe` par `.venv/bin/python`.

La configuration fournie limite l'écoute à `127.0.0.1` et désactive la collecte de statistiques d'usage de Streamlit. Aucune API externe n'est nécessaire pour traiter les images.

`requirements.txt` borne les versions majeures ; `requirements-lock.txt` enregistre les versions exactes de l'environnement vérifié. Pour reproduire cet environnement Python 3.11 sous Windows, installer ce dernier fichier à la place.

## Utilisation

Pour permettre un test depuis un autre ordinateur sans installation de Python, suivre le [guide de déploiement Streamlit](docs/deploiement_streamlit.md). Un dossier de publication séparé est préparé avec `scripts.package_cloud`, en conservant les dix images et en adaptant uniquement la configuration réseau du cloud. Le calcul ExG limite la mémoire avec des buffers 2D, sans changer la formule ou les paramètres.

Sous Windows, après installation des dépendances, double-cliquer sur **`Lancer_AgriPheno.cmd`** pour démarrer le serveur et ouvrir le navigateur. Garder la fenêtre du serveur ouverte pendant l'utilisation ; `Ctrl+C` l'arrête. Si un serveur répond déjà sur le port 8501, le lanceur ouvre simplement sa page.

Si le navigateur affiche **`ERR_CONNECTION_REFUSED`**, le serveur local est arrêté : relancer ce fichier ou exécuter `.\.venv\Scripts\python.exe -m streamlit run app.py` depuis le dossier du projet, puis actualiser la page. Une adresse `127.0.0.1` fonctionne uniquement sur l'ordinateur qui exécute le serveur ; le lien seul ne démarre pas l'application.

1. Choisir un des trois modes : import PNG/JPEG couleur 8 bits, démonstration synthétique ou images réelles de drone. Une image constitue une unité de comparaison ; elle ne représente pas nécessairement une parcelle entière. Son nom de base doit être unique.
2. Régler le seuil ExG, initialement 0,10. Inspecter visuellement l'original, le masque blanc et la superposition magenta. La segmentation est recalculée quand un paramètre change.
3. Activer éventuellement le nettoyage morphologique : ouverture puis fermeture, noyau elliptique impair en pixels et nombre d'itérations communs aux deux opérations.
4. Comparer les couvertures sur le graphique et télécharger le CSV. Le téléchargement est explicite ; l'application n'écrit pas automatiquement dans `data/results/`. Ce dossier est prévu pour y conserver les exports.
5. Facultatif : importer les masques de référence PNG monochromes, binaires 0/255 (0/1 accepté), de même nom de base, dimensions et orientation que les images. Par exemple `parcelle_A.jpg` et `parcelle_A.png`. Blanc = végétation. Aucun redimensionnement ou seuillage automatique n'est appliqué aux références. Leurs noms doivent être uniques.

Les images en niveaux de gris, 16 bits ou avec transparence sont refusées : les convertir explicitement en RGB 8 bits au préalable. OpenCV lit en BGR ; le moteur reçoit du RGB après conversion. L'orientation encodée est conservée, sans appliquer la rotation EXIF. Une limite de 25 millions de pixels est contrôlée après décodage ; ce n'est pas une limite de mémoire du décodeur. Traiter des lots raisonnables sur une machine locale : les images et aperçus occupent de la mémoire et sont recalculés à chaque interaction.

## Définitions et conventions

Pour chaque pixel valide :

```text
S = R + G + B
r = R/S ; g = G/S ; b = B/S
ExG = 2g - r - b, compris entre -1 et 2
végétation = ExG > seuil
couverture (%) = 100 × pixels classés végétation / pixels valides
IoU = intersection(prédiction, référence) / union(prédiction, référence)
F1 = 2 TP / (2 TP + FP + FN)
```

- **Validité** : `S > 0`. Les pixels exactement noirs sont exclus, y compris après morphologie et pour l'IoU. L'ExG noir vaut conventionnellement zéro mais ne sert jamais à classer ces pixels. Les pixels sombres non noirs restent valides. Cette règle peut exclure un vrai couvert très sombre et surestimer la couverture si une grande partie du sol est noire ; vérifier le nombre de pixels valides.
- **Morphologie** : appliquée au masque, jamais aux valeurs ExG. Bords traités avec zéro ; l'exclusion des pixels invalides est réappliquée après chaque opération. Peut réduire les petites feuilles, modifier les bords et combler les espaces. Un noyau de même taille en pixels n'a pas la même taille physique à deux résolutions différentes.
- **Valeurs indéfinies** : sans pixel valide, couverture = `NaN`. Une union vide donne une IoU `NaN`, même si les deux masques sont vides. Dans le CSV, ces valeurs sont des cellules vides ; les colonnes de statut en expliquent la cause.
- **IoU** : calculée sur les seuls pixels RGB valides, après nettoyage si activé. Les références doivent partager le cadrage exact de l'image. Une référence invalide ne supprime pas la mesure de couverture.
- **F1/Dice** : mêmes références et même domaine valide que l'IoU ; deux masques vides donnent `NaN`. Une référence d'adventices seules ou des boîtes de détection ne permettent pas d'évaluer la végétation totale.

## Contrôles qualité et export

Le CSV contient le nom, l'identifiant de parcelle, la provenance déclarée, le seuil, les paramètres de nettoyage, les dimensions, les effectifs de pixels, la couverture, l'IoU et les statuts. La provenance `import_utilisateur` ne certifie pas qu'une image est réelle. Les nombres exportés sont arrondis à six décimales ; cela ne représente pas une précision scientifique.

| Statut | Signification |
| --- | --- |
| `FAIBLE_RESOLUTION` | Au moins un côté inférieur à 256 pixels ; seuil technique indicatif |
| `AUCUN_PIXEL_VALIDE` | Image entièrement noire ; couverture indéfinie |
| `MASQUE_VIDE` | Aucun pixel valide classé végétation |
| `MASQUE_SATURE` | Tous les pixels valides classés végétation |
| `IMAGE_REJETEE` | Fichier vide, illisible ou format non accepté ; ligne conservée |
| `SANS_REFERENCE` | Pas de masque associé ; IoU absente |
| `REFERENCE_INVALIDE` | Référence illisible, non binaire ou dimensions incompatibles |
| `IOU_INDEFINIE` | Union vide dans le domaine valide |
| `REFERENCE_NON_COMPATIBLE_OU_NON_VERIFIEE` | Annotations ne couvrant pas la végétation totale, ou cible non vérifiée |
| `REFERENCE_MANQUANTE` | Référence déclarée mais fichier absent |

## Photographies RGB réelles de drone

Le mode **« Tester avec des images réelles de drone »** charge les images préparées localement, sans connexion réseau. Sélectionner plusieurs identifiants pour les comparer, puis une image pour inspecter son RGB, son masque prédit, sa superposition, sa carte ExG et, si elle est compatible, sa référence. Le tableau et le CSV précisent la source, l'attribution, les observations visuelles et les paramètres. Les observations sont des notes de revue du jeu installé ; aucun diagnostic agronomique n'est automatisé.

Les sources officielles sélectionnées sont [USU-Corn-WeedDB](https://zenodo.org/records/20044178), [CoFly-WeedDB](https://zenodo.org/records/6697343) et [High-Resolution RGB Images and Corresponding Masks of Agricultural Fields](https://zenodo.org/records/12607112). Leurs licences de données CC BY 4.0 ont été vérifiées dans les métadonnées Zenodo : créditer les auteurs, lier la licence et signaler les modifications. Les conditions des données ne sont pas déduites de la licence du code GitHub. Les photographies préparées et figures restent soumises à l'attribution des sources.

L'échantillon cible comprend quatre tuiles RGB de maïs, trois photos de cotonnier et trois TIFF agricoles convertis en PNG. Il exclut les compositions de bandes multispectrales. Des cultures ne sont indiquées au niveau image que lorsque la provenance le permet. Les prises de vue d'un même champ ou vol peuvent être corrélées : ce jeu de démonstration n'est pas un benchmark indépendant ou représentatif. CoFly annote uniquement des adventices et USU fournit des boîtes : leurs annotations ne sont pas utilisées comme masques de végétation totale.

```powershell
# Acquisition avec Internet ; peut reprendre les blocs déjà validés.
.\.venv\Scripts\python.exe -m scripts.acquire_real_images
# Réacquérir une seule source si nécessaire : --only cofly, corn ou agri.
# Réappliquer la revue fournie seulement si les fichiers ont les mêmes empreintes.
.\.venv\Scripts\python.exe -m scripts.apply_real_review
# Rapport, CSV et figures : traitement hors ligne des données préparées.
.\.venv\Scripts\python.exe -m scripts.build_real_report
```

`data/real_drone_images/` contient les PNG RGB ; `data/reference_masks/` les annotations ; `data/sources.csv` fait le lien avec les auteurs, DOI, URLs exactes, chemins ZIP, licences, dates d'accès, empreintes SHA-256, dimensions, transformations et notes de revue. `data/provenance/` conserve les métadonnées de licence. Les références non compatibles restent dans `original_labels/` et ne sont jamais converties en vérité terrain par ExG.

Les gros ZIP sont lus par plages HTTP, validées sur le statut 206, le Content-Range et la taille. Le CRC ZIP vérifie les membres décompressés ; SHA-256 contrôle les blocs repris et les PNG préparés. Les originaux et blocs restent dans `data/.cache/`, ignoré par Git. Chaque requête porte sur un petit bloc ; un échec ne déclenche pas le téléchargement complet des archives de plusieurs gigaoctets. Les TIFF sont préparés séparément ; le chargeur utilisateur conserve son exigence RGB 8 bits. Toute conversion d'échelle doit être documentée et commune aux trois canaux, sans normalisation indépendante par canal.

Le [rapport technique d'entretien](docs/rapport_images_reelles.md) contient les résultats réellement calculés, les figures, la revue des références, les limites et l'explication du code. Les exports reproductibles sont `data/results/real_drone_results.csv` et `data/results/real_drone_thresholds.csv`. Le rapport utilise exactement le pipeline de Streamlit, au seuil 0,10 et sans morphologie ; la comparaison des seuils 0,00/0,10/0,20 est exploratoire et ne choisit pas un meilleur score.

Avant de traiter un nouveau sous-ensemble téléchargé, inspecter les photos et références puis renseigner les notes du catalogue. Le rapport final exige dix images revues. Réacquérir des fichiers identiques conserve les notes de revue. Une modification de l'image préparée invalide ces notes ; les métriques ne sont autorisées que pour une référence de végétation totale déclarée vérifiée et contrôlée par SHA-256.

**Résultat de la revue du jeu livré : aucun masque compatible de végétation totale.** Les trois masques TIFF sont blancs sur de grandes surfaces de sol et suivent l'emprise ou les trous de l'image ; leur interprétation comme masques de validité reste une hypothèse visuelle. Ils sont exclus de l'IoU/F1, comme les annotations d'adventices seules et les boîtes. Les notes de revue sont conservées dans `data/provenance/visual_review.json` et liées aux empreintes des images et annotations examinées. Le rapport publie des couvertures estimées, sans revendiquer de précision terrain. Les fonctions IoU/F1 restent utilisables avec de vraies références compatibles importées par l'utilisateur et dans les tests synthétiques.

Un masque vide ou saturé peut être correct. Ces alertes appellent une inspection, sans décision agronomique automatique. Les contrôles ne détectent pas automatiquement le flou, la surexposition ou un mauvais cadrage.

## Données synthétiques

```powershell
.\.venv\Scripts\python.exe -m scripts.generate_synthetic --seed 42
```

Sept paires PNG sont créées dans `data/images/` et `data/masks/`, avec le préfixe `synthetic_`. `data/synthetic_manifest.csv` précise la provenance synthétique, la graine de génération du jeu et la couverture de référence. Les trois densités et la petite image utilisent respectivement les graines 42, 43, 44 et 45 par défaut. Le sol brun, les feuilles elliptiques, le bruit et le gradient d'éclairage sont des constructions artificielles ; les feuilles pâles introduisent une difficulté de séparation. Les références sont dessinées avant la coloration et ne résultent pas de la segmentation ExG.

Les autres scènes sont entièrement sol, vertes ou noires, pour montrer les contrôles qualité. La graine rend la génération reproductible dans le même environnement. Relancer la commande remplace les fichiers synthétiques de mêmes noms ; utiliser `--output autre_dossier` pour créer un autre jeu.

**Ce jeu ne simule ni une acquisition réelle, ni une distribution représentative des cultures, ni des performances terrain.** Un score élevé sur ces formes artificielles vérifie surtout la cohérence logicielle.

## Démonstration d'entretien (5 minutes)

1. Expliquer le besoin : quantifier la fraction visible de végétation dans un cadrage fixé, avec un outil inspectable et reproductible.
2. Activer les scènes synthétiques. Comparer les scènes sparse, medium et dense, en rappelant leur caractère artificiel.
3. Déplacer le seuil pour observer le compromis entre pixels manqués et faux positifs. Inspecter les feuilles pâles et l'IoU associée.
4. Comparer avec et sans morphologie ; expliquer que le nettoyage change la mesure et exige une échelle adaptée.
5. Montrer les scènes black, soil, green et small, les statuts et l'export CSV. Présenter les tests et les limites ci-dessous.

Pour une validation terrain ultérieure : acquérir des images documentées, annoter des références indépendantes, établir un protocole d'annotation, régler les paramètres sur un jeu distinct puis évaluer sur des parcelles et conditions non utilisées au réglage. Examiner l'erreur de couverture en complément de l'IoU, la variabilité entre conditions et les désaccords d'annotation.

## Limites scientifiques

- Les images sont RGB : **aucun NDVI** ne peut être calculé faute de proche infrarouge.
- La couverture apparente ne suffit pas à mesurer le **LAI, la biomasse, le rendement ou le stress hydrique**. Des données supplémentaires, une calibration et une validation spécifiques seraient nécessaires.
- ExG détecte un contraste de couleur : adventices, objets verts ou certains sols peuvent être inclus ; végétation sèche, jaunie, ombragée ou pâle peut être manquée. Les recouvrements cachent les organes inférieurs.
- La normalisation atténue une multiplication uniforme de la luminosité, mais ne corrige pas la balance des blancs, les ombres colorées, les saturations, la compression JPEG ni le traitement du capteur. Aucun seuil universel n'est garanti.
- La mesure porte sur le cadrage complet, sans polygone de parcelle, orthorectification ou calibration géométrique. Privilégier des vues nadirales avec cadrage, hauteur et éclairage comparables ; bordures, perspective et inter-rangs changent l'interprétation.
- Une image = une unité de comparaison. Plusieurs vues chevauchantes ne sont pas agrégées en une couverture de parcelle. L'application n'identifie pas les cultures ni les plantes individuellement.

## Organisation et vérification

```text
app.py                         point d'entrée Streamlit
src/ui.py                      interface et visualisations
src/analysis.py                pipeline commun application / rapport
src/acquisition.py             lecture ZIP HTTP et cache vérifié
src/segmentation.py            normalisation, ExG, seuil, morphologie, superposition
src/metrics.py                 couverture, IoU et F1
src/quality_control.py         alertes techniques
src/io_utils.py                décodage des images et des références
scripts/generate_synthetic.py  génération indépendante, reproductible
scripts/acquire_real_images.py acquisition et provenance des photographies
scripts/build_real_report.py   rapport, CSV et figures reproductibles
tests/                        calculs, cas limites, I/O et application
data/images/                  PNG synthétiques explicitement nommés
data/masks/                   références binaires synthétiques
data/real_drone_images/        photographies RGB réelles préparées
data/reference_masks/          références réelles et annotations d'origine
data/sources.csv               catalogue et traçabilité par image
data/results/                  exports du rapport et exports manuels
```

Les tests vérifient des résultats calculables à la main : couleurs primaires, invariance à une mise à l'échelle RGB sans saturation, seuil strict, exclusions noires, couverture, intersection/union, masques vides, entrées invalides, morphologie, ordre RGB/BGR, formats refusés et génération déterministe. Les tests Streamlit vérifient le démarrage et le parcours de démonstration, sans constituer une validation visuelle complète dans un navigateur.

Vérification du 12 novembre 2026 : **57 tests réussis**, sans dépendance incompatible signalée par `pip check`. La recette AppTest sur les dix images réelles, avec les accès réseau bloqués, confirme les mêmes couvertures que le CSV à 0,000001 près, la sélection multiple et l'inspection d'un TIFF préparé. Les photographies, superpositions et trois masques TIFF ont été examinés visuellement ; cette revue n'établit aucune précision agronomique. Les vérifications et leurs limites sont consignées dans `docs/validation.json`. Le détail exact des versions se trouve dans `requirements-lock.txt`.

Documentation technique : [import multiple Streamlit](https://docs.streamlit.io/develop/api-reference/widgets/st.file_uploader), [morphologie OpenCV](https://docs.opencv.org/4.x/d9/d61/tutorial_py_morphological_ops.html). Ces références documentent les outils, sans valider l'interprétation agronomique du prototype.
