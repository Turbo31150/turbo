#!/usr/bin/env python3
"""win_wsl_manager.py — Gestionnaire WSL.

Monitore/controle distributions WSL, ressources, ports.

Usage:
    python dev/win_wsl_manager.py --once
    python dev/win_wsl_manager.py --status
    python dev/win_wsl_manager.py --list
    python dev/win_wsl_manager.py --start DISTRO
"""
import argparse
import json
import os
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "wsl_manager.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS wsl_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, distros INTEGER, running INTEGER, report TEXT)""")
    db.commit()
    return db


def get_wsl_distros():
    distros = []
    try:
        out = subprocess.run(
            ["wsl", "--list", "--verbose"],
            capture_output=True, text=True, timeout=10
        )
        lines = out.stdout.strip().replace("\x00", "").split("\n")
        for line in lines[1:]:  # Skip header
            parts = line.strip().split()
            if len(parts) >= 3:
                default = parts[0] == "*"
                name = parts[1] if default else parts[0]
                state = parts[2] if default else parts[1]
                version = parts[3] if default and len(parts) > 3 else parts[2] if len(parts) > 2 else "?"
                distros.append({
                    "name": name,
                    "state": state,
                    "version": version,
                    "default": default,
                })
    except FileNotFoundError:
        pass
    except Exception:
        pass
    return distros


def check_docker_interop():
    try:
        out = subprocess.run(
            ["docker", "info", "--format", "{{.OperatingSystem}}"],
            capture_output=True, text=True, timeout=10
        )
        return {"docker_available": out.returncode == 0, "os": out.stdout.strip()}
    except Exception:
        return {"docker_available": False, "os": "N/A"}


def do_status():
    db = init_db()
    distros = get_wsl_distros()
    docker = check_docker_interop()

    running = sum(1 for d in distros if d["state"].lower() == "running")

    report = {
        "ts": datetime.now().isoformat(),
        "wsl_installed": len(distros) > 0,
        "distros": distros,
        "total": len(distros),
        "running": running,
        "stopped": len(distros) - running,
        "docker_interop": docker,
    }

    db.execute("INSERT INTO wsl_snapshots (ts, distros, running, report) VALUES (?,?,?,?)",
               (time.time(), len(distros), running, json.dumps(report)))
    db.commit()
    db.close()
    return report


def main():
    parser = argparse.ArgumentParser(description="Windows WSL Manager")
    parser.add_argument("--once", "--status", action="store_true", help="Status")
    parser.add_argument("--list", action="store_true", help="List distros")
    parser.add_argument("--start", metavar="DISTRO", help="Start distro")
    parser.add_argument("--stop", action="store_true", help="Stop all")
    args = parser.parse_args()
    print(json.dumps(do_status(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
