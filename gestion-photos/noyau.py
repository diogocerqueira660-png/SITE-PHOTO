"""Cœur de l'appli : shootings, flux de travail, import, rangement, XMP, export.

Aucune dépendance à l'interface graphique : tout ce fichier peut être testé seul.

Organisation d'un shooting sur le disque :

    2026-09-26_Porsche-911-GT3_Lucas/
        shooting.json      -> infos du shooting + notes / choix / commentaires des photos
        01_RAW/            -> fichiers de l'appareil (importés de la carte SD)
        02_PHOTOSHOP/      -> TIF / PSD retouchés dans Photoshop
                              (ceux créés par Lightroom à côté des RAW comptent aussi)
        03_JPG/            -> JPG terminés (exportés / « décompressés » par Lightroom)
        04_WEB/            -> versions réduites pour le site / Instagram

Le flux de travail (les étapes de retouche) est réglable : par défaut
Lightroom (éclairage) -> Photoshop -> Lightroom (export JPG).
"""

from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

# --------------------------------------------------------------------------- dossiers

DOSSIERS = [
    ("RAW", "01_RAW", "RAW"),
    ("TIF", "02_PHOTOSHOP", "TIF / PSD"),
    ("JPG", "03_JPG", "JPG final"),
    ("WEB", "04_WEB", "Web"),
]
CODES_DOSSIERS = [d[0] for d in DOSSIERS]
DOSSIER_ETAPE = {code: dossier for code, dossier, _ in DOSSIERS}
NOM_DOSSIER = {code: nom for code, _, nom in DOSSIERS}
# Anciens noms de dossiers (premières versions de l'appli) toujours reconnus
ANCIENS_DOSSIERS = {"TIF": ["02_LIGHTROOM", "03_PHOTOSHOP"], "JPG": ["04_FINAL"], "WEB": ["05_WEB"]}
DOSSIER_VERS_CODE = {d.lower(): c for c, d, _ in DOSSIERS}
for _code, _anciens in ANCIENS_DOSSIERS.items():
    for _a in _anciens:
        DOSSIER_VERS_CODE[_a.lower()] = _code

FICHIER_SHOOTING = "shooting.json"

EXT_RAW = {".cr2", ".cr3", ".crw", ".nef", ".nrw", ".arw", ".srf", ".sr2", ".raf", ".orf",
           ".rw2", ".pef", ".dng", ".srw", ".x3f", ".3fr", ".iiq", ".erf", ".mef", ".mos", ".raw"}
EXT_TIFF = {".tif", ".tiff"}
EXT_PSD = {".psd", ".psb"}
EXT_JPG = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp"}
EXT_IMAGES = EXT_RAW | EXT_TIFF | EXT_PSD | EXT_JPG
EXT_ANNEXES = {".xmp"}  # fichiers « compagnons » qui suivent le RAW

# Choix de tri d'une photo
PICK, REJET, AUCUN = "pick", "rejet", ""

# Suffixes ajoutés par Lightroom / Photoshop / l'utilisateur, retirés pour
# retrouver la photo d'origine : IMG_1234-Edit-2.tif -> IMG_1234
_SUFFIXES = r"edit|edited|modifier|modifi[ée]|modif|retouche|retouch[ée]?|ps|lr|final|web|hd|insta|net|copy|copie"
_RE_SUFFIXE = re.compile(rf"(?:[-_ ](?:{_SUFFIXES})(?:[-_ ]?\d{{1,2}})?)$", re.IGNORECASE)
_RE_COPIE = re.compile(r"(?: \(\d+\)| - copie| copie| copy)$", re.IGNORECASE)


def cle_photo(nom_fichier: str) -> str:
    """Clé commune à toutes les versions d'une même photo."""
    return nom_de_base(nom_fichier).lower()


def nom_de_base(nom_fichier: str) -> str:
    """Nom d'origine de la photo, sans extension ni suffixe de retouche."""
    base = Path(nom_fichier).stem
    precedent = None
    while base != precedent:
        precedent = base
        base = _RE_COPIE.sub("", base)
        base = _RE_SUFFIXE.sub("", base)
    return base.strip()


