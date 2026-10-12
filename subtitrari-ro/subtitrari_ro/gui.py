"""Fereastra aplicației Subtitrări RO (CustomTkinter, temă întunecată)."""

from __future__ import annotations

import os
import queue
import sys
import tempfile
import threading
import tkinter as tk
from dataclasses import fields
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk

import customtkinter as ctk

from . import __version__, exporturi, fonturi, media, motor, tema
from .model import Proiect, Subtitrare
from .stil import PRESETARI, Stil, incarca_setari, presetare, salveaza_setari
from .transcriere import MODEL_IMPLICIT, MODELE

TIPURI_VIDEO = [
    ("Video", "*.mp4 *.mov *.m4v *.mkv *.avi *.webm *.mxf *.mts"),
    ("Audio", "*.wav *.mp3 *.m4a *.aac *.flac"),
    ("Toate fișierele", "*.*"),
]
TIPURI_PROIECT = [("Proiect Subtitrări RO", "*.subtitrari.json"), ("JSON", "*.json")]
TIPURI_FONT = [("Fonturi", "*.ttf *.otf *.ttc"), ("Toate fișierele", "*.*")]
POZITII = {"Jos": "jos", "Mijloc": "mijloc", "Sus": "sus"}
ANIMATII = {"Niciuna": "niciuna", "Pop": "pop", "Fade": "fade"}
ETICHETE_FORMATE = {
    "srt": "SRT", "vtt": "VTT", "ass": "ASS (cu stil)", "fcpxml": "FCPXML (Final Cut)", "json": "JSON",
    "mp4": "MP4 cu subtitrări arse", "mov": "Strat transparent (MOV)",
}
FORMATE_BIFATE_IMPLICIT = {"srt"}
TEXT_MOSTRA = "Bună ziua! ĂÂÎȘȚ ăâîșț 0123"


def _timp_scurt(t: float) -> str:
    minute, secunde = divmod(max(t, 0.0), 60)
    return f"{int(minute)}:{secunde:04.1f}"


def _cheie(dictionar: dict, valoare):
    return next((k for k, v in dictionar.items() if v == valoare), next(iter(dictionar)))


# ── Fereastra de ales fontul ────────────────────────────────────────────────


class AlegereFont(ctk.CTkToplevel):
    """Căutare în fonturile instalate, cu mostră de text în fontul selectat."""

    def __init__(self, parinte, index: fonturi.IndexFonturi, curent: str, la_alegere, la_adaugare):
        super().__init__(parinte)
        self.title("Alege fontul")
        self.geometry("420x520")
        self.configure(fg_color=tema.FUNDAL)
        self.transient(parinte)
        self.index = index
        self.la_alegere = la_alegere
        self.la_adaugare = la_adaugare
        self.cautare = tk.StringVar()
        self.cautare.trace_add("write", lambda *_: self._filtreaza())

        tema.camp(self, self.cautare, "Caută un font…").pack(fill="x", padx=tema.S4, pady=(tema.S4, tema.S2))
        lista_cadru = ctk.CTkFrame(self, fg_color=tema.SUPRAFATA, border_width=1, border_color=tema.MARGINE,
                                   corner_radius=tema.RAZA_MICA)
        lista_cadru.pack(fill="both", expand=True, padx=tema.S4)
        self.lista = tk.Listbox(
            lista_cadru, bg=tema.SUPRAFATA, fg=tema.TEXT, selectbackground=tema.SELECTIE,
            selectforeground="#FFFFFF", highlightthickness=0, borderwidth=0, activestyle="none",
            font=("Segoe UI", 11), exportselection=False,
        )
        derulare = ctk.CTkScrollbar(lista_cadru, command=self.lista.yview)
        self.lista.configure(yscrollcommand=derulare.set)
        derulare.pack(side="right", fill="y", padx=(0, 2), pady=2)
        self.lista.pack(side="left", fill="both", expand=True, padx=(tema.S2, 0), pady=tema.S1)
        self.lista.bind("<<ListboxSelect>>", lambda _e: self._arata_mostra())
        self.lista.bind("<Double-1>", lambda _e: self._alege())

        self.mostra = ctk.CTkLabel(self, text=TEXT_MOSTRA, text_color=tema.TEXT, height=56,
                                   fg_color=tema.SUPRAFATA_2, corner_radius=tema.RAZA_MICA)
        self.mostra.pack(fill="x", padx=tema.S4, pady=tema.S3)
        butoane = ctk.CTkFrame(self, fg_color="transparent")
        butoane.pack(fill="x", padx=tema.S4, pady=(0, tema.S4))
        tema.buton_secundar(butoane, "Adaugă font din fișier…", self._adauga).pack(side="left")
        tema.buton_principal(butoane, "Alege", self._alege, width=110).pack(side="right")

        self._toate = index.nume_familii()
        self._filtreaza()
        if curent in self._toate:
            i = self._toate.index(curent)
            self.lista.selection_set(i)
            self.lista.see(i)
            self._arata_mostra()
        self.after(100, self.grab_set)

    def _filtreaza(self) -> None:
        text = self.cautare.get().casefold()
        self.lista.delete(0, "end")
        for nume in self._toate:
            if text in nume.casefold():
                self.lista.insert("end", nume)

    def _selectat(self) -> str | None:
        selectie = self.lista.curselection()
        return self.lista.get(selectie[0]) if selectie else None

    def _arata_mostra(self) -> None:
        nume = self._selectat()
        if nume:
            try:
                self.mostra.configure(font=ctk.CTkFont(family=nume, size=20))
            except tk.TclError:
                pass

    def _adauga(self) -> None:
        nume = self.la_adaugare()
        if nume:
            self._toate = self.index.nume_familii()
            self.cautare.set("")
            i = self._toate.index(nume)
            self.lista.selection_clear(0, "end")
            self.lista.selection_set(i)
            self.lista.see(i)
            self._arata_mostra()

    def _alege(self) -> None:
        nume = self._selectat()
        if nume:
            self.la_alegere(nume)
        self.destroy()


