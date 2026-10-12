"""Lucrul cu fișierele video/audio prin ffmpeg și ffprobe."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Callable


class EroareMedia(RuntimeError):
    pass


def _directoare_aplicatie() -> list[Path]:
    directoare = []
    if getattr(sys, "frozen", False):  # aplicația .exe făcută cu PyInstaller
        directoare.append(Path(sys.executable).parent)
        if hasattr(sys, "_MEIPASS"):
            directoare.append(Path(sys._MEIPASS))
    directoare.append(Path(__file__).resolve().parent.parent)
    return directoare


def gaseste_program(nume: str) -> str:
    """Caută ffmpeg/ffprobe: variabila SUBTITRARI_FFMPEG_DIR, folderul aplicației, PATH."""
    exe = nume + (".exe" if sys.platform.startswith("win") else "")
    candidati = []
    if os.environ.get("SUBTITRARI_FFMPEG_DIR"):
        candidati.append(Path(os.environ["SUBTITRARI_FFMPEG_DIR"]) / exe)
    for director in _directoare_aplicatie():
        candidati += [director / "ffmpeg" / "bin" / exe, director / "ffmpeg" / exe, director / exe]
    for cale in candidati:
        if cale.is_file():
            return str(cale)
    gasit = shutil.which(nume)
    if gasit:
        return gasit
    raise EroareMedia(
        f"Nu am găsit programul {nume}. "
        "Descarcă ffmpeg de la https://www.gyan.dev/ffmpeg/builds/ (varianta „release essentials”) "
        "și pune folderul „ffmpeg” lângă aplicație, cu fișierele în ffmpeg\\bin."
    )


def _fara_consola() -> dict:
    """Pe Windows, nu deschidem ferestre negre de consolă pentru ffmpeg."""
    if sys.platform.startswith("win"):
        return {"creationflags": 0x08000000}  # CREATE_NO_WINDOW
    return {}


def ruleaza(argumente: list[str], cwd: str | Path | None = None) -> subprocess.CompletedProcess:
    proces = subprocess.run(
        argumente, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
        errors="replace", **_fara_consola(),
    )
    if proces.returncode != 0:
        ultimele = "\n".join(proces.stderr.strip().splitlines()[-6:])
        raise EroareMedia(f"ffmpeg a raportat o eroare:\n{ultimele}")
    return proces


@dataclass
class InfoVideo:
    cale: str
    latime: int
    inaltime: int
    fps: Fraction
    durata: float
    are_audio: bool
    are_video: bool = True
    timecode: str = ""
    rata_audio: int = 48000
    canale_audio: int = 2

    @property
    def fps_float(self) -> float:
        return float(self.fps)

    @property
    def vertical(self) -> bool:
        return self.inaltime > self.latime

    def descriere(self) -> str:
        minute, secunde = divmod(int(round(self.durata)), 60)
        fps = f"{self.fps_float:.3f}".rstrip("0").rstrip(".")
        sunet = "" if self.are_audio else " · fără sunet"
        return f"{self.latime}×{self.inaltime} · {fps} fps · {minute}:{secunde:02d}{sunet}"


def _fractie(text: str | None) -> Fraction | None:
    if not text or text in ("0/0", "0"):
        return None
    try:
        f = Fraction(text)
    except (ValueError, ZeroDivisionError):
        return None
    return f if 1 <= f <= 240 else None


def info_video(cale: str | Path) -> InfoVideo:
    cale = str(cale)
    if not Path(cale).is_file():
        raise EroareMedia(f"Fișierul nu există: {cale}")
    proces = ruleaza([
        gaseste_program("ffprobe"), "-v", "error", "-print_format", "json",
        "-show_streams", "-show_format", cale,
    ])
    date = json.loads(proces.stdout or "{}")
    fluxuri = date.get("streams", [])
    video = next((s for s in fluxuri if s.get("codec_type") == "video"
                  and not s.get("disposition", {}).get("attached_pic")), None)
    audio = next((s for s in fluxuri if s.get("codec_type") == "audio"), None)
    format_ = date.get("format", {})
    durata = float(format_.get("duration") or (video or audio or {}).get("duration") or 0)
    if video is None:
        if audio is None:
            raise EroareMedia("Fișierul nu are nici imagine, nici sunet.")
        return InfoVideo(cale, 1920, 1080, Fraction(25), durata, True, are_video=False,
                         rata_audio=int(audio.get("sample_rate") or 48000),
                         canale_audio=int(audio.get("channels") or 2))
    latime, inaltime = int(video.get("width", 1920)), int(video.get("height", 1080))
    rotatie = 0
    for side in video.get("side_data_list", []) or []:
        if "rotation" in side:
            rotatie = int(side["rotation"])
    rotatie = rotatie or int(video.get("tags", {}).get("rotate", 0) or 0)
    if abs(rotatie) % 180 == 90:
        latime, inaltime = inaltime, latime
    fps = _fractie(video.get("avg_frame_rate")) or _fractie(video.get("r_frame_rate")) or Fraction(25)
    # Rotunjim ratele aproape standard (ex. 29.97002997 → 30000/1001).
    for standard in (Fraction(24000, 1001), Fraction(30000, 1001), Fraction(60000, 1001)):
        if abs(float(fps) - float(standard)) < 0.01:
            fps = standard
    if fps.denominator not in (1, 1001):
        fps = Fraction(round(float(fps)))
    timecode = video.get("tags", {}).get("timecode") or format_.get("tags", {}).get("timecode", "")
    return InfoVideo(
        cale=cale, latime=latime, inaltime=inaltime, fps=fps, durata=durata,
        are_audio=audio is not None, timecode=timecode or "",
        rata_audio=int((audio or {}).get("sample_rate") or 48000),
        canale_audio=int((audio or {}).get("channels") or 2),
    )


def extrage_audio(video: str | Path, wav: str | Path) -> Path:
    """Sunetul ca WAV mono 16 kHz — formatul folosit de Whisper."""
    ruleaza([
        gaseste_program("ffmpeg"), "-nostdin", "-y", "-i", str(video), "-vn",
        "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(wav),
    ])
    return Path(wav)


@dataclass
class ClipTimeline:
    """Un clip audio din timeline-ul unui editor (trimis de pluginuri)."""

    cale: str
    start: float  # unde începe clipul în timeline (secunde)
    durata: float  # cât durează în timeline (secunde)
    intrare: float = 0.0  # de unde începe în fișierul sursă (secunde)


def mixeaza_timeline(clipuri: list[ClipTimeline], durata_totala: float, wav: str | Path) -> Path:
    """Reconstruiește sunetul unui timeline din clipurile lui, ca WAV mono 16 kHz."""
    cache_audio: dict[str, bool] = {}

    def are_audio(cale: str) -> bool:
        if cale not in cache_audio:
            try:
                cache_audio[cale] = info_video(cale).are_audio
            except EroareMedia:
                cache_audio[cale] = False
        return cache_audio[cale]

    clipuri = [c for c in clipuri if c.durata > 0 and Path(c.cale).is_file() and are_audio(c.cale)]
    if not clipuri:
        raise EroareMedia("Timeline-ul nu are clipuri audio cu fișiere găsite pe disc.")
    argumente = [gaseste_program("ffmpeg"), "-nostdin", "-y"]
    filtre = []
    for i, clip in enumerate(clipuri):
        argumente += ["-ss", f"{max(clip.intrare, 0):.3f}", "-t", f"{clip.durata:.3f}", "-i", clip.cale]
        intarziere = max(0, round(clip.start * 1000))
        filtre.append(
            f"[{i}:a]aresample=16000,aformat=channel_layouts=mono,"
            f"adelay=delays={intarziere}:all=1[a{i}]"
        )
    intrari = "".join(f"[a{i}]" for i in range(len(clipuri)))
    if len(clipuri) == 1:
        filtre.append(f"{intrari}apad[iesire]")
    else:
        filtre.append(
            f"{intrari}amix=inputs={len(clipuri)}:duration=longest:dropout_transition=0,"
            f"volume={len(clipuri)},apad[iesire]"
        )
    argumente += [
        "-filter_complex", ";".join(filtre), "-map", "[iesire]",
        "-t", f"{max(durata_totala, 0.1):.3f}", "-ac", "1", "-ar", "16000",
        "-c:a", "pcm_s16le", str(wav),
    ]
    ruleaza(argumente)
    return Path(wav)


def ruleaza_cu_progres(argumente: list[str], durata: float, progres: Callable[[float], None] | None,
                       cwd: str | Path | None = None) -> None:
    """Rulează ffmpeg și raportează progresul (0–1) citind -progress."""
    argumente = argumente[:1] + ["-progress", "pipe:1", "-nostats"] + argumente[1:]
    proces = subprocess.Popen(
        argumente, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        encoding="utf-8", errors="replace", **_fara_consola(),
    )
    erori: list[str] = []

    import threading

    def citeste_erori():
        for linie in proces.stderr:
            erori.append(linie)
            del erori[:-20]

    fir = threading.Thread(target=citeste_erori, daemon=True)
    fir.start()
    for linie in proces.stdout:
        if progres and linie.startswith("out_time_us=") and durata > 0:
            try:
                progres(min(1.0, int(linie.split("=")[1]) / 1e6 / durata))
            except ValueError:
                pass
    proces.wait()
    fir.join(timeout=2)
    if proces.returncode != 0:
        ultimele = "".join(erori[-6:]).strip()
        raise EroareMedia(f"ffmpeg a raportat o eroare:\n{ultimele}")
    if progres:
        progres(1.0)
