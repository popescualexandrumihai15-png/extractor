import http.client
import json
import threading

import pytest

from subtitrari_ro import server
from subtitrari_ro.model import imparte_timp
from subtitrari_ro.stil import Stil, director_setari

from conftest import TEXT_EXEMPLU, necesita_ffmpeg


@pytest.fixture
def server_pornit(monkeypatch, font_test):
    monkeypatch.setattr(server, "transcrie", lambda wav, **_: imparte_timp(TEXT_EXEMPLU, 0.3, 3.8))
    srv = server.ServerSubtitrari(0, lambda: (Stil(font=font_test), "small", ""))
    fir = threading.Thread(target=srv.serve_forever, daemon=True)
    fir.start()
    yield srv
    srv.shutdown()
    srv.server_close()


def cerere(srv, metoda, cale, corp=None, token=None, antete=None):
    conexiune = http.client.HTTPConnection("127.0.0.1", srv.server_port, timeout=120)
    toate = {"X-Subtitrari-Token": srv.token if token is None else token, "Content-Type": "application/json"}
    toate.update(antete or {})
    date = json.dumps(corp).encode() if corp is not None else None
    conexiune.request(metoda, cale, body=date, headers=toate)
    raspuns = conexiune.getresponse()
    return raspuns.status, json.loads(raspuns.read() or b"{}")


def test_scrie_portul_si_tokenul(server_pornit):
    assert (director_setari() / "port.txt").read_text() == str(server_pornit.server_port)
    assert len((director_setari() / "token.txt").read_text()) >= 32


def test_stare_cu_token(server_pornit):
    cod, date = cerere(server_pornit, "GET", "/api/stare")
    assert cod == 200 and date["ok"]


def test_fara_token_sau_cu_token_gresit(server_pornit):
    assert cerere(server_pornit, "GET", "/api/stare", token="")[0] == 401
    assert cerere(server_pornit, "GET", "/api/stare", token="x" * 43)[0] == 401


def test_refuza_cererile_din_browser(server_pornit):
    cod, _ = cerere(server_pornit, "GET", "/api/stare", antete={"Origin": "https://exemplu.ro"})
    assert cod == 403
    cod, _ = cerere(server_pornit, "GET", "/api/stare", antete={"Host": "atacator.ro"})
    assert cod == 403
    assert cerere(server_pornit, "OPTIONS", "/api/genereaza")[0] in (403, 405)


def test_cerere_invalida(server_pornit, tmp_path):
    cod, date = cerere(server_pornit, "POST", "/api/genereaza", {"clipuri": [], "durata": 3})
    assert cod == 400 and not date["ok"]
    cod, date = cerere(server_pornit, "POST", "/api/genereaza", {
        "clipuri": [{"cale": "/x.wav", "start": 0, "durata": 1}], "durata": 3, "folder": "relativ"})
    assert cod == 400 and "folder" in date["eroare"]


@necesita_ffmpeg
def test_genereaza_pentru_timeline(server_pornit, video_orizontal, tmp_path):
    corp = {
        "clipuri": [{"cale": str(video_orizontal), "start": 0.0, "durata": 4.0, "intrare": 0.0}],
        "durata": 4.0, "latime": 1280, "inaltime": 720, "fps": "30000/1001",
        "folder": str(tmp_path / "iesire"), "nume": "Timeline 1/../x", "formate": ["srt", "fcpxml"],
        "overlay": True,
    }
    cod, date = cerere(server_pornit, "POST", "/api/genereaza", corp)
    assert cod == 200, date
    assert date["subtitrari"] > 0
    assert set(date["fisiere"]) == {"srt", "fcpxml", "mov"}
    for cale in date["fisiere"].values():
        assert cale.startswith(str(tmp_path / "iesire"))  # numele nu poate ieși din folder
