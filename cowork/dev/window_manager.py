#!/usr/bin/env python3
"""window_manager.py — Gestionnaire de fenetres multi-ecran Windows.

Deplace, redimensionne, ferme, minimise, maximise les fenetres.
Supporte le multi-ecran (deplacer sur l'autre ecran).

Usage:
    python dev/window_manager.py --list                    # Lister les fenetres
    python dev/window_manager.py --focus "Chrome"          # Focus sur Chrome
    python dev/window_manager.py --move "Chrome" --screen 2 # Deplacer sur ecran 2
    python dev/window_manager.py --close "Notepad"         # Fermer Notepad
    python dev/window_manager.py --minimize "Discord"      # Minimiser
    python dev/window_manager.py --maximize "Code"         # Maximiser
    python dev/window_manager.py --tile                    # Carreler toutes les fenetres
    python dev/window_manager.py --screens                 # Info ecrans
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import json
import subprocess
import sys
import time
from collections import defaultdict

# ---------------------------------------------------------------------------
# Win32 API Constants
# ---------------------------------------------------------------------------
SW_MINIMIZE = 6
SW_MAXIMIZE = 3
SW_RESTORE = 9
SW_SHOW = 5
SW_HIDE = 0
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
SWP_SHOWWINDOW = 0x0040
GWL_STYLE = -16
WS_VISIBLE = 0x10000000
WS_CAPTION = 0x00C00000
MONITOR_DEFAULTTONEAREST = 0x00000002

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# ---------------------------------------------------------------------------
# Structures
# ---------------------------------------------------------------------------
class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_ulong),
                ("rcMonitor", RECT), ("rcWork", RECT),
                ("dwFlags", ctypes.c_ulong)]

# ---------------------------------------------------------------------------
# Window enumeration
# ---------------------------------------------------------------------------
WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))

def get_all_windows():
    """Liste toutes les fenetres visibles avec titre."""
    windows = []
    def callback(hwnd, lParam):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                title = buff.value
                if title.strip():
                    style = user32.GetWindowLongW(hwnd, GWL_STYLE)
                    if style & WS_CAPTION:
                        rect = RECT()
                        user32.GetWindowRect(hwnd, ctypes.byref(rect))
                        # Get process name
                        pid = ctypes.c_ulong()
                        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                        windows.append({
                            "hwnd": hwnd,
                            "title": title,
                            "pid": pid.value,
                            "x": rect.left, "y": rect.top,
                            "w": rect.right - rect.left,
                            "h": rect.bottom - rect.top,
                        })
        return True
    CMPFUNC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.POINTER(ctypes.c_int))
    user32.EnumWindows(CMPFUNC(callback), 0)
    return windows

def find_window(name: str):
    """Trouve une fenetre par nom (recherche partielle, insensible a la casse)."""
    name_lower = name.lower()
    windows = get_all_windows()
    # Exact match first
    for w in windows:
        if name_lower == w["title"].lower():
            return w
    # Partial match
    for w in windows:
        if name_lower in w["title"].lower():
            return w
    return None

# ---------------------------------------------------------------------------
# Monitor enumeration
# ---------------------------------------------------------------------------
def get_monitors():
    """Liste tous les ecrans avec leurs dimensions."""
    monitors = []
    def callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        user32.GetMonitorInfoW(hMonitor, ctypes.byref(info))
        monitors.append({
            "handle": hMonitor,
            "x": info.rcWork.left,
            "y": info.rcWork.top,
            "w": info.rcWork.right - info.rcWork.left,
            "h": info.rcWork.bottom - info.rcWork.top,
            "primary": bool(info.dwFlags & 1),
            "full_w": info.rcMonitor.right - info.rcMonitor.left,
            "full_h": info.rcMonitor.bottom - info.rcMonitor.top,
        })
        return True
    MONITORENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.POINTER(RECT), ctypes.c_double)
    user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(callback), 0)
    # Sort: primary first, then by x position
    monitors.sort(key=lambda m: (not m["primary"], m["x"]))
    for i, m in enumerate(monitors):
        m["index"] = i + 1
    return monitors

def get_window_monitor(hwnd):
    """Retourne l'index de l'ecran ou se trouve la fenetre."""
    monitors = get_monitors()
    rect = RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    cx = (rect.left + rect.right) // 2
    cy = (rect.top + rect.bottom) // 2
    for m in monitors:
        if m["x"] <= cx < m["x"] + m["w"] and m["y"] <= cy < m["y"] + m["h"]:
            return m["index"]
    return 1

# ---------------------------------------------------------------------------
# Window actions
# ---------------------------------------------------------------------------
def focus_window(hwnd):
    """Met une fenetre au premier plan."""
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetForegroundWindow(hwnd)
    return True

def move_to_screen(hwnd, screen_index: int):
    """Deplace une fenetre vers un ecran specifique."""
    monitors = get_monitors()
    if screen_index < 1 or screen_index > len(monitors):
        return {"error": f"Ecran {screen_index} inexistant. {len(monitors)} ecrans disponibles."}

    target = monitors[screen_index - 1]
    rect = RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w = rect.right - rect.left
    h = rect.bottom - rect.top

    # Centrer sur l'ecran cible
    new_x = target["x"] + (target["w"] - w) // 2
    new_y = target["y"] + (target["h"] - h) // 2

    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetWindowPos(hwnd, 0, new_x, new_y, 0, 0, SWP_NOSIZE | SWP_NOZORDER | SWP_SHOWWINDOW)
    return {"moved": True, "screen": screen_index, "x": new_x, "y": new_y}

def move_to_other_screen(hwnd):
    """Deplace une fenetre vers l'autre ecran (toggle)."""
    monitors = get_monitors()
    if len(monitors) < 2:
        return {"error": "Un seul ecran detecte"}
    current = get_window_monitor(hwnd)
    target = 2 if current == 1 else 1
    return move_to_screen(hwnd, target)

