#!/usr/bin/env python3
"""win_pagefile_optimizer.py (#189) — Pagefile optimizer Windows 11.

Analyse l'utilisation du pagefile, recommande une taille optimale,
track l'historique des pics d'utilisation.

Usage:
    python dev/win_pagefile_optimizer.py --once
    python dev/win_pagefile_optimizer.py --analyze
    python dev/win_pagefile_optimizer.py --recommend
    python dev/win_pagefile_optimizer.py --set 8192
    python dev/win_pagefile_optimizer.py --history
"""
import argparse
import ctypes
import json
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "pagefile_optimizer.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS pagefile_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        allocated_mb INTEGER,
        current_usage_mb INTEGER,
        peak_usage_mb INTEGER,
        usage_ratio REAL,
        total_ram_mb INTEGER,
        available_ram_mb INTEGER,
        recommendation TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        action TEXT,
        old_size_mb INTEGER,
        new_size_mb INTEGER,
        success INTEGER
    )""")
    db.commit()
    return db


def get_ram_info():
    """Get total and available RAM using ctypes."""
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]
    mem = MEMORYSTATUSEX()
    mem.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
    return {
        "total_mb": round(mem.ullTotalPhys / (1024 * 1024)),
        "available_mb": round(mem.ullAvailPhys / (1024 * 1024)),
        "memory_load": mem.dwMemoryLoad,
        "total_pagefile_mb": round(mem.ullTotalPageFile / (1024 * 1024)),
        "available_pagefile_mb": round(mem.ullAvailPageFile / (1024 * 1024)),
    }


def get_pagefile_info():
    """Get pagefile info via wmic."""
    result = {"allocated_mb": 0, "current_usage_mb": 0, "peak_usage_mb": 0}
    try:
        out = subprocess.run(
            ["wmic", "pagefile", "get",
             "AllocatedBaseSize,CurrentUsage,PeakUsage", "/format:csv"],
            capture_output=True, text=True, timeout=15
        )
        if out.returncode == 0:
            lines = [l.strip() for l in out.stdout.strip().split("\n") if l.strip() and not l.startswith("Node")]
            for line in lines:
                parts = [p.strip() for p in line.split(",") if p.strip()]
                if len(parts) >= 4:
                    try:
                        result["allocated_mb"] = int(parts[1])
                        result["current_usage_mb"] = int(parts[2])
                        result["peak_usage_mb"] = int(parts[3])
                    except (ValueError, IndexError):
                        pass
    except Exception:
        pass

    # Fallback: use powershell if wmic returned 0
    if result["allocated_mb"] == 0:
        try:
            ps_cmd = (
                "Get-CimInstance Win32_PageFileUsage | "
                "Select-Object AllocatedBaseSize,CurrentUsage,PeakUsage | "
                "ConvertTo-Json"
            )
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=15
            )
            if out.returncode == 0 and out.stdout.strip():
                data = json.loads(out.stdout)
                if isinstance(data, list):
                    data = data[0]
                result["allocated_mb"] = int(data.get("AllocatedBaseSize", 0))
                result["current_usage_mb"] = int(data.get("CurrentUsage", 0))
                result["peak_usage_mb"] = int(data.get("PeakUsage", 0))
        except Exception:
            pass

    return result


def analyze(db):
    """Analyze current pagefile usage."""
    ram = get_ram_info()
    pf = get_pagefile_info()

    usage_ratio = round(pf["current_usage_mb"] / max(pf["allocated_mb"], 1), 3)

    recommendation = ""
    if usage_ratio > 0.8:
        recommendation = "CRITICAL: Pagefile usage >80%, increase size immediately"
    elif usage_ratio > 0.6:
        recommendation = "WARNING: Pagefile usage >60%, consider increasing"
    elif usage_ratio < 0.1 and pf["allocated_mb"] > ram["total_mb"]:
        recommendation = "INFO: Pagefile oversized for current workload, could reduce"
    else:
        recommendation = "OK: Pagefile usage within normal range"

    db.execute(
        """INSERT INTO pagefile_history
           (ts, allocated_mb, current_usage_mb, peak_usage_mb, usage_ratio,
            total_ram_mb, available_ram_mb, recommendation)
           VALUES (?,?,?,?,?,?,?,?)""",
        (time.time(), pf["allocated_mb"], pf["current_usage_mb"],
         pf["peak_usage_mb"], usage_ratio,
         ram["total_mb"], ram["available_mb"], recommendation)
    )
    db.commit()

    return {
        "status": "ok",
        "ram": {
            "total_mb": ram["total_mb"],
            "available_mb": ram["available_mb"],
            "used_mb": ram["total_mb"] - ram["available_mb"],
            "load_percent": ram["memory_load"]
        },
        "pagefile": {
            "allocated_mb": pf["allocated_mb"],
            "current_usage_mb": pf["current_usage_mb"],
            "peak_usage_mb": pf["peak_usage_mb"],
            "usage_ratio": usage_ratio
        },
        "recommendation": recommendation
    }


def recommend(db):
    """Recommend optimal pagefile size."""
    ram = get_ram_info()
    pf = get_pagefile_info()
    total_ram_gb = ram["total_mb"] / 1024

    # Recommendation logic
    if total_ram_gb <= 8:
        recommended_mb = ram["total_mb"] * 2
        reason = "RAM <= 8GB: pagefile = 2x RAM"
    elif total_ram_gb <= 16:
        recommended_mb = int(ram["total_mb"] * 1.5)
        reason = "RAM <= 16GB: pagefile = 1.5x RAM"
    elif total_ram_gb <= 32:
        recommended_mb = ram["total_mb"]
        reason = "RAM <= 32GB: pagefile = 1x RAM"
    else:
        recommended_mb = 16384  # Fixed 16GB for >32GB RAM
        reason = "RAM > 32GB: fixed 16GB pagefile"

    # Adjust based on peak usage history
    peak_rows = db.execute(
        "SELECT MAX(peak_usage_mb) FROM pagefile_history"
    ).fetchone()
    historical_peak = peak_rows[0] if peak_rows[0] else 0

    if historical_peak > recommended_mb * 0.7:
        recommended_mb = int(historical_peak * 1.5)
        reason += f" (adjusted up: historical peak {historical_peak}MB)"

    # Min/max bounds
    recommended_mb = max(recommended_mb, 2048)
    recommended_mb = min(recommended_mb, 65536)

    change_needed = abs(pf["allocated_mb"] - recommended_mb) > 512

    return {
        "status": "ok",
        "current_allocated_mb": pf["allocated_mb"],
        "recommended_mb": recommended_mb,
        "recommended_gb": round(recommended_mb / 1024, 1),
        "reason": reason,
        "change_needed": change_needed,
        "ram_gb": round(total_ram_gb, 1),
        "historical_peak_mb": historical_peak,
        "command": f"python dev/win_pagefile_optimizer.py --set {recommended_mb}" if change_needed else "No change needed"
    }


def set_pagefile_size(db, size_mb):
    """Set pagefile size (requires admin)."""
    pf = get_pagefile_info()
    old_size = pf["allocated_mb"]

    # Check admin
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        is_admin = False

    if not is_admin:
        db.execute(
            "INSERT INTO actions (ts, action, old_size_mb, new_size_mb, success) VALUES (?,?,?,?,?)",
            (time.time(), "set_pagefile", old_size, size_mb, 0)
        )
        db.commit()
        return {
            "status": "error",
            "error": "Administrator privileges required to change pagefile size",
            "suggestion": "Run as administrator: runas /user:Administrator python dev/win_pagefile_optimizer.py --set " + str(size_mb)
        }

    # Set via wmic
    try:
        cmd = f"wmic pagefileset where name='//\pagefile.sys' set InitialSize={size_mb},MaximumSize={size_mb}"
        out = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        success = out.returncode == 0

        db.execute(
            "INSERT INTO actions (ts, action, old_size_mb, new_size_mb, success) VALUES (?,?,?,?,?)",
            (time.time(), "set_pagefile", old_size, size_mb, int(success))
        )
        db.commit()

        return {
            "status": "ok" if success else "error",
            "old_size_mb": old_size,
            "new_size_mb": size_mb,
            "applied": success,
            "note": "Reboot required for changes to take effect" if success else out.stderr
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def get_history(db, limit=20):
    """Get pagefile usage history."""
    rows = db.execute(
        """SELECT ts, allocated_mb, current_usage_mb, peak_usage_mb, usage_ratio,
                  total_ram_mb, recommendation
           FROM pagefile_history ORDER BY ts DESC LIMIT ?""", (limit,)
    ).fetchall()

    actions = db.execute(
        "SELECT ts, action, old_size_mb, new_size_mb, success FROM actions ORDER BY ts DESC LIMIT 10"
    ).fetchall()

    return {
        "status": "ok",
        "total_records": db.execute("SELECT COUNT(*) FROM pagefile_history").fetchone()[0],
        "history": [
            {
                "ts": datetime.fromtimestamp(r[0]).strftime("%Y-%m-%d %H:%M:%S"),
                "allocated_mb": r[1], "usage_mb": r[2], "peak_mb": r[3],
                "usage_ratio": r[4], "ram_mb": r[5], "recommendation": r[6]
            }
            for r in rows
        ],
        "actions": [
            {
                "ts": datetime.fromtimestamp(a[0]).strftime("%Y-%m-%d %H:%M:%S"),
                "action": a[1], "old_mb": a[2], "new_mb": a[3], "success": bool(a[4])
            }
            for a in actions
        ]
    }


def once(db):
    """Run once: analyze + recommend."""
    analysis = analyze(db)
    rec = recommend(db)
    return {
        "status": "ok",
        "mode": "once",
        "script": "win_pagefile_optimizer.py (#189)",
        "analysis": analysis,
        "recommendation": rec
    }


def main():
    parser = argparse.ArgumentParser(
        description="win_pagefile_optimizer.py (#189) — Pagefile optimizer Windows 11"
    )
    parser.add_argument("--analyze", action="store_true",
                        help="Analyze current pagefile usage")
    parser.add_argument("--recommend", action="store_true",
                        help="Recommend optimal pagefile size")
    parser.add_argument("--set", type=int, metavar="SIZE",
                        help="Set pagefile size in MB (requires admin)")
    parser.add_argument("--history", action="store_true",
                        help="Show pagefile usage history")
    parser.add_argument("--once", action="store_true",
                        help="Run once: analyze + recommend")
    args = parser.parse_args()

    db = init_db()

    if args.analyze:
        result = analyze(db)
    elif args.recommend:
        result = recommend(db)
    elif args.set:
        result = set_pagefile_size(db, args.set)
    elif args.history:
        result = get_history(db)
    elif args.once:
        result = once(db)
    else:
        parser.print_help()
        db.close()
        return

    print(json.dumps(result, ensure_ascii=False, indent=2))
    db.close()


if __name__ == "__main__":
    main()
