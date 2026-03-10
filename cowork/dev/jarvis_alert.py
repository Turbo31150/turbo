#!/usr/bin/env python3
"""JARVIS Alert System — send alerts via Telegram."""
import argparse, json, os, urllib.request, urllib.parse

def load_env():
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

def send_telegram(message: str) -> bool:
    load_env()
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "2010747443")
    if not token:
        print("No TELEGRAM_BOT_TOKEN found")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": message}).encode()
    try:
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"Telegram error: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="JARVIS Alert via Telegram")
    parser.add_argument("message", nargs="?", default="JARVIS Alert: system check required")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--level", choices=["info", "warn", "critical"], default="info")
    args = parser.parse_args()

    prefix = {"info": "[INFO]", "warn": "[WARN]", "critical": "[CRITICAL]"}
    full_msg = f"{prefix[args.level]} {args.message}"

    if send_telegram(full_msg):
        print(f"Alert sent: {full_msg}")
    else:
        print(f"Alert failed (logged locally): {full_msg}")

if __name__ == "__main__":
    main()
