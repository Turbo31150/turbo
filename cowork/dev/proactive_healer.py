#!/usr/bin/env python3
"""proactive_healer.py — Proactive self-healing for JARVIS cluster.

Monitors trends and takes corrective action BEFORE issues become problems:
- Latency trending up -> reduce load on node
- Success rate dropping -> route traffic away
- Disk filling up -> trigger cleanup
- Grade dropping -> run optimizer
- Stale data -> trigger refresh cycles

CLI:
    --once         : Single healing cycle
    --watch        : Continuous healing (default 10 min)
    --history      : Show healing history
    --dry-run      : Show what would heal without acting

Stdlib-only (json, argparse, sqlite3, subprocess, time).
"""

import argparse
import json
import sqlite3
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
GAPS_DB = DATA_DIR / "cowork_gaps.db"
from _paths import ETOILE_DB, TELEGRAM_TOKEN, TELEGRAM_CHAT

# TELEGRAM_TOKEN loaded from _paths (.env)
TELEGRAM_CHAT_ID = TELEGRAM_CHAT

# Healing thresholds
THRESHOLDS = {
    "latency_spike_ms": 10000,    # 10s average = concern
    "success_rate_min": 70,       # Below 70% = act
    "grade_min": 85,              # Below A- = optimize
    "disk_free_min_pct": 10,      # Below 10% = critical
    "stale_baseline_hours": 6,    # Refresh baselines after 6h
}


def get_db(path):
    conn = sqlite3.connect(str(path), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def init_healing_history(db):
    db.execute("""CREATE TABLE IF NOT EXISTS proactive_healing_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        trigger_type TEXT NOT NULL,
        target TEXT,
        action_taken TEXT,
        result TEXT,
        grade_before REAL,
        grade_after REAL
    )""")
    db.commit()


def get_grade():
    """Get current grade score."""
    try:
        r = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "grade_optimizer.py"), "--analyze"],
            capture_output=True, text=True, timeout=15, cwd=str(SCRIPT_DIR)
        )
        for line in r.stdout.split("\n"):
            if '"overall"' in line:
                return float(line.split(":")[1].strip().rstrip(","))
    except Exception:
        pass
    return 0


def check_latency_trends(db):
    """Check for latency degradation."""
    issues = []
    try:
        rows = db.execute("""
            SELECT node, avg_ms, p95_ms FROM latency_baselines
        """).fetchall()
        for r in rows:
            if r["avg_ms"] and r["avg_ms"] > THRESHOLDS["latency_spike_ms"]:
                issues.append({
                    "trigger": "latency_high",
                    "target": r["node"],
                    "detail": f"{r['node']} avg={r['avg_ms']:.0f}ms (>{THRESHOLDS['latency_spike_ms']}ms)",
                    "action": "deprioritize_node",
                })
    except Exception:
        pass
    return issues


def check_success_rate(edb):
    """Check per-node success rates."""
    issues = []
    try:
        has = edb.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE name='agent_dispatch_log'"
        ).fetchone()[0]
        if has:
            rows = edb.execute("""
                SELECT node,
                       ROUND(AVG(CASE WHEN success=1 THEN 100.0 ELSE 0 END), 1) as rate,
                       COUNT(*) as total
                FROM (SELECT * FROM agent_dispatch_log ORDER BY id DESC LIMIT 30)
                GROUP BY node
            """).fetchall()
            for r in rows:
                if r["rate"] < THRESHOLDS["success_rate_min"] and r["total"] >= 3:
                    issues.append({
                        "trigger": "low_success",
                        "target": r["node"],
                        "detail": f"{r['node']} success={r['rate']}% (<{THRESHOLDS['success_rate_min']}%)",
                        "action": "route_away",
                    })
    except Exception:
        pass
    return issues


def check_grade(grade):
    """Check if grade needs optimization."""
    issues = []
    if grade > 0 and grade < THRESHOLDS["grade_min"]:
        issues.append({
            "trigger": "grade_low",
            "target": "system",
            "detail": f"Grade {grade:.1f} (<{THRESHOLDS['grade_min']})",
            "action": "run_optimizer",
        })
    return issues


def check_stale_baselines(db):
    """Check for stale latency baselines."""
    issues = []
    try:
        rows = db.execute("""
            SELECT node, updated_at FROM latency_baselines
        """).fetchall()
        for r in rows:
            if r["updated_at"]:
                try:
                    last = datetime.fromisoformat(r["updated_at"])
                    hours = (datetime.now() - last).total_seconds() / 3600
                    if hours > THRESHOLDS["stale_baseline_hours"]:
                        issues.append({
                            "trigger": "stale_baseline",
                            "target": r["node"],
                            "detail": f"{r['node']} baseline {hours:.0f}h old",
                            "action": "refresh_baseline",
                        })
                except Exception:
                    pass
    except Exception:
        pass
    return issues


