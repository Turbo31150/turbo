#!/usr/bin/env python3
"""voice_screen_reader.py — Lecteur d'ecran vocal pour pilotage sans ecran.

Module de lecture d'ecran et OCR pour controle vocal sous Linux (GNOME + X11).
Permet a l'utilisateur de savoir ce qui est affiche sans regarder l'ecran.
Utilise xdotool, xprop, xclip, scrot, tesseract, et vision IA.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.voice_screen_reader")

# ═══════════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════════

LMSTUDIO_URL = "http://127.0.0.1:1234/v1/chat/completions"
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
VISION_MODEL_LMS = "qwen3-8b"
VISION_MODEL_OLLAMA = "llava:13b"
SCREENSHOT_DIR = Path(tempfile.gettempdir()) / "jarvis_screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)

# Timeout pour les sous-processus (secondes)
CMD_TIMEOUT = 5
VISION_TIMEOUT = 30


def _run(cmd: list[str], timeout: int = CMD_TIMEOUT, input_data: str | None = None) -> str:
    """Execute une commande et retourne stdout. Silencieux en cas d'erreur."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            input=input_data,
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        logger.debug("Commande echouee %s: %s", cmd[0], exc)
        return ""


def _tool_available(name: str) -> bool:
    """Verifie si un outil CLI est disponible."""
    return shutil.which(name) is not None


# ═══════════════════════════════════════════════════════════════════════════════
# Classe principale
# ═══════════════════════════════════════════════════════════════════════════════

