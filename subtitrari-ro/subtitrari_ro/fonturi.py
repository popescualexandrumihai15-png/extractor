"""Fonturi: găsește fonturile instalate, citește numele lor și măsoară textul.

Citim direct fișierele .ttf/.otf/.ttc (tabelele name, head, hhea, OS/2, cmap),
fără dependențe externe. Așa știm:
  * ce familii de fonturi există (lista din interfață),
  * ce fișier aparține fiecărei familii (îl dăm lui libass la randare,
    ca fontul să apară sigur, chiar dacă e instalat doar pentru utilizator),
  * cât de lat iese un rând (pentru subtitrări pe un singur rând),
  * dacă fontul are glifele românești ș/ț cu virgulă.
"""

from __future__ import annotations

import os
import shutil
import struct
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

EXTENSII_FONT = {".ttf", ".otf", ".ttc", ".otc"}


@dataclass
class InfoFont:
    cale: str
    index: int  # poziția în colecție (.ttc); 0 pentru fișiere simple
    familie: str  # nameID 1 — numele pe care îl folosește libass
    stil: str  # nameID 2 — "Regular", "Bold", "Italic"...
    nume_complet: str
    bold: bool
    italic: bool
    unitati_em: int = 1000
    win_ascent: int = 0
    win_descent: int = 0
    hhea_ascent: int = 0
    hhea_descent: int = 0

    @property
    def scara_ass(self) -> float:
        """Raportul dintre mărimea em și mărimea din ASS (Fontsize).

        libass (ca VSFilter) face ca Fontsize să fie înălțimea
        usWinAscent + usWinDescent, nu înălțimea em. Deci em = Fontsize * scara.
        """
        inaltime = self.win_ascent + self.win_descent
        if inaltime <= 0:
            inaltime = self.hhea_ascent - self.hhea_descent
        if inaltime <= 0:
            return 0.85
        return self.unitati_em / inaltime


# ── Citirea fișierelor de font ──────────────────────────────────────────────


def _tabele(date: bytes, offset: int) -> dict[str, tuple[int, int]]:
    num = struct.unpack_from(">H", date, offset + 4)[0]
    tabele = {}
    for i in range(num):
        tag, _suma, off, lung = struct.unpack_from(">4sIII", date, offset + 12 + 16 * i)
        tabele[tag.decode("latin-1")] = (off, lung)
    return tabele


def _decodeaza_nume(platforma: int, codare: int, brut: bytes) -> str | None:
    try:
        if platforma in (0, 3):
            return brut.decode("utf-16-be")
        if platforma == 1 and codare == 0:
            return brut.decode("mac_roman")
    except UnicodeDecodeError:
        return None
    return None


def _nume(date: bytes, tabele: dict) -> dict[int, str]:
    if "name" not in tabele:
        return {}
    off, _ = tabele["name"]
    _fmt, numar, start_siruri = struct.unpack_from(">HHH", date, off)
    candidati: dict[int, list[tuple[int, str]]] = {}
    for i in range(numar):
        plat, cod, limba, id_nume, lung, poz = struct.unpack_from(">HHHHHH", date, off + 6 + 12 * i)
        if id_nume not in (1, 2, 4, 16, 17):
            continue
        brut = date[off + start_siruri + poz: off + start_siruri + poz + lung]
        text = _decodeaza_nume(plat, cod, brut)
        if not text:
            continue
        # Preferăm Windows/engleză, apoi Windows în altă limbă, apoi Mac, apoi Unicode.
        if plat == 3 and limba == 0x409:
            prioritate = 0
        elif plat == 3:
            prioritate = 1
        elif plat == 1 and limba == 0:
            prioritate = 2
        else:
            prioritate = 3
        candidati.setdefault(id_nume, []).append((prioritate, text.strip("\x00 ")))
    return {k: sorted(v)[0][1] for k, v in candidati.items()}


def _citeste_un_font(date: bytes, offset: int, cale: str, index: int) -> InfoFont | None:
    tabele = _tabele(date, offset)
    nume = _nume(date, tabele)
    familie = nume.get(1) or nume.get(16)
    if not familie:
        return None
    stil = nume.get(2, "Regular")
    unitati_em = 1000
    mac_style = 0
    if "head" in tabele:
        off, _ = tabele["head"]
        unitati_em = struct.unpack_from(">H", date, off + 18)[0] or 1000
        mac_style = struct.unpack_from(">H", date, off + 44)[0]
    hhea_asc = hhea_desc = 0
    if "hhea" in tabele:
        off, _ = tabele["hhea"]
        hhea_asc, hhea_desc = struct.unpack_from(">hh", date, off + 4)
    win_asc = win_desc = 0
    fs_selection = 0
    if "OS/2" in tabele:
        off, lung = tabele["OS/2"]
        if lung >= 78:
            fs_selection = struct.unpack_from(">H", date, off + 62)[0]
            win_asc, win_desc = struct.unpack_from(">HH", date, off + 74)
    bold = bool(fs_selection & 0x20) or bool(mac_style & 0x01)
    italic = bool(fs_selection & 0x01) or bool(mac_style & 0x02)
    return InfoFont(
        cale=cale, index=index, familie=familie, stil=stil,
        nume_complet=nume.get(4, f"{familie} {stil}"), bold=bold, italic=italic,
        unitati_em=unitati_em, win_ascent=win_asc, win_descent=win_desc,
        hhea_ascent=hhea_asc, hhea_descent=hhea_desc,
    )


