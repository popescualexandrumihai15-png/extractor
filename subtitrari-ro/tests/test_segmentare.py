from subtitrari_ro import fonturi
from subtitrari_ro.model import Cuvant, imparte_timp
from subtitrari_ro.segmentare import CUVINTE_DE_LEGATURA, imparte_pe_un_rand


def masoara_simplu(text: str) -> float:
    return len(text) * 10.0  # 10 px pe caracter


def test_fiecare_subtitrare_incape_pe_un_rand(cuvinte):
    subtitrari = imparte_pe_un_rand(cuvinte, masoara_simplu, latime_max=300)
    assert subtitrari
    for s in subtitrari:
        assert "\n" not in s.text
        assert masoara_simplu(s.text) <= 300 or len(s.cuvinte) == 1


def test_toate_cuvintele_raman_in_ordine(cuvinte):
    subtitrari = imparte_pe_un_rand(cuvinte, masoara_simplu, latime_max=300)
    reconstruit = [c.text for s in subtitrari for c in s.cuvinte]
    assert reconstruit == [c.text for c in cuvinte]


def test_timpii_nu_se_suprapun(cuvinte):
    subtitrari = imparte_pe_un_rand(cuvinte, masoara_simplu, latime_max=300)
    for a, b in zip(subtitrari, subtitrari[1:]):
        assert a.start < a.end <= b.start


def test_rupe_la_final_de_propozitie(cuvinte):
    subtitrari = imparte_pe_un_rand(cuvinte, masoara_simplu, latime_max=2000)
    assert subtitrari[0].text == "Bună ziua și bine ați venit la Ember."


def test_max_cuvinte(cuvinte):
    subtitrari = imparte_pe_un_rand(cuvinte, masoara_simplu, latime_max=2000, max_cuvinte=3)
    assert all(len(s.cuvinte) <= 3 for s in subtitrari)


def test_max_caractere(cuvinte):
    subtitrari = imparte_pe_un_rand(cuvinte, masoara_simplu, latime_max=5000, max_caractere=20)
    assert all(len(s.text) <= 20 or len(s.cuvinte) == 1 for s in subtitrari)


def test_cuvintele_de_legatura_nu_raman_la_capat_de_rand(cuvinte):
    subtitrari = imparte_pe_un_rand(cuvinte, masoara_simplu, latime_max=220)
    for s in subtitrari[:-1]:
        ultimul = s.cuvinte[-1].text
        assert ultimul.strip(".,!?").casefold() not in CUVINTE_DE_LEGATURA or len(s.cuvinte) == 1, s.text


def test_pauza_lunga_incepe_subtitrare_noua():
    cuvinte = [Cuvant("Salut", 0.0, 0.4), Cuvant("tuturor", 0.45, 0.9), Cuvant("Acum", 2.5, 2.8)]
    subtitrari = imparte_pe_un_rand(cuvinte, masoara_simplu, latime_max=5000)
    assert [s.text for s in subtitrari] == ["Salut tuturor", "Acum"]
    assert subtitrari[0].end <= 2.5


def test_durata_minima():
    cuvinte = [Cuvant("Da.", 1.0, 1.1)]
    s = imparte_pe_un_rand(cuvinte, masoara_simplu, latime_max=500)[0]
    assert s.end - s.start >= 0.6


def test_majuscule_masoara_textul_cu_majuscule():
    latimi = []

    def masoara(text):
        latimi.append(text)
        return len(text) * 10.0

    imparte_pe_un_rand(imparte_timp("bună ziua tuturor", 0, 2), masoara, latime_max=500, majuscule=True)
    assert any(t == t.upper() and "BUNĂ" in t for t in latimi)


def test_estimarea_fara_font_e_pozitiva():
    m = fonturi.Masuratoare(None, 64, bold=True)
    assert not m.exacta
    assert m("Bună ziua") > m("Bună")
