"""Fenêtre principale de l'appli (tkinter)."""

from __future__ import annotations

import os
import queue
import string
import sys
import threading
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import ImageTk

import apercus
import noyau
import reglages
from noyau import AUCUN, ETATS, NOM_ETAPE, PICK, REJET, Shooting

# --------------------------------------------------------------------------- style

FOND = "#1b1e23"
PANNEAU = "#23272e"
CASE = "#2a2f37"
CASE_SEL = "#3a4250"
TEXTE = "#e6e8eb"
GRIS = "#8b95a1"
ACCENT = "#e0a526"

COULEUR_ETAPE = {"RAW": "#7f8c8d", "LR": "#3b7dd8", "PS": "#1fa2c9", "FINAL": "#27ae60", "WEB": "#8e44ad"}
COULEUR_ETAT = {"À trier": GRIS, "Choisie": ACCENT, "Développée": "#3b7dd8", "À retoucher": "#e67e22",
                "En retouche": "#1fa2c9", "Terminée": "#2ecc71", "Rejetée": "#c0392b"}

FILTRES = ["Toutes", "Non rejetées", "Choisies (P)", "3 étoiles et +"] + ETATS
TRIS = ["Nom", "Note", "État"]


def appliquer_style(racine: tk.Tk):
    style = ttk.Style(racine)
    style.theme_use("clam")
    style.configure(".", background=FOND, foreground=TEXTE, fieldbackground=CASE,
                    bordercolor=CASE, lightcolor=CASE, darkcolor=CASE, troughcolor=PANNEAU,
                    selectbackground=CASE_SEL, selectforeground=TEXTE, font=("Segoe UI", 10))
    style.configure("TFrame", background=FOND)
    style.configure("Panneau.TFrame", background=PANNEAU)
    style.configure("TLabel", background=FOND, foreground=TEXTE)
    style.configure("Panneau.TLabel", background=PANNEAU)
    style.configure("Gris.TLabel", foreground=GRIS)
    style.configure("PanneauGris.TLabel", background=PANNEAU, foreground=GRIS)
    style.configure("Titre.TLabel", font=("Segoe UI", 15, "bold"))
    style.configure("PanneauTitre.TLabel", background=PANNEAU, font=("Segoe UI", 12, "bold"))
    style.configure("TButton", background=CASE, foreground=TEXTE, padding=(10, 5), borderwidth=0, width=0)
    style.map("TButton", background=[("active", CASE_SEL), ("disabled", PANNEAU)],
              foreground=[("disabled", GRIS)])
    style.configure("Accent.TButton", background=ACCENT, foreground="#111")
    style.map("Accent.TButton", background=[("active", "#f0b83a")])
    style.configure("TMenubutton", background=CASE, foreground=TEXTE, padding=(10, 5))
    style.configure("TCheckbutton", background=PANNEAU, foreground=TEXTE)
    style.map("TCheckbutton", background=[("active", PANNEAU)])
    for type_ in ("TCheckbutton", "TRadiobutton"):
        style.configure(type_, indicatorbackground=CASE, indicatorforeground="#111", indicatormargin=(0, 0, 6, 0))
        style.map(type_, indicatorbackground=[("selected", ACCENT), ("!selected", CASE)])
    style.configure("TRadiobutton", background=FOND, foreground=TEXTE)
    style.map("TRadiobutton", background=[("active", FOND)])
    style.configure("Fond.TCheckbutton", background=FOND)
    style.map("Fond.TCheckbutton", background=[("active", FOND)])
    style.configure("TEntry", foreground=TEXTE, insertcolor=TEXTE)
    style.configure("TCombobox", foreground=TEXTE, arrowcolor=TEXTE)
    style.map("TCombobox", fieldbackground=[("readonly", CASE)], foreground=[("readonly", TEXTE)])
    racine.option_add("*TCombobox*Listbox.background", CASE)
    racine.option_add("*TCombobox*Listbox.foreground", TEXTE)
    style.configure("Treeview", background=PANNEAU, fieldbackground=PANNEAU, foreground=TEXTE,
                    rowheight=26, borderwidth=0)
    style.map("Treeview", background=[("selected", CASE_SEL)])
    style.configure("Treeview.Heading", background=CASE, foreground=GRIS, borderwidth=0)
    style.configure("Horizontal.TProgressbar", background=ACCENT, troughcolor=CASE)
    style.configure("TPanedwindow", background=FOND)
    racine.configure(bg=FOND)


# --------------------------------------------------------------------------- application