def close_window(hwnd):
    """Ferme une fenetre."""
    WM_CLOSE = 0x0010
    user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
    return True

def minimize_window(hwnd):
    user32.ShowWindow(hwnd, SW_MINIMIZE)
    return True

def maximize_window(hwnd):
    user32.ShowWindow(hwnd, SW_MAXIMIZE)
    return True

def tile_windows():
    """Carrele toutes les fenetres visibles sur l'ecran principal."""
    monitors = get_monitors()
    if not monitors:
        return {"error": "Aucun ecran"}
    primary = monitors[0]
    windows = [w for w in get_all_windows()
               if get_window_monitor(w["hwnd"]) == primary["index"]]

    if not windows:
        return {"tiled": 0}

    n = len(windows)
    cols = int(n ** 0.5) + (1 if n ** 0.5 % 1 else 0)
    rows = (n + cols - 1) // cols
    tile_w = primary["w"] // cols
    tile_h = primary["h"] // rows

    for i, w in enumerate(windows):
        col = i % cols
        row = i // cols
        x = primary["x"] + col * tile_w
        y = primary["y"] + row * tile_h
        user32.ShowWindow(w["hwnd"], SW_RESTORE)
        user32.SetWindowPos(w["hwnd"], 0, x, y, tile_w, tile_h, SWP_NOZORDER | SWP_SHOWWINDOW)

    return {"tiled": n, "grid": f"{cols}x{rows}"}

