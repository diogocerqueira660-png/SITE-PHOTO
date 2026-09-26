"""Réglages de l'appli (dossier de la bibliothèque, chemins Photoshop / Lightroom…)
et ouverture des fichiers dans les logiciels Adobe."""

from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
from pathlib import Path

WINDOWS = sys.platform.startswith("win")
MAC = sys.platform == "darwin"

DEFAUTS = {
    "bibliotheque": "",
    "photoshop": "",
    "lightroom": "",
    "renommer_import": True,
    "filigrane": "Diogo Car Photography",
    "qualite_web": 90,
    "taille_miniatures": 200,
    "modele_flux": "Lightroom → Photoshop → Lightroom",
    "flux": [],  # vide = modèle ci-dessus
}


def dossier_config() -> Path:
    if WINDOWS:
        base = Path(os.environ.get("APPDATA", Path.home()))
    elif MAC:
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    d = base / "GestionPhotosAuto"
    d.mkdir(parents=True, exist_ok=True)
    return d


def charger() -> dict:
    r = dict(DEFAUTS)
    f = dossier_config() / "reglages.json"
    if f.is_file():
        try:
            r.update(json.loads(f.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
    if not r["photoshop"]:
        r["photoshop"] = trouver_logiciel("photoshop")
    if not r["lightroom"]:
        r["lightroom"] = trouver_logiciel("lightroom")
    return r


def enregistrer(reglages: dict):
    f = dossier_config() / "reglages.json"
    f.write_text(json.dumps(reglages, ensure_ascii=False, indent=2), encoding="utf-8")


def trouver_logiciel(nom: str) -> str:
    """Cherche Photoshop / Lightroom Classic aux emplacements d'installation habituels."""
    if WINDOWS:
        motifs = {
            "photoshop": [r"C:\Program Files\Adobe\Adobe Photoshop*\Photoshop.exe"],
            "lightroom": [r"C:\Program Files\Adobe\Adobe Lightroom Classic*\Lightroom.exe",
                          r"C:\Program Files\Adobe\Adobe Lightroom*\Lightroom.exe"],
        }[nom]
    elif MAC:
        motifs = {
            "photoshop": ["/Applications/Adobe Photoshop*/Adobe Photoshop*.app"],
            "lightroom": ["/Applications/Adobe Lightroom Classic*/Adobe Lightroom Classic*.app",
                          "/Applications/Adobe Lightroom Classic.app"],
        }[nom]
    else:
        return ""
    for motif in motifs:
        trouves = sorted(glob.glob(motif))
        if trouves:
            return trouves[-1]  # la version la plus récente
    return ""


def ouvrir_avec(logiciel: str, fichiers: list[Path]):
    """Ouvre des fichiers dans un logiciel (Photoshop, Lightroom…), ou juste le logiciel."""
    fichiers = [str(f) for f in fichiers]
    if not logiciel:
        raise FileNotFoundError("Chemin du logiciel non renseigné (voir Réglages).")
    if MAC:
        subprocess.Popen(["open", "-a", logiciel, *fichiers])
    else:
        if not Path(logiciel).exists():
            raise FileNotFoundError(f"Logiciel introuvable : {logiciel}")
        subprocess.Popen([logiciel, *fichiers])


def ouvrir_dossier(chemin: Path, selectionner: Path | None = None):
    """Ouvre l'explorateur de fichiers (en sélectionnant le fichier si donné)."""
    if WINDOWS:
        if selectionner:
            subprocess.Popen(["explorer", "/select,", str(selectionner)])
        else:
            os.startfile(str(chemin))  # type: ignore[attr-defined]
    elif MAC:
        subprocess.Popen(["open", "-R", str(selectionner)] if selectionner else ["open", str(chemin)])
    else:
        subprocess.Popen(["xdg-open", str(chemin)])


def ouvrir_par_defaut(fichier: Path):
    if WINDOWS:
        os.startfile(str(fichier))  # type: ignore[attr-defined]
    elif MAC:
        subprocess.Popen(["open", str(fichier)])
    else:
        subprocess.Popen(["xdg-open", str(fichier)])
