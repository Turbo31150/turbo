#!/usr/bin/env python3
"""telegram_quick_status.py — One-shot JARVIS status dashboard via Telegram.

Sends a comprehensive status message covering all subsystems in one message.
Designed to be called by the orchestrator or manually.

CLI:
    --once         : Send status to Telegram
    --json         : Output JSON only (no Telegram)

Stdlib-only (json, argparse, sqlite3, urllib, time).
"""

import argparse
import json
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
GAPS_DB = DATA_DIR / "cowork_gaps.db"
ETOILE_DB = Path("F:/BUREAU/turbo/data/etoile.db")

TELEGRAM_TOKEN = "8369376863:AAF-7YGDbun8mXWwqYJFj-eX6P78DeIu9Aw"
TELEGRAM_CHAT_ID = "2010747443"


def get_db(path):
    conn = sqlite3.connect(str(path), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def get_cluster_status():
    """Get cluster node status."""
    try:
        db = get_db(GAPS_DB)
        rows = db.execute("""
            SELECT node, last_status, consecutive_fails
            FROM heartbeat_state ORDER BY node
        """).fetchall()
        db.close()
        online = sum(1 for r in rows if r["last_status"] == "online")
        nodes = {r["node"]: r["last_status"] for r in rows}
        return {"online": online, "total": len(rows), "nodes": nodes}
    except Exception:
        return {"online": 0, "total": 0, "nodes": {}}


def get_dispatch_status():
    """Get dispatch quality metrics."""
    try:
        db = get_db(ETOILE_DB)
        has = db.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE name='agent_dispatch_log'"
        ).fetchone()[0]
        if not has:
            db.close()
            return {"total": 0, "success_pct": 0, "quality": 0}
        row = db.execute("""
            SELECT COUNT(*) as total,
                   ROUND(AVG(CASE WHEN success=1 THEN 100.0 ELSE 0 END), 1) as rate,
                   ROUND(AVG(quality_score)*100, 1) as quality,
                   ROUND(AVG(latency_ms)) as lat
            FROM (SELECT * FROM agent_dispatch_log ORDER BY id DESC LIMIT 50)
        """).fetchone()
        db.close()
        return {
            "total": row["total"], "success_pct": row["rate"] or 0,
            "quality": row["quality"] or 0, "avg_lat_ms": row["lat"] or 0,
        }
    except Exception:
        return {"total": 0, "success_pct": 0, "quality": 0}


def get_crypto_status():
    """Get latest crypto prices."""
    try:
        db = get_db(GAPS_DB)
        rows = db.execute("""
            SELECT pair, price, change_24h_pct
            FROM crypto_price_alerts
            GROUP BY pair HAVING id = MAX(id)
        """).fetchall()
        db.close()
        return {r["pair"]: {"price": r["price"], "change": r["change_24h_pct"]} for r in rows}
    except Exception:
        return {}


def get_orchestrator_status():
    """Get orchestrator task stats."""
    try:
        db = get_db(GAPS_DB)
        rows = db.execute("""
            SELECT task_name, run_count, fail_count
            FROM orchestrator_schedule ORDER BY task_name
        """).fetchall()
        db.close()
        total_runs = sum(r["run_count"] for r in rows)
        total_fails = sum(r["fail_count"] for r in rows)
        return {
            "tasks": len(rows), "total_runs": total_runs,
            "total_fails": total_fails,
            "success_pct": round((total_runs - total_fails) / max(total_runs, 1) * 100, 1),
        }
    except Exception:
        return {"tasks": 0, "total_runs": 0, "success_pct": 0}


def get_risk_status():
    """Get current risk level."""
    try:
        db = get_db(GAPS_DB)
        rows = db.execute("""
            SELECT risk_level, risk_score, target, description
            FROM failure_predictions
            WHERE timestamp > datetime('now', '-2 hours')
            ORDER BY risk_score DESC
        """).fetchall()
        db.close()
        high = sum(1 for r in rows if r["risk_level"] in ("HIGH", "CRITICAL"))
        max_risk = rows[0]["risk_score"] if rows else 0
        return {"total": len(rows), "high": high, "max_risk": max_risk}
    except Exception:
        return {"total": 0, "high": 0, "max_risk": 0}


