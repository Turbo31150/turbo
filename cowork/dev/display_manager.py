#!/usr/bin/env python3
"""display_manager.py

Gestionnaire d'écran Windows (résolution, luminosité, mode nuit/dark).

Fonctionnalités :
* ``--status`` – indique la résolution actuelle, le niveau de luminosité et l'état du mode nuit.
* ``--resolution WxH`` – modifie la résolution (ex. ``1920x1080``) via l'API Win32 (user32.dll).
* ``--brightness N`` – règle la luminosité (0‑100) à l'aide de WMI (classe ``WmiMonitorBrightnessMethods``).
* ``--night-mode on|off`` – active ou désactive le mode sombre du système en modifiant
  la clé de registre ``HKCU/Software/Microsoft/Windows/CurrentVersion/Themes/Personalize``.

Le script utilise uniquement la bibliothèque standard : ``subprocess``, ``argparse``, ``re``,
``ctypes`` et ``winreg``.  Les appels PowerShell sont exécutés via ``subprocess``.
"""

import argparse
import ctypes
import re
import subprocess
import sys
import winreg
from ctypes import wintypes

# Ensure Unicode output works on Windows consoles (cp1252 cannot encode all chars)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Helpers – PowerShell execution
# ---------------------------------------------------------------------------

def ps(command: str) -> str:
    """Execute a PowerShell command and return stripped stdout.
    Retourne une chaîne vide en cas d'erreur.
    """
    try:
        out = subprocess.check_output([
            "bash", "-NoProfile", "-Command", command
        ], text=True, timeout=15)
        return out.strip()
    except subprocess.CalledProcessError:
        return ""
    except Exception:
        return ""

# ---------------------------------------------------------------------------
# Status – résolution, luminosité, mode nuit
# ---------------------------------------------------------------------------

def get_resolution() -> str:
    # Utilise les API Win32 via ctypes pour récupérer la résolution du moniteur principal
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    SM_CXSCREEN = 0
    SM_CYSCREEN = 1
    width = user32.GetSystemMetrics(SM_CXSCREEN)
    height = user32.GetSystemMetrics(SM_CYSCREEN)
    return f"{width}x{height}"

def get_brightness() -> int:
    # WMI – retourne la valeur de luminosité actuelle (0-100)
    cmd = r"(Get-WmiObject -Namespace root\wmi -Class WmiMonitorBrightness).CurrentBrightness"
    out = ps(cmd)
    try:
        return int(out)
    except Exception:
        return -1

def get_night_mode() -> bool:
    # Registre – AppsUseLightTheme = 0 -> mode nuit (dark) activé
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            0,
            winreg.KEY_READ,
        ) as key:
            val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return val == 0
    except Exception:
        return False

def show_status():
    res = get_resolution()
    bright = get_brightness()
    night = get_night_mode()
    print(f"Résolution   : {res}")
    print(f"Luminosité  : {bright if bright >=0 else 'inconnu'} %")
    print(f"Mode nuit   : {'activé' if night else 'désactivé'}")

# ---------------------------------------------------------------------------
# Set resolution – via ChangeDisplaySettingsEx (user32)
# ---------------------------------------------------------------------------

class DEVMODE(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName", wintypes.WCHAR * 32),
        ("dmSpecVersion", wintypes.WORD),
        ("dmDriverVersion", wintypes.WORD),
        ("dmSize", wintypes.WORD),
        ("dmDriverExtra", wintypes.WORD),
        ("dmFields", wintypes.DWORD),
        ("dmOrientation", wintypes.SHORT),
        ("dmPaperSize", wintypes.SHORT),
        ("dmPaperLength", wintypes.SHORT),
        ("dmPaperWidth", wintypes.SHORT),
        ("dmScale", wintypes.SHORT),
        ("dmCopies", wintypes.SHORT),
        ("dmDefaultSource", wintypes.SHORT),
        ("dmPrintQuality", wintypes.SHORT),
        ("dmColor", wintypes.SHORT),
        ("dmDuplex", wintypes.SHORT),
        ("dmYResolution", wintypes.SHORT),
        ("dmTTOption", wintypes.SHORT),
        ("dmCollate", wintypes.SHORT),
        ("dmFormName", wintypes.WCHAR * 32),
        ("dmLogPixels", wintypes.WORD),
        ("dmBitsPerPel", wintypes.DWORD),
        ("dmPelsWidth", wintypes.DWORD),
        ("dmPelsHeight", wintypes.DWORD),
        ("dmDisplayFlags", wintypes.DWORD),
        ("dmDisplayFrequency", wintypes.DWORD),
        ("dmICMMethod", wintypes.DWORD),
        ("dmICMIntent", wintypes.DWORD),
        ("dmMediaType", wintypes.DWORD),
        ("dmDitherType", wintypes.DWORD),
        ("dmReserved1", wintypes.DWORD),
        ("dmReserved2", wintypes.DWORD),
        ("dmPanningWidth", wintypes.DWORD),
        ("dmPanningHeight", wintypes.DWORD),
    ]

    def __init__(self):
        super().__init__()
        self.dmSize = ctypes.sizeof(self)

