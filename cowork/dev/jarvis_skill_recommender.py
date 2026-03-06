#!/usr/bin/env python3
"""jarvis_skill_recommender.py — Recommande de nouveaux skills JARVIS.

Analyse les commandes echouees et gaps.

Usage:
    python dev/jarvis_skill_recommender.py --once
    python dev/jarvis_skill_recommender.py --analyze
    python dev/jarvis_skill_recommender.py --recommend
    python dev/jarvis_skill_recommender.py --gaps
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
DB_PATH = DEV / "data" / "skill_recommender.db"
from _paths import ETOILE_DB
from _paths import JARVIS_DB


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS recommendations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, pattern TEXT, frequency INTEGER,
        suggested_skill TEXT, confidence REAL, status TEXT DEFAULT 'pending')""")
    db.execute("""CREATE TABLE IF NOT EXISTS analyses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, failed_commands INTEGER, patterns_found INTEGER,
        recommendations_made INTEGER)""")
    db.commit()
    return db


def get_failed_commands():
    """Get failed/unmatched commands from JARVIS databases."""
    failed = []

    # From jarvis.db voice_corrections
    if JARVIS_DB.exists():
        try:
            db = sqlite3.connect(str(JARVIS_DB))
            rows = db.execute(
                "SELECT original, confidence FROM voice_corrections WHERE confidence < 0.5 ORDER BY rowid DESC LIMIT 500"
            ).fetchall()
            for r in rows:
                failed.append({"text": r[0], "confidence": r[1], "source": "voice"})
            db.close()
        except Exception:
            pass

    # From etoile.db (queries table if exists)
    if ETOILE_DB.exists():
        try:
            db = sqlite3.connect(str(ETOILE_DB))
            tables = [t[0] for t in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            if "queries" in tables:
                rows = db.execute(
                    "SELECT query, score FROM queries WHERE score < 0.5 ORDER BY rowid DESC LIMIT 500"
                ).fetchall()
                for r in rows:
                    failed.append({"text": r[0], "confidence": r[1] if r[1] else 0, "source": "query"})
            db.close()
        except Exception:
            pass

    return failed


def detect_patterns(failed_commands):
    """Detect recurring patterns in failed commands."""
    # Normalize and count
    normalized = []
    for cmd in failed_commands:
        text = cmd.get("text", "").lower().strip()
        if len(text) > 3:
            # Remove common prefixes
            for prefix in ["jarvis ", "hey jarvis ", "dis ", "fais "]:
                if text.startswith(prefix):
                    text = text[len(prefix):]
            normalized.append(text)

    # Count occurrences
    counter = Counter(normalized)

    # Group similar (simple prefix matching)
    patterns = []
    seen = set()
    for text, count in counter.most_common(50):
        if text in seen or count < 2:
            continue
        similar = [t for t in normalized if t.startswith(text[:10]) and t not in seen]
        total = len(similar)
        if total >= 2:
            patterns.append({
                "pattern": text[:80],
                "frequency": total,
                "examples": list(set(similar))[:3],
            })
            seen.update(similar)

    return patterns


def generate_recommendations(patterns):
    """Generate skill recommendations from patterns."""
    recommendations = []
    for p in patterns[:10]:
        text = p["pattern"]
        # Simple categorization
        if any(kw in text for kw in ["ouvre", "lance", "demarre"]):
            category = "launcher"
        elif any(kw in text for kw in ["cherche", "trouve", "recherche"]):
            category = "search"
        elif any(kw in text for kw in ["montre", "affiche", "lis"]):
            category = "display"
        elif any(kw in text for kw in ["envoie", "message", "mail"]):
            category = "communication"
        else:
            category = "general"

        recommendations.append({
            "pattern": text,
            "frequency": p["frequency"],
            "category": category,
            "suggested_name": text.replace(" ", "_")[:30],
            "confidence": min(0.3 + p["frequency"] * 0.1, 0.95),
        })

    return recommendations


def do_analyze():
    """Full analysis and recommendation."""
    db = init_db()
    failed = get_failed_commands()
    patterns = detect_patterns(failed)
    recommendations = generate_recommendations(patterns)

    # Store recommendations
    for rec in recommendations:
        db.execute(
            "INSERT INTO recommendations (ts, pattern, frequency, suggested_skill, confidence) VALUES (?,?,?,?,?)",
            (time.time(), rec["pattern"], rec["frequency"], rec["suggested_name"], rec["confidence"])
        )

    db.execute(
        "INSERT INTO analyses (ts, failed_commands, patterns_found, recommendations_made) VALUES (?,?,?,?)",
        (time.time(), len(failed), len(patterns), len(recommendations))
    )
    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "failed_commands_analyzed": len(failed),
        "patterns_detected": len(patterns),
        "recommendations": recommendations,
    }


def main():
    parser = argparse.ArgumentParser(description="JARVIS Skill Recommender")
    parser.add_argument("--once", "--analyze", action="store_true", help="Analyze and recommend")
    parser.add_argument("--recommend", action="store_true", help="Show recommendations")
    parser.add_argument("--gaps", action="store_true", help="Show gaps")
    parser.add_argument("--create-stub", action="store_true", help="Create skill stub")
    args = parser.parse_args()

    if args.recommend or args.gaps:
        db = init_db()
        rows = db.execute(
            "SELECT pattern, frequency, suggested_skill, confidence FROM recommendations ORDER BY confidence DESC LIMIT 15"
        ).fetchall()
        db.close()
        print(json.dumps([{
            "pattern": r[0], "freq": r[1], "skill": r[2], "confidence": r[3]
        } for r in rows], indent=2))
    else:
        result = do_analyze()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
