#!/usr/bin/env python3
"""JARVIS Supervisor — Service monitor, health scorer, auto-restarter.

Usage:
    python jarvis_supervisor.py              # one-shot status
    python jarvis_supervisor.py --watch      # continuous loop (30s)
    python jarvis_supervisor.py --restart ws # restart a specific service
"""
import json, subprocess, time, os, sys, logging
from pathlib import Path
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.error import URLError

# ── CONFIG ────────────────────────────────────────────────────────────
BASE = Path("/home/turbo/jarvis-m1-ops")
LOG_FILE = BASE / "data" / "supervisor.log"
ENV_FILE = BASE / ".env"
CHAT_ID = "2010747443"
INTERVAL = 30
TIMEOUT = 5

SERVICES = {
    "m1":        {"name": "M1 LM Studio",  "port": 1234,  "url": "http://127.0.0.1:1234/api/v1/models",  "weight": 25, "critical": True},
    "ol1":       {"name": "OL1 Ollama",    "port": 11434, "url": "http://127.0.0.1:11434/api/tags",       "weight": 15, "critical": True},
    "ws":        {"name": "WS FastAPI",     "port": 9742,  "url": "http://127.0.0.1:9742/health",         "weight": 20, "critical": True},
    "proxy":     {"name": "Proxy",          "port": 18800, "url": "http://127.0.0.1:18800/health",        "weight": 10, "critical": True},
    "telegram":  {"name": "Telegram Bot",   "port": None,  "url": None,                                   "weight": 5,  "critical": False},
    "openclaw":  {"name": "OpenClaw",       "port": 18789, "url": "http://127.0.0.1:18789/",              "weight": 10, "critical": False},
    "dashboard": {"name": "Dashboard",      "port": 8080,  "url": "http://127.0.0.1:8080/",               "weight": 5,  "critical": False},
}

RESTART_CMDS = {
    "telegram": {"cmd": "node telegram-bot.js",       "cwd": str(BASE / "canvas")},
    "ws":       {"cmd": 'python -m uvicorn python_ws.server:app --host 0.0.0.0 --port 9742', "cwd": str(BASE)},
    "proxy":    {"cmd": "node direct-proxy.js",        "cwd": str(BASE / "canvas")},
}

# ── LOGGING ───────────────────────────────────────────────────────────
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.FileHandler(str(LOG_FILE), encoding="utf-8"), logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("supervisor")

# ── HELPERS ───────────────────────────────────────────────────────────
def load_telegram_token():
    """Load TELEGRAM_TOKEN from .env file."""
    if not ENV_FILE.exists():
        return None
    for line in ENV_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("TELEGRAM_TOKEN="):
            return line.split("=", 1)[1].strip()
    return None

TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_TOKEN") or load_telegram_token()

def run(cmd, timeout=TIMEOUT, cwd=None):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           timeout=timeout, encoding="utf-8", errors="replace", cwd=cwd)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None

def http_check(url, timeout=TIMEOUT):
    """Return True if URL responds with 2xx."""
    try:
        with urlopen(url, timeout=timeout) as resp:
            return 200 <= resp.status < 400
    except Exception:
        return False

def port_listening(port):
    """Check if a port is listening via netstat."""
    r = run(f'netstat -ano | findstr ":{port} " | findstr LISTENING')
    return bool(r)

def telegram_bot_running():
    """Check if telegram-bot.js is running in a node.exe process."""
    r = run('wmic process where "name=\'node.exe\'" get commandline', timeout=8)
    return r is not None and "telegram-bot" in r

