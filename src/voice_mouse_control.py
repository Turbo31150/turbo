#!/usr/bin/env python3
"""voice_mouse_control.py -- Controle complet de la souris par la voix.

Module de controle vocal de la souris pour Linux (GNOME + X11).
Utilise xdotool pour toutes les operations souris.
Concu pour les utilisateurs sans souris physique.

Auteur: JARVIS
Date: 2026-03-14
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from typing import Any, Callable


class VoiceMouseControl:
    """Controleur de souris par commandes vocales via xdotool."""

    # Mapping directions francaises -> xdotool/coordonnees
    DIRECTIONS = {
        "haut": (0, -1),
        "bas": (0, 1),
        "gauche": (-1, 0),
        "droite": (1, 0),
    }

    # Mapping boutons
    BUTTONS = {
        "left": 1,
        "gauche": 1,
        "right": 3,
        "droit": 3,
        "middle": 2,
        "milieu": 2,
    }

    # Coins de l'ecran
    CORNERS = {
        "haut gauche": (0, 0),
        "haut droite": (1, 0),
        "bas gauche": (0, 1),
        "bas droite": (1, 1),
        "top-left": (0, 0),
        "top-right": (1, 0),
        "bottom-left": (0, 1),
        "bottom-right": (1, 1),
    }

    def __init__(self) -> None:
        """Initialise le controleur de souris vocal."""
        self._screen_w: int | None = None
        self._screen_h: int | None = None
        self._holding: bool = False

    # ------------------------------------------------------------------ #
    #  Utilitaires internes                                               #
    # ------------------------------------------------------------------ #

    def _run(self, *args: str, capture: bool = False) -> subprocess.CompletedProcess:
        """Execute une commande xdotool."""
        cmd = ["xdotool", *args]
        try:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except FileNotFoundError:
            raise RuntimeError("xdotool n'est pas installe. Installez-le : sudo apt install xdotool")
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Commande xdotool expiree : {' '.join(cmd)}")

    def _get_screen_size(self) -> tuple[int, int]:
        """Recupere la taille de l'ecran via xdotool."""
        if self._screen_w is not None and self._screen_h is not None:
            return self._screen_w, self._screen_h
        result = self._run("getdisplaygeometry")
        if result.returncode != 0:
            raise RuntimeError(f"Impossible d'obtenir la taille de l'ecran: {result.stderr.strip()}")
        parts = result.stdout.strip().split()
        self._screen_w, self._screen_h = int(parts[0]), int(parts[1])
        return self._screen_w, self._screen_h

    def _clamp_position(self, x: int, y: int) -> tuple[int, int]:
        """Limite les coordonnees aux bornes de l'ecran."""
        w, h = self._get_screen_size()
        return max(0, min(x, w - 1)), max(0, min(y, h - 1))

    # ------------------------------------------------------------------ #
    #  Methodes publiques de controle souris                              #
    # ------------------------------------------------------------------ #

    def mouse_move_to(self, x: int, y: int) -> str:
        """Deplace le curseur a une position absolue (x, y)."""
        x, y = self._clamp_position(int(x), int(y))
        result = self._run("mousemove", str(x), str(y))
        if result.returncode != 0:
            return f"Erreur: impossible de deplacer le curseur vers ({x}, {y})"
        return f"Curseur deplace en ({x}, {y})"

    def mouse_move_relative(self, direction: str, pixels: int = 50) -> str:
        """Deplace le curseur dans une direction relative (haut/bas/gauche/droite) de N pixels."""
        direction = direction.lower().strip()
        if direction not in self.DIRECTIONS:
            return f"Erreur: direction inconnue '{direction}'. Utilisez: haut, bas, gauche, droite"
        dx, dy = self.DIRECTIONS[direction]
        dx *= int(pixels)
        dy *= int(pixels)
        result = self._run("mousemove_relative", "--", str(dx), str(dy))
        if result.returncode != 0:
            return f"Erreur: deplacement relatif echoue"
        return f"Curseur deplace de {pixels} pixels vers {direction}"

    def mouse_click(self, button: str = "left") -> str:
        """Effectue un clic souris (gauche/droit/milieu)."""
        button = button.lower().strip()
        btn_num = self.BUTTONS.get(button, 1)
        result = self._run("click", str(btn_num))
        if result.returncode != 0:
            return f"Erreur: clic echoue"
        names = {1: "gauche", 2: "milieu", 3: "droit"}
        return f"Clic {names.get(btn_num, 'gauche')} effectue"

    def mouse_double_click(self) -> str:
        """Effectue un double clic gauche."""
        result = self._run("click", "--repeat", "2", "--delay", "50", "1")
        if result.returncode != 0:
            return "Erreur: double clic echoue"
        return "Double clic effectue"

    def mouse_right_click(self) -> str:
        """Effectue un clic droit."""
        result = self._run("click", "3")
        if result.returncode != 0:
            return "Erreur: clic droit echoue"
        return "Clic droit effectue"

    def mouse_triple_click(self) -> str:
        """Effectue un triple clic (selection de ligne)."""
        result = self._run("click", "--repeat", "3", "--delay", "50", "1")
        if result.returncode != 0:
            return "Erreur: triple clic echoue"
        return "Triple clic effectue (ligne selectionnee)"

    def mouse_drag_to(self, x: int, y: int) -> str:
        """Glisse (drag) depuis la position actuelle vers (x, y)."""
        x, y = self._clamp_position(int(x), int(y))
        # Get current position first
        pos = self._run("getmouselocation")
        if pos.returncode != 0:
            return "Erreur: impossible de lire la position actuelle"
        # mousedown, move, mouseup
        self._run("mousedown", "1")
        self._run("mousemove", "--delay", "100", str(x), str(y))
        self._run("mouseup", "1")
        return f"Glissement effectue vers ({x}, {y})"

    def mouse_scroll_up(self, amount: int = 3) -> str:
        """Fait defiler vers le haut de N clics de molette."""
        amount = int(amount)
        result = self._run("click", "--repeat", str(amount), "--delay", "30", "4")
        if result.returncode != 0:
            return "Erreur: scroll haut echoue"
        return f"Defilement vers le haut ({amount} clics)"

    def mouse_scroll_down(self, amount: int = 3) -> str:
        """Fait defiler vers le bas de N clics de molette."""
        amount = int(amount)
        result = self._run("click", "--repeat", str(amount), "--delay", "30", "5")
        if result.returncode != 0:
            return "Erreur: scroll bas echoue"
        return f"Defilement vers le bas ({amount} clics)"

    def mouse_get_position(self) -> str:
        """Retourne la position actuelle du curseur."""
        result = self._run("getmouselocation")
        if result.returncode != 0:
            return "Erreur: impossible de lire la position du curseur"
        # Output: x:123 y:456 screen:0 window:789
        output = result.stdout.strip()
        match_x = re.search(r"x:(\d+)", output)
        match_y = re.search(r"y:(\d+)", output)
        if match_x and match_y:
            x, y = match_x.group(1), match_y.group(1)
            return f"Position du curseur : x={x}, y={y}"
        return f"Position brute : {output}"

    def mouse_click_at(self, x: int, y: int) -> str:
        """Deplace le curseur en (x, y) puis effectue un clic gauche."""
        x, y = self._clamp_position(int(x), int(y))
        result = self._run("mousemove", str(x), str(y))
        if result.returncode != 0:
            return f"Erreur: deplacement vers ({x}, {y}) echoue"
        result = self._run("click", "1")
        if result.returncode != 0:
            return f"Erreur: clic en ({x}, {y}) echoue"
        return f"Clic effectue en ({x}, {y})"

    def mouse_center(self) -> str:
        """Deplace le curseur au centre de l'ecran."""
        w, h = self._get_screen_size()
        cx, cy = w // 2, h // 2
        result = self._run("mousemove", str(cx), str(cy))
        if result.returncode != 0:
            return "Erreur: deplacement au centre echoue"
        return f"Curseur place au centre de l'ecran ({cx}, {cy})"

    def mouse_move_to_corner(self, corner: str) -> str:
        """Deplace le curseur dans un coin de l'ecran (haut gauche, haut droite, bas gauche, bas droite)."""
        corner = corner.lower().strip()
        if corner not in self.CORNERS:
            available = ", ".join(k for k in self.CORNERS if " " in k and not "-" in k)
            return f"Erreur: coin inconnu '{corner}'. Coins valides : {available}"
        fx, fy = self.CORNERS[corner]
        w, h = self._get_screen_size()
        # Petite marge pour eviter de declencher les hot corners
        margin = 5
        x = margin if fx == 0 else w - margin
        y = margin if fy == 0 else h - margin
        result = self._run("mousemove", str(x), str(y))
        if result.returncode != 0:
            return f"Erreur: deplacement au coin {corner} echoue"
        return f"Curseur deplace au coin {corner} ({x}, {y})"

    def mouse_grid_click(self, row: int, col: int) -> str:
        """Divise l'ecran en grille 3x3 et clique au centre de la cellule (row, col).

        La numerotation suit le pave numerique :
        7=haut-gauche, 8=haut-centre, 9=haut-droite
        4=milieu-gauche, 5=centre, 6=milieu-droite
        1=bas-gauche, 2=bas-centre, 3=bas-droite
        """
        row, col = int(row), int(col)
        if not (1 <= row <= 3 and 1 <= col <= 3):
            return "Erreur: ligne et colonne doivent etre entre 1 et 3"
        w, h = self._get_screen_size()
        cell_w = w // 3
        cell_h = h // 3
        x = cell_w * (col - 1) + cell_w // 2
        y = cell_h * (row - 1) + cell_h // 2
        self._run("mousemove", str(x), str(y))
        result = self._run("click", "1")
        if result.returncode != 0:
            return f"Erreur: clic grille ({row}, {col}) echoue"
        return f"Clic en grille ({row}, {col}) -> position ({x}, {y})"

    def mouse_grid_numpad(self, cell: int) -> str:
        """Clique dans la cellule de la grille 3x3 identifiee par un numero de pave numerique (1-9)."""
        cell = int(cell)
        if not (1 <= cell <= 9):
            return "Erreur: le numero de cellule doit etre entre 1 et 9"
        # Mapping pave numerique -> (row, col)  row 1=haut, row 3=bas
        numpad_map = {
            7: (1, 1), 8: (1, 2), 9: (1, 3),
            4: (2, 1), 5: (2, 2), 6: (2, 3),
            1: (3, 1), 2: (3, 2), 3: (3, 3),
        }
        row, col = numpad_map[cell]
        return self.mouse_grid_click(row, col)

    def mouse_hold(self) -> str:
        """Maintient le bouton gauche enfonce (debut de glissement)."""
        result = self._run("mousedown", "1")
        if result.returncode != 0:
            return "Erreur: impossible de maintenir le clic"
        self._holding = True
        return "Bouton gauche maintenu enfonce"

    def mouse_release(self) -> str:
        """Relache le bouton gauche (fin de glissement)."""
        result = self._run("mouseup", "1")
        if result.returncode != 0:
            return "Erreur: impossible de relacher le clic"
        self._holding = False
        return "Bouton gauche relache"

    def mouse_slow_move(self, direction: str, pixels: int = 10) -> str:
        """Deplacement fin du curseur (precision) dans une direction de N pixels."""
        return self.mouse_move_relative(direction, int(pixels))

    def mouse_scroll_left(self, clicks: int = 3) -> str:
        """Defilement horizontal vers la gauche."""
        result = self._run("click", "--repeat", str(clicks), "6")
        return f"Defilement gauche ({clicks}x)"

    def mouse_scroll_right(self, clicks: int = 3) -> str:
        """Defilement horizontal vers la droite."""
        result = self._run("click", "--repeat", str(clicks), "7")
        return f"Defilement droite ({clicks}x)"

    def mouse_move_to_taskbar(self) -> str:
        """Deplace le curseur vers la barre des taches (bas ecran)."""
        w, h = self._get_screen_size()
        result = self._run("mousemove", str(w // 2), str(h - 5))
        return f"Curseur sur la barre des taches ({w // 2}, {h - 5})"

    def mouse_move_to_menu_bar(self) -> str:
        """Deplace le curseur vers la barre de menu (haut ecran)."""
        w, h = self._get_screen_size()
        result = self._run("mousemove", str(w // 2), str(25))
        return f"Curseur sur la barre de menu ({w // 2}, 25)"

    def mouse_click_middle(self) -> str:
        """Clic milieu (bouton molette)."""
        result = self._run("click", "2")
        return "Clic milieu"

    def mouse_drag_drop(self, x_from: int, y_from: int, x_to: int, y_to: int) -> str:
        """Glisser-deposer entre deux positions."""
        self._run("mousemove", str(x_from), str(y_from))
        import time
        time.sleep(0.1)
        self._run("mousedown", "1")
        time.sleep(0.1)
        self._run("mousemove", "--sync", str(x_to), str(y_to))
        time.sleep(0.1)
        self._run("mouseup", "1")
        return f"Glisser-deposer de ({x_from},{y_from}) vers ({x_to},{y_to})"

    def mouse_shake(self) -> str:
        """Secouer la souris (trouver le curseur visuellement)."""
        import time
        x, y = self.mouse_get_position().split("(")[1].rstrip(")").split(",")
        x, y = int(x.strip()), int(y.strip())
        for _ in range(3):
            self._run("mousemove", str(x + 50), str(y))
            time.sleep(0.05)
            self._run("mousemove", str(x - 50), str(y))
            time.sleep(0.05)
        self._run("mousemove", str(x), str(y))
        return "Souris secouee (curseur localise)"

    def mouse_circle(self) -> str:
        """Faire un mouvement circulaire pour localiser le curseur."""
        import math, time
        pos = self.mouse_get_position()
        match = re.search(r"\((\d+),\s*(\d+)\)", pos)
        if not match:
            return "Position inconnue"
        cx, cy = int(match.group(1)), int(match.group(2))
        radius = 40
        for angle in range(0, 360, 30):
            x = int(cx + radius * math.cos(math.radians(angle)))
            y = int(cy + radius * math.sin(math.radians(angle)))
            self._run("mousemove", str(x), str(y))
            time.sleep(0.02)
        self._run("mousemove", str(cx), str(cy))
        return "Cercle effectue (curseur localise)"


# ====================================================================== #
#  Dictionnaire de commandes vocales                                      #
# ====================================================================== #

_ctrl = VoiceMouseControl()

# Commandes vocales directes (phrase -> callable sans argument)
VOICE_COMMANDS: dict[str, Callable[[], str]] = {
    # Clics
    "clic": _ctrl.mouse_click,
    "clique": _ctrl.mouse_click,
    "clic gauche": _ctrl.mouse_click,
    "clic droit": _ctrl.mouse_right_click,
    "double clic": _ctrl.mouse_double_click,
    "triple clic": _ctrl.mouse_triple_click,
    # Mouvements relatifs
    "curseur en haut": lambda: _ctrl.mouse_move_relative("haut"),
    "curseur en bas": lambda: _ctrl.mouse_move_relative("bas"),
    "curseur a gauche": lambda: _ctrl.mouse_move_relative("gauche"),
    "curseur a droite": lambda: _ctrl.mouse_move_relative("droite"),
    "monte": lambda: _ctrl.mouse_move_relative("haut"),
    "descends": lambda: _ctrl.mouse_move_relative("bas"),
    "gauche": lambda: _ctrl.mouse_move_relative("gauche"),
    "droite": lambda: _ctrl.mouse_move_relative("droite"),
    # Defilement
    "scroll haut": lambda: _ctrl.mouse_scroll_up(),
    "scroll bas": lambda: _ctrl.mouse_scroll_down(),
    "defilement haut": lambda: _ctrl.mouse_scroll_up(),
    "defilement bas": lambda: _ctrl.mouse_scroll_down(),
    "defiler haut": lambda: _ctrl.mouse_scroll_up(),
    "defiler bas": lambda: _ctrl.mouse_scroll_down(),
    # Position
    "position du curseur": _ctrl.mouse_get_position,
    "ou est le curseur": _ctrl.mouse_get_position,
    "position souris": _ctrl.mouse_get_position,
    # Centre
    "curseur au centre": _ctrl.mouse_center,
    "centre": _ctrl.mouse_center,
    "centrer le curseur": _ctrl.mouse_center,
    # Coins
    "curseur coin haut gauche": lambda: _ctrl.mouse_move_to_corner("haut gauche"),
    "curseur coin haut droite": lambda: _ctrl.mouse_move_to_corner("haut droite"),
    "curseur coin bas gauche": lambda: _ctrl.mouse_move_to_corner("bas gauche"),
    "curseur coin bas droite": lambda: _ctrl.mouse_move_to_corner("bas droite"),
    "coin haut gauche": lambda: _ctrl.mouse_move_to_corner("haut gauche"),
    "coin haut droite": lambda: _ctrl.mouse_move_to_corner("haut droite"),
    "coin bas gauche": lambda: _ctrl.mouse_move_to_corner("bas gauche"),
    "coin bas droite": lambda: _ctrl.mouse_move_to_corner("bas droite"),
    # Maintien / relache
    "maintiens le clic": _ctrl.mouse_hold,
    "maintiens": _ctrl.mouse_hold,
    "relache le clic": _ctrl.mouse_release,
    "relache": _ctrl.mouse_release,
    # Scroll horizontal
    "scroll gauche": lambda: _ctrl.mouse_scroll_left(),
    "defilement gauche": lambda: _ctrl.mouse_scroll_left(),
    "scroll droite": lambda: _ctrl.mouse_scroll_right(),
    "defilement droite": lambda: _ctrl.mouse_scroll_right(),
    # Positions nommees
    "curseur barre des taches": _ctrl.mouse_move_to_taskbar,
    "barre des taches": _ctrl.mouse_move_to_taskbar,
    "curseur en bas de l'ecran": _ctrl.mouse_move_to_taskbar,
    "curseur barre de menu": _ctrl.mouse_move_to_menu_bar,
    "barre de menu": _ctrl.mouse_move_to_menu_bar,
    "curseur en haut de l'ecran": _ctrl.mouse_move_to_menu_bar,
    # Clic milieu
    "clic milieu": _ctrl.mouse_click_middle,
    "clic molette": _ctrl.mouse_click_middle,
    # Localisation curseur
    "secoue la souris": _ctrl.mouse_shake,
    "ou est la souris": _ctrl.mouse_shake,
    "trouve le curseur": _ctrl.mouse_shake,
    "montre le curseur": _ctrl.mouse_circle,
    "cercle": _ctrl.mouse_circle,
}

# Patterns parametres : (regex, handler)
# Les groupes nommes sont passes comme kwargs au handler
PARAM_PATTERNS: list[tuple[re.Pattern, Callable[..., str]]] = [
    # "grille 5" ou "grille cinq"
    (
        re.compile(r"grille\s+(\d)", re.IGNORECASE),
        lambda m: _ctrl.mouse_grid_numpad(int(m.group(1))),
    ),
    # "bouge de 120 pixels a droite"
    (
        re.compile(
            r"bouge\s+de\s+(\d+)\s*pixels?\s+(haut|bas|gauche|droite)",
            re.IGNORECASE,
        ),
        lambda m: _ctrl.mouse_move_relative(m.group(2), int(m.group(1))),
    ),
    # "deplace de 30 vers le haut"
    (
        re.compile(
            r"deplace\s+de\s+(\d+)\s+vers\s+(?:le\s+|la\s+)?(haut|bas|gauche|droite)",
            re.IGNORECASE,
        ),
        lambda m: _ctrl.mouse_move_relative(m.group(2), int(m.group(1))),
    ),
    # "curseur en haut de 100"
    (
        re.compile(
            r"curseur\s+(?:en\s+|a\s+)?(haut|bas|gauche|droite)\s+de\s+(\d+)",
            re.IGNORECASE,
        ),
        lambda m: _ctrl.mouse_move_relative(m.group(1), int(m.group(2))),
    ),
    # "mouvement precis haut 5"
    (
        re.compile(
            r"(?:mouvement|deplacement)\s+precis\s+(haut|bas|gauche|droite)\s*(\d+)?",
            re.IGNORECASE,
        ),
        lambda m: _ctrl.mouse_slow_move(m.group(1), int(m.group(2) or 10)),
    ),
    # "scroll haut 10" / "scroll bas 5"
    (
        re.compile(r"scroll\s+(haut|bas)\s+(\d+)", re.IGNORECASE),
        lambda m: (
            _ctrl.mouse_scroll_up(int(m.group(2)))
            if m.group(1).lower() == "haut"
            else _ctrl.mouse_scroll_down(int(m.group(2)))
        ),
    ),
    # "defilement haut 10"
    (
        re.compile(r"defilement\s+(haut|bas)\s+(\d+)", re.IGNORECASE),
        lambda m: (
            _ctrl.mouse_scroll_up(int(m.group(2)))
            if m.group(1).lower() == "haut"
            else _ctrl.mouse_scroll_down(int(m.group(2)))
        ),
    ),
    # "glisse vers 500 300"
    (
        re.compile(r"glisse\s+vers\s+(\d+)\s*[,;]\s*(\d+)", re.IGNORECASE),
        lambda m: _ctrl.mouse_drag_to(int(m.group(1)), int(m.group(2))),
    ),
    # "va en 800 600" / "deplace en 800 600"
    (
        re.compile(
            r"(?:va|deplace|curseur)\s+(?:en|vers|a)\s+(\d+)\s*[,;\s]\s*(\d+)",
            re.IGNORECASE,
        ),
        lambda m: _ctrl.mouse_move_to(int(m.group(1)), int(m.group(2))),
    ),
    # "clic en 400 300"
    (
        re.compile(r"clic(?:que)?\s+en\s+(\d+)\s*[,;\s]\s*(\d+)", re.IGNORECASE),
        lambda m: _ctrl.mouse_click_at(int(m.group(1)), int(m.group(2))),
    ),
]

# Mapping mots-nombres francais pour les chiffres 1-9
_WORD_DIGITS = {
    "un": "1", "deux": "2", "trois": "3", "quatre": "4", "cinq": "5",
    "six": "6", "sept": "7", "huit": "8", "neuf": "9",
}


def _normalize_text(text: str) -> str:
    """Normalise le texte vocal : minuscules, accents simplifies, mots-nombres -> chiffres."""
    text = text.lower().strip()
    # Remplacer mots-nombres par chiffres
    for word, digit in _WORD_DIGITS.items():
        text = re.sub(rf"\b{word}\b", digit, text)
    return text


def execute_mouse_command(text: str) -> str | None:
    """Analyse le texte vocal et execute la commande souris correspondante.

    Retourne la chaine de statut en francais, ou None si aucune commande reconnue.
    """
    text = _normalize_text(text)

    # 1. Essayer les patterns parametres d'abord (plus specifiques)
    for pattern, handler in PARAM_PATTERNS:
        match = pattern.search(text)
        if match:
            return handler(match)

    # 2. Essayer les commandes directes (du plus long au plus court pour eviter les faux positifs)
    for phrase in sorted(VOICE_COMMANDS.keys(), key=len, reverse=True):
        if phrase in text:
            return VOICE_COMMANDS[phrase]()

    return None


def get_controller() -> VoiceMouseControl:
    """Retourne l'instance singleton du controleur souris."""
    return _ctrl


def list_voice_commands() -> dict[str, str]:
    """Liste toutes les commandes vocales disponibles avec leur description."""
    commands = {}
    for phrase in sorted(VOICE_COMMANDS.keys()):
        fn = VOICE_COMMANDS[phrase]
        doc = getattr(fn, "__doc__", None) or ""
        # Pour les lambdas, decrire d'apres la phrase
        if not doc or doc == "<lambda>":
            doc = phrase
        commands[phrase] = doc
    return commands


def list_methods() -> list[dict[str, str]]:
    """Liste toutes les methodes mouse_* disponibles."""
    methods = []
    for name in sorted(dir(_ctrl)):
        if name.startswith("mouse_"):
            fn = getattr(_ctrl, name)
            methods.append({
                "method": name,
                "doc": (fn.__doc__ or "").strip().split("\n")[0],
            })
    return methods


# ====================================================================== #
#  Point d'entree CLI                                                     #
# ====================================================================== #

def main() -> None:
    """Point d'entree en ligne de commande."""
    parser = argparse.ArgumentParser(
        description="Controle de la souris par commandes vocales (xdotool)",
    )
    parser.add_argument(
        "--cmd",
        type=str,
        help="Commande vocale a executer (ex: 'clic droit', 'grille 5')",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Lister toutes les commandes vocales",
    )
    parser.add_argument(
        "--list-methods",
        action="store_true",
        help="Lister toutes les methodes disponibles",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Sortie au format JSON",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test rapide : affiche la position du curseur",
    )
    args = parser.parse_args()

    if args.list:
        cmds = list_voice_commands()
        if args.json:
            print(json.dumps(cmds, ensure_ascii=False, indent=2))
        else:
            print("Commandes vocales disponibles :")
            print("-" * 50)
            for phrase, doc in cmds.items():
                print(f"  \"{phrase}\"  ->  {doc}")
        return

    if args.list_methods:
        methods = list_methods()
        if args.json:
            print(json.dumps(methods, ensure_ascii=False, indent=2))
        else:
            print("Methodes disponibles :")
            print("-" * 50)
            for m in methods:
                print(f"  {m['method']}()  --  {m['doc']}")
        return

    if args.test:
        result = _ctrl.mouse_get_position()
        print(result)
        w, h = _ctrl._get_screen_size()
        print(f"Taille de l'ecran : {w}x{h}")
        return

    if args.cmd:
        result = execute_mouse_command(args.cmd)
        if result is None:
            print(f"Commande non reconnue : \"{args.cmd}\"")
            sys.exit(1)
        if args.json:
            print(json.dumps({"status": result}, ensure_ascii=False))
        else:
            print(result)
        return

    # Mode interactif
    print("Controle souris vocal (tapez 'quitter' pour sortir)")
    print("Tapez une commande :")
    try:
        while True:
            text = input("> ").strip()
            if text.lower() in ("quitter", "quit", "exit", "q"):
                break
            if not text:
                continue
            result = execute_mouse_command(text)
            if result is None:
                print(f"  ? Commande non reconnue : \"{text}\"")
            else:
                print(f"  {result}")
    except (KeyboardInterrupt, EOFError):
        print("\nAu revoir.")


if __name__ == "__main__":
    main()
