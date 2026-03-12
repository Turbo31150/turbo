#!/usr/bin/env python3
"""voice_correction_miner.py — Mines voice_corrections for frequently corrected words.

Reads the voice_corrections table from jarvis.db, aggregates word-level
corrections, and suggests new phonetic mappings or dictionary entries
for the most common misrecognitions.

Usage:
    python dev/voice_correction_miner.py --once
    python dev/voice_correction_miner.py --once --min-freq 3
    python dev/voice_correction_miner.py --dry-run
"""
import argparse
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TURBO_DIR = SCRIPT_DIR.parent.parent
DATA_DIR = TURBO_DIR / "data"
JARVIS_DB = TURBO_DIR / "jarvis.db"


def get_db_tables(db_path: Path) -> list:
    """List all tables in the database."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    return tables


def fetch_corrections(db_path: Path) -> list:
    """Fetch voice correction records from jarvis.db."""
    if not db_path.exists():
        return []

    conn = sqlite3.connect(str(db_path))
    records = []

    tables = get_db_tables(db_path)
    correction_tables = [
        t for t in tables
        if "correction" in t.lower() or "voice" in t.lower()
    ]

    for table in correction_tables:
        try:
            cursor = conn.execute(f"PRAGMA table_info({table})")
            columns = [row[1] for row in cursor.fetchall()]

            cursor = conn.execute(f"SELECT * FROM {table}")
            for row in cursor.fetchall():
                record = dict(zip(columns, row))
                record["_table"] = table
                records.append(record)
        except sqlite3.OperationalError:
            continue

    conn.close()
    return records


def tokenize(text: str) -> list:
    """Split text into lowercase word tokens."""
    if not text or not isinstance(text, str):
        return []
    return re.findall(r"[a-zA-ZÀ-ÿ]+", text.lower())


def mine_word_corrections(records: list, min_freq: int = 2) -> dict:
    """Mine word-level corrections from records.

    Identifies which individual words get misrecognized most often
    by comparing source and target texts word by word.
    """
    # Find text column pairs (source/target)
    if not records:
        return {"word_corrections": [], "suggestions": [], "total_records": 0}

    sample = records[0]
    text_pairs = []

    # Detect column pairs
    keys = [k for k in sample.keys() if k != "_table"]
    str_cols = [k for k in keys if isinstance(sample.get(k), str)]

    # Heuristic: pair sequential string columns
    for i in range(len(str_cols) - 1):
        text_pairs.append((str_cols[i], str_cols[i + 1]))

    # Count word-level mismatches
    word_mismatches = Counter()  # (heard, correct) -> count
    heard_freqs = Counter()  # heard_word -> total times heard wrong

    for record in records:
        for src_col, tgt_col in text_pairs:
            src_text = record.get(src_col, "")
            tgt_text = record.get(tgt_col, "")
            if not src_text or not tgt_text or src_text == tgt_text:
                continue

            src_words = tokenize(src_text)
            tgt_words = tokenize(tgt_text)

            # Simple: if same length, compare word by word
            if len(src_words) == len(tgt_words):
                for sw, tw in zip(src_words, tgt_words):
                    if sw != tw:
                        word_mismatches[(sw, tw)] += 1
                        heard_freqs[sw] += 1
            else:
                # Different lengths: track the whole phrase difference
                src_set = set(src_words)
                tgt_set = set(tgt_words)
                only_src = src_set - tgt_set
                only_tgt = tgt_set - src_set
                for w in only_src:
                    heard_freqs[w] += 1

    # Build suggestions
    suggestions = []
    for (heard, correct), count in word_mismatches.most_common(50):
        if count >= min_freq:
            suggestions.append({
                "heard": heard,
                "correct": correct,
                "frequency": count,
                "suggestion_type": "phonetic_mapping",
                "action": f"Add phonetic: '{heard}' -> '{correct}'",
            })

    # Words that are always wrong (no correct mapping found yet)
    orphan_words = []
    for word, freq in heard_freqs.most_common(20):
        if freq >= min_freq:
            # Check if we already have a suggestion for it
            already = any(s["heard"] == word for s in suggestions)
            if not already:
                orphan_words.append({"word": word, "frequency": freq})

    return {
        "total_records": len(records),
        "unique_word_mismatches": len(word_mismatches),
        "suggestions": suggestions,
        "orphan_words": orphan_words,
        "column_pairs_analyzed": text_pairs,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Mine voice corrections for frequent misrecognitions"
    )
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--dry-run", action="store_true", help="Mine without applying changes")
    parser.add_argument(
        "--min-freq", type=int, default=2,
        help="Minimum frequency for a suggestion (default: 2)"
    )
    parser.add_argument("--db", type=str, default=None, help="Path to jarvis.db")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    db_path = Path(args.db) if args.db else JARVIS_DB

    if not db_path.exists():
        print(json.dumps({
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "error": f"Database not found: {db_path}",
        }))
        sys.exit(1)

    records = fetch_corrections(db_path)
    analysis = mine_word_corrections(records, min_freq=args.min_freq)

    if args.json:
        print(json.dumps(analysis, indent=2, ensure_ascii=False))
        sys.exit(0)

    # Human-readable output
    print("=== Voice Correction Miner ===")
    print(f"Database: {db_path}")
    print(f"Total correction records: {analysis['total_records']}")
    print(f"Unique word mismatches: {analysis['unique_word_mismatches']}")
    print()

    if analysis["suggestions"]:
        print(f"Suggested phonetic mappings (freq >= {args.min_freq}):")
        for s in analysis["suggestions"]:
            print(f"  '{s['heard']}' -> '{s['correct']}' (x{s['frequency']})")
        print()
    else:
        print(f"No repeated word mismatches found (min_freq={args.min_freq}).")
        print()

    if analysis["orphan_words"]:
        print("Frequently misheard words (no clear mapping):")
        for o in analysis["orphan_words"]:
            print(f"  '{o['word']}' (x{o['frequency']})")
        print()

    result = {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "total_records": analysis["total_records"],
        "suggestions_count": len(analysis["suggestions"]),
        "orphan_words_count": len(analysis["orphan_words"]),
    }
    print(json.dumps(result))
    sys.exit(0)


if __name__ == "__main__":
    main()
