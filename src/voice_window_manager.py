#!/usr/bin/env python3
"""voice_window_manager.py — Gestion complete des fenetres et menus par la voix.

Controle integral des fenetres, workspaces, menus et dialogues sur Linux
(GNOME + X11) via xdotool et wmctrl. Concu pour un utilisateur SANS souris.

Usage:
    python src/voice_window_manager.py --cmd "ferme la fenetre"
    python src/voice_window_manager.py --cmd "fenetre en haut a gauche"
    python src/voice_window_manager.py --cmd "passe a firefox"
    python src/voice_window_manager.py --cmd "menu fichier"
    python src/voice_window_manager.py --cmd "workspace 3"
    python src/voice_window_manager.py --list
    python src/voice_window_manager.py --list-methods
"""
from __future__ import annotations

import argparse
import logging
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Optional

__all__ = [
    "VoiceWindowManager",
    "VOICE_COMMANDS",
    "PARAM_PATTERNS",
    "WindowInfo",
]

logger = logging.getLogger("jarvis.voice_window_manager")

# ---------------------------------------------------------------------------
# Structures de donnees
# ---------------------------------------------------------------------------

@dataclass
class WindowInfo:
    """Informations sur une fenetre ouverte."""
    wid: str
    desktop: int
    x: int
    y: int
    width: int
    height: int
    pid: int
    hostname: str
    title: str


# ---------------------------------------------------------------------------
# Patterns de parametres vocaux
# ---------------------------------------------------------------------------

PARAM_PATTERNS: dict[str, re.Pattern] = {
    "number": re.compile(r"(\d+)"),
    "coords": re.compile(r"(\d+)\s*[,x]\s*(\d+)"),
    "dimensions": re.compile(r"(\d+)\s*[xX×par]\s*(\d+)"),
    "app_name": re.compile(r"(?:passe\s+[aà]\s+|fenetre\s+)(.+)", re.IGNORECASE),
    "menu_path": re.compile(
        r"(?:menu\s+)(.+)", re.IGNORECASE
    ),
    "workspace_num": re.compile(r"workspace\s+(\d+)", re.IGNORECASE),
    "window_num": re.compile(r"fen[eê]tre\s+(\d+)", re.IGNORECASE),
}


# ---------------------------------------------------------------------------
# Commandes vocales -> methodes
# ---------------------------------------------------------------------------