def etape_du_fichier(chemin: Path, racine: Path) -> str | None:
    """Type de version d'un fichier : RAW, TIF (passé dans Photoshop), JPG final ou WEB."""
    ext = chemin.suffix.lower()
    if ext in EXT_RAW:
        return "RAW"
    if ext in EXT_TIFF | EXT_PSD:
        return "TIF"
    if ext not in EXT_JPG:
        return None
    try:
        premier = chemin.relative_to(racine).parts[0].lower()
    except (ValueError, IndexError):
        premier = ""
    code = DOSSIER_VERS_CODE.get(premier)
    if code == "TIF":
        return "JPG"  # JPG enregistré à côté des TIF : c'est une version finie
    return code  # RAW (JPG de l'appareil), JPG, WEB, ou None si en vrac


# --------------------------------------------------------------------------- flux de travail

LOGICIELS = {"lightroom": "Lightroom", "photoshop": "Photoshop", "aucun": "Aucun logiciel"}
PREUVES = {
    "manuel": "Je la coche moi-même",
    "tif": "Un TIF / PSD apparaît",
    "jpg": "Un JPG apparaît dans 03_JPG",
}


@dataclass
class Etape:
    id: str
    nom: str
    logiciel: str = "aucun"
    preuve: str = "manuel"

    def en_dict(self) -> dict:
        return {"id": self.id, "nom": self.nom, "logiciel": self.logiciel, "preuve": self.preuve}


MODELES_FLUX = {
    "Lightroom → Photoshop → Lightroom": [
        Etape("lr1", "Lightroom · éclairage", "lightroom", "manuel"),
        Etape("ps", "Photoshop · retouche", "photoshop", "tif"),
        Etape("lr2", "Lightroom · export JPG", "lightroom", "jpg"),
    ],
    "Lightroom → Photoshop": [
        Etape("lr1", "Lightroom · éclairage", "lightroom", "manuel"),
        Etape("ps", "Photoshop · retouche + JPG", "photoshop", "jpg"),
    ],
    "Photoshop → Lightroom": [
        Etape("ps", "Photoshop · retouche", "photoshop", "tif"),
        Etape("lr2", "Lightroom · export JPG", "lightroom", "jpg"),
    ],
    "Lightroom seulement": [
        Etape("lr", "Lightroom · retouche + export", "lightroom", "jpg"),
    ],
}
FLUX_PAR_DEFAUT = "Lightroom → Photoshop → Lightroom"


def flux_depuis(donnees) -> list[Etape]:
    """Flux enregistré dans les réglages -> liste d'étapes (flux par défaut si vide/invalide)."""
    etapes = []
    for d in donnees or []:
        try:
            e = Etape(str(d["id"]), str(d["nom"]).strip() or "Étape",
                      d.get("logiciel", "aucun"), d.get("preuve", "manuel"))
        except (KeyError, TypeError, AttributeError):
            continue
        if e.logiciel not in LOGICIELS:
            e.logiciel = "aucun"
        if e.preuve not in PREUVES:
            e.preuve = "manuel"
        etapes.append(e)
    return etapes or [Etape(**e.en_dict()) for e in MODELES_FLUX[FLUX_PAR_DEFAUT]]


def nouvel_id_etape(flux: list[Etape]) -> str:
    pris = {e.id for e in flux}
    i = 1
    while f"e{i}" in pris:
        i += 1
    return f"e{i}"


# --------------------------------------------------------------------------- modèle

A_TRIER, TERMINEE, REJETEE = "À trier", "Terminée", "Rejetée"


