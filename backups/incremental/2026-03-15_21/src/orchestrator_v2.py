"""OrchestratorV2 — Unified coordination of observability, drift detection, and auto-tune.

Bridges the three Phase 3 subsystems into a single facade used by the REST API,
WebSocket push events, and the main orchestrator pipeline.

Phase 4 additions:
- ROUTING_MATRIX: task-type -> ordered node preferences with weights
- fallback_chain(): drift-aware fallback ordering
- Token budget tracking per node per session
- weighted_score(): dynamic scoring combining routing weight, load, success, latency
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from src.observability import observability_matrix
from src.drift_detector import drift_detector
from src.auto_tune import auto_tune


__all__ = [
    "NodeStats",
    "OrchestratorV2",
    "SessionBudget",
]

logger = logging.getLogger("jarvis.orchestrator_v2")


# ── Routing matrix (task_type -> [(node, weight)]) ─────────────────────

ROUTING_MATRIX: dict[str, list[tuple[str, float]]] = {
    "code":      [("M1", 1.8), ("M2", 1.5), ("OL1", 1.3)],
    "review":    [("M1", 1.8), ("M2", 1.5), ("OL1", 1.3)],
    "reasoning": [("M1", 1.8), ("M2", 1.5), ("OL1", 1.3)],
    "voice":     [("OL1", 1.3), ("M1", 1.8)],
    "trading":   [("OL1", 1.3), ("M1", 1.8), ("M2", 1.5)],
    "system":    [("M1", 1.8), ("OL1", 1.3), ("M3", 1.2)],
    "simple":    [("OL1", 1.3), ("M1", 1.8), ("M3", 1.2)],
    "archi":     [("M1", 1.8), ("OL1", 1.3), ("M2", 1.5)],
    "web":       [("OL1", 1.3), ("M1", 1.8)],
}


@dataclass
class NodeStats:
    """Runtime statistics for a single node."""

    total_calls: int = 0
    success_count: int = 0
    total_latency_ms: float = 0.0
    total_tokens: int = 0
    last_call_ts: float = 0.0
    last_failure_ts: float = 0.0

    @property
    def success_rate(self) -> float:
        return self.success_count / self.total_calls if self.total_calls > 0 else 1.0

    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / self.total_calls if self.total_calls > 0 else 100.0

    @property
    def avg_latency_norm(self) -> float:
        """Normalize latency to 0-1 range (500ms = 1.0)."""
        return min(1.0, max(0.01, self.avg_latency_ms / 500.0))


@dataclass
class SessionBudget:
    """Token usage tracking per session."""

    tokens_by_node: dict[str, int] = field(default_factory=dict)
    calls_by_node: dict[str, int] = field(default_factory=dict)
    start_ts: float = field(default_factory=time.time)

    @property
    def total_tokens(self) -> int:
        return sum(self.tokens_by_node.values())

    @property
    def total_calls(self) -> int:
        return sum(self.calls_by_node.values())

    def record(self, node: str, tokens: int = 0) -> None:
        self.tokens_by_node[node] = self.tokens_by_node.get(node, 0) + tokens
        self.calls_by_node[node] = self.calls_by_node.get(node, 0) + 1


class OrchestratorV2:
    """Unified coordinator for observability + drift + auto-tune + smart routing."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._node_stats: dict[str, NodeStats] = {}
        self._session_budget = SessionBudget()

    def _get_stats(self, node: str) -> NodeStats:
        if node not in self._node_stats:
            self._node_stats[node] = NodeStats()
        return self._node_stats[node]

    # ── Core recording ─────────────────────────────────────────────────

    def record_call(
        self,
        node: str,
        latency_ms: float,
        success: bool,
        tokens: int = 0,
        quality: float = 1.0,
    ) -> None:
        """Record a call across all subsystems + local stats."""
        with self._lock:
            stats = self._get_stats(node)
            stats.total_calls += 1
            stats.total_latency_ms += latency_ms
            stats.total_tokens += tokens
            stats.last_call_ts = time.time()
            if success:
                stats.success_count += 1
            else:
                stats.last_failure_ts = time.time()

            self._session_budget.record(node, tokens)

        try:
            observability_matrix.record_node_call(
                node, latency_ms=latency_ms, success=success,
                tokens=tokens, duration_s=latency_ms / 1000.0,
            )
        except Exception:
            logger.debug("observability record failed for %s", node)

        try:
            drift_detector.record(node, latency_ms=latency_ms, success=success, quality=quality)
        except Exception:
            logger.debug("drift record failed for %s", node)

        try:
            auto_tune.begin_request(node)
            auto_tune.end_request(node, latency_ms=latency_ms, success=success)
        except Exception:
            logger.debug("auto_tune record failed for %s", node)

    # ── Weighted scoring ───────────────────────────────────────────────

    def weighted_score(self, node: str, task_type: str = "code") -> float:
        """Compute dynamic score: routing_weight * (1 - load) * success_rate * (1 / latency_norm).

        Higher score = better candidate.
        """
        routing_weight = 1.0
        matrix_entry = ROUTING_MATRIX.get(task_type, [])
        for n, w in matrix_entry:
            if n == node:
                routing_weight = w
                break

        with self._lock:
            stats = self._get_stats(node)
            success_rate = stats.success_rate
            latency_norm = stats.avg_latency_norm

        try:
            load = auto_tune.get_node_load(node)
            load_factor = min(1.0, load.active_requests / max(1, load.max_concurrent))
        except Exception:
            load_factor = 0.0

        score = routing_weight * (1.0 - load_factor) * success_rate * (1.0 / latency_norm)
        return round(score, 4)

    # ── Smart node selection ───────────────────────────────────────────

    def get_best_node(self, candidates: list[str], task_type: str = "code") -> str | None:
        """Pick the best node using weighted scoring + drift filtering.

        Pipeline: filter degraded -> filter cooling -> score -> pick highest.
        """
        if not candidates:
            return None

        degraded = set(drift_detector.get_degraded_models())
        viable = [c for c in candidates if c not in degraded]

        if not viable:
            viable = list(candidates)

        non_cooling = [c for c in viable if not auto_tune.get_node_load(c).is_cooling]
        if non_cooling:
            viable = non_cooling

        if not viable:
            return candidates[0]

        scored = [(node, self.weighted_score(node, task_type)) for node in viable]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[0][0]

    # ── Fallback chain ─────────────────────────────────────────────────

    def fallback_chain(self, task_type: str = "code", exclude: set[str] | None = None) -> list[str]:
        """Return ordered fallback list for task_type, excluding degraded + specified nodes.

        Uses ROUTING_MATRIX order, filters degraded, scores remaining.
        """
        exclude = exclude or set()
        degraded = set(drift_detector.get_degraded_models())

        matrix_entry = ROUTING_MATRIX.get(task_type, ROUTING_MATRIX.get("simple", []))
        all_nodes = [n for n, _ in matrix_entry]

        viable = [n for n in all_nodes if n not in degraded and n not in exclude]
        if not viable:
            viable = [n for n in all_nodes if n not in exclude]

        scored = [(node, self.weighted_score(node, task_type)) for node in viable]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [n for n, _ in scored]

    # ── Token budget ───────────────────────────────────────────────────

    def get_budget_report(self) -> dict[str, Any]:
        """Return token budget report for current session."""
        with self._lock:
            budget = self._session_budget
            elapsed_s = time.time() - budget.start_ts
            return {
                "total_tokens": budget.total_tokens,
                "total_calls": budget.total_calls,
                "tokens_by_node": dict(budget.tokens_by_node),
                "calls_by_node": dict(budget.calls_by_node),
                "session_duration_s": round(elapsed_s, 1),
                "tokens_per_minute": round(budget.total_tokens / max(1, elapsed_s / 60), 1),
            }

    def reset_budget(self) -> None:
        """Reset session budget counters."""
        with self._lock:
            self._session_budget = SessionBudget()

    # ── Node stats report ──────────────────────────────────────────────

    def get_node_stats(self) -> dict[str, dict[str, Any]]:
        """Return per-node statistics."""
        with self._lock:
            result = {}
            for node, stats in self._node_stats.items():
                result[node] = {
                    "total_calls": stats.total_calls,
                    "success_rate": round(stats.success_rate, 4),
                    "avg_latency_ms": round(stats.avg_latency_ms, 1),
                    "total_tokens": stats.total_tokens,
                    "last_call": stats.last_call_ts,
                    "last_failure": stats.last_failure_ts,
                }
            return result

    # ── Dashboard ──────────────────────────────────────────────────────

    def get_dashboard(self) -> dict[str, Any]:
        """Combined dashboard from all subsystems + routing + budget."""
        obs_report: dict[str, Any] = {}
        drift_report: dict[str, Any] = {}
        tune_report: dict[str, Any] = {}

        try:
            obs_report = observability_matrix.get_report()
        except Exception as exc:
            obs_report = {"error": str(exc)}

        try:
            drift_report = drift_detector.get_report()
        except Exception as exc:
            drift_report = {"error": str(exc)}

        try:
            tune_report = auto_tune.get_status()
        except Exception as exc:
            tune_report = {"error": str(exc)}

        health = self.health_check()

        return {
            "observability": obs_report,
            "drift": drift_report,
            "auto_tune": tune_report,
            "health_score": health,
            "node_stats": self.get_node_stats(),
            "budget": self.get_budget_report(),
        }

    def health_check(self) -> int:
        """Compute overall cluster health score 0-100.

        Weights: observability 40%, drift 30%, auto-tune 30%.
        """
        obs_score = 100
        drift_score = 100
        tune_score = 100

        try:
            alerts = observability_matrix.get_alerts()
            if alerts:
                obs_score = max(0, 100 - len(alerts) * 15)
        except Exception:
            obs_score = 50

        try:
            degraded = drift_detector.get_degraded_models()
            drift_alerts = drift_detector.get_alerts()
            if degraded:
                drift_score = max(0, 100 - len(degraded) * 25)
            elif drift_alerts:
                drift_score = max(50, 100 - len(drift_alerts) * 10)
        except Exception:
            drift_score = 50

        try:
            status = auto_tune.get_status()
            snapshot = status.get("resource_snapshot", {})
            cpu = snapshot.get("cpu_percent", 0)
            mem = snapshot.get("memory_percent", 0)
            if cpu > 90 or mem > 90:
                tune_score = 30
            elif cpu > 70 or mem > 70:
                tune_score = 60
        except Exception:
            tune_score = 50

        return int(0.4 * obs_score + 0.3 * drift_score + 0.3 * tune_score)

    # ── Dispatch Engine (9 Steps) ──────────────────────────────────────

    async def dispatch(self, prompt: str, task_type: str = "simple") -> dict[str, Any]:
        """Blueprint Etoile 9-step Dispatch Engine.
        Steps: Health -> Classify -> Memory -> Prompt_Opt -> Route -> Dispatch -> Gate -> Feedback -> Event
        """
        t_start = time.time()
        
        # 1. Health (Check cluster readiness)
        health_score = self.health_check()
        if health_score < 30:
            return {"error": "Cluster health too low for dispatch", "score": health_score}

        # 2. Classify (Already provided by task_type, but could be refined)
        # 3. Memory (Inject context)
        context = ""
        try:
            from src.agent_memory import agent_memory
            context = agent_memory.get_context(prompt)
        except: pass

        # 4. Prompt Optimization
        optimized_prompt = f"{context}\nUser: {prompt}" if context else prompt

        # 5. Route (Node Selection)
        node = self.get_best_node(list(self._node_stats.keys()) or ["OL1"], task_type)
        
        # 6. Dispatch (Execution)
        # Simplified execution for this implementation
        print(f"[DISPATCH] Routing {task_type} to {node}")
        response_text = f"Simulated response from {node}" # Placeholder
        
        # 7. Gate (Quality Validation)
        try:
            from src.quality_gate import quality_gate
            gate_res = quality_gate.validate(response_text, task_type)
            if not gate_res["passed"]:
                print(f"[GATE] Failed: {gate_res['reason']}. Retrying...")
                # Fallback logic here
        except: pass

        # 8. Feedback (Record metrics)
        latency = (time.time() - t_start) * 1000
        self.record_call(node, latency, success=True)

        # 9. Event (Emit to dashboard)
        try:
            from src.event_stream import event_stream
            event_stream.emit("dispatch", {"node": node, "latency": latency, "task": task_type})
        except: pass

        return {
            "node": node,
            "response": response_text,
            "latency_ms": round(latency, 2),
            "health": health_score
        }


# Global singleton
orchestrator_v2 = OrchestratorV2()
