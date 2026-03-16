
import subprocess
import time
import os
import requests
import json

# Configuration
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL", "")
TEMP_THRESHOLD = 85
CHECK_INTERVAL = 30  # secondes

def send_alert(message):
    print(f"[ALERT] {message}")
    if DISCORD_WEBHOOK:
        try:
            requests.post(DISCORD_WEBHOOK, json={"content": f"🔥 **JARVIS GPU ALERT** 🔥\n{message}"})
        except Exception as e:
            print(f"Failed to send Discord alert: {e}")

def monitor_gpus():
    while True:
        try:
            # Check temp and VRAM
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=index,name,temperature.gpu,memory.used,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5
            )
            
            for line in r.stdout.strip().split("\n"):
                idx, name, temp, used, total = [p.strip() for p in line.split(",")]
                temp = int(temp)
                used = int(used)
                total = int(total)
                
                # Check Temp
                if temp >= TEMP_THRESHOLD:
                    send_alert(f"GPU {idx} ({name}) is running hot: {temp}C!")
                
                # Check OOM (95% VRAM usage)
                if used / total > 0.95:
                    send_alert(f"GPU {idx} ({name}) is almost out of VRAM: {used}/{total}MB used!")
            
            # Check for OOM in dmesg
            dmesg = subprocess.run(["dmesg"], capture_output=True, text=True).stdout
            if "out of memory" in dmesg.lower() or "oom-killer" in dmesg.lower():
                send_alert("⚠️ System OOM-Killer activity detected in dmesg!")
                # Optional: Clear dmesg buffer to avoid repeat alerts if user permits
                # subprocess.run(["sudo", "dmesg", "-c"], capture_output=True)

        except Exception as e:
            print(f"Monitor error: {e}")
            
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    print(f"Starting GPU Watcher (Threshold: {TEMP_THRESHOLD}C)...")
    monitor_gpus()
