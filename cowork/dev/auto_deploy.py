#!/usr/bin/env python3
"""Auto-deploy JARVIS: git pull + verify services."""
import argparse
import json
import subprocess
import socket
import time
import sys

TURBO_DIR = "/home/turbo/jarvis-m1-ops"
SERVICES = {
    "WS": {"port": 9742, "host": "127.0.0.1"},
    "LMStudio": {"port": 1234, "host": "127.0.0.1"},
    "Ollama": {"port": 11434, "host": "127.0.0.1"},
}


def check_port(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, TimeoutError):
        return False


def git_pull(repo_dir: str) -> dict:
    try:
        result = subprocess.run(
            ["git", "pull", "--ff-only"],
            cwd=repo_dir, capture_output=True, text=True, timeout=60
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "stdout": "", "stderr": "git pull timeout (60s)"}
    except FileNotFoundError:
        return {"success": False, "stdout": "", "stderr": "git not found"}


def deploy_cycle() -> dict:
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    pull = git_pull(TURBO_DIR)
    services = {}
    all_ok = True
    for name, cfg in SERVICES.items():
        alive = check_port(cfg["host"], cfg["port"])
        services[name] = {"port": cfg["port"], "alive": alive}
        if not alive:
            all_ok = False
    return {
        "timestamp": ts,
        "git_pull": pull,
        "services": services,
        "all_services_ok": all_ok,
        "deploy_ok": pull["success"] and all_ok,
    }


def main():
    parser = argparse.ArgumentParser(description="Auto-deploy JARVIS")
    parser.add_argument("--once", action="store_true", help="Single run then exit")
    parser.add_argument("--interval", type=int, default=300, help="Loop interval (sec)")
    args = parser.parse_args()

    while True:
        result = deploy_cycle()
        print(json.dumps(result, ensure_ascii=False), flush=True)
        if args.once:
            sys.exit(0 if result["deploy_ok"] else 1)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
