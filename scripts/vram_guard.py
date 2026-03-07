#!/usr/bin/env python3
"""vram_guard.py — VRAM overflow prevention for multi-GPU systems.

Monitors GPU VRAM usage via nvidia-smi and takes corrective action
before Windows hits VIDEO_TDR_FAILURE (green screen / BSOD).

Actions by threshold:
  - 85% VRAM: WARNING log
  - 90% VRAM: Pause cowork crons (create pause flag file)
  - 95% VRAM: Kill non-essential Python processes + unload idle LM Studio models
  - RESTORE: When VRAM drops below 80%, remove pause flag

The pause flag (data/.cowork-paused) should be checked by the
autonomous_orchestrator before launching new cowork batches.

Usage:
    python scripts/vram_guard.py --once       # Single check
    python scripts/vram_guard.py --loop       # Continuous (every 30s)
    python scripts/vram_guard.py --status     # Show GPU VRAM state

Stdlib-only (subprocess, json, time, argparse).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

TURBO_DIR = Path("F:/BUREAU/turbo")
PAUSE_FLAG = TURBO_DIR / "data" / ".cowork-paused"
LOG_FILE = TURBO_DIR / "logs" / "vram_guard.log"

# Thresholds (percentage of total VRAM)
WARN_PCT = 85
PAUSE_PCT = 90
CRITICAL_PCT = 95
RESTORE_PCT = 80

# Check interval in seconds
CHECK_INTERVAL_S = 30

# LM Studio CLI
LMS_CLI = str(Path.home() / ".lmstudio" / "bin" / "lms.exe")


def log(msg: str, level: str = "INFO"):
    """Print and log to file."""
    ts = datetime.now().strftime("%H:%M:%S")
    colors = {"OK": "\033[92m", "WARN": "\033[93m", "CRIT": "\033[91m", "INFO": "\033[96m"}
    color = colors.get(level, "\033[0m")
    print(f"{color}[{ts}] [{level}] {msg}\033[0m")
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [{level}] {msg}\n")
    except OSError:
        pass


def get_gpu_vram() -> list[dict]:
    """Query nvidia-smi for VRAM usage per GPU."""
    try:
        r = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=index,name,memory.used,memory.total,temperature.gpu,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
            encoding="utf-8", errors="replace",
        )
        gpus = []
        for line in r.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 5:
                used = int(parts[2]) if parts[2].isdigit() else 0
                total = int(parts[3]) if parts[3].isdigit() else 1
                temp = int(parts[4]) if parts[4].isdigit() else -1
                util = int(parts[5]) if len(parts) > 5 and parts[5].isdigit() else 0
                pct = round(used / max(total, 1) * 100, 1)
                gpus.append({
                    "index": int(parts[0]) if parts[0].isdigit() else 0,
                    "name": parts[1],
                    "used_mb": used,
                    "total_mb": total,
                    "pct": pct,
                    "temp": temp,
                    "util_pct": util,
                })
        return gpus
    except (subprocess.TimeoutExpired, OSError):
        return []


def pause_cowork():
    """Create pause flag to stop cowork cron dispatching."""
    if not PAUSE_FLAG.exists():
        PAUSE_FLAG.parent.mkdir(parents=True, exist_ok=True)
        PAUSE_FLAG.write_text(
            json.dumps({"paused_at": datetime.now().isoformat(), "reason": "vram_guard"}),
            encoding="utf-8",
        )
        log("COWORK PAUSED — flag created", "WARN")
    else:
        log("Cowork already paused", "WARN")


def resume_cowork():
    """Remove pause flag to allow cowork crons to resume."""
    if PAUSE_FLAG.exists():
        PAUSE_FLAG.unlink(missing_ok=True)
        log("COWORK RESUMED — flag removed", "OK")


def kill_cowork_processes():
    """Kill Python processes running cowork/dev scripts."""
    try:
        r = subprocess.run(
            ["wmic", "process", "where",
             "name='python.exe' and commandline like '%cowork%dev%'",
             "get", "ProcessId,CommandLine", "/FORMAT:CSV"],
            capture_output=True, text=True, timeout=10,
            encoding="utf-8", errors="replace",
        )
        killed = 0
        for line in r.stdout.strip().splitlines():
            parts = line.strip().split(",")
            if len(parts) < 3:
                continue
            try:
                pid = int(parts[-1].strip())
            except ValueError:
                continue
            if pid == os.getpid():
                continue
            # Don't kill protected processes
            cmdline = ",".join(parts[1:-1]).lower()
            if any(p in cmdline for p in ["server.py", "unified_boot", "process_gc", "vram_guard"]):
                continue
            try:
                os.kill(pid, 9)
                killed += 1
            except OSError:
                pass
        if killed:
            log(f"Killed {killed} cowork processes", "CRIT")
        return killed
    except (subprocess.TimeoutExpired, OSError):
        return 0


def unload_idle_models():
    """Unload non-essential LM Studio models to free VRAM."""
    if not Path(LMS_CLI).exists():
        return
    try:
        r = subprocess.run(
            [LMS_CLI, "ps"],
            capture_output=True, text=True, timeout=15,
            encoding="utf-8", errors="replace",
        )
        # Keep qwen3-8b (primary), unload everything else
        for line in r.stdout.splitlines():
            line = line.strip()
            if not line or "qwen3-8b" in line.lower():
                continue
            # Try to extract model identifier
            parts = line.split()
            if parts and "/" in parts[0]:
                model_id = parts[0]
                log(f"Unloading idle model: {model_id}", "WARN")
                subprocess.run(
                    [LMS_CLI, "unload", model_id, "-y"],
                    capture_output=True, timeout=30,
                )
    except (subprocess.TimeoutExpired, OSError) as e:
        log(f"Model unload error: {e}", "WARN")


def check_once() -> dict:
    """Run one VRAM check and take action if needed."""
    gpus = get_gpu_vram()
    if not gpus:
        return {"error": "nvidia-smi unavailable", "gpus": []}

    max_pct = max(g["pct"] for g in gpus)
    max_temp = max(g["temp"] for g in gpus if g["temp"] >= 0) if any(g["temp"] >= 0 for g in gpus) else -1
    action = "none"

    if max_pct >= CRITICAL_PCT:
        log(f"CRITICAL VRAM: {max_pct:.1f}% — killing cowork + unloading models", "CRIT")
        pause_cowork()
        kill_cowork_processes()
        unload_idle_models()
        action = "critical_gc"

    elif max_pct >= PAUSE_PCT:
        log(f"HIGH VRAM: {max_pct:.1f}% — pausing cowork", "WARN")
        pause_cowork()
        action = "paused"

    elif max_pct >= WARN_PCT:
        log(f"VRAM warning: {max_pct:.1f}%", "WARN")
        action = "warning"

    elif max_pct < RESTORE_PCT and PAUSE_FLAG.exists():
        resume_cowork()
        action = "resumed"

    else:
        action = "ok"

    return {
        "timestamp": datetime.now().isoformat(),
        "gpus": gpus,
        "max_vram_pct": max_pct,
        "max_temp": max_temp,
        "action": action,
        "cowork_paused": PAUSE_FLAG.exists(),
    }


def print_status():
    """Display current GPU state."""
    gpus = get_gpu_vram()
    if not gpus:
        print("  nvidia-smi not available")
        return

    print(f"\n  {'GPU':4} {'Name':24} {'VRAM':>14} {'Pct':>6} {'Temp':>5} {'Util':>5}")
    print(f"  {'-'*60}")
    for g in gpus:
        bar_len = int(g["pct"] / 5)
        bar = "#" * bar_len + "." * (20 - bar_len)
        color = "\033[91m" if g["pct"] >= CRITICAL_PCT else \
                "\033[93m" if g["pct"] >= WARN_PCT else "\033[92m"
        print(f"  {g['index']:<4} {g['name']:24} "
              f"{g['used_mb']:>5}/{g['total_mb']:<5}MB "
              f"{color}{g['pct']:>5.1f}%\033[0m "
              f"{g['temp']:>3}C {g['util_pct']:>3}%")

    paused = PAUSE_FLAG.exists()
    print(f"\n  Cowork paused: {'YES' if paused else 'no'}")
    print(f"  Thresholds: warn={WARN_PCT}% pause={PAUSE_PCT}% critical={CRITICAL_PCT}% restore={RESTORE_PCT}%")


def main():
    parser = argparse.ArgumentParser(description="VRAM Guard — prevent GPU memory overflow")
    parser.add_argument("--once", action="store_true", help="Single VRAM check")
    parser.add_argument("--loop", action="store_true", help=f"Continuous check every {CHECK_INTERVAL_S}s")
    parser.add_argument("--status", action="store_true", help="Show GPU VRAM state")
    parser.add_argument("--resume", action="store_true", help="Force-remove cowork pause flag")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    if not any([args.once, args.loop, args.status, args.resume]):
        parser.print_help()
        sys.exit(1)

    if args.resume:
        resume_cowork()
        return

    if args.status:
        print_status()
        return

    if args.once:
        result = check_once()
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            for g in result.get("gpus", []):
                print(f"  GPU{g['index']} {g['name']}: {g['used_mb']}/{g['total_mb']}MB "
                      f"({g['pct']:.1f}%) {g['temp']}C")
            print(f"  Action: {result['action']}")
        return

    if args.loop:
        log(f"VRAM Guard started — check every {CHECK_INTERVAL_S}s", "INFO")
        log(f"Thresholds: warn={WARN_PCT}% pause={PAUSE_PCT}% critical={CRITICAL_PCT}%", "INFO")
        while True:
            try:
                result = check_once()
                if result.get("action") not in ("ok", "none"):
                    for g in result.get("gpus", []):
                        log(f"  GPU{g['index']}: {g['pct']:.1f}% ({g['used_mb']}/{g['total_mb']}MB) {g['temp']}C",
                            "INFO")
                time.sleep(CHECK_INTERVAL_S)
            except KeyboardInterrupt:
                log("VRAM Guard stopped", "INFO")
                break


if __name__ == "__main__":
    main()
