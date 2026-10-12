/* Subtitrări RO — panoul din Premiere Pro (CEP, cu Node.js activat). */
/* global window, document, require, process */

const fs = require("fs");
const os = require("os");
const path = require("path");
const http = require("http");

const elemStare = document.getElementById("stare");
const butonGenereaza = document.getElementById("genereaza");

function arataStare(text, tip) {
  elemStare.textContent = text;
  elemStare.className = tip || "";
}

function directorSetari() {
  if (process.platform === "win32") {
    const baza = process.env.APPDATA || path.join(os.homedir(), "AppData", "Roaming");
    return path.join(baza, "SubtitrariRO");
  }
  if (process.platform === "darwin") {
    return path.join(os.homedir(), "Library", "Application Support", "SubtitrariRO");
  }
  return path.join(process.env.XDG_CONFIG_HOME || path.join(os.homedir(), ".config"), "subtitrari-ro");
}

function citesteSetare(nume) {
  return fs.readFileSync(path.join(directorSetari(), nume), "utf8").trim();
}

function evalScript(cod) {
  return new Promise((rezolva) => window.__adobe_cep__.evalScript(cod, rezolva));
}

function cerere(metoda, cale, date, timeout) {
  const port = Number(citesteSetare("port.txt"));
  const token = citesteSetare("token.txt");
  const corp = date ? JSON.stringify(date) : "";
  return new Promise((rezolva, respinge) => {
    const req = http.request({
      host: "127.0.0.1",
      port: port,
      path: cale,
      method: metoda,
      timeout: timeout,
      headers: {
        "X-Subtitrari-Token": token,
        "Content-Type": "application/json",
        "Content-Length": Buffer.byteLength(corp),
      },
    }, (res) => {
      let text = "";
      res.setEncoding("utf8");
      res.on("data", (bucata) => { text += bucata; });
      res.on("end", () => {
        try {
          rezolva(JSON.parse(text));
        } catch (e) {
          respinge(new Error("Răspuns neașteptat de la aplicație."));
        }
      });
    });
    req.on("timeout", () => req.destroy(new Error("Aplicația nu a răspuns la timp.")));
    req.on("error", respinge);
    req.end(corp);
  });
}

async function genereaza() {
  const vreauSrt = document.getElementById("srt").checked;
  const vreauOverlay = document.getElementById("overlay").checked;
  if (!vreauSrt && !vreauOverlay) {
    arataStare("Bifează cel puțin o opțiune.", "eroare");
    return;
  }
  butonGenereaza.disabled = true;
  try {
    try {
      const stare = await cerere("GET", "/api/stare", null, 5000);
      if (!stare.ok) throw new Error(stare.eroare || "");
    } catch (e) {
      throw new Error("Aplicația Subtitrări RO nu răspunde. Deschide-o și bifează " +
        "„Conexiune cu DaVinci și Premiere”.");
    }

    const info = JSON.parse(await evalScript("subtitrariInfoSecventa()"));
    if (info.eroare) throw new Error(info.eroare);
    if (!info.clipuri.length) throw new Error("Secvența nu are clipuri audio active.");

    const folderBaza = info.folderProiect || path.dirname(info.clipuri[0].cale);
    const folder = path.join(folderBaza, "Subtitrari RO");
    arataStare(`Transcriu ${info.clipuri.length} clipuri audio (${info.durata.toFixed(1)} s). ` +
      "Poate dura câteva minute…");

    const raspuns = await cerere("POST", "/api/genereaza", {
      clipuri: info.clipuri,
      durata: info.durata,
      latime: info.latime,
      inaltime: info.inaltime,
      fps: info.fps,
      folder: folder,
      nume: info.nume,
      formate: vreauSrt ? ["srt"] : [],
      overlay: vreauOverlay,
    }, 6 * 3600 * 1000);
    if (!raspuns.ok) throw new Error(raspuns.eroare || "Generarea a eșuat.");

    const srt = vreauSrt ? (raspuns.fisiere.srt || "") : "";
    const mov = vreauOverlay ? (raspuns.fisiere.mov || "") : "";
    const rezultat = JSON.parse(await evalScript(
      `subtitrariImporta(${JSON.stringify(srt)}, ${JSON.stringify(mov)})`));
    if (rezultat.eroare) throw new Error(rezultat.eroare);
    arataStare(`Gata: ${raspuns.subtitrari} subtitrări. ${rezultat.mesaj}\nFișierele sunt în: ${folder}`, "ok");
  } catch (e) {
    arataStare(e.message, "eroare");
  } finally {
    butonGenereaza.disabled = false;
  }
}

butonGenereaza.addEventListener("click", genereaza);
