#!/usr/bin/env python3
"""Daily health report — Disk, GPU, services, cluster, cowork stats. Save to data/reports/."""
import argparse, json, os, socket, sqlite3, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

ETOILE_DB = Path("F:/BUREAU/turbo/etoile.db")
REPORTS_DIR = Path("F:/BUREAU/turbo/data/reports")
INTERVAL_SECONDS = 86400  # 24 hours


def get_free_gb(drive: str) -> float:
    """Get free space in GB."""
    import ctypes
    free = ctypes.c_ulonglong(0)
    total = ctypes.c_ulonglong(0)
    ctypes.windll.kernel32.GetDiskFreeSpaceExW(drive, ctypes.byref(free), ctypes.byref(total), None)
    return round(free.value / (1024 ** 3), 2), round(total.value / (1024 ** 3), 2)


def get_disk_info() -> dict:
    result = {}
    for d in ["C:\\", "F:\\"]:
        try:
            free, total = get_free_gb(d)
            result[d[:2]] = {"free_gb": free, "total_gb": total, "pct_free": round(free / total * 100, 1)}
        except Exception:
            result[d[:2]] = {"error": "unavailable"}
    return result


def get_gpu_temps() -> list:
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,temperature.gpu,memory.used,memory.total",
             "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10)
        gpus = []
        for line in r.stdout.strip().split("\n"):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 5:
                gpus.append({"index": int(parts[0]), "name": parts[1], "temp_c": int(parts[2]),
                             "vram_used_mb": int(parts[3]), "vram_total_mb": int(parts[4])})
        return gpus
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return [{"error": "nvidia-smi unavailable"}]


def get_services_status() -> dict:
    def _up(h, p):
        try:
            with socket.create_connection((h, p), timeout=2):
                return True
        except (OSError, TimeoutError):
            return False
    services = {
        "lmstudio_1234": _up("127.0.0.1", 1234),
        "ollama_11434": _up("127.0.0.1", 11434),
        "direct_proxy_18800": _up("127.0.0.1", 18800),
        "m2_lmstudio": _up("192.168.1.26", 1234),
        "m3_lmstudio": _up("192.168.1.113", 1234),
    }
    return {k: "UP" if v else "DOWN" for k, v in services.items()}


def get_cluster_stats() -> dict:
    if not ETOILE_DB.exists():
        return {"error": "etoile.db not found"}
    try:
        conn = sqlite3.connect(str(ETOILE_DB), timeout=5)
        cur = conn.execute(
            "SELECT node, status, COUNT(*) FROM cluster_health "
            "WHERE timestamp > datetime('now', '-24 hours') GROUP BY node, status"
        )
        stats = {}
        for node, status, count in cur.fetchall():
            stats.setdefault(node, {})[status] = count
        conn.close()
        return stats
    except sqlite3.Error as e:
        return {"error": str(e)}


def get_cowork_stats() -> dict:
    """Count cowork scripts and recent activity."""
    dev_dir = Path("F:/BUREAU/turbo/cowork/dev")
    scripts = list(dev_dir.glob("*.py")) if dev_dir.exists() else []
    return {"total_scripts": len(scripts), "dir": str(dev_dir)}


def generate_report() -> dict:
    """Generate full health report."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disk": get_disk_info(),
        "gpu": get_gpu_temps(),
        "services": get_services_status(),
        "cluster_24h": get_cluster_stats(),
        "cowork": get_cowork_stats(),
    }


def save_report(report: dict) -> str:
    """Save report to data/reports/ directory."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    filepath = REPORTS_DIR / f"health_{ts}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    return str(filepath)


def log_to_db(report: dict) -> None:
    """Log report generation to etoile.db."""
    if not ETOILE_DB.exists():
        return
    ts = datetime.now(timezone.utc).isoformat()
    svc_up = sum(1 for v in report["services"].values() if v == "UP")
    svc_total = len(report["services"])
    model = f"services={svc_up}/{svc_total} gpus={len(report['gpu'])}"
    try:
        conn = sqlite3.connect(str(ETOILE_DB), timeout=5)
        conn.execute(
            "INSERT INTO cluster_health (timestamp, node, status, model, latency_ms) "
            "VALUES (?, ?, ?, ?, ?)",
            (ts, "daily_report", "GENERATED", model, 0),
        )
        conn.commit()
        conn.close()
    except sqlite3.Error:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily health report generator")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()
    while True:
        report = generate_report()
        filepath = save_report(report)
        log_to_db(report)
        output = {"report": report, "saved_to": filepath}
        print(json.dumps(output, indent=2))
        if args.once:
            break
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
