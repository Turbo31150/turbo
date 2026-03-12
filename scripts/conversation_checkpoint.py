#!/usr/bin/env python3
"""conversation_checkpoint.py — Persistent conversation context for JARVIS.

Solves the #1 context loss problem: when Windows reboots, watchdog kills
services, or Claude/Gemini sessions expire, ALL in-memory conversation
state is lost. This script provides:

1. Checkpoint: Save current conversation context to SQLite
2. Restore: Reload last context on service restart
3. Summarize: Compress old conversations via M1/OL1
4. Inject: Generate context prompt from recent history

The checkpoint table stores turn-by-turn exchanges with timestamps,
token estimates, and session IDs. On restart, the last N turns are
injected as system context to maintain continuity.

Usage:
    python scripts/conversation_checkpoint.py --save --session S1 --role user --content "msg"
    python scripts/conversation_checkpoint.py --restore --session S1 --limit 20
    python scripts/conversation_checkpoint.py --inject --session S1
    python scripts/conversation_checkpoint.py --summarize --session S1
    python scripts/conversation_checkpoint.py --status
    python scripts/conversation_checkpoint.py --gc --days 7

Stdlib-only (sqlite3, json, time, argparse).
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

TURBO_DIR = Path("/home/turbo/jarvis-m1-ops")
DB_PATH = TURBO_DIR / "data" / "conversation_checkpoints.db"

# Limits
MAX_TURNS_PER_SESSION = 200      # Keep last 200 turns per session
MAX_CONTEXT_TOKENS = 4000        # Max tokens in injected context
SUMMARY_THRESHOLD = 50           # Summarize after 50 turns
TOKEN_ESTIMATE_RATIO = 4         # ~4 chars per token


def get_db() -> sqlite3.Connection:
    """Open/create the checkpoint database."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=15000")
    conn.row_factory = sqlite3.Row

    conn.execute("""CREATE TABLE IF NOT EXISTS checkpoints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        turn_index INTEGER NOT NULL,
        timestamp TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        token_estimate INTEGER DEFAULT 0,
        source TEXT DEFAULT 'manual',
        metadata TEXT
    )""")
    conn.execute("""CREATE INDEX IF NOT EXISTS idx_cp_session
        ON checkpoints(session_id, turn_index)""")

    conn.execute("""CREATE TABLE IF NOT EXISTS summaries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        turn_range TEXT NOT NULL,
        summary TEXT NOT NULL,
        token_estimate INTEGER DEFAULT 0
    )""")

    conn.execute("""CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        last_active TEXT NOT NULL,
        turn_count INTEGER DEFAULT 0,
        total_tokens INTEGER DEFAULT 0,
        source TEXT DEFAULT 'unknown',
        metadata TEXT
    )""")

    conn.commit()
    return conn


def save_turn(conn: sqlite3.Connection, session_id: str, role: str,
              content: str, source: str = "manual", metadata: dict | None = None) -> int:
    """Save a single conversation turn."""
    now = datetime.now().isoformat()
    token_est = len(content) // TOKEN_ESTIMATE_RATIO

    # Get next turn index
    row = conn.execute(
        "SELECT MAX(turn_index) FROM checkpoints WHERE session_id=?",
        (session_id,)
    ).fetchone()
    turn_idx = (row[0] or 0) + 1

    conn.execute(
        "INSERT INTO checkpoints (session_id, turn_index, timestamp, role, content, "
        "token_estimate, source, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (session_id, turn_idx, now, role, content[:10000], token_est, source,
         json.dumps(metadata) if metadata else None)
    )

    # Update or create session record
    conn.execute("""
        INSERT INTO sessions (session_id, created_at, last_active, turn_count, total_tokens, source)
        VALUES (?, ?, ?, 1, ?, ?)
        ON CONFLICT(session_id) DO UPDATE SET
            last_active=excluded.last_active,
            turn_count=turn_count+1,
            total_tokens=total_tokens+excluded.total_tokens
    """, (session_id, now, now, token_est, source))

    # Prune old turns if over limit
    count = conn.execute(
        "SELECT COUNT(*) FROM checkpoints WHERE session_id=?", (session_id,)
    ).fetchone()[0]
    if count > MAX_TURNS_PER_SESSION:
        cutoff = count - MAX_TURNS_PER_SESSION
        conn.execute(
            "DELETE FROM checkpoints WHERE session_id=? AND turn_index <= "
            "(SELECT turn_index FROM checkpoints WHERE session_id=? "
            "ORDER BY turn_index LIMIT 1 OFFSET ?)",
            (session_id, session_id, cutoff - 1)
        )

    conn.commit()
    return turn_idx


