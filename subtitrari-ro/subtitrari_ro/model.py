"""Structuri de date: cuvinte cu timp, subtitrări pe un rând și proiectul salvat."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

VERSIUNE_PROIECT = 1

# Diacritice: forma corectă este cu virgulă dedesubt (ș ț), nu cu sedilă (ş ţ).
_SEDILA_LA_VIRGULA = str.maketrans({"ş": "ș", "Ş": "Ș", "ţ": "ț", "Ţ": "Ț"})
_VIRGULA_LA_SEDILA = str.maketrans({"ș": "ş", "Ș": "Ş", "ț": "ţ", "Ț": "Ţ"})


def normalizeaza_diacritice(text: str) -> str:
    """Transformă ş/ţ (sedilă) în ș/ț (virgulă) și curăță spațiile."""
    text = text.translate(_SEDILA_LA_VIRGULA)
    # Whisper scrie uneori „ã” în loc de „ă” (codare veche).
    return text.replace("ã", "ă").replace("Ã", "Ă").strip()


def la_sedila(text: str) -> str:
    """Pentru fonturi vechi care nu au ș/ț cu virgulă."""
    return text.translate(_VIRGULA_LA_SEDILA)


@dataclass
class Cuvant:
    text: str
    start: float
    end: float


@dataclass
class Subtitrare:
    """O subtitrare = un singur rând de text afișat între start și end."""

    cuvinte: list[Cuvant]
    start: float
    end: float

    @property
    def text(self) -> str:
        return " ".join(c.text for c in self.cuvinte)


def imparte_timp(text: str, start: float, end: float) -> list[Cuvant]:
    """Împarte un interval între cuvintele unui text, proporțional cu lungimea lor."""
    bucati = text.split()
    if not bucati:
        return []
    ponderi = [len(b) + 1 for b in bucati]
    total = sum(ponderi)
    durata = max(end - start, 0.01)
    cuvinte, t = [], start
    for bucata, pondere in zip(bucati, ponderi):
        pas = durata * pondere / total
        cuvinte.append(Cuvant(bucata, round(t, 3), round(t + pas, 3)))
        t += pas
    cuvinte[-1].end = round(end, 3)
    return cuvinte


@dataclass
class Proiect:
    """Ce salvăm pe disc: cuvintele transcrise (editabile) și setările."""

    video: str = ""
    limba: str = "ro"
    cuvinte: list[Cuvant] = field(default_factory=list)
    stil: dict = field(default_factory=dict)

    def editeaza(self, subtitrare: Subtitrare, text_nou: str) -> None:
        """Înlocuiește cuvintele unei subtitrări cu textul corectat de utilizator.

        Dacă numărul de cuvinte rămâne același, păstrăm timpii fiecărui cuvânt
        (cazul obișnuit: o greșeală de scriere). Altfel împărțim intervalul.
        """
        if not subtitrare.cuvinte:
            return
        primul = subtitrare.cuvinte[0]
        ultimul = subtitrare.cuvinte[-1]
        i0 = next(i for i, c in enumerate(self.cuvinte) if c is primul)
        i1 = next(i for i, c in enumerate(self.cuvinte) if c is ultimul)
        text_nou = normalizeaza_diacritice(text_nou)
        bucati = text_nou.split()
        vechi = self.cuvinte[i0:i1 + 1]
        if len(bucati) == len(vechi):
            noi = [Cuvant(b, c.start, c.end) for b, c in zip(bucati, vechi)]
        else:
            noi = imparte_timp(text_nou, primul.start, ultimul.end)
        self.cuvinte[i0:i1 + 1] = noi

    def salveaza(self, cale: str | Path) -> None:
        date = {
            "versiune": VERSIUNE_PROIECT,
            "video": self.video,
            "limba": self.limba,
            "stil": self.stil,
            "cuvinte": [asdict(c) for c in self.cuvinte],
        }
        Path(cale).write_text(json.dumps(date, ensure_ascii=False, indent=1), encoding="utf-8")

    @classmethod
    def incarca(cls, cale: str | Path) -> "Proiect":
        date = json.loads(Path(cale).read_text(encoding="utf-8"))
        return cls(
            video=date.get("video", ""),
            limba=date.get("limba", "ro"),
            stil=date.get("stil", {}),
            cuvinte=[Cuvant(**c) for c in date.get("cuvinte", [])],
        )
