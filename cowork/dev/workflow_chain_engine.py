#!/usr/bin/env python3
"""Workflow Chain Engine — Tasks chain together: one finishes, next triggers automatically.

Each step has: script, timeout, recovery_timer, next_step, collect_output.
On success: wait recovery_timer then trigger next.
On failure: retry once after recovery_timer, then skip to next with error logged.
Chains are sequential by design (output feeds input).

Usage:
    python workflow_chain_engine.py --once --chain social_publish_chain
    python workflow_chain_engine.py --list
    python workflow_chain_engine.py --status
    python workflow_chain_engine.py --add-chain NAME '[{"name":...}]'
"""
import argparse
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # cowork/
DB_PATH = BASE_DIR / "data" / "etoile.db"
SCRIPTS_DIR = BASE_DIR / "dev"

# ---------------------------------------------------------------------------
# Pre-defined chains
# ---------------------------------------------------------------------------
CHAINS: dict[str, list[dict]] = {
    "social_publish_chain": [
        {"name": "generate_content",   "script": "news_reactor.py --once",                "timeout": 60,  "recovery_timer": 5,  "collect_output": True},
        {"name": "publish_queue",      "script": "auto_publisher.py --once",               "timeout": 60,  "recovery_timer": 3,  "collect_output": True},
        {"name": "post_linkedin",      "script": "linkedin_content_generator.py --once",   "timeout": 90,  "recovery_timer": 10, "collect_output": True},
        {"name": "engage_feed",        "script": "interaction_bot.py --linkedin",           "timeout": 120, "recovery_timer": 5,  "collect_output": True},
        {"name": "check_responses",    "script": "notification_dispatcher.py --once",       "timeout": 60,  "recovery_timer": 0,  "collect_output": True},
    ],
    "multi_ia_research_chain": [
        {"name": "query_m1",           "script": "curl -s http://127.0.0.1:1234/api/v1/models", "timeout": 30, "recovery_timer": 3, "collect_output": True},
        {"name": "query_ol1_minimax",  "script": "curl -s http://127.0.0.1:11434/api/tags",     "timeout": 30, "recovery_timer": 3, "collect_output": True},
        {"name": "query_perplexity",   "script": "perplexity_dispatcher.py --once",              "timeout": 60, "recovery_timer": 10, "collect_output": True},
        {"name": "merge_results",      "script": "cluster_consensus.py --merge",                 "timeout": 45, "recovery_timer": 2,  "collect_output": True},
        {"name": "send_alert",         "script": "telegram_mcp_bridge.py --alert",               "timeout": 30, "recovery_timer": 0,  "collect_output": False},
    ],
    "morning_routine_chain": [
        {"name": "calendar_briefing",  "script": "calendar_sync.py --briefing",            "timeout": 30, "recovery_timer": 2, "collect_output": True},
        {"name": "email_check",        "script": "email_orchestrator.py --once",            "timeout": 45, "recovery_timer": 3, "collect_output": True},
        {"name": "notifications",      "script": "notification_dispatcher.py --once",       "timeout": 30, "recovery_timer": 2, "collect_output": True},
        {"name": "news_digest",        "script": "news_reactor.py --once",                  "timeout": 60, "recovery_timer": 5, "collect_output": True},
        {"name": "social_sweep",       "script": "social_automation_engine.py --once",      "timeout": 60, "recovery_timer": 3, "collect_output": True},
        {"name": "health_report",      "script": "daily_health_report.py --once",           "timeout": 30, "recovery_timer": 0, "collect_output": True},
    ],
    "codeur_prospect_chain": [
        {"name": "find_projects",      "script": "codeur_profile_manager.py --projects",    "timeout": 60,  "recovery_timer": 5,  "collect_output": True},
        {"name": "gen_proposals",      "script": "interaction_bot.py --propose",             "timeout": 90,  "recovery_timer": 10, "collect_output": True},
        {"name": "send_proposals",     "script": "auto_publisher.py --once",                 "timeout": 60,  "recovery_timer": 3,  "collect_output": True},
        {"name": "track_responses",    "script": "notification_dispatcher.py --once",        "timeout": 60,  "recovery_timer": 0,  "collect_output": True},
    ],
    "full_audit_chain": [
        {"name": "mcp_health",         "script": "mcp_health_monitor.py --once",            "timeout": 30, "recovery_timer": 2, "collect_output": True},
        {"name": "integrity_audit",    "script": "integrity_auditor.py --once",             "timeout": 60, "recovery_timer": 5, "collect_output": True},
        {"name": "security_audit",     "script": "security_auditor.py --once",              "timeout": 60, "recovery_timer": 5, "collect_output": True},
        {"name": "pattern_detect",     "script": "pattern_detector.py --once",              "timeout": 45, "recovery_timer": 2, "collect_output": True},
        {"name": "autonomy_score",     "script": "autonomy_scorer.py --once",               "timeout": 30, "recovery_timer": 2, "collect_output": True},
        {"name": "daily_report",       "script": "daily_health_report.py --once",           "timeout": 30, "recovery_timer": 0, "collect_output": True},
    ],
}

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _ensure_db() -> sqlite3.Connection:
    """Open DB and create tables if needed."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""CREATE TABLE IF NOT EXISTS workflow_chains (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        chain_name  TEXT NOT NULL,
        steps_json  TEXT NOT NULL,
        created_at  TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS workflow_runs (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        chain_name  TEXT NOT NULL,
        started_at  TEXT NOT NULL,
        finished_at TEXT,
        status      TEXT NOT NULL DEFAULT 'running',
        results_json TEXT,
        category    TEXT NOT NULL DEFAULT 'workflow_chains'
    )""")
    conn.commit()
    return conn


