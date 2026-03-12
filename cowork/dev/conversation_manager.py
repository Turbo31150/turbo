#!/usr/bin/env python3
"""
JARVIS Conversation Manager
Standalone Python script for managing multi-turn conversations.
DB: dev/data/conversations.db
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List, Any
import uuid


# Configuration
DB_PATH = Path(__file__).parent / "data" / "conversations.db"


def init_db() -> None:
    """Initialize database with required tables."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Sessions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            ts_created TEXT NOT NULL,
            ts_updated TEXT NOT NULL,
            context TEXT NOT NULL,
            message_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active'
        )
    """)

    # Messages table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            ts TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            tokens_approx INTEGER DEFAULT 0,
            FOREIGN KEY(session_id) REFERENCES sessions(id)
        )
    """)

    conn.commit()
    conn.close()


def get_connection() -> sqlite3.Connection:
    """Get database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def estimate_tokens(text: str) -> int:
    """Rough token estimation (1 token ≈ 4 chars)."""
    return max(1, len(text) // 4)


def cmd_new(context: str) -> None:
    """Start a new conversation."""
    init_db()

    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO sessions (id, ts_created, ts_updated, context, message_count, status)
            VALUES (?, ?, ?, ?, 0, 'active')
        """, (session_id, now, now, context))
        conn.commit()

        result = {
            "status": "ok",
            "session_id": session_id,
            "context": context,
            "ts_created": now,
            "message_count": 0
        }
        print(json.dumps(result, indent=2))
    finally:
        conn.close()


def cmd_add(session_id: str, message: str, role: str = "user") -> None:
    """Add a message to conversation."""
    init_db()

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Verify session exists
        cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        session = cursor.fetchone()

        if not session:
            result = {"status": "error", "message": f"Session {session_id} not found"}
            print(json.dumps(result, indent=2))
            return

        # Insert message
        msg_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')
        tokens = estimate_tokens(message)

        cursor.execute("""
            INSERT INTO messages (id, session_id, ts, role, content, tokens_approx)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (msg_id, session_id, now, role, message, tokens))

        # Update session
        new_count = session["message_count"] + 1
        cursor.execute("""
            UPDATE sessions
            SET ts_updated = ?, message_count = ?
            WHERE id = ?
        """, (now, new_count, session_id))

        conn.commit()

        result = {
            "status": "ok",
            "message_id": msg_id,
            "session_id": session_id,
            "role": role,
            "ts": now,
            "tokens_approx": tokens,
            "message_count": new_count
        }
        print(json.dumps(result, indent=2))
    finally:
        conn.close()


def cmd_history(session_id: str) -> None:
    """Show conversation history."""
    init_db()

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Get session
        cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        session = cursor.fetchone()

        if not session:
            result = {"status": "error", "message": f"Session {session_id} not found"}
            print(json.dumps(result, indent=2))
            return

        # Get messages
        cursor.execute("""
            SELECT id, ts, role, content, tokens_approx
            FROM messages
            WHERE session_id = ?
            ORDER BY ts ASC
        """, (session_id,))

        messages = [dict(row) for row in cursor.fetchall()]

        result = {
            "status": "ok",
            "session_id": session_id,
            "context": session["context"],
            "status": session["status"],
            "ts_created": session["ts_created"],
            "ts_updated": session["ts_updated"],
            "message_count": session["message_count"],
            "messages": messages
        }
        print(json.dumps(result, indent=2))
    finally:
        conn.close()


def cmd_list() -> None:
    """List all conversations."""
    init_db()

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT id, ts_created, ts_updated, context, message_count, status
            FROM sessions
            ORDER BY ts_updated DESC
        """)

        sessions = [dict(row) for row in cursor.fetchall()]

        result = {
            "status": "ok",
            "total": len(sessions),
            "sessions": sessions
        }
        print(json.dumps(result, indent=2))
    finally:
        conn.close()


def cmd_search(keyword: str) -> None:
    """Search across conversations."""
    init_db()

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Search in sessions context
        cursor.execute("""
            SELECT id, ts_created, context, message_count, status
            FROM sessions
            WHERE context LIKE ? OR id LIKE ?
            ORDER BY ts_updated DESC
        """, (f"%{keyword}%", f"%{keyword}%"))

        session_matches = [dict(row) for row in cursor.fetchall()]

        # Search in messages content
        cursor.execute("""
            SELECT DISTINCT
                m.session_id,
                s.context,
                COUNT(m.id) as match_count
            FROM messages m
            JOIN sessions s ON m.session_id = s.id
            WHERE m.content LIKE ?
            GROUP BY m.session_id
            ORDER BY match_count DESC
        """, (f"%{keyword}%",))

        msg_matches = [dict(row) for row in cursor.fetchall()]

        result = {
            "status": "ok",
            "keyword": keyword,
            "session_matches": session_matches,
            "message_matches": msg_matches,
            "total_sessions": len(session_matches),
            "total_message_hits": len(msg_matches)
        }
        print(json.dumps(result, indent=2))
    finally:
        conn.close()