def restore_turns(conn: sqlite3.Connection, session_id: str,
                  limit: int = 20) -> list[dict]:
    """Restore the last N turns for a session."""
    rows = conn.execute(
        "SELECT turn_index, timestamp, role, content, token_estimate, source "
        "FROM checkpoints WHERE session_id=? ORDER BY turn_index DESC LIMIT ?",
        (session_id, limit)
    ).fetchall()

    turns = []
    for r in reversed(rows):  # Chronological order
        turns.append({
            "turn": r["turn_index"],
            "ts": r["timestamp"],
            "role": r["role"],
            "content": r["content"],
            "tokens": r["token_estimate"],
            "source": r["source"],
        })
    return turns


def generate_context_prompt(conn: sqlite3.Connection, session_id: str,
                            max_tokens: int = MAX_CONTEXT_TOKENS) -> str:
    """Generate a context injection prompt from recent conversation history.

    Returns a formatted string that can be prepended to a new conversation
    to maintain continuity after a restart.
    """
    # First check for summaries
    summary_row = conn.execute(
        "SELECT summary FROM summaries WHERE session_id=? ORDER BY id DESC LIMIT 1",
        (session_id,)
    ).fetchone()

    # Get recent turns
    turns = restore_turns(conn, session_id, limit=50)

    # Build context within token budget
    parts = []
    tokens_used = 0

    if summary_row:
        summary = summary_row["summary"]
        summary_tokens = len(summary) // TOKEN_ESTIMATE_RATIO
        if summary_tokens < max_tokens // 2:
            parts.append(f"[Resume de la conversation precedente]\n{summary}")
            tokens_used += summary_tokens

    parts.append("\n[Derniers echanges]")
    for turn in turns:
        turn_tokens = turn["tokens"]
        if tokens_used + turn_tokens > max_tokens:
            break
        prefix = "User" if turn["role"] == "user" else "JARVIS"
        # Truncate very long messages
        content = turn["content"]
        if len(content) > 500:
            content = content[:500] + "..."
        parts.append(f"{prefix}: {content}")
        tokens_used += turn_tokens

    context = "\n".join(parts)
    return context