class VoiceScreenReader:
    """Lecteur d'ecran vocal — lit et decrit le contenu affiche a l'ecran."""

    def __init__(self):
        """Initialise le lecteur d'ecran et detecte les outils disponibles."""
        self.has_xdotool = _tool_available("xdotool")
        self.has_xprop = _tool_available("xprop")
        self.has_xclip = _tool_available("xclip")
        self.has_scrot = _tool_available("scrot")
        self.has_tesseract = _tool_available("tesseract")
        self.has_xdg_open = _tool_available("xdg-open")
        self.has_wmctrl = _tool_available("wmctrl")
        self.has_xrandr = _tool_available("xrandr")
        self._log_capabilities()

    def _log_capabilities(self):
        """Journalise les outils detectes."""
        tools = {
            "xdotool": self.has_xdotool,
            "xprop": self.has_xprop,
            "xclip": self.has_xclip,
            "scrot": self.has_scrot,
            "tesseract": self.has_tesseract,
            "wmctrl": self.has_wmctrl,
            "xrandr": self.has_xrandr,
        }
        available = [k for k, v in tools.items() if v]
        missing = [k for k, v in tools.items() if not v]
        logger.info("Outils disponibles: %s", ", ".join(available) or "aucun")
        if missing:
            logger.info("Outils manquants: %s", ", ".join(missing))

    # ── 1. Titre de la fenetre active ─────────────────────────────────────

    def screen_read_window_title(self) -> str:
        """Lit le titre de la fenetre active.

        Utilise xdotool pour recuperer le nom de la fenetre au premier plan.
        Retourne le titre ou un message d'erreur en francais.
        """
        if not self.has_xdotool:
            return "Erreur : xdotool n'est pas installe."

        wid = _run(["xdotool", "getactivewindow"])
        if not wid:
            return "Impossible de determiner la fenetre active."

        title = _run(["xdotool", "getactivewindow", "getwindowname"])
        if not title:
            return "La fenetre active n'a pas de titre."

        return f"Titre de la fenetre : {title}"

    # ── 2. Presse-papiers ────────────────────────────────────────────────

    def screen_read_clipboard(self) -> str:
        """Lit le contenu du presse-papiers a voix haute.

        Recupere le texte du presse-papiers via xclip.
        """
        if not self.has_xclip:
            return "Erreur : xclip n'est pas installe."

        content = _run(["xclip", "-selection", "clipboard", "-o"])
        if not content:
            return "Le presse-papiers est vide."

        # Tronquer si trop long pour la lecture vocale
        if len(content) > 2000:
            content = content[:2000] + "... (tronque)"

        return f"Contenu du presse-papiers : {content}"

    # ── 3. Selection ─────────────────────────────────────────────────────

    def screen_read_selection(self) -> str:
        """Lit le texte actuellement selectionne.

        Copie la selection dans le presse-papiers via xdotool (Ctrl+C),
        puis lit le contenu copie.
        """
        if not self.has_xdotool or not self.has_xclip:
            return "Erreur : xdotool et xclip sont requis."

        # Sauvegarder le presse-papiers actuel
        old_clip = _run(["xclip", "-selection", "clipboard", "-o"])

        # Simuler Ctrl+C pour copier la selection
        _run(["xdotool", "key", "--clearmodifiers", "ctrl+c"])
        time.sleep(0.3)  # Laisser le temps a la copie

        # Lire le nouveau contenu
        content = _run(["xclip", "-selection", "clipboard", "-o"])

        # Tenter aussi la selection primaire (X11)
        if not content:
            content = _run(["xclip", "-selection", "primary", "-o"])

        # Restaurer l'ancien presse-papiers
        if old_clip:
            subprocess.run(
                ["xclip", "-selection", "clipboard"],
                input=old_clip, text=True, timeout=CMD_TIMEOUT,
                capture_output=True,
            )

        if not content:
            return "Aucun texte selectionne."

        if len(content) > 2000:
            content = content[:2000] + "... (tronque)"

        return f"Texte selectionne : {content}"

    # ── 4. Notifications GNOME ───────────────────────────────────────────

    def screen_read_notifications(self) -> str:
        """Lit les notifications recentes de GNOME.

        Interroge l'historique des notifications via dbus ou gdbus.
        """
        # Methode 1 : gdbus (GNOME Shell)
        try:
            result = subprocess.run(
                [
                    "gdbus", "call", "--session",
                    "--dest", "org.freedesktop.Notifications",
                    "--object-path", "/org/freedesktop/Notifications",
                    "--method", "org.freedesktop.Notifications.GetServerInformation",
                ],
                capture_output=True, text=True, timeout=CMD_TIMEOUT,
            )
            server_ok = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            server_ok = False

        # Methode 2 : lire le journal de notifications GNOME
        notif_text = ""
        try:
            # GNOME notification history via dbus introspection
            result = subprocess.run(
                [
                    "gdbus", "call", "--session",
                    "--dest", "org.gnome.Shell",
                    "--object-path", "/org/gnome/Shell/Notifications",
                    "--method", "org.freedesktop.DBus.Properties.GetAll",
                    "org.gnome.Shell.Notifications",
                ],
                capture_output=True, text=True, timeout=CMD_TIMEOUT,
            )
            if result.stdout.strip():
                notif_text = result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Methode 3 : journalctl recentes
        if not notif_text:
            notif_text = _run([
                "journalctl", "--user", "-t", "gnome-shell",
                "--since", "1 hour ago", "--no-pager", "-q",
                "--output", "cat",
            ], timeout=CMD_TIMEOUT)

        # Methode 4 : notify-log si disponible
        if not notif_text:
            log_path = Path.home() / ".local/share/gnome-shell/notifications"
            if log_path.exists():
                try:
                    notif_text = log_path.read_text(encoding="utf-8")[-3000:]
                except OSError:
                    pass

        if not notif_text:
            return "Aucune notification recente trouvee."

        # Nettoyer et formater
        lines = [l.strip() for l in notif_text.splitlines() if l.strip()]
        recent = lines[-10:]  # 10 dernieres
        return "Notifications recentes :\n" + "\n".join(f"  - {l}" for l in recent)

    # ── 5. Application active ────────────────────────────────────────────

    def screen_active_app(self) -> str:
        """Identifie l'application actuellement au premier plan.

        Retourne le nom de classe et le titre de la fenetre active.
        """
        if not self.has_xdotool:
            return "Erreur : xdotool n'est pas installe."

        wid = _run(["xdotool", "getactivewindow"])
        if not wid:
            return "Impossible de determiner la fenetre active."

        # Nom de la fenetre
        title = _run(["xdotool", "getactivewindow", "getwindowname"])

        # Classe WM
        wm_class = ""
        if self.has_xprop:
            raw = _run(["xprop", "-id", wid, "WM_CLASS"])
            match = re.search(r'"([^"]+)",\s*"([^"]+)"', raw)
            if match:
                wm_class = match.group(2)  # Nom de classe (ex: "Firefox")

        # PID du processus
        pid = _run(["xdotool", "getactivewindow", "getwindowpid"])

        # Nom du processus via /proc
        proc_name = ""
        if pid:
            try:
                proc_name = Path(f"/proc/{pid}/comm").read_text().strip()
            except OSError:
                pass

        parts = []
        if wm_class:
            parts.append(f"Application : {wm_class}")
        if proc_name and proc_name != wm_class.lower():
            parts.append(f"Processus : {proc_name}")
        if title:
            parts.append(f"Titre : {title}")
        if pid:
            parts.append(f"PID : {pid}")

        return "\n".join(parts) if parts else "Application active inconnue."

    # ── 6. Liste des applications ouvertes ───────────────────────────────

    def screen_list_open_apps(self) -> str:
        """Liste toutes les applications ouvertes avec leur nom de fenetre.

        Utilise wmctrl si disponible, sinon xdotool.
        """
        apps: list[str] = []

        if self.has_wmctrl:
            raw = _run(["wmctrl", "-l", "-p"])
            for line in raw.splitlines():
                parts = line.split(None, 4)
                if len(parts) >= 5:
                    wid, desktop, pid, host = parts[0], parts[1], parts[2], parts[3]
                    title = parts[4]
                    if desktop != "-1":  # Ignorer les fenetres speciales
                        apps.append(f"  [{desktop}] {title} (PID {pid})")
        else:
            # Fallback avec xdotool
            if not self.has_xdotool:
                return "Erreur : wmctrl ou xdotool requis."
            raw = _run(["xdotool", "search", "--onlyvisible", "--name", ""])
            for wid in raw.splitlines():
                wid = wid.strip()
                if wid:
                    name = _run(["xdotool", "getwindowname", wid])
                    if name and name not in ("Desktop", ""):
                        apps.append(f"  - {name}")

        if not apps:
            return "Aucune application ouverte detectee."

        return f"Applications ouvertes ({len(apps)}) :\n" + "\n".join(apps)

    # ── 7. Decrire l'ecran (Vision IA) ───────────────────────────────────

    def screen_describe_screen(self) -> str:
        """Capture l'ecran et utilise une IA vision pour decrire le contenu.

        Prend une capture avec scrot, encode en base64, puis envoie a
        LM Studio ou Ollama pour obtenir une description en francais.
        Si aucun modele vision n'est disponible, retourne le titre + app.
        """
        if not self.has_scrot:
            # Fallback sans capture
            return self._describe_fallback()

        # Capture d'ecran
        screenshot_path = SCREENSHOT_DIR / f"screen_{int(time.time())}.png"
        _run(["scrot", "-o", str(screenshot_path)], timeout=10)

        if not screenshot_path.exists():
            return self._describe_fallback()

        # Encoder en base64
        try:
            img_b64 = base64.b64encode(screenshot_path.read_bytes()).decode("ascii")
        except OSError:
            return self._describe_fallback()
        finally:
            # Nettoyer la capture
            try:
                screenshot_path.unlink(missing_ok=True)
            except OSError:
                pass

        # Essayer LM Studio d'abord, puis Ollama
        description = self._vision_lmstudio(img_b64)
        if not description:
            description = self._vision_ollama(img_b64)

        if not description:
            return self._describe_fallback()

        return f"Description de l'ecran :\n{description}"

    def _vision_lmstudio(self, img_b64: str) -> str:
        """Envoie l'image a LM Studio pour description via API vision."""
        try:
            import requests
            payload = {
                "model": VISION_MODEL_LMS,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "/nothink Decris en francais ce que tu vois sur cette capture d'ecran. "
                                        "Mentionne les fenetres ouvertes, le texte visible, les icones importantes.",
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{img_b64}"},
                            },
                        ],
                    }
                ],
                "max_tokens": 500,
                "temperature": 0.3,
            }
            resp = requests.post(LMSTUDIO_URL, json=payload, timeout=VISION_TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                # LM Studio format
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "").strip()
        except Exception as exc:
            logger.debug("Vision LM Studio echouee: %s", exc)
        return ""

    def _vision_ollama(self, img_b64: str) -> str:
        """Envoie l'image a Ollama pour description via API vision."""
        try:
            import requests
            payload = {
                "model": VISION_MODEL_OLLAMA,
                "messages": [
                    {
                        "role": "user",
                        "content": "Decris en francais ce que tu vois sur cette capture d'ecran. "
                                   "Mentionne les fenetres ouvertes, le texte visible, les icones importantes.",
                        "images": [img_b64],
                    }
                ],
                "stream": False,
                "think": False,
            }
            resp = requests.post(OLLAMA_URL, json=payload, timeout=VISION_TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("message", {}).get("content", "").strip()
        except Exception as exc:
            logger.debug("Vision Ollama echouee: %s", exc)
        return ""

    def _describe_fallback(self) -> str:
        """Description minimale sans vision IA : titre + application."""
        title = self.screen_read_window_title()
        app = self.screen_active_app()
        return f"Vision IA indisponible. Informations disponibles :\n{app}\n{title}"

    # ── 8. OCR a une position ────────────────────────────────────────────

    def screen_read_text_at(self, x: int = 0, y: int = 0, width: int = 400, height: int = 200) -> str:
        """Effectue un OCR sur une region autour des coordonnees donnees.

        Capture une zone de l'ecran centree sur (x, y) et utilise
        Tesseract pour extraire le texte. Si x=0 et y=0, utilise la
        position du curseur.
        """
        if not self.has_scrot:
            return "Erreur : scrot n'est pas installe."
        if not self.has_tesseract:
            return "Erreur : tesseract n'est pas installe."

        # Position du curseur si non specifiee
        if x == 0 and y == 0:
            pos = _run(["xdotool", "getmouselocation"])
            match = re.search(r"x:(\d+)\s+y:(\d+)", pos)
            if match:
                x, y = int(match.group(1)), int(match.group(2))
            else:
                return "Impossible de determiner la position du curseur."

        # Calculer la region (centree sur x, y)
        rx = max(0, x - width // 2)
        ry = max(0, y - height // 2)

        # Capture de la region
        region_path = SCREENSHOT_DIR / f"region_{int(time.time())}.png"
        geometry = f"{width}x{height}+{rx}+{ry}"

        _run(["scrot", "-a", geometry, "-o", str(region_path)], timeout=10)

        if not region_path.exists():
            # Fallback: capturer tout l'ecran et cropper avec convert
            full_path = SCREENSHOT_DIR / f"full_{int(time.time())}.png"
            _run(["scrot", "-o", str(full_path)], timeout=10)
            if full_path.exists() and _tool_available("convert"):
                _run([
                    "convert", str(full_path),
                    "-crop", geometry,
                    str(region_path),
                ], timeout=10)
                full_path.unlink(missing_ok=True)

        if not region_path.exists():
            return f"Impossible de capturer la region ({x}, {y})."

        # OCR avec Tesseract
        try:
            text = _run([
                "tesseract", str(region_path), "stdout",
                "-l", "fra+eng",
                "--psm", "6",
            ], timeout=15)
        finally:
            region_path.unlink(missing_ok=True)

        if not text:
            return f"Aucun texte detecte a la position ({x}, {y})."

        text = text.strip()
        return f"Texte OCR a ({x}, {y}) :\n{text}"

    # ── 9. Infos de la fenetre active ────────────────────────────────────

    def screen_window_info(self) -> str:
        """Affiche les informations detaillees de la fenetre active.

        Retourne la taille, la position, la classe WM, le PID, etc.
        """
        if not self.has_xdotool:
            return "Erreur : xdotool n'est pas installe."

        wid = _run(["xdotool", "getactivewindow"])
        if not wid:
            return "Impossible de determiner la fenetre active."

        info: dict[str, str] = {"ID fenetre": wid}

        # Titre
        title = _run(["xdotool", "getactivewindow", "getwindowname"])
        if title:
            info["Titre"] = title

        # Geometrie
        geo = _run(["xdotool", "getactivewindow", "getwindowgeometry"])
        if geo:
            # Parse "Window 123456\n  Position: 100,200 (screen: 0)\n  Geometry: 800x600"
            pos_match = re.search(r"Position:\s*(\d+),(\d+)", geo)
            size_match = re.search(r"Geometry:\s*(\d+x\d+)", geo)
            if pos_match:
                info["Position"] = f"{pos_match.group(1)}, {pos_match.group(2)}"
            if size_match:
                info["Taille"] = size_match.group(1)

        # Classe WM
        if self.has_xprop:
            raw = _run(["xprop", "-id", wid, "WM_CLASS"])
            match = re.search(r'"([^"]+)",\s*"([^"]+)"', raw)
            if match:
                info["Classe"] = match.group(2)
                info["Instance"] = match.group(1)

            # Type de fenetre
            type_raw = _run(["xprop", "-id", wid, "_NET_WM_WINDOW_TYPE"])
            type_match = re.search(r"= (.+)$", type_raw)
            if type_match:
                wtype = type_match.group(1).replace("_NET_WM_WINDOW_TYPE_", "")
                info["Type"] = wtype

            # Etat
            state_raw = _run(["xprop", "-id", wid, "_NET_WM_STATE"])
            state_match = re.search(r"= (.+)$", state_raw)
            if state_match and "not found" not in state_raw:
                states = state_match.group(1).replace("_NET_WM_STATE_", "")
                info["Etat"] = states

        # PID
        pid = _run(["xdotool", "getactivewindow", "getwindowpid"])
        if pid:
            info["PID"] = pid
            try:
                proc_name = Path(f"/proc/{pid}/comm").read_text().strip()
                info["Processus"] = proc_name
            except OSError:
                pass

        lines = [f"  {k} : {v}" for k, v in info.items()]
        return "Informations fenetre :\n" + "\n".join(lines)

    # ── 10. Lire le menu (accessibilite) ─────────────────────────────────

    def screen_read_menu(self) -> str:
        """Tente de lire les elements du menu de l'application active.

        Utilise atspi / accessibilite GNOME si disponible,
        sinon tente une approche par xprop.
        """
        # Methode 1 : atspi via python-atspi2 / gi
        try:
            import gi
            gi.require_version("Atspi", "2.0")
            from gi.repository import Atspi
            desktop = Atspi.get_desktop(0)
            if desktop:
                app_count = desktop.get_child_count()
                # Trouver l'application active
                active_title = _run(["xdotool", "getactivewindow", "getwindowname"])
                menu_items: list[str] = []

                for i in range(app_count):
                    app = desktop.get_child_at_index(i)
                    if app and app.get_name():
                        # Parcourir les menus
                        self._collect_menu_items(app, menu_items, depth=0, max_depth=3)
                        if menu_items:
                            break

                if menu_items:
                    return "Elements de menu :\n" + "\n".join(f"  - {m}" for m in menu_items[:30])
        except (ImportError, Exception) as exc:
            logger.debug("atspi indisponible: %s", exc)

        # Methode 2 : tenter de lire via xprop _NET_WM_MENU ou GTK
        if self.has_xprop:
            wid = _run(["xdotool", "getactivewindow"])
            if wid:
                # GtkMenuBar via accessibilite - best effort
                raw = _run(["xprop", "-id", wid, "_GTK_MENUBAR_OBJECT_PATH"])
                if raw and "not found" not in raw:
                    return f"Chemin menu GTK detecte : {raw}"

        return "Lecture du menu non disponible (accessibilite atspi non activee ou absente)."

    def _collect_menu_items(self, node: Any, items: list[str], depth: int, max_depth: int):
        """Parcourt recursivement l'arbre d'accessibilite pour extraire les menus."""
        if depth > max_depth or len(items) > 30:
            return
        try:
            role = node.get_role_name() if hasattr(node, "get_role_name") else ""
            name = node.get_name() if hasattr(node, "get_name") else ""
            if role in ("menu item", "menu", "menu bar", "check menu item", "radio menu item"):
                if name:
                    prefix = "  " * depth
                    items.append(f"{prefix}{name} [{role}]")
            child_count = node.get_child_count() if hasattr(node, "get_child_count") else 0
            for i in range(min(child_count, 50)):
                child = node.get_child_at_index(i)
                if child:
                    self._collect_menu_items(child, items, depth + 1, max_depth)
        except Exception:
            pass

    # ── 11. Zoom / Loupe ─────────────────────────────────────────────────

    def screen_magnify(self, factor: int = 2) -> str:
        """Agrandit la zone autour du curseur.

        Capture une zone autour du curseur, l'agrandit par le facteur donne,
        et l'affiche dans une fenetre temporaire. Utilise scrot + convert.
        """
        if not self.has_scrot:
            return "Erreur : scrot n'est pas installe."

        # Position du curseur
        pos = _run(["xdotool", "getmouselocation"])
        match = re.search(r"x:(\d+)\s+y:(\d+)", pos)
        if not match:
            return "Impossible de determiner la position du curseur."

        cx, cy = int(match.group(1)), int(match.group(2))
        # Zone a capturer (200x200 autour du curseur)
        cap_size = 200
        rx = max(0, cx - cap_size // 2)
        ry = max(0, cy - cap_size // 2)

        region_path = SCREENSHOT_DIR / f"magnify_src_{int(time.time())}.png"
        zoomed_path = SCREENSHOT_DIR / f"magnify_zoom_{int(time.time())}.png"

        geometry = f"{cap_size}x{cap_size}+{rx}+{ry}"
        _run(["scrot", "-a", geometry, "-o", str(region_path)], timeout=10)

        if not region_path.exists():
            return "Impossible de capturer la zone."

        # Agrandir avec ImageMagick convert ou Python PIL
        new_size = cap_size * factor
        success = False

        if _tool_available("convert"):
            _run([
                "convert", str(region_path),
                "-resize", f"{new_size}x{new_size}",
                "-filter", "point",  # Nearest-neighbor pour un zoom net
                str(zoomed_path),
            ], timeout=10)
            success = zoomed_path.exists()
        else:
            # Fallback PIL
            try:
                from PIL import Image
                img = Image.open(region_path)
                img = img.resize((new_size, new_size), Image.NEAREST)
                img.save(zoomed_path)
                success = True
            except (ImportError, OSError) as exc:
                logger.debug("PIL fallback echoue: %s", exc)

        # Nettoyer la source
        region_path.unlink(missing_ok=True)

        if not success:
            return "Impossible d'agrandir l'image (ni convert ni PIL disponible)."

        # Afficher l'image zoomee
        if _tool_available("eog"):
            subprocess.Popen(["eog", str(zoomed_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif _tool_available("feh"):
            subprocess.Popen(["feh", str(zoomed_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif _tool_available("xdg-open"):
            subprocess.Popen(["xdg-open", str(zoomed_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            return f"Image agrandie sauvegardee : {zoomed_path}"

        return f"Zone agrandie x{factor} autour de ({cx}, {cy}). Image affichee."

    # ── 12. Barre des taches / panel ─────────────────────────────────────

    def screen_taskbar_info(self) -> str:
        """Liste les elements de la barre des taches / panel GNOME.

        Recupere les fenetres dans la taskbar via wmctrl et les favoris
        du dash GNOME via gsettings.
        """
        sections: list[str] = []

        # Favoris du dash GNOME
        favorites = _run(["gsettings", "get", "org.gnome.shell", "favorite-apps"])
        if favorites:
            # Parse: ['firefox.desktop', 'org.gnome.Nautilus.desktop', ...]
            apps = re.findall(r"'([^']+)'", favorites)
            if apps:
                clean = [a.replace(".desktop", "") for a in apps]
                sections.append("Favoris du dock :\n" + "\n".join(f"  - {a}" for a in clean))

        # Fenetres ouvertes dans la barre
        if self.has_wmctrl:
            raw = _run(["wmctrl", "-l"])
            windows = []
            for line in raw.splitlines():
                parts = line.split(None, 3)
                if len(parts) >= 4:
                    desktop = parts[1]
                    title = parts[3]
                    if desktop != "-1" and title:
                        windows.append(title)
            if windows:
                sections.append(
                    f"Fenetres dans la barre ({len(windows)}) :\n"
                    + "\n".join(f"  - {w}" for w in windows)
                )

        # Bureau actuel
        current_desktop = _run(["xdotool", "get-desktop"]) if self.has_xdotool else ""
        total_desktops = _run(["xdotool", "get-num-desktops"]) if self.has_xdotool else ""
        if current_desktop and total_desktops:
            sections.append(f"Bureau : {int(current_desktop) + 1} sur {total_desktops}")

        # Resolution ecran
        if self.has_xrandr:
            raw = _run(["xrandr", "--current"])
            res_match = re.search(r"(\d+x\d+)\+\d+\+\d+", raw)
            if res_match:
                sections.append(f"Resolution : {res_match.group(1)}")

        if not sections:
            return "Impossible de lire les informations de la barre des taches."

        return "Informations du panel :\n" + "\n\n".join(sections)

    # ── 13. Contraste eleve ────────────────────────────────────────────────

    def screen_high_contrast(self, on_off: str = "toggle") -> str:
        """Active/desactive le mode contraste eleve GNOME."""
        if on_off == "toggle":
            current = _run(["gsettings", "get", "org.gnome.desktop.a11y.interface", "high-contrast"])
            new_val = "false" if "true" in current.lower() else "true"
        else:
            new_val = "true" if on_off.lower() in ("on", "oui", "activer") else "false"
        _run(["gsettings", "set", "org.gnome.desktop.a11y.interface", "high-contrast", new_val])
        return f"Contraste eleve {'active' if new_val == 'true' else 'desactive'}"

    # ── 14. Taille du texte ────────────────────────────────────────────────

    def screen_text_size(self, action: str = "increase") -> str:
        """Augmenter/diminuer la taille du texte systeme."""
        current = _run(["gsettings", "get", "org.gnome.desktop.interface", "text-scaling-factor"])
        try:
            factor = float(current.strip())
        except ValueError:
            factor = 1.0
        if action in ("increase", "plus", "augmenter"):
            factor = min(3.0, factor + 0.25)
        elif action in ("decrease", "moins", "diminuer"):
            factor = max(0.5, factor - 0.25)
        elif action in ("reset", "normal"):
            factor = 1.0
        _run(["gsettings", "set", "org.gnome.desktop.interface", "text-scaling-factor", str(factor)])
        return f"Taille du texte: {factor:.2f}x"

    # ── 15. Lecture plein ecran OCR ────────────────────────────────────────

    def screen_full_ocr(self) -> str:
        """OCR sur tout l'ecran (extraction de tout le texte visible)."""
        if not self.has_scrot or not self.has_tesseract:
            return "Erreur: scrot et tesseract requis pour OCR plein ecran."

        screenshot = SCREENSHOT_DIR / f"fullscr_{int(time.time())}.png"
        _run(["scrot", "-o", str(screenshot)], timeout=10)

        if not screenshot.exists():
            return "Impossible de capturer l'ecran."

        try:
            text = _run([
                "tesseract", str(screenshot), "stdout",
                "-l", "fra+eng", "--psm", "3",
            ], timeout=30)
        finally:
            screenshot.unlink(missing_ok=True)

        if not text or not text.strip():
            return "Aucun texte detecte sur l'ecran."

        # Nettoyer et tronquer
        clean = "\n".join(l for l in text.splitlines() if l.strip())
        if len(clean) > 3000:
            clean = clean[:3000] + "\n... (tronque)"
        return f"Texte visible sur l'ecran:\n{clean}"

    # ── 16. Resume IA de l'ecran ──────────────────────────────────────────

    def screen_summarize(self) -> str:
        """Resume intelligent de ce qui est affiche (via IA locale)."""
        # D'abord capturer le titre et l'app
        title = self.screen_read_window_title()
        app = self.screen_active_app()

        # Tenter OCR rapide
        ocr_text = ""
        if self.has_scrot and self.has_tesseract:
            screenshot = SCREENSHOT_DIR / f"summ_{int(time.time())}.png"
            _run(["scrot", "-o", str(screenshot)], timeout=10)
            if screenshot.exists():
                try:
                    ocr_text = _run([
                        "tesseract", str(screenshot), "stdout",
                        "-l", "fra+eng", "--psm", "3",
                    ], timeout=15)
                finally:
                    screenshot.unlink(missing_ok=True)

        # Construire un resume
        parts = [app]
        if ocr_text:
            # Prendre les premieres lignes significatives
            lines = [l.strip() for l in ocr_text.splitlines() if len(l.strip()) > 5][:10]
            if lines:
                parts.append("Contenu visible:\n  " + "\n  ".join(lines))

        return "\n".join(parts)

    # ── 17. Curseur de souris position ────────────────────────────────────

    def screen_cursor_position(self) -> str:
        """Position actuelle du curseur."""
        if not self.has_xdotool:
            return "xdotool requis."
        pos = _run(["xdotool", "getmouselocation"])
        match = re.search(r"x:(\d+)\s+y:(\d+)", pos)
        if match:
            return f"Curseur: x={match.group(1)}, y={match.group(2)}"
        return "Position du curseur inconnue"

    # ── 18. Couleur sous le curseur ───────────────────────────────────────

    def screen_color_at_cursor(self) -> str:
        """Identifie la couleur du pixel sous le curseur."""
        if not self.has_scrot:
            return "scrot requis."

        pos = _run(["xdotool", "getmouselocation"])
        match = re.search(r"x:(\d+)\s+y:(\d+)", pos)
        if not match:
            return "Position inconnue."

        x, y = match.group(1), match.group(2)
        # Capturer 1 pixel
        pixel_path = SCREENSHOT_DIR / f"pixel_{int(time.time())}.png"
        _run(["scrot", "-a", f"1x1+{x}+{y}", "-o", str(pixel_path)], timeout=5)

        if not pixel_path.exists():
            return "Impossible de capturer le pixel."

        try:
            if _tool_available("convert"):
                color = _run(["convert", str(pixel_path), "-format", "%[hex:u.p{0,0}]", "info:"])
                if color:
                    return f"Couleur a ({x},{y}): #{color}"
            # Fallback PIL
            try:
                from PIL import Image
                img = Image.open(pixel_path)
                r, g, b = img.getpixel((0, 0))[:3]
                return f"Couleur a ({x},{y}): RGB({r},{g},{b}) / #{r:02x}{g:02x}{b:02x}"
            except ImportError:
                pass
        finally:
            pixel_path.unlink(missing_ok=True)

        return "Impossible de determiner la couleur."


# ═══════════════════════════════════════════════════════════════════════════════
# Commandes vocales
# ═══════════════════════════════════════════════════════════════════════════════

# Instance globale
_reader = VoiceScreenReader()

VOICE_COMMANDS: dict[str, dict[str, Any]] = {
    "screen_read_title": {
        "patterns": [
            r"lis le titre",
            r"quel est le titre",
            r"titre de la fen[eê]tre",
            r"lis.*titre",
        ],
        "method": "screen_read_window_title",
        "description": "Lit le titre de la fenetre active",
    },
    "screen_read_selection": {
        "patterns": [
            r"lis la s[eé]lection",
            r"lis ce que j'ai s[eé]lectionn[eé]",
            r"lis.*s[eé]lection",
            r"qu'est.ce qui est s[eé]lectionn[eé]",
        ],
        "method": "screen_read_selection",
        "description": "Lit le texte selectionne",
    },
    "screen_read_clipboard": {
        "patterns": [
            r"lis le presse.papiers",
            r"presse.papiers",
            r"clipboard",
            r"qu'est.ce.*(copi|presse)",
        ],
        "method": "screen_read_clipboard",
        "description": "Lit le contenu du presse-papiers",
    },
    "screen_active_app": {
        "patterns": [
            r"quelle application",
            r"quelle app",
            r"quel programme",
            r"application active",
            r"c'est quoi.*app",
        ],
        "method": "screen_active_app",
        "description": "Identifie l'application active",
    },
    "screen_list_apps": {
        "patterns": [
            r"quelles applications ouvertes",
            r"liste.*applications",
            r"applications ouvertes",
            r"fen[eê]tres ouvertes",
            r"qu'est.ce qui est ouvert",
        ],
        "method": "screen_list_open_apps",
        "description": "Liste les applications ouvertes",
    },
    "screen_describe": {
        "patterns": [
            r"d[eé]cris l'[eé]cran",
            r"qu'est.ce que je vois",
            r"d[eé]cris.*[eé]cran",
            r"que vois.tu",
            r"qu'y a.t.il.*[eé]cran",
        ],
        "method": "screen_describe_screen",
        "description": "Decrit le contenu de l'ecran via IA vision",
    },
    "screen_notifications": {
        "patterns": [
            r"lis les notifications",
            r"notifications",
            r"quelles notifications",
            r"notifs",
        ],
        "method": "screen_read_notifications",
        "description": "Lit les notifications recentes",
    },
    "screen_window_info": {
        "patterns": [
            r"info fen[eê]tre",
            r"informations fen[eê]tre",
            r"d[eé]tails fen[eê]tre",
            r"taille fen[eê]tre",
            r"position fen[eê]tre",
        ],
        "method": "screen_window_info",
        "description": "Infos detaillees sur la fenetre active",
    },
    "screen_magnify": {
        "patterns": [
            r"zoom",
            r"agrandis la zone",
            r"loupe",
            r"magnifier",
            r"zoome",
        ],
        "method": "screen_magnify",
        "description": "Agrandit la zone autour du curseur",
    },
    "screen_taskbar": {
        "patterns": [
            r"barre des t[aâ]ches",
            r"taskbar",
            r"panel",
            r"dock",
            r"info.*barre",
        ],
        "method": "screen_taskbar_info",
        "description": "Informations sur la barre des taches",
    },
    "screen_read_menu": {
        "patterns": [
            r"lis le menu",
            r"menu",
            r"[eé]l[eé]ments du menu",
            r"quelles options",
        ],
        "method": "screen_read_menu",
        "description": "Lit les elements du menu",
    },
    "screen_ocr": {
        "patterns": [
            r"lis.*texte.*[àa] (\d+)\s*[,x]\s*(\d+)",
            r"ocr\s+[àa]",
            r"texte.*position",
        ],
        "method": "screen_read_text_at",
        "description": "OCR sur une region de l'ecran",
    },
    "screen_high_contrast": {
        "patterns": [
            r"contraste [eé]lev[eé]",
            r"haut contraste",
            r"high contrast",
            r"contraste fort",
            r"active.*contraste",
        ],
        "method": "screen_high_contrast",
        "description": "Active/desactive le mode contraste eleve",
    },
    "screen_text_bigger": {
        "patterns": [
            r"texte plus gros",
            r"augmente.*texte",
            r"police plus grande",
            r"grossis.*texte",
            r"agrandis.*texte",
        ],
        "method": "screen_text_size",
        "description": "Augmenter la taille du texte systeme",
        "params": {"action": "increase"},
    },
    "screen_text_smaller": {
        "patterns": [
            r"texte plus petit",
            r"diminue.*texte",
            r"police plus petite",
            r"r[eé]duis.*texte",
        ],
        "method": "screen_text_size",
        "description": "Diminuer la taille du texte systeme",
        "params": {"action": "decrease"},
    },
    "screen_text_normal": {
        "patterns": [
            r"texte normal",
            r"taille.*texte.*normal",
            r"r[eé]initialise.*texte",
            r"reset.*texte",
        ],
        "method": "screen_text_size",
        "description": "Reinitialiser la taille du texte",
        "params": {"action": "reset"},
    },
    "screen_full_ocr": {
        "patterns": [
            r"ocr.*(?:plein|complet|tout)",
            r"lis.*tout.*[eé]cran",
            r"texte visible",
            r"tout le texte",
            r"lis l'[eé]cran",
        ],
        "method": "screen_full_ocr",
        "description": "OCR plein ecran - extrait tout le texte visible",
    },
    "screen_summarize": {
        "patterns": [
            r"r[eé]sum[eé].*[eé]cran",
            r"r[eé]sume.*affich",
            r"qu'est.ce.*affich",
            r"synth[eè]se.*[eé]cran",
        ],
        "method": "screen_summarize",
        "description": "Resume intelligent de l'ecran",
    },
    "screen_cursor_pos": {
        "patterns": [
            r"position.*curseur",
            r"o[uù].*curseur",
            r"curseur.*o[uù]",
            r"coordonn[eé]es.*curseur",
        ],
        "method": "screen_cursor_position",
        "description": "Position actuelle du curseur",
    },
    "screen_color": {
        "patterns": [
            r"couleur.*curseur",
            r"quelle couleur",
            r"couleur.*pixel",
            r"identifie.*couleur",
            r"pipette",
        ],
        "method": "screen_color_at_cursor",
        "description": "Couleur du pixel sous le curseur",
    },
}

PARAM_PATTERNS: dict[str, list[dict[str, Any]]] = {
    "screen_magnify": [
        {
            "param": "factor",
            "patterns": [
                r"(?:zoom|facteur|x)\s*(\d+)",
                r"(\d+)\s*(?:fois|x)",
            ],
            "type": int,
            "default": 2,
        },
    ],
    "screen_ocr": [
        {
            "param": "x",
            "patterns": [
                r"(?:x|position)\s*(\d+)",
                r"(\d+)\s*[,x]\s*\d+",
            ],
            "type": int,
            "default": 0,
        },
        {
            "param": "y",
            "patterns": [
                r"(?:y|position\s*\d+\s*[,x])\s*(\d+)",
                r"\d+\s*[,x]\s*(\d+)",
            ],
            "type": int,
            "default": 0,
        },
        {
            "param": "width",
            "patterns": [r"largeur\s*(\d+)"],
            "type": int,
            "default": 400,
        },
        {
            "param": "height",
            "patterns": [r"hauteur\s*(\d+)"],
            "type": int,
            "default": 200,
        },
    ],
}


# ═══════════════════════════════════════════════════════════════════════════════
# Execution des commandes vocales
# ═══════════════════════════════════════════════════════════════════════════════

def _extract_params(command_key: str, text: str) -> dict[str, Any]:
    """Extrait les parametres d'une commande vocale a partir du texte."""
    params: dict[str, Any] = {}
    param_defs = PARAM_PATTERNS.get(command_key, [])
    for pdef in param_defs:
        value = pdef["default"]
        for pattern in pdef["patterns"]:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                try:
                    value = pdef["type"](m.group(1))
                except (ValueError, IndexError):
                    pass
                break
        params[pdef["param"]] = value
    return params


def execute_screen_command(text: str) -> str | None:
    """Execute une commande de lecture d'ecran a partir du texte vocal.

    Analyse le texte, identifie la commande correspondante, extrait
    les parametres eventuels et execute la methode appropriee.

    Args:
        text: Texte vocal reconnu par le STT.

    Returns:
        Le resultat en francais, ou None si aucune commande reconnue.
    """
    text_lower = text.lower().strip()

    for cmd_key, cmd_def in VOICE_COMMANDS.items():
        for pattern in cmd_def["patterns"]:
            if re.search(pattern, text_lower, re.IGNORECASE):
                method_name = cmd_def["method"]
                method = getattr(_reader, method_name, None)
                if method is None:
                    return f"Erreur : methode {method_name} introuvable."

                # Parametres pre-definis dans la commande
                params = dict(cmd_def.get("params", {}))
                # Extraire les parametres dynamiques du texte
                params.update(_extract_params(cmd_key, text_lower))

                try:
                    if params:
                        result = method(**params)
                    else:
                        result = method()
                    logger.info("Commande ecran '%s' executee", cmd_key)
                    return result
                except Exception as exc:
                    logger.error("Erreur commande ecran '%s': %s", cmd_key, exc)
                    return f"Erreur lors de l'execution : {exc}"

    return None


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if len(sys.argv) < 2:
        print("Usage: voice_screen_reader.py <commande vocale>")
        print()
        print("Commandes disponibles :")
        for key, cmd in VOICE_COMMANDS.items():
            print(f"  {cmd['description']}")
            print(f"    Exemples: {', '.join(repr(p) for p in cmd['patterns'][:2])}")
        print()
        print("Exemples :")
        print('  python voice_screen_reader.py "quel est le titre"')
        print('  python voice_screen_reader.py "decris l\'ecran"')
        print('  python voice_screen_reader.py "quelles applications ouvertes"')
        print('  python voice_screen_reader.py "zoom x3"')
        sys.exit(0)

    query = " ".join(sys.argv[1:])
    result = execute_screen_command(query)

    if result:
        print(result)
    else:
        print(f"Commande non reconnue : {query!r}")
        print("Tapez sans argument pour voir les commandes disponibles.")
        sys.exit(1)
