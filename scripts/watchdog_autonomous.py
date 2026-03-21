#!/usr/bin/env python3
"""JARVIS Watchdog Autonomous — Cycle autonome periodique avec suivi grade/health.

Appelle POST /api/autonomous/cycle toutes les 5 minutes, enregistre le grade
dans SQLite, declenche self-improve si grade < B, et alerte Telegram si < C.

Usage:
    python scripts/watchdog_autonomous.py --once       # Un seul cycle
    python scripts/watchdog_autonomous.py --daemon      # Boucle infinie (5min)
    python scripts/watchdog_autonomous.py --status      # Derniers cycles DB
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.process_singleton import ProcessSingleton

# ── Constants ─────────────────────────────────────────────────────────
SERVICE_NAME = "watchdog_autonomous"
WS_BASE = "http://127.0.0.1:9742"
CYCLE_URL = f"{WS_BASE}/api/autonomous/cycle"
SELF_IMPROVE_URL = f"{WS_BASE}/api/self-improve/run"
TELEGRAM_URL = f"{WS_BASE}/api/telegram/send"
INTERVAL_S = 300  # 5 minutes
HTTP_TIMEOUT = 120  # autonomous cycle can be slow

LOG_DIR = ROOT / "logs"
LOG_FILE = LOG_DIR / "watchdog_autonomous.log"
DB_PATH = ROOT / "data" / "watchdog.db"

# Grade ordering for comparisons
GRADE_ORDER = {"A+": 5, "A": 4, "B": 3, "C": 2, "F": 1}

_running = True


def _signal_handler(sig, frame):
    global _running
    _running = False


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)

# ── Logging ───────────────────────────────────────────────────────────

LOG_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("jarvis.watchdog_autonomous")
logger.setLevel(logging.DEBUG)

_fmt = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

_fh = logging.FileHandler(str(LOG_FILE), encoding="utf-8")
_fh.setLevel(logging.DEBUG)
_fh.setFormatter(_fmt)
logger.addHandler(_fh)

_sh = logging.StreamHandler(sys.stdout)
_sh.setLevel(logging.INFO)
_sh.setFormatter(_fmt)
logger.addHandler(_sh)


# ── Database ──────────────────────────────────────────────────────────

def init_db() -> None:
    """Create the watchdog.db and cycles table if they don't exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB_PATH))
    con.execute("""CREATE TABLE IF NOT EXISTS cycles (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        ts              TEXT    NOT NULL,
        grade           TEXT    NOT NULL,
        health_score    REAL    NOT NULL DEFAULT 0,
        issues_count    INTEGER NOT NULL DEFAULT 0,
        decisions_count INTEGER NOT NULL DEFAULT 0,
        fix_applied     INTEGER NOT NULL DEFAULT 0
    )""")
    con.commit()
    con.close()
    logger.debug("DB initialized: %s", DB_PATH)


def save_cycle(ts: str, grade: str, health_score: float,
               issues_count: int, decisions_count: int, fix_applied: int) -> None:
    """Insert one cycle row into the database."""
    try:
        con = sqlite3.connect(str(DB_PATH))
        con.execute(
            "INSERT INTO cycles (ts, grade, health_score, issues_count, decisions_count, fix_applied) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ts, grade, health_score, issues_count, decisions_count, fix_applied),
        )
        con.commit()
        con.close()
    except sqlite3.Error as exc:
        logger.error("DB write failed: %s", exc)


def show_status() -> None:
    """Print the last 20 cycles from the database."""
    if not DB_PATH.exists():
        print("No watchdog database found.")
        return
    con = sqlite3.connect(str(DB_PATH))
    rows = con.execute(
        "SELECT id, ts, grade, health_score, issues_count, decisions_count, fix_applied "
        "FROM cycles ORDER BY id DESC LIMIT 20"
    ).fetchall()
    con.close()

    if not rows:
        print("No cycles recorded yet.")
        return

    print(f"\n{'='*72}")
    print(f"  JARVIS Watchdog Autonomous — Last {len(rows)} cycles")
    print(f"{'='*72}")
    print(f"  {'ID':>5}  {'Timestamp':>19}  {'Grade':>5}  {'Health':>6}  {'Issues':>6}  {'Dec':>4}  {'Fix':>3}")
    print(f"  {'-'*5}  {'-'*19}  {'-'*5}  {'-'*6}  {'-'*6}  {'-'*4}  {'-'*3}")
    for row in rows:
        rid, ts, grade, health, issues, decisions, fix = row
        marker = " <<" if GRADE_ORDER.get(grade, 0) < GRADE_ORDER["B"] else ""
        print(f"  {rid:>5}  {ts:>19}  {grade:>5}  {health:>6.1f}  {issues:>6}  {decisions:>4}  {fix:>3}{marker}")
    print()


# ── HTTP helpers ──────────────────────────────────────────────────────

