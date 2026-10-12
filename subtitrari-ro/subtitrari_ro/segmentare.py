"""Împarte cuvintele transcrise în subtitrări de UN SINGUR RÂND.

Reguli:
  * rândul nu depășește lățimea permisă (măsurată cu fontul ales);
  * opțional, cel mult N cuvinte pe subtitrare (stil „social”);
  * rupem la final de propoziție, la pauze în vorbire și după durata maximă;
  * nu lăsăm la final de rând cuvinte de legătură („și”, „de”, „la”...),
    le mutăm pe rândul următor;
  * subtitrările nu se suprapun; dacă vorbirea e continuă, se lipesc.
"""

from __future__ import annotations

from typing import Callable

from .model import Cuvant, Subtitrare

# Cuvinte care nu arată bine singure la capăt de rând.
CUVINTE_DE_LEGATURA = {
    "a", "al", "ale", "ai", "o", "un", "unei", "unui", "și", "si", "de", "la", "în",
    "in", "cu", "pe", "că", "ca", "să", "sa", "nu", "mai", "din", "pentru", "care",
    "dar", "sau", "prin", "spre", "fără", "lui", "cel", "cea", "cei", "cele", "se",
    "te", "mă", "ne", "vă", "le", "îi", "iar", "ori", "după", "până", "despre",
    "sub", "peste", "între", "dintre", "către", "cum", "când", "unde", "ce", "cât",
    "foarte", "tot", "toate", "acest", "această", "aceste", "acești", "dacă",
}

FINAL_PROPOZITIE = (".", "!", "?", "…", "...")


def _curat(cuvant: str) -> str:
    return cuvant.strip(".,;:!?…\"'„”«»()[]-–—").casefold()


def _e_de_legatura(cuvant: str) -> bool:
    if cuvant.rstrip()[-1:] in ",.;:!?…":
        return False  # are punctuație, deci e un capăt natural
    return _curat(cuvant) in CUVINTE_DE_LEGATURA


def imparte_pe_un_rand(
    cuvinte: list[Cuvant],
    masoara: Callable[[str], float],
    latime_max: float,
    max_cuvinte: int = 0,
    max_caractere: int = 0,
    max_durata: float = 3.5,
    pauza: float = 0.6,
    min_durata: float = 0.6,
    majuscule: bool = False,
) -> list[Subtitrare]:
    """Grupează cuvintele în subtitrări pe un rând.

    masoara(text) întoarce lățimea în pixeli a textului; latime_max e lățimea
    disponibilă în pixeli. max_cuvinte / max_caractere = 0 înseamnă fără limită.
    """
    cuvinte = [c for c in cuvinte if c.text.strip()]
    if not cuvinte:
        return []

    def text_de(grup: list[Cuvant]) -> str:
        t = " ".join(c.text for c in grup)
        return t.upper() if majuscule else t

    def incape(grup: list[Cuvant]) -> bool:
        if max_cuvinte and len(grup) > max_cuvinte:
            return False
        text = text_de(grup)
        if max_caractere and len(grup) > 1 and len(text) > max_caractere:
            return False
        return masoara(text) <= latime_max

    grupuri: list[list[Cuvant]] = []
    curent: list[Cuvant] = []
    for cuvant in cuvinte:
        if curent:
            ultimul = curent[-1]
            natural = (
                cuvant.start - ultimul.end >= pauza
                or ultimul.text.rstrip().endswith(FINAL_PROPOZITIE)
                # La virgulă rupem doar dacă rândul e deja pe jumătate plin.
                or (ultimul.text.rstrip().endswith((",", ";", ":"))
                    and masoara(text_de(curent)) > latime_max * 0.5)
            )
            de_capacitate = not incape(curent + [cuvant]) or cuvant.end - curent[0].start > max_durata
            if natural or de_capacitate:
                rest: list[Cuvant] = []
                if de_capacitate and not natural:
                    # Rândul s-a umplut: cuvintele de legătură de la capăt trec pe rândul nou.
                    while len(curent) > 1 and _e_de_legatura(curent[-1].text) \
                            and incape([curent[-1]] + rest + [cuvant]):
                        rest.insert(0, curent.pop())
                grupuri.append(curent)
                curent = rest
        curent.append(cuvant)
    if curent:
        grupuri.append(curent)

    # Echilibrează: un rând rupt doar din lipsă de loc, urmat de un rest scurt
    # („... pentru clipurile” / „noastre.”), cedează cuvinte rândului următor.
    for i in range(len(grupuri) - 1):
        grup, urmator = grupuri[i], grupuri[i + 1]
        lipit = urmator[0].start - grup[-1].end < pauza
        rupt_de_lungime = not grup[-1].text.rstrip().endswith((*FINAL_PROPOZITIE, ",", ";", ":"))
        dupa = grupuri[i + 2][0].start - urmator[-1].end if i + 2 < len(grupuri) else pauza
        rest_scurt = (
            masoara(text_de(urmator)) < latime_max * 0.4
            and (urmator[-1].text.rstrip().endswith(FINAL_PROPOZITIE) or dupa >= pauza)
        )
        if not (lipit and rupt_de_lungime and rest_scurt):
            continue
        while len(grup) > 1:
            candidat = [grup[-1]] + urmator
            if not incape(candidat) or masoara(text_de(candidat)) > masoara(text_de(grup[:-1])):
                break
            urmator.insert(0, grup.pop())

    # Mută cuvintele de legătură de la capăt de rând pe rândul următor,
    # dacă nu e pauză între ele și dacă încap acolo.
    for i in range(len(grupuri) - 1):
        grup, urmator = grupuri[i], grupuri[i + 1]
        while (
            len(grup) > 1
            and _e_de_legatura(grup[-1].text)
            and urmator[0].start - grup[-1].end < pauza
            and incape([grup[-1]] + urmator)
        ):
            urmator.insert(0, grup.pop())

    subtitrari = [Subtitrare(g, g[0].start, g[-1].end) for g in grupuri if g]
    return ajusteaza_timpi(subtitrari, pauza=pauza, min_durata=min_durata)


def ajusteaza_timpi(
    subtitrari: list[Subtitrare], pauza: float = 0.6, min_durata: float = 0.6,
    ramanere: float = 0.3,
) -> list[Subtitrare]:
    """Lipește subtitrările apropiate, prelungește puțin finalul, evită suprapunerea."""
    for i, s in enumerate(subtitrari):
        urmatorul = subtitrari[i + 1].start if i + 1 < len(subtitrari) else None
        if urmatorul is not None and urmatorul - s.end < pauza:
            s.end = urmatorul  # vorbire continuă: fără clipire între rânduri
        else:
            s.end = s.end + ramanere if urmatorul is None else min(s.end + ramanere, urmatorul)
        if s.end - s.start < min_durata:
            limita = urmatorul if urmatorul is not None else s.start + min_durata
            s.end = max(s.end, min(s.start + min_durata, limita))
        s.start = round(s.start, 3)
        s.end = round(s.end, 3)
    return subtitrari
