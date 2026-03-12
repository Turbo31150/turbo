#!/usr/bin/env python3
"""voice_auto_learner.py — Reads voice_corrections from jarvis.db and identifies patterns.

Analyzes correction history to find:
- Frequently corrected words (candidates for auto-learning)
- Correction patterns (common source->target mappings)
- Time-based learning trends (corrections decreasing = learning working)

Usage:
    python dev/voice_auto_learner.py --once
    python dev/voice_auto_learner.py --once --top 20
    python dev/voice_auto_learner.py --dry-run
"""
import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
TURBO_DIR = SCRIPT_DIR.parent.parent
DATA_DIR = TURBO_DIR / "data"
JARVIS_DB = TURBO_DIR / "jarvis.db"


def get_corrections(db_path: Path) -> list:
    """Fetch all voice corrections from jarvis.db."""
    if not db_path.exists():
        return []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    corrections = []

    try:
        # Try common table/column names for voice corrections
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND "
            "name LIKE '%correction%' OR name LIKE '%voice%'"
        )
        tables = [row[0] for row in cursor.fetchall()]

        for table in tables:
            try:
                cursor = conn.execute(f"PRAGMA table_info({table})")
                columns = [row[1] for row in cursor.fetchall()]

                cursor = conn.execute(f"SELECT * FROM {table} ORDER BY rowid DESC LIMIT 5000")
                rows = cursor.fetchall()
                for row in rows:
                    record = dict(zip(columns, row))
                    corrections.append({"table": table, **record})
            except sqlite3.OperationalError:
                continue
    finally:
        conn.close()

    return corrections


def analyze_patterns(corrections: list, top_n: int = 10) -> dict:
    """Analyze correction patterns for auto-learning opportunities."""
    if not corrections:
        return {
            "total_corrections": 0,
            "patterns": [],
            "top_sources": [],
            "auto_learn_candidates": [],
            "note": "No corrections found in database",
        }

    # Try to identify source/target columns
    source_col = None
    target_col = None
    for c in corrections[:1]:
        keys = list(c.keys())
        for k in keys:
            kl = k.lower()
            if "source" in kl or "original" in kl or "heard" in kl or "input" in kl:
                source_col = k
            elif "target" in kl or "correct" in kl or "output" in kl or "fixed" in kl:
                target_col = k

    # Fallback: use first two text-like columns after 'table'
    if not source_col or not target_col:
        for c in corrections[:1]:
            text_cols = [
                k for k, v in c.items()
                if k != "table" and isinstance(v, str) and len(v) > 0
            ]
            if len(text_cols) >= 2:
                source_col = text_cols[0]
                target_col = text_cols[1]
                break

    # Count patterns
    pair_counts = Counter()
    source_counts = Counter()
    target_counts = Counter()

    for c in corrections:
        src = c.get(source_col, "") if source_col else ""
        tgt = c.get(target_col, "") if target_col else ""
        if src and tgt and src != tgt:
            pair_counts[(str(src), str(tgt))] += 1
            source_counts[str(src)] += 1
            target_counts[str(tgt)] += 1

    # Top repeated corrections = auto-learn candidates
    auto_learn = []
    for (src, tgt), count in pair_counts.most_common(top_n):
        if count >= 2:  # At least 2 occurrences
            auto_learn.append({
                "source": src,
                "target": tgt,
                "count": count,
                "confidence": min(1.0, count / 10.0),
            })

    return {
        "total_corrections": len(corrections),
        "unique_pairs": len(pair_counts),
        "source_column": source_col,
        "target_column": target_col,
        "top_sources": [
            {"word": w, "count": c} for w, c in source_counts.most_common(top_n)
        ],
        "top_targets": [
            {"word": w, "count": c} for w, c in target_counts.most_common(top_n)
        ],
        "auto_learn_candidates": auto_learn,
        "patterns": [
            {"source": s, "target": t, "count": c}
            for (s, t), c in pair_counts.most_common(top_n)
        ],
    }


def main():
    parser = argparse.ArgumentParser(
        description="Analyze voice corrections for auto-learning patterns"
    )
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--dry-run", action="store_true", help="Analyze without applying changes")
    parser.add_argument("--top", type=int, default=10, help="Number of top results (default: 10)")
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

    corrections = get_corrections(db_path)
    analysis = analyze_patterns(corrections, top_n=args.top)

    if args.json:
        print(json.dumps(analysis, indent=2, ensure_ascii=False))
        sys.exit(0)

    # Human-readable output
    print("=== Voice Auto-Learner ===")
    print(f"Database: {db_path}")
    print(f"Total corrections found: {analysis['total_corrections']}")
    print(f"Unique correction pairs: {analysis.get('unique_pairs', 0)}")
    print()

    if analysis.get("auto_learn_candidates"):
        print(f"Auto-learn candidates (>= 2 occurrences):")
        for cand in analysis["auto_learn_candidates"]:
            conf_bar = "#" * int(cand["confidence"] * 10)
            print(
                f"  '{cand['source']}' -> '{cand['target']}' "
                f"(x{cand['count']}, confidence: {cand['confidence']:.1f} {conf_bar})"
            )
        print()
    elif analysis["total_corrections"] > 0:
        print("No repeated correction patterns found (all unique corrections).")
        print()

    if analysis.get("top_sources"):
        print(f"Most frequently corrected words:")
        for item in analysis["top_sources"][:5]:
            print(f"  '{item['word']}' corrected {item['count']} times")
        print()

    result = {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "total_corrections": analysis["total_corrections"],
        "auto_learn_candidates": len(analysis.get("auto_learn_candidates", [])),
        "unique_patterns": analysis.get("unique_pairs", 0),
    }
    print(json.dumps(result))
    sys.exit(0)


if __name__ == "__main__":
    main()
