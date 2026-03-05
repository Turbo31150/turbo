#!/usr/bin/env python3
"""voice_command_fuzzer.py — Fuzz test voice commands for edge cases.

Loads voice commands from etoile.db, generates variations (typos, partial,
reversed, similar sounds), and tests recognition accuracy.
"""

import argparse
import json
import os
import random
import sqlite3
import string
import sys
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'cowork_gaps.db')
ETOILE_DB = os.path.join(os.path.dirname(__file__), '..', '..', 'etoile.db')


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.execute("""CREATE TABLE IF NOT EXISTS fuzz_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        original TEXT, variant TEXT, variant_type TEXT,
        matched INTEGER DEFAULT 0, confidence REAL DEFAULT 0,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    db.commit()
    return db


def load_commands():
    """Load voice commands from etoile.db."""
    if not os.path.exists(ETOILE_DB):
        return ["status systeme", "check cluster", "lance trading", "audit securite",
                "lis mes mails", "rapport quotidien", "temperature gpu"]
    db = sqlite3.connect(ETOILE_DB)
    try:
        rows = db.execute("SELECT DISTINCT trigger_text FROM voice_commands LIMIT 500").fetchall()
        return [r[0] for r in rows if r[0]]
    except Exception:
        try:
            rows = db.execute("SELECT DISTINCT command FROM commands LIMIT 500").fetchall()
            return [r[0] for r in rows if r[0]]
        except Exception:
            return ["status systeme", "check cluster", "lance trading"]
    finally:
        db.close()


def generate_variants(command, count=5):
    """Generate fuzz variants of a voice command."""
    variants = []
    words = command.split()

    # Typo: swap adjacent chars
    if len(command) > 3:
        for _ in range(min(count, 2)):
            i = random.randint(1, len(command) - 2)
            v = command[:i] + command[i+1] + command[i] + command[i+2:]
            variants.append((v, "typo"))

    # Partial: truncate
    if len(words) > 1:
        variants.append((" ".join(words[:-1]), "partial"))
        variants.append((" ".join(words[1:]), "partial_start"))

    # Reversed words
    if len(words) > 1:
        variants.append((" ".join(reversed(words)), "reversed"))

    # Similar sounds (French phonetics)
    phonetic_map = {"ai": "e", "au": "o", "ou": "u", "an": "en", "in": "ain",
                    "ph": "f", "qu": "k", "ss": "s", "tion": "sion"}
    for old, new in phonetic_map.items():
        if old in command:
            variants.append((command.replace(old, new, 1), "phonetic"))
            break

    # Extra noise
    noise_chars = " euh hmm alors"
    variants.append((random.choice(noise_chars.split()) + " " + command, "noise_prefix"))

    # Case variations
    variants.append((command.upper(), "uppercase"))
    variants.append((command.title(), "titlecase"))

    return variants[:count]


def fuzz_test(commands, count_per_cmd=5):
    """Run fuzz test on all commands."""
    db = init_db()
    results = []
    total_variants = 0

    for cmd in commands:
        variants = generate_variants(cmd, count_per_cmd)
        for variant, vtype in variants:
            # Simple match score: Levenshtein-like ratio
            common = sum(1 for a, b in zip(cmd.lower(), variant.lower()) if a == b)
            confidence = common / max(len(cmd), len(variant)) if max(len(cmd), len(variant)) > 0 else 0
            matched = confidence > 0.6

            db.execute(
                "INSERT INTO fuzz_results (original, variant, variant_type, matched, confidence) VALUES (?,?,?,?,?)",
                (cmd, variant, vtype, int(matched), round(confidence, 3))
            )
            results.append({
                "original": cmd, "variant": variant, "type": vtype,
                "matched": matched, "confidence": round(confidence, 3)
            })
            total_variants += 1

    db.commit()

    # Stats
    matched_count = sum(1 for r in results if r["matched"])
    stats = {
        "commands_tested": len(commands),
        "total_variants": total_variants,
        "matched": matched_count,
        "match_rate": round(matched_count / max(1, total_variants) * 100, 1),
        "by_type": {}
    }

    for r in results:
        t = r["type"]
        if t not in stats["by_type"]:
            stats["by_type"][t] = {"total": 0, "matched": 0}
        stats["by_type"][t]["total"] += 1
        if r["matched"]:
            stats["by_type"][t]["matched"] += 1

    db.close()
    return stats, results


def show_stats():
    """Show historical fuzz stats."""
    if not os.path.exists(DB_PATH):
        return {"error": "No fuzz data yet"}
    db = sqlite3.connect(DB_PATH)
    total = db.execute("SELECT COUNT(*) FROM fuzz_results").fetchone()[0]
    matched = db.execute("SELECT COUNT(*) FROM fuzz_results WHERE matched=1").fetchone()[0]
    by_type = db.execute("""
        SELECT variant_type, COUNT(*) as cnt, SUM(matched) as ok, AVG(confidence) as avg_conf
        FROM fuzz_results GROUP BY variant_type
    """).fetchall()
    db.close()
    return {
        "total_tests": total, "matched": matched,
        "match_rate": round(matched / max(1, total) * 100, 1),
        "by_type": {r[0]: {"count": r[1], "matched": r[2], "avg_confidence": round(r[3], 3)} for r in by_type}
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Voice Command Fuzzer")
    parser.add_argument("--once", action="store_true", help="Run fuzz test once")
    parser.add_argument("--count", type=int, default=5, help="Variants per command")
    parser.add_argument("--stats", action="store_true", help="Show historical stats")
    args = parser.parse_args()

    if args.stats:
        print(json.dumps(show_stats(), indent=2, ensure_ascii=False))
    elif args.once or not args.stats:
        commands = load_commands()
        stats, _ = fuzz_test(commands, args.count)
        print(json.dumps(stats, indent=2, ensure_ascii=False))
