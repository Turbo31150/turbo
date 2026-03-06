#!/usr/bin/env python3
"""daily_cowork_report.py — Generate and send daily COWORK performance report.

Compiles metrics from the last 24h: dispatches, success rates, quality,
trends, alerts, and improvements. Sends summary to Telegram.

CLI:
    --once       : generate and send daily report
    --generate   : generate without sending
    --history    : show past reports
    --stats      : show report statistics

Stdlib-only (sqlite3, json, argparse, urllib).
"""

import argparse
import json
import os
import sqlite3
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
DB_PATH = DATA_DIR / "cowork_gaps.db"
from _paths import ETOILE_DB, TELEGRAM_TOKEN, TELEGRAM_CHAT

# TELEGRAM_TOKEN loaded from _paths (.env)
TELEGRAM_CHAT_ID = TELEGRAM_CHAT


def init_db(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS daily_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        report_json TEXT NOT NULL,
        sent_telegram INTEGER DEFAULT 0,
        message_id INTEGER
    )""")
    conn.commit()


def get_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def send_telegram(text):
    """Send message to Telegram."""
    parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
    ids = []
    for part in parts:
        data = urllib.parse.urlencode({
            "chat_id": TELEGRAM_CHAT_ID, "text": part, "parse_mode": "Markdown"
        }).encode()
        try:
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data
            )
            resp = urllib.request.urlopen(req, timeout=10)
            r = json.loads(resp.read())
            if r.get("ok"):
                ids.append(r["result"]["message_id"])
        except Exception:
            # Retry without markdown
            try:
                data2 = urllib.parse.urlencode({"chat_id": TELEGRAM_CHAT_ID, "text": part}).encode()
                req2 = urllib.request.Request(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data2
                )
                urllib.request.urlopen(req2, timeout=10)
            except Exception:
                pass
    return ids


def generate_report():
    """Generate daily performance report."""
    now = datetime.now()
    yesterday = (now - timedelta(hours=24)).isoformat()

    report = {
        "date": now.strftime("%Y-%m-%d"),
        "generated_at": now.isoformat(),
        "period": "last_24h",
    }

    if not ETOILE_DB.exists():
        report["error"] = "etoile.db not found"
        return report

    edb = sqlite3.connect(str(ETOILE_DB))
    edb.row_factory = sqlite3.Row

    # Today's dispatches
    today_stats = edb.execute("""
        SELECT COUNT(*) as total,
               SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) as success,
               AVG(latency_ms) as avg_lat,
               AVG(quality_score) as avg_q
        FROM agent_dispatch_log
        WHERE timestamp >= ?
    """, (yesterday,)).fetchone()

    total = today_stats["total"] or 0
    success = today_stats["success"] or 0

    report["dispatches"] = {
        "total": total,
        "success": success,
        "success_rate_pct": round(success / max(total, 1) * 100, 1),
        "avg_latency_ms": round(today_stats["avg_lat"] or 0),
        "avg_quality": round(today_stats["avg_q"] or 0, 3),
    }

    # Top patterns today
    top_patterns = edb.execute("""
        SELECT classified_type, COUNT(*) as cnt,
               AVG(CASE WHEN success=1 THEN 100.0 ELSE 0.0 END) as rate
        FROM agent_dispatch_log
        WHERE timestamp >= ?
        GROUP BY classified_type
        ORDER BY cnt DESC LIMIT 8
    """, (yesterday,)).fetchall()
    report["top_patterns"] = [
        {"pattern": r["classified_type"], "count": r["cnt"],
         "success_pct": round(r["rate"], 1)}
        for r in top_patterns
    ]

    # Node performance today
    node_stats = edb.execute("""
        SELECT node, COUNT(*) as cnt,
               AVG(CASE WHEN success=1 THEN 100.0 ELSE 0.0 END) as rate,
               AVG(latency_ms) as avg_lat
        FROM agent_dispatch_log
        WHERE timestamp >= ?
        GROUP BY node
        ORDER BY cnt DESC
    """, (yesterday,)).fetchall()
    report["nodes"] = [
        {"node": r["node"], "dispatches": r["cnt"],
         "success_pct": round(r["rate"], 1),
         "avg_ms": round(r["avg_lat"] or 0)}
        for r in node_stats
    ]

    # Errors today
    errors = edb.execute("""
        SELECT COUNT(*) FROM agent_dispatch_log
        WHERE timestamp >= ? AND success = 0
    """, (yesterday,)).fetchone()[0]
    report["errors_today"] = errors

    edb.close()

    # COWORK script stats
    script_count = len(list(SCRIPT_DIR.glob("*.py")))
    report["cowork_scripts"] = script_count

    # Mapped scripts
    try:
        edb2 = sqlite3.connect(str(ETOILE_DB))
        mapped = edb2.execute("SELECT COUNT(*) FROM cowork_script_mapping WHERE status='active'").fetchone()[0]
        edb2.close()
        report["mapped_scripts"] = mapped
    except Exception:
        report["mapped_scripts"] = "?"

    # Check for alerts
    conn = get_db()
    alerts_today = 0
    try:
        alerts_today = conn.execute("""
            SELECT COUNT(*) FROM proactive_alerts
            WHERE timestamp >= ?
        """, (yesterday,)).fetchone()[0]
    except Exception:
        pass
    report["alerts_today"] = alerts_today

    # Improvements applied today
    improvements_today = 0
    try:
        improvements_today = conn.execute("""
            SELECT COUNT(*) FROM auto_improvements
            WHERE timestamp >= ? AND applied = 1
        """, (yesterday,)).fetchone()[0]
    except Exception:
        pass
    report["improvements_today"] = improvements_today

    conn.close()

    return report


def format_telegram_report(report):
    """Format report for Telegram."""
    d = report.get("dispatches", {})
    patterns = report.get("top_patterns", [])
    nodes = report.get("nodes", [])

    patterns_text = "\n".join(
        f"  {p['pattern']:12s} n={p['count']:3d} ok={p['success_pct']:.0f}%"
        for p in patterns[:6]
    )
    nodes_text = "\n".join(
        f"  {n['node']:5s} n={n['dispatches']:3d} ok={n['success_pct']:.0f}% lat={n['avg_ms']}ms"
        for n in nodes
    )

    return f"""*Rapport COWORK Quotidien*
{report.get('date', '?')}
{'='*30}

