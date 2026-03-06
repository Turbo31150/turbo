"""Collab CLI — Command-line interface for the collab bridge.

Usage:
    python collab_cli.py next
    python collab_cli.py stats
    python collab_cli.py get <task_id>
    python collab_cli.py list [status]
    python collab_cli.py create <json>
    python collab_cli.py claim <task_id>
    python collab_cli.py complete <task_id> <json>
    python collab_cli.py cancel <task_id>
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.collab_bridge import (
    create_task, get_pending_tasks, claim_task,
    complete_task, get_task, list_tasks, cancel_task, stats,
)


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "usage: collab_cli.py <command> [args]"}))
        return

    cmd = sys.argv[1]

    if cmd == "next":
        p = get_pending_tasks("perplexity")
        print(json.dumps({"task": p[0] if p else None}))

    elif cmd == "stats":
        print(json.dumps(stats()))

    elif cmd == "get" and len(sys.argv) > 2:
        t = get_task(sys.argv[2])
        print(json.dumps(t or {"error": "not found"}))

    elif cmd == "list":
        status = sys.argv[2] if len(sys.argv) > 2 else None
        print(json.dumps(list_tasks(status=status)))

    elif cmd == "create":
        data = json.loads(sys.argv[2]) if len(sys.argv) > 2 else json.load(sys.stdin)
        print(json.dumps(create_task(**data)))

    elif cmd == "claim" and len(sys.argv) > 2:
        print(json.dumps(claim_task(sys.argv[2]) or {"error": "not found"}))

    elif cmd == "complete" and len(sys.argv) > 2:
        data = json.loads(sys.argv[3]) if len(sys.argv) > 3 else json.load(sys.stdin)
        print(json.dumps(
            complete_task(sys.argv[2], data.get("result", ""), data.get("success", True))
            or {"error": "not found"}
        ))

    elif cmd == "cancel" and len(sys.argv) > 2:
        print(json.dumps(cancel_task(sys.argv[2]) or {"error": "not found"}))

    else:
        print(json.dumps({"error": f"unknown command: {cmd}"}))


if __name__ == "__main__":
    main()
