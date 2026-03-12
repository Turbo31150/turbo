#!/usr/bin/env python3
"""jarvis_state_machine.py (#185) — System state machine for JARVIS.

States: idle, active, trading, maintenance, emergency, sleeping.
Transition DAG with validation. Full state change logging.

Usage:
    python dev/jarvis_state_machine.py --once
    python dev/jarvis_state_machine.py --status
    python dev/jarvis_state_machine.py --transition active
    python dev/jarvis_state_machine.py --history
    python dev/jarvis_state_machine.py --reset
"""
import argparse
import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "state_machine.db"

# Valid states
STATES = ["idle", "active", "trading", "maintenance", "emergency", "sleeping"]

# Transition DAG: from_state -> [allowed_to_states]
TRANSITIONS = {
    "idle":        ["active", "trading", "maintenance", "sleeping", "emergency"],
    "active":      ["idle", "trading", "maintenance", "emergency"],
    "trading":     ["active", "idle", "emergency"],
    "maintenance": ["idle", "active", "emergency"],
    "emergency":   ["idle", "maintenance"],
    "sleeping":    ["idle", "emergency"],
}

DEFAULT_STATE = "idle"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS state (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        current_state TEXT NOT NULL DEFAULT 'idle',
        entered_at REAL,
        previous_state TEXT DEFAULT '',
        transition_count INTEGER DEFAULT 0
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS state_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        from_state TEXT,
        to_state TEXT,
        event TEXT DEFAULT '',
        duration_in_prev REAL DEFAULT 0
    )""")
    # Ensure singleton row
    row = db.execute("SELECT id FROM state WHERE id=1").fetchone()
    if not row:
        db.execute(
            "INSERT INTO state (id, current_state, entered_at) VALUES (1, ?, ?)",
            (DEFAULT_STATE, time.time())
        )
    db.commit()
    return db


def get_current_state(db):
    """Get current state info."""
    row = db.execute(
        "SELECT current_state, entered_at, previous_state, transition_count FROM state WHERE id=1"
    ).fetchone()
    current, entered_at, prev, count = row
    duration = time.time() - entered_at if entered_at else 0
    return {
        "current_state": current,
        "entered_at": datetime.fromtimestamp(entered_at).isoformat() if entered_at else None,
        "duration_seconds": round(duration, 1),
        "duration_human": _format_duration(duration),
        "previous_state": prev or "none",
        "transition_count": count,
        "allowed_transitions": TRANSITIONS.get(current, [])
    }


def _format_duration(seconds):
    """Format seconds into human-readable."""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds // 60)}m {int(seconds % 60)}s"
    else:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        return f"{h}h {m}m"


def transition(db, target_state, event="manual"):
    """Transition to a new state."""
    target_state = target_state.lower().strip()

    if target_state not in STATES:
        return {
            "status": "error",
            "error": f"Invalid state: {target_state}",
            "valid_states": STATES
        }

    row = db.execute("SELECT current_state, entered_at FROM state WHERE id=1").fetchone()
    current, entered_at = row

    if target_state == current:
        return {
            "status": "noop",
            "message": f"Already in state: {current}"
        }

    allowed = TRANSITIONS.get(current, [])
    if target_state not in allowed:
        return {
            "status": "error",
            "error": f"Transition {current} -> {target_state} not allowed",
            "current": current,
            "allowed": allowed
        }

    now = time.time()
    duration_in_prev = now - entered_at if entered_at else 0

    # Log the transition
    db.execute(
        "INSERT INTO state_log (ts, from_state, to_state, event, duration_in_prev) VALUES (?,?,?,?,?)",
        (now, current, target_state, event, duration_in_prev)
    )

    # Update current state
    db.execute(
        "UPDATE state SET current_state=?, entered_at=?, previous_state=?, transition_count=transition_count+1 WHERE id=1",
        (target_state, now, current)
    )
    db.commit()

    return {
        "status": "ok",
        "from": current,
        "to": target_state,
        "event": event,
        "duration_in_previous": round(duration_in_prev, 1),
        "allowed_next": TRANSITIONS.get(target_state, [])
    }


def get_history(db, limit=50):
    """Get state transition history."""
    rows = db.execute(
        "SELECT ts, from_state, to_state, event, duration_in_prev FROM state_log ORDER BY ts DESC LIMIT ?",
        (limit,)
    ).fetchall()
    history = []
    for r in rows:
        history.append({
            "time": datetime.fromtimestamp(r[0]).isoformat(),
            "from": r[1], "to": r[2],
            "event": r[3],
            "duration_in_prev": round(r[4], 1)
        })
    return {"status": "ok", "count": len(history), "history": history}


def reset_state(db):
    """Reset to idle state."""
    row = db.execute("SELECT current_state FROM state WHERE id=1").fetchone()
    old = row[0] if row else "unknown"

    if old != DEFAULT_STATE:
        db.execute(
            "INSERT INTO state_log (ts, from_state, to_state, event, duration_in_prev) VALUES (?,?,?,?,?)",
            (time.time(), old, DEFAULT_STATE, "reset", 0)
        )

    db.execute(
        "UPDATE state SET current_state=?, entered_at=?, previous_state=?, transition_count=0 WHERE id=1",
        (DEFAULT_STATE, time.time(), old)
    )
    db.commit()
    return {
        "status": "ok",
        "previous": old,
        "current": DEFAULT_STATE,
        "message": "State machine reset to idle"
    }


def once(db):
    """Run once: show current state and stats."""
    state = get_current_state(db)
    log_count = db.execute("SELECT COUNT(*) FROM state_log").fetchone()[0]

    # State durations summary
    state_times = {}
    for s in STATES:
        total = db.execute(
            "SELECT COALESCE(SUM(duration_in_prev), 0) FROM state_log WHERE from_state=?", (s,)
        ).fetchone()[0]
        state_times[s] = round(total, 1)

    return {
        "status": "ok", "mode": "once",
        "current": state,
        "total_transitions": log_count,
        "state_durations": state_times,
        "transition_dag": TRANSITIONS
    }


def main():
    parser = argparse.ArgumentParser(description="JARVIS State Machine (#185) — System state management")
    parser.add_argument("--status", action="store_true", help="Show current state")
    parser.add_argument("--transition", type=str, help="Transition to a new state (event name)")
    parser.add_argument("--history", action="store_true", help="Show transition history")
    parser.add_argument("--reset", action="store_true", help="Reset to idle state")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    db = init_db()

    if args.status:
        result = get_current_state(db)
    elif args.transition:
        result = transition(db, args.transition)
    elif args.history:
        result = get_history(db)
    elif args.reset:
        result = reset_state(db)
    elif args.once:
        result = once(db)
    else:
        parser.print_help()
        return

    print(json.dumps(result, indent=2, default=str))
    db.close()


if __name__ == "__main__":
    main()
