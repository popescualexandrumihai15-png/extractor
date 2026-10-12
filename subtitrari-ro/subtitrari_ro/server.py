"""Server local pentru pluginuri (DaVinci Resolve, Premiere Pro).

Pluginul trimite lista clipurilor audio din timeline; aplicația reconstruiește
sunetul, îl transcrie, face subtitrările cu stilul din fereastră și scrie
fișierele (SRT, strat transparent MOV etc.) în folderul cerut.

Siguranță:
  * ascultă doar pe 127.0.0.1 (nu e accesibil din rețea);
  * cere antetul X-Subtitrari-Token, cu tokenul din folderul de setări;
  * refuză cererile din browser (au antet Origin) și Host-urile străine,
    ca o pagină web să nu poată folosi serverul.
"""

from __future__ import annotations

import hmac
import json
import secrets
import shutil
import tempfile
import threading
from fractions import Fraction
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable

from . import __version__, media, motor
from .model import Proiect
from .stil import Stil, director_setari, incarca_setari
from .transcriere import MODEL_IMPLICIT, transcrie

PORT_IMPLICIT = 47817
MARIME_MAXIMA_CERERE = 2_000_000
FORMATE_PERMISE = {"srt", "vtt", "ass", "fcpxml", "json"}


def token() -> str:
    """Tokenul secret, creat la prima pornire. Pluginurile îl citesc din același fișier."""
    cale = director_setari() / "token.txt"
    try:
        valoare = cale.read_text(encoding="utf-8").strip()
        if len(valoare) >= 32:
            return valoare
    except OSError:
        pass
    valoare = secrets.token_urlsafe(32)
    cale.write_text(valoare, encoding="utf-8")
    try:
        cale.chmod(0o600)
    except OSError:
        pass
    return valoare


FurnizorStil = Callable[[], tuple[Stil, str, str]]


def stil_din_setari() -> tuple[Stil, str, str]:
    setari = incarca_setari()
    return (Stil.din_dict(setari.get("stil")), setari.get("model", MODEL_IMPLICIT),
            setari.get("vocabular", ""))


class EroareCerere(ValueError):
    pass


def _numar(valoare, nume: str, minim: float = 0.0) -> float:
    try:
        x = float(valoare)
    except (TypeError, ValueError):
        raise EroareCerere(f"Câmpul „{nume}” trebuie să fie un număr.") from None
    if x != x or x < minim:  # NaN sau prea mic
        raise EroareCerere(f"Câmpul „{nume}” are o valoare nepermisă.")
    return x


def proceseaza_cerere(date: dict, furnizor: FurnizorStil) -> dict:
    """Generează subtitrările pentru un timeline. Întoarce fișierele scrise."""
    clipuri_brute = date.get("clipuri")
    if not isinstance(clipuri_brute, list) or not clipuri_brute or len(clipuri_brute) > 2000:
        raise EroareCerere("Cererea nu conține clipuri audio.")
    clipuri = []
    for c in clipuri_brute:
        if not isinstance(c, dict) or not isinstance(c.get("cale"), str):
            raise EroareCerere("Un clip nu are calea fișierului.")
        clipuri.append(media.ClipTimeline(
            cale=c["cale"], start=_numar(c.get("start", 0), "start"),
            durata=_numar(c.get("durata", 0), "durata"), intrare=_numar(c.get("intrare", 0), "intrare"),
        ))
    durata = _numar(date.get("durata"), "durata", 0.1)
    latime = int(_numar(date.get("latime", 1920), "latime", 16))
    inaltime = int(_numar(date.get("inaltime", 1080), "inaltime", 16))
    try:
        fps = Fraction(str(date.get("fps", 25))).limit_denominator(1001)
    except (ValueError, ZeroDivisionError):
        raise EroareCerere("Câmpul „fps” nu e valid.") from None
    if not 1 <= fps <= 240:
        raise EroareCerere("Câmpul „fps” nu e valid.")
    folder = Path(str(date.get("folder", "")))
    if not folder.is_absolute():
        raise EroareCerere("Câmpul „folder” trebuie să fie o cale completă.")
    nume = "".join(ch for ch in str(date.get("nume", "timeline")) if ch.isalnum() or ch in " -_.")[:80]
    nume = nume.strip(" .") or "timeline"
    formate = [f for f in date.get("formate", ["srt"]) if f in FORMATE_PERMISE]
    overlay = bool(date.get("overlay", False))

    stil, model, vocabular = furnizor()
    director = Path(tempfile.mkdtemp(prefix="subtitrari_plugin_"))
    try:
        wav = media.mixeaza_timeline(clipuri, durata, director / "timeline.wav")
        cuvinte = transcrie(wav, model=model, vocabular=vocabular)
    finally:
        shutil.rmtree(director, ignore_errors=True)
    info = media.InfoVideo(cale=str(folder / f"{nume}.wav"), latime=latime, inaltime=inaltime,
                           fps=fps, durata=durata, are_audio=True, are_video=False)
    proiect = Proiect(video="", cuvinte=cuvinte)
    fisiere = motor.exporta(proiect, stil, info, folder, formate, nume=nume, overlay=overlay)
    subtitrari = motor.construieste_subtitrari(cuvinte, stil, info)
    return {
        "ok": True,
        "subtitrari": len(subtitrari),
        "fisiere": {k: str(v) for k, v in fisiere.items()},
    }


