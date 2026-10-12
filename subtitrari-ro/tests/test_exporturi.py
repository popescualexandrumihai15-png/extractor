import re
import xml.etree.ElementTree as ET
from fractions import Fraction

from subtitrari_ro import exporturi
from subtitrari_ro.media import InfoVideo
from subtitrari_ro.model import Cuvant, Subtitrare
from subtitrari_ro.stil import Stil


def _subtitrari():
    a = [Cuvant("Bună", 0.5, 0.9), Cuvant("ziua", 0.9, 1.4)]
    b = [Cuvant("Așa", 1.4, 1.8), Cuvant("ține", 1.8, 2.3), Cuvant("minte.", 2.3, 3.0)]
    return [Subtitrare(a, 0.5, 1.4), Subtitrare(b, 1.4, 3.0)]


def _info(fps=Fraction(25), cale="/tmp/clip.mp4", are_video=True):
    return InfoVideo(cale=cale, latime=1920, inaltime=1080, fps=fps, durata=4.0, are_audio=True,
                     are_video=are_video)


def test_srt():
    text = exporturi.srt(_subtitrari(), Stil())
    assert text.startswith("1\n00:00:00,500 --> 00:00:01,400\nBună ziua\n")
    assert "2\n00:00:01,400 --> 00:00:03,000\nAșa ține minte.\n" in text


def test_srt_majuscule_si_sedila():
    text = exporturi.srt(_subtitrari(), Stil(majuscule=True, sedila=True))
    assert "AŞA ŢINE MINTE." in text


def test_vtt():
    text = exporturi.vtt(_subtitrari(), Stil())
    assert text.startswith("WEBVTT\n")
    assert "00:00:00.500 --> 00:00:01.400" in text


def test_ass_un_singur_rand_si_rezolutia_videoului():
    text = exporturi.ass(_subtitrari(), Stil(font="Inter"), 1080, 1920)
    assert "WrapStyle: 2" in text
    assert "PlayResX: 1080" in text and "PlayResY: 1920" in text
    assert "Style: Default,Inter,64," in text
    dialoguri = [l for l in text.splitlines() if l.startswith("Dialogue:")]
    assert len(dialoguri) == 2
    assert dialoguri[0].endswith(",Bună ziua")


def test_ass_evidentiaza_fiecare_cuvant():
    stil = Stil(evidentiere=True, culoare_evidentiere="#FFD400", culoare_text="#FFFFFF")
    dialoguri = [l for l in exporturi.ass(_subtitrari(), stil, 1920, 1080).splitlines()
                 if l.startswith("Dialogue:")]
    assert len(dialoguri) == 5  # câte un eveniment pentru fiecare cuvânt rostit
    assert r"{\1c&H00D4FF&}Bună{\1c&HFFFFFF&} ziua" in dialoguri[0]
    assert r"Bună {\1c&H00D4FF&}ziua{\1c&HFFFFFF&}" in dialoguri[1]


def test_ass_cutie_si_animatii():
    text = exporturi.ass(_subtitrari(), Stil(cutie=True, animatie="fade"), 1920, 1080)
    stil = next(l for l in text.splitlines() if l.startswith("Style:")).split(",")
    assert stil[15] == "3"  # BorderStyle 3 = cutie opacă
    assert r"{\fad(150,120)}" in text
    pop = exporturi.ass(_subtitrari(), Stil(animatie="pop"), 1920, 1080)
    assert r"\t(0,120,\fscx100\fscy100)" in pop


def test_ass_escape_acolade():
    s = [Subtitrare([Cuvant("{x}", 0, 1)], 0, 1)]
    assert "Dialogue: 0,0:00:00.00,0:00:01.00,Default,,0,0,0,,(x)" in exporturi.ass(s, Stil(), 1920, 1080)


def _timpi_fcpxml(xml_text):
    return re.findall(r'(?:offset|duration|start)="([^"]+)"', xml_text)


def test_fcpxml_valid_si_aliniat_la_cadre():
    for fps in (Fraction(25), Fraction(30000, 1001), Fraction(24000, 1001)):
        text = exporturi.fcpxml(_subtitrari(), Stil(), _info(fps))
        radacina = ET.fromstring(text.split("\n", 2)[2])
        assert radacina.tag == "fcpxml"
        titluri = radacina.findall(".//title")
        assert [t.get("name") for t in titluri] == ["Bună ziua", "Așa ține minte."]
        durata_cadru = 1 / fps
        for valoare in _timpi_fcpxml(text):
            secunde = Fraction(valoare.rstrip("s"))
            assert (secunde / durata_cadru).denominator == 1, (fps, valoare)


def test_fcpxml_include_videoul_sau_gap():
    cu_video = exporturi.fcpxml(_subtitrari(), Stil(), _info())
    assert "<asset-clip" in cu_video and 'src="file:///tmp/clip.mp4"' in cu_video
    fara = exporturi.fcpxml(_subtitrari(), Stil(), _info(are_video=False))
    assert "<gap" in fara and "<asset" not in fara


def test_fcpxml_evidentiere_are_stil_separat():
    text = exporturi.fcpxml(_subtitrari(), Stil(evidentiere=True), _info())
    radacina = ET.fromstring(text.split("\n", 2)[2])
    primul = radacina.find(".//title")
    ref_uri = [e.get("ref") for e in primul.find("text")]
    assert len(set(ref_uri)) == 2
    id_uri = [d.get("id") for d in radacina.iter("text-style-def")]
    assert len(id_uri) == len(set(id_uri))  # FCP cere id-uri unice


def test_scrie_srt_cu_bom(tmp_path):
    cale = exporturi.scrie("srt", _subtitrari(), Stil(), _info(), tmp_path / "x.srt")
    assert cale.read_bytes().startswith(b"\xef\xbb\xbf1\n")
