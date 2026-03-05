#!/usr/bin/env python3
"""interaction_predictor.py — Prediction intelligente des interactions utilisateur.

Apprend des patterns d'interaction, predit les besoins, suggere des actions proactives.
Analyse les heures, frequences, sequences de commandes.

Usage:
    python dev/interaction_predictor.py --learn FILE       # Apprendre d'un fichier de logs
    python dev/interaction_predictor.py --predict           # Predire la prochaine action
    python dev/interaction_predictor.py --suggest           # Suggestions proactives
    python dev/interaction_predictor.py --patterns          # Afficher les patterns detectes
    python dev/interaction_predictor.py --stats             # Statistiques d'utilisation
    python dev/interaction_predictor.py --log "commande"    # Logger une interaction
    python dev/interaction_predictor.py --routine           # Routine du moment
"""
import argparse
import json
import os
import re
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "predictor.db"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS interactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, hour INTEGER, day_of_week INTEGER,
        command TEXT, category TEXT, params TEXT,
        duration_ms INTEGER DEFAULT 0, success INTEGER DEFAULT 1)""")
    db.execute("""CREATE TABLE IF NOT EXISTS patterns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, pattern_type TEXT, pattern_key TEXT,
        pattern_value TEXT, confidence REAL, occurrences INTEGER)""")
    db.execute("""CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, predicted_action TEXT, confidence REAL,
        reason TEXT, was_correct INTEGER DEFAULT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS sequences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, command_a TEXT, command_b TEXT,
        count INTEGER DEFAULT 1, avg_delay_s REAL DEFAULT 0)""")
    db.commit()
    return db

# ---------------------------------------------------------------------------
# Categories de commandes
# ---------------------------------------------------------------------------
CATEGORIES = {
    "email": ["mail", "email", "inbox", "courrier", "gmail"],
    "trading": ["trading", "trade", "crypto", "bitcoin", "signal", "marche"],
    "system": ["status", "health", "gpu", "temperature", "disque", "ram", "cpu"],
    "desktop": ["range", "bureau", "organise", "fichier", "dossier"],
    "browser": ["ouvre", "navigateur", "chrome", "cherche", "google", "site", "page"],
    "window": ["fenetre", "ecran", "deplace", "maximise", "minimise", "ferme"],
    "voice": ["vocal", "parle", "dis", "repete"],
    "cluster": ["cluster", "benchmark", "noeud", "modele", "agent"],
    "dev": ["code", "script", "test", "deploie", "commit", "git"],
    "rapport": ["rapport", "resume", "bilan", "recap"],
}

def categorize(command: str) -> str:
    cmd_lower = command.lower()
    for cat, keywords in CATEGORIES.items():
        for kw in keywords:
            if kw in cmd_lower:
                return cat
    return "other"

# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------
def log_interaction(db, command: str, params: str = "", duration_ms: int = 0, success: bool = True):
    """Enregistre une interaction."""
    now = time.time()
    dt = datetime.fromtimestamp(now)
    category = categorize(command)
    db.execute(
        "INSERT INTO interactions (ts, hour, day_of_week, command, category, params, duration_ms, success) VALUES (?,?,?,?,?,?,?,?)",
        (now, dt.hour, dt.weekday(), command, category, params, duration_ms, int(success))
    )
    # Update sequences (last command → this command)
    last = db.execute(
        "SELECT command, ts FROM interactions ORDER BY ts DESC LIMIT 1 OFFSET 1"
    ).fetchone()
    if last:
        last_cmd, last_ts = last
        delay = now - last_ts
        if delay < 3600:  # Only if within 1 hour
            existing = db.execute(
                "SELECT id, count, avg_delay_s FROM sequences WHERE command_a=? AND command_b=?",
                (categorize(last_cmd), category)
            ).fetchone()
            if existing:
                new_count = existing[1] + 1
                new_avg = (existing[2] * existing[1] + delay) / new_count
                db.execute("UPDATE sequences SET count=?, avg_delay_s=?, ts=? WHERE id=?",
                           (new_count, new_avg, now, existing[0]))
            else:
                db.execute(
                    "INSERT INTO sequences (ts, command_a, command_b, count, avg_delay_s) VALUES (?,?,?,1,?)",
                    (now, categorize(last_cmd), category, delay)
                )
    db.commit()
    return {"logged": True, "command": command, "category": category, "hour": dt.hour}

def analyze_patterns(db) -> list:
    """Analyse les patterns d'utilisation."""
    patterns = []

    # Pattern 1: Heures de pointe par categorie
    rows = db.execute(
        "SELECT category, hour, COUNT(*) as cnt FROM interactions GROUP BY category, hour ORDER BY cnt DESC"
    ).fetchall()
    hourly = defaultdict(lambda: defaultdict(int))
    for cat, hour, cnt in rows:
        hourly[cat][hour] = cnt
    for cat, hours in hourly.items():
        if hours:
            peak_hour = max(hours, key=hours.get)
            patterns.append({
                "type": "peak_hour",
                "category": cat,
                "hour": peak_hour,
                "count": hours[peak_hour],
                "confidence": min(hours[peak_hour] / 5, 1.0),
            })

    # Pattern 2: Sequences frequentes
    seqs = db.execute(
        "SELECT command_a, command_b, count, avg_delay_s FROM sequences WHERE count >= 2 ORDER BY count DESC LIMIT 20"
    ).fetchall()
    for a, b, cnt, delay in seqs:
        patterns.append({
            "type": "sequence",
            "from": a, "to": b,
            "count": cnt,
            "avg_delay_s": round(delay, 1),
            "confidence": min(cnt / 5, 1.0),
        })

    # Pattern 3: Jours de la semaine
    rows = db.execute(
        "SELECT day_of_week, category, COUNT(*) FROM interactions GROUP BY day_of_week, category ORDER BY 3 DESC"
    ).fetchall()
    day_patterns = defaultdict(lambda: defaultdict(int))
    for dow, cat, cnt in rows:
        day_patterns[dow][cat] = cnt
    days = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    for dow, cats in day_patterns.items():
        top = max(cats, key=cats.get) if cats else None
        if top:
            patterns.append({
                "type": "day_preference",
                "day": days[dow],
                "top_category": top,
                "count": cats[top],
            })

    # Pattern 4: Frequence globale
    total = db.execute("SELECT COUNT(*) FROM interactions").fetchone()[0]
    first = db.execute("SELECT MIN(ts) FROM interactions").fetchone()[0]
    if first and total > 1:
        days_active = max((time.time() - first) / 86400, 1)
        patterns.append({
            "type": "frequency",
            "total_interactions": total,
            "days_active": round(days_active, 1),
            "avg_per_day": round(total / days_active, 1),
        })

    return patterns

