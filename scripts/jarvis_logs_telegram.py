#!/usr/bin/env python3
"""JARVIS Logs — Show recent unified console logs for Telegram.
Usage: python jarvis_logs_telegram.py [N] [filter]
  N = number of lines (default 30)
  filter = keyword to filter (optional)
"""
import re, sys
from pathlib import Path

LOG_FILE = Path("/home/turbo/jarvis-m1-ops/data/jarvis_unified.log")
SUPERVISOR_LOG = Path("/home/turbo/jarvis-m1-ops/data/supervisor.log")

def read_logs(filepath, n=30, filt=None):
    if not filepath.exists():
        return f"Log file not found: {filepath}"
    raw = filepath.read_text(encoding="utf-8", errors="replace")
    # Strip ANSI escape codes
    lines = [re.sub(r'\x1b\[[0-9;]*m', '', l) for l in raw.splitlines()]
    if filt:
        lines = [l for l in lines if filt.lower() in l.lower()]
    recent = lines[-n:] if len(lines) > n else lines
    return "\n".join(recent) if recent else "No matching lines"

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = sys.argv[1:]

    n = 30
    filt = None
    log = LOG_FILE

    for a in args:
        if a.isdigit():
            n = int(a)
        elif a in ("supervisor", "super", "sup"):
            log = SUPERVISOR_LOG
        elif a in ("error", "errors", "err"):
            filt = "ERROR"
        elif a in ("warn", "warning"):
            filt = "WARN"
        else:
            filt = a

    header = f"LOGS ({log.name}, last {n}"
    if filt:
        header += f", filter='{filt}'"
    header += ")"

    print(header)
    print("-" * len(header))
    print(read_logs(log, n, filt))