@dataclass
class Photo:
    cle: str
    fichiers: dict[str, list[Path]] = field(default_factory=dict)  # RAW/TIF/JPG/WEB -> fichiers
    note: int = 0
    choix: str = AUCUN
    faites: set[str] = field(default_factory=set)  # étapes cochées à la main
    envoyee: str = ""                              # étape en cours dans un logiciel
    commentaire: str = ""

    @property
    def versions(self) -> list[str]:
        return [c for c in CODES_DOSSIERS if self.fichiers.get(c)]

    @property
    def nom(self) -> str:
        for c in CODES_DOSSIERS:
            if self.fichiers.get(c):
                return self.fichiers[c][0].name
        return self.cle

    def dernier(self, code: str) -> Path | None:
        f = self.fichiers.get(code)
        return max(f, key=lambda p: p.stat().st_mtime) if f else None

    def raw(self) -> Path | None:
        raws = self.fichiers.get("RAW", [])
        vrais = [f for f in raws if f.suffix.lower() in EXT_RAW]
        return (vrais or raws or [None])[0]  # le RAW plutôt que le JPG de l'appareil

    def _preuve(self, preuve: str) -> bool:
        if preuve == "tif":
            return bool(self.fichiers.get("TIF"))
        if preuve == "jpg":
            return bool(self.fichiers.get("JPG") or self.fichiers.get("WEB"))
        return False

    def etapes_faites(self, flux: list[Etape]) -> list[bool]:
        """Une étape est faite si elle est cochée ou si son fichier existe.
        Le flux est linéaire : si une étape est faite, celles d'avant aussi."""
        faites = [e.id in self.faites or self._preuve(e.preuve) for e in flux]
        if self.fichiers.get("TIF"):
            # un TIF/PSD existe : tout ce qui précède Photoshop est forcément fait
            ps = next((i for i, e in enumerate(flux) if e.logiciel == "photoshop"), 0)
            if ps > 0:
                faites[ps - 1] = True
        derniere = max((i for i, f in enumerate(faites) if f), default=-1)
        return [i <= derniere for i in range(len(flux))]

    def prochaine(self, flux: list[Etape]) -> Etape | None:
        for e, faite in zip(flux, self.etapes_faites(flux)):
            if not faite:
                return e
        return None

    def colonne(self, flux: list[Etape]) -> str:
        """Où en est la photo : À trier, id d'une étape, Terminée ou Rejetée."""
        if self.choix == REJET:
            return REJETEE
        faites = self.etapes_faites(flux)
        if all(faites):
            return TERMINEE
        if self.choix != PICK and not any(faites) and not self.envoyee:
            return A_TRIER
        return self.prochaine(flux).id

    def etat(self, flux: list[Etape]) -> str:
        col = self.colonne(flux)
        if col in (A_TRIER, TERMINEE, REJETEE):
            return col
        e = self.prochaine(flux)
        if self.envoyee == e.id and e.logiciel != "aucun":
            return f"Chez {LOGICIELS[e.logiciel]}"
        return e.nom

    def fichier_a_ouvrir(self) -> Path | None:
        """Le meilleur fichier à ouvrir : la version Photoshop (TIF/PSD) si elle existe, sinon le RAW."""
        return self.dernier("TIF") or self.raw() or self.dernier("JPG")

    def envoyer(self, flux: list[Etape], etape: Etape):
        """La photo part à cette étape : celles d'avant sont considérées comme faites."""
        for e in flux:
            if e.id == etape.id:
                break
            self.faites.add(e.id)
        self.envoyee = etape.id

    def marquer_faite(self, flux: list[Etape]):
        """Coche l'étape en cours (et donc celles d'avant)."""
        e = self.prochaine(flux)
        if e:
            self.envoyer(flux, e)
            self.faites.add(e.id)
            self.envoyee = ""
        if self.choix == AUCUN:
            self.choix = PICK

    def fichier_apercu(self) -> Path | None:
        """Fichier le plus abouti, pour la miniature."""
        for code in ("JPG", "WEB", "TIF", "RAW"):
            fichiers = self.fichiers.get(code)
            if fichiers:
                jpg = [f for f in fichiers if f.suffix.lower() in EXT_JPG]
                return (jpg or fichiers)[0]  # un JPG s'affiche plus vite qu'un RAW
        return None


def nom_dossier_shooting(jour: date, voiture: str, client: str = "") -> str:
    morceaux = [jour.isoformat(), voiture.strip(), client.strip()]
    nom = "_".join(m for m in morceaux if m)
    nom = re.sub(r"[\\/:*?\"<>|]+", "", nom)
    return re.sub(r"\s+", "-", nom)


