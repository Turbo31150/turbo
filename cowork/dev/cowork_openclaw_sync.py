#!/usr/bin/env python3
"""cowork_openclaw_sync.py — Bidirectional bridge between Cowork system and OpenClaw Gateway.

Pushes cowork execution results and workflow chain results to OpenClaw for dispatching,
pulls completed OpenClaw task results and agent statuses back into etoile.db.

CLI:
    python cowork_openclaw_sync.py --once      # Full sync cycle (push + pull)
    python cowork_openclaw_sync.py --push      # Push cowork results to OpenClaw
    python cowork_openclaw_sync.py --pull      # Pull OpenClaw results to cowork
    python cowork_openclaw_sync.py --status    # Check sync status

Stdlib-only. All HTTP via urllib.request. Logs to etoile.db memories (category='openclaw_sync').
"""

import argparse
import json
import sqlite3
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from _paths import ETOILE_DB

OPENCLAW_BASE = "http://127.0.0.1:18789"
SYNC_CATEGORY = "openclaw_sync"
SCRIPT_NAME = "cowork_openclaw_sync.py"

# Prefix → OpenClaw agent mapping for auto-assign
AGENT_MAP = {
    "win_": "win-monitor",
    "jarvis_": "jarvis-core",
    "ia_": "ia-engine",
    "cluster_": "cluster-manager",
    "trading_": "trading-agent",
    "browser": "browser-agent",
    "telegram_": "telegram-bot",
    "email_": "email-agent",
    "workspace_": "workspace-agent",
    "domino_": "domino-executor",
}


