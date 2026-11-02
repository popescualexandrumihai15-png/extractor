"""Transcriere reală în română, cap-coadă, prin aplicație și prin pluginurile simulate.

Rulează doar când există un model faster-whisper local și espeak-ng (vorbire sintetică):
    SUBTITRARI_MODEL=/cale/catre/faster-whisper-small python -m pytest tests/test_transcriere_reala.py
"""

import json
import os
import shutil
import subprocess
import threading
from pathlib import Path

import pytest

from subtitrari_ro import media, motor, server
from subtitrari_ro.stil import Stil

from conftest import ARE_FFMPEG

MODEL = os.environ.get("SUBTITRARI_MODEL", "")
pytestmark = pytest.mark.skipif(
    not (MODEL and Path(MODEL, "model.bin").is_file() and shutil.which("espeak-ng") and ARE_FFMPEG),
    reason="setează SUBTITRARI_MODEL (folder faster-whisper) și instalează espeak-ng și ffmpeg",
)

TEXT = (
    "Bună! Noi suntem Ember, un studio de animație din Cluj-Napoca. "
    "Facem grafică în mișcare și efecte vizuale. Ai o idee? Scrie-ne!"
)


@pytest.fixture(scope="module")
def clip_vorbit(tmp_path_factory) -> Path:
    director = tmp_path_factory.mktemp("vorbire")
    wav = director / "voce.wav"
    subprocess.run(["espeak-ng", "-v", "ro", "-s", "140", "-w", str(wav), TEXT], check=True)
    clip = director / "clip vorbit.mp4"
    subprocess.run([
        "ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-f", "lavfi",
        "-i", "color=c=0x1b0f3a:s=720x1280:r=25", "-i", str(wav),
        "-af", "adelay=600:all=1,apad=pad_dur=1", "-shortest", "-c:v", "libx264",
        "-pix_fmt", "yuv420p", "-c:a", "aac", str(clip),
    ], check=True)
    return clip


def test_transcriere_reala_in_romana(clip_vorbit):
    proiect = motor.transcrie_video(clip_vorbit, model=MODEL, vocabular="Ember, Cluj-Napoca")
    text = " ".join(c.text for c in proiect.cuvinte)
    for cuvant in ("Ember", "Cluj-Napoca", "animație", "mișcare", "Scrie-ne"):
        assert cuvant in text, text
    assert len(proiect.cuvinte) >= 18, text  # nicio propoziție pierdută
    assert all(a.start <= a.end <= b.start + 1e-6 for a, b in zip(proiect.cuvinte, proiect.cuvinte[1:]))
    info = media.info_video(clip_vorbit)
    # Vorbirea începe la 0,6 s; Whisper marchează uneori primul cuvânt cu ~0,3 s mai devreme.
    assert proiect.cuvinte[0].start >= 0.1 and proiect.cuvinte[-1].end <= info.durata + 0.1


@pytest.fixture
def server_real(font_test):
    srv = server.ServerSubtitrari(0, lambda: (Stil(font=font_test), MODEL, "Ember, Cluj-Napoca"))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()
    srv.server_close()


def test_davinci_cu_transcriere_reala(server_real, clip_vorbit, capsys):
    from test_plugin_davinci import START_TIMELINE, _ruleaza
    from emulatoare import resolve_fals as rf

    timeline = rf.Timeline("Reel", "25", 720, 1280, START_TIMELINE, int(media.info_video(clip_vorbit).durata * 25))
    timeline.piste["audio"][0] = [rf.TimelineItem(rf.MediaPoolItem(str(clip_vorbit), 25.0), START_TIMELINE,
                                                  timeline.durata, 0)]
    resolve = rf.Resolve(rf.Project(timeline))
    _ruleaza(resolve)
    assert "Gata" in capsys.readouterr().out
    srt = next(clip_vorbit.parent.glob("Subtitrari RO/Reel_subtitrari.srt")).read_text(encoding="utf-8-sig")
    assert "Ember" in srt and "Cluj-Napoca" in srt


def test_premiere_cu_transcriere_reala(server_real, clip_vorbit, tmp_path):
    if shutil.which("node") is None:
        pytest.skip("Node.js nu e instalat")
    from test_plugin_premiere import _ruleaza, _secventa

    secventa = _secventa(clip_vorbit)
    durata = media.info_video(clip_vorbit).durata
    secventa["durata"] = durata
    secventa["audio"][0]["clipuri"][0] = {"cale": str(clip_vorbit), "start": 0, "end": durata, "inPoint": 0}
    rezultat = _ruleaza(tmp_path, {"secventa": secventa, "durata": durata,
                                   "cale_proiect": str(tmp_path / "p" / "Clip.prproj")})
    assert rezultat["erori"] == [] and rezultat["clasa"] == "ok", rezultat
    srt = (tmp_path / "p" / "Subtitrari RO" / "Reel 9x16_subtitrari.srt").read_text(encoding="utf-8-sig")
    assert "Ember" in srt and "Cluj-Napoca" in srt
    assert json.dumps(rezultat["subtitrari"]) == '["Reel 9x16_subtitrari.srt"]'