def _load_chains_from_db(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    """Load user-defined chains from DB, merged over built-ins."""
    chains = dict(CHAINS)
    rows = conn.execute("SELECT chain_name, steps_json FROM workflow_chains ORDER BY updated_at DESC").fetchall()
    for name, steps_json in rows:
        try:
            chains[name] = json.loads(steps_json)
        except json.JSONDecodeError:
            pass
    return chains


def _save_chain_to_db(conn: sqlite3.Connection, name: str, steps: list[dict]) -> None:
    """Upsert a chain definition."""
    existing = conn.execute("SELECT id FROM workflow_chains WHERE chain_name=?", (name,)).fetchone()
    js = json.dumps(steps, ensure_ascii=False)
    if existing:
        conn.execute("UPDATE workflow_chains SET steps_json=?, updated_at=datetime('now') WHERE id=?", (js, existing[0]))
    else:
        conn.execute("INSERT INTO workflow_chains (chain_name, steps_json) VALUES (?,?)", (name, js))
    conn.commit()


def _log_run(conn: sqlite3.Connection, chain_name: str, started: str, finished: str | None, status: str, results: list[dict]) -> None:
    conn.execute(
        "INSERT INTO workflow_runs (chain_name, started_at, finished_at, status, results_json, category) VALUES (?,?,?,?,?,?)",
        (chain_name, started, finished, status, json.dumps(results, ensure_ascii=False), "workflow_chains"),
    )
    conn.commit()

# ---------------------------------------------------------------------------
# Step execution
# ---------------------------------------------------------------------------

def _resolve_command(script: str) -> list[str]:
    """Turn a script string into a subprocess command list."""
    parts = script.split()
    if not parts:
        return []
    # If it starts with a known binary (curl, node, python), run directly
    if parts[0] in ("curl", "node", "python", "python3"):
        return parts
    # Otherwise treat as a Python script relative to SCRIPTS_DIR
    candidate = SCRIPTS_DIR / parts[0]
    if candidate.exists():
        return [sys.executable, str(candidate)] + parts[1:]
    # Fallback: try running as-is via shell
    return parts


def _run_step(step: dict, context_file: str | None) -> dict:
    """Execute a single step. Returns result dict."""
    name = step["name"]
    timeout = step.get("timeout", 60)
    collect = step.get("collect_output", True)
    cmd = _resolve_command(step["script"])
    if not cmd:
        return {"step": name, "status": "error", "error": "empty command", "output": None, "duration": 0}

    env = dict(os.environ)
    if context_file:
        env["CHAIN_CONTEXT_FILE"] = context_file

    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, env=env, cwd=str(SCRIPTS_DIR),
        )
        duration = round(time.monotonic() - t0, 2)
        stdout = proc.stdout.strip() if proc.stdout else ""
        stderr = proc.stderr.strip() if proc.stderr else ""
        ok = proc.returncode == 0

        # Try to parse stdout as JSON
        output_data = None
        if collect and stdout:
            try:
                output_data = json.loads(stdout)
            except json.JSONDecodeError:
                output_data = stdout[:2000]

        return {
            "step": name,
            "status": "ok" if ok else "failed",
            "returncode": proc.returncode,
            "output": output_data if collect else None,
            "stderr": stderr[:500] if stderr and not ok else None,
            "duration": duration,
        }
    except subprocess.TimeoutExpired:
        return {"step": name, "status": "timeout", "error": f"exceeded {timeout}s", "output": None, "duration": timeout}
    except FileNotFoundError as exc:
        return {"step": name, "status": "error", "error": str(exc), "output": None, "duration": round(time.monotonic() - t0, 2)}
    except Exception as exc:
        return {"step": name, "status": "error", "error": str(exc), "output": None, "duration": round(time.monotonic() - t0, 2)}


