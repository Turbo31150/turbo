#!/usr/bin/env python3
"""cowork_health_summary.py — Unified health summary of the entire COWORK system.

Aggregates data from all subsystems into a single health score and report:
- Script health (test pass rate)
- Cluster health (node availability)
- Dispatch health (success rate, latency, quality)
- Infrastructure (script count, mapping coverage, scheduler)

CLI:
    --once       : generate health summary
    --telegram   : generate and send to Telegram
    --stats      : show health history

Stdlib-only (sqlite3, json, argparse, urllib, subprocess).
"""

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
DB_PATH = DATA_DIR / "cowork_gaps.db"
ETOILE_DB = Path(r"F:/BUREAU/turbo/etoile.db")
PYTHON = sys.executable

TELEGRAM_TOKEN = "8369376863:AAF-7YGDbun8mXWwqYJFj-eX6P78DeIu9Aw"
TELEGRAM_CHAT_ID = "2010747443"


def init_db(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS health_summaries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        overall_score REAL,
        grade TEXT,
        summary_json TEXT
    )""")
    conn.commit()


def get_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def run_script(name, args):
    script_path = SCRIPT_DIR / f"{name}.py"
    if not script_path.exists():
        return None
    cmd = [PYTHON, str(script_path)] + (args if isinstance(args, list) else [args])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=str(SCRIPT_DIR))
        if r.returncode == 0 and r.stdout.strip():
            return json.loads(r.stdout)
    except Exception:
        pass
    return None


def check_scripts():
    """Check script health."""
    total = len(list(SCRIPT_DIR.glob("*.py")))
    data = run_script("cowork_self_test_runner", ["--level", "3"])
    if data:
        passed = data.get("passed", 0)
        total_tests = data.get("total_tests", 0)
        rate = data.get("success_rate_pct", 0)
        return {"total_scripts": total, "tests_passed": passed, "tests_total": total_tests, "pass_rate": rate, "score": rate}
    return {"total_scripts": total, "tests_passed": 0, "tests_total": 0, "pass_rate": 0, "score": 0}


def check_cluster():
    """Check cluster health."""
    data = run_script("cluster_health_watchdog", "--once")
    if data:
        nodes = data.get("nodes", [])
        online = sum(1 for n in nodes if n.get("status") == "healthy")
        total = len(nodes)
        score = online / max(total, 1) * 100
        avg_ms = sum(n.get("response_ms", 0) for n in nodes) / max(len(nodes), 1)
        return {
            "status": data.get("cluster_status", "?"),
            "online": online, "total": total,
            "avg_response_ms": round(avg_ms),
            "alerts": len(data.get("alerts", [])),
            "score": score,
        }
    return {"status": "unknown", "online": 0, "total": 0, "avg_response_ms": 0, "alerts": 0, "score": 0}


def check_dispatch():
    """Check dispatch performance."""
    if not ETOILE_DB.exists():
        return {"score": 0}
    edb = sqlite3.connect(str(ETOILE_DB), timeout=10)
    edb.row_factory = sqlite3.Row

    # Check if table exists
    has_table = edb.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='agent_dispatch_log'"
    ).fetchone()[0]
    if not has_table:
        edb.close()
        return {"recent_dispatches": 0, "success_rate": 0, "avg_latency_ms": 0,
                "avg_quality": 0, "score": 50.0, "note": "no dispatch data yet"}

    row = edb.execute("""
        SELECT COUNT(*) as total,
               AVG(CASE WHEN success=1 THEN 100.0 ELSE 0.0 END) as rate,
               AVG(latency_ms) as avg_lat,
               AVG(quality_score) as avg_q
        FROM (SELECT * FROM agent_dispatch_log ORDER BY id DESC LIMIT 200)
    """).fetchone()

    total = row["total"] or 0
    rate = row["rate"] or 0
    avg_lat = row["avg_lat"] or 0
    avg_q = row["avg_q"] or 0

    # Score: weighted combination
    lat_score = max(0, 100 - (avg_lat / 500))  # Penalize high latency
    q_score = avg_q * 100
    score = rate * 0.5 + lat_score * 0.2 + q_score * 0.3

    edb.close()
    return {
        "recent_dispatches": total,
        "success_rate": round(rate, 1),
        "avg_latency_ms": round(avg_lat),
        "avg_quality": round(avg_q, 3),
        "score": round(score, 1),
    }


def check_infrastructure():
    """Check infrastructure coverage."""
    if not ETOILE_DB.exists():
        return {"score": 0}
    edb = sqlite3.connect(str(ETOILE_DB))

    scripts = len(list(SCRIPT_DIR.glob("*.py")))
    mapped = edb.execute("SELECT COUNT(*) FROM cowork_script_mapping WHERE status='active'").fetchone()[0]
    patterns = edb.execute("SELECT COUNT(DISTINCT pattern_id) FROM cowork_script_mapping WHERE status='active'").fetchone()[0]
    edb.close()

    coverage = mapped / max(scripts, 1) * 100
    score = min(coverage, 100)

    return {
        "scripts": scripts,
        "mapped": mapped,
        "patterns": patterns,
        "coverage_pct": round(coverage, 1),
        "score": round(score, 1),
    }


def compute_grade(score):
    if score >= 95:
        return "A+"
    elif score >= 90:
        return "A"
    elif score >= 85:
        return "A-"
    elif score >= 80:
        return "B+"
    elif score >= 75:
        return "B"
    elif score >= 70:
        return "B-"
    elif score >= 60:
        return "C"
    elif score >= 50:
        return "D"
    return "F"


def generate_summary():
    """Generate complete health summary."""
    scripts = check_scripts()
    cluster = check_cluster()
    dispatch = check_dispatch()
    infra = check_infrastructure()

    # Overall: weighted average
    overall = (
        scripts["score"] * 0.25 +
        cluster["score"] * 0.25 +
        dispatch["score"] * 0.3 +
        infra["score"] * 0.2
    )
    grade = compute_grade(overall)

    summary = {
        "timestamp": datetime.now().isoformat(),
        "overall_score": round(overall, 1),
        "grade": grade,
        "subsystems": {
            "scripts": scripts,
            "cluster": cluster,
            "dispatch": dispatch,
            "infrastructure": infra,
        },
    }

    # Store
    conn = get_db()
    conn.execute(
        "INSERT INTO health_summaries (timestamp, overall_score, grade, summary_json) VALUES (?, ?, ?, ?)",
        (summary["timestamp"], overall, grade, json.dumps(summary))
    )
    conn.commit()
    conn.close()

    return summary


def format_telegram(summary):
    """Format for Telegram."""
    s = summary["subsystems"]
    sc = s["scripts"]
    cl = s["cluster"]
    di = s["dispatch"]
    inf = s["infrastructure"]

    def bar(val, width=10):
        filled = int(val / 100 * width)
        return f"[{'#' * filled}{'.' * (width - filled)}]"

    return f"""<b>COWORK Health Summary</b>
{'=' * 30}