def summarize_session(conn: sqlite3.Connection, session_id: str) -> str | None:
    """Summarize older turns using local M1 (qwen3-8b).

    Returns summary text or None if M1 is unavailable.
    """
    import urllib.request

    turns = restore_turns(conn, session_id, limit=SUMMARY_THRESHOLD)
    if len(turns) < 10:
        return None

    # Build conversation text for summarization
    convo_text = "\n".join(
        f"{'User' if t['role'] == 'user' else 'JARVIS'}: {t['content'][:200]}"
        for t in turns[:30]
    )

    prompt = (
        "/nothink\n"
        "Resume cette conversation en 3-5 points cles. "
        "Garde les faits importants, decisions, et contexte technique. "
        "Format: liste a puces.\n\n"
        f"{convo_text}"
    )

    try:
        payload = json.dumps({
            "model": "qwen3-8b",
            "input": prompt,
            "temperature": 0.2,
            "max_output_tokens": 512,
            "stream": False,
            "store": False,
        }).encode()

        req = urllib.request.Request(
            "http://127.0.0.1:1234/api/v1/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())

        # Extract message content (skip reasoning blocks)
        summary = ""
        for block in reversed(data.get("output", [])):
            if block.get("type") == "message":
                for c in block.get("content", []):
                    if c.get("type") == "output_text":
                        summary = c.get("text", "")
                        break
                if summary:
                    break

        if summary:
            now = datetime.now().isoformat()
            first_turn = turns[0]["turn"]
            last_turn = turns[-1]["turn"]
            conn.execute(
                "INSERT INTO summaries (session_id, timestamp, turn_range, summary, token_estimate) "
                "VALUES (?, ?, ?, ?, ?)",
                (session_id, now, f"{first_turn}-{last_turn}",
                 summary[:2000], len(summary) // TOKEN_ESTIMATE_RATIO)
            )
            conn.commit()
            return summary
    except Exception as e:
        print(f"  Summarization failed (M1 unavailable?): {e}")
    return None


def gc_old_sessions(conn: sqlite3.Connection, days: int = 7) -> int:
    """Delete checkpoints older than N days."""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    cursor = conn.execute(
        "DELETE FROM checkpoints WHERE timestamp < ?", (cutoff,)
    )
    deleted = cursor.rowcount
    conn.execute(
        "DELETE FROM sessions WHERE last_active < ?", (cutoff,)
    )
    conn.execute(
        "DELETE FROM summaries WHERE timestamp < ?", (cutoff,)
    )
    conn.commit()
    return deleted


def print_status(conn: sqlite3.Connection):
    """Show checkpoint database status."""
    sessions = conn.execute(
        "SELECT session_id, turn_count, total_tokens, last_active, source "
        "FROM sessions ORDER BY last_active DESC LIMIT 20"
    ).fetchall()

    total_turns = conn.execute("SELECT COUNT(*) FROM checkpoints").fetchone()[0]
    total_summaries = conn.execute("SELECT COUNT(*) FROM summaries").fetchone()[0]

    print(f"\n  Conversation Checkpoint Status")
    print(f"  {'='*50}")
    print(f"  Total turns:     {total_turns}")
    print(f"  Total summaries: {total_summaries}")
    print(f"  Active sessions: {len(sessions)}")
    print(f"  DB size:         {DB_PATH.stat().st_size / 1024:.1f} KB" if DB_PATH.exists() else "")

    if sessions:
        print(f"\n  {'Session':<20} {'Turns':>6} {'Tokens':>8} {'Last Active':>20} {'Source':<10}")
        print(f"  {'-'*70}")
        for s in sessions:
            print(f"  {s['session_id']:<20} {s['turn_count']:>6} {s['total_tokens']:>8} "
                  f"{s['last_active'][:19]:>20} {s['source']:<10}")


def main():
    parser = argparse.ArgumentParser(description="Conversation Checkpoint — persist context across restarts")
    parser.add_argument("--save", action="store_true", help="Save a conversation turn")
    parser.add_argument("--restore", action="store_true", help="Restore recent turns")
    parser.add_argument("--inject", action="store_true", help="Generate context injection prompt")
    parser.add_argument("--summarize", action="store_true", help="Summarize session via M1")
    parser.add_argument("--status", action="store_true", help="Show database status")
    parser.add_argument("--gc", action="store_true", help="Delete old checkpoints")

    parser.add_argument("--session", type=str, default="default", help="Session ID")
    parser.add_argument("--role", type=str, default="user", help="Turn role (user/assistant)")
    parser.add_argument("--content", type=str, default="", help="Turn content")
    parser.add_argument("--source", type=str, default="manual", help="Source (telegram/ws/cli)")
    parser.add_argument("--limit", type=int, default=20, help="Number of turns to restore")
    parser.add_argument("--days", type=int, default=7, help="GC age threshold in days")
    parser.add_argument("--json", action="store_true", help="JSON output")

    args = parser.parse_args()

    if not any([args.save, args.restore, args.inject, args.summarize, args.status, args.gc]):
        parser.print_help()
        sys.exit(1)

    conn = get_db()

    if args.status:
        print_status(conn)
        conn.close()
        return

    if args.save:
        if not args.content:
            print("  Error: --content required for --save")
            sys.exit(1)
        turn_idx = save_turn(conn, args.session, args.role, args.content, args.source)
        if args.json:
            print(json.dumps({"session": args.session, "turn": turn_idx}))
        else:
            print(f"  Saved turn #{turn_idx} to session '{args.session}'")
        conn.close()
        return

    if args.restore:
        turns = restore_turns(conn, args.session, args.limit)
        if args.json:
            print(json.dumps(turns, indent=2))
        else:
            for t in turns:
                prefix = "User" if t["role"] == "user" else "JARVIS"
                content = t["content"][:100] + "..." if len(t["content"]) > 100 else t["content"]
                print(f"  [{t['ts'][:19]}] {prefix}: {content}")
        conn.close()
        return

    if args.inject:
        context = generate_context_prompt(conn, args.session)
        if args.json:
            print(json.dumps({"session": args.session, "context": context,
                              "tokens": len(context) // TOKEN_ESTIMATE_RATIO}))
        else:
            print(context)
        conn.close()
        return

    if args.summarize:
        summary = summarize_session(conn, args.session)
        if summary:
            print(f"  Summary saved for session '{args.session}':")
            print(f"  {summary[:300]}")
        else:
            print(f"  No summary generated (not enough turns or M1 unavailable)")
        conn.close()
        return

    if args.gc:
        deleted = gc_old_sessions(conn, args.days)
        print(f"  Deleted {deleted} checkpoints older than {args.days} days")
        conn.close()
        return


if __name__ == "__main__":
    main()
