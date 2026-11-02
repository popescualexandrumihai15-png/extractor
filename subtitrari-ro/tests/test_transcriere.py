from types import SimpleNamespace

import pytest

from subtitrari_ro.transcriere import _e_halucinatie


def segment(text, no_speech=0.0, logprob=-0.2):
    return SimpleNamespace(text=text, no_speech_prob=no_speech, avg_logprob=logprob)


def test_halucinatii_tipice_in_liniste_sunt_eliminate():
    assert _e_halucinatie(segment("Vă mulțumim pentru vizionare!", no_speech=0.6))
    assert _e_halucinatie(segment(" Abonați-vă la canal", logprob=-0.9))
    assert _e_halucinatie(segment("Subtitrarea realizată de comunitatea Amara.org", no_speech=0.4))


def test_vorbirea_reala_ramane():
    assert not _e_halucinatie(segment("Vă mulțumim pentru vizionare!", no_speech=0.05, logprob=-0.2))
    assert not _e_halucinatie(segment("Astăzi vă arătăm animațiile noastre."))


def test_cratima_lipeste_bucatile_whisper():
    from subtitrari_ro.model import Cuvant
    from subtitrari_ro.transcriere import adauga_cuvant

    cuvinte: list[Cuvant] = []
    for text, start, end in [("din", 0.0, 0.2), ("Cluj", 0.2, 0.5), ("-Napoca.", 0.5, 0.9),
                             ("Scrie", 1.0, 1.3), ("-ne", 1.3, 1.4), ("într-", 2.0, 2.2), ("o", 2.2, 2.3),
                             ("-", 3.0, 3.1), ("gata", 5.0, 5.2), ("-ne", 6.0, 6.1)]:
        adauga_cuvant(cuvinte, text, start, end)
    texte = [c.text for c in cuvinte]
    assert texte[:4] == ["din", "Cluj-Napoca.", "Scrie-ne", "într-o"]
    assert cuvinte[1].start == 0.2 and cuvinte[1].end == 0.9
    assert texte[-1] == "-ne"  # după o pauză lungă nu se lipește


def test_citeste_wav_fara_pyav(tmp_path):
    import wave

    np = pytest.importorskip("numpy")

    from subtitrari_ro.transcriere import citeste_wav

    esantioane = (np.sin(np.linspace(0, 40 * np.pi, 16000)) * 16000).astype("<i2")
    cale = tmp_path / "a.wav"
    with wave.open(str(cale), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(16000)
        f.writeframes(esantioane.tobytes())
    audio = citeste_wav(cale)
    assert isinstance(audio, np.ndarray) and audio.dtype == np.float32 and len(audio) == 16000
    assert abs(float(audio.max()) - 16000 / 32768) < 1e-3

    stereo = tmp_path / "b.wav"
    with wave.open(str(stereo), "wb") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(44100)
        f.writeframes(b"\x00\x00" * 200)
    assert citeste_wav(stereo) == str(stereo)  # alt format: îl decodează faster-whisper
