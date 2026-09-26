# Gestion Photos Auto V.1 — appli PC et Mac

<img src="ressources/logo_256.png" width="96" alt="logo">

Appli de bureau pour **organiser tes shootings de voitures** et suivre chaque photo,
de la carte SD jusqu'au JPG final :

```
Carte SD → Tri → Lightroom (éclairage) → Photoshop → Lightroom (export JPG) → Web / Insta
```

Les étapes de retouche se **règlent dans ⚙ Paramètres** si tu travailles autrement.
L'appli travaille directement sur **tes dossiers** : rien n'est envoyé sur Internet.

## Installation (Windows) — le plus simple

1. Télécharge **GestionPhotosAuto.exe** :
   <https://github.com/diogocerqueira660-png/SITE-PHOTO/releases/latest/download/GestionPhotosAuto.exe>
2. Range-le où tu veux (par ex. sur le Bureau) et **double-clique** dessus.
3. Si Windows affiche « Windows a protégé votre ordinateur » : **Informations complémentaires**
   → **Exécuter quand même** (normal pour une appli perso non signée).
4. Choisis le dossier où ranger tous tes shootings. C'est tout.

Pas besoin d'installer Python. Le `.exe` est refabriqué automatiquement à chaque mise à jour.

## Installation (Mac)

1. Télécharge **GestionPhotosAuto-Mac.zip** :
   <https://github.com/diogocerqueira660-png/SITE-PHOTO/releases/latest/download/GestionPhotosAuto-Mac.zip>
2. Double-clique dessus pour le décompresser, puis glisse **Gestion Photos Auto** dans **Applications**.
3. La première fois : **clic droit → Ouvrir** (l'appli n'est pas signée par Apple).
   Si le Mac refuse : **Réglages Système → Confidentialité et sécurité → Ouvrir quand même**.

Version faite pour les Mac Apple Silicon (M1, M2, M3, M4). Sur un ancien Mac Intel,
utilise `lancer.command` (avec Python installé).

## Comment ça marche

### 1. Un shooting = un dossier bien rangé

**＋ Nouveau shooting** → voiture, client, date. L'appli crée :

```
2026-09-26_Porsche-911-GT3_Lucas/
    01_RAW/         ← photos de l'appareil
    02_PHOTOSHOP/   ← TIF / PSD retouchés
    03_JPG/         ← JPG finis (exportés de Lightroom)
    04_WEB/         ← versions site / Instagram
```

### 2. Import de la carte SD

La carte est détectée toute seule. Seules les nouvelles photos sont copiées, chaque copie est
vérifiée, et elles peuvent être renommées (`2026-09-26_Porsche-911-GT3_0001.CR3`).

### 3. Le tri, photo par photo

Clique **▶ Trier les photos** (ou touche `T`) : chaque photo s'affiche **en grand**, avec en bas
un gros bouton rouge **✕ Supprimer** et un gros bouton vert **✓ Garder**.

| Touche | Action |
|--------|--------|
| `P` ou `Entrée` | Garder |
| `X` ou `Suppr` | Supprimer |
| `1` … `5` | Étoiles |
| `←` `→` | Photo précédente / suivante |
| `Ctrl+Z` ou ↶ | Revenir sur le dernier choix |
| `Échap` | Terminer |

À la fin : le nombre de photos gardées / supprimées, et un bouton pour **mettre les supprimées
à la corbeille** de l'ordinateur (toujours récupérables depuis la corbeille). Tant que tu ne
cliques pas dessus, les photos supprimées sont seulement mises de côté (étape *Rejetées*).

Le tri s'ouvre sur les photos *À trier* ; si tu as coché plusieurs photos, il s'ouvre sur celles-là.
Dans la grille, les étapes en haut sont des boutons : *Toutes · À trier › Lightroom · éclairage ›
Photoshop · retouche › Lightroom · export JPG · Terminées · Rejetées*, avec le nombre de photos
à chaque étape.

### 4. Envoyer plusieurs photos d'un coup

- **Coche** les photos avec le **rond en haut à gauche** de chaque vignette
  (ou `Ctrl`+clic, `Maj`+clic, bouton **Tout**).