def snap_window(hwnd, position: str):
    """Snap une fenetre a gauche/droite/haut/bas de l'ecran."""
    monitors = get_monitors()
    screen_idx = get_window_monitor(hwnd)
    screen = monitors[screen_idx - 1]

    positions = {
        "left":   (screen["x"], screen["y"], screen["w"] // 2, screen["h"]),
        "right":  (screen["x"] + screen["w"] // 2, screen["y"], screen["w"] // 2, screen["h"]),
        "top":    (screen["x"], screen["y"], screen["w"], screen["h"] // 2),
        "bottom": (screen["x"], screen["y"] + screen["h"] // 2, screen["w"], screen["h"] // 2),
        "full":   (screen["x"], screen["y"], screen["w"], screen["h"]),
    }

    if position not in positions:
        return {"error": f"Position inconnue: {position}. Options: {list(positions.keys())}"}

    x, y, w, h = positions[position]
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetWindowPos(hwnd, 0, x, y, w, h, SWP_NOZORDER | SWP_SHOWWINDOW)
    return {"snapped": position, "rect": {"x": x, "y": y, "w": w, "h": h}}

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="JARVIS Window Manager — Gestion fenetres multi-ecran")
    parser.add_argument("--list", action="store_true", help="Lister les fenetres visibles")
    parser.add_argument("--screens", action="store_true", help="Info sur les ecrans")
    parser.add_argument("--focus", type=str, help="Focus sur une fenetre (nom partiel)")
    parser.add_argument("--move", type=str, help="Deplacer une fenetre")
    parser.add_argument("--screen", type=int, default=0, help="Ecran cible (1, 2, ...)")
    parser.add_argument("--other-screen", type=str, help="Deplacer vers l'autre ecran")
    parser.add_argument("--close", type=str, help="Fermer une fenetre")
    parser.add_argument("--minimize", type=str, help="Minimiser une fenetre")
    parser.add_argument("--maximize", type=str, help="Maximiser une fenetre")
    parser.add_argument("--tile", action="store_true", help="Carreler toutes les fenetres")
    parser.add_argument("--snap", type=str, help="Snap une fenetre (left/right/top/bottom/full)")
    parser.add_argument("--snap-target", type=str, help="Fenetre cible pour snap")
    args = parser.parse_args()

    if args.screens:
        monitors = get_monitors()
        for m in monitors:
            del m["handle"]
        print(json.dumps(monitors, indent=2, ensure_ascii=False))
        return

    if args.list:
        windows = get_all_windows()
        output = []
        for w in windows:
            output.append({
                "title": w["title"][:80],
                "pid": w["pid"],
                "screen": get_window_monitor(w["hwnd"]),
                "pos": f"{w['x']},{w['y']}",
                "size": f"{w['w']}x{w['h']}",
            })
        print(json.dumps(output, indent=2, ensure_ascii=False))
        return

    if args.tile:
        result = tile_windows()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    # Actions sur une fenetre specifique
    target_name = args.focus or args.move or args.close or args.minimize or args.maximize or args.other_screen or args.snap_target
    if not target_name and not args.snap:
        parser.print_help()
        return

    if args.snap and args.snap_target:
        target_name = args.snap_target

    if target_name:
        win = find_window(target_name)
        if not win:
            print(json.dumps({"error": f"Fenetre '{target_name}' non trouvee"}, ensure_ascii=False))
            sys.exit(1)

        result = {"window": win["title"][:60]}

        if args.focus:
            focus_window(win["hwnd"])
            result["action"] = "focused"
        elif args.move:
            if args.screen > 0:
                r = move_to_screen(win["hwnd"], args.screen)
                result.update(r)
                result["action"] = "moved"
            else:
                result["error"] = "Specifiez --screen N"
        elif args.other_screen:
            r = move_to_other_screen(win["hwnd"])
            result.update(r)
            result["action"] = "moved_other"
        elif args.close:
            close_window(win["hwnd"])
            result["action"] = "closed"
        elif args.minimize:
            minimize_window(win["hwnd"])
            result["action"] = "minimized"
        elif args.maximize:
            maximize_window(win["hwnd"])
            result["action"] = "maximized"

        if args.snap:
            r = snap_window(win["hwnd"], args.snap)
            result.update(r)
            result["action"] = "snapped"

        print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