class Shooting:
    def __init__(self, dossier: Path | str):
        self.dossier = Path(dossier)
        self.infos: dict = {"voiture": "", "client": "", "date": "", "notes": ""}
        self.meta: dict[str, dict] = {}
        self.photos: list[Photo] = []
        self._charger_meta()

    # -- création / fichiers
    @classmethod
    def creer(cls, bibliotheque: Path | str, voiture: str, client: str = "",
              jour: date | None = None, notes: str = "") -> "Shooting":
        jour = jour or date.today()
        dossier = Path(bibliotheque) / nom_dossier_shooting(jour, voiture, client)
        if dossier.exists() and (dossier / FICHIER_SHOOTING).exists():
            raise FileExistsError(f"Le shooting existe déjà : {dossier.name}")
        for _, sous_dossier, _ in DOSSIERS:
            (dossier / sous_dossier).mkdir(parents=True, exist_ok=True)
        s = cls(dossier)
        s.infos.update({"voiture": voiture.strip(), "client": client.strip(),
                        "date": jour.isoformat(), "notes": notes})
        s.enregistrer()
        return s

    @staticmethod
    def est_shooting(dossier: Path) -> bool:
        return (dossier / FICHIER_SHOOTING).is_file() or (dossier / "01_RAW").is_dir()

    @property
    def nom(self) -> str:
        return self.dossier.name

    def chemin_etape(self, code: str) -> Path:
        """Dossier d'un type de fichier (reprend un ancien nom de dossier s'il existe)."""
        nouveau = self.dossier / DOSSIER_ETAPE[code]
        if nouveau.is_dir():
            return nouveau
        for ancien in ANCIENS_DOSSIERS.get(code, []):
            if (self.dossier / ancien).is_dir():
                return self.dossier / ancien
        return nouveau

    def _charger_meta(self):
        f = self.dossier / FICHIER_SHOOTING
        if f.is_file():
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                data = {}
            self.infos.update(data.get("infos", {}))
            self.meta = data.get("photos", {})

    def enregistrer(self):
        for p in self.photos:
            m = {k: v for k, v in (("note", p.note), ("choix", p.choix),
                                   ("faites", sorted(p.faites)), ("envoyee", p.envoyee),
                                   ("commentaire", p.commentaire)) if v}
            if m:
                self.meta[p.cle] = m
            else:
                self.meta.pop(p.cle, None)
        data = {"infos": self.infos, "photos": self.meta,
                "modifie": datetime.now().isoformat(timespec="seconds")}
        tmp = self.dossier / (FICHIER_SHOOTING + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.dossier / FICHIER_SHOOTING)

    # -- analyse du dossier
    def fichiers_images(self):
        for chemin in sorted(self.dossier.rglob("*")):
            if not chemin.is_file() or chemin.name.startswith("."):
                continue
            if any(part.startswith(".") for part in chemin.relative_to(self.dossier).parts):
                continue
            code = etape_du_fichier(chemin, self.dossier)
            if code:
                yield code, chemin

    def analyser(self) -> list[Photo]:
        par_cle: dict[str, Photo] = {}
        for code, chemin in self.fichiers_images():
            cle = cle_photo(chemin.name)
            photo = par_cle.setdefault(cle, Photo(cle))
            photo.fichiers.setdefault(code, []).append(chemin)
        for cle, photo in par_cle.items():
            m = self.meta.get(cle, {})
            photo.note = int(m.get("note", 0))
            photo.choix = m.get("choix", AUCUN)
            photo.faites = set(m.get("faites", []))
            photo.envoyee = m.get("envoyee", "")
            photo.commentaire = m.get("commentaire", "")
        self.photos = sorted(par_cle.values(), key=lambda p: p.cle)
        return self.photos

    def resume(self, flux: list[Etape]) -> dict:
        if not self.photos:
            self.analyser()
        colonnes = {A_TRIER: 0, **{e.id: 0 for e in flux}, TERMINEE: 0, REJETEE: 0}
        for p in self.photos:
            colonnes[p.colonne(flux)] += 1
        en_cours = sum(v for k, v in colonnes.items() if k not in (A_TRIER, REJETEE))
        objectif = en_cours or (len(self.photos) - colonnes[REJETEE])
        finies = colonnes[TERMINEE]
        return {"total": len(self.photos), "colonnes": colonnes, "objectif": objectif,
                "terminees": finies,
                "progression": round(100 * finies / objectif) if objectif else 0}

    def a_ranger(self) -> list[tuple[Path, Path]]:
        """Fichiers posés en vrac à la racine du shooting -> dossier où ils vont.

        Les TIF/PSD créés par Lightroom à côté des RAW ne sont jamais déplacés :
        Lightroom perdrait leur trace dans son catalogue.
        """
        mouvements = []
        for chemin in sorted(self.dossier.iterdir()):
            ext = chemin.suffix.lower()
            if not chemin.is_file() or ext not in EXT_IMAGES | EXT_ANNEXES:
                continue
            if ext in EXT_RAW or ext in EXT_ANNEXES:
                code = "RAW"
            elif ext in EXT_TIFF | EXT_PSD:
                code = "TIF"
            else:
                code = "JPG"
            mouvements.append((chemin, self.chemin_etape(code) / chemin.name))
        return mouvements

    def ranger(self, mouvements: list[tuple[Path, Path]] | None = None) -> int:
        mouvements = self.a_ranger() if mouvements is None else mouvements
        n = 0
        for source, dest in mouvements:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest = nom_libre(dest)
            shutil.move(str(source), str(dest))
            n += 1
        return n


