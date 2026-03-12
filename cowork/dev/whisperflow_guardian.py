#!/usr/bin/env python3
"""WhisperFlow Guardian — Monitor and auto-restart the voice overlay.

Checks Electron process + WS backend (port 9742). Sends Telegram alerts on failures.
Pattern follows electron_app_monitor.py.

Usage:
    python whisperflow_guardian.py --once     # Single check
    python whisperflow_guardian.py --loop     # Continuous monitoring (60s interval)
    python whisperflow_guardian.py --restart  # Force restart WhisperFlow
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from _paths import TURBO_DIR, TELEGRAM_TOKEN, TELEGRAM_CHAT

WS_PORT = 9742
WHISPERFLOW_DIR = TURBO_DIR / "whisperflow"
CHECK_INTERVAL = 60


def check_whisperflow_process():
    """Check if WhisperFlow Electron process is running."""
    try:
        r = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq electron.exe", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=5,
        )
        return "electron.exe" in r.stdout.lower()
    except (subprocess.TimeoutExpired, OSError):
        return False


def check_ws_backend():
    """Check if the WS backend (port 9742) is responding."""
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{WS_PORT}/health")
        with urllib.request.urlopen(req, timeout=3):
            return True
    except Exception:
        return False


def restart_whisperflow():
    """Restart the WhisperFlow Electron app."""
    print("[RESTART] Launching WhisperFlow...")
    try:
        subprocess.Popen(
            ["electron", "."],
            cwd=str(WHISPERFLOW_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        time.sleep(5)
        return check_whisperflow_process()
    except OSError as e:
        print(f"[ERROR] Failed to restart: {e}")
        return False


def send_telegram_alert(message):
    """Send a Telegram alert."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        return
    try:
        data = json.dumps({"chat_id": TELEGRAM_CHAT, "text": message}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def status_check():
    """Perform a full status check and return results."""
    wf_alive = check_whisperflow_process()
    ws_alive = check_ws_backend()
    return {"whisperflow": wf_alive, "ws_backend": ws_alive}


def main():
    parser = argparse.ArgumentParser(description="WhisperFlow Guardian")
    parser.add_argument("--once", action="store_true", help="Single check")
    parser.add_argument("--loop", action="store_true", help="Continuous monitoring")
    parser.add_argument("--restart", action="store_true", help="Force restart")
    parser.add_argument("--interval", type=int, default=CHECK_INTERVAL)
    args = parser.parse_args()

    if args.restart:
        ok = restart_whisperflow()
        print("WhisperFlow restarted:" , "OK" if ok else "FAILED")
        sys.exit(0 if ok else 1)

    if args.once or not args.loop:
        s = status_check()
        wf = "RUNNING" if s["whisperflow"] else "OFFLINE"
        ws = "RUNNING" if s["ws_backend"] else "OFFLINE"
        print(f"WhisperFlow: {wf} | WS Backend (:{WS_PORT}): {ws}")
        if not s["whisperflow"] and s["ws_backend"]:
            print("WhisperFlow is down but WS backend is up — restart recommended")
        sys.exit(0 if s["whisperflow"] else 1)

    if args.loop:
        print(f"WhisperFlow Guardian — check every {args.interval}s")
        consecutive_failures = 0
        while True:
            try:
                s = status_check()
                ts = time.strftime("%H:%M")

                if s["whisperflow"]:
                    consecutive_failures = 0
                    print(f"[{ts}] WhisperFlow OK | WS: {'OK' if s['ws_backend'] else 'DOWN'}")
                else:
                    consecutive_failures += 1
                    print(f"[{ts}] WhisperFlow DOWN (failure #{consecutive_failures})")

                    if not s["ws_backend"]:
                        print(f"[{ts}] WS backend also down — skipping restart")
                    elif consecutive_failures <= 3:
                        ok = restart_whisperflow()
                        if ok:
                            print(f"[{ts}] WhisperFlow restarted OK")
                            send_telegram_alert("WhisperFlow was down and has been restarted.")
                        else:
                            print(f"[{ts}] WhisperFlow restart FAILED")
                            send_telegram_alert("WhisperFlow is down and restart failed!")

                time.sleep(args.interval)
            except KeyboardInterrupt:
                break


if __name__ == "__main__":
    main()