def predict_next(db) -> dict:
    """Predit la prochaine action probable."""
    now = datetime.now()
    hour = now.hour
    dow = now.weekday()

    predictions = []

    # Based on current hour + day
    rows = db.execute("""
        SELECT category, COUNT(*) as cnt FROM interactions
        WHERE hour = ? AND day_of_week = ?
        GROUP BY category ORDER BY cnt DESC LIMIT 3
    """, (hour, dow)).fetchall()
    for cat, cnt in rows:
        predictions.append({
            "action": cat,
            "reason": f"A {hour}h le {['lundi','mardi','mercredi','jeudi','vendredi','samedi','dimanche'][dow]}, tu fais souvent '{cat}'",
            "confidence": min(cnt / 3, 0.95),
            "occurrences": cnt,
        })

    # Based on last command sequence
    last = db.execute(
        "SELECT command, category FROM interactions ORDER BY ts DESC LIMIT 1"
    ).fetchone()
    if last:
        last_cat = last[1]
        seqs = db.execute(
            "SELECT command_b, count, avg_delay_s FROM sequences WHERE command_a=? ORDER BY count DESC LIMIT 3",
            (last_cat,)
        ).fetchall()
        for next_cat, cnt, delay in seqs:
            predictions.append({
                "action": next_cat,
                "reason": f"Apres '{last_cat}', tu fais souvent '{next_cat}' (dans ~{delay:.0f}s)",
                "confidence": min(cnt / 5, 0.9),
                "occurrences": cnt,
            })

    # Deduplicate and sort by confidence
    seen = set()
    unique = []
    for p in sorted(predictions, key=lambda x: x["confidence"], reverse=True):
        if p["action"] not in seen:
            seen.add(p["action"])
            unique.append(p)

    return {
        "timestamp": now.isoformat(),
        "hour": hour,
        "predictions": unique[:5],
    }

def get_suggestions(db) -> dict:
    """Suggestions proactives basees sur les patterns."""
    now = datetime.now()
    suggestions = []

    # Check if it's time for common routines
    patterns = analyze_patterns(db)
    for p in patterns:
        if p["type"] == "peak_hour" and p["hour"] == now.hour and p["confidence"] >= 0.5:
            suggestions.append({
                "suggestion": f"C'est l'heure habituelle pour '{p['category']}'",
                "category": p["category"],
                "confidence": p["confidence"],
            })

    # Check unfulfilled routines today
    today_start = datetime(now.year, now.month, now.day).timestamp()
    today_cats = set(r[0] for r in db.execute(
        "SELECT DISTINCT category FROM interactions WHERE ts >= ?", (today_start,)
    ).fetchall())

    # Find categories usually done by now
    usual = db.execute("""
        SELECT category, COUNT(*) as cnt FROM interactions
        WHERE hour <= ? AND day_of_week = ?
        GROUP BY category HAVING cnt >= 3 ORDER BY cnt DESC
    """, (now.hour, now.weekday())).fetchall()

    for cat, cnt in usual:
        if cat not in today_cats:
            suggestions.append({
                "suggestion": f"Tu fais habituellement '{cat}' avant {now.hour}h — pas encore fait aujourd'hui",
                "category": cat,
                "confidence": min(cnt / 5, 0.8),
                "missed": True,
            })

    return {
        "timestamp": now.isoformat(),
        "suggestions": sorted(suggestions, key=lambda x: x["confidence"], reverse=True)[:5],
    }

