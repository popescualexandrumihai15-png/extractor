"""Leagă totul: video → transcriere → subtitrări pe un rând → exporturi și randări."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Callable

from . import exporturi, fonturi, media, randare, segmentare
from .model import Cuvant, Proiect, Subtitrare
from .stil import Stil
from .transcriere import MODEL_IMPLICIT, transcrie


def masuratoare(stil: Stil, info: media.InfoVideo,
                index: fonturi.IndexFonturi | None = None) -> fonturi.Masuratoare:
    index = index or fonturi.index_sistem()
    font = index.gaseste(stil.font, stil.bold, stil.italic)
    contur = 0.0 if stil.cutie else stil.contur_px(info.latime, info.inaltime)
    return fonturi.Masuratoare(font, stil.marime_px(info.latime, info.inaltime), stil.bold,
                               stil.italic, contur)


def construieste_subtitrari(cuvinte: list[Cuvant], stil: Stil, info: media.InfoVideo,
                            index: fonturi.IndexFonturi | None = None) -> list[Subtitrare]:
    masoara = masuratoare(stil, info, index)
    latime_max = info.latime * stil.latime_max / 100
    if stil.cutie:
        latime_max -= 2 * stil.contur_px(info.latime, info.inaltime)
    # Copii ale cuvintelor: segmentarea ajustează timpii subtitrărilor, nu ai cuvintelor.
    return segmentare.imparte_pe_un_rand(
        cuvinte, masoara, latime_max, max_cuvinte=stil.max_cuvinte,
        max_caractere=stil.max_caractere, majuscule=stil.majuscule,
    )


def scara_em(stil: Stil, index: fonturi.IndexFonturi | None = None) -> float:
    index = index or fonturi.index_sistem()
    font = index.gaseste(stil.font, stil.bold, stil.italic)
    return font.scara_ass if font else 0.85


def transcrie_video(cale_video: str | Path, model: str = MODEL_IMPLICIT, vocabular: str = "",
                    progres: Callable[[float], None] | None = None,
                    stare: Callable[[str], None] | None = None) -> Proiect:
    info = media.info_video(cale_video)
    if not info.are_audio:
        raise media.EroareMedia("Videoul nu are sunet, deci nu am ce transcrie.")
    director = Path(tempfile.mkdtemp(prefix="subtitrari_audio_"))
    try:
        if stare:
            stare("Extrag sunetul din video…")
        wav = media.extrage_audio(cale_video, director / "audio.wav")
        cuvinte = transcrie(wav, model=model, vocabular=vocabular, progres=progres, stare=stare)
    finally:
        shutil.rmtree(director, ignore_errors=True)
    return Proiect(video=str(cale_video), cuvinte=cuvinte)


def exporta(proiect: Proiect, stil: Stil, info: media.InfoVideo, director: str | Path,
            formate: list[str], nume: str | None = None, arde: bool = False,
            overlay: bool = False, progres: Callable[[float], None] | None = None,
            stare: Callable[[str], None] | None = None,
            index: fonturi.IndexFonturi | None = None) -> dict[str, Path]:
    """Scrie fișierele cerute. Întoarce formatul → calea fișierului."""
    index = index or fonturi.index_sistem()
    director = Path(director)
    director.mkdir(parents=True, exist_ok=True)
    nume = nume or Path(info.cale).stem
    subtitrari = construieste_subtitrari(proiect.cuvinte, stil, info, index)
    fisiere: dict[str, Path] = {}
    for format_ in formate:
        extensie = exporturi.FORMATE[format_][1]
        cale = director / f"{nume}_subtitrari{extensie}"
        if format_ == "fcpxml":
            cale.write_text(exporturi.fcpxml(subtitrari, stil, info, scara_em(stil, index)),
                            encoding="utf-8")
        else:
            exporturi.scrie(format_, subtitrari, stil, info, cale)
        fisiere[format_] = cale
    if arde:
        if stare:
            stare("Randez videoul cu subtitrări…")
        fisiere["mp4"] = randare.arde_in_video(
            info, subtitrari, stil, director / f"{nume}_cu_subtitrari.mp4", index, progres)
    if overlay:
        if stare:
            stare("Randez stratul transparent cu subtitrări…")
        fisiere["mov"] = randare.overlay_transparent(
            info, subtitrari, stil, director / f"{nume}_subtitrari_overlay.mov", index, progres)
    return fisiere
