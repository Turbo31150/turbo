#!/usr/bin/env python3
"""JARVIS Auto-Scan Daemon — autonomous system scanning + cluster-powered analysis.

Scans all subsystems, asks M1 for analysis, auto-fixes safe issues, reports.

Usage:
    python scripts/jarvis_auto_scan.py --once       # Single scan
    python scripts/jarvis_auto_scan.py --daemon      # Loop every 10min
    python scripts/jarvis_auto_scan.py --dry-run     # Scan without fixing
"""
from __future__ import annotations

import argparse
import glob as _glob
import json
import logging
import os
import re
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = ROOT / "data" / "auto_scan.db"
SCAN_INTERVAL = 600  # 10 minutes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "auto_scan.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("auto_scan")

_running = True
def _sig(s, f): global _running; _running = False
signal.signal(signal.SIGINT, _sig)
signal.signal(signal.SIGTERM, _sig)


def _init_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT, duration_ms REAL, issues_found INTEGER, issues_fixed INTEGER,
        health_score INTEGER, report TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS issues (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scan_id INTEGER, ts TEXT, category TEXT, severity TEXT,
        description TEXT, auto_fixed INTEGER DEFAULT 0, fix_result TEXT
    )""")
    conn.commit()
    return conn


def _http_get(url: str, timeout: float = 5.0):
    import urllib.request
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def _http_post(url: str, data: dict, timeout: float = 10.0):
    import urllib.request
    try:
        req = urllib.request.Request(url, data=json.dumps(data).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def _check_port(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def _ask_m1(prompt: str) -> str:
    """Ask M1/qwen3-8b for analysis."""
    if not _check_port("127.0.0.1", 1234):
        return "M1 offline"
    import urllib.request
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:1234/api/v1/chat",
            data=json.dumps({
                "model": "qwen3-8b",
                "input": f"/nothink\n{prompt}",
                "temperature": 0.2,
                "max_output_tokens": 512,
                "stream": False,
                "store": False,
            }).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())
        for item in reversed(data.get("output", [])):
            if item.get("type") == "message":
                content = item.get("content", "")
                if isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict) and c.get("type") == "output_text":
                            return c.get("text", "")[:500]
                        elif isinstance(c, str):
                            return c[:500]
                elif isinstance(content, str):
                    return content[:500]
        return "No response"
    except Exception as e:
        return f"M1 error: {e}"


def _notify(message: str):
    """Send notification via WS API (Telegram + Windows toast queue)."""
    _http_post("http://127.0.0.1:9742/api/notifications/push",
               {"title": "JARVIS Scan", "message": message[:400]})
    _http_post("http://127.0.0.1:9742/api/telegram/send",
               {"message": message[:2000]})


# -- Scanners ----------------------------------------------------------

def scan_cluster() -> list[dict]:
    issues: list[dict] = []
    nodes = [
        ("M1", "127.0.0.1", 1234),
        ("OL1", "127.0.0.1", 11434),
        ("M3", "192.168.1.113", 1234),
        ("M2", "192.168.1.26", 1234),
    ]
    for name, host, port in nodes:
        if not _check_port(host, port):
            sev = "critical" if name == "M1" else "warning"
            issues.append({"category": "cluster", "severity": sev,
                          "description": f"{name} ({host}:{port}) OFFLINE"})

    # Check M1 has models loaded
    if _check_port("127.0.0.1", 1234):
        data = _http_get("http://127.0.0.1:1234/api/v1/models")
        if data:
            loaded = sum(
                1 for m in data.get("data", [])
                if m.get("loaded_instances")
            )
            if loaded == 0:
                # Fallback: try a quick ping to verify model is really missing
                ping_resp = _http_post("http://127.0.0.1:1234/v1/chat/completions", {
                    "model": "qwen3-8b",
                    "messages": [{"role": "user", "content": "/nothink\nping"}],
                    "max_tokens": 1, "stream": False,
                })
                if not ping_resp or "error" in str(ping_resp).lower():
                    issues.append({"category": "cluster", "severity": "critical",
                                  "description": "M1: 0 modeles charges (qwen3-8b manquant)"})
    return issues


def scan_services() -> list[dict]:
    issues: list[dict] = []
    services = [
        ("WS", "127.0.0.1", 9742),
        ("OpenClaw", "127.0.0.1", 18789),
        ("Dashboard", "127.0.0.1", 8080),
    ]
    for name, host, port in services:
        if not _check_port(host, port):
            issues.append({"category": "service", "severity": "warning",
                          "description": f"{name} (:{port}) DOWN"})
    return issues


def scan_databases() -> list[dict]:
    issues: list[dict] = []
    data_dir = ROOT / "data"
    for db_name in ["etoile.db", "jarvis.db", "scheduler.db"]:
        db_path = data_dir / db_name
        if not db_path.exists():
            issues.append({"category": "database", "severity": "critical",
                          "description": f"{db_name} MISSING"})
            continue
        try:
            conn = sqlite3.connect(str(db_path))
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                issues.append({"category": "database", "severity": "critical",
                              "description": f"{db_name} integrity FAILED: {integrity}"})
            # Check for bloat (WAL size)
            size_mb = db_path.stat().st_size / (1024 * 1024)
            if size_mb > 50:
                issues.append({"category": "database", "severity": "warning",
                              "description": f"{db_name} large: {size_mb:.1f}MB (consider VACUUM)"})
            conn.close()
        except Exception as e:
            issues.append({"category": "database", "severity": "warning",
                          "description": f"{db_name} error: {e}"})
    return issues


def scan_gpu() -> list[dict]:
    issues: list[dict] = []
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,temperature.gpu,memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        for line in r.stdout.strip().split("\n"):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 4:
                temp = int(parts[1])
                vram_used = int(parts[2])
                vram_total = int(parts[3])
                if temp > 85:
                    issues.append({"category": "gpu", "severity": "critical",
                                  "description": f"GPU {parts[0]}: {temp}C OVERHEATING"})
                elif temp > 75:
                    issues.append({"category": "gpu", "severity": "warning",
                                  "description": f"GPU {parts[0]}: {temp}C warm"})
                if vram_total > 0 and vram_used / vram_total > 0.95:
                    issues.append({"category": "gpu", "severity": "warning",
                                  "description": f"GPU {parts[0]}: VRAM {vram_used}/{vram_total}MB (>95%)"})
    except Exception:
        issues.append({"category": "gpu", "severity": "info",
                      "description": "nvidia-smi unavailable"})
    return issues


def scan_disk() -> list[dict]:
    issues: list[dict] = []
    for drive in ("/\", "F:/"):
        try:
            total, used, free = shutil.disk_usage(drive)
            free_gb = free / (1024 ** 3)
            if free_gb < 5:
                issues.append({"category": "disk", "severity": "critical",
                              "description": f"{drive} only {free_gb:.1f}GB free"})
            elif free_gb < 20:
                issues.append({"category": "disk", "severity": "warning",
                              "description": f"{drive} {free_gb:.1f}GB free (low)"})
        except Exception:
            pass
    return issues


def scan_system() -> list[dict]:
    """Check CPU, RAM, and network reachability."""
    issues: list[dict] = []

    # --- CPU usage ---
    cpu_pct: float | None = None
    try:
        import psutil
        cpu_pct = psutil.cpu_percent(interval=1)
    except ImportError:
        try:
            r = subprocess.run(
                ["wmic", "cpu", "get", "loadpercentage"],
                capture_output=True, text=True, timeout=10,
            )
            for line in r.stdout.strip().splitlines():
                line = line.strip()
                if line.isdigit():
                    cpu_pct = float(line)
                    break
        except Exception:
            pass

    if cpu_pct is not None:
        if cpu_pct > 90:
            issues.append({"category": "system", "severity": "critical",
                          "description": f"CPU usage {cpu_pct:.0f}% (>90% critical)"})
        elif cpu_pct > 75:
            issues.append({"category": "system", "severity": "warning",
                          "description": f"CPU usage {cpu_pct:.0f}% (>75% warning)"})

    # --- RAM usage ---
    ram_pct: float | None = None
    try:
        import psutil
        mem = psutil.virtual_memory()
        ram_pct = mem.percent
    except ImportError:
        try:
            r = subprocess.run(
                ["wmic", "OS", "get", "FreePhysicalMemory,TotalVisibleMemorySize"],
                capture_output=True, text=True, timeout=10,
            )
            lines = [l.strip() for l in r.stdout.strip().splitlines() if l.strip()]
            # Header line then data line with two numbers
            for line in lines:
                parts = line.split()
                if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                    free_kb = int(parts[0])
                    total_kb = int(parts[1])
                    if total_kb > 0:
                        ram_pct = (1 - free_kb / total_kb) * 100
                    break
        except Exception:
            pass

    if ram_pct is not None:
        if ram_pct > 90:
            issues.append({"category": "system", "severity": "critical",
                          "description": f"RAM usage {ram_pct:.0f}% (>90% critical)"})
        elif ram_pct > 80:
            issues.append({"category": "system", "severity": "warning",
                          "description": f"RAM usage {ram_pct:.0f}% (>80% warning)"})

    # --- Network reachability ---
    hosts = [
        ("internet", "8.8.8.8", 53, "critical"),
        ("M2-node", "192.168.1.26", 1234, "warning"),
        ("M3-node", "192.168.1.113", 1234, "warning"),
    ]
    for label, host, port, sev in hosts:
        try:
            with socket.create_connection((host, port), timeout=3):
                pass
        except Exception:
            issues.append({"category": "system", "severity": sev,
                          "description": f"Network: {label} ({host}:{port}) unreachable"})

    return issues


def scan_logs() -> list[dict]:
    """Scan recent log files for ERROR/CRITICAL entries from the last hour."""
    issues: list[dict] = []
    log_dir = ROOT / "logs"
    if not log_dir.is_dir():
        return issues

    cutoff = datetime.now() - timedelta(hours=1)
    total_errors = 0
    total_criticals = 0
    files_checked = 0

    # Patterns to match common log timestamp formats and severity
    # e.g. "2026-03-10 14:30:00 [ERROR] ..." or "2026-03-10 14:30:00,123 [CRITICAL] ..."
    ts_pattern = re.compile(
        r"(\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2})"
    )
    severity_pattern = re.compile(
        r"\b(ERROR|CRITICAL)\b", re.IGNORECASE
    )

    for log_file in sorted(log_dir.glob("*.log")):
        try:
            # Read last 50 lines efficiently
            with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                try:
                    # Seek to end and read backwards for efficiency on large files
                    lines = f.readlines()
                    tail = lines[-50:] if len(lines) > 50 else lines
                except Exception:
                    continue

            files_checked += 1
            for line in tail:
                sev_match = severity_pattern.search(line)
                if not sev_match:
                    continue
                # Check if the timestamp is within the last hour
                ts_match = ts_pattern.search(line)
                if ts_match:
                    try:
                        ts_str = ts_match.group(1).replace("T", " ")
                        line_ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                        if line_ts < cutoff:
                            continue  # Too old
                    except ValueError:
                        pass  # Can't parse timestamp, count it anyway
                sev = sev_match.group(1).upper()
                if sev == "ERROR":
                    total_errors += 1
                elif sev == "CRITICAL":
                    total_criticals += 1
        except Exception:
            continue

    error_count = total_errors + total_criticals
    if error_count > 30:
        issues.append({"category": "logs", "severity": "critical",
                      "description": f"High error rate in logs: {total_errors} ERROR + "
                                     f"{total_criticals} CRITICAL in last hour "
                                     f"({files_checked} log files)"})
    elif error_count > 10:
        issues.append({"category": "logs", "severity": "warning",
                      "description": f"Elevated error rate in logs: {total_errors} ERROR + "
                                     f"{total_criticals} CRITICAL in last hour "
                                     f"({files_checked} log files)"})

    return issues


def scan_dispatch_quality() -> list[dict]:
    issues: list[dict] = []
    try:
        db_path = ROOT / "data" / "etoile.db"
        if not db_path.exists():
            return issues
        conn = sqlite3.connect(str(db_path))
        # Check if table exists before querying
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        if "dispatch_pipeline_log" not in tables:
            conn.close()
            return issues
        # Check recent dispatch quality
        rows = conn.execute(
            "SELECT quality, node FROM dispatch_pipeline_log ORDER BY id DESC LIMIT 20"
        ).fetchall()
        if rows:
            valid_q = [r[0] for r in rows if r[0] is not None]
            if valid_q:
                avg_q = sum(valid_q) / len(valid_q)
                if avg_q < 0.5:
                    issues.append({"category": "dispatch", "severity": "warning",
                                  "description": f"Dispatch quality low: {avg_q:.2f} (last 20)"})
            # Node distribution
            node_counts: dict[str, int] = {}
            for _, node in rows:
                if node:
                    node_counts[node] = node_counts.get(node, 0) + 1
            for node, count in node_counts.items():
                if count > 15:
                    issues.append({"category": "dispatch", "severity": "info",
                                  "description": f"Dispatch concentrated on {node}: {count}/20"})
        conn.close()
    except Exception:
        pass
    return issues


# -- Auto-fix (safe operations only) -----------------------------------

def auto_fix(issue: dict, dry_run: bool = False) -> str:
    desc = issue["description"]

    if "M1: 0 modeles charges" in desc:
        if dry_run:
            return "[DRY] Would load qwen3-8b on M1"
        log.info("Auto-fix: loading qwen3-8b on M1...")
        resp = _http_post("http://127.0.0.1:1234/v1/chat/completions", {
            "model": "qwen3-8b",
            "messages": [{"role": "user", "content": "/nothink\nping"}],
            "max_tokens": 1, "stream": False,
        }, timeout=60)
        return "qwen3-8b loaded" if resp and resp.get("choices") else "load attempted"

    if "consider VACUUM" in desc:
        if dry_run:
            return "[DRY] Would VACUUM database"
        db_name = desc.split()[0]
        db_path = ROOT / "data" / db_name
        try:
            conn = sqlite3.connect(str(db_path))
            conn.execute("VACUUM")
            conn.close()
            return f"VACUUM {db_name} done"
        except Exception as e:
            return f"VACUUM failed: {e}"

    return ""


# -- Main scan cycle ----------------------------------------------------

def run_scan(dry_run: bool = False) -> dict:
    t0 = time.time()
    log.info("=== Auto-Scan cycle start ===")

    all_issues: list[dict] = []
    all_issues.extend(scan_cluster())
    all_issues.extend(scan_services())
    all_issues.extend(scan_databases())
    all_issues.extend(scan_gpu())
    all_issues.extend(scan_disk())
    all_issues.extend(scan_system())
    all_issues.extend(scan_logs())
    all_issues.extend(scan_dispatch_quality())

    # Feed decision engine with signals
    if not dry_run:
        try:
            for issue in all_issues:
                _http_post("http://127.0.0.1:9742/api/decisions/signal", {
                    "source": "auto_scan",
                    "severity": issue["severity"],
                    "category": issue["category"],
                    "description": issue["description"],
                })
        except Exception:
            pass  # WS might not be running

    # Auto-fix fixable issues
    fixed = 0
    for issue in all_issues:
        result = auto_fix(issue, dry_run)
        if result:
            issue["auto_fixed"] = 1
            issue["fix_result"] = result
            fixed += 1
            log.info("  Fix: %s -> %s", issue["description"][:60], result)

    duration_ms = (time.time() - t0) * 1000

    # Calculate health score
    critical = sum(1 for i in all_issues if i["severity"] == "critical")
    warnings = sum(1 for i in all_issues if i["severity"] == "warning")
    health = max(0, 100 - critical * 20 - warnings * 5)

    # Ask M1 for analysis if issues found
    m1_analysis = ""
    if all_issues and not dry_run and _check_port("127.0.0.1", 1234):
        summary = "; ".join(
            f"[{i['severity']}] {i['description']}" for i in all_issues[:10]
        )
        m1_analysis = _ask_m1(
            f"JARVIS scan a trouve {len(all_issues)} problemes. "
            f"Analyse et suggere des actions:\n{summary}"
        )
        log.info("M1 analysis: %s", m1_analysis[:200])

    # Save to DB
    conn = _init_db()
    report_data = {
        "issues": all_issues,
        "m1_analysis": m1_analysis,
        "health_score": health,
        "duration_ms": round(duration_ms, 1),
    }
    cur = conn.execute(
        "INSERT INTO scans (ts, duration_ms, issues_found, issues_fixed, health_score, report) "
        "VALUES (?,?,?,?,?,?)",
        (datetime.now().isoformat(), duration_ms, len(all_issues), fixed,
         health, json.dumps(report_data))
    )
    scan_id = cur.lastrowid
    for issue in all_issues:
        conn.execute(
            "INSERT INTO issues (scan_id, ts, category, severity, description, "
            "auto_fixed, fix_result) VALUES (?,?,?,?,?,?,?)",
            (scan_id, datetime.now().isoformat(), issue["category"],
             issue["severity"], issue["description"],
             issue.get("auto_fixed", 0), issue.get("fix_result", ""))
        )
    conn.commit()
    conn.close()

    # Notify
    if health >= 95:
        grade = "A+"
    elif health >= 85:
        grade = "A"
    elif health >= 70:
        grade = "B"
    elif health >= 50:
        grade = "C"
    else:
        grade = "F"

    summary_msg = (
        f"[Scan] {grade} ({health}/100) | "
        f"{len(all_issues)} issues, {fixed} fixed | {duration_ms:.0f}ms"
    )
    if all_issues:
        summary_msg += "\n" + "\n".join(
            f"- [{i['severity']}] {i['description'][:60]}"
            for i in all_issues[:5]
        )
    if m1_analysis:
        summary_msg += f"\n\nM1: {m1_analysis[:200]}"

    log.info("Grade: %s (%d/100) | %d issues, %d fixed",
             grade, health, len(all_issues), fixed)

    if not dry_run:
        _notify(summary_msg)

    log.info("=== Auto-Scan cycle end ===")
    return report_data


def main():
    p = argparse.ArgumentParser(description="JARVIS Auto-Scan Daemon")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="Single scan")
    mode.add_argument("--daemon", action="store_true", help="Loop every 10min")
    p.add_argument("--dry-run", action="store_true", help="Scan without fixing")
    args = p.parse_args()

    if args.once:
        result = run_scan(dry_run=args.dry_run)
        sys.stdout.buffer.write(json.dumps(result, indent=2, ensure_ascii=True).encode("utf-8"))
        sys.stdout.buffer.write(b"\n")
    elif args.daemon:
        log.info("Daemon mode — interval %ds", SCAN_INTERVAL)
        while _running:
            try:
                run_scan(dry_run=args.dry_run)
            except Exception as e:
                log.error("Scan error: %s", e)
            for _ in range(SCAN_INTERVAL):
                if not _running:
                    break
                time.sleep(1)
        log.info("Daemon stopped")


if __name__ == "__main__":
    main()