VOICE_COMMANDS: dict[str, str] = {
    # --- Fenetre: basiques ---
    "ferme la fenetre":         "wm_close",
    "ferme fenetre":            "wm_close",
    "fermer":                   "wm_close",
    "alt f4":                   "wm_close",
    "minimise":                 "wm_minimize",
    "minimise la fenetre":      "wm_minimize",
    "reduis la fenetre":        "wm_minimize",
    "maximise":                 "wm_maximize",
    "maximise la fenetre":      "wm_maximize",
    "agrandis la fenetre":      "wm_maximize",
    "plein ecran":              "wm_fullscreen",
    "ecran complet":            "wm_fullscreen",
    "mode plein ecran":         "wm_fullscreen",
    "f11":                      "wm_fullscreen",
    "restaure la fenetre":      "wm_restore",
    "restaure":                 "wm_restore",
    "fenetre normale":          "wm_restore",
    "toujours devant":          "wm_always_on_top",
    "toujours au dessus":       "wm_always_on_top",
    "epingle la fenetre":       "wm_always_on_top",

    # --- Positionnement ---
    "fenetre a gauche":         "wm_snap_left",
    "snap gauche":              "wm_snap_left",
    "moitie gauche":            "wm_snap_left",
    "fenetre a droite":         "wm_snap_right",
    "snap droite":              "wm_snap_right",
    "moitie droite":            "wm_snap_right",
    "fenetre en haut a gauche": "wm_snap_top_left",
    "quart haut gauche":        "wm_snap_top_left",
    "fenetre en haut a droite": "wm_snap_top_right",
    "quart haut droite":        "wm_snap_top_right",
    "fenetre en bas a gauche":  "wm_snap_bottom_left",
    "quart bas gauche":         "wm_snap_bottom_left",
    "fenetre en bas a droite":  "wm_snap_bottom_right",
    "quart bas droite":         "wm_snap_bottom_right",
    "centre la fenetre":        "wm_center",
    "fenetre au centre":        "wm_center",
    "centre":                   "wm_center",
    "deplace la fenetre":       "wm_move_to",
    "bouge la fenetre":         "wm_move_to",
    "redimensionne":            "wm_resize",
    "taille fenetre":           "wm_resize",

    # --- Changement de fenetre ---
    "fenetre suivante":         "wm_switch_next",
    "alt tab":                  "wm_switch_next",
    "prochaine fenetre":        "wm_switch_next",
    "fenetre precedente":       "wm_switch_prev",
    "alt shift tab":            "wm_switch_prev",
    "liste les fenetres":       "wm_list_windows",
    "quelles fenetres":         "wm_list_windows",
    "montre les fenetres":      "wm_list_windows",
    "cycle fenetre":            "wm_cycle_windows",
    "meme application":         "wm_cycle_windows",

    # --- Focus par nom (pattern dynamique) ---
    "passe a":                  "wm_focus_by_name",
    "va sur":                   "wm_focus_by_name",
    "ouvre":                    "wm_focus_by_name",
    "affiche":                  "wm_focus_by_name",

    # --- Focus par numero (pattern dynamique) ---
    "fenetre":                  "wm_focus_by_number",

    # --- Workspaces ---
    "workspace suivant":        "wm_workspace_next",
    "bureau suivant":           "wm_workspace_next",
    "espace suivant":           "wm_workspace_next",
    "workspace precedent":      "wm_workspace_prev",
    "bureau precedent":         "wm_workspace_prev",
    "espace precedent":         "wm_workspace_prev",
    "workspace":                "wm_workspace_goto",
    "bureau":                   "wm_workspace_goto",
    "deplace vers workspace":   "wm_move_to_workspace",
    "envoie vers workspace":    "wm_move_to_workspace",
    "deplace vers bureau":      "wm_move_to_workspace",
    "vue d'ensemble":           "wm_workspace_overview",
    "overview":                 "wm_workspace_overview",
    "activites":                "wm_workspace_overview",

    # --- Menus ---
    "ouvre le menu":            "wm_open_menu",
    "barre de menu":           "wm_open_menu",
    "f10":                      "wm_open_menu",
    "menu fichier":             "wm_menu_item",
    "menu edition":             "wm_menu_item",
    "menu affichage":           "wm_menu_item",
    "menu outils":              "wm_menu_item",
    "menu aide":                "wm_menu_item",
    "menu insertion":           "wm_menu_item",
    "menu format":              "wm_menu_item",
    "menu":                     "wm_menu_item",
    "clic droit":               "wm_context_menu",
    "menu contextuel":          "wm_context_menu",
    "fleche haut":              "wm_menu_up",
    "fleche bas":               "wm_menu_down",
    "fleche gauche":            "wm_menu_left",
    "fleche droite":            "wm_menu_right",
    "selectionne":              "wm_menu_select",
    "entree":                   "wm_menu_select",
    "valide":                   "wm_menu_select",
    "echappe":                  "wm_menu_cancel",
    "escape":                   "wm_menu_cancel",
    "annule le menu":           "wm_menu_cancel",

    # --- Dialogues ---
    "ok":                       "wm_dialog_ok",
    "confirme":                 "wm_dialog_ok",
    "accepte":                  "wm_dialog_ok",
    "annuler":                  "wm_dialog_cancel",
    "annule":                   "wm_dialog_cancel",
    "champ suivant":            "wm_dialog_tab_next",
    "tab":                      "wm_dialog_tab_next",
    "suivant":                  "wm_dialog_tab_next",
    "champ precedent":          "wm_dialog_tab_prev",
    "shift tab":                "wm_dialog_tab_prev",
    "precedent":                "wm_dialog_tab_prev",
    "espace":                   "wm_dialog_space",
    "coche":                    "wm_dialog_space",
    "decoche":                  "wm_dialog_space",
    "appuie":                   "wm_dialog_space",

    # --- Tiling ---
    "cote a cote":              "wm_tile_side_by_side",
    "fenetre cote a cote":      "wm_tile_side_by_side",
    "cote-a-cote":              "wm_tile_side_by_side",
    "empile":                   "wm_tile_stack",
    "empile les fenetres":      "wm_tile_stack",
    "haut bas":                 "wm_tile_stack",

    # --- Multi-fenetres avancees ---
    "minimise tout":            "wm_minimize_all",
    "montre le bureau":         "wm_minimize_all",
    "affiche le bureau":        "wm_minimize_all",
    "super d":                  "wm_minimize_all",
    "ferme toutes les fenetres": "wm_close_all_except",
    "ferme les autres":         "wm_close_all_except",
    "garde seulement celle-ci": "wm_close_all_except",
    "minimise les autres":      "wm_minimize_all_except",
    "cache les autres":         "wm_minimize_all_except",
    "mosaique 4":               "wm_tile_grid_4",
    "mosaique quatre":          "wm_tile_grid_4",
    "grille quatre":            "wm_tile_grid_4",
    "quatre fenetres":          "wm_tile_grid_4",
    "2 par 2":                  "wm_tile_grid_4",
    "mosaique 3":               "wm_tile_grid_3",
    "mosaique trois":           "wm_tile_grid_3",
    "layout principal":         "wm_tile_grid_3",
    "une grande deux petites":  "wm_tile_grid_3",
    "echange les fenetres":     "wm_swap_windows",
    "swap fenetres":            "wm_swap_windows",
    "inverse les fenetres":     "wm_swap_windows",
    "permute les fenetres":     "wm_swap_windows",
    "transparente":             "wm_opacity",
    "opacite":                  "wm_opacity",
    "rends transparent":        "wm_opacity",
    "combien de workspaces":    "wm_workspace_count",
    "nombre de bureaux":        "wm_workspace_count",
    "quel workspace":           "wm_workspace_count",
}


# ---------------------------------------------------------------------------
# Classe principale
# ---------------------------------------------------------------------------

