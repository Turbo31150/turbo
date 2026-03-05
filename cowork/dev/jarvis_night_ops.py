#!/usr/bin/env python3
"""JARVIS Night Operations — Autonomous tasks during off-hours.

Runs maintenance, optimization, and improvement tasks when user
is inactive. Backs up, cleans, benchmarks, and prepares reports.
"""
import argparse
import json
import os
import sqlite3
import subprocess
import time
from pathlib import Path

DB_PATH = Path(__file__).parent / "night_ops.db"
TURBO = Path("F:/BUREAU/turbo")

def init_db():
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS operations (
        id INTEGER PRIMARY KEY, ts REAL, operation TEXT,
        status TEXT, duration_s REAL, details TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY, ts REAL, report_type TEXT,
        content TEXT)""")
    db.commit()
    return db

def is_night_hours():
    """Check if it's currently night hours (23h-7h)."""
    hour = int(time.strftime('%H'))
    return hour >= 23 or hour < 7

def op_vacuum_databases(db):
    """VACUUM all JARVIS databases."""
    start = time.time()
    dbs_vacuumed = 0
    details = []
    for dbpath in (TURBO / "data").glob("*.db"):
        try:
            conn = sqlite3.connect(str(dbpath))
            size_before = dbpath.stat().st_size
            conn.execute("VACUUM")
            conn.close()
            size_after = dbpath.stat().st_size
            saved = size_before - size_after
            if saved > 0:
                details.append(f"{dbpath.name}: -{saved//1024}KB")
            dbs_vacuumed += 1
        except Exception as e:
            details.append(f"{dbpath.name}: FAIL {e}")
    duration = time.time() - start
    db.execute(
        "INSERT INTO operations (ts, operation, status, duration_s, details) VALUES (?,?,?,?,?)",
        (time.time(), "vacuum_databases", "ok", duration, json.dumps(details[:20])))
    db.commit()
    return dbs_vacuumed, details

def op_clean_temp_files(db):
    """Clean temporary and cache files."""
    start = time.time()
    cleaned = 0
    # TTS cache
    tts_cache = TURBO / "data" / "tts_cache"
    if tts_cache.exists():
        for f in tts_cache.glob("*.mp3"):
            age_hours = (time.time() - f.stat().st_mtime) / 3600
            if age_hours > 24:
                f.unlink(missing_ok=True)
                cleaned += 1
    # Python cache
    for pycache in TURBO.rglob("__pycache__"):
        for pyc in pycache.glob("*.pyc"):
            age_hours = (time.time() - pyc.stat().st_mtime) / 3600
            if age_hours > 72:
                pyc.unlink(missing_ok=True)
                cleaned += 1
    # Old logs
    for log in (TURBO / "data").glob("*.log"):
        size_mb = log.stat().st_size / (1024 * 1024)
        if size_mb > 50:
            # Truncate to last 10000 lines
            try:
                lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
                if len(lines) > 10000:
                    log.write_text("\n".join(lines[-10000:]), encoding="utf-8")
                    cleaned += 1
            except Exception:
                pass

    duration = time.time() - start
    db.execute(
        "INSERT INTO operations (ts, operation, status, duration_s, details) VALUES (?,?,?,?,?)",
        (time.time(), "clean_temp", "ok", duration, f"{cleaned} files cleaned"))
    db.commit()
    return cleaned

def op_git_maintenance(db):
    """Git repository maintenance."""
    start = time.time()
    results = []
    try:
        # Git gc
        r = subprocess.run(
            ["git", "gc", "--auto"],
            capture_output=True, text=True, timeout=60, cwd=str(TURBO))
        results.append(f"gc: {'ok' if r.returncode == 0 else 'fail'}")

        # Check repo size
        r = subprocess.run(
            ["git", "count-objects", "-vH"],
            capture_output=True, text=True, timeout=10, cwd=str(TURBO))
        if r.returncode == 0:
            for line in r.stdout.splitlines():
                if "size-pack" in line:
                    results.append(line.strip())
    except (subprocess.TimeoutExpired, OSError) as e:
        results.append(f"error: {e}")

    duration = time.time() - start
    db.execute(
        "INSERT INTO operations (ts, operation, status, duration_s, details) VALUES (?,?,?,?,?)",
        (time.time(), "git_maintenance", "ok", duration, json.dumps(results)))
    db.commit()
    return results

def op_generate_morning_report(db):
    """Generate a morning report for Turbo."""
    # Collect overnight stats
    since = time.time() - 28800  # last 8 hours
    ops = db.execute(
        "SELECT operation, status, duration_s FROM operations WHERE ts > ?",
        (since,)).fetchall()

    report_lines = [
        f"# Rapport Night Ops — {time.strftime('%Y-%m-%d %H:%M')}",
        "",
        f"## Operations executees: {len(ops)}",
    ]
    for op, status, dur in ops:
        icon = "✅" if status == "ok" else "❌"
        report_lines.append(f"- {icon} {op} ({dur:.1f}s)")

    report = "\n".join(report_lines)
    db.execute(
        "INSERT INTO reports (ts, report_type, content) VALUES (?,?,?)",
        (time.time(), "morning", report))
    db.commit()
    return report

def send_morning_telegram(report):
    """Send morning report to Telegram."""
    try:
        edb = sqlite3.connect(str(TURBO / "data" / "etoile.db"))
        row = edb.execute("SELECT value FROM memories WHERE key='telegram_bot_token'").fetchone()
        token = row[0] if row else ""
        edb.close()
    except Exception:
        return
    if not token:
        return
    msg = f"🌅 *JARVIS Night Ops Report*\n{report[:3000]}"
    try:
        body = json.dumps({"chat_id": "2010747443", "text": msg, "parse_mode": "Markdown"}).encode()
        import urllib.request
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=body, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass

def run_night_ops(db, notify=False):
    """Run all night operations."""
    print("=== JARVIS Night Ops ===")

    n, details = op_vacuum_databases(db)
    print(f"  VACUUM: {n} databases")
    for d in details[:5]:
        print(f"    {d}")

    cleaned = op_clean_temp_files(db)
    print(f"  Clean: {cleaned} temp files")

    git = op_git_maintenance(db)
    print(f"  Git: {', '.join(git)}")

    report = op_generate_morning_report(db)
    print(f"  Report generated ({len(report)} chars)")

    if notify:
        send_morning_telegram(report)
        print("  Morning report sent to Telegram")

def main():
    parser = argparse.ArgumentParser(description="JARVIS Night Operations")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--notify", action="store_true", help="Send Telegram report")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--force", action="store_true", help="Run even outside night hours")
    parser.add_argument("--report", action="store_true", help="Show last report")
    args = parser.parse_args()

    db = init_db()

    if args.report:
        row = db.execute("SELECT content FROM reports ORDER BY ts DESC LIMIT 1").fetchone()
        print(row[0] if row else "No reports yet")
        return

    if args.once or not args.loop:
        if is_night_hours() or args.force:
            run_night_ops(db, args.notify)
        else:
            print(f"Pas en heures de nuit ({time.strftime('%H:%M')}). Utiliser --force pour forcer.")

    if args.loop:
        print("Night Ops en attente...")
        while True:
            try:
                if is_night_hours():
                    run_night_ops(db, args.notify)
                    time.sleep(3600)  # Run once per hour during night
                else:
                    time.sleep(600)  # Check every 10 min during day
            except KeyboardInterrupt:
                break

if __name__ == "__main__":
    main()
