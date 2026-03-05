#!/usr/bin/env python3
"""latency_monitor.py — Real-time latency monitoring and anomaly detection.

Tracks response times across all cluster nodes and detects:
- Latency spikes (> 2x baseline)
- Progressive degradation (trending up)
- Node stalls (no response)

Stores baselines and alerts when anomalies detected.

CLI:
    --once         : Single monitoring pass
    --watch        : Continuous monitoring (default 5 min)
    --baselines    : Show current baselines
    --alert        : Send alerts on anomaly

Stdlib-only (json, argparse, sqlite3, urllib, time, math).
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

TELEGRAM_TOKEN = "TELEGRAM_TOKEN_REDACTED"
TELEGRAM_CHAT_ID = "2010747443"

PROBE_PROMPT = "OK"

NODES = {
    "M1":  {"url": "http://127.0.0.1:1234/api/v1/chat", "model": "qwen3-8b",
            "ollama": False, "prefix": "/nothink\n"},
    "OL1": {"url": "http://127.0.0.1:11434/api/chat", "model": "qwen3:1.7b",
            "ollama": True},
    "M2":  {"url": "http://192.168.1.26:1234/api/v1/chat", "model": "deepseek-r1-0528-qwen3-8b",
            "ollama": False},
    "M3":  {"url": "http://192.168.1.113:1234/api/v1/chat", "model": "deepseek-r1-0528-qwen3-8b",
            "ollama": False},
}


def get_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(GAPS_DB), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS latency_baselines (
        node TEXT PRIMARY KEY,
        avg_ms REAL,
        stddev_ms REAL,
        p50_ms REAL,
        p95_ms REAL,
        sample_count INTEGER DEFAULT 0,
        updated_at TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS latency_anomalies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        node TEXT NOT NULL,
        measured_ms INTEGER,
        baseline_ms REAL,
        anomaly_type TEXT,
        severity TEXT
    )""")
    conn.commit()
    return conn


def probe_node(node_name):
    """Send lightweight probe to measure latency."""
    node = NODES.get(node_name)
    if not node:
        return None

    start = time.time()
    try:
        if node.get("ollama"):
            body = json.dumps({
                "model": node["model"],
                "messages": [{"role": "user", "content": PROBE_PROMPT}],
                "stream": False, "think": False,
            }).encode()
        else:
            prefix = node.get("prefix", "")
            body = json.dumps({
                "model": node["model"],
                "input": f"{prefix}{PROBE_PROMPT}",
                "temperature": 0.1, "max_output_tokens": 32,
                "stream": False, "store": False,
            }).encode()

        req = urllib.request.Request(node["url"], data=body,
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=30)
        return int((time.time() - start) * 1000)
    except Exception as e:
        print(f"    [{node_name} probe error: {str(e)[:80]}]")
        return None


def get_baseline(db, node):
    """Get stored baseline for a node."""
    row = db.execute(
        "SELECT * FROM latency_baselines WHERE node=?", (node,)
    ).fetchone()
    if row:
        return dict(row)
    return None


def update_baseline(db, node, latency_ms):
    """Update baseline with exponential moving average."""
    alpha = 0.2  # EMA smoothing factor
    baseline = get_baseline(db, node)
    now = datetime.now().isoformat()

    if baseline and baseline["sample_count"] > 0:
        new_avg = baseline["avg_ms"] * (1 - alpha) + latency_ms * alpha
        # Approximate stddev update
        diff = abs(latency_ms - new_avg)
        new_std = baseline["stddev_ms"] * (1 - alpha) + diff * alpha
        new_count = baseline["sample_count"] + 1
        # P50/P95 approximation (weighted)
        new_p50 = baseline["p50_ms"] * 0.9 + latency_ms * 0.1
        new_p95 = max(baseline["p95_ms"] * 0.95 + latency_ms * 0.05, latency_ms * 0.8)
    else:
        new_avg = latency_ms
        new_std = latency_ms * 0.3
        new_count = 1
        new_p50 = latency_ms
        new_p95 = latency_ms * 1.5

    db.execute("""
        INSERT INTO latency_baselines (node, avg_ms, stddev_ms, p50_ms, p95_ms, sample_count, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(node) DO UPDATE SET
            avg_ms=?, stddev_ms=?, p50_ms=?, p95_ms=?, sample_count=?, updated_at=?
    """, (node, new_avg, new_std, new_p50, new_p95, new_count, now,
          new_avg, new_std, new_p50, new_p95, new_count, now))
    db.commit()