def lister_shootings(bibliotheque: Path | str) -> list[Shooting]:
    bib = Path(bibliotheque)
    if not bib.is_dir():
        return []
    shootings = [Shooting(d) for d in bib.iterdir()
                 if d.is_dir() and not d.name.startswith(".") and Shooting.est_shooting(d)]
    return sorted(shootings, key=lambda s: (s.infos.get("date") or s.nom), reverse=True)


def fichiers_de(photo: Photo) -> list[Path]:
    """Tous les fichiers d'une photo (toutes versions + fichiers .xmp à côté des RAW)."""
    fichiers = [f for liste in photo.fichiers.values() for f in liste]
    for f in list(fichiers):
        xmp = f.with_suffix(".xmp")
        if f.suffix.lower() in EXT_RAW and xmp.is_file() and xmp not in fichiers:
            fichiers.append(xmp)
    return fichiers


def mettre_a_la_corbeille(shooting: "Shooting", photos: list[Photo], corbeille=None) -> int:
    """Envoie les fichiers des photos à la corbeille de Windows / du Mac (récupérables).

    Si la corbeille du système n'est pas disponible, les fichiers sont déplacés
    dans le dossier caché « .corbeille » du shooting. Renvoie le nombre de fichiers.
    """
    if corbeille is None:
        try:
            from send2trash import send2trash as corbeille
        except ImportError:
            corbeille = None
    n = 0
    for p in photos:
        for f in fichiers_de(p):
            if not f.exists():
                continue
            try:
                if corbeille is None:
                    raise OSError("pas de corbeille système")
                corbeille(str(f))
            except OSError:
                dest = shooting.dossier / ".corbeille" / f.relative_to(shooting.dossier)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(f), str(nom_libre(dest)))
            n += 1
        shooting.meta.pop(p.cle, None)
    shooting.photos = [p for p in shooting.photos if p not in photos]
    shooting.enregistrer()
    return n


def nom_libre(chemin: Path) -> Path:
    """Évite d'écraser un fichier : IMG.jpg -> IMG (2).jpg."""
    if not chemin.exists():
        return chemin
    i = 2
    while True:
        candidat = chemin.with_name(f"{chemin.stem} ({i}){chemin.suffix}")
        if not candidat.exists():
            return candidat
        i += 1


# --------------------------------------------------------------------------- import

