"""Exporturi: SRT, VTT, ASS (cu stil), FCPXML (Final Cut Pro) și JSON."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from .media import InfoVideo
from .model import Subtitrare, la_sedila
from .stil import Stil, culoare_ass, culoare_ass_inline, culoare_fcp


def pregateste_text(text: str, stil: Stil) -> str:
    if stil.majuscule:
        text = text.upper()
    if stil.sedila:
        text = la_sedila(text)
    return text


# ── Evenimente: ce text apare și când (cu cuvântul evidențiat, dacă e cazul) ──


@dataclass
class Eveniment:
    start: float
    end: float
    bucati: list[tuple[str, bool]]  # (cuvânt, este cuvântul rostit acum)
    prima: bool  # primul eveniment al subtitrării (pentru animația de intrare)
    ultima: bool  # ultimul eveniment al subtitrării (pentru animația de ieșire)


def evenimente(subtitrari: list[Subtitrare], stil: Stil) -> list[Eveniment]:
    rezultat: list[Eveniment] = []
    for s in subtitrari:
        cuvinte = [pregateste_text(c.text, stil) for c in s.cuvinte]
        if not cuvinte:
            continue
        if not stil.evidentiere:
            rezultat.append(Eveniment(s.start, s.end, [(" ".join(cuvinte), False)], True, True))
            continue
        limite = [s.start] + [max(c.start, s.start) for c in s.cuvinte[1:]] + [s.end]
        for k in range(1, len(limite)):
            limite[k] = min(max(limite[k], limite[k - 1]), s.end)
        bucati_sub = []
        for k in range(len(cuvinte)):
            if limite[k + 1] - limite[k] >= 0.01:
                bucati = [(w, i == k) for i, w in enumerate(cuvinte)]
                bucati_sub.append(Eveniment(limite[k], limite[k + 1], bucati, False, False))
        if not bucati_sub:
            bucati_sub.append(Eveniment(s.start, s.end, [(w, False) for w in cuvinte], False, False))
        bucati_sub[0].prima = True
        bucati_sub[-1].ultima = True
        rezultat.extend(bucati_sub)
    return rezultat


# ── SRT și VTT ──────────────────────────────────────────────────────────────


def _timp_srt(t: float, separator: str = ",") -> str:
    ms = max(0, round(t * 1000))
    ore, ms = divmod(ms, 3_600_000)
    minute, ms = divmod(ms, 60_000)
    secunde, ms = divmod(ms, 1000)
    return f"{ore:02d}:{minute:02d}:{secunde:02d}{separator}{ms:03d}"


def srt(subtitrari: list[Subtitrare], stil: Stil) -> str:
    blocuri = []
    for i, s in enumerate(subtitrari, 1):
        text = pregateste_text(s.text, stil)
        blocuri.append(f"{i}\n{_timp_srt(s.start)} --> {_timp_srt(s.end)}\n{text}\n")
    return "\n".join(blocuri)


def vtt(subtitrari: list[Subtitrare], stil: Stil) -> str:
    blocuri = ["WEBVTT\n"]
    for s in subtitrari:
        text = pregateste_text(s.text, stil)
        blocuri.append(f"{_timp_srt(s.start, '.')} --> {_timp_srt(s.end, '.')}\n{text}\n")
    return "\n".join(blocuri)


# ── ASS (stil complet, folosit și la randare) ───────────────────────────────


def _timp_ass(t: float) -> str:
    cs = max(0, round(t * 100))
    ore, cs = divmod(cs, 360_000)
    minute, cs = divmod(cs, 6000)
    secunde, cs = divmod(cs, 100)
    return f"{ore}:{minute:02d}:{secunde:02d}.{cs:02d}"


def _escape_ass(text: str) -> str:
    return text.replace("\\", "/").replace("{", "(").replace("}", ")").replace("\n", " ")


ALINIERE_ASS = {"jos": 2, "mijloc": 5, "sus": 8}


def ass(subtitrari: list[Subtitrare], stil: Stil, latime: int, inaltime: int) -> str:
    scara = stil.scara(latime, inaltime)
    marime = round(stil.marime_px(latime, inaltime))
    umbra = round(stil.umbra * scara, 2)
    if stil.cutie:
        stil_bordura = 3
        culoare_bordura = culoare_ass(stil.culoare_cutie, stil.opacitate_cutie)
        contur = round(max(stil.grosime_contur, 1) * scara, 2)  # spațiul din jurul textului
    else:
        stil_bordura = 1
        culoare_bordura = culoare_ass(stil.culoare_contur)
        contur = round(stil.grosime_contur * scara, 2)
    margine_v = round(inaltime * stil.margine / 100)
    margine_lat = round(latime * (100 - stil.latime_max) / 200)
    primara = culoare_ass_inline(stil.culoare_text)
    evidentiata = culoare_ass_inline(stil.culoare_evidentiere)

    antet = "\n".join([
        "[Script Info]",
        "; Generat de Subtitrări RO",
        "ScriptType: v4.00+",
        f"PlayResX: {latime}",
        f"PlayResY: {inaltime}",
        "WrapStyle: 2",  # fără împărțire automată: un singur rând
        "ScaledBorderAndShadow: yes",
        "YCbCr Matrix: TV.709",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        ",".join(str(v) for v in [
            "Style: Default", stil.font.replace(",", " "), marime,
            culoare_ass(stil.culoare_text), culoare_ass(stil.culoare_evidentiere),
            culoare_bordura, culoare_ass(stil.culoare_umbra, stil.opacitate_umbra),
            -1 if stil.bold else 0, -1 if stil.italic else 0, 0, 0, 100, 100, 0, 0,
            stil_bordura, contur, umbra, ALINIERE_ASS.get(stil.pozitie, 2),
            margine_lat, margine_lat, margine_v, 1,
        ]),
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ])

    linii = [antet]
    for ev in evenimente(subtitrari, stil):
        etichete = ""
        if stil.animatie == "pop" and ev.prima:
            etichete = r"{\fscx70\fscy70\t(0,120,\fscx100\fscy100)}"
        elif stil.animatie == "fade":
            intrare = 150 if ev.prima else 0
            iesire = 120 if ev.ultima else 0
            if intrare or iesire:
                etichete = rf"{{\fad({intrare},{iesire})}}"
        parti = []
        for cuvant, activ in ev.bucati:
            cuvant = _escape_ass(cuvant)
            if activ:
                parti.append(rf"{{\1c{evidentiata}}}{cuvant}{{\1c{primara}}}")
            else:
                parti.append(cuvant)
        text = etichete + " ".join(parti)
        linii.append(f"Dialogue: 0,{_timp_ass(ev.start)},{_timp_ass(ev.end)},Default,,0,0,0,,{text}")
    return "\n".join(linii) + "\n"


# ── FCPXML (Final Cut Pro): titluri „Basic Title” cu stilul ales ────────────

UID_BASIC_TITLE = ".../Titles.localized/Bumper:Opener.localized/Basic Title.localized/Basic Title.moti"
CHEIE_POZITIE = "9999/999166631/999166633/1/100/101"


def _tc_la_secunde(tc: str, fps: Fraction) -> float:
    try:
        ore, minute, secunde, cadre = (int(x) for x in tc.replace(";", ":").split(":"))
    except ValueError:
        return 0.0
    rata = round(float(fps))
    return ((ore * 3600 + minute * 60 + secunde) * rata + cadre) / float(fps)


def fcpxml(subtitrari: list[Subtitrare], stil: Stil, info: InfoVideo, scara_em: float = 0.85,
           include_video: bool = True, nume_proiect: str = "Subtitrări RO") -> str:
    fps = info.fps
    durata_cadru = 1 / fps

    def cadre(secunde: float) -> int:
        return max(0, round(secunde * fps))

    def timp(nr_cadre: int) -> str:
        valoare = nr_cadre * durata_cadru
        if valoare == 0:
            return "0s"
        if valoare.denominator == 1:
            return f"{valoare.numerator}s"
        return f"{valoare.numerator}/{valoare.denominator}s"

    include_video = include_video and info.are_video
    if include_video:
        # Clipul video nu poate fi mai lung decât fișierul; titlurile se taie la final.
        total = max(cadre(info.durata), 1)
    else:
        total = max(cadre(info.durata), cadre(subtitrari[-1].end) if subtitrari else 1, 1)
    w, h = info.latime, info.inaltime
    em = stil.marime_px(w, h) * scara_em
    margine = h * stil.margine / 100
    if stil.pozitie == "jos":
        y = -(h / 2 - margine - em * 0.6)
    elif stil.pozitie == "sus":
        y = h / 2 - margine - em * 0.6
    else:
        y = 0.0

    radacina = ET.Element("fcpxml", version="1.9")
    resurse = ET.SubElement(radacina, "resources")
    ET.SubElement(resurse, "format", id="r1", frameDuration=timp(1), width=str(w), height=str(h))
    ET.SubElement(resurse, "effect", id="r2", name="Basic Title", uid=UID_BASIC_TITLE)
    start_tc = cadre(_tc_la_secunde(info.timecode, fps)) if info.timecode else 0

    librarie = ET.SubElement(radacina, "library")
    eveniment = ET.SubElement(librarie, "event", name=nume_proiect)
    proiect = ET.SubElement(eveniment, "project", name=nume_proiect)
    secventa = ET.SubElement(proiect, "sequence", format="r1", duration=timp(total), tcStart="0s",
                             tcFormat="NDF", audioLayout="stereo", audioRate="48k")
    spine = ET.SubElement(secventa, "spine")

    if include_video:
        asset = ET.SubElement(
            resurse, "asset", id="r3", name=Path(info.cale).stem, start=timp(start_tc),
            duration=timp(total), hasVideo="1", format="r1",
        )
        if info.are_audio:
            asset.set("hasAudio", "1")
            asset.set("audioSources", "1")
            asset.set("audioChannels", str(info.canale_audio))
            asset.set("audioRate", str(info.rata_audio))
        ET.SubElement(asset, "media-rep", kind="original-media", src=Path(info.cale).resolve().as_uri())
        parinte = ET.SubElement(spine, "asset-clip", ref="r3", offset="0s", name=Path(info.cale).stem,
                                start=timp(start_tc), duration=timp(total), tcFormat="NDF")
        baza = start_tc
    else:
        parinte = ET.SubElement(spine, "gap", name="Gap", offset="0s", start="0s", duration=timp(total))
        baza = 0

    def stil_text(id_stil: str, culoare: str) -> ET.Element:
        definitie = ET.Element("text-style-def", id=id_stil)
        fata = "Bold Italic" if stil.bold and stil.italic else "Bold" if stil.bold else \
            "Italic" if stil.italic else "Regular"
        atribute = {
            "font": stil.font, "fontSize": f"{em:.0f}", "fontFace": fata,
            "fontColor": culoare_fcp(culoare), "alignment": "center",
        }
        if stil.bold:
            atribute["bold"] = "1"
        if stil.italic:
            atribute["italic"] = "1"
        if stil.grosime_contur > 0 and not stil.cutie:
            atribute["strokeColor"] = culoare_fcp(stil.culoare_contur)
            atribute["strokeWidth"] = f"{stil.contur_px(w, h):.1f}"
        if stil.umbra > 0:
            atribute["shadowColor"] = culoare_fcp(stil.culoare_umbra, stil.opacitate_umbra)
            atribute["shadowOffset"] = f"{stil.umbra * stil.scara(w, h):.1f} 315"
            atribute["shadowBlurRadius"] = "1"
        ET.SubElement(definitie, "text-style", **atribute)
        return definitie

    id_stil = 0
    sfarsit_anterior = 0
    for ev in evenimente(subtitrari, stil):
        a = max(cadre(ev.start), sfarsit_anterior)
        b = min(max(cadre(ev.end), a + 1), total)
        if b <= a:
            continue
        sfarsit_anterior = b
        text_complet = " ".join(c for c, _ in ev.bucati)
        titlu = ET.SubElement(parinte, "title", ref="r2", lane="1", offset=timp(baza + a),
                              name=text_complet[:40], start="0s", duration=timp(b - a))
        ET.SubElement(titlu, "param", name="Position", key=CHEIE_POZITIE, value=f"0 {y:.0f}")
        element_text = ET.SubElement(titlu, "text")
        id_stil += 1
        id_normal = f"ts{id_stil}"
        definitii = [stil_text(id_normal, stil.culoare_text)]
        id_activ = None
        if any(activ for _, activ in ev.bucati):
            id_stil += 1
            id_activ = f"ts{id_stil}"
            definitii.append(stil_text(id_activ, stil.culoare_evidentiere))
        for i, (cuvant, activ) in enumerate(ev.bucati):
            bucata = ET.SubElement(element_text, "text-style", ref=id_activ if activ else id_normal)
            bucata.text = cuvant + (" " if i < len(ev.bucati) - 1 else "")
        titlu.extend(definitii)

    ET.indent(radacina, space="  ")
    corp = ET.tostring(radacina, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE fcpxml>\n' + corp + "\n"


# ── JSON (pentru pluginuri și alte unelte) ──────────────────────────────────


def json_subtitrari(subtitrari: list[Subtitrare], stil: Stil) -> str:
    return json.dumps({
        "subtitrari": [
            {"start": s.start, "end": s.end, "text": pregateste_text(s.text, stil),
             "cuvinte": [{"text": pregateste_text(c.text, stil), "start": c.start, "end": c.end}
                         for c in s.cuvinte]}
            for s in subtitrari
        ],
    }, ensure_ascii=False, indent=1)


FORMATE = {
    "srt": ("SRT – DaVinci, Premiere, CapCut, Final Cut", ".srt"),
    "vtt": ("VTT – web, YouTube", ".vtt"),
    "ass": ("ASS – cu stil complet (Aegisub, VLC)", ".ass"),
    "fcpxml": ("FCPXML – Final Cut Pro, titluri cu fontul ales", ".fcpxml"),
    "json": ("JSON – date pentru alte unelte", ".json"),
}


def scrie(format_: str, subtitrari: list[Subtitrare], stil: Stil, info: InfoVideo,
          cale: str | Path) -> Path:
    cale = Path(cale)
    if format_ == "srt":
        # Cu BOM: Premiere și CapCut pe Windows citesc corect diacriticele.
        cale.write_text(srt(subtitrari, stil), encoding="utf-8-sig")
    elif format_ == "vtt":
        cale.write_text(vtt(subtitrari, stil), encoding="utf-8")
    elif format_ == "ass":
        cale.write_text(ass(subtitrari, stil, info.latime, info.inaltime), encoding="utf-8-sig")
    elif format_ == "fcpxml":
        cale.write_text(fcpxml(subtitrari, stil, info), encoding="utf-8")
    elif format_ == "json":
        cale.write_text(json_subtitrari(subtitrari, stil), encoding="utf-8")
    else:
        raise ValueError(f"Format necunoscut: {format_}")
    return cale