def get_script_count():
    """Get total scripts."""
    return len(list(SCRIPT_DIR.glob("*.py")))


def build_status():
    """Build complete status."""
    cluster = get_cluster_status()
    dispatch = get_dispatch_status()
    crypto = get_crypto_status()
    orch = get_orchestrator_status()
    risk = get_risk_status()
    scripts = get_script_count()

    # Compute overall health
    scores = []
    if cluster["total"]: scores.append(cluster["online"] / cluster["total"] * 100)
    if dispatch["total"]: scores.append(dispatch["success_pct"])
    scores.append(100 if orch["success_pct"] >= 95 else orch["success_pct"])
    scores.append(100 - risk["max_risk"])
    overall = round(sum(scores) / max(len(scores), 1), 1)
    grade = "A+" if overall >= 95 else "A" if overall >= 90 else "A-" if overall >= 85 else "B" if overall >= 75 else "C" if overall >= 60 else "F"

    return {
        "overall": overall, "grade": grade,
        "cluster": cluster, "dispatch": dispatch,
        "crypto": crypto, "orchestrator": orch,
        "risk": risk, "scripts": scripts,
    }


def format_telegram(status):
    """Format status as Telegram message."""
    ts = datetime.now().strftime("%H:%M")
    s = status

    # Header with grade
    grade_emoji = {"A+": "++", "A": "+", "A-": "+", "B": "~", "C": "-", "F": "!!"}
    ge = grade_emoji.get(s["grade"], "?")

    lines = [
        f"<b>JARVIS</b> {ge} <b>{s['grade']}</b> ({s['overall']}/100) <code>{ts}</code>",
        "",
    ]

    # Cluster
    c = s["cluster"]
    node_str = " ".join(
        f"{'OK' if st == 'online' else 'XX'}:{n}"
        for n, st in sorted(c.get("nodes", {}).items())
    )
    lines.append(f"<b>Cluster</b> {c['online']}/{c['total']}  {node_str}")

    # Dispatch
    d = s["dispatch"]
    if d["total"]:
        lines.append(f"<b>Dispatch</b> {d['success_pct']}% ok | q={d['quality']}% | {d['avg_lat_ms']}ms ({d['total']} recent)")

    # Crypto
    for pair, data in sorted(s.get("crypto", {}).items()):
        ch = data["change"]
        arrow = "+" if ch > 0 else ""
        lines.append(f"  {pair} ${data['price']} ({arrow}{ch:.2f}%)")

    # Orchestrator
    o = s["orchestrator"]
    lines.append(f"<b>Tasks</b> {o['tasks']} tasks | {o['total_runs']} runs | {o['success_pct']}% ok")

    # Risk
    r = s["risk"]
    if r["total"]:
        risk_label = "SAFE" if r["max_risk"] < 25 else "CAUTION" if r["max_risk"] < 50 else "WARNING"
        lines.append(f"<b>Risk</b> {risk_label} ({r['total']} items, {r['high']} high)")

    # Scripts
    lines.append(f"<b>Scripts</b> {s['scripts']}")

    return "\n".join(lines)


def send_telegram(text):
    data = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"
    }).encode()
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description="Telegram Quick Status")
    parser.add_argument("--once", action="store_true", help="Send status")
    parser.add_argument("--json", action="store_true", help="JSON only")
    args = parser.parse_args()

    if not any([args.once, args.json]):
        parser.print_help()
        sys.exit(1)

    status = build_status()

    if args.json:
        print(json.dumps(status, indent=2))
        return

    msg = format_telegram(status)
    send_telegram(msg)
    print(msg.replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", ""))
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
