#!/usr/bin/env python3
"""win_startup_profiler.py (#190) — Boot profiler Windows 11.

Parse les evenements de demarrage via wevtutil, timeline par service,
identifie les 5 plus lents, suggere des desactivations.

Usage:
    python dev/win_startup_profiler.py --once
    python dev/win_startup_profiler.py --profile
    python dev/win_startup_profiler.py --timeline
    python dev/win_startup_profiler.py --disable "ServiceName"
    python dev/win_startup_profiler.py --compare
"""
import argparse
import ctypes
import json
import re
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "startup_profiler.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS boot_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        boot_time_ms INTEGER,
        main_path_ms INTEGER,
        boot_post_ms INTEGER,
        event_count INTEGER,
        slowest_json TEXT,
        raw_events_json TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS service_timelines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        profile_id INTEGER,
        service_name TEXT,
        duration_ms INTEGER,
        degradation TEXT,
        FOREIGN KEY (profile_id) REFERENCES boot_profiles(id)
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        action TEXT,
        service_name TEXT,
        success INTEGER,
        details TEXT
    )""")
    db.commit()
    return db


def parse_boot_events():
    """Parse boot events from Windows Event Log."""
    events = []

    # Try wevtutil for boot performance events (Event IDs 100-110)
    try:
        cmd = [
            "wevtutil", "qe",
            "Microsoft-Windows-Diagnostics-Performance/Operational",
            "/c:20", "/f:text", "/rd:true",
            "/q:*[System[(EventID>=100 and EventID<=110)]]"
        ]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if out.returncode == 0 and out.stdout.strip():
            current_event = {}
            for line in out.stdout.split("\n"):
                line = line.strip()
                if line.startswith("Event["):
                    if current_event:
                        events.append(current_event)
                    current_event = {}
                elif ":" in line:
                    key, _, val = line.partition(":")
                    key = key.strip()
                    val = val.strip()
                    if key == "Event ID":
                        current_event["event_id"] = int(val) if val.isdigit() else val
                    elif key == "Date":
                        current_event["date"] = val
                    elif key == "BootTime" or key == "MainPathBootTime":
                        current_event["main_path_ms"] = int(val) if val.isdigit() else 0
                    elif key == "BootPostBootTime":
                        current_event["post_boot_ms"] = int(val) if val.isdigit() else 0
                    elif key == "Source" or key == "Provider Name":
                        current_event["source"] = val
            if current_event:
                events.append(current_event)
    except Exception:
        pass

    # Fallback: PowerShell
    if not events:
        try:
            ps_cmd = (
                "Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-Diagnostics-Performance/Operational'; Id=100,101,102,103,106,107,108,109,110} -MaxEvents 20 -ErrorAction SilentlyContinue | "
                "Select-Object Id,TimeCreated,Message | "
                "ForEach-Object { @{Id=$_.Id; Time=$_.TimeCreated.ToString('yyyy-MM-dd HH:mm:ss'); Msg=$_.Message.Substring(0, [Math]::Min(500, $_.Message.Length))} } | "
                "ConvertTo-Json -Depth 2"
            )
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=20
            )
            if out.returncode == 0 and out.stdout.strip():
                data = json.loads(out.stdout)
                if isinstance(data, dict):
                    data = [data]
                for item in data:
                    event = {
                        "event_id": item.get("Id", 0),
                        "date": item.get("Time", ""),
                        "message": item.get("Msg", "")
                    }
                    # Parse duration from message
                    msg = item.get("Msg", "")
                    ms_match = re.search(r'(\d+)\s*ms', msg)
                    if ms_match:
                        event["main_path_ms"] = int(ms_match.group(1))
                    events.append(event)
        except Exception:
            pass

    return events


def get_startup_apps():
    """Get startup applications via powershell."""
    apps = []
    try:
        ps_cmd = (
            "Get-CimInstance Win32_StartupCommand | "
            "Select-Object Name,Command,Location | "
            "ConvertTo-Json -Depth 2"
        )
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=15
        )
        if out.returncode == 0 and out.stdout.strip():
            data = json.loads(out.stdout)
            if isinstance(data, dict):
                data = [data]
            for item in data:
                apps.append({
                    "name": item.get("Name", ""),
                    "command": item.get("Command", "")[:200],
                    "location": item.get("Location", "")
                })
    except Exception:
        pass
    return apps


def get_slow_services():
    """Identify slow-starting services."""
    slow = []
    try:
        ps_cmd = (
            "Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-Diagnostics-Performance/Operational'; Id=101} -MaxEvents 30 -ErrorAction SilentlyContinue | "
            "ForEach-Object { "
            "  $xml = [xml]$_.ToXml(); "
            "  $name = ($xml.Event.EventData.Data | Where-Object {$_.Name -eq 'Name'}).'#text'; "
            "  $dur = ($xml.Event.EventData.Data | Where-Object {$_.Name -eq 'TotalTime'}).'#text'; "
            "  @{Name=$name; Duration=[int]$dur; Time=$_.TimeCreated.ToString('yyyy-MM-dd HH:mm:ss')} "
            "} | Sort-Object Duration -Descending | Select-Object -First 10 | "
            "ConvertTo-Json -Depth 2"
        )
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=20
        )
        if out.returncode == 0 and out.stdout.strip():
            data = json.loads(out.stdout)
            if isinstance(data, dict):
                data = [data]
            for item in data:
                if item.get("Name"):
                    slow.append({
                        "name": item["Name"],
                        "duration_ms": item.get("Duration", 0),
                        "time": item.get("Time", "")
                    })
    except Exception:
        pass
    return slow


def profile_boot(db):
    """Full boot profile."""
    events = parse_boot_events()
    slow_services = get_slow_services()
    startup_apps = get_startup_apps()

    # Extract boot times from events
    boot_time_ms = 0
    main_path_ms = 0
    post_boot_ms = 0
    for e in events:
        if e.get("event_id") == 100 or e.get("event_id") == "100":
            main_path_ms = e.get("main_path_ms", 0)
            post_boot_ms = e.get("post_boot_ms", 0)
            boot_time_ms = main_path_ms + post_boot_ms

    # Fallback: use last boot time from systeminfo
    if boot_time_ms == 0:
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToString('yyyy-MM-dd HH:mm:ss')"],
                capture_output=True, text=True, timeout=10
            )
            if out.returncode == 0:
                boot_time_str = out.stdout.strip()
                events.append({"event_id": "info", "date": boot_time_str, "note": "Last boot time"})
        except Exception:
            pass

    # Store profile
    slowest = slow_services[:5]
    db.execute(
        """INSERT INTO boot_profiles
           (ts, boot_time_ms, main_path_ms, boot_post_ms, event_count, slowest_json, raw_events_json)
           VALUES (?,?,?,?,?,?,?)""",
        (time.time(), boot_time_ms, main_path_ms, post_boot_ms,
         len(events), json.dumps(slowest, ensure_ascii=False),
         json.dumps(events[:20], ensure_ascii=False, default=str))
    )
    db.commit()
    profile_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Store service timelines
    for svc in slow_services:
        degradation = "critical" if svc["duration_ms"] > 10000 else \
                      "slow" if svc["duration_ms"] > 3000 else "normal"
        db.execute(
            """INSERT INTO service_timelines (ts, profile_id, service_name, duration_ms, degradation)
               VALUES (?,?,?,?,?)""",
            (time.time(), profile_id, svc["name"], svc["duration_ms"], degradation)
        )
    db.commit()

    return {
        "status": "ok",
        "boot_time_ms": boot_time_ms,
        "main_path_ms": main_path_ms,
        "post_boot_ms": post_boot_ms,
        "event_count": len(events),
        "startup_apps": len(startup_apps),
        "top5_slowest": slowest,
        "startup_apps_list": startup_apps[:10],
        "suggestions": [
            f"Consider disabling: {s['name']} ({s['duration_ms']}ms)"
            for s in slowest if s.get("duration_ms", 0) > 3000
        ]
    }


def timeline(db):
    """Show service timeline from last profile."""
    rows = db.execute(
        """SELECT service_name, duration_ms, degradation, ts
           FROM service_timelines
           ORDER BY duration_ms DESC LIMIT 20"""
    ).fetchall()

    return {
        "status": "ok",
        "total_services_profiled": len(rows),
        "timeline": [
            {
                "service": r[0], "duration_ms": r[1],
                "degradation": r[2],
                "ts": datetime.fromtimestamp(r[3]).strftime("%Y-%m-%d %H:%M:%S")
            }
            for r in rows
        ]
    }


def disable_service(db, service_name):
    """Disable a startup service/app."""
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        is_admin = False

    if not is_admin:
        return {
            "status": "error",
            "error": "Administrator privileges required",
            "suggestion": f"Run as admin: sc config \"{service_name}\" start=disabled"
        }

    try:
        out = subprocess.run(
            ["sc", "config", service_name, "start=disabled"],
            capture_output=True, text=True, timeout=10
        )
        success = out.returncode == 0
        db.execute(
            "INSERT INTO actions (ts, action, service_name, success, details) VALUES (?,?,?,?,?)",
            (time.time(), "disable", service_name, int(success),
             out.stdout.strip() or out.stderr.strip())
        )
        db.commit()
        return {
            "status": "ok" if success else "error",
            "service": service_name,
            "disabled": success,
            "output": (out.stdout.strip() or out.stderr.strip())[:200]
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def compare_profiles(db):
    """Compare last 2 boot profiles."""
    rows = db.execute(
        "SELECT ts, boot_time_ms, main_path_ms, boot_post_ms, event_count FROM boot_profiles ORDER BY ts DESC LIMIT 2"
    ).fetchall()

    if len(rows) < 2:
        return {
            "status": "info",
            "message": "Need at least 2 profiles to compare. Run --profile twice.",
            "profiles_available": len(rows)
        }

    current = rows[0]
    previous = rows[1]
    delta_ms = current[1] - previous[1]

    return {
        "status": "ok",
        "current": {
            "ts": datetime.fromtimestamp(current[0]).strftime("%Y-%m-%d %H:%M:%S"),
            "boot_time_ms": current[1], "main_path_ms": current[2]
        },
        "previous": {
            "ts": datetime.fromtimestamp(previous[0]).strftime("%Y-%m-%d %H:%M:%S"),
            "boot_time_ms": previous[1], "main_path_ms": previous[2]
        },
        "delta_ms": delta_ms,
        "improvement": delta_ms < 0,
        "change_percent": round(delta_ms / max(previous[1], 1) * 100, 1)
    }


def once(db):
    """Run once: profile boot."""
    profile = profile_boot(db)
    total = db.execute("SELECT COUNT(*) FROM boot_profiles").fetchone()[0]

    return {
        "status": "ok",
        "mode": "once",
        "script": "win_startup_profiler.py (#190)",
        "total_profiles": total,
        "profile": profile
    }


def main():
    parser = argparse.ArgumentParser(
        description="win_startup_profiler.py (#190) — Boot profiler Windows 11"
    )
    parser.add_argument("--profile", action="store_true",
                        help="Profile current boot performance")
    parser.add_argument("--timeline", action="store_true",
                        help="Show service startup timeline")
    parser.add_argument("--disable", type=str, metavar="SERVICE",
                        help="Disable a startup service (requires admin)")
    parser.add_argument("--compare", action="store_true",
                        help="Compare last 2 boot profiles")
    parser.add_argument("--once", action="store_true",
                        help="Run once: full boot profile")
    args = parser.parse_args()

    db = init_db()

    if args.profile:
        result = profile_boot(db)
    elif args.timeline:
        result = timeline(db)
    elif args.disable:
        result = disable_service(db, args.disable)
    elif args.compare:
        result = compare_profiles(db)
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
