"""OpenClaw Session Garbage Collector — DevOps Auto-Cleanup.

Nettoie les sessions JSONL accumulées pour éviter le "Context size exceeded".
- Garde les N dernières sessions par agent (default: 2)
- Supprime les sessions > X jours (default: 3)
- Logge les actions dans data/openclaw_gc.log
- Peut tourner en cron ou via le scheduler JARVIS

Usage:
    python scripts/openclaw_session_gc.py [--max-sessions 2] [--max-days 3] [--dry-run]
"""
import argparse
import glob
import logging
import os
import time
from datetime import datetime
from pathlib import Path

OPENCLAW_DIR = Path.home() / ".openclaw"
AGENTS_DIR = OPENCLAW_DIR / "agents"
LOG_FILE = Path(__file__).resolve().parent.parent / "data" / "openclaw_gc.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [GC] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(str(LOG_FILE), encoding="utf-8"),
    ],
)
log = logging.getLogger("openclaw_gc")


def get_agent_sessions(agent_dir: Path) -> list[Path]:
    """Get all session files for an agent, sorted by mtime (newest first)."""
    sessions_dir = agent_dir / "sessions"
    if not sessions_dir.exists():
        return []
    files = list(sessions_dir.glob("*.jsonl"))
    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return files


def cleanup_agent(agent_name: str, agent_dir: Path, max_sessions: int, max_days: int, dry_run: bool) -> dict:
    """Clean up sessions for a single agent."""
    files = get_agent_sessions(agent_dir)
    if not files:
        return {"agent": agent_name, "total": 0, "deleted": 0, "kept": 0}

    now = time.time()
    max_age = max_days * 86400
    to_delete = []

    for i, f in enumerate(files):
        age = now - f.stat().st_mtime
        if i >= max_sessions or age > max_age:
            to_delete.append(f)

    # Also clean .deleted files
    deleted_files = list((agent_dir / "sessions").glob("*.deleted"))
    to_delete.extend(deleted_files)

    for f in to_delete:
        if not dry_run:
            f.unlink(missing_ok=True)

    return {
        "agent": agent_name,
        "total": len(files),
        "deleted": len(to_delete),
        "kept": len(files) - len([d for d in to_delete if d.suffix == ".jsonl"]),
    }


def run_gc(max_sessions: int = 2, max_days: int = 3, dry_run: bool = False) -> dict:
    """Run garbage collection across all agents."""
    if not AGENTS_DIR.exists():
        log.warning("Agents directory not found: %s", AGENTS_DIR)
        return {"error": "agents_dir_not_found"}

    results = []
    total_deleted = 0
    total_kept = 0

    for agent_dir in sorted(AGENTS_DIR.iterdir()):
        if not agent_dir.is_dir():
            continue
        result = cleanup_agent(agent_dir.name, agent_dir, max_sessions, max_days, dry_run)
        if result["deleted"] > 0:
            log.info(
                "%s%s: %d/%d sessions deleted (kept %d)",
                "[DRY-RUN] " if dry_run else "",
                result["agent"],
                result["deleted"],
                result["total"],
                result["kept"],
            )
            results.append(result)
        total_deleted += result["deleted"]
        total_kept += result["kept"]

    summary = {
        "agents_cleaned": len(results),
        "total_deleted": total_deleted,
        "total_kept": total_kept,
        "dry_run": dry_run,
        "timestamp": datetime.now().isoformat(),
    }
    log.info(
        "%sGC complete: %d files deleted, %d kept across %d agents",
        "[DRY-RUN] " if dry_run else "",
        total_deleted,
        total_kept,
        len(results),
    )
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OpenClaw Session Garbage Collector")
    parser.add_argument("--max-sessions", type=int, default=2, help="Max sessions to keep per agent")
    parser.add_argument("--max-days", type=int, default=3, help="Max age in days")
    parser.add_argument("--dry-run", action="store_true", help="Preview without deleting")
    args = parser.parse_args()
    run_gc(args.max_sessions, args.max_days, args.dry_run)
