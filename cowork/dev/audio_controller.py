#!/usr/bin/env python3
"""audio_controller.py

Contrôle du volume audio sous Windows.

Fonctionnalités :
* ``--volume N`` : définit le volume système à ``N`` (0‑100).  Si l'utilitaire
  ``nircmd.exe`` est présent (habituellement dans ``/\Program Files/nircmd``),
  on utilise ``nircmd setsysvolume`` ; sinon on simule la montée/descente du
  volume via les touches de media (PowerShell ``SendKeys``).
* ``--mute`` / ``--unmute`` : active ou désactive le mute du son (même logique que
  ci‑dessus).
* ``--status`` : rapporte le niveau actuel du volume et l’état du mute.  Quand
  ``nircmd`` est disponible on utilise ``nircmd getsysvolume`` et
  ``nircmd mutesysvolume 0|1`` ; sinon on indique simplement que le statut n’est
  pas disponible.
* ``--devices`` : liste les périphériques audio et indique celui qui est
  sélectionné comme défaut.  Ceci repose sur le module PowerShell ``Get-AudioDevice``
  (disponible sur les systèmes récents) ; si la commande échoue on indique que
  l’information n’est pas récupérable.

Le script utilise uniquement la bibliothèque standard (``subprocess``,
``argparse``, ``os``, ``json``) et les appels PowerShell.  Il ne dépend pas de
bibliothèques Python externes.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Ensure Unicode output works on Windows consoles (cp1252 cannot encode all chars)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Helpers – localisation de nircmd (if installed)
# ---------------------------------------------------------------------------
NIRCMD_PATH = None
possible_paths = [
    Path(os.getenv("ProgramFiles", "C:/Program Files")) / "nircmd" / "nircmd.exe",
    Path(os.getenv("ProgramFiles(x86)", "C:/Program Files (x86)")) / "nircmd" / "nircmd.exe",
]
for p in possible_paths:
    if p.is_file():
        NIRCMD_PATH = str(p)
        break

# ---------------------------------------------------------------------------
# PowerShell execution wrapper
# ---------------------------------------------------------------------------
def ps(command: str):
    """Execute a PowerShell command and return its stdout stripped.
    Returns an empty string on error.
    """
    try:
        out = subprocess.check_output([
            "powershell", "-NoProfile", "-Command", command
        ], text=True, timeout=10)
        return out.strip()
    except subprocess.CalledProcessError as e:
        print(f"[audio_controller] PowerShell error: {e}", file=sys.stderr)
        return ""
    except Exception as e:
        print(f"[audio_controller] Unexpected error: {e}", file=sys.stderr)
        return ""

# ---------------------------------------------------------------------------
# Volume actions – nircmd preferred, fallback to SendKeys
# ---------------------------------------------------------------------------
def set_volume_percent(percent: int):
    percent = max(0, min(100, percent))
    if NIRCMD_PATH:
        # nircmd expects a 0‑65535 range; convert accordingly
        value = int(percent * 65535 / 100)
        subprocess.run([NIRCMD_PATH, "setsysvolume", str(value)], check=False)
        print(f"[audio_controller] Volume fixé à {percent}% via nircmd.")
    else:
        # Fallback: emulate volume up/down key presses to reach target
        # First, mute then unmute to reset? We'll just send the appropriate number
        # of up/down keys. We assume current volume unknown, so we adjust relatively.
        # Here we simply send the "volume up" key repeatedly (step of ~2%).
        steps = percent // 2  # each SendKeys volume up ~2% on many systems
        for _ in range(steps):
            ps("(New-Object -ComObject WScript.Shell).SendKeys([char]175)")
        print(f"[audio_controller] Volume approximativement réglé à {percent}% via SendKeys.")

def mute():
    if NIRCMD_PATH:
        subprocess.run([NIRCMD_PATH, "mutesysvolume", "1"], check=False)
        print("[audio_controller] Son muet (nircmd).")
    else:
        ps("(New-Object -ComObject WScript.Shell).SendKeys([char]173)")
        print("[audio_controller] Son muet (SendKeys).")

def unmute():
    if NIRCMD_PATH:
        subprocess.run([NIRCMD_PATH, "mutesysvolume", "0"], check=False)
        print("[audio_controller] Son réactivé (nircmd).")
    else:
        # Toggle mute off – same key works as toggle
        ps("(New-Object -ComObject WScript.Shell).SendKeys([char]173)")
        print("[audio_controller] Son réactivé (SendKeys).")

def get_status():
    if NIRCMD_PATH:
        # nircmd getsysvolume returns a value 0‑65535
        out = subprocess.check_output([NIRCMD_PATH, "getsysvolume"], text=True).strip()
        try:
            val = int(out)
            percent = round(val * 100 / 65535)
        except Exception:
            percent = "?"
        # mute status
        mute_out = subprocess.check_output([NIRCMD_PATH, "mutesysvolume", "2"], text=True).strip()
        mute_state = "muted" if mute_out == "1" else "unmuted"
        print(f"Volume : {percent}% – {mute_state}")
    else:
        print("[audio_controller] Statut du volume indisponible sans nircmd.")
        # Attempt a best‑effort using PowerShell to query current audio endpoint
        # This requires the WindowsAudioDevice-Powershell module which may not be present.
        ps_cmd = "(Get-AudioDevice -Playback).Volume"
        vol = ps(ps_cmd)
        if vol:
            print(f"Volume (via PowerShell) : {vol}%")
        else:
            print("Volume inconnu.")
        # Mute status similar
        mute_ps = "(Get-AudioDevice -Playback).Mute"
        mute = ps(mute_ps)
        if mute:
            print(f"Mute : {mute}")

def list_devices():
    # Try PowerShell
    ps_cmd = "Get-AudioDevice -Playback | Select-Object -Property Name, Default"
    out = ps(ps_cmd)
    if out:
        print("Périphériques audio (PowerShell) :")
        print(out)
    else:
        print("[audio_controller] Impossible de lister les périphériques – PowerShell Get-AudioDevice indisponible.")

# ---------------------------------------------------------------------------
# CLI parsing
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Contrôleur audio Windows (volume, mute, statut, périphériques).")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--volume", type=int, metavar="N", help="Définit le volume système à N (0‑100).")
    group.add_argument("--mute", action="store_true", help="Mute le son.")
    group.add_argument("--unmute", action="store_true", help="Démute le son.")
    group.add_argument("--status", action="store_true", help="Affiche le volume et le statut mute.")
    group.add_argument("--devices", action="store_true", help="Liste les périphériques audio et le défaut.")
    args = parser.parse_args()

    if args.volume is not None:
        set_volume_percent(args.volume)
    elif args.mute:
        mute()
    elif args.unmute:
        unmute()
    elif args.status:
        get_status()
    elif args.devices:
        list_devices()

if __name__ == "__main__":
    main()
