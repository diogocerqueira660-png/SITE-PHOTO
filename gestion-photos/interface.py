"""Fenêtre principale de l'appli (CustomTkinter, design sombre moderne)."""

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
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageEnhance, ImageOps, ImageTk

import apercus
import noyau
import reglages
from noyau import A_TRIER, AUCUN, PICK, REJET, REJETEE, TERMINEE, Shooting

# --------------------------------------------------------------------------- style

FOND = "#0f1115"
BARRE = "#14171c"
CARTE = "#1b1f26"
CARTE_SURVOL = "#212631"
CHAMP = "#252b35"
BORD = "#2b313c"
TEXTE = "#eef1f5"
DOUX = "#8a93a3"
PALE = "#5b6472"
ACCENT = "#ff7a1a"
ACCENT_SURVOL = "#ff9447"
VERT = "#22c55e"
ROUGE = "#ef4444"
COULEUR_LOGICIEL = {"lightroom": "#38bdf8", "photoshop": "#818cf8", "aucun": "#c084fc"}
COULEUR_VERSION = {"RAW": "#64748b", "TIF": "#818cf8", "JPG": VERT, "WEB": "#f472b6"}

if sys.platform.startswith("win"):
    POLICE = "Segoe UI"
elif sys.platform == "darwin":
    POLICE = "Helvetica Neue"
else:
    POLICE = "DejaVu Sans"


def police(taille=13, gras=False):
    return ctk.CTkFont(family=POLICE, size=taille, weight="bold" if gras else "normal")


def melange(c1: str, c2: str, t: float) -> str:
    """Mélange deux couleurs (t = part de c2)."""
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def bouton(parent, texte, commande=None, style="secondaire", **kw):
    styles = {
        "principal": dict(fg_color=ACCENT, hover_color=ACCENT_SURVOL, text_color="#16100a",
                          text_color_disabled="#8a4a18"),
        "secondaire": dict(fg_color=CHAMP, hover_color=BORD, text_color=TEXTE),
        "discret": dict(fg_color="transparent", hover_color=CHAMP, text_color=DOUX),
        "danger": dict(fg_color="transparent", hover_color=melange(CARTE, ROUGE, .25), text_color=ROUGE),
    }
    options = dict(corner_radius=10, height=36, font=police(13, style == "principal"))
    options.update(styles[style])
    options.update(kw)
    return ctk.CTkButton(parent, text=texte, command=commande, **options)


def menu_sombre(parent):
    return tk.Menu(parent, tearoff=0, bg=CARTE, fg=TEXTE, activebackground=CHAMP,
                   activeforeground=TEXTE, bd=0, relief="flat", font=(POLICE, 11))


# --------------------------------------------------------------------------- application

