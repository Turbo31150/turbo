#!/usr/bin/env python3
"""JARVIS Singleton Guard — CLI wrapper pour process_singleton.

Wrapper CLI universel utilise par TOUS les launchers BAT pour garantir
qu'un seul exemplaire de chaque service tourne a la fois.
Delegue a src/process_singleton.py (le vrai moteur singleton).

Usage BAT:
    python scripts/singleton_guard.py --name orchestrator --kill
    python scripts/singleton_guard.py --name dashboard --kill --port 8080
    python scripts/singleton_guard.py --list
    python scripts/singleton_guard.py --cleanup

Usage Python (depuis scripts/):
    from singleton_guard import acquire, release
    acquire("orchestrator")
    ...
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Add parent so we can import from src/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.process_singleton import singleton


def acquire(name: str, port: int | None = None) -> bool:
    """Kill existing + register current PID. Returns True on success."""
    try:
        singleton.acquire(name, pid=os.getpid(), port=port)
        return True
    except Exception as e:
        print(f"  [SINGLETON] {name}: echec acquire: {e}")
        return False


def release(name: str):
    """Release singleton lock."""
    singleton.release(name)


def main():
    parser = argparse.ArgumentParser(description="JARVIS Singleton Guard (CLI)")
    parser.add_argument("--name", help="Service name")
    parser.add_argument("--kill", action="store_true", help="Kill existing + acquire lock")
    parser.add_argument("--port", type=int, help="Also kill on this TCP port")
    parser.add_argument("--release", action="store_true", help="Release lock")
    parser.add_argument("--status", action="store_true", help="Show status of a service")
    parser.add_argument("--list", action="store_true", help="List all services")
    parser.add_argument("--cleanup", action="store_true", help="Remove stale PID files")
    parser.add_argument("--kill-all", action="store_true", help="Kill ALL registered services")
    args = parser.parse_args()

    if args.list:
        services = singleton.list_all()
        if not services:
            print("  Aucun service enregistre")
        else:
            print(f"\n  {'Service':25} {'PID':8} {'Status'}")
            print(f"  {'-'*25} {'-'*8} {'-'*10}")
            for name, info in services.items():
                status = "RUNNING" if info["alive"] else "DEAD"
                pid = str(info["pid"] or "-")
                print(f"  {name:25} {pid:8} {status}")
        return

    if args.cleanup:
        cleaned = singleton.cleanup_dead()
        print(f"  Cleaned {len(cleaned)} stale PIDs: {', '.join(cleaned) if cleaned else 'none'}")
        return

    if args.kill_all:
        killed = singleton.kill_all()
        print(f"  Killed {len(killed)} services: {', '.join(killed) if killed else 'none'}")
        return

    if not args.name:
        parser.print_help()
        sys.exit(1)

    if args.status:
        alive, pid = singleton.is_running(args.name)
        status = "RUNNING" if alive else "STOPPED"
        print(f"  {args.name}: {status} (PID {pid or '-'})")
        sys.exit(0 if alive else 1)

    if args.release:
        singleton.release(args.name)
        print(f"  {args.name}: released")
        return

    if args.kill:
        # Kill existing, acquire for current PID, then release immediately
        # (the BAT will start the real daemon process right after)
        singleton.acquire(args.name, pid=0, port=args.port)
        # Release so the daemon process can re-acquire with its own PID
        singleton.release(args.name)
        print(f"  {args.name}: existing killed, ready for launch")
        return

    # Default: acquire and hold (for Python daemon use)
    ok = acquire(args.name, port=args.port)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
