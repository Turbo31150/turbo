#!/usr/bin/env python3
"""cowork_loop_generator.py — Parse documented tasks into autonomous workflow chains.

Reads COWORK_MEGA_TASKS.md (100 tasks) and COWORK_MEGA_PROMPT.md (40 JSON tasks),
generates loop entries with chaining, and inserts into etoile.db workflow_chains table.

Usage:
    python cowork_loop_generator.py --once          # full pipeline: parse + generate + DB insert
    python cowork_loop_generator.py --from-mega      # parse COWORK_MEGA_TASKS.md only
    python cowork_loop_generator.py --from-prompt    # parse COWORK_MEGA_PROMPT.md only
    python cowork_loop_generator.py --list           # list generated loops
    python cowork_loop_generator.py --count          # count total loops
"""
import argparse
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent          # cowork/
DEV_DIR = BASE_DIR / "dev"
MEGA_TASKS = BASE_DIR / "COWORK_MEGA_TASKS.md"
MEGA_PROMPT = BASE_DIR / "COWORK_MEGA_PROMPT.md"
DB_PATH = BASE_DIR / "etoile.db"

# ── Category → interval mapping (seconds) ──────────────────────────────
CATEGORY_INTERVALS = {
    "WIN_MONITORING": 60,
    "MONITORING": 60,
    "CLUSTER": 60,
    "TRADING": 300,
    "VOICE": 600,
    "NLP": 600,
    "SOCIAL": 600,
    "TELEGRAM": 600,
    "COMMS": 600,
    "BROWSER": 600,
    "DEVOPS": 3600,
    "AUTO": 3600,
    "DATA": 3600,
    "MCP": 3600,
    "DOCKER": 7200,
    "AUDIT": 3600,
    "MAINTENANCE": 7200,
}

# ── Category → color code ──────────────────────────────────────────────
CATEGORY_COLORS = {
    "WIN_MONITORING": "RED",
    "MONITORING": "RED",
    "CLUSTER": "RED",
    "TRADING": "ORANGE",
    "VOICE": "YELLOW",
    "NLP": "YELLOW",
    "SOCIAL": "BLUE",
    "TELEGRAM": "BLUE",
    "COMMS": "BLUE",
    "BROWSER": "GREEN",
    "DEVOPS": "GREEN",
    "AUTO": "YELLOW",
    "DATA": "ORANGE",
    "MCP": "YELLOW",
    "DOCKER": "RED",
    "AUDIT": "ORANGE",
    "MAINTENANCE": "RED",
}

# ── Agent assignment by category ────────────────────────────────────────
CATEGORY_AGENTS = {
    "WIN_MONITORING": "OL1",
    "MONITORING": "OL1",
    "CLUSTER": "M1",
    "TRADING": "OL1",
    "VOICE": "M1",
    "NLP": "M1",
    "SOCIAL": "BrowserOS",
    "TELEGRAM": "LOCAL",
    "COMMS": "LOCAL",
    "BROWSER": "BrowserOS",
    "DEVOPS": "LOCAL",
    "AUTO": "M1",
    "DATA": "LOCAL",
    "MCP": "LOCAL",
    "DOCKER": "LOCAL",
    "AUDIT": "M2",
    "MAINTENANCE": "LOCAL",
}


# ═══════════════════════════════════════════════════════════════════════
# Parsers
# ═══════════════════════════════════════════════════════════════════════

def parse_mega_tasks(path: Path) -> list[dict]:
    """Parse COWORK_MEGA_TASKS.md — lines like:
       1. [WIN_MONITORING] description → `script.py`
    """
    if not path.exists():
        print(f"[WARN] {path} not found", file=sys.stderr)
        return []
    pattern = re.compile(
        r"^\s*(\d+)\.\s*\[([A-Z_]+)\]\s+(.+?)\s*→\s*`([^`]+)`",
    )
    tasks = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = pattern.match(line)
        if m:
            tid, cat, desc, script = m.group(1), m.group(2), m.group(3), m.group(4)
            tasks.append({
                "id": int(tid),
                "category": cat,
                "description": desc.strip(),
                "script": script.strip(),
                "source": "mega_tasks",
            })
    return tasks


