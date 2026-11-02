"""Panoul Premiere Pro, rulat cap-coadă pe un Premiere simulat (Node) și pe serverul real."""

import json
import os
import shutil
import subprocess
import threading
from pathlib import Path

import pytest

from subtitrari_ro import server
from subtitrari_ro.model import imparte_timp
from subtitrari_ro.stil import Stil

from conftest import TEXT_EXEMPLU, necesita_ffmpeg

RADACINA = Path(__file__).resolve().parent.parent
PANOU = RADACINA / "pluginuri" / "premiere_pro" / "com.subtitrari.ro"
HARNESS = Path(__file__).resolve().parent / "emulatoare" / "premiere_fals.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="Node.js nu e instalat")


@pytest.fixture
def server_pornit(monkeypatch, font_test):
    cereri = []
    original = server.proceseaza_cerere

    def inregistreaza(date, furnizor):
        cereri.append(date)
        return original(date, furnizor)

    monkeypatch.setattr(server, "proceseaza_cerere", inregistreaza)
    monkeypatch.setattr(server, "transcrie", lambda wav, **_: imparte_timp(TEXT_EXEMPLU, 0.6, 3.4))
    srv = server.ServerSubtitrari(0, lambda: (Stil(font=font_test), "small", ""))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    srv.cereri = cereri
    yield srv
    srv.shutdown()
    srv.server_close()


def _secventa(video: Path, piste_video_ocupate: int = 1) -> dict:
    return {
        "nume": "Reel 9x16",
        "fps": 30000 / 1001,
        "durata": 4.0,
        "latime": 1080,
        "inaltime": 1920,
        "video": [[{"cale": str(video), "start": 0, "end": 4}] for _ in range(piste_video_ocupate)] + [[], []],
        "audio": [
            {"muted": False, "clipuri": [
                {"cale": str(video), "start": 0.5, "end": 3.5, "inPoint": 0.5},
                {"cale": str(video), "start": 3.5, "end": 4.0, "inPoint": 0, "disabled": True},
                {"fara_fisier": True, "start": 0, "end": 1, "inPoint": 0},
            ]},
            {"muted": True, "clipuri": [{"cale": str(video), "start": 0, "end": 4, "inPoint": 0}]},
        ],
    }


def _ruleaza(tmp_path: Path, scenariu: dict) -> dict:
    scenariu = {"panou": str(PANOU), "durata": 4.0, **scenariu}
    fisier = tmp_path / "scenariu.json"
    fisier.write_text(json.dumps(scenariu), encoding="utf-8")
    proces = subprocess.run(["node", str(HARNESS), str(fisier)], capture_output=True, text=True,
                            timeout=300, env=dict(os.environ))
    assert proces.returncode == 0, proces.stderr
    return json.loads(proces.stdout)


@necesita_ffmpeg
def test_premiere_cap_coada(server_pornit, video_vertical, tmp_path):
    cale_proiect = tmp_path / "proiect" / "Clip.prproj"
    rezultat = _ruleaza(tmp_path, {"secventa": _secventa(video_vertical), "cale_proiect": str(cale_proiect)})
    assert rezultat["erori"] == []
    assert rezultat["clasa"] == "ok", rezultat["stare"]
    assert rezultat["buton_activ"]

    (cerere,) = server_pornit.cereri
    (clip,) = cerere["clipuri"]  # clipul dezactivat, secvența imbricată și pista mută sunt ignorate
    assert clip == {"cale": str(video_vertical), "start": 0.5, "durata": 3.0, "intrare": 0.5}
    assert (cerere["latime"], cerere["inaltime"]) == (1080, 1920)
    assert float(cerere["fps"]) == pytest.approx(29.97, abs=0.01)
    assert cerere["folder"] == str(cale_proiect.parent / "Subtitrari RO")
    assert cerere["formate"] == ["srt"] and cerere["overlay"] is True

    (bin_,) = rezultat["bin"]
    assert bin_["nume"] == "Subtitrări RO"
    assert sorted(Path(n).suffix for n in bin_["continut"]) == [".mov", ".srt"]
    assert rezultat["subtitrari"] == ["Reel 9x16_subtitrari.srt"]
    apel_subtitrari = [a for a in rezultat["apeluri"] if a[0] == "createCaptionTrack"]
    assert apel_subtitrari == [["createCaptionTrack", "Reel 9x16_subtitrari.srt", 0, 0]]
    # Stratul stilizat merge pe prima pistă video liberă de deasupra clipurilor (V2), la 0.
    assert rezultat["pistele_video"][1] == ["Reel 9x16_subtitrari_overlay.mov"]
    assert ["overwriteClip", "Reel 9x16_subtitrari_overlay.mov", "0"] in rezultat["apeluri"]


@necesita_ffmpeg
def test_premiere_adauga_pista_daca_toate_sunt_ocupate(server_pornit, video_vertical, tmp_path):
    secventa = _secventa(video_vertical, piste_video_ocupate=3)
    secventa["video"] = secventa["video"][:3]  # nicio pistă liberă
    rezultat = _ruleaza(tmp_path, {"secventa": secventa, "bifa_srt": False})
    assert rezultat["erori"] == []
    assert rezultat["clasa"] == "ok", rezultat["stare"]
    assert ["qe.addTracks", 1] in rezultat["apeluri"]
    assert rezultat["pistele_video"][3] == ["Reel 9x16_subtitrari_overlay.mov"]
    assert rezultat["subtitrari"] == []
    assert server_pornit.cereri[0]["formate"] == []


def test_premiere_fara_secventa(server_pornit, tmp_path):
    rezultat = _ruleaza(tmp_path, {"secventa": None})
    assert rezultat["clasa"] == "eroare"
    assert "Deschide o secvență" in rezultat["stare"]
    assert server_pornit.cereri == []


def test_premiere_fara_aplicatie(tmp_path, video_vertical):
    rezultat = _ruleaza(tmp_path, {"secventa": _secventa(video_vertical)})
    assert rezultat["clasa"] == "eroare"
    assert "Aplicația Subtitrări RO nu răspunde" in rezultat["stare"]


def test_premiere_fara_optiuni(tmp_path, video_vertical):
    rezultat = _ruleaza(tmp_path, {"secventa": _secventa(video_vertical), "bifa_srt": False,
                                   "bifa_overlay": False})
    assert rezultat["clasa"] == "eroare"
    assert "Bifează cel puțin o opțiune" in rezultat["stare"]
