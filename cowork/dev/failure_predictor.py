#!/usr/bin/env python3
"""failure_predictor.py — Predict and prevent cluster failures before they happen.

Analyzes trends to predict:
- Node failures (increasing latency/error rate)
- Disk space running out
- Quality degradation
- Timeout patterns

Generates proactive alerts BEFORE problems become critical.

CLI:
    --once         : Single prediction cycle
    --watch        : Continuous prediction (default 15 min)
    --risk         : Show current risk assessment
    --telegram     : Send risk report to Telegram

Stdlib-only (json, argparse, sqlite3, time, math).
"""

import argparse
import json
import math
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
from _paths import ETOILE_DB

TELEGRAM_TOKEN = "8369376863:AAF-7YGDbun8mXWwqYJFj-eX6P78DeIu9Aw"
TELEGRAM_CHAT_ID = "2010747443"


def get_db(path):
    conn = sqlite3.connect(str(path), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def init_predictions_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS failure_predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        category TEXT NOT NULL,
        target TEXT NOT NULL,
        risk_level TEXT NOT NULL,
        risk_score REAL,
        description TEXT,
        recommended_action TEXT
    )""")
    conn.commit()


def predict_node_failures(gaps_db, edb):
    """Predict node failures based on heartbeat and dispatch trends."""
    predictions = []

    # Heartbeat trend: are any nodes getting slower?
    try:
        nodes = gaps_db.execute("""
            SELECT node,
                   AVG(CASE WHEN id > (SELECT MAX(id)-5 FROM heartbeat_log WHERE node=hl.node)
                       THEN latency_ms END) as recent_lat,
                   AVG(CASE WHEN id <= (SELECT MAX(id)-5 FROM heartbeat_log WHERE node=hl.node)
                            AND id > (SELECT MAX(id)-10 FROM heartbeat_log WHERE node=hl.node)
                       THEN latency_ms END) as older_lat,
                   SUM(CASE WHEN status='offline' AND id > (SELECT MAX(id)-10 FROM heartbeat_log WHERE node=hl.node)
                       THEN 1 ELSE 0 END) as recent_offline
            FROM heartbeat_log hl
            GROUP BY node
        """).fetchall()

        for n in nodes:
            risk = 0
            reasons = []

            # Latency increasing
            if n["recent_lat"] and n["older_lat"] and n["older_lat"] > 0:
                lat_increase = (n["recent_lat"] - n["older_lat"]) / n["older_lat"] * 100
                if lat_increase > 50:
                    risk += 30
                    reasons.append(f"latency +{lat_increase:.0f}%")
                elif lat_increase > 20:
                    risk += 15
                    reasons.append(f"latency +{lat_increase:.0f}%")

            # Recent offline events
            if n["recent_offline"] and n["recent_offline"] > 0:
                risk += n["recent_offline"] * 20
                reasons.append(f"{n['recent_offline']} offline events")

            if risk > 0:
                level = "HIGH" if risk >= 50 else "MEDIUM" if risk >= 25 else "LOW"
                predictions.append({
                    "category": "node_failure",
                    "target": n["node"],
                    "risk_score": min(risk, 100),
                    "risk_level": level,
                    "description": f"Node {n['node']} risk: {', '.join(reasons)}",
                    "action": f"Monitor {n['node']} closely, prepare fallback",
                })
    except Exception:
        pass

    # Dispatch quality trend
    try:
        has = edb.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE name='agent_dispatch_log'"
        ).fetchone()[0]
        if has:
            nodes = edb.execute("""
                SELECT node,
                       AVG(CASE WHEN id > (SELECT MAX(id)-10 FROM agent_dispatch_log)
                           THEN CASE WHEN success=1 THEN 1.0 ELSE 0 END END) as recent_rate,
                       AVG(CASE WHEN id <= (SELECT MAX(id)-10 FROM agent_dispatch_log)
                                AND id > (SELECT MAX(id)-20 FROM agent_dispatch_log)
                           THEN CASE WHEN success=1 THEN 1.0 ELSE 0 END END) as older_rate
                FROM agent_dispatch_log
                GROUP BY node
            """).fetchall()

            for n in nodes:
                if n["recent_rate"] is not None and n["older_rate"] is not None:
                    if n["older_rate"] > 0:
                        change = (n["recent_rate"] - n["older_rate"]) / n["older_rate"] * 100
                        if change < -20:
                            risk = min(abs(change), 80)
                            predictions.append({
                                "category": "quality_degradation",
                                "target": n["node"],
                                "risk_score": risk,
                                "risk_level": "HIGH" if risk >= 50 else "MEDIUM",
                                "description": f"Success rate dropping {change:.0f}% on {n['node']}",
                                "action": f"Check {n['node']} model and config",
                            })
    except Exception:
        pass

    return predictions


def predict_resource_issues():
    """Predict disk space and resource issues."""
    predictions = []

    # Disk space
    try:
        if sys.platform == "win32":
            import ctypes
            for drive, name in [("F:\\", "F"), ("C:\\", "C")]:
                free = ctypes.c_ulonglong()
                total = ctypes.c_ulonglong()
                ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                    drive, None, ctypes.pointer(total), ctypes.pointer(free))
                free_gb = free.value / (1024**3)
                total_gb = total.value / (1024**3)
                pct_free = free_gb / total_gb * 100

                if pct_free < 5:
                    predictions.append({
                        "category": "disk_space",
                        "target": f"Drive {name}",
                        "risk_score": 90,
                        "risk_level": "CRITICAL",
                        "description": f"{name}: only {free_gb:.1f}GB free ({pct_free:.1f}%)",
                        "action": "Clean temp files, old models, backups",
                    })
                elif pct_free < 15:
                    predictions.append({
                        "category": "disk_space",
                        "target": f"Drive {name}",
                        "risk_score": 40,
                        "risk_level": "MEDIUM",
                        "description": f"{name}: {free_gb:.1f}GB free ({pct_free:.1f}%)",
                        "action": "Monitor disk usage, plan cleanup",
                    })
    except Exception:
        pass

    # DB growth
    for name, path in [("etoile", ETOILE_DB), ("gaps", GAPS_DB)]:
        if path.exists():
            size_mb = path.stat().st_size / (1024 * 1024)
            if size_mb > 50:
                predictions.append({
                    "category": "db_growth",
                    "target": name,
                    "risk_score": 30,
                    "risk_level": "LOW",
                    "description": f"{name}.db is {size_mb:.1f}MB",
                    "action": "Run log_compressor.py --once",
                })

    return predictions


def predict_pattern_issues(gaps_db):
    """Predict dispatch pattern issues."""
    predictions = []

    try:
        # Check for patterns with increasing timeout usage
        configs = gaps_db.execute("""
            SELECT pattern, node, recommended_timeout_s, p95_latency_ms
            FROM timeout_configs
            WHERE timestamp > datetime('now', '-24 hours')
        """).fetchall()

        for c in configs:
            if c["p95_latency_ms"] and c["recommended_timeout_s"]:
                ratio = c["p95_latency_ms"] / (c["recommended_timeout_s"] * 1000)
                if ratio > 0.8:
                    predictions.append({
                        "category": "timeout_risk",
                        "target": f"{c['pattern']}/{c['node']}",
                        "risk_score": int(ratio * 80),
                        "risk_level": "HIGH" if ratio > 0.9 else "MEDIUM",
                        "description": f"P95 at {ratio*100:.0f}% of timeout ({c['pattern']}/{c['node']})",
                        "action": "Increase timeout or optimize prompt size",
                    })
    except Exception:
        pass

    return predictions


def run_prediction_cycle():
    """Run all prediction models."""
    gaps_db = get_db(GAPS_DB)
    init_predictions_table(gaps_db)

    try:
        edb = get_db(ETOILE_DB)
    except Exception:
        edb = None

    all_predictions = []
    all_predictions.extend(predict_node_failures(gaps_db, edb))
    all_predictions.extend(predict_resource_issues())
    all_predictions.extend(predict_pattern_issues(gaps_db))

    # Dedup: keep only unique (category, target) with highest risk
    seen = {}
    for p in all_predictions:
        key = (p["category"], p["target"])
        if key not in seen or p["risk_score"] > seen[key]["risk_score"]:
            seen[key] = p
    all_predictions = list(seen.values())

    # Store predictions (clear old ones first to avoid accumulation)
    ts = datetime.now().isoformat()
    gaps_db.execute("DELETE FROM failure_predictions WHERE timestamp < datetime('now', '-2 hours')")
    for p in all_predictions:
        gaps_db.execute("""
            INSERT INTO failure_predictions
            (timestamp, category, target, risk_level, risk_score, description, recommended_action)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (ts, p["category"], p["target"], p["risk_level"],
              p["risk_score"], p["description"], p["action"]))
    gaps_db.commit()

    if edb:
        edb.close()
    gaps_db.close()

    return all_predictions


