"""Transcriere automată cu Whisper (faster-whisper), cu timp pentru fiecare cuvânt."""

from __future__ import annotations

import os
import re
import threading
from pathlib import Path
from typing import Callable

from .model import Cuvant, normalizeaza_diacritice
from .stil import director_setari

MODELE = {
    "Rapid (mic, merge și fără placă video)": "small",
    "Echilibrat (recomandat)": "large-v3-turbo",
    "Precis (cel mai lent)": "large-v3",
}
MODEL_IMPLICIT = "large-v3-turbo"

# Whisper imită stilul textului din prompt: o frază românească cu diacritice
# și punctuație îl face să scrie la fel.
PROMPT_RO = (
    "Bună ziua. Aceasta este o transcriere în limba română, cu diacritice corecte "
    "(ă, â, î, ș, ț) și cu punctuație."
)

# Fraze pe care Whisper le „aude” în liniște sau peste muzică.
HALUCINATII = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"^(vă )?mulțum(esc|im)( frumos)? pentru (vizionare|atenție)[.!]*$",
        r"^abonați-vă.*",
        r"^nu uitați să (dați like|vă abonați).*",
        r"^subtitr(are|ări|area).*(realizat|făcut|de către|amara).*",
        r".*amara\.org.*",
        r"^\W*$",
    )
]


def _e_halucinatie(segment) -> bool:
    text = normalizeaza_diacritice(segment.text)
    suspect = segment.no_speech_prob > 0.25 or segment.avg_logprob < -0.6
    if suspect and any(p.match(text) for p in HALUCINATII):
        return True
    return segment.no_speech_prob > 0.85 and segment.avg_logprob < -1.0


_modele: dict[str, object] = {}
_lacat = threading.Lock()


def director_modele() -> Path:
    director = director_setari() / "modele"
    director.mkdir(parents=True, exist_ok=True)
    return director


def _incarca_model(nume: str, forteaza_cpu: bool = False):
    from faster_whisper import WhisperModel

    cheie = f"{nume}|{'cpu' if forteaza_cpu else 'auto'}"
    with _lacat:
        if cheie in _modele:
            return _modele[cheie]
        model = None
        if not forteaza_cpu:
            try:
                import ctranslate2

                if ctranslate2.get_cuda_device_count() > 0:
                    model = WhisperModel(nume, device="cuda", compute_type="float16",
                                         download_root=str(director_modele()))
            except Exception:
                model = None
        if model is None:
            model = WhisperModel(nume, device="cpu", compute_type="int8",
                                 cpu_threads=os.cpu_count() or 4,
                                 download_root=str(director_modele()))
        _modele[cheie] = model
        return model


def transcrie(
    cale_audio: str | Path,
    model: str = MODEL_IMPLICIT,
    limba: str | None = "ro",
    vocabular: str = "",
    progres: Callable[[float], None] | None = None,
    stare: Callable[[str], None] | None = None,
) -> list[Cuvant]:
    """Transcrie un fișier audio. Întoarce cuvintele cu timpul lor.

    vocabular: nume proprii sau termeni (de exemplu nume de branduri), separate
    prin virgulă, ca Whisper să le scrie corect.
    """
    import importlib.util

    if importlib.util.find_spec("faster_whisper") is None:
        raise RuntimeError(
            "Lipsește componenta de transcriere (faster-whisper). "
            "Rulează: pip install -r requirements.txt"
        )

    prompt = PROMPT_RO
    if vocabular.strip():
        prompt += " Termeni folosiți: " + vocabular.strip().rstrip(".") + "."

    def ruleaza(forteaza_cpu: bool) -> list[Cuvant]:
        if stare:
            stare("Încarc modelul de transcriere. Prima dată îl descarc, poate dura câteva minute.")
        whisper = _incarca_model(model, forteaza_cpu)
        if stare:
            stare("Transcriu sunetul…")
        segmente, info = whisper.transcribe(
            str(cale_audio),
            language=limba or None,
            task="transcribe",
            beam_size=5,
            word_timestamps=True,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            condition_on_previous_text=False,
            initial_prompt=prompt,
            hallucination_silence_threshold=2.0,
        )
        durata = max(getattr(info, "duration", 0.0) or 0.0, 0.001)
        cuvinte: list[Cuvant] = []
        for segment in segmente:
            if progres:
                progres(min(1.0, segment.end / durata))
            if _e_halucinatie(segment):
                continue
            for w in segment.words or []:
                text = normalizeaza_diacritice(w.word)
                if not text:
                    continue
                start = max(float(w.start), cuvinte[-1].end if cuvinte else 0.0)
                end = max(float(w.end), start + 0.05)
                cuvinte.append(Cuvant(text, round(start, 3), round(end, 3)))
        if progres:
            progres(1.0)
        return cuvinte

    try:
        return ruleaza(forteaza_cpu=False)
    except RuntimeError as e:
        # Pe Windows, placa video poate exista fără bibliotecile CUDA (cuBLAS/cuDNN).
        if any(s in str(e).lower() for s in ("cuda", "cublas", "cudnn")):
            if stare:
                stare("Placa video nu poate fi folosită. Continui pe procesor (mai lent).")
            return ruleaza(forteaza_cpu=True)
        raise
