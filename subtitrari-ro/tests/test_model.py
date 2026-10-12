from subtitrari_ro.model import Proiect, Subtitrare, imparte_timp, la_sedila, normalizeaza_diacritice


def test_diacritice_cu_virgula():
    assert normalizeaza_diacritice(" Aşa şi Ţara ţine ") == "Așa și Țara ține"
    assert normalizeaza_diacritice("mãr") == "măr"


def test_la_sedila():
    assert la_sedila("ș ț Ș Ț") == "ş ţ Ş Ţ"


def test_imparte_timp_acopera_intervalul():
    cuvinte = imparte_timp("unu doi trei", 1.0, 4.0)
    assert [c.text for c in cuvinte] == ["unu", "doi", "trei"]
    assert cuvinte[0].start == 1.0 and cuvinte[-1].end == 4.0
    assert all(a.end <= b.start + 1e-6 for a, b in zip(cuvinte, cuvinte[1:]))


def _proiect():
    p = Proiect(video="clip.mp4", cuvinte=imparte_timp("Bună ziua tuturor celor de aici", 0, 3))
    s = Subtitrare(p.cuvinte[:3], 0, 1.5)
    return p, s


def test_editare_cu_acelasi_numar_de_cuvinte_pastreaza_timpii():
    p, s = _proiect()
    timpi = [(c.start, c.end) for c in p.cuvinte[:3]]
    p.editeaza(s, "Bună seara tuturor")
    assert [c.text for c in p.cuvinte[:3]] == ["Bună", "seara", "tuturor"]
    assert [(c.start, c.end) for c in p.cuvinte[:3]] == timpi


def test_editare_cu_alt_numar_de_cuvinte():
    p, s = _proiect()
    p.editeaza(s, "Salut")
    assert [c.text for c in p.cuvinte] == ["Salut", "celor", "de", "aici"]


def test_editare_corecteaza_sedila():
    p, s = _proiect()
    p.editeaza(s, "Bună şi ţie")
    assert p.cuvinte[1].text == "și" and p.cuvinte[2].text == "ție"


def test_salvare_si_incarcare(tmp_path):
    p, _ = _proiect()
    p.stil = {"font": "Arial", "marime": 70}
    cale = tmp_path / "clip.subtitrari.json"
    p.salveaza(cale)
    q = Proiect.incarca(cale)
    assert q.video == "clip.mp4"
    assert q.stil["marime"] == 70
    assert [c.text for c in q.cuvinte] == [c.text for c in p.cuvinte]
