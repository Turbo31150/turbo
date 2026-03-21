#!/usr/bin/env python3
"""Disk space watcher — Check C: and F: free space, alert if <5GB, log to etoile.db."""
import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ETOILE_DB = Path("F:/BUREAU/turbo/etoile.db")
DRIVES = {"C:": "C:\\", "F:": "F:\\"}
ALERT_THRESHOLD_GB = 5.0
INTERVAL_SECONDS = 300  # 5 minutes


def get_disk_usage(path: str) -> dict:
    """Return disk usage info for a path."""
    try:
        st = os.statvfs(path) if hasattr(os, "statvfs") else None
    except (OSError, AttributeError):
        st = None
    # Windows fallback via shutil-free method
    import ctypes
    free_bytes = ctypes.c_ulonglong(0)
    total_bytes = ctypes.c_ulonglong(0)
    ctypes.windll.kernel32.GetDiskFreeSpaceExW(
        path, ctypes.byref(free_bytes), ctypes.byref(total_bytes), None
    )
    free_gb = free_bytes.value / (1024 ** 3)
    total_gb = total_bytes.value / (1024 ** 3)
    used_gb = total_gb - free_gb
    return {
        "total_gb": round(total_gb, 2),
        "used_gb": round(used_gb, 2),
        "free_gb": round(free_gb, 2),
        "pct_used": round((used_gb / total_gb) * 100, 1) if total_gb > 0 else 0,
    }


def log_to_db(drive: str, info: dict, alert: bool) -> None:
    """Log disk status to etoile.db cluster_health table."""
    if not ETOILE_DB.exists():
        return
    status = "ALERT" if alert else "OK"
    model = f"free={info['free_gb']}GB used={info['pct_used']}%"
    ts = datetime.now(timezone.utc).isoformat()
    try:
        conn = sqlite3.connect(str(ETOILE_DB), timeout=5)
        conn.execute(
            "INSERT INTO cluster_health (timestamp, node, status, model, latency_ms) "
            "VALUES (?, ?, ?, ?, ?)",
            (ts, f"disk_{drive}", status, model, 0),
        )
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        print(f"[WARN] DB error: {e}", file=sys.stderr)


def check_all() -> dict:
    """Check all drives and return results."""
    results = {}
    alerts = []
    for name, path in DRIVES.items():
        if not os.path.exists(path):
            results[name] = {"status": "MISSING"}
            continue
        info = get_disk_usage(path)
        alert = info["free_gb"] < ALERT_THRESHOLD_GB
        info["alert"] = alert
        results[name] = info
        log_to_db(name, info, alert)
        if alert:
            alerts.append(f"{name} LOW: {info['free_gb']}GB free")
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "drives": results,
        "alerts": alerts,
        "status": "ALERT" if alerts else "OK",
    }


def run_loop(once: bool) -> None:
    """Main loop or single check."""
    while True:
        result = check_all()
        print(json.dumps(result, indent=2))
        if result["alerts"]:
            for a in result["alerts"]:
                print(f"[ALERT] {a}", file=sys.stderr)
        if once:
            break
        time.sleep(INTERVAL_SECONDS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Disk space watcher for C: and F:")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--threshold", type=float, default=5.0, help="Alert threshold in GB")
    args = parser.parse_args()
    global ALERT_THRESHOLD_GB
    ALERT_THRESHOLD_GB = args.threshold
    run_loop(args.once)


if __name__ == "__main__":
    main()
