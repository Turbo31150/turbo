#!/usr/bin/env python3
"""jarvis_nlp_enhancer.py — Ameliorateur NLP JARVIS.

Enrichit la comprehension du langage naturel.

Usage:
    python dev/jarvis_nlp_enhancer.py --once
    python dev/jarvis_nlp_enhancer.py --analyze
    python dev/jarvis_nlp_enhancer.py --synonyms
    python dev/jarvis_nlp_enhancer.py --typos
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
DB_PATH = DEV / "data" / "nlp_enhancer.db"
JARVIS_DB = Path("F:/BUREAU/turbo/data/jarvis.db")

SYNONYM_MAP = {
    "supprime": ["efface", "enleve", "retire", "delete", "remove", "vire"],
    "ouvre": ["lance", "demarre", "start", "open", "run"],
    "ferme": ["quitte", "arrete", "stop", "close", "kill", "termine"],
    "cherche": ["trouve", "search", "look", "scan", "regarde"],
    "copie": ["duplique", "clone", "copy"],
    "deplace": ["bouge", "move", "transfere"],
    "affiche": ["montre", "display", "show", "print"],
    "sauvegarde": ["save", "backup", "enregistre"],
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS analyses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, failed_commands INTEGER, new_synonyms INTEGER,
        typos_detected INTEGER, expansions INTEGER)""")
    db.execute("""CREATE TABLE IF NOT EXISTS suggestions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, original TEXT, suggestion TEXT,
        suggestion_type TEXT, confidence REAL)""")
    db.commit()
    return db


def get_failed_commands():
    failed = []
    if not JARVIS_DB.exists():
        return failed
    try:
        db = sqlite3.connect(str(JARVIS_DB))
        tables = [t[0] for t in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        for t in tables:
            cols = [c[1] for c in db.execute(f"PRAGMA table_info([{t}])").fetchall()]
            if "confidence" in cols:
                text_col = next((c for c in cols if c in ("text", "command", "input", "original")), None)
                if text_col:
                    try:
                        rows = db.execute(
                            f"SELECT [{text_col}], confidence FROM [{t}] WHERE confidence < 0.5 AND [{text_col}] IS NOT NULL LIMIT 100"
                        ).fetchall()
                        for r in rows:
                            if r[0]:
                                failed.append({"text": r[0], "confidence": r[1]})
                    except Exception:
                        pass
        db.close()
    except Exception:
        pass
    return failed


def detect_missing_synonyms(failed):
    suggestions = []
    for f in failed:
        text = f["text"].lower()
        for base, syns in SYNONYM_MAP.items():
            for syn in syns:
                if syn in text and base not in text:
                    suggestions.append({
                        "original": f["text"],
                        "suggestion": f"Add synonym: '{syn}' → '{base}'",
                        "type": "synonym",
                        "confidence": 0.7,
                    })
                    break
    return suggestions


def detect_typos(failed):
    typos = []
    common_typos = {
        "statu": "status", "healt": "health", "tradin": "trading",
        "cluste": "cluster", "audti": "audit", "systeme": "system",
    }
    for f in failed:
        text = f["text"].lower()
        for typo, correct in common_typos.items():
            if typo in text:
                typos.append({
                    "original": f["text"],
                    "suggestion": f"Typo: '{typo}' → '{correct}'",
                    "type": "typo",
                    "confidence": 0.8,
                })
    return typos


def do_analyze():
    db = init_db()
    failed = get_failed_commands()
    synonyms = detect_missing_synonyms(failed)
    typos = detect_typos(failed)

    all_suggestions = synonyms + typos
    for s in all_suggestions:
        db.execute("INSERT INTO suggestions (ts, original, suggestion, suggestion_type, confidence) VALUES (?,?,?,?,?)",
                   (time.time(), s["original"], s["suggestion"], s["type"], s["confidence"]))

    db.execute("INSERT INTO analyses (ts, failed_commands, new_synonyms, typos_detected, expansions) VALUES (?,?,?,?,?)",
               (time.time(), len(failed), len(synonyms), len(typos), 0))
    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "failed_commands_analyzed": len(failed),
        "synonym_suggestions": len(synonyms),
        "typo_detections": len(typos),
        "top_suggestions": all_suggestions[:15],
    }


def main():
    parser = argparse.ArgumentParser(description="JARVIS NLP Enhancer")
    parser.add_argument("--once", "--analyze", action="store_true", help="Analyze NLP")
    parser.add_argument("--synonyms", action="store_true", help="Show synonyms")
    parser.add_argument("--typos", action="store_true", help="Show typos")
    parser.add_argument("--expand", action="store_true", help="Expand triggers")
    args = parser.parse_args()
    print(json.dumps(do_analyze(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
