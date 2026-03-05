"""
J.A.R.V.I.S. COMMAND CENTER v1.0 - Cockpit de Controle GUI
Interface Tkinter pour piloter JARVIS: commandes, micro, memoire, Genesis.
Branche: commander_v2.py (pipeline v3.5) + learned_patterns DB + workflow_engine.
"""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
import sys
import os
import sqlite3
import io
from datetime import datetime

ROOT_DIR = r"F:\BUREAU\TRADING_V2_PRODUCTION"
SYS_PATH = os.path.join(ROOT_DIR, "voice_system")
SCRIPTS_PATH = os.path.join(ROOT_DIR, "scripts")
DB_PATH = os.path.join(ROOT_DIR, "database", "trading.db")

sys.path.insert(0, SYS_PATH)
sys.path.insert(0, SCRIPTS_PATH)

# Import du Cerveau (Commander V2)
COMMANDER_OK = False
try:
    import commander_v2
    COMMANDER_OK = True
    print("  Cerveau connecte (commander_v2 v3.5)")
except Exception as e:
    print(f"  Erreur import commander_v2: {e}")

# TTS
TTS_OK = False
try:
    import pyttsx3
    _tts = pyttsx3.init()
    _tts.setProperty('rate', 180)
    for v in _tts.getProperty('voices'):
        if 'french' in v.name.lower() or 'fr' in v.id.lower():
            _tts.setProperty('voice', v.id)
            break
    TTS_OK = True
except:
    pass

# Hotkey globale (keyboard module)
KEYBOARD_OK = False
try:
    import keyboard
    KEYBOARD_OK = True
except:
    pass


class JarvisDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("J.A.R.V.I.S. COMMAND CENTER v1.0")
        self.root.geometry("1000x700")
        self.root.configure(bg="#1e1e1e")

        # Styles
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure("TFrame", background="#1e1e1e")
        self.style.configure("TLabel", background="#1e1e1e", foreground="white",
                             font=("Segoe UI", 10))
        self.style.configure("TButton", font=("Segoe UI", 10, "bold"),
                             background="#007acc", foreground="white")
        self.style.configure("TNotebook", background="#1e1e1e",
                             tabmargins=[2, 5, 2, 0])
        self.style.configure("TNotebook.Tab", background="#333", foreground="white",
                             padding=[10, 5])

        self.mic_active = False
        self.setup_ui()

        # Hotkey Ctrl+Espace
        if KEYBOARD_OK:
            keyboard.add_hotkey('ctrl+space', self._toggle_mic_safe)

        self.refresh_command_list()
        self.log("Systeme initialise. Pret.")
        status = []
        if COMMANDER_OK:
            status.append("Cerveau OK")
        if TTS_OK:
            status.append("TTS OK")
        if KEYBOARD_OK:
            status.append("Hotkey OK")
        self.log(f"  Modules: {', '.join(status)}")

    def setup_ui(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # TAB 1: PILOTAGE
        self.tab_pilot = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_pilot, text=" PILOTAGE LIVE ")
        self.setup_pilot_tab()

        # TAB 2: MEMOIRE & COMMANDES
        self.tab_memory = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_memory, text=" MEMOIRE & CONFIG ")
        self.setup_memory_tab()

        # TAB 3: STATS
        self.tab_stats = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_stats, text=" STATS & SANTE ")
        self.setup_stats_tab()

    def setup_pilot_tab(self):
        # Zone Haut: Status et Micro
        top_frame = tk.Frame(self.tab_pilot, bg="#1e1e1e")
        top_frame.pack(fill='x', pady=20)

        hotkey_label = " (Ctrl+Espace)" if KEYBOARD_OK else ""
        self.btn_mic = tk.Button(
            top_frame, text=f"MICRO OFF{hotkey_label}",
            bg="#cc0000", fg="white",
            font=("Segoe UI", 16, "bold"), height=2, width=28,
            command=self.toggle_mic)
        self.btn_mic.pack()

        # Console de Log
        log_frame = tk.LabelFrame(self.tab_pilot, text="Journal d'Activite",
                                  bg="#1e1e1e", fg="#00ccff",
                                  font=("Segoe UI", 10))
        log_frame.pack(fill='both', expand=True, padx=10, pady=10)

        self.console = tk.Text(log_frame, bg="#000", fg="#00ff00",
                               font=("Consolas", 10), state='disabled',
                               wrap='word')
        scrollbar = tk.Scrollbar(log_frame, command=self.console.yview)
        self.console.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self.console.pack(fill='both', expand=True, padx=5, pady=5)

        # Commande Clavier
        input_frame = tk.Frame(self.tab_pilot, bg="#1e1e1e")
        input_frame.pack(fill='x', padx=10, pady=10)

        tk.Label(input_frame, text="Commande :",
                 bg="#1e1e1e", fg="white",
                 font=("Segoe UI", 10)).pack(side='left')
        self.entry_cmd = tk.Entry(input_frame, bg="#333", fg="white",
                                  insertbackground="white",
                                  font=("Segoe UI", 12))
        self.entry_cmd.pack(side='left', fill='x', expand=True, padx=10)
        self.entry_cmd.bind("<Return>", self._on_enter)

        tk.Button(input_frame, text="EXECUTER", bg="#007acc", fg="white",
                  font=("Segoe UI", 10, "bold"),
                  command=self.manual_execute).pack(side='right')

    def setup_memory_tab(self):
        # Toolbar
        toolbar = tk.Frame(self.tab_memory, bg="#1e1e1e")
        toolbar.pack(fill='x', pady=10, padx=10)

        tk.Button(toolbar, text="Actualiser",
                  command=self.refresh_command_list,
                  bg="#444", fg="white").pack(side='left', padx=5)
        tk.Button(toolbar, text="Ajouter Commande",
                  command=self.add_custom_command,
                  bg="#007acc", fg="white").pack(side='left', padx=5)
        tk.Button(toolbar, text="Generer Outil (IA)",
                  command=self.genesis_prompt,
                  bg="#9900cc", fg="white").pack(side='left', padx=5)

        tk.Label(toolbar, text="Clic droit: Simuler / Executer / Supprimer",
                 bg="#1e1e1e", fg="gray").pack(side='right')

        # Treeview
        columns = ("phrase", "action", "params", "source", "usage")
        self.tree = ttk.Treeview(self.tab_memory, columns=columns,
                                 show='headings', selectmode='browse')

        self.tree.heading("phrase", text="Phrase Declencheur")
        self.tree.heading("action", text="Action")
        self.tree.heading("params", text="Parametres")
        self.tree.heading("source", text="Source")
        self.tree.heading("usage", text="Utilisations")

        self.tree.column("phrase", width=200)
        self.tree.column("action", width=150)
        self.tree.column("params", width=200)
        self.tree.column("source", width=80)
        self.tree.column("usage", width=60)

        tree_scroll = tk.Scrollbar(self.tab_memory, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        tree_scroll.pack(side='right', fill='y', padx=(0, 10))
        self.tree.pack(fill='both', expand=True, padx=10, pady=10)

        # Menu Contextuel
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Simuler Vocalement (Test Pipeline)",
                                      command=self.simulate_vocal_selection)
        self.context_menu.add_command(label="Executer Immediatement",
                                      command=self.execute_selection)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Oublier (Supprimer)",
                                      command=self.delete_selection)

        self.tree.bind("<Button-3>", self.show_context_menu)

    def setup_stats_tab(self):
        # Stats frame
        self.stats_text = tk.Text(self.tab_stats, bg="#000", fg="#00ccff",
                                  font=("Consolas", 11), state='disabled',
                                  wrap='word')
        self.stats_text.pack(fill='both', expand=True, padx=10, pady=10)

        btn_frame = tk.Frame(self.tab_stats, bg="#1e1e1e")
        btn_frame.pack(fill='x', padx=10, pady=5)
        tk.Button(btn_frame, text="Rafraichir Stats",
                  command=self.refresh_stats,
                  bg="#007acc", fg="white",
                  font=("Segoe UI", 10, "bold")).pack(side='left', padx=5)
        tk.Button(btn_frame, text="Auto-Amelioration",
                  command=self.run_auto_learn,
                  bg="#00aa44", fg="white",
                  font=("Segoe UI", 10, "bold")).pack(side='left', padx=5)

        self.refresh_stats()

    # === LOGGING ===

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        full_msg = f"[{timestamp}] {message}\n"
        self.console.config(state='normal')
        self.console.insert('end', full_msg)
        self.console.see('end')
        self.console.config(state='disabled')

    # === MICRO ===

    def _toggle_mic_safe(self):
        """Appele depuis hotkey (thread different) → planifier dans main loop"""
        self.root.after(0, self.toggle_mic)

    def toggle_mic(self):
        self.mic_active = not self.mic_active
        hotkey_label = " (Ctrl+Espace)" if KEYBOARD_OK else ""
        if self.mic_active:
            self.btn_mic.config(text=f"MICRO ON - Ecoute...{hotkey_label}",
                                bg="#00cc00")
            self.log("Microphone ACTIVE. Parlez maintenant.")
            threading.Thread(target=self._listen_once, daemon=True).start()
        else:
            self.btn_mic.config(text=f"MICRO OFF{hotkey_label}", bg="#cc0000")
            self.log("Microphone DESACTIVE.")

    def _listen_once(self):
        """Ecoute un segment audio et envoie au pipeline"""
        try:
            from faster_whisper import WhisperModel
            import sounddevice as sd
            import numpy as np
            import wave

            self.root.after(0, self.log, "  [MIC] Chargement Whisper...")
            try:
                model = WhisperModel("large-v3-turbo", device="cuda",
                                     compute_type="float16")
            except:
                model = WhisperModel("small", device="cpu", compute_type="int8")

            sample_rate = 16000
            duration = 8  # secondes max
            self.root.after(0, self.log, "  [MIC] Enregistrement...")
            audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate,
                           channels=1, dtype='float32')
            sd.wait()
            audio_np = audio.flatten()

            # Sauver WAV
            tmp = os.path.join(ROOT_DIR, "logs", "_gui_audio.wav")
            os.makedirs(os.path.dirname(tmp), exist_ok=True)
            audio_int16 = (audio_np * 32767).astype(np.int16)
            with wave.open(tmp, 'w') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(audio_int16.tobytes())

            segments, info = model.transcribe(tmp, language="fr")
            text = " ".join(s.text.strip() for s in segments).strip()

            if text and len(text) > 2:
                self.root.after(0, self.log, f"  [STT] \"{text}\"")
                self.root.after(0, self._process_in_thread, text)
            else:
                self.root.after(0, self.log, "  [STT] Rien detecte.")

        except ImportError:
            self.root.after(0, self.log,
                            "  [MIC] faster_whisper/sounddevice non installe. Utilisez le clavier.")
        except Exception as e:
            self.root.after(0, self.log, f"  [MIC] Erreur: {e}")
        finally:
            # Reset micro
            self.root.after(0, self._reset_mic)

    def _reset_mic(self):
        self.mic_active = False
        hotkey_label = " (Ctrl+Espace)" if KEYBOARD_OK else ""
        self.btn_mic.config(text=f"MICRO OFF{hotkey_label}", bg="#cc0000")

    # === COMMANDES ===

    def _on_enter(self, event):
        self.manual_execute()

    def manual_execute(self):
        text = self.entry_cmd.get().strip()
        if not text:
            return
        self.log(f"CMD: {text}")
        self.entry_cmd.delete(0, 'end')
        self._process_in_thread(text)

    def _process_in_thread(self, text):
        threading.Thread(target=self._process_command, args=(text,),
                         daemon=True).start()

    def _process_command(self, text):
        if not COMMANDER_OK:
            self.root.after(0, self.log, "  Cerveau non connecte.")
            return
        try:
            # Capturer stdout du pipeline
            old_stdout = sys.stdout
            capture = io.StringIO()
            sys.stdout = capture

            commander_v2.process_input(text)

            sys.stdout = old_stdout
            output = capture.getvalue().strip()

            if output:
                for line in output.split('\n'):
                    self.root.after(0, self.log, f"  {line.strip()}")
            else:
                self.root.after(0, self.log, f"  Pipeline execute: {text}")

            # Rafraichir la memoire apres un delai
            self.root.after(1500, self.refresh_command_list)
        except Exception as e:
            sys.stdout = sys.__stdout__
            self.root.after(0, self.log, f"  ERREUR PIPELINE: {e}")

    # === MEMOIRE (COMMANDES APPRISES) ===

    def refresh_command_list(self):
        for i in self.tree.get_children():
            self.tree.delete(i)

        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            try:
                cur.execute("""SELECT pattern_text, action, params, source, usage_count
                               FROM learned_patterns ORDER BY usage_count DESC""")
                for row in cur.fetchall():
                    self.tree.insert('', 'end', values=row)
            except:
                try:
                    cur.execute("""SELECT trigger_phrase, action, params, source, uses
                                   FROM learning_patterns ORDER BY uses DESC""")
                    for row in cur.fetchall():
                        self.tree.insert('', 'end', values=row)
                except:
                    pass
            conn.close()
        except Exception as e:
            self.log(f"Erreur DB: {e}")

    def show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)

    def execute_selection(self):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0])['values']
        phrase = vals[0]
        self.log(f"EXEC DIRECT: '{phrase}'")
        self._process_in_thread(phrase)

    def simulate_vocal_selection(self):
        """TTS prononce la commande puis l'injecte dans le pipeline"""
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0])['values']
        phrase = str(vals[0])

        self.log(f"SIMULATION VOCALE: '{phrase}'")

        def _sim():
            if TTS_OK:
                _tts.say(f"Commande de test: {phrase}")
                _tts.runAndWait()
            self._process_command(phrase)

        threading.Thread(target=_sim, daemon=True).start()

    def delete_selection(self):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0])['values']
        phrase = vals[0]

        if messagebox.askyesno("Confirmer", f"Oublier le pattern '{phrase}' ?"):
            self._process_in_thread(f"oublie {phrase}")
            self.root.after(1000, self.refresh_command_list)

    def add_custom_command(self):
        phrase = simpledialog.askstring("Nouveau Pattern",
                                        "Phrase declencheur (ex: 'lance le protocole alpha'):")
        if not phrase:
            return
        action = simpledialog.askstring("Action",
                                         "Action (ex: OPEN_APP, RUN_SCAN, OPEN_URL):")
        if not action:
            return
        params = simpledialog.askstring("Parametres",
                                         "Parametres (ex: notepad, ou vide):") or ""

        cmd = f"apprends {phrase} = {action} {params}".strip()
        self.log(f"APPRENTISSAGE: {cmd}")
        self._process_in_thread(cmd)

    def genesis_prompt(self):
        req = simpledialog.askstring("Genesis AI",
                                      "Decris l'outil a creer (ex: 'trier les photos'):")
        if req:
            self.log(f"GENESIS: {req}")
            self._process_in_thread(f"code un outil pour {req}")

    # === STATS ===

    def refresh_stats(self):
        self.stats_text.config(state='normal')
        self.stats_text.delete('1.0', 'end')

        lines = []
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()

            # Command history stats
            cur.execute("SELECT COUNT(*) FROM command_history")
            total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM command_history WHERE exec_success = 1")
            ok = cur.fetchone()[0]
            rate = round(ok / total * 100, 1) if total > 0 else 0

            lines.append("=== JARVIS STATS ===\n")
            lines.append(f"  Commandes totales: {total}")
            lines.append(f"  Taux de succes: {rate}% ({ok}/{total})")

            # Sources
            cur.execute("""SELECT intent_source, COUNT(*) as cnt FROM command_history
                           GROUP BY intent_source ORDER BY cnt DESC""")
            sources = cur.fetchall()
            if sources:
                lines.append("\n  Sources d'intention:")
                for src, cnt in sources:
                    pct = round(cnt / total * 100) if total > 0 else 0
                    lines.append(f"    {src}: {cnt} ({pct}%)")

            # Top actions
            cur.execute("""SELECT action, COUNT(*) as cnt FROM command_history
                           WHERE action IS NOT NULL
                           GROUP BY action ORDER BY cnt DESC LIMIT 10""")
            top = cur.fetchall()
            if top:
                lines.append("\n  Top actions:")
                for action, cnt in top:
                    lines.append(f"    {action}: {cnt}")

            # Learned patterns
            try:
                cur.execute("SELECT COUNT(*) FROM learned_patterns")
                lp = cur.fetchone()[0]
                lines.append(f"\n  Patterns appris (learned_patterns): {lp}")
            except:
                pass

            # Legacy patterns
            try:
                cur.execute("SELECT COUNT(*) FROM learning_patterns")
                lp2 = cur.fetchone()[0]
                lines.append(f"  Patterns legacy (learning_patterns): {lp2}")
            except:
                pass

            # Workflows
            try:
                cur.execute("SELECT COUNT(*) FROM macro_workflows")
                wf = cur.fetchone()[0]
                lines.append(f"  Workflows memorises: {wf}")
            except:
                pass

            # Recent failures
            cur.execute("""SELECT raw_text, COUNT(*) as cnt FROM command_history
                           WHERE action = 'UNKNOWN' OR exec_success = 0
                           GROUP BY raw_text HAVING cnt >= 2
                           ORDER BY cnt DESC LIMIT 5""")
            fails = cur.fetchall()
            if fails:
                lines.append("\n  Echecs frequents:")
                for txt, cnt in fails:
                    lines.append(f"    \"{txt[:40]}\" x{cnt}")

            # M2 latency
            cur.execute("""SELECT AVG(m2_latency_ms) FROM command_history
                           WHERE intent_source = 'M2' AND m2_latency_ms > 0""")
            avg_m2 = cur.fetchone()[0]
            if avg_m2:
                lines.append(f"\n  Latence M2 moyenne: {int(avg_m2)}ms")

            conn.close()

        except Exception as e:
            lines.append(f"\n  Erreur stats: {e}")

        self.stats_text.insert('1.0', '\n'.join(lines))
        self.stats_text.config(state='disabled')

    def run_auto_learn(self):
        """Lance auto_expand_fallback + suggest_genesis"""
        self.log("Auto-amelioration en cours...")
        self._process_in_thread("auto-amelioration")
        self.root.after(3000, self.refresh_stats)
        self.root.after(3000, self.refresh_command_list)


if __name__ == "__main__":
    root = tk.Tk()
    app = JarvisDashboard(root)
    root.mainloop()
