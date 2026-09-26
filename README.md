# Site photo — Portfolio automobile

Portfolio simple (HTML / CSS / JavaScript, sans serveur) : **un album par shooting**,
et pour chaque shooting, un **téléchargement des photos en HD protégé par un mot de passe**.

## Structure

```
index.html                 → accueil : la liste des shootings
album.html                 → la page d'un shooting (album.html#nom-du-shooting)
css/style.css              → le design (couleurs en haut du fichier)
js/                        → le fonctionnement des pages
albums/                    → TES SHOOTINGS (créés par le script, un dossier par shooting)
  albums.js                → la liste des shootings lue par le site (générée automatiquement)
  <shooting>/album.json    → titre, date, lieu, description, liste des photos
  <shooting>/web/          → photos redimensionnées pour l'affichage (2000 px)
  <shooting>/mini/         → miniatures (800 px)
  <shooting>/hd/           → originaux CHIFFRÉS pour le téléchargement
outils/ajouter_shooting.py → le script pour ajouter un shooting
```

## Préparer ton ordinateur (une seule fois)

Il faut **Python 3** ([python.org](https://www.python.org/downloads/)), puis dans un terminal :

```bash
pip install pillow cryptography
```

## Ajouter un shooting

1. Mets les photos du shooting dans un dossier sur ton ordinateur (JPG exportés depuis Lightroom, par exemple).
2. Dans un terminal, placé dans le dossier du site :

```bash
python3 outils/ajouter_shooting.py "/chemin/vers/le/dossier" --titre "Porsche 911 GT3" --date 2026-08-14 --lieu "Circuit Paul Ricard"
```

3. Le script te demande le **mot de passe** de ce shooting (celui que tu donneras au client / au propriétaire de la voiture).
4. C'est tout : le shooting apparaît sur l'accueil. Les shootings sont triés du plus récent au plus ancien.

Options utiles :

| Option | Effet |
|---|---|
| `--description "..."` | petit texte affiché sur la page du shooting |
| `--couverture 3` | la 3ᵉ photo sert d'image de couverture (défaut : la 1ʳᵉ) |
| `--mot-de-passe xxx` | donne le mot de passe directement au lieu de le taper |
| `--sans-telechargement` | shooting visible mais pas téléchargeable |
| `--remplacer` | refait un shooting qui existe déjà (ex : tu as ajouté des photos) |
| `--nom porsche-gt3` | choisit le nom du dossier / de l'adresse de la page |

**Modifier** un titre, une date… : édite `albums/<shooting>/album.json`, puis lance
`python3 outils/ajouter_shooting.py --reconstruire`.
**Supprimer** un shooting : supprime son dossier dans `albums/`, puis lance la même commande.
**Changer le mot de passe** : refais le shooting avec `--remplacer`.

Les deux shootings « Exemple » (mots de passe : `porsche` et `gtr`) sont là pour tester : supprime les dossiers
`albums/exemple-porsche` et `albums/exemple-gtr` puis lance `--reconstruire` quand tu as ajouté les tiens.

## Comment marche le mot de passe

- Les photos affichées sur le site sont publiques (versions web 2000 px).
- Les **originaux** sont **chiffrés** (AES-256) avec le mot de passe du shooting. Le mot de passe n'est
  écrit nulle part : sans lui, les fichiers du dossier `hd/` sont illisibles, même si quelqu'un les récupère
  (y compris sur GitHub).
- Le visiteur tape le mot de passe → son navigateur déchiffre les photos → il télécharge tout en `.zip`,
  ou photo par photo depuis la visionneuse (bouton ⬇).
- ⚠ Si tu oublies un mot de passe, il est impossible de le retrouver : il faudra refaire le shooting.
  Note-les quelque part.

## Voir le site sur ton ordinateur

Le téléchargement ne marche pas en ouvrant simplement `index.html` (sécurité du navigateur).
Lance un mini-serveur dans le dossier du site :

```bash
python3 -m http.server
```

puis ouvre <http://localhost:8000>.

## À personnaliser

- **Nom / logo** : « Diogo Car Photography » dans `index.html`, `album.html` et `js/album.js`.
- **Lien Instagram** : dans `index.html`.
- **Couleur principale** : `--accent` en haut de `css/style.css`.

## Mettre en ligne (gratuit)

Avec **GitHub Pages** : dépôt GitHub → *Settings* → *Pages* → *Deploy from a branch* → choisis la branche et `/ (root)`.
Le site sera disponible à `https://<ton-pseudo>.github.io/SITE-PHOTO/`.

Limites de GitHub : 100 Mo max par fichier (donc par photo originale) et environ 1 Go pour tout le site.
Au-delà, il faudra un autre hébergement (Netlify, Cloudflare Pages ou un hébergeur classique : le site fonctionne partout tel quel).
