#!/usr/bin/env python3
"""JARVIS Production Auto-Improve — Validates, diagnoses, and auto-fixes issues.

Runs production_validator.run_validation(), analyzes results, applies safe fixes,
and sends a Telegram summary.

Usage:
    python scripts/production_auto_improve.py --once        # Single run
    python scripts/production_auto_improve.py --daemon      # Loop every 15 min
    python scripts/production_auto_improve.py --dry-run     # Analyze without fixing
"""
from __future__ import annotations
import argparse, json, logging, os, signal, socket, subprocess, sys, time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

_env = ROOT / ".env"
if _env.exists():
    for _l in _env.read_text(encoding="utf-8", errors="ignore").splitlines():
        _l = _l.strip()
        if _l and not _l.startswith("#") and "=" in _l:
            _k, _, _v = _l.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

LOG_FILE = ROOT / "logs" / "production_auto_improve.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()],
)
log = logging.getLogger("production_auto_improve")

WS_HOST, WS_PORT = "127.0.0.1", 9742
M1_HOST, M1_PORT = "127.0.0.1", 1234
M3_HOST, M3_PORT = "192.168.1.113", 1234
DAEMON_INTERVAL = 900
_running = True

def _signal_handler(sig, frame):
    global _running; _running = False; log.info("Shutdown requested")
signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)

# ── Helpers ──────────────────────────────────────────────────────────
def _http_post(host, port, path, data, timeout=10.0):
    try:
        req = urllib.request.Request(
            f"http://{host}:{port}{path}", data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception: return None

def _http_get(host, port, path, timeout=5.0):
    try:
        with urllib.request.urlopen(f"http://{host}:{port}{path}", timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception: return None

def _check_port(host, port, timeout=2.0):
    try:
        with socket.create_connection((host, port), timeout=timeout): return True
    except (OSError, ConnectionRefusedError, TimeoutError): return False

def _send_telegram(message):
    try:
        req = urllib.request.Request(
            f"http://{WS_HOST}:{WS_PORT}/api/telegram/send",
            data=json.dumps({"message": message[:4000]}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode()).get("ok", False)
    except Exception: return False

# ── Fix actions (safe, non-destructive) ──────────────────────────────
def fix_ws_down():
    if _check_port(WS_HOST, WS_PORT): return "WS already up"
    log.info("Starting WS :9742...")
    try:
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        subprocess.Popen(
            ["uv", "run", "python", "-m", "uvicorn", "python_ws.server:app",
             "--host", "127.0.0.1", "--port", "9742"],
            cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=flags)
        time.sleep(7)
        return "WS started OK" if _check_port(WS_HOST, WS_PORT) else "WS start attempted, not yet responding"
    except Exception as e: return f"WS start failed: {e}"

def fix_m1_model():
    log.info("Loading qwen3-8b on M1...")
    resp = _http_post(M1_HOST, M1_PORT, "/v1/chat/completions", {
        "model": "qwen3-8b", "messages": [{"role": "user", "content": "/nothink\nhi"}],
        "max_tokens": 1, "stream": False}, timeout=30.0)
    return "qwen3-8b loaded on M1" if resp and resp.get("choices") else "qwen3-8b load request sent (may still be loading)"

def fix_m3_model():
    if not _check_port(M3_HOST, M3_PORT): return "M3 OFFLINE, cannot load model"
    log.info("Loading deepseek-r1 on M3...")
    resp = _http_post(M3_HOST, M3_PORT, "/v1/chat/completions", {
        "model": "deepseek-r1-0528-qwen3-8b", "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 1, "stream": False}, timeout=60.0)
    return "deepseek-r1 loaded on M3" if resp and resp.get("choices") else "deepseek-r1 load request sent to M3"

def log_intent_misses(results):
    for r in results:
        if r.name == "Intent Classifier" and r.score < 100:
            misses = [d for d in r.details if d.startswith("Miss:")]
            for m in misses: log.warning("Intent miss: %s", m)
            if misses: return f"Logged {len(misses)} intent miss(es)"
    return "No intent misses"

# ── Main cycle ───────────────────────────────────────────────────────
def run_cycle(dry_run=False):
    """Run one validate-and-fix cycle. Returns summary dict."""
    from production_validator import run_validation, to_json
    log.info("=== Auto-Improve cycle start ===")
    results = run_validation(quick=False)
    report = to_json(results)
    fixes = []

    for layer in report["layers"]:
        fixable = layer.get("fixable", [])
        name = layer["name"]
        details = layer["details"]
        # WS down
        if "restart_ws" in fixable or (name == "Services" and any("9742" in d and "OFFLINE" in d for d in details)):
            fixes.append("[DRY] Would start WS :9742" if dry_run else fix_ws_down())
        # M1 qwen3-8b not loaded
        if "load_qwen3_8b" in fixable:
            fixes.append("[DRY] Would load qwen3-8b on M1" if dry_run else fix_m1_model())
        # M3 deepseek-r1 missing
        if name == "Heavy Reasoning Models":
            m3_bad = any("M3_deepseek-r1" in d and ("not found" in d or "OFFLINE" in d) for d in details)
            if m3_bad and _check_port(M3_HOST, M3_PORT):
                fixes.append("[DRY] Would load deepseek-r1 on M3" if dry_run else fix_m3_model())

    # Intent classifier misses
    ic = next((l for l in report["layers"] if l["name"] == "Intent Classifier"), None)
    if ic and ic["score"] < 100:
        fixes.append(log_intent_misses(results))

    summary = {"timestamp": datetime.now().isoformat(), "grade": report["grade"],
                "score": report["score"], "fixes": fixes, "dry_run": dry_run}

    log.info("Grade: %s (%s/100) | Fixes: %d", summary["grade"], summary["score"], len(fixes))
    for f in fixes: log.info("  -> %s", f)

    if fixes and not dry_run:
        tg = f"[Auto-Improve] {summary['grade']} ({summary['score']}/100)\n" + "\n".join(f"- {f}" for f in fixes)
        summary["telegram"] = "sent" if _send_telegram(tg) else "failed"

    log.info("=== Auto-Improve cycle end ===")
    return summary

# ── Entry points ─────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(description="JARVIS Production Auto-Improve")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="Single run then exit")
    mode.add_argument("--daemon", action="store_true", help="Loop every 15 minutes")
    p.add_argument("--dry-run", action="store_true", help="Analyze without applying fixes")
    args = p.parse_args()
    if args.once:
        print(json.dumps(run_cycle(dry_run=args.dry_run), indent=2))
    elif args.daemon:
        log.info("Daemon mode — interval %ds", DAEMON_INTERVAL)
        while _running:
            try: run_cycle(dry_run=args.dry_run)
            except Exception as e: log.error("Cycle error: %s", e)
            for _ in range(DAEMON_INTERVAL):
                if not _running: break
                time.sleep(1)
        log.info("Daemon stopped")

if __name__ == "__main__":
    main()