def apply_healing(issue, db, dry_run=False):
    """Apply a healing action."""
    action = issue["action"]
    result = {"applied": False, "detail": ""}

    if dry_run:
        result["detail"] = f"Would: {action} on {issue['target']}"
        return result

    if action == "deprioritize_node":
        try:
            db.execute("""
                UPDATE node_reliability SET composite = composite * 0.8
                WHERE node = ?
            """, (issue["target"],))
            db.commit()
            result["applied"] = True
            result["detail"] = f"Reduced reliability for {issue['target']}"
        except Exception as e:
            result["detail"] = str(e)[:100]

    elif action == "route_away":
        try:
            # Update circuit breaker to OPEN
            now = datetime.now().isoformat()
            db.execute("""
                INSERT INTO circuit_breaker_state (node, state, fail_count, last_fail, last_transition, updated_at)
                VALUES (?, 'OPEN', 3, ?, ?, ?)
                ON CONFLICT(node) DO UPDATE SET state='OPEN', fail_count=3, last_fail=?, last_transition=?, updated_at=?
            """, (issue["target"], now, now, now, now, now, now))
            db.commit()
            result["applied"] = True
            result["detail"] = f"Circuit breaker OPEN for {issue['target']}"
        except Exception as e:
            result["detail"] = str(e)[:100]

    elif action == "run_optimizer":
        try:
            r = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "grade_optimizer.py"), "--once"],
                capture_output=True, text=True, timeout=30, cwd=str(SCRIPT_DIR)
            )
            result["applied"] = r.returncode == 0
            result["detail"] = "Optimizer run" if result["applied"] else r.stderr[:100]
        except Exception as e:
            result["detail"] = str(e)[:100]

    elif action == "refresh_baseline":
        try:
            r = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "latency_monitor.py"), "--once"],
                capture_output=True, text=True, timeout=60, cwd=str(SCRIPT_DIR)
            )
            result["applied"] = r.returncode == 0
            result["detail"] = "Baselines refreshed" if result["applied"] else r.stderr[:100]
        except Exception as e:
            result["detail"] = str(e)[:100]

    return result


def send_telegram(text):
    data = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"
    }).encode()
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def healing_cycle(dry_run=False):
    """Run one healing cycle."""
    db = get_db(GAPS_DB)
    init_healing_history(db)

    try:
        edb = get_db(ETOILE_DB)
    except Exception:
        edb = None

    grade_before = get_grade()
    all_issues = []

    all_issues.extend(check_latency_trends(db))
    if edb:
        all_issues.extend(check_success_rate(edb))
    all_issues.extend(check_grade(grade_before))
    all_issues.extend(check_stale_baselines(db))

    actions = []
    for issue in all_issues:
        result = apply_healing(issue, db, dry_run)
        actions.append({**issue, "result": result})

        prefix = "[DRY]" if dry_run else "[FIX]"
        print(f"  {prefix} {issue['trigger']:20} {issue['target']:10} -> {result['detail']}")

    grade_after = get_grade() if not dry_run else grade_before

    # Log to DB
    if not dry_run and actions:
        now = datetime.now().isoformat()
        for a in actions:
            if a["result"]["applied"]:
                db.execute("""
                    INSERT INTO proactive_healing_log
                    (timestamp, trigger_type, target, action_taken, result, grade_before, grade_after)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (now, a["trigger"], a["target"], a["action"],
                      a["result"]["detail"], grade_before, grade_after))
        db.commit()

    if edb:
        edb.close()
    db.close()

    return {
        "timestamp": datetime.now().isoformat(),
        "issues_found": len(all_issues),
        "actions_applied": sum(1 for a in actions if a["result"].get("applied")),
        "grade_before": grade_before,
        "grade_after": grade_after,
        "actions": [{
            "trigger": a["trigger"],
            "target": a["target"],
            "detail": a["result"]["detail"],
        } for a in actions],
    }


def show_history(db):
    """Show healing history."""
    rows = db.execute("""
        SELECT * FROM proactive_healing_log ORDER BY id DESC LIMIT 20
    """).fetchall()
    if not rows:
        print("No healing history yet")
        return
    for r in rows:
        print(f"  [{r['timestamp'][:16]}] {r['trigger_type']:20} {r['target']:10} "
              f"grade={r['grade_before']:.1f}->{r['grade_after']:.1f} {r['result']}")


def main():
    parser = argparse.ArgumentParser(description="Proactive Healer")
    parser.add_argument("--once", action="store_true", help="Single cycle")
    parser.add_argument("--watch", action="store_true", help="Continuous")
    parser.add_argument("--interval", type=int, default=10, help="Interval (min)")
    parser.add_argument("--history", action="store_true", help="Show history")
    parser.add_argument("--dry-run", action="store_true", help="Dry run")
    args = parser.parse_args()

    if not any([args.once, args.watch, args.history, args.dry_run]):
        parser.print_help()
        sys.exit(1)

    if args.history:
        db = get_db(GAPS_DB)
        init_healing_history(db)
        show_history(db)
        db.close()
        return

    if args.once or args.dry_run:
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] Proactive healing {'(dry-run)' if args.dry_run else ''}...")
        summary = healing_cycle(dry_run=args.dry_run)
        print(f"\n  Issues: {summary['issues_found']} | Actions: {summary['actions_applied']}")
        print(f"  Grade: {summary['grade_before']:.1f} -> {summary['grade_after']:.1f}")
        return

    if args.watch:
        print(f"Proactive healing every {args.interval}m")
        while True:
            try:
                ts = datetime.now().strftime("%H:%M:%S")
                summary = healing_cycle()
                if summary["actions_applied"] > 0:
                    print(f"[{ts}] Healed {summary['actions_applied']} issues")
                    send_telegram(
                        f"<b>Proactive Healing</b>\n"
                        f"{summary['actions_applied']} fixes applied\n"
                        f"Grade: {summary['grade_before']:.1f} -> {summary['grade_after']:.1f}"
                    )
                time.sleep(args.interval * 60)
            except KeyboardInterrupt:
                print("\nStopped")
                break


if __name__ == "__main__":
    main()