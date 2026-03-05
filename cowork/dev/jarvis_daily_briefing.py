#!/usr/bin/env python3
"""jarvis_daily_briefing.py — Genere un briefing quotidien complet.

Collecte infos (cluster, trading, systeme), genere resume via M1,
envoie sur Telegram.

Usage:
    python dev/jarvis_daily_briefing.py --once
    python dev/jarvis_daily_briefing.py --generate
    python dev/jarvis_daily_briefing.py --send
    python dev/jarvis_daily_briefing.py --history
"""
import argparse
import json
import os
import sqlite3
import subprocess
import time
import urllib.request
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "daily_briefing.db"
WS_URL = "http://127.0.0.1:9742"
OL1_URL = "http://127.0.0.1:11434"
M1_URL = "http://127.0.0.1:1234"
TELEGRAM_PROXY = "http://127.0.0.1:18800"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS briefings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, briefing TEXT, sent INTEGER DEFAULT 0)""")
    db.commit()
    return db


def collect_cluster_status():
    """Collect cluster health."""
    nodes = {}
    for name, url in [("OL1", f"{OL1_URL}/api/tags"), ("M1", f"{M1_URL}/api/v1/models")]:
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=3) as r:
                nodes[name] = "ONLINE"
        except Exception:
            nodes[name] = "OFFLINE"
    return nodes


def collect_autonomous_status():
    """Collect autonomous loop status."""
    try:
        req = urllib.request.Request(f"{WS_URL}/api/autonomous/status")
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode())
            tasks = data.get("tasks", {})
            ok = sum(1 for t in tasks.values() if isinstance(t, dict) and t.get("fail_count", 0) <= 3)
            return {"tasks_ok": ok, "total": len(tasks)}
    except Exception:
        return {"tasks_ok": 0, "total": 0}


def collect_gpu_status():
    """Collect GPU info."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu,memory.used,memory.total,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            gpus = []
            for line in result.stdout.strip().split("\n"):
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 4:
                    gpus.append({
                        "temp": int(parts[0]), "vram_used": int(parts[1]),
                        "vram_total": int(parts[2]), "load": int(parts[3]),
                    })
            return gpus
    except Exception:
        pass
    return []


def collect_disk_status():
    """Collect disk free space."""
    import shutil
    disks = {}
    for drive in ["C:", "F:"]:
        try:
            usage = shutil.disk_usage(drive + "\\")
            disks[drive] = {"free_gb": round(usage.free / (1024**3), 1), "total_gb": round(usage.total / (1024**3), 1)}
        except Exception:
            pass
    return disks


def generate_briefing():
    """Generate the daily briefing."""
    now = datetime.now()
    cluster = collect_cluster_status()
    autonomous = collect_autonomous_status()
    gpus = collect_gpu_status()
    disks = collect_disk_status()

    lines = [f"**JARVIS Briefing — {now.strftime('%d/%m/%Y %H:%M')}**\n"]

    # Cluster
    cluster_str = ", ".join(f"{k}: {v}" for k, v in cluster.items())
    lines.append(f"**Cluster**: {cluster_str}")

    # Autonomous
    lines.append(f"**Taches autonomes**: {autonomous['tasks_ok']}/{autonomous['total']} OK")

    # GPU
    if gpus:
        for i, gpu in enumerate(gpus):
            lines.append(f"**GPU {i}**: {gpu['temp']}C, VRAM {gpu['vram_used']}/{gpu['vram_total']}MB, Load {gpu['load']}%")

    # Disks
    for drive, info in disks.items():
        lines.append(f"**{drive}**: {info['free_gb']}GB free / {info['total_gb']}GB")

    # Dev scripts count
    dev_count = len(list(DEV.glob("*.py")))
    lines.append(f"**Scripts dev/**: {dev_count}")

    return "\n".join(lines)


def send_telegram(text):
    """Send briefing via Telegram."""
    try:
        data = json.dumps({"text": text}).encode()
        req = urllib.request.Request(
            f"{TELEGRAM_PROXY}/chat", data=data,
            headers={"Content-Type": "application/json"}, method="POST"
        )
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception:
        return False


def do_once():
    """Generate and optionally send briefing."""
    db = init_db()
    briefing = generate_briefing()

    db.execute("INSERT INTO briefings (ts, briefing) VALUES (?,?)", (time.time(), briefing))
    db.commit()
    db.close()
    return {"briefing": briefing}


def do_send():
    """Generate and send briefing."""
    db = init_db()
    briefing = generate_briefing()
    sent = send_telegram(briefing)

    db.execute("INSERT INTO briefings (ts, briefing, sent) VALUES (?,?,?)",
               (time.time(), briefing, int(sent)))
    db.commit()
    db.close()
    return {"briefing": briefing, "sent": sent}


def main():
    parser = argparse.ArgumentParser(description="JARVIS Daily Briefing")
    parser.add_argument("--once", "--generate", action="store_true", help="Generate briefing")
    parser.add_argument("--send", action="store_true", help="Generate + send Telegram")
    parser.add_argument("--history", action="store_true", help="Past briefings")
    args = parser.parse_args()

    if args.send:
        result = do_send()
    else:
        result = do_once()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
