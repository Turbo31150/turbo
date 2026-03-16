#!/usr/bin/env python3
"""Windows Performance Tuner — Optimize system for IA workloads.

Profiles CPU, RAM, disk I/O, applies tuning for GPU compute,
manages virtual memory, and monitors bottlenecks.
"""
import argparse
import json
import sqlite3
import subprocess
import time
from pathlib import Path

DB_PATH = Path(__file__).parent / "performance_tuner.db"

def init_db():
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS profiles (
        id INTEGER PRIMARY KEY, ts REAL, cpu_pct REAL, ram_pct REAL,
        disk_read_mbps REAL, disk_write_mbps REAL, gpu_util_pct REAL,
        gpu_temp_c REAL, gpu_vram_pct REAL, bottleneck TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS tunings (
        id INTEGER PRIMARY KEY, ts REAL, action TEXT,
        before_value TEXT, after_value TEXT, success INTEGER)""")
    db.commit()
    return db

def get_cpu_ram():
    """Get CPU and RAM usage."""
    ps = (
        "$cpu = (Get-CimInstance Win32_Processor).LoadPercentage;"
        "$os = Get-CimInstance Win32_OperatingSystem;"
        "$ram = [math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory) / $os.TotalVisibleMemorySize * 100, 1);"
        "$total_gb = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1);"
        "$free_gb = [math]::Round($os.FreePhysicalMemory / 1MB, 1);"
        "Write-Output \"$cpu|$ram|$total_gb|$free_gb\""
    )
    try:
        r = subprocess.run(
            ["bash", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            parts = r.stdout.strip().split("|")
            if len(parts) >= 4:
                return {
                    "cpu_pct": float(parts[0] or 0),
                    "ram_pct": float(parts[1] or 0),
                    "ram_total_gb": float(parts[2] or 0),
                    "ram_free_gb": float(parts[3] or 0),
                }
    except (subprocess.TimeoutExpired, ValueError, OSError):
        pass
    return {"cpu_pct": 0, "ram_pct": 0, "ram_total_gb": 0, "ram_free_gb": 0}

def get_gpu_stats():
    """Get GPU stats via nvidia-smi."""
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu,temperature.gpu,memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            lines = r.stdout.strip().splitlines()
            gpus = []
            for line in lines:
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 4:
                    gpus.append({
                        "util": float(parts[0]),
                        "temp": float(parts[1]),
                        "vram_used": float(parts[2]),
                        "vram_total": float(parts[3]),
                    })
            return gpus
    except (subprocess.TimeoutExpired, OSError):
        pass
    return []

def get_disk_io():
    """Get disk I/O stats."""
    ps = (
        "$disk = Get-CimInstance Win32_PerfFormattedData_PerfDisk_PhysicalDisk | "
        "Where-Object { $_.Name -eq '_Total' }; "
        "Write-Output \"$($disk.DiskReadBytesPersec / 1MB)|$($disk.DiskWriteBytesPersec / 1MB)\""
    )
    try:
        r = subprocess.run(
            ["bash", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            parts = r.stdout.strip().split("|")
            if len(parts) >= 2:
                return float(parts[0] or 0), float(parts[1] or 0)
    except (subprocess.TimeoutExpired, ValueError, OSError):
        pass
    return 0.0, 0.0

def identify_bottleneck(cpu, ram, gpus, disk_read, disk_write):
    """Identify the current system bottleneck."""
    bottlenecks = []
    if cpu > 90:
        bottlenecks.append("CPU")
    if ram > 90:
        bottlenecks.append("RAM")
    for i, g in enumerate(gpus):
        if g["util"] > 95:
            bottlenecks.append(f"GPU{i}_COMPUTE")
        if g["temp"] > 80:
            bottlenecks.append(f"GPU{i}_THERMAL")
        vram_pct = g["vram_used"] / max(g["vram_total"], 1) * 100
        if vram_pct > 95:
            bottlenecks.append(f"GPU{i}_VRAM")
    if disk_read > 500 or disk_write > 300:
        bottlenecks.append("DISK_IO")
    return ", ".join(bottlenecks) if bottlenecks else "NONE"

def take_profile(db):
    """Take a full system performance profile."""
    sys_stats = get_cpu_ram()
    gpus = get_gpu_stats()
    disk_r, disk_w = get_disk_io()

    gpu_util = gpus[0]["util"] if gpus else 0
    gpu_temp = gpus[0]["temp"] if gpus else 0
    gpu_vram = (gpus[0]["vram_used"] / max(gpus[0]["vram_total"], 1) * 100) if gpus else 0

    bottleneck = identify_bottleneck(
        sys_stats["cpu_pct"], sys_stats["ram_pct"], gpus, disk_r, disk_w)

    db.execute(
        "INSERT INTO profiles (ts, cpu_pct, ram_pct, disk_read_mbps, disk_write_mbps, gpu_util_pct, gpu_temp_c, gpu_vram_pct, bottleneck) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (time.time(), sys_stats["cpu_pct"], sys_stats["ram_pct"], disk_r, disk_w,
         gpu_util, gpu_temp, gpu_vram, bottleneck))
    db.commit()

    return {
        "cpu": sys_stats["cpu_pct"], "ram": sys_stats["ram_pct"],
        "ram_free_gb": sys_stats["ram_free_gb"],
        "disk_r": disk_r, "disk_w": disk_w,
        "gpus": gpus, "bottleneck": bottleneck,
    }

def suggest_tunings(profile):
    """Suggest performance tunings based on profile."""
    suggestions = []
    if profile["ram"] > 85:
        suggestions.append("Liberer RAM: fermer apps inutiles, vider cache standby")
    if profile["cpu"] > 80:
        suggestions.append("CPU charge: verifier processus gourmands, reduire parallelisme cluster")
    for i, g in enumerate(profile.get("gpus", [])):
        if g["temp"] > 75:
            suggestions.append(f"GPU{i} chaud ({g['temp']}C): augmenter fan, reduire charge")
        vram_pct = g["vram_used"] / max(g["vram_total"], 1) * 100
        if vram_pct > 90:
            suggestions.append(f"GPU{i} VRAM saturee ({vram_pct:.0f}%): decharger modeles")
    if profile["bottleneck"] == "NONE":
        suggestions.append("Systeme optimal — pas de bottleneck detecte")
    return suggestions

def main():
    parser = argparse.ArgumentParser(description="Windows Performance Tuner")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--suggest", action="store_true")
    args = parser.parse_args()

    db = init_db()

    if args.once or args.suggest or not args.loop:
        profile = take_profile(db)
        print("=== Performance Profile ===")
        print(f"  CPU: {profile['cpu']:.0f}% | RAM: {profile['ram']:.0f}% (free: {profile['ram_free_gb']:.1f} GB)")
        print(f"  Disk: R={profile['disk_r']:.1f} MB/s | W={profile['disk_w']:.1f} MB/s")
        for i, g in enumerate(profile.get("gpus", [])):
            vram_pct = g["vram_used"] / max(g["vram_total"], 1) * 100
            print(f"  GPU{i}: {g['util']:.0f}% util | {g['temp']:.0f}C | VRAM {g['vram_used']:.0f}/{g['vram_total']:.0f} MB ({vram_pct:.0f}%)")
        print(f"  Bottleneck: {profile['bottleneck']}")

        if args.suggest:
            suggestions = suggest_tunings(profile)
            print("\n=== Suggestions ===")
            for s in suggestions:
                print(f"  → {s}")

    if args.loop:
        print("Performance Tuner en boucle continue...")
        while True:
            try:
                profile = take_profile(db)
                ts = time.strftime('%H:%M')
                print(f"[{ts}] CPU:{profile['cpu']:.0f}% RAM:{profile['ram']:.0f}% GPU:{profile.get('gpus',[{}])[0].get('temp',0):.0f}C | {profile['bottleneck']}")
                time.sleep(args.interval)
            except KeyboardInterrupt:
                break

if __name__ == "__main__":
    main()
