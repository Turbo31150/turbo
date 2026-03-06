#!/usr/bin/env python3
"""dispatch_realtime_monitor.py — Real-time dispatch monitoring with Telegram notifications.

Monitors agent_dispatch_log in etoile.db for anomalies and sends Telegram alerts
for critical events: consecutive failures, latency spikes, success rate drops,
and new pattern types.

CLI:
    --once       : check last 10 dispatches, report JSON summary + alerts
    --watch      : continuous monitoring every 30s
    --stats      : show monitoring event history grouped by type

Stdlib-only (sqlite3, json, argparse, urllib, time).
"""

import argparse
import json
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
DB_PATH = DATA_DIR / "cowork_gaps.db"
ETOILE_DB = Path(r"F:/BUREAU/turbo/etoile.db")

TELEGRAM_TOKEN = "8369376863:AAF-7YGDbun8mXWwqYJFj-eX6P78DeIu9Aw"
TELEGRAM_CHAT_ID = "2010747443"

# Thresholds
CONSECUTIVE_FAIL_THRESHOLD = 3
LATENCY_SPIKE_FACTOR = 2.0
SUCCESS_RATE_WINDOW = 20
SUCCESS_RATE_MIN = 0.60
WATCH_INTERVAL_S = 30


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def init_db(conn):
    """Create monitoring tables if they don't exist."""
    conn.execute("""CREATE TABLE IF NOT EXISTS monitor_state (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated TEXT NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS realtime_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        event_type TEXT NOT NULL,
        severity TEXT NOT NULL,
        details TEXT,
        notified INTEGER DEFAULT 0
    )""")
    conn.commit()


def get_db():
    """Open (or create) cowork_gaps.db with monitoring tables."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def get_state(conn, key, default=None):
    """Read a value from monitor_state."""
    row = conn.execute(
        "SELECT value FROM monitor_state WHERE key = ?", (key,)
    ).fetchone()
    return row["value"] if row else default


def set_state(conn, key, value):
    """Upsert a value into monitor_state."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO monitor_state (key, value, updated) VALUES (?, ?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated=excluded.updated",
        (key, str(value), now),
    )
    conn.commit()


