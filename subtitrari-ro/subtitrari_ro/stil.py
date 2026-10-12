"""Stilul subtitrărilor (font, culori, contur, poziție) și presetările."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path

POZITII = ("jos", "mijloc", "sus")
ANIMATII = ("niciuna", "pop", "fade")


@dataclass
class Stil:
    nume: str = "Clasic"
    font: str = "Arial"
    marime: int = 64  # pixeli pentru un video de 1080 (latura mică); se scalează
    bold: bool = True
    italic: bool = False
    majuscule: bool = False
    culoare_text: str = "#FFFFFF"
    culoare_contur: str = "#000000"
    grosime_contur: float = 3.0
    umbra: float = 1.0
    culoare_umbra: str = "#000000"
    opacitate_umbra: int = 60  # procente
    cutie: bool = False  # fundal opac în spatele textului
    culoare_cutie: str = "#000000"
    opacitate_cutie: int = 65
    pozitie: str = "jos"
    margine: int = 8  # procente din înălțimea video (pentru jos/sus)
    latime_max: int = 86  # procente din lățimea video folosite de un rând
    max_cuvinte: int = 0  # 0 = cât încape pe rând
    max_caractere: int = 42  # rânduri scurte se citesc mai ușor; 0 = fără limită
    evidentiere: bool = False  # colorează cuvântul rostit acum
    culoare_evidentiere: str = "#FFD400"
    animatie: str = "niciuna"
    sedila: bool = False  # ş ţ în loc de ș ț, pentru fonturi vechi

    def scara(self, latime: int, inaltime: int) -> float:
        return min(latime, inaltime) / 1080.0

    def marime_px(self, latime: int, inaltime: int) -> float:
        return self.marime * self.scara(latime, inaltime)

    def contur_px(self, latime: int, inaltime: int) -> float:
        return self.grosime_contur * self.scara(latime, inaltime)

    def la_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def din_dict(cls, date: dict | None) -> "Stil":
        if not date:
            return cls()
        cunoscute = {f.name for f in fields(cls)}
        stil = cls(**{k: v for k, v in date.items() if k in cunoscute})
        if stil.pozitie not in POZITII:
            stil.pozitie = "jos"
        if stil.animatie not in ANIMATII:
            stil.animatie = "niciuna"
        return stil


PRESETARI: dict[str, Stil] = {
    "Clasic": Stil(),
    "Social – majuscule": Stil(
        nume="Social – majuscule", marime=78, majuscule=True, grosime_contur=5.0,
        umbra=2.0, pozitie="jos", margine=22, max_cuvinte=3, evidentiere=True,
        culoare_evidentiere="#FFD400", animatie="pop",
    ),
    "Cutie neagră": Stil(
        nume="Cutie neagră", marime=56, bold=False, cutie=True, grosime_contur=10.0,
        umbra=0.0, opacitate_cutie=70,
    ),
    "Karaoke": Stil(
        nume="Karaoke", marime=70, evidentiere=True, culoare_evidentiere="#00E5FF",
        grosime_contur=4.0, max_cuvinte=5,
    ),
    "Minimal": Stil(
        nume="Minimal", marime=58, bold=False, grosime_contur=0.0, umbra=2.5,
        opacitate_umbra=70,
    ),
}


def presetare(nume: str) -> Stil:
    return replace(PRESETARI.get(nume, PRESETARI["Clasic"]))


# ── Culori ──────────────────────────────────────────────────────────────────


def hex_la_rgb(culoare: str) -> tuple[int, int, int]:
    c = culoare.strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) != 6:
        return (255, 255, 255)
    try:
        return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    except ValueError:
        return (255, 255, 255)


def culoare_ass(culoare: str, opacitate: int = 100) -> str:
    """#RRGGBB + opacitate (%) → &HAABBGGRR (în ASS, AA=00 înseamnă opac)."""
    r, g, b = hex_la_rgb(culoare)
    alfa = round(255 * (1 - max(0, min(100, opacitate)) / 100))
    return f"&H{alfa:02X}{b:02X}{g:02X}{r:02X}"


def culoare_ass_inline(culoare: str) -> str:
    """Culoare pentru etichete \\1c în textul ASS: &HBBGGRR&."""
    r, g, b = hex_la_rgb(culoare)
    return f"&H{b:02X}{g:02X}{r:02X}&"


def culoare_fcp(culoare: str, opacitate: int = 100) -> str:
    """#RRGGBB → "r g b a" cu valori 0–1, cum cere FCPXML."""
    r, g, b = hex_la_rgb(culoare)
    a = max(0, min(100, opacitate)) / 100
    return " ".join(f"{v:.4g}" for v in (r / 255, g / 255, b / 255, a))


# ── Setări salvate (ultimul stil folosit, preluat și de pluginuri) ──────────


def director_setari() -> Path:
    if sys.platform.startswith("win"):
        baza = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        director = baza / "SubtitrariRO"
    elif sys.platform == "darwin":
        director = Path.home() / "Library" / "Application Support" / "SubtitrariRO"
    else:
        director = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "subtitrari-ro"
    director.mkdir(parents=True, exist_ok=True)
    return director


def incarca_setari() -> dict:
    cale = director_setari() / "setari.json"
    try:
        return json.loads(cale.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def salveaza_setari(setari: dict) -> None:
    cale = director_setari() / "setari.json"
    cale.write_text(json.dumps(setari, ensure_ascii=False, indent=1), encoding="utf-8")
