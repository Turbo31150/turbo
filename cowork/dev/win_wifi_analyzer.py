#!/usr/bin/env python3
"""win_wifi_analyzer.py — Analyseur WiFi Windows.

Scan reseaux, force signal, canaux, optimisation.

Usage:
    python dev/win_wifi_analyzer.py --once
    python dev/win_wifi_analyzer.py --scan
    python dev/win_wifi_analyzer.py --signal
    python dev/win_wifi_analyzer.py --channels
"""
import argparse
import json
import os
import re
import sqlite3
import subprocess
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "wifi_analyzer.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS wifi_scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, ssid TEXT, signal_pct INTEGER,
        channel INTEGER, auth TEXT)""")
    db.commit()
    return db


def get_current_connection():
    try:
        out = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True, text=True, timeout=10
        )
        info = {}
        for line in out.stdout.split("\n"):
            if ":" in line:
                parts = line.split(":", 1)
                key = parts[0].strip().lower()
                val = parts[1].strip()
                if "ssid" in key and "bssid" not in key:
                    info["ssid"] = val
                elif "signal" in key:
                    info["signal"] = val
                elif "channel" in key:
                    info["channel"] = val
                elif "receive" in key or "transmit" in key:
                    info[key.replace(" ", "_")] = val
        return info
    except Exception:
        return {}


def scan_networks():
    networks = []
    try:
        out = subprocess.run(
            ["netsh", "wlan", "show", "networks", "mode=bssid"],
            capture_output=True, text=True, timeout=15
        )
        current = {}
        for line in out.stdout.split("\n"):
            line = line.strip()
            if line.startswith("SSID") and "BSSID" not in line:
                if current.get("ssid"):
                    networks.append(current)
                current = {"ssid": line.split(":", 1)[1].strip() if ":" in line else ""}
            elif "Signal" in line:
                m = re.search(r"(\d+)%", line)
                current["signal_pct"] = int(m.group(1)) if m else 0
            elif "Channel" in line:
                m = re.search(r"(\d+)", line.split(":", 1)[1])
                current["channel"] = int(m.group(1)) if m else 0
            elif "Authentication" in line or "Authentification" in line:
                current["auth"] = line.split(":", 1)[1].strip() if ":" in line else ""
        if current.get("ssid"):
            networks.append(current)
    except Exception:
        pass
    return networks


def do_scan():
    db = init_db()
    current = get_current_connection()
    networks = scan_networks()

    for n in networks:
        db.execute("INSERT INTO wifi_scans (ts, ssid, signal_pct, channel, auth) VALUES (?,?,?,?,?)",
                   (time.time(), n.get("ssid", ""), n.get("signal_pct", 0),
                    n.get("channel", 0), n.get("auth", "")))

    channels = Counter(n.get("channel", 0) for n in networks if n.get("channel"))
    congested = [ch for ch, cnt in channels.items() if cnt > 2]

    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "current_connection": current,
        "networks_found": len(networks),
        "networks": sorted(networks, key=lambda x: x.get("signal_pct", 0), reverse=True)[:15],
        "channel_usage": dict(channels.most_common(10)),
        "congested_channels": congested,
    }


def main():
    parser = argparse.ArgumentParser(description="Windows WiFi Analyzer")
    parser.add_argument("--once", "--scan", action="store_true", help="Scan networks")
    parser.add_argument("--signal", action="store_true", help="Signal strength")
    parser.add_argument("--channels", action="store_true", help="Channel analysis")
    parser.add_argument("--optimize", action="store_true", help="Optimize")
    args = parser.parse_args()
    print(json.dumps(do_scan(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