def get_routine(db) -> dict:
    """Routine typique pour ce moment."""
    now = datetime.now()
    hour = now.hour
    dow = now.weekday()

    # What do I usually do at this hour?
    rows = db.execute("""
        SELECT category, command, COUNT(*) as cnt
        FROM interactions
        WHERE hour = ? AND day_of_week = ?
        GROUP BY category ORDER BY cnt DESC LIMIT 5
    """, (hour, dow)).fetchall()

    routine = []
    for cat, cmd, cnt in rows:
        routine.append({"category": cat, "example": cmd, "frequency": cnt})

    # Next hour prediction
    next_rows = db.execute("""
        SELECT category, COUNT(*) as cnt
        FROM interactions
        WHERE hour = ? AND day_of_week = ?
        GROUP BY category ORDER BY cnt DESC LIMIT 3
    """, ((hour + 1) % 24, dow)).fetchall()

    return {
        "current_hour": hour,
        "day": ["lundi","mardi","mercredi","jeudi","vendredi","samedi","dimanche"][dow],
        "usual_now": routine,
        "coming_up": [{"category": cat, "frequency": cnt} for cat, cnt in next_rows],
    }

def get_stats(db) -> dict:
    """Statistiques d'utilisation."""
    total = db.execute("SELECT COUNT(*) FROM interactions").fetchone()[0]
    cats = db.execute("SELECT category, COUNT(*) FROM interactions GROUP BY category ORDER BY 2 DESC").fetchall()
    hours = db.execute("SELECT hour, COUNT(*) FROM interactions GROUP BY hour ORDER BY 2 DESC LIMIT 5").fetchall()
    recent = db.execute("SELECT command, category, ts FROM interactions ORDER BY ts DESC LIMIT 10").fetchall()
    seqs = db.execute("SELECT command_a, command_b, count FROM sequences ORDER BY count DESC LIMIT 10").fetchall()

    return {
        "total_interactions": total,
        "by_category": {cat: cnt for cat, cnt in cats},
        "peak_hours": {str(h): cnt for h, cnt in hours},
        "recent": [{"command": cmd[:50], "category": cat,
                     "when": datetime.fromtimestamp(ts).strftime("%H:%M")} for cmd, cat, ts in recent],
        "top_sequences": [{"from": a, "to": b, "count": c} for a, b, c in seqs],
    }

def learn_from_file(db, filepath: str) -> dict:
    """Apprend d'un fichier de logs (JSONL ou texte)."""
    path = Path(filepath)
    if not path.exists():
        return {"error": f"Fichier non trouve: {filepath}"}

    imported = 0
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                cmd = data.get("command", data.get("text", data.get("content", "")))
                ts = data.get("timestamp", data.get("ts", time.time()))
                if cmd:
                    dt = datetime.fromtimestamp(ts) if isinstance(ts, (int, float)) else datetime.now()
                    category = categorize(cmd)
                    db.execute(
                        "INSERT INTO interactions (ts, hour, day_of_week, command, category) VALUES (?,?,?,?,?)",
                        (dt.timestamp(), dt.hour, dt.weekday(), cmd[:200], category)
                    )
                    imported += 1
            except json.JSONDecodeError:
                # Plain text line
                if len(line) > 3:
                    category = categorize(line)
                    db.execute(
                        "INSERT INTO interactions (ts, hour, day_of_week, command, category) VALUES (?,?,?,?,?)",
                        (time.time(), datetime.now().hour, datetime.now().weekday(), line[:200], category)
                    )
                    imported += 1

    db.commit()
    return {"imported": imported, "file": str(path)}

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="JARVIS Interaction Predictor — Prediction intelligente")
    parser.add_argument("--learn", type=str, help="Apprendre d'un fichier de logs")
    parser.add_argument("--log", type=str, help="Logger une interaction")
    parser.add_argument("--predict", action="store_true", help="Predire prochaine action")
    parser.add_argument("--suggest", action="store_true", help="Suggestions proactives")
    parser.add_argument("--patterns", action="store_true", help="Patterns detectes")
    parser.add_argument("--stats", action="store_true", help="Statistiques")
    parser.add_argument("--routine", action="store_true", help="Routine du moment")
    args = parser.parse_args()

    db = init_db()

    if args.learn:
        result = learn_from_file(db, args.learn)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.log:
        result = log_interaction(db, args.log)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.predict:
        result = predict_next(db)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.suggest:
        result = get_suggestions(db)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.patterns:
        result = analyze_patterns(db)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.stats:
        result = get_stats(db)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.routine:
        result = get_routine(db)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        # Default: predict + suggest
        result = {
            "predictions": predict_next(db),
            "suggestions": get_suggestions(db),
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))

    db.close()

if __name__ == "__main__":
    main()
