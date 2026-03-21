#!/usr/bin/env python3
"""Auto cleaner — When C: <2GB, clean temp/caches. Log cleaned amount to etoile.db."""
import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ETOILE_DB = Path("F:/BUREAU/turbo/etoile.db")
CRITICAL_THRESHOLD_GB = 2.0
INTERVAL_SECONDS = 600  # 10 minutes


def get_free_gb(drive: str = "C:\\") -> float:
    """Get free space in GB for a drive using ctypes."""
    import ctypes
    free = ctypes.c_ulonglong(0)
    ctypes.windll.kernel32.GetDiskFreeSpaceExW(drive, ctypes.byref(free), None, None)
    return free.value / (1024 ** 3)


def dir_size(path: str) -> int:
    """Get total size of a directory in bytes."""
    total = 0
    try:
        for entry in os.scandir(path):
            try:
                if entry.is_file(follow_symlinks=False):
                    total += entry.stat().st_size
                elif entry.is_dir(follow_symlinks=False):
                    total += dir_size(entry.path)
            except (PermissionError, OSError):
                pass
    except (PermissionError, OSError):
        pass
    return total


def clean_directory(path: str) -> int:
    """Remove files in directory, return bytes freed."""
    freed = 0
    if not os.path.isdir(path):
        return 0
    for root, dirs, files in os.walk(path, topdown=False):
        for f in files:
            fp = os.path.join(root, f)
            try:
                sz = os.path.getsize(fp)
                os.remove(fp)
                freed += sz
            except (PermissionError, OSError):
                pass
        for d in dirs:
            try:
                os.rmdir(os.path.join(root, d))
            except (PermissionError, OSError):
                pass
    return freed


def run_cmd(cmd: list) -> str:
    """Run a command silently, return stdout."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return r.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def clean_all() -> dict:
    """Run all cleanup tasks, return results."""
    freed = {}
    # Windows temp
    temp = os.environ.get("TEMP", r"C:\Users\franc\AppData\Local\Temp")
    freed["windows_temp"] = clean_directory(temp)
    # pip cache
    pip_cache = Path.home() / "AppData" / "Local" / "pip" / "cache"
    freed["pip_cache"] = clean_directory(str(pip_cache))
    # npm cache
    run_cmd(["npm", "cache", "clean", "--force"])
    freed["npm_cache_cleaned"] = True
    # uv cache
    uv_cache = Path.home() / "AppData" / "Local" / "uv" / "cache"
    freed["uv_cache"] = clean_directory(str(uv_cache))
    # docker builder prune
    run_cmd(["docker", "builder", "prune", "-f", "--all"])
    freed["docker_prune"] = True
    total_bytes = sum(v for v in freed.values() if isinstance(v, int))
    return {"cleaned_mb": round(total_bytes / (1024 ** 2), 1), "details": freed}


def log_to_db(cleaned_mb: float, free_before: float, free_after: float) -> None:
    """Log cleaning event to etoile.db."""
    if not ETOILE_DB.exists():
        return
    ts = datetime.now(timezone.utc).isoformat()
    model = f"cleaned={cleaned_mb}MB before={free_before:.1f}GB after={free_after:.1f}GB"
    try:
        conn = sqlite3.connect(str(ETOILE_DB), timeout=5)
        conn.execute(
            "INSERT INTO cluster_health (timestamp, node, status, model, latency_ms) "
            "VALUES (?, ?, ?, ?, ?)",
            (ts, "auto_cleaner", "CLEANED", model, 0),
        )
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        print(f"[WARN] DB error: {e}", file=sys.stderr)


def check_and_clean(force: bool = False) -> dict:
    """Check free space and clean if needed."""
    free_before = get_free_gb("C:\\")
    ts = datetime.now(timezone.utc).isoformat()
    if free_before >= CRITICAL_THRESHOLD_GB and not force:
        return {"timestamp": ts, "status": "OK", "free_gb": round(free_before, 2),
                "action": "none", "threshold_gb": CRITICAL_THRESHOLD_GB}
    result = clean_all()
    free_after = get_free_gb("C:\\")
    log_to_db(result["cleaned_mb"], free_before, free_after)
    return {"timestamp": ts, "status": "CLEANED", "free_before_gb": round(free_before, 2),
            "free_after_gb": round(free_after, 2), **result}


def main() -> None:
    parser = argparse.ArgumentParser(description="Auto cleaner — free C: when <2GB")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--force", action="store_true", help="Force clean even if space OK")
    parser.add_argument("--threshold", type=float, default=2.0, help="Threshold in GB")
    args = parser.parse_args()
    global CRITICAL_THRESHOLD_GB
    CRITICAL_THRESHOLD_GB = args.threshold
    while True:
        result = check_and_clean(force=args.force)
        print(json.dumps(result, indent=2))
        if args.once:
            break
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
