#!/usr/bin/env python3
"""GPU monitoring via nvidia-smi — output temp/VRAM/utilization per GPU as JSON."""

import argparse
import json
import subprocess
import time


def query_nvidia_smi():
    """Run nvidia-smi and parse CSV output."""
    cmd = [
        "nvidia-smi",
        "--query-gpu=index,name,temperature.gpu,memory.used,memory.total,utilization.gpu,utilization.memory,fan.speed,power.draw,power.limit",
        "--format=csv,noheader,nounits",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return {"error": f"nvidia-smi failed: {result.stderr.strip()}"}
    except FileNotFoundError:
        return {"error": "nvidia-smi not found — NVIDIA drivers not installed or not in PATH"}
    except subprocess.TimeoutExpired:
        return {"error": "nvidia-smi timed out (10s)"}

    gpus = []
    for line in result.stdout.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 10:
            continue
        try:
            gpu = {
                "index": int(parts[0]),
                "name": parts[1],
                "temperature_c": int(parts[2]) if parts[2] not in ("[N/A]", "") else None,
                "vram_used_mb": int(parts[3]) if parts[3] not in ("[N/A]", "") else None,
                "vram_total_mb": int(parts[4]) if parts[4] not in ("[N/A]", "") else None,
                "gpu_util_pct": int(parts[5]) if parts[5] not in ("[N/A]", "") else None,
                "mem_util_pct": int(parts[6]) if parts[6] not in ("[N/A]", "") else None,
                "fan_speed_pct": int(parts[7]) if parts[7] not in ("[N/A]", "") else None,
                "power_draw_w": float(parts[8]) if parts[8] not in ("[N/A]", "") else None,
                "power_limit_w": float(parts[9]) if parts[9] not in ("[N/A]", "") else None,
            }
            if gpu["vram_total_mb"] and gpu["vram_used_mb"] is not None:
                gpu["vram_free_mb"] = gpu["vram_total_mb"] - gpu["vram_used_mb"]
                gpu["vram_used_pct"] = round(gpu["vram_used_mb"] / gpu["vram_total_mb"] * 100, 1)
            gpus.append(gpu)
        except (ValueError, IndexError):
            continue

    return {"gpus": gpus, "gpu_count": len(gpus)}


def run_once():
    data = query_nvidia_smi()
    output = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        **data,
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="GPU monitoring via nvidia-smi (JSON output)")
    parser.add_argument("--once", action="store_true", help="Single run then exit")
    args = parser.parse_args()

    if args.once:
        run_once()
    else:
        print("Use --once for a single run. Use --help for options.")


if __name__ == "__main__":
    main()
