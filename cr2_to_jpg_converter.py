import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import sys
import webbrowser

# ── dependency check ────────────────────────────────────────────────────────
MISSING = []
try:
    import rawpy
except ImportError:
    MISSING.append("rawpy")
try:
    from PIL import Image
except ImportError:
    MISSING.append("Pillow")

# ── colour palette ───────────────────────────────────────────────────────────
BG        = "#1a1a2e"
PANEL     = "#16213e"
ACCENT    = "#e94560"
ACCENT2   = "#0f3460"
TEXT      = "#eaeaea"
TEXT_DIM  = "#7a7a9a"
SUCCESS   = "#4caf50"
WARNING   = "#ff9800"
ENTRY_BG  = "#0d1b2a"
RADIUS    = 8

# ── fonts ────────────────────────────────────────────────────────────────────
FONT_H1   = ("Segoe UI", 20, "bold")
FONT_H2   = ("Segoe UI", 12, "bold")
FONT_BODY = ("Segoe UI", 10)
FONT_SMALL= ("Segoe UI", 9)
FONT_MONO = ("Consolas", 9)


class CR2Converter(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CR2 → JPG Converter")
        self.geometry("820x640")
        self.resizable(True, True)
        self.configure(bg=BG)
        self.minsize(700, 540)

        self.files: list[str] = []
        self.output_dir = tk.StringVar(value="")
        self.quality    = tk.IntVar(value=92)
        self.keep_exif  = tk.BooleanVar(value=True)
        self.running    = False
        self.stop_flag  = False

        self._build_ui()

        if MISSING:
            self._show_install_dialog()

    # ── UI construction ───────────────────────────────────────────────────────
    def _build_ui(self):
        # ── header
        hdr = tk.Frame(self, bg=ACCENT2, pady=14)
        hdr.pack(fill="x")
        tk.Label(hdr, text="⬡  CR2 → JPG Converter",
                 font=FONT_H1, bg=ACCENT2, fg=TEXT).pack(side="left", padx=22)
        tk.Label(hdr, text="Canon RAW Batch Converter",
                 font=FONT_SMALL, bg=ACCENT2, fg=TEXT_DIM).pack(side="left", padx=4)

        # TIBorWeb branding – right side of header
        brand_frame = tk.Frame(hdr, bg=ACCENT2)
        brand_frame.pack(side="right", padx=20)
        tk.Label(brand_frame, text="by", font=FONT_SMALL,
                 bg=ACCENT2, fg=TEXT_DIM).pack(side="left", padx=(0, 4))
        link = tk.Label(brand_frame, text="TIBorWeb",
                        font=("Segoe UI", 11, "bold"), bg=ACCENT2, fg=ACCENT,
                        cursor="hand2")
        link.pack(side="left")
        link.bind("<Button-1>", lambda e: webbrowser.open("https://tiborweb.de"))
        link.bind("<Enter>", lambda e: link.config(fg="#ff8fa8", font=("Segoe UI", 11, "bold underline")))
        link.bind("<Leave>", lambda e: link.config(fg=ACCENT, font=("Segoe UI", 11, "bold")))

        # ── main two-column layout
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=16, pady=12)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        left  = tk.Frame(body, bg=BG)
        right = tk.Frame(body, bg=BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0,8))
        right.grid(row=0, column=1, sticky="nsew")

        self._build_file_panel(left)
        self._build_settings_panel(right)

        # ── bottom bar
        self._build_bottom_bar()

    def _build_file_panel(self, parent):
        parent.rowconfigure(1, weight=1)
        parent.columnconfigure(0, weight=1)

        # label row
        lbl_row = tk.Frame(parent, bg=BG)
        lbl_row.grid(row=0, column=0, sticky="ew", pady=(0,6))
        tk.Label(lbl_row, text="CR2 Dateien", font=FONT_H2,
                 bg=BG, fg=TEXT).pack(side="left")
        self.count_lbl = tk.Label(lbl_row, text="0 Dateien",
                                   font=FONT_SMALL, bg=BG, fg=TEXT_DIM)
        self.count_lbl.pack(side="right")

        # drop / list frame
        frame = tk.Frame(parent, bg=PANEL, bd=0, highlightthickness=2,
                         highlightbackground=ACCENT2,
                         highlightcolor=ACCENT)
        frame.grid(row=1, column=0, sticky="nsew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        # listbox + scrollbar
        sb = tk.Scrollbar(frame)
        sb.grid(row=0, column=1, sticky="ns", padx=(0,2), pady=2)
        self.listbox = tk.Listbox(
            frame,
            yscrollcommand=sb.set,
            bg=PANEL, fg=TEXT, selectbackground=ACCENT, selectforeground=TEXT,
            font=FONT_MONO, borderwidth=0, highlightthickness=0,
            activestyle="none", relief="flat"
        )
        self.listbox.grid(row=0, column=0, sticky="nsew", padx=(4,0), pady=4)
        sb.config(command=self.listbox.yview)

        # drag-hint label (hidden when files exist)
        self.hint_lbl = tk.Label(
            frame,
            text="📂\n\nDateien hier ablegen\noder unten hinzufügen",
            font=FONT_BODY, bg=PANEL, fg=TEXT_DIM, justify="center"
        )
        self.hint_lbl.place(relx=0.5, rely=0.5, anchor="center")

        # button row
        btn_row = tk.Frame(parent, bg=BG)
        btn_row.grid(row=2, column=0, sticky="ew", pady=(6,0))
        self._btn(btn_row, "＋ Hinzufügen",  self._add_files,   ACCENT).pack(side="left", padx=(0,4))
        self._btn(btn_row, "📁 Ordner",       self._add_folder,  ACCENT2).pack(side="left", padx=(0,4))
        self._btn(btn_row, "✕ Entfernen",     self._remove_sel,  "#333355").pack(side="left", padx=(0,4))
        self._btn(btn_row, "⬜ Alle löschen",  self._clear_files, "#333355").pack(side="left")

    def _build_settings_panel(self, parent):
        parent.columnconfigure(0, weight=1)

        tk.Label(parent, text="Einstellungen", font=FONT_H2,
                 bg=BG, fg=TEXT).grid(row=0, column=0, sticky="w", pady=(0,6))

        card = tk.Frame(parent, bg=PANEL, padx=14, pady=12)
        card.grid(row=1, column=0, sticky="ew")
        card.columnconfigure(1, weight=1)

        # output directory
        tk.Label(card, text="Ausgabe-Ordner", font=FONT_SMALL,
                 bg=PANEL, fg=TEXT_DIM).grid(row=0, column=0, columnspan=2, sticky="w")
        out_row = tk.Frame(card, bg=PANEL)
        out_row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(2,10))
        out_row.columnconfigure(0, weight=1)
        self.out_entry = tk.Entry(out_row, textvariable=self.output_dir,
                                   font=FONT_SMALL, bg=ENTRY_BG, fg=TEXT,
                                   insertbackground=TEXT, relief="flat",
                                   highlightthickness=1, highlightbackground=ACCENT2)
        self.out_entry.grid(row=0, column=0, sticky="ew", ipady=4, padx=(0,4))
        self._btn(out_row, "…", self._choose_output, ACCENT2, width=3).grid(row=0, column=1)

        # quality
        tk.Label(card, text="JPEG Qualität", font=FONT_SMALL,
                 bg=PANEL, fg=TEXT_DIM).grid(row=2, column=0, sticky="w")
        self.qual_val_lbl = tk.Label(card, text=f"{self.quality.get()} %",
                                      font=FONT_SMALL, bg=PANEL, fg=ACCENT, width=5)
        self.qual_val_lbl.grid(row=2, column=1, sticky="e")
        q_slider = tk.Scale(card, from_=50, to=100, orient="horizontal",
                             variable=self.quality, command=self._update_qual_lbl,
                             bg=PANEL, fg=TEXT, troughcolor=ENTRY_BG,
                             activebackground=ACCENT, highlightthickness=0,
                             sliderrelief="flat", bd=0, length=160)
        q_slider.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0,10))

        # EXIF
        self._checkbox(card, "EXIF-Daten beibehalten", self.keep_exif).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(0,4))

        # output mode
        tk.Label(card, text="Speichern in …", font=FONT_SMALL,
                 bg=PANEL, fg=TEXT_DIM).grid(row=5, column=0, columnspan=2,
                                              sticky="w", pady=(6,2))
        self.out_mode = tk.StringVar(value="same")
        modes = [("Gleichem Ordner wie CR2", "same"),
                 ("Gewähltem Ausgabe-Ordner",  "custom")]
        for i, (label, val) in enumerate(modes):
            rb = tk.Radiobutton(card, text=label, variable=self.out_mode, value=val,
                                 font=FONT_SMALL, bg=PANEL, fg=TEXT,
                                 selectcolor=ACCENT2, activebackground=PANEL,
                                 activeforeground=TEXT, relief="flat")
            rb.grid(row=6+i, column=0, columnspan=2, sticky="w")

        # ── progress section
        tk.Label(parent, text="Fortschritt", font=FONT_H2,
                 bg=BG, fg=TEXT).grid(row=2, column=0, sticky="w", pady=(16,6))

        prog_card = tk.Frame(parent, bg=PANEL, padx=14, pady=12)
        prog_card.grid(row=3, column=0, sticky="ew")
        prog_card.columnconfigure(0, weight=1)

        self.prog_bar = ttk.Progressbar(prog_card, mode="determinate", length=200)
        self._style_progressbar()
        self.prog_bar.grid(row=0, column=0, sticky="ew", pady=(0,6))

        self.prog_lbl = tk.Label(prog_card, text="Bereit", font=FONT_SMALL,
                                  bg=PANEL, fg=TEXT_DIM)
        self.prog_lbl.grid(row=1, column=0, sticky="w")

        self.status_lbl = tk.Label(prog_card, text="",
                                    font=FONT_SMALL, bg=PANEL, fg=TEXT_DIM,
                                    wraplength=220, justify="left")
        self.status_lbl.grid(row=2, column=0, sticky="w", pady=(4,0))

    def _build_bottom_bar(self):
        bar = tk.Frame(self, bg=ACCENT2, pady=10)
        bar.pack(fill="x", side="bottom")
        self._btn(bar, "▶  Konvertierung starten",
                  self._start, ACCENT, padx=18).pack(side="right", padx=14)
        self.stop_btn = self._btn(bar, "■  Stopp", self._stop, "#555577", padx=12)
        self.stop_btn.pack(side="right", padx=(0,6))
        self.stop_btn.config(state="disabled")

        # bottom-left: copyright + link
        footer_frame = tk.Frame(bar, bg=ACCENT2)
        footer_frame.pack(side="left", padx=14)
        tk.Label(footer_frame, text="© 2025 TIBorWeb  |  ",
                 font=FONT_SMALL, bg=ACCENT2, fg=TEXT_DIM).pack(side="left")
        footer_link = tk.Label(footer_frame, text="tiborweb.de",
                                font=("Segoe UI", 9, "underline"), bg=ACCENT2,
                                fg=ACCENT, cursor="hand2")
        footer_link.pack(side="left")
        footer_link.bind("<Button-1>", lambda e: webbrowser.open("https://tiborweb.de"))
        footer_link.bind("<Enter>", lambda e: footer_link.config(fg="#ff8fa8"))
        footer_link.bind("<Leave>", lambda e: footer_link.config(fg=ACCENT))

    # ── helper widgets ────────────────────────────────────────────────────────
    def _btn(self, parent, text, cmd, color, padx=10, width=None):
        b = tk.Button(parent, text=text, command=cmd,
                      bg=color, fg=TEXT, font=FONT_BODY,
                      relief="flat", padx=padx, cursor="hand2",
                      activebackground=ACCENT, activeforeground=TEXT,
                      bd=0)
        if width:
            b.config(width=width)
        return b

    def _checkbox(self, parent, text, var):
        return tk.Checkbutton(parent, text=text, variable=var,
                               font=FONT_SMALL, bg=PANEL, fg=TEXT,
                               selectcolor=ACCENT, activebackground=PANEL,
                               activeforeground=TEXT, relief="flat")

    def _style_progressbar(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TProgressbar",
                         troughcolor=ENTRY_BG, background=ACCENT,
                         bordercolor=PANEL, lightcolor=ACCENT, darkcolor=ACCENT)

    def _update_qual_lbl(self, _=None):
        self.qual_val_lbl.config(text=f"{self.quality.get()} %")

    # ── file management ───────────────────────────────────────────────────────
    def _add_files(self):
        paths = filedialog.askopenfilenames(
            title="CR2 Dateien auswählen",
            filetypes=[("Canon RAW", "*.cr2 *.CR2"), ("Alle Dateien", "*.*")]
        )
        for p in paths:
            if p not in self.files:
                self.files.append(p)
        self._refresh_list()

    def _add_folder(self):
        folder = filedialog.askdirectory(title="Ordner mit CR2 Dateien wählen")
        if folder:
            for fn in os.listdir(folder):
                if fn.lower().endswith(".cr2"):
                    full = os.path.join(folder, fn)
                    if full not in self.files:
                        self.files.append(full)
        self._refresh_list()

    def _remove_sel(self):
        sel = list(self.listbox.curselection())
        for i in reversed(sel):
            del self.files[i]
        self._refresh_list()

    def _clear_files(self):
        self.files.clear()
        self._refresh_list()

    def _refresh_list(self):
        self.listbox.delete(0, "end")
        for f in self.files:
            self.listbox.insert("end", os.path.basename(f))
        n = len(self.files)
        self.count_lbl.config(text=f"{n} Datei{'en' if n!=1 else ''}")
        if n:
            self.hint_lbl.place_forget()
        else:
            self.hint_lbl.place(relx=0.5, rely=0.5, anchor="center")

    def _choose_output(self):
        d = filedialog.askdirectory(title="Ausgabe-Ordner wählen")
        if d:
            self.output_dir.set(d)
            self.out_mode.set("custom")

    # ── conversion ────────────────────────────────────────────────────────────
    def _start(self):
        if MISSING:
            self._show_install_dialog(); return
        if not self.files:
            messagebox.showwarning("Keine Dateien", "Bitte zuerst CR2 Dateien hinzufügen."); return
        if self.out_mode.get() == "custom" and not self.output_dir.get():
            messagebox.showwarning("Kein Ausgabe-Ordner",
                                   "Bitte einen Ausgabe-Ordner wählen oder\n'Gleichem Ordner' aktivieren."); return
        self.running   = True
        self.stop_flag = False
        self.stop_btn.config(state="normal")
        threading.Thread(target=self._convert_worker, daemon=True).start()

    def _stop(self):
        self.stop_flag = True
        self.prog_lbl.config(text="Wird gestoppt …", fg=WARNING)

    def _convert_worker(self):
        total   = len(self.files)
        success = 0
        errors  = []

        self.prog_bar["maximum"] = total
        self.prog_bar["value"]   = 0

        for idx, src in enumerate(self.files):
            if self.stop_flag:
                break

            name = os.path.basename(src)
            self.after(0, lambda n=name, i=idx: (
                self.prog_lbl.config(text=f"{i+1}/{total}  –  {n}", fg=TEXT_DIM),
                self.prog_bar.config(value=i)
            ))

            # determine output path
            if self.out_mode.get() == "custom":
                out_dir = self.output_dir.get()
            else:
                out_dir = os.path.dirname(src)

            out_path = os.path.join(out_dir,
                                    os.path.splitext(name)[0] + ".jpg")

            try:
                with rawpy.imread(src) as raw:
                    rgb = raw.postprocess(
                        use_camera_wb=True,
                        half_size=False,
                        no_auto_bright=False,
                        output_bps=8
                    )
                img = Image.fromarray(rgb)

                save_kwargs = {"quality": self.quality.get(), "optimize": True}

                # copy EXIF if requested
                if self.keep_exif.get():
                    try:
                        import piexif
                        exif = piexif.load(src)
                        save_kwargs["exif"] = piexif.dump(exif)
                    except Exception:
                        pass   # piexif optional

                img.save(out_path, "JPEG", **save_kwargs)
                success += 1

            except Exception as e:
                errors.append(f"{name}: {e}")

            self.after(0, lambda v=idx+1: self.prog_bar.config(value=v))

        self.running = False
        self.after(0, lambda: self._done(success, errors, total))

    def _done(self, success, errors, total):
        self.stop_btn.config(state="disabled")
        stopped = self.stop_flag

        if errors:
            self.status_lbl.config(
                text="⚠  " + "\n".join(errors[:3]) +
                     (f"\n…und {len(errors)-3} weitere" if len(errors)>3 else ""),
                fg=WARNING)
        else:
            self.status_lbl.config(text="", fg=TEXT_DIM)

        if stopped:
            self.prog_lbl.config(
                text=f"Gestoppt – {success}/{total} konvertiert", fg=WARNING)
        else:
            self.prog_lbl.config(
                text=f"✔  {success}/{total} erfolgreich konvertiert", fg=SUCCESS)
            if not errors:
                messagebox.showinfo("Fertig!",
                    f"{success} Datei(en) erfolgreich konvertiert. 🎉")

    # ── install helper ────────────────────────────────────────────────────────
    def _show_install_dialog(self):
        dlg = tk.Toplevel(self)
        dlg.title("Fehlende Pakete"); dlg.configure(bg=BG)
        dlg.geometry("460x260"); dlg.grab_set()
        tk.Label(dlg, text="⚠  Fehlende Bibliotheken",
                 font=FONT_H2, bg=BG, fg=ACCENT).pack(pady=(18,6))
        tk.Label(dlg,
                 text="Folgende Python-Pakete werden benötigt\nund müssen einmalig installiert werden:",
                 font=FONT_BODY, bg=BG, fg=TEXT).pack()
        pkg_str = "  •  " + "\n  •  ".join(MISSING)
        tk.Label(dlg, text=pkg_str, font=FONT_MONO, bg=PANEL, fg=ACCENT,
                 padx=14, pady=8).pack(fill="x", padx=24, pady=8)
        cmd = f"pip install {' '.join(MISSING)}"
        tk.Label(dlg, text=f"Terminal-Befehl:\n{cmd}",
                 font=FONT_MONO, bg=BG, fg=TEXT_DIM).pack()
        def copy_cmd():
            self.clipboard_clear()
            self.clipboard_append(cmd)
            messagebox.showinfo("Kopiert", f"Befehl in Zwischenablage:\n{cmd}", parent=dlg)
        self._btn(dlg, "📋 Befehl kopieren", copy_cmd, ACCENT, padx=16).pack(pady=(10,0))


# ── entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = CR2Converter()
    app.mainloop()
