#!/usr/bin/env python3
"""service_watcher.py

Surveillance des services Windows critiques.

Fonctionnalités :
* Vérifie que les services listés (par défaut : ``Ollama``, ``LMStudio`` et ``OpenClaw``)
  sont en cours d'exécution.
* En mode ``--watch`` (boucle de 60 s) le script relance automatiquement tout service
  qui serait arrêté.
* ``--status`` : affiche l'état actuel de chaque service.
* ``--restart SERVICE`` : redémarre le service indiqué immédiatement.
* ``--history`` : montre l'historique des contrôles/restarts (SQLite
  ``services.db``).

Une configuration JSON optionnelle ``service_watcher_config.json`` peut être placée
dans le même répertoire pour définir la liste des services à surveiller :
```
{
    "services": ["Ollama", "LMStudio", "OpenClaw"]
}
```
Si le fichier n'existe pas, la liste par défaut ci‑dessus est utilisée.

Le script utilise uniquement la bibliothèque standard : ``subprocess``, ``sqlite3``,
``json``, ``argparse`` et ``datetime``.
"""

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DEFAULT_SERVICES = ["Ollama", "LMStudio", "OpenClaw"]
CONFIG_FILE = Path(__file__).with_name("service_watcher_config.json")
DB_PATH = Path(__file__).with_name("services.db")

def load_config() -> List[str]:
    if CONFIG_FILE.is_file():
        try:
            with CONFIG_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
                services = data.get("services")
                if isinstance(services, list):
                    return [str(s) for s in services]
        except Exception as e:
            print(f"[service_watcher] Erreur de lecture du config : {e}", file=sys.stderr)
    return DEFAULT_SERVICES

# ---------------------------------------------------------------------------
# SQLite helpers
# ---------------------------------------------------------------------------

def init_db(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            service TEXT NOT NULL,
            status TEXT NOT NULL,   -- "running" / "stopped"
            action TEXT NOT NULL    -- "check" / "restart"
        )
        """
    )
    conn.commit()

def insert_log(conn: sqlite3.Connection, service: str, status: str, action: str):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO logs (ts, service, status, action) VALUES (?,?,?,?)",
        (datetime.utcnow().isoformat() + "Z", service, status, action),
    )
    conn.commit()

def fetch_history(conn: sqlite3.Connection, limit: int = 20):
    cur = conn.cursor()
    cur.execute("SELECT ts, service, status, action FROM logs ORDER BY ts DESC LIMIT ?", (limit,))
    return cur.fetchall()

# ---------------------------------------------------------------------------
# PowerShell helpers – service status & restart
# ---------------------------------------------------------------------------

def ps(command: str) -> str:
    """Run a PowerShell command and return stripped stdout. Errors return empty string."""
    try:
        out = subprocess.check_output([
            "bash", "-NoProfile", "-Command", command
        ], text=True, timeout=15)
        return out.strip()
    except subprocess.CalledProcessError as e:
        # PowerShell errors end up here; we treat as empty result
        return ""
    except Exception:
        return ""

def get_service_status(name: str) -> str:
    # Returns "running" or "stopped"
    cmd = f"Get-Service -Name '{name}' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Status"
    out = ps(cmd)
    if out.lower() == "running":
        return "running"
    else:
        return "stopped"

def restart_service(name: str) -> bool:
    cmd = f"Restart-Service -Name '{name}' -Force -ErrorAction SilentlyContinue"
    out = ps(cmd)
    # No output on success; we verify by checking new status
    time.sleep(2)  # brief pause for service to come up
    return get_service_status(name) == "running"

# ---------------------------------------------------------------------------
# Core checking logic
# ---------------------------------------------------------------------------

def check_services(services: List[str], conn: sqlite3.Connection, auto_restart: bool = False):
    for srv in services:
        status = get_service_status(srv)
        insert_log(conn, srv, status, "check")
        print(f"[service_watcher] {srv}: {status}")
        if status != "running" and auto_restart:
            print(f"[service_watcher] Tentative de redémarrage de {srv}…")
            ok = restart_service(srv)
            new_status = "running" if ok else "stopped"
            insert_log(conn, srv, new_status, "restart")
            print(f"[service_watcher] {srv} après redémarrage : {new_status}")

# ---------------------------------------------------------------------------
# CLI actions
# ---------------------------------------------------------------------------

def cmd_status(services: List[str]):
    conn = sqlite3.connect(str(DB_PATH))
    init_db(conn)
    check_services(services, conn, auto_restart=False)
    conn.close()

def cmd_restart(service_name: str, services: List[str]):
    if service_name not in services:
        print(f"[service_watcher] Service non configuré : {service_name}")
        return
    conn = sqlite3.connect(str(DB_PATH))
    init_db(conn)
    ok = restart_service(service_name)
    new_status = "running" if ok else "stopped"
    insert_log(conn, service_name, new_status, "restart")
    print(f"[service_watcher] {service_name} après redémarrage : {new_status}")
    conn.close()

def cmd_watch(services: List[str]):
    conn = sqlite3.connect(str(DB_PATH))
    init_db(conn)
    print("[service_watcher] Démarrage de la boucle de surveillance (60 s). Ctrl‑C pour arrêter.")
    try:
        while True:
            check_services(services, conn, auto_restart=True)
            time.sleep(60)
    except KeyboardInterrupt:
        print("[service_watcher] Surveillance interrompue par l'utilisateur.")
    finally:
        conn.close()

def cmd_history():
    conn = sqlite3.connect(str(DB_PATH))
    init_db(conn)
    rows = fetch_history(conn, limit=50)
    conn.close()
    if not rows:
        print("[service_watcher] Aucun historique disponible.")
        return
    for ts, svc, status, action in rows:
        print(f"{ts} – {svc} – {status} – {action}")

def main():
    parser = argparse.ArgumentParser(description="Surveillance des services critiques Windows.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--status", action="store_true", help="Afficher l'état actuel des services configurés")
    group.add_argument("--watch", action="store_true", help="Boucle de surveillance (vérifie chaque minute et redémarre si down)")
    group.add_argument("--restart", metavar="SERVICE", help="Redémarrer immédiatement le service indiqué")
    group.add_argument("--history", action="store_true", help="Afficher l'historique des contrôles/restarts")
    args = parser.parse_args()

    services = load_config()

    if args.status:
        cmd_status(services)
    elif args.watch:
        cmd_watch(services)
    elif args.restart:
        cmd_restart(args.restart, services)
    elif args.history:
        cmd_history()

if __name__ == "__main__":
    main()
