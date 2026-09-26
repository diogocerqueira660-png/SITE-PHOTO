import os
import sys
import tempfile
import time
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import noyau  # noqa: E402
from noyau import PICK, REJET, Shooting  # noqa: E402


def ecrire(chemin: Path, contenu: bytes = b"x", age: float = 0):
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_bytes(contenu)
    if age:
        t = time.time() - age
        os.utime(chemin, (t, t))
    return chemin


def image(chemin: Path, taille=(600, 400), couleur="red"):
    from PIL import Image
    chemin.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", taille, couleur).save(chemin)
    return chemin


class TestCle(unittest.TestCase):
    def test_versions_lightroom_photoshop(self):
        for nom in ("IMG_1234.CR3", "IMG_1234-Edit.tif", "IMG_1234-Edit-2.psd", "IMG_1234-Modifier.tif",
                    "IMG_1234_web.jpg", "IMG_1234-Edit_insta.jpg", "IMG_1234 copie.jpg", "IMG_1234 (2).jpg",
                    "img_1234_final.jpg"):
            self.assertEqual(noyau.cle_photo(nom), "img_1234", nom)

    def test_noms_renommes(self):
        self.assertEqual(noyau.cle_photo("2026-09-26_Porsche-911_0007-Edit.psd"), "2026-09-26_porsche-911_0007")
        self.assertNotEqual(noyau.cle_photo("DSC_0001.NEF"), noyau.cle_photo("DSC_0002.NEF"))


