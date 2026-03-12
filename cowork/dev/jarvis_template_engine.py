#!/usr/bin/env python3
"""jarvis_template_engine.py — Moteur de templates JARVIS.

Genere fichiers/configs/scripts a partir de templates.

Usage:
    python dev/jarvis_template_engine.py --once
    python dev/jarvis_template_engine.py --create
    python dev/jarvis_template_engine.py --list
    python dev/jarvis_template_engine.py --render NAME
"""
import argparse
import json
import os
import sqlite3
import string
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "template_engine.db"

BUILTIN_TEMPLATES = {
    "cowork_script": {
        "description": "Template script COWORK standard",
        "template": '''#!/usr/bin/env python3
"""${name}.py — ${description}.

Usage:
    python dev/${name}.py --once
    python dev/${name}.py --${main_action}
"""
import argparse, json, os, sqlite3, time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "${name}.db"

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, data TEXT)""")
    db.commit()
    return db

def do_main():
    db = init_db()
    result = {"ts": datetime.now().isoformat(), "status": "ok"}
    db.execute("INSERT INTO results (ts, data) VALUES (?,?)", (time.time(), json.dumps(result)))
    db.commit(); db.close()
    return result

def main():
    parser = argparse.ArgumentParser(description="${description}")
    parser.add_argument("--once", "--${main_action}", action="store_true")
    args = parser.parse_args()
    print(json.dumps(do_main(), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
''',
        "variables": ["name", "description", "main_action"],
    },
    "config_json": {
        "description": "Template config JSON",
        "template": '{\n  "name": "${name}",\n  "version": "${version}",\n  "enabled": true,\n  "created": "${date}"\n}',
        "variables": ["name", "version", "date"],
    },
    "commit_message": {
        "description": "Template commit message",
        "template": "${type}(${scope}): ${description}\n\n${body}",
        "variables": ["type", "scope", "description", "body"],
    },
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, name TEXT UNIQUE, description TEXT,
        template TEXT, variables TEXT, usage_count INTEGER DEFAULT 0)""")
    db.commit()
    return db


def seed_templates():
    db = init_db()
    for name, info in BUILTIN_TEMPLATES.items():
        try:
            db.execute("INSERT OR IGNORE INTO templates (ts, name, description, template, variables) VALUES (?,?,?,?,?)",
                       (time.time(), name, info["description"], info["template"],
                        json.dumps(info["variables"])))
        except Exception:
            pass
    db.commit()
    db.close()


def do_list():
    seed_templates()
    db = init_db()
    rows = db.execute("SELECT name, description, variables, usage_count FROM templates ORDER BY name").fetchall()
    db.close()
    return {
        "ts": datetime.now().isoformat(),
        "templates": [
            {"name": r[0], "description": r[1],
             "variables": json.loads(r[2]) if r[2] else [], "usage_count": r[3]}
            for r in rows
        ],
        "total": len(rows),
    }


def main():
    parser = argparse.ArgumentParser(description="JARVIS Template Engine")
    parser.add_argument("--once", "--list", action="store_true", help="List templates")
    parser.add_argument("--create", action="store_true", help="Create template")
    parser.add_argument("--render", metavar="NAME", help="Render template")
    parser.add_argument("--variables", action="store_true", help="Show variables")
    args = parser.parse_args()
    print(json.dumps(do_list(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
