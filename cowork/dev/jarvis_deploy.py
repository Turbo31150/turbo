#!/usr/bin/env python3
"""JARVIS Deploy — git pull + restart core services."""
import argparse, subprocess, sys, os

TURBO_DIR = os.path.join(os.path.dirname(__file__), "..", "..")

def run(cmd: str, cwd: str = None) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60, cwd=cwd)
        return r.returncode, r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        return 1, "Timeout"

def main():
    parser = argparse.ArgumentParser(description="Deploy JARVIS updates")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--skip-pull", action="store_true")
    parser.add_argument("--skip-restart", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    steps = []

    if not args.skip_pull:
        if args.dry_run:
            print("[DRY RUN] Would: git pull origin main")
        else:
            code, out = run("git pull origin main", cwd=TURBO_DIR)
            steps.append(("git pull", code == 0, out.strip()[:100]))
            print(f"Git pull: {'OK' if code == 0 else 'FAIL'} - {out.strip()[:100]}")

    if not args.skip_restart:
        services = [
            ("WS", "taskkill /F /IM python.exe /FI \"WINDOWTITLE eq jarvis_ws\" 2>nul & cd /d F:/BUREAU/turbo && start /b cmd /c \"title jarvis_ws && uv run python python_ws/server.py\""),
        ]
        for name, cmd in services:
            if args.dry_run:
                print(f"[DRY RUN] Would restart: {name}")
            else:
                code, out = run(cmd)
                steps.append((name, code == 0, out.strip()[:80]))
                print(f"Restart {name}: {'OK' if code == 0 else 'FAIL'}")

    success = all(s[1] for s in steps) if steps else True
    print(f"\nDeploy {'SUCCESS' if success else 'PARTIAL'}: {len([s for s in steps if s[1]])}/{len(steps)} steps OK")

if __name__ == "__main__":
    main()
