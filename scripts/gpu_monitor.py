#!/usr/bin/env python3
"""JARVIS GPU Thermal & OOM Monitor - Background Service."""

import subprocess
import time
import requests
import os
from dotenv import load_dotenv

load_dotenv()
DISCORD_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

def send_alert(msg: str):
    if DISCORD_URL:
        requests.post(DISCORD_URL, json={"content": f"🚨 **[JARVIS GPU ALERT]** {msg}"})
    print(f"ALERT: {msg}")

def monitor_gpus():
    while True:
        try:
            # Query GPU Temp and VRAM
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=index,name,temperature.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"],
                text=True
            )
            for line in out.strip().split("\n"):
                idx, name, temp, used, total = line.split(", ")
                temp = int(temp)
                pct = int(used) * 100 / int(total)

                # Heat check
                if temp > 85:
                    send_alert(f"GPU {idx} ({name}) Surchauffe : {temp}°C !")
                
                # OOM Check
                if pct > 98:
                    send_alert(f"GPU {idx} ({name}) OOM IMMINENT : {pct:.1f}% utilisé !")

        except Exception as e:
            print(f"Monitor error: {e}")
        
        time.sleep(30)  # Check every 30s

if __name__ == "__main__":
    monitor_gpus()