class _Handler(BaseHTTPRequestHandler):
    server_version = f"SubtitrariRO/{__version__}"

    def log_message(self, *_args):  # fără zgomot în consolă
        pass

    def _raspunde(self, cod: int, date: dict) -> None:
        corp = json.dumps(date, ensure_ascii=False).encode("utf-8")
        self.send_response(cod)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corp)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corp)

    def _permis(self) -> bool:
        port = self.server.server_port
        if self.headers.get("Host", "") not in (f"127.0.0.1:{port}", f"localhost:{port}"):
            self._raspunde(403, {"ok": False, "eroare": "Host nepermis."})
            return False
        if self.headers.get("Origin") is not None:
            self._raspunde(403, {"ok": False, "eroare": "Cererile din browser nu sunt permise."})
            return False
        primit = self.headers.get("X-Subtitrari-Token", "")
        if not hmac.compare_digest(primit.encode(), self.server.token.encode()):
            self._raspunde(401, {"ok": False, "eroare": "Token lipsă sau greșit."})
            return False
        return True

    def do_GET(self):
        if not self._permis():
            return
        if self.path == "/api/stare":
            self._raspunde(200, {"ok": True, "aplicatie": "Subtitrări RO", "versiune": __version__,
                                 "ocupat": self.server.lacat.locked()})
        else:
            self._raspunde(404, {"ok": False, "eroare": "Adresă necunoscută."})

    def do_POST(self):
        if not self._permis():
            return
        if self.path != "/api/genereaza":
            self._raspunde(404, {"ok": False, "eroare": "Adresă necunoscută."})
            return
        try:
            lungime = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            lungime = -1
        if not 0 < lungime <= MARIME_MAXIMA_CERERE:
            self._raspunde(413, {"ok": False, "eroare": "Cererea e goală sau prea mare."})
            return
        try:
            date = json.loads(self.rfile.read(lungime).decode("utf-8"))
            if not isinstance(date, dict):
                raise ValueError
        except (ValueError, UnicodeDecodeError):
            self._raspunde(400, {"ok": False, "eroare": "Cererea nu e JSON valid."})
            return
        if not self.server.lacat.acquire(blocking=False):
            self._raspunde(409, {"ok": False, "eroare": "Aplicația lucrează deja la o cerere. "
                                                      "Încearcă din nou după ce termină."})
            return
        try:
            self._raspunde(200, proceseaza_cerere(date, self.server.furnizor))
        except EroareCerere as e:
            self._raspunde(400, {"ok": False, "eroare": str(e)})
        except Exception as e:  # erorile de ffmpeg/transcriere ajung la plugin
            self._raspunde(500, {"ok": False, "eroare": str(e)})
        finally:
            self.server.lacat.release()

    def do_OPTIONS(self):  # fără CORS: browserele nu primesc acces
        self._raspunde(405, {"ok": False, "eroare": "Metodă nepermisă."})

    do_PUT = do_DELETE = do_PATCH = do_OPTIONS


class ServerSubtitrari(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, port: int, furnizor: FurnizorStil):
        super().__init__(("127.0.0.1", port), _Handler)
        self.furnizor = furnizor
        self.token = token()
        self.lacat = threading.Lock()
        (director_setari() / "port.txt").write_text(str(self.server_port), encoding="utf-8")


def porneste_in_fundal(furnizor: FurnizorStil | None = None, port: int = PORT_IMPLICIT) -> ServerSubtitrari:
    server = ServerSubtitrari(port, furnizor or stil_din_setari)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def ruleaza(port: int = PORT_IMPLICIT) -> None:
    """Server fără fereastră (stilul se ia din ultimele setări salvate)."""
    server = ServerSubtitrari(port, stil_din_setari)
    print(f"Subtitrări RO ascultă pe http://127.0.0.1:{server.server_port} (Ctrl+C oprește).")
    print(f"Tokenul pentru pluginuri e în: {director_setari() / 'token.txt'}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
