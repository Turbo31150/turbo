#!/usr/bin/env python3
"""COWORK Dispatcher — Route tasks to cowork scripts via pattern matching.
Integrates with etoile.db pattern agents and executes scripts from dev/.
"""

import sqlite3
import subprocess
import sys
import os
import json
import re
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, '..', 'etoile.db')
DEV_PATH = os.path.join(BASE, 'dev')
PYTHON = sys.executable


def get_cowork_patterns(db_path=DB_PATH):
    """Load all COWORK patterns from etoile.db."""
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    rows = db.execute("""
        SELECT p.pattern_id, p.agent_id, p.pattern_type, p.keywords, p.description,
               p.model_primary, p.strategy, p.priority
        FROM agent_patterns p
        WHERE p.pattern_id LIKE 'PAT_CW_%'
        ORDER BY p.priority ASC
    """).fetchall()
    db.close()
    return [dict(r) for r in rows]


def get_scripts_for_pattern(pattern_id, db_path=DB_PATH):
    """Get scripts mapped to a pattern."""
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    rows = db.execute("""
        SELECT script_name, script_path, status
        FROM cowork_script_mapping
        WHERE pattern_id = ? AND status = 'active'
    """, (pattern_id,)).fetchall()
    db.close()
    return [dict(r) for r in rows]


def match_pattern(query, patterns):
    """Match a query to the best COWORK pattern using keyword scoring."""
    query_lower = query.lower()
    query_words = set(re.findall(r'\w+', query_lower))
    scores = []

    for pat in patterns:
        keywords = set((pat.get('keywords') or '').split(','))
        # Score: keyword overlap + description match
        keyword_score = len(query_words & keywords)
        desc_words = set(re.findall(r'\w+', (pat.get('description') or '').lower()))
        desc_score = len(query_words & desc_words) * 0.5
        # Priority bonus (lower priority number = higher bonus)
        priority_bonus = (6 - pat['priority']) * 0.3
        total = keyword_score + desc_score + priority_bonus
        if total > 0:
            scores.append((total, pat))

    scores.sort(key=lambda x: -x[0])
    return scores


def execute_script(script_name, args=None, timeout=60):
    """Execute a cowork script and return output."""
    script_path = os.path.join(DEV_PATH, f"{script_name}.py")
    if not os.path.exists(script_path):
        return {"error": f"Script not found: {script_path}"}

    cmd = [PYTHON, script_path]
    if args:
        cmd.extend(args)
    else:
        cmd.append("--once")

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, cwd=DEV_PATH
        )
        return {
            "script": script_name,
            "returncode": result.returncode,
            "stdout": result.stdout[-2000:] if result.stdout else "",
            "stderr": result.stderr[-500:] if result.stderr else "",
            "success": result.returncode == 0
        }
    except subprocess.TimeoutExpired:
        return {"script": script_name, "error": "timeout", "success": False}
    except Exception as e:
        return {"script": script_name, "error": str(e), "success": False}


def dispatch(query, execute=False, top_n=3):
    """Dispatch a query: find matching patterns and optionally execute scripts."""
    patterns = get_cowork_patterns()
    matches = match_pattern(query, patterns)

    result = {
        "query": query,
        "matches": [],
        "timestamp": datetime.now().isoformat()
    }

    for score, pat in matches[:top_n]:
        scripts = get_scripts_for_pattern(pat['pattern_id'])
        match_entry = {
            "pattern_id": pat['pattern_id'],
            "agent_id": pat['agent_id'],
            "description": pat['description'],
            "score": round(score, 2),
            "scripts": [s['script_name'] for s in scripts],
            "script_count": len(scripts)
        }

        if execute and scripts:
            # Execute first matching script
            exec_result = execute_script(scripts[0]['script_name'])
            match_entry["execution"] = exec_result

        result["matches"].append(match_entry)

    return result


def list_all():
    """List all patterns and their scripts."""
    patterns = get_cowork_patterns()
    total_scripts = 0
    for pat in patterns:
        scripts = get_scripts_for_pattern(pat['pattern_id'])
        total_scripts += len(scripts)
        print(f"\n{pat['pattern_id']} ({pat['agent_id']})")
        print(f"  {pat['description']}")
        print(f"  Strategy: {pat['strategy']} | Priority: {pat['priority']}")
        print(f"  Scripts ({len(scripts)}): {', '.join(s['script_name'] for s in scripts[:5])}"
              + (f" +{len(scripts)-5} more" if len(scripts) > 5 else ""))

    print(f"\n--- Total: {len(patterns)} patterns, {total_scripts} scripts ---")


def health_check():
    """Check which scripts actually exist and are parseable."""
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    rows = db.execute("SELECT * FROM cowork_script_mapping").fetchall()
    db.close()

    ok = 0
    missing = 0
    errors = []

    for r in rows:
        script_path = os.path.join(DEV_PATH, f"{r['script_name']}.py")
        if os.path.exists(script_path):
            try:
                with open(script_path, 'r', encoding='utf-8', errors='ignore') as f:
                    compile(f.read(), script_path, 'exec')
                ok += 1
            except SyntaxError as e:
                errors.append({"script": r['script_name'], "error": str(e)})
        else:
            missing += 1

    result = {
        "total": len(rows),
        "ok": ok,
        "missing": missing,
        "syntax_errors": len(errors),
        "errors": errors[:10]
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="COWORK Dispatcher")
    parser.add_argument("--dispatch", type=str, help="Query to dispatch")
    parser.add_argument("--execute", action="store_true", help="Execute matched scripts")
    parser.add_argument("--list", action="store_true", help="List all patterns")
    parser.add_argument("--health", action="store_true", help="Health check scripts")
    parser.add_argument("--once", action="store_true", help="Alias for --health")
    args = parser.parse_args()

    if args.dispatch:
        result = dispatch(args.dispatch, execute=args.execute)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.list:
        list_all()
    elif args.health or args.once:
        health_check()
    else:
        parser.print_help()
