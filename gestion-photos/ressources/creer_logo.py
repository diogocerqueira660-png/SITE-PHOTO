"""Dessine le logo de l'appli (noir et rouge) et l'enregistre en PNG, ICO (Windows) et ICNS (Mac).

    python ressources/creer_logo.py
"""

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ICI = Path(__file__).resolve().parent
T = 1024
ROUGE = (225, 6, 0)


def degrade(taille, haut, bas):
    im = Image.new("RGB", (1, taille))
    for y in range(taille):
        t = y / (taille - 1)
        im.putpixel((0, y), tuple(round(a + (b - a) * t) for a, b in zip(haut, bas)))
    return im.resize((taille, taille))


def logo() -> Image.Image:
    # fond : carré arrondi noir, léger dégradé
    masque = Image.new("L", (T, T), 0)
    ImageDraw.Draw(masque).rounded_rectangle([40, 40, T - 40, T - 40], 220, fill=255)
    fond = degrade(T, (30, 30, 32), (6, 6, 7))
    im = Image.new("RGBA", (T, T), (0, 0, 0, 0))
    im.paste(fond, (0, 0), masque)

    c = T / 2 + 60  # objectif un peu à droite, lignes de vitesse à gauche
    # halo rouge derrière l'objectif
    halo = Image.new("RGBA", (T, T), (0, 0, 0, 0))
    ImageDraw.Draw(halo).ellipse([c - 300, T / 2 - 300, c + 300, T / 2 + 300], fill=ROUGE + (120,))
    halo = halo.filter(ImageFilter.GaussianBlur(70))
    halo.putalpha(Image.composite(halo.getchannel("A"), Image.new("L", (T, T), 0), masque))
    im = Image.alpha_composite(im, halo)

    d = ImageDraw.Draw(im)
    # bague de l'objectif
    r_ext, r_int = 300, 238
    d.ellipse([c - r_ext, T / 2 - r_ext, c + r_ext, T / 2 + r_ext], fill=ROUGE + (255,))
    d.ellipse([c - r_int, T / 2 - r_int, c + r_int, T / 2 + r_int], fill=(10, 10, 11, 255))

    # diaphragme : 6 lamelles rouges autour d'une ouverture hexagonale
    r_lame, r_trou = 218, 84
    for k in range(6):
        a = math.radians(60 * k - 90)
        a2 = math.radians(60 * (k + 1) - 90)
        p1 = (c + r_trou * math.cos(a), T / 2 + r_trou * math.sin(a))
        p2 = (c + r_trou * math.cos(a2), T / 2 + r_trou * math.sin(a2))
        # la lamelle part du bord de l'ouverture et s'enroule vers la bague
        p3 = (c + r_lame * math.cos(a2 + math.radians(22)), T / 2 + r_lame * math.sin(a2 + math.radians(22)))
        p4 = (c + r_lame * math.cos(a + math.radians(22)), T / 2 + r_lame * math.sin(a + math.radians(22)))
        teinte = 150 + 18 * (k % 3)
        d.polygon([p1, p2, p3, p4], fill=(teinte + 60, 6 + 4 * (k % 2), 0, 255))
    # séparations entre lamelles
    for k in range(6):
        a = math.radians(60 * k - 90)
        p1 = (c + r_trou * math.cos(a), T / 2 + r_trou * math.sin(a))
        p2 = (c + r_lame * math.cos(a + math.radians(22)), T / 2 + r_lame * math.sin(a + math.radians(22)))
        d.line([p1, p2], fill=(10, 10, 11, 255), width=10)

    # reflet
    reflet = Image.new("RGBA", (T, T), (0, 0, 0, 0))
    ImageDraw.Draw(reflet).ellipse([c - 200, T / 2 - 215, c - 60, T / 2 - 150], fill=(255, 255, 255, 70))
    im = Image.alpha_composite(im, reflet.filter(ImageFilter.GaussianBlur(18)))

    # lignes de vitesse (côté gauche)
    d = ImageDraw.Draw(im)
    y0 = T / 2
    for k, (y, longueur) in enumerate(((y0 - 100, 120), (y0, 170), (y0 + 100, 120))):
        x_fin = c - r_ext - 26
        d.rounded_rectangle([x_fin - longueur, y - 14, x_fin, y + 14], 14, fill=ROUGE + (255 - 70 * (k % 2),))
    im.putalpha(Image.composite(im.getchannel("A"), Image.new("L", (T, T), 0), masque))
    return im


def main():
    im = logo()
    im.save(ICI / "logo.png")
    im.resize((256, 256), Image.LANCZOS).save(ICI / "logo_256.png")
    im.save(ICI / "logo.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    im.save(ICI / "logo.icns")
    print("logo créé dans", ICI)


if __name__ == "__main__":
    main()
