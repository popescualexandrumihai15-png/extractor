from subtitrari_ro import fonturi


def test_indexul_gaseste_fonturi(index_fonturi, font_test):
    info = index_fonturi.gaseste(font_test)
    assert info is not None
    assert info.unitati_em > 0
    assert 0.5 < info.scara_ass < 1.2


def test_gaseste_varianta_bold(index_fonturi, font_test):
    normal = index_fonturi.gaseste(font_test, bold=False)
    bold = index_fonturi.gaseste(font_test, bold=True)
    assert normal is not None and bold is not None
    if any(k[0] for k in index_fonturi.familii[normal.familie]):
        assert bold.bold


def test_glife_romanesti(index_fonturi, font_test):
    info = index_fonturi.gaseste(font_test)
    assert fonturi.are_caractere(info, "ăâî")
    assert not fonturi.are_caractere(info, "\U0001F600\U000E0001")


def test_masurare_exacta_cu_pillow(index_fonturi, font_test):
    info = index_fonturi.gaseste(font_test)
    m = fonturi.Masuratoare(info, 64, bold=False)
    assert m.exacta
    assert m("Bună ziua tuturor") > m("Bună ziua") > 0


def test_citeste_font_inexistent():
    assert fonturi.citeste_font("/nu/exista.ttf") == []


def test_director_fonturi_copiaza_familia(index_fonturi, font_test, tmp_path):
    director = fonturi.pregateste_director_fonturi(index_fonturi, font_test, tmp_path / "fonts")
    assert any(director.iterdir())
