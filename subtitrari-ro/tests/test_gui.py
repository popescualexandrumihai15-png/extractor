import os

import pytest

from subtitrari_ro.model import Proiect

from conftest import TEXT_EXEMPLU, necesita_ffmpeg

tk = pytest.importorskip("tkinter")
ctk = pytest.importorskip("customtkinter")
necesita_ecran = pytest.mark.skipif(not os.environ.get("DISPLAY") and os.name != "nt",
                                    reason="nu există ecran (rulați cu xvfb-run)")


@necesita_ecran
@necesita_ffmpeg
def test_fereastra_genereaza_lista_si_previzualizarea(video_orizontal):
    from subtitrari_ro import gui, tema
    from subtitrari_ro.model import imparte_timp

    tema.aplica()
    root = ctk.CTk()
    try:
        app = gui.AplicatieSubtitrari(root)
        app.conexiune.set(False)
        assert app._incarca_video(str(video_orizontal))
        app._transcriere_gata(Proiect(video=str(video_orizontal), cuvinte=imparte_timp(TEXT_EXEMPLU, 0.3, 3.8)))
        assert len(app.tabel.get_children()) == len(app.subtitrari) > 0

        app._alege_presetare("Social – majuscule")
        app._dupa_schimbare_stil()
        assert app.stil_curent().majuscule
        assert app.tabel.item("0")["values"][3] == app.subtitrari[0].text.upper()

        primul = app.subtitrari[0]
        app.proiect.editeaza(primul, "Salut")
        app._reconstruieste()
        assert app.subtitrari[0].cuvinte[0].text == "Salut"
    finally:
        root.destroy()
