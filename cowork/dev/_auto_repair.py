#!/usr/bin/env python3
"""Auto-repair: analyse errors from orchestrator runs and attempts fixes."""
import sys, json, os, sqlite3, subprocess, time, urllib.parse, urllib.request
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from _paths import TELEGRAM_TOKEN, TELEGRAM_CHAT

SCRIPT_DIR = Path(__file__).resolve().parent
DB_PATH = SCRIPT_DIR / "data" / "cowork_gaps.db"

def send_telegram(text):
    data = urllib.parse.urlencode({"chat_id": TELEGRAM_CHAT, "text": text[:4000]}).encode()
    try:
        req = urllib.request.Request(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data)
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass

def get_recent_failures(hours=2):
    """Get recent task failures from orchestrator_runs."""
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    rows = conn.execute("""
        SELECT task_name, timestamp, output_summary
        FROM orchestrator_runs
        WHERE success = 0 AND timestamp > ?
        ORDER BY timestamp DESC LIMIT 20
    """, (cutoff,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def check_cluster_health():
    """Quick health check of cluster nodes."""
    import urllib.request
    nodes = [
        ("M1", "http://127.0.0.1:1234/v1/models"),
        ("OL1", "http://127.0.0.1:11434/api/tags"),
        ("M2", "http://192.168.1.26:1234/v1/models"),
        ("M3", "http://192.168.1.113:1234/v1/models"),
    ]
    results = {}
    for name, url in nodes:
        try:
            req = urllib.request.Request(url)
            urllib.request.urlopen(req, timeout=3)
            results[name] = "online"
        except Exception:
            results[name] = "offline"
    return results

def attempt_repair(failure):
    """Attempt to repair a specific failure."""
    task = failure["task_name"]
    error = failure.get("output_summary", "")
    repairs = []

    # Common repairs
    if "ModuleNotFoundError" in error or "ImportError" in error:
        module = error.split("'")[1] if "'" in error else "unknown"
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", module],
                         capture_output=True, timeout=30)
            repairs.append(f"pip install {module}")
        except Exception:
            pass

    if "timeout" in error.lower() or "Timeout" in error:
        repairs.append("timeout detected - will retry on next cycle")

    if "connection refused" in error.lower() or "WinError 10061" in error:
        # Try restarting the relevant service
        if "11434" in error:
            try:
                subprocess.run(["powershell", "-Command", "Start-Process ollama -ArgumentList 'serve' -WindowStyle Hidden"],
                             capture_output=True, timeout=10)
                repairs.append("restarted Ollama")
            except Exception:
                pass

    if "Script not found" in error:
        repairs.append("script missing - skipping")

    if "disk" in error.lower() and "space" in error.lower():
        try:
            subprocess.run([sys.executable, str(SCRIPT_DIR / "cleanup_temp.py"), "--once"],
                         capture_output=True, timeout=60)
            repairs.append("ran cleanup_temp")
        except Exception:
            pass

    return repairs

def main():
    if "--once" not in sys.argv:
        print("Usage: _auto_repair.py --once")
        sys.exit(1)

    failures = get_recent_failures(hours=2)
    cluster = check_cluster_health()
    online = sum(1 for s in cluster.values() if s == "online")

    repairs_done = []

    # Repair recent failures
    unique_tasks = {}
    for f in failures:
        if f["task_name"] not in unique_tasks:
            unique_tasks[f["task_name"]] = f

    for task_name, failure in unique_tasks.items():
        repairs = attempt_repair(failure)
        if repairs:
            repairs_done.append(f"{task_name}: {', '.join(repairs)}")

    # Cluster health repairs
    for name, status in cluster.items():
        if status == "offline":
            if name == "OL1":
                try:
                    subprocess.run(["powershell", "-Command",
                                  "Start-Process ollama -ArgumentList 'serve' -WindowStyle Hidden"],
                                 capture_output=True, timeout=10)
                    repairs_done.append(f"{name}: attempted Ollama restart")
                except Exception:
                    pass

    # Report
    lines = [f"[AUTO-REPAIR] Cluster: {online}/4 online | {len(failures)} recent failures"]
    if repairs_done:
        lines.append("Repairs:")
        for r in repairs_done:
            lines.append(f"  + {r}")
    else:
        lines.append("No repairs needed")

    report = "\n".join(lines)
    print(report)

    if repairs_done:
        send_telegram(report)

    print(json.dumps({
        "cluster": cluster,
        "failures": len(failures),
        "repairs": len(repairs_done),
        "details": repairs_done,
    }))

if __name__ == "__main__":
    main()
