#!/usr/bin/env python3
"""jarvis_rule_engine.py (#183) — IF/THEN/ELSE rule engine for automation.

Rules stored in SQLite as JSON conditions and actions.
Conditions: time, gpu_temp, disk, cpu_pct, mem_pct
Actions: shell command execution

Usage:
    python dev/jarvis_rule_engine.py --once
    python dev/jarvis_rule_engine.py --add '{"name":"high_temp","condition":{"type":"gpu_temp","operator":">","value":80},"action":"echo GPU HOT","else_action":"echo GPU OK"}'
    python dev/jarvis_rule_engine.py --list
    python dev/jarvis_rule_engine.py --evaluate
    python dev/jarvis_rule_engine.py --test RULE_ID
"""
import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "rule_engine.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        condition_json TEXT NOT NULL,
        action TEXT NOT NULL,
        else_action TEXT DEFAULT '',
        enabled INTEGER DEFAULT 1,
        priority INTEGER DEFAULT 50,
        created_at REAL,
        last_evaluated REAL,
        last_result TEXT,
        eval_count INTEGER DEFAULT 0
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS eval_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rule_id INTEGER,
        ts REAL,
        condition_met INTEGER,
        action_taken TEXT,
        output TEXT,
        FOREIGN KEY (rule_id) REFERENCES rules(id)
    )""")
    db.commit()
    return db


def evaluate_condition(cond):
    """Evaluate a single condition dict. Returns (bool, actual_value)."""
    ctype = cond.get("type", "")
    op = cond.get("operator", "==")
    target = cond.get("value")

    actual = None

    if ctype == "time":
        # value is "HH:MM", operator is ">", "<", "=="
        now = datetime.now().strftime("%H:%M")
        actual = now
        if op == ">":
            return now > target, actual
        elif op == "<":
            return now < target, actual
        elif op == "==":
            return now == target, actual
        elif op == ">=":
            return now >= target, actual
        elif op == "<=":
            return now <= target, actual

    elif ctype == "gpu_temp":
        # Try nvidia-smi
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5
            )
            temps = [int(t.strip()) for t in r.stdout.strip().split("\n") if t.strip()]
            actual = max(temps) if temps else 0
        except Exception:
            actual = 0

    elif ctype == "disk":
        # value is percentage, checks C: by default
        drive = cond.get("drive", "C:/")
        try:
            usage = shutil.disk_usage(drive)
            actual = round(usage.used / usage.total * 100, 1)
        except Exception:
            actual = 0

    elif ctype == "cpu_pct":
        # Rough CPU estimate via wmic
        try:
            r = subprocess.run(
                ["wmic", "cpu", "get", "LoadPercentage", "/format:csv"],
                capture_output=True, text=True, timeout=5
            )
            for line in r.stdout.strip().split("\n"):
                parts = line.strip().split(",")
                if len(parts) >= 2 and parts[-1].strip().isdigit():
                    actual = int(parts[-1].strip())
                    break
            if actual is None:
                actual = 0
        except Exception:
            actual = 0

    elif ctype == "mem_pct":
        try:
            r = subprocess.run(
                ["wmic", "os", "get", "FreePhysicalMemory,TotalVisibleMemorySize", "/format:csv"],
                capture_output=True, text=True, timeout=5
            )
            for line in r.stdout.strip().split("\n"):
                parts = line.strip().split(",")
                if len(parts) >= 3:
                    try:
                        free = int(parts[1].strip())
                        total = int(parts[2].strip())
                        actual = round((1 - free / total) * 100, 1)
                        break
                    except ValueError:
                        continue
            if actual is None:
                actual = 0
        except Exception:
            actual = 0

    elif ctype == "port_open":
        import socket
        port = int(target)
        host = cond.get("host", "127.0.0.1")
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            result = s.connect_ex((host, port))
            s.close()
            actual = 1 if result == 0 else 0
            target = 1
        except Exception:
            actual = 0
            target = 1

    else:
        return False, f"unknown_type:{ctype}"

    # Compare
    if actual is None:
        return False, None
    try:
        target_num = float(target)
        actual_num = float(actual)
        if op == ">":
            return actual_num > target_num, actual
        elif op == "<":
            return actual_num < target_num, actual
        elif op == ">=":
            return actual_num >= target_num, actual
        elif op == "<=":
            return actual_num <= target_num, actual
        elif op == "==":
            return actual_num == target_num, actual
        elif op == "!=":
            return actual_num != target_num, actual
    except (ValueError, TypeError):
        return str(actual) == str(target), actual

    return False, actual


def add_rule(db, rule_json):
    """Add a rule from JSON string."""
    rule = json.loads(rule_json) if isinstance(rule_json, str) else rule_json
    name = rule.get("name", f"rule_{int(time.time())}")
    condition = json.dumps(rule["condition"])
    action = rule.get("action", "echo no_action")
    else_action = rule.get("else_action", "")
    priority = rule.get("priority", 50)

    db.execute(
        "INSERT OR REPLACE INTO rules (name, condition_json, action, else_action, priority, created_at) VALUES (?,?,?,?,?,?)",
        (name, condition, action, else_action, priority, time.time())
    )
    db.commit()
    return {"status": "ok", "name": name, "condition": rule["condition"], "action": action}


def list_rules(db):
    """List all rules."""
    rows = db.execute(
        "SELECT id, name, condition_json, action, else_action, enabled, priority, eval_count, last_result FROM rules ORDER BY priority DESC"
    ).fetchall()
    rules = []
    for r in rows:
        rules.append({
            "id": r[0], "name": r[1],
            "condition": json.loads(r[2]),
            "action": r[3], "else_action": r[4],
            "enabled": bool(r[5]), "priority": r[6],
            "eval_count": r[7], "last_result": r[8]
        })
    return {"status": "ok", "count": len(rules), "rules": rules}


def evaluate_rules(db):
    """Evaluate all enabled rules."""
    rows = db.execute(
        "SELECT id, name, condition_json, action, else_action FROM rules WHERE enabled=1 ORDER BY priority DESC"
    ).fetchall()

    results = []
    for r in rows:
        rule_id, name, cond_json, action, else_action = r
        cond = json.loads(cond_json)
        met, actual = evaluate_condition(cond)

        chosen_action = action if met else (else_action or None)
        output = ""

        if chosen_action:
            try:
                proc = subprocess.run(
                    chosen_action, shell=True, capture_output=True, text=True, timeout=10
                )
                output = proc.stdout.strip()[:500]
            except Exception as e:
                output = f"error: {e}"

        db.execute(
            "UPDATE rules SET last_evaluated=?, last_result=?, eval_count=eval_count+1 WHERE id=?",
            (time.time(), "met" if met else "not_met", rule_id)
        )
        db.execute(
            "INSERT INTO eval_log (rule_id, ts, condition_met, action_taken, output) VALUES (?,?,?,?,?)",
            (rule_id, time.time(), int(met), chosen_action or "none", output)
        )
        results.append({
            "rule": name, "condition_met": met,
            "actual_value": actual, "action_taken": chosen_action or "none",
            "output": output
        })

    db.commit()
    return {"status": "ok", "evaluated": len(results), "results": results}


def test_rule(db, rule_id):
    """Test a single rule without executing action."""
    row = db.execute(
        "SELECT id, name, condition_json, action, else_action FROM rules WHERE id=? OR name=?",
        (rule_id if str(rule_id).isdigit() else -1, str(rule_id))
    ).fetchone()

    if not row:
        return {"status": "error", "error": f"Rule not found: {rule_id}"}

    _, name, cond_json, action, else_action = row
    cond = json.loads(cond_json)
    met, actual = evaluate_condition(cond)

    return {
        "status": "ok", "rule": name,
        "condition": cond, "condition_met": met,
        "actual_value": actual,
        "would_execute": action if met else (else_action or "nothing"),
        "dry_run": True
    }


def once(db):
    """Run once: show stats and evaluate all rules."""
    rules = list_rules(db)
    log_count = db.execute("SELECT COUNT(*) FROM eval_log").fetchone()[0]
    eval_result = evaluate_rules(db)
    return {
        "status": "ok", "mode": "once",
        "rules_count": rules["count"],
        "eval_log_entries": log_count,
        "evaluation": eval_result
    }


def main():
    parser = argparse.ArgumentParser(description="JARVIS Rule Engine (#183) — IF/THEN/ELSE automation rules")
    parser.add_argument("--add", type=str, help="Add rule as JSON string")
    parser.add_argument("--list", action="store_true", help="List all rules")
    parser.add_argument("--evaluate", action="store_true", help="Evaluate all enabled rules")
    parser.add_argument("--test", type=str, help="Test a rule by ID or name (dry run)")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    db = init_db()

    if args.add:
        result = add_rule(db, args.add)
    elif args.list:
        result = list_rules(db)
    elif args.evaluate:
        result = evaluate_rules(db)
    elif args.test:
        result = test_rule(db, args.test)
    elif args.once:
        result = once(db)
    else:
        parser.print_help()
        return

    print(json.dumps(result, indent=2, default=str))
    db.close()


if __name__ == "__main__":
    main()
