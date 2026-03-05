#!/usr/bin/env python3
"""JARVIS Voice Trainer — Entrainement continu des corrections vocales."""
import json, sys, os, sqlite3
from datetime import datetime
from collections import Counter

JARVIS_DB = "F:/BUREAU/turbo/data/jarvis.db"
TRAINER_DB = "C:/Users/franc/.openclaw/workspace/dev/trainer.db"

def init_db():
    conn = sqlite3.connect(TRAINER_DB)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS suggestions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT, wrong TEXT, correct TEXT, category TEXT,
        confidence REAL, source TEXT, applied INTEGER DEFAULT 0
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS patterns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pattern TEXT UNIQUE, frequency INTEGER, last_seen TEXT
    )""")
    conn.commit()
    return conn

def load_corrections():
    if not os.path.exists(JARVIS_DB):
        print(f"DB not found: {JARVIS_DB}")
        return []
    conn = sqlite3.connect(JARVIS_DB)
    c = conn.cursor()
    try:
        c.execute("SELECT wrong, correct, category, hit_count FROM voice_corrections ORDER BY id DESC")
        rows = [{"wrong": r[0], "correct": r[1], "category": r[2], "type": "phonetic", "hits": r[3]} for r in c.fetchall()]
    except Exception as e:
        print(f"Error: {e}")
        c.execute("SELECT * FROM voice_corrections LIMIT 1")
        print(f"Columns: {[d[0] for d in c.description]}")
        rows = []
    conn.close()
    return rows

def analyze_patterns(corrections):
    """Analyse les patterns d'erreurs les plus frequents."""
    wrong_words = Counter()
    categories = Counter()
    types = Counter()
    prefixes = Counter()

    for c in corrections:
        wrong = c["wrong"].lower()
        wrong_words[wrong] += 1
        if c["category"]: categories[c["category"]] += 1
        if c["type"]: types[c["type"]] += 1
        # Common prefix patterns
        words = wrong.split()
        if words:
            prefixes[words[0]] += 1

    return {
        "total": len(corrections),
        "unique_wrong": len(wrong_words),
        "top_errors": wrong_words.most_common(20),
        "top_categories": categories.most_common(10),
        "top_types": types.most_common(5),
        "top_prefixes": prefixes.most_common(10),
    }

def suggest_corrections(corrections, tdb):
    """Genere des suggestions de nouvelles corrections basees sur les patterns."""
    # Find similar wrong forms that might need new corrections
    wrong_set = {c["wrong"].lower() for c in corrections}
    correct_map = {}
    for c in corrections:
        correct_map[c["wrong"].lower()] = c["correct"]

    suggestions = []
    # Pattern: common misspellings/phonetic variations
    phonetic_swaps = [
        ("j", "g"), ("s", "c"), ("f", "ph"), ("k", "c"), ("ai", "e"),
        ("au", "o"), ("ou", "u"), ("an", "en"), ("in", "ain"),
    ]

    for c in corrections[:100]:  # Check recent corrections
        wrong = c["wrong"].lower()
        for old, new in phonetic_swaps:
            variant = wrong.replace(old, new, 1)
            if variant != wrong and variant not in wrong_set:
                suggestions.append({
                    "wrong": variant,
                    "correct": c["correct"],
                    "category": c["category"],
                    "confidence": 0.6,
                    "source": f"phonetic_swap:{old}->{new} from '{wrong}'",
                })

    # Save suggestions
    tc = tdb.cursor()
    added = 0
    for s in suggestions[:50]:  # Limit
        try:
            tc.execute("INSERT OR IGNORE INTO suggestions (ts, wrong, correct, category, confidence, source) VALUES (?,?,?,?,?,?)",
                      (datetime.now().isoformat(), s["wrong"], s["correct"], s["category"], s["confidence"], s["source"]))
            if tc.rowcount > 0: added += 1
        except: pass
    tdb.commit()

    return suggestions[:50], added

def show_stats(corrections, analysis):
    print(f"[VOICE TRAINER] {analysis['total']} corrections, {analysis['unique_wrong']} unique")
    print(f"\nTop erreurs:")
    for word, count in analysis["top_errors"][:10]:
        print(f"  '{word}': {count}x")
    print(f"\nCategories:")
    for cat, count in analysis["top_categories"]:
        print(f"  {cat}: {count}")
    print(f"\nTypes:")
    for t, count in analysis["top_types"]:
        print(f"  {t}: {count}")

if __name__ == "__main__":
    tdb = init_db()
    corrections = load_corrections()

    if "--analyze" in sys.argv:
        analysis = analyze_patterns(corrections)
        show_stats(corrections, analysis)

    elif "--suggest" in sys.argv:
        suggestions, added = suggest_corrections(corrections, tdb)
        print(f"[VOICE TRAINER] {len(suggestions)} suggestions generees, {added} nouvelles")
        for s in suggestions[:10]:
            print(f"  '{s['wrong']}' -> '{s['correct']}' ({s['source'][:40]})")

    elif "--stats" in sys.argv:
        analysis = analyze_patterns(corrections)
        tc = tdb.cursor()
        tc.execute("SELECT COUNT(*) FROM suggestions")
        total_sug = tc.fetchone()[0]
        tc.execute("SELECT COUNT(*) FROM suggestions WHERE applied=1")
        applied = tc.fetchone()[0]
        print(f"[VOICE TRAINER] {analysis['total']} corrections | {total_sug} suggestions ({applied} applied)")

    else:
        print("Usage: voice_trainer.py --analyze | --suggest | --stats")

    tdb.close()
