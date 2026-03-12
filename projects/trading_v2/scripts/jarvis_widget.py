"""
J.A.R.V.I.S. WIDGET v1.0 - Panneau Flottant Bureau
Mini-widget always-on-top, draggable, avec boutons de lancement rapide.
Coin bas-droit de l'ecran. Double-clic titre pour plier/deplier.
"""
import tkinter as tk
import subprocess
import os
import sys
import sqlite3
from datetime import datetime

ROOT = r"/home/turbo\TRADING_V2_PRODUCTION"
LAUNCHERS = os.path.join(ROOT, "launchers")
SCRIPTS = os.path.join(ROOT, "scripts")
VOICE = os.path.join(ROOT, "voice_system")
DB_PATH = os.path.join(ROOT, "database", "trading.db")

# Python absolu (evite alias Windows Store)
PYTHON_EXE = sys.executable

# Couleurs
BG = "#0d1117"
BG_BTN = "#161b22"
FG = "#c9d1d9"
ACCENT = "#58a6ff"
GREEN = "#3fb950"
RED = "#f85149"
PURPLE = "#bc8cff"
ORANGE = "#d29922"
BORDER = "#30363d"


class JarvisWidget:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("J.A.R.V.I.S.")
        self.root.attributes('-topmost', True)
        self.root.configure(bg=BG)
        self.root.resizable(False, False)

        self.collapsed = False
        self.processes = {}  # nom -> Popen

        # Position: bas-droit de l'ecran
        self.width = 220
        self.height = 500
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = screen_w - self.width - 30
        y = screen_h - self.height - 80
        self.root.geometry(f"{self.width}x{self.height}+{x}+{y}")

        # Force visible
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

        # Drag support
        self._drag_data = {"x": 0, "y": 0}

        self._build_ui()
        self._update_status()

    def _build_ui(self):
        """Construit l'interface complete"""
        # TITRE (draggable + double-clic = collapse)
        self.title_bar = tk.Frame(self.root, bg="#1f6feb", height=30, cursor="fleur")
        self.title_bar.pack(fill='x')
        self.title_bar.pack_propagate(False)

        self.lbl_title = tk.Label(
            self.title_bar, text="J.A.R.V.I.S.", bg="#1f6feb", fg="white",
            font=("Segoe UI", 10, "bold")
        )
        self.lbl_title.pack(side='left', padx=8)

        # Bouton fermer
        btn_close = tk.Label(
            self.title_bar, text="X", bg="#1f6feb", fg="white",
            font=("Consolas", 10, "bold"), cursor="hand2"
        )
        btn_close.pack(side='right', padx=8)
        btn_close.bind("<Button-1>", lambda e: self.root.destroy())

        # Drag events
        self.title_bar.bind("<Button-1>", self._start_drag)
        self.title_bar.bind("<B1-Motion>", self._on_drag)
        self.lbl_title.bind("<Button-1>", self._start_drag)
        self.lbl_title.bind("<B1-Motion>", self._on_drag)
        self.lbl_title.bind("<Double-1>", self._toggle_collapse)

        # CONTENU (colapsable)
        self.content = tk.Frame(self.root, bg=BG)
        self.content.pack(fill='both', expand=True)

        # Status line
        self.lbl_status = tk.Label(
            self.content, text="STANDBY", bg=BG, fg=ORANGE,
            font=("Consolas", 8)
        )
        self.lbl_status.pack(pady=(5, 2))

        # Separateur
        tk.Frame(self.content, bg=BORDER, height=1).pack(fill='x', padx=10, pady=2)

        # --- SECTION: JARVIS ---
        self._section_label("JARVIS")
        self._btn("Command Center", ACCENT, self._launch_gui)
        self._btn("Voice PTT", GREEN, self._launch_voice)
        self._btn("Mode Clavier", FG, self._launch_keyboard)

        # Separateur
        tk.Frame(self.content, bg=BORDER, height=1).pack(fill='x', padx=10, pady=3)

        # --- SECTION: TRADING ---
        self._section_label("TRADING")
        self._btn("Hyper Scan", RED, self._launch_scan)
        self._btn("Sniper", ORANGE, self._launch_sniper)
        self._btn("Pipeline 10", GREEN, self._launch_pipeline)
        self._btn("Monitor RIVER", ACCENT, self._launch_river)
        self._btn("Trident", PURPLE, self._launch_trident)

        # Separateur
        tk.Frame(self.content, bg=BORDER, height=1).pack(fill='x', padx=10, pady=3)

        # --- SECTION: QUICK ---
        self._section_label("RAPIDE")
        self._btn("Electron App", PURPLE, self._launch_electron)

        # Footer
        self.lbl_footer = tk.Label(
            self.content, text="", bg=BG, fg="#484f58",
            font=("Consolas", 7)
        )
        self.lbl_footer.pack(side='bottom', pady=3)

    def _section_label(self, text):
        tk.Label(
            self.content, text=text, bg=BG, fg="#484f58",
            font=("Segoe UI", 7, "bold")
        ).pack(anchor='w', padx=12, pady=(4, 0))

    def _btn(self, text, color, command):
        btn = tk.Label(
            self.content, text=text, bg=BG_BTN, fg=color,
            font=("Segoe UI", 9), cursor="hand2",
            padx=10, pady=3, anchor='w',
            relief='flat', borderwidth=0
        )
        btn.pack(fill='x', padx=8, pady=1)
        btn.bind("<Button-1>", lambda e: command())
        btn.bind("<Enter>", lambda e: btn.config(bg="#21262d"))
        btn.bind("<Leave>", lambda e: btn.config(bg=BG_BTN))

    # ================================================================
    # DRAG
    # ================================================================

    def _start_drag(self, event):
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y

    def _on_drag(self, event):
        x = self.root.winfo_x() + event.x - self._drag_data["x"]
        y = self.root.winfo_y() + event.y - self._drag_data["y"]
        self.root.geometry(f"+{x}+{y}")

    def _toggle_collapse(self, event=None):
        self.collapsed = not self.collapsed
        if self.collapsed:
            self.content.pack_forget()
            self.root.geometry(f"{self.width}x30")
            self.lbl_title.config(text="J.A.R.V.I.S. [+]")
        else:
            self.content.pack(fill='both', expand=True)
            self.root.geometry(f"{self.width}x{self.height}")
            self.lbl_title.config(text="J.A.R.V.I.S.")

    # ================================================================
    # LAUNCHERS
    # ================================================================

    def _launch(self, name, bat_name=None, script=None):
        """Lance un script dans une nouvelle fenetre CMD"""
        self.lbl_status.config(text=f"LAUNCHING: {name}", fg=GREEN)

        if bat_name:
            path = os.path.join(LAUNCHERS, bat_name)
            if os.path.exists(path):
                proc = subprocess.Popen(f'start "{name}" cmd /k "{path}"', shell=True)
                self.processes[name] = proc
        elif script:
            proc = subprocess.Popen(
                f'start "{name}" cmd /k "{PYTHON_EXE}" -u "{script}"', shell=True
            )
            self.processes[name] = proc

        self.root.after(2000, lambda: self.lbl_status.config(text="READY", fg=GREEN))

    def _launch_gui(self):
        self._launch("GUI", bat_name="JARVIS_GUI.bat")

    def _launch_voice(self):
        self._launch("Voice", bat_name="JARVIS_VOICE.bat")

    def _launch_keyboard(self):
        self._launch("Keyboard", bat_name="JARVIS_KEYBOARD.bat")

    def _launch_scan(self):
        self._launch("Scan", bat_name="SCAN_HYPER.bat")

    def _launch_sniper(self):
        self._launch("Sniper", bat_name="SNIPER.bat")

    def _launch_pipeline(self):
        self._launch("Pipeline", bat_name="PIPELINE_10.bat")

    def _launch_river(self):
        self._launch("River", bat_name="MONITOR_RIVER.bat")

    def _launch_trident(self):
        self._launch("Trident", bat_name="TRIDENT.bat")

    def _launch_electron(self):
        electron_dir = os.path.join(ROOT, "electron-app")
        pkg_json = os.path.join(electron_dir, "package.json")
        if os.path.exists(pkg_json):
            subprocess.Popen(f'start cmd /k "cd /d {electron_dir} && npm start"', shell=True)
            self.lbl_status.config(text="ELECTRON: starting...", fg=PURPLE)
        else:
            self.lbl_status.config(text="ELECTRON: not installed", fg=RED)

    # ================================================================
    # STATUS
    # ================================================================

    def _update_status(self):
        """Met a jour le footer avec l'heure et stats DB"""
        now = datetime.now().strftime("%H:%M")
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM command_history")
            cmds = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM learned_patterns")
            patterns = cur.fetchone()[0]
            conn.close()
            self.lbl_footer.config(text=f"{now} | {cmds} cmds | {patterns} patterns")
        except Exception:
            self.lbl_footer.config(text=f"{now}")

        self.root.after(30000, self._update_status)  # Refresh toutes les 30s

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    widget = JarvisWidget()
    widget.run()