def cmd_export(session_id: str) -> None:
    """Export conversation as JSON."""
    init_db()

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Get session
        cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        session = cursor.fetchone()

        if not session:
            result = {"status": "error", "message": f"Session {session_id} not found"}
            print(json.dumps(result, indent=2))
            return

        # Get messages
        cursor.execute("""
            SELECT id, ts, role, content, tokens_approx
            FROM messages
            WHERE session_id = ?
            ORDER BY ts ASC
        """, (session_id,))

        messages = [dict(row) for row in cursor.fetchall()]

        export = {
            "version": "1.0",
            "session_id": session_id,
            "context": session["context"],
            "status": session["status"],
            "ts_created": session["ts_created"],
            "ts_updated": session["ts_updated"],
            "message_count": session["message_count"],
            "total_tokens": sum(m["tokens_approx"] for m in messages),
            "messages": messages
        }
        print(json.dumps(export, indent=2))
    finally:
        conn.close()


def cmd_stats() -> None:
    """Conversation statistics."""
    init_db()

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Session stats
        cursor.execute("""
            SELECT
                COUNT(*) as total_sessions,
                SUM(message_count) as total_messages,
                AVG(message_count) as avg_messages_per_session,
                MAX(message_count) as max_messages_in_session,
                SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active_sessions
            FROM sessions
        """)

        stats_row = cursor.fetchone()

        # Message stats
        cursor.execute("""
            SELECT
                COUNT(*) as total_message_records,
                SUM(tokens_approx) as total_tokens,
                AVG(tokens_approx) as avg_tokens_per_message,
                COUNT(DISTINCT session_id) as sessions_with_messages
            FROM messages
        """)

        msg_row = cursor.fetchone()

        # Role breakdown
        cursor.execute("""
            SELECT role, COUNT(*) as count, SUM(tokens_approx) as tokens
            FROM messages
            GROUP BY role
        """)

        roles = [dict(row) for row in cursor.fetchall()]

        result = {
            "status": "ok",
            "sessions": {
                "total": stats_row["total_sessions"] or 0,
                "active": stats_row["active_sessions"] or 0,
                "total_messages": stats_row["total_messages"] or 0,
                "avg_per_session": round(stats_row["avg_messages_per_session"] or 0, 2),
                "max_in_session": stats_row["max_messages_in_session"] or 0
            },
            "messages": {
                "total_records": msg_row["total_message_records"] or 0,
                "total_tokens": msg_row["total_tokens"] or 0,
                "avg_tokens_per_msg": round(msg_row["avg_tokens_per_message"] or 0, 2),
                "sessions_used": msg_row["sessions_with_messages"] or 0
            },
            "by_role": roles
        }
        print(json.dumps(result, indent=2))
    finally:
        conn.close()


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="JARVIS Conversation Manager - Multi-turn conversation storage and retrieval",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python conversation_manager.py --new "debugging api authentication"
  python conversation_manager.py --add <SESSION_ID> "what is the error?"
  python conversation_manager.py --history <SESSION_ID>
  python conversation_manager.py --list
  python conversation_manager.py --search "authentication"
  python conversation_manager.py --export <SESSION_ID>
  python conversation_manager.py --stats

Database location: dev/data/conversations.db
        """
    )

    parser.add_argument("--new", type=str, help="Start new conversation with context")
    parser.add_argument("--add", nargs=2, metavar=("SESSION_ID", "MESSAGE"), help="Add message to conversation")
    parser.add_argument("--history", type=str, metavar="SESSION_ID", help="Show conversation history")
    parser.add_argument("--list", action="store_true", help="List all conversations")
    parser.add_argument("--search", type=str, help="Search across conversations")
    parser.add_argument("--export", type=str, metavar="SESSION_ID", help="Export conversation as JSON")
    parser.add_argument("--stats", action="store_true", help="Show conversation statistics")

    args = parser.parse_args()

    # Ensure at least one command is specified
    if not any([args.new, args.add, args.history, args.list, args.search, args.export, args.stats]):
        parser.print_help()
        sys.exit(1)

    try:
        if args.new:
            cmd_new(args.new)
        elif args.add:
            cmd_add(args.add[0], args.add[1])
        elif args.history:
            cmd_history(args.history)
        elif args.list:
            cmd_list()
        elif args.search:
            cmd_search(args.search)
        elif args.export:
            cmd_export(args.export)
        elif args.stats:
            cmd_stats()
    except Exception as e:
        error_result = {
            "status": "error",
            "message": str(e),
            "type": type(e).__name__
        }
        print(json.dumps(error_result, indent=2), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
