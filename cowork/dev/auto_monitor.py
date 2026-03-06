#!/usr/bin/env python3
"""JARVIS Auto Monitor — Surveillance cluster en continu."""
import json, time, sys, urllib.request, urllib.error
from datetime import datetime

NODES = {
    "M1": {"url": "http://127.0.0.1:1234/api/v1/models", "type": "lmstudio"},
    "OL1": {"url": "http://127.0.0.1:11434/api/tags", "type": "ollama"},
}
TELEGRAM_TOKEN = "8369376863:AAF-7YGDbun8mXWwqYJFj-eX6P78DeIu9Aw"
TELEGRAM_CHAT = "2010747443"
LOG_FILE = "C:/Users/franc/.openclaw/workspace/dev/monitor_log.json"

def check_node(name, cfg):
    try:
        req = urllib.request.Request(cfg["url"], headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
            if cfg["type"] == "lmstudio":
                models = [m for m in data.get("data", data.get("models", [])) if m.get("loaded_instances")]
                return {"status": "online", "models": len(models)}
            else:
                return {"status": "online", "models": len(data.get("models", []))}
    except Exception as e:
        return {"status": "offline", "error": str(e)[:100]}

def send_telegram(msg):
    data = json.dumps({"chat_id": TELEGRAM_CHAT, "text": msg}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                                 data=data, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=10)
    except: pass

def run_check():
    results = {}
    alerts = []
    for name, cfg in NODES.items():
        r = check_node(name, cfg)
        results[name] = {**r, "checked_at": datetime.now().isoformat()}
        if r["status"] == "offline":
            alerts.append(f"{name} DOWN: {r.get('error','?')}")
    # Log
    try:
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps({"ts": datetime.now().isoformat(), **results}) + "\n")
    except: pass
    # Alerts
    if alerts:
        send_telegram(f"[JARVIS ALERT] {' | '.join(alerts)}")
    return results, alerts

if __name__ == "__main__":
    if "--once" in sys.argv:
        results, alerts = run_check()
        for n, r in results.items():
            print(f"{n}: {r['status']} ({r.get('models','?')} models)")
        if alerts: print(f"ALERTS: {alerts}")
        else: print("All nodes OK")
    elif "--loop" in sys.argv:
        interval = 60
        print(f"Monitoring every {interval}s... Ctrl+C to stop")
        while True:
            results, alerts = run_check()
            ts = datetime.now().strftime("%H:%M:%S")
            status = " | ".join(f"{n}:{r['status']}" for n,r in results.items())
            print(f"[{ts}] {status}" + (f" ALERT: {alerts}" if alerts else ""))
            time.sleep(interval)
    else:
        print("Usage: auto_monitor.py --once | --loop")
