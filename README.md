# Diogo Car Photography

Portfolio de photographie automobile avec **espace client** et **espace admin**.

- **Portfolio public** : les shootings que tu choisis d'afficher.
- **Espace client** : le client crée un compte avec son email et retrouve directement *ses* shootings,
  qu'il peut télécharger en haute définition (tout en .zip ou photo par photo).
- **Espace admin** (toi) : créer un shooting, envoyer les photos depuis le navigateur (glisser-déposer),
  choisir la couverture, donner l'accès aux clients par leur email, gérer les comptes clients.

> **Appli PC et Mac de gestion des photos (V.1)** : le dossier [`gestion-photos/`](gestion-photos/) contient une
> appli de bureau pour organiser tes shootings sur ton ordinateur (import carte SD, tri,
> suivi RAW → Lightroom → Photoshop → Final, export web/Instagram). Voir son README.

## Comment ça marche

1. Dans l'admin, tu crées un shooting et tu indiques l'email du client (ex : `lucas@gmail.com`).
2. Tu glisses les photos : le site garde l'original et crée une version web et une miniature.
3. Le client va sur **Espace client → Créer un compte** avec ce même email : son shooting apparaît
   automatiquement dans « Mes photos ». Il peut tout télécharger.
4. Si tu coches **« Afficher dans le portfolio public »**, le shooting apparaît aussi sur l'accueil
   pour tout le monde (visible, mais pas téléchargeable).

Un shooting privé est invisible pour les autres : même un client connecté ne peut ni le voir,
ni ouvrir ses photos s'il n'est pas dans la liste des emails.

**Mot de passe oublié** (client) : dans *Admin → Clients*, bouton « Nouveau mot de passe » : le site
en génère un provisoire que tu transmets au client ; il pourra le changer depuis son espace.

## Lancer le site sur ton ordinateur

Il faut **Node.js 22** ([nodejs.org](https://nodejs.org)).

```bash
npm install
cp .env.example .env      # puis ouvre .env et mets ton email + un mot de passe admin
npm start
```

Ouvre <http://localhost:3000>, clique sur **Espace client** et connecte-toi avec l'email et le
mot de passe admin du fichier `.env` : tu arrives dans l'administration.

## Structure

```
server/            → le serveur (comptes, sessions, albums, envoi des photos, zip)
  index.js         → toutes les adresses du site et de l'API
  db.js            → la base de données (SQLite)
  auth.js          → connexion, sessions, protections
  photos.js        → redimensionnement et stockage des photos
public/            → les pages du site
  index.html       → portfolio public
  album.html       → page d'un shooting
  connexion.html   → connexion / création de compte
  espace.html      → « Mes photos » du client
  admin.html       → administration
  css/style.css    → le design (couleurs en haut du fichier)
data/              → créé automatiquement : base de données + photos (NE PAS PERDRE)
```

## Mettre en ligne

Le site a besoin d'un **serveur Node.js avec un disque permanent** (pour les photos) :
GitHub Pages ne suffit plus.

**Option simple — [Railway](https://railway.app)** (environ 5 $/mois) :
1. *New Project → Deploy from GitHub repo* → choisis ce dépôt (le `Dockerfile` est utilisé automatiquement).
2. Dans le service : *Variables* → ajoute `ADMIN_EMAIL` et `ADMIN_PASSWORD`.
3. *Settings → Volumes* → ajoute un volume monté sur `/data` (c'est là que vont les photos).
4. *Settings → Networking → Generate Domain* (ou branche ton propre nom de domaine).

**Autres options** : Render (avec un *Persistent Disk* monté sur `/data`), Fly.io (avec un volume),
ou un petit serveur VPS (Hetzner, OVH… ~5 €/mois, plus de place pour les photos) avec `docker run`.

Prévois assez d'espace disque : les originaux sont gardés tels quels.

## Sauvegardes

Tout (comptes, shootings, photos) est dans le dossier `data/` (ou le volume `/data`).
Sauvegarde-le régulièrement : si le disque est perdu, les photos le sont aussi.

## Sécurité

- Mots de passe chiffrés (bcrypt), jamais stockés en clair.
- Session par cookie sécurisé (`HttpOnly`, `SameSite`), valable 30 jours.
- Chaque photo est vérifiée à chaque demande : impossible d'ouvrir l'adresse d'une photo privée
  sans avoir accès au shooting.
- Tentatives de connexion limitées (10 par 15 minutes).
- En ligne, utilise toujours une adresse en **https** (Railway, Render et Fly le font automatiquement).
