# Gestion Photos Auto — appli PC

Petite appli de bureau (Windows / Mac) pour **organiser tes shootings de voitures**
et suivre chaque photo de la carte SD jusqu'à la version finale :

```
Carte SD → RAW → Lightroom → Photoshop → Final HD → Web / Instagram
```

Elle travaille directement sur **tes dossiers** : rien n'est envoyé sur Internet, et tu
peux continuer à tout ouvrir avec l'Explorateur, Lightroom ou Photoshop.

## Ce qu'elle fait pour toi

- **Un dossier propre par shooting**, créé en un clic :
  ```
  2026-09-26_Porsche-911-GT3_Lucas/
      01_RAW/          ← fichiers de l'appareil
      02_LIGHTROOM/    ← exports TIFF de Lightroom à retoucher
      03_PHOTOSHOP/    ← tes PSD
      04_FINAL/        ← JPG HD terminés
      05_WEB/          ← versions site / Instagram
  ```
- **Import de la carte SD** : détecte la carte, copie seulement les nouvelles photos,
  vérifie chaque copie, et peut renommer (`2026-09-26_Porsche-911-GT3_0001.CR3`).
  Le RAW et le JPG d'une même prise gardent le même numéro.
- **Tri rapide** au clavier : notes ★ (1 à 5), garder (P), rejeter (X), « à retoucher » (R),
  plus un commentaire de retouche par photo (« enlever reflet portière… »).
- **Suivi de chaque photo** : l'appli reconnaît toutes les versions d'une même photo
  (`IMG_1234.CR3`, `IMG_1234-Edit.tif`, `IMG_1234-Edit.psd`, `IMG_1234.jpg`…) et affiche
  des pastilles **RAW · LR · PS · FINAL · WEB** + un état :
  À trier → Choisie → Développée → À retoucher → En retouche → Terminée.
- **Passage vers Photoshop en un clic** (ou touche Entrée) : ouvre le bon fichier — le PSD
  si tu as déjà commencé, sinon l'export Lightroom, sinon le RAW (Camera Raw).
  Tu peux en ouvrir plusieurs d'un coup.
- **Mise à jour automatique** : dès que Photoshop ou Lightroom enregistre un fichier dans
  le shooting, l'appli le voit et met la photo à jour.
- **« Ranger le vrac »** : les fichiers posés n'importe où dans le shooting sont
  rangés dans le bon dossier (RAW, TIFF, PSD, JPG), après confirmation.
- **Lien avec Lightroom** : les notes passent de l'appli à Lightroom et inversement
  grâce aux fichiers `.xmp` (sans toucher à tes réglages Lightroom).
- **Export web / Instagram** : depuis `04_FINAL`, crée des JPG allégés (2048 px, 1600 px,
  Insta 4:5, carré, story) avec ta signature en filigrane, dans `05_WEB`.
- **Avancement** de chaque shooting (% de photos terminées) dans la liste de gauche.

## Installation (Windows)

1. Installe **Python 3.10 ou plus récent** depuis [python.org](https://www.python.org/downloads/)
   (coche **« Add python.exe to PATH »** pendant l'installation).
2. Double-clique sur **`lancer.bat`**. La première fois, il installe ce qu'il faut (Pillow).
3. Au premier lancement, choisis le dossier où ranger tous tes shootings
   (par ex. `D:\Photos Voitures`).

Photoshop et Lightroom Classic sont trouvés automatiquement. Sinon : **⚙ Réglages**.

**Pour avoir un vrai `.exe`** (sans avoir besoin de Python ensuite) : double-clique sur
`creer_exe.bat`, puis utilise `dist\GestionPhotosAuto.exe` (tu peux l'épingler à la barre des tâches).

Sur **Mac** : double-clique sur `lancer.command` (ou `python3 app.py` dans le Terminal).

**Aperçus RAW** : l'appli lit l'aperçu JPEG caché dans tes RAW (CR2, CR3, NEF, ARW, RAF…).
Pour un rendu encore plus fiable : `pip install rawpy` (déjà inclus dans le `.exe`).

## Ta journée type

1. **Nouveau shooting** → marque, modèle, client, date. → « Importer maintenant ? » → Oui.
2. Carte SD branchée : elle est proposée d'office → **Importer**. Tu peux formater la carte après.
3. **Tri** : flèches pour avancer, `P` garder, `X` rejeter, `1`-`5` les étoiles,
   `Espace` pour voir en grand. Filtre **Afficher : Choisies (P)** pour ne garder que les bonnes.
4. **Lightroom** : importe le dossier `01_RAW` dans Lightroom (Ajouter, sans déplacer).
   Menu **Lightroom ▾ → écrire les notes** puis dans Lightroom
   *Métadonnées → Lire les métadonnées à partir des fichiers* : tes étoiles et rejets y sont.
   Exporte tes photos développées en TIFF dans `02_LIGHTROOM`
   (ou fais « Modifier dans Photoshop », l'appli le détecte aussi).
5. **Photoshop** : filtre *Développée* ou *À retoucher*, sélectionne, **Entrée**.
   Enregistre ton PSD dans `03_PHOTOSHOP` et le JPG final dans `04_FINAL`.
   Les pastilles passent au vert toutes seules.
6. **Export web/Insta** → les images pour le site et les réseaux arrivent dans `05_WEB`.

### Raccourcis

| Touche | Action |
|--------|--------|
| `1` … `5` / `0` | Note / sans note |
| `P` / `X` / `U` | Garder / rejeter / annuler |
| `R` | Marquer « à retoucher dans Photoshop » |
| `Entrée` / double-clic | Ouvrir dans Photoshop |
| `Espace` | Aperçu en grand (Échap pour fermer) |
| Flèches, `Maj`+clic, `Ctrl`+clic, `Ctrl+A` | Naviguer / sélectionner |
| `F5` | Actualiser |
| Clic droit | Menu (Lightroom, montrer dans le dossier, notes…) |

## Bon à savoir

- Tes notes, choix et commentaires sont enregistrés dans `shooting.json` à l'intérieur
  de chaque shooting : si tu déplaces ou sauvegardes le dossier, ils suivent.
- Rien n'est jamais supprimé par l'appli. « Ranger le vrac » ne fait que déplacer,
  et ne touche pas aux fichiers que Lightroom a créés à côté des RAW (pour qu'il ne les perde pas).
- Un dossier déjà existant qui contient un sous-dossier `01_RAW` est reconnu comme shooting.

## Pour les curieux

```
app.py          → point d'entrée
interface.py    → la fenêtre (tkinter)
noyau.py        → shootings, import, suivi des versions, rangement, XMP, export web
apercus.py      → miniatures (JPG, TIFF, PSD, RAW) avec cache
reglages.py     → réglages, recherche de Photoshop / Lightroom
tests/          → tests automatiques : python -m unittest discover -s tests
```
