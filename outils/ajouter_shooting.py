#!/usr/bin/env python3
"""
Ajoute un shooting au site.

    python3 outils/ajouter_shooting.py "/chemin/vers/mes photos" --titre "Porsche 911 GT3"

Ce que fait le script :
  - crée le dossier albums/<nom-du-shooting>/
  - fabrique une version web (2000 px) et une miniature (800 px) de chaque photo
  - si un mot de passe est donné : chiffre les originaux (AES-256) pour le
    téléchargement ; sans le mot de passe, ils sont illisibles, même si
    quelqu'un récupère les fichiers
  - met à jour albums/albums.js (la liste lue par le site)

Autres commandes :
    python3 outils/ajouter_shooting.py --reconstruire
        → régénère albums/albums.js (après avoir supprimé un dossier d'album,
          ou modifié un album.json à la main)

Prérequis (une seule fois) :  pip install pillow cryptography
"""
import argparse
import base64
import getpass
import json
import os
import re
import shutil
import sys
import unicodedata
from pathlib import Path

try:
    from PIL import Image, ImageOps
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
except ImportError:
    sys.exit("Il manque des modules. Lance d'abord :  pip install pillow cryptography")

RACINE = Path(__file__).resolve().parent.parent
ALBUMS = RACINE / "albums"
EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}
TAILLE_WEB = 2000
TAILLE_MINI = 800
ITERATIONS = 250_000  # doit rester identique côté navigateur (lu depuis album.json)
VERIF = b"shooting-ok"


def slugifier(texte):
    texte = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", texte.lower()).strip("-") or "shooting"


def deriver_cle(mot_de_passe, sel):
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=sel, iterations=ITERATIONS)
    return kdf.derive(mot_de_passe.encode("utf-8"))


def chiffrer(cle, donnees):
    iv = os.urandom(12)
    return iv + AESGCM(cle).encrypt(iv, donnees, None)  # format : IV (12 octets) + données + tag


def redimensionner(img, taille, destination):
    copie = img.copy()
    copie.thumbnail((taille, taille), Image.LANCZOS)
    copie.save(destination, "JPEG", quality=85, optimize=True, progressive=True)
    return copie.size


def ajouter(args):
    source = Path(args.source).expanduser()
    if not source.is_dir():
        sys.exit(f"Dossier introuvable : {source}")
    fichiers = sorted(p for p in source.iterdir() if p.suffix.lower() in EXTENSIONS)
    if not fichiers:
        sys.exit("Aucune photo (jpg, png, webp, tif) trouvée dans ce dossier.")

    slug = slugifier(args.nom or args.titre)
    dossier = ALBUMS / slug
    if dossier.exists():
        if not args.remplacer:
            sys.exit(f"L'album « {slug} » existe déjà. Ajoute --remplacer pour l'écraser.")
        shutil.rmtree(dossier)
    (dossier / "web").mkdir(parents=True)
    (dossier / "mini").mkdir()

    mot_de_passe = None
    if not args.sans_telechargement:
        mot_de_passe = args.mot_de_passe or getpass.getpass("Mot de passe pour télécharger ce shooting : ")
        if not mot_de_passe:
            sys.exit("Mot de passe vide. Utilise --sans-telechargement si tu ne veux pas de téléchargement.")
        (dossier / "hd").mkdir()
        sel = os.urandom(16)
        cle = deriver_cle(mot_de_passe, sel)

    photos = []
    for i, chemin in enumerate(fichiers, 1):
        nom = f"{i:03d}.jpg"
        print(f"  [{i}/{len(fichiers)}] {chemin.name}")
        with Image.open(chemin) as img:
            img = ImageOps.exif_transpose(img).convert("RGB")
            largeur, hauteur = redimensionner(img, TAILLE_WEB, dossier / "web" / nom)
            redimensionner(img, TAILLE_MINI, dossier / "mini" / nom)
        photo = {"fichier": nom, "largeur": largeur, "hauteur": hauteur}
        if mot_de_passe:
            (dossier / "hd" / f"{i:03d}.bin").write_bytes(chiffrer(cle, chemin.read_bytes()))
            photo["original"] = chemin.name
        photos.append(photo)

    couverture = max(1, min(args.couverture, len(photos)))
    album = {
        "slug": slug,
        "titre": args.titre,
        "date": args.date or "",
        "lieu": args.lieu or "",
        "description": args.description or "",
        "couverture": photos[couverture - 1]["fichier"],
        "photos": photos,
    }
    if mot_de_passe:
        album["telechargement"] = {
            "sel": base64.b64encode(sel).decode(),
            "iterations": ITERATIONS,
            "verif": base64.b64encode(chiffrer(cle, VERIF)).decode(),
        }
    (dossier / "album.json").write_text(json.dumps(album, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✔ Album « {args.titre} » créé dans albums/{slug}/ ({len(photos)} photos)")
    reconstruire()


def reconstruire():
    albums = []
    for fichier in ALBUMS.glob("*/album.json"):
        albums.append(json.loads(fichier.read_text(encoding="utf-8")))
    # plus récent en premier (date au format AAAA-MM-JJ), sans date à la fin
    albums.sort(key=lambda a: a.get("date") or "", reverse=True)
    contenu = (
        "// Fichier généré par outils/ajouter_shooting.py — ne pas modifier à la main.\n"
        "// Pour changer un titre, une date…, modifie albums/<album>/album.json puis lance\n"
        "//   python3 outils/ajouter_shooting.py --reconstruire\n"
        f"const ALBUMS = {json.dumps(albums, ensure_ascii=False, indent=2)};\n"
    )
    (ALBUMS / "albums.js").write_text(contenu, encoding="utf-8")
    print(f"✔ albums/albums.js mis à jour ({len(albums)} album(s))")


def main():
    p = argparse.ArgumentParser(description="Ajoute un shooting au site.")
    p.add_argument("source", nargs="?", help="dossier contenant les photos du shooting")
    p.add_argument("--titre", help="titre affiché (ex : « Porsche 911 GT3 »)")
    p.add_argument("--date", help="date au format AAAA-MM-JJ (sert aussi au tri)")
    p.add_argument("--lieu", help="lieu du shooting")
    p.add_argument("--description", help="petit texte affiché sur la page de l'album")
    p.add_argument("--couverture", type=int, default=1, help="numéro de la photo de couverture (défaut : 1)")
    p.add_argument("--nom", help="nom du dossier / de l'adresse (par défaut : tiré du titre)")
    p.add_argument("--mot-de-passe", help="mot de passe de téléchargement (sinon demandé)")
    p.add_argument("--sans-telechargement", action="store_true", help="album visible mais pas téléchargeable")
    p.add_argument("--remplacer", action="store_true", help="écrase l'album s'il existe déjà")
    p.add_argument("--reconstruire", action="store_true", help="régénère seulement albums/albums.js")
    args = p.parse_args()

    ALBUMS.mkdir(exist_ok=True)
    if args.reconstruire:
        reconstruire()
    elif args.source and args.titre:
        ajouter(args)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