def parse_mega_prompt(path: Path) -> list[dict]:
    """Parse COWORK_MEGA_PROMPT.md — extract JSON arrays from ```json blocks."""
    if not path.exists():
        print(f"[WARN] {path} not found", file=sys.stderr)
        return []
    text = path.read_text(encoding="utf-8")
    tasks = []
    for block in re.findall(r"```json\s*\n(.*?)```", text, re.DOTALL):
        try:
            items = json.loads(block)
        except json.JSONDecodeError:
            continue
        if not isinstance(items, list):
            continue
        for item in items:
            script_raw = item.get("script", "")
            script_name = script_raw.split()[0] if script_raw else ""
            cat = _infer_category(item.get("color", ""), item.get("task", ""))
            tasks.append({
                "id": 1000 + item.get("id", 0),
                "category": cat,
                "description": item.get("task", ""),
                "script": script_name,
                "agent_hint": item.get("agent", ""),
                "source": "mega_prompt",
            })
    return tasks


def _infer_category(color: str, task: str) -> str:
    """Best-effort category from color + keywords."""
    color_map = {"RED": "MONITORING", "ORANGE": "DATA", "YELLOW": "AUTO", "GREEN": "DEVOPS", "BLUE": "SOCIAL"}
    kw_map = [
        ("trading", "TRADING"), ("cluster", "CLUSTER"), ("health", "MONITORING"),
        ("docker", "DOCKER"), ("mcp", "MCP"), ("telegram", "TELEGRAM"),
        ("browser", "BROWSER"), ("linkedin", "SOCIAL"), ("codeur", "SOCIAL"),
        ("voice", "VOICE"), ("audit", "AUDIT"), ("backup", "DEVOPS"),
    ]
    lower = task.lower()
    for kw, cat in kw_map:
        if kw in lower:
            return cat
    return color_map.get(color.upper(), "AUTO")


# ═══════════════════════════════════════════════════════════════════════
# Loop generation
# ═══════════════════════════════════════════════════════════════════════

def generate_loops(tasks: list[dict]) -> tuple[list[dict], int]:
    """Build loop entries and chain links. Returns (loops, chains_created)."""
    by_cat: dict[str, list[dict]] = {}
    for t in tasks:
        by_cat.setdefault(t["category"], []).append(t)

    loops = []
    chains = 0
    for cat, cat_tasks in by_cat.items():
        cat_tasks.sort(key=lambda x: x["id"])
        for i, t in enumerate(cat_tasks):
            next_name = None
            if i + 1 < len(cat_tasks):
                nxt = cat_tasks[i + 1]
                next_name = f"loop_{nxt['category'].lower()}_{nxt['id']}"
                chains += 1
            agent = t.get("agent_hint") or CATEGORY_AGENTS.get(cat, "LOCAL")
            loops.append({
                "name": f"loop_{cat.lower()}_{t['id']}",
                "script": f"cowork/dev/{t['script']}",
                "args": "--once",
                "interval_s": CATEGORY_INTERVALS.get(cat, 300),
                "retry_count": 1,
                "recovery_timer_s": 10,
                "category": cat,
                "agent": agent,
                "color": CATEGORY_COLORS.get(cat, "WHITE"),
                "chain_next": next_name,
                "description": t.get("description", ""),
                "source": t.get("source", ""),
            })
    return loops, chains


# ═══════════════════════════════════════════════════════════════════════
# Database
# ═══════════════════════════════════════════════════════════════════════

def ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workflow_chains (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            script TEXT NOT NULL,
            args TEXT DEFAULT '--once',
            interval_s INTEGER DEFAULT 300,
            retry_count INTEGER DEFAULT 1,
            recovery_timer_s INTEGER DEFAULT 10,
            category TEXT,
            agent TEXT,
            color TEXT,
            chain_next TEXT,
            description TEXT,
            source TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()


def insert_loops(loops: list[dict], db_path: Path) -> int:
    conn = sqlite3.connect(str(db_path))
    ensure_table(conn)
    inserted = 0
    for lp in loops:
        try:
            conn.execute(
                """INSERT OR REPLACE INTO workflow_chains
                   (name, script, args, interval_s, retry_count, recovery_timer_s,
                    category, agent, color, chain_next, description, source, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))""",
                (lp["name"], lp["script"], lp["args"], lp["interval_s"],
                 lp["retry_count"], lp["recovery_timer_s"], lp["category"],
                 lp["agent"], lp["color"], lp["chain_next"],
                 lp["description"], lp["source"]),
            )
            inserted += 1
        except sqlite3.Error as e:
            print(f"[ERR] {lp['name']}: {e}", file=sys.stderr)
    conn.commit()
    conn.close()
    return inserted


# ═══════════════════════════════════════════════════════════════════════
# CLI actions
# ═══════════════════════════════════════════════════════════════════════

def action_once() -> None:
    tasks = parse_mega_tasks(MEGA_TASKS) + parse_mega_prompt(MEGA_PROMPT)
    loops, chains = generate_loops(tasks)
    inserted = insert_loops(loops, DB_PATH)
    cats = sorted({lp["category"] for lp in loops})
    result = {
        "total_tasks_read": len(tasks),
        "loops_generated": len(loops),
        "chains_created": chains,
        "db_inserted": inserted,
        "categories": cats,
        "db_path": str(DB_PATH),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


def action_from_mega() -> None:
    tasks = parse_mega_tasks(MEGA_TASKS)
    loops, chains = generate_loops(tasks)
    inserted = insert_loops(loops, DB_PATH)
    print(json.dumps({
        "source": "COWORK_MEGA_TASKS.md",
        "total_tasks_read": len(tasks),
        "loops_generated": len(loops),
        "chains_created": chains,
        "db_inserted": inserted,
        "categories": sorted({lp["category"] for lp in loops}),
    }, indent=2, ensure_ascii=False))


def action_from_prompt() -> None:
    tasks = parse_mega_prompt(MEGA_PROMPT)
    loops, chains = generate_loops(tasks)
    inserted = insert_loops(loops, DB_PATH)
    print(json.dumps({
        "source": "COWORK_MEGA_PROMPT.md",
        "total_tasks_read": len(tasks),
        "loops_generated": len(loops),
        "chains_created": chains,
        "db_inserted": inserted,
        "categories": sorted({lp["category"] for lp in loops}),
    }, indent=2, ensure_ascii=False))


def action_list() -> None:
    if not DB_PATH.exists():
        print(json.dumps({"error": "etoile.db not found"}))
        return
    conn = sqlite3.connect(str(DB_PATH))
    ensure_table(conn)
    cur = conn.execute(
        "SELECT name, category, script, interval_s, agent, chain_next FROM workflow_chains ORDER BY category, name"
    )
    rows = [{"name": r[0], "category": r[1], "script": r[2],
             "interval_s": r[3], "agent": r[4], "chain_next": r[5]} for r in cur.fetchall()]
    conn.close()
    print(json.dumps({"loops": rows, "total": len(rows)}, indent=2, ensure_ascii=False))


def action_count() -> None:
    if not DB_PATH.exists():
        print(json.dumps({"count": 0, "error": "etoile.db not found"}))
        return
    conn = sqlite3.connect(str(DB_PATH))
    ensure_table(conn)
    total = conn.execute("SELECT COUNT(*) FROM workflow_chains").fetchone()[0]
    by_cat = dict(conn.execute(
        "SELECT category, COUNT(*) FROM workflow_chains GROUP BY category ORDER BY category"
    ).fetchall())
    conn.close()
    print(json.dumps({"count": total, "by_category": by_cat}, indent=2, ensure_ascii=False))


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate autonomous workflow loops from documented tasks")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--once", action="store_true", help="Full pipeline: parse all sources, generate loops, insert DB")
    group.add_argument("--from-mega", action="store_true", help="Parse COWORK_MEGA_TASKS.md only")
    group.add_argument("--from-prompt", action="store_true", help="Parse COWORK_MEGA_PROMPT.md only")
    group.add_argument("--list", action="store_true", help="List all generated loops from DB")
    group.add_argument("--count", action="store_true", help="Count total loops in DB")
    args = parser.parse_args()

    if args.once:
        action_once()
    elif args.from_mega:
        action_from_mega()
    elif args.from_prompt:
        action_from_prompt()
    elif args.list:
        action_list()
    elif args.count:
        action_count()


if __name__ == "__main__":
    main()
