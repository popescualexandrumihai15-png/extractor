/* Premiere Pro simulat, pentru testarea panoului CEP Subtitrări RO.
 *
 * Rulează panoul adevărat (index.html + js/main.js) și scriptul adevărat
 * (jsx/host.jsx) peste un DOM ExtendScript fals, construit după ghidul oficial
 * de scripting Premiere (ppro-scripting.docsforadobe.dev): colecții cu
 * numItems/numTracks, Time cu seconds/ticks, Track.overwriteClip(item, ticks),
 * Sequence.createCaptionTrack(item, secunde, format), Project.importFiles(...).
 *
 * Folosire: node premiere_fals.js scenariu.json  → scrie JSON cu rezultatul.
 */

"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const scenariu = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const PANOU = scenariu.panou;
const TICKS = 254016000000;
const apeluri = [];
const erori = [];

function verifica(conditie, mesaj) {
  if (!conditie) erori.push(mesaj);
}

// ── Obiecte ExtendScript ─────────────────────────────────────────────────

const ProjectItemType = { CLIP: 1, BIN: 2, ROOT: 3, FILE: 4 };
const Sequence = { CAPTION_FORMAT_SUBTITLE: 0, CAPTION_FORMAT_608: 1, CAPTION_FORMAT_708: 2 };

function colectie(elemente, camp) {
  const c = { _elemente: elemente };
  Object.defineProperty(c, camp, { get: () => elemente.length });
  const proxy = new Proxy(c, {
    get(t, cheie) {
      if (typeof cheie === "string" && /^\d+$/.test(cheie)) return elemente[Number(cheie)];
      return t[cheie];
    },
  });
  return proxy;
}

function Time(secunde) {
  this.seconds = secunde;
  this.ticks = String(Math.round(secunde * TICKS));
}

class ProjectItem {
  constructor(name, type, cale) {
    this.name = name;
    this.type = type;
    this._cale = cale || "";
    this._copii = [];
    this.children = colectie(this._copii, "numItems");
  }
  getMediaPath() { return this._cale; }
  createBin(nume) {
    verifica(this.type === ProjectItemType.BIN || this.type === ProjectItemType.ROOT,
      "createBin funcționează doar în bin-uri");
    const bin = new ProjectItem(nume, ProjectItemType.BIN);
    this._copii.push(bin);
    apeluri.push(["createBin", nume]);
    return bin;
  }
}

class TrackItem {
  constructor(item, start, end, inPoint, disabled) {
    this.projectItem = item;
    this.start = new Time(start);
    this.end = new Time(end);
    this.inPoint = new Time(inPoint);
    this.disabled = !!disabled;
  }
}

class Track {
  constructor(clipuri, muted) {
    this._clipuri = clipuri;
    this._muted = !!muted;
    this.clips = colectie(this._clipuri, "numItems");
  }
  isMuted() { return this._muted; }
  overwriteClip(item, timp) {
    verifica(typeof timp === "string" && /^\d+$/.test(timp), "overwriteClip cere timpul în ticks, ca text");
    verifica(item instanceof ProjectItem, "overwriteClip cere un ProjectItem");
    apeluri.push(["overwriteClip", item.name, timp]);
    this._clipuri.push(new TrackItem(item, Number(timp) / TICKS, scenariu.durata, 0));
    return true;
  }
}

function File(cale) {
  this.fsName = cale;
  this.displayName = path.basename(cale);
  this.parent = { fsName: path.dirname(cale) };
}

const radacina = new ProjectItem("root", ProjectItemType.ROOT);

function construiesteSecventa(s) {
  const video = s.video.map((clipuri) => new Track(clipuri.map((c) =>
    new TrackItem(new ProjectItem("v", ProjectItemType.CLIP, c.cale), c.start, c.end, 0)), false));
  const audio = s.audio.map((p) => new Track(p.clipuri.map((c) => {
    const item = c.fara_fisier ? new ProjectItem("Nested", ProjectItemType.CLIP, "")
      : new ProjectItem(path.basename(c.cale), ProjectItemType.CLIP, c.cale);
    return new TrackItem(item, c.start, c.end, c.inPoint, c.disabled);
  }), p.muted));
  const videoTracks = colectie(video, "numTracks");
  return {
    name: s.nume,
    timebase: String(Math.round(TICKS / s.fps)),
    end: String(Math.round(s.durata * TICKS)),
    frameSizeHorizontal: s.latime,
    frameSizeVertical: s.inaltime,
    audioTracks: colectie(audio, "numTracks"),
    videoTracks,
    _video: video,
    captionTracks: [],
    createCaptionTrack(item, startAtTime, format) {
      verifica(item instanceof ProjectItem && /\.srt$/i.test(item.getMediaPath()), "createCaptionTrack cere un .srt importat");
      verifica(typeof startAtTime === "number", "startAtTime e în secunde (număr)");
      verifica(format === Sequence.CAPTION_FORMAT_SUBTITLE, "formatul trebuie să fie CAPTION_FORMAT_SUBTITLE");
      apeluri.push(["createCaptionTrack", item.name, startAtTime, format]);
      this.captionTracks.push(item.name);
      return true;
    },
  };
}