def format_risk_report(predictions):
    """Format risk report for Telegram."""
    ts = datetime.now().strftime("%H:%M:%S")
    if not predictions:
        return f"<b>Risk Report</b> <code>{ts}</code>\n\nNo risks detected"

    lines = [f"<b>Risk Report</b> <code>{ts}</code>"]

    # Sort by risk score
    predictions.sort(key=lambda p: -p["risk_score"])

    for p in predictions:
        emoji = "!!" if p["risk_level"] == "CRITICAL" else "!" if p["risk_level"] == "HIGH" else "~"
        lines.append(f"\n{emoji} <b>{p['target']}</b> [{p['risk_level']}] {p['risk_score']}/100")
        lines.append(f"  {p['description']}")
        lines.append(f"  Action: {p['action']}")

    max_risk = predictions[0]["risk_score"] if predictions else 0
    overall = "SAFE" if max_risk < 25 else "CAUTION" if max_risk < 50 else "WARNING" if max_risk < 75 else "DANGER"
    lines.insert(1, f"Overall: <b>{overall}</b> (max risk: {max_risk}/100)")

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
    parser = argparse.ArgumentParser(description="Failure Predictor")
    parser.add_argument("--once", action="store_true", help="Single prediction")
    parser.add_argument("--watch", action="store_true", help="Continuous prediction")
    parser.add_argument("--interval", type=int, default=15, help="Interval (min)")
    parser.add_argument("--risk", action="store_true", help="Show risk assessment")
    parser.add_argument("--telegram", action="store_true", help="Send Telegram")
    args = parser.parse_args()

    if not any([args.once, args.watch, args.risk, args.telegram]):
        parser.print_help()
        sys.exit(1)

    if args.risk:
        predictions = run_prediction_cycle()
        for p in sorted(predictions, key=lambda x: -x["risk_score"]):
            print(f"  [{p['risk_level']:8}] {p['risk_score']:3}/100 {p['target']:20} {p['description']}")
        print(f"\nTotal: {len(predictions)} risks identified")
        return

    if args.once or args.telegram:
        predictions = run_prediction_cycle()
        report = format_risk_report(predictions)
        print(report.replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", ""))

        if args.telegram:
            send_telegram(report)
            print("\nRisk report sent to Telegram")

        result = {
            "timestamp": datetime.now().isoformat(),
            "total_risks": len(predictions),
            "high_risks": sum(1 for p in predictions if p["risk_level"] in ["HIGH", "CRITICAL"]),
            "predictions": predictions,
        }
        print(json.dumps(result, indent=2))
        return

    if args.watch:
        print(f"Failure prediction every {args.interval}m")
        while True:
            predictions = run_prediction_cycle()
            ts = datetime.now().strftime("%H:%M:%S")
            high = sum(1 for p in predictions if p["risk_level"] in ["HIGH", "CRITICAL"])
            print(f"[{ts}] {len(predictions)} risks ({high} high)")

            # Send alert only if high risks
            if high > 0:
                report = format_risk_report(predictions)
                send_telegram(report)

            time.sleep(args.interval * 60)


if __name__ == "__main__":
    main()
