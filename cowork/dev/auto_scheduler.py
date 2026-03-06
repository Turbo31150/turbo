#!/usr/bin/env python3
"""JARVIS Auto Scheduler — Planificateur de taches recurrentes (cron-like)."""
import json, sys, os, subprocess, time
from datetime import datetime, timedelta

# TELEGRAM_TOKEN loaded from _paths (.env)
# TELEGRAM_CHAT loaded from _paths (.env)
SCHEDULE_FILE = "C:/Users/franc/.openclaw/workspace/dev/schedule.json"
LOG_FILE = "C:/Users/franc/.openclaw/workspace/dev/scheduler_log.json"

# Default schedule
DEFAULT_SCHEDULE = [
    {
        "name": "cluster_check",
        "command": "python C:/Users/franc/.openclaw/workspace/dev/auto_monitor.py --once",
        "interval_min": 5,
        "enabled": True,
        "description": "Verification cluster toutes les 5 min"
    },
    {
        "name": "trading_scan",
        "command": "python C:/Users/franc/.openclaw/workspace/dev/auto_trader.py --once",
        "interval_min": 10,
        "enabled": True,
        "description": "Scan MEXC toutes les 10 min"
    },
    {
        "name": "daily_report",
        "command": "python C:/Users/franc/.openclaw/workspace/dev/auto_reporter.py --once --notify",
        "interval_min": 1440,
        "enabled": True,
        "description": "Rapport quotidien"
    },
    {
        "name": "optimize",
        "command": "python C:/Users/franc/.openclaw/workspace/dev/win_optimizer.py --once --notify",
        "interval_min": 60,
        "enabled": True,
        "description": "Nettoyage systeme toutes les heures"
    },
    {
        "name": "error_scan",
        "command": "python C:/Users/franc/.openclaw/workspace/dev/auto_learner.py --once --notify",
        "interval_min": 30,
        "enabled": True,
        "description": "Scan erreurs toutes les 30 min"
    },
    {
        "name": "backup",
        "command": "python C:/Users/franc/.openclaw/workspace/dev/win_backup.py --once --notify",
        "interval_min": 1440,
        "enabled": True,
        "description": "Backup quotidien"
    },
]

def send_telegram(msg):
    import urllib.request
from _paths import TELEGRAM_TOKEN, TELEGRAM_CHAT
    data = json.dumps({"chat_id": TELEGRAM_CHAT, "text": msg}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                                 data=data, headers={"Content-Type": "application/json"})
    try: urllib.request.urlopen(req, timeout=10)
    except: pass

def load_schedule():
    if os.path.exists(SCHEDULE_FILE):
        with open(SCHEDULE_FILE, "r") as f:
            return json.load(f)
    # Create default
    save_schedule(DEFAULT_SCHEDULE)
    return DEFAULT_SCHEDULE

def save_schedule(schedule):
    with open(SCHEDULE_FILE, "w") as f:
        json.dump(schedule, f, indent=2)

def log_execution(name, success, duration, output=""):
    entry = {
        "ts": datetime.now().isoformat(),
        "task": name,
        "ok": success,
        "duration_s": round(duration, 1),
        "output": output[:200]
    }
    try:
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except: pass

def execute_task(task):
    start = time.time()
    try:
        result = subprocess.run(
            task["command"], shell=True, capture_output=True, text=True, timeout=120
        )
        duration = time.time() - start
        success = result.returncode == 0
        output = result.stdout[:200] if success else result.stderr[:200]
        log_execution(task["name"], success, duration, output)
        return success, output
    except Exception as e:
        duration = time.time() - start
        log_execution(task["name"], False, duration, str(e))
        return False, str(e)[:200]

def run_scheduler():
    schedule = load_schedule()
    last_run = {}  # name -> datetime

    send_telegram(f"[JARVIS SCHEDULER] Demarre avec {len([t for t in schedule if t['enabled']])} taches actives")
    print(f"[SCHEDULER] {datetime.now().strftime('%H:%M:%S')} — {len(schedule)} taches configurees")

    for t in schedule:
        if t["enabled"]:
            print(f"  {t['name']}: every {t['interval_min']}min — {t['description']}")

    while True:
        now = datetime.now()
        for task in schedule:
            if not task["enabled"]:
                continue
            name = task["name"]
            interval = timedelta(minutes=task["interval_min"])
            last = last_run.get(name)

            if last is None or (now - last) >= interval:
                print(f"[{now.strftime('%H:%M:%S')}] Running: {name}")
                success, output = execute_task(task)
                last_run[name] = now
                status = "OK" if success else "FAIL"
                print(f"  -> {status}: {output[:60]}")

        time.sleep(30)  # Check every 30s

if __name__ == "__main__":
    if "--list" in sys.argv:
        schedule = load_schedule()
        print(f"[SCHEDULER] {len(schedule)} taches:")
        for t in schedule:
            status = "ON" if t["enabled"] else "OFF"
            print(f"  [{status}] {t['name']}: every {t['interval_min']}min — {t['description']}")

    elif "--run-once" in sys.argv:
        schedule = load_schedule()
        name = sys.argv[sys.argv.index("--run-once")+1] if len(sys.argv) > sys.argv.index("--run-once")+1 else None
        for t in schedule:
            if name and t["name"] != name:
                continue
            if t["enabled"]:
                print(f"Running: {t['name']}")
                ok, out = execute_task(t)
                print(f"  {'OK' if ok else 'FAIL'}: {out[:80]}")

    elif "--start" in sys.argv:
        run_scheduler()

    elif "--enable" in sys.argv:
        name = sys.argv[sys.argv.index("--enable")+1]
        schedule = load_schedule()
        for t in schedule:
            if t["name"] == name:
                t["enabled"] = True
                save_schedule(schedule)
                print(f"Enabled: {name}")
                break

    elif "--disable" in sys.argv:
        name = sys.argv[sys.argv.index("--disable")+1]
        schedule = load_schedule()
        for t in schedule:
            if t["name"] == name:
                t["enabled"] = False
                save_schedule(schedule)
                print(f"Disabled: {name}")
                break

    else:
        print("Usage: auto_scheduler.py --list | --start | --run-once [name]")
        print("       --enable <name> | --disable <name>")