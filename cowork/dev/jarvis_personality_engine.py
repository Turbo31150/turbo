#!/usr/bin/env python3
"""jarvis_personality_engine.py — JARVIS personality modes and adaptive style.
COWORK #223 — Batch 102: JARVIS Conversational AI

Usage:
    python dev/jarvis_personality_engine.py --mode
    python dev/jarvis_personality_engine.py --set professionnel
    python dev/jarvis_personality_engine.py --adapt
    python dev/jarvis_personality_engine.py --stats
    python dev/jarvis_personality_engine.py --once
"""
import argparse, json, sqlite3, time, subprocess, os
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "personality_engine.db"

PERSONALITIES = {
    "professionnel": {
        "description": "Concis, formel, direct. Pas d'humour.",
        "tone": "formal",
        "verbosity": "low",
        "humor": False,
        "emoji": False,
        "greeting": "Bonjour. Comment puis-je vous aider ?",
        "hours": (8, 18),
        "subjects": ["business", "email", "meeting", "report"]
    },
    "decontracte": {
        "description": "Detendu, humour leger, conversationnel.",
        "tone": "casual",
        "verbosity": "medium",
        "humor": True,
        "emoji": False,
        "greeting": "Salut Turbo ! Quoi de neuf ?",
        "hours": (18, 23),
        "subjects": ["general", "chat", "music", "gaming"]
    },
    "technique": {
        "description": "Focus code, snippets, details techniques.",
        "tone": "technical",
        "verbosity": "high",
        "humor": False,
        "emoji": False,
        "greeting": "Mode technique actif. Quel est le probleme ?",
        "hours": (9, 22),
        "subjects": ["code", "debug", "architecture", "system", "cluster"]
    },
    "pedagogique": {
        "description": "Explications detaillees, exemples, analogies.",
        "tone": "educational",
        "verbosity": "high",
        "humor": False,
        "emoji": False,
        "greeting": "Mode pedagogique. Je vais tout expliquer etape par etape.",
        "hours": (0, 24),
        "subjects": ["learning", "tutorial", "explain", "how-to"]
    },
    "urgence": {
        "description": "Ultra-concis, priorite action, pas de fioriture.",
        "tone": "urgent",
        "verbosity": "minimal",
        "humor": False,
        "emoji": False,
        "greeting": "Mode urgence. Action ?",
        "hours": (0, 24),
        "subjects": ["alert", "error", "critical", "fix"]
    }
}

