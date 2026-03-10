#!/usr/bin/env python3
"""Send a notification to Telegram via JARVIS WS API."""

import argparse
import json
import urllib.request
import urllib.error
import time

SEND_URL = "http://127.0.0.1:9742/api/telegram/send"


def send_message(message, timeout=10):
    """Send message via Telegram API endpoint."""
    payload = json.dumps({"message": message}).encode()
    req = urllib.request.Request(
        SEND_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        return {"error": str(e), "status": e.code, "body": body}
    except Exception as e:
        return {"error": str(e)}


def run_once(message):
    t0 = time.perf_counter()
    result = send_message(message)
    elapsed = round(time.perf_counter() - t0, 3)

    output = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "message_sent": message,
        "latency_s": elapsed,
        "success": "error" not in result,
        "response": result,
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="Send Telegram notification via JARVIS API")
    parser.add_argument("--once", action="store_true", help="Single run then exit")
    parser.add_argument("--message", "-m", type=str, default="JARVIS cowork notification test",
                        help="Message to send (default: test message)")
    args = parser.parse_args()

    if args.once:
        run_once(args.message)
    else:
        print("Use --once for a single run. Use --help for options.")


if __name__ == "__main__":
    main()