class Application(ctk.CTk):
    def __init__(self):
        ctk.set_appearance_mode("dark")
        super().__init__(fg_color=FOND)
        self.reglages = reglages.charger()
        self.flux = noyau.flux_depuis(self.reglages.get("flux"))
        self.shooting: Shooting | None = None
        self.photos: list[noyau.Photo] = []  # photos affichées (après filtre / tri)
        self.selection: set[int] = set()
        self.courant: int | None = None
        self.survol: int | None = None
        self.filtre = "Toutes"
        self.images: dict[str, tuple] = {}   # chemin aperçu -> (PhotoImage, PhotoImage sombre)
        self.index_image: dict[str, list[int]] = {}
        self.generation = 0
        self.file: queue.Queue = queue.Queue()
        self.executeur = ThreadPoolExecutor(max_workers=max(2, (os.cpu_count() or 4) // 2))
        self.signature = None
        self.cartes: dict[str, CarteShooting] = {}
        self._toast_id = None

        self.title("Gestion Photos Auto")
        self.geometry("1480x900")
        self.minsize(1100, 680)
        self._construire()
        self._raccourcis()

        self.after(60, self._recevoir)
        self.after(3000, self._surveiller)
        self.protocol("WM_DELETE_WINDOW", self.quitter)
        self.actualiser_liste()
        self._afficher_accueil_si_besoin()

    @property
    def echelle(self) -> float:
        try:
            return ctk.ScalingTracker.get_widget_scaling(self)
        except Exception:
            return 1.0

    # ------------------------------------------------------------------ construction
    def _construire(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # -- barre latérale
        cote = ctk.CTkFrame(self, fg_color=BARRE, corner_radius=0, width=290)
        cote.grid(row=0, column=0, sticky="nsw")
        cote.grid_propagate(False)
        cote.grid_rowconfigure(4, weight=1)
        cote.grid_columnconfigure(0, weight=1)
        logo = ctk.CTkFrame(cote, fg_color="transparent")
        logo.grid(row=0, column=0, sticky="ew", padx=20, pady=(22, 18))
        ctk.CTkLabel(logo, text="◆", font=police(22, True), text_color=ACCENT).pack(side="left")
        titre = ctk.CTkFrame(logo, fg_color="transparent")
        titre.pack(side="left", padx=10)
        ctk.CTkLabel(titre, text="Gestion Photos", font=police(17, True), text_color=TEXTE,
                     height=20).pack(anchor="w")
        ctk.CTkLabel(titre, text="Auto · RAW → JPG", font=police(11), text_color=DOUX,
                     height=14).pack(anchor="w")
        bouton(cote, "＋  Nouveau shooting", self.nouveau_shooting, "principal",
               height=42).grid(row=1, column=0, sticky="ew", padx=16)
        bouton(cote, "⤓  Importer une carte SD", self.importer,
               height=38).grid(row=2, column=0, sticky="ew", padx=16, pady=(8, 0))
        ctk.CTkLabel(cote, text="MES SHOOTINGS", font=police(11, True), text_color=PALE,
                     anchor="w").grid(row=3, column=0, sticky="ew", padx=22, pady=(26, 4))
        self.liste = ctk.CTkScrollableFrame(cote, fg_color="transparent", corner_radius=0,
                                            scrollbar_button_color=CHAMP)
        self.liste.grid(row=4, column=0, sticky="nsew", padx=6)
        bouton(cote, "⚙   Paramètres", self.ouvrir_parametres, "discret", anchor="w",
               height=40).grid(row=5, column=0, sticky="ew", padx=12, pady=12)

        # -- zone principale
        self.principal = ctk.CTkFrame(self, fg_color=FOND, corner_radius=0)
        self.principal.grid(row=0, column=1, sticky="nsew")
        self.principal.grid_columnconfigure(0, weight=1)
        self.principal.grid_rowconfigure(3, weight=1)

        entete = ctk.CTkFrame(self.principal, fg_color="transparent")
        entete.grid(row=0, column=0, sticky="ew", padx=28, pady=(22, 6))
        entete.grid_columnconfigure(0, weight=1)
        self.lbl_titre = ctk.CTkLabel(entete, text="", font=police(26, True), text_color=TEXTE, anchor="w")
        self.lbl_titre.grid(row=0, column=0, sticky="w")
        self.lbl_sous_titre = ctk.CTkLabel(entete, text="", font=police(13), text_color=DOUX, anchor="w")
        self.lbl_sous_titre.grid(row=1, column=0, sticky="w")
        actions = ctk.CTkFrame(entete, fg_color="transparent")
        actions.grid(row=0, column=1, rowspan=2, sticky="e")
        self.boutons_shooting = [
            bouton(actions, "⤓  Importer", self.importer, width=110),
            bouton(actions, "↗  Export web / Insta", self.exporter_web, width=160),
            bouton(actions, "•••", self._menu_plus, width=46),
        ]
        for b in self.boutons_shooting:
            b.pack(side="left", padx=(8, 0))
        prog = ctk.CTkFrame(entete, fg_color="transparent")
        prog.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        prog.grid_columnconfigure(0, weight=1)
        self.barre_prog = ctk.CTkProgressBar(prog, height=6, corner_radius=3, fg_color=CHAMP,
                                             progress_color=VERT)
        self.barre_prog.grid(row=0, column=0, sticky="ew")
        self.barre_prog.set(0)
        self.lbl_prog = ctk.CTkLabel(prog, text="", font=police(12, True), text_color=DOUX, width=150, anchor="e")
        self.lbl_prog.grid(row=0, column=1, padx=(12, 0))

        # -- le flux : chaque étape est un filtre cliquable
        self.barre_flux = ctk.CTkFrame(self.principal, fg_color="transparent")
        self.barre_flux.grid(row=1, column=0, sticky="ew", padx=24, pady=(14, 4))
        self.barre_flux.grid_columnconfigure(0, weight=1)
        self._largeur_flux = 0
        self.barre_flux.bind("<Configure>", self._flux_redimensionne)

        outils = ctk.CTkFrame(self.principal, fg_color="transparent")
        outils.grid(row=2, column=0, sticky="ew", padx=28, pady=(4, 8))
        outils.grid_columnconfigure(0, weight=1)
        self.lbl_aide = ctk.CTkLabel(outils, text="", font=police(12), text_color=DOUX, anchor="w",
                                     justify="left", wraplength=430)
        self.lbl_aide.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(outils, text="Trier par", font=police(12), text_color=PALE).grid(row=0, column=1, padx=(10, 6))
        self.var_tri = ctk.StringVar(value="Nom")
        ctk.CTkSegmentedButton(outils, values=["Nom", "Note", "Étape"], variable=self.var_tri,
                               command=lambda v: self.appliquer_filtre(), font=police(12),
                               fg_color=CHAMP, selected_color=BORD, selected_hover_color=BORD,
                               unselected_color=CHAMP, unselected_hover_color=CARTE_SURVOL,
                               height=30).grid(row=0, column=2)
        ctk.CTkLabel(outils, text="Taille", font=police(12), text_color=PALE).grid(row=0, column=3, padx=(18, 6))
        self.curseur = ctk.CTkSlider(outils, from_=140, to=320, number_of_steps=9, width=110,
                                     button_color=DOUX, button_hover_color=TEXTE, progress_color=PALE,
                                     fg_color=CHAMP, command=self._changer_taille)
        self.curseur.set(int(self.reglages.get("taille_miniatures", 200)))
        self.curseur.grid(row=0, column=4)

        grille = ctk.CTkFrame(self.principal, fg_color="transparent")
        grille.grid(row=3, column=0, sticky="nsew", padx=(20, 8))
        grille.grid_columnconfigure(0, weight=1)
        grille.grid_rowconfigure(0, weight=1)
        self.toile = tk.Canvas(grille, bg=FOND, highlightthickness=0, bd=0, takefocus=1)
        self.toile.grid(row=0, column=0, sticky="nsew")
        defil = ctk.CTkScrollbar(grille, command=self.toile.yview, button_color=CHAMP,
                                 button_hover_color=BORD)
        defil.grid(row=0, column=1, sticky="ns")
        self.toile.configure(yscrollcommand=defil.set)
        self.toile.bind("<Configure>", lambda e: self._redessiner_si_largeur())
        self.toile.bind("<Button-1>", self._clic)
        self.toile.bind("<Control-Button-1>", lambda e: self._clic(e, ajout=True))
        if sys.platform == "darwin":
            self.toile.bind("<Command-Button-1>", lambda e: self._clic(e, ajout=True))
        self.toile.bind("<Shift-Button-1>", lambda e: self._clic(e, etendre=True))
        self.toile.bind("<Double-Button-1>", lambda e: self.envoyer())
        self.toile.bind("<Button-3>", self._menu_contextuel)
        self.toile.bind("<Button-2>", self._menu_contextuel)
        self.toile.bind("<Motion>", self._mouvement)
        self.toile.bind("<Leave>", lambda e: self._survoler(None))
        for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.toile.bind(ev, self._molette)
        self._largeur = 0

        # -- barre d'actions sur la sélection (apparaît quand on coche des photos)
        self.barre_sel = ctk.CTkFrame(self.principal, fg_color=CARTE, corner_radius=16,
                                      border_width=1, border_color=BORD)
        self.lbl_sel = ctk.CTkLabel(self.barre_sel, text="", font=police(14, True), text_color=TEXTE)
        self.lbl_sel.pack(side="left", padx=(18, 14), pady=12)
        self.btn_envoyer = bouton(self.barre_sel, "", self.envoyer, "principal", height=40)
        self.btn_envoyer.pack(side="left")
        self.btn_faite = bouton(self.barre_sel, "✓  Étape faite", self.marquer_faite, height=40)
        self.btn_faite.pack(side="left", padx=(8, 0))
        ctk.CTkFrame(self.barre_sel, width=1, height=26, fg_color=BORD).pack(side="left", padx=12)
        bouton(self.barre_sel, "Garder", lambda: self.choisir(PICK), "discret", width=70,
               height=40).pack(side="left")
        bouton(self.barre_sel, "Rejeter", lambda: self.choisir(REJET), "danger", width=70,
               height=40).pack(side="left")
        bouton(self.barre_sel, "Tout", self.tout_selectionner, "discret", width=56,
               height=40).pack(side="left", padx=(6, 0))
        bouton(self.barre_sel, "✕", self.deselectionner, "discret", width=40,
               height=40).pack(side="left", padx=(0, 10))

        # -- panneau de détail
        self.detail = PanneauDetail(self)
        self.detail.grid(row=0, column=2, sticky="nse")

        # -- notification
        self.toast = ctk.CTkLabel(self.principal, text="", font=police(13), text_color=TEXTE,
                                  fg_color=CHAMP, corner_radius=12, wraplength=620, justify="left")
        self._maj_boutons()
        self._construire_flux({})

    def _raccourcis(self):
        t = self.toile
        for n in range(6):
            t.bind(str(n), lambda e, n=n: self.noter(n))
            t.bind(f"<KP_{n}>", lambda e, n=n: self.noter(n))
        for touche, action in (("p", lambda: self.choisir(PICK)), ("x", lambda: self.choisir(REJET)),
                               ("u", lambda: self.choisir(AUCUN)), ("d", self.marquer_faite)):
            t.bind(touche, lambda e, a=action: a())
            t.bind(touche.upper(), lambda e, a=action: a())
        t.bind("<Return>", lambda e: self.envoyer())
        t.bind("<space>", lambda e: self.grand_apercu())
        t.bind("<Escape>", lambda e: self.deselectionner())
        t.bind("<Control-a>", lambda e: self.tout_selectionner())
        t.bind("<Left>", lambda e: self.deplacer(-1))
        t.bind("<Right>", lambda e: self.deplacer(1))
        t.bind("<Shift-Left>", lambda e: self.deplacer(-1, etendre=True))
        t.bind("<Shift-Right>", lambda e: self.deplacer(1, etendre=True))
        t.bind("<Up>", lambda e: self.deplacer(-self._colonnes()))
        t.bind("<Down>", lambda e: self.deplacer(self._colonnes()))
        self.bind("<F5>", lambda e: self.recharger())

    # ------------------------------------------------------------------ bibliothèque / shootings
    def _afficher_accueil_si_besoin(self):
        if not self.reglages["bibliotheque"] or not Path(self.reglages["bibliotheque"]).is_dir():
            self.lbl_titre.configure(text="Bienvenue 👋")
            self.lbl_sous_titre.configure(text="Commence par choisir le dossier où ranger tous tes shootings.")
            self._message_toile("Choisis un dossier (par ex. « Photos Voitures » sur ton disque).\n"
                                "Chaque shooting y aura son propre dossier bien rangé.",
                                "Choisir le dossier", self.changer_bibliotheque)
        elif not self.cartes:
            self.lbl_titre.configure(text="Aucun shooting")
            self.lbl_sous_titre.configure(text=self.reglages["bibliotheque"])
            self._message_toile("Crée ton premier shooting : marque, modèle, client…",
                                "＋  Nouveau shooting", self.nouveau_shooting)
        else:
            self.lbl_titre.configure(text="Choisis un shooting")
            self.lbl_sous_titre.configure(text="à gauche, dans « Mes shootings »")

    def changer_bibliotheque(self):
        d = filedialog.askdirectory(title="Dossier de tes shootings", parent=self,
                                    initialdir=self.reglages["bibliotheque"] or str(Path.home()))
        if d:
            self.reglages["bibliotheque"] = d
            reglages.enregistrer(self.reglages)
            self.shooting = None
            self.photos = []
            self.actualiser_liste()
            self.redessiner()
            self._afficher_accueil_si_besoin()

    def actualiser_liste(self):
        for c in self.cartes.values():
            c.destroy()
        self.cartes = {}
        for s in noyau.lister_shootings(self.reglages["bibliotheque"]):
            carte = CarteShooting(self.liste, self, s)
            carte.pack(fill="x", pady=4, padx=4)
            self.cartes[str(s.dossier)] = carte
        self._maj_cartes()

    def _maj_cartes(self):
        actif = str(self.shooting.dossier) if self.shooting else None
        for cle, carte in self.cartes.items():
            carte.selectionner(cle == actif)

    def ouvrir_shooting(self, dossier: Path):
        if self.shooting and self.shooting.dossier == dossier:
            return
        self.detail.enregistrer_commentaire()
        self.shooting = Shooting(dossier)
        self.images.clear()
        self.selection.clear()
        self.courant = None
        self.filtre = "Toutes"
        self._maj_cartes()
        self.recharger(garder_selection=False)
        self.toile.focus_set()

    # ------------------------------------------------------------------ chargement
    def recharger(self, garder_selection: bool = True):
        if not self.shooting:
            return
        cles = {self.photos[i].cle for i in self.selection} if garder_selection else set()
        cle_courante = self.photos[self.courant].cle if garder_selection and self.courant is not None else None
        self.shooting = Shooting(self.shooting.dossier)
        self.shooting.analyser()
        self.signature = self._signature()
        s = self.shooting
        self.lbl_titre.configure(text=s.infos.get("voiture") or s.nom)
        details = [s.infos.get("client"), _date_lisible(s.infos.get("date", "")), s.infos.get("notes")]
        self.lbl_sous_titre.configure(text="  ·  ".join(x for x in details if x))
        self.appliquer_filtre(cles, cle_courante)
        self._maj_boutons()

    def appliquer_filtre(self, cles: set[str] | None = None, cle_courante: str | None = None):
        if not self.shooting:
            return
        if cles is None:
            cles = {self.photos[i].cle for i in self.selection}
            cle_courante = self.photos[self.courant].cle if self.courant is not None else None
        photos = self.shooting.photos
        if self.filtre != "Toutes":
            photos = [p for p in photos if p.colonne(self.flux) == self.filtre]
        tri = self.var_tri.get()
        if tri == "Note":
            photos = sorted(photos, key=lambda p: (-p.note, p.cle))
        elif tri == "Étape":
            ordre = [A_TRIER] + [e.id for e in self.flux] + [TERMINEE, REJETEE]
            photos = sorted(photos, key=lambda p: (ordre.index(p.colonne(self.flux)), p.cle))
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
        self._maj_resume()
        self._maj_selection()

    def _signature(self):
        """Empreinte rapide du dossier pour voir si Lightroom/Photoshop y ont écrit."""
        if not self.shooting:
            return None
        sig = []
        dossiers = {self.shooting.dossier} | {self.shooting.chemin_etape(c) for c in noyau.CODES_DOSSIERS}
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
                self.detail.enregistrer_commentaire()
                self.recharger()
                self._maj_carte_active()
        finally:
            self.after(2500, self._surveiller)

    def _maj_carte_active(self):
        if self.shooting and str(self.shooting.dossier) in self.cartes:
            self.cartes[str(self.shooting.dossier)].maj(self.shooting)

    # ------------------------------------------------------------------ flux (filtres par étape)
    def _construire_flux(self, colonnes: dict):
        for w in self.barre_flux.winfo_children():
            w.destroy()
        if not self.shooting:
            return
        pastilles = [("Toutes", "Toutes", DOUX, len(self.shooting.photos)),
                     (A_TRIER, "À trier", "#94a3b8", colonnes.get(A_TRIER, 0))]
        pastilles += [(e.id, e.nom, COULEUR_LOGICIEL[e.logiciel], colonnes.get(e.id, 0)) for e in self.flux]
        pastilles += [(TERMINEE, "Terminées", VERT, colonnes.get(TERMINEE, 0)),
                      (REJETEE, "Rejetées", ROUGE, colonnes.get(REJETEE, 0))]
        self._pastilles = []
        for k, (cle, nom, couleur, n) in enumerate(pastilles):
            groupe = ctk.CTkFrame(self.barre_flux, fg_color="transparent")
            if 2 <= k <= len(pastilles) - 2:
                ctk.CTkLabel(groupe, text="›", font=police(16), text_color=PALE, width=12).pack(side="left")
            actif = cle == self.filtre
            ctk.CTkButton(
                groupe, text=f"●  {nom}   {n}", height=32, corner_radius=16,
                font=police(12, actif), border_width=1,
                fg_color=melange(FOND, couleur, .18) if actif else "transparent",
                border_color=couleur if actif else BORD, hover_color=CARTE_SURVOL,
                text_color=TEXTE if (actif or n) else PALE,
                command=lambda c=cle: self._filtrer(c)).pack(side="left", padx=3)
            self._pastilles.append(groupe)
        self._placer_pastilles()
        self._maj_aide()

    def _placer_pastilles(self):
        """Dispose les étapes sur une ou plusieurs lignes selon la largeur disponible."""
        if not getattr(self, "_pastilles", None):
            return
        self.update_idletasks()
        dispo = max(self.barre_flux.winfo_width(), 400)
        x = ligne = 0
        for g in self._pastilles:
            l = g.winfo_reqwidth()
            if x and x + l > dispo:
                ligne += 1
                x = 0
            g.grid(row=ligne, column=0, sticky="w", padx=(x, 0), pady=2)
            x += l

    def _flux_redimensionne(self, event):
        if abs(event.width - self._largeur_flux) > 20:
            self._largeur_flux = event.width
            self.after_idle(self._placer_pastilles)

    def _filtrer(self, cle):
        self.filtre = cle
        self.toile.yview_moveto(0)
        self.appliquer_filtre()

    def _maj_aide(self):
        f = self.filtre
        etape = next((e for e in self.flux if e.id == f), None)
        if etape:
            logiciel = noyau.LOGICIELS[etape.logiciel]
            if etape.logiciel == "aucun":
                texte = f"En attente de « {etape.nom} ». Coche-les puis « ✓ Étape faite »."
            else:
                texte = (f"En attente de « {etape.nom} ». Coche-les puis « Envoyer vers {logiciel} » "
                         "pour les ouvrir toutes d'un coup.")
        else:
            texte = {
                A_TRIER: "Trie tes photos : P ou « Garder » pour les bonnes, X pour rejeter, 1 à 5 pour les étoiles.",
                TERMINEE: "Photos finies (JPG dans 03_JPG). Prêtes pour l'export web / Instagram.",
                REJETEE: "Photos écartées. U pour les remettre dans le tri.",
            }.get(f, "Coche les photos avec le rond en haut à gauche, puis envoie-les à l'étape suivante. "
                     "Espace = voir en grand.")
        self.lbl_aide.configure(text=texte)

    def _maj_resume(self):
        if not self.shooting:
            return
        r = self.shooting.resume(self.flux)
        self.barre_prog.set(r["progression"] / 100)
        self.lbl_prog.configure(text=f"{r['terminees']} / {r['objectif']} terminées")
        self._construire_flux(r["colonnes"])

    def _maj_boutons(self):
        etat = "normal" if self.shooting else "disabled"
        for b in self.boutons_shooting:
            b.configure(state=etat)

    # ------------------------------------------------------------------ miniatures
    def _taille(self) -> int:
        return int(self.reglages.get("taille_miniatures", 200))

    def _dims_image(self):
        l = int(self._taille() * self.echelle)
        return l, int(l * 0.68)

    def _charger_miniatures(self):
        self.generation += 1
        gen = self.generation
        for cle, cases in self.index_image.items():
            if cle in self.images or not cle:
                continue
            f = self.photos[cases[0]].fichier_apercu()
            self.executeur.submit(self._produire, gen, cle, f, self._dims_image(), int(12 * self.echelle))

    def _produire(self, gen, cle, fichier, dims, rayon):
        if gen != self.generation:
            return
        l, h = dims
        try:
            im = apercus.miniature(fichier, 480 if max(l, h) <= 240 else 800)
        except Exception:
            im = apercus.vignette_texte("?", l)
        im = ImageOps.fit(im, (l, h), Image.LANCZOS)
        normal = _arrondir(im, rayon, CARTE)
        sombre = _arrondir(ImageEnhance.Brightness(im).enhance(0.28), rayon, CARTE)
        self.file.put((gen, cle, normal, sombre))

    def _recevoir(self):
        try:
            for _ in range(40):
                gen, cle, normal, sombre = self.file.get_nowait()
                if gen != self.generation:
                    continue
                self.images[cle] = (ImageTk.PhotoImage(normal), ImageTk.PhotoImage(sombre))
                for idx in self.index_image.get(cle, []):
                    self._dessiner_case(idx)
        except queue.Empty:
            pass
        self.after(50, self._recevoir)

    def _changer_taille(self, valeur):
        valeur = int(valeur)
        if valeur == self._taille():
            return
        self.reglages["taille_miniatures"] = valeur
        reglages.enregistrer(self.reglages)
        self.images.clear()
        self.redessiner()
        self._charger_miniatures()

    # ------------------------------------------------------------------ grille
    def _dims(self):
        e = self.echelle
        l, h = self._dims_image()
        return l + int(18 * e), h + int(96 * e)  # case + marge

    def _colonnes(self) -> int:
        l, _ = self._dims()
        return max(1, (self.toile.winfo_width() - 10) // l)

    def _redessiner_si_largeur(self):
        if self.toile.winfo_width() != self._largeur:
            self._largeur = self.toile.winfo_width()
            if self.shooting:
                self.redessiner()
            else:
                self._afficher_accueil_si_besoin()

    def _message_toile(self, texte, libelle=None, commande=None):
        self.toile.delete("all")
        l = max(self.toile.winfo_width(), 600)
        self.toile.create_text(l // 2, 150, text=texte, fill=DOUX, font=(POLICE, 14), justify="center",
                               width=520)
        if libelle:
            b = bouton(self.toile, libelle, commande, "principal", height=42)
            self.toile.create_window(l // 2, 230, window=b)
        self.toile.configure(scrollregion=(0, 0, l, 300))

    def redessiner(self):
        self.toile.delete("all")
        if not self.shooting:
            return
        if not self.photos:
            if self.shooting.photos:
                self._message_toile("Aucune photo à cette étape pour l'instant. ✨")
            else:
                self._message_toile("Ce shooting est vide.\nImporte ta carte SD pour commencer.",
                                    "⤓  Importer une carte SD", self.importer)
            return
        for i in range(len(self.photos)):
            self._dessiner_case(i)
        l, h = self._dims()
        lignes = (len(self.photos) + self._colonnes() - 1) // self._colonnes()
        self.toile.configure(scrollregion=(0, 0, self._colonnes() * l, lignes * h + 90 * self.echelle))

    def _pos(self, i):
        l, h = self._dims()
        c = self._colonnes()
        return 6 + (i % c) * l, 6 + (i // c) * h

    def _geo(self, i):
        """Positions utiles d'une case : cadre, image, rond de sélection."""
        e = self.echelle
        x, y = self._pos(i)
        l, h = self._dims()
        il, ih = self._dims_image()
        w, hh = l - int(14 * e), h - int(14 * e)
        ix, iy = x + (w - il) // 2, y + (w - il) // 2
        return x, y, w, hh, ix, iy, il, ih, ix + int(18 * e), iy + int(18 * e)

    def _dessiner_case(self, i: int):
        if i >= len(self.photos):
            return
        t = self.toile
        e = self.echelle
        tag = f"case{i}"
        t.delete(tag)
        p = self.photos[i]
        x, y, w, hh, ix, iy, il, ih, cx, cy = self._geo(i)
        sel = i in self.selection
        fond = CARTE_SURVOL if (i == self.survol or sel) else CARTE
        _rect_arrondi(t, x, y, x + w, y + hh, int(14 * e), fill=fond,
                      outline=ACCENT if sel else (BORD if i == self.courant else fond),
                      width=max(1, int(2 * e)) if sel or i == self.courant else 1, tags=tag)
        imgs = self.images.get(_cle_image(p))
        if imgs:
            t.create_image(ix, iy, image=imgs[1] if p.choix == REJET else imgs[0], anchor="nw", tags=tag)
        else:
            _rect_arrondi(t, ix, iy, ix + il, iy + ih, int(12 * e), fill=CHAMP, outline="", tags=tag)
        # rond de sélection
        r = int(11 * e)
        if sel:
            t.create_oval(cx - r, cy - r, cx + r, cy + r, fill=ACCENT, outline=ACCENT, tags=tag)
            t.create_text(cx, cy, text="✓", fill="#16100a", font=(POLICE, -int(13 * e), "bold"), tags=tag)
        else:
            t.create_oval(cx - r, cy - r, cx + r, cy + r, fill="", outline="#e5e7eb",
                          width=max(1, int(2 * e)), tags=tag)
        if p.choix == REJET:
            t.create_text(ix + il // 2, iy + ih // 2, text="Rejetée", fill=ROUGE,
                          font=(POLICE, -int(15 * e), "bold"), tags=tag)
        # nom
        ty = iy + ih + int(18 * e)
        t.create_text(x + int(12 * e), ty, text=_raccourcir(p.nom, max(10, int(il / e) // 12)), fill=DOUX,
                      anchor="w", font=(POLICE, -int(11 * e)), tags=tag)
        t.create_text(x + w - int(12 * e), ty, text="★" * p.note + "☆" * (5 - p.note),
                      fill=ACCENT if p.note else PALE, anchor="e", font=(POLICE, -int(12 * e)), tags=tag)
        # pastille d'état + étoiles
        col = p.colonne(self.flux)
        couleur = self._couleur_colonne(col)
        police_etat = (POLICE, -int(11 * e), "bold")
        texte = _raccourcir(p.etat(self.flux), max(12, int(il / e) // 8))
        mesure = t.create_text(-999, -999, text=texte, font=police_etat)
        bx1, _, bx2, _ = t.bbox(mesure)
        t.delete(mesure)
        largeur = bx2 - bx1 + int(18 * e)
        py = ty + int(24 * e)
        _rect_arrondi(t, x + int(10 * e), py - int(11 * e), x + int(10 * e) + largeur, py + int(11 * e),
                      int(11 * e), fill=melange(fond, couleur, .2), outline="", tags=tag)
        t.create_text(x + int(10 * e) + largeur // 2, py, text=texte, fill=couleur, font=police_etat, tags=tag)
        # barre d'avancement : un segment par étape
        faites = p.etapes_faites(self.flux)
        prochaine = p.prochaine(self.flux)
        n = len(self.flux)
        by = py + int(22 * e)
        gauche, droite = x + int(12 * e), x + w - int(12 * e)
        ecart = int(4 * e)
        seg = (droite - gauche - ecart * (n - 1)) / max(n, 1)
        for k, etape in enumerate(self.flux):
            sx = gauche + k * (seg + ecart)
            if p.choix == REJET:
                c = BORD
            elif faites[k]:
                c = VERT
            elif prochaine and etape.id == prochaine.id and col != A_TRIER:
                c = COULEUR_LOGICIEL[etape.logiciel]
            else:
                c = BORD
            t.create_rectangle(sx, by, sx + seg, by + max(3, int(4 * e)), fill=c, outline="", tags=tag)

    def _couleur_colonne(self, col):
        if col == A_TRIER:
            return "#94a3b8"
        if col == TERMINEE:
            return VERT
        if col == REJETEE:
            return ROUGE
        etape = next((e for e in self.flux if e.id == col), None)
        return COULEUR_LOGICIEL[etape.logiciel] if etape else DOUX

    def _index_a(self, event) -> int | None:
        x, y = self.toile.canvasx(event.x), self.toile.canvasy(event.y)
        l, h = self._dims()
        c = self._colonnes()
        col, lig = int((x - 6) // l), int((y - 6) // h)
        if col < 0 or col >= c or lig < 0:
            return None
        i = lig * c + col
        return i if i < len(self.photos) else None

    def _sur_rond(self, event, i) -> bool:
        cx, cy = self._geo(i)[-2:]
        ex, ey = self.toile.canvasx(event.x), self.toile.canvasy(event.y)
        return (ex - cx) ** 2 + (ey - cy) ** 2 <= (20 * self.echelle) ** 2

    def _clic(self, event, ajout=False, etendre=False):
        self.toile.focus_set()
        i = self._index_a(event)
        if i is None:
            if not ajout and not etendre:
                self.deselectionner()
            return "break"
        if etendre and self.courant is not None:
            a, b = sorted((self.courant, i))
            self._selectionner(self.selection | set(range(a, b + 1)), i)
        elif ajout or self._sur_rond(event, i):
            self._selectionner(self.selection ^ {i}, i)
        else:
            self._selectionner({i}, i)
        return "break"

    def _mouvement(self, event):
        self._survoler(self._index_a(event))

    def _survoler(self, i):
        if i == self.survol:
            return
        ancien, self.survol = self.survol, i
        for k in (ancien, i):
            if k is not None:
                self._dessiner_case(k)
        self.toile.configure(cursor="hand2" if i is not None else "")

    def _selectionner(self, nouvelle: set[int], courant: int | None):
        self.detail.enregistrer_commentaire()
        anciens = self.selection | ({self.courant} if self.courant is not None else set())
        self.selection = nouvelle
        self.courant = courant
        for i in anciens | nouvelle | ({courant} if courant is not None else set()):
            if 0 <= i < len(self.photos):
                self._dessiner_case(i)
        self._maj_selection()
        self._voir(courant)

    def _maj_selection(self):
        self.detail.afficher()
        n = len(self.selection)
        if not n:
            self.barre_sel.place_forget()
            return
        self.lbl_sel.configure(text=f"{n} sélectionnée{'s' if n > 1 else ''}")
        etapes = [p.prochaine(self.flux) for p in self._selectionnees() if p.choix != REJET]
        logiciels = {e.logiciel for e in etapes if e} - {"aucun"}
        if len(logiciels) == 1:
            texte = f"Envoyer vers {noyau.LOGICIELS[logiciels.pop()]}  ▶"
        elif logiciels:
            texte = "Envoyer à l'étape suivante  ▶"
        else:
            texte = None
        if texte:
            self.btn_envoyer.configure(text=texte)
            self.btn_envoyer.pack(side="left", after=self.lbl_sel)
        else:
            self.btn_envoyer.pack_forget()
        self.barre_sel.place(relx=0.5, rely=1.0, y=-18, anchor="s")
        self.barre_sel.lift()

    def _voir(self, i):
        if i is None:
            return
        _, h = self._dims()
        _, y = self._pos(i)
        region = str(self.toile.cget("scrollregion")).split()
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
        self._selectionner(self.selection | {i} if etendre else {i}, i)
        return "break"

    def tout_selectionner(self):
        self._selectionner(set(range(len(self.photos))), self.courant or 0)
        return "break"

    def deselectionner(self):
        self._selectionner(set(), self.courant)
        return "break"

    def _selectionnees(self) -> list[noyau.Photo]:
        return [self.photos[i] for i in sorted(self.selection) if i < len(self.photos)]

    # ------------------------------------------------------------------ tri / notes
    def _modifier(self, action, photos=None):
        photos = photos if photos is not None else self._selectionnees()
        if not photos or not self.shooting:
            self.notifier("Coche d'abord une ou plusieurs photos (clic sur le rond en haut à gauche).")
            return False
        for p in photos:
            action(p)
        self.shooting.enregistrer()
        self._maj_resume()
        cles = {p.cle for p in photos}
        for i, p in enumerate(self.photos):
            if p.cle in cles:
                self._dessiner_case(i)
        self._maj_selection()
        self._maj_carte_active()
        return True

    def noter(self, n):
        self._modifier(lambda p: setattr(p, "note", n))

    def choisir(self, choix):
        ok = self._modifier(lambda p: setattr(p, "choix", choix))
        if ok and choix and len(self.selection) == 1 and self.courant is not None:
            self.deplacer(1)  # tri rapide : on passe à la suivante

    def marquer_faite(self):
        photos = [p for p in self._selectionnees() if p.choix != REJET]
        if self._modifier(lambda p: p.marquer_faite(self.flux), photos):
            self.notifier(f"✓  Étape validée pour {len(photos)} photo(s).")

    # ------------------------------------------------------------------ envoi vers les logiciels
    def envoyer(self):
        """Ouvre les photos cochées dans le logiciel de leur prochaine étape (toutes d'un coup)."""
        photos = [p for p in self._selectionnees() if p.choix != REJET and p.prochaine(self.flux)]
        if not photos:
            self.notifier("Coche les photos à envoyer (clic sur le rond), puis recommence.")
            return
        groupes: dict[str, list[noyau.Photo]] = {}
        for p in photos:
            groupes.setdefault(p.prochaine(self.flux).id, []).append(p)
        messages = []
        for id_etape, groupe in groupes.items():
            etape = next(e for e in self.flux if e.id == id_etape)
            if etape.logiciel == "aucun":
                continue
            chemin = self.reglages.get(etape.logiciel, "")
            nom_logiciel = noyau.LOGICIELS[etape.logiciel]
            if not chemin:
                messagebox.showwarning(nom_logiciel, f"Indique où est installé {nom_logiciel} dans ⚙ Paramètres.",
                                       parent=self)
                self.ouvrir_parametres()
                return
            fichiers = [f for f in (p.fichier_a_ouvrir() for p in groupe) if f]
            try:
                reglages.ouvrir_avec(chemin, fichiers)
            except Exception as ex:
                messagebox.showerror(nom_logiciel, str(ex), parent=self)
                return
            for p in groupe:
                p.envoyer(self.flux, etape)
                if p.choix == AUCUN:
                    p.choix = PICK
            messages.append(self._conseil(etape, len(fichiers)))
        if messages:
            self.shooting.enregistrer()
            self.appliquer_filtre()
            self._maj_carte_active()
            self.notifier("\n".join(messages), duree=9000)

    def _conseil(self, etape: noyau.Etape, n: int) -> str:
        logiciel = noyau.LOGICIELS[etape.logiciel]
        debut = f"▶  {n} photo(s) ouverte(s) dans {logiciel}."
        if etape.preuve == "tif":
            return debut + " Enregistre en TIF (Ctrl+S) : l'appli passera la photo à l'étape suivante toute seule."
        if etape.preuve == "jpg":
            dossier = self.shooting.chemin_etape("JPG")
            self.clipboard_clear()
            self.clipboard_append(str(dossier))
            return (debut + f" Exporte en JPG dans {dossier.name} — le chemin est copié, "
                            "colle-le (Ctrl+V) dans la fenêtre d'export.")
        return debut + " Quand c'est fini, coche-les et clique « ✓ Étape faite »."

    def ouvrir_avec_logiciel(self, cle_logiciel: str):
        fichiers = [f for f in (p.fichier_a_ouvrir() for p in self._selectionnees()) if f]
        try:
            reglages.ouvrir_avec(self.reglages.get(cle_logiciel, ""), fichiers)
        except Exception as ex:
            messagebox.showerror(noyau.LOGICIELS[cle_logiciel], str(ex), parent=self)

    def notifier(self, texte, duree=5000):
        self.toast.configure(text="  " + texte + "  ")
        self.toast.place(relx=0.5, rely=1.0, y=-96, anchor="s")
        self.toast.lift()
        if self._toast_id:
            self.after_cancel(self._toast_id)
        self._toast_id = self.after(duree, self.toast.place_forget)

    # ------------------------------------------------------------------ menus
    def _menu_plus(self):
        m = menu_sombre(self)
        m.add_command(label="📂  Ouvrir le dossier du shooting", command=self.ouvrir_dossier_shooting)
        m.add_command(label="🧹  Ranger les fichiers en vrac", command=self.ranger)
        m.add_separator()
        m.add_command(label="Lightroom ← écrire mes notes (XMP)", command=self.ecrire_xmp)
        m.add_command(label="Lightroom → lire ses notes (XMP)", command=self.lire_xmp)
        m.add_separator()
        m.add_command(label="⟳  Actualiser (F5)", command=self.recharger)
        b = self.boutons_shooting[-1]
        m.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height() + 4)

    def _menu_contextuel(self, event):
        i = self._index_a(event)
        if i is None:
            return
        if i not in self.selection:
            self._selectionner({i}, i)
        m = menu_sombre(self)
        m.add_command(label="▶  Envoyer à l'étape suivante", command=self.envoyer)
        m.add_command(label="✓  Étape faite", command=self.marquer_faite)
        m.add_separator()
        m.add_command(label="Ouvrir dans Photoshop", command=lambda: self.ouvrir_avec_logiciel("photoshop"))
        m.add_command(label="Ouvrir dans Lightroom", command=lambda: self.ouvrir_avec_logiciel("lightroom"))
        m.add_command(label="Voir en grand", command=self.grand_apercu)
        m.add_command(label="Montrer dans le dossier", command=self._montrer)
        m.add_separator()
        m.add_command(label="Garder (P)", command=lambda: self.choisir(PICK))
        m.add_command(label="Rejeter (X)", command=lambda: self.choisir(REJET))
        m.add_command(label="Remettre à trier", command=self._remettre_a_trier)
        m.tk_popup(event.x_root, event.y_root)

    def _remettre_a_trier(self):
        def action(p):
            p.choix, p.faites, p.envoyee = AUCUN, set(), ""
        self._modifier(action)

    def _montrer(self):
        if self.courant is not None:
            f = self.photos[self.courant].fichier_a_ouvrir()
            if f:
                reglages.ouvrir_dossier(f.parent, f)

    def ouvrir_dossier_shooting(self):
        if self.shooting:
            reglages.ouvrir_dossier(self.shooting.dossier)

    def grand_apercu(self):
        if self.courant is not None:
            GrandApercu(self, self.courant)
        return "break"

    # ------------------------------------------------------------------ actions shooting
    def nouveau_shooting(self):
        if not self.reglages["bibliotheque"] or not Path(self.reglages["bibliotheque"]).is_dir():
            self.changer_bibliotheque()
            if not self.reglages["bibliotheque"]:
                return
        FenetreNouveau(self)

    def shooting_cree(self, s: Shooting, importer: bool):
        self.actualiser_liste()
        self.ouvrir_shooting(s.dossier)
        if importer:
            self.importer()

    def importer(self):
        if not self.shooting:
            self.notifier("Choisis d'abord (ou crée) le shooting où ranger les photos.")
            return
        FenetreImport(self)

    def ranger(self):
        mouvements = self.shooting.a_ranger()
        if not mouvements:
            self.notifier("✓  Tout est déjà bien rangé.")
            return
        lignes = [f"{s.name}  →  {d.parent.name}" for s, d in mouvements]
        texte = "\n".join(lignes[:25]) + (f"\n… et {len(lignes) - 25} autres" if len(lignes) > 25 else "")
        if messagebox.askyesno("Ranger", f"Déplacer {len(mouvements)} fichier(s) ?\n\n{texte}", parent=self):
            n = self.shooting.ranger(mouvements)
            self.notifier(f"🧹  {n} fichier(s) rangé(s).")
            self.recharger()

    def ecrire_xmp(self):
        n = noyau.exporter_notes_xmp(self.shooting.photos)
        messagebox.showinfo("Lightroom", f"Notes écrites pour {n} RAW.\n\nDans Lightroom : sélectionne les "
                            "photos → Métadonnées → « Lire les métadonnées à partir des fichiers ».",
                            parent=self)

    def lire_xmp(self):
        n = noyau.importer_notes_xmp(self.shooting.photos)
        self.shooting.enregistrer()
        self.recharger()
        self.notifier(f"Notes Lightroom lues pour {n} photo(s). (Pense à faire Ctrl+S dans Lightroom avant.)")

    def exporter_web(self):
        FenetreExport(self)

    def ouvrir_parametres(self):
        FenetreParametres(self)

    def parametres_changes(self, biblio_changee: bool):
        self.flux = noyau.flux_depuis(self.reglages.get("flux"))
        if self.filtre not in [A_TRIER, TERMINEE, REJETEE, "Toutes"] + [e.id for e in self.flux]:
            self.filtre = "Toutes"
        if biblio_changee:
            self.shooting = None
            self.photos = []
            self.redessiner()
            self.actualiser_liste()
            self._afficher_accueil_si_besoin()
        else:
            self.actualiser_liste()
            self.recharger()

    def quitter(self):
        self.detail.enregistrer_commentaire()
        self.executeur.shutdown(wait=False, cancel_futures=True)
        self.destroy()


# --------------------------------------------------------------------------- petits outils

def _rect_arrondi(toile, x1, y1, x2, y2, r, **kw):
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    points = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
              x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return toile.create_polygon(points, smooth=True, **kw)


def _arrondir(im: Image.Image, rayon: int, fond: str) -> Image.Image:
    masque = Image.new("L", im.size, 0)
    ImageDraw.Draw(masque).rounded_rectangle([0, 0, im.width - 1, im.height - 1], rayon, fill=255)
    sortie = Image.new("RGB", im.size, fond)
    sortie.paste(im.convert("RGB"), (0, 0), masque)
    return sortie


def _cle_image(p: noyau.Photo) -> str:
    f = p.fichier_apercu()
    return str(f) if f else ""


def _raccourcir(texte: str, n: int) -> str:
    return texte if len(texte) <= n else texte[: n - 1] + "…"


MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]


def _date_lisible(iso: str) -> str:
    try:
        d = date.fromisoformat(iso)
    except ValueError:
        return iso
    return f"{d.day} {MOIS[d.month - 1]} {d.year}"


# --------------------------------------------------------------------------- composants

class CarteShooting(ctk.CTkFrame):
    def __init__(self, parent, app: Application, s: Shooting):
        super().__init__(parent, fg_color="transparent", corner_radius=12, border_width=1, border_color=BARRE)
        self.app = app
        self.dossier = s.dossier
        self._actif = False
        self.lbl_nom = ctk.CTkLabel(self, text="", font=police(14, True), text_color=TEXTE, anchor="w")
        self.lbl_nom.pack(fill="x", padx=14, pady=(10, 0))
        self.lbl_info = ctk.CTkLabel(self, text="", font=police(12), text_color=DOUX, anchor="w", height=18)
        self.lbl_info.pack(fill="x", padx=14)
        bas = ctk.CTkFrame(self, fg_color="transparent")
        bas.pack(fill="x", padx=14, pady=(6, 12))
        self.barre = ctk.CTkProgressBar(bas, width=100, height=5, corner_radius=3, fg_color=CHAMP,
                                        progress_color=VERT)
        self.barre.pack(side="left", fill="x", expand=True)
        self.lbl_pct = ctk.CTkLabel(bas, text="", font=police(11, True), text_color=DOUX, width=52, anchor="e")
        self.lbl_pct.pack(side="left", padx=(8, 0))
        self.maj(s)
        for w in (self, self.lbl_nom, self.lbl_info, bas, self.barre, self.lbl_pct):
            w.bind("<Button-1>", lambda e: self.app.ouvrir_shooting(self.dossier))
            w.bind("<Enter>", lambda e: self._survol(True))
            w.bind("<Leave>", lambda e: self._survol(False))

    def maj(self, s: Shooting):
        r = s.resume(self.app.flux)
        self.lbl_nom.configure(text=_raccourcir(s.infos.get("voiture") or s.nom, 26))
        infos = [s.infos.get("client"), _date_lisible(s.infos.get("date", "")), f"{r['total']} photos"]
        self.lbl_info.configure(text=" · ".join(x for x in infos if x))
        self.barre.set(r["progression"] / 100)
        self.lbl_pct.configure(text=f"{r['progression']} %")

    def selectionner(self, actif: bool):
        self._actif = actif
        self.configure(fg_color=CARTE if actif else "transparent", border_color=BORD if actif else BARRE)

    def _survol(self, dedans):
        if not self._actif:
            self.configure(fg_color=CARTE_SURVOL if dedans else "transparent")


class PanneauDetail(ctk.CTkFrame):
    """Colonne de droite : la photo en cours, son avancement, ses fichiers et la note de retouche."""

    def __init__(self, app: Application):
        super().__init__(app, fg_color=BARRE, corner_radius=0, width=330)
        self.app = app
        self.grid_propagate(False)
        self.pack_propagate(False)
        self.photo: noyau.Photo | None = None
        self.image = None
        self._chemin_image = None

        self.vide = ctk.CTkLabel(self, text="Clique sur une photo\npour voir son détail", font=police(13),
                                 text_color=PALE, justify="center")
        self.contenu = ctk.CTkScrollableFrame(self, fg_color="transparent", scrollbar_button_color=CHAMP)
        c = self.contenu
        self.lbl_image = ctk.CTkLabel(c, text="", fg_color=CARTE, corner_radius=14, height=200)
        self.lbl_image.pack(fill="x", padx=8, pady=(14, 12))
        self.lbl_nom = ctk.CTkLabel(c, text="", font=police(15, True), text_color=TEXTE, anchor="w",
                                    justify="left", wraplength=280)
        self.lbl_nom.pack(fill="x", padx=12)
        ligne = ctk.CTkFrame(c, fg_color="transparent")
        ligne.pack(fill="x", padx=10, pady=(8, 4))
        self.pastille = ctk.CTkLabel(ligne, text="", font=police(12, True), corner_radius=11, height=24)
        self.pastille.pack(side="left")
        self.etoiles = []
        boite = ctk.CTkFrame(c, fg_color="transparent")
        boite.pack(fill="x", padx=6)
        for n in range(1, 6):
            b = ctk.CTkButton(boite, text="★", width=24, height=26, fg_color="transparent", hover_color=CHAMP,
                              font=police(16), corner_radius=6, command=lambda n=n: self._noter(n))
            b.pack(side="left")
            self.etoiles.append(b)

        self._titre(c, "AVANCEMENT")
        self.cadre_etapes = ctk.CTkFrame(c, fg_color=CARTE, corner_radius=12)
        self.cadre_etapes.pack(fill="x", padx=8)
        self._titre(c, "FICHIERS")
        self.cadre_fichiers = ctk.CTkFrame(c, fg_color=CARTE, corner_radius=12)
        self.cadre_fichiers.pack(fill="x", padx=8)
        self._titre(c, "NOTE DE RETOUCHE")
        self.txt = ctk.CTkTextbox(c, height=90, fg_color=CARTE, corner_radius=12, font=police(13),
                                  text_color=TEXTE, border_width=0, wrap="word")
        self.txt.pack(fill="x", padx=8, pady=(0, 16))
        self.txt.bind("<FocusOut>", lambda e: self.enregistrer_commentaire())
        self.vide.place(relx=0.5, rely=0.45, anchor="center")

    def _titre(self, parent, texte):
        ctk.CTkLabel(parent, text=texte, font=police(11, True), text_color=PALE,
                     anchor="w").pack(fill="x", padx=12, pady=(18, 6))

    def _noter(self, n):
        if self.photo:
            n = 0 if self.photo.note == n and len(self.app.selection) <= 1 else n
            self.app._modifier(lambda p: setattr(p, "note", n), self.app._selectionnees() or [self.photo])

    def enregistrer_commentaire(self):
        if not self.photo or not self.app.shooting:
            return
        texte = self.txt.get("1.0", "end").strip()
        if texte != self.photo.commentaire:
            self.photo.commentaire = texte
            self.app.shooting.enregistrer()

    def afficher(self):
        app = self.app
        p = app.photos[app.courant] if app.courant is not None and app.courant < len(app.photos) else None
        if p is None:
            self.photo = None
            self.contenu.pack_forget()
            self.vide.place(relx=0.5, rely=0.45, anchor="center")
            return
        changement = p is not self.photo
        self.photo = p
        self.vide.place_forget()
        self.contenu.pack(fill="both", expand=True)
        flux = app.flux
        self.lbl_nom.configure(text=p.nom)
        couleur = app._couleur_colonne(p.colonne(flux))
        self.pastille.configure(text=f"  {p.etat(flux)}  ", text_color=couleur,
                                fg_color=melange(BARRE, couleur, .2))
        for k, b in enumerate(self.etoiles, start=1):
            b.configure(text_color=ACCENT if k <= p.note else PALE)
        self._image(p)
        # avancement
        for w in self.cadre_etapes.winfo_children():
            w.destroy()
        faites = p.etapes_faites(flux)
        prochaine = p.prochaine(flux)
        lignes = [("Import RAW", True, None)] + [(e.nom, f, e) for e, f in zip(flux, faites)]
        for k, (nom, faite, etape) in enumerate(lignes):
            en_cours = (etape is not None and prochaine is not None and etape.id == prochaine.id
                        and p.choix != REJET)
            ligne = ctk.CTkFrame(self.cadre_etapes, fg_color="transparent")
            ligne.pack(fill="x", padx=12, pady=(10 if k == 0 else 3, 10 if k == len(lignes) - 1 else 3))
            if faite:
                symbole, coul = "✓", VERT
            elif en_cours:
                symbole, coul = "●", COULEUR_LOGICIEL[etape.logiciel]
            else:
                symbole, coul = "○", PALE
            ctk.CTkLabel(ligne, text=symbole, font=police(14, True), text_color=coul, width=22).pack(side="left")
            ctk.CTkLabel(ligne, text=nom, font=police(13, en_cours),
                         text_color=TEXTE if (faite or en_cours) else DOUX, anchor="w").pack(side="left", padx=(6, 0))
        # fichiers
        for w in self.cadre_fichiers.winfo_children():
            w.destroy()
        for code in noyau.CODES_DOSSIERS:
            fichiers = p.fichiers.get(code, [])
            ligne = ctk.CTkFrame(self.cadre_fichiers, fg_color="transparent")
            ligne.pack(fill="x", padx=10, pady=(8 if code == "RAW" else 2, 8 if code == "WEB" else 2))
            couleur = COULEUR_VERSION[code]
            ctk.CTkLabel(ligne, text=code, font=police(10, True), width=40, height=20, corner_radius=6,
                         fg_color=melange(CARTE, couleur, .25) if fichiers else CHAMP,
                         text_color=couleur if fichiers else PALE).pack(side="left")
            if not fichiers:
                ctk.CTkLabel(ligne, text="—", text_color=PALE, font=police(12)).pack(side="left", padx=8)
            for f in fichiers[:2]:
                lien = ctk.CTkLabel(ligne, text=_raccourcir(f.name, 24 if len(fichiers) == 1 else 12),
                                    text_color="#93c5fd", font=police(12), cursor="hand2")
                lien.pack(side="left", padx=(8, 0))
                lien.bind("<Button-1>", lambda e, f=f: reglages.ouvrir_dossier(f.parent, f))
        if changement:
            self.txt.delete("1.0", "end")
            if p.commentaire:
                self.txt.insert("1.0", p.commentaire)

    def _image(self, p):
        f = p.fichier_apercu()
        if f is None or (str(f) == self._chemin_image and self.image is not None):
            return
        self._chemin_image = str(f)

        def travail(chemin=f):
            try:
                im = apercus.miniature(chemin, 640)
            except Exception:
                return
            self.app.after(0, lambda: self._poser(str(chemin), im))

        self.app.executeur.submit(travail)

    def _poser(self, chemin, im):
        if chemin != self._chemin_image or not self.winfo_exists():
            return
        largeur = 290
        hauteur = min(int(largeur * im.height / im.width), 330)
        im = ImageOps.fit(im, (largeur * 2, hauteur * 2), Image.LANCZOS)
        im = _arrondir(im, 24, BARRE)
        self.image = ctk.CTkImage(light_image=im, dark_image=im, size=(largeur, hauteur))
        self.lbl_image.configure(image=self.image, height=hauteur, fg_color="transparent")


class GrandApercu(ctk.CTkToplevel):
    def __init__(self, app: Application, index: int):
        super().__init__(app, fg_color="#000000")
        self.app = app
        self.index = index
        self.title("Aperçu")
        self.cote = min(self.winfo_screenwidth(), self.winfo_screenheight()) - 140
        self.geometry(f"{int(self.cote * 1.4)}x{self.cote}")
        self.lbl = tk.Label(self, bg="#000000")
        self.lbl.pack(fill="both", expand=True)
        self.info = ctk.CTkLabel(self, text="", font=police(12), text_color=DOUX, fg_color="#000000")
        self.info.pack(fill="x", pady=6)
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<space>", lambda e: self.destroy())
        self.bind("<Left>", lambda e: self._aller(-1))
        self.bind("<Right>", lambda e: self._aller(1))
        self._montrer()
        self.after(150, self._premier_plan)

    def _premier_plan(self):
        self.lift()
        self.focus_force()

    def _aller(self, d):
        self.index = min(max(self.index + d, 0), len(self.app.photos) - 1)
        self._montrer()

    def _montrer(self):
        p = self.app.photos[self.index]
        f = p.fichier_apercu()
        if not f:
            return
        self.img = ImageTk.PhotoImage(apercus.grand_apercu(f, self.cote))
        self.lbl.configure(image=self.img)
        self.info.configure(text=f"{p.nom}   ·   {p.etat(self.app.flux)}   ·   ← →  pour naviguer   ·   "
                                 "Échap pour fermer")


# --------------------------------------------------------------------------- fenêtres

class Fenetre(ctk.CTkToplevel):
    def __init__(self, app, titre, sous_titre=""):
        super().__init__(app, fg_color=FOND)
        self.app = app
        self.title(titre)
        self.transient(app)
        self.resizable(False, False)
        self.corps = ctk.CTkFrame(self, fg_color="transparent")
        self.corps.pack(fill="both", expand=True, padx=28, pady=24)
        ctk.CTkLabel(self.corps, text=titre, font=police(20, True), text_color=TEXTE,
                     anchor="w").pack(fill="x")
        if sous_titre:
            ctk.CTkLabel(self.corps, text=sous_titre, font=police(13), text_color=DOUX, anchor="w",
                         justify="left", wraplength=520).pack(fill="x", pady=(2, 0))
        self.bind("<Escape>", lambda e: self.fermer())
        self.protocol("WM_DELETE_WINDOW", self.fermer)

    def champ(self, libelle, variable=None, placeholder="", largeur=420):
        ctk.CTkLabel(self.corps, text=libelle, font=police(12, True), text_color=DOUX,
                     anchor="w").pack(fill="x", pady=(16, 4))
        e = ctk.CTkEntry(self.corps, textvariable=variable, placeholder_text=placeholder, width=largeur,
                         height=40, corner_radius=10, fg_color=CHAMP, border_color=BORD, text_color=TEXTE,
                         font=police(13))
        e.pack(fill="x")
        return e

    def boutons(self):
        b = ctk.CTkFrame(self.corps, fg_color="transparent")
        b.pack(fill="x", pady=(24, 0))
        return b

    def montrer(self):
        self.update_idletasks()
        a = self.app
        x = a.winfo_rootx() + (a.winfo_width() - self.winfo_width()) // 2
        y = a.winfo_rooty() + (a.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.after(120, self._modal)

    def _modal(self):
        try:
            self.lift()
            self.focus_force()
            self.grab_set()
        except tk.TclError:
            pass

    def fermer(self):
        self.destroy()


class FenetreNouveau(Fenetre):
    def __init__(self, app):
        super().__init__(app, "Nouveau shooting", "Un dossier bien rangé sera créé pour ce shooting.")
        self.voiture = self.champ("VOITURE", placeholder="ex. Porsche 911 GT3")
        self.client = self.champ("CLIENT (facultatif)", placeholder="ex. Lucas")
        self.var_date = ctk.StringVar(value=date.today().isoformat())
        self.champ("DATE", self.var_date)
        self.notes = self.champ("LIEU / NOTES (facultatif)", placeholder="ex. Circuit Paul Ricard")
        self.erreur = ctk.CTkLabel(self.corps, text="", text_color=ROUGE, font=police(12), anchor="w")
        self.erreur.pack(fill="x", pady=(8, 0))
        b = self.boutons()
        bouton(b, "Créer et importer les photos", lambda: self._creer(True), "principal",
               height=42).pack(side="right")
        bouton(b, "Créer", lambda: self._creer(False), height=42).pack(side="right", padx=8)
        bouton(b, "Annuler", self.fermer, "discret", height=42).pack(side="left")
        self.bind("<Return>", lambda e: self._creer(True))
        self.after(200, self.voiture.focus_set)
        self.montrer()

    def _creer(self, importer):
        if not self.voiture.get().strip():
            self.erreur.configure(text="Indique au moins la voiture.")
            return
        try:
            jour = date.fromisoformat(self.var_date.get().strip())
        except ValueError:
            self.erreur.configure(text="Date invalide (format AAAA-MM-JJ, ex. 2026-09-26).")
            return
        try:
            s = Shooting.creer(self.app.reglages["bibliotheque"], self.voiture.get(), self.client.get(),
                               jour, self.notes.get())
        except (FileExistsError, OSError) as e:
            self.erreur.configure(text=str(e))
            return
        self.destroy()
        self.app.shooting_cree(s, importer)


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


class FenetreImport(Fenetre):
    def __init__(self, app: Application):
        self.s = app.shooting
        super().__init__(app, "Importer des photos",
                         f"Vers « {self.s.infos.get('voiture') or self.s.nom} »  ·  "
                         f"dossier {noyau.DOSSIER_ETAPE['RAW']}")
        self.plan = []
        self.annule = False
        self.en_cours = False
        cartes = cartes_memoire()
        ctk.CTkLabel(self.corps, text="DEPUIS", font=police(12, True), text_color=DOUX,
                     anchor="w").pack(fill="x", pady=(18, 4))
        ligne = ctk.CTkFrame(self.corps, fg_color="transparent")
        ligne.pack(fill="x")
        self.var_source = ctk.StringVar(value=cartes[0] if cartes else "")
        ctk.CTkComboBox(ligne, variable=self.var_source, values=cartes or [""], width=400, height=40,
                        corner_radius=10, fg_color=CHAMP, border_color=BORD, button_color=BORD,
                        text_color=TEXTE, font=police(13),
                        command=lambda v: self._analyser()).pack(side="left")
        bouton(ligne, "Parcourir…", self._parcourir, height=40).pack(side="left", padx=(8, 0))
        if cartes:
            ctk.CTkLabel(self.corps, text="✓ Carte SD détectée", text_color=VERT, font=police(12),
                         anchor="w").pack(fill="x", pady=(4, 0))

        try:
            jour = date.fromisoformat(self.s.infos.get("date", ""))
        except ValueError:
            jour = date.today()
        self.var_renommer = ctk.BooleanVar(value=bool(app.reglages.get("renommer_import", True)))
        ctk.CTkSwitch(self.corps, text="Renommer les photos", variable=self.var_renommer, font=police(13),
                      text_color=TEXTE, progress_color=ACCENT,
                      command=self._analyser).pack(anchor="w", pady=(20, 4))
        self.var_prefixe = ctk.StringVar(value=noyau.nom_dossier_shooting(jour, self.s.infos.get("voiture", "")
                                                                          or "photo"))
        e = ctk.CTkEntry(self.corps, textvariable=self.var_prefixe, height=38, corner_radius=10, fg_color=CHAMP,
                         border_color=BORD, text_color=TEXTE, font=police(13))
        e.pack(fill="x")
        e.bind("<FocusOut>", lambda ev: self._analyser())

        self.info = ctk.CTkLabel(self.corps, text="", font=police(13), text_color=DOUX, anchor="w",
                                 justify="left", wraplength=520)
        self.info.pack(fill="x", pady=(18, 6))
        self.prog = ctk.CTkProgressBar(self.corps, height=8, corner_radius=4, fg_color=CHAMP,
                                       progress_color=ACCENT)
        self.prog.set(0)
        self.prog.pack(fill="x")
        b = self.boutons()
        self.btn_go = bouton(b, "Importer", self._lancer, "principal", height=42, width=140)
        self.btn_go.pack(side="right")
        self.btn_fermer = bouton(b, "Fermer", self.fermer, "discret", height=42)
        self.btn_fermer.pack(side="left")
        self.var_source.trace_add("write", lambda *a: self.after(300, self._analyser))
        self._analyser()
        self.montrer()

    def _parcourir(self):
        d = filedialog.askdirectory(parent=self, title="Carte SD ou dossier de photos")
        if d:
            self.var_source.set(d)

    def _analyser(self):
        if self.en_cours:
            return
        src = self.var_source.get().strip()
        if not src or not Path(src).is_dir():
            self.plan = []
            self.info.configure(text="Branche ta carte SD ou choisis un dossier avec « Parcourir ».")
            self.btn_go.configure(state="disabled")
            return
        prefixe = self.var_prefixe.get().strip() if self.var_renommer.get() else ""
        try:
            self.plan = noyau.preparer_import(src, self.s.chemin_etape("RAW"), prefixe)
        except OSError as e:
            self.info.configure(text=f"Lecture impossible : {e}")
            return
        taille = sum(s.stat().st_size for s, _ in self.plan) / 1e9
        if self.plan:
            self.info.configure(text=f"📷  {len(self.plan)} nouveau(x) fichier(s) · {taille:.1f} Go\n"
                                     f"ex. {self.plan[0][0].name}  →  {self.plan[0][1].name}\n"
                                     "Les photos déjà importées sont ignorées automatiquement.")
        else:
            self.info.configure(text="Rien de nouveau à importer depuis ce dossier.")
        self.btn_go.configure(state="normal" if self.plan else "disabled")

    def _lancer(self):
        self.app.reglages["renommer_import"] = self.var_renommer.get()
        reglages.enregistrer(self.app.reglages)
        self.en_cours = True
        self.btn_go.configure(state="disabled", text="Import…")
        self.btn_fermer.configure(text="Arrêter")
        plan = list(self.plan)

        def progression(i, n, nom):
            self.after(0, lambda: (self.prog.set(i / n), self.info.configure(text=f"{i} / {n}   ·   {nom}")))

        def travail():
            try:
                n = noyau.importer(plan, progression, lambda: self.annule)
                self.after(0, lambda: self._fini(f"✓  {n} fichier(s) importé(s) et vérifié(s).\n"
                                                 "Tu peux formater la carte."))
            except Exception as e:
                self.after(0, lambda e=e: self._fini(f"Erreur : {e}"))

        threading.Thread(target=travail, daemon=True).start()

    def _fini(self, texte):
        self.en_cours = False
        if self.winfo_exists():
            self.info.configure(text=texte)
            self.btn_fermer.configure(text="Fermer")
            self.btn_go.configure(text="Importer")
        self.app.recharger()
        self.app._maj_carte_active()

    def fermer(self):
        if self.en_cours:
            self.annule = True
            return
        self.destroy()


class FenetreExport(Fenetre):
    def __init__(self, app: Application):
        super().__init__(app, "Export web / Instagram",
                         "Crée des JPG légers dans 04_WEB à partir de tes photos terminées (03_JPG).")
        self.sources_sel = noyau.sources_pour_export(app._selectionnees())
        self.sources_tout = noyau.sources_pour_export(app.shooting.photos)
        self.var_quoi = ctk.StringVar(value="sel" if self.sources_sel else "tout")
        ctk.CTkLabel(self.corps, text="PHOTOS", font=police(12, True), text_color=DOUX,
                     anchor="w").pack(fill="x", pady=(18, 6))
        for val, texte in (("sel", f"Les photos cochées ({len(self.sources_sel)} terminée(s))"),
                           ("tout", f"Toutes les terminées ({len(self.sources_tout)})")):
            ctk.CTkRadioButton(self.corps, text=texte, value=val, variable=self.var_quoi, font=police(13),
                               text_color=TEXTE, fg_color=ACCENT, hover_color=ACCENT_SURVOL,
                               border_color=PALE).pack(anchor="w", pady=3)
        ctk.CTkLabel(self.corps, text="FORMAT", font=police(12, True), text_color=DOUX,
                     anchor="w").pack(fill="x", pady=(16, 6))
        self.var_format = ctk.StringVar(value=next(iter(noyau.FORMATS_WEB)))
        ctk.CTkOptionMenu(self.corps, variable=self.var_format, values=list(noyau.FORMATS_WEB), width=320,
                          height=38, corner_radius=10, fg_color=CHAMP, button_color=BORD,
                          button_hover_color=CARTE_SURVOL, text_color=TEXTE, font=police(13),
                          dropdown_fg_color=CARTE, dropdown_text_color=TEXTE).pack(anchor="w")
        self.var_filigrane = ctk.StringVar(value=app.reglages.get("filigrane", ""))
        self.champ("SIGNATURE (vide = aucune)", self.var_filigrane)
        ligne = ctk.CTkFrame(self.corps, fg_color="transparent")
        ligne.pack(fill="x", pady=(16, 0))
        ctk.CTkLabel(ligne, text="Bandes Insta", font=police(13), text_color=DOUX).pack(side="left")
        self.var_fond = ctk.StringVar(value="Noir")
        ctk.CTkSegmentedButton(ligne, values=["Noir", "Blanc"], variable=self.var_fond, font=police(12),
                               selected_color=BORD, unselected_color=CHAMP,
                               fg_color=CHAMP).pack(side="left", padx=10)
        ctk.CTkLabel(ligne, text="Qualité", font=police(13), text_color=DOUX).pack(side="left", padx=(20, 6))
        self.var_qualite = ctk.IntVar(value=int(app.reglages.get("qualite_web", 90)))
        self.lbl_q = ctk.CTkLabel(ligne, text=str(self.var_qualite.get()), font=police(13, True), width=30)
        ctk.CTkSlider(ligne, from_=60, to=100, number_of_steps=40, variable=self.var_qualite, width=120,
                      button_color=ACCENT, progress_color=ACCENT, fg_color=CHAMP,
                      command=lambda v: self.lbl_q.configure(text=str(int(v)))).pack(side="left")
        self.lbl_q.pack(side="left", padx=6)
        self.info = ctk.CTkLabel(self.corps, text="", font=police(13), text_color=DOUX, anchor="w")
        self.info.pack(fill="x", pady=(18, 6))
        self.prog = ctk.CTkProgressBar(self.corps, height=8, corner_radius=4, fg_color=CHAMP,
                                       progress_color=ACCENT)
        self.prog.set(0)
        self.prog.pack(fill="x")
        b = self.boutons()
        self.btn = bouton(b, "Exporter", self._lancer, "principal", height=42, width=140)
        self.btn.pack(side="right")
        bouton(b, "Fermer", self.fermer, "discret", height=42).pack(side="left")
        self.montrer()

    def _lancer(self):
        sources = self.sources_sel if self.var_quoi.get() == "sel" else self.sources_tout
        if not sources:
            self.info.configure(text="Aucune photo terminée : il faut d'abord un JPG dans 03_JPG.")
            return
        self.app.reglages["filigrane"] = self.var_filigrane.get()
        self.app.reglages["qualite_web"] = int(self.var_qualite.get())
        reglages.enregistrer(self.app.reglages)
        self.btn.configure(state="disabled")
        args = dict(format_web=self.var_format.get(), qualite=int(self.var_qualite.get()),
                    filigrane=self.var_filigrane.get().strip(),
                    fond="#000000" if self.var_fond.get() == "Noir" else "#ffffff")
        dossier = self.app.shooting.chemin_etape("WEB")

        def progression(i, n, nom):
            self.after(0, lambda: (self.prog.set(i / n), self.info.configure(text=f"{i} / {n}   ·   {nom}")))

        def travail():
            try:
                crees = noyau.exporter_web(sources, dossier, progression=progression, **args)
                self.after(0, lambda: self._fini(f"✓  {len(crees)} image(s) créée(s) dans {dossier.name}."))
            except Exception as e:
                self.after(0, lambda e=e: self._fini(f"Erreur : {e}"))

        threading.Thread(target=travail, daemon=True).start()

    def _fini(self, texte):
        if self.winfo_exists():
            self.info.configure(text=texte)
            self.btn.configure(state="normal")
        self.app.recharger()


class FenetreParametres(Fenetre):
    def __init__(self, app: Application):
        super().__init__(app, "Paramètres")
        r = app.reglages
        onglets = ctk.CTkTabview(self.corps, width=680, height=560, fg_color=CARTE, corner_radius=14,
                                 segmented_button_fg_color=CHAMP, segmented_button_selected_color=BORD,
                                 segmented_button_selected_hover_color=BORD,
                                 segmented_button_unselected_color=CHAMP, text_color=TEXTE)
        onglets.pack(fill="both", expand=True, pady=(12, 0))
        flux_tab = onglets.add("Mon flux de travail")
        general = onglets.add("Dossiers et logiciels")

        # -- flux de travail
        ctk.CTkLabel(flux_tab, text="Les étapes que suit chaque photo après le tri. L'appli s'en sert pour savoir "
                                    "où en est chaque photo et vers quel logiciel l'envoyer.",
                     font=police(12), text_color=DOUX, wraplength=620, justify="left",
                     anchor="w").pack(fill="x", padx=12, pady=(6, 10))
        ligne = ctk.CTkFrame(flux_tab, fg_color="transparent")
        ligne.pack(fill="x", padx=12)
        ctk.CTkLabel(ligne, text="Modèle", font=police(13, True), text_color=TEXTE).pack(side="left")
        self.var_modele = ctk.StringVar(value=r.get("modele_flux") or noyau.FLUX_PAR_DEFAUT)
        ctk.CTkOptionMenu(ligne, variable=self.var_modele, values=list(noyau.MODELES_FLUX) + ["Personnalisé"],
                          width=300, height=34, corner_radius=10, fg_color=CHAMP, button_color=BORD,
                          button_hover_color=CARTE_SURVOL, text_color=TEXTE, font=police(13),
                          dropdown_fg_color=CARTE, dropdown_text_color=TEXTE,
                          command=self._choisir_modele).pack(side="left", padx=10)
        self.apercu_flux = ctk.CTkLabel(flux_tab, text="", font=police(12, True), text_color=ACCENT,
                                        wraplength=620, justify="left", anchor="w")
        self.apercu_flux.pack(fill="x", padx=12, pady=(10, 6))
        self.cadre_etapes = ctk.CTkScrollableFrame(flux_tab, fg_color="transparent", height=300)
        self.cadre_etapes.pack(fill="both", expand=True, padx=4)
        bouton(flux_tab, "＋  Ajouter une étape", self._ajouter, "discret", height=34).pack(anchor="w", padx=8)
        self.etapes = noyau.flux_depuis(r.get("flux"))
        self._dessiner_etapes()

        # -- dossiers et logiciels
        self.vars = {}
        for cle, libelle, type_ in (("bibliotheque", "DOSSIER DES SHOOTINGS", "dossier"),
                                    ("lightroom", "LIGHTROOM CLASSIC", "fichier"),
                                    ("photoshop", "PHOTOSHOP", "fichier")):
            ctk.CTkLabel(general, text=libelle, font=police(12, True), text_color=DOUX,
                         anchor="w").pack(fill="x", padx=12, pady=(14, 4))
            l = ctk.CTkFrame(general, fg_color="transparent")
            l.pack(fill="x", padx=12)
            v = ctk.StringVar(value=str(r.get(cle, "")))
            ctk.CTkEntry(l, textvariable=v, height=38, corner_radius=10, fg_color=CHAMP, border_color=BORD,
                         text_color=TEXTE, font=police(12)).pack(side="left", fill="x", expand=True)
            bouton(l, "Parcourir…", lambda v=v, t=type_: self._parcourir(v, t),
                   height=38).pack(side="left", padx=(8, 0))
            self.vars[cle] = v
        ctk.CTkLabel(general, text="Photoshop et Lightroom sont cherchés automatiquement. Indique-les ici s'ils "
                                   "ne sont pas trouvés (fichier Photoshop.exe / Lightroom.exe).",
                     font=police(12), text_color=PALE, wraplength=620, justify="left",
                     anchor="w").pack(fill="x", padx=12, pady=(14, 0))

        b = self.boutons()
        bouton(b, "Enregistrer", self._valider, "principal", height=42, width=140).pack(side="right")
        bouton(b, "Annuler", self.fermer, "discret", height=42).pack(side="left")
        self.montrer()

    def _parcourir(self, var, type_):
        if type_ == "dossier":
            v = filedialog.askdirectory(parent=self)
        elif sys.platform == "darwin":
            v = filedialog.askopenfilename(parent=self, initialdir="/Applications")
        else:
            v = filedialog.askopenfilename(parent=self, filetypes=[("Programme", "*.exe"), ("Tous", "*.*")])
        if v:
            var.set(v)

    def _choisir_modele(self, nom):
        if nom in noyau.MODELES_FLUX:
            self.etapes = [noyau.Etape(**e.en_dict()) for e in noyau.MODELES_FLUX[nom]]
            self._dessiner_etapes()

    def _lire_lignes(self):
        logiciels = {v: k for k, v in noyau.LOGICIELS.items()}
        preuves = {v: k for k, v in noyau.PREUVES.items()}
        for e, (v_nom, v_log, v_preuve) in zip(self.etapes, self.lignes):
            e.nom = v_nom.get().strip() or "Étape"
            e.logiciel = logiciels[v_log.get()]
            e.preuve = preuves[v_preuve.get()]

    def _personnalise(self):
        self._lire_lignes()
        self.var_modele.set("Personnalisé")
        self._maj_apercu()

    def _dessiner_etapes(self):
        for w in self.cadre_etapes.winfo_children():
            w.destroy()
        self.lignes = []
        for k, e in enumerate(self.etapes):
            carte = ctk.CTkFrame(self.cadre_etapes, fg_color=CHAMP, corner_radius=12)
            carte.pack(fill="x", pady=4, padx=4)
            carte.grid_columnconfigure(4, weight=1)
            ctk.CTkLabel(carte, text=str(k + 1), width=28, height=28, corner_radius=14,
                         fg_color=COULEUR_LOGICIEL[e.logiciel], text_color="#0f1115",
                         font=police(12, True)).grid(row=0, column=0, rowspan=2, padx=10, pady=10)
            v_nom = ctk.StringVar(value=e.nom)
            ent = ctk.CTkEntry(carte, textvariable=v_nom, height=32, width=260, corner_radius=8, fg_color=CARTE,
                               border_width=0, text_color=TEXTE, font=police(13, True))
            ent.grid(row=0, column=1, columnspan=3, sticky="w", pady=(10, 2))
            ent.bind("<KeyRelease>", lambda ev: self._personnalise())
            v_log = ctk.StringVar(value=noyau.LOGICIELS[e.logiciel])
            v_preuve = ctk.StringVar(value=noyau.PREUVES[e.preuve])
            options = dict(height=28, corner_radius=8, fg_color=CARTE, button_color=CARTE,
                           button_hover_color=BORD, text_color=TEXTE, font=police(12),
                           dropdown_fg_color=CARTE, dropdown_text_color=TEXTE,
                           command=lambda v: (self._personnalise(), self._dessiner_etapes()))
            ctk.CTkOptionMenu(carte, variable=v_log, values=list(noyau.LOGICIELS.values()), width=140,
                              **options).grid(row=1, column=1, sticky="w", pady=(2, 10))
            ctk.CTkLabel(carte, text="finie quand :", font=police(11), text_color=PALE).grid(
                row=1, column=2, sticky="w", padx=(10, 4), pady=(2, 10))
            ctk.CTkOptionMenu(carte, variable=v_preuve, values=list(noyau.PREUVES.values()), width=220,
                              **options).grid(row=1, column=3, sticky="w", pady=(2, 10))
            outils = ctk.CTkFrame(carte, fg_color="transparent")
            outils.grid(row=0, column=4, rowspan=2, padx=8, sticky="e")
            for texte, action in (("↑", -1), ("↓", 1)):
                ctk.CTkButton(outils, text=texte, width=28, height=28, corner_radius=8, fg_color="transparent",
                              hover_color=BORD, text_color=DOUX,
                              command=lambda k=k, a=action: self._deplacer(k, a)).pack(side="left")
            ctk.CTkButton(outils, text="✕", width=28, height=28, corner_radius=8, fg_color="transparent",
                          hover_color=melange(CHAMP, ROUGE, .3), text_color=ROUGE,
                          command=lambda k=k: self._supprimer(k)).pack(side="left")
            self.lignes.append((v_nom, v_log, v_preuve))
        self._maj_apercu()

    def _maj_apercu(self):
        self.apercu_flux.configure(text="RAW  →  " + "  →  ".join(e.nom for e in self.etapes) + "  →  ✓ Terminée")

    def _deplacer(self, k, d):
        self._lire_lignes()
        j = k + d
        if 0 <= j < len(self.etapes):
            self.etapes[k], self.etapes[j] = self.etapes[j], self.etapes[k]
            self.var_modele.set("Personnalisé")
            self._dessiner_etapes()

    def _supprimer(self, k):
        self._lire_lignes()
        if len(self.etapes) <= 1:
            return
        del self.etapes[k]
        self.var_modele.set("Personnalisé")
        self._dessiner_etapes()

    def _ajouter(self):
        self._lire_lignes()
        self.etapes.append(noyau.Etape(noyau.nouvel_id_etape(self.etapes), "Nouvelle étape", "aucun", "manuel"))
        self.var_modele.set("Personnalisé")
        self._dessiner_etapes()

    def _valider(self):
        self._lire_lignes()
        r = self.app.reglages
        ancienne_biblio = r["bibliotheque"]
        for cle, v in self.vars.items():
            r[cle] = v.get().strip()
        r["modele_flux"] = self.var_modele.get()
        r["flux"] = [e.en_dict() for e in self.etapes]
        reglages.enregistrer(r)
        self.destroy()
        self.app.parametres_changes(r["bibliotheque"] != ancienne_biblio)


def lancer():
    app = Application()
    app.mainloop()
