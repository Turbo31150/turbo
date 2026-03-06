#!/usr/bin/env python3
"""scheduled_task_creator.py

Créateur de tâches planifiées Windows via schtasks.

CLI :
    --create NAME --command CMD --trigger TYPE [--time HH:MM] [--interval MIN]
    --list              : Lister les tâches JARVIS
    --delete NAME       : Supprimer une tâche
    --run NAME          : Exécuter immédiatement une tâche
    --status NAME       : État d'une tâche
"""

import argparse
import subprocess
import sys
from typing import List

TELEGRAM_TOKEN = "8369376863:AAF-7YGDbun8mXWwqYJFj-eX6P78DeIu9Aw"
TELEGRAM_CHAT_ID = "2010747443"
TASK_PREFIX = "JARVIS_"

def telegram_send(msg: str):
    import urllib.parse, urllib.request
    try:
        data = urllib.parse.urlencode({"chat_id": TELEGRAM_CHAT_ID, "text": msg}).encode()
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=10)
    except Exception:
        pass

def run_cmd(cmd: List[str], timeout: int = 15) -> str:
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT, timeout=timeout).strip()
    except subprocess.CalledProcessError as e:
        return e.output.strip() if e.output else ""
    except Exception:
        return ""

# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
def create_task(name: str, command: str, trigger: str, time_str: str = None, interval: int = None):
    full_name = f"{TASK_PREFIX}{name}"
    cmd = ["schtasks", "/Create", "/TN", full_name, "/TR", command, "/F"]

    if trigger == "daily":
        cmd += ["/SC", "DAILY"]
        if time_str:
            cmd += ["/ST", time_str]
    elif trigger == "hourly":
        cmd += ["/SC", "MINUTE", "/MO", str(interval or 60)]
    elif trigger == "minute":
        cmd += ["/SC", "MINUTE", "/MO", str(interval or 5)]
    elif trigger == "startup":
        cmd += ["/SC", "ONSTART"]
    elif trigger == "logon":
        cmd += ["/SC", "ONLOGON"]
    else:
        print(f"[scheduled_task_creator] Trigger inconnu : {trigger}")
        return

    out = run_cmd(cmd)
    if "SUCCESS" in out.upper() or "succès" in out.lower():
        print(f"[scheduled_task_creator] Tâche '{full_name}' créée.")
        telegram_send(f"📅 Tâche planifiée créée : {full_name} ({trigger})")
    else:
        print(f"[scheduled_task_creator] Erreur : {out}")

# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------
def list_tasks():
    out = run_cmd(["schtasks", "/Query", "/FO", "TABLE", "/NH"])
    jarvis_tasks = []
    for line in out.splitlines():
        if TASK_PREFIX in line:
            jarvis_tasks.append(line.strip())
    if not jarvis_tasks:
        print("[scheduled_task_creator] Aucune tâche JARVIS trouvée.")
        return
    print(f"Tâches planifiées JARVIS ({len(jarvis_tasks)}) :")
    for t in jarvis_tasks:
        parts = t.split()
        name = parts[0] if parts else t
        status = parts[-1] if len(parts) > 1 else "?"
        print(f"  📅 {name} — {status}")

# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------
def delete_task(name: str):
    full_name = f"{TASK_PREFIX}{name}" if not name.startswith(TASK_PREFIX) else name
    out = run_cmd(["schtasks", "/Delete", "/TN", full_name, "/F"])
    if "SUCCESS" in out.upper() or "succès" in out.lower():
        print(f"[scheduled_task_creator] Tâche '{full_name}' supprimée.")
    else:
        print(f"[scheduled_task_creator] Erreur : {out}")

# ---------------------------------------------------------------------------
# Run now
# ---------------------------------------------------------------------------
def run_task(name: str):
    full_name = f"{TASK_PREFIX}{name}" if not name.startswith(TASK_PREFIX) else name
    out = run_cmd(["schtasks", "/Run", "/TN", full_name])
    if "SUCCESS" in out.upper() or "succès" in out.lower():
        print(f"[scheduled_task_creator] Tâche '{full_name}' lancée.")
    else:
        print(f"[scheduled_task_creator] Erreur : {out}")

# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------
def task_status(name: str):
    full_name = f"{TASK_PREFIX}{name}" if not name.startswith(TASK_PREFIX) else name
    out = run_cmd(["schtasks", "/Query", "/TN", full_name, "/V", "/FO", "LIST"])
    if out:
        print(out)
    else:
        print(f"[scheduled_task_creator] Tâche '{full_name}' introuvable.")

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Créateur de tâches planifiées Windows.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_create = sub.add_parser("create", help="Créer une tâche")
    p_create.add_argument("name", help="Nom de la tâche")
    p_create.add_argument("--cmd", required=True, help="Commande à exécuter")
    p_create.add_argument("--trigger", required=True, choices=["daily", "hourly", "minute", "startup", "logon"])
    p_create.add_argument("--time", help="Heure (HH:MM) pour trigger daily")
    p_create.add_argument("--interval", type=int, help="Intervalle en minutes")

    p_list = sub.add_parser("list", help="Lister les tâches JARVIS")

    p_delete = sub.add_parser("delete", help="Supprimer une tâche")
    p_delete.add_argument("name", help="Nom de la tâche")

    p_run = sub.add_parser("run", help="Exécuter une tâche")
    p_run.add_argument("name", help="Nom de la tâche")

    p_status = sub.add_parser("status", help="État d'une tâche")
    p_status.add_argument("name", help="Nom de la tâche")

    args = parser.parse_args()

    if args.command == "create":
        create_task(args.name, args.cmd, args.trigger, args.time, args.interval)
    elif args.command == "list":
        list_tasks()
    elif args.command == "delete":
        delete_task(args.name)
    elif args.command == "run":
        run_task(args.name)
    elif args.command == "status":
        task_status(args.name)

if __name__ == "__main__":
    main()
