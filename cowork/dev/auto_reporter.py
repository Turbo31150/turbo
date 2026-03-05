#!/usr/bin/env python3
"""JARVIS Auto Reporter — Rapport quotidien cluster/trading/systeme."""
import json, sys, os, subprocess, urllib.request
from datetime import datetime

TELEGRAM_TOKEN = "TELEGRAM_TOKEN_REDACTED"
TELEGRAM_CHAT = "2010747443"
REPORT_DIR = "C:/Users/franc/.openclaw/workspace/dev/reports"

NODES = {
    "M1": {"url": "http://127.0.0.1:1234/api/v1/models", "type": "lmstudio"},
    "M2": {"url": "http://192.168.1.26:1234/api/v1/models", "type": "lmstudio"},
    "M3": {"url": "http://192.168.1.113:1234/api/v1/models", "type": "lmstudio"},
    "OL1": {"url": "http://127.0.0.1:11434/api/tags", "type": "ollama"},
}

TRADING_PAIRS = ["BTC_USDT", "ETH_USDT", "SOL_USDT", "SUI_USDT", "PEPE_USDT"]

def send_telegram(msg):
    data = json.dumps({"chat_id": TELEGRAM_CHAT, "text": msg, "parse_mode": "Markdown"}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                                 data=data, headers={"Content-Type": "application/json"})
    try: urllib.request.urlopen(req, timeout=10)
    except: pass

def check_node(name, cfg):
    try:
        req = urllib.request.Request(cfg["url"])
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
            if cfg["type"] == "lmstudio":
                loaded = len([m for m in data.get("data", data.get("models", [])) if m.get("loaded_instances")])
                return {"status": "OK", "models": loaded}
            else:
                return {"status": "OK", "models": len(data.get("models", []))}
    except:
        return {"status": "DOWN", "models": 0}

def get_system_info():
    info = {}
    try:
        r = subprocess.run(["powershell", "-Command",
            "Get-CimInstance Win32_OperatingSystem | Select TotalVisibleMemorySize,FreePhysicalMemory | ConvertTo-Json"],
            capture_output=True, text=True, timeout=10)
        ram = json.loads(r.stdout)
        info["ram_total_gb"] = round(ram.get("TotalVisibleMemorySize", 0) / 1048576, 1)
        info["ram_free_gb"] = round(ram.get("FreePhysicalMemory", 0) / 1048576, 1)
    except: pass
    try:
        r = subprocess.run(["powershell", "-Command",
            "Get-PSDrive C,F -ErrorAction SilentlyContinue | Select Name,@{N='FreeGB';E={[math]::Round($_.Free/1GB,1)}},@{N='UsedGB';E={[math]::Round($_.Used/1GB,1)}} | ConvertTo-Json"],
            capture_output=True, text=True, timeout=10)
        info["disks"] = json.loads(r.stdout)
    except: pass
    try:
        r = subprocess.run(["powershell", "-Command",
            "(Get-CimInstance Win32_Processor).LoadPercentage"],
            capture_output=True, text=True, timeout=10)
        info["cpu_pct"] = int(r.stdout.strip()) if r.stdout.strip() else 0
    except: pass
    return info

def get_trading_snapshot():
    try:
        req = urllib.request.Request("https://contract.mexc.com/api/v1/contract/ticker")
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        tickers = data.get("data", [])
        results = []
        for t in tickers:
            if t.get("symbol") in TRADING_PAIRS:
                change = float(t.get("riseFallRate", 0)) * 100
                price = float(t.get("lastPrice", 0))
                results.append({"symbol": t["symbol"], "price": price, "change": round(change, 2)})
        results.sort(key=lambda x: abs(x["change"]), reverse=True)
        return results
    except:
        return []

def generate_report():
    ts = datetime.now()
    report = {"generated": ts.isoformat()}

    # Cluster
    cluster = {}
    online = 0
    for name, cfg in NODES.items():
        r = check_node(name, cfg)
        cluster[name] = r
        if r["status"] == "OK": online += 1
    report["cluster"] = cluster

    # System
    sys_info = get_system_info()
    report["system"] = sys_info

    # Trading
    trading = get_trading_snapshot()
    report["trading"] = trading

    # Format
    lines = [f"*JARVIS DAILY REPORT* — {ts.strftime('%d/%m/%Y %H:%M')}"]
    lines.append(f"\n*CLUSTER* ({online}/{len(NODES)} online)")
    for n, r in cluster.items():
        icon = "OK" if r["status"] == "OK" else "DOWN"
        lines.append(f"  {n}: {icon} ({r['models']} modeles)")

    lines.append(f"\n*SYSTEME*")
    lines.append(f"  CPU: {sys_info.get('cpu_pct', '?')}%")
    lines.append(f"  RAM: {sys_info.get('ram_free_gb', '?')}GB libre / {sys_info.get('ram_total_gb', '?')}GB")
    if sys_info.get("disks"):
        disks = sys_info["disks"] if isinstance(sys_info["disks"], list) else [sys_info["disks"]]
        for d in disks:
            lines.append(f"  Disque {d.get('Name','?')}: {d.get('FreeGB','?')}GB libre")

    if trading:
        lines.append(f"\n*TRADING TOP 5*")
        for t in trading[:5]:
            arrow = "+" if t["change"] > 0 else ""
            lines.append(f"  {t['symbol']}: ${t['price']} ({arrow}{t['change']}%)")

    return "\n".join(lines), report

if __name__ == "__main__":
    os.makedirs(REPORT_DIR, exist_ok=True)

    if "--once" in sys.argv:
        text, data = generate_report()
        print(text)
        # Save JSON
        fn = os.path.join(REPORT_DIR, f"report_{datetime.now().strftime('%Y%m%d_%H%M')}.json")
        with open(fn, "w") as f:
            json.dump(data, f, indent=2)
        if "--notify" in sys.argv:
            send_telegram(text)
    elif "--loop" in sys.argv:
        import time
        interval = 86400  # 24h
        print(f"Daily report... Ctrl+C to stop")
        while True:
            text, data = generate_report()
            send_telegram(text)
            fn = os.path.join(REPORT_DIR, f"report_{datetime.now().strftime('%Y%m%d_%H%M')}.json")
            with open(fn, "w") as f: json.dump(data, f, indent=2)
            print(f"[{datetime.now().strftime('%H:%M')}] Report sent")
            time.sleep(interval)
    else:
        print("Usage: auto_reporter.py --once [--notify] | --loop")
