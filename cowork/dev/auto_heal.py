#!/usr/bin/env python3
"""Auto-heal: check critical ports and restart missing services."""
import argparse
import json
import socket
import subprocess
import time
import sys

SERVICES = {
    "WS": {
        "port": 9742, "host": "127.0.0.1",
        "restart_cmd": ["python", "-m", "uvicorn", "python_ws.server:app",
                        "--host", "127.0.0.1", "--port", "9742"],
        "cwd": "/home/turbo/jarvis-m1-ops",
    },
    "LMStudio": {
        "port": 1234, "host": "127.0.0.1",
        "restart_cmd": None,  # External, cannot restart from script
    },
    "Ollama": {
        "port": 11434, "host": "127.0.0.1",
        "restart_cmd": ["ollama", "serve"],
    },
    "OpenClaw": {
        "port": 18789, "host": "127.0.0.1",
        "restart_cmd": None,  # External gateway
    },
}


def check_port(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, TimeoutError):
        return False


def attempt_restart(name: str, cfg: dict) -> dict:
    cmd = cfg.get("restart_cmd")
    if not cmd:
        return {"action": "skip", "reason": f"{name} has no restart command"}
    try:
        proc = subprocess.Popen(
            cmd, cwd=cfg.get("cwd"),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            if sys.platform == "win32" else 0,
        )
        time.sleep(3)
        alive = check_port(cfg["host"], cfg["port"])
        return {"action": "restarted", "pid": proc.pid, "alive_after": alive}
    except (FileNotFoundError, OSError) as e:
        return {"action": "failed", "error": str(e)}


def heal_cycle(do_restart: bool = True) -> dict:
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    results = {}
    healed = 0
    down = 0
    for name, cfg in SERVICES.items():
        alive = check_port(cfg.get("host", "127.0.0.1"), cfg["port"])
        entry = {"port": cfg["port"], "alive": alive}
        if not alive:
            down += 1
            if do_restart:
                entry["heal"] = attempt_restart(name, cfg)
                if entry["heal"].get("alive_after"):
                    healed += 1
        results[name] = entry
    return {
        "timestamp": ts,
        "services": results,
        "down": down,
        "healed": healed,
        "all_ok": down == 0 or healed == down,
    }


def main():
    parser = argparse.ArgumentParser(description="Auto-heal JARVIS services")
    parser.add_argument("--once", action="store_true", help="Single run then exit")
    parser.add_argument("--interval", type=int, default=60, help="Loop interval (sec)")
    parser.add_argument("--check-only", action="store_true", help="No restart attempts")
    args = parser.parse_args()

    while True:
        result = heal_cycle(do_restart=not args.check_only)
        print(json.dumps(result, ensure_ascii=False), flush=True)
        if args.once:
            sys.exit(0 if result["all_ok"] else 1)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