def run_chain(chain_name: str, steps: list[dict]) -> dict:
    """Run an entire chain sequentially. Returns summary JSON."""
    conn = _ensure_db()
    started = datetime.now(timezone.utc).isoformat()
    results: list[dict] = []
    context_file = None
    overall = "ok"

    for i, step in enumerate(steps):
        result = _run_step(step, context_file)
        # On failure: retry once after recovery_timer
        if result["status"] not in ("ok",):
            wait = step.get("recovery_timer", 3)
            if wait > 0:
                time.sleep(wait)
            retry = _run_step(step, context_file)
            retry["retry"] = True
            if retry["status"] == "ok":
                result = retry
            else:
                result["retry_failed"] = True
                overall = "partial"

        results.append(result)

        # Write output to temp file for next step
        if result.get("output") is not None:
            tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", prefix=f"chain_{chain_name}_step{i}_", delete=False, dir=tempfile.gettempdir())
            json.dump(result["output"], tmp, ensure_ascii=False)
            tmp.close()
            context_file = tmp.name
        # Wait recovery_timer before next step
        wait = step.get("recovery_timer", 0)
        if wait > 0 and result["status"] == "ok" and i < len(steps) - 1:
            time.sleep(wait)

    finished = datetime.now(timezone.utc).isoformat()
    _log_run(conn, chain_name, started, finished, overall, results)
    conn.close()

    # Cleanup temp files
    if context_file and os.path.exists(context_file):
        try:
            os.unlink(context_file)
        except OSError:
            pass

    return {"chain": chain_name, "status": overall, "started": started, "finished": finished, "steps": results}

# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def cmd_list(conn: sqlite3.Connection) -> None:
    chains = _load_chains_from_db(conn)
    out = []
    for name, steps in sorted(chains.items()):
        out.append({"chain": name, "steps": len(steps), "names": [s["name"] for s in steps]})
    print(json.dumps(out, indent=2, ensure_ascii=False))


def cmd_status(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        "SELECT chain_name, started_at, finished_at, status FROM workflow_runs ORDER BY id DESC LIMIT 20"
    ).fetchall()
    out = [{"chain": r[0], "started": r[1], "finished": r[2], "status": r[3]} for r in rows]
    print(json.dumps(out, indent=2, ensure_ascii=False))


def cmd_run_once(conn: sqlite3.Connection, chain_name: str) -> None:
    chains = _load_chains_from_db(conn)
    if chain_name not in chains:
        print(json.dumps({"error": f"chain '{chain_name}' not found", "available": sorted(chains.keys())}))
        sys.exit(1)
    result = run_chain(chain_name, chains[chain_name])
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_add_chain(conn: sqlite3.Connection, name: str, steps_json: str) -> None:
    try:
        steps = json.loads(steps_json)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"invalid JSON: {e}"}))
        sys.exit(1)
    if not isinstance(steps, list) or not steps:
        print(json.dumps({"error": "steps must be a non-empty JSON array"}))
        sys.exit(1)
    for i, s in enumerate(steps):
        if "name" not in s or "script" not in s:
            print(json.dumps({"error": f"step {i} missing 'name' or 'script'"}))
            sys.exit(1)
        s.setdefault("timeout", 60)
        s.setdefault("recovery_timer", 3)
        s.setdefault("collect_output", True)
    _save_chain_to_db(conn, name, steps)
    print(json.dumps({"ok": True, "chain": name, "steps": len(steps)}))


def main() -> None:
    parser = argparse.ArgumentParser(description="Workflow Chain Engine — sequential task chains with recovery")
    parser.add_argument("--once", action="store_true", help="Run chain once then exit")
    parser.add_argument("--chain", type=str, help="Chain name to run (with --once)")
    parser.add_argument("--list", action="store_true", help="List all defined chains")
    parser.add_argument("--status", action="store_true", help="Show recent chain runs")
    parser.add_argument("--add-chain", nargs=2, metavar=("NAME", "STEPS_JSON"), help="Add/update a chain definition")
    args = parser.parse_args()

    conn = _ensure_db()

    if args.list:
        cmd_list(conn)
    elif args.status:
        cmd_status(conn)
    elif args.add_chain:
        cmd_add_chain(conn, args.add_chain[0], args.add_chain[1])
    elif args.once:
        if not args.chain:
            parser.error("--once requires --chain NAME")
        cmd_run_once(conn, args.chain)
    else:
        parser.print_help()
        sys.exit(0)

    conn.close()


if __name__ == "__main__":
    main()
