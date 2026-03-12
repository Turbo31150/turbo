"""OpenClaw Watchdog — DevOps Daemon.

Surveille en continu:
1. Gateway (port 18789)
2. Gemini OpenAI proxy (port 18793)
3. Provider health (6 providers)
4. Session garbage collection (toutes les heures)

Redémarre automatiquement les services down.

Usage:
    python scripts/openclaw_watchdog.py [--once] [--interval 60]
"""
import argparse
import json
import logging
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_FILE = ROOT / "data" / "openclaw_watchdog.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [WATCHDOG] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(str(LOG_FILE), encoding="utf-8"),
    ],
)
log = logging.getLogger("openclaw_watchdog")


def check_port(host: str, port: int, timeout: float = 3) -> bool:
    """Check if a port is responding to HTTP."""
    try:
        urllib.request.urlopen(f"http://{host}:{port}/", timeout=timeout)
        return True
    except Exception:
        try:
            urllib.request.urlopen(f"http://{host}:{port}/health", timeout=timeout)
            return True
        except Exception:
            return False


def restart_gemini_proxy():
    """Restart the Gemini OpenAI proxy."""
    proxy_path = ROOT / "gemini-openai-proxy.js"
    if not proxy_path.exists():
        log.warning("Gemini proxy not found: %s", proxy_path)
        return False
    try:
        subprocess.Popen(
            ["node", str(proxy_path)],
            cwd=str(ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        time.sleep(3)
        alive = check_port("127.0.0.1", 18793)
        log.info("Gemini proxy restart: %s", "OK" if alive else "FAILED")
        return alive
    except Exception as e:
        log.error("Gemini proxy restart error: %s", e)
        return False


def restart_gateway():
    """Restart the OpenClaw gateway."""
    openclaw_dir = Path.home() / ".openclaw"
    try:
        subprocess.Popen(
            ["npx", "openclaw", "gateway", "--port", "18789"],
            cwd=str(openclaw_dir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            shell=True,
        )
        time.sleep(8)
        alive = check_port("127.0.0.1", 18789)
        log.info("Gateway restart: %s", "OK" if alive else "FAILED")
        return alive
    except Exception as e:
        log.error("Gateway restart error: %s", e)
        return False


def run_session_gc():
    """Run session garbage collection."""
    try:
        from openclaw_session_gc import run_gc
        result = run_gc(max_sessions=2, max_days=3, dry_run=False)
        if result.get("total_deleted", 0) > 0:
            log.info("Session GC: %d files deleted", result["total_deleted"])
        return result
    except ImportError:
        gc_script = ROOT / "scripts" / "openclaw_session_gc.py"
        if gc_script.exists():
            subprocess.run([sys.executable, str(gc_script)], capture_output=True, timeout=30)
            return {"status": "ran_external"}
        return {"status": "gc_not_found"}


def run_cycle() -> dict:
    """Run one watchdog cycle."""
    report = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")}

    # Check gateway
    gw_alive = check_port("127.0.0.1", 18789)
    report["gateway"] = "UP" if gw_alive else "DOWN"
    if not gw_alive:
        log.warning("Gateway DOWN — attempting restart")
        restart_gateway()
        report["gateway_action"] = "restarted"

    # Check Gemini proxy
    gp_alive = check_port("127.0.0.1", 18793)
    report["gemini_proxy"] = "UP" if gp_alive else "DOWN"
    if not gp_alive:
        log.warning("Gemini proxy DOWN — attempting restart")
        restart_gemini_proxy()
        report["gemini_action"] = "restarted"

    # Check M1 LM Studio
    m1_alive = check_port("127.0.0.1", 1234)
    report["m1"] = "UP" if m1_alive else "DOWN"

    # Check OL1 Ollama
    ol1_alive = check_port("127.0.0.1", 11434)
    report["ol1"] = "UP" if ol1_alive else "DOWN"

    # Check JARVIS WS
    ws_alive = check_port("127.0.0.1", 9742)
    report["jarvis_ws"] = "UP" if ws_alive else "DOWN"

    healthy = sum(1 for k in ["gateway", "gemini_proxy", "m1", "ol1", "jarvis_ws"] if report.get(k) == "UP")
    report["healthy"] = f"{healthy}/5"

    log.info("Cycle: %s", report["healthy"])
    return report


def main():
    parser = argparse.ArgumentParser(description="OpenClaw Watchdog")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--interval", type=int, default=60, help="Check interval in seconds")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    log.info("OpenClaw Watchdog starting (interval=%ds)", args.interval)

    gc_last_run = 0
    gc_interval = 3600  # 1 hour

    while True:
        report = run_cycle()

        # Run GC every hour
        if time.time() - gc_last_run > gc_interval:
            run_session_gc()
            gc_last_run = time.time()

        if args.json:
            print(json.dumps(report))

        if args.once:
            break

        time.sleep(args.interval)


if __name__ == "__main__":
    main()
