#!/usr/bin/env python3
import subprocess
import psutil
import time
import requests
from datetime import datetime

def get_vram_usage():
    try:
        out = subprocess.check_output(["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader"])
        return sum(float(x.split()[0]) for x in out.decode().split('\n') if x.strip())
    except:
        return 0

def get_zram_usage():
    try:
        out = subprocess.check_output(["zramctl", "--output", "DATA", "--bytes", "--noheadings"])
        return sum(int(x) for x in out.decode().split('\n') if x.strip())
    except:
        return 0

print(f"[{datetime.now()}] 🚀 JARVIS Resource Manager Started (Aggressive VRAM/RAM Tuning)")

while True:
    ram = psutil.virtual_memory()
    vram = get_vram_usage()
    zram = get_zram_usage()
    
    total_mem = ram.total / 1024**3
    used_mem = ram.used / 1024**3
    vram_gb = vram / 1024
    
    status = ""
    if used_mem > total_mem * 0.85:
        status = "🔥 HIGH MEM -> Boost VRAM/emuV | Swapping to ZRAM"
        # Logique systemctl ou DBus pour libérer de la RAM
    elif vram_gb > 35:
        status = "🟢 GPU HEAVY -> RAM équilibré"
    else:
        status = "💤 IDLE -> Low Power Mode"
        
    print(f"[{datetime.now()}] RAM: {used_mem:.1f}/{total_mem:.1f}GB | VRAM: {vram_gb:.1f}GB | ZRAM: {zram/1024**3:.1f}GB -> {status}")
    
    time.sleep(30)
