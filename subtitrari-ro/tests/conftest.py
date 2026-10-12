import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from subtitrari_ro import fonturi  # noqa: E402
from subtitrari_ro.model import Cuvant, imparte_timp  # noqa: E402

ARE_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
necesita_ffmpeg = pytest.mark.skipif(not ARE_FFMPEG, reason="ffmpeg nu e instalat")

TEXT_EXEMPLU = (
    "Bună ziua și bine ați venit la Ember. Astăzi vă arătăm cum facem animații, "
    "grafică în mișcare și efecte vizuale pentru clipurile noastre. Urmăriți până la final!"
)


@pytest.fixture(autouse=True)
def setari_izolate(tmp_path, monkeypatch):
    """Fiecare test are propriul folder de setări (token, port, setari.json)."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))


@pytest.fixture
def cuvinte() -> list[Cuvant]:
    return imparte_timp(TEXT_EXEMPLU, 0.3, 5.8)


@pytest.fixture(scope="session")
def index_fonturi() -> fonturi.IndexFonturi:
    return fonturi.index_sistem()


@pytest.fixture(scope="session")
def font_test(index_fonturi) -> str:
    nume = fonturi.font_implicit(index_fonturi)
    if not index_fonturi.gaseste(nume):
        pytest.skip("nu există fonturi instalate")
    return nume


def _genereaza(cale: Path, latime: int, inaltime: int, fps: str, durata: float = 4.0) -> Path:
    subprocess.run([
        "ffmpeg", "-nostdin", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", f"testsrc2=s={latime}x{inaltime}:r={fps}:d={durata}",
        "-f", "lavfi", "-i", f"sine=frequency=440:d={durata}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(cale),
    ], check=True)
    return cale


@pytest.fixture(scope="session")
def video_orizontal(tmp_path_factory) -> Path:
    if not ARE_FFMPEG:
        pytest.skip("ffmpeg nu e instalat")
    return _genereaza(tmp_path_factory.mktemp("media") / "orizontal.mp4", 1280, 720, "25")


@pytest.fixture(scope="session")
def video_vertical(tmp_path_factory) -> Path:
    if not ARE_FFMPEG:
        pytest.skip("ffmpeg nu e instalat")
    return _genereaza(tmp_path_factory.mktemp("media") / "vertical.mp4", 720, 1280, "30000/1001")