class Application:
    def __init__(self, racine: tk.Tk):
        self.racine = racine
        self.reglages = reglages.charger()
        self.shooting: Shooting | None = None
        self.photos: list[noyau.Photo] = []     # photos affichées (après filtre / tri)
        self.selection: set[int] = set()
        self.courant: int | None = None
        self.images: dict[str, ImageTk.PhotoImage] = {}  # chemin de l'aperçu -> miniature
        self.index_image: dict[str, list[int]] = {}      # chemin de l'aperçu -> cases
        self.image_detail = None
        self.generation = 0
        self.file_miniatures: queue.Queue = queue.Queue()
        self.executeur = ThreadPoolExecutor(max_workers=max(2, (os.cpu_count() or 4) // 2))
        self.signature = None

        racine.title("Gestion Photos Auto")
        racine.geometry("1440x880")
        racine.minsize(1000, 600)
        appliquer_style(racine)
        self._construire()
        self._raccourcis()

        racine.after(60, self._recevoir_miniatures)
        racine.after(4000, self._surveiller)
        racine.protocol("WM_DELETE_WINDOW", self.quitter)

        if not self.reglages["bibliotheque"] or not Path(self.reglages["bibliotheque"]).is_dir():
            racine.after(200, self.premier_lancement)
        else:
            self.actualiser_liste()

    # ------------------------------------------------------------------ construction
    def _construire(self):
        barre = ttk.Frame(self.racine, padding=(12, 10))
        barre.pack(fill="x")
        ttk.Label(barre, text="📷  Gestion Photos Auto", style="Titre.TLabel").pack(side="left")
        ttk.Button(barre, text="⚙ Réglages", command=self.ouvrir_reglages).pack(side="right")
        ttk.Button(barre, text="⤓ Importer carte SD", command=self.importer).pack(side="right", padx=6)
        ttk.Button(barre, text="＋ Nouveau shooting", style="Accent.TButton",
                   command=self.nouveau_shooting).pack(side="right")
        self.lbl_biblio = ttk.Label(barre, text="", style="Gris.TLabel")
        self.lbl_biblio.pack(side="left", padx=20)

        self.lbl_statut = ttk.Label(self.racine, text="", style="Gris.TLabel", padding=(12, 4))
        self.lbl_statut.pack(side="bottom", fill="x")
        corps = ttk.Frame(self.racine)
        corps.pack(fill="both", expand=True)

        # -- liste des shootings
        gauche = ttk.Frame(corps, style="Panneau.TFrame", padding=8, width=370)
        gauche.pack(side="left", fill="y")
        gauche.pack_propagate(False)
        ttk.Label(gauche, text="Shootings", style="PanneauTitre.TLabel").pack(anchor="w", pady=(0, 6))
        self.arbre = ttk.Treeview(gauche, columns=("date", "photos", "avancement"), show="tree headings",
                                  selectmode="browse")
        self.arbre.heading("#0", text="Voiture / client")
        self.arbre.heading("date", text="Date")
        self.arbre.heading("photos", text="Nb")
        self.arbre.heading("avancement", text="Fini")
        self.arbre.column("#0", width=150)
        self.arbre.column("date", width=92, anchor="center", stretch=False)
        self.arbre.column("photos", width=56, anchor="center", stretch=False)
        self.arbre.column("avancement", width=50, anchor="center", stretch=False)
        self.arbre.pack(fill="both", expand=True)
        self.arbre.bind("<<TreeviewSelect>>", lambda e: self._choisir_shooting())

        # -- centre : le shooting
        droite = ttk.Frame(corps, style="Panneau.TFrame", padding=10, width=340)
        droite.pack(side="right", fill="y")
        droite.pack_propagate(False)
        centre = ttk.Frame(corps, padding=(10, 6))
        centre.pack(side="left", fill="both", expand=True)
        entete = ttk.Frame(centre)
        entete.pack(fill="x")
        self.lbl_titre = ttk.Label(entete, text="Choisis ou crée un shooting", style="Titre.TLabel")
        self.lbl_titre.pack(side="left")
        self.barre_prog = ttk.Progressbar(entete, length=160, maximum=100)
        self.barre_prog.pack(side="right")

        self.lbl_resume = ttk.Label(centre, text="", style="Gris.TLabel")
        self.lbl_resume.pack(anchor="w")
        actions = ttk.Frame(centre)
        actions.pack(fill="x", pady=8)
        self.boutons_shooting = [
            ttk.Button(actions, text="Photoshop ⏎", style="Accent.TButton",
                       command=self.ouvrir_photoshop),
            ttk.Button(actions, text="Ranger le vrac", command=self.ranger),
        ]
        self.menu_lr = tk.Menu(self.racine, tearoff=0, bg=CASE, fg=TEXTE, activebackground=CASE_SEL)
        self.menu_lr.add_command(label="Appli → Lightroom : écrire les notes (XMP)", command=self.ecrire_xmp)
        self.menu_lr.add_command(label="Lightroom → Appli : lire les notes (XMP)", command=self.lire_xmp)
        self.menu_lr.add_separator()
        self.menu_lr.add_command(label="Ouvrir la sélection dans Lightroom", command=self.ouvrir_lightroom)
        lr = ttk.Menubutton(actions, text="Lightroom ▾", menu=self.menu_lr)
        self.boutons_shooting += [
            lr,
            ttk.Button(actions, text="Export web/Insta", command=self.exporter_web),
            ttk.Button(actions, text="Dossier", command=self.ouvrir_dossier_shooting),
            ttk.Button(actions, text="⟳", width=3, command=self.recharger),
        ]
        for b in self.boutons_shooting:
            b.pack(side="left", padx=(0, 6))

        filtres = ttk.Frame(centre)
        filtres.pack(fill="x", pady=(0, 8))
        self.var_tri = tk.StringVar(value="Nom")
        cb = ttk.Combobox(filtres, textvariable=self.var_tri, values=TRIS, state="readonly", width=7)
        cb.pack(side="right")
        cb.bind("<<ComboboxSelected>>", lambda e: self.appliquer_filtre())
        ttk.Label(filtres, text="Tri", style="Gris.TLabel").pack(side="right", padx=4)
        self.var_filtre = tk.StringVar(value="Toutes")
        cb = ttk.Combobox(filtres, textvariable=self.var_filtre, values=FILTRES, state="readonly", width=15)
        cb.pack(side="right", padx=(0, 10))
        cb.bind("<<ComboboxSelected>>", lambda e: self.appliquer_filtre())
        ttk.Label(filtres, text="Afficher", style="Gris.TLabel").pack(side="right", padx=4)

        grille = ttk.Frame(centre)
        grille.pack(fill="both", expand=True)
        self.toile = tk.Canvas(grille, bg=FOND, highlightthickness=0, takefocus=1)
        defil = ttk.Scrollbar(grille, orient="vertical", command=self.toile.yview)
        self.toile.configure(yscrollcommand=defil.set)
        defil.pack(side="right", fill="y")
        self.toile.pack(side="left", fill="both", expand=True)
        self.toile.bind("<Configure>", lambda e: self._redessiner_si_largeur())
        self.toile.bind("<Button-1>", self._clic)
        self.toile.bind("<Control-Button-1>", lambda e: self._clic(e, ajout=True))
        self.toile.bind("<Shift-Button-1>", lambda e: self._clic(e, etendre=True))
        self.toile.bind("<Double-Button-1>", lambda e: self.ouvrir_photoshop())
        self.toile.bind("<Button-3>", self._menu_contextuel)
        self.toile.bind("<Button-2>", self._menu_contextuel)
        for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.toile.bind(ev, self._molette)
        self._largeur = 0

        aide = ("1-5 note · P garder · X rejeter · U annuler · R à retoucher · "
                "Entrée Photoshop · Espace aperçu")
        ttk.Label(centre, text=aide, style="Gris.TLabel").pack(anchor="w", pady=(6, 0))

        # -- droite : détail de la photo
        self.lbl_apercu = tk.Label(droite, bg=PANNEAU, bd=0)
        self.lbl_apercu.pack(pady=(0, 8))
        self.lbl_nom = ttk.Label(droite, text="", style="PanneauTitre.TLabel", wraplength=310)
        self.lbl_nom.pack(anchor="w")
        self.lbl_etat = tk.Label(droite, text="", bg=PANNEAU, fg=GRIS, font=("Segoe UI", 10, "bold"))
        self.lbl_etat.pack(anchor="w", pady=(2, 8))

        etoiles = ttk.Frame(droite, style="Panneau.TFrame")
        etoiles.pack(anchor="w")
        self.btn_etoiles = []
        for n in range(1, 6):
            b = tk.Label(etoiles, text="★", font=("Segoe UI", 18), bg=PANNEAU, fg=GRIS, cursor="hand2")
            b.pack(side="left")
            b.bind("<Button-1>", lambda e, n=n: self.noter(n, bascule=True))
            self.btn_etoiles.append(b)

        choix = ttk.Frame(droite, style="Panneau.TFrame")
        choix.pack(anchor="w", pady=8, fill="x")
        ttk.Button(choix, text="✓ Garder", command=lambda: self.choisir(PICK)).pack(side="left")
        ttk.Button(choix, text="✗ Rejeter", command=lambda: self.choisir(REJET)).pack(side="left", padx=6)
        ttk.Button(choix, text="↺", width=3, command=lambda: self.choisir(AUCUN)).pack(side="left")
        self.var_retouche = tk.BooleanVar()
        ttk.Checkbutton(droite, text="À retoucher dans Photoshop", variable=self.var_retouche,
                        command=self._basculer_retouche_case).pack(anchor="w")

        ttk.Label(droite, text="Versions du fichier", style="PanneauTitre.TLabel").pack(anchor="w", pady=(14, 4))
        self.cadre_versions = ttk.Frame(droite, style="Panneau.TFrame")
        self.cadre_versions.pack(fill="x")

        ttk.Label(droite, text="Commentaire de retouche", style="PanneauTitre.TLabel").pack(anchor="w", pady=(14, 4))
        self.txt_commentaire = tk.Text(droite, height=5, width=30, bg=CASE, fg=TEXTE, insertbackground=TEXTE,
                                       relief="flat", wrap="word", font=("Segoe UI", 10))
        self.txt_commentaire.pack(fill="x")
        self.txt_commentaire.bind("<FocusOut>", lambda e: self._enregistrer_commentaire())
        ttk.Label(droite, text="ex. : enlever reflet portière, ciel plus dramatique…",
                  style="PanneauGris.TLabel", wraplength=310).pack(anchor="w")
        self._maj_boutons()

    def _raccourcis(self):
        t = self.toile
        for n in range(6):
            t.bind(str(n), lambda e, n=n: self.noter(n))
            t.bind(f"<KP_{n}>", lambda e, n=n: self.noter(n))
        for touche, action in (("p", lambda: self.choisir(PICK)), ("x", lambda: self.choisir(REJET)),
                               ("u", lambda: self.choisir(AUCUN)), ("r", self.basculer_retouche)):
            t.bind(touche, lambda e, a=action: a())
            t.bind(touche.upper(), lambda e, a=action: a())
        t.bind("<Return>", lambda e: self.ouvrir_photoshop())
        t.bind("<space>", lambda e: self.grand_apercu())
        t.bind("<Control-a>", lambda e: self.tout_selectionner())
        for touche, dx in (("<Left>", -1), ("<Right>", 1)):
            t.bind(touche, lambda e, d=dx: self.deplacer(d))
            t.bind(f"<Shift-{touche[1:]}", lambda e, d=dx: self.deplacer(d, etendre=True))
        t.bind("<Up>", lambda e: self.deplacer(-self._colonnes()))
        t.bind("<Down>", lambda e: self.deplacer(self._colonnes()))
        self.racine.bind("<F5>", lambda e: self.recharger())

    # ------------------------------------------------------------------ bibliothèque
    def premier_lancement(self):
        messagebox.showinfo(
            "Bienvenue",
            "Choisis le dossier où ranger tous tes shootings (par ex. « Photos Voitures » "
            "sur ton disque de photos).\n\nChaque shooting y aura son propre dossier "
            "RAW → Lightroom → Photoshop → Final → Web.", parent=self.racine)
        self.changer_bibliotheque()

    def changer_bibliotheque(self):
        d = filedialog.askdirectory(title="Dossier de tes shootings", parent=self.racine,
                                    initialdir=self.reglages["bibliotheque"] or str(Path.home()))
        if d:
            self.reglages["bibliotheque"] = d
            reglages.enregistrer(self.reglages)
            self.actualiser_liste()

    def actualiser_liste(self, choisir: Path | None = None):
        bib = self.reglages["bibliotheque"]
        self.lbl_biblio.configure(text=f"Bibliothèque : {bib}" if bib else "")
        garder = choisir or (self.shooting.dossier if self.shooting else None)
        self.arbre.delete(*self.arbre.get_children())
        for s in noyau.lister_shootings(bib):
            r = s.resume()
            titre = " · ".join(x for x in (s.infos.get("voiture"), s.infos.get("client")) if x) or s.nom
            self.arbre.insert("", "end", iid=str(s.dossier), text=titre,
                              values=(s.infos.get("date", ""), r["total"], f"{r['progression']} %"))
        if garder and self.arbre.exists(str(garder)):
            self.arbre.selection_set(str(garder))
            self.arbre.see(str(garder))

    def _choisir_shooting(self):
        sel = self.arbre.selection()
        if not sel:
            return
        dossier = Path(sel[0])
        if self.shooting and self.shooting.dossier == dossier:
            return
        self._enregistrer_commentaire()
        self.shooting = Shooting(dossier)
        self.images.clear()
        self.selection.clear()
        self.courant = None
        self.recharger(garder_selection=False)

    # ------------------------------------------------------------------ chargement
    def recharger(self, garder_selection: bool = True):
        if not self.shooting:
            return
        cles = {self.photos[i].cle for i in self.selection} if garder_selection else set()
        cle_courante = self.photos[self.courant].cle if garder_selection and self.courant is not None else None
        self.shooting = Shooting(self.shooting.dossier)
        self.shooting.analyser()
        self.signature = self._signature()
        self.appliquer_filtre(cles, cle_courante)
        s = self.shooting
        titre = " · ".join(x for x in (s.infos.get("voiture"), s.infos.get("client")) if x) or s.nom
        self.lbl_titre.configure(text=titre)
        self._maj_resume()
        self._maj_boutons()

    def appliquer_filtre(self, cles: set[str] | None = None, cle_courante: str | None = None):
        if not self.shooting:
            return
        if cles is None:
            cles = {self.photos[i].cle for i in self.selection}
            cle_courante = self.photos[self.courant].cle if self.courant is not None else None
        f = self.var_filtre.get()
        photos = self.shooting.photos
        if f == "Non rejetées":
            photos = [p for p in photos if p.choix != REJET]
        elif f == "Choisies (P)":
            photos = [p for p in photos if p.choix == PICK]
        elif f == "3 étoiles et +":
            photos = [p for p in photos if p.note >= 3]
        elif f in ETATS:
            photos = [p for p in photos if p.etat == f]
        tri = self.var_tri.get()
        if tri == "Note":
            photos = sorted(photos, key=lambda p: (-p.note, p.cle))
        elif tri == "État":
            photos = sorted(photos, key=lambda p: (ETATS.index(p.etat), p.cle))
        self.photos = list(photos)
        self.index_image = {}
        for i, p in enumerate(self.photos):
            self.index_image.setdefault(_cle_image(p), []).append(i)
        self.selection = {i for i, p in enumerate(self.photos) if p.cle in cles}
        self.courant = next((i for i, p in enumerate(self.photos) if p.cle == cle_courante), None)
        if self.courant is None and self.selection:
            self.courant = min(self.selection)
        self.redessiner()
        self._charger_miniatures()
        self._maj_detail()

    def _signature(self):
        """Empreinte rapide du dossier pour voir si Lightroom/Photoshop y ont écrit."""
        if not self.shooting:
            return None
        sig = []
        dossiers = [self.shooting.dossier] + [self.shooting.chemin_etape(e) for e in noyau.CODES_ETAPES]
        for d in dossiers:
            try:
                with os.scandir(d) as it:
                    for e in it:
                        if e.is_file() and not e.name.startswith("."):
                            sig.append((e.name, e.stat().st_size))
            except OSError:
                continue
        return hash(tuple(sorted(sig)))

    def _surveiller(self):
        try:
            if self.shooting and self._signature() != self.signature:
                self._enregistrer_commentaire()
                self.recharger()
                self._statut("Nouveaux fichiers détectés : liste mise à jour.")
                self.actualiser_liste()
        finally:
            self.racine.after(3000, self._surveiller)

    # ------------------------------------------------------------------ miniatures
    def _taille(self) -> int:
        return int(self.reglages.get("taille_miniatures", 200))

    def _charger_miniatures(self):
        self.generation += 1
        gen = self.generation
        taille = self._taille()
        for cle, cases in self.index_image.items():
            if cle in self.images or not cle:
                continue
            f = self.photos[cases[0]].fichier_apercu()
            self.executeur.submit(self._produire_miniature, gen, cle, f, taille)

    def _produire_miniature(self, gen, cle, fichier, taille):
        if gen != self.generation:
            return
        try:
            im = apercus.miniature(fichier, taille)
        except Exception:
            im = apercus.vignette_texte("?", taille)
        self.file_miniatures.put((gen, cle, im))

    def _recevoir_miniatures(self):
        try:
            for _ in range(40):
                gen, cle, im = self.file_miniatures.get_nowait()
                if gen != self.generation:
                    continue
                self.images[cle] = ImageTk.PhotoImage(im)
                for idx in self.index_image.get(cle, []):
                    self.toile.itemconfigure(f"img{idx}", image=self.images[cle])
                    if idx == self.courant:
                        self._maj_detail()
        except queue.Empty:
            pass
        self.racine.after(60, self._recevoir_miniatures)

    # ------------------------------------------------------------------ grille
    def _dims(self):
        t = self._taille()
        return t + 20, t + 66  # largeur, hauteur d'une case

    def _colonnes(self) -> int:
        l, _ = self._dims()
        return max(1, (self.toile.winfo_width() - 8) // l)

    def _redessiner_si_largeur(self):
        if self.toile.winfo_width() != self._largeur:
            self._largeur = self.toile.winfo_width()
            self.redessiner()

    def redessiner(self):
        self.toile.delete("all")
        if not self.shooting:
            return
        if not self.photos:
            msg = ("Aucune photo pour ce filtre." if self.shooting.photos else
                   "Ce shooting est vide.\n\nClique sur « ⤓ Importer carte SD » "
                   "ou glisse tes RAW dans le dossier 01_RAW.")
            self.toile.create_text(self.toile.winfo_width() // 2, 120, text=msg, fill=GRIS,
                                   font=("Segoe UI", 12), justify="center")
            return
        for i in range(len(self.photos)):
            self._dessiner_case(i)
        l, h = self._dims()
        lignes = (len(self.photos) + self._colonnes() - 1) // self._colonnes()
        self.toile.configure(scrollregion=(0, 0, self._colonnes() * l, lignes * h + 10))

    def _pos(self, i):
        l, h = self._dims()
        c = self._colonnes()
        return 6 + (i % c) * l, 6 + (i // c) * h

    def _dessiner_case(self, i: int):
        t = self.toile
        tag = f"case{i}"
        t.delete(tag)
        p = self.photos[i]
        x, y = self._pos(i)
        l, h = self._dims()
        taille = self._taille()
        sel = i in self.selection
        bord = ACCENT if i == self.courant else (CASE_SEL if sel else CASE)
        t.create_rectangle(x, y, x + l - 8, y + h - 8, fill=CASE_SEL if sel else CASE,
                           outline=bord, width=2, tags=tag)
        cx, cy = x + (l - 8) // 2, y + 6 + taille // 2
        t.create_image(cx, cy, image=self.images.get(_cle_image(p), ""), tags=(tag, f"img{i}"))
        if p.choix == REJET:
            t.create_text(cx, cy, text="✗", fill="#c0392b", font=("Segoe UI", 36, "bold"), tags=tag)
        # nom
        ty = y + taille + 14
        t.create_text(x + 8, ty, text=_raccourcir(p.nom, max(12, taille // 7)), fill=TEXTE, anchor="w",
                      font=("Segoe UI", 9), tags=tag)
        # étapes présentes
        by = ty + 18
        bx = x + 8
        for code in noyau.CODES_ETAPES:
            present = bool(p.fichiers.get(code))
            largeur = 8 + 7 * len(code)
            t.create_rectangle(bx, by - 8, bx + largeur, by + 8,
                               fill=COULEUR_ETAPE[code] if present else PANNEAU, outline="", tags=tag)
            t.create_text(bx + largeur / 2, by, text=code, fill=TEXTE if present else "#4a525e",
                          font=("Segoe UI", 7, "bold"), tags=tag)
            bx += largeur + 3
        # état
        etat = p.etat
        marque = {PICK: "✓ ", REJET: ""}.get(p.choix, "")
        if p.a_retoucher and etat not in ("À retoucher",):
            marque += "✎ "
        t.create_text(x + 8, by + 19, text=marque + etat, fill=COULEUR_ETAT[etat], anchor="w",
                      font=("Segoe UI", 9, "bold"), tags=tag)
        etoiles = "★" * p.note + "☆" * (5 - p.note)
        t.create_text(x + l - 14, by + 19, text=etoiles, fill=ACCENT if p.note else "#4a525e",
                      anchor="e", font=("Segoe UI", 9), tags=tag)

    def _index_a(self, event) -> int | None:
        x, y = self.toile.canvasx(event.x), self.toile.canvasy(event.y)
        l, h = self._dims()
        c = self._colonnes()
        col, lig = int((x - 6) // l), int((y - 6) // h)
        if col < 0 or col >= c or lig < 0:
            return None
        i = lig * c + col
        return i if i < len(self.photos) else None

    def _clic(self, event, ajout=False, etendre=False):
        self.toile.focus_set()
        i = self._index_a(event)
        if i is None:
            if not ajout and not etendre:
                self._selectionner(set(), None)
            return "break"
        if etendre and self.courant is not None:
            a, b = sorted((self.courant, i))
            self._selectionner(self.selection | set(range(a, b + 1)), i)
        elif ajout:
            self._selectionner(self.selection ^ {i}, i)
        else:
            self._selectionner({i}, i)
        return "break"

    def _selectionner(self, nouvelle: set[int], courant: int | None):
        self._enregistrer_commentaire()
        anciens = self.selection | ({self.courant} if self.courant is not None else set())
        self.selection = nouvelle
        self.courant = courant
        for i in anciens | nouvelle | ({courant} if courant is not None else set()):
            if 0 <= i < len(self.photos):
                self._dessiner_case(i)
        self._maj_detail()
        self._voir(courant)

    def _voir(self, i):
        if i is None:
            return
        _, h = self._dims()
        _, y = self._pos(i)
        region = self.toile.cget("scrollregion").split()
        if len(region) != 4:
            return
        total = float(region[3]) or 1
        haut, bas = self.toile.canvasy(0), self.toile.canvasy(self.toile.winfo_height())
        if y < haut:
            self.toile.yview_moveto(y / total)
        elif y + h > bas:
            self.toile.yview_moveto((y + h - self.toile.winfo_height()) / total)

    def _molette(self, event):
        if event.num == 4:
            pas = -3
        elif event.num == 5:
            pas = 3
        else:
            pas = -int(event.delta / 40) if sys.platform == "darwin" else -int(event.delta / 120) * 3
        self.toile.yview_scroll(pas, "units")

    def deplacer(self, d, etendre=False):
        if not self.photos:
            return "break"
        i = 0 if self.courant is None else min(max(self.courant + d, 0), len(self.photos) - 1)
        if etendre:
            self._selectionner(self.selection | {i}, i)
        else:
            self._selectionner({i}, i)
        return "break"

    def tout_selectionner(self):
        self._selectionner(set(range(len(self.photos))), self.courant or 0)
        return "break"

    def _selectionnees(self) -> list[noyau.Photo]:
        return [self.photos[i] for i in sorted(self.selection)]

    # ------------------------------------------------------------------ tri / notes
    def _modifier(self, action):
        photos = self._selectionnees()
        if not photos:
            self._statut("Sélectionne d'abord une ou plusieurs photos.")
            return
        for p in photos:
            action(p)
        self.shooting.enregistrer()
        for i in self.selection:
            self._dessiner_case(i)
        self._maj_detail()
        self._maj_resume()

    def noter(self, n, bascule=False):
        courant = self.photos[self.courant] if self.courant is not None else None
        if bascule and courant and courant.note == n and len(self.selection) == 1:
            n = 0
        self._modifier(lambda p: setattr(p, "note", n))

    def choisir(self, choix):
        self._modifier(lambda p: setattr(p, "choix", choix))
        if choix and len(self.selection) == 1 and self.courant is not None:
            self.deplacer(1)  # tri rapide : on passe à la suivante

    def basculer_retouche(self):
        photos = self._selectionnees()
        valeur = not all(p.a_retoucher for p in photos)
        self._modifier(lambda p: setattr(p, "a_retoucher", valeur))

    def _basculer_retouche_case(self):
        v = self.var_retouche.get()
        self._modifier(lambda p: setattr(p, "a_retoucher", v))

    def _enregistrer_commentaire(self):
        if self.courant is None or not self.shooting or self.courant >= len(self.photos):
            return
        p = self.photos[self.courant]
        texte = self.txt_commentaire.get("1.0", "end").strip()
        if texte != p.commentaire:
            p.commentaire = texte
            self.shooting.enregistrer()

    # ------------------------------------------------------------------ panneau détail
    def _maj_detail(self):
        for w in self.cadre_versions.winfo_children():
            w.destroy()
        self.txt_commentaire.delete("1.0", "end")
        if self.courant is None or self.courant >= len(self.photos):
            self.lbl_apercu.configure(image="", text="")
            self.image_detail = None
            self.lbl_nom.configure(text="Aucune photo sélectionnée" if self.shooting else "")
            self.lbl_etat.configure(text="")
            for b in self.btn_etoiles:
                b.configure(fg="#4a525e")
            return
        p = self.photos[self.courant]
        nb = len(self.selection)
        self.lbl_nom.configure(text=p.nom + (f"   (+{nb - 1} sélectionnées)" if nb > 1 else ""))
        self.lbl_etat.configure(text=p.etat, fg=COULEUR_ETAT[p.etat])
        for k, b in enumerate(self.btn_etoiles, start=1):
            b.configure(fg=ACCENT if k <= p.note else "#4a525e")
        self.var_retouche.set(p.a_retoucher)
        if p.commentaire:
            self.txt_commentaire.insert("1.0", p.commentaire)
        img = self.images.get(_cle_image(p))
        if img:
            self.image_detail = img
            self.lbl_apercu.configure(image=img)
        for code in noyau.CODES_ETAPES:
            fichiers = p.fichiers.get(code, [])
            ligne = ttk.Frame(self.cadre_versions, style="Panneau.TFrame")
            ligne.pack(fill="x", pady=1)
            tk.Label(ligne, text=f" {code} ", bg=COULEUR_ETAPE[code] if fichiers else CASE,
                     fg=TEXTE, font=("Segoe UI", 8, "bold"), width=6).pack(side="left")
            if not fichiers:
                ttk.Label(ligne, text=f"  pas encore ({NOM_ETAPE[code]})",
                          style="PanneauGris.TLabel").pack(side="left")
            for f in fichiers[:3]:
                lien = tk.Label(ligne, text=_raccourcir(f.name, 28 if len(fichiers) == 1 else 14), bg=PANNEAU, fg="#8fb8ff",
                                cursor="hand2", font=("Segoe UI", 9, "underline"))
                lien.pack(side="left", padx=6)
                lien.bind("<Button-1>", lambda e, f=f: self._ouvrir_fichier(f))
                lien.bind("<Button-3>", lambda e, f=f: reglages.ouvrir_dossier(f.parent, f))
            if len(fichiers) > 3:
                ttk.Label(ligne, text=f"+{len(fichiers) - 3}", style="PanneauGris.TLabel").pack(side="left")
        ttk.Label(self.cadre_versions, text="clic : ouvrir · clic droit : voir dans le dossier",
                  style="PanneauGris.TLabel", wraplength=310).pack(anchor="w", pady=(4, 0))

    def _maj_resume(self):
        if not self.shooting:
            return
        r = self.shooting.resume()
        e = r["etats"]
        self.lbl_resume.configure(
            text=f"{r['total']} photos · {e['Rejetée']} rejetées · "
                 f"{e['À retoucher'] + e['En retouche']} en retouche · "
                 f"{r['terminees']}/{r['objectif']} terminées")
        self.barre_prog.configure(value=r["progression"])

    def _maj_boutons(self):
        etat = "normal" if self.shooting else "disabled"
        for b in self.boutons_shooting:
            b.configure(state=etat)

    def _statut(self, texte):
        self.lbl_statut.configure(text=texte)

    # ------------------------------------------------------------------ menus
    def _menu_contextuel(self, event):
        i = self._index_a(event)
        if i is None:
            return
        if i not in self.selection:
            self._selectionner({i}, i)
        m = tk.Menu(self.racine, tearoff=0, bg=CASE, fg=TEXTE, activebackground=CASE_SEL)
        m.add_command(label="Ouvrir dans Photoshop", command=self.ouvrir_photoshop)
        m.add_command(label="Ouvrir dans Lightroom", command=self.ouvrir_lightroom)
        m.add_command(label="Aperçu en grand", command=self.grand_apercu)
        m.add_command(label="Montrer dans le dossier", command=self._montrer)
        m.add_separator()
        m.add_command(label="✓ Garder (P)", command=lambda: self.choisir(PICK))
        m.add_command(label="✗ Rejeter (X)", command=lambda: self.choisir(REJET))
        m.add_command(label="✎ À retoucher (R)", command=self.basculer_retouche)
        notes = tk.Menu(m, tearoff=0, bg=CASE, fg=TEXTE, activebackground=CASE_SEL)
        for n in range(6):
            notes.add_command(label="★" * n or "Sans note", command=lambda n=n: self.noter(n))
        m.add_cascade(label="Note", menu=notes)
        m.tk_popup(event.x_root, event.y_root)

    def _montrer(self):
        if self.courant is not None:
            f = self.photos[self.courant].fichier_pour_photoshop()
            if f:
                reglages.ouvrir_dossier(f.parent, f)

    # ------------------------------------------------------------------ logiciels
    def _ouvrir_fichier(self, f: Path):
        try:
            if f.suffix.lower() in noyau.EXT_PSD | noyau.EXT_TIFF and self.reglages["photoshop"]:
                reglages.ouvrir_avec(self.reglages["photoshop"], [f])
            else:
                reglages.ouvrir_par_defaut(f)
        except Exception as e:
            messagebox.showerror("Ouverture impossible", str(e), parent=self.racine)

    def ouvrir_photoshop(self):
        photos = self._selectionnees()
        if not photos:
            self._statut("Sélectionne les photos à ouvrir dans Photoshop.")
            return
        if not self.reglages["photoshop"]:
            messagebox.showwarning("Photoshop", "Indique où est installé Photoshop dans ⚙ Réglages.",
                                   parent=self.racine)
            self.ouvrir_reglages()
            return
        fichiers = [f for f in (p.fichier_pour_photoshop() for p in photos) if f]
        try:
            reglages.ouvrir_avec(self.reglages["photoshop"], fichiers)
        except Exception as e:
            messagebox.showerror("Photoshop", str(e), parent=self.racine)
            return
        for p in photos:
            if "PS" not in p.fichiers and "FINAL" not in p.fichiers:
                p.a_retoucher = True
        self.shooting.enregistrer()
        for i in self.selection:
            self._dessiner_case(i)
        self._maj_detail()
        self._statut(f"{len(fichiers)} fichier(s) envoyé(s) à Photoshop. Enregistre le PSD dans "
                     f"{noyau.DOSSIER_ETAPE['PS']} et le JPG terminé dans {noyau.DOSSIER_ETAPE['FINAL']}.")

    def ouvrir_lightroom(self):
        photos = self._selectionnees()
        fichiers = [f for p in photos for f in p.fichiers.get("RAW", [])[:1]]
        if not fichiers:
            self._statut("Aucun RAW dans la sélection.")
            return
        try:
            reglages.ouvrir_avec(self.reglages["lightroom"], fichiers)
        except Exception as e:
            messagebox.showerror("Lightroom", str(e), parent=self.racine)

    def ouvrir_dossier_shooting(self):
        if self.shooting:
            reglages.ouvrir_dossier(self.shooting.dossier)

    def grand_apercu(self):
        if self.courant is None:
            return "break"
        p = self.photos[self.courant]
        f = p.fichier_apercu()
        if not f:
            return "break"
        fen = tk.Toplevel(self.racine, bg="#000")
        fen.title(p.nom)
        cote = min(fen.winfo_screenwidth(), fen.winfo_screenheight()) - 120
        img = ImageTk.PhotoImage(apercus.grand_apercu(f, cote))
        lbl = tk.Label(fen, image=img, bg="#000")
        lbl.image = img
        lbl.pack()
        for touche in ("<Escape>", "<space>", "<Button-1>"):
            fen.bind(touche, lambda e: fen.destroy())
        fen.focus_set()
        return "break"

    # ------------------------------------------------------------------ actions shooting
    def nouveau_shooting(self):
        if not self.reglages["bibliotheque"]:
            self.changer_bibliotheque()
            if not self.reglages["bibliotheque"]:
                return
        d = Formulaire(self.racine, "Nouveau shooting", [
            ("voiture", "Voiture (ex. Porsche 911 GT3)", ""),
            ("client", "Client (facultatif)", ""),
            ("date", "Date (AAAA-MM-JJ)", date.today().isoformat()),
            ("notes", "Lieu / notes", ""),
        ])
        if not d.resultat:
            return
        r = d.resultat
        if not r["voiture"].strip():
            messagebox.showerror("Nouveau shooting", "Indique au moins la voiture.", parent=self.racine)
            return
        try:
            jour = date.fromisoformat(r["date"].strip())
        except ValueError:
            messagebox.showerror("Nouveau shooting", "Date invalide (format AAAA-MM-JJ).", parent=self.racine)
            return
        try:
            s = Shooting.creer(self.reglages["bibliotheque"], r["voiture"], r["client"], jour, r["notes"])
        except FileExistsError as e:
            messagebox.showerror("Nouveau shooting", str(e), parent=self.racine)
            return
        self.shooting = None
        self.actualiser_liste(choisir=s.dossier)
        if messagebox.askyesno("Nouveau shooting", "Shooting créé. Importer les photos maintenant ?",
                               parent=self.racine):
            self.importer()

    def importer(self):
        if not self.shooting:
            messagebox.showinfo("Importer", "Choisis d'abord (ou crée) le shooting de destination.",
                                parent=self.racine)
            return
        FenetreImport(self)

    def ranger(self):
        mouvements = self.shooting.a_ranger()
        if not mouvements:
            messagebox.showinfo("Ranger", "Tout est déjà bien rangé 👍", parent=self.racine)
            return
        lignes = [f"{s.relative_to(self.shooting.dossier)}  →  {d.parent.name}" for s, d in mouvements]
        texte = "\n".join(lignes[:25]) + (f"\n… et {len(lignes) - 25} autres" if len(lignes) > 25 else "")
        if messagebox.askyesno("Ranger le vrac", f"Déplacer {len(mouvements)} fichier(s) ?\n\n{texte}",
                               parent=self.racine):
            n = self.shooting.ranger(mouvements)
            self._statut(f"{n} fichier(s) rangé(s).")
            self.recharger()

    def ecrire_xmp(self):
        n = noyau.exporter_notes_xmp(self.shooting.photos)
        messagebox.showinfo("Lightroom", f"Notes écrites pour {n} RAW.\n\nDans Lightroom : sélectionne les "
                            "photos → Métadonnées → « Lire les métadonnées à partir des fichiers ».\n"
                            "Les photos rejetées ont la note « Rejetée » (-1).", parent=self.racine)

    def lire_xmp(self):
        n = noyau.importer_notes_xmp(self.shooting.photos)
        self.shooting.enregistrer()
        self.recharger()
        messagebox.showinfo("Lightroom", f"Notes lues pour {n} photo(s).\n\nAstuce : dans Lightroom, fais "
                            "Ctrl+S (Enregistrer les métadonnées dans le fichier) avant.", parent=self.racine)

    def exporter_web(self):
        FenetreExport(self)

    def ouvrir_reglages(self):
        FenetreReglages(self)

    def quitter(self):
        self._enregistrer_commentaire()
        self.executeur.shutdown(wait=False, cancel_futures=True)
        self.racine.destroy()


def _cle_image(p: noyau.Photo) -> str:
    f = p.fichier_apercu()
    return str(f) if f else ""


def _raccourcir(texte: str, n: int) -> str:
    return texte if len(texte) <= n else texte[: n - 1] + "…"


# --------------------------------------------------------------------------- dialogues

class Dialogue(tk.Toplevel):
    def __init__(self, parent, titre):
        super().__init__(parent, bg=FOND)
        self.title(titre)
        self.transient(parent)
        self.resizable(False, False)
        self.corps = ttk.Frame(self, padding=16)
        self.corps.pack(fill="both", expand=True)

    def centrer_et_attendre(self, attendre=True):
        self.update_idletasks()
        p = self.master
        x = p.winfo_rootx() + (p.winfo_width() - self.winfo_width()) // 2
        y = p.winfo_rooty() + (p.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass
        if attendre:
            self.wait_window()


class Formulaire(Dialogue):
    def __init__(self, parent, titre, champs):
        super().__init__(parent, titre)
        self.resultat = None
        self.vars = {}
        for ligne, (cle, libelle, defaut) in enumerate(champs):
            ttk.Label(self.corps, text=libelle).grid(row=ligne, column=0, sticky="w", pady=4, padx=(0, 10))
            v = tk.StringVar(value=defaut)
            e = ttk.Entry(self.corps, textvariable=v, width=36)
            e.grid(row=ligne, column=1, pady=4)
            if ligne == 0:
                e.focus_set()
            self.vars[cle] = v
        b = ttk.Frame(self.corps)
        b.grid(row=len(champs), column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(b, text="Annuler", command=self.destroy).pack(side="right")
        ttk.Button(b, text="Créer", style="Accent.TButton", command=self._valider).pack(side="right", padx=6)
        self.bind("<Return>", lambda e: self._valider())
        self.bind("<Escape>", lambda e: self.destroy())
        self.centrer_et_attendre()

    def _valider(self):
        self.resultat = {k: v.get() for k, v in self.vars.items()}
        self.destroy()


def cartes_memoire() -> list[str]:
    """Cartes SD / disques contenant un dossier DCIM."""
    trouves = []
    if sys.platform.startswith("win"):
        for lettre in string.ascii_uppercase[3:]:
            if Path(f"{lettre}:/DCIM").is_dir():
                trouves.append(f"{lettre}:/DCIM")
    else:
        for base in ("/Volumes", "/media", f"/media/{os.environ.get('USER', '')}", "/run/media"):
            b = Path(base)
            if b.is_dir():
                for d in b.iterdir():
                    try:
                        if (d / "DCIM").is_dir():
                            trouves.append(str(d / "DCIM"))
                    except OSError:
                        continue
    return trouves


class FenetreImport(Dialogue):
    def __init__(self, app: Application):
        super().__init__(app.racine, "Importer des photos")
        self.app = app
        self.s = app.shooting
        self.plan = []
        self.annule = False
        cartes = cartes_memoire()
        c = self.corps
        ttk.Label(c, text=f"Vers : {self.s.nom} / {noyau.DOSSIER_ETAPE['RAW']}",
                  style="Gris.TLabel").grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(c, text="Depuis").grid(row=1, column=0, sticky="w", pady=8)
        self.var_source = tk.StringVar(value=cartes[0] if cartes else "")
        ttk.Combobox(c, textvariable=self.var_source, values=cartes, width=44).grid(row=1, column=1, pady=8)
        ttk.Button(c, text="Parcourir…", command=self._parcourir).grid(row=1, column=2, padx=(6, 0))

        self.var_renommer = tk.BooleanVar(value=bool(app.reglages.get("renommer_import", True)))
        try:
            jour = date.fromisoformat(self.s.infos.get("date", ""))
        except ValueError:
            jour = date.today()
        prefixe = noyau.nom_dossier_shooting(jour, self.s.infos.get("voiture", "") or "photo")
        self.var_prefixe = tk.StringVar(value=prefixe)
        ttk.Checkbutton(c, text="Renommer en", variable=self.var_renommer, style="Fond.TCheckbutton",
                        command=self._analyser).grid(row=2, column=0, sticky="w")
        e = ttk.Entry(c, textvariable=self.var_prefixe, width=46)
        e.grid(row=2, column=1, sticky="w")
        e.bind("<FocusOut>", lambda ev: self._analyser())
        ttk.Label(c, text="_0001.CR3 …", style="Gris.TLabel").grid(row=2, column=2, sticky="w", padx=4)

        self.lbl_info = ttk.Label(c, text="", style="Gris.TLabel", wraplength=520)
        self.lbl_info.grid(row=3, column=0, columnspan=3, sticky="w", pady=(12, 4))
        self.prog = ttk.Progressbar(c, length=520, maximum=100)
        self.prog.grid(row=4, column=0, columnspan=3, pady=4)
        b = ttk.Frame(c)
        b.grid(row=5, column=0, columnspan=3, sticky="e", pady=(10, 0))
        self.btn_annuler = ttk.Button(b, text="Fermer", command=self._fermer)
        self.btn_annuler.pack(side="right")
        self.btn_go = ttk.Button(b, text="Importer", style="Accent.TButton", command=self._lancer)
        self.btn_go.pack(side="right", padx=6)
        self.var_source.trace_add("write", lambda *a: self.after(300, self._analyser))
        self.protocol("WM_DELETE_WINDOW", self._fermer)
        self._analyser()
        self.centrer_et_attendre(attendre=False)

    def _parcourir(self):
        d = filedialog.askdirectory(parent=self, title="Carte SD ou dossier de photos")
        if d:
            self.var_source.set(d)

    def _analyser(self):
        src = self.var_source.get().strip()
        if not src or not Path(src).is_dir():
            self.plan = []
            self.lbl_info.configure(text="Branche ta carte SD ou choisis un dossier.")
            self.btn_go.configure(state="disabled")
            return
        prefixe = self.var_prefixe.get().strip() if self.var_renommer.get() else ""
        try:
            self.plan = noyau.preparer_import(src, self.s.chemin_etape("RAW"), prefixe)
        except OSError as e:
            self.lbl_info.configure(text=f"Lecture impossible : {e}")
            return
        taille = sum(s.stat().st_size for s, _ in self.plan) / 1e9
        if self.plan:
            exemple = f"{self.plan[0][0].name} → {self.plan[0][1].name}"
            self.lbl_info.configure(text=f"{len(self.plan)} fichier(s) nouveaux à copier ({taille:.1f} Go). "
                                         f"Les photos déjà importées sont ignorées.\nEx. : {exemple}")
        else:
            self.lbl_info.configure(text="Rien de nouveau à importer depuis ce dossier.")
        self.btn_go.configure(state="normal" if self.plan else "disabled")

    def _lancer(self):
        self.app.reglages["renommer_import"] = self.var_renommer.get()
        reglages.enregistrer(self.app.reglages)
        self.btn_go.configure(state="disabled")
        self.btn_annuler.configure(text="Arrêter")
        plan = list(self.plan)

        def progression(i, n, nom):
            self.after(0, lambda: (self.prog.configure(value=100 * i / n),
                                   self.lbl_info.configure(text=f"{i}/{n} · {nom}")))

        def travail():
            try:
                n = noyau.importer(plan, progression, lambda: self.annule)
                self.after(0, lambda: self._fini(f"{n} fichier(s) importé(s) et vérifié(s). "
                                                 "Tu peux formater la carte."))
            except Exception as e:
                self.after(0, lambda e=e: self._fini(f"Erreur : {e}"))

        threading.Thread(target=travail, daemon=True).start()

    def _fini(self, texte):
        if not self.winfo_exists():
            return
        self.lbl_info.configure(text=texte)
        self.btn_annuler.configure(text="Fermer")
        self.app.recharger()
        self.app.actualiser_liste()

    def _fermer(self):
        if self.btn_annuler.cget("text") == "Arrêter":
            self.annule = True
            return
        self.destroy()


class FenetreExport(Dialogue):
    def __init__(self, app: Application):
        super().__init__(app.racine, "Exporter pour le web / Instagram")
        self.app = app
        c = self.corps
        sel = [p for p in app._selectionnees()]
        self.sources_sel = noyau.sources_pour_export(sel)
        self.sources_tout = noyau.sources_pour_export(app.shooting.photos)
        self.var_quoi = tk.StringVar(value="sel" if self.sources_sel else "tout")
        ttk.Label(c, text="Photos (on part des fichiers de 04_FINAL)").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Radiobutton(c, text=f"Sélection ({len(self.sources_sel)} terminée(s))", value="sel",
                        variable=self.var_quoi).grid(row=1, column=0, columnspan=2, sticky="w")
        ttk.Radiobutton(c, text=f"Toutes les terminées ({len(self.sources_tout)})", value="tout",
                        variable=self.var_quoi).grid(row=2, column=0, columnspan=2, sticky="w")
        ttk.Label(c, text="Format").grid(row=3, column=0, sticky="w", pady=(12, 4))
        self.var_format = tk.StringVar(value=next(iter(noyau.FORMATS_WEB)))
        ttk.Combobox(c, textvariable=self.var_format, values=list(noyau.FORMATS_WEB), state="readonly",
                     width=30).grid(row=3, column=1, sticky="w", pady=(12, 4))
        ttk.Label(c, text="Qualité JPG").grid(row=4, column=0, sticky="w", pady=4)
        self.var_qualite = tk.IntVar(value=int(app.reglages.get("qualite_web", 90)))
        ttk.Spinbox(c, from_=60, to=100, textvariable=self.var_qualite, width=6).grid(row=4, column=1, sticky="w")
        ttk.Label(c, text="Signature").grid(row=5, column=0, sticky="w", pady=4)
        self.var_filigrane = tk.StringVar(value=app.reglages.get("filigrane", ""))
        ttk.Entry(c, textvariable=self.var_filigrane, width=32).grid(row=5, column=1, sticky="w")
        ttk.Label(c, text="Bandes (Insta)").grid(row=6, column=0, sticky="w", pady=4)
        self.var_fond = tk.StringVar(value="Noir")
        ttk.Combobox(c, textvariable=self.var_fond, values=["Noir", "Blanc"], state="readonly",
                     width=8).grid(row=6, column=1, sticky="w")
        self.prog = ttk.Progressbar(c, length=420, maximum=100)
        self.prog.grid(row=7, column=0, columnspan=2, pady=(14, 4))
        self.lbl = ttk.Label(c, text="Les fichiers vont dans 05_WEB.", style="Gris.TLabel")
        self.lbl.grid(row=8, column=0, columnspan=2, sticky="w")
        b = ttk.Frame(c)
        b.grid(row=9, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(b, text="Fermer", command=self.destroy).pack(side="right")
        self.btn = ttk.Button(b, text="Exporter", style="Accent.TButton", command=self._lancer)
        self.btn.pack(side="right", padx=6)
        self.centrer_et_attendre(attendre=False)

    def _lancer(self):
        sources = self.sources_sel if self.var_quoi.get() == "sel" else self.sources_tout
        if not sources:
            self.lbl.configure(text="Aucune photo terminée : mets d'abord les JPG finis dans 04_FINAL.")
            return
        self.app.reglages["filigrane"] = self.var_filigrane.get()
        self.app.reglages["qualite_web"] = self.var_qualite.get()
        reglages.enregistrer(self.app.reglages)
        self.btn.configure(state="disabled")
        args = dict(format_web=self.var_format.get(), qualite=int(self.var_qualite.get()),
                    filigrane=self.var_filigrane.get().strip(),
                    fond="#000000" if self.var_fond.get() == "Noir" else "#ffffff")
        dossier = self.app.shooting.chemin_etape("WEB")

        def progression(i, n, nom):
            self.after(0, lambda: (self.prog.configure(value=100 * i / n),
                                   self.lbl.configure(text=f"{i}/{n} · {nom}")))

        def travail():
            try:
                crees = noyau.exporter_web(sources, dossier, progression=progression, **args)
                self.after(0, lambda: self._fini(f"{len(crees)} image(s) créée(s) dans 05_WEB."))
            except Exception as e:
                self.after(0, lambda e=e: self._fini(f"Erreur : {e}"))

        threading.Thread(target=travail, daemon=True).start()

    def _fini(self, texte):
        if self.winfo_exists():
            self.lbl.configure(text=texte)
            self.btn.configure(state="normal")
        self.app.recharger()


class FenetreReglages(Dialogue):
    def __init__(self, app: Application):
        super().__init__(app.racine, "Réglages")
        self.app = app
        r = app.reglages
        c = self.corps
        self.vars = {}
        lignes = [("bibliotheque", "Dossier des shootings", "dossier"),
                  ("photoshop", "Photoshop", "fichier"),
                  ("lightroom", "Lightroom Classic", "fichier"),
                  ("filigrane", "Signature des exports web", None)]
        for i, (cle, libelle, parcourir) in enumerate(lignes):
            ttk.Label(c, text=libelle).grid(row=i, column=0, sticky="w", pady=4, padx=(0, 10))
            v = tk.StringVar(value=str(r.get(cle, "")))
            ttk.Entry(c, textvariable=v, width=56).grid(row=i, column=1, pady=4)
            if parcourir:
                ttk.Button(c, text="…", width=3,
                           command=lambda v=v, t=parcourir: self._parcourir(v, t)).grid(row=i, column=2, padx=4)
            self.vars[cle] = v
        ttk.Label(c, text="Taille des miniatures").grid(row=len(lignes), column=0, sticky="w", pady=4)
        self.var_taille = tk.IntVar(value=int(r.get("taille_miniatures", 200)))
        ttk.Spinbox(c, from_=120, to=360, increment=20, textvariable=self.var_taille,
                    width=6).grid(row=len(lignes), column=1, sticky="w")
        ttk.Label(c, text="Photoshop et Lightroom sont cherchés automatiquement ; indique-les ici "
                          "s'ils ne sont pas trouvés.", style="Gris.TLabel",
                  wraplength=520).grid(row=len(lignes) + 1, column=0, columnspan=3, sticky="w", pady=(8, 0))
        b = ttk.Frame(c)
        b.grid(row=len(lignes) + 2, column=0, columnspan=3, sticky="e", pady=(12, 0))
        ttk.Button(b, text="Annuler", command=self.destroy).pack(side="right")
        ttk.Button(b, text="Enregistrer", style="Accent.TButton", command=self._valider).pack(side="right", padx=6)
        self.centrer_et_attendre()

    def _parcourir(self, var, type_):
        if type_ == "dossier":
            v = filedialog.askdirectory(parent=self)
        elif sys.platform == "darwin":
            v = filedialog.askopenfilename(parent=self, initialdir="/Applications")
        else:
            v = filedialog.askopenfilename(parent=self, filetypes=[("Programme", "*.exe"), ("Tous", "*.*")])
        if v:
            var.set(v)

    def _valider(self):
        ancienne_biblio = self.app.reglages["bibliotheque"]
        ancienne_taille = self.app.reglages.get("taille_miniatures")
        for cle, v in self.vars.items():
            self.app.reglages[cle] = v.get().strip()
        self.app.reglages["taille_miniatures"] = int(self.var_taille.get())
        reglages.enregistrer(self.app.reglages)
        self.destroy()
        if self.app.reglages["taille_miniatures"] != ancienne_taille:
            self.app.images.clear()
            self.app.recharger()
        if self.app.reglages["bibliotheque"] != ancienne_biblio:
            self.app.shooting = None
            self.app.photos = []
            self.app.redessiner()
            self.app.actualiser_liste()


def lancer():
    if sys.platform.startswith("win"):
        try:  # affichage net sur les écrans haute résolution
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    racine = tk.Tk()
    Application(racine)
    racine.mainloop()
