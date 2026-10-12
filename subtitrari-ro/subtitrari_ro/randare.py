"""Randări cu ffmpeg + libass: previzualizare, video cu subtitrări arse, strat transparent."""

from __future__ import annotations

import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator

from . import exporturi, fonturi
from .media import InfoVideo, gaseste_program, ruleaza, ruleaza_cu_progres
from .model import Subtitrare
from .stil import Stil


@contextmanager
def director_lucru(info: InfoVideo, subtitrari: list[Subtitrare], stil: Stil,
                   index: fonturi.IndexFonturi | None) -> Iterator[Path]:
    """Director temporar cu sub.ass și fonts/ (fișierele fontului ales).

    ffmpeg rulează cu acest director curent, ca filtrul „ass” să primească
    doar căi relative (pe Windows, „C:\\” în filtre cere escape-uri complicate).
    """
    director = Path(tempfile.mkdtemp(prefix="subtitrari_randare_"))
    try:
        (director / "sub.ass").write_text(
            exporturi.ass(subtitrari, stil, info.latime, info.inaltime), encoding="utf-8")
        fonturi_dir = director / "fonts"
        fonturi_dir.mkdir()
        if index is not None:
            fonturi.pregateste_director_fonturi(index, stil.font, fonturi_dir)
        yield director
    finally:
        shutil.rmtree(director, ignore_errors=True)


FILTRU_ASS = "ass=sub.ass:fontsdir=fonts"


def previzualizare(info: InfoVideo, subtitrari: list[Subtitrare], stil: Stil, timp: float,
                   iesire: str | Path, latime: int = 640,
                   index: fonturi.IndexFonturi | None = None) -> Path:
    """Un cadru din video, la momentul „timp”, cu subtitrările desenate ca la export."""
    iesire = Path(iesire).resolve()
    timp = max(0.0, min(timp, max(info.durata - 0.05, 0.0)))
    with director_lucru(info, subtitrari, stil, index) as director:
        if info.are_video:
            argumente = [
                gaseste_program("ffmpeg"), "-nostdin", "-y", "-ss", f"{timp:.3f}", "-copyts",
                "-i", str(Path(info.cale).resolve()),
                "-vf", f"scale={info.latime}:{info.inaltime},setsar=1,{FILTRU_ASS},scale={latime}:-2",
                "-frames:v", "1", str(iesire),
            ]
        else:  # doar audio: fundal gri
            argumente = [
                gaseste_program("ffmpeg"), "-nostdin", "-y", "-f", "lavfi",
                "-i", f"color=c=0x404040:s={info.latime}x{info.inaltime}:d={timp + 1:.3f}",
                "-vf", f"{FILTRU_ASS},scale={latime}:-2", "-ss", f"{timp:.3f}",
                "-frames:v", "1", str(iesire),
            ]
        ruleaza(argumente, cwd=director)
    return iesire


def arde_in_video(info: InfoVideo, subtitrari: list[Subtitrare], stil: Stil, iesire: str | Path,
                  index: fonturi.IndexFonturi | None = None,
                  progres: Callable[[float], None] | None = None) -> Path:
    """Video MP4 (H.264) cu subtitrările desenate în imagine — gata de urcat pe rețele."""
    iesire = Path(iesire).resolve()
    with director_lucru(info, subtitrari, stil, index) as director:
        argumente = [
            gaseste_program("ffmpeg"), "-nostdin", "-y", "-i", str(Path(info.cale).resolve()),
            "-vf", FILTRU_ASS, "-map", "0:v:0", "-map", "0:a:0?",
            "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(iesire),
        ]
        ruleaza_cu_progres(argumente, info.durata, progres, cwd=director)
    return iesire


def overlay_transparent(info: InfoVideo, subtitrari: list[Subtitrare], stil: Stil,
                        iesire: str | Path, index: fonturi.IndexFonturi | None = None,
                        progres: Callable[[float], None] | None = None) -> Path:
    """MOV ProRes 4444 cu canal alfa: doar subtitrările, pe fundal transparent.

    Se pune peste video într-un track deasupra (Premiere, DaVinci, Final Cut).
    """
    iesire = Path(iesire).resolve()
    durata = max(info.durata, subtitrari[-1].end if subtitrari else 1.0)
    fps = f"{info.fps.numerator}/{info.fps.denominator}"
    with director_lucru(info, subtitrari, stil, index) as director:
        argumente = [
            gaseste_program("ffmpeg"), "-nostdin", "-y", "-f", "lavfi",
            # format=rgba trebuie să fie în sursă; altfel ffmpeg pierde transparența.
            "-i", f"color=c=black@0.0:s={info.latime}x{info.inaltime}:r={fps}:d={durata:.3f},format=rgba",
            "-vf", "ass=sub.ass:fontsdir=fonts:alpha=1",
            "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le",
            "-vendor", "apl0", str(iesire),
        ]
        ruleaza_cu_progres(argumente, durata, progres, cwd=director)
    return iesire
