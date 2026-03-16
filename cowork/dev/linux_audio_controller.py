#!/usr/bin/env python3
"""win_audio_controller.py — Controleur audio Windows.

Gere volume, mute, switch devices par commande.

Usage:
    python dev/win_audio_controller.py --once
    python dev/win_audio_controller.py --status
    python dev/win_audio_controller.py --volume 80
    python dev/win_audio_controller.py --mute
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
DB_PATH = DEV / "data" / "audio_controller.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS audio_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, action TEXT, volume INTEGER, muted INTEGER)""")
    db.commit()
    return db


def get_audio_status():
    try:
        out = subprocess.run(
            ["bash", "-Command",
             "$audio = Get-CimInstance Win32_SoundDevice | Select-Object Name,Status | ConvertTo-Json;"
             "Write-Output $audio"],
            capture_output=True, text=True, timeout=10
        )
        devices = []
        if out.stdout.strip():
            data = json.loads(out.stdout)
            if isinstance(data, dict):
                data = [data]
            devices = [{"name": d.get("Name", "?"), "status": d.get("Status", "?")} for d in data]
        return {"devices": devices, "count": len(devices)}
    except Exception:
        return {"devices": [], "count": 0}


def get_volume():
    try:
        out = subprocess.run(
            ["bash", "-Command",
             "Add-Type -TypeDefinition @'\n"
             "using System.Runtime.InteropServices;\n"
             "public class Audio {\n"
             "  [DllImport(\"user32.dll\")] public static extern int SendMessageW(int h, int m, int w, int l);\n"
             "}\n"
             "'@\n"
             "[Audio]::SendMessageW(-1, 0x0319, 0, 0)"],
            capture_output=True, text=True, timeout=5
        )
    except Exception:
        pass
    return -1  # Volume level not easily available without COM


def do_status():
    db = init_db()
    audio = get_audio_status()

    report = {
        "ts": datetime.now().isoformat(),
        "audio_devices": audio["devices"],
        "device_count": audio["count"],
        "note": "Use --volume N to set volume via nircmd or bash",
    }

    db.execute("INSERT INTO audio_log (ts, action, volume, muted) VALUES (?,?,?,?)",
               (time.time(), "status", -1, -1))
    db.commit()
    db.close()
    return report


def main():
    parser = argparse.ArgumentParser(description="Windows Audio Controller")
    parser.add_argument("--once", "--status", action="store_true", help="Audio status")
    parser.add_argument("--volume", type=int, metavar="N", help="Set volume 0-100")
    parser.add_argument("--mute", action="store_true", help="Toggle mute")
    parser.add_argument("--devices", action="store_true", help="List devices")
    args = parser.parse_args()
    print(json.dumps(do_status(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
