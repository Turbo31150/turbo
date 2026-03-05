#!/usr/bin/env python3
"""smart_launcher.py

Lanceur d'applications Windows intelligent.

Fonctionnalités :
* **--launch APP** – si l'application nommée (ex. ``chrome``) est déjà en cours d'exécution,
  le script la met au premier plan (focus) ; sinon il la lance via ``Start-Process``.
* **--list** – affiche la table de correspondance (nom logique → executable/path).
* **--running** – liste les applications de la table qui sont actuellement actives (via ``Get-Process``).
* **--kill APP** – arrête l'application (``Stop-Process``) si elle est en cours.

Le mapping supporte plus de 20 programmes courants (Chrome, VS Code, Terminal,
Discord, Spotify, Steam, etc.).  Le script utilise uniquement la bibliothèque
standard : ``subprocess``, ``argparse`` et ``json`` pour la configuration.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Mapping des applications – clé = nom logique, valeur = exécutable ou chemin complet
# ---------------------------------------------------------------------------
APP_MAP = {
    "chrome": "chrome",  # relies on PATH or default install location
    "vscode": "code",   # VS Code command line
    "terminal": "powershell",  # opens a new PowerShell window
    "discord": "discord",  # assumes discord is on PATH
    "spotify": "spotify",  # Spotify client
    "steam": "steam",      # Steam client
    "postman": "postman",  # Postman API client
    "notepad": "notepad.exe",
    "explorer": "explorer.exe",
    "calc": "calc.exe",
    "paint": "mspaint.exe",
    "edge": "msedge.exe",
    "firefox": "firefox.exe",
    "zoom": "Zoom\Zoom.exe",
    "slack": "slack.exe",
    "teams": "Teams.exe",
    "telegram": "Telegram.exe",
    "obs": "obs64.exe",
    "gitbash": "C:/Program Files/Git/git-bash.exe",
    "sublime": "subl.exe",
    "pycharm": "C:/Program Files/JetBrains/PyCharm Community Edition 2023.2.2/bin/pycharm64.exe",
    "docker": "Docker Desktop.exe",
    "mongodb": "C:/Program Files/MongoDB/Server/7.0/bin/mongod.exe",
    "node": "node.exe",
    "python": "python.exe",
    "vlc": "vlc.exe",
}

# ---------------------------------------------------------------------------
# PowerShell helpers – run a command and return stdout stripped
# ---------------------------------------------------------------------------
def ps(command: str):
    try:
        result = subprocess.check_output([
            "powershell", "-NoProfile", "-Command", command
        ], text=True, timeout=10)
        return result.strip()
    except Exception as e:
        print(f"[smart_launcher] PowerShell error : {e}", file=sys.stderr)
        return ""

# ---------------------------------------------------------------------------
# Application state helpers
# ---------------------------------------------------------------------------
def is_running(app_name: str) -> bool:
    """Return True if a process with the given executable name is running.
    ``app_name`` should be the executable part (e.g. ``chrome.exe`` or ``chrome``).
    """
    proc_list = ps("Get-Process | Select-Object -ExpandProperty ProcessName")
    # PowerShell returns names without .exe extension
    running = [p.lower() for p in proc_list.splitlines() if p]
    target = Path(app_name).stem.lower()
    return target in running

def focus_app(app_name: str):
    """Bring the first matching window to the foreground.
    Uses ``(New-Object -ComObject Shell.Application).Windows()`` to iterate.
    """
    script = (
        "$shell = New-Object -ComObject Shell.Application; "
        "$wins = $shell.Windows(); "
        "foreach ($w in $wins) { "
        "  if ($w.Document.title -and $w.LocationName -match '{}' ) { "
        "    $w.Visible = $true; "
        "    $w.Focus(); "
        "    break; "
        "  } "
        "}" 
    ).format(app_name)
    ps(script)

def launch_app(exec_name: str):
    # Use Start-Process; if exec_name contains a path with spaces, quote it.
    ps(f"Start-Process \"{exec_name}\"")

def kill_app(app_name: str):
    ps(f"Stop-Process -Name '{app_name}' -Force -ErrorAction SilentlyContinue")

# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------
def cmd_list():
    print("Applications disponibles :")
    for key, exe in sorted(APP_MAP.items()):
        print(f"  {key:<12} → {exe}")

def cmd_running():
    print("Applications en cours d'exécution :")
    for key, exe in APP_MAP.items():
        if is_running(exe):
            print(f"  {key}")

def cmd_launch(app_key: str):
    if app_key not in APP_MAP:
        print(f"[smart_launcher] Application inconnue : {app_key}")
        sys.exit(1)
    exe = APP_MAP[app_key]
    if is_running(exe):
        print(f"[smart_launcher] {app_key} déjà lancé – mise au premier plan.")
        focus_app(app_key)
    else:
        print(f"[smart_launcher] Lancement de {app_key} ({exe}) …")
        launch_app(exe)

def cmd_kill(app_key: str):
    if app_key not in APP_MAP:
        print(f"[smart_launcher] Application inconnue : {app_key}")
        sys.exit(1)
    exe = APP_MAP[app_key]
    if is_running(exe):
        print(f"[smart_launcher] Arrêt de {app_key} …")
        kill_app(exe)
    else:
        print(f"[smart_launcher] {app_key} n'est pas en cours d'exécution.")

def main():
    parser = argparse.ArgumentParser(description="Lanceur intelligent d'applications Windows.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="Lister les applications connues")
    group.add_argument("--running", action="store_true", help="Lister les applications connues qui sont déjà en cours")
    group.add_argument("--launch", metavar="APP", help="Lancer ou focuser l'application donnée")
    group.add_argument("--kill", metavar="APP", help="Arrêter l'application donnée")
    args = parser.parse_args()

    if args.list:
        cmd_list()
    elif args.running:
        cmd_running()
    elif args.launch:
        cmd_launch(args.launch.lower())
    elif args.kill:
        cmd_kill(args.kill.lower())

if __name__ == "__main__":
    main()
