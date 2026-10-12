from types import SimpleNamespace

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