<b>Score: {summary['overall_score']}/100  Grade: {summary['grade']}</b>

<b>Scripts</b> {bar(sc['score'])} {sc['score']:.0f}%
  {sc['tests_passed']}/{sc['tests_total']} tests OK | {sc['total_scripts']} fichiers

<b>Cluster</b> {bar(cl['score'])} {cl['score']:.0f}%
  {cl['online']}/{cl['total']} noeuds | {cl['avg_response_ms']}ms | {cl['alerts']} alertes

<b>Dispatch</b> {bar(di['score'])} {di['score']:.0f}%
  OK: {di.get('success_rate', 0)}% | Lat: {di.get('avg_latency_ms', 0)}ms | Q: {di.get('avg_quality', 0)}

<b>Infrastructure</b> {bar(inf['score'])} {inf['score']:.0f}%
  {inf.get('mapped', 0)}/{inf.get('scripts', 0)} mappes | {inf.get('patterns', 0)} patterns

<code>{datetime.now().strftime('%H:%M:%S')}</code>"""


def send_telegram(text):
    data = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"
    }).encode()
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data
        )
        resp = urllib.request.urlopen(req, timeout=10)
        r = json.loads(resp.read())
        return r.get("result", {}).get("message_id", 0)
    except Exception:
        # Retry without HTML
        try:
            data2 = urllib.parse.urlencode({"chat_id": TELEGRAM_CHAT_ID, "text": text}).encode()
            req2 = urllib.request.Request(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data2
            )
            urllib.request.urlopen(req2, timeout=10)
        except Exception:
            pass
    return 0


def main():
    parser = argparse.ArgumentParser(description="COWORK Health Summary")
    parser.add_argument("--once", action="store_true", help="Generate summary")
    parser.add_argument("--telegram", action="store_true", help="Generate and send")
    parser.add_argument("--stats", action="store_true", help="Show history")
    args = parser.parse_args()

    if not any([args.once, args.telegram, args.stats]):
        parser.print_help()
        sys.exit(1)

    if args.stats:
        conn = get_db()
        rows = conn.execute("""
            SELECT timestamp, overall_score, grade
            FROM health_summaries ORDER BY id DESC LIMIT 20
        """).fetchall()
        conn.close()
        result = {"history": [dict(r) for r in rows]}
    else:
        summary = generate_summary()
        result = summary
        if args.telegram:
            msg = format_telegram(summary)
            mid = send_telegram(msg)
            result["telegram_sent"] = True
            result["message_id"] = mid

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
