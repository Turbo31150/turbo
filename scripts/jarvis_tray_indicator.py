"""jarvis_tray_indicator.py — Indicateur JARVIS dans la barre systeme GNOME.

Affiche une icone JARVIS dans le panel GNOME avec menu:
- Status cluster (M1/OL1)
- GPU temperatures
- Services count
- Actions rapides (restart voice, dashboard, backup)

Usage:
    python scripts/jarvis_tray_indicator.py
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import threading
import time

import gi
gi.require_version('Gtk', '3.0')
try:
    gi.require_version('AyatanaAppIndicator3', '0.1')
    from gi.repository import AyatanaAppIndicator3 as AppIndicator3
except (ValueError, ImportError):
    gi.require_version('AppIndicator3', '0.1')
    from gi.repository import AppIndicator3

from gi.repository import Gtk, GLib

ICON_PATH = os.path.expanduser("~/Pictures/JARVIS/jarvis-icon-48.png")
UPDATE_INTERVAL = 10  # secondes


def _run(cmd, timeout=5):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=isinstance(cmd, str))
        return r.stdout.strip()
    except Exception:
        return ""


class JarvisTrayIndicator:
    def __init__(self):
        self.indicator = AppIndicator3.Indicator.new(
            "jarvis-os",
            ICON_PATH,
            AppIndicator3.IndicatorCategory.SYSTEM_SERVICES,
        )
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self.indicator.set_title("JARVIS OS")

        # Donnees
        self.gpu_temp = "?"
        self.services_count = 0
        self.m1_ok = False
        self.ol1_ok = False
        self.voice_active = False

        # Menu
        self.menu = Gtk.Menu()
        self._build_menu()
        self.indicator.set_menu(self.menu)

        # Mise a jour periodique
        GLib.timeout_add_seconds(UPDATE_INTERVAL, self._update_data)
        # Premier update
        threading.Thread(target=self._fetch_data, daemon=True).start()

    def _build_menu(self):
        # Header
        header = Gtk.MenuItem(label="J.A.R.V.I.S  OS v12.4")
        header.set_sensitive(False)
        self.menu.append(header)
        self.menu.append(Gtk.SeparatorMenuItem())

        # Status dynamiques
        self.lbl_cluster = Gtk.MenuItem(label="Cluster: ...")
        self.lbl_cluster.set_sensitive(False)
        self.menu.append(self.lbl_cluster)

        self.lbl_gpu = Gtk.MenuItem(label="GPU: ...")
        self.lbl_gpu.set_sensitive(False)
        self.menu.append(self.lbl_gpu)

        self.lbl_services = Gtk.MenuItem(label="Services: ...")
        self.lbl_services.set_sensitive(False)
        self.menu.append(self.lbl_services)

        self.lbl_voice = Gtk.MenuItem(label="Voice: ...")
        self.lbl_voice.set_sensitive(False)
        self.menu.append(self.lbl_voice)

        self.menu.append(Gtk.SeparatorMenuItem())

        # Actions
        items = [
            ("Dashboard Web", self._on_dashboard),
            ("Restart Voice", self._on_restart_voice),
            ("GPU Details", self._on_gpu),
            ("Backup SQL", self._on_backup),
            ("Terminal JARVIS", self._on_terminal),
        ]
        for label, callback in items:
            item = Gtk.MenuItem(label=label)
            item.connect("activate", callback)
            self.menu.append(item)

        self.menu.append(Gtk.SeparatorMenuItem())

        # Widgets
        widgets_sub = Gtk.MenuItem(label="Widgets")
        widgets_menu = Gtk.Menu()
        for label, cmd in [("Activer", "start"), ("Desactiver", "stop"), ("Redemarrer", "restart")]:
            item = Gtk.MenuItem(label=label)
            item.connect("activate", lambda w, c=cmd: self._widgets_action(c))
            widgets_menu.append(item)
        widgets_sub.set_submenu(widgets_menu)
        self.menu.append(widgets_sub)

        self.menu.append(Gtk.SeparatorMenuItem())

        # Quitter
        quit_item = Gtk.MenuItem(label="Quitter l'indicateur")
        quit_item.connect("activate", self._on_quit)
        self.menu.append(quit_item)

        self.menu.show_all()

    def _fetch_data(self):
        """Collecte les donnees en arriere-plan."""
        # GPU temp (premiere)
        try:
            output = _run(["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"])
            temps = [int(t.strip()) for t in output.split("\n") if t.strip()]
            self.gpu_temp = f"{max(temps)}C max" if temps else "?"
        except Exception:
            self.gpu_temp = "?"

        # Services
        try:
            output = _run("systemctl --user list-units 'jarvis-*' --no-pager --no-legend 2>/dev/null | grep -c 'active running'")
            self.services_count = int(output.strip()) if output.strip().isdigit() else 0
        except Exception:
            self.services_count = 0

        # Cluster
        self.m1_ok = _run(["curl", "-s", "--max-time", "2", "http://127.0.0.1:1234/api/v1/models"]) != ""
        self.ol1_ok = _run(["curl", "-s", "--max-time", "2", "http://127.0.0.1:11434/api/tags"]) != ""

        # Voice
        self.voice_active = _run(["systemctl", "--user", "is-active", "jarvis-voice"]).strip() == "active"

    def _update_data(self):
        """Met a jour les labels du menu (appele par GLib timer)."""
        threading.Thread(target=self._fetch_data, daemon=True).start()

        # Mettre a jour les labels
        m1 = "OK" if self.m1_ok else "OFF"
        ol1 = "OK" if self.ol1_ok else "OFF"
        self.lbl_cluster.set_label(f"Cluster: M1:{m1}  OL1:{ol1}")
        self.lbl_gpu.set_label(f"GPU: {self.gpu_temp}")
        self.lbl_services.set_label(f"Services: {self.services_count} actifs")
        self.lbl_voice.set_label(f"Voice: {'ACTIVE' if self.voice_active else 'OFF'} (898 cmds)")

        # Changer le label de l'indicateur
        self.indicator.set_label(f" {self.gpu_temp}", "JARVIS")

        return True  # Continuer le timer

    def _on_dashboard(self, _):
        subprocess.Popen(["xdg-open", "http://127.0.0.1:8088"])

    def _on_restart_voice(self, _):
        subprocess.Popen(["systemctl", "--user", "restart", "jarvis-voice"])
        subprocess.Popen(["notify-send", "JARVIS", "Voice pipeline redemarré", "-i", ICON_PATH])

    def _on_gpu(self, _):
        subprocess.Popen(["gnome-terminal", "--title=JARVIS GPU", "--",
                         "bash", "-c", "nvidia-smi; echo ''; echo 'Appuyez sur Entree...'; read"])

    def _on_backup(self, _):
        subprocess.Popen(["bash", "-c", "/usr/local/bin/jarvis backup && notify-send 'JARVIS' 'Backup SQL OK' -i " + ICON_PATH])

    def _on_terminal(self, _):
        subprocess.Popen(["gnome-terminal", "--working-directory=/home/turbo/jarvis", "--title=JARVIS Terminal"])

    def _widgets_action(self, action):
        subprocess.Popen(["bash", os.path.expanduser("~/jarvis/scripts/jarvis_widgets.sh"), action])

    def _on_quit(self, _):
        Gtk.main_quit()


def main():
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    indicator = JarvisTrayIndicator()
    Gtk.main()


if __name__ == "__main__":
    main()
