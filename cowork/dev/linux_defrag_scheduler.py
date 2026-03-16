#!/usr/bin/env python3
"""win_defrag_scheduler.py — Drive defrag analyzer and scheduler with SSD detection.
COWORK #228 — Batch 104: Windows Maintenance Pro

Usage:
    python dev/win_defrag_scheduler.py --analyze C
    python dev/win_defrag_scheduler.py --optimize C
    python dev/win_defrag_scheduler.py --schedule
    python dev/win_defrag_scheduler.py --history
    python dev/win_defrag_scheduler.py --once
"""
import argparse, json, sqlite3, time, subprocess, os
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "defrag_scheduler.db"

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS drive_analysis (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        drive TEXT NOT NULL,
        media_type TEXT,
        total_gb REAL,
        free_gb REAL,
        fragmentation_pct REAL,
        needs_defrag INTEGER DEFAULT 0,
        is_ssd INTEGER DEFAULT 0,
        details TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS defrag_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        drive TEXT NOT NULL,
        action TEXT NOT NULL,
        result TEXT,
        duration_seconds INTEGER,
        success INTEGER DEFAULT 1
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS defrag_schedule (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        drive TEXT NOT NULL,
        day_of_week TEXT DEFAULT 'sunday',
        hour INTEGER DEFAULT 3,
        optimize_type TEXT DEFAULT 'auto',
        active INTEGER DEFAULT 1,
        last_run TEXT
    )""")
    db.commit()
    return db

def get_drive_info(drive_letter):
    """Get drive information including SSD detection."""
    drive = drive_letter.rstrip(":").upper()
    info = {"drive": f"{drive}:", "media_type": "unknown", "is_ssd": False}

    # Get disk type (SSD vs HDD)
    try:
        cmd = f'bash -NoProfile -Command "Get-PhysicalDisk | Select-Object MediaType, BusType, Size, FriendlyName | ConvertTo-Json"'
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15, shell=True)
        if r.stdout.strip():
            disks = json.loads(r.stdout)
            if isinstance(disks, dict):
                disks = [disks]
            for disk in disks:
                mt = str(disk.get("MediaType", "")).lower()
                if "ssd" in mt or "solid" in mt:
                    info["media_type"] = "SSD"
                    info["is_ssd"] = True
                elif "hdd" in mt or "unspecified" in mt:
                    info["media_type"] = "HDD"
                info["bus_type"] = disk.get("BusType", "")
                info["friendly_name"] = disk.get("FriendlyName", "")
    except Exception:
        pass

    # Get drive space
    try:
        cmd = f'bash -NoProfile -Command "Get-PSDrive {drive} | Select-Object Used, Free | ConvertTo-Json"'
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10, shell=True)
        if r.stdout.strip():
            data = json.loads(r.stdout)
            used = data.get("Used", 0)
            free = data.get("Free", 0)
            total = used + free
            info["total_gb"] = round(total / (1024**3), 2)
            info["free_gb"] = round(free / (1024**3), 2)
            info["used_pct"] = round((used / total) * 100, 1) if total > 0 else 0
    except Exception:
        pass

    return info

def analyze_fragmentation(drive_letter):
    """Analyze drive fragmentation using defrag /A."""
    drive = drive_letter.rstrip(":").upper()
    try:
        cmd = f'defrag {drive}: /A /V 2>&1'
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, shell=True)
        output = r.stdout + r.stderr
        # Parse fragmentation percentage
        frag_pct = None
        for line in output.split("\n"):
            line_lower = line.lower().strip()
            if "fragmented" in line_lower and "%" in line_lower:
                import re
                match = re.search(r'(\d+)\s*%', line)
                if match:
                    frag_pct = float(match.group(1))
                    break
        return {
            "output_preview": output[:500],
            "fragmentation_pct": frag_pct,
            "raw_exit_code": r.returncode
        }
    except Exception as e:
        return {"error": str(e), "fragmentation_pct": None}

def do_analyze(drive_letter):
    db = init_db()
    info = get_drive_info(drive_letter)
    frag = analyze_fragmentation(drive_letter)

    frag_pct = frag.get("fragmentation_pct")
    needs_defrag = False
    if frag_pct is not None:
        needs_defrag = frag_pct > 10 and not info.get("is_ssd", False)

    recommendation = "No action needed"
    if info.get("is_ssd"):
        recommendation = "SSD detected — use TRIM optimization (not traditional defrag)"
    elif frag_pct and frag_pct > 10:
        recommendation = f"Fragmentation at {frag_pct}% — defragmentation recommended"
    elif frag_pct is not None:
        recommendation = f"Fragmentation at {frag_pct}% — no defrag needed"

    db.execute("""INSERT INTO drive_analysis (ts, drive, media_type, total_gb, free_gb, fragmentation_pct, needs_defrag, is_ssd, details)
                  VALUES (?,?,?,?,?,?,?,?,?)""",
               (datetime.now().isoformat(), f"{drive_letter.upper()}:", info.get("media_type"),
                info.get("total_gb"), info.get("free_gb"), frag_pct, int(needs_defrag),
                int(info.get("is_ssd", False)), frag.get("output_preview", "")[:500]))
    db.commit()

    result = {
        "action": "analyze",
        "drive": info,
        "fragmentation_pct": frag_pct,
        "needs_defrag": needs_defrag,
        "recommendation": recommendation,
        "analysis_output": frag.get("output_preview", "")[:300],
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_optimize(drive_letter):
    db = init_db()
    drive = drive_letter.rstrip(":").upper()
    info = get_drive_info(drive_letter)

    # Choose optimization type based on media
    if info.get("is_ssd"):
        opt_cmd = f'defrag {drive}: /O /V 2>&1'
        opt_type = "TRIM/Optimize"
    else:
        opt_cmd = f'defrag {drive}: /U /V 2>&1'
        opt_type = "Defragment"

    start = time.time()
    try:
        r = subprocess.run(opt_cmd, capture_output=True, text=True, timeout=600, shell=True)
        duration = int(time.time() - start)
        output = r.stdout + r.stderr
        success = r.returncode == 0

        db.execute("INSERT INTO defrag_history (ts, drive, action, result, duration_seconds, success) VALUES (?,?,?,?,?,?)",
                   (datetime.now().isoformat(), f"{drive}:", opt_type, output[:500], duration, int(success)))
        db.commit()

        result = {
            "action": "optimize",
            "drive": f"{drive}:",
            "type": opt_type,
            "is_ssd": info.get("is_ssd", False),
            "duration_seconds": duration,
            "success": success,
            "output_preview": output[:300],
            "ts": datetime.now().isoformat()
        }
    except subprocess.TimeoutExpired:
        result = {"action": "optimize", "drive": f"{drive}:", "error": "Timeout (>10min)", "ts": datetime.now().isoformat()}

    db.close()
    return result

def do_schedule():
    db = init_db()
    rows = db.execute("SELECT drive, day_of_week, hour, optimize_type, active, last_run FROM defrag_schedule ORDER BY drive").fetchall()
    schedules = [{"drive": r[0], "day": r[1], "hour": r[2], "type": r[3], "active": bool(r[4]), "last_run": r[5]} for r in rows]
    if not schedules:
        # Show Windows default schedule
        schedules = [{"note": "No custom schedules. Windows auto-optimizes drives weekly by default."}]
    result = {"action": "schedule", "schedules": schedules, "ts": datetime.now().isoformat()}
    db.close()
    return result

def do_history():
    db = init_db()
    rows = db.execute("SELECT ts, drive, action, duration_seconds, success FROM defrag_history ORDER BY id DESC LIMIT 20").fetchall()
    history = [{"ts": r[0], "drive": r[1], "action": r[2], "duration_s": r[3], "success": bool(r[4])} for r in rows]
    analyses = db.execute("SELECT ts, drive, media_type, fragmentation_pct, needs_defrag FROM drive_analysis ORDER BY id DESC LIMIT 10").fetchall()
    result = {
        "action": "history",
        "optimization_history": history,
        "recent_analyses": [{"ts": r[0], "drive": r[1], "type": r[2], "frag_pct": r[3], "needs_defrag": bool(r[4])} for r in analyses],
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_once():
    db = init_db()
    analyses = db.execute("SELECT COUNT(*) FROM drive_analysis").fetchone()[0]
    optimizations = db.execute("SELECT COUNT(*) FROM defrag_history").fetchone()[0]
    last = db.execute("SELECT ts, drive, fragmentation_pct FROM drive_analysis ORDER BY id DESC LIMIT 1").fetchone()
    result = {
        "status": "ok",
        "total_analyses": analyses,
        "total_optimizations": optimizations,
        "last_analysis": {"ts": last[0], "drive": last[1], "frag_pct": last[2]} if last else None,
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def main():
    parser = argparse.ArgumentParser(description="Drive Defrag Scheduler — COWORK #228")
    parser.add_argument("--analyze", type=str, metavar="DRIVE", help="Analyze drive (e.g. C)")
    parser.add_argument("--optimize", type=str, metavar="DRIVE", help="Optimize drive")
    parser.add_argument("--schedule", action="store_true", help="Show defrag schedule")
    parser.add_argument("--history", action="store_true", help="Show defrag history")
    parser.add_argument("--once", action="store_true", help="One-shot status check")
    args = parser.parse_args()

    if args.analyze:
        print(json.dumps(do_analyze(args.analyze), ensure_ascii=False, indent=2))
    elif args.optimize:
        print(json.dumps(do_optimize(args.optimize), ensure_ascii=False, indent=2))
    elif args.schedule:
        print(json.dumps(do_schedule(), ensure_ascii=False, indent=2))
    elif args.history:
        print(json.dumps(do_history(), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(do_once(), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
