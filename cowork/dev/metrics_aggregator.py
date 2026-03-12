#!/usr/bin/env python3
"""metrics_aggregator.py — Centralized metrics dashboard for JARVIS.

Aggregates data from all subsystems into a single view:
- Cluster: nodes online, latency, models loaded
- Dispatch: success rate, quality, routing efficiency
- Trading: price data, alert counts
- Scripts: total, test pass rate
- Infrastructure: DB sizes, disk usage

CLI:
    --once         : Generate metrics snapshot
    --watch        : Continuous metrics (default 5 min)
    --telegram     : Send Telegram dashboard
    --history      : Show metrics history

Stdlib-only (json, argparse, sqlite3, os, time).
"""

import argparse
import json
import os
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
from _paths import ETOILE_DB, TELEGRAM_TOKEN, TELEGRAM_CHAT
from _paths import JARVIS_DB

# TELEGRAM_TOKEN loaded from _paths (.env)
TELEGRAM_CHAT_ID = TELEGRAM_CHAT


def get_db(path, timeout=10):
    conn = sqlite3.connect(str(path), timeout=timeout)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def init_metrics_db(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS metrics_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        category TEXT NOT NULL,
        metric_name TEXT NOT NULL,
        value REAL,
        unit TEXT,
        details TEXT
    )""")
    conn.commit()


def collect_cluster_metrics():
    """Collect cluster health metrics."""
    metrics = {}
    try:
        db = get_db(GAPS_DB)
        rows = db.execute("""
            SELECT node, last_status, consecutive_fails
            FROM heartbeat_state
        """).fetchall()
        online = sum(1 for r in rows if r["last_status"] == "online")
        total = len(rows)
        metrics["cluster_online"] = online
        metrics["cluster_total"] = total
        metrics["cluster_health_pct"] = round(online / max(total, 1) * 100, 1)

        # Recent heartbeat latencies
        lats = db.execute("""
            SELECT node, AVG(latency_ms) as avg_lat
            FROM heartbeat_log
            WHERE timestamp > datetime('now', '-1 hour')
            GROUP BY node
        """).fetchall()
        for r in lats:
            metrics[f"heartbeat_lat_{r['node']}"] = round(r["avg_lat"])
        db.close()
    except Exception:
        metrics["cluster_health_pct"] = 0
    return metrics


def collect_dispatch_metrics():
    """Collect dispatch performance metrics."""
    metrics = {}
    try:
        db = get_db(ETOILE_DB)
        has = db.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE name='agent_dispatch_log'"
        ).fetchone()[0]
        if not has:
            db.close()
            return {"dispatch_total": 0}

        row = db.execute("""
            SELECT COUNT(*) as total,
                   AVG(CASE WHEN success=1 THEN 100.0 ELSE 0 END) as rate,
                   AVG(latency_ms) as avg_lat,
                   AVG(quality_score) as avg_q
            FROM (SELECT * FROM agent_dispatch_log ORDER BY id DESC LIMIT 100)
        """).fetchone()
        metrics["dispatch_total"] = row["total"]
        metrics["dispatch_success_pct"] = round(row["rate"] or 0, 1)
        metrics["dispatch_avg_latency_ms"] = round(row["avg_lat"] or 0)
        metrics["dispatch_avg_quality"] = round((row["avg_q"] or 0) * 100, 1)

        # Per-node
        nodes = db.execute("""
            SELECT node,
                   COUNT(*) as cnt,
                   AVG(CASE WHEN success=1 THEN 100.0 ELSE 0 END) as rate
            FROM agent_dispatch_log
            GROUP BY node
        """).fetchall()
        for n in nodes:
            metrics[f"dispatch_{n['node']}_rate"] = round(n["rate"], 1)
        db.close()
    except Exception:
        metrics["dispatch_total"] = 0
    return metrics


def collect_trading_metrics():
    """Collect trading/crypto metrics."""
    metrics = {}
    try:
        db = get_db(GAPS_DB)
        row = db.execute("""
            SELECT COUNT(*) as total,
                   MAX(price) as max_price,
                   MIN(price) as min_price
            FROM crypto_price_alerts
            WHERE timestamp > datetime('now', '-24 hours')
        """).fetchone()
        metrics["crypto_checks_24h"] = row["total"]

        # Latest prices
        pairs = db.execute("""
            SELECT pair, price, change_24h_pct
            FROM crypto_price_alerts
            GROUP BY pair
            HAVING id = MAX(id)
        """).fetchall()
        for p in pairs:
            metrics[f"price_{p['pair']}"] = p["price"]
            metrics[f"change_{p['pair']}"] = p["change_24h_pct"]
        db.close()
    except Exception:
        pass
    return metrics


def collect_script_metrics():
    """Collect script/test metrics."""
    metrics = {}
    try:
        scripts = len(list(SCRIPT_DIR.glob("*.py")))
        metrics["total_scripts"] = scripts

        db = get_db(ETOILE_DB)
        has = db.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE name='cowork_script_mapping'"
        ).fetchone()[0]
        if has:
            mapped = db.execute(
                "SELECT COUNT(*) FROM cowork_script_mapping WHERE status='active'"
            ).fetchone()[0]
            metrics["mapped_scripts"] = mapped
        db.close()
    except Exception:
        pass

    # Test results from latest self_test run
    try:
        db = get_db(GAPS_DB)
        row = db.execute("""
            SELECT SUM(CASE WHEN passed=1 THEN 1 ELSE 0 END) as ok,
                   COUNT(*) as total
            FROM self_test_results
            WHERE run_id = (SELECT MAX(id) FROM self_test_runs)
        """).fetchone()
        if row and row["total"]:
            metrics["test_pass_rate"] = round(row["ok"] / row["total"] * 100, 1)
            metrics["tests_passed"] = row["ok"]
            metrics["tests_total"] = row["total"]
        db.close()
    except Exception:
        pass
    return metrics


def collect_infra_metrics():
    """Collect infrastructure metrics."""
    metrics = {}

    # Database sizes
    for name, path in [("etoile", ETOILE_DB), ("gaps", GAPS_DB), ("jarvis", JARVIS_DB)]:
        if path.exists():
            size_mb = path.stat().st_size / (1024 * 1024)
            metrics[f"db_{name}_mb"] = round(size_mb, 1)

    # Disk space
    try:
        stat = os.statvfs("/") if sys.platform != "win32" else None
        if sys.platform == "win32":
            import ctypes
            free = ctypes.c_ulonglong()
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                "F:/", None, None, ctypes.pointer(free))
            metrics["disk_f_free_gb"] = round(free.value / (1024**3), 1)
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                "/\", None, None, ctypes.pointer(free))
            metrics["disk_c_free_gb"] = round(free.value / (1024**3), 1)
    except Exception:
        pass

    # Orchestrator task stats
    try:
        db = get_db(GAPS_DB)
        tasks = db.execute("""
            SELECT task_name, run_count, fail_count
            FROM orchestrator_schedule
        """).fetchall()
        total_runs = sum(t["run_count"] for t in tasks)
        total_fails = sum(t["fail_count"] for t in tasks)
        metrics["orchestrator_total_runs"] = total_runs
        metrics["orchestrator_fail_rate"] = round(
            total_fails / max(total_runs, 1) * 100, 1)
        db.close()
    except Exception:
        pass

    return metrics


def collect_all():
    """Collect all metrics."""
    all_metrics = {}
    all_metrics.update(collect_cluster_metrics())
    all_metrics.update(collect_dispatch_metrics())
    all_metrics.update(collect_trading_metrics())
    all_metrics.update(collect_script_metrics())
    all_metrics.update(collect_infra_metrics())
    return all_metrics


def store_snapshot(metrics):
    """Store metrics snapshot in DB."""
    db = get_db(GAPS_DB)
    init_metrics_db(db)
    ts = datetime.now().isoformat()
    for name, value in metrics.items():
        if isinstance(value, (int, float)):
            cat = name.split("_")[0]
            db.execute("""
                INSERT INTO metrics_snapshots (timestamp, category, metric_name, value)
                VALUES (?, ?, ?, ?)
            """, (ts, cat, name, value))
    db.commit()
    db.close()


def format_telegram_dashboard(metrics):
    """Format metrics as Telegram dashboard."""
    ts = datetime.now().strftime("%H:%M:%S")
    lines = [f"<b>JARVIS Metrics</b> <code>{ts}</code>"]

    # Cluster
    lines.append("")
    lines.append(f"<b>Cluster</b>: {metrics.get('cluster_online', '?')}/{metrics.get('cluster_total', '?')} online")
    for key in sorted(metrics):
        if key.startswith("heartbeat_lat_"):
            node = key.replace("heartbeat_lat_", "")
            lines.append(f"  {node}: {metrics[key]}ms")

    # Dispatch
    lines.append("")
    lines.append(f"<b>Dispatch</b>: {metrics.get('dispatch_success_pct', 0)}% ok | "
                 f"q={metrics.get('dispatch_avg_quality', 0)}% | "
                 f"{metrics.get('dispatch_avg_latency_ms', 0)}ms")

    # Crypto
    for key in sorted(metrics):
        if key.startswith("price_"):
            pair = key.replace("price_", "")
            change = metrics.get(f"change_{pair}", 0)
            arrow = "+" if change > 0 else ""
            lines.append(f"  {pair}: ${metrics[key]} ({arrow}{change:.2f}%)")

    # Scripts
    lines.append("")
    lines.append(f"<b>Scripts</b>: {metrics.get('total_scripts', '?')} | "
                 f"Tests: {metrics.get('test_pass_rate', '?')}%")

    # Infra
    lines.append(f"<b>Disk</b>: C={metrics.get('disk_c_free_gb', '?')}GB | "
                 f"F={metrics.get('disk_f_free_gb', '?')}GB")

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
    parser = argparse.ArgumentParser(description="Metrics Aggregator")
    parser.add_argument("--once", action="store_true", help="Collect metrics once")
    parser.add_argument("--watch", action="store_true", help="Continuous metrics")
    parser.add_argument("--interval", type=int, default=5, help="Interval (min)")
    parser.add_argument("--telegram", action="store_true", help="Send Telegram")
    parser.add_argument("--history", action="store_true", help="Show history")
    args = parser.parse_args()

    if not any([args.once, args.watch, args.telegram, args.history]):
        parser.print_help()
        sys.exit(1)

    if args.history:
        db = get_db(GAPS_DB)
        init_metrics_db(db)
        rows = db.execute("""
            SELECT timestamp, metric_name, value
            FROM metrics_snapshots
            ORDER BY id DESC LIMIT 50
        """).fetchall()
        for r in rows:
            print(f"  {r['timestamp'][:16]} {r['metric_name']:30} {r['value']}")
        db.close()
        return

    if args.once or args.telegram:
        metrics = collect_all()
        store_snapshot(metrics)
        print(json.dumps(metrics, indent=2))

        if args.telegram:
            msg = format_telegram_dashboard(metrics)
            send_telegram(msg)
            print("\nTelegram dashboard sent")
        return

    if args.watch:
        print(f"Metrics collection every {args.interval}m")
        while True:
            metrics = collect_all()
            store_snapshot(metrics)
            ts = datetime.now().strftime("%H:%M:%S")
            online = metrics.get("cluster_online", 0)
            dispatch = metrics.get("dispatch_success_pct", 0)
            print(f"[{ts}] Cluster {online}N | Dispatch {dispatch}% | "
                  f"{metrics.get('total_scripts', 0)} scripts")
            time.sleep(args.interval * 60)


if __name__ == "__main__":
    main()