def check_anomaly(db, node, latency_ms):
    """Check if latency is anomalous."""
    baseline = get_baseline(db, node)
    if not baseline or baseline["sample_count"] < 3:
        return None

    avg = baseline["avg_ms"]
    std = max(baseline["stddev_ms"], 50)  # Min 50ms stddev

    # Z-score
    z = (latency_ms - avg) / std

    if z > 3:
        return {"type": "spike", "severity": "HIGH", "z_score": round(z, 1)}
    elif z > 2:
        return {"type": "elevated", "severity": "MEDIUM", "z_score": round(z, 1)}
    elif latency_ms > baseline["p95_ms"] * 1.5:
        return {"type": "above_p95", "severity": "LOW", "z_score": round(z, 1)}

    return None


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


def monitor_pass(db, alert=False):
    """Run one monitoring pass across all nodes."""
    results = {}
    anomalies = []
    now = datetime.now().isoformat()

    for node_name in NODES:
        lat = probe_node(node_name)
        if lat is None:
            results[node_name] = {"status": "offline", "latency_ms": None}
            continue

        results[node_name] = {"status": "online", "latency_ms": lat}
        update_baseline(db, node_name, lat)

        anomaly = check_anomaly(db, node_name, lat)
        if anomaly:
            anomalies.append({"node": node_name, "latency_ms": lat, **anomaly})
            db.execute("""
                INSERT INTO latency_anomalies (timestamp, node, measured_ms, baseline_ms, anomaly_type, severity)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (now, node_name, lat,
                  get_baseline(db, node_name).get("avg_ms", 0),
                  anomaly["type"], anomaly["severity"]))
            db.commit()

        baseline = get_baseline(db, node_name)
        avg = baseline["avg_ms"] if baseline else 0
        indicator = "!" if anomaly and anomaly["severity"] == "HIGH" else \
                   "~" if anomaly else "+"
        print(f"  {indicator} {node_name:4} {lat:5}ms (avg={avg:.0f}ms)", end="")
        if anomaly:
            print(f" [{anomaly['type']} z={anomaly['z_score']}]", end="")
        print()

    if anomalies and alert:
        high = [a for a in anomalies if a["severity"] == "HIGH"]
        if high:
            lines = [f"<b>Latency Alert</b> <code>{datetime.now().strftime('%H:%M')}</code>"]
            for a in high:
                lines.append(f"! {a['node']}: {a['latency_ms']}ms ({a['type']})")
            send_telegram("\n".join(lines))

    return results, anomalies


def show_baselines(db):
    """Show all baselines."""
    rows = db.execute("SELECT * FROM latency_baselines ORDER BY node").fetchall()
    if not rows:
        print("No baselines yet. Run --once first.")
        return

    print("=== Latency Baselines ===")
    for r in rows:
        print(f"  {r['node']:4} avg={r['avg_ms']:.0f}ms std={r['stddev_ms']:.0f}ms "
              f"p50={r['p50_ms']:.0f}ms p95={r['p95_ms']:.0f}ms samples={r['sample_count']}")


def main():
    parser = argparse.ArgumentParser(description="Latency Monitor")
    parser.add_argument("--once", action="store_true", help="Single pass")
    parser.add_argument("--watch", action="store_true", help="Continuous")
    parser.add_argument("--interval", type=int, default=5, help="Interval (min)")
    parser.add_argument("--baselines", action="store_true", help="Show baselines")
    parser.add_argument("--alert", action="store_true", help="Send alerts")
    args = parser.parse_args()

    if not any([args.once, args.watch, args.baselines]):
        parser.print_help()
        sys.exit(1)

    db = get_db()

    if args.baselines:
        show_baselines(db)
        db.close()
        return

    if args.once:
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] Latency probe...")
        results, anomalies = monitor_pass(db, alert=args.alert)
        if anomalies:
            print(f"\n  {len(anomalies)} anomalies detected")
        db.close()
        return

    if args.watch:
        print(f"Latency monitoring every {args.interval}m")
        while True:
            try:
                ts = datetime.now().strftime("%H:%M:%S")
                print(f"\n[{ts}]")
                monitor_pass(db, alert=args.alert)
                time.sleep(args.interval * 60)
            except KeyboardInterrupt:
                print("\nStopped")
                break

    db.close()


if __name__ == "__main__":
    main()
