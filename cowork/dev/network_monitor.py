#!/usr/bin/env python3
"""JARVIS Network Monitor — Surveillance reseau cluster."""
import json, sys, os, sqlite3, subprocess, time
from datetime import datetime

DB_PATH = "C:/Users/franc/.openclaw/workspace/dev/network.db"
# TELEGRAM_TOKEN loaded from _paths (.env)
# TELEGRAM_CHAT loaded from _paths (.env)

TARGETS = {
    "M1": "127.0.0.1",
    "M2": "192.168.1.26",
    "M3": "192.168.1.113",
    "Gateway": "127.0.0.1",
    "Google": "8.8.8.8",
}
LATENCY_ALERT = 500  # ms
LOSS_ALERT = 5  # %

def send_telegram(msg):
    import urllib.request
    data = json.dumps({"chat_id": TELEGRAM_CHAT, "text": msg}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                                 data=data, headers={"Content-Type": "application/json"})
    try: urllib.request.urlopen(req, timeout=10)
    except: pass

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS pings (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, target TEXT,
        host TEXT, latency_ms REAL, loss_pct REAL, status TEXT
    )""")
    conn.commit()
    return conn

def ping_host(host, count=4):
    try:
        result = subprocess.run(
            ["ping", "-n", str(count), "-w", "2000", host],
            capture_output=True, text=True, timeout=15
        )
        output = result.stdout
        # Parse average latency
        latency = None
        loss = 100
        for line in output.split("\n"):
            if "Average" in line or "Moyenne" in line:
                parts = line.split("=")
                if len(parts) >= 2:
                    val = parts[-1].strip().replace("ms", "").strip()
                    try: latency = float(val)
                    except: pass
            if "Lost" in line or "perdus" in line:
                # (0% loss) or (0% de perte)
                import re
from _paths import TELEGRAM_TOKEN, TELEGRAM_CHAT
                m = re.search(r'\((\d+)%', line)
                if m: loss = int(m.group(1))
        return {
            "latency_ms": latency if latency else -1,
            "loss_pct": loss,
            "status": "ok" if latency and loss < 100 else "down",
        }
    except Exception as e:
        return {"latency_ms": -1, "loss_pct": 100, "status": "error"}

def run_check(conn, notify=False):
    ts = datetime.now().isoformat()
    results = {}
    alerts = []
    c = conn.cursor()

    for name, host in TARGETS.items():
        r = ping_host(host)
        results[name] = r
        c.execute("INSERT INTO pings (ts, target, host, latency_ms, loss_pct, status) VALUES (?,?,?,?,?,?)",
                  (ts, name, host, r["latency_ms"], r["loss_pct"], r["status"]))
        if r["status"] != "ok":
            alerts.append(f"{name} ({host}): DOWN")
        elif r["latency_ms"] > LATENCY_ALERT:
            alerts.append(f"{name}: latency {r['latency_ms']}ms > {LATENCY_ALERT}ms")
        elif r["loss_pct"] > LOSS_ALERT:
            alerts.append(f"{name}: {r['loss_pct']}% packet loss")
    conn.commit()

    lines = [f"[NETWORK MONITOR] {datetime.now().strftime('%H:%M:%S')}"]
    for name, r in results.items():
        icon = "OK" if r["status"] == "ok" else "DOWN"
        lat = f"{r['latency_ms']}ms" if r["latency_ms"] > 0 else "N/A"
        lines.append(f"  {name}: {icon} | {lat} | loss={r['loss_pct']}%")

    if alerts and notify:
        send_telegram(f"[JARVIS NETWORK] Alertes:\n" + "\n".join(alerts))

    return "\n".join(lines), alerts

if __name__ == "__main__":
    conn = init_db()
    if "--once" in sys.argv:
        text, alerts = run_check(conn, notify="--notify" in sys.argv)
        print(text)
    elif "--loop" in sys.argv:
        interval = 60
        print(f"Monitoring every {interval}s...")
        while True:
            text, _ = run_check(conn, notify=True)
            print(text)
            time.sleep(interval)
    elif "--history" in sys.argv:
        c = conn.cursor()
        c.execute("SELECT ts, target, latency_ms, loss_pct, status FROM pings ORDER BY id DESC LIMIT 20")
        for r in c.fetchall():
            print(f"  {r[0][:16]} {r[1]}: {r[2]}ms loss={r[3]}% [{r[4]}]")
    else:
        print("Usage: network_monitor.py --once [--notify] | --loop | --history")
    conn.close()