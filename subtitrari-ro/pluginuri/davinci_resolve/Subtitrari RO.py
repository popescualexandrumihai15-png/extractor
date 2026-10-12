"""Subtitrări RO — script pentru DaVinci Resolve (merge și în versiunea gratuită).

Ce face:
  1. citește clipurile audio din timeline-ul deschis;
  2. le trimite aplicației Subtitrări RO (trebuie să fie deschisă);
  3. importă rezultatul în Media Pool, în folderul „Subtitrări RO”:
     - subtitrările SRT, puse pe un track de subtitrări;
     - opțional, un strat video transparent cu subtitrările în stilul și
       fontul ales în aplicație, pus pe un track video nou, deasupra.

Instalare: vezi pluginuri/README.md (sau rulează instaleaza_davinci.bat).
Pornire: Workspace → Scripts → Edit → Subtitrari RO.
Mesajele apar în Workspace → Console.
"""

import json
import os
import sys
import urllib.error
import urllib.request

# ── Setări (poți schimba True/False) ──────────────────────────────────────
PUNE_SUBTITRARI_SRT = True  # track de subtitrări Resolve (text editabil)
PUNE_STRAT_STILIZAT = True  # video transparent cu fontul și stilul din aplicație
FOLDER_IESIRE = ""  # gol = folderul „Subtitrari RO” de lângă primul clip audio

FPS_STANDARD = {23.976: "24000/1001", 29.97: "30000/1001", 59.94: "60000/1001", 47.952: "48000/1001"}


def mesaj(text):
    print("[Subtitrări RO] " + text)


def director_setari():
    if sys.platform.startswith("win"):
        baza = os.environ.get("APPDATA", os.path.join(os.path.expanduser("~"), "AppData", "Roaming"))
        return os.path.join(baza, "SubtitrariRO")
    if sys.platform == "darwin":
        return os.path.join(os.path.expanduser("~"), "Library", "Application Support", "SubtitrariRO")
    baza = os.environ.get("XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config"))
    return os.path.join(baza, "subtitrari-ro")


def citeste_setare(nume):
    with open(os.path.join(director_setari(), nume), encoding="utf-8") as f:
        return f.read().strip()


