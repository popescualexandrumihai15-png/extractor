"""Tema vizuală a aplicației (întunecată, ca în editoarele video), într-un singur loc.

Paleta urmează regula 60-30-10: fundalul ocupă cea mai mare parte, cardurile
sunt cu o treaptă mai deschise, iar accentul portocaliu apare doar pe acțiuni,
pe elementul activ și pe focus. Cardurile se despart prin margini de 1 px.
"""

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

# ── Culori ──────────────────────────────────────────────────────────────────
FUNDAL = "#0F1115"  # L0: fundalul ferestrei
SUPRAFATA = "#171A21"  # L1: carduri, bara de sus, lista
SUPRAFATA_2 = "#1F232C"  # L2: câmpuri, butoane secundare, file
SUPRAFATA_HOVER = "#262B36"
RAND_ALTERNAT = "#1A1E26"  # o treaptă peste L1, pentru rândurile listei
MARGINE = "#2A2F3A"  # margine subtilă de 1 px
MARGINE_HOVER = "#3A4150"
SCENA = "#08090B"  # fundalul previzualizării, ca un monitor de editare

TEXT = "#E8EAED"
TEXT_SECUNDAR = "#A6ADBB"
TEXT_ESTOMPAT = "#6B7280"

ACCENT = "#FF6A2B"  # portocaliu jar: acțiuni, element activ, focus
ACCENT_HOVER = "#FF8148"
ACCENT_ESTOMPAT = "#3D2419"  # fundal pentru elementul selectat
TEXT_PE_ACCENT = "#160B06"  # text închis pe portocaliu, pentru contrast
SELECTIE = "#512E23"

SUCCES = "#34C77B"
PERICOL = "#F05252"

RAZA = 10  # colțuri pentru carduri
RAZA_MICA = 6  # colțuri pentru butoane și câmpuri

# ── Spațiere (bază 4) ───────────────────────────────────────────────────────
S1, S2, S3, S4, S5, S6 = 4, 8, 12, 16, 20, 24


def font(marime: int = 13, bold: bool = False) -> ctk.CTkFont:
    return ctk.CTkFont(size=marime, weight="bold" if bold else "normal")


def aplica() -> None:
    ctk.set_appearance_mode("dark")


# ── Piese folosite peste tot ────────────────────────────────────────────────


def card(parinte, titlu: str | None = None, pas: str | None = None) -> tuple[ctk.CTkFrame, ctk.CTkFrame]:
    """Card L1 cu margine de 1 px. Întoarce (cardul, zona de conținut)."""
    cadru = ctk.CTkFrame(parinte, fg_color=SUPRAFATA, border_width=1, border_color=MARGINE,
                         corner_radius=RAZA)
    if titlu:
        antet = ctk.CTkFrame(cadru, fg_color="transparent")
        antet.pack(fill="x", padx=S4, pady=(S3, S1))
        if pas:
            ctk.CTkLabel(antet, text=pas, width=22, height=22, corner_radius=11, fg_color=ACCENT_ESTOMPAT,
                         text_color=ACCENT, font=font(12, True)).pack(side="left", padx=(0, S2))
        ctk.CTkLabel(antet, text=titlu, text_color=TEXT, font=font(14, True)).pack(side="left")
    continut = ctk.CTkFrame(cadru, fg_color="transparent")
    continut.pack(fill="both", expand=True, padx=S4, pady=(S1, S4))
    return cadru, continut


def buton_principal(parinte, text: str, comanda, **optiuni) -> ctk.CTkButton:
    return ctk.CTkButton(parinte, text=text, command=comanda, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                         text_color=TEXT_PE_ACCENT, text_color_disabled=TEXT_ESTOMPAT,
                         font=font(13, True), height=38, corner_radius=RAZA_MICA, **optiuni)


def buton_secundar(parinte, text: str, comanda, **optiuni) -> ctk.CTkButton:
    optiuni.setdefault("height", 32)
    return ctk.CTkButton(parinte, text=text, command=comanda, fg_color=SUPRAFATA_2,
                         hover_color=SUPRAFATA_HOVER, border_width=1, border_color=MARGINE,
                         text_color=TEXT, font=font(12), corner_radius=RAZA_MICA, **optiuni)


def eticheta(parinte, text: str = "", secundar: bool = False, estompat: bool = False,
             marime: int = 12, bold: bool = False, **optiuni) -> ctk.CTkLabel:
    culoare = TEXT_ESTOMPAT if estompat else TEXT_SECUNDAR if secundar else TEXT
    return ctk.CTkLabel(parinte, text=text, text_color=culoare, font=font(marime, bold), **optiuni)


def camp(parinte, variabila: tk.Variable, indiciu: str = "", **optiuni) -> ctk.CTkEntry:
    return ctk.CTkEntry(parinte, textvariable=variabila, placeholder_text=indiciu or None,
                        fg_color=SUPRAFATA_2, border_color=MARGINE, border_width=1, text_color=TEXT,
                        placeholder_text_color=TEXT_ESTOMPAT, corner_radius=RAZA_MICA, height=32,
                        font=font(12), **optiuni)


def bifa(parinte, text: str, variabila: tk.Variable, **optiuni) -> ctk.CTkCheckBox:
    return ctk.CTkCheckBox(parinte, text=text, variable=variabila, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                           border_color=MARGINE_HOVER, checkmark_color=TEXT_PE_ACCENT, text_color=TEXT,
                           font=font(12), checkbox_width=18, checkbox_height=18, corner_radius=4,
                           border_width=1, **optiuni)


def comutator(parinte, text: str, variabila: tk.Variable, **optiuni) -> ctk.CTkSwitch:
    return ctk.CTkSwitch(parinte, text=text, variable=variabila, progress_color=ACCENT,
                         button_color=TEXT, button_hover_color="#FFFFFF", fg_color=MARGINE_HOVER,
                         text_color=TEXT, font=font(12), **optiuni)


def segmente(parinte, valori: list[str], variabila: tk.Variable, comanda=None) -> ctk.CTkSegmentedButton:
    return ctk.CTkSegmentedButton(parinte, values=valori, variable=variabila, command=comanda,
                                  fg_color=SUPRAFATA_2, selected_color=ACCENT,
                                  selected_hover_color=ACCENT_HOVER, unselected_color=SUPRAFATA_2,
                                  unselected_hover_color=SUPRAFATA_HOVER, text_color=TEXT,
                                  font=font(12), corner_radius=RAZA_MICA, height=30)


def meniu(parinte, valori: list[str], variabila: tk.Variable, comanda=None, **optiuni) -> ctk.CTkOptionMenu:
    return ctk.CTkOptionMenu(parinte, values=valori, variable=variabila, command=comanda,
                             fg_color=SUPRAFATA_2, button_color=SUPRAFATA_2, button_hover_color=SUPRAFATA_HOVER,
                             dropdown_fg_color=SUPRAFATA_2, dropdown_hover_color=SUPRAFATA_HOVER,
                             dropdown_text_color=TEXT, text_color=TEXT, font=font(12),
                             dropdown_font=font(12), corner_radius=RAZA_MICA, height=32, **optiuni)


def glisor(parinte, variabila: tk.Variable, minim: float, maxim: float, pasi: int, comanda=None) -> ctk.CTkSlider:
    return ctk.CTkSlider(parinte, variable=variabila, from_=minim, to=maxim, number_of_steps=pasi,
                         command=comanda, progress_color=ACCENT, button_color=TEXT,
                         button_hover_color="#FFFFFF", fg_color=MARGINE, height=16)
