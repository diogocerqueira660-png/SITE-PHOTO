"""Miniatures des photos (JPG, TIFF, PSD, et RAW via l'aperçu JPEG intégré au fichier).

Les miniatures sont gardées en cache pour que l'appli s'ouvre vite la fois suivante.
"""

from __future__ import annotations

import hashlib
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFile, ImageOps

from noyau import EXT_RAW

ImageFile.LOAD_TRUNCATED_IMAGES = True
Image.MAX_IMAGE_PIXELS = None  # grands panoramas / PSB

try:  # facultatif : meilleur rendu des RAW si installé (pip install rawpy)
    import rawpy  # type: ignore
except ImportError:
    rawpy = None


def dossier_cache() -> Path:
    from reglages import dossier_config
    d = dossier_config() / "miniatures"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cle_cache(chemin: Path, taille: int) -> str:
    st = chemin.stat()
    brut = f"{chemin.resolve()}|{st.st_size}|{int(st.st_mtime)}|{taille}"
    return hashlib.sha1(brut.encode("utf-8")).hexdigest()


def miniature(chemin: Path, taille: int = 240) -> Image.Image:
    """Renvoie une miniature RGB (depuis le cache si possible)."""
    try:
        cache = dossier_cache() / f"{_cle_cache(chemin, taille)}.jpg"
    except OSError:
        cache = None
    if cache and cache.is_file():
        try:
            with Image.open(cache) as im:
                return im.convert("RGB")
        except OSError:
            pass
    try:
        im = _ouvrir(chemin, taille)
        im.thumbnail((taille, taille), Image.LANCZOS)
    except Exception:  # fichier illisible : on affiche une vignette avec l'extension
        return vignette_texte(chemin.suffix.upper().lstrip(".") or "?", taille)
    if cache:
        try:
            im.save(cache, "JPEG", quality=85)
        except OSError:
            pass
    return im


def _ouvrir(chemin: Path, taille: int) -> Image.Image:
    if chemin.suffix.lower() in EXT_RAW:
        return _apercu_raw(chemin, taille)
    im = Image.open(chemin)
    im.draft("RGB", (taille * 2, taille * 2))  # décodage JPEG rapide en taille réduite
    im = ImageOps.exif_transpose(im)
    return _en_rgb(im)


def _en_rgb(im: Image.Image) -> Image.Image:
    if im.mode in ("I;16", "I;16B", "I;16L", "I"):
        im = im.point(lambda v: v / 256).convert("L")
    if im.mode == "CMYK":
        im = im.convert("RGB")
    return im.convert("RGB")


def _apercu_raw(chemin: Path, taille: int) -> Image.Image:
    if rawpy is not None:
        try:
            with rawpy.imread(str(chemin)) as raw:
                thumb = raw.extract_thumb()
            if thumb.format == rawpy.ThumbFormat.JPEG:
                im = Image.open(io.BytesIO(thumb.data))
            else:
                im = Image.fromarray(thumb.data)
            return _en_rgb(ImageOps.exif_transpose(im))
        except Exception:
            pass
    return _jpeg_integre(chemin, taille)


def _jpeg_integre(chemin: Path, taille: int) -> Image.Image:
    """Cherche le plus grand JPEG caché dans le RAW (tous les boîtiers en mettent un)."""
    data = chemin.read_bytes()
    meilleur, pixels = None, 0
    debut, essais = 0, 0
    while essais < 40:
        i = data.find(b"\xff\xd8\xff", debut)
        if i < 0:
            break
        debut = i + 3
        if i + 3 >= len(data) or not 0xC0 <= data[i + 3] <= 0xFE:
            continue  # pas un vrai début de JPEG (octets au hasard dans les données RAW)
        try:
            im = Image.open(_Decale(data, i))
            if im.format != "JPEG":
                continue
            essais += 1
            n = im.width * im.height
            if n > pixels:
                meilleur, pixels = (i, im), n
        except Exception:
            continue
    if not meilleur:
        raise ValueError("pas d'aperçu intégré")
    debut, _ = meilleur
    im = Image.open(io.BytesIO(data[debut:]))  # une seule vraie copie, pour le décodage
    im.draft("RGB", (taille * 2, taille * 2))
    im.load()
    return _en_rgb(ImageOps.exif_transpose(im))


class _Decale(io.RawIOBase):
    """Vue « fichier » sur data[debut:] sans recopier les dizaines de Mo du RAW."""

    def __init__(self, data: bytes, debut: int):
        self._vue = memoryview(data)[debut:]
        self._pos = 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def read(self, n=-1):
        fin = len(self._vue) if n is None or n < 0 else min(len(self._vue), self._pos + n)
        morceau = bytes(self._vue[self._pos:fin])
        self._pos = fin
        return morceau

    def seek(self, pos, whence=0):
        base = {0: 0, 1: self._pos, 2: len(self._vue)}[whence]
        self._pos = max(0, base + pos)
        return self._pos

    def tell(self):
        return self._pos


def vignette_texte(texte: str, taille: int) -> Image.Image:
    im = Image.new("RGB", (taille, int(taille * 2 / 3)), "#2b2f36")
    d = ImageDraw.Draw(im)
    x0, y0, x1, y1 = d.textbbox((0, 0), texte)
    d.text(((im.width - (x1 - x0)) / 2, (im.height - (y1 - y0)) / 2), texte, fill="#9aa3ad")
    return im


def grand_apercu(chemin: Path, taille: int = 1600) -> Image.Image:
    return miniature(chemin, taille)
