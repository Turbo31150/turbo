"""JARVIS Auto-Scaler — Dynamic cluster adjustment based on load.

Monitors node health and dispatches, then:
  - Loads/unloads models on M1 based on demand
  - Adjusts concurrency limits per node
  - Shifts traffic away from degraded nodes
  - Activates cloud models when local nodes saturated

Usage:
    from src.auto_scaler import AutoScaler
    scaler = AutoScaler()
    actions = await scaler.scale()
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger("jarvis.auto_scaler")

DB_PATH = "F:/BUREAU/turbo/etoile.db"


@dataclass
class ScaleAction:
    action: str  # load_model, unload_model, shift_traffic, adjust_concurrency, activate_cloud
    target: str  # node or model name
    reason: str
    params: dict


class AutoScaler:
    """Dynamic cluster scaling based on load and health."""

    # Thresholds
    HIGH_LATENCY_MS = 30000  # 30s = overloaded
    LOW_SUCCESS_RATE = 0.7
    MIN_DISPATCHES = 10  # minimum data before acting

    # Node capacity
    NODE_MAX_CONCURRENT = {
        "M1": 6, "M2": 3, "M3": 2,
        "OL1": 3,
    }

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    async def scale(self) -> list[dict]:
        """Analyze cluster state and return scaling actions."""
        actions = []

        # Get current node stats
        stats = self._get_node_stats()

        for node, s in stats.items():
            # Check for overloaded nodes
            if s["total"] >= self.MIN_DISPATCHES:
                if s["avg_ms"] > self.HIGH_LATENCY_MS:
                    actions.append({
                        "action": "reduce_load",
                        "target": node,
                        "reason": f"High latency: {s['avg_ms']:.0f}ms (>{self.HIGH_LATENCY_MS}ms)",
                        "suggestion": f"Reduce concurrency or shift traffic to other nodes",
                    })

                if s["rate"] < self.LOW_SUCCESS_RATE:
                    actions.append({
                        "action": "shift_traffic",
                        "target": node,
                        "reason": f"Low success: {s['rate']:.0%} (<{self.LOW_SUCCESS_RATE:.0%})",
                        "suggestion": f"Route {node} patterns to M1 or OL1 instead",
                    })

        # Check if M1 is overloaded and needs help
        m1 = stats.get("M1", {})
        if m1.get("total", 0) > 50 and m1.get("avg_ms", 0) > 20000:
            # Check if OL1 has capacity
            ol1 = stats.get("OL1", {})
            if ol1.get("rate", 1) > 0.8:
                actions.append({
                    "action": "rebalance",
                    "target": "M1->OL1",
                    "reason": f"M1 overloaded ({m1['avg_ms']:.0f}ms avg), OL1 has capacity",
                    "suggestion": "Route simple/nano/micro patterns to OL1",
                })

        # Check M1 loaded models
        try:
            async with httpx.AsyncClient() as c:
                r = await c.get("http://127.0.0.1:1234/api/v1/models", timeout=3)
                models = r.json().get("data", r.json().get("models", []))
                loaded = [m for m in models if m.get("loaded_instances")]
                available = [m for m in models if not m.get("loaded_instances")]

                if len(loaded) == 0:
                    actions.append({
                        "action": "load_model",
                        "target": "M1:qwen3-8b",
                        "reason": "No model loaded on M1",
                        "suggestion": "Load qwen3-8b (champion model)",
                    })
                elif len(loaded) >= 3:
                    actions.append({
                        "action": "unload_excess",
                        "target": f"M1:{len(loaded)} models",
                        "reason": f"{len(loaded)} models loaded, VRAM may be constrained",
                        "suggestion": "Keep only the 2 most-used models",
                    })

                actions.append({
                    "action": "info",
                    "target": "M1",
                    "reason": f"{len(loaded)} models loaded, {len(available)} available",
                    "suggestion": f"Loaded: {[m.get('key','?') for m in loaded]}",
                })
        except Exception:
            actions.append({
                "action": "alert",
                "target": "M1",
                "reason": "Cannot reach M1 LM Studio API",
                "suggestion": "Check LM Studio is running on port 1234",
            })

        # Check OL1 status
        try:
            async with httpx.AsyncClient() as c:
                r = await c.get("http://127.0.0.1:11434/api/tags", timeout=3)
                models = r.json().get("models", [])
                actions.append({
                    "action": "info",
                    "target": "OL1",
                    "reason": f"{len(models)} models available",
                    "suggestion": "Ollama healthy",
                })
        except Exception:
            actions.append({
                "action": "alert",
                "target": "OL1",
                "reason": "Cannot reach Ollama",
                "suggestion": "Check Ollama is running on port 11434",
            })

        # Overall recommendation
        total_dispatches = sum(s.get("total", 0) for s in stats.values())
        total_ok = sum(s.get("ok", 0) for s in stats.values())
        overall_rate = total_ok / max(1, total_dispatches)

        if overall_rate < 0.8 and total_dispatches > 20:
            actions.append({
                "action": "cluster_alert",
                "target": "cluster",
                "reason": f"Overall success rate {overall_rate:.0%} is below 80%",
                "suggestion": "Focus traffic on M1+OL1, disable M2/M3 from active routing",
            })

        return actions

    def _get_node_stats(self) -> dict:
        """Get recent node performance from dispatch_log."""
        try:
            db = sqlite3.connect(self.db_path)
            db.row_factory = sqlite3.Row
            rows = db.execute("""
                SELECT node, COUNT(*) as total,
                       SUM(success) as ok,
                       AVG(latency_ms) as avg_ms,
                       AVG(success) as rate
                FROM agent_dispatch_log
                WHERE node IS NOT NULL
                GROUP BY node
            """).fetchall()
            db.close()
            return {r["node"]: dict(r) for r in rows}
        except Exception:
            return {}

    async def auto_heal(self) -> list[dict]:
        """Attempt to fix cluster issues automatically."""
        actions = await self.scale()
        healed = []

        for a in actions:
            if a["action"] == "load_model" and "qwen3-8b" in a["target"]:
                try:
                    async with httpx.AsyncClient() as c:
                        r = await c.post(
                            "http://127.0.0.1:1234/api/v1/models/load",
                            json={"model": "qwen3-8b"}, timeout=30,
                        )
                        if r.status_code == 200:
                            healed.append({"action": "loaded", "target": "qwen3-8b", "ok": True})
                except Exception as e:
                    healed.append({"action": "load_failed", "target": "qwen3-8b", "error": str(e)[:100]})

        return healed


# CLI
async def _main():
    scaler = AutoScaler()
    actions = await scaler.scale()
    print(f"\n=== AUTO-SCALER: {len(actions)} actions ===")
    for a in actions:
        icon = {"info": "i", "alert": "!", "load_model": "+", "reduce_load": "-",
                "shift_traffic": ">", "rebalance": "~", "cluster_alert": "!!"}.get(a["action"], "?")
        print(f"  [{icon}] {a['action']:20s} {a['target']:20s}")
        print(f"      {a['reason']}")
        print(f"      -> {a['suggestion']}")

if __name__ == "__main__":
    asyncio.run(_main())