- Une barre apparaît en bas : **« Envoyer vers Photoshop ▶ »** (ou Lightroom, selon l'étape).
  Toutes les photos cochées s'ouvrent d'un coup dans le bon logiciel.
- **« Étape faite »** pour valider une étape à la main (ex. l'éclairage Lightroom).
- Les boutons **Ps** et **Lr** ouvrent les photos cochées dans Photoshop ou Lightroom
  **quelle que soit leur étape** (aussi dans le panneau de droite et au clic droit).

Au survol de la souris, la photo s'avance avec une ombre : c'est celle sur laquelle tu vas cliquer.

L'appli **voit toute seule** quand une étape est finie :

| Étape (flux par défaut) | Finie quand… |
|---|---|
| Lightroom · éclairage | tu cliques « ✓ Étape faite » (ou tu envoies vers Photoshop) |
| Photoshop · retouche | un **TIF / PSD** apparaît (à côté du RAW ou dans `02_PHOTOSHOP`) |
| Lightroom · export JPG | un **JPG** apparaît dans `03_JPG` |

Quand tu envoies vers l'export Lightroom, le chemin de `03_JPG` est **copié** : colle-le
(`Ctrl+V`) dans la fenêtre d'export de Lightroom.

**Astuce Lightroom → Photoshop** : le plus simple reste « Modifier dans Photoshop » depuis
Lightroom (l'appli détecte le TIF créé). Si tu passes par l'appli, active dans Lightroom
*Paramètres du catalogue → Métadonnées → « Inclure automatiquement les paramètres de
développement dans le XMP »* : Photoshop ouvrira le RAW avec ton éclairage Lightroom.

### 5. Export web / Instagram

**↗ Export web / Insta** : depuis `03_JPG`, crée des JPG légers (2048 px, Insta 4:5, carré,
story) avec ta signature, dans `04_WEB`.

## Changer les étapes (⚙ Paramètres → Mon flux de travail)

Choisis un modèle — *Lightroom → Photoshop → Lightroom* (par défaut), *Lightroom → Photoshop*,
*Photoshop → Lightroom*, *Lightroom seulement* — ou fais le tien : renomme les étapes,
change leur ordre (↑ ↓), ajoute-en, supprime-en. Pour chaque étape tu choisis le **logiciel**
et **quand elle est finie** (je la coche moi-même / un TIF apparaît / un JPG apparaît).

## Raccourcis

| Touche | Action |
|--------|--------|
| clic sur le rond, `Ctrl`+clic, `Maj`+clic | Cocher plusieurs photos |
| `Entrée` / double-clic | Envoyer à l'étape suivante |
| `D` | Étape faite |
| `1` … `5` / `0` | Note / sans note |
| `P` / `X` / `U` | Garder / rejeter / annuler |
| `Espace` | Aperçu en grand (← → pour naviguer, Échap pour fermer) |
| `Échap` | Tout décocher |
| `F5` | Actualiser |
| Clic droit | Menu (ouvrir dans Photoshop / Lightroom, montrer dans le dossier…) |

## Bon à savoir

- Notes, choix, étapes et commentaires sont dans `shooting.json`, dans chaque shooting :
  si tu déplaces ou sauvegardes le dossier, ils suivent.
- L'appli ne supprime jamais rien. « Ranger les fichiers en vrac » (menu •••) ne fait que
  déplacer ce qui traîne à la racine du shooting, jamais les TIF créés par Lightroom.
- Les shootings créés avec la première version (dossiers `02_LIGHTROOM`, `04_FINAL`…)
  sont toujours reconnus.
- Notes ↔ Lightroom : menu ••• → écrire / lire les notes XMP.

## Installation avec Python (pour modifier l'appli)

Python 3.10+ ([python.org](https://www.python.org/downloads/), cocher « Add python.exe to PATH »),
puis double-clic sur `lancer.bat` (Windows) ou `lancer.command` (Mac).
`creer_exe.bat` fabrique le `.exe` en local, `creer_app_mac.command` l'appli Mac.
Le logo se régénère avec `python ressources/creer_logo.py`.

```
app.py          → point d'entrée
interface.py    → la fenêtre (CustomTkinter)
noyau.py        → shootings, flux de travail, import, rangement, XMP, export web
apercus.py      → miniatures (JPG, TIFF, PSD, RAW) avec cache
reglages.py     → réglages, recherche de Photoshop / Lightroom
tests/          → tests automatiques : python -m unittest discover -s tests
```
