#!/usr/bin/env python3
"""Resource Contention Monitor — Detect GPU/CPU contention between scripts.

Monitors running Python processes, detects GPU memory contention via nvidia-smi,
and alerts when too many scripts run simultaneously or resources are over-committed.

Usage:
    python resource_contention_monitor.py --once
    python resource_contention_monitor.py --once --watch --threshold 80
"""

import argparse
import datetime
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import glob


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "cowork_gaps.db")


def init_db(conn):
    """Initialize SQLite tables for resource monitoring."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS resource_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            cpu_percent REAL,
            memory_percent REAL,
            python_processes INTEGER,
            gpu_count INTEGER,
            gpu_memory_used_mb REAL,
            gpu_memory_total_mb REAL,
            gpu_utilization_percent REAL,
            contention_detected INTEGER DEFAULT 0,
            alerts TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS contention_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            alert_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            message TEXT,
            resource TEXT,
            current_value REAL,
            threshold_value REAL
        )
    """)
    conn.commit()


def get_python_processes(verbose=False):
    """List running Python processes with resource info."""
    processes = []
    try:
        # Use tasklist on Windows
        result = subprocess.run(
            ["tasklist", "/FO", "CSV", "/FI", "IMAGENAME eq python.exe", "/V"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            for line in lines[1:]:  # Skip header
                try:
                    parts = line.strip('"').split('","')
                    if len(parts) >= 5:
                        processes.append({
                            "name": parts[0],
                            "pid": int(parts[1]) if parts[1].isdigit() else 0,
                            "mem_usage": parts[4].strip() if len(parts) > 4 else "N/A",
                            "status": parts[5].strip() if len(parts) > 5 else "N/A"
                        })
                except (ValueError, IndexError):
                    continue

        # Also check for python3.exe and pythonw.exe
        for exe in ["python3.exe", "pythonw.exe"]:
            result2 = subprocess.run(
                ["tasklist", "/FO", "CSV", "/FI", f"IMAGENAME eq {exe}", "/V"],
                capture_output=True, text=True, timeout=10
            )
            if result2.returncode == 0:
                lines2 = result2.stdout.strip().split("\n")
                for line in lines2[1:]:
                    try:
                        parts = line.strip('"').split('","')
                        if len(parts) >= 5 and "INFO" not in line:
                            processes.append({
                                "name": parts[0],
                                "pid": int(parts[1]) if parts[1].isdigit() else 0,
                                "mem_usage": parts[4].strip() if len(parts) > 4 else "N/A",
                                "status": parts[5].strip() if len(parts) > 5 else "N/A"
                            })
                    except (ValueError, IndexError):
                        continue

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        if verbose:
            print(f"  Warning: Could not list Python processes: {e}")
    return processes


def get_cpu_usage(verbose=False):
    """Get CPU usage percentage."""
    try:
        # Use wmic on Windows
        result = subprocess.run(
            ["wmic", "cpu", "get", "loadpercentage", "/value"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            match = re.search(r"LoadPercentage=(\d+)", result.stdout)
            if match:
                return float(match.group(1))
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    # Fallback: try PowerShell
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "(Get-CimInstance -ClassName Win32_Processor).LoadPercentage"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0 and result.stdout.strip().isdigit():
            return float(result.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    return -1.0


def get_memory_usage(verbose=False):
    """Get system memory usage percentage."""
    try:
        result = subprocess.run(
            ["wmic", "OS", "get",
             "FreePhysicalMemory,TotalVisibleMemorySize", "/value"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            free_match = re.search(r"FreePhysicalMemory=(\d+)", result.stdout)
            total_match = re.search(r"TotalVisibleMemorySize=(\d+)", result.stdout)
            if free_match and total_match:
                free_kb = int(free_match.group(1))
                total_kb = int(total_match.group(1))
                used_pct = (1 - free_kb / total_kb) * 100 if total_kb > 0 else 0
                return round(used_pct, 1)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return -1.0


def get_gpu_info(verbose=False):
    """Get GPU information via nvidia-smi."""
    gpu_info = {
        "gpus": [],
        "total_memory_mb": 0,
        "used_memory_mb": 0,
        "avg_utilization": 0,
        "gpu_count": 0,
        "available": False
    }

    try:
        result = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=index,name,memory.used,memory.total,utilization.gpu,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            gpu_info["available"] = True
            total_util = 0

            for line in result.stdout.strip().split("\n"):
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 6:
                    try:
                        gpu = {
                            "index": int(parts[0]),
                            "name": parts[1],
                            "memory_used_mb": float(parts[2]),
                            "memory_total_mb": float(parts[3]),
                            "utilization_percent": float(parts[4]),
                            "temperature_c": float(parts[5])
                        }
                        gpu["memory_percent"] = round(
                            gpu["memory_used_mb"] / gpu["memory_total_mb"] * 100, 1
                        ) if gpu["memory_total_mb"] > 0 else 0
                        gpu_info["gpus"].append(gpu)
                        gpu_info["total_memory_mb"] += gpu["memory_total_mb"]
                        gpu_info["used_memory_mb"] += gpu["memory_used_mb"]
                        total_util += gpu["utilization_percent"]
                    except (ValueError, IndexError):
                        continue

            gpu_info["gpu_count"] = len(gpu_info["gpus"])
            if gpu_info["gpu_count"] > 0:
                gpu_info["avg_utilization"] = round(
                    total_util / gpu_info["gpu_count"], 1
                )

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        if verbose:
            print(f"  nvidia-smi not available: {e}")

    return gpu_info


def detect_contention(cpu_pct, mem_pct, gpu_info, python_procs, threshold, verbose=False):
    """Detect resource contention and generate alerts."""
    alerts = []

    # CPU contention
    if cpu_pct >= 0 and cpu_pct >= threshold:
        alerts.append({
            "type": "cpu_high",
            "severity": "critical" if cpu_pct >= 95 else "warning",
            "message": f"CPU usage at {cpu_pct}% (threshold: {threshold}%)",
            "resource": "cpu",
            "current_value": cpu_pct,
            "threshold_value": threshold
        })

    # Memory contention
    if mem_pct >= 0 and mem_pct >= threshold:
        alerts.append({
            "type": "memory_high",
            "severity": "critical" if mem_pct >= 95 else "warning",
            "message": f"Memory usage at {mem_pct}% (threshold: {threshold}%)",
            "resource": "memory",
            "current_value": mem_pct,
            "threshold_value": threshold
        })

    # GPU memory contention
    if gpu_info["available"]:
        for gpu in gpu_info["gpus"]:
            if gpu["memory_percent"] >= threshold:
                alerts.append({
                    "type": "gpu_memory_high",
                    "severity": "critical" if gpu["memory_percent"] >= 95 else "warning",
                    "message": (f"GPU {gpu['index']} ({gpu['name']}) memory at "
                               f"{gpu['memory_percent']}% "
                               f"({gpu['memory_used_mb']:.0f}/{gpu['memory_total_mb']:.0f} MB)"),
                    "resource": f"gpu_{gpu['index']}_memory",
                    "current_value": gpu["memory_percent"],
                    "threshold_value": threshold
                })

            if gpu["utilization_percent"] >= threshold:
                alerts.append({
                    "type": "gpu_util_high",
                    "severity": "warning",
                    "message": (f"GPU {gpu['index']} utilization at "
                               f"{gpu['utilization_percent']}%"),
                    "resource": f"gpu_{gpu['index']}_util",
                    "current_value": gpu["utilization_percent"],
                    "threshold_value": threshold
                })

            if gpu["temperature_c"] >= 80:
                alerts.append({
                    "type": "gpu_thermal",
                    "severity": "critical" if gpu["temperature_c"] >= 90 else "warning",
                    "message": (f"GPU {gpu['index']} temperature at "
                               f"{gpu['temperature_c']}C"),
                    "resource": f"gpu_{gpu['index']}_temp",
                    "current_value": gpu["temperature_c"],
                    "threshold_value": 80
                })

    # Process count contention
    proc_count = len(python_procs)
    if proc_count >= 10:
        alerts.append({
            "type": "too_many_python",
            "severity": "warning",
            "message": f"{proc_count} Python processes running simultaneously",
            "resource": "python_processes",
            "current_value": proc_count,
            "threshold_value": 10
        })

    return alerts


def run(args):
    """Main execution logic."""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    init_db(conn)

    threshold = args.threshold

    if args.verbose:
        print(f"[contention] Monitoring resources (threshold={threshold}%)")

    # Gather resource information
    if args.verbose:
        print("[contention] Checking CPU...")
    cpu_pct = get_cpu_usage(args.verbose)

    if args.verbose:
        print("[contention] Checking memory...")
    mem_pct = get_memory_usage(args.verbose)

    if args.verbose:
        print("[contention] Checking GPU...")
    gpu_info = get_gpu_info(args.verbose)

    if args.verbose:
        print("[contention] Listing Python processes...")
    python_procs = get_python_processes(args.verbose)

    # Detect contention
    alerts = detect_contention(cpu_pct, mem_pct, gpu_info, python_procs,
                               threshold, args.verbose)

    # Save to DB
    now = datetime.datetime.now().isoformat()
    contention_detected = 1 if alerts else 0

    conn.execute(
        "INSERT INTO resource_snapshots "
        "(timestamp, cpu_percent, memory_percent, python_processes, "
        "gpu_count, gpu_memory_used_mb, gpu_memory_total_mb, gpu_utilization_percent, "
        "contention_detected, alerts) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (now, cpu_pct, mem_pct, len(python_procs),
         gpu_info["gpu_count"], gpu_info["used_memory_mb"],
         gpu_info["total_memory_mb"], gpu_info["avg_utilization"],
         contention_detected, json.dumps([a["type"] for a in alerts]))
    )

    for alert in alerts:
        conn.execute(
            "INSERT INTO contention_alerts "
            "(timestamp, alert_type, severity, message, resource, current_value, threshold_value) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (now, alert["type"], alert["severity"], alert["message"],
             alert["resource"], alert["current_value"], alert["threshold_value"])
        )

    conn.commit()
    conn.close()

    # JSON output
    result = {
        "timestamp": now,
        "cpu_percent": cpu_pct,
        "memory_percent": mem_pct,
        "python_processes": len(python_procs),
        "gpu": {
            "available": gpu_info["available"],
            "count": gpu_info["gpu_count"],
            "used_memory_mb": round(gpu_info["used_memory_mb"], 1),
            "total_memory_mb": round(gpu_info["total_memory_mb"], 1),
            "avg_utilization": gpu_info["avg_utilization"],
            "gpus": [
                {
                    "index": g["index"],
                    "name": g["name"],
                    "memory_percent": g["memory_percent"],
                    "utilization_percent": g["utilization_percent"],
                    "temperature_c": g["temperature_c"]
                }
                for g in gpu_info["gpus"]
            ]
        },
        "contention_detected": bool(alerts),
        "alerts_count": len(alerts),
        "alerts": alerts,
        "processes": python_procs[:20]  # Limit output
    }

    if args.verbose:
        print(f"\n[contention] CPU: {cpu_pct}% | Memory: {mem_pct}% | "
              f"GPUs: {gpu_info['gpu_count']} | Python procs: {len(python_procs)}")
        if alerts:
            print(f"[contention] ALERTS ({len(alerts)}):")
            for a in alerts:
                icon = "!!" if a["severity"] == "critical" else "!"
                print(f"  [{icon}] {a['message']}")
        else:
            print("[contention] No contention detected")

    print(json.dumps(result, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Resource Contention Monitor — Detect GPU/CPU contention between scripts"
    )
    parser.add_argument("--once", action="store_true",
                        help="Run once and exit")
    parser.add_argument("--watch", action="store_true",
                        help="Continuous monitoring mode")
    parser.add_argument("--threshold", type=int, default=80,
                        help="Alert threshold percentage (default: 80)")
    parser.add_argument("--verbose", action="store_true",
                        help="Enable verbose output")
    args = parser.parse_args()

    if args.once:
        run(args)
    elif args.watch:
        print(f"[contention] Watching resources (threshold={args.threshold}%, Ctrl+C to stop)")
        while True:
            try:
                run(args)
                time.sleep(30)
            except KeyboardInterrupt:
                print("\n[contention] Stopped")
                break
    else:
        run(args)


if __name__ == "__main__":
    main()