def http_post(url: str, payload: dict, timeout: float = HTTP_TIMEOUT) -> dict | None:
    """POST JSON to a URL, return parsed response or None on error."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body.strip() else {}
    except urllib.error.HTTPError as exc:
        logger.error("HTTP %d from %s: %s", exc.code, url, exc.reason)
        return None
    except urllib.error.URLError as exc:
        logger.error("URL error for %s: %s", url, exc.reason)
        return None
    except Exception as exc:
        logger.error("Request to %s failed: %s", url, exc)
        return None


# ── Core logic ────────────────────────────────────────────────────────

def run_autonomous_cycle() -> dict | None:
    """POST /api/autonomous/cycle and return the parsed report."""
    logger.info("Triggering autonomous cycle...")
    result = http_post(CYCLE_URL, {"notify": True, "fix": True})
    if result is None:
        logger.error("Autonomous cycle call failed (WS :9742 unreachable?)")
    return result


def run_self_improve() -> dict | None:
    """POST /api/self-improve/run and return the result."""
    logger.info("Triggering self-improve cycle...")
    result = http_post(SELF_IMPROVE_URL, {})
    if result is None:
        logger.error("Self-improve call failed")
    return result


def send_telegram_alert(message: str) -> bool:
    """POST /api/telegram/send with an alert message."""
    logger.info("Sending Telegram alert: %s", message[:80])
    result = http_post(TELEGRAM_URL, {"message": message}, timeout=10)
    return result is not None


def extract_metrics(report: dict) -> dict:
    """Extract grade, health_score, issues_count, decisions_count from the cycle report."""
    grade = report.get("grade", "F")
    health_score = 0.0
    raw = report.get("overall_health", 0)
    if isinstance(raw, (int, float)):
        health_score = float(raw)

    # Issues count: from scan section
    scan = report.get("scan", {})
    issues_count = 0
    if isinstance(scan.get("issues_count"), int):
        issues_count = scan["issues_count"]
    elif isinstance(scan.get("issues"), list):
        issues_count = len(scan["issues"])

    # Decisions count
    decisions = report.get("decisions", {})
    decisions_count = 0
    if isinstance(decisions.get("count"), int):
        decisions_count = decisions["count"]

    return {
        "grade": grade,
        "health_score": health_score,
        "issues_count": issues_count,
        "decisions_count": decisions_count,
    }


def run_once() -> bool:
    """Execute one full watchdog iteration. Returns True if successful."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fix_applied = 0

    # Step 1: Run autonomous cycle
    report = run_autonomous_cycle()
    if report is None:
        # WS offline — record a failure row
        save_cycle(ts, grade="F", health_score=0, issues_count=-1,
                   decisions_count=0, fix_applied=0)
        send_telegram_alert("ALERTE: Watchdog impossible de contacter WS :9742 — cycle echoue")
        return False

    metrics = extract_metrics(report)
    grade = metrics["grade"]
    health_score = metrics["health_score"]
    issues_count = metrics["issues_count"]
    decisions_count = metrics["decisions_count"]

    logger.info(
        "Cycle result: grade=%s health=%.1f issues=%d decisions=%d",
        grade, health_score, issues_count, decisions_count,
    )

    # Step 2: If grade < B, run self-improve
    if GRADE_ORDER.get(grade, 0) < GRADE_ORDER["B"]:
        logger.warning("Grade %s < B — triggering self-improve", grade)
        si_result = run_self_improve()
        if si_result is not None:
            fix_applied = 1
            logger.info("Self-improve completed: %s", json.dumps(si_result)[:200])
        else:
            logger.error("Self-improve failed")

    # Step 2.5: Kill phantom processes every cycle
    try:
        kp_script = Path("F:/BUREAU/turbo/scripts/kill_phantoms.py")
        kp_r = subprocess.run(
            ["python3", str(kp_script), "--json"],
            capture_output=True, text=True, timeout=30,
            encoding="utf-8", errors="replace"
        )
        if kp_r.stdout.strip():
            kp_data = json.loads(kp_r.stdout)
            kp_killed = kp_data.get("killed", 0)
            if kp_killed > 0:
                logger.info("Kill Phantoms: %d killed, %.0fMB freed",
                            kp_killed, kp_data.get("mem_freed_mb", 0))
    except Exception as e:
        logger.debug("Kill Phantoms skipped: %s", e)

    # Step 3: If grade < C, send Telegram alert
    if GRADE_ORDER.get(grade, 0) < GRADE_ORDER["C"]:
        alert_msg = (
            f"ALERTE: grade {grade} (health {health_score:.0f}/100)\n"
            f"Issues: {issues_count} | Decisions: {decisions_count}\n"
            f"Self-improve: {'applied' if fix_applied else 'N/A'}"
        )
        send_telegram_alert(alert_msg)

    # Step 4: Save to DB
    save_cycle(ts, grade, health_score, issues_count, decisions_count, fix_applied)

    return True


# ── Main ──────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="JARVIS Watchdog Autonomous — cycle monitor with grade tracking",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="Run a single cycle then exit")
    mode.add_argument("--daemon", action="store_true", help="Loop every 5 minutes")
    mode.add_argument("--status", action="store_true", help="Show recent cycles from DB")
    parser.add_argument("--interval", type=int, default=INTERVAL_S,
                        help=f"Seconds between cycles in daemon mode (default {INTERVAL_S})")
    args = parser.parse_args()

    # Status: no singleton needed
    if args.status:
        show_status()
        return

    # Singleton guard
    singleton = ProcessSingleton()
    singleton.acquire(SERVICE_NAME)
    logger.info("Singleton acquired: %s (PID %d)", SERVICE_NAME, os.getpid())

    # Init DB
    init_db()

    if args.once:
        logger.info("=== Watchdog Autonomous — single run ===")
        ok = run_once()
        singleton.release(SERVICE_NAME)
        sys.exit(0 if ok else 1)

    # Daemon mode
    interval = args.interval
    logger.info("=== Watchdog Autonomous — daemon mode (interval %ds) ===", interval)

    cycle_num = 0
    try:
        while _running:
            cycle_num += 1
            logger.info("--- Daemon cycle %d ---", cycle_num)
            run_once()

            # Interruptible sleep
            for _ in range(interval):
                if not _running:
                    break
                time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("Watchdog stopping after %d cycles", cycle_num)
        singleton.release(SERVICE_NAME)


if __name__ == "__main__":
    main()
