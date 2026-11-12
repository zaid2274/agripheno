# Publier AgriPheno pour un test à distance

Le lien `127.0.0.1:8501` est local. Streamlit Community Cloud exécute le projet sur un serveur distant et fournit une URL partageable ; ton ordinateur peut ensuite être éteint.

## État de préparation

- Le dossier de publication doit contenir `app.py` à sa racine, `requirements.txt`, `src/`, les dix PNG réels, leur catalogue et les attributions.
- Le traitement est le même que dans l'application locale, sans réduction des images. Le calcul ExG utilise des buffers 2D pour limiter la mémoire, avec les mêmes opérations numériques.
- Les caches, `.venv`, fichiers de logs et archives originales volumineuses sont exclus.
- Le fichier `.streamlit/config.toml` de publication n'impose pas l'adresse locale `127.0.0.1` ; celui du projet local est conservé.
- Aucun secret ou clé API n'est requis pour le fonctionnement du prototype. La connexion aux comptes de déploiement reste nécessaire pour publier.

Préparer un dossier neuf depuis le projet local :

```powershell
.\.venv\Scripts\python.exe -m scripts.package_cloud C:\agripheno\AgriPheno-cloud
```

## GitHub et déploiement

1. Créer un dépôt GitHub nommé `agripheno` et y transférer **le contenu** du dossier de publication avec Git ou GitHub Desktop. Les trois grandes images PNG dépassent 25 Mio et ne peuvent donc pas être envoyées par l'interface web GitHub ; elles restent sous la limite de 100 Mio par fichier pour Git. Ne pas envoyer seulement le ZIP : `app.py` doit être visible dans le dépôt.
2. Un dépôt privé permet de conserver le code privé. Vérifier également les réglages de partage de l'application : une application issue d'un dépôt privé n'est pas automatiquement accessible à ton encadrante.
3. Se connecter à [Streamlit Community Cloud](https://share.streamlit.io/) avec le compte autorisé à accéder au dépôt GitHub.
4. Choisir **Create app**, sélectionner le dépôt et sa branche, puis indiquer **`app.py`** comme fichier principal. Dans les réglages avancés, choisir **Python 3.11**, la version utilisée pour les vérifications locales.
5. Déployer, puis consulter les logs si une erreur d'installation ou de lancement apparaît.
6. Pour un test sans connexion de ton encadrante, régler le partage de l'application sur public. Son URL devient alors accessible à toute personne qui la connaît et l'application peut être indexée. Le dépôt GitHub peut rester privé. Si tu préfères un accès réservé, ajouter ton encadrante comme visiteuse dans les réglages de partage ; elle devra alors s'authentifier.
7. Ouvrir l'URL hébergée, sélectionner « Tester avec des images réelles de drone », vérifier les dix images, modifier le seuil, inspecter une superposition et télécharger le CSV.

Ne transmettre l'URL qu'après cette vérification. Le nom exact est celui attribué par Streamlit lors du déploiement ; aucun lien de production n'est créé par la seule préparation du dossier.

## Limites de la démonstration

Les ressources d'un hébergement partagé sont limitées. Les grandes images et les visites simultanées augmentent la mémoire utilisée. Les paramètres et les images sont traités par session ; l'application n'enregistre pas automatiquement les images importées sur disque. Ne pas télécharger le jeu Zenodo complet depuis le serveur d'hébergement : toutes les données de démonstration nécessaires sont déjà incluses.

Les limites scientifiques restent celles du README : couverture apparente, pas de LAI/biomasse/stress ; aucun IoU/F1 terrain avec les annotations incompatibles du jeu livré.

## Documentation officielle consultée

- [Organisation des fichiers](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/file-organization)
- [Déployer une application](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app)
- [Partager une application publique ou privée](https://docs.streamlit.io/deploy/streamlit-community-cloud/share-your-app)
- [Limites de taille des fichiers GitHub](https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository)
