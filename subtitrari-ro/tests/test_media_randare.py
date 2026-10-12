from pathlib import Path

from PIL import Image

from subtitrari_ro import media, motor, randare
from subtitrari_ro.model import Proiect
from subtitrari_ro.stil import presetare

from conftest import necesita_ffmpeg


@necesita_ffmpeg
def test_info_video(video_orizontal, video_vertical):
    info = media.info_video(video_orizontal)
    assert (info.latime, info.inaltime, info.fps_float) == (1280, 720, 25.0)
    assert info.are_audio and 3.9 < info.durata < 4.2
    v = media.info_video(video_vertical)
    assert v.vertical and str(v.fps) == "30000/1001"


@necesita_ffmpeg
def test_extrage_audio(video_orizontal, tmp_path):
    wav = media.extrage_audio(video_orizontal, tmp_path / "a.wav")
    info = media.info_video(wav)
    assert not info.are_video and info.rata_audio == 16000 and info.canale_audio == 1


@necesita_ffmpeg
def test_mixeaza_timeline(video_orizontal, tmp_path):
    clipuri = [media.ClipTimeline(str(video_orizontal), start=0.0, durata=2.0, intrare=1.0),
               media.ClipTimeline(str(video_orizontal), start=3.0, durata=1.5),
               media.ClipTimeline("/nu/exista.mp4", start=0, durata=1)]
    wav = media.mixeaza_timeline(clipuri, 6.0, tmp_path / "mix.wav")
    assert 5.9 < media.info_video(wav).durata < 6.1


@necesita_ffmpeg
def test_previzualizare_si_randari(video_vertical, cuvinte, index_fonturi, font_test, tmp_path):
    info = media.info_video(video_vertical)
    stil = presetare("Social – majuscule")
    stil.font = font_test
    subtitrari = motor.construieste_subtitrari(cuvinte, stil, info, index_fonturi)

    png = randare.previzualizare(info, subtitrari, stil, 1.0, tmp_path / "p.png", 360, index_fonturi)
    assert Image.open(png).size == (360, 640)

    mp4 = randare.arde_in_video(info, subtitrari, stil, tmp_path / "ars.mp4", index_fonturi)
    rezultat = media.info_video(mp4)
    assert rezultat.are_audio and (rezultat.latime, rezultat.inaltime) == (720, 1280)

    mov = randare.overlay_transparent(info, subtitrari, stil, tmp_path / "strat.mov", index_fonturi)
    cadru = tmp_path / "cadru.png"
    media.ruleaza([media.gaseste_program("ffmpeg"), "-y", "-ss", "1.0", "-i", str(mov),
                   "-frames:v", "1", str(cadru)])
    alfa = Image.open(cadru).getchannel("A")
    minim, maxim = alfa.getextrema()
    assert minim == 0 and maxim == 255  # fundal transparent, text opac


@necesita_ffmpeg
def test_exporta_toate_formatele(video_orizontal, cuvinte, index_fonturi, font_test, tmp_path):
    info = media.info_video(video_orizontal)
    stil = presetare("Clasic")
    stil.font = font_test
    fisiere = motor.exporta(Proiect(video=str(video_orizontal), cuvinte=cuvinte), stil, info, tmp_path,
                            ["srt", "vtt", "ass", "fcpxml", "json"], index=index_fonturi)
    assert set(fisiere) == {"srt", "vtt", "ass", "fcpxml", "json"}
    assert all(Path(c).stat().st_size > 0 for c in fisiere.values())
