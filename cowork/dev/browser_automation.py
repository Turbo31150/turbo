#!/usr/bin/env python3
"""browser_automation.py — Enregistre et rejoue des macros de navigation.

Enregistre des sequences d'actions browser (navigate, click, scroll, fill)
comme pipelines JSON rejouables via browser_navigator.py.

Usage:
    python dev/browser_automation.py --once
    python dev/browser_automation.py --record MACRO_NAME
    python dev/browser_automation.py --replay MACRO_NAME
    python dev/browser_automation.py --list
    python dev/browser_automation.py --test
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
DB_PATH = DEV / "data" / "browser_macros.db"
WS_URL = "http://127.0.0.1:9742"

# Pre-built macro templates
TEMPLATES = {
    "google_search": {
        "name": "google_search",
        "description": "Recherche Google et lit resultats",
        "steps": [
            {"action": "navigate", "params": {"url": "https://www.google.com"}},
            {"action": "fill", "params": {"selector": "textarea[name=q]", "value": "{query}"}},
            {"action": "press_key", "params": {"key": "Enter"}},
            {"action": "wait", "params": {"seconds": 2}},
            {"action": "read_page", "params": {}},
        ],
    },
    "github_check": {
        "name": "github_check",
        "description": "Verifier les notifications GitHub",
        "steps": [
            {"action": "navigate", "params": {"url": "https://github.com/notifications"}},
            {"action": "wait", "params": {"seconds": 3}},
            {"action": "read_page", "params": {}},
        ],
    },
    "mexc_check": {
        "name": "mexc_check",
        "description": "Verifier les positions MEXC",
        "steps": [
            {"action": "navigate", "params": {"url": "https://futures.mexc.com/exchange"}},
            {"action": "wait", "params": {"seconds": 5}},
            {"action": "screenshot", "params": {}},
        ],
    },
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS macros (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE, description TEXT,
        steps TEXT, created REAL, last_run REAL,
        run_count INTEGER DEFAULT 0, status TEXT DEFAULT 'active')""")
    db.execute("""CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, macro_name TEXT, success INTEGER,
        duration_s REAL, error TEXT)""")
    db.commit()
    return db


def call_browser_api(action, params=None):
    """Call browser MCP endpoint via REST API."""
    endpoint_map = {
        "navigate": "/api/browser/navigate",
        "click": "/api/browser/click",
        "scroll": "/api/browser/scroll",
        "fill": "/api/browser/fill",
        "read_page": "/api/browser/read",
        "screenshot": "/api/browser/screenshot",
        "press_key": "/api/browser/press_key",
        "go_back": "/api/browser/back",
        "go_forward": "/api/browser/forward",
    }

    endpoint = endpoint_map.get(action)
    if not endpoint:
        if action == "wait":
            time.sleep(params.get("seconds", 1) if params else 1)
            return {"success": True, "action": "wait"}
        return {"error": f"Unknown action: {action}"}

    try:
        url = f"{WS_URL}{endpoint}"
        data = json.dumps(params or {}).encode()
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"error": str(e)}


def save_macro(name, description, steps):
    """Save a macro to the database."""
    db = init_db()
    db.execute(
        "INSERT OR REPLACE INTO macros (name, description, steps, created) VALUES (?,?,?,?)",
        (name, description, json.dumps(steps), time.time())
    )
    db.commit()
    db.close()


def replay_macro(name, variables=None):
    """Replay a saved macro."""
    db = init_db()
    row = db.execute("SELECT steps FROM macros WHERE name=?", (name,)).fetchone()
    if not row:
        # Check templates
        if name in TEMPLATES:
            steps = TEMPLATES[name]["steps"]
        else:
            db.close()
            return {"error": f"Macro '{name}' not found"}
    else:
        steps = json.loads(row[0])

    variables = variables or {}
    start = time.time()
    results = []
    success = True

    for i, step in enumerate(steps):
        # Variable substitution
        params = step.get("params", {})
        for k, v in params.items():
            if isinstance(v, str):
                for var_name, var_val in variables.items():
                    params[k] = v.replace(f"{{{var_name}}}", str(var_val))

        result = call_browser_api(step["action"], params)
        results.append({
            "step": i + 1,
            "action": step["action"],
            "result": result,
        })

        if "error" in result and result["error"]:
            success = False
            break

    duration = time.time() - start

    # Record run
    db.execute(
        "INSERT INTO runs (ts, macro_name, success, duration_s, error) VALUES (?,?,?,?,?)",
        (time.time(), name, 1 if success else 0, duration,
         results[-1].get("result", {}).get("error") if not success else None)
    )
    db.execute(
        "UPDATE macros SET last_run=?, run_count=run_count+1 WHERE name=?",
        (time.time(), name)
    )
    db.commit()
    db.close()

    return {
        "macro": name,
        "success": success,
        "steps_executed": len(results),
        "duration_s": round(duration, 2),
        "results": results,
    }


def list_macros():
    """List all macros."""
    db = init_db()
    rows = db.execute(
        "SELECT name, description, run_count, last_run, status FROM macros ORDER BY name"
    ).fetchall()
    db.close()

    macros = []
    # Add DB macros
    for r in rows:
        macros.append({
            "name": r[0], "description": r[1],
            "run_count": r[2],
            "last_run": datetime.fromtimestamp(r[3]).isoformat() if r[3] else None,
            "status": r[4], "source": "db",
        })
    # Add templates
    for name, tmpl in TEMPLATES.items():
        if not any(m["name"] == name for m in macros):
            macros.append({
                "name": name, "description": tmpl["description"],
                "steps": len(tmpl["steps"]), "source": "template",
            })
    return macros


def do_once():
    """Install templates + report."""
    db = init_db()
    installed = 0
    for name, tmpl in TEMPLATES.items():
        existing = db.execute("SELECT COUNT(*) FROM macros WHERE name=?", (name,)).fetchone()[0]
        if existing == 0:
            db.execute(
                "INSERT INTO macros (name, description, steps, created) VALUES (?,?,?,?)",
                (name, tmpl["description"], json.dumps(tmpl["steps"]), time.time())
            )
            installed += 1
    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "templates_installed": installed,
        "macros": list_macros(),
    }


def main():
    parser = argparse.ArgumentParser(description="Browser Automation — Record & replay macros")
    parser.add_argument("--once", action="store_true", help="Install templates + status")
    parser.add_argument("--record", metavar="NAME", help="Record a new macro")
    parser.add_argument("--replay", metavar="NAME", help="Replay a macro")
    parser.add_argument("--list", action="store_true", help="List all macros")
    parser.add_argument("--test", action="store_true", help="Test templates")
    parser.add_argument("--var", action="append", help="Variable KEY=VALUE for replay")
    args = parser.parse_args()

    if args.list:
        print(json.dumps(list_macros(), ensure_ascii=False, indent=2))
    elif args.replay:
        variables = {}
        if args.var:
            for v in args.var:
                if "=" in v:
                    k, val = v.split("=", 1)
                    variables[k] = val
        result = replay_macro(args.replay, variables)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.test:
        result = replay_macro("google_search", {"query": "JARVIS AI assistant"})
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        result = do_once()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
