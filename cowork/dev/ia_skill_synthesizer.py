#!/usr/bin/env python3
"""ia_skill_synthesizer.py — Synthetiseur de skills IA.

Cree automatiquement des skills a partir des patterns d'usage.

Usage:
    python dev/ia_skill_synthesizer.py --once
    python dev/ia_skill_synthesizer.py --synthesize
    python dev/ia_skill_synthesizer.py --from-logs
    python dev/ia_skill_synthesizer.py --test
"""
import argparse
import json
import os
import sqlite3
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "skill_synthesizer.db"
ETOILE_DB = Path("F:/BUREAU/turbo/data/etoile.db")


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS synthesized_skills (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, name TEXT, triggers TEXT,
        action TEXT, source_pattern TEXT, confidence REAL)""")
    db.commit()
    return db


def find_repeated_patterns(min_count=5):
    patterns = Counter()
    if not ETOILE_DB.exists():
        return patterns

    try:
        db = sqlite3.connect(str(ETOILE_DB))
        for t in [t[0] for t in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]:
            cols = [c[1] for c in db.execute(f"PRAGMA table_info([{t}])").fetchall()]
            cmd_col = next((c for c in cols if c in ("action", "command", "tool", "input")), None)
            if cmd_col:
                try:
                    rows = db.execute(f"SELECT [{cmd_col}] FROM [{t}] WHERE [{cmd_col}] IS NOT NULL LIMIT 5000").fetchall()
                    for r in rows:
                        val = (r[0] or "").strip()
                        if val and len(val) > 3:
                            # Normalize
                            normalized = val.lower().strip()
                            patterns[normalized] += 1
                except Exception:
                    pass
        db.close()
    except Exception:
        pass

    return Counter({k: v for k, v in patterns.items() if v >= min_count})


def generate_skill_candidates(patterns):
    candidates = []
    for pattern, count in patterns.most_common(20):
        words = pattern.split()
        if len(words) < 2:
            continue
        name = "_".join(words[:3])[:30]
        candidates.append({
            "name": f"auto_{name}",
            "pattern": pattern,
            "frequency": count,
            "triggers": [pattern],
            "confidence": min(count / 10, 0.95),
        })
    return candidates


def do_synthesize():
    db = init_db()
    patterns = find_repeated_patterns()
    candidates = generate_skill_candidates(patterns)

    for c in candidates:
        db.execute("INSERT INTO synthesized_skills (ts, name, triggers, action, source_pattern, confidence) VALUES (?,?,?,?,?,?)",
                   (time.time(), c["name"], json.dumps(c["triggers"]),
                    f"execute_{c['name']}", c["pattern"], c["confidence"]))

    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "patterns_found": len(patterns),
        "candidates_generated": len(candidates),
        "top_patterns": dict(patterns.most_common(10)),
        "skill_candidates": candidates[:10],
    }


def main():
    parser = argparse.ArgumentParser(description="IA Skill Synthesizer")
    parser.add_argument("--once", "--synthesize", action="store_true", help="Synthesize")
    parser.add_argument("--from-logs", action="store_true", help="From logs")
    parser.add_argument("--test", action="store_true", help="Test skills")
    parser.add_argument("--deploy", action="store_true", help="Deploy")
    args = parser.parse_args()
    print(json.dumps(do_synthesize(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
