#!/usr/bin/env python3
"""jarvis_dialog_manager.py — Multi-turn dialog context manager for JARVIS.
COWORK #222 — Batch 102: JARVIS Conversational AI

Usage:
    python dev/jarvis_dialog_manager.py --start
    python dev/jarvis_dialog_manager.py --context
    python dev/jarvis_dialog_manager.py --history
    python dev/jarvis_dialog_manager.py --reset
    python dev/jarvis_dialog_manager.py --once
"""
import argparse, json, sqlite3, time, subprocess, os, hashlib, re
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "dialog_manager.db"

MAX_CONTEXT_TURNS = 20
MAX_CONTEXT_TOKENS_ESTIMATE = 4000

TOPIC_KEYWORDS = {
    "code": ["code", "python", "javascript", "function", "class", "bug", "error", "debug", "variable", "script", "module", "import"],
    "trading": ["trading", "bitcoin", "crypto", "mexc", "signal", "profit", "loss", "position", "usdt", "btc", "eth", "sol"],
    "system": ["windows", "service", "process", "registry", "disk", "ram", "cpu", "gpu", "driver", "update", "install"],
    "cluster": ["cluster", "node", "m1", "m2", "m3", "ollama", "lmstudio", "model", "agent", "benchmark"],
    "voice": ["voice", "tts", "whisper", "wake", "speech", "dictation", "audio", "microphone"],
    "general": ["jarvis", "aide", "help", "bonjour", "salut", "merci", "question"],
}

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT UNIQUE NOT NULL,
        started_at TEXT NOT NULL,
        last_activity TEXT NOT NULL,
        topic TEXT DEFAULT 'general',
        turns INTEGER DEFAULT 0,
        entities TEXT DEFAULT '[]',
        summary TEXT,
        active INTEGER DEFAULT 1
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS turns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        ts TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        topic TEXT,
        entities TEXT DEFAULT '[]',
        token_estimate INTEGER DEFAULT 0,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id)
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS topic_changes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        ts TEXT NOT NULL,
        from_topic TEXT,
        to_topic TEXT,
        trigger_text TEXT
    )""")
    db.commit()
    return db

def generate_session_id():
    return hashlib.md5(f"{time.time()}_{os.getpid()}".encode()).hexdigest()[:12]

def estimate_tokens(text):
    """Rough token estimate: ~4 chars per token for French/English mix."""
    return max(1, len(text) // 4)

def detect_topic(text):
    """Detect topic from text content."""
    text_lower = text.lower()
    scores = {}
    for topic, keywords in TOPIC_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[topic] = score
    if scores:
        return max(scores, key=scores.get)
    return "general"

def extract_entities(text):
    """Extract simple entities (names, numbers, paths, URLs)."""
    entities = []
    # File paths
    paths = re.findall(r'[A-Za-z]:[/\\][\w/\\.\\-]+', text)
    for p in paths:
        entities.append({"type": "path", "value": p})
    # Numbers
    numbers = re.findall(r'\b\d+\.?\d*\b', text)
    for n in numbers[:5]:
        entities.append({"type": "number", "value": n})
    # Quoted strings
    quoted = re.findall(r'"([^"]+)"', text)
    for q in quoted:
        entities.append({"type": "quoted", "value": q})
    return entities

def get_active_session(db):
    """Get or create active session."""
    row = db.execute("SELECT session_id, topic, turns, started_at FROM sessions WHERE active=1 ORDER BY id DESC LIMIT 1").fetchone()
    if row:
        return {"session_id": row[0], "topic": row[1], "turns": row[2], "started_at": row[3]}
    return None

def do_start():
    db = init_db()
    # Deactivate old sessions
    db.execute("UPDATE sessions SET active=0 WHERE active=1")
    sid = generate_session_id()
    now = datetime.now().isoformat()
    db.execute("INSERT INTO sessions (session_id, started_at, last_activity, topic, turns, active) VALUES (?,?,?,?,?,?)",
               (sid, now, now, "general", 0, 1))
    db.commit()
    result = {
        "action": "start_session",
        "session_id": sid,
        "topic": "general",
        "started_at": now,
        "status": "active"
    }
    db.close()
    return result

def do_context():
    db = init_db()
    session = get_active_session(db)
    if not session:
        db.close()
        return {"error": "No active session. Use --start first."}

    sid = session["session_id"]
    turns = db.execute("SELECT ts, role, content, topic, entities, token_estimate FROM turns WHERE session_id=? ORDER BY id DESC LIMIT ?",
                       (sid, MAX_CONTEXT_TURNS)).fetchall()
    turns.reverse()

    context_turns = []
    total_tokens = 0
    for t in turns:
        tokens = t[5]
        total_tokens += tokens
        context_turns.append({
            "ts": t[0], "role": t[1], "content": t[2][:200],
            "topic": t[3], "entities": json.loads(t[4]) if t[4] else [],
            "tokens": tokens
        })

    # Session entities
    all_entities = []
    for ct in context_turns:
        all_entities.extend(ct.get("entities", []))
    unique_entities = list({json.dumps(e): e for e in all_entities}.values())

    needs_resume = total_tokens > MAX_CONTEXT_TOKENS_ESTIMATE
    result = {
        "action": "context",
        "session_id": sid,
        "topic": session["topic"],
        "turns_in_context": len(context_turns),
        "total_turns": session["turns"],
        "estimated_tokens": total_tokens,
        "needs_resume": needs_resume,
        "entities": unique_entities[:20],
        "context": context_turns,
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_history():
    db = init_db()
    sessions = db.execute("SELECT session_id, started_at, last_activity, topic, turns, active FROM sessions ORDER BY id DESC LIMIT 20").fetchall()
    history = []
    for s in sessions:
        history.append({
            "session_id": s[0], "started_at": s[1], "last_activity": s[2],
            "topic": s[3], "turns": s[4], "active": bool(s[5])
        })
    topic_changes = db.execute("SELECT ts, from_topic, to_topic, trigger_text FROM topic_changes ORDER BY id DESC LIMIT 10").fetchall()
    result = {
        "action": "history",
        "sessions": history,
        "total_sessions": len(history),
        "recent_topic_changes": [{"ts": r[0], "from": r[1], "to": r[2], "trigger": r[3][:80] if r[3] else None} for r in topic_changes],
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_reset():
    db = init_db()
    db.execute("UPDATE sessions SET active=0")
    db.commit()
    result = {
        "action": "reset",
        "all_sessions_deactivated": True,
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_once():
    db = init_db()
    session = get_active_session(db)
    total_sessions = db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    total_turns = db.execute("SELECT COUNT(*) FROM turns").fetchone()[0]
    total_topic_changes = db.execute("SELECT COUNT(*) FROM topic_changes").fetchone()[0]
    result = {
        "status": "ok",
        "active_session": session,
        "total_sessions": total_sessions,
        "total_turns": total_turns,
        "total_topic_changes": total_topic_changes,
        "max_context_turns": MAX_CONTEXT_TURNS,
        "max_context_tokens": MAX_CONTEXT_TOKENS_ESTIMATE,
        "supported_topics": list(TOPIC_KEYWORDS.keys()),
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def main():
    parser = argparse.ArgumentParser(description="JARVIS Dialog Manager — COWORK #222")
    parser.add_argument("--start", action="store_true", help="Start new dialog session")
    parser.add_argument("--context", action="store_true", help="Show current context")
    parser.add_argument("--history", action="store_true", help="Show session history")
    parser.add_argument("--reset", action="store_true", help="Reset all sessions")
    parser.add_argument("--once", action="store_true", help="One-shot status check")
    args = parser.parse_args()

    if args.start:
        print(json.dumps(do_start(), ensure_ascii=False, indent=2))
    elif args.context:
        print(json.dumps(do_context(), ensure_ascii=False, indent=2))
    elif args.history:
        print(json.dumps(do_history(), ensure_ascii=False, indent=2))
    elif args.reset:
        print(json.dumps(do_reset(), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(do_once(), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
