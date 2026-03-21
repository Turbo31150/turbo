#!/usr/bin/env python3
"""Docker health monitor — Check jarvis-cowork-* containers, restart if exited, log status."""
import argparse
import json
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ETOILE_DB = Path("F:/BUREAU/turbo/etoile.db")
CONTAINER_PREFIX = "jarvis-cowork-"
INTERVAL_SECONDS = 120  # 2 minutes


def run_docker(args: list) -> str:
    """Run a docker command and return stdout."""
    try:
        r = subprocess.run(
            ["docker"] + args, capture_output=True, text=True, timeout=30,
        )
        return r.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return ""


def list_containers() -> list:
    """List all jarvis-cowork-* containers with status."""
    output = run_docker([
        "ps", "-a", "--filter", f"name={CONTAINER_PREFIX}",
        "--format", "{{.Names}}|{{.Status}}|{{.Image}}|{{.ID}}"
    ])
    if not output:
        return []
    containers = []
    for line in output.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("|")
        if len(parts) >= 4:
            status_text = parts[1].lower()
            running = "up" in status_text
            containers.append({
                "name": parts[0], "status_text": parts[1],
                "image": parts[2], "id": parts[3],
                "running": running,
            })
    return containers


def restart_container(container_id: str) -> bool:
    """Restart an exited container."""
    result = run_docker(["restart", container_id])
    if result or not result:  # docker restart returns empty on success
        time.sleep(3)
        check = run_docker(["inspect", "-f", "{{.State.Running}}", container_id])
        return check.strip().lower() == "true"
    return False


def log_to_db(container: str, status: str, action: str) -> None:
    """Log container status to etoile.db."""
    if not ETOILE_DB.exists():
        return
    ts = datetime.now(timezone.utc).isoformat()
    try:
        conn = sqlite3.connect(str(ETOILE_DB), timeout=5)
        conn.execute(
            "INSERT INTO cluster_health (timestamp, node, status, model, latency_ms) "
            "VALUES (?, ?, ?, ?, ?)",
            (ts, f"docker_{container}", status, action, 0),
        )
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        print(f"[WARN] DB error: {e}", file=sys.stderr)


def check_all(auto_restart: bool = True) -> dict:
    """Check all jarvis-cowork containers."""
    # Verify docker is available
    version = run_docker(["version", "--format", "{{.Server.Version}}"])
    if not version:
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "ERROR", "error": "Docker not available",
            "containers": [],
        }
    containers = list_containers()
    results = []
    restarted = 0
    for c in containers:
        action = "none"
        if not c["running"] and auto_restart:
            ok = restart_container(c["id"])
            action = "restarted_ok" if ok else "restart_failed"
            c["running"] = ok
            restarted += 1
        status = "running" if c["running"] else "exited"
        results.append({
            "name": c["name"], "status": status,
            "image": c["image"], "action": action,
        })
        if action != "none" or not c["running"]:
            log_to_db(c["name"], status.upper(), action)
    all_ok = all(r["status"] == "running" for r in results)
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "docker_version": version,
        "status": "OK" if all_ok else "DEGRADED",
        "total": len(results),
        "running": sum(1 for r in results if r["status"] == "running"),
        "restarted": restarted,
        "containers": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Docker health monitor for jarvis-cowork containers")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--no-restart", action="store_true", help="Check only, no restart")
    args = parser.parse_args()
    while True:
        result = check_all(auto_restart=not args.no_restart)
        print(json.dumps(result, indent=2))
        if args.once:
            break
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