def citeste_font(cale: str | os.PathLike) -> list[InfoFont]:
    """Întoarce informațiile despre toate fonturile dintr-un fișier."""
    cale = str(cale)
    try:
        with open(cale, "rb") as f:
            date = f.read()
    except OSError:
        return []
    try:
        if date[:4] == b"ttcf":
            numar = struct.unpack_from(">I", date, 8)[0]
            rezultat = []
            for i in range(numar):
                offset = struct.unpack_from(">I", date, 12 + 4 * i)[0]
                info = _citeste_un_font(date, offset, cale, i)
                if info:
                    rezultat.append(info)
            return rezultat
        if date[:4] in (b"\x00\x01\x00\x00", b"OTTO", b"true"):
            info = _citeste_un_font(date, 0, cale, 0)
            return [info] if info else []
    except struct.error:
        return []
    return []


def are_caractere(info: InfoFont, caractere: str) -> bool:
    """Verifică în tabela cmap dacă fontul are glife pentru toate caracterele."""
    try:
        with open(info.cale, "rb") as f:
            date = f.read()
        offset = 0
        if date[:4] == b"ttcf":
            offset = struct.unpack_from(">I", date, 12 + 4 * info.index)[0]
        tabele = _tabele(date, offset)
        if "cmap" not in tabele:
            return False
        baza, _ = tabele["cmap"]
        num = struct.unpack_from(">H", date, baza + 2)[0]
        subtabele = {}
        for i in range(num):
            plat, cod, off = struct.unpack_from(">HHI", date, baza + 4 + 8 * i)
            subtabele[(plat, cod)] = baza + off
        for cheie in ((3, 10), (0, 4), (0, 6), (3, 1), (0, 3), (0, 1), (0, 0)):
            if cheie in subtabele:
                poz = subtabele[cheie]
                return all(_glifa(date, poz, ord(c)) for c in caractere)
    except (OSError, struct.error):
        return False
    return False


def _glifa(date: bytes, poz: int, cod: int) -> int:
    fmt = struct.unpack_from(">H", date, poz)[0]
    if fmt == 4:
        if cod > 0xFFFF:
            return 0
        seg2 = struct.unpack_from(">H", date, poz + 6)[0]
        n = seg2 // 2
        sfarsit = poz + 14
        inceput = sfarsit + seg2 + 2
        delta = inceput + seg2
        range_off = delta + seg2
        for i in range(n):
            capat = struct.unpack_from(">H", date, sfarsit + 2 * i)[0]
            if capat < cod:
                continue
            start = struct.unpack_from(">H", date, inceput + 2 * i)[0]
            if start > cod:
                return 0
            d = struct.unpack_from(">h", date, delta + 2 * i)[0]
            ro = struct.unpack_from(">H", date, range_off + 2 * i)[0]
            if ro == 0:
                return (cod + d) & 0xFFFF
            adresa = range_off + 2 * i + ro + 2 * (cod - start)
            g = struct.unpack_from(">H", date, adresa)[0]
            return (g + d) & 0xFFFF if g else 0
        return 0
    if fmt == 12:
        n = struct.unpack_from(">I", date, poz + 12)[0]
        for i in range(n):
            start, stop, g0 = struct.unpack_from(">III", date, poz + 16 + 12 * i)
            if start <= cod <= stop:
                return g0 + (cod - start)
        return 0
    return 0


# ── Indexul fonturilor instalate ────────────────────────────────────────────


def directoare_fonturi_sistem() -> list[Path]:
    acasa = Path.home()
    if sys.platform.startswith("win"):
        windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
        local = Path(os.environ.get("LOCALAPPDATA", acasa / "AppData" / "Local"))
        return [windir / "Fonts", local / "Microsoft" / "Windows" / "Fonts"]
    if sys.platform == "darwin":
        return [
            Path("/System/Library/Fonts"),
            Path("/System/Library/Fonts/Supplemental"),
            Path("/Library/Fonts"),
            acasa / "Library" / "Fonts",
        ]
    return [
        Path("/usr/share/fonts"),
        Path("/usr/local/share/fonts"),
        acasa / ".local" / "share" / "fonts",
        acasa / ".fonts",
    ]


