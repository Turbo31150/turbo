#!/usr/bin/env python3
"""jarvis_voice_trainer.py — Entraineur vocal JARVIS.

Detecte commandes mal reconnues, genere corrections automatiques.

Usage:
    python dev/jarvis_voice_trainer.py --once
    python dev/jarvis_voice_trainer.py --analyze
    python dev/jarvis_voice_trainer.py --gaps
    python dev/jarvis_voice_trainer.py --test
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
DB_PATH = DEV / "data" / "voice_trainer.db"
JARVIS_DB = Path("F:/BUREAU/turbo/data/jarvis.db")
ETOILE_DB = Path("F:/BUREAU/turbo/data/etoile.db")


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS analyses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, total_corrections INTEGER, low_confidence INTEGER,
        patterns_found INTEGER, corrections_generated INTEGER)""")
    db.execute("""CREATE TABLE IF NOT EXISTS generated_corrections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, original TEXT, corrected TEXT,
        confidence REAL, status TEXT DEFAULT 'pending')""")
    db.commit()
    return db


def get_low_confidence_phrases():
    """Get phrases with low recognition confidence."""
    phrases = []
    if not JARVIS_DB.exists():
        return phrases
    try:
        db = sqlite3.connect(str(JARVIS_DB))
        tables = [t[0] for t in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        if "voice_corrections" in tables:
            rows = db.execute(
                "SELECT original, corrected, confidence FROM voice_corrections WHERE confidence < 0.7 ORDER BY rowid DESC LIMIT 200"
            ).fetchall()
            for r in rows:
                phrases.append({"original": r[0], "corrected": r[1], "confidence": r[2]})
        db.close()
    except Exception:
        pass
    return phrases


def detect_patterns(phrases):
    """Detect recurring misrecognition patterns."""
    # Group by similar originals
    originals = [p["original"].lower().strip() for p in phrases if p.get("original")]
    counter = Counter(originals)
    patterns = []
    for text, count in counter.most_common(20):
        if count >= 2 and len(text) > 3:
            # Find the corrected versions
            corrections = [p["corrected"] for p in phrases if p.get("original", "").lower().strip() == text and p.get("corrected")]
            best_correction = Counter(corrections).most_common(1)[0][0] if corrections else text
            patterns.append({
                "original": text,
                "frequency": count,
                "best_correction": best_correction,
                "confidence": round(sum(p["confidence"] for p in phrases if p.get("original", "").lower().strip() == text) / count, 3),
            })
    return patterns


def generate_corrections(patterns):
    """Generate phonetic corrections for patterns."""
    corrections = []
    for p in patterns:
        # Simple phonetic mapping for French
        original = p["original"]
        corrected = p["best_correction"]

        if original != corrected and len(corrected) > 2:
            corrections.append({
                "original": original,
                "corrected": corrected,
                "frequency": p["frequency"],
                "type": "phonetic",
                "confidence": min(0.4 + p["frequency"] * 0.1, 0.95),
            })

    return corrections


def do_analyze():
    """Full voice training analysis."""
    db = init_db()
    phrases = get_low_confidence_phrases()
    patterns = detect_patterns(phrases)
    corrections = generate_corrections(patterns)

    # Store corrections
    for c in corrections:
        db.execute(
            "INSERT INTO generated_corrections (ts, original, corrected, confidence) VALUES (?,?,?,?)",
            (time.time(), c["original"], c["corrected"], c["confidence"])
        )

    db.execute(
        "INSERT INTO analyses (ts, total_corrections, low_confidence, patterns_found, corrections_generated) VALUES (?,?,?,?,?)",
        (time.time(), len(phrases), sum(1 for p in phrases if p.get("confidence", 1) < 0.5),
         len(patterns), len(corrections))
    )
    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "total_low_confidence": len(phrases),
        "patterns_detected": len(patterns),
        "corrections_generated": len(corrections),
        "top_patterns": patterns[:10],
        "corrections": corrections[:10],
    }


def main():
    parser = argparse.ArgumentParser(description="JARVIS Voice Trainer")
    parser.add_argument("--once", "--analyze", action="store_true", help="Analyze and train")
    parser.add_argument("--gaps", action="store_true", help="Show gaps")
    parser.add_argument("--generate", action="store_true", help="Generate corrections")
    parser.add_argument("--test", action="store_true", help="Test corrections")
    args = parser.parse_args()

    result = do_analyze()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
