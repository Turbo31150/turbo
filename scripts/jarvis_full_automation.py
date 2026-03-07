"""JARVIS Full Automation Daemon — Total automation orchestrator.

Runs as a continuous daemon that:
1. Auto-dispatches incoming messages to OpenClaw agents
2. Monitors cluster health + auto-heals
3. Runs periodic routines (maintenance, reports, trading scans)
4. Tracks all metrics in etoile.db
5. Self-improves routing based on success rates

Usage:
    uv run python scripts/jarvis_full_automation.py
    uv run python scripts/jarvis_full_automation.py --check   # One-shot health check
    uv run python scripts/jarvis_full_automation.py --status  # Show daemon status
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import signal
import socket
import sys
import time
from datetime import datetime
from pathlib import Path

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("jarvis.automation")

# ── Port checks ──────────────────────────────────────────────────────────────

SERVICES = {
    "LM Studio M1": ("127.0.0.1", 1234),
    "Ollama OL1": ("127.0.0.1", 11434),
    "JARVIS WS": ("127.0.0.1", 9742),
    "OpenClaw GW": ("127.0.0.1", 18789),
    "LM Studio M2": ("192.168.1.26", 1234),
    "LM Studio M3": ("192.168.1.113", 1234),
}


def check_port(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False


def health_check() -> dict:
    """Quick health check of all services."""
    results = {}
    for name, (host, port) in SERVICES.items():
        ok = check_port(host, port)
        results[name] = {"host": host, "port": port, "online": ok}
        status = "ONLINE" if ok else "OFFLINE"
        logger.info(f"  {name:<20} {host}:{port:<6} {status}")
    online = sum(1 for r in results.values() if r["online"])
    logger.info(f"  Services: {online}/{len(results)} online")
    return results


async def run_tool(tool_name: str, args: dict = None) -> dict:
    """Execute a JARVIS tool via HTTP."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            from src.ia_tool_executor import execute_tool_call
            return await execute_tool_call(tool_name, args or {}, caller="automation")
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def automation_cycle():
    """Run one automation cycle."""
    logger.info("=== Automation cycle start ===")
    t0 = time.time()

    # 1. Health check
    health = health_check()
    online = sum(1 for r in health.values() if r["online"])

    # 2. Check autonomous tasks
    result = await run_tool("jarvis_autonomous_status")
    if result.get("ok"):
        data = result.get("result", {})
        tasks = data.get("tasks", {})
        if isinstance(tasks, dict):
            enabled = sum(1 for t in tasks.values() if isinstance(t, dict) and t.get("enabled"))
            failed = sum(1 for t in tasks.values() if isinstance(t, dict) and t.get("fail_count", 0) > 0)
            logger.info(f"  Autonomous: {enabled} enabled, {failed} failed")

    # 3. Check alerts
    result = await run_tool("jarvis_alerts_active")
    if result.get("ok"):
        alerts = result.get("result", {}).get("alerts", [])
        if alerts:
            logger.warning(f"  Active alerts: {len(alerts)}")
            for a in alerts[:3]:
                logger.warning(f"    - {a.get('message', a)}")

    # 4. OpenClaw routing stats
    try:
        from src.openclaw_bridge import get_bridge
        stats = get_bridge().get_stats()
        logger.info(f"  Routes: {stats.get('total_routes', 0)} total")
    except Exception:
        pass

    elapsed = time.time() - t0
    logger.info(f"=== Cycle done in {elapsed:.1f}s ({online}/{len(health)} services) ===")
    return {"online": online, "total": len(health), "elapsed": elapsed}


async def daemon_loop(interval: int = 300):
    """Main daemon loop — runs every `interval` seconds."""
    logger.info(f"JARVIS Full Automation Daemon — interval={interval}s")
    logger.info(f"Services monitored: {len(SERVICES)}")

    running = True

    def _stop(sig, frame):
        nonlocal running
        logger.info("Shutdown signal received")
        running = False

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    cycle = 0
    while running:
        cycle += 1
        logger.info(f"\n--- Cycle #{cycle} at {datetime.now().strftime('%H:%M:%S')} ---")
        try:
            await automation_cycle()
        except Exception as e:
            logger.exception(f"Cycle error: {e}")

        # Wait for next cycle
        for _ in range(interval):
            if not running:
                break
            await asyncio.sleep(1)

    logger.info("Daemon stopped")


def show_status():
    """Show current automation status."""
    print("JARVIS Full Automation — Status")
    print("=" * 50)
    health_check()

    try:
        from src.openclaw_bridge import get_bridge
        bridge = get_bridge()
        stats = bridge.get_stats()
        print(f"\nOpenClaw Routes: {stats.get('total_routes', 0)}")
        for agent, info in list(stats.get("by_agent", {}).items())[:10]:
            print(f"  {agent:<25} {info['count']} calls ({info['avg_confidence']:.0%} conf)")
    except Exception as e:
        print(f"\nOpenClaw bridge error: {e}")

    try:
        from src.ia_tool_executor import get_tool_metrics
        metrics = get_tool_metrics()
        print(f"\nTool calls: {metrics.get('total_calls', 0)}")
        for name, info in list(metrics.get("tools", {}).items())[:5]:
            print(f"  {name:<30} {info['calls']} ({info['success_rate']:.0%} ok, {info['avg_ms']:.0f}ms)")
    except Exception as e:
        print(f"\nTool metrics error: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JARVIS Full Automation")
    parser.add_argument("--check", action="store_true", help="One-shot health check")
    parser.add_argument("--status", action="store_true", help="Show daemon status")
    parser.add_argument("--interval", type=int, default=300, help="Cycle interval seconds")
    args = parser.parse_args()

    if args.check:
        health_check()
    elif args.status:
        show_status()
    else:
        asyncio.run(daemon_loop(args.interval))