def get_conn():
    conn = sqlite3.connect(str(ETOILE_DB), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def ensure_sync_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS openclaw_sync_queue (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        direction   TEXT NOT NULL,
        payload     TEXT NOT NULL,
        status      TEXT NOT NULL DEFAULT 'pending',
        agent       TEXT,
        created_at  TEXT NOT NULL DEFAULT (datetime('now')),
        synced_at   TEXT,
        error       TEXT
    )""")
    conn.commit()


def http_json(url, data=None, method="GET", timeout=10):
    """HTTP request returning parsed JSON or None on failure."""
    try:
        if data is not None:
            body = json.dumps(data).encode()
            req = urllib.request.Request(url, data=body, method=method,
                                         headers={"Content-Type": "application/json"})
        else:
            req = urllib.request.Request(url, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def log_memory(conn, key, value):
    """Insert a log entry into memories table."""
    try:
        conn.execute(
            "INSERT INTO memories (category, key, value, source, confidence) VALUES (?,?,?,?,?)",
            (SYNC_CATEGORY, key, json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value,
             SCRIPT_NAME, 0.9))
        conn.commit()
    except Exception:
        pass


def resolve_agent(script_name):
    """Map script prefix to OpenClaw agent name."""
    for prefix, agent in AGENT_MAP.items():
        if script_name.startswith(prefix):
            return agent
    return "general-agent"


# ── PUSH: cowork → OpenClaw ──────────────────────────────────────────

def fetch_execution_log(conn, limit=50):
    try:
        return conn.execute(
            "SELECT id, script, args, exit_code, duration_ms, success, stdout_preview "
            "FROM cowork_execution_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    except Exception:
        return []


def fetch_workflow_runs(conn, limit=20):
    try:
        return conn.execute(
            "SELECT id, chain_name, started_at, finished_at, status, results_json "
            "FROM workflow_runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    except Exception:
        return []


def push_to_openclaw(conn):
    """Push cowork results to OpenClaw or queue if offline."""
    ensure_sync_table(conn)
    pushed, queued, errors = 0, 0, 0

    # 1. Execution log entries
    rows = fetch_execution_log(conn)
    for r in rows:
        already = conn.execute(
            "SELECT 1 FROM openclaw_sync_queue WHERE direction='push' AND status IN ('pushed','pending') "
            "AND json_extract(payload,'$.source_id')=? AND json_extract(payload,'$.source_type')='execution_log'",
            (r["id"],)).fetchone()
        if already:
            continue
        agent = resolve_agent(r["script"] or "")
        task = {"source_type": "execution_log", "source_id": r["id"],
                "script": r["script"], "args": r["args"], "exit_code": r["exit_code"],
                "duration_ms": r["duration_ms"], "success": bool(r["success"]),
                "preview": (r["stdout_preview"] or "")[:200], "assigned_agent": agent}
        resp = http_json(f"{OPENCLAW_BASE}/api/dispatch", data={"task": task, "agent": agent})
        if resp:
            conn.execute(
                "INSERT INTO openclaw_sync_queue (direction, payload, status, agent, synced_at) VALUES (?,?,?,?,datetime('now'))",
                ("push", json.dumps(task), "pushed", agent))
            pushed += 1
        else:
            conn.execute(
                "INSERT INTO openclaw_sync_queue (direction, payload, status, agent) VALUES (?,?,?,?)",
                ("push", json.dumps(task), "pending", agent))
            queued += 1

    # 2. Workflow run entries
    wf_rows = fetch_workflow_runs(conn)
    for r in wf_rows:
        already = conn.execute(
            "SELECT 1 FROM openclaw_sync_queue WHERE direction='push' AND status IN ('pushed','pending') "
            "AND json_extract(payload,'$.source_id')=? AND json_extract(payload,'$.source_type')='workflow_run'",
            (r["id"],)).fetchone()
        if already:
            continue
        task = {"source_type": "workflow_run", "source_id": r["id"],
                "chain_name": r["chain_name"], "started_at": r["started_at"],
                "finished_at": r["finished_at"], "status": r["status"],
                "assigned_agent": "workflow-agent"}
        resp = http_json(f"{OPENCLAW_BASE}/api/dispatch", data={"task": task, "agent": "workflow-agent"})
        status = "pushed" if resp else "pending"
        conn.execute(
            "INSERT INTO openclaw_sync_queue (direction, payload, status, agent, synced_at) VALUES (?,?,?,?,?)",
            ("push", json.dumps(task), status, "workflow-agent",
             datetime.utcnow().isoformat() if resp else None))
        if resp:
            pushed += 1
        else:
            queued += 1

    conn.commit()
    result = {"pushed": pushed, "queued": queued, "errors": errors, "ts": datetime.utcnow().isoformat() + "Z"}
    log_memory(conn, f"push_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}", result)
    return result


# ── PULL: OpenClaw → cowork ──────────────────────────────────────────

def pull_from_openclaw(conn):
    """Pull completed tasks and agent statuses from OpenClaw into etoile.db."""
    ensure_sync_table(conn)
    pulled, errors = 0, 0

    # 1. Completed tasks via /api/status
    status_data = http_json(f"{OPENCLAW_BASE}/api/status")
    if status_data:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        conn.execute(
            "INSERT INTO openclaw_sync_queue (direction, payload, status, synced_at) VALUES (?,?,?,datetime('now'))",
            ("pull", json.dumps(status_data), "pulled"))
        log_memory(conn, f"pull_status_{ts}", status_data)
        pulled += 1
    else:
        errors += 1

    # 2. Agent statuses via /api/agents
    agents_data = http_json(f"{OPENCLAW_BASE}/api/agents")
    if agents_data:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        conn.execute(
            "INSERT INTO openclaw_sync_queue (direction, payload, status, agent, synced_at) VALUES (?,?,?,?,datetime('now'))",
            ("pull", json.dumps(agents_data), "pulled", "all_agents"))
        log_memory(conn, f"pull_agents_{ts}", agents_data)
        pulled += 1
    else:
        errors += 1

    conn.commit()
    result = {"pulled": pulled, "errors": errors, "openclaw_online": status_data is not None,
              "ts": datetime.utcnow().isoformat() + "Z"}
    log_memory(conn, f"pull_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}", result)
    return result


# ── STATUS ────────────────────────────────────────────────────────────

def sync_status(conn):
    """Return sync queue statistics and agent utilization."""
    ensure_sync_table(conn)
    counts = {}
    for s in ("pending", "pushed", "pulled", "failed"):
        row = conn.execute("SELECT COUNT(*) FROM openclaw_sync_queue WHERE status=?", (s,)).fetchone()
        counts[s] = row[0] if row else 0

    pending_push = conn.execute(
        "SELECT COUNT(*) FROM openclaw_sync_queue WHERE direction='push' AND status='pending'").fetchone()[0]
    counts["pending_push"] = pending_push

    last_sync = conn.execute(
        "SELECT MAX(synced_at) FROM openclaw_sync_queue WHERE synced_at IS NOT NULL").fetchone()
    counts["last_sync"] = last_sync[0] if last_sync and last_sync[0] else None

    # Agent utilization from latest pull
    agents_data = http_json(f"{OPENCLAW_BASE}/api/agents")
    utilization = {}
    if agents_data and isinstance(agents_data, (list, dict)):
        agents_list = agents_data if isinstance(agents_data, list) else agents_data.get("agents", [])
        for a in agents_list:
            name = a.get("name", a.get("id", "unknown"))
            utilization[name] = a.get("status", "unknown")

    return {"counts": counts, "agent_utilization": utilization,
            "openclaw_online": agents_data is not None,
            "ts": datetime.utcnow().isoformat() + "Z"}


# ── MAIN ──────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Cowork <-> OpenClaw bidirectional sync bridge")
    ap.add_argument("--once", action="store_true", help="Full sync cycle (push + pull)")
    ap.add_argument("--push", action="store_true", help="Push cowork results to OpenClaw")
    ap.add_argument("--pull", action="store_true", help="Pull OpenClaw results to cowork")
    ap.add_argument("--status", action="store_true", help="Check sync status")
    args = ap.parse_args()

    if not any([args.once, args.push, args.pull, args.status]):
        ap.print_help()
        sys.exit(1)

    conn = get_conn()
    try:
        if args.once:
            push_res = push_to_openclaw(conn)
            pull_res = pull_from_openclaw(conn)
            result = {"action": "full_sync", "push": push_res, "pull": pull_res}
        elif args.push:
            result = {"action": "push", **push_to_openclaw(conn)}
        elif args.pull:
            result = {"action": "pull", **pull_from_openclaw(conn)}
        elif args.status:
            result = {"action": "status", **sync_status(conn)}
        else:
            result = {"error": "no action specified"}

        print(json.dumps(result, indent=2, ensure_ascii=False))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
