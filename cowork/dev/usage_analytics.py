#!/usr/bin/env python3
"""JARVIS Usage Analytics — Analytics d'utilisation du systeme."""
import json, sys, os, sqlite3, glob
from _paths import JARVIS_DB
from datetime import datetime
from collections import Counter

ANALYTICS_DB = "C:/Users/franc/.openclaw/workspace/dev/analytics.db"
JARVIS_DB = str(JARVIS_DB)
LOG_DIR = os.path.expandvars(r"%USERPROFILE%\.openclaw\agents\main\logs")
SESSION_DIR = os.path.expandvars(r"%USERPROFILE%\.openclaw\agents\main\sessions")

def init_db():
    conn = sqlite3.connect(ANALYTICS_DB)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT,
        total_commands INTEGER, total_sessions INTEGER,
        total_errors INTEGER, avg_latency_ms REAL, data TEXT
    )""")
    conn.commit()
    return conn

def analyze_commands():
    """Analyse les commandes les plus utilisees depuis jarvis.db."""
    if not os.path.exists(JARVIS_DB):
        return {"error": "jarvis.db not found"}
    conn = sqlite3.connect(JARVIS_DB)
    c = conn.cursor()
    try:
        c.execute("SELECT COUNT(*) FROM commands")
        total = c.fetchone()[0]
        c.execute("SELECT category, COUNT(*) FROM commands GROUP BY category ORDER BY COUNT(*) DESC LIMIT 15")
        categories = {r[0]: r[1] for r in c.fetchall()}
    except:
        total = 0; categories = {}

    # Skills
    try:
        c.execute("SELECT COUNT(*) FROM skills")
        total_skills = c.fetchone()[0]
    except:
        total_skills = 0

    conn.close()
    return {"total_commands": total, "categories": categories, "total_skills": total_skills}

def analyze_sessions():
    """Compte les sessions OpenClaw."""
    session_file = os.path.join(SESSION_DIR, "sessions.json")
    if os.path.exists(session_file):
        try:
            with open(session_file) as f:
                sessions = json.load(f)
            return len(sessions)
        except: return 0
    # Count .jsonl files
    jsonl_files = glob.glob(os.path.join(SESSION_DIR, "*.jsonl"))
    return len(jsonl_files)

def analyze_logs():
    """Analyse les logs OpenClaw pour erreurs et latences."""
    errors = Counter()
    total_lines = 0

    if not os.path.isdir(LOG_DIR):
        return {"total_lines": 0, "errors": {}, "error_count": 0}

    log_files = sorted(glob.glob(os.path.join(LOG_DIR, "*.log")))[-5:]  # Last 5 logs
    for lf in log_files:
        try:
            with open(lf, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    total_lines += 1
                    ll = line.lower()
                    if "error" in ll: errors["error"] += 1
                    elif "timeout" in ll: errors["timeout"] += 1
                    elif "fail" in ll: errors["fail"] += 1
        except: pass

    return {"total_lines": total_lines, "errors": dict(errors.most_common(10)), "error_count": sum(errors.values())}

def generate_report(conn):
    cmds = analyze_commands()
    sessions = analyze_sessions()
    logs = analyze_logs()

    data = {"commands": cmds, "sessions": sessions, "logs": logs}

    # Save snapshot
    c = conn.cursor()
    c.execute("INSERT INTO snapshots (ts, total_commands, total_sessions, total_errors, avg_latency_ms, data) VALUES (?,?,?,?,?,?)",
              (datetime.now().isoformat(), cmds.get("total_commands", 0), sessions,
               logs.get("error_count", 0), 0, json.dumps(data)))
    conn.commit()

    return data

if __name__ == "__main__":
    conn = init_db()

    if "--once" in sys.argv or "--report" in sys.argv:
        data = generate_report(conn)
        cmds = data["commands"]
        logs = data["logs"]
        print(f"[USAGE ANALYTICS] {datetime.now().strftime('%H:%M')}")
        print(f"\n  Commands: {cmds.get('total_commands', 0)} | Skills: {cmds.get('total_skills', 0)}")
        print(f"  Sessions: {data['sessions']}")
        print(f"  Log lines: {logs['total_lines']} | Errors: {logs['error_count']}")
        if cmds.get("categories"):
            print(f"\n  Top categories:")
            for cat, count in list(cmds["categories"].items())[:10]:
                print(f"    {cat}: {count}")
        if logs.get("errors"):
            print(f"\n  Error types:")
            for etype, count in logs["errors"].items():
                print(f"    {etype}: {count}")

    elif "--top-commands" in sys.argv:
        cmds = analyze_commands()
        print(f"[TOP COMMANDS] {cmds.get('total_commands', 0)} total")
        for cat, count in cmds.get("categories", {}).items():
            print(f"  {cat}: {count}")

    elif "--errors" in sys.argv:
        logs = analyze_logs()
        print(f"[ERRORS] {logs['error_count']} in {logs['total_lines']} lines")
        for etype, count in logs.get("errors", {}).items():
            print(f"  {etype}: {count}")

    elif "--history" in sys.argv:
        c = conn.cursor()
        c.execute("SELECT ts, total_commands, total_sessions, total_errors FROM snapshots ORDER BY id DESC LIMIT 10")
        rows = c.fetchall()
        print(f"[ANALYTICS HISTORY] {len(rows)} snapshots:")
        for r in rows:
            print(f"  {r[0][:16]}: cmds={r[1]} sessions={r[2]} errors={r[3]}")

    else:
        print("Usage: usage_analytics.py --once | --top-commands | --errors | --history")

    conn.close()