#!/usr/bin/env python3
"""Recreate hardlinks after git clone or disk restore.

etoile.db lives in data/ but 52+ src/ files reference the root path.
A hardlink makes both paths point to the same physical file on NTFS.

Usage:
    python scripts/tools/setup_hardlinks.py
"""
import os
import subprocess
import sys
from pathlib import Path

TURBO = Path(__file__).resolve().parent.parent.parent

LINKS = [
    # (link_path_relative, target_path_relative)
    ("etoile.db", "data/etoile.db"),
]


def create_hardlink(link: Path, target: Path) -> bool:
    if not target.exists():
        print(f"  SKIP: {target} does not exist")
        return False

    if link.exists():
        # Check if already same file (hardlink)
        if os.path.samefile(str(link), str(target)):
            print(f"  OK: {link.name} already hardlinked to {target}")
            return True
        # Different file — remove and recreate
        link.unlink()
        print(f"  REMOVED stale {link.name}")

    try:
        result = subprocess.run(
            ["powershell", "-Command",
             f'New-Item -ItemType HardLink -Path "{link}" -Target "{target}"'],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            print(f"  CREATED: {link.name} -> {target}")
            return True
        else:
            print(f"  FAIL: {result.stderr.strip()}")
            return False
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def main():
    print("=== Setup JARVIS Hardlinks ===")
    ok = 0
    for link_rel, target_rel in LINKS:
        link = TURBO / link_rel
        target = TURBO / target_rel
        if create_hardlink(link, target):
            ok += 1
    print(f"\n{ok}/{len(LINKS)} hardlinks OK")
    return 0 if ok == len(LINKS) else 1


if __name__ == "__main__":
    sys.exit(main())
