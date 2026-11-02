"""Un DaVinci Resolve simulat, pentru testarea scriptului de plugin.

Implementează doar funcțiile folosite de script, cu semnăturile și valorile
de întoarcere din documentația oficială a API-ului de scripting
(README-ul din Developer/Scripting, Resolve 19–21). Reproduce și un
comportament real documentat pe forumul Blackmagic: subtitrările adăugate cu
MediaPool.AppendToTimeline ajung după subtitrările existente pe ST1,
indiferent de recordFrame.
"""

from __future__ import annotations

from pathlib import Path

CHEI_CLIPINFO = {"mediaPoolItem", "startFrame", "endFrame", "mediaType", "trackIndex", "recordFrame"}


class MediaPoolItem:
    def __init__(self, cale: str, fps: float = 25.0, cadre: int = 0):
        self.cale = cale
        self.fps = fps
        self.cadre = cadre

    def GetClipProperty(self, cheie=None):  # noqa: N802 (numele vin din API-ul Resolve)
        proprietati = {"File Path": self.cale, "FPS": f"{self.fps:g}", "Clip Name": Path(self.cale).name}
        return proprietati if cheie is None else proprietati.get(cheie, "")

    @property
    def e_subtitrare(self) -> bool:
        return self.cale.lower().endswith(".srt")


class TimelineItem:
    def __init__(self, mpi: MediaPoolItem | None, start: int, durata: int, sursa_start: int,
                 activ: bool = True):
        self.mpi = mpi
        self.start = start
        self.durata = durata
        self.sursa_start = sursa_start  # în cadrele clipului sursă
        self.activ = activ

    def GetMediaPoolItem(self):  # noqa: N802
        return self.mpi

    def GetStart(self, subframe=False):  # noqa: N802
        return self.start

    def GetEnd(self, subframe=False):  # noqa: N802
        return self.start + self.durata

    def GetDuration(self, subframe=False):  # noqa: N802
        return self.durata

    def GetLeftOffset(self, subframe=False):  # noqa: N802
        return self.sursa_start

    def GetSourceStartFrame(self):  # noqa: N802
        return self.sursa_start

    def GetSourceStartTime(self):  # noqa: N802
        return self.sursa_start / self.mpi.fps if self.mpi else 0.0

    def GetClipEnabled(self):  # noqa: N802
        return self.activ


class Folder:
    def __init__(self, nume: str):
        self.nume = nume
        self.subfoldere: list[Folder] = []
        self.clipuri: list[MediaPoolItem] = []

    def GetName(self):  # noqa: N802
        return self.nume

    def GetSubFolderList(self):  # noqa: N802
        return list(self.subfoldere)

    def GetClipList(self):  # noqa: N802
        return list(self.clipuri)


class Timeline:
    def __init__(self, nume: str, fps: str, latime: int, inaltime: int, start: int, durata: int):
        self.nume = nume
        self.setari = {"timelineFrameRate": fps, "timelineResolutionWidth": str(latime),
                       "timelineResolutionHeight": str(inaltime)}
        self.start = start
        self.durata = durata
        self.piste = {"video": [[]], "audio": [[]], "subtitle": []}
        self.piste_active = {}

    def GetName(self):  # noqa: N802
        return self.nume

    def GetSetting(self, nume=None):  # noqa: N802
        return dict(self.setari) if nume is None else self.setari.get(nume, "")

    def GetStartFrame(self):  # noqa: N802
        return self.start

    def GetEndFrame(self):  # noqa: N802
        return self.start + self.durata

    def GetTrackCount(self, tip):  # noqa: N802
        return len(self.piste[tip])

    def GetItemListInTrack(self, tip, index):  # noqa: N802
        if not 1 <= index <= len(self.piste[tip]):
            return None
        return list(self.piste[tip][index - 1])

    def GetIsTrackEnabled(self, tip, index):  # noqa: N802
        return self.piste_active.get((tip, index), True)

    def AddTrack(self, tip, optiuni=None):  # noqa: N802
        self.piste[tip].append([])
        return True


class MediaPool:
    def __init__(self, proiect: "Project"):
        self.proiect = proiect
        self.radacina = Folder("Master")
        self.curent = self.radacina
        self.importuri: list[str] = []
        self.adaugari: list = []

    def GetRootFolder(self):  # noqa: N802
        return self.radacina

    def GetCurrentFolder(self):  # noqa: N802
        return self.curent

    def AddSubFolder(self, folder, nume):  # noqa: N802
        nou = Folder(nume)
        folder.subfoldere.append(nou)
        return nou

    def SetCurrentFolder(self, folder):  # noqa: N802
        self.curent = folder
        return True

    def ImportMedia(self, cai):  # noqa: N802
        elemente = []
        for cale in cai:
            if not Path(cale).is_file():
                continue  # Resolve întoarce o listă goală pentru căi greșite
            fps = float(self.proiect.timeline.setari["timelineFrameRate"].split()[0])
            mpi = MediaPoolItem(cale, fps)
            self.curent.clipuri.append(mpi)
            self.importuri.append(cale)
            elemente.append(mpi)
        return elemente

    def AppendToTimeline(self, *argumente):  # noqa: N802
        """Cele trei forme documentate: (clip1, clip2...), ([clips]), ([{clipInfo}...])."""
        if len(argumente) == 1 and isinstance(argumente[0], list):
            argumente = tuple(argumente[0])
        timeline = self.proiect.timeline
        rezultat = []
        for arg in argumente:
            self.adaugari.append(arg)
            if isinstance(arg, dict):
                necunoscute = set(arg) - CHEI_CLIPINFO
                assert not necunoscute, f"chei clipInfo nedocumentate: {necunoscute}"
                mpi = arg["mediaPoolItem"]
                assert isinstance(mpi, MediaPoolItem)
                durata = int(arg["endFrame"]) - int(arg["startFrame"]) + 1
                tip = "video" if arg.get("mediaType", 1) == 1 else "audio"
                index = int(arg.get("trackIndex", 1))
                assert 1 <= index <= len(timeline.piste[tip]), "trackIndex în afara pistelor existente"
                item = TimelineItem(mpi, int(arg.get("recordFrame", timeline.start)), durata,
                                    int(arg["startFrame"]))
                timeline.piste[tip][index - 1].append(item)
                rezultat.append(item)
            elif isinstance(arg, MediaPoolItem) and arg.e_subtitrare:
                # Comportament real: după ultima subtitrare de pe ST1, nu la timpul din SRT.
                if not timeline.piste["subtitle"]:
                    timeline.piste["subtitle"].append([])
                st1 = timeline.piste["subtitle"][0]
                start = max((i.GetEnd() for i in st1), default=timeline.start)
                item = TimelineItem(arg, start, 1, 0)
                st1.append(item)
                rezultat.append(item)
            else:
                v1 = timeline.piste["video"][0]
                start = max((i.GetEnd() for i in v1), default=timeline.start)
                item = TimelineItem(arg, start, 1, 0)
                v1.append(item)
                rezultat.append(item)
        return rezultat


class Project:
    def __init__(self, timeline: Timeline | None):
        self.timeline = timeline
        self.media_pool = MediaPool(self)

    def GetCurrentTimeline(self):  # noqa: N802
        return self.timeline

    def GetMediaPool(self):  # noqa: N802
        return self.media_pool


class ProjectManager:
    def __init__(self, proiect: Project):
        self.proiect = proiect

    def GetCurrentProject(self):  # noqa: N802
        return self.proiect


class Resolve:
    def __init__(self, proiect: Project):
        self.manager = ProjectManager(proiect)

    def GetProjectManager(self):  # noqa: N802
        return self.manager