def set_resolution(width: int, height: int):
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    CDS_UPDATEREGISTRY = 0x00000001
    DISP_CHANGE_SUCCESSFUL = 0
    dm = DEVMODE()
    dm.dmPelsWidth = width
    dm.dmPelsHeight = height
    dm.dmFields = 0x800000 | 0x400000  # DM_PELSWIDTH | DM_PELSHEIGHT
    result = user32.ChangeDisplaySettingsExW(None, ctypes.byref(dm), None, CDS_UPDATEREGISTRY, None)
    if result == DISP_CHANGE_SUCCESSFUL:
        print(f"[display_manager] Résolution changée en {width}x{height}.")
    else:
        print(f"[display_manager] Échec du changement de résolution (code {result}).")

# ---------------------------------------------------------------------------
# Set brightness via WMI method
# ---------------------------------------------------------------------------

def set_brightness(level: int):
    level = max(0, min(100, level))
    # WMI method – call SetBrightness on each monitor
    script = (
        r"$wmi = Get-WmiObject -Namespace root\wmi -Class WmiMonitorBrightnessMethods; "
        f"$wmi.WmiSetBrightness(1, {level})"
    )
    out = ps(script)
    if out is not None:
        print(f"[display_manager] Luminosité réglée à {level} %.")
    else:
        print("[display_manager] Échec du réglage de la luminosité.")

# ---------------------------------------------------------------------------
# Night mode – toggle dark theme via registry (AppsUseLightTheme)
# ---------------------------------------------------------------------------

def set_night_mode(enable: bool):
    value = 0 if enable else 1
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.SetValueEx(key, "AppsUseLightTheme", 0, winreg.REG_DWORD, value)
        # Also affect system theme (optional)
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.SetValueEx(key, "SystemUsesLightTheme", 0, winreg.REG_DWORD, value)
        state = "activé" if enable else "désactivé"
        print(f"[display_manager] Mode nuit {state} (dark theme).")
    except Exception as e:
        print(f"[display_manager] Erreur lors du changement du mode nuit : {e}")

# ---------------------------------------------------------------------------
# CLI handling
# ---------------------------------------------------------------------------

def parse_resolution(arg: str) -> tuple:
    m = re.match(r"^(\d+)[xX](\d+)$", arg)
    if not m:
        raise argparse.ArgumentTypeError("Le format doit être WxH, ex. 1920x1080")
    return int(m.group(1)), int(m.group(2))

def main():
    parser = argparse.ArgumentParser(description="Gestionnaire d'écran Windows (résolution, luminosité, mode nuit).")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--status", action="store_true", help="Afficher la configuration actuelle")
    group.add_argument("--resolution", type=parse_resolution, metavar="WxH", help="Définir la résolution (ex: 1920x1080)")
    group.add_argument("--brightness", type=int, metavar="N", help="Régler la luminosité (0‑100)")
    group.add_argument("--night-mode", choices=["on", "off"], help="Activer (on) ou désactiver (off) le mode nuit")
    args = parser.parse_args()

    if args.status:
        show_status()
    elif args.resolution:
        w, h = args.resolution
        set_resolution(w, h)
    elif args.brightness is not None:
        set_brightness(args.brightness)
    elif args.night_mode:
        set_night_mode(args.night_mode == "on")

if __name__ == "__main__":
    main()