class VoiceWindowManager:
    """Gestionnaire de fenetres et menus pilote entierement a la voix.

    Utilise xdotool et wmctrl pour controler fenetres, workspaces,
    menus et dialogues sur GNOME/X11 sans souris.
    """

    def __init__(self) -> None:
        """Initialise le gestionnaire et verifie les dependances."""
        self._check_deps()
        self._screen_w: int = 0
        self._screen_h: int = 0
        self._refresh_screen_size()

    # ===================================================================
    # Utilitaires internes
    # ===================================================================

    @staticmethod
    def _check_deps() -> None:
        """Verifie que xdotool et wmctrl sont installes."""
        missing = []
        for tool in ("xdotool", "wmctrl"):
            if not shutil.which(tool):
                missing.append(tool)
        if missing:
            raise RuntimeError(
                f"Outils manquants: {', '.join(missing)}. "
                f"Installez avec: sudo apt install {' '.join(missing)}"
            )

    def _refresh_screen_size(self) -> None:
        """Met a jour les dimensions de l'ecran."""
        try:
            out = self._run("xdotool getdisplaygeometry")
            parts = out.strip().split()
            if len(parts) == 2:
                self._screen_w = int(parts[0])
                self._screen_h = int(parts[1])
        except Exception:
            self._screen_w = 1920
            self._screen_h = 1080

    @staticmethod
    def _run(cmd: str, timeout: int = 5) -> str:
        """Execute une commande shell et retourne stdout."""
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=timeout,
            )
            if result.returncode != 0 and result.stderr:
                logger.warning("Commande '%s' stderr: %s", cmd, result.stderr.strip())
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            logger.error("Timeout commande: %s", cmd)
            return ""
        except Exception as e:
            logger.error("Erreur commande '%s': %s", cmd, e)
            return ""

    @staticmethod
    def _xdo(args: str) -> str:
        """Raccourci pour xdotool."""
        return VoiceWindowManager._run(f"xdotool {args}")

    @staticmethod
    def _wmctrl(args: str) -> str:
        """Raccourci pour wmctrl."""
        return VoiceWindowManager._run(f"wmctrl {args}")

    def _get_active_wid(self) -> str:
        """Retourne l'identifiant de la fenetre active."""
        return self._xdo("getactivewindow")

    def _get_window_geometry(self, wid: str) -> tuple[int, int, int, int]:
        """Retourne (x, y, largeur, hauteur) de la fenetre."""
        out = self._xdo(f"getwindowgeometry --shell {wid}")
        vals: dict[str, int] = {}
        for line in out.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                try:
                    vals[k.strip()] = int(v.strip())
                except ValueError:
                    pass
        return vals.get("X", 0), vals.get("Y", 0), vals.get("WIDTH", 800), vals.get("HEIGHT", 600)

    def _parse_window_list(self) -> list[WindowInfo]:
        """Parse la sortie de wmctrl -lGp en liste de WindowInfo."""
        out = self._wmctrl("-lGp")
        windows: list[WindowInfo] = []
        for line in out.splitlines():
            parts = line.split(None, 8)
            if len(parts) < 9:
                continue
            try:
                winfo = WindowInfo(
                    wid=parts[0],
                    desktop=int(parts[1]),
                    pid=int(parts[2]),
                    x=int(parts[3]),
                    y=int(parts[4]),
                    width=int(parts[5]),
                    height=int(parts[6]),
                    hostname=parts[7],
                    title=parts[8],
                )
                windows.append(winfo)
            except (ValueError, IndexError):
                continue
        return windows

    # ===================================================================
    # WINDOW BASICS (1-6)
    # ===================================================================

    def wm_close(self) -> str:
        """Ferme la fenetre active avec Alt+F4."""
        self._xdo("key alt+F4")
        return "Fenetre fermee."

    def wm_minimize(self) -> str:
        """Minimise la fenetre active dans la barre des taches."""
        wid = self._get_active_wid()
        if not wid:
            return "Aucune fenetre active."
        self._xdo(f"windowminimize {wid}")
        return "Fenetre minimisee."

    def wm_maximize(self) -> str:
        """Maximise la fenetre active ou bascule l'etat maximise."""
        wid = self._get_active_wid()
        if not wid:
            return "Aucune fenetre active."
        self._wmctrl(f"-i -r {wid} -b toggle,maximized_vert,maximized_horz")
        return "Fenetre maximisee."

    def wm_restore(self) -> str:
        """Restaure la fenetre depuis l'etat maximise."""
        wid = self._get_active_wid()
        if not wid:
            return "Aucune fenetre active."
        self._wmctrl(f"-i -r {wid} -b remove,maximized_vert,maximized_horz")
        return "Fenetre restauree."

    def wm_fullscreen(self) -> str:
        """Bascule le mode plein ecran (F11)."""
        wid = self._get_active_wid()
        if not wid:
            return "Aucune fenetre active."
        self._wmctrl(f"-i -r {wid} -b toggle,fullscreen")
        return "Plein ecran bascule."

    def wm_always_on_top(self) -> str:
        """Bascule le mode 'toujours au dessus' pour la fenetre active."""
        wid = self._get_active_wid()
        if not wid:
            return "Aucune fenetre active."
        self._wmctrl(f"-i -r {wid} -b toggle,above")
        return "Mode 'toujours au dessus' bascule."

    # ===================================================================
    # WINDOW POSITIONING (7-15)
    # ===================================================================

    def wm_snap_left(self) -> str:
        """Ancre la fenetre sur la moitie gauche de l'ecran."""
        wid = self._get_active_wid()
        if not wid:
            return "Aucune fenetre active."
        w = self._screen_w // 2
        h = self._screen_h
        self._wmctrl(f"-i -r {wid} -b remove,maximized_vert,maximized_horz")
        time.sleep(0.05)
        self._wmctrl(f"-i -r {wid} -e 0,0,0,{w},{h}")
        return f"Fenetre ancree a gauche ({w}x{h})."

    def wm_snap_right(self) -> str:
        """Ancre la fenetre sur la moitie droite de l'ecran."""
        wid = self._get_active_wid()
        if not wid:
            return "Aucune fenetre active."
        w = self._screen_w // 2
        h = self._screen_h
        self._wmctrl(f"-i -r {wid} -b remove,maximized_vert,maximized_horz")
        time.sleep(0.05)
        self._wmctrl(f"-i -r {wid} -e 0,{w},0,{w},{h}")
        return f"Fenetre ancree a droite ({w}x{h})."

    def wm_snap_top_left(self) -> str:
        """Ancre la fenetre dans le quart superieur gauche."""
        wid = self._get_active_wid()
        if not wid:
            return "Aucune fenetre active."
        w = self._screen_w // 2
        h = self._screen_h // 2
        self._wmctrl(f"-i -r {wid} -b remove,maximized_vert,maximized_horz")
        time.sleep(0.05)
        self._wmctrl(f"-i -r {wid} -e 0,0,0,{w},{h}")
        return f"Fenetre en haut a gauche ({w}x{h})."

    def wm_snap_top_right(self) -> str:
        """Ancre la fenetre dans le quart superieur droit."""
        wid = self._get_active_wid()
        if not wid:
            return "Aucune fenetre active."
        w = self._screen_w // 2
        h = self._screen_h // 2
        self._wmctrl(f"-i -r {wid} -b remove,maximized_vert,maximized_horz")
        time.sleep(0.05)
        self._wmctrl(f"-i -r {wid} -e 0,{w},0,{w},{h}")
        return f"Fenetre en haut a droite ({w}x{h})."

    def wm_snap_bottom_left(self) -> str:
        """Ancre la fenetre dans le quart inferieur gauche."""
        wid = self._get_active_wid()
        if not wid:
            return "Aucune fenetre active."
        w = self._screen_w // 2
        h = self._screen_h // 2
        self._wmctrl(f"-i -r {wid} -b remove,maximized_vert,maximized_horz")
        time.sleep(0.05)
        self._wmctrl(f"-i -r {wid} -e 0,0,{h},{w},{h}")
        return f"Fenetre en bas a gauche ({w}x{h})."

    def wm_snap_bottom_right(self) -> str:
        """Ancre la fenetre dans le quart inferieur droit."""
        wid = self._get_active_wid()
        if not wid:
            return "Aucune fenetre active."
        w = self._screen_w // 2
        h = self._screen_h // 2
        self._wmctrl(f"-i -r {wid} -b remove,maximized_vert,maximized_horz")
        time.sleep(0.05)
        self._wmctrl(f"-i -r {wid} -e 0,{w},{h},{w},{h}")
        return f"Fenetre en bas a droite ({w}x{h})."

    def wm_center(self) -> str:
        """Centre la fenetre active au milieu de l'ecran."""
        wid = self._get_active_wid()
        if not wid:
            return "Aucune fenetre active."
        _, _, ww, wh = self._get_window_geometry(wid)
        x = max(0, (self._screen_w - ww) // 2)
        y = max(0, (self._screen_h - wh) // 2)
        self._wmctrl(f"-i -r {wid} -b remove,maximized_vert,maximized_horz")
        time.sleep(0.05)
        self._wmctrl(f"-i -r {wid} -e 0,{x},{y},{ww},{wh}")
        return f"Fenetre centree a ({x}, {y})."

    def wm_move_to(self, x: int = 0, y: int = 0) -> str:
        """Deplace la fenetre active a la position (x, y)."""
        wid = self._get_active_wid()
        if not wid:
            return "Aucune fenetre active."
        _, _, ww, wh = self._get_window_geometry(wid)
        self._wmctrl(f"-i -r {wid} -b remove,maximized_vert,maximized_horz")
        time.sleep(0.05)
        self._wmctrl(f"-i -r {wid} -e 0,{x},{y},{ww},{wh}")
        return f"Fenetre deplacee a ({x}, {y})."

    def wm_resize(self, width: int = 800, height: int = 600) -> str:
        """Redimensionne la fenetre active a la taille donnee."""
        wid = self._get_active_wid()
        if not wid:
            return "Aucune fenetre active."
        wx, wy, _, _ = self._get_window_geometry(wid)
        self._wmctrl(f"-i -r {wid} -b remove,maximized_vert,maximized_horz")
        time.sleep(0.05)
        self._wmctrl(f"-i -r {wid} -e 0,{wx},{wy},{width},{height}")
        return f"Fenetre redimensionnee a {width}x{height}."

    # ===================================================================
    # WINDOW SWITCHING (16-21)
    # ===================================================================

    def wm_switch_next(self) -> str:
        """Passe a la fenetre suivante (Alt+Tab)."""
        self._xdo("key alt+Tab")
        return "Fenetre suivante."

    def wm_switch_prev(self) -> str:
        """Passe a la fenetre precedente (Alt+Shift+Tab)."""
        self._xdo("key alt+shift+Tab")
        return "Fenetre precedente."

    def wm_focus_by_name(self, name: str = "") -> str:
        """Active la fenetre dont le titre contient le nom donne."""
        if not name:
            return "Aucun nom de fenetre specifie."
        name_clean = name.strip()
        # Essai direct via wmctrl -a (insensible a la casse)
        ret = self._wmctrl(f"-a '{name_clean}'")
        # Verification: chercher parmi les fenetres
        windows = self._parse_window_list()
        for w in windows:
            if name_clean.lower() in w.title.lower():
                self._wmctrl(f"-i -a {w.wid}")
                return f"Fenetre '{w.title}' activee."
        return f"Aucune fenetre trouvee contenant '{name_clean}'."

    def wm_focus_by_number(self, n: int = 1) -> str:
        """Active la N-ieme fenetre de la liste (numerotation a partir de 1)."""
        windows = self._parse_window_list()
        if not windows:
            return "Aucune fenetre ouverte."
        idx = max(1, min(n, len(windows))) - 1
        target = windows[idx]
        self._wmctrl(f"-i -a {target.wid}")
        return f"Fenetre {n} activee: '{target.title}'."

    def wm_list_windows(self) -> str:
        """Liste toutes les fenetres ouvertes avec leur numero."""
        windows = self._parse_window_list()
        if not windows:
            return "Aucune fenetre ouverte."
        lines = [f"  {i+1}. [{w.desktop}] {w.title}" for i, w in enumerate(windows)]
        header = f"{len(windows)} fenetres ouvertes:"
        return header + "\n" + "\n".join(lines)

    def wm_cycle_windows(self) -> str:
        """Cycle entre les fenetres de la meme application (Alt+`)."""
        self._xdo("key alt+grave")
        return "Cycle entre fenetres de la meme application."

    # ===================================================================
    # WORKSPACES (22-26)
    # ===================================================================

    def wm_workspace_next(self) -> str:
        """Passe au workspace suivant."""
        self._xdo("key super+Page_Down")
        return "Workspace suivant."

    def wm_workspace_prev(self) -> str:
        """Passe au workspace precedent."""
        self._xdo("key super+Page_Up")
        return "Workspace precedent."

    def wm_workspace_goto(self, n: int = 1) -> str:
        """Va directement au workspace numero N (base 1)."""
        desktop = max(0, n - 1)
        self._wmctrl(f"-s {desktop}")
        return f"Workspace {n} active."

    def wm_move_to_workspace(self, n: int = 1) -> str:
        """Deplace la fenetre active vers le workspace N."""
        wid = self._get_active_wid()
        if not wid:
            return "Aucune fenetre active."
        desktop = max(0, n - 1)
        self._wmctrl(f"-i -r {wid} -t {desktop}")
        return f"Fenetre deplacee vers workspace {n}."

    def wm_workspace_overview(self) -> str:
        """Affiche la vue d'ensemble des workspaces (touche Super)."""
        self._xdo("key super")
        return "Vue d'ensemble des workspaces."

    # ===================================================================
    # MENU NAVIGATION (27-35)
    # ===================================================================

    def wm_open_menu(self) -> str:
        """Ouvre la barre de menu de l'application (F10)."""
        self._xdo("key F10")
        return "Menu ouvert."

    def wm_menu_item(self, path: str = "") -> str:
        """Navigue vers un element de menu par chemin (ex: 'Fichier > Nouveau').

        Accepte un chemin separe par '>' ou simplement un nom de menu
        de premier niveau comme 'Fichier', 'Edition', etc.
        """
        if not path:
            return "Aucun chemin de menu specifie."

        path_clean = path.strip()

        # Mapping des noms de menus courants vers leur raccourci Alt+lettre
        menu_accelerators: dict[str, str] = {
            "fichier": "alt+f",
            "edition": "alt+e",
            "affichage": "alt+a",
            "insertion": "alt+i",
            "format": "alt+o",
            "outils": "alt+t",
            "aide": "alt+h",
            "file": "alt+f",
            "edit": "alt+e",
            "view": "alt+v",
            "tools": "alt+t",
            "help": "alt+h",
        }

        # Decoupage du chemin
        items = [s.strip() for s in path_clean.split(">") if s.strip()]
        if not items:
            return "Chemin de menu vide."

        # Premier element: ouvrir le menu principal
        first = items[0].lower()
        if first in menu_accelerators:
            self._xdo(f"key {menu_accelerators[first]}")
        else:
            # Ouvre le menu generique puis tape le nom
            self._xdo("key F10")
            time.sleep(0.15)
            self._xdo(f"type --clearmodifiers '{items[0]}'")

        # Navigation dans les sous-menus
        for item in items[1:]:
            time.sleep(0.15)
            self._xdo("key Right")  # Entrer dans le sous-menu
            time.sleep(0.1)
            # Cherche l'element en tapant sa premiere lettre ou en naviguant
            self._xdo(f"type --clearmodifiers '{item}'")

        time.sleep(0.1)
        return f"Navigation menu: {' > '.join(items)}."

    def wm_context_menu(self) -> str:
        """Ouvre le menu contextuel (clic droit) avec Shift+F10."""
        self._xdo("key shift+F10")
        return "Menu contextuel ouvert."

    def wm_menu_up(self) -> str:
        """Fleche haut dans un menu."""
        self._xdo("key Up")
        return "Menu: haut."

    def wm_menu_down(self) -> str:
        """Fleche bas dans un menu."""
        self._xdo("key Down")
        return "Menu: bas."

    def wm_menu_left(self) -> str:
        """Fleche gauche — retour au menu parent."""
        self._xdo("key Left")
        return "Menu: gauche."

    def wm_menu_right(self) -> str:
        """Fleche droite — entrer dans le sous-menu."""
        self._xdo("key Right")
        return "Menu: droite."

    def wm_menu_select(self) -> str:
        """Valide la selection dans le menu (Entree)."""
        self._xdo("key Return")
        return "Element de menu selectionne."

    def wm_menu_cancel(self) -> str:
        """Ferme le menu ouvert (Echap)."""
        self._xdo("key Escape")
        return "Menu ferme."

    # ===================================================================
    # DIALOG NAVIGATION (36-40)
    # ===================================================================

    def wm_dialog_ok(self) -> str:
        """Valide le dialogue (Entree — OK/Accepter)."""
        self._xdo("key Return")
        return "Dialogue valide."

    def wm_dialog_cancel(self) -> str:
        """Annule le dialogue (Echap)."""
        self._xdo("key Escape")
        return "Dialogue annule."

    def wm_dialog_tab_next(self) -> str:
        """Passe au champ ou bouton suivant dans le dialogue (Tab)."""
        self._xdo("key Tab")
        return "Champ suivant."

    def wm_dialog_tab_prev(self) -> str:
        """Revient au champ ou bouton precedent (Shift+Tab)."""
        self._xdo("key shift+Tab")
        return "Champ precedent."

    def wm_dialog_space(self) -> str:
        """Appuie sur Espace (coche/decoche, active bouton)."""
        self._xdo("key space")
        return "Espace appuye."

    # ===================================================================
    # TILING (41-42)
    # ===================================================================

    def wm_tile_side_by_side(self) -> str:
        """Place les deux dernieres fenetres cote a cote (gauche/droite)."""
        windows = self._parse_window_list()
        if len(windows) < 2:
            return "Il faut au moins 2 fenetres pour le tiling."

        w = self._screen_w // 2
        h = self._screen_h

        # Fenetre active -> gauche
        wid_active = self._get_active_wid()
        if wid_active:
            self._wmctrl(f"-i -r {wid_active} -b remove,maximized_vert,maximized_horz")
            time.sleep(0.05)
            self._wmctrl(f"-i -r {wid_active} -e 0,0,0,{w},{h}")

        # Trouver la deuxieme fenetre (la plus recente qui n'est pas l'active)
        other = None
        for win in reversed(windows):
            # Comparaison des wid en hexa
            try:
                if int(win.wid, 16) != int(wid_active, 0):
                    other = win
                    break
            except (ValueError, TypeError):
                if win.wid != wid_active:
                    other = win
                    break

        if other:
            self._wmctrl(f"-i -r {other.wid} -b remove,maximized_vert,maximized_horz")
            time.sleep(0.05)
            self._wmctrl(f"-i -r {other.wid} -e 0,{w},0,{w},{h}")
            return f"Tiling cote a cote: active | {other.title}."
        return "Impossible de trouver une deuxieme fenetre."

    def wm_tile_stack(self) -> str:
        """Empile les deux dernieres fenetres (haut/bas)."""
        windows = self._parse_window_list()
        if len(windows) < 2:
            return "Il faut au moins 2 fenetres pour le tiling."

        w = self._screen_w
        h = self._screen_h // 2

        wid_active = self._get_active_wid()
        if wid_active:
            self._wmctrl(f"-i -r {wid_active} -b remove,maximized_vert,maximized_horz")
            time.sleep(0.05)
            self._wmctrl(f"-i -r {wid_active} -e 0,0,0,{w},{h}")

        other = None
        for win in reversed(windows):
            try:
                if int(win.wid, 16) != int(wid_active, 0):
                    other = win
                    break
            except (ValueError, TypeError):
                if win.wid != wid_active:
                    other = win
                    break

        if other:
            self._wmctrl(f"-i -r {other.wid} -b remove,maximized_vert,maximized_horz")
            time.sleep(0.05)
            self._wmctrl(f"-i -r {other.wid} -e 0,0,{h},{w},{h}")
            return f"Tiling empile: active / {other.title}."
        return "Impossible de trouver une deuxieme fenetre."

    # ===================================================================
    # Multi-fenetres avancees
    # ===================================================================

    def wm_minimize_all(self) -> str:
        """Minimiser toutes les fenetres (afficher le bureau)."""
        self._xdo("key super+d")
        return "Toutes les fenetres minimisees"

    def wm_close_all_except(self) -> str:
        """Fermer toutes les fenetres sauf l'active."""
        active = self._get_active_wid()
        windows = self._parse_window_list()
        closed = 0
        for w in windows:
            if w.wid != active and w.desktop != "-1":
                try:
                    self._wmctrl(f"-i -c {w.wid}")
                    closed += 1
                    time.sleep(0.1)
                except Exception:
                    pass
        return f"{closed} fenetres fermees (active conservee)"

    def wm_minimize_all_except(self) -> str:
        """Minimiser toutes sauf la fenetre active."""
        active = self._get_active_wid()
        windows = self._parse_window_list()
        minimized = 0
        for w in windows:
            if w.wid != active and w.desktop != "-1":
                try:
                    self._xdo(f"windowminimize {w.wid}")
                    minimized += 1
                except Exception:
                    pass
        return f"{minimized} fenetres minimisees (active conservee)"

    def wm_tile_grid_4(self) -> str:
        """Disposer 4 fenetres en mosaique 2x2."""
        self._refresh_screen_size()
        w, h = self._screen_w, self._screen_h
        half_w, half_h = w // 2, h // 2

        windows = [wi for wi in self._parse_window_list() if wi.desktop != "-1"]
        if len(windows) < 2:
            return "Pas assez de fenetres pour une mosaique"

        positions = [
            (0, 0, half_w, half_h),       # haut gauche
            (half_w, 0, half_w, half_h),   # haut droite
            (0, half_h, half_w, half_h),   # bas gauche
            (half_w, half_h, half_w, half_h),  # bas droite
        ]

        placed = 0
        for i, win in enumerate(windows[:4]):
            x, y, pw, ph = positions[i]
            try:
                self._wmctrl(f"-i -r {win.wid} -b remove,maximized_vert,maximized_horz")
                time.sleep(0.02)
                self._wmctrl(f"-i -r {win.wid} -e 0,{x},{y},{pw},{ph}")
                placed += 1
            except Exception:
                pass
        return f"Mosaique 2x2: {placed} fenetres placees"

    def wm_tile_grid_3(self) -> str:
        """Disposer 3 fenetres: 1 grande a gauche, 2 petites a droite."""
        self._refresh_screen_size()
        w, h = self._screen_w, self._screen_h
        two_thirds = w * 2 // 3
        one_third = w // 3

        windows = [wi for wi in self._parse_window_list() if wi.desktop != "-1"]
        if len(windows) < 2:
            return "Pas assez de fenetres"

        positions = [
            (0, 0, two_thirds, h),          # gauche 2/3
            (two_thirds, 0, one_third, h // 2),  # droite haut
            (two_thirds, h // 2, one_third, h // 2),  # droite bas
        ]

        placed = 0
        for i, win in enumerate(windows[:3]):
            x, y, pw, ph = positions[i]
            try:
                self._wmctrl(f"-i -r {win.wid} -b remove,maximized_vert,maximized_horz")
                time.sleep(0.02)
                self._wmctrl(f"-i -r {win.wid} -e 0,{x},{y},{pw},{ph}")
                placed += 1
            except Exception:
                pass
        return f"Layout 1+2: {placed} fenetres placees"

    def wm_swap_windows(self) -> str:
        """Echanger la position des 2 fenetres les plus recentes."""
        windows = [wi for wi in self._parse_window_list() if wi.desktop != "-1"]
        if len(windows) < 2:
            return "Pas assez de fenetres"

        w1, w2 = windows[0], windows[1]
        geo1 = self._xdo(f"getwindowgeometry {w1.wid}")
        geo2 = self._xdo(f"getwindowgeometry {w2.wid}")

        pos1 = re.search(r"Position:\s*(\d+),(\d+)", geo1)
        size1 = re.search(r"Geometry:\s*(\d+)x(\d+)", geo1)
        pos2 = re.search(r"Position:\s*(\d+),(\d+)", geo2)
        size2 = re.search(r"Geometry:\s*(\d+)x(\d+)", geo2)

        if not all([pos1, size1, pos2, size2]):
            return "Impossible de lire les geometries"

        # Echanger
        self._wmctrl(f"-i -r {w1.wid} -e 0,{pos2.group(1)},{pos2.group(2)},{size2.group(1)},{size2.group(2)}")
        self._wmctrl(f"-i -r {w2.wid} -e 0,{pos1.group(1)},{pos1.group(2)},{size1.group(1)},{size1.group(2)}")

        return f"Fenetres echangees: {w1.title[:30]} <-> {w2.title[:30]}"

    def wm_opacity(self, level: int = 80) -> str:
        """Rendre la fenetre active semi-transparente."""
        # Utilise xprop pour definir l'opacite
        opacity_val = int(level / 100 * 0xFFFFFFFF)
        active = self._get_active_wid()
        self._run(f"xprop -id {active} -f _NET_WM_WINDOW_OPACITY 32c -set _NET_WM_WINDOW_OPACITY {opacity_val}")
        return f"Opacite fenetre: {level}%"

    def wm_workspace_count(self) -> str:
        """Nombre de workspaces actuels."""
        count = self._xdo("get-num-desktops")
        current = self._xdo("get-desktop")
        try:
            return f"Workspace {int(current) + 1} sur {count}"
        except ValueError:
            return f"Workspaces: {count}"

    # ===================================================================
    # Dispatch vocal
    # ===================================================================

    def dispatch(self, text: str) -> str:
        """Analyse une commande vocale et execute la methode correspondante.

        Parcourt VOICE_COMMANDS du plus long au plus court pour eviter
        les correspondances partielles incorrectes.
        """
        text_lower = text.strip().lower()
        if not text_lower:
            return "Commande vide."

        # Tri par longueur decroissante pour match le plus precis d'abord
        sorted_commands = sorted(VOICE_COMMANDS.keys(), key=len, reverse=True)

        for trigger in sorted_commands:
            if text_lower.startswith(trigger) or text_lower == trigger:
                method_name = VOICE_COMMANDS[trigger]
                method = getattr(self, method_name, None)
                if method is None:
                    return f"Methode {method_name} non implementee."

                # Extraction du reste de la commande (parametres)
                remainder = text_lower[len(trigger):].strip()

                # --- Methodes avec parametres ---
                if method_name == "wm_focus_by_name":
                    name = remainder or text_lower.split(trigger, 1)[-1].strip()
                    return method(name)

                if method_name == "wm_focus_by_number":
                    m = PARAM_PATTERNS["number"].search(remainder or text_lower)
                    if m:
                        return method(int(m.group(1)))
                    return self.wm_list_windows()

                if method_name == "wm_workspace_goto":
                    m = PARAM_PATTERNS["number"].search(remainder or text_lower)
                    if m:
                        return method(int(m.group(1)))
                    return "Numero de workspace manquant."

                if method_name == "wm_move_to_workspace":
                    m = PARAM_PATTERNS["number"].search(remainder or text_lower)
                    if m:
                        return method(int(m.group(1)))
                    return "Numero de workspace manquant."

                if method_name == "wm_move_to":
                    m = PARAM_PATTERNS["coords"].search(remainder or text_lower)
                    if m:
                        return method(int(m.group(1)), int(m.group(2)))
                    return "Coordonnees manquantes (ex: 100,200)."

                if method_name == "wm_resize":
                    m = PARAM_PATTERNS["dimensions"].search(remainder or text_lower)
                    if m:
                        return method(int(m.group(1)), int(m.group(2)))
                    return "Dimensions manquantes (ex: 800x600)."

                if method_name == "wm_menu_item":
                    # Extraire le chemin du menu depuis la commande complete
                    path = remainder
                    if not path:
                        # "menu fichier" -> path = "fichier"
                        path = text_lower.replace("menu", "").strip()
                    if path:
                        return method(path)
                    return method()

                # Methodes sans parametre
                return method()

        return f"Commande non reconnue: '{text}'. Dites 'liste les fenetres' pour voir les fenetres."

    # ===================================================================
    # Introspection
    # ===================================================================

    def list_methods(self) -> list[dict[str, str]]:
        """Retourne la liste de toutes les methodes wm_ avec leur description."""
        methods = []
        for name in sorted(dir(self)):
            if name.startswith("wm_") and callable(getattr(self, name)):
                func = getattr(self, name)
                doc = (func.__doc__ or "").split("\n")[0].strip()
                methods.append({"name": name, "description": doc})
        return methods

    def list_voice_commands(self) -> list[dict[str, str]]:
        """Retourne la liste de toutes les commandes vocales avec leur methode."""
        return [
            {"trigger": trigger, "method": method}
            for trigger, method in sorted(VOICE_COMMANDS.items())
        ]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    """Point d'entree CLI pour le gestionnaire de fenetres vocal."""
    parser = argparse.ArgumentParser(
        description="Gestionnaire de fenetres vocal JARVIS (Linux/GNOME/X11)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Exemples:
  %(prog)s --cmd "ferme la fenetre"
  %(prog)s --cmd "fenetre en haut a gauche"
  %(prog)s --cmd "passe a firefox"
  %(prog)s --cmd "menu fichier"
  %(prog)s --cmd "workspace 3"
  %(prog)s --cmd "cote a cote"
  %(prog)s --list
  %(prog)s --list-methods
""",
    )
    parser.add_argument("--cmd", type=str, help="Commande vocale a executer")
    parser.add_argument(
        "--list", action="store_true",
        help="Affiche toutes les commandes vocales disponibles",
    )
    parser.add_argument(
        "--list-methods", action="store_true",
        help="Affiche toutes les methodes wm_ disponibles",
    )
    parser.add_argument(
        "--windows", action="store_true",
        help="Liste les fenetres ouvertes",
    )

    args = parser.parse_args()

    if not any([args.cmd, args.list, args.list_methods, args.windows]):
        parser.print_help()
        sys.exit(0)

    try:
        mgr = VoiceWindowManager()
    except RuntimeError as e:
        print(f"ERREUR: {e}", file=sys.stderr)
        sys.exit(1)

    if args.list:
        cmds = mgr.list_voice_commands()
        print(f"\n{'='*60}")
        print(f" {len(cmds)} commandes vocales disponibles")
        print(f"{'='*60}\n")
        current_method = ""
        for cmd in sorted(cmds, key=lambda c: c["method"]):
            if cmd["method"] != current_method:
                current_method = cmd["method"]
                func = getattr(mgr, current_method, None)
                doc = ""
                if func:
                    doc = (func.__doc__ or "").split("\n")[0].strip()
                print(f"\n  [{current_method}] {doc}")
            print(f"    - \"{cmd['trigger']}\"")
        print()
        sys.exit(0)

    if args.list_methods:
        methods = mgr.list_methods()
        print(f"\n{'='*60}")
        print(f" {len(methods)} methodes disponibles")
        print(f"{'='*60}\n")
        for m in methods:
            print(f"  {m['name']:30s} {m['description']}")
        print()
        sys.exit(0)

    if args.windows:
        result = mgr.wm_list_windows()
        print(result)
        sys.exit(0)

    if args.cmd:
        result = mgr.dispatch(args.cmd)
        print(result)


def execute_window_command(text: str) -> dict:
    """Interface unifiee pour le voice_router."""
    try:
        mgr = VoiceWindowManager()
        result = mgr.dispatch(text)
        if result and "inconnue" not in result.lower():
            return {"success": True, "method": "window_manager", "result": result, "confidence": 0.8}
    except Exception:
        pass
    return {"success": False, "method": "unknown", "result": f"Non reconnu: {text}", "confidence": 0.0}


if __name__ == "__main__":
    main()