# ── Fereastra principală ────────────────────────────────────────────────────


class AplicatieSubtitrari:
    def __init__(self, root: ctk.CTk):
        self.root = root
        self.root.title(f"Subtitrări RO {__version__}")
        self.root.configure(fg_color=tema.FUNDAL)
        self.root.minsize(1180, 720)
        if self.root.winfo_screenheight() < 900 and sys.platform.startswith("win"):
            self.root.after(0, lambda: self.root.state("zoomed"))
        else:
            self.root.geometry("1360x860")

        self.setari = incarca_setari()
        self.coada: queue.Queue = queue.Queue()
        self.index = fonturi.IndexFonturi()
        self.fonturi_gata = False
        self.info: media.InfoVideo | None = None
        self.proiect: Proiect | None = None
        self.subtitrari: list[Subtitrare] = []
        self.ocupat = False
        self._fara_reactie = False
        self._programare_stil = None
        self._imagine_prev = None
        self._temp = Path(tempfile.mkdtemp(prefix="subtitrari_gui_"))
        self._cerere_prev = None
        self._eveniment_prev = threading.Event()
        self._lacat_prev = threading.Lock()
        self.server = None

        self.cale_video = tk.StringVar()
        self.nume_video = tk.StringVar(value="Niciun video încărcat")
        self.info_text = tk.StringVar(value="Alege un clip ca să începi.")
        self.model = tk.StringVar()
        self.vocabular = tk.StringVar(value=self.setari.get("vocabular", ""))
        self.presetare = tk.StringVar(value=self.setari.get("presetare", "Clasic"))
        self.folder_export = tk.StringVar(value=self.setari.get("folder_export", ""))
        self.timp_prev = tk.DoubleVar(value=0.0)
        self.timp_text = tk.StringVar(value="0:00.0")
        self.durata_text = tk.StringVar(value="0:00.0")
        self.stare = tk.StringVar(value="Încarcă un video ca să începi.")
        self.conexiune = tk.BooleanVar(value=self.setari.get("conexiune_pluginuri", True))
        self.pozitie_text = tk.StringVar()
        self.animatie_text = tk.StringVar()
        self.formate = {
            f: tk.BooleanVar(value=f in self.setari.get("formate", FORMATE_BIFATE_IMPLICIT))
            for f in ETICHETE_FORMATE
        }
        self.vars_stil: dict[str, tk.Variable] = {}
        self._creeaza_variabile_stil(Stil.din_dict(self.setari.get("stil")))
        self.model.set(_cheie(MODELE, self.setari.get("model", MODEL_IMPLICIT)))

        self._construieste_ui()
        self._actualizeaza_instantaneu()
        self.model.trace_add("write", self._actualizeaza_instantaneu)
        self.vocabular.trace_add("write", self._actualizeaza_instantaneu)
        self.root.protocol("WM_DELETE_WINDOW", self._inchide)
        self.root.after(100, self._proceseaza_coada)
        threading.Thread(target=self._fir_previzualizare, daemon=True).start()
        threading.Thread(target=self._incarca_fonturi, daemon=True).start()
        if self.conexiune.get():
            self.root.after(500, self._comuta_conexiune)

    # ── Variabilele de stil ────────────────────────────────────────────────

    def _creeaza_variabile_stil(self, stil: Stil) -> None:
        for camp in fields(Stil):
            valoare = getattr(stil, camp.name)
            if isinstance(valoare, bool):
                var = tk.BooleanVar(value=valoare)
            elif isinstance(valoare, int):
                var = tk.IntVar(value=valoare)
            elif isinstance(valoare, float):
                var = tk.DoubleVar(value=valoare)
            else:
                var = tk.StringVar(value=valoare)
            var.trace_add("write", lambda *_: self._stil_schimbat())
            self.vars_stil[camp.name] = var

    def stil_curent(self) -> Stil:
        date = {}
        implicit = Stil()
        for nume, var in self.vars_stil.items():
            try:
                valoare = var.get()
            except (tk.TclError, ValueError):
                valoare = getattr(implicit, nume)
            tip = type(getattr(implicit, nume))
            if tip is int:
                valoare = int(round(float(valoare)))
            date[nume] = valoare
        return Stil.din_dict(date)

    def _aplica_stil(self, stil: Stil, cu_font: bool = False) -> None:
        self._fara_reactie = True
        try:
            for nume, var in self.vars_stil.items():
                if nume == "font" and not cu_font:
                    continue  # fontul ales rămâne când schimbi presetarea
                var.set(getattr(stil, nume))
        finally:
            self._fara_reactie = False
        self._actualizeaza_controale_stil()
        self._stil_schimbat()

    # ── Construirea ferestrei ──────────────────────────────────────────────

    def _construieste_ui(self) -> None:
        self._stil_tabel()
        self._bara_sus()
        self._bara_stare()

        corp = ctk.CTkFrame(self.root, fg_color="transparent")
        corp.pack(fill="both", expand=True, padx=tema.S4, pady=tema.S4)
        corp.grid_columnconfigure(0, minsize=300, weight=0)
        corp.grid_columnconfigure(1, weight=1)
        corp.grid_columnconfigure(2, minsize=340, weight=0)
        corp.grid_rowconfigure(0, weight=1)

        stanga = ctk.CTkFrame(corp, fg_color="transparent", width=300)
        stanga.grid(row=0, column=0, sticky="nsew", padx=(0, tema.S4))
        self._card_video(stanga)
        self._card_export(stanga)

        centru = ctk.CTkFrame(corp, fg_color="transparent")
        centru.grid(row=0, column=1, sticky="nsew")
        centru.grid_columnconfigure(0, weight=1)
        centru.grid_rowconfigure(0, weight=3)
        centru.grid_rowconfigure(2, weight=2)
        self._scena(centru)
        self._card_subtitrari(centru)

        dreapta = ctk.CTkFrame(corp, fg_color="transparent", width=340)
        dreapta.grid(row=0, column=2, sticky="nsew", padx=(tema.S4, 0))
        self._card_stil(dreapta)
        self._actualizeaza_controale_stil()

    def _stil_tabel(self) -> None:
        stil = ttk.Style()
        stil.theme_use("clam")
        stil.configure("Treeview", background=tema.SUPRAFATA, fieldbackground=tema.SUPRAFATA,
                       foreground=tema.TEXT, bordercolor=tema.SUPRAFATA, borderwidth=0,
                       rowheight=30, font=("Segoe UI", 11))
        stil.configure("Treeview.Heading", background=tema.SUPRAFATA_2, foreground=tema.TEXT_SECUNDAR,
                       bordercolor=tema.MARGINE, relief="flat", font=("Segoe UI", 10, "bold"), padding=(6, 4))
        stil.map("Treeview", background=[("selected", tema.SELECTIE)], foreground=[("selected", "#FFFFFF")])
        stil.map("Treeview.Heading", background=[("active", tema.SUPRAFATA_HOVER)])
        stil.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

    def _bara_sus(self) -> None:
        bara = ctk.CTkFrame(self.root, fg_color=tema.SUPRAFATA, corner_radius=0, height=56)
        bara.pack(fill="x")
        bara.pack_propagate(False)
        ctk.CTkFrame(self.root, fg_color=tema.MARGINE, corner_radius=0, height=1).pack(fill="x")
        ctk.CTkLabel(bara, text="●", text_color=tema.ACCENT, font=tema.font(20, True)).pack(
            side="left", padx=(tema.S5, tema.S2))
        ctk.CTkLabel(bara, text="Subtitrări RO", text_color=tema.TEXT, font=tema.font(17, True)).pack(side="left")
        tema.eticheta(bara, f"v{__version__}", estompat=True).pack(side="left", padx=(tema.S2, 0), pady=(4, 0))
        tema.eticheta(bara, "Subtitrări în română, pe un singur rând, cu fontul tău", secundar=True).pack(
            side="left", padx=(tema.S6, 0))
        self.punct_conexiune = ctk.CTkLabel(bara, text="●", text_color=tema.TEXT_ESTOMPAT, font=tema.font(14))
        self.punct_conexiune.pack(side="right", padx=(tema.S2, tema.S5))
        tema.comutator(bara, "Conexiune cu DaVinci și Premiere", self.conexiune,
                       command=self._comuta_conexiune).pack(side="right")
        ctk.CTkFrame(bara, fg_color=tema.MARGINE, width=1, height=28).pack(side="right", padx=tema.S5)
        tema.buton_secundar(bara, "Salvează proiectul", self._salveaza_proiect, width=140).pack(
            side="right", padx=(tema.S2, 0))
        tema.buton_secundar(bara, "Deschide proiect", self._deschide_proiect, width=130).pack(side="right")

    def _bara_stare(self) -> None:
        bara = ctk.CTkFrame(self.root, fg_color=tema.SUPRAFATA, corner_radius=0, height=32)
        bara.pack(fill="x", side="bottom")
        bara.pack_propagate(False)
        ctk.CTkFrame(self.root, fg_color=tema.MARGINE, corner_radius=0, height=1).pack(fill="x", side="bottom")
        ctk.CTkLabel(bara, textvariable=self.stare, text_color=tema.TEXT_SECUNDAR, font=tema.font(12),
                     anchor="w").pack(side="left", fill="x", expand=True, padx=tema.S5)
        self.progres = ctk.CTkProgressBar(bara, width=240, height=6, progress_color=tema.ACCENT,
                                          fg_color=tema.MARGINE)
        self.progres.set(0)
        self.progres.pack(side="right", padx=tema.S5)

    def _card_video(self, parinte) -> None:
        cadru, c = tema.card(parinte, "Video", "1")
        cadru.pack(fill="x")
        tema.buton_secundar(c, "📂  Alege un video", self._alege_video, height=40).pack(fill="x")
        tema.eticheta(c, textvariable=self.nume_video, bold=True, anchor="w", wraplength=260,
                      justify="left").pack(fill="x", pady=(tema.S2, 0))
        tema.eticheta(c, textvariable=self.info_text, estompat=True, anchor="w").pack(fill="x")

        tema.eticheta(c, "Model de transcriere", secundar=True, anchor="w").pack(fill="x", pady=(tema.S2, 2))
        tema.meniu(c, list(MODELE), self.model).pack(fill="x")
        tema.eticheta(c, "Nume și termeni din clip", secundar=True, anchor="w").pack(fill="x", pady=(tema.S2, 2))
        tema.camp(c, self.vocabular, "Ember, Cluj-Napoca, After Effects").pack(fill="x")
        self.buton_generare = tema.buton_principal(c, "🎙  Generează subtitrările", self._genereaza)
        self.buton_generare.pack(fill="x", pady=(tema.S3, 0))

    def _card_export(self, parinte) -> None:
        cadru, c = tema.card(parinte, "Export", "3")
        cadru.pack(fill="x", pady=(tema.S4, 0))
        grila = ctk.CTkFrame(c, fg_color="transparent")
        grila.pack(fill="x")
        grila.grid_columnconfigure((0, 1), weight=1)
        for i, format_ in enumerate(("srt", "vtt", "ass", "json", "fcpxml")):
            tema.bifa(grila, ETICHETE_FORMATE[format_], self.formate[format_]).grid(
                row=i // 2, column=i % 2, sticky="w", pady=2)
        tema.bifa(grila, ETICHETE_FORMATE["mp4"], self.formate["mp4"]).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(tema.S2, 2))
        tema.bifa(grila, ETICHETE_FORMATE["mov"], self.formate["mov"]).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=2)

        rand = ctk.CTkFrame(c, fg_color="transparent")
        rand.pack(fill="x", pady=(tema.S3, 0))
        tema.buton_secundar(rand, "…", self._alege_folder, width=36).pack(side="right", padx=(tema.S2, 0))
        tema.camp(rand, self.folder_export, "Folder: lângă video").pack(side="left", fill="x", expand=True)
        self.buton_export = tema.buton_principal(c, "📤  Exportă", self._exporta)
        self.buton_export.pack(fill="x", pady=(tema.S3, 0))

    def _scena(self, parinte) -> None:
        scena = ctk.CTkFrame(parinte, fg_color=tema.SCENA, border_width=1, border_color=tema.MARGINE,
                             corner_radius=tema.RAZA)
        scena.grid(row=0, column=0, sticky="nsew")
        self.panza = tk.Canvas(scena, bg=tema.SCENA, highlightthickness=0, width=640, height=360)
        self.panza.pack(fill="both", expand=True, padx=2, pady=2)
        self.panza.bind("<Configure>", lambda _e: self._la_redimensionare())

        transport = ctk.CTkFrame(parinte, fg_color="transparent")
        transport.grid(row=1, column=0, sticky="ew", pady=tema.S3)
        ctk.CTkLabel(transport, textvariable=self.timp_text, text_color=tema.TEXT, font=tema.font(12, True),
                     width=56).pack(side="left")
        self.cursor_timp = tema.glisor(transport, self.timp_prev, 0.0, 1.0, 1000, comanda=self._timp_mutat)
        self.cursor_timp.pack(side="left", fill="x", expand=True, padx=tema.S3)
        self.cursor_timp.bind("<ButtonRelease-1>", lambda _e: self._cere_previzualizare())
        ctk.CTkLabel(transport, textvariable=self.durata_text, text_color=tema.TEXT_ESTOMPAT,
                     font=tema.font(12), width=56).pack(side="left")

    def _card_subtitrari(self, parinte) -> None:
        cadru = ctk.CTkFrame(parinte, fg_color=tema.SUPRAFATA, border_width=1, border_color=tema.MARGINE,
                             corner_radius=tema.RAZA)
        cadru.grid(row=2, column=0, sticky="nsew")
        antet = ctk.CTkFrame(cadru, fg_color="transparent")
        antet.pack(fill="x", padx=tema.S4, pady=(tema.S3, tema.S2))
        ctk.CTkLabel(antet, text="Subtitrări", text_color=tema.TEXT, font=tema.font(14, True)).pack(side="left")
        self.numar_subtitrari = ctk.CTkLabel(antet, text="0", text_color=tema.TEXT_SECUNDAR,
                                             fg_color=tema.SUPRAFATA_2, corner_radius=9, height=20, width=32,
                                             font=tema.font(11, True))
        self.numar_subtitrari.pack(side="left", padx=tema.S2)
        tema.eticheta(antet, "Dublu-clic pe text ca să-l corectezi", estompat=True).pack(side="right")

        zona = ctk.CTkFrame(cadru, fg_color="transparent")
        zona.pack(fill="both", expand=True, padx=tema.S2, pady=(0, tema.S2))
        self.tabel = ttk.Treeview(zona, columns=("nr", "start", "sfarsit", "text"), show="headings",
                                  height=5, selectmode="browse")
        for coloana, titlu, latime, intindere in (
            ("nr", "#", 44, False), ("start", "START", 80, False),
            ("sfarsit", "SFÂRȘIT", 80, False), ("text", "TEXT", 520, True),
        ):
            self.tabel.heading(coloana, text=titlu, anchor="w")
            self.tabel.column(coloana, width=latime, stretch=intindere, anchor="w")
        self.tabel.tag_configure("alternat", background=tema.RAND_ALTERNAT)
        derulare = ctk.CTkScrollbar(zona, command=self.tabel.yview)
        self.tabel.configure(yscrollcommand=derulare.set)
        derulare.pack(side="right", fill="y")
        self.tabel.pack(side="left", fill="both", expand=True)
        self.tabel.bind("<<TreeviewSelect>>", lambda _e: self._rand_selectat())
        self.tabel.bind("<Double-1>", self._editeaza_rand)
        self.lista_goala = tema.eticheta(zona, "Subtitrările apar aici după „Generează subtitrările”.",
                                         estompat=True, fg_color=tema.SUPRAFATA)
        self.lista_goala.place(relx=0.5, rely=0.55, anchor="center")

    def _card_stil(self, parinte) -> None:
        cadru, c = tema.card(parinte, "Stil", "2")
        cadru.pack(fill="both", expand=True)
        v = self.vars_stil

        tema.eticheta(c, "Presetări", secundar=True, anchor="w").pack(fill="x", pady=(0, 2))
        grila = ctk.CTkFrame(c, fg_color="transparent")
        grila.pack(fill="x")
        grila.grid_columnconfigure((0, 1), weight=1)
        self.butoane_presetari: dict[str, ctk.CTkButton] = {}
        for i, nume in enumerate(PRESETARI):
            buton = tema.buton_secundar(grila, nume, lambda n=nume: self._alege_presetare(n), height=30)
            stanga = i % 2 == 0
            buton.grid(row=i // 2, column=i % 2, sticky="ew", pady=3,
                       padx=(0, 3) if stanga else (3, 0))
            self.butoane_presetari[nume] = buton

        tema.eticheta(c, "Font", secundar=True, anchor="w").pack(fill="x", pady=(tema.S3, 2))
        self.buton_font = tema.buton_secundar(c, "Încarc fonturile…", self._deschide_alegere_font, anchor="w")
        self.buton_font.pack(fill="x")
        self.mostra_font = ctk.CTkLabel(c, text=TEXT_MOSTRA, text_color=tema.TEXT, anchor="w", height=30)
        self.mostra_font.pack(fill="x", pady=(tema.S1, 0))

        file = ctk.CTkTabview(c, fg_color=tema.SUPRAFATA_2, border_width=1, border_color=tema.MARGINE,
                              segmented_button_fg_color=tema.SUPRAFATA_2,
                              segmented_button_selected_color=tema.ACCENT,
                              segmented_button_selected_hover_color=tema.ACCENT_HOVER,
                              segmented_button_unselected_color=tema.SUPRAFATA_2,
                              segmented_button_unselected_hover_color=tema.SUPRAFATA_HOVER,
                              text_color=tema.TEXT, corner_radius=tema.RAZA_MICA, height=360)
        file.pack(fill="both", expand=True, pady=(tema.S2, 0))
        self.file_stil = file

        f = file.add("Text")
        self._rand_glisor(f, "Mărime", "marime", 16, 200, 92, lambda x: f"{int(x)} px")
        bife = ctk.CTkFrame(f, fg_color="transparent")
        bife.pack(fill="x", pady=(tema.S3, 0))
        tema.bifa(bife, "Bold", v["bold"]).pack(side="left", padx=(0, tema.S3))
        tema.bifa(bife, "Italic", v["italic"]).pack(side="left", padx=(0, tema.S3))
        tema.bifa(bife, "MAJUSCULE", v["majuscule"]).pack(side="left")
        self._rand_culoare(f, "Culoare text", "culoare_text")
        rand = self._rand_culoare(f, None, "culoare_evidentiere")
        tema.comutator(rand, "Evidențiază cuvântul rostit", v["evidentiere"]).pack(side="left")
        tema.bifa(f, "ş ţ cu sedilă (pentru fonturi vechi)", v["sedila"]).pack(fill="x", pady=(tema.S3, 0))

        f = file.add("Contur")
        self._rand_culoare(f, "Contur", "culoare_contur")
        self._rand_glisor(f, "Grosime contur", "grosime_contur", 0, 20, 40, lambda x: f"{x:.1f}")
        self._rand_culoare(f, "Umbră", "culoare_umbra")
        self._rand_glisor(f, "Distanța umbrei", "umbra", 0, 20, 40, lambda x: f"{x:.1f}")
        self._rand_glisor(f, "Opacitatea umbrei", "opacitate_umbra", 0, 100, 20, lambda x: f"{int(x)} %")
        rand = self._rand_culoare(f, None, "culoare_cutie")
        tema.comutator(rand, "Cutie în spatele textului", v["cutie"]).pack(side="left")
        self._rand_glisor(f, "Opacitatea cutiei", "opacitate_cutie", 0, 100, 20, lambda x: f"{int(x)} %")

        f = file.add("Poziție")
        tema.eticheta(f, "Poziție", secundar=True, anchor="w").pack(fill="x", pady=(tema.S1, 2))
        tema.segmente(f, list(POZITII), self.pozitie_text,
                      lambda t: v["pozitie"].set(POZITII[t])).pack(fill="x")
        self._rand_glisor(f, "Distanța de la margine", "margine", 0, 45, 45, lambda x: f"{int(x)} %")
        self._rand_glisor(f, "Lățimea maximă a rândului", "latime_max", 40, 100, 30, lambda x: f"{int(x)} %")
        tema.eticheta(f, "Animație", secundar=True, anchor="w").pack(fill="x", pady=(tema.S3, 2))
        tema.segmente(f, list(ANIMATII), self.animatie_text,
                      lambda t: v["animatie"].set(ANIMATII[t])).pack(fill="x")
        self._rand_glisor(f, "Cuvinte pe rând", "max_cuvinte", 0, 10, 10,
                          lambda x: "cât încape" if int(x) == 0 else f"max. {int(x)}")
        self._rand_glisor(f, "Caractere pe rând", "max_caractere", 0, 80, 40,
                          lambda x: "fără limită" if int(x) == 0 else f"max. {int(x)}")

    # ── Controale mici ─────────────────────────────────────────────────────

    def _rand_glisor(self, parinte, titlu: str, camp: str, minim, maxim, pasi, format_) -> None:
        var = self.vars_stil[camp]
        rand = ctk.CTkFrame(parinte, fg_color="transparent")
        rand.pack(fill="x", pady=(tema.S2, 0))
        tema.eticheta(rand, titlu, secundar=True, anchor="w").pack(side="left")
        valoare = tema.eticheta(rand, "", anchor="e")
        valoare.pack(side="right")
        tema.glisor(parinte, var, minim, maxim, pasi).pack(fill="x", pady=(2, 0))

        def actualizeaza(*_):
            try:
                valoare.configure(text=format_(float(var.get())))
            except (tk.TclError, ValueError):
                pass

        var.trace_add("write", actualizeaza)
        actualizeaza()

    def _rand_culoare(self, parinte, titlu: str | None, camp: str) -> ctk.CTkFrame:
        var = self.vars_stil[camp]
        rand = ctk.CTkFrame(parinte, fg_color="transparent")
        rand.pack(fill="x", pady=(tema.S3, 0))
        if titlu:
            tema.eticheta(rand, titlu, secundar=True, anchor="w").pack(side="left")
        buton = ctk.CTkButton(rand, text="", width=40, height=24, corner_radius=tema.RAZA_MICA,
                              fg_color=var.get(), hover_color=var.get(), border_width=1,
                              border_color=tema.MARGINE_HOVER)
        buton.pack(side="right")

        def alege():
            rezultat = colorchooser.askcolor(color=var.get(), title="Alege culoarea", parent=self.root)
            if rezultat and rezultat[1]:
                var.set(rezultat[1].upper())

        def actualizeaza(*_):
            try:
                buton.configure(fg_color=var.get(), hover_color=var.get())
            except (tk.TclError, ValueError):
                pass

        buton.configure(command=alege)
        var.trace_add("write", actualizeaza)
        return rand

    def _actualizeaza_controale_stil(self) -> None:
        self.pozitie_text.set(_cheie(POZITII, self.vars_stil["pozitie"].get()))
        self.animatie_text.set(_cheie(ANIMATII, self.vars_stil["animatie"].get()))
        for nume, buton in getattr(self, "butoane_presetari", {}).items():
            activ = nume == self.presetare.get()
            buton.configure(fg_color=tema.ACCENT_ESTOMPAT if activ else tema.SUPRAFATA_2,
                            border_color=tema.ACCENT if activ else tema.MARGINE)
        self._actualizeaza_font_afisat()

    def _actualizeaza_font_afisat(self) -> None:
        if not hasattr(self, "buton_font"):
            return
        familie = self.vars_stil["font"].get()
        if self.fonturi_gata:
            self.buton_font.configure(text=f"{familie}   ▾")
        try:
            self.mostra_font.configure(font=ctk.CTkFont(
                family=familie, size=18, weight="bold" if self.vars_stil["bold"].get() else "normal"))
        except (tk.TclError, ValueError):
            pass

    def _alege_presetare(self, nume: str) -> None:
        self.presetare.set(nume)
        self._aplica_stil(presetare(nume))

    # ── Fonturi ────────────────────────────────────────────────────────────

    def _incarca_fonturi(self) -> None:
        index = fonturi.index_sistem()
        for cale in self.setari.get("fonturi_adaugate", []):
            if Path(cale).is_file():
                index.adauga_fisier(cale)
        self.coada.put(("fonturi", index))

    def _fonturi_incarcate(self, index: fonturi.IndexFonturi) -> None:
        self.index = index
        self.fonturi_gata = True
        if not index.gaseste(self.vars_stil["font"].get()):
            self.vars_stil["font"].set(fonturi.font_implicit(index))
        self._font_ales(self.vars_stil["font"].get())

    def _deschide_alegere_font(self) -> None:
        if not self.fonturi_gata:
            self.stare.set("Încă încarc lista de fonturi. Încearcă din nou peste o secundă.")
            return
        AlegereFont(self.root, self.index, self.vars_stil["font"].get(), self._font_ales, self._adauga_font)

    def _font_ales(self, familie: str) -> None:
        info = self.index.gaseste(familie)
        if info is None:
            return
        self.vars_stil["font"].set(info.familie)
        self._actualizeaza_font_afisat()
        if not fonturi.are_caractere(info, "șțȘȚ") and not self.vars_stil["sedila"].get():
            self.stare.set(f"Fontul „{info.familie}” nu are literele ș și ț cu virgulă. "
                           "Bifează „ş ţ cu sedilă” (fila Text) sau alege alt font.")

    def _adauga_font(self) -> str | None:
        cale = filedialog.askopenfilename(title="Alege fișierul fontului", filetypes=TIPURI_FONT)
        if not cale:
            return None
        familii = self.index.adauga_fisier(cale)
        if not familii:
            messagebox.showerror("Eroare", "Nu am putut citi fontul. Alege un fișier .ttf, .otf sau .ttc.")
            return None
        adaugate = self.setari.setdefault("fonturi_adaugate", [])
        if cale not in adaugate:
            adaugate.append(cale)
        self.stare.set(f"Am adăugat fontul „{familii[0]}”.")
        return familii[0]

    # ── Video și transcriere ───────────────────────────────────────────────

    def _alege_video(self) -> None:
        cale = filedialog.askopenfilename(title="Alege videoul", filetypes=TIPURI_VIDEO)
        if cale:
            self._incarca_video(cale)

    def _incarca_video(self, cale: str) -> bool:
        try:
            self.info = media.info_video(cale)
        except media.EroareMedia as e:
            messagebox.showerror("Eroare", f"Nu am putut deschide videoul.\n\n{e}")
            return False
        self.cale_video.set(cale)
        self.nume_video.set(Path(cale).name)
        self.info_text.set(self.info.descriere())
        if not self.folder_export.get():
            self.folder_export.set(str(Path(cale).parent))
        self.cursor_timp.configure(to=max(self.info.durata, 0.1))
        self.durata_text.set(_timp_scurt(self.info.durata))
        self.timp_prev.set(min(1.0, self.info.durata / 2))
        self._timp_mutat()
        self.stare.set("Video încărcat. Apasă „Generează subtitrările”.")
        self._cere_previzualizare()
        return True

    def _genereaza(self) -> None:
        if self.ocupat:
            return
        cale = self.cale_video.get().strip()
        if not cale:
            messagebox.showwarning("Atenție", "Încarcă mai întâi un video.")
            return
        model = MODELE.get(self.model.get(), MODEL_IMPLICIT)
        vocabular = self.vocabular.get()
        self._ocupat(True)

        def lucru():
            try:
                proiect = motor.transcrie_video(
                    cale, model=model, vocabular=vocabular,
                    progres=lambda p: self.coada.put(("progres", p)),
                    stare=lambda s: self.coada.put(("stare", s)),
                )
                self.coada.put(("transcriere", proiect))
            except Exception as e:  # afișăm orice eroare, nu închidem aplicația
                self.coada.put(("eroare", ("Transcrierea a eșuat.", e)))

        threading.Thread(target=lucru, daemon=True).start()

    def _transcriere_gata(self, proiect: Proiect) -> None:
        self._ocupat(False)
        if not proiect.cuvinte:
            self.stare.set("Nu am găsit vorbire în video.")
            messagebox.showwarning("Atenție", "Nu am găsit vorbire în video. Verifică dacă are sunet cu voce.")
            return
        self.proiect = proiect
        self._reconstruieste()
        if self.subtitrari:
            primul = self.subtitrari[0]
            self.timp_prev.set((primul.start + primul.end) / 2)
            self._timp_mutat()
        self._cere_previzualizare()
        self.stare.set("Subtitrările sunt gata. Verifică textul în listă, alege stilul, apoi exportă.")

    # ── Subtitrări și listă ────────────────────────────────────────────────

    def _stil_schimbat(self) -> None:
        if self._fara_reactie:
            return
        if self._programare_stil is not None:
            self.root.after_cancel(self._programare_stil)
        self._programare_stil = self.root.after(300, self._dupa_schimbare_stil)

    def _dupa_schimbare_stil(self) -> None:
        self._programare_stil = None
        self._actualizeaza_controale_stil()
        self._actualizeaza_instantaneu()
        self._reconstruieste()
        self._cere_previzualizare()

    def _reconstruieste(self) -> None:
        if self.proiect is None or self.info is None:
            return
        selectat = self.tabel.selection()
        stil = self.stil_curent()
        self.subtitrari = motor.construieste_subtitrari(self.proiect.cuvinte, stil, self.info, self.index)
        self.tabel.delete(*self.tabel.get_children())
        for i, s in enumerate(self.subtitrari):
            self.tabel.insert("", "end", iid=str(i), tags=("alternat",) if i % 2 else (), values=(
                i + 1, _timp_scurt(s.start), _timp_scurt(s.end), exporturi.pregateste_text(s.text, stil)))
        if selectat and self.tabel.exists(selectat[0]):
            self.tabel.selection_set(selectat[0])
        self.numar_subtitrari.configure(text=str(len(self.subtitrari)))
        if self.subtitrari:
            self.lista_goala.place_forget()
        else:
            self.lista_goala.place(relx=0.5, rely=0.55, anchor="center")

    def _rand_selectat(self) -> None:
        selectat = self.tabel.selection()
        if not selectat:
            return
        s = self.subtitrari[int(selectat[0])]
        self.timp_prev.set((s.start + s.end) / 2)
        self._timp_mutat()
        self._cere_previzualizare()

    def _editeaza_rand(self, eveniment) -> None:
        rand = self.tabel.identify_row(eveniment.y)
        if not rand or self.proiect is None:
            return
        x, y, latime, inaltime = self.tabel.bbox(rand, "text")
        subtitrare = self.subtitrari[int(rand)]
        valoare = tk.StringVar(value=subtitrare.text)
        intrare = tk.Entry(self.tabel, textvariable=valoare, font=("Segoe UI", 11), relief="flat",
                           bg=tema.SUPRAFATA_2, fg=tema.TEXT, insertbackground=tema.TEXT,
                           highlightthickness=1, highlightcolor=tema.ACCENT, highlightbackground=tema.ACCENT)
        intrare.place(x=x, y=y, width=latime, height=inaltime)
        intrare.focus_set()
        intrare.select_range(0, "end")

        def salveaza(_e=None):
            text = valoare.get().strip()
            intrare.destroy()
            if text != subtitrare.text:
                self.proiect.editeaza(subtitrare, text)
                self._reconstruieste()
                self._cere_previzualizare()
                self.stare.set("Am salvat corectura.")

        intrare.bind("<Return>", salveaza)
        intrare.bind("<FocusOut>", salveaza)
        intrare.bind("<Escape>", lambda _e: intrare.destroy())

    # ── Previzualizare ─────────────────────────────────────────────────────

    def _timp_mutat(self, *_):
        self.timp_text.set(_timp_scurt(self.timp_prev.get()))

    def _la_redimensionare(self) -> None:
        if self.info is None:
            self._deseneaza_gol()
        else:
            self._cere_previzualizare()

    def _deseneaza_gol(self) -> None:
        self.panza.delete("all")
        latime, inaltime = self.panza.winfo_width(), self.panza.winfo_height()
        self.panza.create_text(latime // 2, inaltime // 2 - 18, text="▶", fill=tema.MARGINE_HOVER,
                               font=("Segoe UI", 34))
        self.panza.create_text(latime // 2, inaltime // 2 + 26, text="Încarcă un video ca să vezi previzualizarea.",
                               fill=tema.TEXT_ESTOMPAT, font=("Segoe UI", 12))

    def _cere_previzualizare(self) -> None:
        if self.info is None:
            return
        latime_panza = max(self.panza.winfo_width(), 200)
        inaltime_panza = max(self.panza.winfo_height(), 120)
        scara = min(latime_panza / self.info.latime, inaltime_panza / self.info.inaltime)
        latime = max(2, int(self.info.latime * scara) // 2 * 2)
        with self._lacat_prev:
            self._cerere_prev = (self.info, list(self.subtitrari), self.stil_curent(),
                                 self.timp_prev.get(), latime)
        self._eveniment_prev.set()

    def _fir_previzualizare(self) -> None:
        from . import randare

        contor = 0
        while True:
            self._eveniment_prev.wait()
            self._eveniment_prev.clear()
            with self._lacat_prev:
                cerere, self._cerere_prev = self._cerere_prev, None
            if cerere is None:
                continue
            info, subtitrari, stil, timp, latime = cerere
            contor += 1
            iesire = self._temp / f"prev_{contor % 3}.png"
            try:
                randare.previzualizare(info, subtitrari, stil, timp, iesire, latime,
                                       self.index if self.fonturi_gata else None)
                self.coada.put(("previzualizare", str(iesire)))
            except Exception as e:
                self.coada.put(("stare", f"Previzualizarea a eșuat: {str(e).splitlines()[-1]}"))

    def _arata_previzualizare(self, cale: str) -> None:
        try:
            self._imagine_prev = tk.PhotoImage(file=cale)
        except tk.TclError:
            return
        self.panza.delete("all")
        self.panza.create_image(self.panza.winfo_width() // 2, self.panza.winfo_height() // 2,
                                image=self._imagine_prev, anchor="center")

    # ── Proiect și export ──────────────────────────────────────────────────

    def _alege_folder(self) -> None:
        cale = filedialog.askdirectory(title="Alege folderul pentru export")
        if cale:
            self.folder_export.set(cale)

    def _salveaza_proiect(self) -> None:
        if self.proiect is None:
            messagebox.showwarning("Atenție", "Nu există subtitrări de salvat. Generează-le mai întâi.")
            return
        initial = Path(self.proiect.video).stem + ".subtitrari.json" if self.proiect.video else ""
        cale = filedialog.asksaveasfilename(title="Salvează proiectul", defaultextension=".subtitrari.json",
                                            initialfile=initial, filetypes=TIPURI_PROIECT)
        if not cale:
            return
        self.proiect.stil = self.stil_curent().la_dict()
        self.proiect.salveaza(cale)
        self.stare.set(f"Proiect salvat: {cale}")

    def _deschide_proiect(self) -> None:
        cale = filedialog.askopenfilename(title="Deschide proiectul", filetypes=TIPURI_PROIECT)
        if not cale:
            return
        try:
            proiect = Proiect.incarca(cale)
        except (OSError, ValueError, KeyError, TypeError) as e:
            messagebox.showerror("Eroare", f"Nu am putut citi proiectul.\n\n{e}")
            return
        if proiect.video and Path(proiect.video).is_file():
            self._incarca_video(proiect.video)
        else:
            messagebox.showwarning("Atenție", "Nu găsesc videoul proiectului. Încarcă-l din nou cu „Alege un video”.")
        if proiect.stil:
            self._aplica_stil(Stil.din_dict(proiect.stil), cu_font=True)
        self.proiect = proiect
        self._reconstruieste()
        self._cere_previzualizare()
        self.stare.set(f"Proiect deschis: {len(self.subtitrari)} subtitrări.")

    def _exporta(self) -> None:
        if self.ocupat:
            return
        if self.proiect is None or self.info is None or not self.subtitrari:
            messagebox.showwarning("Atenție", "Nu există subtitrări de exportat. "
                                              "Apasă mai întâi „Generează subtitrările”.")
            return
        formate = [f for f in exporturi.FORMATE if self.formate[f].get()]
        arde, overlay = self.formate["mp4"].get(), self.formate["mov"].get()
        if not (formate or arde or overlay):
            messagebox.showwarning("Atenție", "Bifează cel puțin un format de export.")
            return
        folder = self.folder_export.get().strip() or str(Path(self.info.cale).parent)
        stil, proiect, info, index = self.stil_curent(), self.proiect, self.info, self.index
        self._ocupat(True)

        def lucru():
            try:
                fisiere = motor.exporta(
                    proiect, stil, info, folder, formate, arde=arde, overlay=overlay,
                    progres=lambda p: self.coada.put(("progres", p)),
                    stare=lambda s: self.coada.put(("stare", s)), index=index)
                self.coada.put(("export", (folder, fisiere)))
            except Exception as e:
                self.coada.put(("eroare", ("Exportul a eșuat.", e)))

        threading.Thread(target=lucru, daemon=True).start()

    def _export_gata(self, folder: str, fisiere: dict) -> None:
        self._ocupat(False)
        lista = "\n".join(f"• {Path(c).name}" for c in fisiere.values())
        messagebox.showinfo("Finalizat", f"Am salvat {len(fisiere)} fișiere în:\n{folder}\n\n{lista}")
        self.stare.set(f"Gata! {len(fisiere)} fișiere salvate în: {folder}")
        self._salveaza_setari()

    # ── Conexiunea cu pluginurile ──────────────────────────────────────────

    def _comuta_conexiune(self) -> None:
        if self.conexiune.get() and self.server is None:
            try:
                from . import server

                self.server = server.porneste_in_fundal(self._stil_pentru_pluginuri)
                self.stare.set(f"Conexiunea cu editoarele e pornită (portul {self.server.server_port}).")
            except OSError as e:
                self.server = None
                self.stare.set(f"Conexiunea cu editoarele nu a pornit: {e}")
        elif not self.conexiune.get() and self.server is not None:
            self.server.shutdown()
            self.server = None
            self.stare.set("Conexiunea cu editoarele e oprită.")
        self.punct_conexiune.configure(text_color=tema.SUCCES if self.server else tema.TEXT_ESTOMPAT)

    def _actualizeaza_instantaneu(self, *_):
        """Copie a setărilor pentru firul serverului (variabilele Tk se citesc doar aici)."""
        self._instantaneu = (self.stil_curent(), MODELE.get(self.model.get(), MODEL_IMPLICIT),
                             self.vocabular.get())

    def _stil_pentru_pluginuri(self) -> tuple[Stil, str, str]:
        """Apelată din firul serverului: stilul, modelul și termenii din fereastră."""
        return self._instantaneu

    # ── Coada de mesaje dintre fire ────────────────────────────────────────

    def _ocupat(self, ocupat: bool) -> None:
        self.ocupat = ocupat
        stare = "disabled" if ocupat else "normal"
        self.buton_generare.configure(state=stare)
        self.buton_export.configure(state=stare)
        self.progres.set(0)

    def _proceseaza_coada(self) -> None:
        try:
            while True:
                tip, date = self.coada.get_nowait()
                if tip == "progres":
                    self.progres.set(date)
                elif tip == "stare":
                    self.stare.set(date)
                elif tip == "transcriere":
                    self._transcriere_gata(date)
                elif tip == "export":
                    self._export_gata(*date)
                elif tip == "previzualizare":
                    self._arata_previzualizare(date)
                elif tip == "fonturi":
                    self._fonturi_incarcate(date)
                elif tip == "eroare":
                    titlu, exceptie = date
                    self._ocupat(False)
                    self.stare.set(titlu)
                    messagebox.showerror("Eroare", f"{titlu}\n\n{exceptie}")
        except queue.Empty:
            pass
        self.root.after(100, self._proceseaza_coada)

    # ── Închidere ──────────────────────────────────────────────────────────

    def _salveaza_setari(self) -> None:
        self.setari.update({
            "stil": self.stil_curent().la_dict(),
            "presetare": self.presetare.get(),
            "model": MODELE.get(self.model.get(), MODEL_IMPLICIT),
            "vocabular": self.vocabular.get(),
            "folder_export": self.folder_export.get(),
            "formate": [f for f, v in self.formate.items() if v.get()],
            "conexiune_pluginuri": self.conexiune.get(),
        })
        try:
            salveaza_setari(self.setari)
        except OSError:
            pass

    def _inchide(self) -> None:
        if self.ocupat and not messagebox.askyesno(
                "Ieșire", "Încă lucrez. Dacă închizi acum, lucrul se pierde. Închizi aplicația?"):
            return
        self._salveaza_setari()
        if self.server is not None:
            self.server.shutdown()
        self.root.destroy()


def porneste(cale_video: str | None = None) -> None:
    tema.aplica()
    root = ctk.CTk()
    aplicatie = AplicatieSubtitrari(root)
    if cale_video and os.path.isfile(cale_video):
        root.after(200, lambda: aplicatie._incarca_video(cale_video))
    root.mainloop()


if __name__ == "__main__":
    porneste(sys.argv[1] if len(sys.argv) > 1 else None)