SUBJECT_KEYWORDS = {
    "code": ["code", "python", "function", "class", "debug", "error", "script", "module"],
    "trading": ["trading", "signal", "profit", "btc", "crypto", "position"],
    "system": ["windows", "service", "process", "disk", "ram", "cpu", "gpu"],
    "general": ["salut", "bonjour", "aide", "help", "question", "merci"],
    "learning": ["apprends", "explique", "comment", "pourquoi", "tutorial"],
}

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS personality_state (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        mode TEXT NOT NULL,
        reason TEXT,
        auto_detected INTEGER DEFAULT 0
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS personality_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        mode TEXT NOT NULL,
        duration_seconds INTEGER DEFAULT 0,
        interactions INTEGER DEFAULT 0
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS adaptation_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        hour INTEGER,
        detected_subject TEXT,
        suggested_mode TEXT,
        applied INTEGER DEFAULT 0
    )""")
    db.commit()
    return db

def get_current_mode(db):
    row = db.execute("SELECT mode, ts, reason FROM personality_state ORDER BY id DESC LIMIT 1").fetchone()
    if row:
        return {"mode": row[0], "since": row[1], "reason": row[2]}
    return {"mode": "professionnel", "since": datetime.now().isoformat(), "reason": "default"}

def detect_subject(text):
    text_lower = text.lower()
    scores = {}
    for subject, keywords in SUBJECT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[subject] = score
    return max(scores, key=scores.get) if scores else "general"

def suggest_mode_by_context(hour=None, subject=None):
    """Suggest personality mode based on hour and subject."""
    if hour is None:
        hour = datetime.now().hour
    if subject is None:
        subject = "general"

    # Subject-based
    for mode_name, mode_info in PERSONALITIES.items():
        if subject in mode_info.get("subjects", []):
            h_start, h_end = mode_info["hours"]
            if h_start <= hour < h_end:
                return mode_name

    # Hour-based fallback
    if 8 <= hour < 18:
        return "professionnel"
    elif 18 <= hour < 23:
        return "decontracte"
    else:
        return "decontracte"

def do_mode():
    db = init_db()
    current = get_current_mode(db)
    mode_info = PERSONALITIES.get(current["mode"], {})
    result = {
        "action": "current_mode",
        "mode": current["mode"],
        "since": current["since"],
        "reason": current["reason"],
        "description": mode_info.get("description", ""),
        "tone": mode_info.get("tone", ""),
        "verbosity": mode_info.get("verbosity", ""),
        "humor": mode_info.get("humor", False),
        "greeting": mode_info.get("greeting", ""),
        "available_modes": list(PERSONALITIES.keys()),
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_set(mode_name):
    db = init_db()
    mode_name = mode_name.lower()
    if mode_name not in PERSONALITIES:
        db.close()
        return {"error": f"Unknown mode '{mode_name}'", "available": list(PERSONALITIES.keys())}

    db.execute("INSERT INTO personality_state (ts, mode, reason, auto_detected) VALUES (?,?,?,?)",
               (datetime.now().isoformat(), mode_name, "manual_set", 0))
    db.commit()

    mode_info = PERSONALITIES[mode_name]
    result = {
        "action": "set_mode",
        "mode": mode_name,
        "description": mode_info["description"],
        "greeting": mode_info["greeting"],
        "tone": mode_info["tone"],
        "success": True,
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_adapt():
    db = init_db()
    hour = datetime.now().hour
    suggested = suggest_mode_by_context(hour=hour)
    current = get_current_mode(db)

    changed = suggested != current["mode"]
    if changed:
        db.execute("INSERT INTO personality_state (ts, mode, reason, auto_detected) VALUES (?,?,?,?)",
                   (datetime.now().isoformat(), suggested, f"auto_adapt_hour_{hour}", 1))

    db.execute("INSERT INTO adaptation_log (ts, hour, detected_subject, suggested_mode, applied) VALUES (?,?,?,?,?)",
               (datetime.now().isoformat(), hour, "time_based", suggested, int(changed)))
    db.commit()

    result = {
        "action": "adapt",
        "current_hour": hour,
        "previous_mode": current["mode"],
        "suggested_mode": suggested,
        "changed": changed,
        "description": PERSONALITIES[suggested]["description"],
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_stats():
    db = init_db()
    mode_counts = db.execute("SELECT mode, COUNT(*) FROM personality_state GROUP BY mode ORDER BY COUNT(*) DESC").fetchall()
    auto_count = db.execute("SELECT COUNT(*) FROM personality_state WHERE auto_detected=1").fetchone()[0]
    manual_count = db.execute("SELECT COUNT(*) FROM personality_state WHERE auto_detected=0").fetchone()[0]
    total = db.execute("SELECT COUNT(*) FROM personality_state").fetchone()[0]
    recent = db.execute("SELECT ts, mode, reason FROM personality_state ORDER BY id DESC LIMIT 10").fetchall()
    adaptations = db.execute("SELECT COUNT(*) FROM adaptation_log").fetchone()[0]

    result = {
        "action": "stats",
        "mode_usage": {r[0]: r[1] for r in mode_counts},
        "total_switches": total,
        "auto_detected": auto_count,
        "manual_set": manual_count,
        "total_adaptations": adaptations,
        "recent_changes": [{"ts": r[0], "mode": r[1], "reason": r[2]} for r in recent],
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_once():
    db = init_db()
    current = get_current_mode(db)
    total = db.execute("SELECT COUNT(*) FROM personality_state").fetchone()[0]
    result = {
        "status": "ok",
        "current_mode": current["mode"],
        "current_description": PERSONALITIES.get(current["mode"], {}).get("description", ""),
        "since": current["since"],
        "total_switches": total,
        "available_modes": list(PERSONALITIES.keys()),
        "current_hour": datetime.now().hour,
        "suggested_mode": suggest_mode_by_context(),
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def main():
    parser = argparse.ArgumentParser(description="JARVIS Personality Engine — COWORK #223")
    parser.add_argument("--mode", action="store_true", help="Show current personality mode")
    parser.add_argument("--set", type=str, metavar="STYLE", help="Set personality mode")
    parser.add_argument("--adapt", action="store_true", help="Auto-adapt based on context")
    parser.add_argument("--stats", action="store_true", help="Show personality statistics")
    parser.add_argument("--once", action="store_true", help="One-shot status check")
    args = parser.parse_args()

    if args.set:
        print(json.dumps(do_set(args.set), ensure_ascii=False, indent=2))
    elif args.mode:
        print(json.dumps(do_mode(), ensure_ascii=False, indent=2))
    elif args.adapt:
        print(json.dumps(do_adapt(), ensure_ascii=False, indent=2))
    elif args.stats:
        print(json.dumps(do_stats(), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(do_once(), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
