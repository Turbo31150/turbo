#!/usr/bin/env python3
"""win_dns_cache_manager.py — Gestionnaire cache DNS Windows.

Monitore, flush, statistiques resolution.

Usage:
    python dev/win_dns_cache_manager.py --once
    python dev/win_dns_cache_manager.py --show
    python dev/win_dns_cache_manager.py --flush
    python dev/win_dns_cache_manager.py --stats
"""
import argparse
import json
import os
import socket
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "dns_cache_manager.db"
TEST_DOMAINS = ["google.com", "github.com", "pypi.org", "anthropic.com", "microsoft.com"]


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS dns_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, cache_entries INTEGER, avg_resolve_ms REAL,
        slowest_domain TEXT, slowest_ms REAL)""")
    db.commit()
    return db


def get_dns_cache_count():
    try:
        out = subprocess.run(
            ["bash", "-Command",
             "(Get-DnsClientCache | Measure-Object).Count"],
            capture_output=True, text=True, timeout=10
        )
        return int(out.stdout.strip() or "0")
    except Exception:
        return -1


def measure_dns_resolution():
    results = []
    for domain in TEST_DOMAINS:
        try:
            start = time.time()
            socket.getaddrinfo(domain, 80, socket.AF_INET)
            ms = (time.time() - start) * 1000
            results.append({"domain": domain, "resolve_ms": round(ms, 1), "status": "ok"})
        except Exception:
            results.append({"domain": domain, "resolve_ms": -1, "status": "fail"})
    return results


def do_status():
    db = init_db()
    cache_count = get_dns_cache_count()
    resolutions = measure_dns_resolution()

    ok_res = [r for r in resolutions if r["status"] == "ok"]
    avg_ms = sum(r["resolve_ms"] for r in ok_res) / max(len(ok_res), 1)
    slowest = max(ok_res, key=lambda x: x["resolve_ms"]) if ok_res else {"domain": "N/A", "resolve_ms": 0}

    db.execute("INSERT INTO dns_stats (ts, cache_entries, avg_resolve_ms, slowest_domain, slowest_ms) VALUES (?,?,?,?,?)",
               (time.time(), cache_count, avg_ms, slowest["domain"], slowest["resolve_ms"]))
    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "cache_entries": cache_count,
        "avg_resolve_ms": round(avg_ms, 1),
        "resolutions": resolutions,
        "slowest": slowest,
        "recommendation": "Consider flushing DNS cache" if cache_count > 1000 else "Cache size OK",
    }


def main():
    parser = argparse.ArgumentParser(description="Windows DNS Cache Manager")
    parser.add_argument("--once", "--show", action="store_true", help="Show status")
    parser.add_argument("--flush", action="store_true", help="Flush cache")
    parser.add_argument("--stats", action="store_true", help="Stats")
    parser.add_argument("--monitor", action="store_true", help="Monitor")
    args = parser.parse_args()
    print(json.dumps(do_status(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
