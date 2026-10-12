"""Pornire: fără argumente deschide fereastra; cu argumente lucrează din linia de comandă.

Exemple:
  python -m subtitrari_ro                          # fereastra
  python -m subtitrari_ro clip.mp4 --formate srt,fcpxml --arde
  python -m subtitrari_ro clip.mp4 --stil "Social – majuscule" --font "Montserrat" --overlay
  python -m subtitrari_ro server                   # doar serverul pentru pluginuri
  python -m subtitrari_ro fonturi                  # lista fonturilor găsite
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _cli(argumente: list[str]) -> int:
    from . import exporturi, fonturi, media, motor
    from .stil import PRESETARI, Stil, incarca_setari, presetare
    from .transcriere import MODEL_IMPLICIT

    parser = argparse.ArgumentParser(prog="subtitrari_ro", description="Subtitrări automate în română.")
    parser.add_argument("video", help="fișierul video sau audio")
    parser.add_argument("--formate", default="srt",
                        help=f"separate prin virgulă: {','.join(exporturi.FORMATE)} (implicit: srt)")
    parser.add_argument("--folder", help="unde se salvează (implicit: lângă video)")
    parser.add_argument("--stil", help=f"presetare: {', '.join(PRESETARI)} (implicit: ultimul stil folosit)")
    parser.add_argument("--font", help="familia fontului, de exemplu „Arial”")
    parser.add_argument("--marime", type=int, help="mărimea textului (pixeli la 1080p)")
    parser.add_argument("--majuscule", action="store_true", help="text cu majuscule")
    parser.add_argument("--model", default=None, help=f"model Whisper (implicit: {MODEL_IMPLICIT})")
    parser.add_argument("--vocabular", default="", help="nume și termeni, separați prin virgulă")
    parser.add_argument("--arde", action="store_true", help="și un MP4 cu subtitrările în imagine")
    parser.add_argument("--overlay", action="store_true", help="și un MOV transparent cu subtitrările")
    parser.add_argument("--proiect", action="store_true", help="salvează și proiectul .subtitrari.json")
    a = parser.parse_args(argumente)

    setari = incarca_setari()
    stil = presetare(a.stil) if a.stil else Stil.din_dict(setari.get("stil"))
    if a.font:
        stil.font = a.font
    if a.marime:
        stil.marime = a.marime
    if a.majuscule:
        stil.majuscule = True
    formate = [f.strip() for f in a.formate.split(",") if f.strip()]
    necunoscute = [f for f in formate if f not in exporturi.FORMATE]
    if necunoscute:
        parser.error(f"format necunoscut: {', '.join(necunoscute)}")

    index = fonturi.index_sistem()
    if not index.gaseste(stil.font):
        inlocuitor = fonturi.font_implicit(index)
        print(f"Fontul „{stil.font}” nu e instalat. Folosesc „{inlocuitor}”.", file=sys.stderr)
        stil.font = inlocuitor

    def progres(p: float) -> None:
        print(f"\r  {p * 100:5.1f}%", end="", file=sys.stderr, flush=True)

    def stare(s: str) -> None:
        print(f"\n{s}", file=sys.stderr)

    proiect = motor.transcrie_video(a.video, model=a.model or setari.get("model", MODEL_IMPLICIT),
                                    vocabular=a.vocabular, progres=progres, stare=stare)
    info = media.info_video(a.video)
    folder = Path(a.folder) if a.folder else Path(a.video).resolve().parent
    fisiere = motor.exporta(proiect, stil, info, folder, formate, arde=a.arde, overlay=a.overlay,
                            progres=progres, stare=stare, index=index)
    if a.proiect:
        proiect.stil = stil.la_dict()
        cale = folder / f"{Path(a.video).stem}.subtitrari.json"
        proiect.salveaza(cale)
        fisiere["proiect"] = cale
    print(file=sys.stderr)
    for cale in fisiere.values():
        print(cale)
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        from .gui import porneste

        porneste()
        return 0
    if argv[0] == "server":
        from .server import PORT_IMPLICIT, ruleaza

        ruleaza(int(argv[1]) if len(argv) > 1 else PORT_IMPLICIT)
        return 0
    if argv[0] == "fonturi":
        from .fonturi import index_sistem

        for nume in index_sistem().nume_familii():
            print(nume)
        return 0
    if len(argv) == 1 and Path(argv[0]).is_file() and argv[0].lower().endswith(
            (".mp4", ".mov", ".mkv", ".m4v", ".avi", ".webm")) and sys.stdin is None:
        from .gui import porneste  # dublu-clic / „Deschide cu” pe Windows, fără consolă

        porneste(argv[0])
        return 0
    try:
        return _cli(argv)
    except Exception as e:  # mesaj scurt, fără traceback, pentru utilizator
        print(f"Eroare: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