const secventa = scenariu.secventa ? construiesteSecventa(scenariu.secventa) : 0;

const contextJsx = vm.createContext({
  File,
  Sequence,
  ProjectItemType,
  app: {
    project: {
      activeSequence: secventa,
      rootItem: radacina,
      path: scenariu.cale_proiect || "",
      importFiles(cai, suppressUI, bin, ca_imagini) {
        verifica(Array.isArray(cai), "importFiles cere un array de căi");
        verifica(suppressUI === true, "importFiles ar trebui să ascundă dialogurile (suppressUI)");
        verifica(bin instanceof ProjectItem, "importFiles cere bin-ul țintă");
        verifica(ca_imagini === false, "importAsNumberedStills trebuie să fie false");
        for (const cale of cai) {
          verifica(fs.existsSync(cale), "fișierul importat nu există: " + cale);
          bin._copii.push(new ProjectItem(path.basename(cale), ProjectItemType.CLIP, cale));
          apeluri.push(["importFiles", path.basename(cale)]);
        }
        return true;
      },
    },
    enableQE() {
      contextJsx.qe = {
        project: {
          getActiveSequence() {
            return {
              addTracks(nrVideo) {
                apeluri.push(["qe.addTracks", nrVideo]);
                for (let i = 0; i < nrVideo; i++) secventa._video.push(new Track([], false));
              },
            };
          },
        },
      };
    },
  },
});

vm.runInContext(fs.readFileSync(path.join(PANOU, "jsx", "host.jsx"), "utf8"), contextJsx,
  { filename: "host.jsx" });

// ── Puntea CEP și DOM-ul panoului ────────────────────────────────────────

const window = {
  __adobe_cep__: {
    evalScript(cod, callback) {
      let rezultat;
      try {
        const valoare = vm.runInContext(cod, contextJsx);
        rezultat = valoare === undefined ? "undefined" : String(valoare);
      } catch (e) {
        rezultat = "EvalScript error.";
        erori.push("ExtendScript a aruncat: " + e.message);
      }
      setTimeout(() => callback(rezultat), 0);
    },
  },
};

const html = fs.readFileSync(path.join(PANOU, "index.html"), "utf8");
const elemente = {};
for (const id of ["srt", "overlay", "genereaza", "stare"]) {
  verifica(html.includes(`id="${id}"`), `index.html nu are elementul #${id}`);
  elemente[id] = { id, checked: true, disabled: false, textContent: "", className: "", _ascultatori: {},
    addEventListener(tip, f) { this._ascultatori[tip] = f; } };
}
elemente.srt.checked = scenariu.bifa_srt !== false;
elemente.overlay.checked = scenariu.bifa_overlay !== false;
const document = { getElementById: (id) => elemente[id] || null };

// În CEP cu --mixed-context, scriptul paginii vede window, document și require-ul Node.
const contextPanou = vm.createContext({ require, window, document, process, Buffer, console, setTimeout });
vm.runInContext(fs.readFileSync(path.join(PANOU, "js", "main.js"), "utf8"), contextPanou,
  { filename: "main.js" });

// ── Clic pe buton și așteptarea rezultatului ─────────────────────────────

(async () => {
  const buton = elemente.genereaza;
  verifica(typeof buton._ascultatori.click === "function", "butonul nu are acțiune la clic");
  const promisiune = buton._ascultatori.click();
  verifica(buton.disabled === true, "butonul trebuie dezactivat cât timp lucrează");
  await promisiune;
  const rezultat = {
    stare: elemente.stare.textContent,
    clasa: elemente.stare.className,
    buton_activ: !buton.disabled,
    apeluri,
    erori,
    pistele_video: secventa ? secventa._video.map((t) => t._clipuri.map((c) => c.projectItem.name)) : [],
    subtitrari: secventa ? secventa.captionTracks : [],
    bin: radacina._copii.map((b) => ({ nume: b.name, continut: b._copii.map((c) => c.name) })),
  };
  process.stdout.write(JSON.stringify(rezultat));
})().catch((e) => {
  process.stdout.write(JSON.stringify({ erori: [...erori, "eroare în harness: " + e.stack] }));
});
