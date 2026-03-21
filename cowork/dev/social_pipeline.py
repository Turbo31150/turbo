#!/usr/bin/env python3
"""Social Pipeline — Master orchestrator for all 6 content automation triggers.

Launches LinkedIn, Codeur, Email, Calendar, Drive in parallel.

Usage:
    python cowork/dev/social_pipeline.py --once     # Run all 6 triggers once
    python cowork/dev/social_pipeline.py --linkedin  # LinkedIn only
    python cowork/dev/social_pipeline.py --email     # Email only
    python cowork/dev/social_pipeline.py --status    # Check last run status
"""

import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

TURBO = Path(__file__).resolve().parent.parent.parent
DEV = TURBO / "cowork" / "dev"
PYTHON = sys.executable

TRIGGERS = {
    "linkedin": "linkedin_content_generator",
    "codeur": "codeur_profile_manager",
    "email": "email_orchestrator",
    "calendar": "calendar_sync",
    "drive": "drive_organizer",
    "telegram": "telegram_mcp_bridge",
}


def run_trigger(name, script_name):
    """Run a single trigger script."""
    path = DEV / f"{script_name}.py"
    if not path.exists():
        return {"trigger": name, "status": "MISSING", "script": script_name}
    start = time.time()
    try:
        r = subprocess.run([PYTHON, str(path), "--once"],
                           capture_output=True, text=True, timeout=120, cwd=str(TURBO))
        elapsed = round(time.time() - start, 1)
        return {"trigger": name, "status": "OK" if r.returncode == 0 else "FAIL",
                "elapsed_s": elapsed, "exit_code": r.returncode,
                "output_lines": len(r.stdout.splitlines())}
    except subprocess.TimeoutExpired:
        return {"trigger": name, "status": "TIMEOUT", "elapsed_s": 120}
    except Exception as e:
        return {"trigger": name, "status": "ERROR", "error": str(e)}


def run_all():
    """Run all triggers in parallel."""
    results = []
    start = time.time()
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(run_trigger, name, script): name
                   for name, script in TRIGGERS.items()}
        for future in as_completed(futures):
            results.append(future.result())

    ok = sum(1 for r in results if r["status"] == "OK")
    report = {
        "timestamp": datetime.now().isoformat(),
        "pipeline": "social",
        "triggers": results,
        "total": len(results),
        "ok": ok,
        "failed": len(results) - ok,
        "elapsed_s": round(time.time() - start, 1)
    }

    # Log to etoile.db
    try:
        import sqlite3
        db = sqlite3.connect(str(TURBO / "etoile.db"))
        db.execute("INSERT INTO memories(category,key,value,confidence,source,updated_at) VALUES(?,?,?,?,?,?)",
                   ("social_pipeline", f"run_{datetime.now().strftime('%Y%m%d_%H%M')}",
                    json.dumps({"ok": ok, "total": len(results)}), 1.0,
                    "social_pipeline", datetime.now().isoformat()))
        db.commit()
        db.close()
    except Exception:
        pass

    print(json.dumps(report, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description="Social Pipeline — Master Orchestrator")
    parser.add_argument("--once", action="store_true", help="Run all triggers")
    parser.add_argument("--status", action="store_true", help="Check last run")
    for name in TRIGGERS:
        parser.add_argument(f"--{name}", action="store_true", help=f"Run {name} only")
    args = parser.parse_args()

    if args.once:
        run_all()
    elif args.status:
        try:
            import sqlite3
            db = sqlite3.connect(str(TURBO / "etoile.db"))
            row = db.execute("SELECT value,updated_at FROM memories WHERE category='social_pipeline' ORDER BY rowid DESC LIMIT 1").fetchone()
            print(json.dumps({"last_run": row[1] if row else "never", "result": json.loads(row[0]) if row else None}, indent=2))
            db.close()
        except Exception as e:
            print(json.dumps({"error": str(e)}))
    else:
        # Check individual triggers
        for name in TRIGGERS:
            if getattr(args, name, False):
                r = run_trigger(name, TRIGGERS[name])
                print(json.dumps(r, indent=2))
                return
        run_all()


if __name__ == "__main__":
    main()