def preparer_import(source: Path | str, destination: Path, renommer: str = "",
                    extensions: set[str] | None = None, debut: int = 1) -> list[tuple[Path, Path]]:
    """Liste des copies à faire depuis une carte SD / un dossier.

    `renommer` : préfixe du nouveau nom (ex. « 2026-09-26_Porsche-911 » donne
    « 2026-09-26_Porsche-911_0001.CR3 »). Les fichiers d'une même prise
    (RAW + JPG + XMP) gardent le même numéro. Vide = noms d'origine.
    Les fichiers déjà présents (même nom d'origine et même taille) sont ignorés.
    """
    extensions = extensions or (EXT_IMAGES | EXT_ANNEXES)
    source = Path(source)
    fichiers = [f for f in source.rglob("*") if f.is_file() and not f.name.startswith(".")
                and f.suffix.lower() in extensions]
    groupes: dict[tuple[Path, str], list[Path]] = {}
    for f in fichiers:
        groupes.setdefault((f.parent, f.stem.lower()), []).append(f)
    # ordre de prise de vue
    ordre = sorted(groupes.values(), key=lambda g: (min(f.stat().st_mtime for f in g), g[0].name))

    deja = _index_existants(destination)
    plan = []
    numero = debut
    if renommer:
        numero = max(debut, _prochain_numero(destination, renommer))
    for groupe in ordre:
        a_copier = [f for f in groupe if (f.name.lower(), f.stat().st_size) not in deja]
        if not a_copier:
            continue
        for f in sorted(a_copier):
            nom = f"{renommer}_{numero:04d}{f.suffix}" if renommer else f.name
            plan.append((f, destination / nom))
        if renommer:
            numero += 1
    return plan


def _index_existants(destination: Path) -> set[tuple[str, int]]:
    """(nom d'origine, taille) des fichiers déjà importés, pour éviter les doublons."""
    index = set()
    journal = destination / ".import.json"
    if journal.is_file():
        try:
            for nom, taille in json.loads(journal.read_text(encoding="utf-8")):
                index.add((nom.lower(), taille))
        except (OSError, ValueError):
            pass
    if destination.is_dir():
        for f in destination.iterdir():
            if f.is_file():
                index.add((f.name.lower(), f.stat().st_size))
    return index


def _prochain_numero(destination: Path, prefixe: str) -> int:
    motif = re.compile(re.escape(prefixe) + r"_(\d+)$", re.IGNORECASE)
    plus_grand = 0
    if destination.is_dir():
        for f in destination.iterdir():
            m = motif.match(f.stem)
            if m:
                plus_grand = max(plus_grand, int(m.group(1)))
    return plus_grand + 1


