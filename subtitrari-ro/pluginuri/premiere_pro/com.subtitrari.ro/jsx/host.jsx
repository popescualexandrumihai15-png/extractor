/* Subtitrări RO — partea ExtendScript (rulează în Premiere Pro).
 *
 * ExtendScript nu are obiectul JSON, așa că răspunsurile sunt construite manual.
 */

var TICKS_PE_SECUNDA = 254016000000;
var NUME_BIN = "Subtitrări RO";

function _esc(text) {
    return String(text)
        .replace(/\\/g, "\\\\")
        .replace(/"/g, '\\"')
        .replace(/\r/g, "")
        .replace(/\n/g, "\\n");
}

function _eroare(text) {
    return '{"eroare":"' + _esc(text) + '"}';
}

/* Informațiile despre secvența activă: dimensiuni, fps și clipurile audio. */
function subtitrariInfoSecventa() {
    if (!app.project) {
        return _eroare("Deschide un proiect.");
    }
    var seq = app.project.activeSequence;
    if (!seq) {
        return _eroare("Deschide o secvență în timeline.");
    }
    var fps = TICKS_PE_SECUNDA / parseFloat(seq.timebase);
    var durata = parseFloat(seq.end) / TICKS_PE_SECUNDA;
    var clipuri = [];
    for (var t = 0; t < seq.audioTracks.numTracks; t++) {
        var track = seq.audioTracks[t];
        if (track.isMuted && track.isMuted()) {
            continue;
        }
        for (var c = 0; c < track.clips.numItems; c++) {
            var clip = track.clips[c];
            if (clip.disabled || !clip.projectItem) {
                continue;
            }
            var cale = clip.projectItem.getMediaPath();
            if (!cale) {
                continue; // secvențe imbricate sau elemente fără fișier
            }
            clipuri.push(
                '{"cale":"' + _esc(cale) + '"' +
                ',"start":' + clip.start.seconds +
                ',"durata":' + (clip.end.seconds - clip.start.seconds) +
                ',"intrare":' + clip.inPoint.seconds + '}'
            );
        }
    }
    var folder = "";
    if (app.project.path) {
        folder = new File(app.project.path).parent.fsName;
    }
    return '{"nume":"' + _esc(seq.name) + '"' +
        ',"latime":' + seq.frameSizeHorizontal +
        ',"inaltime":' + seq.frameSizeVertical +
        ',"fps":' + fps +
        ',"durata":' + durata +
        ',"folderProiect":"' + _esc(folder) + '"' +
        ',"clipuri":[' + clipuri.join(",") + ']}';
}

function _gasesteBin() {
    var radacina = app.project.rootItem;
    for (var i = 0; i < radacina.children.numItems; i++) {
        var copil = radacina.children[i];
        if (copil.type === ProjectItemType.BIN && copil.name === NUME_BIN) {
            return copil;
        }
    }
    return radacina.createBin(NUME_BIN);
}

function _numeFisier(cale) {
    return new File(cale).displayName;
}

function _importa(cale, bin) {
    app.project.importFiles([cale], true, bin, false);
    var nume = _numeFisier(cale);
    var gasit = null;
    for (var i = 0; i < bin.children.numItems; i++) {
        if (bin.children[i].name === nume) {
            gasit = bin.children[i]; // ultimul cu acest nume = cel abia importat
        }
    }
    return gasit;
}

function _trackVideoLiber(seq) {
    var liber = null;
    for (var i = seq.videoTracks.numTracks - 1; i >= 0; i--) {
        if (seq.videoTracks[i].clips.numItems === 0) {
            liber = seq.videoTracks[i];
        } else {
            break;
        }
    }
    return liber;
}

/* Importă rezultatul: SRT ca track de subtitrări, MOV pe un track video liber de sus. */
function subtitrariImporta(caleSrt, caleMov) {
    var seq = app.project.activeSequence;
    if (!seq) {
        return _eroare("Secvența nu mai e deschisă.");
    }
    var bin = _gasesteBin();
    var rezultat = [];

    if (caleSrt) {
        var srt = _importa(caleSrt, bin);
        if (srt && seq.createCaptionTrack) {
            seq.createCaptionTrack(srt, 0, Sequence.CAPTION_FORMAT_SUBTITLE);
            rezultat.push("Subtitrările sunt pe un track de subtitrări.");
        } else if (srt) {
            rezultat.push("SRT-ul e în bin-ul „" + NUME_BIN + "”. Trage-l pe timeline.");
        }
    }

    if (caleMov) {
        var mov = _importa(caleMov, bin);
        if (mov) {
            var track = _trackVideoLiber(seq);
            if (!track) {
                try {
                    app.enableQE();
                    qe.project.getActiveSequence().addTracks(1, seq.videoTracks.numTracks, 0);
                    track = _trackVideoLiber(seq);
                } catch (e) {
                    track = null;
                }
            }
            if (track) {
                track.overwriteClip(mov, 0);
                rezultat.push("Stratul stilizat e pe track-ul video de sus.");
            } else {
                rezultat.push("Stratul stilizat e în bin-ul „" + NUME_BIN +
                    "”. Adaugă un track video și pune-l deasupra, la început.");
            }
        }
    }
    return '{"mesaj":"' + _esc(rezultat.join(" ")) + '"}';
}
