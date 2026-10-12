# Pluginuri pentru editoare

Pluginurile trimit sunetul din timeline către aplicația Subtitrări RO. Aplicația face subtitrările cu stilul ales în fereastră și le pune înapoi în proiect.

**Înainte de orice plugin:** deschide aplicația Subtitrări RO. Verifică apoi că e pornit comutatorul „Conexiune cu DaVinci și Premiere” din dreapta sus. Punctul de lângă el devine verde.

Fișierele generate se salvează în folderul `Subtitrari RO`, lângă proiect sau lângă primul clip audio.

## DaVinci Resolve (și versiunea gratuită)

Resolve are nevoie de Python 3 instalat pentru scripturi (<https://www.python.org/downloads/>).

**Instalare:**

- Windows: dă dublu-clic pe `instaleaza_davinci.bat`.
- macOS: dă dublu-clic pe `instaleaza_davinci_mac.command`.

**Folosire:**

1. Deschide timeline-ul.
2. Alege Workspace → Scripts → Edit → **Subtitrari RO**.
3. Așteaptă. Mesajele apar în Workspace → Console.

Rezultatul:

- subtitrările SRT pe un track de subtitrări (text editabil în Resolve);
- stratul transparent cu fontul și stilul tău pe un track video nou, deasupra.

Dacă vrei doar unul dintre ele, deschide fișierul `Subtitrari RO.py` și schimbă `True` în `False` la `PUNE_SUBTITRARI_SRT` sau `PUNE_STRAT_STILIZAT`.

## Premiere Pro (2021 sau mai nou)

**Instalare:**

- Windows: dă dublu-clic pe `instaleaza_premiere.bat`.
- macOS: dă dublu-clic pe `instaleaza_premiere_mac.command`.

Scriptul copiază panoul și permite panourile nesemnate (setarea `PlayerDebugMode` de la Adobe). Repornește apoi Premiere Pro.

**Folosire:**

1. Deschide secvența.
2. Alege Window → Extensions → **Subtitrări RO**.
3. Bifează ce vrei și apasă „Generează subtitrările”.

Rezultatul:

- un track de subtitrări (Captions), editabil în Premiere;
- stratul transparent cu fontul și stilul tău pe primul track video liber de sus.

Sunt citite clipurile audio active cu fișier pe disc. Secvențele imbricate (nested) nu sunt citite.

## Final Cut Pro

Final Cut nu permite pluginuri simple de acest tip. Exportă din aplicație și importă în Final Cut:

- **Subtitrări editabile:** în Final Cut, File → Import → Captions → fișierul `.srt`.
- **Titluri cu fontul tău:** File → Import → XML → fișierul `.fcpxml`. Apare un proiect nou, cu videoul și cu un titlu „Basic Title” pentru fiecare subtitrare, în fontul și culorile alese.
- **Strat transparent:** importă fișierul `.mov` și pune-l deasupra clipului.

## CapCut

CapCut nu are pluginuri pentru aplicații externe. Ai două variante:

- **Subtitrări editabile:** importă fișierul `.srt` din meniul de subtitrări al CapCut. Numele meniului diferă de la o versiune la alta.
- **Cu fontul și stilul tău:** în aplicație bifează „MP4 cu subtitrări arse”, apoi folosește videoul rezultat în CapCut.
