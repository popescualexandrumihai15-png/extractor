import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import shutil
from pathlib import Path


class AplicatieExtractiePoze:
    def __init__(self, root):
        self.root = root
        self.root.title("Extractor Poze")
        self.root.geometry("750x580")
        self.root.resizable(True, True)
        self.root.configure(bg="#f0f0f0")

        # Variables
        self.folder_poze = tk.StringVar()
        self.folder_destinatie = tk.StringVar()
        self.fisier_lista = tk.StringVar()
        self.stare = tk.StringVar(value="Gata de utilizare.")

        self._construieste_ui()

    def _construieste_ui(self):
        # ── Title ──────────────────────────────────────────────
        titlu = tk.Label(
            self.root, text="🖼  Extractor Poze",
            font=("Segoe UI", 18, "bold"),
            bg="#f0f0f0", fg="#2c3e50"
        )
        titlu.pack(pady=(18, 4))

        subtitlu = tk.Label(
            self.root,
            text="Selectează folderul cu poze, lista de nume și folderul destinație",
            font=("Segoe UI", 9), bg="#f0f0f0", fg="#7f8c8d"
        )
        subtitlu.pack(pady=(0, 12))

        # ── Paths frame ────────────────────────────────────────
        frame_cai = tk.LabelFrame(
            self.root, text="  Configurare  ",
            font=("Segoe UI", 9, "bold"),
            bg="#f0f0f0", fg="#2c3e50", padx=10, pady=8
        )
        frame_cai.pack(fill="x", padx=20, pady=(0, 10))

        self._rand_cale(frame_cai, "Folder poze:", self.folder_poze,
                        lambda: self._alege_folder(self.folder_poze), row=0)
        self._rand_cale(frame_cai, "Fișier listă (.txt):", self.fisier_lista,
                        lambda: self._alege_fisier(self.fisier_lista), row=1)
        self._rand_cale(frame_cai, "Folder destinație:", self.folder_destinatie,
                        lambda: self._alege_folder(self.folder_destinatie), row=2)

        # ── Buttons: load list ─────────────────────────────────
        btn_frame_top = tk.Frame(self.root, bg="#f0f0f0")
        btn_frame_top.pack(fill="x", padx=20, pady=(0, 6))

        tk.Button(
            btn_frame_top, text="📂  Încarcă lista",
            command=self._incarca_lista,
            font=("Segoe UI", 9, "bold"),
            bg="#3498db", fg="white", relief="flat",
            padx=14, pady=6, cursor="hand2"
        ).pack(side="left")

        tk.Button(
            btn_frame_top, text="✔  Selectează tot",
            command=self._selecteaza_tot,
            font=("Segoe UI", 9),
            bg="#95a5a6", fg="white", relief="flat",
            padx=14, pady=6, cursor="hand2"
        ).pack(side="left", padx=(8, 0))

        tk.Button(
            btn_frame_top, text="✘  Deselectează tot",
            command=self._deselecteaza_tot,
            font=("Segoe UI", 9),
            bg="#95a5a6", fg="white", relief="flat",
            padx=14, pady=6, cursor="hand2"
        ).pack(side="left", padx=(8, 0))

        # ── List frame ─────────────────────────────────────────
        frame_lista = tk.LabelFrame(
            self.root, text="  Poze din listă (bifează ce vrei să copiezi)  ",
            font=("Segoe UI", 9, "bold"),
            bg="#f0f0f0", fg="#2c3e50", padx=6, pady=6
        )
        frame_lista.pack(fill="both", expand=True, padx=20, pady=(0, 8))

        scroll_y = tk.Scrollbar(frame_lista, orient="vertical")
        scroll_y.pack(side="right", fill="y")

        self.listbox = tk.Listbox(
            frame_lista,
            selectmode="multiple",
            font=("Segoe UI", 10),
            bg="white", fg="#2c3e50",
            selectbackground="#3498db",
            selectforeground="white",
            activestyle="none",
            relief="flat",
            highlightthickness=1,
            highlightcolor="#3498db",
            yscrollcommand=scroll_y.set
        )
        self.listbox.pack(fill="both", expand=True)
        scroll_y.config(command=self.listbox.yview)

        # ── Bottom buttons ─────────────────────────────────────
        btn_frame_bot = tk.Frame(self.root, bg="#f0f0f0")
        btn_frame_bot.pack(fill="x", padx=20, pady=(0, 6))

        tk.Button(
            btn_frame_bot, text="📋  Copiază pozele selectate",
            command=self._copiaza_poze,
            font=("Segoe UI", 10, "bold"),
            bg="#27ae60", fg="white", relief="flat",
            padx=18, pady=8, cursor="hand2"
        ).pack(side="left")

        tk.Button(
            btn_frame_bot, text="🚪  Ieșire",
            command=self._iesire,
            font=("Segoe UI", 10, "bold"),
            bg="#e74c3c", fg="white", relief="flat",
            padx=18, pady=8, cursor="hand2"
        ).pack(side="right")

        # ── Progress bar ───────────────────────────────────────
        self.progress = ttk.Progressbar(
            self.root, orient="horizontal", mode="determinate", length=100
        )
        self.progress.pack(fill="x", padx=20, pady=(0, 4))

        # ── Status bar ─────────────────────────────────────────
        tk.Label(
            self.root, textvariable=self.stare,
            font=("Segoe UI", 9), bg="#dfe6e9", fg="#2c3e50",
            anchor="w", padx=10, pady=4
        ).pack(fill="x", side="bottom")

    # ── Helper: single path row ────────────────────────────────
    def _rand_cale(self, parent, label_text, var, command, row):
        tk.Label(
            parent, text=label_text,
            font=("Segoe UI", 9), bg="#f0f0f0", fg="#2c3e50", width=20, anchor="w"
        ).grid(row=row, column=0, sticky="w", pady=3)

        tk.Entry(
            parent, textvariable=var,
            font=("Segoe UI", 9), width=46,
            relief="solid", bd=1
        ).grid(row=row, column=1, sticky="ew", padx=(4, 6), pady=3)

        tk.Button(
            parent, text="Răsfoiește…",
            command=command,
            font=("Segoe UI", 8),
            bg="#ecf0f1", relief="flat",
            padx=8, pady=3, cursor="hand2"
        ).grid(row=row, column=2, pady=3)

        parent.columnconfigure(1, weight=1)

    # ── Dialog helpers ─────────────────────────────────────────
    def _alege_folder(self, var):
        path = filedialog.askdirectory(title="Selectează folderul")
        if path:
            var.set(path)

    def _alege_fisier(self, var):
        path = filedialog.askopenfilename(
            title="Selectează fișierul listă",
            filetypes=[("Fișiere text", "*.txt"), ("Toate fișierele", "*.*")]
        )
        if path:
            var.set(path)

    # ── Load list from .txt ────────────────────────────────────
    def _incarca_lista(self):
        fisier = self.fisier_lista.get().strip()
        if not fisier:
            messagebox.showwarning("Atenție", "Selectează mai întâi un fișier listă (.txt).")
            return
        if not os.path.isfile(fisier):
            messagebox.showerror("Eroare", f"Fișierul nu a fost găsit:\n{fisier}")
            return

        try:
            with open(fisier, "r", encoding="utf-8") as f:
                linii = [l.strip() for l in f if l.strip()]
        except Exception as e:
            messagebox.showerror("Eroare la citire", str(e))
            return

        self.listbox.delete(0, tk.END)
        for linie in linii:
            self.listbox.insert(tk.END, linie)

        self.stare.set(f"Listă încărcată: {len(linii)} intrări.")

    # ── Select / deselect all ──────────────────────────────────
    def _selecteaza_tot(self):
        self.listbox.select_set(0, tk.END)

    def _deselecteaza_tot(self):
        self.listbox.select_clear(0, tk.END)

    # ── Copy selected photos ───────────────────────────────────
    def _copiaza_poze(self):
        folder_sursa = self.folder_poze.get().strip()
        folder_dest  = self.folder_destinatie.get().strip()

        if not folder_sursa:
            messagebox.showwarning("Atenție", "Selectează folderul cu poze.")
            return
        if not folder_dest:
            messagebox.showwarning("Atenție", "Selectează folderul destinație.")
            return
        if not os.path.isdir(folder_sursa):
            messagebox.showerror("Eroare", f"Folderul cu poze nu există:\n{folder_sursa}")
            return

        selectate = self.listbox.curselection()
        if not selectate:
            messagebox.showwarning("Atenție", "Nicio poză selectată din listă.")
            return

        os.makedirs(folder_dest, exist_ok=True)

        copiate, negasite = 0, []

        self.progress["maximum"] = len(selectate)
        self.progress["value"] = 0

        for i, idx in enumerate(selectate):
            nume = self.listbox.get(idx).strip()
            sursa = os.path.join(folder_sursa, nume)

            if os.path.isfile(sursa):
                dest = os.path.join(folder_dest, nome_unic(folder_dest, nume))
                shutil.copy2(sursa, dest)
                copiate += 1
            else:
                # Try case-insensitive search
                found = _cauta_case_insensitive(folder_sursa, nume)
                if found:
                    dest = os.path.join(folder_dest, nome_unic(folder_dest, os.path.basename(found)))
                    shutil.copy2(found, dest)
                    copiate += 1
                else:
                    negasite.append(nume)

            self.progress["value"] = i + 1
            self.root.update_idletasks()

        # Summary
        msg = f"Copiate: {copiate} poze."
        if negasite:
            msg += f"\n\nNegăsite ({len(negasite)}):\n" + "\n".join(negasite[:20])
            if len(negasite) > 20:
                msg += f"\n... și încă {len(negasite)-20}"
            messagebox.showwarning("Finalizat cu avertismente", msg)
        else:
            messagebox.showinfo("Finalizat", msg)

        self.stare.set(f"Gata! {copiate} poze copiate în: {folder_dest}")

    # ── Exit ───────────────────────────────────────────────────
    def _iesire(self):
        if messagebox.askyesno("Ieșire", "Ești sigur că vrei să închizi aplicația?"):
            self.root.destroy()


# ── Utilities ──────────────────────────────────────────────────

def nome_unic(folder, nume):
    """Return a unique filename inside folder (adds _1, _2 … if name exists)."""
    dest = os.path.join(folder, nume)
    if not os.path.exists(dest):
        return nume
    stem = Path(nume).stem
    suffix = Path(nume).suffix
    contor = 1
    while True:
        nou = f"{stem}_{contor}{suffix}"
        if not os.path.exists(os.path.join(folder, nou)):
            return nou
        contor += 1


def _cauta_case_insensitive(folder, nume):
    """Search for a file in folder ignoring case."""
    try:
        for f in os.listdir(folder):
            if f.lower() == nume.lower():
                return os.path.join(folder, f)
    except Exception:
        pass
    return None


# ── Entry point ────────────────────────────────────────────────

if __name__ == "__main__":
    root = tk.Tk()
    app = AplicatieExtractiePoze(root)
    root.mainloop()
