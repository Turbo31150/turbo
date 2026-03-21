#!/usr/bin/env python3
"""Cowork wrapper: kill_phantoms — invoque le script principal."""
import subprocess, sys, json
from pathlib import Path

SCRIPT = Path("F:/BUREAU/turbo/scripts/kill_phantoms.py")

def main():
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        capture_output=True, text=True, timeout=30,
        encoding="utf-8", errors="replace"
    )
    if r.stdout.strip():
        data = json.loads(r.stdout)
        killed = data.get("killed", 0)
        print(json.dumps({"success": True, "killed": killed, "mem_freed_mb": data.get("mem_freed_mb", 0)}))
    else:
        print(json.dumps({"success": True, "killed": 0}))

if __name__ == "__main__":
    main()
