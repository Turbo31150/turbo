"""JARVIS Decision Engine — Autonomous decision making.

Receives signals from monitoring subsystems, evaluates rules,
and triggers appropriate actions. The brain that connects everything.
"""

from __future__ import annotations
import asyncio
import json
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Awaitable

logger = logging.getLogger("jarvis.decision_engine")
ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Signal:
    """An event/signal from a subsystem."""
    source: str  # e.g. "auto_scan", "vram_optimizer", "log_analyzer"
    severity: str  # "info", "warning", "critical"
    category: str  # "cluster", "gpu", "disk", "service", "performance"
    description: str
    data: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class Decision:
    """A decision made by the engine."""
    action: str  # e.g. "restart_service", "unload_model", "notify", "escalate"
    target: str
    reason: str
    priority: int = 5  # 1=highest, 10=lowest
    auto_execute: bool = True
    params: dict = field(default_factory=dict)


class DecisionEngine:
    def __init__(self):
        self._rules: list[tuple[str, Callable]] = []  # (name, rule_fn)
        self._action_handlers: dict[str, Callable] = {}
        self._decision_log: list[dict] = []
        self._signal_count = 0
        self._decision_count = 0
        self._db_path = ROOT / "data" / "decisions.db"
        self._init_db()
        self._register_default_rules()
        self._register_default_handlers()

    def _init_db(self):
        conn = sqlite3.connect(str(self._db_path))
        conn.execute("""CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT, signal_source TEXT, signal_severity TEXT,
            signal_desc TEXT, action TEXT, target TEXT,
            reason TEXT, result TEXT, auto_executed INTEGER
        )""")
        conn.commit()
        conn.close()

    def register_rule(self, name: str, rule_fn: Callable[[Signal], Decision | None]):
        """Register a decision rule. rule_fn receives a Signal and returns a Decision or None."""
        self._rules.append((name, rule_fn))

    def register_handler(self, action: str, handler: Callable):
        """Register an action handler."""
        self._action_handlers[action] = handler

    async def process_signal(self, signal: Signal) -> list[dict]:
        """Process a signal through all rules and execute decisions."""
        self._signal_count += 1
        results = []

        for rule_name, rule_fn in self._rules:
            try:
                decision = rule_fn(signal)
                if decision:
                    result = {"rule": rule_name, "decision": decision.action,
                              "target": decision.target, "reason": decision.reason}

                    if decision.auto_execute and decision.action in self._action_handlers:
                        try:
                            handler = self._action_handlers[decision.action]
                            if asyncio.iscoroutinefunction(handler):
                                exec_result = await handler(decision)
                            else:
                                exec_result = handler(decision)
                            result["executed"] = True
                            result["exec_result"] = str(exec_result)[:200]
                        except Exception as e:
                            result["executed"] = False
                            result["exec_error"] = str(e)
                    else:
                        result["executed"] = False
                        result["exec_result"] = "no handler or auto_execute=False"

                    self._decision_count += 1
                    results.append(result)
                    self._save_decision(signal, decision, result)
            except Exception as e:
                logger.warning("Rule %s failed: %s", rule_name, e)

        return results

    def _save_decision(self, signal: Signal, decision: Decision, result: dict):
        try:
            conn = sqlite3.connect(str(self._db_path))
            conn.execute(
                "INSERT INTO decisions (ts, signal_source, signal_severity, signal_desc, "
                "action, target, reason, result, auto_executed) VALUES (?,?,?,?,?,?,?,?,?)",
                (datetime.now().isoformat(), signal.source, signal.severity,
                 signal.description[:200], decision.action, decision.target,
                 decision.reason[:200], json.dumps(result, default=str)[:500],
                 1 if result.get("executed") else 0)
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    def _register_default_rules(self):
        """Register built-in decision rules."""

        def rule_critical_node_offline(signal: Signal) -> Decision | None:
            if signal.severity == "critical" and "OFFLINE" in signal.description:
                node = signal.description.split("(")[0].strip()
                return Decision(
                    action="heal_node", target=node,
                    reason=f"Node {node} offline — attempting self-heal",
                    priority=1
                )
            return None

        def rule_vram_critical(signal: Signal) -> Decision | None:
            if signal.category == "gpu" and signal.severity == "critical" and "VRAM" in signal.description:
                return Decision(
                    action="notify", target="gpu",
                    reason="VRAM critical — notify operator",
                    priority=2,
                    params={"message": signal.description}
                )
            return None

        def rule_high_error_rate(signal: Signal) -> Decision | None:
            if "error rate" in signal.description.lower() and signal.severity in ("warning", "critical"):
                return Decision(
                    action="analyze_logs", target="logs",
                    reason="High error rate detected — running log analysis",
                    priority=3
                )
            return None

        def rule_model_missing(signal: Signal) -> Decision | None:
            if "0 modeles charges" in signal.description:
                return Decision(
                    action="load_model", target="M1",
                    reason="No models loaded on M1 — loading qwen3-8b",
                    priority=1,
                    params={"model": "qwen3-8b"}
                )
            return None

        def rule_disk_low(signal: Signal) -> Decision | None:
            if signal.category == "disk" and signal.severity == "critical":
                return Decision(
                    action="notify", target="disk",
                    reason=f"Disk space critical: {signal.description}",
                    priority=2,
                    params={"message": signal.description}
                )
            return None

        def rule_temp_high(signal: Signal) -> Decision | None:
            if "OVERHEATING" in signal.description:
                return Decision(
                    action="throttle_gpu", target="gpu",
                    reason="GPU overheating — throttle workload",
                    priority=1
                )
            return None

        self.register_rule("critical_node_offline", rule_critical_node_offline)
        self.register_rule("vram_critical", rule_vram_critical)
        self.register_rule("high_error_rate", rule_high_error_rate)
        self.register_rule("model_missing", rule_model_missing)
        self.register_rule("disk_low", rule_disk_low)
        self.register_rule("temp_high", rule_temp_high)

    def _register_default_handlers(self):
        """Register default action handlers."""

        async def handle_notify(decision: Decision) -> str:
            import urllib.request
            try:
                data = json.dumps({
                    "title": f"JARVIS Decision: {decision.action}",
                    "message": decision.params.get("message", decision.reason)[:400]
                }).encode()
                req = urllib.request.Request(
                    "http://127.0.0.1:9742/api/notifications/push",
                    data=data, headers={"Content-Type": "application/json"}
                )
                urllib.request.urlopen(req, timeout=5)
                return "notified"
            except Exception:
                return "notify_failed"

        async def handle_heal_node(decision: Decision) -> str:
            try:
                from src.autonomous_loop import autonomous_loop
                result = await autonomous_loop._task_self_heal()
                healed = result.get("healed", [])
                return f"healed: {healed}" if healed else "no nodes healed"
            except Exception as e:
                return f"heal_error: {e}"

        async def handle_load_model(decision: Decision) -> str:
            import urllib.request
            model = decision.params.get("model", "qwen3-8b")
            try:
                data = json.dumps({
                    "model": model,
                    "messages": [{"role": "user", "content": "/nothink\nping"}],
                    "max_tokens": 1, "stream": False,
                }).encode()
                req = urllib.request.Request(
                    "http://127.0.0.1:1234/v1/chat/completions",
                    data=data, headers={"Content-Type": "application/json"}
                )
                urllib.request.urlopen(req, timeout=60)
                return f"{model} loaded"
            except Exception as e:
                return f"load_failed: {e}"

        async def handle_analyze_logs(decision: Decision) -> str:
            try:
                from src.log_analyzer import log_analyzer
                result = log_analyzer.analyze_recent()
                return f"errors={result.get('errors',0)} trend={result.get('trend','?')}"
            except Exception as e:
                return f"analysis_error: {e}"

        async def handle_throttle_gpu(decision: Decision) -> str:
            return "throttle_requested (manual action needed)"

        self.register_handler("notify", handle_notify)
        self.register_handler("heal_node", handle_heal_node)
        self.register_handler("load_model", handle_load_model)
        self.register_handler("analyze_logs", handle_analyze_logs)
        self.register_handler("throttle_gpu", handle_throttle_gpu)

    def get_stats(self) -> dict:
        """Get engine statistics."""
        try:
            conn = sqlite3.connect(str(self._db_path))
            total = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
            executed = conn.execute("SELECT COUNT(*) FROM decisions WHERE auto_executed=1").fetchone()[0]
            recent = conn.execute(
                "SELECT action, COUNT(*) FROM decisions GROUP BY action ORDER BY COUNT(*) DESC LIMIT 5"
            ).fetchall()
            conn.close()
        except Exception:
            total = executed = 0
            recent = []

        return {
            "signals_processed": self._signal_count,
            "decisions_made": self._decision_count,
            "total_decisions_db": total,
            "auto_executed": executed,
            "rules_count": len(self._rules),
            "handlers_count": len(self._action_handlers),
            "top_actions": [{"action": r[0], "count": r[1]} for r in recent],
        }

    def get_recent_decisions(self, limit: int = 20) -> list[dict]:
        """Get recent decisions from DB."""
        try:
            conn = sqlite3.connect(str(self._db_path))
            rows = conn.execute(
                "SELECT ts, signal_source, signal_severity, signal_desc, action, target, reason, auto_executed "
                "FROM decisions ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            conn.close()
            return [
                {"ts": r[0], "source": r[1], "severity": r[2], "description": r[3],
                 "action": r[4], "target": r[5], "reason": r[6], "executed": bool(r[7])}
                for r in rows
            ]
        except Exception:
            return []


# Singleton
decision_engine = DecisionEngine()