def cere(port, token, cale, date=None, timeout=10):
    corp = None if date is None else json.dumps(date).encode("utf-8")
    cerere = urllib.request.Request(
        "http://127.0.0.1:%s%s" % (port, cale), data=corp, method="GET" if corp is None else "POST",
        headers={"X-Subtitrari-Token": token, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(cerere, timeout=timeout) as raspuns:
            return json.loads(raspuns.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8"))
        except ValueError:
            return {"ok": False, "eroare": "Eroare HTTP %s" % e.code}


def obtine_resolve():
    for nume in ("resolve",):
        if nume in globals():
            return globals()[nume]
    try:
        import DaVinciResolveScript as dvr  # noqa: N813

        return dvr.scriptapp("Resolve")
    except ImportError:
        pass
    if "bmd" in globals():
        return globals()["bmd"].scriptapp("Resolve")
    return None


def fps_timeline(timeline):
    text = str(timeline.GetSetting("timelineFrameRate") or "25").split()[0]
    valoare = float(text)
    for standard, fractie in FPS_STANDARD.items():
        if abs(valoare - standard) < 0.01:
            return valoare, fractie
    return valoare, str(int(round(valoare)))


def intrare_sursa(item, fps):
    """Momentul din fișierul sursă de unde începe clipul (secunde)."""
    try:
        valoare = item.GetSourceStartTime()  # Resolve 19+
        if valoare is not None:
            return float(valoare)
    except Exception:
        pass
    try:
        return float(item.GetLeftOffset()) / fps
    except Exception:
        return 0.0


def clipuri_audio(timeline, fps):
    start = timeline.GetStartFrame()
    clipuri = []
    for i in range(1, (timeline.GetTrackCount("audio") or 0) + 1):
        try:
            if timeline.GetIsTrackEnabled("audio", i) is False:
                continue
        except Exception:
            pass
        for item in timeline.GetItemListInTrack("audio", i) or []:
            try:
                if item.GetClipEnabled() is False:
                    continue
            except Exception:
                pass
            mpi = item.GetMediaPoolItem()
            cale = mpi.GetClipProperty("File Path") if mpi else ""
            if not cale:
                continue
            clipuri.append({
                "cale": cale,
                "start": (item.GetStart() - start) / fps,
                "durata": item.GetDuration() / fps,
                "intrare": intrare_sursa(item, fps),
            })
    return clipuri


def folder_bin(media_pool):
    radacina = media_pool.GetRootFolder()
    for sub in radacina.GetSubFolderList() or []:
        if sub.GetName() == "Subtitrări RO":
            return sub
    return media_pool.AddSubFolder(radacina, "Subtitrări RO")


def main():
    resolve = obtine_resolve()
    if resolve is None:
        mesaj("Nu găsesc DaVinci Resolve. Pornește scriptul din Workspace → Scripts.")
        return
    proiect = resolve.GetProjectManager().GetCurrentProject()
    timeline = proiect.GetCurrentTimeline() if proiect else None
    if timeline is None:
        mesaj("Deschide un timeline, apoi pornește din nou scriptul.")
        return

    try:
        port, token = citeste_setare("port.txt"), citeste_setare("token.txt")
    except OSError:
        mesaj("Nu găsesc aplicația Subtitrări RO. Deschide aplicația și bifează "
              "„Conexiune cu DaVinci și Premiere”.")
        return
    stare = cere(port, token, "/api/stare", timeout=5) if port else {}
    if not stare.get("ok"):
        mesaj("Aplicația Subtitrări RO nu răspunde. Deschide-o și bifează „Conexiune cu DaVinci și Premiere”.")
        return

    fps, fps_text = fps_timeline(timeline)
    clipuri = clipuri_audio(timeline, fps)
    if not clipuri:
        mesaj("Timeline-ul nu are clipuri audio active.")
        return
    durata = (timeline.GetEndFrame() - timeline.GetStartFrame()) / fps
    folder = FOLDER_IESIRE or os.path.join(os.path.dirname(clipuri[0]["cale"]), "Subtitrari RO")
    mesaj("Trimit %d clipuri audio (%.1f s). Transcrierea poate dura câteva minute…" % (len(clipuri), durata))

    raspuns = cere(port, token, "/api/genereaza", {
        "clipuri": clipuri,
        "durata": durata,
        "latime": int(timeline.GetSetting("timelineResolutionWidth") or 1920),
        "inaltime": int(timeline.GetSetting("timelineResolutionHeight") or 1080),
        "fps": fps_text,
        "folder": folder,
        "nume": timeline.GetName(),
        "formate": ["srt"],
        "overlay": PUNE_STRAT_STILIZAT,
    }, timeout=6 * 3600)
    if not raspuns.get("ok"):
        mesaj("Generarea a eșuat: %s" % raspuns.get("eroare", "eroare necunoscută"))
        return
    fisiere = raspuns.get("fisiere", {})
    mesaj("Am primit %d subtitrări." % raspuns.get("subtitrari", 0))

    media_pool = proiect.GetMediaPool()
    media_pool.SetCurrentFolder(folder_bin(media_pool))

    if PUNE_SUBTITRARI_SRT and fisiere.get("srt"):
        elemente = media_pool.ImportMedia([fisiere["srt"]]) or []
        if elemente and media_pool.AppendToTimeline(elemente):
            mesaj("Subtitrările sunt pe track-ul de subtitrări.")
        else:
            mesaj("Am importat SRT-ul în Media Pool (folderul „Subtitrări RO”). "
                  "Trage-l pe timeline, la început.")

    if PUNE_STRAT_STILIZAT and fisiere.get("mov"):
        elemente = media_pool.ImportMedia([fisiere["mov"]]) or []
        if elemente:
            timeline.AddTrack("video")
            track = timeline.GetTrackCount("video")
            cadre = int(round(durata * fps))
            pus = media_pool.AppendToTimeline([{
                "mediaPoolItem": elemente[0], "startFrame": 0, "endFrame": max(cadre - 1, 0),
                "trackIndex": track, "recordFrame": timeline.GetStartFrame(), "mediaType": 1,
            }])
            if pus:
                mesaj("Stratul stilizat e pe track-ul video V%d." % track)
            else:
                mesaj("Am importat stratul stilizat în Media Pool. Pune-l pe un track video deasupra, la început.")

    mesaj("Gata. Fișierele sunt în: %s" % folder)


main()