def record_event(conn, event_type, severity, details, notified=0):
    """Insert a monitoring event."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO realtime_events (timestamp, event_type, severity, details, notified) "
        "VALUES (?, ?, ?, ?, ?)",
        (now, event_type, severity, json.dumps(details, ensure_ascii=False), notified),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------

def send_telegram(text, severity="warning"):
    """Send a message to Telegram. Returns True on success."""
    icon = {"critical": "\U0001f534", "warning": "\U0001f7e1", "info": "\U0001f7e2"}.get(severity, "\u26aa")
    msg = f"{icon} *Dispatch Monitor*\n{text}"

    data = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "Markdown",
    }).encode()

    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data
        )
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as exc:
        print(f"  [TG] send failed: {exc}", file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# Etoile DB readers
# ---------------------------------------------------------------------------

def open_etoile():
    """Open etoile.db read-only."""
    if not ETOILE_DB.exists():
        return None
    conn = sqlite3.connect(str(ETOILE_DB))
    conn.row_factory = sqlite3.Row
    return conn


def fetch_dispatches_since(edb, since_id):
    """Return dispatches with id > since_id, ordered ASC."""
    return edb.execute(
        "SELECT id, timestamp, request_text, classified_type, agent_id, model_used, "
        "node, strategy, latency_ms, tokens_in, tokens_out, success, error_msg, quality_score "
        "FROM agent_dispatch_log WHERE id > ? ORDER BY id ASC",
        (since_id,),
    ).fetchall()


def fetch_last_n(edb, n=10):
    """Return last n dispatches, ordered DESC (most recent first)."""
    return edb.execute(
        "SELECT id, timestamp, request_text, classified_type, agent_id, model_used, "
        "node, strategy, latency_ms, tokens_in, tokens_out, success, error_msg, quality_score "
        "FROM agent_dispatch_log ORDER BY id DESC LIMIT ?",
        (n,),
    ).fetchall()


def fetch_average_latency(edb, limit=100):
    """Return average latency_ms of last `limit` successful dispatches."""
    row = edb.execute(
        "SELECT AVG(latency_ms) as avg_lat FROM ("
        "  SELECT latency_ms FROM agent_dispatch_log "
        "  WHERE success = 1 AND latency_ms IS NOT NULL "
        "  ORDER BY id DESC LIMIT ?"
        ")",
        (limit,),
    ).fetchone()
    return row["avg_lat"] if row and row["avg_lat"] else 5000.0


def fetch_known_patterns(edb):
    """Return set of all classified_type values ever seen."""
    rows = edb.execute(
        "SELECT DISTINCT classified_type FROM agent_dispatch_log WHERE classified_type IS NOT NULL"
    ).fetchall()
    return {r["classified_type"] for r in rows}


# ---------------------------------------------------------------------------
# Analysis / alert logic
# ---------------------------------------------------------------------------

def analyze_dispatches(dispatches, avg_latency, known_patterns, db_conn):
    """Analyze a batch of dispatches and return list of alert dicts.

    Each alert: {"event_type": str, "severity": str, "details": dict}
    """
    alerts = []

    if not dispatches:
        return alerts

    # --- 1. Consecutive failures ---
    consecutive_fails = 0
    fail_nodes = []
    for d in dispatches:
        if not d["success"]:
            consecutive_fails += 1
            fail_nodes.append(d["node"] or "unknown")
        else:
            consecutive_fails = 0
            fail_nodes = []

    if consecutive_fails >= CONSECUTIVE_FAIL_THRESHOLD:
        alerts.append({
            "event_type": "consecutive_failures",
            "severity": "critical",
            "details": {
                "count": consecutive_fails,
                "nodes": fail_nodes[-CONSECUTIVE_FAIL_THRESHOLD:],
                "last_error": dispatches[-1]["error_msg"],
            },
        })

    # --- 2. Latency spikes (aggregated per node to avoid spam) ---
    threshold_ms = avg_latency * LATENCY_SPIKE_FACTOR
    spike_by_node = {}
    for d in dispatches:
        lat = d["latency_ms"]
        if lat and lat > threshold_ms:
            node = d["node"] or "unknown"
            if node not in spike_by_node:
                spike_by_node[node] = {"count": 0, "max_ms": 0, "model": d["model_used"]}
            spike_by_node[node]["count"] += 1
            if lat > spike_by_node[node]["max_ms"]:
                spike_by_node[node]["max_ms"] = lat

    for node, info in spike_by_node.items():
        alerts.append({
            "event_type": "latency_spike",
            "severity": "warning",
            "details": {
                "latency_ms": round(info["max_ms"], 1),
                "avg_latency_ms": round(avg_latency, 1),
                "factor": round(info["max_ms"] / avg_latency, 2),
                "node": node,
                "model": info["model"],
                "spike_count": info["count"],
            },
        })

    # --- 3. Success rate drop (rolling window) ---
    # Look at the most recent SUCCESS_RATE_WINDOW dispatches among the batch
    window = dispatches[-SUCCESS_RATE_WINDOW:] if len(dispatches) >= SUCCESS_RATE_WINDOW else dispatches
    if len(window) >= SUCCESS_RATE_WINDOW:
        successes = sum(1 for d in window if d["success"])
        rate = successes / len(window)
        if rate < SUCCESS_RATE_MIN:
            alerts.append({
                "event_type": "success_rate_drop",
                "severity": "critical",
                "details": {
                    "rate": round(rate * 100, 1),
                    "window": len(window),
                    "threshold_pct": round(SUCCESS_RATE_MIN * 100, 1),
                    "successes": successes,
                    "failures": len(window) - successes,
                },
            })

    # --- 4. New pattern types ---
    # Retrieve patterns we already notified about
    notified_raw = get_state(db_conn, "notified_patterns", "")
    notified_patterns = set(notified_raw.split(",")) if notified_raw else set()
    all_known = known_patterns | notified_patterns

    for d in dispatches:
        ptype = d["classified_type"]
        if ptype and ptype not in all_known:
            alerts.append({
                "event_type": "new_pattern",
                "severity": "info",
                "details": {
                    "pattern": ptype,
                    "dispatch_id": d["id"],
                    "node": d["node"],
                },
            })
            notified_patterns.add(ptype)

    # Persist notified patterns
    if notified_patterns:
        set_state(db_conn, "notified_patterns", ",".join(sorted(notified_patterns)))

    return alerts


ALERT_COOLDOWN_S = 600  # 10 minutes cooldown per event_type

def _should_send(event_type, db_conn):
    """Check if we should send this alert (cooldown check)."""
    key = f"last_alert_{event_type}"
    last_raw = get_state(db_conn, key, "0")
    try:
        last_ts = float(last_raw)
    except (ValueError, TypeError):
        last_ts = 0
    now = time.time()
    if now - last_ts < ALERT_COOLDOWN_S:
        return False
    set_state(db_conn, key, str(now))
    return True


def process_alerts(alerts, db_conn):
    """Record alerts in DB and send Telegram for critical/warning events."""
    sent_count = 0
    for a in alerts:
        severity = a["severity"]
        should_notify = severity in ("critical", "warning")

        # Cooldown: don't spam the same event type within 10 minutes
        if should_notify and not _should_send(a["event_type"], db_conn):
            record_event(db_conn, a["event_type"], severity, a["details"], 0)
            continue

        notified = 0
        if should_notify:
            details = a["details"]
            if a["event_type"] == "consecutive_failures":
                text = (
                    f"*{details['count']} consecutive failures*\n"
                    f"Nodes: {', '.join(details['nodes'])}\n"
                    f"Last error: `{details.get('last_error', 'N/A')}`"
                )
            elif a["event_type"] == "latency_spike":
                cnt = details.get("spike_count", 1)
                cnt_txt = f" ({cnt} spikes)" if cnt > 1 else ""
                text = (
                    f"*Latency spike* on `{details['node']}`{cnt_txt}\n"
                    f"Max {details['latency_ms']}ms (avg {details['avg_latency_ms']}ms, "
                    f"{details['factor']}x)\nModel: `{details.get('model', '?')}`"
                )
            elif a["event_type"] == "success_rate_drop":
                text = (
                    f"*Success rate drop*: {details['rate']}% "
                    f"(threshold {details['threshold_pct']}%)\n"
                    f"{details['successes']}/{details['window']} OK"
                )
            else:
                text = f"*{a['event_type']}*\n```{json.dumps(details, indent=2)}```"

            ok = send_telegram(text, severity)
            notified = 1 if ok else 0
            if ok:
                sent_count += 1

        record_event(db_conn, a["event_type"], severity, a["details"], notified)

    return sent_count


# ---------------------------------------------------------------------------
# CLI modes
# ---------------------------------------------------------------------------

def cmd_once():
    """--once: check last 10 dispatches, detect alerts, output JSON summary."""
    edb = open_etoile()
    if not edb:
        print(json.dumps({"error": "etoile.db not found"}))
        return 1

    db = get_db()

    last_10 = fetch_last_n(edb, 10)
    avg_lat = fetch_average_latency(edb)
    known = fetch_known_patterns(edb)

    # For analysis, reverse to ASC order
    dispatches = list(reversed(last_10))

    summary_rows = []
    for d in last_10:
        summary_rows.append({
            "id": d["id"],
            "timestamp": d["timestamp"],
            "type": d["classified_type"],
            "node": d["node"],
            "model": d["model_used"],
            "latency_ms": round(d["latency_ms"], 1) if d["latency_ms"] else None,
            "success": bool(d["success"]),
            "error": d["error_msg"],
        })

    alerts = analyze_dispatches(dispatches, avg_lat, known, db)
    sent = process_alerts(alerts, db)

    # Update last_seen_id
    if dispatches:
        set_state(db, "last_seen_id", dispatches[-1]["id"])

    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "last_10": summary_rows,
        "avg_latency_ms": round(avg_lat, 1),
        "known_patterns": sorted(known),
        "alerts": [{"event_type": a["event_type"], "severity": a["severity"],
                     "details": a["details"]} for a in alerts],
        "telegram_sent": sent,
    }

    edb.close()
    db.close()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def cmd_watch():
    """--watch: continuous monitoring every 30s."""
    print(f"[dispatch_realtime_monitor] watch mode — interval {WATCH_INTERVAL_S}s (Ctrl+C to stop)", flush=True)

    db = get_db()

    # Initialize last_seen_id if not set
    edb = open_etoile()
    if not edb:
        print("ERROR: etoile.db not found", file=sys.stderr)
        return 1

    last_id = int(get_state(db, "last_seen_id", "0"))
    if last_id == 0:
        # Start from current max to avoid alerting on old data
        row = edb.execute("SELECT MAX(id) as mx FROM agent_dispatch_log").fetchone()
        last_id = row["mx"] if row and row["mx"] else 0
        set_state(db, "last_seen_id", last_id)
        print(f"  Initialized last_seen_id = {last_id}", flush=True)
    edb.close()

    cycle = 0
    try:
        while True:
            cycle += 1
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")

            edb = open_etoile()
            if not edb:
                print(f"  [{now}] etoile.db unavailable, retrying...", flush=True)
                time.sleep(WATCH_INTERVAL_S)
                continue

            last_id = int(get_state(db, "last_seen_id", "0"))
            new_dispatches = fetch_dispatches_since(edb, last_id)
            avg_lat = fetch_average_latency(edb)
            known = fetch_known_patterns(edb)

            if new_dispatches:
                new_max_id = new_dispatches[-1]["id"]
                alerts = analyze_dispatches(new_dispatches, avg_lat, known, db)
                sent = process_alerts(alerts, db)
                set_state(db, "last_seen_id", new_max_id)

                print(
                    f"  [{now}] cycle={cycle} new={len(new_dispatches)} "
                    f"alerts={len(alerts)} tg_sent={sent} last_id={new_max_id}",
                    flush=True,
                )
            else:
                print(f"  [{now}] cycle={cycle} no new dispatches", flush=True)

            edb.close()
            time.sleep(WATCH_INTERVAL_S)

    except KeyboardInterrupt:
        print("\n[dispatch_realtime_monitor] stopped by user")
        db.close()
        return 0


def cmd_stats():
    """--stats: show event history grouped by type."""
    db = get_db()

    # Grouped counts
    rows = db.execute(
        "SELECT event_type, severity, COUNT(*) as cnt, "
        "SUM(notified) as tg_sent, "
        "MIN(timestamp) as first_seen, MAX(timestamp) as last_seen "
        "FROM realtime_events "
        "GROUP BY event_type, severity "
        "ORDER BY cnt DESC"
    ).fetchall()

    groups = []
    for r in rows:
        groups.append({
            "event_type": r["event_type"],
            "severity": r["severity"],
            "count": r["cnt"],
            "telegram_sent": r["tg_sent"],
            "first_seen": r["first_seen"],
            "last_seen": r["last_seen"],
        })

    # Total
    total_row = db.execute("SELECT COUNT(*) as c FROM realtime_events").fetchone()
    total = total_row["c"] if total_row else 0

    # Recent 20 events
    recent = db.execute(
        "SELECT id, timestamp, event_type, severity, details, notified "
        "FROM realtime_events ORDER BY id DESC LIMIT 20"
    ).fetchall()

    recent_list = []
    for r in recent:
        entry = {
            "id": r["id"],
            "timestamp": r["timestamp"],
            "event_type": r["event_type"],
            "severity": r["severity"],
            "notified": bool(r["notified"]),
        }
        try:
            entry["details"] = json.loads(r["details"])
        except (json.JSONDecodeError, TypeError):
            entry["details"] = r["details"]
        recent_list.append(entry)

    # Monitor state
    last_id = get_state(db, "last_seen_id", "0")
    notified_patterns = get_state(db, "notified_patterns", "")

    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_events": total,
        "by_type": groups,
        "recent_20": recent_list,
        "state": {
            "last_seen_id": int(last_id),
            "notified_patterns": notified_patterns.split(",") if notified_patterns else [],
        },
    }

    db.close()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Real-time dispatch monitoring with Telegram alerts"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--once", action="store_true", help="Check last 10 dispatches")
    group.add_argument("--watch", action="store_true", help="Continuous monitoring every 30s")
    group.add_argument("--stats", action="store_true", help="Show monitoring event history")

    args = parser.parse_args()

    if args.once:
        return cmd_once()
    elif args.watch:
        return cmd_watch()
    elif args.stats:
        return cmd_stats()
    return 1


if __name__ == "__main__":
    sys.exit(main())
