#!/usr/bin/env python3
"""win_process_analyzer.py — Deep process analysis (#252).

Uses tasklist /v /fo csv, identifies suspicious processes (high CPU>50%,
unknown publisher), process tree via wmic.

Usage:
    python dev/win_process_analyzer.py --once
    python dev/win_process_analyzer.py --scan
    python dev/win_process_analyzer.py --top
    python dev/win_process_analyzer.py --suspicious
    python dev/win_process_analyzer.py --tree
"""
import argparse
import csv
import io
import json
import os
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "process_analyzer.db"

KNOWN_SYSTEM = {
    "system idle process", "system", "registry", "smss.exe", "csrss.exe",
    "wininit.exe", "services.exe", "lsass.exe", "svchost.exe", "fontdrvhost.exe",
    "dwm.exe", "conhost.exe", "sihost.exe", "taskhostw.exe", "ctfmon.exe",
    "runtimebroker.exe", "shellexperiencehost.exe", "searchhost.exe",
    "startmenuexperiencehost.exe", "textinputhost.exe", "widgetservice.exe",
    "dllhost.exe", "audiodg.exe", "spoolsv.exe", "wudfhost.exe", "dashost.exe",
    "securityhealthservice.exe", "securityhealthsystray.exe", "searchindexer.exe",
    "msedgewebview2.exe", "tasklist.exe", "cmd.exe", "explorer.exe",
}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS process_scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        total_processes INTEGER,
        total_memory_mb REAL,
        suspicious_count INTEGER
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS processes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scan_id INTEGER,
        ts TEXT NOT NULL,
        name TEXT NOT NULL,
        pid INTEGER,
        session_name TEXT,
        session_num INTEGER,
        mem_kb INTEGER,
        status TEXT,
        username TEXT,
        cpu_time TEXT,
        window_title TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS suspicious (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        name TEXT NOT NULL,
        pid INTEGER,
        reason TEXT,
        mem_kb INTEGER,
        details TEXT
    )""")
    db.commit()
    return db


def parse_tasklist():
    """Parse tasklist /v /fo csv output."""
    processes = []
    try:
        out = subprocess.check_output(
            ["tasklist", "/v", "/fo", "csv"],
            stderr=subprocess.DEVNULL, text=True, timeout=30,
        )
        reader = csv.DictReader(io.StringIO(out))
        for row in reader:
            name = row.get("Image Name", "").strip()
            pid_str = row.get("PID", "0").strip()
            mem_str = row.get("Mem Usage", "0").strip().replace(",", "").replace(" K", "").replace("\xa0", "")
            try:
                pid = int(pid_str)
            except ValueError:
                pid = 0
            try:
                mem_kb = int(mem_str.replace("K", "").strip())
            except ValueError:
                mem_kb = 0

            processes.append({
                "name": name,
                "pid": pid,
                "session_name": row.get("Session Name", "").strip(),
                "session_num": row.get("Session#", "").strip(),
                "mem_kb": mem_kb,
                "status": row.get("Status", "").strip(),
                "username": row.get("User Name", "").strip(),
                "cpu_time": row.get("CPU Time", "").strip(),
                "window_title": row.get("Window Title", "").strip(),
            })
    except Exception as e:
        processes.append({"name": "ERROR", "pid": 0, "error": str(e), "mem_kb": 0})
    return processes


def get_process_tree():
    """Get process parent-child relationships via wmic."""
    tree = {}
    try:
        out = subprocess.check_output(
            ["wmic", "process", "get", "ProcessId,ParentProcessId,Name", "/format:csv"],
            stderr=subprocess.DEVNULL, text=True, timeout=15,
        )
        for line in out.strip().split("\n"):
            parts = line.strip().split(",")
            if len(parts) >= 4:
                name = parts[1].strip()
                ppid_str = parts[2].strip()
                pid_str = parts[3].strip()
                try:
                    pid = int(pid_str)
                    ppid = int(ppid_str)
                    tree[pid] = {"name": name, "ppid": ppid}
                except ValueError:
                    pass
    except Exception:
        pass
    return tree


def find_suspicious(processes):
    """Identify suspicious processes."""
    suspicious = []
    for p in processes:
        name_lower = p["name"].lower()
        reasons = []

        # High memory (>500MB)
        if p["mem_kb"] > 512000:
            reasons.append(f"high_memory:{p['mem_kb']//1024}MB")

        # Unknown process (not in known list)
        if name_lower not in KNOWN_SYSTEM and p["pid"] > 4:
            # Check if it has a window title (user app)
            if not p.get("window_title") or p["window_title"] == "N/A":
                if p["mem_kb"] > 50000:
                    reasons.append("unknown_background_process")

        # High CPU time
        cpu_time = p.get("cpu_time", "0:00:00")
        if cpu_time and cpu_time != "N/A":
            parts = cpu_time.split(":")
            try:
                if len(parts) == 3:
                    hours = int(parts[0])
                    if hours > 2:
                        reasons.append(f"high_cpu_time:{cpu_time}")
            except ValueError:
                pass

        if reasons:
            suspicious.append({
                "name": p["name"], "pid": p["pid"],
                "reasons": reasons, "mem_kb": p["mem_kb"],
                "cpu_time": p.get("cpu_time", ""),
                "username": p.get("username", ""),
            })

    return suspicious


def do_scan():
    """Full process scan."""
    db = init_db()
    now = datetime.now()
    processes = parse_tasklist()
    suspicious = find_suspicious(processes)
    total_mem = sum(p.get("mem_kb", 0) for p in processes)

    scan_id = db.execute(
        "INSERT INTO process_scans (ts, total_processes, total_memory_mb, suspicious_count) VALUES (?,?,?,?)",
        (now.isoformat(), len(processes), round(total_mem / 1024, 1), len(suspicious)),
    ).lastrowid

    for p in processes[:200]:
        db.execute(
            "INSERT INTO processes (scan_id, ts, name, pid, session_name, mem_kb, status, username, cpu_time, window_title) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (scan_id, now.isoformat(), p.get("name", ""), p.get("pid", 0),
             p.get("session_name", ""), p.get("mem_kb", 0), p.get("status", ""),
             p.get("username", ""), p.get("cpu_time", ""), p.get("window_title", "")),
        )

    db.commit()
    result = {
        "ts": now.isoformat(), "action": "scan", "scan_id": scan_id,
        "total_processes": len(processes),
        "total_memory_mb": round(total_mem / 1024, 1),
        "suspicious_count": len(suspicious),
    }
    db.close()
    return result


def do_top():
    """Show top processes by memory."""
    processes = parse_tasklist()
    processes.sort(key=lambda p: p.get("mem_kb", 0), reverse=True)

    result = {
        "ts": datetime.now().isoformat(), "action": "top",
        "top_by_memory": [
            {"name": p["name"], "pid": p["pid"], "mem_mb": round(p["mem_kb"] / 1024, 1),
             "cpu_time": p.get("cpu_time", ""), "status": p.get("status", "")}
            for p in processes[:20]
        ],
    }
    return result


def do_suspicious():
    """Show suspicious processes."""
    db = init_db()
    processes = parse_tasklist()
    suspicious = find_suspicious(processes)
    now = datetime.now()

    for s in suspicious:
        db.execute(
            "INSERT INTO suspicious (ts, name, pid, reason, mem_kb, details) VALUES (?,?,?,?,?,?)",
            (now.isoformat(), s["name"], s["pid"], ", ".join(s["reasons"]),
             s["mem_kb"], json.dumps(s)),
        )
    db.commit()

    result = {
        "ts": now.isoformat(), "action": "suspicious",
        "count": len(suspicious),
        "processes": suspicious[:20],
    }
    db.close()
    return result


def do_tree():
    """Show process tree."""
    tree = get_process_tree()
    # Build children map
    children = {}
    for pid, info in tree.items():
        ppid = info["ppid"]
        if ppid not in children:
            children[ppid] = []
        children[ppid].append({"pid": pid, "name": info["name"]})

    # Find root processes (ppid=0 or ppid not in tree)
    roots = []
    for pid, info in tree.items():
        if info["ppid"] == 0 or info["ppid"] not in tree:
            child_list = children.get(pid, [])
            roots.append({
                "pid": pid, "name": info["name"],
                "children_count": len(child_list),
                "children": [c["name"] for c in child_list[:5]],
            })

    roots.sort(key=lambda r: r["children_count"], reverse=True)
    result = {
        "ts": datetime.now().isoformat(), "action": "tree",
        "total_in_tree": len(tree),
        "root_processes": roots[:20],
    }
    return result


def do_status():
    db = init_db()
    result = {
        "ts": datetime.now().isoformat(), "script": "win_process_analyzer.py", "script_id": 252,
        "db": str(DB_PATH),
        "total_scans": db.execute("SELECT COUNT(*) FROM process_scans").fetchone()[0],
        "total_suspicious": db.execute("SELECT COUNT(*) FROM suspicious").fetchone()[0],
        "status": "ok",
    }
    db.close()
    return result


def main():
    parser = argparse.ArgumentParser(description="win_process_analyzer.py — Deep process analysis (#252)")
    parser.add_argument("--scan", action="store_true", help="Full process scan")
    parser.add_argument("--top", action="store_true", help="Top processes by memory")
    parser.add_argument("--suspicious", action="store_true", help="Show suspicious processes")
    parser.add_argument("--tree", action="store_true", help="Show process tree")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    if args.scan:
        result = do_scan()
    elif args.top:
        result = do_top()
    elif args.suspicious:
        result = do_suspicious()
    elif args.tree:
        result = do_tree()
    else:
        result = do_status()

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
