"""Scriptul pentru DaVinci Resolve, rulat cap-coadă pe un Resolve simulat și pe serverul real."""

import runpy
import threading
from pathlib import Path

import pytest

from subtitrari_ro import server
from subtitrari_ro.model import imparte_timp
from subtitrari_ro.stil import Stil, director_setari

from conftest import TEXT_EXEMPLU, necesita_ffmpeg
from emulatoare import resolve_fals as rf

SCRIPT = Path(__file__).resolve().parent.parent / "pluginuri" / "davinci_resolve" / "Subtitrari RO.py"
START_TIMELINE = 108000  # 01:00:00:00 la 29,97 fps, ca într-un timeline Resolve obișnuit


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


def _resolve(video: Path) -> rf.Resolve:
    timeline = rf.Timeline("Promo Ember", "29.97", 1920, 1080, START_TIMELINE, 120)
    clip = rf.MediaPoolItem(str(video), fps=29.97)
    timeline.piste["audio"][0] = [
        rf.TimelineItem(clip, START_TIMELINE + 15, 90, 15),  # de la 0,5 s, 3 s, din secunda 0,5
        rf.TimelineItem(clip, START_TIMELINE + 105, 10, 0, activ=False),  # clip dezactivat
        rf.TimelineItem(None, START_TIMELINE + 110, 5, 0),  # generator fără fișier
    ]
    timeline.piste["audio"].append([rf.TimelineItem(clip, START_TIMELINE, 120, 0)])
    timeline.piste_active[("audio", 2)] = False  # pistă dezactivată
    return rf.Resolve(rf.Project(timeline))


def _ruleaza(resolve=None):
    globale = {"resolve": resolve} if resolve is not None else {}
    runpy.run_path(str(SCRIPT), init_globals=globale, run_name="__main__")


@necesita_ffmpeg
def test_davinci_cap_coada(server_pornit, video_orizontal, capsys):
    resolve = _resolve(video_orizontal)
    proiect = resolve.GetProjectManager().GetCurrentProject()
    timeline = proiect.GetCurrentTimeline()

    _ruleaza(resolve)
    iesire = capsys.readouterr().out
    assert "Generarea a eșuat" not in iesire, iesire

    # Ce a trimis scriptul aplicației.
    (cerere,) = server_pornit.cereri
    (clip,) = cerere["clipuri"]  # pista dezactivată, clipul dezactivat și generatorul sunt ignorate
    assert clip["cale"] == str(video_orizontal)
    assert clip["start"] == pytest.approx(15 / 29.97)
    assert clip["durata"] == pytest.approx(90 / 29.97)
    assert clip["intrare"] == pytest.approx(15 / 29.97)
    assert cerere["fps"] == "30000/1001"
    assert (cerere["latime"], cerere["inaltime"]) == (1920, 1080)
    assert cerere["durata"] == pytest.approx(120 / 29.97)
    assert cerere["nume"] == "Promo Ember"
    assert cerere["folder"] == str(video_orizontal.parent / "Subtitrari RO")
    assert cerere["overlay"] is True

    # Ce a pus înapoi în proiect.
    pool = proiect.GetMediaPool()
    (bin_,) = [f for f in pool.GetRootFolder().GetSubFolderList() if f.GetName() == "Subtitrări RO"]
    nume = sorted(Path(c.cale).suffix for c in bin_.GetClipList())
    assert nume == [".mov", ".srt"]
    st1 = timeline.GetItemListInTrack("subtitle", 1)
    assert len(st1) == 1 and st1[0].GetStart() == START_TIMELINE  # la începutul timeline-ului
    assert timeline.GetTrackCount("video") == 2
    (strat,) = timeline.GetItemListInTrack("video", 2)
    assert strat.GetStart() == START_TIMELINE
    assert strat.GetDuration() == 120
    assert strat.GetMediaPoolItem().cale.endswith("_subtitrari_overlay.mov")
    assert "Gata" in iesire


@necesita_ffmpeg
def test_davinci_nu_decaleaza_subtitrarile_existente(server_pornit, video_orizontal, capsys):
    resolve = _resolve(video_orizontal)
    timeline = resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
    _ruleaza(resolve)
    _ruleaza(resolve)  # a doua rulare: ST1 are deja subtitrări
    iesire = capsys.readouterr().out
    assert len(timeline.GetItemListInTrack("subtitle", 1)) == 1
    assert "ST1 are deja subtitrări" in iesire


def test_davinci_fara_aplicatie_pornita(capsys):
    timeline = rf.Timeline("T", "25", 1920, 1080, 90000, 100)
    timeline.piste["audio"][0] = [rf.TimelineItem(rf.MediaPoolItem(__file__), 90000, 50, 0)]
    _ruleaza(rf.Resolve(rf.Project(timeline)))
    assert "Deschide aplicația" in capsys.readouterr().out
    assert not (director_setari() / "port.txt").exists()


def test_davinci_fara_timeline(capsys):
    _ruleaza(rf.Resolve(rf.Project(None)))
    assert "Deschide un timeline" in capsys.readouterr().out


def test_davinci_fara_resolve(capsys):
    _ruleaza(None)
    assert "Nu găsesc DaVinci Resolve" in capsys.readouterr().out
