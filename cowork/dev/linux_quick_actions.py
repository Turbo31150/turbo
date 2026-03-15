#!/usr/bin/env python3
"""win_quick_actions.py — #206 Quick action catalog with fuzzy search and MRU.
Usage:
    python dev/win_quick_actions.py --list
    python dev/win_quick_actions.py --run "open chrome"
    python dev/win_quick_actions.py --add '{"name":"open chrome","command":"start chrome","category":"browser"}'
    python dev/win_quick_actions.py --remove 3
    python dev/win_quick_actions.py --once
"""
import argparse, json, sqlite3, time, subprocess, os
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "quick_actions.db"

DEFAULT_ACTIONS = [
    {"name": "open chrome", "command": "start chrome", "category": "browser", "alias": "chrome,web"},
    {"name": "open explorer", "command": "start explorer", "category": "system", "alias": "files,folders"},
    {"name": "open terminal", "command": "start cmd", "category": "dev", "alias": "cmd,shell"},
    {"name": "open bash", "command": "start bash", "category": "dev", "alias": "ps,posh"},
    {"name": "open task manager", "command": "start taskmgr", "category": "system", "alias": "taskmgr,procs"},
    {"name": "open notepad", "command": "start notepad", "category": "editor", "alias": "note,text"},
    {"name": "open calculator", "command": "start calc", "category": "util", "alias": "calc"},
    {"name": "cluster check", "command": "python dev/health_checker.py --once", "category": "jarvis", "alias": "health,check"},
    {"name": "gpu status", "command": "nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,memory.used --format=csv,noheader", "category": "system", "alias": "gpu,nvidia"},
    {"name": "ip config", "command": "ipconfig", "category": "network", "alias": "ip,network"},
]


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        command TEXT NOT NULL,
        category TEXT DEFAULT 'general',
        alias TEXT DEFAULT '',
        use_count INTEGER DEFAULT 0,
        last_used TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS action_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action_id INTEGER,
        success INTEGER,
        exit_code INTEGER,
        output_preview TEXT,
        duration_ms REAL,
        ts TEXT DEFAULT (datetime('now','localtime')),
        FOREIGN KEY(action_id) REFERENCES actions(id)
    )""")
    # Seed defaults if empty
    count = db.execute("SELECT COUNT(*) FROM actions").fetchone()[0]
    if count == 0:
        for a in DEFAULT_ACTIONS:
            db.execute(
                "INSERT OR IGNORE INTO actions (name, command, category, alias) VALUES (?,?,?,?)",
                (a["name"], a["command"], a["category"], a.get("alias", ""))
            )
    db.commit()
    return db


def _fuzzy_match(query, name, alias):
    """Simple fuzzy matching score."""
    query = query.lower()
    text = (name + " " + alias).lower()
    # Exact match
    if query == name.lower():
        return 100
    # Substring
    if query in text:
        return 80
    # Token match
    query_tokens = query.split()
    text_tokens = text.split()
    matched = sum(1 for qt in query_tokens if any(qt in tt for tt in text_tokens))
    if matched > 0:
        return 50 + (matched / len(query_tokens)) * 30
    # Character match
    chars_matched = sum(1 for c in query if c in text)
    return max(0, (chars_matched / len(query)) * 40) if query else 0


def list_actions(db, query=None):
    """List actions, optionally filtered by fuzzy search."""
    rows = db.execute(
        "SELECT id, name, command, category, alias, use_count, last_used FROM actions ORDER BY use_count DESC"
    ).fetchall()

    actions = []
    for r in rows:
        entry = {
            "id": r[0], "name": r[1], "command": r[2],
            "category": r[3], "alias": r[4],
            "use_count": r[5], "last_used": r[6]
        }
        if query:
            score = _fuzzy_match(query, r[1], r[4])
            if score > 20:
                entry["match_score"] = round(score)
                actions.append(entry)
        else:
            actions.append(entry)

    if query:
        actions.sort(key=lambda x: x.get("match_score", 0), reverse=True)

    return {"actions": actions, "total": len(actions), "query": query}


def run_action(db, name_or_id):
    """Run an action by name (fuzzy) or ID."""
    # Try by ID
    try:
        aid = int(name_or_id)
        row = db.execute("SELECT id, name, command FROM actions WHERE id=?", (aid,)).fetchone()
    except ValueError:
        row = None

    # Fuzzy search by name
    if not row:
        rows = db.execute("SELECT id, name, command, alias FROM actions").fetchall()
        best = None
        best_score = 0
        for r in rows:
            score = _fuzzy_match(name_or_id, r[1], r[3])
            if score > best_score:
                best_score = score
                best = r
        if best and best_score > 30:
            row = (best[0], best[1], best[2])
        else:
            return {"error": f"No action matching '{name_or_id}'"}

    aid, aname, cmd = row

    start = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=30, cwd=str(DEV.parent)
        )
        duration = (time.perf_counter() - start) * 1000
        success = proc.returncode == 0
        output = (proc.stdout or proc.stderr or "")[:2000]

        db.execute("UPDATE actions SET use_count=use_count+1, last_used=datetime('now','localtime') WHERE id=?", (aid,))
        db.execute(
            "INSERT INTO action_log (action_id, success, exit_code, output_preview, duration_ms) VALUES (?,?,?,?,?)",
            (aid, int(success), proc.returncode, output[:500], round(duration, 1))
        )
        db.commit()

        return {
            "action": aname,
            "command": cmd,
            "success": success,
            "exit_code": proc.returncode,
            "duration_ms": round(duration, 1),
            "output_preview": output[:500]
        }
    except subprocess.TimeoutExpired:
        duration = (time.perf_counter() - start) * 1000
        db.execute(
            "INSERT INTO action_log (action_id, success, exit_code, output_preview, duration_ms) VALUES (?,?,?,?,?)",
            (aid, 0, -1, "timeout", round(duration, 1))
        )
        db.commit()
        return {"action": aname, "error": "timeout after 30s"}
    except Exception as e:
        return {"action": aname, "error": str(e)}


def add_action(db, spec):
    """Add a new action."""
    if isinstance(spec, str):
        spec = json.loads(spec)
    name = spec.get("name", "")
    command = spec.get("command", "")
    if not name or not command:
        return {"error": "name and command required"}

    try:
        db.execute(
            "INSERT INTO actions (name, command, category, alias) VALUES (?,?,?,?)",
            (name, command, spec.get("category", "custom"), spec.get("alias", ""))
        )
        db.commit()
        return {"added": name, "command": command}
    except sqlite3.IntegrityError:
        return {"error": f"Action '{name}' already exists"}


def remove_action(db, action_id):
    """Remove an action by ID."""
    row = db.execute("SELECT name FROM actions WHERE id=?", (action_id,)).fetchone()
    if not row:
        return {"error": f"Action {action_id} not found"}
    db.execute("DELETE FROM actions WHERE id=?", (action_id,))
    db.execute("DELETE FROM action_log WHERE action_id=?", (action_id,))
    db.commit()
    return {"removed": action_id, "name": row[0]}


def do_status(db):
    total = db.execute("SELECT COUNT(*) FROM actions").fetchone()[0]
    total_runs = db.execute("SELECT COUNT(*) FROM action_log").fetchone()[0]
    mru = db.execute(
        "SELECT name, use_count, last_used FROM actions WHERE last_used IS NOT NULL ORDER BY last_used DESC LIMIT 5"
    ).fetchall()
    cats = db.execute(
        "SELECT category, COUNT(*) FROM actions GROUP BY category ORDER BY COUNT(*) DESC"
    ).fetchall()
    return {
        "script": "win_quick_actions.py",
        "id": 206,
        "db": str(DB_PATH),
        "total_actions": total,
        "total_runs": total_runs,
        "categories": {c[0]: c[1] for c in cats},
        "most_recent": [{"name": m[0], "uses": m[1], "last": m[2]} for m in mru],
        "ts": datetime.now().isoformat()
    }


def main():
    parser = argparse.ArgumentParser(description="Windows Quick Actions — catalog with fuzzy search")
    parser.add_argument("--list", nargs="?", const="", metavar="QUERY", help="List actions (optional fuzzy filter)")
    parser.add_argument("--run", type=str, metavar="ACTION", help="Run action by name or ID")
    parser.add_argument("--add", type=str, metavar="JSON", help="Add action from JSON")
    parser.add_argument("--remove", type=int, metavar="ID", help="Remove action by ID")
    parser.add_argument("--once", action="store_true", help="Show status")
    args = parser.parse_args()

    db = init_db()

    if args.list is not None:
        result = list_actions(db, args.list if args.list else None)
    elif args.run:
        result = run_action(db, args.run)
    elif args.add:
        result = add_action(db, args.add)
    elif args.remove:
        result = remove_action(db, args.remove)
    else:
        result = do_status(db)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    db.close()


if __name__ == "__main__":
    main()
