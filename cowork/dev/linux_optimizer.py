#!/usr/bin/env python3
"""JARVIS Win Optimizer — Nettoyage et optimisation Windows."""
import json, sys, os, subprocess, shutil
from datetime import datetime
from _paths import TELEGRAM_TOKEN, TELEGRAM_CHAT

# TELEGRAM_TOKEN loaded from _paths (.env)
# TELEGRAM_CHAT loaded from _paths (.env)
LOG_FILE = "C:/Users/franc/.openclaw/workspace/dev/optimizer_log.json"

TEMP_DIRS = [
    os.path.expandvars(r"%TEMP%"),
    os.path.expandvars(r"%LOCALAPPDATA%\Temp"),
    r"/Windows\Temp",
    os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Windows\INetCache"),
]

def send_telegram(msg):
    import urllib.request
    data = json.dumps({"chat_id": TELEGRAM_CHAT, "text": msg}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                                 data=data, headers={"Content-Type": "application/json"})
    try: urllib.request.urlopen(req, timeout=10)
    except: pass

def get_dir_size(path):
    total = 0
    try:
        for dirpath, _, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try: total += os.path.getsize(fp)
                except: pass
    except: pass
    return total

def clean_temp_dirs():
    total_freed = 0
    cleaned = []
    for d in TEMP_DIRS:
        if not os.path.exists(d):
            continue
        before = get_dir_size(d)
        count = 0
        for item in os.listdir(d):
            fp = os.path.join(d, item)
            try:
                if os.path.isfile(fp):
                    os.unlink(fp)
                    count += 1
                elif os.path.isdir(fp):
                    shutil.rmtree(fp, ignore_errors=True)
                    count += 1
            except: pass
        after = get_dir_size(d)
        freed = before - after
        total_freed += freed
        cleaned.append({"dir": d, "freed_mb": round(freed / 1048576, 1), "items": count})
    return total_freed, cleaned

def get_disk_info():
    result = subprocess.run(
        ["bash", "-Command",
         "Get-PSDrive -PSProvider FileSystem | Select Name,Used,Free | ConvertTo-Json"],
        capture_output=True, text=True, timeout=10
    )
    try: return json.loads(result.stdout)
    except: return []

def get_ram_info():
    result = subprocess.run(
        ["bash", "-Command",
         "(Get-CimInstance Win32_OperatingSystem | Select TotalVisibleMemorySize,FreePhysicalMemory) | ConvertTo-Json"],
        capture_output=True, text=True, timeout=10
    )
    try: return json.loads(result.stdout)
    except: return {}

def flush_dns():
    try:
        subprocess.run(["ipconfig", "/flushdns"], capture_output=True, timeout=10)
        return True
    except: return False

def run_optimization(notify=True):
    report = {"ts": datetime.now().isoformat(), "actions": []}

    # 1. Clean temp
    freed, cleaned = clean_temp_dirs()
    freed_mb = round(freed / 1048576, 1)
    report["actions"].append({"action": "clean_temp", "freed_mb": freed_mb, "details": cleaned})

    # 2. Disk info
    disks = get_disk_info()
    report["actions"].append({"action": "disk_info", "disks": disks})

    # 3. RAM info
    ram = get_ram_info()
    report["actions"].append({"action": "ram_info", "ram": ram})

    # 4. Flush DNS
    dns_ok = flush_dns()
    report["actions"].append({"action": "flush_dns", "ok": dns_ok})

    # Log
    try:
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(report) + "\n")
    except: pass

    # Summary
    total_ram_mb = ram.get("TotalVisibleMemorySize", 0) / 1024
    free_ram_mb = ram.get("FreePhysicalMemory", 0) / 1024
    summary = (f"[JARVIS OPTIMIZER] {datetime.now().strftime('%H:%M')}\n"
               f"Temp nettoyé: {freed_mb} MB libérés\n"
               f"RAM: {round(free_ram_mb)}MB libre / {round(total_ram_mb)}MB\n"
               f"DNS flush: {'OK' if dns_ok else 'FAIL'}")

    if notify and freed_mb > 10:
        send_telegram(summary)

    return summary, report

if __name__ == "__main__":
    if "--once" in sys.argv:
        summary, _ = run_optimization(notify="--notify" in sys.argv)
        print(summary)
    elif "--loop" in sys.argv:
        import time
        interval = 3600  # 1h
        print(f"Optimizing every {interval}s... Ctrl+C to stop")
        while True:
            summary, _ = run_optimization(notify=True)
            print(summary)
            time.sleep(interval)
    else:
        print("Usage: win_optimizer.py --once [--notify] | --loop")