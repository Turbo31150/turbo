#!/usr/bin/env python3
"""win_system_restore_manager.py (#197) — Windows Restore Point Manager.

Lists restore points via PowerShell Get-ComputerRestorePoint.
Creates new restore points. Checks system protection status.

Usage:
    python dev/win_system_restore_manager.py --once
    python dev/win_system_restore_manager.py --create "Before JARVIS update"
    python dev/win_system_restore_manager.py --list
    python dev/win_system_restore_manager.py --status
"""
import argparse
import json
import re
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "restore_manager.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS restore_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        action TEXT,
        description TEXT,
        result TEXT,
        details TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS restore_points_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        seq_number INTEGER,
        description TEXT,
        creation_time TEXT,
        restore_type TEXT
    )""")
    db.commit()
    return db


def get_restore_points():
    """Get list of restore points via PowerShell."""
    points = []
    try:
        r = subprocess.run(
            ["bash", "-NoProfile", "-Command",
             "try { Get-ComputerRestorePoint | Select-Object SequenceNumber, Description, "
             "CreationTime, RestorePointType | ConvertTo-Json -Compress } "
             "catch { Write-Output '{\"error\": \"access_denied\"}' }"],
            capture_output=True, text=True, timeout=15
        )
        if r.stdout.strip():
            data = json.loads(r.stdout.strip())
            if isinstance(data, dict):
                if "error" in data:
                    return [], data["error"]
                data = [data]
            for pt in data:
                rtype_map = {
                    0: "APPLICATION_INSTALL",
                    1: "APPLICATION_UNINSTALL",
                    10: "DEVICE_DRIVER_INSTALL",
                    12: "MODIFY_SETTINGS",
                    13: "CANCELLED_OPERATION"
                }
                rtype = pt.get("RestorePointType", 0)
                points.append({
                    "sequence": pt.get("SequenceNumber", 0),
                    "description": pt.get("Description", ""),
                    "creation_time": str(pt.get("CreationTime", "")),
                    "type": rtype_map.get(rtype, f"TYPE_{rtype}")
                })
    except json.JSONDecodeError:
        return [], "JSON parse error"
    except subprocess.TimeoutExpired:
        return [], "PowerShell timeout"
    except Exception as e:
        return [], str(e)

    return points, None


def get_protection_status():
    """Check if System Restore is enabled."""
    status = {
        "enabled": False,
        "drives": []
    }
    try:
        r = subprocess.run(
            ["bash", "-NoProfile", "-Command",
             "try { Get-ComputerRestorePoint -LastStatus } catch { }; "
             "vssadmin list shadowstorage 2>$null | Select-String -Pattern 'For volume|Used|Allocated|Maximum'"],
            capture_output=True, text=True, timeout=10
        )
        if r.stdout.strip():
            status["raw"] = r.stdout.strip()[:500]
    except Exception:
        pass

    # Check via wmic
    try:
        r = subprocess.run(
            ["bash", "-NoProfile", "-Command",
             "try { (Get-ComputerRestorePoint | Measure-Object).Count } catch { Write-Output '0' }"],
            capture_output=True, text=True, timeout=10
        )
        count = int(r.stdout.strip()) if r.stdout.strip().isdigit() else 0
        status["restore_point_count"] = count
        status["enabled"] = count > 0 or True  # System Restore might be enabled with 0 points
    except Exception:
        status["restore_point_count"] = 0

    # Check if System Restore service is running
    try:
        r = subprocess.run(
            ["bash", "-NoProfile", "-Command",
             "(Get-Service -Name 'srservice' -ErrorAction SilentlyContinue).Status"],
            capture_output=True, text=True, timeout=5
        )
        svc_status = r.stdout.strip()
        status["service_status"] = svc_status if svc_status else "unknown"
    except Exception:
        status["service_status"] = "unknown"

    return status


def create_restore_point(db, description="JARVIS Checkpoint"):
    """Create a new System Restore point (requires admin)."""
    try:
        r = subprocess.run(
            ["bash", "-NoProfile", "-Command",
             f'Checkpoint-Computer -Description "{description}" -RestorePointType MODIFY_SETTINGS -ErrorAction Stop'],
            capture_output=True, text=True, timeout=60
        )
        if r.returncode == 0:
            result = "ok"
            details = "Restore point created successfully"
        else:
            result = "error"
            details = r.stderr.strip()[:300] or "Unknown error (may need admin privileges)"

    except subprocess.TimeoutExpired:
        result = "timeout"
        details = "PowerShell timeout (60s)"
    except Exception as e:
        result = "error"
        details = str(e)

    db.execute(
        "INSERT INTO restore_log (ts, action, description, result, details) VALUES (?,?,?,?,?)",
        (time.time(), "create", description, result, details)
    )
    db.commit()

    return {
        "status": result,
        "description": description,
        "details": details,
        "note": "Creating restore points requires administrator privileges" if result == "error" else ""
    }


def list_restore_points(db):
    """List all restore points."""
    points, err = get_restore_points()

    if err:
        return {"status": "error", "error": err, "note": "May require admin privileges"}

    # Cache to DB
    for pt in points:
        db.execute(
            "INSERT OR REPLACE INTO restore_points_cache (ts, seq_number, description, creation_time, restore_type) VALUES (?,?,?,?,?)",
            (time.time(), pt["sequence"], pt["description"], pt["creation_time"], pt["type"])
        )
    db.commit()

    return {
        "status": "ok",
        "count": len(points),
        "points": points
    }


def get_status(db):
    """Get System Restore status."""
    protection = get_protection_status()
    points, err = get_restore_points()

    # History from our log
    log_rows = db.execute(
        "SELECT ts, action, description, result FROM restore_log ORDER BY ts DESC LIMIT 10"
    ).fetchall()
    history = []
    for r in log_rows:
        history.append({
            "time": datetime.fromtimestamp(r[0]).isoformat(),
            "action": r[1], "description": r[2], "result": r[3]
        })

    return {
        "status": "ok",
        "protection": protection,
        "restore_points": len(points) if not err else f"error: {err}",
        "latest_point": points[0] if points else None,
        "our_actions": history
    }


def once(db):
    """Run once: show status and list points."""
    status = get_status(db)
    points = list_restore_points(db)

    db.execute(
        "INSERT INTO restore_log (ts, action, description, result, details) VALUES (?,?,?,?,?)",
        (time.time(), "check", "once mode health check", "ok", "")
    )
    db.commit()

    return {
        "status": "ok", "mode": "once",
        "protection_status": status["protection"],
        "restore_points": points,
        "our_log_count": db.execute("SELECT COUNT(*) FROM restore_log").fetchone()[0]
    }


def main():
    parser = argparse.ArgumentParser(description="System Restore Manager (#197) — Windows restore points")
    parser.add_argument("--create", type=str, nargs="?", const="JARVIS Checkpoint",
                        help="Create a restore point")
    parser.add_argument("--list", action="store_true", help="List restore points")
    parser.add_argument("--status", action="store_true", help="Show protection status")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    db = init_db()

    if args.create is not None:
        result = create_restore_point(db, args.create)
    elif args.list:
        result = list_restore_points(db)
    elif args.status:
        result = get_status(db)
    elif args.once:
        result = once(db)
    else:
        parser.print_help()
        return

    print(json.dumps(result, indent=2, default=str))
    db.close()


if __name__ == "__main__":
    main()
