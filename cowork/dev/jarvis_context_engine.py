#!/usr/bin/env python3
"""jarvis_context_engine.py — Moteur de contexte JARVIS.

Indexe toutes les connaissances pour enrichir les reponses.

Usage:
    python dev/jarvis_context_engine.py --once
    python dev/jarvis_context_engine.py --build
    python dev/jarvis_context_engine.py --query TOPIC
    python dev/jarvis_context_engine.py --stats
"""
import argparse
from _paths import TURBO_DIR
import json
import os
import re
import sqlite3
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "context_engine.db"

# Sources to index
SOURCES = [
    {"type": "claude_md", "path": "C:/Users/franc/.claude/CLAUDE.md"},
    {"type": "memory", "path": "C:/Users/franc/.claude/projects/C--Users-franc/memory/MEMORY.md"},
    {"type": "dev_scripts", "glob": "C:/Users/franc/.openclaw/workspace/dev/*.py"},
    {"type": "src_modules", "glob": str(TURBO_DIR / "src" / "*.py")},
]


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS index_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        word TEXT, source_type TEXT, filepath TEXT,
        line_num INTEGER, context TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS builds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, total_entries INTEGER, files_indexed INTEGER,
        words_indexed INTEGER)""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_word ON index_entries(word)")
    db.commit()
    return db


def tokenize(text):
    """Simple tokenizer — extract meaningful words."""
    words = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]{2,}', text.lower())
    # Filter stopwords
    stop = {"the", "and", "for", "from", "with", "that", "this", "are", "was", "not",
            "def", "self", "import", "return", "none", "true", "false", "class"}
    return [w for w in words if w not in stop and len(w) > 2]


def index_file(filepath, source_type):
    """Index a single file."""
    entries = []
    try:
        content = Path(filepath).read_text(encoding="utf-8", errors="ignore")
        for i, line in enumerate(content.split("\n"), 1):
            words = tokenize(line)
            for word in set(words):  # Dedupe per line
                entries.append({
                    "word": word, "source_type": source_type,
                    "filepath": str(filepath), "line_num": i,
                    "context": line.strip()[:150],
                })
    except Exception:
        pass
    return entries


def do_build():
    """Build the full index."""
    db = init_db()

    # Clear old index
    db.execute("DELETE FROM index_entries")

    total_entries = 0
    files_indexed = 0
    all_words = set()

    for source in SOURCES:
        if "glob" in source:
            files = sorted(Path(source["glob"]).parent.glob(Path(source["glob"]).name))
        elif "path" in source:
            p = Path(source["path"])
            files = [p] if p.exists() else []
        else:
            continue

        for f in files:
            if not f.exists() or f.name.startswith("__"):
                continue
            entries = index_file(f, source["type"])
            for e in entries:
                db.execute(
                    "INSERT INTO index_entries (word, source_type, filepath, line_num, context) VALUES (?,?,?,?,?)",
                    (e["word"], e["source_type"], e["filepath"], e["line_num"], e["context"])
                )
                all_words.add(e["word"])
            total_entries += len(entries)
            files_indexed += 1

    db.execute(
        "INSERT INTO builds (ts, total_entries, files_indexed, words_indexed) VALUES (?,?,?,?)",
        (time.time(), total_entries, files_indexed, len(all_words))
    )
    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "files_indexed": files_indexed,
        "total_entries": total_entries,
        "unique_words": len(all_words),
    }


def query_index(topic, top_k=10):
    """Query the index for a topic."""
    db = init_db()
    words = tokenize(topic)
    if not words:
        db.close()
        return []

    # Search for each word
    results = defaultdict(lambda: {"score": 0, "contexts": []})
    for word in words:
        rows = db.execute(
            "SELECT filepath, line_num, context, source_type FROM index_entries WHERE word=? LIMIT 50",
            (word,)
        ).fetchall()
        for r in rows:
            key = f"{r[0]}:{r[1]}"
            results[key]["score"] += 1
            results[key]["filepath"] = r[0]
            results[key]["line"] = r[1]
            results[key]["context"] = r[2]
            results[key]["source"] = r[3]

    db.close()

    # Sort by score
    sorted_results = sorted(results.values(), key=lambda x: x["score"], reverse=True)[:top_k]
    return [{
        "filepath": r["filepath"], "line": r["line"],
        "context": r["context"], "source": r["source"], "score": r["score"],
    } for r in sorted_results]


def main():
    parser = argparse.ArgumentParser(description="JARVIS Context Engine")
    parser.add_argument("--once", "--build", action="store_true", help="Build index")
    parser.add_argument("--query", metavar="TOPIC", help="Query index")
    parser.add_argument("--refresh", action="store_true", help="Refresh index")
    parser.add_argument("--stats", action="store_true", help="Show stats")
    args = parser.parse_args()

    if args.query:
        results = query_index(args.query)
        print(json.dumps(results, ensure_ascii=False, indent=2))
    elif args.stats:
        db = init_db()
        total = db.execute("SELECT COUNT(*) FROM index_entries").fetchone()[0]
        builds = db.execute("SELECT ts, files_indexed, words_indexed FROM builds ORDER BY ts DESC LIMIT 5").fetchall()
        db.close()
        print(json.dumps({
            "total_entries": total,
            "builds": [{"ts": datetime.fromtimestamp(b[0]).isoformat(), "files": b[1], "words": b[2]} for b in builds]
        }, indent=2))
    else:
        result = do_build()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()