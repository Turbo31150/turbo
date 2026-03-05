#!/usr/bin/env python3
"""cross_channel_sync.py — Synchronise les actions entre voix, Telegram et MCP.

Merge les logs de tous les canaux dans user_patterns (etoile.db)
pour alimenter le prediction_engine. Dedup automatique.

Usage:
    python dev/cross_channel_sync.py --once
    python dev/cross_channel_sync.py --sync
    python dev/cross_channel_sync.py --report
    python dev/cross_channel_sync.py --loop --interval 900
"""
import argparse
import json
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
ETOILE_DB = Path("F:/BUREAU/turbo/data/etoile.db")
JARVIS_DB = Path("F:/BUREAU/turbo/data/jarvis.db")
DB_PATH = DEV / "data" / "cross_channel.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS sync_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, voice_synced INTEGER, telegram_synced INTEGER,
        mcp_synced INTEGER, dedup_removed INTEGER, report TEXT)""")
    db.commit()
    return db


def ensure_user_patterns():
    """Ensure user_patterns table exists in etoile.db."""
    if not ETOILE_DB.exists():
        return False
    try:
        conn = sqlite3.connect(str(ETOILE_DB))
        conn.execute("""CREATE TABLE IF NOT EXISTS user_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            hour INTEGER,
            weekday INTEGER,
            context TEXT,
            timestamp REAL)""")
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def sync_voice_data():
    """Sync voice command executions into user_patterns."""
    if not JARVIS_DB.exists():
        return 0

    synced = 0
    try:
        jarvis = sqlite3.connect(str(JARVIS_DB))
        jarvis.row_factory = sqlite3.Row
        etoile = sqlite3.connect(str(ETOILE_DB))

        # Get successful voice commands
        rows = jarvis.execute("""
            SELECT corrected_text, confidence, timestamp
            FROM voice_corrections
            WHERE confidence >= 0.6 AND corrected_text IS NOT NULL
            ORDER BY timestamp DESC LIMIT 300
        """).fetchall()

        for row in rows:
            ts = row["timestamp"] if row["timestamp"] else 0
            if ts == 0:
                continue
            dt = datetime.fromtimestamp(ts)
            action = f"voice:{row['corrected_text']}"

            # Dedup check
            existing = etoile.execute(
                "SELECT COUNT(*) FROM user_patterns WHERE action=? AND ABS(timestamp-?)<30",
                (action, ts)
            ).fetchone()[0]

            if existing == 0:
                etoile.execute(
                    "INSERT INTO user_patterns (action, hour, weekday, context, timestamp) VALUES (?,?,?,?,?)",
                    (action, dt.hour, dt.weekday(),
                     json.dumps({"source": "voice", "confidence": row["confidence"]}), ts)
                )
                synced += 1

        etoile.commit()
        etoile.close()
        jarvis.close()
    except Exception as e:
        print(f"[WARN] sync_voice: {e}")
    return synced


def sync_telegram_data():
    """Sync Telegram interactions into user_patterns."""
    synced = 0
    try:
        etoile = sqlite3.connect(str(ETOILE_DB))

        # Check if telegram_log table exists
        has_table = etoile.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='telegram_log'"
        ).fetchone()[0]

        if has_table:
            rows = etoile.execute("""
                SELECT message, timestamp FROM telegram_log
                WHERE timestamp > ? ORDER BY timestamp DESC LIMIT 200
            """, (time.time() - 86400,)).fetchall()  # Last 24h

            for row in rows:
                ts = row[1] if row[1] else 0
                if ts == 0:
                    continue
                dt = datetime.fromtimestamp(ts)
                msg = row[0][:100] if row[0] else ""
                action = f"telegram:{msg}"

                existing = etoile.execute(
                    "SELECT COUNT(*) FROM user_patterns WHERE action=? AND ABS(timestamp-?)<30",
                    (action, ts)
                ).fetchone()[0]

                if existing == 0:
                    etoile.execute(
                        "INSERT INTO user_patterns (action, hour, weekday, context, timestamp) VALUES (?,?,?,?,?)",
                        (action, dt.hour, dt.weekday(),
                         json.dumps({"source": "telegram"}), ts)
                    )
                    synced += 1

        etoile.commit()
        etoile.close()
    except Exception as e:
        print(f"[WARN] sync_telegram: {e}")
    return synced


def sync_mcp_data():
    """Sync MCP tool usage into user_patterns."""
    synced = 0
    try:
        etoile = sqlite3.connect(str(ETOILE_DB))

        has_table = etoile.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='tool_metrics'"
        ).fetchone()[0]

        if has_table:
            rows = etoile.execute("""
                SELECT tool_name, COUNT(*) as cnt, MAX(timestamp) as last_ts
                FROM tool_metrics
                WHERE timestamp > ?
                GROUP BY tool_name
                HAVING cnt >= 2
                ORDER BY cnt DESC LIMIT 50
            """, (time.time() - 86400,)).fetchall()

            for row in rows:
                ts = row[2] if row[2] else time.time()
                dt = datetime.fromtimestamp(ts)
                action = f"mcp:{row[0]}"

                existing = etoile.execute(
                    "SELECT COUNT(*) FROM user_patterns WHERE action=? AND ABS(timestamp-?)<60",
                    (action, ts)
                ).fetchone()[0]

                if existing == 0:
                    etoile.execute(
                        "INSERT INTO user_patterns (action, hour, weekday, context, timestamp) VALUES (?,?,?,?,?)",
                        (action, dt.hour, dt.weekday(),
                         json.dumps({"source": "mcp", "count": row[1]}), ts)
                    )
                    synced += 1

        etoile.commit()
        etoile.close()
    except Exception as e:
        print(f"[WARN] sync_mcp: {e}")
    return synced


def dedup_patterns():
    """Remove duplicate patterns (same action within 30 seconds)."""
    removed = 0
    try:
        etoile = sqlite3.connect(str(ETOILE_DB))

        # Find duplicates: same action, timestamp within 30s
        dupes = etoile.execute("""
            SELECT p1.id FROM user_patterns p1
            INNER JOIN user_patterns p2
            ON p1.action = p2.action
            AND ABS(p1.timestamp - p2.timestamp) < 30
            AND p1.id > p2.id
            LIMIT 500
        """).fetchall()

        if dupes:
            ids = [d[0] for d in dupes]
            placeholders = ",".join("?" * len(ids))
            cursor = etoile.execute(
                f"DELETE FROM user_patterns WHERE id IN ({placeholders})", ids
            )
            removed = cursor.rowcount
            etoile.commit()

        etoile.close()
    except Exception as e:
        print(f"[WARN] dedup: {e}")
    return removed


def do_sync():
    """Full sync cycle: voice + telegram + mcp + dedup."""
    if not ensure_user_patterns():
        return {"error": "Cannot access etoile.db"}

    db = init_db()

    voice = sync_voice_data()
    telegram = sync_telegram_data()
    mcp = sync_mcp_data()
    deduped = dedup_patterns()

    # Count total patterns
    total = 0
    try:
        conn = sqlite3.connect(str(ETOILE_DB))
        total = conn.execute("SELECT COUNT(*) FROM user_patterns").fetchone()[0]
        conn.close()
    except Exception:
        pass

    report = {
        "ts": datetime.now().isoformat(),
        "voice_synced": voice,
        "telegram_synced": telegram,
        "mcp_synced": mcp,
        "total_synced": voice + telegram + mcp,
        "dedup_removed": deduped,
        "total_patterns": total,
    }

    db.execute(
        "INSERT INTO sync_runs (ts, voice_synced, telegram_synced, mcp_synced, dedup_removed, report) VALUES (?,?,?,?,?,?)",
        (time.time(), voice, telegram, mcp, deduped, json.dumps(report))
    )
    db.commit()
    db.close()
    return report


def get_report():
    """Get sync history."""
    db = init_db()
    rows = db.execute("SELECT * FROM sync_runs ORDER BY ts DESC LIMIT 20").fetchall()
    db.close()
    report = []
    for r in rows:
        report.append({
            "ts": datetime.fromtimestamp(r[1]).isoformat() if r[1] else None,
            "voice": r[2], "telegram": r[3], "mcp": r[4],
            "dedup": r[5],
        })
    return report


def main():
    parser = argparse.ArgumentParser(description="Cross-Channel Sync — Merge voice/telegram/mcp into predictions")
    parser.add_argument("--once", "--sync", action="store_true", help="Run sync cycle")
    parser.add_argument("--report", action="store_true", help="Sync history")
    parser.add_argument("--loop", action="store_true", help="Continuous sync")
    parser.add_argument("--interval", type=int, default=900, help="Loop interval (seconds)")
    args = parser.parse_args()

    if args.report:
        report = get_report()
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif args.loop:
        print(f"[CROSS_CHANNEL] Starting continuous sync (interval={args.interval}s)")
        while True:
            try:
                result = do_sync()
                total = result.get("total_synced", 0)
                print(f"[{result['ts']}] Synced: {total} (voice={result['voice_synced']}, tg={result['telegram_synced']}, mcp={result['mcp_synced']}) dedup={result['dedup_removed']}")
            except Exception as e:
                print(f"[ERROR] Sync failed: {e}")
            time.sleep(args.interval)
    else:
        result = do_sync()
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
