from subtitrari_ro.stil import PRESETARI, Stil, culoare_ass, culoare_ass_inline, culoare_fcp, presetare


def test_culori():
    assert culoare_ass("#FF8000") == "&H000080FF"
    assert culoare_ass("#000000", 60) == "&H66000000"
    assert culoare_ass_inline("#112233") == "&H332211&"
    assert culoare_fcp("#FFFFFF") == "1 1 1 1"


def test_scara_dupa_latura_mica():
    s = Stil(marime=60)
    assert s.marime_px(1920, 1080) == 60
    assert s.marime_px(1080, 1920) == 60
    assert s.marime_px(3840, 2160) == 120


def test_din_dict_ignora_campuri_necunoscute_si_valori_invalide():
    s = Stil.din_dict({"font": "Inter", "camp_vechi": 1, "pozitie": "stanga", "animatie": "zbor"})
    assert s.font == "Inter" and s.pozitie == "jos" and s.animatie == "niciuna"


def test_presetarile_sunt_copii():
    a = presetare("Clasic")
    a.marime = 999
    assert PRESETARI["Clasic"].marime != 999
    assert set(PRESETARI) >= {"Clasic", "Social – majuscule", "Cutie neagră", "Karaoke", "Minimal"}
