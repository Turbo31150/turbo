#!/usr/bin/env python3
"""linux_desktop_control.py — Pilote Linux entierement a la voix.

Controle complet du PC Linux sans clavier ni souris:
- Navigateur (via browser_pilot.py CDP Chrome DevTools Protocol, port 9222)
- GNOME Desktop (via xdotool, wmctrl)
- Systeme (CPU, RAM, GPU, disques, processus, services)
- Audio PipeWire (via pactl/wpctl)
- Reseau (via nmcli, bluetoothctl)
- Fichiers (via nautilus, xdg-open)

Usage:
    python src/linux_desktop_control.py --cmd "ouvre google"
    python src/linux_desktop_control.py --cmd "monte le volume"
    python src/linux_desktop_control.py --cmd "ouvre firefox"
    python src/linux_desktop_control.py --list
    python src/linux_desktop_control.py --list-methods
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BROWSER_PILOT = Path(__file__).parent.parent / "cowork" / "dev" / "browser_pilot.py"
PYTHON = sys.executable
CDP_PORT = 9222
SCREENSHOT_DIR = Path.home() / "Pictures" / "Screenshots"


# ===========================================================================
# LinuxDesktopControl — Classe principale
# ===========================================================================
class LinuxDesktopControl:
    """Controle complet du PC Linux a la voix: navigateur, desktop, systeme, multimedia."""

    def __init__(self):
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        # Detection de l'environnement graphique
        self._session_type = os.environ.get("XDG_SESSION_TYPE", "x11")
        self._desktop = os.environ.get("XDG_CURRENT_DESKTOP", "GNOME").upper()

    # -----------------------------------------------------------------------
    # Helpers internes
    # -----------------------------------------------------------------------
    def _run(self, cmd: list | str, timeout: int = 15, shell: bool = False) -> str:
        """Execute une commande systeme et retourne stdout."""
        try:
            r = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout, shell=shell
            )
            return r.stdout.strip() if r.returncode == 0 else r.stderr.strip()
        except subprocess.TimeoutExpired:
            return "ERREUR: Timeout commande"
        except FileNotFoundError:
            cmd_name = cmd[0] if isinstance(cmd, list) else cmd.split()[0]
            return f"ERREUR: {cmd_name} non installe"
        except Exception as e:
            return f"ERREUR: {e}"

    def _browser_cmd(self, *args, timeout: int = 20) -> str:
        """Appelle browser_pilot.py avec les arguments donnes."""
        if not BROWSER_PILOT.exists():
            return "ERREUR: browser_pilot.py introuvable"
        cmd = [PYTHON, str(BROWSER_PILOT)] + list(args)
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            output = r.stdout.strip()
            if r.returncode != 0 and r.stderr.strip():
                return r.stderr.strip()
            try:
                data = json.loads(output)
                if isinstance(data, dict):
                    if "error" in data:
                        return f"ERREUR navigateur: {data['error']}"
                    if "result" in data:
                        return str(data["result"])
                    if "text" in data:
                        return str(data["text"])[:2000]
                    if "action" in data:
                        return f"{data['action']}: OK"
                return output
            except (json.JSONDecodeError, ValueError):
                return output if output else "OK"
        except subprocess.TimeoutExpired:
            return "ERREUR: Timeout navigateur"
        except Exception as e:
            return f"ERREUR: {e}"

    def _ensure_cdp(self) -> str | None:
        """Verifie que CDP est actif, sinon lance le navigateur."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(("127.0.0.1", CDP_PORT))
            sock.close()
            if result != 0:
                self._browser_cmd("--start")
                time.sleep(1)
                return "Navigateur lance"
            return None
        except Exception:
            self._browser_cmd("--start")
            return "Navigateur lance"

    def _xdotool(self, *args) -> str:
        """Wrapper xdotool."""
        return self._run(["xdotool"] + list(args))

    def _wmctrl(self, *args) -> str:
        """Wrapper wmctrl."""
        return self._run(["wmctrl"] + list(args))

    # ===================================================================
    # NAVIGATEUR — via browser_pilot.py CDP (identique au VCC Windows)
    # ===================================================================
    def browser_open(self, url: str) -> str:
        """Ouvre une URL dans le navigateur."""
        self._ensure_cdp()
        if not url.startswith(("http://", "https://", "file://")):
            url = "https://" + url
        return self._browser_cmd("--navigate", url)

    def browser_search(self, query: str) -> str:
        """Recherche sur Google."""
        self._ensure_cdp()
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        return self._browser_cmd("--navigate", url)

    def browser_back(self) -> str:
        return self._browser_cmd("--back")

    def browser_forward(self) -> str:
        return self._browser_cmd("--forward")

    def browser_scroll(self, direction: str = "down", amount: int = 500) -> str:
        d = direction.lower()
        if d in ("up", "down", "top", "bottom"):
            return self._browser_cmd("--scroll", d)
        return f"Direction inconnue: {direction}"

    def browser_click(self, text_or_selector: str) -> str:
        if any(c in text_or_selector for c in ".#[]>+~="):
            return self._browser_cmd("--click", text_or_selector)
        return self._browser_cmd("--click-text", text_or_selector)

    def browser_type(self, text: str) -> str:
        return self._browser_cmd("--type", text)

    def browser_press(self, key: str) -> str:
        return self._browser_cmd("--press", key)

    def browser_new_tab(self, url: str = "about:blank") -> str:
        self._ensure_cdp()
        return self._browser_cmd("--new-tab", url)

    def browser_close_tab(self) -> str:
        return self._browser_cmd("--close-tab")

    def browser_tabs(self) -> str:
        output = self._browser_cmd("--tabs")
        try:
            tabs = json.loads(output)
            if isinstance(tabs, list):
                lines = [f"{i+1}. {t.get('title', 'Sans titre')} — {t.get('url', '')}"
                         for i, t in enumerate(tabs)]
                return f"{len(tabs)} onglet(s):\n" + "\n".join(lines)
        except (json.JSONDecodeError, ValueError):
            pass
        return output

    def browser_read(self) -> str:
        return self._browser_cmd("--text")

    def browser_screenshot(self, path: str = None) -> str:
        if not path:
            path = str(SCREENSHOT_DIR / f"browser_{int(time.time())}.png")
        return self._browser_cmd("--screenshot", path)

    def browser_zoom(self, in_out: str = "in") -> str:
        if in_out.lower() in ("in", "plus", "+"):
            js = "document.body.style.zoom = (parseFloat(document.body.style.zoom || 1) + 0.1).toString(); 'zoom: ' + document.body.style.zoom"
        else:
            js = "document.body.style.zoom = Math.max(0.1, parseFloat(document.body.style.zoom || 1) - 0.1).toString(); 'zoom: ' + document.body.style.zoom"
        return self._browser_cmd("--eval", js)

    def browser_find(self, text: str) -> str:
        js = f"window.find('{text.replace(chr(39), chr(92)+chr(39))}') ? 'Trouve: {text}' : 'Non trouve: {text}'"
        return self._browser_cmd("--eval", js)

    def browser_bookmark(self) -> str:
        self._xdotool("key", "ctrl+d")
        return "Boite de dialogue favoris ouverte"

    def browser_refresh(self) -> str:
        return self._browser_cmd("--eval", "location.reload(); 'page rafraichie'")

    def browser_fullscreen(self) -> str:
        self._xdotool("key", "F11")
        return "Plein ecran bascule"

    # ===================================================================
    # LINUX DESKTOP — Applications
    # ===================================================================
    APP_MAP = {
        # Editeurs
        "notepad": "gedit", "bloc-notes": "gedit", "blocnotes": "gedit",
        "gedit": "gedit", "editeur": "gedit", "nano": "gnome-terminal -- nano",
        # Utilitaires
        "calc": "gnome-calculator", "calculatrice": "gnome-calculator",
        "calculator": "gnome-calculator",
        "explorer": "nautilus", "explorateur": "nautilus",
        "fichiers": "nautilus", "gestionnaire de fichiers": "nautilus",
        # Terminaux
        "terminal": "gnome-terminal", "wt": "gnome-terminal",
        "bash": "gnome-terminal", "console": "gnome-terminal",
        "cmd": "gnome-terminal",
        # Parametres
        "parametres": "gnome-control-center", "settings": "gnome-control-center",
        "reglages": "gnome-control-center", "control": "gnome-control-center",
        "panneau": "gnome-control-center",
        # Navigateurs
        "chrome": "google-chrome-stable", "chromium": "chromium-browser",
        "firefox": "firefox", "edge": "microsoft-edge-stable",
        # Multimedia
        "spotify": "spotify", "vlc": "vlc", "musique": "rhythmbox",
        # Communication
        "discord": "discord", "telegram": "telegram-desktop",
        "slack": "slack",
        # Dev
        "code": "code", "vscode": "code",
        "visual studio code": "code",
        # Systeme
        "moniteur": "gnome-system-monitor",
        "gestionnaire": "gnome-system-monitor",
        "task manager": "gnome-system-monitor",
        "moniteur systeme": "gnome-system-monitor",
        # Graphique
        "paint": "drawing", "gimp": "gimp",
        "capture": "gnome-screenshot",
        # Bureautique
        "writer": "libreoffice --writer", "word": "libreoffice --writer",
        "calc_office": "libreoffice --calc", "excel": "libreoffice --calc",
        "impress": "libreoffice --impress",
    }

    def linux_open_app(self, name: str) -> str:
        """Ouvrir une application Linux."""
        key = name.lower().strip()
        cmd = self.APP_MAP.get(key)
        if not cmd:
            # Tenter de trouver l'executable directement
            if shutil.which(key):
                cmd = key
            else:
                # Tenter via gtk-launch avec le nom .desktop
                desktop_names = [key, key.replace(" ", "-"), key.replace(" ", "")]
                for dn in desktop_names:
                    r = self._run(["gtk-launch", dn], timeout=5)
                    if "ERREUR" not in r:
                        return f"{name} ouvert"
                return f"Application inconnue: {name}"

        # Lancer en arriere-plan
        try:
            parts = cmd.split()
            subprocess.Popen(
                parts,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return f"{name} ouvert"
        except Exception as e:
            return f"ERREUR: {e}"

    def linux_close_app(self) -> str:
        """Fermer la fenetre active (Alt+F4)."""
        self._xdotool("key", "alt+F4")
        return "Fenetre fermee"

    def linux_minimize(self) -> str:
        """Minimiser la fenetre active."""
        self._xdotool("key", "super+h")
        return "Fenetre minimisee"

    def linux_maximize(self) -> str:
        """Maximiser la fenetre active."""
        self._xdotool("key", "super+Up")
        return "Fenetre maximisee"

    def linux_switch_app(self) -> str:
        """Basculer entre les fenetres (Alt+Tab)."""
        self._xdotool("key", "alt+Tab")
        return "Fenetre changee"

    def linux_snap_left(self) -> str:
        """Ancrer la fenetre a gauche."""
        self._xdotool("key", "super+Left")
        return "Fenetre ancree a gauche"

    def linux_snap_right(self) -> str:
        """Ancrer la fenetre a droite."""
        self._xdotool("key", "super+Right")
        return "Fenetre ancree a droite"

    def linux_desktop_show(self) -> str:
        """Afficher le bureau (minimiser tout)."""
        self._xdotool("key", "super+d")
        return "Bureau affiche"

    def linux_list_windows(self) -> str:
        """Lister les fenetres ouvertes."""
        output = self._wmctrl("-l")
        if not output or "ERREUR" in output:
            return "Aucune fenetre trouvee"
        lines = output.strip().split("\n")
        result = []
        for line in lines:
            parts = line.split(None, 4)
            if len(parts) >= 5:
                result.append(parts[4])
            elif len(parts) >= 4:
                result.append(parts[3])
        return f"{len(result)} fenetre(s):\n" + "\n".join(f"  - {w}" for w in result)

    def linux_focus_window(self, name: str) -> str:
        """Mettre le focus sur une fenetre par nom."""
        self._wmctrl("-a", name)
        return f"Focus sur: {name}"

    # ===================================================================
    # LINUX — Capture d'ecran
    # ===================================================================
    def linux_screenshot(self, path: str = None) -> str:
        """Capture d'ecran via scrot ou gnome-screenshot."""
        if not path:
            path = str(SCREENSHOT_DIR / f"screen_{int(time.time())}.png")
        if shutil.which("scrot"):
            self._run(["scrot", path])
        elif shutil.which("gnome-screenshot"):
            self._run(["gnome-screenshot", "-f", path])
        elif shutil.which("grim"):
            self._run(["grim", path])
        else:
            return "ERREUR: Aucun outil de capture installe (scrot/gnome-screenshot/grim)"
        if os.path.exists(path):
            return f"Capture sauvegardee: {path}"
        return "Erreur lors de la capture"

    # ===================================================================
    # LINUX — Verrouillage / Alimentation
    # ===================================================================
    def linux_lock(self) -> str:
        """Verrouiller l'ecran."""
        self._run(["loginctl", "lock-session"])
        return "Ecran verrouille"

    def linux_shutdown(self) -> str:
        """Eteindre l'ordinateur."""
        self._run(["systemctl", "poweroff"])
        return "Extinction en cours"

    def linux_restart(self) -> str:
        """Redemarrer l'ordinateur."""
        self._run(["systemctl", "reboot"])
        return "Redemarrage en cours"

    def linux_sleep(self) -> str:
        """Mise en veille."""
        self._run(["systemctl", "suspend"])
        return "Mise en veille"

    # ===================================================================
    # LINUX — Audio PipeWire / PulseAudio
    # ===================================================================
    def linux_volume(self, action: str = "up") -> str:
        """Controle du volume via pactl (PipeWire/PulseAudio)."""
        key = action.lower()
        if key in ("up", "plus", "augmenter"):
            self._run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "+5%"])
            return "Volume augmente"
        elif key in ("down", "moins", "baisser"):
            self._run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "-5%"])
            return "Volume baisse"
        elif key in ("mute", "couper", "muet"):
            self._run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"])
            return "Son coupe/reactive"
        elif key.isdigit():
            self._run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{key}%"])
            return f"Volume regle a {key}%"
        return f"Action inconnue: {action}"

    def linux_volume_level(self) -> str:
        """Obtenir le niveau de volume actuel."""
        output = self._run(["pactl", "get-sink-volume", "@DEFAULT_SINK@"])
        # Extraire le pourcentage
        match = re.search(r"(\d+)%", output)
        if match:
            return f"Volume actuel: {match.group(1)}%"
        return output

    # ===================================================================
    # LINUX — Luminosite
    # ===================================================================
    def linux_brightness(self, action: str = "up") -> str:
        """Luminosite ecran via brightnessctl."""
        if not shutil.which("brightnessctl"):
            # Fallback xrandr
            if action.lower() == "up":
                return self._run("xrandr --output $(xrandr | grep ' connected' | head -1 | cut -d' ' -f1) --brightness 1.0", shell=True)
            else:
                return self._run("xrandr --output $(xrandr | grep ' connected' | head -1 | cut -d' ' -f1) --brightness 0.7", shell=True)
        if action.lower() in ("up", "plus"):
            self._run(["brightnessctl", "set", "+10%"])
            return "Luminosite augmentee"
        else:
            self._run(["brightnessctl", "set", "10%-"])
            return "Luminosite baissee"

    # ===================================================================
    # LINUX — Reseau
    # ===================================================================
    def linux_wifi(self, on_off: str = "on") -> str:
        """Activer/desactiver le WiFi via nmcli."""
        if on_off.lower() in ("on", "activer", "oui", "allumer"):
            self._run(["nmcli", "radio", "wifi", "on"])
            return "WiFi active"
        else:
            self._run(["nmcli", "radio", "wifi", "off"])
            return "WiFi desactive"

    def linux_bluetooth(self, on_off: str = "on") -> str:
        """Activer/desactiver le Bluetooth via bluetoothctl."""
        if on_off.lower() in ("on", "activer", "oui", "allumer"):
            self._run(["bluetoothctl", "power", "on"])
            return "Bluetooth active"
        else:
            self._run(["bluetoothctl", "power", "off"])
            return "Bluetooth desactive"

    def linux_network_info(self) -> str:
        """Informations reseau."""
        ip = self._run(["hostname", "-I"])
        wifi = self._run(["nmcli", "-t", "-f", "ACTIVE,SSID", "dev", "wifi"])
        active_ssid = ""
        for line in wifi.split("\n"):
            if line.startswith("yes:") or line.startswith("oui:"):
                active_ssid = line.split(":", 1)[1] if ":" in line else ""
                break
        return f"IP: {ip.split()[0] if ip else 'inconnue'}" + (f", WiFi: {active_ssid}" if active_ssid else "")

    # ===================================================================
    # LINUX — Fichiers
    # ===================================================================
    def linux_file_explorer(self, path: str = None) -> str:
        """Ouvrir le gestionnaire de fichiers."""
        target = path or str(Path.home())
        try:
            subprocess.Popen(
                ["nautilus", target],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return f"Explorateur ouvert: {target}"
        except FileNotFoundError:
            self._run(["xdg-open", target])
            return f"Explorateur ouvert: {target}"

    def linux_open_file(self, path: str) -> str:
        """Ouvrir un fichier avec l'application par defaut."""
        self._run(["xdg-open", path])
        return f"Fichier ouvert: {path}"

    # ===================================================================
    # LINUX — Presse-papiers
    # ===================================================================
    def linux_clipboard_copy(self) -> str:
        """Copier (Ctrl+C)."""
        self._xdotool("key", "ctrl+c")
        return "Copie dans le presse-papiers"

    def linux_clipboard_paste(self) -> str:
        """Coller (Ctrl+V)."""
        self._xdotool("key", "ctrl+v")
        return "Colle depuis le presse-papiers"

    def linux_clipboard_read(self) -> str:
        """Lire le contenu du presse-papiers."""
        if shutil.which("xclip"):
            return self._run(["xclip", "-selection", "clipboard", "-o"])
        elif shutil.which("xsel"):
            return self._run(["xsel", "--clipboard", "--output"])
        return "ERREUR: xclip ou xsel non installe"

    # ===================================================================
    # LINUX — Recherche
    # ===================================================================
    def linux_search(self, query: str = "") -> str:
        """Recherche d'applications/fichiers via GNOME Activities."""
        self._xdotool("key", "super")
        if query:
            time.sleep(0.5)
            self._xdotool("type", "--clearmodifiers", query)
            return f"Recherche: {query}"
        return "Recherche ouverte"

    # ===================================================================
    # LINUX — Multimedia
    # ===================================================================
    def linux_media_play_pause(self) -> str:
        """Play/Pause media."""
        self._run(["playerctl", "play-pause"])
        return "Lecture/pause"

    def linux_media_next(self) -> str:
        """Piste suivante."""
        self._run(["playerctl", "next"])
        return "Piste suivante"

    def linux_media_previous(self) -> str:
        """Piste precedente."""
        self._run(["playerctl", "previous"])
        return "Piste precedente"

    def linux_media_stop(self) -> str:
        """Arreter la lecture."""
        self._run(["playerctl", "stop"])
        return "Lecture arretee"

    # ===================================================================
    # LINUX — Monitoring systeme
    # ===================================================================
    def linux_cpu_usage(self) -> str:
        """Usage CPU."""
        output = self._run(["grep", "cpu ", "/proc/stat"])
        if "ERREUR" in output:
            return self._run("top -bn1 | head -5", shell=True)
        parts = output.split()
        if len(parts) >= 5:
            idle = int(parts[4])
            total = sum(int(x) for x in parts[1:])
            usage = 100 - (idle * 100 // total) if total > 0 else 0
            return f"CPU: {usage}% utilise"
        return "Impossible de lire l'usage CPU"

    def linux_memory_usage(self) -> str:
        """Usage memoire."""
        output = self._run(["free", "-h"])
        lines = output.split("\n")
        if len(lines) >= 2:
            parts = lines[1].split()
            if len(parts) >= 3:
                return f"RAM: {parts[2]} utilises sur {parts[1]}"
        return output

    def linux_disk_usage(self) -> str:
        """Usage disque."""
        output = self._run(["df", "-h", "/"])
        lines = output.split("\n")
        if len(lines) >= 2:
            parts = lines[1].split()
            if len(parts) >= 5:
                return f"Disque /: {parts[2]} utilises sur {parts[1]} ({parts[4]})"
        return output

    def linux_gpu_info(self) -> str:
        """Informations GPU (nvidia-smi)."""
        if shutil.which("nvidia-smi"):
            output = self._run(["nvidia-smi", "--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total",
                               "--format=csv,noheader,nounits"])
            if "ERREUR" not in output:
                gpus = []
                for i, line in enumerate(output.strip().split("\n")):
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 5:
                        gpus.append(f"GPU{i}: {parts[0]} — {parts[1]}°C, {parts[2]}% GPU, {parts[3]}/{parts[4]} MB VRAM")
                return "\n".join(gpus) if gpus else output
        return "Pas de GPU NVIDIA detecte"

    def linux_processes(self) -> str:
        """Liste des processus les plus gourmands."""
        return self._run("ps aux --sort=-%mem | head -8", shell=True)

    def linux_kill_process(self, name: str) -> str:
        """Tuer un processus par nom."""
        result = self._run(["pkill", "-f", name])
        if not result:
            return f"Processus {name} arrete"
        return result

    def linux_uptime(self) -> str:
        """Uptime du systeme."""
        return self._run(["uptime", "-p"])

    def linux_ip_address(self) -> str:
        """Adresse IP."""
        return self._run(["hostname", "-I"])

    # ===================================================================
    # LINUX — Services systemd
    # ===================================================================
    def linux_service_status(self, name: str) -> str:
        """Statut d'un service systemd."""
        output = self._run(["systemctl", "is-active", name])
        return f"Service {name}: {output}"

    def linux_service_restart(self, name: str) -> str:
        """Redemarrer un service systemd."""
        output = self._run(["systemctl", "restart", name])
        return output or f"Service {name} redemarre"

    # ===================================================================
    # LINUX — Workspaces GNOME
    # ===================================================================
    def linux_workspace_next(self) -> str:
        """Aller au workspace suivant."""
        self._xdotool("key", "super+Page_Down")
        return "Workspace suivant"

    def linux_workspace_prev(self) -> str:
        """Aller au workspace precedent."""
        self._xdotool("key", "super+Page_Up")
        return "Workspace precedent"

    def linux_workspace_overview(self) -> str:
        """Vue d'ensemble des workspaces (Activities)."""
        self._xdotool("key", "super")
        return "Vue d'ensemble"

    # ===================================================================
    # LINUX — Gestion de fichiers a la voix
    # ===================================================================
    def linux_create_folder(self, name: str, path: str = None) -> str:
        """Creer un dossier."""
        base = path or str(Path.home())
        target = os.path.join(base, name)
        os.makedirs(target, exist_ok=True)
        return f"Dossier cree: {target}"

    def linux_create_file(self, name: str, path: str = None) -> str:
        """Creer un fichier vide."""
        base = path or str(Path.home())
        target = os.path.join(base, name)
        Path(target).touch()
        return f"Fichier cree: {target}"

    def linux_delete_file(self, name: str, path: str = None) -> str:
        """Supprimer un fichier ou dossier (vers la corbeille)."""
        base = path or str(Path.home())
        target = os.path.join(base, name)
        if shutil.which("gio"):
            result = self._run(["gio", "trash", target])
            return result or f"Mis a la corbeille: {name}"
        return "ERREUR: gio non disponible"

    def linux_rename_file(self, old_name: str, new_name: str, path: str = None) -> str:
        """Renommer un fichier ou dossier."""
        base = path or str(Path.home())
        src = os.path.join(base, old_name)
        dst = os.path.join(base, new_name)
        if os.path.exists(src):
            os.rename(src, dst)
            return f"Renomme: {old_name} → {new_name}"
        return f"ERREUR: {old_name} introuvable"

    def linux_move_file(self, name: str, destination: str) -> str:
        """Deplacer un fichier ou dossier."""
        src = os.path.expanduser(name)
        dst = os.path.expanduser(destination)
        result = self._run(["mv", src, dst])
        return result or f"Deplace: {name} → {destination}"

    def linux_list_files(self, path: str = None) -> str:
        """Lister les fichiers d'un dossier."""
        target = path or str(Path.home())
        # Resoudre ~ et les chemins relatifs
        target = os.path.expanduser(target)
        if not os.path.isabs(target):
            target = os.path.join(str(Path.home()), target)
        # Corriger la casse des dossiers courants
        if not os.path.exists(target):
            parent = os.path.dirname(target)
            basename = os.path.basename(target)
            if os.path.isdir(parent):
                for entry in os.listdir(parent):
                    if entry.lower() == basename.lower():
                        target = os.path.join(parent, entry)
                        break
        output = self._run(["ls", "-lh", "--color=never", target])
        lines = output.strip().split("\n")
        if len(lines) > 15:
            return "\n".join(lines[:15]) + f"\n... et {len(lines)-15} autres fichiers"
        return output

    def linux_find_file(self, name: str) -> str:
        """Chercher un fichier par nom."""
        output = self._run(["find", str(Path.home()), "-maxdepth", "4", "-iname", f"*{name}*", "-type", "f"], timeout=10)
        files = [f for f in output.strip().split("\n") if f][:10]
        if files:
            return f"{len(files)} fichier(s) trouve(s):\n" + "\n".join(f"  {f}" for f in files)
        return f"Aucun fichier contenant '{name}'"

    def linux_disk_space_detailed(self) -> str:
        """Espace disque detaille sur toutes les partitions."""
        return self._run(["df", "-h", "--type=ext4", "--type=btrfs", "--type=xfs", "--type=ntfs"])

    # ===================================================================
    # LINUX — Dictee de texte (frappe dans n'importe quelle app)
    # ===================================================================
    def linux_type_text(self, text: str) -> str:
        """Taper du texte dans l'application active."""
        self._xdotool("type", "--clearmodifiers", "--delay", "20", text)
        return f"Texte tape: {text[:50]}..."

    def linux_type_key(self, key: str) -> str:
        """Appuyer sur une touche ou combo clavier."""
        # Normaliser les noms de touches
        key_map = {
            "entree": "Return", "enter": "Return", "retour": "Return",
            "echap": "Escape", "escape": "Escape",
            "tab": "Tab", "tabulation": "Tab",
            "espace": "space", "space": "space",
            "supprimer": "Delete", "delete": "Delete",
            "backspace": "BackSpace", "effacer": "BackSpace",
            "haut": "Up", "bas": "Down", "gauche": "Left", "droite": "Right",
            "debut": "Home", "fin": "End",
            "page haut": "Page_Up", "page bas": "Page_Down",
            "f1": "F1", "f2": "F2", "f3": "F3", "f4": "F4", "f5": "F5",
            "f6": "F6", "f7": "F7", "f8": "F8", "f9": "F9", "f10": "F10",
            "f11": "F11", "f12": "F12",
        }
        xkey = key_map.get(key.lower(), key)
        self._xdotool("key", "--clearmodifiers", xkey)
        return f"Touche: {key}"

    def linux_hotkey(self, combo: str) -> str:
        """Executer un raccourci clavier (ex: ctrl+s, alt+f4, super+l)."""
        self._xdotool("key", "--clearmodifiers", combo)
        return f"Raccourci: {combo}"

    def linux_select_all(self) -> str:
        """Selectionner tout (Ctrl+A)."""
        self._xdotool("key", "ctrl+a")
        return "Tout selectionne"

    def linux_undo(self) -> str:
        """Annuler (Ctrl+Z)."""
        self._xdotool("key", "ctrl+z")
        return "Annulation"

    def linux_redo(self) -> str:
        """Refaire (Ctrl+Y / Ctrl+Shift+Z)."""
        self._xdotool("key", "ctrl+shift+z")
        return "Retabli"

    def linux_save(self) -> str:
        """Sauvegarder (Ctrl+S)."""
        self._xdotool("key", "ctrl+s")
        return "Sauvegarde"

    # ===================================================================
    # LINUX — Tmux / Terminal avance
    # ===================================================================
    def linux_tmux_list(self) -> str:
        """Lister les sessions tmux."""
        output = self._run(["tmux", "list-sessions"])
        if "ERREUR" in output or "no server" in output:
            return "Aucune session tmux active"
        return output

    def linux_tmux_attach(self, session: str = "") -> str:
        """S'attacher a une session tmux."""
        if session:
            self._run(["gnome-terminal", "--", "tmux", "attach-session", "-t", session])
        else:
            self._run(["gnome-terminal", "--", "tmux", "attach"])
        return f"Attache a tmux {session or '(derniere)'}"

    def linux_tmux_new(self, name: str = "") -> str:
        """Creer une nouvelle session tmux."""
        cmd = ["gnome-terminal", "--", "tmux", "new-session"]
        if name:
            cmd.extend(["-s", name])
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            return f"Session tmux '{name}' creee" if name else "Nouvelle session tmux"
        except Exception as e:
            return f"ERREUR: {e}"

    # ===================================================================
    # LINUX — Gestion des services systemd a la voix
    # ===================================================================
    def linux_services_list(self) -> str:
        """Lister les services JARVIS actifs."""
        output = self._run("systemctl --user list-units 'jarvis-*' --no-pager --no-legend", shell=True)
        lines = output.strip().split("\n")
        result = []
        for line in lines:
            parts = line.split()
            if len(parts) >= 4:
                name = parts[0].replace(".service", "")
                state = parts[2]  # active/inactive
                result.append(f"  {name}: {state}")
        return f"{len(result)} service(s) JARVIS:\n" + "\n".join(result)

    def linux_service_logs(self, name: str) -> str:
        """Voir les logs recents d'un service."""
        output = self._run(["journalctl", "--user", "-u", name, "--no-pager", "-n", "10"])
        return output or f"Pas de logs pour {name}"

    # ===================================================================
    # LINUX — Installation de paquets
    # ===================================================================
    def linux_install_package(self, name: str) -> str:
        """Installer un paquet via apt (necessite sudo)."""
        return self._run(["sudo", "apt", "install", "-y", name], timeout=120)

    def linux_update_system(self) -> str:
        """Mettre a jour le systeme."""
        return self._run(["sudo", "apt", "update"], timeout=120)

    # ===================================================================
    # LINUX — Commande bash libre
    # ===================================================================
    def linux_run_command(self, command: str) -> str:
        """Executer une commande bash arbitraire."""
        # Securite: limiter la longueur et bloquer les commandes destructives
        dangerous = ["rm -rf /", "mkfs", "dd if=", "> /dev/sd"]
        for d in dangerous:
            if d in command:
                return f"REFUSE: commande dangereuse detectee ({d})"
        output = self._run(command, shell=True, timeout=30)
        if len(output) > 2000:
            return output[:2000] + "\n... (tronque)"
        return output or "Commande executee"

    # ===================================================================
    # LINUX — Notifications
    # ===================================================================
    def linux_notify(self, message: str, title: str = "JARVIS") -> str:
        """Envoyer une notification desktop."""
        self._run(["notify-send", title, message])
        return f"Notification: {message}"

    # ===================================================================
    # LINUX — Mode conversationnel IA
    # ===================================================================
    def linux_ask_ia(self, question: str) -> str:
        """Poser une question a l'IA locale via Ollama ou LM Studio."""
        import urllib.request
        # Essayer Ollama d'abord, puis LM Studio
        endpoints = [
            ("http://127.0.0.1:11434/api/generate", lambda q: json.dumps({
                "model": "qwen2.5:1.5b", "prompt": q,
                "stream": False, "options": {"num_predict": 200}
            }), lambda d: d.get("response", "")),
            ("http://127.0.0.1:1234/v1/chat/completions", lambda q: json.dumps({
                "messages": [{"role": "user", "content": f"/nothink {q}"}],
                "max_tokens": 200, "temperature": 0.7
            }), lambda d: d.get("choices", [{}])[0].get("message", {}).get("content", "")),
        ]
        for url, payload_fn, extract_fn in endpoints:
            try:
                req = urllib.request.Request(
                    url, data=payload_fn(question).encode(),
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read())
                    result = extract_fn(data)
                    if result:
                        return result.strip()[:500]
            except Exception:
                continue
        return "ERREUR: Aucune IA disponible"

    # ===================================================================
    # LINUX — Gestion de l'ecran / affichage
    # ===================================================================
    def linux_screen_resolution(self) -> str:
        """Obtenir la resolution d'ecran."""
        output = self._run(["xrandr", "--current"])
        for line in output.split("\n"):
            if " connected" in line and "+" in line:
                match = re.search(r"(\d+x\d+)", line)
                if match:
                    return f"Resolution: {match.group(1)}"
        return "Resolution inconnue"

    def linux_dark_mode(self, on_off: str = "on") -> str:
        """Activer/desactiver le mode sombre GNOME."""
        if on_off.lower() in ("on", "activer", "oui", "sombre"):
            self._run(["gsettings", "set", "org.gnome.desktop.interface", "color-scheme", "prefer-dark"])
            return "Mode sombre active"
        else:
            self._run(["gsettings", "set", "org.gnome.desktop.interface", "color-scheme", "prefer-light"])
            return "Mode clair active"

    def linux_night_light(self, on_off: str = "on") -> str:
        """Activer/desactiver la veilleuse GNOME."""
        val = "true" if on_off.lower() in ("on", "activer", "oui") else "false"
        self._run(["gsettings", "set", "org.gnome.settings-daemon.plugins.color", "night-light-enabled", val])
        return f"Veilleuse {'activee' if val == 'true' else 'desactivee'}"

    # ===================================================================
    # LINUX — Connexions Bluetooth avancees
    # ===================================================================
    def linux_bluetooth_devices(self) -> str:
        """Lister les appareils Bluetooth connus."""
        output = self._run(["bluetoothctl", "devices"])
        return output or "Aucun appareil Bluetooth"

    def linux_bluetooth_connect(self, device: str = "") -> str:
        """Connecter un appareil Bluetooth."""
        if not device:
            # Tenter le dernier casque Sony
            output = self._run(["bluetoothctl", "devices"])
            for line in output.split("\n"):
                if "Sony" in line or "WH-1000" in line or "XM4" in line:
                    mac = line.split()[1] if len(line.split()) >= 2 else ""
                    if mac:
                        self._run(["bluetoothctl", "connect", mac])
                        return f"Connexion au casque Sony: {mac}"
            return "Aucun casque Sony trouve"
        self._run(["bluetoothctl", "connect", device])
        return f"Connexion a: {device}"

    def linux_bluetooth_disconnect(self) -> str:
        """Deconnecter tous les appareils Bluetooth."""
        output = self._run(["bluetoothctl", "devices", "Connected"])
        for line in output.split("\n"):
            parts = line.split()
            if len(parts) >= 2 and ":" in parts[1]:
                self._run(["bluetoothctl", "disconnect", parts[1]])
        return "Appareils Bluetooth deconnectes"

    # ===================================================================
    # LINUX — Date / Heure / Calendrier
    # ===================================================================
    def linux_datetime(self) -> str:
        """Date et heure actuelles."""
        output = self._run(["date", "+%A %d %B %Y, %H:%M:%S"])
        return f"Il est {output}"

    def linux_calendar(self) -> str:
        """Calendrier du mois."""
        return self._run(["cal"])

    def linux_timer(self, seconds: str = "60") -> str:
        """Lancer un minuteur avec notification."""
        try:
            secs = int(seconds)
            # Lancer en arriere-plan
            subprocess.Popen(
                ["bash", "-c", f"sleep {secs} && notify-send 'JARVIS Timer' 'Minuteur de {secs}s termine!' && paplay /usr/share/sounds/freedesktop/stereo/complete.oga 2>/dev/null"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
            )
            return f"Minuteur de {secs} secondes lance"
        except ValueError:
            return f"ERREUR: '{seconds}' n'est pas un nombre valide"

    # ===================================================================
    # LINUX — Processus avances
    # ===================================================================
    def linux_top_cpu(self) -> str:
        """Top 10 processus par CPU."""
        return self._run("ps aux --sort=-%cpu | head -11", shell=True)

    def linux_top_memory(self) -> str:
        """Top 10 processus par memoire."""
        return self._run("ps aux --sort=-%mem | head -11", shell=True)

    def linux_kill_pid(self, pid: str) -> str:
        """Tuer un processus par PID."""
        result = self._run(["kill", "-9", pid])
        return result or f"Processus {pid} tue"

    def linux_ports_open(self) -> str:
        """Lister les ports ouverts."""
        output = self._run(["ss", "-tulpn"])
        lines = output.strip().split("\n")
        if len(lines) > 20:
            return "\n".join(lines[:20]) + f"\n... et {len(lines)-20} autres"
        return output

    def linux_process_count(self) -> str:
        """Nombre de processus en cours."""
        output = self._run("ps aux | wc -l", shell=True)
        return f"{output.strip()} processus en cours"

    # ===================================================================
    # LINUX — JARVIS interne (pilotage vocal du cluster)
    # ===================================================================
    def jarvis_cluster_status(self) -> str:
        """Statut du cluster JARVIS (M1/M2/OL1)."""
        import urllib.request
        nodes = [
            ("M1", "http://127.0.0.1:1234/api/v1/models"),
            ("OL1", "http://127.0.0.1:11434/api/tags"),
        ]
        results = []
        for name, url in nodes:
            try:
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=3) as resp:
                    data = json.loads(resp.read())
                    if isinstance(data, dict) and "data" in data:
                        models = [m.get("id", "?") for m in data["data"][:3]]
                        results.append(f"{name}: OK ({', '.join(models)})")
                    elif isinstance(data, dict) and "models" in data:
                        models = [m.get("name", "?") for m in data["models"][:3]]
                        results.append(f"{name}: OK ({', '.join(models)})")
                    else:
                        results.append(f"{name}: OK")
            except Exception:
                results.append(f"{name}: OFFLINE")
        return "Cluster JARVIS:\n" + "\n".join(f"  {r}" for r in results)

    def jarvis_services_health(self) -> str:
        """Sante de tous les services JARVIS."""
        output = self._run("systemctl --user list-units 'jarvis-*' --no-pager --no-legend", shell=True)
        lines = output.strip().split("\n")
        active = sum(1 for l in lines if "active" in l and "inactive" not in l)
        inactive = sum(1 for l in lines if "inactive" in l or "dead" in l)
        failed = sum(1 for l in lines if "failed" in l)
        return f"Services JARVIS: {active} actifs, {inactive} inactifs, {failed} en erreur"

    def jarvis_db_status(self) -> str:
        """Statut des bases SQL JARVIS."""
        try:
            from src.db_boot_validator import get_db_boot_summary
            return f"Bases SQL: {get_db_boot_summary()}"
        except Exception as e:
            return f"Erreur lecture status DB: {e}"

    def jarvis_gpu_temperatures(self) -> str:
        """Temperatures GPU en temps reel."""
        if shutil.which("nvidia-smi"):
            output = self._run(["nvidia-smi", "--query-gpu=index,name,temperature.gpu,fan.speed,power.draw",
                               "--format=csv,noheader,nounits"])
            if "ERREUR" not in output:
                gpus = []
                for line in output.strip().split("\n"):
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 5:
                        gpus.append(f"GPU{parts[0]}: {parts[1]} — {parts[2]}°C, fan {parts[3]}%, {parts[4]}W")
                return "\n".join(gpus)
        return "Pas de GPU NVIDIA"

    def jarvis_vram_usage(self) -> str:
        """Usage VRAM de toutes les GPUs."""
        if shutil.which("nvidia-smi"):
            output = self._run(["nvidia-smi", "--query-gpu=index,memory.used,memory.total,utilization.gpu",
                               "--format=csv,noheader,nounits"])
            if "ERREUR" not in output:
                gpus = []
                for line in output.strip().split("\n"):
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 4:
                        used, total = int(parts[1]), int(parts[2])
                        pct = round(used / total * 100) if total > 0 else 0
                        gpus.append(f"GPU{parts[0]}: {used}/{total} MB ({pct}%), util {parts[3]}%")
                return "VRAM:\n" + "\n".join(f"  {g}" for g in gpus)
        return "Pas de GPU NVIDIA"

    def jarvis_restart_service(self, name: str) -> str:
        """Redemarrer un service JARVIS specifique."""
        svc = name if name.startswith("jarvis-") else f"jarvis-{name}"
        self._run(["systemctl", "--user", "restart", f"{svc}.service"])
        status = self._run(["systemctl", "--user", "is-active", f"{svc}.service"])
        return f"Service {svc}: {status}"

    def jarvis_start_service(self, name: str) -> str:
        """Demarrer un service JARVIS specifique."""
        svc = name if name.startswith("jarvis-") else f"jarvis-{name}"
        self._run(["systemctl", "--user", "start", f"{svc}.service"])
        status = self._run(["systemctl", "--user", "is-active", f"{svc}.service"])
        return f"Service {svc}: {status}"

    def jarvis_stop_service(self, name: str) -> str:
        """Arreter un service JARVIS specifique."""
        svc = name if name.startswith("jarvis-") else f"jarvis-{name}"
        self._run(["systemctl", "--user", "stop", f"{svc}.service"])
        return f"Service {svc} arrete"

    # ===================================================================
    # LINUX — Reseau avance
    # ===================================================================
    def linux_ping(self, host: str = "8.8.8.8") -> str:
        """Ping un hote (4 paquets)."""
        output = self._run(["ping", "-c", "4", "-W", "2", host], timeout=15)
        # Extraire la derniere ligne (stats)
        lines = output.strip().split("\n")
        for line in reversed(lines):
            if "rtt" in line or "min/avg/max" in line:
                return f"Ping {host}: {line}"
            if "packets" in line:
                return f"Ping {host}: {line}"
        return output[:200]

    def linux_dns_lookup(self, domain: str) -> str:
        """Resolution DNS d'un domaine."""
        output = self._run(["dig", "+short", domain])
        if not output or "ERREUR" in output:
            output = self._run(["nslookup", domain])
        return output[:300] or f"Resolution echouee pour {domain}"

    def linux_public_ip(self) -> str:
        """Obtenir l'IP publique."""
        import urllib.request
        try:
            with urllib.request.urlopen("https://ifconfig.me", timeout=5) as resp:
                return f"IP publique: {resp.read().decode().strip()}"
        except Exception:
            return self._run(["curl", "-s", "--max-time", "5", "https://ifconfig.me"])

    def linux_wifi_list(self) -> str:
        """Lister les reseaux WiFi disponibles."""
        output = self._run(["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "dev", "wifi", "list"])
        lines = output.strip().split("\n")[:15]
        result = []
        for line in lines:
            parts = line.split(":")
            if len(parts) >= 3 and parts[0]:
                result.append(f"  {parts[0]:25s} Signal: {parts[1]}% ({parts[2]})")
        return f"{len(result)} reseaux WiFi:\n" + "\n".join(result) if result else "Aucun reseau WiFi"

    def linux_wifi_connect(self, ssid: str) -> str:
        """Connecter a un reseau WiFi."""
        output = self._run(["nmcli", "dev", "wifi", "connect", ssid], timeout=30)
        return output or f"Connexion a {ssid}"

    def linux_speed_test(self) -> str:
        """Test de vitesse internet simplifie."""
        import urllib.request
        t0 = time.time()
        try:
            with urllib.request.urlopen("http://speedtest.tele2.net/1MB.zip", timeout=15) as resp:
                data = resp.read()
                duration = time.time() - t0
                speed_mbps = round(len(data) * 8 / duration / 1_000_000, 1)
                return f"Debit: ~{speed_mbps} Mbps (1 Mo en {duration:.1f}s)"
        except Exception as e:
            return f"Test de vitesse echoue: {e}"

    # ===================================================================
    # LINUX — Securite
    # ===================================================================
    def linux_who_logged(self) -> str:
        """Qui est connecte au systeme."""
        return self._run(["who"])

    def linux_last_logins(self) -> str:
        """Dernieres connexions."""
        return self._run(["last", "-n", "10"])

    def linux_firewall_status(self) -> str:
        """Statut du firewall."""
        output = self._run(["sudo", "ufw", "status"])
        if "ERREUR" in output or "not found" in output:
            output = self._run(["sudo", "iptables", "-L", "--line-numbers", "-n"])
        return output[:500]

    # ===================================================================
    # LINUX — Energie / Performance
    # ===================================================================
    def linux_cpu_temperatures(self) -> str:
        """Temperatures CPU."""
        if shutil.which("sensors"):
            output = self._run(["sensors"])
            # Filtrer pour garder les lignes de temperature
            lines = [l for l in output.split("\n") if "°C" in l or "Tctl" in l or "Core" in l]
            return "\n".join(lines[:10]) if lines else output[:300]
        return "lm-sensors non installe"

    def linux_battery_status(self) -> str:
        """Statut batterie (laptops)."""
        bat_path = Path("/sys/class/power_supply/BAT0/capacity")
        if bat_path.exists():
            capacity = bat_path.read_text().strip()
            status_path = Path("/sys/class/power_supply/BAT0/status")
            status = status_path.read_text().strip() if status_path.exists() else "Inconnu"
            return f"Batterie: {capacity}% ({status})"
        return "Pas de batterie detectee (desktop)"

    def linux_swap_usage(self) -> str:
        """Usage swap."""
        output = self._run(["free", "-h"])
        for line in output.split("\n"):
            if "Swap" in line or "Échange" in line:
                return f"Swap: {line.strip()}"
        return "Swap non configure"

    def linux_load_average(self) -> str:
        """Charge moyenne du systeme."""
        try:
            with open("/proc/loadavg") as f:
                parts = f.read().split()
                return f"Charge: {parts[0]} (1min), {parts[1]} (5min), {parts[2]} (15min)"
        except Exception:
            return self._run(["uptime"])

    # ===================================================================
    # LINUX — Clipboard avance
    # ===================================================================
    def linux_clipboard_clear(self) -> str:
        """Vider le presse-papiers."""
        if shutil.which("xclip"):
            self._run(["bash", "-c", "echo -n '' | xclip -selection clipboard"])
        elif shutil.which("xsel"):
            self._run(["xsel", "--clipboard", "--clear"])
        return "Presse-papiers vide"

    def linux_clipboard_type(self) -> str:
        """Coller le presse-papiers en tapant (pour les apps qui ne supportent pas Ctrl+V)."""
        content = ""
        if shutil.which("xclip"):
            content = self._run(["xclip", "-selection", "clipboard", "-o"])
        elif shutil.which("xsel"):
            content = self._run(["xsel", "--clipboard", "--output"])
        if content:
            self._xdotool("type", "--clearmodifiers", "--delay", "10", content)
            return f"Colle par frappe: {content[:50]}..."
        return "Presse-papiers vide"

    # ===================================================================
    # LINUX — Gestion ecrans multiples
    # ===================================================================
    def linux_screens_info(self) -> str:
        """Informations sur les ecrans connectes."""
        output = self._run(["xrandr", "--current"])
        screens = []
        for line in output.split("\n"):
            if " connected" in line:
                match = re.search(r"(\S+)\s+connected\s+(?:primary\s+)?(\d+x\d+)", line)
                if match:
                    screens.append(f"  {match.group(1)}: {match.group(2)}")
                else:
                    screens.append(f"  {line.split()[0]}: connecte")
        return f"{len(screens)} ecran(s):\n" + "\n".join(screens)

    # ===================================================================
    # LINUX — Raccourcis systeme utiles
    # ===================================================================
    def linux_open_settings_section(self, section: str) -> str:
        """Ouvrir une section specifique des parametres GNOME."""
        sections_map = {
            "wifi": "wifi", "reseau": "network", "son": "sound", "audio": "sound",
            "affichage": "display", "ecran": "display", "bluetooth": "bluetooth",
            "imprimante": "printers", "clavier": "keyboard", "souris": "mouse",
            "alimentation": "power", "energie": "power", "utilisateurs": "user-accounts",
            "region": "region", "langue": "region", "confidentialite": "privacy",
            "a propos": "info-overview", "info": "info-overview",
        }
        gnome_section = sections_map.get(section.lower(), section)
        try:
            subprocess.Popen(
                ["gnome-control-center", gnome_section],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
            )
            return f"Parametres {section} ouverts"
        except Exception as e:
            return f"ERREUR: {e}"

    # ===================================================================
    # VOICE LEARNING — Rapport et apprentissage vocal
    # ===================================================================
    # ===================================================================
    # MACROS VOCALES — Enregistrer et rejouer des sequences
    # ===================================================================
    def macro_list(self) -> str:
        """Lister les macros vocales enregistrees."""
        from src.voice_macros import macro_manager
        return macro_manager.list_macros()

    def macro_start(self, name: str = "nouvelle") -> str:
        """Demarrer l'enregistrement d'une macro."""
        from src.voice_macros import macro_manager
        return macro_manager.start_recording(name)

    def macro_stop(self) -> str:
        """Arreter l'enregistrement de la macro."""
        from src.voice_macros import macro_manager
        return macro_manager.stop_recording()

    def macro_play(self, name: str) -> str:
        """Rejouer une macro par son nom."""
        from src.voice_macros import macro_manager
        return macro_manager.play(name)

    def macro_delete(self, name: str) -> str:
        """Supprimer une macro."""
        from src.voice_macros import macro_manager
        return macro_manager.delete_macro(name)

    def macro_status(self) -> str:
        """Statut de l'enregistrement en cours."""
        from src.voice_macros import macro_manager
        return macro_manager.get_recording_status()

    def voice_report(self) -> str:
        """Rapport de qualite vocale (taux de succes, top echecs)."""
        try:
            from src.voice_learning import get_voice_report
            return get_voice_report(hours=24)
        except Exception as e:
            return f"Rapport vocal indisponible: {e}"

    def voice_learn(self) -> str:
        """Lancer l'apprentissage vocal automatique."""
        try:
            from src.voice_learning import learn_and_improve
            result = learn_and_improve(auto_apply=True)
            applied = result.get("applied", 0)
            suggestions = result.get("suggestions_count", 0)
            analysis = result.get("analysis", {})
            rate = analysis.get("success_rate", "?")
            return f"Apprentissage: {suggestions} suggestions, {applied} appliquees. Taux reussite: {rate}%"
        except Exception as e:
            return f"Apprentissage echoue: {e}"

    def voice_corrections_count(self) -> str:
        """Nombre de corrections vocales en base."""
        try:
            from src.db_boot_validator import get_voice_cache
            cache = get_voice_cache()
            return f"{len(cache.get('corrections', {}))} corrections vocales actives"
        except Exception as e:
            return f"Erreur: {e}"

    # ===================================================================
    # SPOTIFY — Controle avance via playerctl/dbus
    # ===================================================================
    def spotify_now_playing(self) -> str:
        """Quelle chanson joue actuellement sur Spotify."""
        artist = self._run(["playerctl", "-p", "spotify", "metadata", "artist"])
        title = self._run(["playerctl", "-p", "spotify", "metadata", "title"])
        if artist and title and "ERREUR" not in artist:
            return f"En cours: {artist} — {title}"
        # Fallback: n'importe quel lecteur
        artist = self._run(["playerctl", "metadata", "artist"])
        title = self._run(["playerctl", "metadata", "title"])
        if artist and title and "ERREUR" not in artist:
            return f"En cours: {artist} — {title}"
        return "Aucune musique en lecture"

    def spotify_shuffle(self, on_off: str = "toggle") -> str:
        """Activer/desactiver le shuffle Spotify."""
        current = self._run(["playerctl", "-p", "spotify", "shuffle"])
        if on_off == "toggle":
            new_val = "Off" if current.strip().lower() == "on" else "On"
        else:
            new_val = "On" if on_off.lower() in ("on", "oui", "activer") else "Off"
        self._run(["playerctl", "-p", "spotify", "shuffle", new_val])
        return f"Shuffle {'active' if new_val == 'On' else 'desactive'}"

    def spotify_repeat(self, mode: str = "toggle") -> str:
        """Changer le mode de repetition Spotify."""
        modes = {"none": "None", "track": "Track", "playlist": "Playlist"}
        if mode in modes:
            self._run(["playerctl", "-p", "spotify", "loop", modes[mode]])
            return f"Repetition: {mode}"
        # Toggle: None -> Track -> Playlist -> None
        current = self._run(["playerctl", "-p", "spotify", "loop"]).strip().lower()
        cycle = {"none": "Track", "track": "Playlist", "playlist": "None"}
        new_mode = cycle.get(current, "None")
        self._run(["playerctl", "-p", "spotify", "loop", new_mode])
        return f"Repetition: {new_mode.lower()}"

    def spotify_volume(self, level: str = "50") -> str:
        """Regler le volume Spotify (0-100)."""
        try:
            vol = max(0, min(100, int(level))) / 100
            self._run(["playerctl", "-p", "spotify", "volume", str(vol)])
            return f"Volume Spotify: {int(vol * 100)}%"
        except ValueError:
            return f"Volume invalide: {level}"

    def spotify_open(self) -> str:
        """Ouvrir Spotify."""
        try:
            subprocess.Popen(["spotify"], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, start_new_session=True)
            return "Spotify ouvert"
        except FileNotFoundError:
            return "Spotify non installe"

    def spotify_like(self) -> str:
        """Liker la chanson en cours (raccourci clavier Spotify)."""
        # Spotify Linux: pas de raccourci natif, utiliser dbus
        self._run(["dbus-send", "--print-reply", "--dest=org.mpris.MediaPlayer2.spotify",
                   "/org/mpris/MediaPlayer2", "org.mpris.MediaPlayer2.Player.Like"])
        return "Chanson likee"

    # ===================================================================
    # TRADING — Pilotage vocal du trading JARVIS
    # ===================================================================
    def trading_scan(self) -> str:
        """Lancer un scan trading rapide."""
        import urllib.request
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:8901/process",
                data=json.dumps({"action": "trading_scan", "params": {"min_score": 75, "top": 5}}).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
                return f"Scan trading: {json.dumps(data, ensure_ascii=False)[:300]}"
        except Exception as e:
            return f"Scan trading echoue: {e}"

    def trading_positions(self) -> str:
        """Voir les positions trading ouvertes."""
        import urllib.request
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:8901/process",
                data=json.dumps({"action": "trading_positions"}).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                if isinstance(data, list):
                    if not data:
                        return "Aucune position ouverte"
                    lines = [f"  {p.get('symbol', '?')}: {p.get('pnl', '?')}%" for p in data[:5]]
                    return f"{len(data)} position(s):\n" + "\n".join(lines)
                return str(data)[:300]
        except Exception as e:
            return f"Positions indisponibles: {e}"

    def trading_signals(self) -> str:
        """Voir les signaux trading en attente."""
        import sqlite3 as _sqlite3
        try:
            conn = _sqlite3.connect(str(Path(__file__).parent.parent / "data" / "sniper.db"))
            rows = conn.execute("SELECT symbol, type, ts FROM signals ORDER BY ts DESC LIMIT 5").fetchall()
            conn.close()
            if not rows:
                return "Aucun signal trading recent"
            lines = [f"  {r[0]}: {r[1]}" for r in rows]
            return f"{len(rows)} signal(s) recents:\n" + "\n".join(lines)
        except Exception as e:
            return f"Signaux indisponibles: {e}"

    def trading_status(self) -> str:
        """Statut general du trading JARVIS."""
        sentinel = self._run(["systemctl", "--user", "is-active", "jarvis-trading-sentinel.service"])
        positions = "actif" if sentinel.strip() == "active" else "inactif"
        return f"Trading sentinel: {positions}"

    # ===================================================================
    # WORKFLOWS — Controle n8n et pipelines
    # ===================================================================
    def workflow_list(self) -> str:
        """Lister les workflows actifs."""
        import urllib.request
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:5678/api/v1/workflows?active=true",
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                workflows = data.get("data", [])
                if not workflows:
                    return "Aucun workflow actif"
                lines = [f"  {w.get('name', '?')}" for w in workflows[:10]]
                return f"{len(workflows)} workflow(s) actifs:\n" + "\n".join(lines)
        except Exception as e:
            return f"n8n indisponible: {e}"

    def workflow_status(self) -> str:
        """Statut de n8n."""
        n8n = self._run(["systemctl", "--user", "is-active", "jarvis-n8n.service"])
        return f"n8n: {n8n.strip()}"

    # ===================================================================
    # SYSTEM — Commandes systeme supplementaires
    # ===================================================================
    def linux_hostname(self) -> str:
        """Nom de la machine."""
        return self._run(["hostname"])

    def linux_kernel_version(self) -> str:
        """Version du noyau Linux."""
        return self._run(["uname", "-r"])

    def linux_os_info(self) -> str:
        """Informations sur le systeme d'exploitation."""
        output = self._run(["lsb_release", "-d", "-s"])
        kernel = self._run(["uname", "-r"])
        return f"{output}, Kernel {kernel}"

    def linux_users_logged(self) -> str:
        """Nombre d'utilisateurs connectes."""
        output = self._run(["who", "-q"])
        return output

    def linux_scheduled_tasks(self) -> str:
        """Taches planifiees (crontab)."""
        output = self._run(["crontab", "-l"])
        if "no crontab" in output.lower() or "ERREUR" in output:
            return "Aucune tache cron"
        lines = [l for l in output.split("\n") if l.strip() and not l.startswith("#")]
        return f"{len(lines)} tache(s) cron:\n" + "\n".join(lines[:10])

    def linux_memory_detailed(self) -> str:
        """Informations memoire detaillees."""
        return self._run(["free", "-h", "--wide"])

    def linux_system_summary(self) -> str:
        """Resume complet du systeme (CPU, RAM, GPU, disque, uptime)."""
        cpu = self.linux_cpu_usage()
        ram = self.linux_memory_usage()
        disk = self.linux_disk_usage()
        uptime = self.linux_uptime()
        load = self.linux_load_average()
        gpu_count = len(self._run(["nvidia-smi", "-L"]).strip().split("\n")) if shutil.which("nvidia-smi") else 0
        return f"{cpu}\n{ram}\n{disk}\n{uptime}\n{load}\nGPUs: {gpu_count}"

    def jarvis_full_dashboard(self) -> str:
        """Tableau de bord JARVIS complet — resume systeme + cluster + services + trading."""
        sections = []

        # 1. Systeme
        cpu = self.linux_cpu_usage()
        ram = self.linux_memory_usage()
        load = self.linux_load_average()
        uptime = self.linux_uptime()
        sections.append(f"SYSTEME: {cpu}, {ram}, {load}, {uptime}")

        # 2. GPUs
        if shutil.which("nvidia-smi"):
            gpu_output = self._run(["nvidia-smi", "--query-gpu=index,temperature.gpu,utilization.gpu,memory.used,memory.total",
                                   "--format=csv,noheader,nounits"])
            if "ERREUR" not in gpu_output:
                gpu_lines = []
                for line in gpu_output.strip().split("\n"):
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 5:
                        gpu_lines.append(f"GPU{parts[0]}: {parts[1]}°C, {parts[2]}%util, {parts[3]}/{parts[4]}MB")
                sections.append("GPUs: " + " | ".join(gpu_lines))

        # 3. Services JARVIS
        svc_output = self._run("systemctl --user list-units 'jarvis-*' --no-pager --no-legend 2>/dev/null | grep -c 'active running'", shell=True)
        sections.append(f"SERVICES: {svc_output.strip()} actifs")

        # 4. Cluster
        import urllib.request
        cluster_parts = []
        for name, url in [("M1", "http://127.0.0.1:1234/api/v1/models"), ("OL1", "http://127.0.0.1:11434/api/tags")]:
            try:
                with urllib.request.urlopen(url, timeout=2) as resp:
                    cluster_parts.append(f"{name}:OK")
            except Exception:
                cluster_parts.append(f"{name}:OFF")
        sections.append(f"CLUSTER: {', '.join(cluster_parts)}")

        # 5. Trading
        sentinel = self._run(["systemctl", "--user", "is-active", "jarvis-trading-sentinel.service"])
        sections.append(f"TRADING: sentinel {sentinel.strip()}")

        # 6. Voice analytics
        try:
            from src.voice_learning import analyze_failures
            analysis = analyze_failures(hours=24)
            if analysis.get("total", 0) > 0:
                sections.append(f"VOICE: {analysis['total']} cmds, {analysis['success_rate']}% reussite, {analysis['avg_latency_ms']}ms moy")
        except Exception:
            pass

        # 7. Disk
        disk = self.linux_disk_usage()
        sections.append(f"DISQUE: {disk}")

        return "=== JARVIS DASHBOARD ===\n" + "\n".join(sections)

    # ===================================================================
    # DOCKER — Gestion containers par voix
    # ===================================================================
    def docker_ps(self) -> str:
        """Lister les containers Docker en cours."""
        if not shutil.which("docker"):
            return "Docker non installe"
        output = self._run(["docker", "ps", "--format", "table {{.Names}}\t{{.Status}}\t{{.Ports}}"])
        lines = output.strip().split("\n")
        if len(lines) <= 1:
            return "Aucun container Docker en cours"
        return f"{len(lines)-1} container(s):\n" + "\n".join(f"  {l}" for l in lines[1:10])

    def docker_ps_all(self) -> str:
        """Lister tous les containers (y compris arretes)."""
        if not shutil.which("docker"):
            return "Docker non installe"
        output = self._run(["docker", "ps", "-a", "--format", "table {{.Names}}\t{{.Status}}"])
        lines = output.strip().split("\n")
        return f"{len(lines)-1} container(s) total:\n" + "\n".join(f"  {l}" for l in lines[1:15])

    def docker_images(self) -> str:
        """Lister les images Docker."""
        if not shutil.which("docker"):
            return "Docker non installe"
        output = self._run(["docker", "images", "--format", "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"])
        lines = output.strip().split("\n")
        return f"{len(lines)-1} image(s):\n" + "\n".join(f"  {l}" for l in lines[1:15])

    def docker_start(self, name: str) -> str:
        """Demarrer un container Docker."""
        output = self._run(["docker", "start", name])
        return output or f"Container {name} demarre"

    def docker_stop(self, name: str) -> str:
        """Arreter un container Docker."""
        output = self._run(["docker", "stop", name])
        return output or f"Container {name} arrete"

    def docker_restart(self, name: str) -> str:
        """Redemarrer un container Docker."""
        output = self._run(["docker", "restart", name])
        return output or f"Container {name} redemarre"

    def docker_logs(self, name: str) -> str:
        """Voir les logs d'un container Docker."""
        output = self._run(["docker", "logs", "--tail", "15", name])
        return output[:1000] or f"Pas de logs pour {name}"

    def docker_stats(self) -> str:
        """Stats Docker (CPU, RAM par container)."""
        if not shutil.which("docker"):
            return "Docker non installe"
        output = self._run(["docker", "stats", "--no-stream",
                           "--format", "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"])
        return output[:1000] or "Aucun container en cours"

    def docker_compose_up(self, path: str = "") -> str:
        """Docker compose up."""
        cmd = ["docker", "compose", "up", "-d"]
        if path:
            cmd = ["docker", "compose", "-f", path, "up", "-d"]
        return self._run(cmd, timeout=60)

    def docker_compose_down(self, path: str = "") -> str:
        """Docker compose down."""
        cmd = ["docker", "compose", "down"]
        if path:
            cmd = ["docker", "compose", "-f", path, "down"]
        return self._run(cmd, timeout=30)

    # ===================================================================
    # GIT — Controle vocal de Git
    # ===================================================================
    def git_status(self) -> str:
        """Git status du repertoire courant."""
        output = self._run(["git", "-C", str(Path.home() / "jarvis"), "status", "--short"])
        if not output or "ERREUR" in output:
            return "Pas de depot git ou erreur"
        lines = output.strip().split("\n")
        return f"Git: {len(lines)} fichier(s) modifie(s):\n" + "\n".join(f"  {l}" for l in lines[:10])

    def git_log(self) -> str:
        """Derniers commits git."""
        output = self._run(["git", "-C", str(Path.home() / "jarvis"), "log", "--oneline", "-10"])
        return output or "Pas de commits"

    def git_branch(self) -> str:
        """Branche git actuelle."""
        output = self._run(["git", "-C", str(Path.home() / "jarvis"), "branch", "--show-current"])
        return f"Branche: {output}" if output else "Pas de depot git"

    def git_pull(self) -> str:
        """Git pull."""
        return self._run(["git", "-C", str(Path.home() / "jarvis"), "pull"], timeout=30)

    # ===================================================================
    # RACCOURCIS PRODUCTIVITE
    # ===================================================================
    # ===================================================================
    # WIDGETS & DASHBOARD — Contrôle vocal
    # ===================================================================
    def widgets_start(self) -> str:
        """Activer les widgets desktop Conky."""
        self._run(["bash", str(Path.home() / "jarvis/scripts/jarvis_widgets.sh"), "start"])
        return "Widgets JARVIS activés"

    def widgets_stop(self) -> str:
        """Désactiver les widgets desktop."""
        self._run(["bash", str(Path.home() / "jarvis/scripts/jarvis_widgets.sh"), "stop"])
        return "Widgets JARVIS désactivés"

    def widgets_restart(self) -> str:
        """Redémarrer les widgets."""
        self._run(["bash", str(Path.home() / "jarvis/scripts/jarvis_widgets.sh"), "restart"])
        return "Widgets JARVIS redémarrés"

    def dashboard_open(self) -> str:
        """Ouvrir le dashboard web JARVIS."""
        self._run(["xdg-open", "http://127.0.0.1:8088"])
        return "Dashboard JARVIS ouvert"

    def dashboard_restart(self) -> str:
        """Redémarrer le service dashboard web."""
        self._run(["systemctl", "--user", "restart", "jarvis-dashboard-web.service"])
        return "Dashboard web redémarré"

    # ===================================================================
    # PROFILS JARVIS — Basculer entre modes
    # ===================================================================
    # ===================================================================
    # ROUTINES JARVIS — Séquences automatiques
    # ===================================================================
    # ===================================================================
    # CONTEXTE INTELLIGENT — App active
    # ===================================================================
    # ===================================================================
    # FAVORIS — Top commandes et raccourcis
    # ===================================================================
    def voice_favorites(self) -> str:
        """Afficher les commandes vocales les plus utilisées."""
        try:
            import sqlite3 as _sq
            conn = _sq.connect(str(Path(__file__).parent.parent / "data" / "jarvis.db"), timeout=5)
            rows = conn.execute(
                "SELECT text, COUNT(*) as cnt FROM voice_analytics WHERE success=1 GROUP BY text ORDER BY cnt DESC LIMIT 15"
            ).fetchall()
            conn.close()
            if not rows:
                return "Pas encore de favoris — utilisez les commandes vocales!"
            lines = [f"  {i+1:2d}. {r[0][:30]:30s} ({r[1]}x)" for i, r in enumerate(rows)]
            return f"Top {len(lines)} commandes:\n" + "\n".join(lines)
        except Exception as e:
            return f"Erreur: {e}"

    def voice_stats_detailed(self) -> str:
        """Statistiques vocales détaillées."""
        try:
            import sqlite3 as _sq
            conn = _sq.connect(str(Path(__file__).parent.parent / "data" / "jarvis.db"), timeout=5)
            total = conn.execute("SELECT COUNT(*) FROM voice_analytics").fetchone()[0]
            success = conn.execute("SELECT COUNT(*) FROM voice_analytics WHERE success=1").fetchone()[0]
            avg_lat = conn.execute("SELECT AVG(latency_ms) FROM voice_analytics WHERE success=1").fetchone()[0] or 0
            today = conn.execute("SELECT COUNT(*) FROM voice_analytics WHERE timestamp > strftime('%s','now','-1 day')").fetchone()[0]
            conn.close()
            rate = round(success / total * 100, 1) if total > 0 else 0
            return (f"Statistiques vocales:\n"
                    f"  Total: {total} commandes\n"
                    f"  Succès: {rate}%\n"
                    f"  Latence moyenne: {round(avg_lat)}ms\n"
                    f"  Aujourd'hui: {today} commandes")
        except Exception as e:
            return f"Erreur: {e}"

    def context_info(self) -> str:
        """Infos sur l'application active et le contexte."""
        from src.app_context import get_active_app, get_app_category, CONTEXTUAL_HINTS
        app = get_active_app()
        cat = get_app_category(app)
        hints = CONTEXTUAL_HINTS.get(cat, {})
        parts = [f"Application: {app.get('class', '?')} ({cat})",
                 f"Titre: {app.get('title', '?')[:60]}"]
        if hints:
            parts.append("Commandes contextuelles:")
            for k, v in hints.items():
                parts.append(f"  '{k}' → {v}")
        return "\n".join(parts)

    # ===================================================================
    # SYSTEMD COMPLET — Tous services Linux
    # ===================================================================
    def systemd_list_all(self) -> str:
        """Lister tous les services système actifs."""
        output = self._run("systemctl list-units --type=service --state=active --no-pager --no-legend | head -20", shell=True)
        lines = output.strip().split("\n")
        return f"{len(lines)} services actifs (top 20):\n" + "\n".join(f"  {l.split()[0]}" for l in lines)

    def systemd_search(self, name: str) -> str:
        """Chercher un service systemd."""
        output = self._run(f"systemctl list-units --type=service --all --no-pager --no-legend | grep -i '{name}'", shell=True)
        if not output:
            return f"Aucun service contenant '{name}'"
        lines = output.strip().split("\n")[:10]
        return f"{len(lines)} service(s) trouvé(s):\n" + "\n".join(f"  {l.split()[0]} [{l.split()[2] if len(l.split())>2 else '?'}]" for l in lines)

    def systemd_enable(self, name: str) -> str:
        """Activer un service au démarrage."""
        self._run(["systemctl", "--user", "enable", f"{name}.service"])
        return f"Service {name} activé au boot"

    def systemd_disable(self, name: str) -> str:
        """Désactiver un service au démarrage."""
        self._run(["systemctl", "--user", "disable", f"{name}.service"])
        return f"Service {name} désactivé au boot"

    def systemd_timers(self) -> str:
        """Lister les timers systemd actifs."""
        output = self._run("systemctl --user list-timers --no-pager --no-legend", shell=True)
        lines = output.strip().split("\n")[:10]
        return f"{len(lines)} timer(s):\n" + "\n".join(f"  {l}" for l in lines)

    # ===================================================================
    # RÉSEAU AVANCÉ — SSH, tunnels, VPN, scan
    # ===================================================================
    def ssh_to_m2(self) -> str:
        """Ouvrir un terminal SSH vers M2."""
        subprocess.Popen(["gnome-terminal", "--title=SSH M2", "--",
                         "ssh", "turbo@192.168.1.26"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return "Terminal SSH M2 ouvert"

    def ssh_to_server(self) -> str:
        """Ouvrir un terminal SSH vers le Server."""
        subprocess.Popen(["gnome-terminal", "--title=SSH Server", "--",
                         "ssh", "turbo@192.168.1.113"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return "Terminal SSH Server ouvert"

    def network_connections(self) -> str:
        """Connexions réseau actives."""
        output = self._run(["ss", "-tunp"])
        lines = output.strip().split("\n")
        return f"{len(lines)-1} connexion(s) active(s):\n" + "\n".join(f"  {l}" for l in lines[1:10])

    def network_scan_local(self) -> str:
        """Scanner le réseau local."""
        if shutil.which("nmap"):
            output = self._run(["nmap", "-sn", "192.168.1.0/24"], timeout=30)
            hosts = [l for l in output.split("\n") if "Nmap scan report" in l]
            return f"{len(hosts)} hôte(s) sur le réseau:\n" + "\n".join(f"  {h.split('for ')[-1]}" for h in hosts[:15])
        # Fallback arp
        output = self._run(["arp", "-a"])
        return output[:500]

    def network_wake_m2(self) -> str:
        """Wake-on-LAN pour M2."""
        if shutil.which("wakeonlan"):
            # MAC M2 à adapter
            self._run(["wakeonlan", "XX:XX:XX:XX:XX:XX"])
            return "Wake-on-LAN envoyé à M2"
        return "wakeonlan non installé"

    def vpn_status(self) -> str:
        """Statut VPN."""
        output = self._run(["nmcli", "connection", "show", "--active"])
        vpn_lines = [l for l in output.split("\n") if "vpn" in l.lower() or "wireguard" in l.lower()]
        if vpn_lines:
            return f"VPN actif: {vpn_lines[0]}"
        return "Aucun VPN actif"

    def routine_run(self, name: str) -> str:
        """Exécuter une routine JARVIS."""
        from src.jarvis_routines import run_routine
        return run_routine(name)

    def routine_list(self) -> str:
        """Lister les routines disponibles."""
        from src.jarvis_routines import list_routines
        return list_routines()

    def profile_switch(self, name: str) -> str:
        """Basculer vers un profil JARVIS."""
        from src.jarvis_profiles import switch_profile
        return switch_profile(name)

    def profile_list(self) -> str:
        """Lister les profils disponibles."""
        from src.jarvis_profiles import list_profiles
        return list_profiles()

    def profile_current(self) -> str:
        """Profil JARVIS actuel."""
        from src.jarvis_profiles import get_current_profile
        return f"Profil actuel: {get_current_profile()}"

    def wallpaper_refresh(self) -> str:
        """Regénérer le fond d'écran JARVIS avec données temps réel."""
        self._run(["python", str(Path(__file__).parent.parent / "scripts/jarvis_dynamic_wallpaper.py")])
        return "Fond d'écran JARVIS régénéré avec données GPU temps réel"

    def screenshot_desktop(self) -> str:
        """Capture d'écran complète avec widgets."""
        ts = int(time.time())
        path = str(Path.home() / f"Pictures/Screenshots/jarvis_desktop_{ts}.png")
        if shutil.which("scrot"):
            self._run(["scrot", "-d", "1", path])
        elif shutil.which("gnome-screenshot"):
            self._run(["gnome-screenshot", "-f", path])
        return f"Capture sauvegardée: {path}"

    # ===================================================================
    # COMMANDES AVANCÉES — Screenshot IA, OCR clipboard, recherche fichiers IA
    # ===================================================================
    def screenshot_annotate(self) -> str:
        """Capture d'écran + description IA automatique."""
        ts = int(time.time())
        path = str(Path.home() / f"Pictures/Screenshots/jarvis_annotated_{ts}.png")
        if shutil.which("scrot"):
            self._run(["scrot", path])
        if not os.path.exists(path):
            return "Capture échouée"
        # Demander à l'IA de décrire
        description = self.linux_ask_ia(f"Décris cette capture d'écran sauvegardée en {path}")
        self._run(["notify-send", "JARVIS Screenshot", description[:200], "-i", "jarvis"])
        return f"Capture annotée: {path}\n{description[:200]}"

    def ocr_to_clipboard(self) -> str:
        """OCR plein écran et copie le texte dans le presse-papiers."""
        if not shutil.which("scrot") or not shutil.which("tesseract"):
            return "scrot et tesseract requis"
        ts = int(time.time())
        screenshot = f"/tmp/jarvis_ocr_{ts}.png"
        self._run(["scrot", screenshot])
        if not os.path.exists(screenshot):
            return "Capture échouée"
        text = self._run(["tesseract", screenshot, "stdout", "-l", "fra+eng", "--psm", "3"], timeout=20)
        os.unlink(screenshot)
        if text and shutil.which("xclip"):
            subprocess.run(["xclip", "-selection", "clipboard"], input=text, text=True, timeout=5, capture_output=True)
            lines = len(text.strip().split("\n"))
            return f"OCR: {lines} lignes copiées dans le presse-papiers"
        return "Aucun texte détecté par OCR"

    def search_files_ia(self, query: str) -> str:
        """Recherche intelligente de fichiers par description IA."""
        # Chercher par nom d'abord
        output = self._run(["find", str(Path.home()), "-maxdepth", "4", "-iname", f"*{query}*", "-type", "f"], timeout=10)
        files = [f for f in output.strip().split("\n") if f][:8]
        if files:
            return f"{len(files)} fichier(s) trouvé(s):\n" + "\n".join(f"  {f}" for f in files)
        # Chercher dans les noms de dossiers
        output = self._run(["find", str(Path.home()), "-maxdepth", "3", "-iname", f"*{query}*", "-type", "d"], timeout=10)
        dirs = [d for d in output.strip().split("\n") if d][:5]
        if dirs:
            return f"{len(dirs)} dossier(s) trouvé(s):\n" + "\n".join(f"  {d}" for d in dirs)
        return f"Rien trouvé pour '{query}'"

    # ===================================================================
    # NAVIGATEUR AVANCÉ
    # ===================================================================
    def browser_history(self) -> str:
        """Ouvrir l'historique du navigateur."""
        self._xdotool("key", "ctrl+h")
        return "Historique ouvert"

    def browser_downloads(self) -> str:
        """Ouvrir les téléchargements."""
        self._xdotool("key", "ctrl+j")
        return "Téléchargements ouverts"

    def browser_private(self) -> str:
        """Ouvrir un onglet privé."""
        self._xdotool("key", "ctrl+shift+p")
        return "Navigation privée ouverte"

    def browser_devtools(self) -> str:
        """Ouvrir les outils développeur."""
        self._xdotool("key", "F12")
        return "DevTools ouverts"

    def browser_tab_number(self, n: str) -> str:
        """Aller à l'onglet N."""
        try:
            num = int(n)
            if 1 <= num <= 9:
                self._xdotool("key", f"alt+{num}")
                return f"Onglet {num}"
        except ValueError:
            pass
        return f"Numéro d'onglet invalide: {n}"

    def browser_tab_close_others(self) -> str:
        """Fermer tous les onglets sauf l'actif (pas de raccourci natif, utilise le menu)."""
        # Clic droit sur l'onglet + sélection
        self._run(["notify-send", "JARVIS", "Fermez les autres onglets via clic droit"])
        return "Utilisez clic droit sur l'onglet pour fermer les autres"

    def browser_mute_tab(self) -> str:
        """Couper le son de l'onglet actif."""
        self._xdotool("key", "ctrl+m")
        return "Son de l'onglet coupé/rétabli"

    def browser_print(self) -> str:
        """Imprimer la page."""
        self._xdotool("key", "ctrl+p")
        return "Impression ouverte"

    def browser_save_page(self) -> str:
        """Sauvegarder la page."""
        self._xdotool("key", "ctrl+s")
        return "Sauvegarde de page"

    # ===================================================================
    # MULTIMÉDIA PIPEWIRE AVANCÉ
    # ===================================================================
    def audio_list_outputs(self) -> str:
        """Lister les sorties audio disponibles."""
        output = self._run(["pactl", "list", "sinks", "short"])
        lines = output.strip().split("\n")
        results = []
        for line in lines:
            parts = line.split("\t")
            if len(parts) >= 2:
                results.append(f"  {parts[0]}: {parts[1]}")
        return f"{len(results)} sortie(s) audio:\n" + "\n".join(results)

    def audio_list_inputs(self) -> str:
        """Lister les entrées audio (microphones)."""
        output = self._run(["pactl", "list", "sources", "short"])
        lines = output.strip().split("\n")
        results = []
        for line in lines:
            parts = line.split("\t")
            if len(parts) >= 2 and "monitor" not in parts[1].lower():
                results.append(f"  {parts[0]}: {parts[1]}")
        return f"{len(results)} entrée(s) audio:\n" + "\n".join(results)

    def audio_switch_headphones(self) -> str:
        """Basculer vers le casque (Sony WH-1000XM4 ou premier BT)."""
        output = self._run(["pactl", "list", "sinks", "short"])
        for line in output.split("\n"):
            if "bluetooth" in line.lower() or "bluez" in line.lower():
                sink_id = line.split("\t")[0]
                self._run(["pactl", "set-default-sink", sink_id])
                return f"Sortie audio: casque Bluetooth (sink {sink_id})"
        return "Aucun casque Bluetooth trouvé"

    def audio_switch_speakers(self) -> str:
        """Basculer vers les haut-parleurs."""
        output = self._run(["pactl", "list", "sinks", "short"])
        for line in output.split("\n"):
            if "analog" in line.lower() or "alsa" in line.lower():
                sink_id = line.split("\t")[0]
                self._run(["pactl", "set-default-sink", sink_id])
                return f"Sortie audio: haut-parleurs (sink {sink_id})"
        return "Haut-parleurs non trouvés"

    def audio_switch_hdmi(self) -> str:
        """Basculer vers la sortie HDMI."""
        output = self._run(["pactl", "list", "sinks", "short"])
        for line in output.split("\n"):
            if "hdmi" in line.lower():
                sink_id = line.split("\t")[0]
                self._run(["pactl", "set-default-sink", sink_id])
                return f"Sortie audio: HDMI (sink {sink_id})"
        return "Sortie HDMI non trouvée"

    def audio_record_start(self) -> str:
        """Commencer l'enregistrement micro."""
        ts = int(time.time())
        path = str(Path.home() / f"Music/jarvis_recording_{ts}.wav")
        subprocess.Popen(
            ["arecord", "-f", "cd", "-t", "wav", path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return f"Enregistrement démarré: {path}"

    def audio_record_stop(self) -> str:
        """Arrêter l'enregistrement micro."""
        self._run(["pkill", "arecord"])
        return "Enregistrement arrêté"

    def audio_current_output(self) -> str:
        """Sortie audio actuellement utilisée."""
        output = self._run(["pactl", "get-default-sink"])
        return f"Sortie audio: {output}"

    def system_health_voice(self) -> str:
        """Check santé complet vocalisé (court pour TTS)."""
        cpu = self._run("grep 'cpu ' /proc/stat | awk '{u=$2+$4; t=$2+$4+$5; printf \"%.0f\", u/t*100}'", shell=True)
        ram = self._run("free | awk '/Mem:/{printf \"%.0f\", $3/$2*100}'", shell=True)
        gpu_temp = self._run(["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"])
        temps = [int(t.strip()) for t in gpu_temp.split("\n") if t.strip()]
        max_temp = max(temps) if temps else 0
        svc_count = self._run("systemctl --user list-units 'jarvis-*' --no-pager --no-legend | grep -c running", shell=True)

        status = "nominal"
        if int(cpu or 0) > 80 or int(ram or 0) > 85:
            status = "chargé"
        if max_temp > 75:
            status = "attention GPU chaud"

        return f"Système {status}. CPU {cpu}%, RAM {ram}%, GPU max {max_temp} degrés, {svc_count} services"

    def linux_do_not_disturb(self, on_off: str = "on") -> str:
        """Mode ne pas deranger GNOME."""
        val = "true" if on_off.lower() in ("on", "activer", "oui") else "false"
        self._run(["gsettings", "set", "org.gnome.desktop.notifications", "show-banners", "false" if val == "true" else "true"])
        return f"Ne pas deranger {'active' if val == 'true' else 'desactive'}"

    def linux_focus_mode(self) -> str:
        """Active le mode focus: ne pas deranger + mode sombre + ferme les notifs."""
        self.linux_do_not_disturb("on")
        self.linux_dark_mode("on")
        self._run(["notify-send", "JARVIS", "Mode focus active"])
        return "Mode focus: ne pas deranger + mode sombre"

    def linux_break_mode(self) -> str:
        """Desactive le mode focus."""
        self.linux_do_not_disturb("off")
        return "Mode focus desactive"


# ===========================================================================
# VOICE_COMMANDS — Mapping phrases vocales → methodes
# ===========================================================================
VOICE_COMMANDS = {
    # ===================================================================
    # NAVIGATEUR — Sites courants
    # ===================================================================
    "ouvre google": ("browser_open", {"url": "https://google.com"}),
    "va sur google": ("browser_open", {"url": "https://google.com"}),
    "google": ("browser_open", {"url": "https://google.com"}),
    "ouvre youtube": ("browser_open", {"url": "https://youtube.com"}),
    "va sur youtube": ("browser_open", {"url": "https://youtube.com"}),
    "youtube": ("browser_open", {"url": "https://youtube.com"}),
    "ouvre gmail": ("browser_open", {"url": "https://gmail.com"}),
    "va sur gmail": ("browser_open", {"url": "https://gmail.com"}),
    "ouvre twitter": ("browser_open", {"url": "https://x.com"}),
    "ouvre x": ("browser_open", {"url": "https://x.com"}),
    "ouvre facebook": ("browser_open", {"url": "https://facebook.com"}),
    "ouvre reddit": ("browser_open", {"url": "https://reddit.com"}),
    "ouvre github": ("browser_open", {"url": "https://github.com"}),
    "ouvre linkedin": ("browser_open", {"url": "https://linkedin.com"}),
    "ouvre wikipedia": ("browser_open", {"url": "https://fr.wikipedia.org"}),
    "ouvre amazon": ("browser_open", {"url": "https://amazon.fr"}),
    "ouvre netflix": ("browser_open", {"url": "https://netflix.com"}),
    "ouvre twitch": ("browser_open", {"url": "https://twitch.tv"}),
    "ouvre chatgpt": ("browser_open", {"url": "https://chat.openai.com"}),
    "ouvre claude": ("browser_open", {"url": "https://claude.ai"}),
    "ouvre whatsapp": ("browser_open", {"url": "https://web.whatsapp.com"}),
    "ouvre telegram": ("browser_open", {"url": "https://web.telegram.org"}),
    "ouvre instagram": ("browser_open", {"url": "https://instagram.com"}),
    "ouvre tiktok": ("browser_open", {"url": "https://tiktok.com"}),
    "ouvre le site": ("browser_open", {}),
    "va sur le site": ("browser_open", {}),
    "ouvre la page": ("browser_open", {}),
    "navigue vers": ("browser_open", {}),

    # NAVIGATEUR — Recherche
    "cherche sur google": ("browser_search", {}),
    "recherche sur google": ("browser_search", {}),
    "recherche google": ("browser_search", {}),
    "recherche": ("browser_search", {}),
    "cherche": ("browser_search", {}),
    "google cherche": ("browser_search", {}),
    "fais une recherche": ("browser_search", {}),
    "trouve": ("browser_search", {}),
    "cherche sur internet": ("browser_search", {}),
    "recherche sur internet": ("browser_search", {}),
    "recherche web": ("browser_search", {}),

    # NAVIGATEUR — Navigation
    "page precedente": ("browser_back", {}),
    "retour": ("browser_back", {}),
    "reviens en arriere": ("browser_back", {}),
    "en arriere": ("browser_back", {}),
    "recule": ("browser_back", {}),
    "page suivante": ("browser_forward", {}),
    "avance": ("browser_forward", {}),
    "va en avant": ("browser_forward", {}),

    # NAVIGATEUR — Scroll
    "descends": ("browser_scroll", {"direction": "down"}),
    "scroll en bas": ("browser_scroll", {"direction": "down"}),
    "plus bas": ("browser_scroll", {"direction": "down"}),
    "monte": ("browser_scroll", {"direction": "up"}),
    "scroll en haut": ("browser_scroll", {"direction": "up"}),
    "remonte": ("browser_scroll", {"direction": "up"}),
    "tout en haut": ("browser_scroll", {"direction": "top"}),
    "haut de page": ("browser_scroll", {"direction": "top"}),
    "tout en bas": ("browser_scroll", {"direction": "bottom"}),
    "bas de page": ("browser_scroll", {"direction": "bottom"}),

    # NAVIGATEUR — Interaction
    "clique": ("browser_click", {}),
    "clique sur": ("browser_click", {}),
    "tape": ("browser_type", {}),
    "ecris": ("browser_type", {}),
    "entree": ("browser_press", {"key": "Enter"}),
    "valide": ("browser_press", {"key": "Enter"}),
    "tabulation": ("browser_press", {"key": "Tab"}),
    "echap": ("browser_press", {"key": "Escape"}),
    "efface": ("browser_press", {"key": "Backspace"}),

    # NAVIGATEUR — Onglets
    "nouvel onglet": ("browser_new_tab", {}),
    "ouvre un onglet": ("browser_new_tab", {}),
    "ferme l'onglet": ("browser_close_tab", {}),
    "ferme cet onglet": ("browser_close_tab", {}),
    "les onglets": ("browser_tabs", {}),
    "liste les onglets": ("browser_tabs", {}),

    # NAVIGATEUR — Lecture & Info
    "lis la page": ("browser_read", {}),
    "lis le contenu": ("browser_read", {}),
    "contenu de la page": ("browser_read", {}),
    "capture ecran navigateur": ("browser_screenshot", {}),
    "screenshot navigateur": ("browser_screenshot", {}),

    # NAVIGATEUR — Zoom / Divers
    "zoom plus": ("browser_zoom", {"in_out": "in"}),
    "zoome": ("browser_zoom", {"in_out": "in"}),
    "zoom moins": ("browser_zoom", {"in_out": "out"}),
    "dezoome": ("browser_zoom", {"in_out": "out"}),
    "actualise": ("browser_refresh", {}),
    "rafraichis": ("browser_refresh", {}),
    "recharge la page": ("browser_refresh", {}),
    "plein ecran": ("browser_fullscreen", {}),
    "cherche dans la page": ("browser_find", {}),
    "ajoute aux favoris": ("browser_bookmark", {}),

    # ===================================================================
    # LINUX — Applications
    # ===================================================================
    "ouvre le bloc-notes": ("linux_open_app", {"name": "gedit"}),
    "ouvre notepad": ("linux_open_app", {"name": "gedit"}),
    "ouvre la calculatrice": ("linux_open_app", {"name": "calculatrice"}),
    "calculatrice": ("linux_open_app", {"name": "calculatrice"}),
    "ouvre l'explorateur": ("linux_open_app", {"name": "nautilus"}),
    "explorateur de fichiers": ("linux_open_app", {"name": "nautilus"}),
    "ouvre mes fichiers": ("linux_open_app", {"name": "nautilus"}),
    "ouvre le terminal": ("linux_open_app", {"name": "terminal"}),
    "terminal": ("linux_open_app", {"name": "terminal"}),
    "ouvre un terminal": ("linux_open_app", {"name": "terminal"}),
    "ouvre les parametres": ("linux_open_app", {"name": "parametres"}),
    "parametres": ("linux_open_app", {"name": "parametres"}),
    "ouvre les reglages": ("linux_open_app", {"name": "reglages"}),
    "ouvre chrome": ("linux_open_app", {"name": "chrome"}),
    "ouvre firefox": ("linux_open_app", {"name": "firefox"}),
    "ouvre spotify": ("linux_open_app", {"name": "spotify"}),
    "ouvre discord": ("linux_open_app", {"name": "discord"}),
    "ouvre vs code": ("linux_open_app", {"name": "code"}),
    "ouvre vscode": ("linux_open_app", {"name": "code"}),
    "ouvre visual studio code": ("linux_open_app", {"name": "code"}),
    "ouvre vlc": ("linux_open_app", {"name": "vlc"}),
    "ouvre gimp": ("linux_open_app", {"name": "gimp"}),
    "moniteur systeme": ("linux_open_app", {"name": "moniteur"}),
    "gestionnaire de taches": ("linux_open_app", {"name": "gestionnaire"}),

    # LINUX — Fenetres
    "ferme la fenetre": ("linux_close_app", {}),
    "ferme l'application": ("linux_close_app", {}),
    "alt f4": ("linux_close_app", {}),
    "quitte": ("linux_close_app", {}),
    "minimise": ("linux_minimize", {}),
    "minimise la fenetre": ("linux_minimize", {}),
    "reduis la fenetre": ("linux_minimize", {}),
    "cache la fenetre": ("linux_minimize", {}),
    "maximise": ("linux_maximize", {}),
    "maximise la fenetre": ("linux_maximize", {}),
    "agrandis la fenetre": ("linux_maximize", {}),
    "mets en grand": ("linux_maximize", {}),
    "change de fenetre": ("linux_switch_app", {}),
    "alt tab": ("linux_switch_app", {}),
    "fenetre suivante": ("linux_switch_app", {}),
    "bascule": ("linux_switch_app", {}),
    "fenetre a gauche": ("linux_snap_left", {}),
    "snap gauche": ("linux_snap_left", {}),
    "mets a gauche": ("linux_snap_left", {}),
    "fenetre a droite": ("linux_snap_right", {}),
    "snap droite": ("linux_snap_right", {}),
    "mets a droite": ("linux_snap_right", {}),
    "affiche le bureau": ("linux_desktop_show", {}),
    "montre le bureau": ("linux_desktop_show", {}),
    "bureau": ("linux_desktop_show", {}),
    "minimise tout": ("linux_desktop_show", {}),
    "liste les fenetres": ("linux_list_windows", {}),
    "quelles fenetres": ("linux_list_windows", {}),
    "fenetres ouvertes": ("linux_list_windows", {}),

    # LINUX — Volume / Audio
    "monte le volume": ("linux_volume", {"action": "up"}),
    "augmente le volume": ("linux_volume", {"action": "up"}),
    "volume plus": ("linux_volume", {"action": "up"}),
    "plus fort": ("linux_volume", {"action": "up"}),
    "baisse le volume": ("linux_volume", {"action": "down"}),
    "diminue le volume": ("linux_volume", {"action": "down"}),
    "volume moins": ("linux_volume", {"action": "down"}),
    "moins fort": ("linux_volume", {"action": "down"}),
    "coupe le son": ("linux_volume", {"action": "mute"}),
    "mute": ("linux_volume", {"action": "mute"}),
    "silence": ("linux_volume", {"action": "mute"}),
    "reactive le son": ("linux_volume", {"action": "mute"}),
    "quel volume": ("linux_volume_level", {}),
    "niveau du volume": ("linux_volume_level", {}),

    # LINUX — Luminosite
    "augmente la luminosite": ("linux_brightness", {"action": "up"}),
    "luminosite plus": ("linux_brightness", {"action": "up"}),
    "plus lumineux": ("linux_brightness", {"action": "up"}),
    "baisse la luminosite": ("linux_brightness", {"action": "down"}),
    "luminosite moins": ("linux_brightness", {"action": "down"}),
    "moins lumineux": ("linux_brightness", {"action": "down"}),

    # LINUX — Reseau
    "active le wifi": ("linux_wifi", {"on_off": "on"}),
    "allume le wifi": ("linux_wifi", {"on_off": "on"}),
    "desactive le wifi": ("linux_wifi", {"on_off": "off"}),
    "coupe le wifi": ("linux_wifi", {"on_off": "off"}),
    "active le bluetooth": ("linux_bluetooth", {"on_off": "on"}),
    "allume le bluetooth": ("linux_bluetooth", {"on_off": "on"}),
    "desactive le bluetooth": ("linux_bluetooth", {"on_off": "off"}),
    "coupe le bluetooth": ("linux_bluetooth", {"on_off": "off"}),
    "info reseau": ("linux_network_info", {}),
    "adresse ip": ("linux_ip_address", {}),
    "mon ip": ("linux_ip_address", {}),

    # LINUX — Alimentation
    "eteins l'ordinateur": ("linux_shutdown", {}),
    "eteins le pc": ("linux_shutdown", {}),
    "extinction": ("linux_shutdown", {}),
    "shutdown": ("linux_shutdown", {}),
    "redemarre": ("linux_restart", {}),
    "redemarre le pc": ("linux_restart", {}),
    "redemarrage": ("linux_restart", {}),
    "restart": ("linux_restart", {}),
    "mise en veille": ("linux_sleep", {}),
    "veille": ("linux_sleep", {}),
    "mets en veille": ("linux_sleep", {}),
    "verrouille l'ecran": ("linux_lock", {}),
    "verrouille": ("linux_lock", {}),
    "verrouille le pc": ("linux_lock", {}),
    "lock": ("linux_lock", {}),

    # LINUX — Capture
    "capture ecran": ("linux_screenshot", {}),
    "screenshot": ("linux_screenshot", {}),
    "capture d'ecran": ("linux_screenshot", {}),
    "fais une capture": ("linux_screenshot", {}),
    "prends une capture": ("linux_screenshot", {}),

    # LINUX — Fichiers
    "ouvre l'explorateur de fichiers": ("linux_file_explorer", {}),
    "ouvre mes documents": ("linux_file_explorer", {"path": "~/Documents"}),
    "ouvre mes telechargements": ("linux_file_explorer", {"path": "~/Downloads"}),
    "ouvre le dossier home": ("linux_file_explorer", {}),

    # LINUX — Presse-papiers
    "copier": ("linux_clipboard_copy", {}),
    "copie": ("linux_clipboard_copy", {}),
    "coller": ("linux_clipboard_paste", {}),
    "colle": ("linux_clipboard_paste", {}),
    "lis le presse-papiers": ("linux_clipboard_read", {}),
    "contenu du presse-papiers": ("linux_clipboard_read", {}),

    # LINUX — Multimedia
    "lecture": ("linux_media_play_pause", {}),
    "pause": ("linux_media_play_pause", {}),
    "play": ("linux_media_play_pause", {}),
    "play pause": ("linux_media_play_pause", {}),
    "joue": ("linux_media_play_pause", {}),
    "reprends": ("linux_media_play_pause", {}),
    "piste suivante": ("linux_media_next", {}),
    "chanson suivante": ("linux_media_next", {}),
    "next": ("linux_media_next", {}),
    "suivant": ("linux_media_next", {}),
    "piste precedente": ("linux_media_previous", {}),
    "chanson precedente": ("linux_media_previous", {}),
    "previous": ("linux_media_previous", {}),
    "precedent": ("linux_media_previous", {}),
    "arrete la musique": ("linux_media_stop", {}),
    "stop musique": ("linux_media_stop", {}),

    # LINUX — Monitoring
    "usage processeur": ("linux_cpu_usage", {}),
    "cpu": ("linux_cpu_usage", {}),
    "usage cpu": ("linux_cpu_usage", {}),
    "charge cpu": ("linux_cpu_usage", {}),
    "usage memoire": ("linux_memory_usage", {}),
    "memoire": ("linux_memory_usage", {}),
    "ram": ("linux_memory_usage", {}),
    "combien de ram": ("linux_memory_usage", {}),
    "espace disque": ("linux_disk_usage", {}),
    "disque": ("linux_disk_usage", {}),
    "usage disque": ("linux_disk_usage", {}),
    "temperature gpu": ("linux_gpu_info", {}),
    "gpu": ("linux_gpu_info", {}),
    "info gpu": ("linux_gpu_info", {}),
    "carte graphique": ("linux_gpu_info", {}),
    "processus": ("linux_processes", {}),
    "liste les processus": ("linux_processes", {}),
    "quels processus": ("linux_processes", {}),
    "uptime": ("linux_uptime", {}),
    "depuis quand": ("linux_uptime", {}),

    # LINUX — Recherche
    "recherche d'applications": ("linux_search", {}),
    "recherche systeme": ("linux_search", {}),
    "ouvre activities": ("linux_workspace_overview", {}),

    # LINUX — Workspaces
    "workspace suivant": ("linux_workspace_next", {}),
    "bureau suivant": ("linux_workspace_next", {}),
    "espace de travail suivant": ("linux_workspace_next", {}),
    "workspace precedent": ("linux_workspace_prev", {}),
    "bureau precedent": ("linux_workspace_prev", {}),
    "vue d'ensemble": ("linux_workspace_overview", {}),
    "overview": ("linux_workspace_overview", {}),
    "activities": ("linux_workspace_overview", {}),

    # LINUX — Gestion de fichiers
    "liste les fichiers": ("linux_list_files", {}),
    "quels fichiers": ("linux_list_files", {}),
    "montre les fichiers": ("linux_list_files", {}),
    "ls": ("linux_list_files", {}),
    "espace disque detaille": ("linux_disk_space_detailed", {}),
    "partitions": ("linux_disk_space_detailed", {}),

    # LINUX — Dictee / Frappe
    "tout selectionner": ("linux_select_all", {}),
    "selectionne tout": ("linux_select_all", {}),
    "ctrl a": ("linux_select_all", {}),
    "annuler": ("linux_undo", {}),
    "ctrl z": ("linux_undo", {}),
    "defaire": ("linux_undo", {}),
    "refaire": ("linux_redo", {}),
    "ctrl y": ("linux_redo", {}),
    "sauvegarder": ("linux_save", {}),
    "sauvegarde": ("linux_save", {}),
    "ctrl s": ("linux_save", {}),
    "enregistre": ("linux_save", {}),

    # LINUX — Tmux
    "sessions tmux": ("linux_tmux_list", {}),
    "liste les sessions tmux": ("linux_tmux_list", {}),
    "tmux": ("linux_tmux_list", {}),
    "attache tmux": ("linux_tmux_attach", {}),
    "rejoins tmux": ("linux_tmux_attach", {}),

    # LINUX — Services systemd
    "services jarvis": ("linux_services_list", {}),
    "liste les services": ("linux_services_list", {}),
    "etat des services": ("linux_services_list", {}),

    # LINUX — Mise a jour
    "mets a jour le systeme": ("linux_update_system", {}),
    "mise a jour": ("linux_update_system", {}),
    "apt update": ("linux_update_system", {}),

    # LINUX — Notifications
    "notification": ("linux_notify", {"message": "Test notification JARVIS"}),
    "notifie": ("linux_notify", {}),

    # LINUX — Mode sombre / Veilleuse
    "mode sombre": ("linux_dark_mode", {"on_off": "on"}),
    "dark mode": ("linux_dark_mode", {"on_off": "on"}),
    "active le mode sombre": ("linux_dark_mode", {"on_off": "on"}),
    "mode clair": ("linux_dark_mode", {"on_off": "off"}),
    "desactive le mode sombre": ("linux_dark_mode", {"on_off": "off"}),
    "active la veilleuse": ("linux_night_light", {"on_off": "on"}),
    "veilleuse": ("linux_night_light", {"on_off": "on"}),
    "desactive la veilleuse": ("linux_night_light", {"on_off": "off"}),

    # LINUX — Bluetooth avance
    "appareils bluetooth": ("linux_bluetooth_devices", {}),
    "liste bluetooth": ("linux_bluetooth_devices", {}),
    "connecte le casque": ("linux_bluetooth_connect", {}),
    "connecte le sony": ("linux_bluetooth_connect", {}),
    "connecte le bluetooth": ("linux_bluetooth_connect", {}),
    "deconnecte le bluetooth": ("linux_bluetooth_disconnect", {}),
    "deconnecte le casque": ("linux_bluetooth_disconnect", {}),

    # LINUX — Date / Heure / Minuteur
    "quelle heure": ("linux_datetime", {}),
    "quelle date": ("linux_datetime", {}),
    "date et heure": ("linux_datetime", {}),
    "l'heure": ("linux_datetime", {}),
    "calendrier": ("linux_calendar", {}),
    "montre le calendrier": ("linux_calendar", {}),

    # LINUX — Resolution / Affichage
    "resolution ecran": ("linux_screen_resolution", {}),
    "quelle resolution": ("linux_screen_resolution", {}),

    # LINUX — IA conversationnel
    "demande a l'ia": ("linux_ask_ia", {}),
    "pose une question": ("linux_ask_ia", {}),
    "question ia": ("linux_ask_ia", {}),

    # ===================================================================
    # PROCESSUS AVANCES
    # ===================================================================
    "top cpu": ("linux_top_cpu", {}),
    "processus cpu": ("linux_top_cpu", {}),
    "qui utilise le cpu": ("linux_top_cpu", {}),
    "top memoire": ("linux_top_memory", {}),
    "top ram": ("linux_top_memory", {}),
    "qui utilise la ram": ("linux_top_memory", {}),
    "processus memoire": ("linux_top_memory", {}),
    "ports ouverts": ("linux_ports_open", {}),
    "liste les ports": ("linux_ports_open", {}),
    "quels ports sont ouverts": ("linux_ports_open", {}),
    "combien de processus": ("linux_process_count", {}),
    "nombre de processus": ("linux_process_count", {}),

    # ===================================================================
    # JARVIS — Pilotage vocal du cluster
    # ===================================================================
    "status cluster": ("jarvis_cluster_status", {}),
    "statut cluster": ("jarvis_cluster_status", {}),
    "etat du cluster": ("jarvis_cluster_status", {}),
    "cluster jarvis": ("jarvis_cluster_status", {}),
    "comment va le cluster": ("jarvis_cluster_status", {}),
    "sante des services": ("jarvis_services_health", {}),
    "health check": ("jarvis_services_health", {}),
    "etat des services": ("jarvis_services_health", {}),
    "services jarvis": ("jarvis_services_health", {}),
    "combien de services actifs": ("jarvis_services_health", {}),
    "status base de donnees": ("jarvis_db_status", {}),
    "statut sql": ("jarvis_db_status", {}),
    "etat des bases": ("jarvis_db_status", {}),
    "bases de donnees": ("jarvis_db_status", {}),
    "temperatures gpu": ("jarvis_gpu_temperatures", {}),
    "temperature des gpu": ("jarvis_gpu_temperatures", {}),
    "chaleur gpu": ("jarvis_gpu_temperatures", {}),
    "gpu chaud": ("jarvis_gpu_temperatures", {}),
    "les gpu sont chauds": ("jarvis_gpu_temperatures", {}),
    "vram": ("jarvis_vram_usage", {}),
    "usage vram": ("jarvis_vram_usage", {}),
    "memoire gpu": ("jarvis_vram_usage", {}),
    "combien de vram": ("jarvis_vram_usage", {}),

    # ===================================================================
    # RESEAU AVANCE
    # ===================================================================
    "ping": ("linux_ping", {}),
    "ping google": ("linux_ping", {"host": "8.8.8.8"}),
    "test connexion": ("linux_ping", {"host": "8.8.8.8"}),
    "suis-je connecte": ("linux_ping", {"host": "8.8.8.8"}),
    "ip publique": ("linux_public_ip", {}),
    "mon ip publique": ("linux_public_ip", {}),
    "quelle est mon ip": ("linux_public_ip", {}),
    "reseaux wifi": ("linux_wifi_list", {}),
    "liste les wifi": ("linux_wifi_list", {}),
    "wifi disponibles": ("linux_wifi_list", {}),
    "quels wifi": ("linux_wifi_list", {}),
    "test vitesse": ("linux_speed_test", {}),
    "test de vitesse": ("linux_speed_test", {}),
    "speed test": ("linux_speed_test", {}),
    "vitesse internet": ("linux_speed_test", {}),

    # ===================================================================
    # SECURITE
    # ===================================================================
    "qui est connecte": ("linux_who_logged", {}),
    "utilisateurs connectes": ("linux_who_logged", {}),
    "sessions actives": ("linux_who_logged", {}),
    "dernieres connexions": ("linux_last_logins", {}),
    "historique connexions": ("linux_last_logins", {}),
    "statut firewall": ("linux_firewall_status", {}),
    "pare-feu": ("linux_firewall_status", {}),

    # ===================================================================
    # ENERGIE / PERFORMANCE / MONITORING
    # ===================================================================
    "temperature cpu": ("linux_cpu_temperatures", {}),
    "temperatures cpu": ("linux_cpu_temperatures", {}),
    "cpu chaud": ("linux_cpu_temperatures", {}),
    "chaleur cpu": ("linux_cpu_temperatures", {}),
    "capteurs": ("linux_cpu_temperatures", {}),
    "sensors": ("linux_cpu_temperatures", {}),
    "batterie": ("linux_battery_status", {}),
    "etat batterie": ("linux_battery_status", {}),
    "swap": ("linux_swap_usage", {}),
    "usage swap": ("linux_swap_usage", {}),
    "charge systeme": ("linux_load_average", {}),
    "load average": ("linux_load_average", {}),
    "charge du serveur": ("linux_load_average", {}),

    # ===================================================================
    # CLIPBOARD AVANCE
    # ===================================================================
    "vide le presse-papiers": ("linux_clipboard_clear", {}),
    "efface le presse-papiers": ("linux_clipboard_clear", {}),
    "clear clipboard": ("linux_clipboard_clear", {}),
    "colle par frappe": ("linux_clipboard_type", {}),
    "colle en tapant": ("linux_clipboard_type", {}),

    # ===================================================================
    # ECRANS MULTIPLES
    # ===================================================================
    "info ecrans": ("linux_screens_info", {}),
    "ecrans connectes": ("linux_screens_info", {}),
    "combien d'ecrans": ("linux_screens_info", {}),
    "moniteurs": ("linux_screens_info", {}),

    # ===================================================================
    # SPOTIFY — Controle musical avance
    # ===================================================================
    "quelle chanson": ("spotify_now_playing", {}),
    "c'est quoi cette chanson": ("spotify_now_playing", {}),
    "qu'est-ce qui joue": ("spotify_now_playing", {}),
    "chanson en cours": ("spotify_now_playing", {}),
    "quel titre": ("spotify_now_playing", {}),
    "musique en cours": ("spotify_now_playing", {}),
    "ouvre spotify": ("spotify_open", {}),
    "lance spotify": ("spotify_open", {}),
    "shuffle": ("spotify_shuffle", {}),
    "lecture aleatoire": ("spotify_shuffle", {}),
    "melange les titres": ("spotify_shuffle", {}),
    "mode aleatoire": ("spotify_shuffle", {}),
    "active le shuffle": ("spotify_shuffle", {"on_off": "on"}),
    "desactive le shuffle": ("spotify_shuffle", {"on_off": "off"}),
    "repetition": ("spotify_repeat", {}),
    "mode repetition": ("spotify_repeat", {}),
    "repete la chanson": ("spotify_repeat", {"mode": "track"}),
    "repete la playlist": ("spotify_repeat", {"mode": "playlist"}),
    "pas de repetition": ("spotify_repeat", {"mode": "none"}),
    "like": ("spotify_like", {}),
    "j'aime cette chanson": ("spotify_like", {}),
    "aime ce titre": ("spotify_like", {}),

    # ===================================================================
    # TRADING — Pilotage vocal
    # ===================================================================
    "scan trading": ("trading_scan", {}),
    "lance un scan": ("trading_scan", {}),
    "analyse le marche": ("trading_scan", {}),
    "opportunites trading": ("trading_scan", {}),
    "scanner le marche": ("trading_scan", {}),
    "positions": ("trading_positions", {}),
    "mes positions": ("trading_positions", {}),
    "positions ouvertes": ("trading_positions", {}),
    "portefeuille": ("trading_positions", {}),
    "signaux trading": ("trading_signals", {}),
    "signaux": ("trading_signals", {}),
    "derniers signaux": ("trading_signals", {}),
    "status trading": ("trading_status", {}),
    "statut trading": ("trading_status", {}),
    "etat du trading": ("trading_status", {}),

    # ===================================================================
    # WORKFLOWS n8n
    # ===================================================================
    "workflows actifs": ("workflow_list", {}),
    "liste les workflows": ("workflow_list", {}),
    "quels workflows": ("workflow_list", {}),
    "statut n8n": ("workflow_status", {}),
    "etat de n8n": ("workflow_status", {}),
    "n8n": ("workflow_status", {}),

    # ===================================================================
    # SYSTEME — Commandes supplementaires
    # ===================================================================
    "nom de la machine": ("linux_hostname", {}),
    "hostname": ("linux_hostname", {}),
    "version du noyau": ("linux_kernel_version", {}),
    "version kernel": ("linux_kernel_version", {}),
    "quel linux": ("linux_os_info", {}),
    "version linux": ("linux_os_info", {}),
    "info systeme": ("linux_os_info", {}),
    "quel systeme": ("linux_os_info", {}),
    "taches planifiees": ("linux_scheduled_tasks", {}),
    "crontab": ("linux_scheduled_tasks", {}),
    "taches cron": ("linux_scheduled_tasks", {}),
    "memoire detaillee": ("linux_memory_detailed", {}),
    "ram detaillee": ("linux_memory_detailed", {}),
    "resume systeme": ("linux_system_summary", {}),
    "bilan systeme": ("linux_system_summary", {}),
    "comment va le systeme": ("linux_system_summary", {}),
    "etat general": ("linux_system_summary", {}),
    "diagnostic rapide": ("linux_system_summary", {}),

    # ===================================================================
    # VOICE LEARNING — Rapport et apprentissage
    # ===================================================================
    "rapport vocal": ("voice_report", {}),
    "qualite vocale": ("voice_report", {}),
    "comment je parle": ("voice_report", {}),
    "taux de reussite": ("voice_report", {}),
    "statistiques vocales": ("voice_report", {}),
    "apprends": ("voice_learn", {}),
    "apprentissage vocal": ("voice_learn", {}),
    "ameliore toi": ("voice_learn", {}),
    "apprends de mes erreurs": ("voice_learn", {}),
    "combien de corrections": ("voice_corrections_count", {}),
    "corrections vocales": ("voice_corrections_count", {}),

    # ===================================================================
    # DOCKER — Gestion containers
    # ===================================================================
    "containers": ("docker_ps", {}),
    "docker ps": ("docker_ps", {}),
    "liste les containers": ("docker_ps", {}),
    "containers en cours": ("docker_ps", {}),
    "quels containers": ("docker_ps", {}),
    "tous les containers": ("docker_ps_all", {}),
    "docker tous": ("docker_ps_all", {}),
    "images docker": ("docker_images", {}),
    "liste les images": ("docker_images", {}),
    "stats docker": ("docker_stats", {}),
    "docker stats": ("docker_stats", {}),
    "performances docker": ("docker_stats", {}),
    "compose up": ("docker_compose_up", {}),
    "docker up": ("docker_compose_up", {}),
    "compose down": ("docker_compose_down", {}),
    "docker down": ("docker_compose_down", {}),

    # ===================================================================
    # GIT — Controle vocal
    # ===================================================================
    "git status": ("git_status", {}),
    "statut git": ("git_status", {}),
    "modifications git": ("git_status", {}),
    "quoi de neuf en git": ("git_status", {}),
    "derniers commits": ("git_log", {}),
    "git log": ("git_log", {}),
    "historique git": ("git_log", {}),
    "quelle branche": ("git_branch", {}),
    "branche git": ("git_branch", {}),
    "git pull": ("git_pull", {}),
    "tire le code": ("git_pull", {}),
    "met a jour le code": ("git_pull", {}),

    # ===================================================================
    # PRODUCTIVITE
    # ===================================================================
    "ne pas deranger": ("linux_do_not_disturb", {"on_off": "on"}),
    "mode silencieux": ("linux_do_not_disturb", {"on_off": "on"}),
    "pas de notifications": ("linux_do_not_disturb", {"on_off": "on"}),
    "reactive les notifications": ("linux_do_not_disturb", {"on_off": "off"}),
    "mode focus": ("linux_focus_mode", {}),
    "concentration": ("linux_focus_mode", {}),
    "mode travail": ("linux_focus_mode", {}),
    "fin du focus": ("linux_break_mode", {}),
    "pause": ("linux_break_mode", {}),
    "mode normal": ("linux_break_mode", {}),

    # ===================================================================
    # WIDGETS & DASHBOARD
    # ===================================================================
    "active les widgets": ("widgets_start", {}),
    "widgets on": ("widgets_start", {}),
    "lance les widgets": ("widgets_start", {}),
    "affiche les widgets": ("widgets_start", {}),
    "desactive les widgets": ("widgets_stop", {}),
    "widgets off": ("widgets_stop", {}),
    "cache les widgets": ("widgets_stop", {}),
    "redemarrer les widgets": ("widgets_restart", {}),
    "refresh widgets": ("widgets_restart", {}),
    "ouvre le dashboard": ("dashboard_open", {}),
    "dashboard web": ("dashboard_open", {}),
    "ouvre le tableau de bord web": ("dashboard_open", {}),
    "redemarrer le dashboard web": ("dashboard_restart", {}),
    "capture du bureau": ("screenshot_desktop", {}),
    "screenshot complet": ("screenshot_desktop", {}),
    "photo du bureau": ("screenshot_desktop", {}),
    "regenere le fond d'ecran": ("wallpaper_refresh", {}),
    "refresh wallpaper": ("wallpaper_refresh", {}),
    "nouveau fond d'ecran": ("wallpaper_refresh", {}),
    "met a jour le fond d'ecran": ("wallpaper_refresh", {}),

    # ===================================================================
    # PROFILS JARVIS
    # ===================================================================
    "mode travail": ("profile_switch", {"name": "travail"}),
    "profil travail": ("profile_switch", {"name": "travail"}),
    "mode dev": ("profile_switch", {"name": "dev"}),
    "profil dev": ("profile_switch", {"name": "dev"}),
    "mode developpement": ("profile_switch", {"name": "dev"}),
    "mode gaming": ("profile_switch", {"name": "gaming"}),
    "profil gaming": ("profile_switch", {"name": "gaming"}),
    "mode jeu": ("profile_switch", {"name": "gaming"}),
    "mode veille": ("profile_switch", {"name": "veille"}),
    "profil veille": ("profile_switch", {"name": "veille"}),
    "mode economie": ("profile_switch", {"name": "veille"}),
    "mode presentation": ("profile_switch", {"name": "presentation"}),
    "profil presentation": ("profile_switch", {"name": "presentation"}),
    "mode normal": ("profile_switch", {"name": "normal"}),
    "profil normal": ("profile_switch", {"name": "normal"}),
    "retour a la normale": ("profile_switch", {"name": "normal"}),
    "liste les profils": ("profile_list", {}),
    "quels profils": ("profile_list", {}),
    "profils disponibles": ("profile_list", {}),
    "quel profil": ("profile_current", {}),
    "profil actuel": ("profile_current", {}),

    # ===================================================================
    # ROUTINES JARVIS
    # ===================================================================
    "routine du matin": ("routine_run", {"name": "matin"}),
    "bonjour jarvis": ("routine_run", {"name": "matin"}),
    "briefing du matin": ("routine_run", {"name": "matin"}),
    "routine du soir": ("routine_run", {"name": "soir"}),
    "bonsoir jarvis": ("routine_run", {"name": "soir"}),
    "rapport du soir": ("routine_run", {"name": "soir"}),
    "routine bureau": ("routine_run", {"name": "bureau"}),
    "je suis au bureau": ("routine_run", {"name": "bureau"}),
    "routine depart": ("routine_run", {"name": "depart"}),
    "je pars": ("routine_run", {"name": "depart"}),
    "au revoir jarvis": ("routine_run", {"name": "depart"}),
    "routine gaming": ("routine_run", {"name": "gaming"}),
    "on joue": ("routine_run", {"name": "gaming"}),
    "routine reset": ("routine_run", {"name": "reset"}),
    "remise a zero": ("routine_run", {"name": "reset"}),
    "liste les routines": ("routine_list", {}),
    "quelles routines": ("routine_list", {}),
    "routines disponibles": ("routine_list", {}),

    # ===================================================================
    # COMMANDES AVANCÉES
    # ===================================================================
    "screenshot annote": ("screenshot_annotate", {}),
    "capture annotee": ("screenshot_annotate", {}),
    "capture avec description": ("screenshot_annotate", {}),
    "ocr clipboard": ("ocr_to_clipboard", {}),
    "copie le texte de l'ecran": ("ocr_to_clipboard", {}),
    "ocr dans le presse-papiers": ("ocr_to_clipboard", {}),
    "lis et copie l'ecran": ("ocr_to_clipboard", {}),
    "sante du systeme": ("system_health_voice", {}),
    "check sante": ("system_health_voice", {}),
    "tout va bien": ("system_health_voice", {}),
    "comment va le pc": ("system_health_voice", {}),

    # ===================================================================
    # NAVIGATEUR AVANCÉ
    # ===================================================================
    "historique": ("browser_history", {}),
    "ouvre l'historique": ("browser_history", {}),
    "history": ("browser_history", {}),
    "telechargements": ("browser_downloads", {}),
    "ouvre les telechargements": ("browser_downloads", {}),
    "downloads": ("browser_downloads", {}),
    "navigation privee": ("browser_private", {}),
    "mode prive": ("browser_private", {}),
    "incognito": ("browser_private", {}),
    "outils developpeur": ("browser_devtools", {}),
    "devtools": ("browser_devtools", {}),
    "f12": ("browser_devtools", {}),
    "coupe le son de l'onglet": ("browser_mute_tab", {}),
    "mute l'onglet": ("browser_mute_tab", {}),
    "imprime la page": ("browser_print", {}),
    "imprimer": ("browser_print", {}),
    "sauvegarde la page": ("browser_save_page", {}),
    "enregistre la page": ("browser_save_page", {}),

    # ===================================================================
    # MULTIMÉDIA PIPEWIRE
    # ===================================================================
    "sorties audio": ("audio_list_outputs", {}),
    "liste les sorties audio": ("audio_list_outputs", {}),
    "quelles enceintes": ("audio_list_outputs", {}),
    "entrees audio": ("audio_list_inputs", {}),
    "liste les micros": ("audio_list_inputs", {}),
    "bascule sur le casque": ("audio_switch_headphones", {}),
    "sortie casque": ("audio_switch_headphones", {}),
    "audio casque": ("audio_switch_headphones", {}),
    "mets le casque": ("audio_switch_headphones", {}),
    "bascule sur les enceintes": ("audio_switch_speakers", {}),
    "sortie haut-parleurs": ("audio_switch_speakers", {}),
    "audio enceintes": ("audio_switch_speakers", {}),
    "mets les enceintes": ("audio_switch_speakers", {}),
    "bascule sur hdmi": ("audio_switch_hdmi", {}),
    "sortie hdmi": ("audio_switch_hdmi", {}),
    "audio hdmi": ("audio_switch_hdmi", {}),
    "commence a enregistrer": ("audio_record_start", {}),
    "enregistre le micro": ("audio_record_start", {}),
    "demarre l'enregistrement": ("audio_record_start", {}),
    "arrete l'enregistrement": ("audio_record_stop", {}),
    "stop enregistrement": ("audio_record_stop", {}),
    "quelle sortie audio": ("audio_current_output", {}),
    "sur quoi je joue le son": ("audio_current_output", {}),

    # ===================================================================
    # CONTEXTE INTELLIGENT
    # ===================================================================
    "quelle app est active": ("context_info", {}),
    "contexte": ("context_info", {}),
    "qu'est-ce qui est ouvert": ("context_info", {}),
    "info application": ("context_info", {}),

    # ===================================================================
    # SYSTEMD COMPLET
    # ===================================================================
    "tous les services": ("systemd_list_all", {}),
    "services linux": ("systemd_list_all", {}),
    "liste tous les services": ("systemd_list_all", {}),
    "timers": ("systemd_timers", {}),
    "liste les timers": ("systemd_timers", {}),
    "taches planifiees systemd": ("systemd_timers", {}),

    # ===================================================================
    # RÉSEAU AVANCÉ
    # ===================================================================
    "ssh m2": ("ssh_to_m2", {}),
    "connecte toi a m2": ("ssh_to_m2", {}),
    "ouvre m2": ("ssh_to_m2", {}),
    "terminal m2": ("ssh_to_m2", {}),
    "ssh serveur": ("ssh_to_server", {}),
    "ssh server": ("ssh_to_server", {}),
    "connecte toi au serveur": ("ssh_to_server", {}),
    "terminal serveur": ("ssh_to_server", {}),
    "connexions reseau": ("network_connections", {}),
    "connexions actives": ("network_connections", {}),
    "qui est connecte au reseau": ("network_connections", {}),
    "scan reseau": ("network_scan_local", {}),
    "scanner le reseau": ("network_scan_local", {}),
    "quels appareils sur le reseau": ("network_scan_local", {}),
    "reveille m2": ("network_wake_m2", {}),
    "wake m2": ("network_wake_m2", {}),
    "statut vpn": ("vpn_status", {}),
    "vpn": ("vpn_status", {}),

    # ===================================================================
    # FAVORIS & STATS
    # ===================================================================
    "favoris": ("voice_favorites", {}),
    "mes commandes preferees": ("voice_favorites", {}),
    "top commandes": ("voice_favorites", {}),
    "commandes les plus utilisees": ("voice_favorites", {}),
    "statistiques detaillees": ("voice_stats_detailed", {}),
    "stats vocales detaillees": ("voice_stats_detailed", {}),
    "combien de commandes aujourd'hui": ("voice_stats_detailed", {}),

    # ===================================================================
    # MACROS VOCALES
    # ===================================================================
    "liste les macros": ("macro_list", {}),
    "macros": ("macro_list", {}),
    "quelles macros": ("macro_list", {}),
    "stop macro": ("macro_stop", {}),
    "arrete la macro": ("macro_stop", {}),
    "fin macro": ("macro_stop", {}),
    "statut macro": ("macro_status", {}),

    # ===================================================================
    # JARVIS DASHBOARD — Rapport complet
    # ===================================================================
    "jarvis rapport": ("jarvis_full_dashboard", {}),
    "rapport complet": ("jarvis_full_dashboard", {}),
    "tableau de bord": ("jarvis_full_dashboard", {}),
    "dashboard": ("jarvis_full_dashboard", {}),
    "rapport jarvis": ("jarvis_full_dashboard", {}),
    "comment va jarvis": ("jarvis_full_dashboard", {}),
    "bilan complet": ("jarvis_full_dashboard", {}),
    "etat complet": ("jarvis_full_dashboard", {}),
}


# ===========================================================================
# PARAM_PATTERNS — Extraction de parametres depuis la commande vocale
# ===========================================================================
PARAM_PATTERNS = [
    # "ouvre [app]"
    (re.compile(r"^(?:ouvre|lance|demarre|start)\s+(?:l[ea]\s+|un\s+|une\s+)?(.+)$", re.I),
     "linux_open_app", lambda m: {"name": m.group(1).strip()}),
    # "cherche [query] sur google"
    (re.compile(r"^(?:cherche|recherche)\s+(?:sur\s+(?:google|internet)\s+)?(.+)$", re.I),
     "browser_search", lambda m: {"query": m.group(1).strip()}),
    # "va sur [url]"
    (re.compile(r"^(?:va\s+sur|navigue\s+vers|ouvre\s+le\s+site)\s+(.+)$", re.I),
     "browser_open", lambda m: {"url": m.group(1).strip()}),
    # "tape [texte]"
    (re.compile(r"^(?:tape|ecris|saisis|entre\s+le\s+texte)\s+(.+)$", re.I),
     "browser_type", lambda m: {"text": m.group(1).strip()}),
    # "clique sur [element]"
    (re.compile(r"^(?:clique|appuie)\s+(?:sur\s+)?(.+)$", re.I),
     "browser_click", lambda m: {"text_or_selector": m.group(1).strip()}),
    # "tue/kill [processus]"
    (re.compile(r"^(?:tue|kill|arrete|ferme)\s+(?:le\s+)?(?:processus\s+)?(.+)$", re.I),
     "linux_kill_process", lambda m: {"name": m.group(1).strip()}),
    # "volume [0-100]"
    (re.compile(r"^(?:volume|mets\s+le\s+volume)\s+(?:a\s+)?(\d+)(?:\s*%)?$", re.I),
     "linux_volume", lambda m: {"action": m.group(1).strip()}),
    # "cherche dans la page [texte]"
    (re.compile(r"^(?:cherche|trouve|recherche)\s+dans\s+la\s+page\s+(.+)$", re.I),
     "browser_find", lambda m: {"text": m.group(1).strip()}),
    # "focus sur [fenetre]"
    (re.compile(r"^(?:focus|bascule\s+vers|passe\s+a)\s+(.+)$", re.I),
     "linux_focus_window", lambda m: {"name": m.group(1).strip()}),
    # "statut service [nom]" — exige le mot "service" pour eviter de capter "status cluster"/"statut sql"
    (re.compile(r"^(?:statut|status)\s+(?:du\s+)?service\s+(.+)$", re.I),
     "linux_service_status", lambda m: {"name": m.group(1).strip()}),
    # "redemarre service [nom]"
    (re.compile(r"^(?:redemarre|restart)\s+(?:le\s+)?(?:service\s+)(.+)$", re.I),
     "linux_service_restart", lambda m: {"name": m.group(1).strip()}),
    # "dicte [texte]" — taper du texte dans l'app active
    (re.compile(r"^(?:dicte|dicte\s+moi|tape\s+dans\s+l'app|ecris\s+dans\s+l'app)\s+(.+)$", re.I),
     "linux_type_text", lambda m: {"text": m.group(1).strip()}),
    # "raccourci [combo]"
    (re.compile(r"^(?:raccourci|hotkey|combinaison)\s+(.+)$", re.I),
     "linux_hotkey", lambda m: {"combo": m.group(1).strip().replace(" plus ", "+").replace(" ", "+")}),
    # "touche [key]"
    (re.compile(r"^(?:touche|appuie\s+sur\s+la\s+touche)\s+(.+)$", re.I),
     "linux_type_key", lambda m: {"key": m.group(1).strip()}),
    # "cree le dossier [nom]"
    (re.compile(r"^(?:cree|creer|nouveau)\s+(?:le\s+)?(?:dossier|repertoire)\s+(.+)$", re.I),
     "linux_create_folder", lambda m: {"name": m.group(1).strip()}),
    # "cree le fichier [nom]"
    (re.compile(r"^(?:cree|creer|nouveau)\s+(?:le\s+)?(?:fichier)\s+(.+)$", re.I),
     "linux_create_file", lambda m: {"name": m.group(1).strip()}),
    # "supprime [fichier]"
    (re.compile(r"^(?:supprime|efface|jette)\s+(?:le\s+)?(?:fichier|dossier)?\s*(.+)$", re.I),
     "linux_delete_file", lambda m: {"name": m.group(1).strip()}),
    # "renomme [ancien] en [nouveau]"
    (re.compile(r"^(?:renomme|rename)\s+(.+?)\s+(?:en|vers|par)\s+(.+)$", re.I),
     "linux_rename_file", lambda m: {"old_name": m.group(1).strip(), "new_name": m.group(2).strip()}),
    # "cherche le fichier [nom]"
    (re.compile(r"^(?:cherche|trouve|ou\s+est)\s+(?:le\s+)?(?:fichier)\s+(.+)$", re.I),
     "linux_find_file", lambda m: {"name": m.group(1).strip()}),
    # "liste les fichiers de [dossier]"
    (re.compile(r"^(?:liste|montre|affiche)\s+(?:les\s+)?fichiers\s+(?:de|du|dans)\s+(.+)$", re.I),
     "linux_list_files", lambda m: {"path": m.group(1).strip()}),
    # "logs du service [nom]"
    (re.compile(r"^(?:logs?|journaux?)\s+(?:du\s+)?(?:service\s+)?(.+)$", re.I),
     "linux_service_logs", lambda m: {"name": m.group(1).strip()}),
    # "installe [paquet]"
    (re.compile(r"^(?:installe|install)\s+(?:le\s+)?(?:paquet\s+)?(.+)$", re.I),
     "linux_install_package", lambda m: {"name": m.group(1).strip()}),
    # "execute [commande]" — commande bash libre
    (re.compile(r"^(?:execute|lance\s+la\s+commande|commande|run)\s+(.+)$", re.I),
     "linux_run_command", lambda m: {"command": m.group(1).strip()}),
    # "notifie [message]"
    (re.compile(r"^(?:notifie|notification|envoie\s+une\s+notification)\s+(.+)$", re.I),
     "linux_notify", lambda m: {"message": m.group(1).strip()}),
    # "demande a l'ia [question]"
    (re.compile(r"^(?:demande\s+a\s+l'ia|question\s+ia|pose\s+la\s+question)\s+(.+)$", re.I),
     "linux_ask_ia", lambda m: {"question": m.group(1).strip()}),
    # "minuteur [secondes]"
    (re.compile(r"^(?:minuteur|timer|chrono)\s+(?:de\s+)?(\d+)\s*(?:secondes?|s)?$", re.I),
     "linux_timer", lambda m: {"seconds": m.group(1).strip()}),
    # "connecte [appareil bluetooth]"
    (re.compile(r"^(?:connecte)\s+(?:le\s+)?(.+)$", re.I),
     "linux_bluetooth_connect", lambda m: {"device": m.group(1).strip()}),
    # "nouvelle session tmux [nom]"
    (re.compile(r"^(?:nouvelle?\s+)?(?:session\s+)?tmux\s+(.+)$", re.I),
     "linux_tmux_new", lambda m: {"name": m.group(1).strip()}),
    # "ping [host]"
    (re.compile(r"^ping\s+(.+)$", re.I),
     "linux_ping", lambda m: {"host": m.group(1).strip()}),
    # "dns [domaine]" / "resolve [domaine]"
    (re.compile(r"^(?:dns|resolve|resolution)\s+(.+)$", re.I),
     "linux_dns_lookup", lambda m: {"domain": m.group(1).strip()}),
    # "connecte wifi [ssid]"
    (re.compile(r"^(?:connecte?\s+(?:au?\s+)?wifi|wifi\s+connecte?)\s+(.+)$", re.I),
     "linux_wifi_connect", lambda m: {"ssid": m.group(1).strip()}),
    # "tue le processus [pid]" / "kill [pid]"
    (re.compile(r"^(?:tue\s+(?:le\s+)?processus|kill)\s+(\d+)$", re.I),
     "linux_kill_pid", lambda m: {"pid": m.group(1).strip()}),
    # "redemarre le service [nom]" / "restart [service]"
    (re.compile(r"^(?:redemarre|restart)\s+(?:le\s+)?(?:service\s+)?(.+)$", re.I),
     "jarvis_restart_service", lambda m: {"name": m.group(1).strip()}),
    # "demarre le service [nom]"
    (re.compile(r"^(?:demarre|start)\s+(?:le\s+)?service\s+(.+)$", re.I),
     "jarvis_start_service", lambda m: {"name": m.group(1).strip()}),
    # "arrete le service [nom]"
    (re.compile(r"^(?:arrete|stop)\s+(?:le\s+)?service\s+(.+)$", re.I),
     "jarvis_stop_service", lambda m: {"name": m.group(1).strip()}),
    # "parametres [section]" / "reglages [section]"
    (re.compile(r"^(?:parametres?|reglages?)\s+(?:de\s+|du\s+)?(.+)$", re.I),
     "linux_open_settings_section", lambda m: {"section": m.group(1).strip()}),
    # "docker start [container]"
    (re.compile(r"^docker\s+start\s+(.+)$", re.I),
     "docker_start", lambda m: {"name": m.group(1).strip()}),
    # "docker stop [container]"
    (re.compile(r"^docker\s+stop\s+(.+)$", re.I),
     "docker_stop", lambda m: {"name": m.group(1).strip()}),
    # "docker restart [container]"
    (re.compile(r"^docker\s+restart\s+(.+)$", re.I),
     "docker_restart", lambda m: {"name": m.group(1).strip()}),
    # "docker logs [container]" / "logs docker [container]"
    (re.compile(r"^(?:docker\s+logs?|logs?\s+docker)\s+(.+)$", re.I),
     "docker_logs", lambda m: {"name": m.group(1).strip()}),
    # "demarre le container [nom]"
    (re.compile(r"^(?:demarre|start)\s+(?:le\s+)?container\s+(.+)$", re.I),
     "docker_start", lambda m: {"name": m.group(1).strip()}),
    # "arrete le container [nom]"
    (re.compile(r"^(?:arrete|stop)\s+(?:le\s+)?container\s+(.+)$", re.I),
     "docker_stop", lambda m: {"name": m.group(1).strip()}),
    # "enregistre macro [nom]" / "nouvelle macro [nom]"
    (re.compile(r"^(?:enregistre|nouvelle|cree)\s+(?:la\s+)?macro\s+(.+)$", re.I),
     "macro_start", lambda m: {"name": m.group(1).strip()}),
    # "lance la macro [nom]" / "joue la macro [nom]"
    (re.compile(r"^(?:lance|joue|execute|rejoue)\s+(?:la\s+)?macro\s+(.+)$", re.I),
     "macro_play", lambda m: {"name": m.group(1).strip()}),
    # "supprime la macro [nom]"
    (re.compile(r"^(?:supprime|efface)\s+(?:la\s+)?macro\s+(.+)$", re.I),
     "macro_delete", lambda m: {"name": m.group(1).strip()}),
    # "cherche le fichier [query]" / "trouve [query]"
    (re.compile(r"^(?:cherche|trouve|ou\s+est)\s+(?:le\s+fichier\s+)?(.+)$", re.I),
     "search_files_ia", lambda m: {"query": m.group(1).strip()}),
    # "profil [nom]" / "active le profil [nom]"
    (re.compile(r"^(?:profil|active\s+le\s+profil)\s+(.+)$", re.I),
     "profile_switch", lambda m: {"name": m.group(1).strip()}),
    # "routine [nom]" / "lance la routine [nom]"
    (re.compile(r"^(?:routine|lance\s+la\s+routine)\s+(.+)$", re.I),
     "routine_run", lambda m: {"name": m.group(1).strip()}),
    # "onglet [numero]"
    (re.compile(r"^(?:onglet|tab)\s+(\d)$", re.I),
     "browser_tab_number", lambda m: {"n": m.group(1)}),
    # "cherche le service [nom]"
    (re.compile(r"^(?:cherche|trouve)\s+(?:le\s+)?service\s+(.+)$", re.I),
     "systemd_search", lambda m: {"name": m.group(1).strip()}),
    # "active le service [nom] au boot"
    (re.compile(r"^(?:active|enable)\s+(?:le\s+)?(?:service\s+)?(.+?)\s+(?:au\s+boot|au\s+demarrage)$", re.I),
     "systemd_enable", lambda m: {"name": m.group(1).strip()}),
    # "desactive le service [nom] au boot"
    (re.compile(r"^(?:desactive|disable)\s+(?:le\s+)?(?:service\s+)?(.+?)\s+(?:au\s+boot|au\s+demarrage)$", re.I),
     "systemd_disable", lambda m: {"name": m.group(1).strip()}),
    # "volume spotify [niveau]"
    (re.compile(r"^(?:volume\s+spotify|spotify\s+volume)\s+(\d+)$", re.I),
     "spotify_volume", lambda m: {"level": m.group(1)}),
]


# ===========================================================================
# Fonction principale d'execution
# ===========================================================================
def _log_desktop_action(text: str, method_name: str, result_str: str, success: bool, duration_ms: float):
    """Log une action desktop dans action_history pour le brain learning."""
    try:
        from src.skills import log_action
        action = f"desktop:{method_name}"
        result_text = f"cmd='{text[:100]}' duration={duration_ms:.0f}ms result={result_str[:100]}"
        log_action(action, result_text, success)
    except Exception:
        pass  # Ne jamais bloquer le pipeline vocal


def execute_voice_command(text: str, vcc: LinuxDesktopControl = None) -> dict:
    """Execute une commande vocale et retourne le resultat.

    Returns:
        {"success": bool, "method": str, "result": str, "confidence": float}
    """
    if vcc is None:
        vcc = LinuxDesktopControl()

    normalized = text.lower().strip()
    start = time.time()

    # 1. Essayer les patterns parametriques
    for pattern, method_name, param_fn in PARAM_PATTERNS:
        match = pattern.match(normalized)
        if match:
            params = param_fn(match)
            method = getattr(vcc, method_name, None)
            if method:
                try:
                    result = method(**params)
                    duration_ms = (time.time() - start) * 1000
                    _log_desktop_action(text, method_name, str(result)[:200], True, duration_ms)
                    return {"success": True, "method": method_name, "result": result, "confidence": 0.9}
                except Exception as e:
                    duration_ms = (time.time() - start) * 1000
                    _log_desktop_action(text, method_name, str(e), False, duration_ms)
                    return {"success": False, "method": method_name, "result": str(e), "confidence": 0.9}

    # 2. Correspondance exacte
    if normalized in VOICE_COMMANDS:
        method_name, params = VOICE_COMMANDS[normalized]
        method = getattr(vcc, method_name, None)
        if method:
            try:
                result = method(**params)
                duration_ms = (time.time() - start) * 1000
                _log_desktop_action(text, method_name, str(result)[:200], True, duration_ms)
                return {"success": True, "method": method_name, "result": result, "confidence": 1.0}
            except Exception as e:
                duration_ms = (time.time() - start) * 1000
                _log_desktop_action(text, method_name, str(e), False, duration_ms)
                return {"success": False, "method": method_name, "result": str(e), "confidence": 1.0}

    # 3. Correspondance par sous-chaine (plus longue d'abord)
    sorted_commands = sorted(VOICE_COMMANDS.keys(), key=len, reverse=True)
    for cmd in sorted_commands:
        if cmd in normalized:
            method_name, params = VOICE_COMMANDS[cmd]
            method = getattr(vcc, method_name, None)
            if method:
                try:
                    result = method(**params)
                    duration_ms = (time.time() - start) * 1000
                    _log_desktop_action(text, method_name, str(result)[:200], True, duration_ms)
                    return {"success": True, "method": method_name, "result": result, "confidence": 0.7}
                except Exception as e:
                    duration_ms = (time.time() - start) * 1000
                    _log_desktop_action(text, method_name, str(e), False, duration_ms)
                    return {"success": False, "method": method_name, "result": str(e), "confidence": 0.7}

    # 4. Correspondance floue
    best_match = difflib.get_close_matches(normalized, VOICE_COMMANDS.keys(), n=1, cutoff=0.6)
    if best_match:
        method_name, params = VOICE_COMMANDS[best_match[0]]
        method = getattr(vcc, method_name, None)
        if method:
            try:
                result = method(**params)
                duration_ms = (time.time() - start) * 1000
                _log_desktop_action(text, method_name, str(result)[:200], True, duration_ms)
                return {"success": True, "method": method_name, "result": result,
                        "confidence": difflib.SequenceMatcher(None, normalized, best_match[0]).ratio()}
            except Exception as e:
                duration_ms = (time.time() - start) * 1000
                _log_desktop_action(text, method_name, str(e), False, duration_ms)
                return {"success": False, "method": method_name, "result": str(e), "confidence": 0.5}

    return {"success": False, "method": "unknown", "result": f"Commande non reconnue: {text}", "confidence": 0.0}


# ===========================================================================
# CLI
# ===========================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Linux Desktop Voice Control")
    parser.add_argument("--cmd", help="Commande vocale a executer")
    parser.add_argument("--method", help="Methode directe a appeler")
    parser.add_argument("--params", help="Parametres JSON pour --method")
    parser.add_argument("--list", action="store_true", help="Lister les commandes vocales")
    parser.add_argument("--list-methods", action="store_true", help="Lister les methodes")
    args = parser.parse_args()

    vcc = LinuxDesktopControl()

    if args.list:
        for cmd, (method, params) in sorted(VOICE_COMMANDS.items()):
            print(f"  {cmd:40s} → {method}({params})")
        print(f"\nTotal: {len(VOICE_COMMANDS)} commandes vocales")

    elif args.list_methods:
        methods = sorted(set(m for m, _ in VOICE_COMMANDS.values()))
        for m in methods:
            doc = getattr(vcc, m, None)
            desc = doc.__doc__.strip() if doc and doc.__doc__ else ""
            print(f"  {m:30s} — {desc}")
        print(f"\nTotal: {len(methods)} methodes")

    elif args.method:
        method = getattr(vcc, args.method, None)
        if not method:
            print(f"Methode inconnue: {args.method}")
            sys.exit(1)
        params = json.loads(args.params) if args.params else {}
        print(method(**params))

    elif args.cmd:
        result = execute_voice_command(args.cmd, vcc)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    else:
        parser.print_help()