def send_telegram(message):
    """Send alert to Telegram."""
    if not TG_TOKEN:
        log.warning("No Telegram token — alert not sent")
        return False
    try:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        data = json.dumps({"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}).encode()
        req = Request(url, data=data, headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        log.warning(f"Telegram send failed: {e}")
        return False

# ── SERVICE CHECK ─────────────────────────────────────────────────────
def check_service(key):
    """Check a single service. Returns (key, name, alive, latency_ms)."""
    svc = SERVICES[key]
    t0 = time.time()
    if key == "telegram":
        alive = telegram_bot_running()
    elif svc["url"]:
        alive = http_check(svc["url"])
    else:
        alive = port_listening(svc["port"]) if svc["port"] else False
    latency = round((time.time() - t0) * 1000)
    return key, svc["name"], alive, latency

def check_all():
    """Check all services, return dict of results."""
    results = {}
    for key in SERVICES:
        k, name, alive, lat = check_service(key)
        results[k] = {"name": name, "alive": alive, "latency_ms": lat}
    return results

# ── HEALTH GRADE ──────────────────────────────────────────────────────
def compute_grade(results):
    """Compute weighted health grade from results."""
    total_weight = sum(s["weight"] for s in SERVICES.values())
    earned = 0
    down = []
    for key, svc in SERVICES.items():
        if results[key]["alive"]:
            earned += svc["weight"]
        else:
            down.append((key, svc["name"], svc["critical"]))
    score = round(earned * 100 / total_weight) if total_weight else 0
    if score >= 95:   grade = "A+"
    elif score >= 85: grade = "A"
    elif score >= 70: grade = "B"
    elif score >= 50: grade = "C"
    else:             grade = "D"
    return grade, score, down

# ── RESTART ───────────────────────────────────────────────────────────
def restart_service(key):
    """Restart a service by key. Returns True on launch."""
    if key not in RESTART_CMDS:
        log.error(f"No restart command for '{key}'. Available: {', '.join(RESTART_CMDS)}")
        return False
    cfg = RESTART_CMDS[key]
    log.info(f"Restarting {SERVICES[key]['name']}...")
    try:
        subprocess.Popen(
            cfg["cmd"], shell=True, cwd=cfg["cwd"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
        )
        log.info(f"  -> {SERVICES[key]['name']} restart launched")
        return True
    except Exception as e:
        log.error(f"  -> Restart failed: {e}")
        return False

# ── DISPLAY ───────────────────────────────────────────────────────────
def format_status(results, grade, score, down, elapsed):
    """Format a human-readable status block."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"{'=' * 50}",
        f"JARVIS SUPERVISOR  |  Grade {grade} ({score}/100)  |  {ts}",
        f"{'=' * 50}",
    ]
    for key in SERVICES:
        r = results[key]
        status = "UP" if r["alive"] else "DOWN"
        port_str = f":{SERVICES[key]['port']}" if SERVICES[key]["port"] else "    "
        crit = " [CRITICAL]" if not r["alive"] and SERVICES[key]["critical"] else ""
        lines.append(f"  {port_str:>6}  {r['name']:<18} {status:<5} ({r['latency_ms']}ms){crit}")
    if down:
        lines.append("")
        lines.append("  ISSUES:")
        for key, name, crit in down:
            tag = "CRITICAL" if crit else "WARNING"
            lines.append(f"    - {tag}: {name} is DOWN")
    lines.append(f"{'=' * 50}")
    lines.append(f"  Scan completed in {elapsed}s")
    return "\n".join(lines)

# ── MAIN LOOPS ────────────────────────────────────────────────────────
def one_shot():
    """Single status check."""
    t0 = time.time()
    results = check_all()
    grade, score, down = compute_grade(results)
    elapsed = round(time.time() - t0, 1)
    print(format_status(results, grade, score, down, elapsed))
    return grade, score, down

def watch_loop():
    """Continuous monitoring with auto-restart and Telegram alerts."""
    log.info("Supervisor started — watching every %ds", INTERVAL)
    prev_down = set()
    while True:
        try:
            t0 = time.time()
            results = check_all()
            grade, score, down = compute_grade(results)
            elapsed = round(time.time() - t0, 1)
            print(format_status(results, grade, score, down, elapsed))

            # Detect newly-down critical services
            cur_down = {k for k, _, _ in down}
            newly_down = cur_down - prev_down
            recovered = prev_down - cur_down

            for key in recovered:
                name = SERVICES[key]["name"]
                log.info(f"RECOVERED: {name} is back UP")
                send_telegram(f"<b>JARVIS</b> {name} RECOVERED")

            for key, name, crit in down:
                if key in newly_down:
                    log.warning(f"DOWN: {name} (critical={crit})")
                    if crit:
                        send_telegram(f"<b>JARVIS ALERT</b> {name} is DOWN (grade {grade})")
                    # Auto-restart if we have a command for it
                    if key in RESTART_CMDS:
                        ok = restart_service(key)
                        if ok:
                            send_telegram(f"<b>JARVIS</b> Auto-restart launched: {name}")

            prev_down = cur_down
            time.sleep(INTERVAL)
        except KeyboardInterrupt:
            log.info("Supervisor stopped by user")
            break
        except Exception as e:
            log.error(f"Supervisor loop error: {e}")
            time.sleep(INTERVAL)

# ── CLI ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = sys.argv[1:]

    if "--watch" in args:
        watch_loop()
    elif "--restart" in args:
        idx = args.index("--restart")
        key = args[idx + 1] if idx + 1 < len(args) else None
        if not key or key not in SERVICES:
            print(f"Usage: --restart <{'|'.join(RESTART_CMDS)}>"  )
            sys.exit(1)
        restart_service(key)
    else:
        one_shot()