@dataclass
class IndexFonturi:
    """Familie → variante (bold, italic) → InfoFont."""

    familii: dict[str, dict[tuple[bool, bool], InfoFont]] = field(default_factory=dict)

    def adauga_fisier(self, cale: str | os.PathLike) -> list[str]:
        familii_noi = []
        for info in citeste_font(cale):
            if info.familie.startswith(("CustomTkinter", ".")):
                continue  # fonturi interne ale unor programe, nu pentru text
            variante = self.familii.setdefault(info.familie, {})
            cheie = (info.bold, info.italic)
            # Prima variantă găsită rămâne; fișierele utilizatorului se adaugă după sistem.
            variante.setdefault(cheie, info)
            if info.familie not in familii_noi:
                familii_noi.append(info.familie)
        return familii_noi

    def adauga_director(self, director: Path) -> None:
        if not director.is_dir():
            return
        for radacina, _dirs, fisiere in os.walk(director):
            for nume in fisiere:
                if Path(nume).suffix.lower() in EXTENSII_FONT:
                    self.adauga_fisier(Path(radacina) / nume)

    def nume_familii(self) -> list[str]:
        return sorted(self.familii, key=str.casefold)

    def gaseste(self, familie: str, bold: bool = False, italic: bool = False) -> InfoFont | None:
        """Varianta cea mai apropiată de stilul cerut."""
        variante = self.familii.get(familie)
        if not variante:
            for nume, v in self.familii.items():
                if nume.casefold() == familie.casefold():
                    variante = v
                    break
        if not variante:
            return None
        for cheie in ((bold, italic), (bold, False), (False, italic), (False, False)):
            if cheie in variante:
                return variante[cheie]
        return next(iter(variante.values()))

    def fisiere_familie(self, familie: str) -> list[str]:
        variante = self.familii.get(familie, {})
        return sorted({info.cale for info in variante.values()})


_index_global: IndexFonturi | None = None


def index_sistem(reconstruieste: bool = False) -> IndexFonturi:
    """Scanează o singură dată fonturile instalate (durează ~1 s pe Windows)."""
    global _index_global
    if _index_global is None or reconstruieste:
        index = IndexFonturi()
        for director in directoare_fonturi_sistem():
            index.adauga_director(director)
        _index_global = index
    return _index_global


FONTURI_DE_REZERVA = ["Arial", "Helvetica", "Liberation Sans", "DejaVu Sans", "Noto Sans"]


def font_implicit(index: IndexFonturi) -> str:
    for nume in FONTURI_DE_REZERVA:
        if index.gaseste(nume):
            return nume
    familii = index.nume_familii()
    return familii[0] if familii else "Arial"


def pregateste_director_fonturi(index: IndexFonturi, familie: str, destinatie: Path) -> Path:
    """Copiază fișierele familiei alese într-un director dat lui libass (fontsdir)."""
    destinatie.mkdir(parents=True, exist_ok=True)
    for cale in index.fisiere_familie(familie):
        tinta = destinatie / Path(cale).name
        if not tinta.exists():
            try:
                shutil.copy2(cale, tinta)
            except OSError:
                pass
    return destinatie


# ── Măsurarea textului ──────────────────────────────────────────────────────

_LATIMI_ESTIMATE = {
    **{c: 0.28 for c in "iIl.,;:'!|ìíjfrt()[]"},
    **{c: 0.85 for c in "mwMW"},
    " ": 0.28,
}


def estimeaza_latime(text: str, marime_ass: float, bold: bool = False) -> float:
    """Estimare aproximativă când nu avem fișierul fontului (pentru siguranță, mai lată)."""
    total = 0.0
    for c in text:
        if c in _LATIMI_ESTIMATE:
            total += _LATIMI_ESTIMATE[c]
        elif c.isupper():
            total += 0.68
        elif c.isdigit():
            total += 0.56
        else:
            total += 0.52
    return total * marime_ass * 0.88 * (1.07 if bold else 1.0)


class Masuratoare:
    """Măsoară lățimea în pixeli a unui rând, exact cum îl va desena libass."""

    def __init__(self, info: InfoFont | None, marime_ass: float, bold: bool,
                 italic: bool = False, contur: float = 0.0):
        self.info = info
        self.marime_ass = marime_ass
        self.bold = bold
        self.contur = contur
        # Bold „sintetic” dacă cerem bold, dar fontul găsit nu e bold.
        self.factor = 1.06 if (bold and info is not None and not info.bold) else 1.0
        self._font = None
        if info is not None:
            try:
                from PIL import ImageFont

                em = max(1, round(marime_ass * info.scara_ass))
                self._font = ImageFont.truetype(info.cale, size=em, index=info.index)
            except Exception:  # Pillow lipsă sau font nesuportat
                self._font = None

    @property
    def exacta(self) -> bool:
        return self._font is not None

    def __call__(self, text: str) -> float:
        if self._font is not None:
            latime = self._font.getlength(text) * self.factor
        else:
            latime = estimeaza_latime(text, self.marime_ass, self.bold)
        return latime + 2 * self.contur


def director_temporar(prefix: str = "subtitrari_") -> Path:
    return Path(tempfile.mkdtemp(prefix=prefix))