class TestShooting(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.bib = Path(self.tmp.name)
        self.s = Shooting.creer(self.bib, "Porsche 911 GT3", "Lucas", date(2026, 9, 26))

    def tearDown(self):
        self.tmp.cleanup()

    def test_creation(self):
        self.assertEqual(self.s.nom, "2026-09-26_Porsche-911-GT3_Lucas")
        for _, dossier, _ in noyau.ETAPES:
            self.assertTrue((self.s.dossier / dossier).is_dir())
        self.assertEqual([x.nom for x in noyau.lister_shootings(self.bib)], [self.s.nom])
        with self.assertRaises(FileExistsError):
            Shooting.creer(self.bib, "Porsche 911 GT3", "Lucas", date(2026, 9, 26))

    def test_suivi_des_etapes(self):
        d = self.s.dossier
        ecrire(d / "01_RAW/IMG_1.CR3")
        ecrire(d / "01_RAW/IMG_1.JPG")
        ecrire(d / "01_RAW/IMG_2.CR3")
        ecrire(d / "01_RAW/IMG_2-Edit.tif")          # « Modifier dans Photoshop » de Lightroom
        ecrire(d / "01_RAW/IMG_3.CR3")
        ecrire(d / "02_LIGHTROOM/IMG_3.tif")
        ecrire(d / "03_PHOTOSHOP/IMG_3-Edit.psd")
        ecrire(d / "04_FINAL/IMG_3.jpg")
        ecrire(d / "05_WEB/IMG_3_insta.jpg")
        photos = {p.cle: p for p in self.s.analyser()}
        self.assertEqual(set(photos), {"img_1", "img_2", "img_3"})
        self.assertEqual(photos["img_1"].etapes, ["RAW"])
        self.assertEqual(len(photos["img_1"].fichiers["RAW"]), 2)
        self.assertEqual(photos["img_2"].etapes, ["RAW", "LR"])
        self.assertEqual(photos["img_3"].etapes, ["RAW", "LR", "PS", "FINAL", "WEB"])
        self.assertEqual(photos["img_1"].etat, "À trier")
        self.assertEqual(photos["img_2"].etat, "Développée")
        self.assertEqual(photos["img_3"].etat, "Terminée")
        self.assertEqual(photos["img_2"].fichier_pour_photoshop().name, "IMG_2-Edit.tif")
        self.assertEqual(photos["img_3"].fichier_pour_photoshop().name, "IMG_3-Edit.psd")
        self.assertEqual(photos["img_1"].fichier_pour_photoshop().name, "IMG_1.CR3")
        self.assertEqual(photos["img_1"].fichier_apercu().suffix, ".JPG")

    def test_notes_enregistrees(self):
        ecrire(self.s.dossier / "01_RAW/IMG_1.CR3")
        ecrire(self.s.dossier / "01_RAW/IMG_2.CR3")
        p1, p2 = self.s.analyser()
        p1.note, p1.choix, p1.commentaire = 4, PICK, "reflet portière"
        p2.choix = REJET
        self.s.enregistrer()
        s2 = Shooting(self.s.dossier)
        p1, p2 = s2.analyser()
        self.assertEqual((p1.note, p1.choix, p1.commentaire), (4, PICK, "reflet portière"))
        self.assertEqual(p2.etat, "Rejetée")
        r = s2.resume()
        self.assertEqual((r["total"], r["objectif"], r["terminees"]), (2, 1, 0))

    def test_ranger(self):
        d = self.s.dossier
        ecrire(d / "IMG_9.CR3")
        ecrire(d / "IMG_9.xmp")
        ecrire(d / "IMG_9-Edit.tif")
        ecrire(d / "IMG_9_final.jpg")
        ecrire(d / "02_LIGHTROOM/IMG_8-Edit.psd")
        ecrire(d / "01_RAW/IMG_7-Edit.psd")  # à côté du RAW : Lightroom le suit, on n'y touche pas
        plan = {s.name: dst.parent.name for s, dst in self.s.a_ranger()}
        self.assertEqual(plan, {"IMG_9.CR3": "01_RAW", "IMG_9.xmp": "01_RAW", "IMG_9-Edit.tif": "02_LIGHTROOM",
                                "IMG_9_final.jpg": "04_FINAL", "IMG_8-Edit.psd": "03_PHOTOSHOP"})
        self.assertEqual(self.s.ranger(), 5)
        self.assertEqual(self.s.a_ranger(), [])
        self.assertTrue((d / "03_PHOTOSHOP/IMG_8-Edit.psd").exists())
        self.assertTrue((d / "01_RAW/IMG_7-Edit.psd").exists())


class TestImport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.carte = base / "SD/DCIM/100CANON"
        ecrire(self.carte / "IMG_0002.CR3", b"b" * 20, age=50)
        ecrire(self.carte / "IMG_0002.JPG", b"bj", age=50)
        ecrire(self.carte / "IMG_0001.CR3", b"a" * 10, age=100)
        ecrire(self.carte / "notes.txt")
        self.dest = base / "shoot/01_RAW"

    def tearDown(self):
        self.tmp.cleanup()

    def test_renommage_et_doublons(self):
        plan = noyau.preparer_import(self.carte.parent, self.dest, "2026-09-26_M3")
        noms = [(s.name, d.name) for s, d in plan]
        self.assertEqual(noms, [("IMG_0001.CR3", "2026-09-26_M3_0001.CR3"),
                                ("IMG_0002.CR3", "2026-09-26_M3_0002.CR3"),
                                ("IMG_0002.JPG", "2026-09-26_M3_0002.JPG")])
        self.assertEqual(noyau.importer(plan), 3)
        self.assertEqual((self.dest / "2026-09-26_M3_0002.CR3").read_bytes(), b"b" * 20)
        # Deuxième import de la même carte : rien de nouveau
        self.assertEqual(noyau.preparer_import(self.carte.parent, self.dest, "2026-09-26_M3"), [])
        # Nouvelle photo sur la carte : numérotation qui continue
        ecrire(self.carte / "IMG_0003.CR3", b"c")
        plan = noyau.preparer_import(self.carte.parent, self.dest, "2026-09-26_M3")
        self.assertEqual([d.name for _, d in plan], ["2026-09-26_M3_0003.CR3"])

    def test_sans_renommage(self):
        plan = noyau.preparer_import(self.carte.parent, self.dest)
        noyau.importer(plan)
        self.assertEqual(sorted(f.name for f in self.dest.iterdir() if not f.name.startswith(".")),
                         ["IMG_0001.CR3", "IMG_0002.CR3", "IMG_0002.JPG"])
        self.assertEqual(noyau.preparer_import(self.carte.parent, self.dest), [])


class TestXmp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raw = ecrire(Path(self.tmp.name) / "IMG_1.CR3")

    def tearDown(self):
        self.tmp.cleanup()

    def test_creation_et_lecture(self):
        self.assertIsNone(noyau.lire_note_xmp(self.raw))
        noyau.ecrire_note_xmp(self.raw, 4)
        self.assertEqual(noyau.lire_note_xmp(self.raw), 4)
        noyau.ecrire_note_xmp(self.raw, -1)
        self.assertEqual(noyau.lire_note_xmp(self.raw), -1)

    def test_xmp_lightroom_existant(self):
        xmp = self.raw.with_suffix(".xmp")
        original = ('<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
                    '<rdf:Description rdf:about="" xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/" '
                    'crs:Exposure2012="+0.35"></rdf:Description></rdf:RDF></x:xmpmeta>')
        xmp.write_text(original)
        noyau.ecrire_note_xmp(self.raw, 3)
        texte = xmp.read_text()
        self.assertIn('crs:Exposure2012="+0.35"', texte)  # les réglages Lightroom sont conservés
        self.assertIn('xmlns:xmp="http://ns.adobe.com/xap/1.0/"', texte)
        self.assertEqual(noyau.lire_note_xmp(self.raw), 3)
        noyau.ecrire_note_xmp(self.raw, 5)
        self.assertEqual(xmp.read_text().count("xmp:Rating"), 1)
        self.assertEqual(noyau.lire_note_xmp(self.raw), 5)

    def test_aller_retour_photos(self):
        p = noyau.Photo("img_1", {"RAW": [self.raw]}, note=2)
        self.assertEqual(noyau.exporter_notes_xmp([p]), 1)
        noyau.ecrire_note_xmp(self.raw, 5)  # l'utilisateur change la note dans Lightroom
        self.assertEqual(noyau.importer_notes_xmp([p]), 1)
        self.assertEqual(p.note, 5)


class TestExportWeb(unittest.TestCase):
    def test_formats(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            src = image(Path(tmp) / "04_FINAL/IMG_1.jpg", (4000, 2667))
            dest = Path(tmp) / "05_WEB"
            (web,) = noyau.exporter_web([src], dest, "Long côté 2048 px (site)", filigrane="Diogo")
            with Image.open(web) as im:
                self.assertEqual(max(im.size), 2048)
            (insta,) = noyau.exporter_web([src], dest, "Instagram 4:5 (1080×1350)")
            with Image.open(insta) as im:
                self.assertEqual(im.size, (1080, 1350))
            self.assertEqual({web.name, insta.name}, {"IMG_1_web.jpg", "IMG_1_insta.jpg"})
            self.assertEqual(noyau.cle_photo(insta.name), "img_1")


class TestApercus(unittest.TestCase):
    def test_jpeg_cache_dans_un_raw(self):
        import io
        from PIL import Image
        os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp()
        import apercus
        grand, petit = io.BytesIO(), io.BytesIO()
        Image.new("RGB", (1600, 1067), "blue").save(grand, "JPEG")
        Image.new("RGB", (160, 120), "green").save(petit, "JPEG")
        with tempfile.TemporaryDirectory() as tmp:
            raw = ecrire(Path(tmp) / "IMG_1.CR3", b"\x00" * 500 + petit.getvalue() + b"\xff\xd8\xff\x00"
                         + b"\x01" * 300 + grand.getvalue() + b"\x00" * 1000)
            im = apercus.miniature(raw, 200)
            self.assertEqual(im.width, 200)
            r, g, b = im.getpixel((100, 60))
            self.assertGreater(b, 200)  # c'est bien le grand aperçu (bleu), pas la vignette verte
            illisible = ecrire(Path(tmp) / "IMG_2.NEF", b"rien")
            self.assertEqual(apercus.miniature(illisible, 200).width, 200)


if __name__ == "__main__":
    unittest.main()
