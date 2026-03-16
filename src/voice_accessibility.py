"""JARVIS — Systeme d'accessibilite vocale pour Linux.

Fournit des commandes d'accessibilite completes : lecteur d'ecran, loupe/zoom,
haut contraste, clavier visuel, dictee amelioree et navigation clavier.
Utilise xdotool, gsettings, orca, tesseract, xclip et piper TTS.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger("jarvis.voice_accessibility")

# ═══════════════════════════════════════════════════════════════════════════════
# Constantes
# ═══════════════════════════════════════════════════════════════════════════════

CMD_TIMEOUT: int = 5
VISION_TIMEOUT: int = 30
SCREENSHOT_DIR: Path = Path(tempfile.gettempdir()) / "jarvis_a11y_screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)

LMSTUDIO_URL: str = "http://127.0.0.1:1234/v1/chat/completions"

# Facteurs par defaut pour le zoom et la taille du texte
DEFAULT_ZOOM_STEP: float = 0.5
DEFAULT_TEXT_SCALE_STEP: float = 0.2
DEFAULT_TEXT_SCALE: float = 1.0
MIN_ZOOM: float = 1.0
MAX_ZOOM: float = 10.0
MIN_TEXT_SCALE: float = 0.5
MAX_TEXT_SCALE: float = 3.0

# Dictee : mots-cles speciaux transformes en caracteres
DICTATION_PUNCTUATION: dict[str, str] = {
    "point": ".",
    "virgule": ",",
    "point d'exclamation": "!",
    "point d'interrogation": "?",
    "deux points": ":",
    "point-virgule": ";",
    "points de suspension": "...",
    "guillemets": '"',
    "parenthese ouvrante": "(",
    "parenthese fermante": ")",
    "tiret": "-",
    "apostrophe": "'",
}

# Navigation : mapping commande vocale -> touche xdotool
NAVIGATION_KEYS: dict[str, str] = {
    "tab suivant": "Tab",
    "entre": "Return",
    "echappe": "Escape",
    "alt tab": "alt+Tab",
    "page suivante": "Next",
    "page precedente": "Prior",
    "fleche haut": "Up",
    "fleche bas": "Down",
    "fleche gauche": "Left",
    "fleche droite": "Right",
    "debut": "Home",
    "fin": "End",
    "supprimer": "Delete",
    "retour arriere": "BackSpace",
}


# ═══════════════════════════════════════════════════════════════════════════════
# Utilitaires systeme
# ═══════════════════════════════════════════════════════════════════════════════

def _run(cmd: list[str], timeout: int = CMD_TIMEOUT, input_data: str | None = None) -> str:
    """Execute une commande shell et retourne stdout."""
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
        logger.warning("Commande echouee %s : %s", cmd, exc)
        return ""


def _run_detached(cmd: list[str]) -> None:
    """Lance un processus detache (fire-and-forget)."""
    try:
        subprocess.Popen(  # noqa: S603
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, OSError) as exc:
        logger.warning("Lancement detache echoue %s : %s", cmd, exc)


def _has_tool(name: str) -> bool:
    """Verifie si un outil est disponible dans le PATH."""
    return shutil.which(name) is not None


def _gsettings_get(schema: str, key: str) -> str:
    """Recupere une valeur gsettings."""
    return _run(["gsettings", "get", schema, key])


def _gsettings_set(schema: str, key: str, value: str) -> bool:
    """Modifie une valeur gsettings."""
    result = _run(["gsettings", "set", schema, key, value])
    return result is not None


# ═══════════════════════════════════════════════════════════════════════════════
# Classe principale
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class VoiceAccessibilityManager:
    """Gestionnaire central d'accessibilite vocale pour Linux (GNOME + X11).

    Regroupe lecteur d'ecran, loupe/zoom, haut contraste,
    clavier visuel, dictee amelioree et navigation clavier.
    """

    # Etat interne
    screen_reader_active: bool = False
    dictation_active: bool = False
    high_contrast_active: bool = False
    screen_keyboard_active: bool = False
    current_zoom: float = 1.0
    current_text_scale: float = 1.0
    dictation_buffer: list[str] = field(default_factory=list)

    # Registre des commandes : pattern -> callback
    _command_map: dict[str, Callable[..., dict[str, Any]]] = field(
        default_factory=dict, init=False, repr=False,
    )

    def __post_init__(self) -> None:
        """Enregistre toutes les commandes d'accessibilite."""
        self._register_commands()
        self._sync_system_state()

    # ───────────────────────────────────────────────────────────────────────
    # Enregistrement des commandes
    # ───────────────────────────────────────────────────────────────────────

    def _register_commands(self) -> None:
        """Construit le mapping commande vocale -> methode."""
        # Lecteur d'ecran
        self._command_map["lis cette fenetre"] = self._read_active_window
        self._command_map["decris l'ecran"] = self._describe_screen
        self._command_map["lis le texte selectionne"] = self._read_selection

        # Loupe et zoom
        self._command_map["zoom avant"] = self._zoom_in
        self._command_map["zoom arriere"] = self._zoom_out
        self._command_map["taille du texte plus grande"] = self._text_scale_up
        self._command_map["taille du texte normale"] = self._text_scale_reset

        # Haut contraste
        self._command_map["contraste eleve"] = self._high_contrast_on
        self._command_map["contraste normal"] = self._high_contrast_off
        self._command_map["inverse les couleurs"] = self._invert_colors

        # Clavier visuel
        self._command_map["clavier a l'ecran"] = self._screen_keyboard_on
        self._command_map["ferme le clavier"] = self._screen_keyboard_off

        # Dictee amelioree
        self._command_map["mode dictee"] = self._dictation_start
        self._command_map["arrete la dictee"] = self._dictation_stop
        self._command_map["corrige le dernier mot"] = self._dictation_correct_last
        self._command_map["nouvelle ligne"] = self._dictation_newline
        self._command_map["point"] = self._dictation_period

        # Navigation clavier
        for vocal_key, xdotool_key in NAVIGATION_KEYS.items():
            # Capture de xdotool_key dans la closure
            self._command_map[vocal_key] = (
                lambda k=xdotool_key: self._send_key(k)
            )

    def _sync_system_state(self) -> None:
        """Synchronise l'etat interne avec les reglages systeme actuels."""
        try:
            # Zoom actuel
            raw_zoom = _gsettings_get(
                "org.gnome.desktop.a11y.magnifier", "mag-factor",
            )
            if raw_zoom:
                self.current_zoom = float(raw_zoom)

            # Echelle du texte
            raw_scale = _gsettings_get(
                "org.gnome.desktop.interface", "text-scaling-factor",
            )
            if raw_scale:
                self.current_text_scale = float(raw_scale)

            # Haut contraste
            raw_hc = _gsettings_get(
                "org.gnome.desktop.interface", "gtk-theme",
            )
            self.high_contrast_active = "HighContrast" in (raw_hc or "")

            # Clavier virtuel
            raw_kb = _gsettings_get(
                "org.gnome.desktop.a11y.applications",
                "screen-keyboard-enabled",
            )
            self.screen_keyboard_active = raw_kb == "true"
        except Exception:  # noqa: BLE001
            logger.debug("Impossible de synchroniser l'etat systeme a11y")

    # ───────────────────────────────────────────────────────────────────────
    # API publique principale
    # ───────────────────────────────────────────────────────────────────────

    def execute_accessibility_command(self, text: str) -> dict[str, Any]:
        """Execute une commande d'accessibilite a partir du texte vocal.

        Args:
            text: Texte brut issu de la reconnaissance vocale.

        Returns:
            Dictionnaire avec 'success', 'action', 'message' et details optionnels.
        """
        normalized = self._normalize(text)

        # Recherche exacte
        if normalized in self._command_map:
            return self._command_map[normalized]()

        # Recherche par inclusion (tolerant aux prefixes/suffixes)
        for pattern, handler in self._command_map.items():
            if pattern in normalized or normalized in pattern:
                return handler()

        # Gestion de la dictee active : tout texte est tape
        if self.dictation_active:
            return self._dictation_type(text)

        return {
            "success": False,
            "action": "unknown",
            "message": f"Commande d'accessibilite non reconnue : {text}",
        }

    def get_accessibility_status(self) -> dict[str, Any]:
        """Retourne l'etat complet de toutes les fonctions d'accessibilite.

        Returns:
            Dictionnaire avec l'etat de chaque module a11y.
        """
        self._sync_system_state()
        return {
            "screen_reader_active": self.screen_reader_active,
            "dictation_active": self.dictation_active,
            "high_contrast_active": self.high_contrast_active,
            "screen_keyboard_active": self.screen_keyboard_active,
            "current_zoom": self.current_zoom,
            "current_text_scale": self.current_text_scale,
            "available_tools": {
                "xdotool": _has_tool("xdotool"),
                "xclip": _has_tool("xclip"),
                "tesseract": _has_tool("tesseract"),
                "orca": _has_tool("orca"),
                "scrot": _has_tool("scrot"),
                "piper": _has_tool("piper"),
                "gsettings": _has_tool("gsettings"),
            },
            "registered_commands": sorted(self._command_map.keys()),
        }

    def toggle_screen_reader(self, enabled: bool) -> None:
        """Active ou desactive le lecteur d'ecran orca.

        Args:
            enabled: True pour activer, False pour desactiver.
        """
        if enabled and not self.screen_reader_active:
            _run_detached(["orca"])
            self.screen_reader_active = True
            logger.info("Lecteur d'ecran orca active")
        elif not enabled and self.screen_reader_active:
            _run(["pkill", "-f", "orca"])
            self.screen_reader_active = False
            logger.info("Lecteur d'ecran orca desactive")

    def set_zoom_level(self, factor: float) -> None:
        """Regle le niveau de zoom de la loupe GNOME.

        Args:
            factor: Facteur de zoom (1.0 = normal, >1.0 = agrandi).
        """
        clamped = max(MIN_ZOOM, min(MAX_ZOOM, factor))
        _gsettings_set(
            "org.gnome.desktop.a11y.magnifier", "mag-factor", str(clamped),
        )
        # Active la loupe si zoom > 1
        if clamped > 1.0:
            _gsettings_set(
                "org.gnome.desktop.a11y.applications",
                "screen-magnifier-enabled", "true",
            )
        else:
            _gsettings_set(
                "org.gnome.desktop.a11y.applications",
                "screen-magnifier-enabled", "false",
            )
        self.current_zoom = clamped
        logger.info("Zoom regle a %.1f", clamped)

    def set_text_scaling(self, factor: float) -> None:
        """Regle le facteur d'echelle du texte systeme.

        Args:
            factor: Facteur d'echelle (1.0 = normal).
        """
        clamped = max(MIN_TEXT_SCALE, min(MAX_TEXT_SCALE, factor))
        _gsettings_set(
            "org.gnome.desktop.interface",
            "text-scaling-factor", str(clamped),
        )
        self.current_text_scale = clamped
        logger.info("Echelle du texte reglee a %.1f", clamped)

    def toggle_high_contrast(self, enabled: bool) -> None:
        """Active ou desactive le mode haut contraste.

        Args:
            enabled: True pour haut contraste, False pour normal.
        """
        if enabled:
            _gsettings_set(
                "org.gnome.desktop.interface", "gtk-theme", "'HighContrast'",
            )
            _gsettings_set(
                "org.gnome.desktop.interface",
                "icon-theme", "'HighContrast'",
            )
            self.high_contrast_active = True
            logger.info("Mode haut contraste active")
        else:
            _gsettings_set(
                "org.gnome.desktop.interface", "gtk-theme", "'Adwaita'",
            )
            _gsettings_set(
                "org.gnome.desktop.interface", "icon-theme", "'Adwaita'",
            )
            self.high_contrast_active = False
            logger.info("Mode haut contraste desactive")

    # ───────────────────────────────────────────────────────────────────────
    # Lecteur d'ecran
    # ───────────────────────────────────────────────────────────────────────

    def _read_active_window(self) -> dict[str, Any]:
        """Lit le nom de la fenetre active et lance orca pour la decrire."""
        window_id = _run(["xdotool", "getactivewindow"])
        if not window_id:
            return {"success": False, "action": "read_window", "message": "Aucune fenetre active detectee"}

        window_name = _run(["xdotool", "getactivewindow", "getwindowname"])
        # Lancer orca pour lire le contenu
        self.toggle_screen_reader(enabled=True)
        self._speak(f"Fenetre active : {window_name}")
        return {
            "success": True,
            "action": "read_window",
            "message": f"Fenetre active : {window_name}",
            "window_id": window_id,
            "window_name": window_name,
        }

    def _describe_screen(self) -> dict[str, Any]:
        """Capture l'ecran, effectue un OCR et resume via IA."""
        screenshot_path = SCREENSHOT_DIR / f"a11y_{int(time.time())}.png"

        # Capture d'ecran
        capture_ok = _run(["scrot", str(screenshot_path)])
        if not screenshot_path.exists():
            return {"success": False, "action": "describe_screen", "message": "Capture d'ecran impossible"}

        # OCR avec tesseract
        ocr_text = _run(
            ["tesseract", str(screenshot_path), "stdout", "-l", "fra+eng"],
            timeout=VISION_TIMEOUT,
        )

        # Resume IA si du texte a ete extrait
        summary = ocr_text[:500] if ocr_text else "Aucun texte detecte a l'ecran"

        if ocr_text:
            ai_summary = self._ask_ai_summary(ocr_text)
            if ai_summary:
                summary = ai_summary

        self._speak(summary)

        # Nettoyage
        try:
            screenshot_path.unlink(missing_ok=True)
        except OSError:
            pass

        return {
            "success": True,
            "action": "describe_screen",
            "message": summary,
            "ocr_length": len(ocr_text),
        }

    def _read_selection(self) -> dict[str, Any]:
        """Lit le texte actuellement selectionne via xclip + piper TTS."""
        selected = _run(["xclip", "-selection", "primary", "-o"])
        if not selected:
            selected = _run(["xclip", "-selection", "clipboard", "-o"])

        if not selected:
            return {"success": False, "action": "read_selection", "message": "Aucun texte selectionne"}

        self._speak(selected)
        return {
            "success": True,
            "action": "read_selection",
            "message": f"Texte lu : {selected[:100]}...",
            "text": selected,
        }

    # ───────────────────────────────────────────────────────────────────────
    # Loupe et zoom
    # ───────────────────────────────────────────────────────────────────────

    def _zoom_in(self) -> dict[str, Any]:
        """Augmente le zoom de la loupe GNOME."""
        new_zoom = self.current_zoom + DEFAULT_ZOOM_STEP
        self.set_zoom_level(new_zoom)
        return {
            "success": True,
            "action": "zoom_in",
            "message": f"Zoom augmente a {self.current_zoom:.1f}x",
            "zoom": self.current_zoom,
        }

    def _zoom_out(self) -> dict[str, Any]:
        """Diminue le zoom de la loupe GNOME."""
        new_zoom = self.current_zoom - DEFAULT_ZOOM_STEP
        self.set_zoom_level(new_zoom)
        return {
            "success": True,
            "action": "zoom_out",
            "message": f"Zoom reduit a {self.current_zoom:.1f}x",
            "zoom": self.current_zoom,
        }

    def _text_scale_up(self) -> dict[str, Any]:
        """Augmente la taille du texte systeme."""
        new_scale = self.current_text_scale + DEFAULT_TEXT_SCALE_STEP
        self.set_text_scaling(new_scale)
        return {
            "success": True,
            "action": "text_scale_up",
            "message": f"Taille du texte augmentee a {self.current_text_scale:.1f}x",
            "scale": self.current_text_scale,
        }

    def _text_scale_reset(self) -> dict[str, Any]:
        """Remet la taille du texte a 1.0."""
        self.set_text_scaling(DEFAULT_TEXT_SCALE)
        return {
            "success": True,
            "action": "text_scale_reset",
            "message": "Taille du texte remise a 1.0",
            "scale": self.current_text_scale,
        }

    # ───────────────────────────────────────────────────────────────────────
    # Haut contraste
    # ───────────────────────────────────────────────────────────────────────

    def _high_contrast_on(self) -> dict[str, Any]:
        """Active le mode haut contraste."""
        self.toggle_high_contrast(enabled=True)
        return {
            "success": True,
            "action": "high_contrast_on",
            "message": "Mode haut contraste active",
        }

    def _high_contrast_off(self) -> dict[str, Any]:
        """Desactive le mode haut contraste."""
        self.toggle_high_contrast(enabled=False)
        return {
            "success": True,
            "action": "high_contrast_off",
            "message": "Mode haut contraste desactive",
        }

    def _invert_colors(self) -> dict[str, Any]:
        """Inverse les couleurs de l'ecran via xrandr ou gsettings."""
        # Tenter l'inversion via xrandr (compatible X11)
        output = _run(["xrandr", "--query"])
        # Trouver l'ecran actif
        screen_name = ""
        for line in output.splitlines():
            if " connected" in line:
                screen_name = line.split()[0]
                break

        if screen_name:
            _run(["xrandr", "--output", screen_name, "--brightness", "1.0"])
            # Utiliser xcalib pour inversion
            if _has_tool("xcalib"):
                _run(["xcalib", "-invert", "-alter"])
                return {
                    "success": True,
                    "action": "invert_colors",
                    "message": f"Couleurs inversees sur {screen_name}",
                }

        return {
            "success": False,
            "action": "invert_colors",
            "message": "Inversion des couleurs non supportee (installer xcalib)",
        }

    # ───────────────────────────────────────────────────────────────────────
    # Clavier visuel
    # ───────────────────────────────────────────────────────────────────────

    def _screen_keyboard_on(self) -> dict[str, Any]:
        """Active le clavier virtuel GNOME."""
        _gsettings_set(
            "org.gnome.desktop.a11y.applications",
            "screen-keyboard-enabled", "true",
        )
        self.screen_keyboard_active = True
        return {
            "success": True,
            "action": "screen_keyboard_on",
            "message": "Clavier a l'ecran active",
        }

    def _screen_keyboard_off(self) -> dict[str, Any]:
        """Desactive le clavier virtuel GNOME."""
        _gsettings_set(
            "org.gnome.desktop.a11y.applications",
            "screen-keyboard-enabled", "false",
        )
        self.screen_keyboard_active = False
        return {
            "success": True,
            "action": "screen_keyboard_off",
            "message": "Clavier a l'ecran desactive",
        }

    # ───────────────────────────────────────────────────────────────────────
    # Dictee amelioree
    # ───────────────────────────────────────────────────────────────────────

    def _dictation_start(self) -> dict[str, Any]:
        """Active le mode dictee continue."""
        self.dictation_active = True
        self.dictation_buffer.clear()
        return {
            "success": True,
            "action": "dictation_start",
            "message": "Mode dictee active — parlez, je tape",
        }

    def _dictation_stop(self) -> dict[str, Any]:
        """Desactive le mode dictee."""
        self.dictation_active = False
        total_words = len(self.dictation_buffer)
        return {
            "success": True,
            "action": "dictation_stop",
            "message": f"Dictee arretee ({total_words} mots tapes)",
            "words_typed": total_words,
        }

    def _dictation_correct_last(self) -> dict[str, Any]:
        """Corrige le dernier mot tape : supprime et attend le remplacement."""
        if not self.dictation_buffer:
            return {"success": False, "action": "dictation_correct", "message": "Rien a corriger"}

        last_word = self.dictation_buffer.pop()
        # Effacer le dernier mot : backspace par caractere + espace
        for _ in range(len(last_word) + 1):
            _run(["xdotool", "key", "BackSpace"])

        return {
            "success": True,
            "action": "dictation_correct",
            "message": f"Mot '{last_word}' efface — dites le remplacement",
            "removed": last_word,
        }

    def _dictation_newline(self) -> dict[str, Any]:
        """Insere un retour a la ligne."""
        _run(["xdotool", "key", "Return"])
        return {
            "success": True,
            "action": "dictation_newline",
            "message": "Nouvelle ligne inseree",
        }

    def _dictation_period(self) -> dict[str, Any]:
        """Insere un point."""
        _run(["xdotool", "type", "--clearmodifiers", "."])
        self.dictation_buffer.append(".")
        return {
            "success": True,
            "action": "dictation_period",
            "message": "Point insere",
        }

    def _dictation_type(self, text: str) -> dict[str, Any]:
        """Tape le texte dicte dans la fenetre active.

        Gere les mots-cles de ponctuation (ex: 'point' -> '.').
        """
        # Remplacer les mots-cles par la ponctuation correspondante
        output_text = text
        for keyword, char in DICTATION_PUNCTUATION.items():
            output_text = re.sub(
                rf"\b{re.escape(keyword)}\b", char, output_text, flags=re.IGNORECASE,
            )

        # Taper le texte via xdotool
        _run(["xdotool", "type", "--clearmodifiers", "--delay", "20", output_text])
        self.dictation_buffer.extend(output_text.split())

        return {
            "success": True,
            "action": "dictation_type",
            "message": f"Tape : {output_text}",
            "typed": output_text,
        }

    # ───────────────────────────────────────────────────────────────────────
    # Navigation clavier
    # ───────────────────────────────────────────────────────────────────────

    def _send_key(self, key: str) -> dict[str, Any]:
        """Envoie une touche via xdotool.

        Args:
            key: Nom de la touche xdotool (ex: 'Tab', 'Return', 'alt+Tab').
        """
        _run(["xdotool", "key", "--clearmodifiers", key])
        return {
            "success": True,
            "action": "send_key",
            "message": f"Touche envoyee : {key}",
            "key": key,
        }

    # ───────────────────────────────────────────────────────────────────────
    # Utilitaires internes
    # ───────────────────────────────────────────────────────────────────────

    @staticmethod
    def _normalize(text: str) -> str:
        """Normalise le texte vocal : minuscules, sans accents problematiques."""
        return (
            text.lower()
            .strip()
            .replace("è", "e")
            .replace("é", "e")
            .replace("ê", "e")
            .replace("à", "a")
            .replace("ô", "o")
            .replace("î", "i")
            .replace("û", "u")
            .replace("ù", "u")
            .replace("ç", "c")
        )

    @staticmethod
    def _speak(text: str) -> None:
        """Synthetise et lit le texte via piper TTS ou espeak en fallback."""
        if _has_tool("piper"):
            try:
                subprocess.run(
                    ["piper", "--model", "fr_FR-siwis-medium", "--output-raw"],
                    input=text,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                return
            except (subprocess.TimeoutExpired, OSError):
                pass

        # Fallback : espeak
        if _has_tool("espeak-ng"):
            _run(["espeak-ng", "-v", "fr", text])
        elif _has_tool("espeak"):
            _run(["espeak", "-v", "fr", text])
        else:
            logger.warning("Aucun moteur TTS disponible (piper, espeak-ng, espeak)")

    @staticmethod
    def _ask_ai_summary(ocr_text: str) -> str | None:
        """Demande un resume du texte OCR via LM Studio."""
        try:
            import urllib.request

            payload = json.dumps({
                "model": "qwen3-8b",
                "messages": [
                    {
                        "role": "system",
                        "content": "Tu es un assistant d'accessibilite. Resume brievement ce qui est affiche a l'ecran.",
                    },
                    {
                        "role": "user",
                        "content": f"Voici le texte OCR de l'ecran :\n{ocr_text[:2000]}",
                    },
                ],
                "max_tokens": 200,
                "temperature": 0.3,
            }).encode()

            req = urllib.request.Request(
                LMSTUDIO_URL,
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=VISION_TIMEOUT) as resp:
                data = json.loads(resp.read())
                return data["choices"][0]["message"]["content"]
        except Exception:  # noqa: BLE001
            logger.debug("Resume IA indisponible, utilisation du texte OCR brut")
            return None


# ═══════════════════════════════════════════════════════════════════════════════
# Liste des commandes vocales exportees pour integration dans jarvis.db
# ═══════════════════════════════════════════════════════════════════════════════

ACCESSIBILITY_VOICE_COMMANDS: list[dict[str, Any]] = [
    # Lecteur d'ecran
    {
        "name": "a11y_read_window",
        "category": "accessibility",
        "description": "Lit le nom de la fenetre active avec orca",
        "triggers": json.dumps(["lis cette fenetre", "lis la fenetre", "quelle fenetre"]),
        "action_type": "a11y",
        "action": "read_active_window",
    },
    {
        "name": "a11y_describe_screen",
        "category": "accessibility",
        "description": "Capture l'ecran, OCR et resume IA",
        "triggers": json.dumps(["decris l'ecran", "qu'est-ce qui est affiche", "decris l'ecran"]),
        "action_type": "a11y",
        "action": "describe_screen",
    },
    {
        "name": "a11y_read_selection",
        "category": "accessibility",
        "description": "Lit le texte selectionne via TTS",
        "triggers": json.dumps(["lis le texte selectionne", "lis la selection", "lis ce texte"]),
        "action_type": "a11y",
        "action": "read_selection",
    },
    # Loupe et zoom
    {
        "name": "a11y_zoom_in",
        "category": "accessibility",
        "description": "Augmente le zoom de la loupe",
        "triggers": json.dumps(["zoom avant", "agrandir", "plus gros"]),
        "action_type": "a11y",
        "action": "zoom_in",
    },
    {
        "name": "a11y_zoom_out",
        "category": "accessibility",
        "description": "Diminue le zoom de la loupe",
        "triggers": json.dumps(["zoom arriere", "reduire", "plus petit"]),
        "action_type": "a11y",
        "action": "zoom_out",
    },
    {
        "name": "a11y_text_bigger",
        "category": "accessibility",
        "description": "Augmente la taille du texte systeme",
        "triggers": json.dumps(["taille du texte plus grande", "texte plus grand", "agrandir le texte"]),
        "action_type": "a11y",
        "action": "text_scale_up",
    },
    {
        "name": "a11y_text_normal",
        "category": "accessibility",
        "description": "Remet la taille du texte a la normale",
        "triggers": json.dumps(["taille du texte normale", "texte normal", "taille normale"]),
        "action_type": "a11y",
        "action": "text_scale_reset",
    },
    # Haut contraste
    {
        "name": "a11y_high_contrast_on",
        "category": "accessibility",
        "description": "Active le mode haut contraste",
        "triggers": json.dumps(["contraste eleve", "haut contraste", "mode contraste"]),
        "action_type": "a11y",
        "action": "high_contrast_on",
    },
    {
        "name": "a11y_high_contrast_off",
        "category": "accessibility",
        "description": "Desactive le mode haut contraste",
        "triggers": json.dumps(["contraste normal", "desactive le contraste", "contraste standard"]),
        "action_type": "a11y",
        "action": "high_contrast_off",
    },
    {
        "name": "a11y_invert_colors",
        "category": "accessibility",
        "description": "Inverse les couleurs de l'ecran",
        "triggers": json.dumps(["inverse les couleurs", "inverser couleurs", "negatif"]),
        "action_type": "a11y",
        "action": "invert_colors",
    },
    # Clavier visuel
    {
        "name": "a11y_screen_keyboard_on",
        "category": "accessibility",
        "description": "Affiche le clavier virtuel a l'ecran",
        "triggers": json.dumps(["clavier a l'ecran", "affiche le clavier", "clavier virtuel"]),
        "action_type": "a11y",
        "action": "screen_keyboard_on",
    },
    {
        "name": "a11y_screen_keyboard_off",
        "category": "accessibility",
        "description": "Ferme le clavier virtuel",
        "triggers": json.dumps(["ferme le clavier", "cache le clavier", "desactive le clavier"]),
        "action_type": "a11y",
        "action": "screen_keyboard_off",
    },
    # Dictee amelioree
    {
        "name": "a11y_dictation_start",
        "category": "accessibility",
        "description": "Active le mode dictee continue",
        "triggers": json.dumps(["mode dictee", "active la dictee", "commence la dictee"]),
        "action_type": "a11y",
        "action": "dictation_start",
    },
    {
        "name": "a11y_dictation_stop",
        "category": "accessibility",
        "description": "Arrete le mode dictee",
        "triggers": json.dumps(["arrete la dictee", "stop dictee", "fin de dictee"]),
        "action_type": "a11y",
        "action": "dictation_stop",
    },
    {
        "name": "a11y_dictation_correct",
        "category": "accessibility",
        "description": "Corrige le dernier mot dicte",
        "triggers": json.dumps(["corrige le dernier mot", "correction", "efface le dernier mot"]),
        "action_type": "a11y",
        "action": "dictation_correct_last",
    },
    {
        "name": "a11y_dictation_newline",
        "category": "accessibility",
        "description": "Insere un retour a la ligne en dictee",
        "triggers": json.dumps(["nouvelle ligne", "retour a la ligne", "a la ligne"]),
        "action_type": "a11y",
        "action": "dictation_newline",
    },
    # Navigation clavier
    {
        "name": "a11y_nav_tab",
        "category": "accessibility",
        "description": "Envoie la touche Tab",
        "triggers": json.dumps(["tab suivant", "tabulation", "prochain champ"]),
        "action_type": "a11y",
        "action": "send_key:Tab",
    },
    {
        "name": "a11y_nav_enter",
        "category": "accessibility",
        "description": "Envoie la touche Entree",
        "triggers": json.dumps(["entre", "entree", "valider"]),
        "action_type": "a11y",
        "action": "send_key:Return",
    },
    {
        "name": "a11y_nav_escape",
        "category": "accessibility",
        "description": "Envoie la touche Echap",
        "triggers": json.dumps(["echappe", "echap", "annuler"]),
        "action_type": "a11y",
        "action": "send_key:Escape",
    },
    {
        "name": "a11y_nav_alt_tab",
        "category": "accessibility",
        "description": "Bascule entre les fenetres (Alt+Tab)",
        "triggers": json.dumps(["alt tab", "change de fenetre", "fenetre suivante"]),
        "action_type": "a11y",
        "action": "send_key:alt+Tab",
    },
]


def install_voice_commands(db_path: str = "/home/turbo/jarvis/data/jarvis.db") -> int:
    """Insere les commandes d'accessibilite dans la table voice_commands.

    Args:
        db_path: Chemin vers la base jarvis.db.

    Returns:
        Nombre de commandes inserees.
    """
    import sqlite3

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    inserted = 0

    for cmd in ACCESSIBILITY_VOICE_COMMANDS:
        try:
            cursor.execute(
                """
                INSERT OR REPLACE INTO voice_commands
                    (name, category, description, triggers, action_type, action, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cmd["name"],
                    cmd["category"],
                    cmd["description"],
                    cmd["triggers"],
                    cmd["action_type"],
                    cmd["action"],
                    time.time(),
                ),
            )
            inserted += 1
        except sqlite3.Error as exc:
            logger.warning("Erreur insertion commande %s : %s", cmd["name"], exc)

    conn.commit()
    conn.close()
    logger.info("Commandes d'accessibilite installees : %d/%d", inserted, len(ACCESSIBILITY_VOICE_COMMANDS))
    return inserted


# ═══════════════════════════════════════════════════════════════════════════════
# Point d'entree pour installation directe
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    count = install_voice_commands()
    print(f"[OK] {count} commandes d'accessibilite inserees dans jarvis.db")

    # Test rapide du statut
    manager = VoiceAccessibilityManager()
    status = manager.get_accessibility_status()
    print(f"[INFO] Outils disponibles : {status['available_tools']}")
    print(f"[INFO] Commandes enregistrees : {len(status['registered_commands'])}")
