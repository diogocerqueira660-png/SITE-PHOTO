# Site photo — Photographe automobile

Site vitrine simple (HTML / CSS / JavaScript, sans framework) pour présenter des photos de voitures.

## Structure

```
index.html          → la page (textes, sections, contact)
css/style.css       → le design (couleurs en haut du fichier)
js/photos.js        → LA LISTE DE TES PHOTOS (c'est ici que tu ajoutes tes photos)
js/main.js          → galerie, filtres, visionneuse plein écran, menu mobile
images/photos/      → tes photos
images/hero.svg     → image de fond de l'accueil (à remplacer)
images/portrait.svg → ta photo pour la section « À propos » (à remplacer)
```

## Voir le site

Ouvre simplement `index.html` dans ton navigateur (double-clic).

## Ajouter tes photos

1. Copie tes photos (JPG de préférence, ~2000 px de large, < 500 Ko) dans `images/photos/`.
2. Ouvre `js/photos.js` et ajoute une ligne par photo :
   ```js
   { src: "images/photos/golf-gti.jpg", titre: "VW Golf GTI", categorie: "Sportives", lieu: "Circuit de Magny-Cours" },
   ```
3. Les boutons de filtre sont créés automatiquement à partir des catégories.
4. Supprime les lignes `placeholder-X.svg` et les fichiers correspondants.

## À personnaliser

- **Nom / logo** : dans `index.html`, cherche « Ton Nom » et « TON<span>NOM</span> ».
- **Image d'accueil** : dans `css/style.css`, section *Hero*, remplace `../images/hero.svg` par ta meilleure photo.
- **Couleur principale** : `--accent` en haut de `css/style.css` (rouge par défaut).
- **Textes** : section « À propos », « Prestations », chiffres, email, Instagram.
- **Email du formulaire** : `CONTACT_EMAIL` dans `js/main.js`. Par défaut le formulaire ouvre l'application mail du visiteur.
  Pour recevoir les messages directement, crée un formulaire gratuit sur [Formspree](https://formspree.io) et mets son adresse dans `action` du `<form>`.

## Mettre en ligne (gratuit)

Avec **GitHub Pages** : dans le dépôt GitHub → *Settings* → *Pages* → *Deploy from a branch* → choisis la branche et `/ (root)`.
Le site sera disponible à `https://<ton-pseudo>.github.io/SITE-PHOTO/`.