def importer(plan: list[tuple[Path, Path]], progression=None, annule=lambda: False) -> int:
    """Copie les fichiers (dates conservées) et vérifie la taille de chaque copie."""
    faits = 0
    journal_par_dossier: dict[Path, list] = {}
    for i, (source, dest) in enumerate(plan):
        if annule():
            break
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest = nom_libre(dest)
        tmp = dest.with_name(dest.name + ".partiel")
        shutil.copy2(source, tmp)
        taille = source.stat().st_size
        if tmp.stat().st_size != taille:
            tmp.unlink(missing_ok=True)
            raise IOError(f"Copie incomplète : {source}")
        os.replace(tmp, dest)
        journal_par_dossier.setdefault(dest.parent, []).append([source.name, taille])
        faits += 1
        if progression:
            progression(i + 1, len(plan), source.name)
    for dossier, entrees in journal_par_dossier.items():
        journal = dossier / ".import.json"
        anciens = []
        if journal.is_file():
            try:
                anciens = json.loads(journal.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                anciens = []
        journal.write_text(json.dumps(anciens + entrees), encoding="utf-8")
    return faits


# --------------------------------------------------------------------------- XMP (Lightroom)

_XMP_VIDE = """<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:xmp="http://ns.adobe.com/xap/1.0/"
    xmp:Rating="{note}"/>
 </rdf:RDF>
</x:xmpmeta>
"""
_RE_NOTE_ATTR = re.compile(r'xmp:Rating="(-?\d+)"')
_RE_NOTE_ELEM = re.compile(r"<xmp:Rating>(-?\d+)</xmp:Rating>")


def chemin_xmp(raw: Path) -> Path:
    return raw.with_suffix(".xmp")


def lire_note_xmp(raw: Path) -> int | None:
    xmp = chemin_xmp(raw)
    if not xmp.is_file():
        return None
    texte = xmp.read_text(encoding="utf-8", errors="ignore")
    m = _RE_NOTE_ATTR.search(texte) or _RE_NOTE_ELEM.search(texte)
    return int(m.group(1)) if m else None


def ecrire_note_xmp(raw: Path, note: int):
    """Écrit la note (0 à 5, -1 = rejet) dans le fichier .xmp lu par Lightroom."""
    xmp = chemin_xmp(raw)
    if not xmp.is_file():
        xmp.write_text(_XMP_VIDE.format(note=note), encoding="utf-8")
        return
    texte = xmp.read_text(encoding="utf-8", errors="ignore")
    if _RE_NOTE_ATTR.search(texte):
        texte = _RE_NOTE_ATTR.sub(f'xmp:Rating="{note}"', texte, count=1)
    elif _RE_NOTE_ELEM.search(texte):
        texte = _RE_NOTE_ELEM.sub(f"<xmp:Rating>{note}</xmp:Rating>", texte, count=1)
    else:
        m = re.search(r"<rdf:Description\b([^>]*?)(/?)>", texte, re.DOTALL)
        if not m:
            raise ValueError(f"Fichier XMP illisible : {xmp.name}")
        attributs = m.group(1)
        ajout = ""
        if "xmlns:xmp=" not in attributs:
            ajout += '\n    xmlns:xmp="http://ns.adobe.com/xap/1.0/"'
        ajout += f'\n    xmp:Rating="{note}"'
        texte = texte[:m.end(1)] + ajout + texte[m.end(1):]
    xmp.write_text(texte, encoding="utf-8")


def fichiers_raw_xmp(photo: Photo) -> list[Path]:
    """RAW dont Lightroom lit les notes dans un .xmp à côté (pas les DNG/JPG)."""
    return [f for f in photo.fichiers.get("RAW", [])
            if f.suffix.lower() in EXT_RAW and f.suffix.lower() != ".dng"]


def exporter_notes_xmp(photos: list[Photo]) -> int:
    n = 0
    for p in photos:
        note = -1 if p.choix == REJET else p.note
        for raw in fichiers_raw_xmp(p):
            if note == 0 and not chemin_xmp(raw).exists():
                continue
            ecrire_note_xmp(raw, note)
            n += 1
    return n


def importer_notes_xmp(photos: list[Photo]) -> int:
    n = 0
    for p in photos:
        for raw in fichiers_raw_xmp(p):
            note = lire_note_xmp(raw)
            if note is None:
                continue
            if note < 0:
                p.choix = REJET
            else:
                p.note = min(note, 5)
                if p.choix == REJET:
                    p.choix = AUCUN
            n += 1
            break
    return n


# --------------------------------------------------------------------------- export web

FORMATS_WEB = {
    "Long côté 2048 px (site)": ("long", 2048),
    "Long côté 1600 px": ("long", 1600),
    "Instagram 4:5 (1080×1350)": ("cadre", (1080, 1350)),
    "Instagram carré (1080×1080)": ("cadre", (1080, 1080)),
    "Story (1080×1920)": ("cadre", (1080, 1920)),
}


def exporter_web(sources: list[Path], dossier: Path, format_web: str,
                 qualite: int = 90, filigrane: str = "", fond: str = "#000000",
                 progression=None) -> list[Path]:
    """Crée des JPG allégés (sRGB, redimensionnés, filigrane optionnel)."""
    from PIL import Image, ImageDraw, ImageFont, ImageOps

    mode, taille = FORMATS_WEB[format_web]
    dossier.mkdir(parents=True, exist_ok=True)
    suffixe = {"Long côté 2048 px (site)": "web", "Long côté 1600 px": "web1600",
               "Instagram 4:5 (1080×1350)": "insta", "Instagram carré (1080×1080)": "carre",
               "Story (1080×1920)": "story"}[format_web]
    crees = []
    for i, source in enumerate(sources):
        with Image.open(source) as im:
            im = ImageOps.exif_transpose(im)
            if im.mode not in ("RGB", "L"):
                im = im.convert("RGB")
            im = im.convert("RGB")
            if mode == "long":
                im.thumbnail((taille, taille), Image.LANCZOS)
                sortie = im
            else:
                l, h = taille
                im.thumbnail((l, h), Image.LANCZOS)
                sortie = Image.new("RGB", (l, h), fond)
                sortie.paste(im, ((l - im.width) // 2, (h - im.height) // 2))
            if filigrane:
                _filigrane(sortie, filigrane, ImageDraw, ImageFont)
            dest = nom_libre(dossier / f"{nom_de_base(source.name)}_{suffixe}.jpg")
            sortie.save(dest, "JPEG", quality=qualite, optimize=True, progressive=True)
            crees.append(dest)
        if progression:
            progression(i + 1, len(sources), source.name)
    return crees


def _filigrane(image, texte, ImageDraw, ImageFont):
    taille = max(14, image.width // 45)
    police = None
    for nom in ("arial.ttf", "Arial.ttf", "DejaVuSans.ttf", "Helvetica.ttc"):
        try:
            police = ImageFont.truetype(nom, taille)
            break
        except OSError:
            continue
    police = police or ImageFont.load_default()
    calque = image.convert("RGBA")
    dessin = ImageDraw.Draw(calque)
    x0, y0, x1, y1 = dessin.textbbox((0, 0), texte, font=police)
    marge = taille
    pos = (image.width - (x1 - x0) - marge, image.height - (y1 - y0) - marge)
    dessin.text((pos[0] + 1, pos[1] + 1), texte, font=police, fill=(0, 0, 0, 110))
    dessin.text(pos, texte, font=police, fill=(255, 255, 255, 170))
    image.paste(calque.convert("RGB"))


def sources_pour_export(photos: list[Photo]) -> list[Path]:
    """Pour chaque photo : son JPG final (dossier 03_JPG) — la version « _net » si elle existe."""
    sources = []
    for p in photos:
        finals = p.fichiers.get("JPG", [])
        nettes = [f for f in finals if Path(f).stem.lower().endswith("_net")]
        if nettes or finals:
            sources.append(max(nettes or finals, key=lambda f: f.stat().st_mtime))
    return sources


# --------------------------------------------------------------------------- netteté

NIVEAUX_NETTETE = {
    # rayon (px), intensité (%), seuil : accentuation des détails fins
    "Légère": (0.8, 70, 2),
    "Moyenne": (1.2, 110, 2),
    "Forte": (1.8, 160, 3),
}


def accentuer(image, niveau: str = "Moyenne"):
    """Netteté sur la luminosité seulement : couleurs et éclairage restent identiques.

    On accentue une copie en niveaux de gris (les détails), puis on ajoute le même
    gain de détail aux trois canaux R, V, B : les écarts entre canaux — donc la
    teinte et la saturation — ne bougent pas. L'échelle du masque suit la taille
    de la photo pour un rendu comparable en 24 ou 45 Mpx.
    """
    from PIL import Image, ImageChops, ImageFilter

    rayon, intensite, seuil = NIVEAUX_NETTETE[niveau]
    rayon *= max(1.0, max(image.size) / 4000)
    rgb = image.convert("RGB")
    lum = rgb.convert("L")
    nette = lum.filter(ImageFilter.UnsharpMask(radius=rayon, percent=intensite, threshold=seuil))
    plus = ImageChops.subtract(nette, lum)    # détails à éclaircir
    moins = ImageChops.subtract(lum, nette)   # détails à assombrir
    canaux = [ImageChops.subtract(ImageChops.add(c, plus), moins) for c in rgb.split()]
    return Image.merge("RGB", canaux)


def nom_nettete(source: Path) -> Path:
    return source.with_name(f"{nom_de_base(source.name)}_net.jpg")


def ameliorer_nettete(sources: list[Path], niveau: str = "Moyenne", qualite: int = 96,
                      progression=None) -> list[Path]:
    """Crée une version plus nette de chaque JPG final, à côté : IMG_1234_net.jpg.

    L'original n'est jamais modifié. Le profil couleur (ICC) et les EXIF sont
    conservés, et le JPG est enregistré sans sous-échantillonnage des couleurs.
    """
    from PIL import Image, ImageOps

    crees = []
    for i, source in enumerate(sources):
        with Image.open(source) as im:
            icc = im.info.get("icc_profile")
            exif = im.info.get("exif")
            im = ImageOps.exif_transpose(im) if not exif else im
            net = accentuer(im, niveau)
        dest = nom_nettete(source)
        options = {"quality": qualite, "subsampling": 0, "optimize": True}
        if icc:
            options["icc_profile"] = icc
        if exif:
            options["exif"] = exif
        net.save(dest, "JPEG", **options)
        crees.append(dest)
        if progression:
            progression(i + 1, len(sources), source.name)
    return crees
