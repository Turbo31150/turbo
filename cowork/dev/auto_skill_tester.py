#!/usr/bin/env python3
"""auto_skill_tester.py — Teste automatiquement les skills generees par brain.py.

Charge toutes les skills JARVIS, les teste en dry-run,
score la fiabilite, et flag celles qui sont cassees.

Usage:
    python dev/auto_skill_tester.py --once
    python dev/auto_skill_tester.py --test-all
    python dev/auto_skill_tester.py --test-new
    python dev/auto_skill_tester.py --report
"""
import argparse
import json
import os
import sqlite3
import time
import urllib.request
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
from _paths import ETOILE_DB
DB_PATH = DEV / "data" / "skill_tests.db"
WS_URL = "http://127.0.0.1:9742"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS test_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, skill_name TEXT, status TEXT,
        score REAL, details TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, total_skills INTEGER, passed INTEGER,
        failed INTEGER, score REAL, report TEXT)""")
    db.commit()
    return db


def get_all_skills():
    """Get skills from etoile.db."""
    if not ETOILE_DB.exists():
        return []
    try:
        conn = sqlite3.connect(str(ETOILE_DB))
        conn.row_factory = sqlite3.Row

        # Check if skills table exists
        has_skills = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='skills'"
        ).fetchone()[0]
        if not has_skills:
            conn.close()
            return []

        rows = conn.execute(
            "SELECT name, triggers, action_type, action, category, confidence FROM skills ORDER BY name"
        ).fetchall()
        conn.close()

        skills = []
        for r in rows:
            skills.append({
                "name": r["name"],
                "triggers": json.loads(r["triggers"]) if r["triggers"] else [],
                "action_type": r["action_type"],
                "action": r["action"],
                "category": r["category"],
                "confidence": r["confidence"] if r["confidence"] else 0,
            })
        return skills
    except Exception as e:
        print(f"[WARN] get_all_skills: {e}")
        return []


def get_voice_commands():
    """Get voice commands from etoile.db."""
    if not ETOILE_DB.exists():
        return []
    try:
        conn = sqlite3.connect(str(ETOILE_DB))
        conn.row_factory = sqlite3.Row

        has_cmds = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='voice_commands'"
        ).fetchone()[0]
        if not has_cmds:
            conn.close()
            return []

        rows = conn.execute(
            "SELECT name, trigger_text, action_type, action FROM voice_commands LIMIT 200"
        ).fetchall()
        conn.close()

        commands = []
        for r in rows:
            commands.append({
                "name": r["name"],
                "trigger": r["trigger_text"],
                "action_type": r["action_type"],
                "action": r["action"],
            })
        return commands
    except Exception as e:
        return []


def test_skill(skill):
    """Test a single skill (dry-run validation)."""
    score = 0.0
    issues = []

    # 1. Check structure
    if skill.get("name"):
        score += 0.2
    else:
        issues.append("missing_name")

    if skill.get("triggers") and len(skill["triggers"]) > 0:
        score += 0.2
    else:
        issues.append("no_triggers")

    if skill.get("action_type") in ("python", "hotkey", "pipeline", "domino", "mcp"):
        score += 0.2
    else:
        issues.append(f"invalid_action_type: {skill.get('action_type')}")

    if skill.get("action"):
        score += 0.2
    else:
        issues.append("missing_action")

    # 2. Check for dangerous patterns
    action_str = str(skill.get("action", "")).lower()
    dangerous = ["rm -rf", "format c:", "del /f /s", "shutdown", "rmdir /s"]
    if any(d in action_str for d in dangerous):
        score = 0.0
        issues.append("DANGEROUS_ACTION")

    # 3. Check confidence
    if skill.get("confidence", 0) >= 0.7:
        score += 0.1
    elif skill.get("confidence", 0) >= 0.5:
        score += 0.05

    # 4. Check trigger quality
    triggers = skill.get("triggers", [])
    if triggers:
        avg_len = sum(len(t) for t in triggers) / len(triggers)
        if avg_len >= 3:
            score += 0.1
        if len(triggers) >= 2:
            score += 0.05

    # 5. Check if action endpoint exists (for MCP)
    if skill.get("action_type") == "mcp":
        try:
            req = urllib.request.Request(f"{WS_URL}/api/status", method="GET")
            with urllib.request.urlopen(req, timeout=3):
                score += 0.05
        except Exception:
            issues.append("ws_server_unreachable")

    return {
        "name": skill.get("name", "unknown"),
        "score": round(min(score, 1.0), 3),
        "status": "pass" if score >= 0.5 else "fail",
        "issues": issues,
    }


def test_command(cmd):
    """Test a voice command (basic validation)."""
    score = 0.0
    issues = []

    if cmd.get("name"):
        score += 0.25
    else:
        issues.append("missing_name")

    if cmd.get("trigger") and len(cmd["trigger"]) >= 2:
        score += 0.25
    else:
        issues.append("missing_trigger")

    if cmd.get("action_type") in ("python", "hotkey", "pipeline", "domino", "mcp"):
        score += 0.25
    else:
        issues.append(f"invalid_action_type: {cmd.get('action_type')}")

    if cmd.get("action"):
        score += 0.25
    else:
        issues.append("missing_action")

    return {
        "name": cmd.get("name", "unknown"),
        "score": round(score, 3),
        "status": "pass" if score >= 0.5 else "fail",
        "issues": issues,
    }


def do_test_all():
    """Test all skills and commands."""
    db = init_db()
    skills = get_all_skills()
    commands = get_voice_commands()

    results = {"skills": [], "commands": []}
    passed = 0
    failed = 0

    # Test skills
    for skill in skills:
        result = test_skill(skill)
        results["skills"].append(result)
        db.execute(
            "INSERT INTO test_results (ts, skill_name, status, score, details) VALUES (?,?,?,?,?)",
            (time.time(), result["name"], result["status"], result["score"], json.dumps(result))
        )
        if result["status"] == "pass":
            passed += 1
        else:
            failed += 1

    # Test sample commands
    for cmd in commands[:50]:
        result = test_command(cmd)
        results["commands"].append(result)
        if result["status"] == "pass":
            passed += 1
        else:
            failed += 1

    total = passed + failed
    score = passed / max(total, 1)

    report = {
        "ts": datetime.now().isoformat(),
        "total_tested": total,
        "skills_tested": len(results["skills"]),
        "commands_tested": len(results["commands"]),
        "passed": passed,
        "failed": failed,
        "score": round(score, 3),
        "failed_items": [r for r in results["skills"] + results["commands"] if r["status"] == "fail"][:10],
    }

    db.execute(
        "INSERT INTO runs (ts, total_skills, passed, failed, score, report) VALUES (?,?,?,?,?,?)",
        (time.time(), total, passed, failed, score, json.dumps(report))
    )
    db.commit()
    db.close()
    return report


def get_report():
    """Get historical test reports."""
    db = init_db()
    rows = db.execute("SELECT * FROM runs ORDER BY ts DESC LIMIT 10").fetchall()
    db.close()
    reports = []
    for r in rows:
        reports.append({
            "ts": datetime.fromtimestamp(r[1]).isoformat() if r[1] else None,
            "total": r[2], "passed": r[3], "failed": r[4],
            "score": r[5],
        })
    return reports


def main():
    parser = argparse.ArgumentParser(description="Auto Skill Tester — Validate JARVIS skills")
    parser.add_argument("--once", "--test-all", action="store_true", help="Test all skills")
    parser.add_argument("--test-new", action="store_true", help="Test only new/recent skills")
    parser.add_argument("--report", action="store_true", help="Show test history")
    args = parser.parse_args()

    if args.report:
        report = get_report()
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        result = do_test_all()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