*Dispatches (24h)*
  Total: {d.get('total', 0)}
  Succes: {d.get('success_rate_pct', 0)}%
  Latence moy: {d.get('avg_latency_ms', 0)}ms
  Qualite moy: {d.get('avg_quality', 0)}

*Patterns*
{patterns_text}

*Noeuds*
{nodes_text}

*Alertes*: {report.get('alerts_today', 0)}
*Erreurs*: {report.get('errors_today', 0)}
*Ameliorations*: {report.get('improvements_today', 0)}
*Scripts COWORK*: {report.get('cowork_scripts', '?')}

_Genere {datetime.now().strftime('%H:%M')}_"""


def main():
    parser = argparse.ArgumentParser(description="Daily COWORK Report")
    parser.add_argument("--once", action="store_true", help="Generate and send")
    parser.add_argument("--generate", action="store_true", help="Generate only")
    parser.add_argument("--history", action="store_true", help="Past reports")
    parser.add_argument("--stats", action="store_true", help="Stats")
    args = parser.parse_args()

    if not any([args.once, args.generate, args.history, args.stats]):
        parser.print_help()
        sys.exit(1)

    if args.history or args.stats:
        conn = get_db()
        rows = conn.execute("SELECT timestamp, sent_telegram FROM daily_reports ORDER BY timestamp DESC LIMIT 10").fetchall()
        conn.close()
        result = {"reports": [dict(r) for r in rows]}
    else:
        report = generate_report()
        conn = get_db()
        msg_id = 0

        if args.once:
            msg = format_telegram_report(report)
            ids = send_telegram(msg)
            msg_id = ids[0] if ids else 0

        conn.execute("""
            INSERT INTO daily_reports (timestamp, report_json, sent_telegram, message_id)
            VALUES (?, ?, ?, ?)
        """, (datetime.now().isoformat(), json.dumps(report), int(args.once), msg_id))
        conn.commit()
        conn.close()

        result = report
        if args.once:
            result["telegram_sent"] = True
            result["message_id"] = msg_id

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()