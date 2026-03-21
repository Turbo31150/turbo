#!/usr/bin/env python3
"""Cowork wrapper: prompt_library — re-index + stats."""
import subprocess, sys, json
from pathlib import Path

SCRIPT = Path("F:/BUREAU/turbo/scripts/prompt_library.py")

def main():
    # Re-index
    subprocess.run([sys.executable, str(SCRIPT), "--index"],
                   capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace")
    # Get stats
    r = subprocess.run([sys.executable, str(SCRIPT), "--score", "--json"],
                       capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace")
    if r.stdout.strip():
        data = json.loads(r.stdout)
        print(json.dumps({"success": True, "total": data.get("total", 0),
                           "avg_score": data.get("avg_score", 0)}))
    else:
        print(json.dumps({"success": True, "indexed": True}))

if __name__ == "__main__":
    main()
