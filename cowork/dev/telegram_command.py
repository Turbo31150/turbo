#!/usr/bin/env python3
"""Check Telegram for recent commands via JARVIS WS API."""

import argparse
import json
import time
import urllib.request
import urllib.error

HISTORY_URL = "http://127.0.0.1:9742/api/telegram/history"


def fetch(url, timeout=10):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}


def extract_commands(history, limit=20):
    """Extract command-like messages (starting with /) from history."""
    messages = []
    if isinstance(history, dict):
        messages = history.get("messages", history.get("history", []))
    elif isinstance(history, list):
        messages = history

    commands = []
    for msg in messages:
        text = ""
        if isinstance(msg, dict):
            text = msg.get("text", msg.get("message", msg.get("content", "")))
        elif isinstance(msg, str):
            text = msg
        if text.strip().startswith("/"):
            commands.append({
                "command": text.strip(),
                "timestamp": msg.get("timestamp", msg.get("date", "")) if isinstance(msg, dict) else "",
                "from": msg.get("from", msg.get("user", "")) if isinstance(msg, dict) else "",
            })

    return commands[:limit]


def run_once():
    data = fetch(HISTORY_URL)

    if "error" in data:
        output = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "status": "UNREACHABLE",
            "error": data["error"],
            "commands": [],
        }
    else:
        commands = extract_commands(data)
        output = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "status": "OK",
            "total_commands_found": len(commands),
            "commands": commands,
            "raw_message_count": len(data) if isinstance(data, list)
                else len(data.get("messages", data.get("history", []))),
        }
    print(json.dumps(output, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="Check Telegram for recent commands")
    parser.add_argument("--once", action="store_true", help="Single run then exit")
    args = parser.parse_args()

    if args.once:
        run_once()
    else:
        print("Use --once for a single run. Use --help for options.")


if __name__ == "__main__":
    main()
