"""JARVIS Adaptive Router — Real-time routing with circuit breakers and load balancing.

Learns from every dispatch in real-time (not just DB stats):
  - Circuit breaker per node (open after N failures, half-open after cooldown)
  - Weighted round-robin with dynamic weight adjustment
  - Latency-aware routing (exponential moving average)
  - Pattern-node affinity scores from dispatch_log

Usage:
    from src.adaptive_router import AdaptiveRouter
    router = AdaptiveRouter()
    node = router.pick_node("code", "Ecris un parser JSON")
    router.record(node, success=True, latency_ms=1200)
"""

from __future__ import annotations

import logging
import sqlite3
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


__all__ = [
    "AdaptiveRouter",
    "CircuitBreaker",
    "CircuitState",
    "NodeHealth",
    "PatternAffinity",
    "get_router",
]

logger = logging.getLogger("jarvis.adaptive_router")

DB_PATH = "F:/BUREAU/turbo/etoile.db"


class CircuitState(Enum):
    CLOSED = "closed"      # Normal — all requests go through
    OPEN = "open"          # Tripped — reject all requests
    HALF_OPEN = "half_open"  # Testing — allow 1 request to test recovery


@dataclass
class CircuitBreaker:
    """Per-node circuit breaker."""
    node: str
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_ts: float = 0
    last_success_ts: float = 0

    # Config
    failure_threshold: int = 5       # trips to OPEN after N consecutive failures
    success_threshold: int = 2       # closes after N successes in HALF_OPEN
    cooldown_s: float = 60.0         # time before OPEN -> HALF_OPEN

    def record_success(self):
        self.success_count += 1
        self.last_success_ts = time.time()
        self.failure_count = 0
        if self.state == CircuitState.HALF_OPEN:
            if self.success_count >= self.success_threshold:
                self.state = CircuitState.CLOSED
                logger.info(f"Circuit {self.node}: HALF_OPEN -> CLOSED (recovered)")

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_ts = time.time()
        self.success_count = 0
        if self.state == CircuitState.CLOSED and self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit {self.node}: CLOSED -> OPEN (tripped after {self.failure_count} failures)")
        elif self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit {self.node}: HALF_OPEN -> OPEN (test failed)")

    def allow_request(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            elapsed = time.time() - self.last_failure_ts
            if elapsed >= self.cooldown_s:
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                logger.info(f"Circuit {self.node}: OPEN -> HALF_OPEN (cooldown elapsed)")
                return True
            return False
        # HALF_OPEN: allow limited requests
        return True


@dataclass
class NodeHealth:
    """Real-time health metrics for a node."""
    node: str
    ema_latency_ms: float = 0.0    # Exponential moving average
    ema_alpha: float = 0.3         # Higher = more weight to recent
    total_calls: int = 0
    total_success: int = 0
    active_requests: int = 0       # Concurrent in-flight
    max_concurrent: int = 6        # Per-node limit
    base_weight: float = 1.0
    dynamic_weight: float = 1.0    # Adjusted by performance

    @property
    def success_rate(self) -> float:
        return self.total_success / max(1, self.total_calls)

    @property
    def effective_weight(self) -> float:
        """Weight adjusted by success rate and latency."""
        sr = self.success_rate
        # Penalize high latency (normalize to 0-1 range, lower is better)
        latency_factor = max(0.1, 1.0 - (self.ema_latency_ms / 60000))
        # Penalize near-capacity nodes
        capacity_factor = max(0.1, 1.0 - (self.active_requests / self.max_concurrent))
        return self.base_weight * sr * latency_factor * capacity_factor

    def update_latency(self, ms: float):
        if self.ema_latency_ms == 0:
            self.ema_latency_ms = ms
        else:
            self.ema_latency_ms = self.ema_alpha * ms + (1 - self.ema_alpha) * self.ema_latency_ms


@dataclass
class PatternAffinity:
    """How well a node handles a specific pattern type."""
    pattern: str
    node: str
    score: float = 0.0    # 0-1, higher is better
    calls: int = 0
    successes: int = 0
    avg_quality: float = 0.0
    avg_latency_ms: float = 0.0


class AdaptiveRouter:
    """Real-time adaptive routing with circuit breakers and load balancing."""

    NODE_LIMITS = {
        "M1": 6, "M2": 3, "M3": 2,
        "OL1": 3,
    }

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.circuits: dict[str, CircuitBreaker] = {}
        self.health: dict[str, NodeHealth] = {}
        self.affinity: dict[str, dict[str, PatternAffinity]] = defaultdict(dict)
        self._init_nodes()
        self._load_history()

    def _init_nodes(self):
        """Initialize circuit breakers and health for all known nodes."""
        from src.pattern_agents import NODES
        for name, cfg in NODES.items():
            self.circuits[name] = CircuitBreaker(node=name)
            self.health[name] = NodeHealth(
                node=name,
                base_weight=cfg.get("weight", 1.0),
                max_concurrent=self.NODE_LIMITS.get(name, 3),
            )

    def _load_history(self):
        """Seed health metrics from dispatch_log."""
        try:
            db = sqlite3.connect(self.db_path)
            db.row_factory = sqlite3.Row
            rows = db.execute("""
                SELECT node, classified_type as pattern, COUNT(*) as n,
                       SUM(success) as ok,
                       AVG(latency_ms) as avg_ms,
                       AVG(quality_score) as avg_q
                FROM agent_dispatch_log
                WHERE node IS NOT NULL
                GROUP BY node, classified_type
            """).fetchall()
            db.close()

            for r in rows:
                node, pattern = r["node"], r["pattern"]
                n, ok = r["n"], r["ok"] or 0
                avg_ms, avg_q = r["avg_ms"] or 0, r["avg_q"] or 0

                # Update health
                if node in self.health:
                    self.health[node].total_calls += n
                    self.health[node].total_success += ok
                    self.health[node].ema_latency_ms = avg_ms

                # Update affinity
                if pattern:
                    score = (ok / max(1, n)) * 0.5 + min(1, avg_q) * 0.3 + max(0, 1 - avg_ms / 30000) * 0.2
                    self.affinity[pattern][node] = PatternAffinity(
                        pattern=pattern, node=node,
                        score=score, calls=n, successes=ok,
                        avg_quality=avg_q, avg_latency_ms=avg_ms,
                    )
        except Exception as e:
            logger.warning(f"Failed to load history: {e}")

    def pick_node(self, pattern: str, prompt: str = "", preferred: str = "M1") -> str:
        """Pick the optimal node for a pattern, considering circuit state, load, and affinity."""
        candidates = []

        # Gather candidates from affinity + preferred + all healthy nodes
        for name, h in self.health.items():
            cb = self.circuits.get(name)
            if cb and not cb.allow_request():
                continue  # Circuit open
            if h.active_requests >= h.max_concurrent:
                continue  # At capacity

            # Compute score: affinity + effective_weight
            aff = self.affinity.get(pattern, {}).get(name)
            aff_score = aff.score if aff else 0.3  # Default for unknown
            eff_weight = h.effective_weight

            # Bonus for preferred node
            pref_bonus = 0.2 if name == preferred else 0

            total_score = aff_score * 0.5 + eff_weight * 0.3 + pref_bonus * 0.2
            candidates.append((name, total_score))

        if not candidates:
            # Everything down — fallback to preferred or M1
            logger.error("No available nodes! Falling back to preferred node.")
            return preferred

        # Sort by score descending
        candidates.sort(key=lambda x: -x[1])
        chosen = candidates[0][0]
        return chosen

    def pick_nodes(self, pattern: str, count: int = 3, preferred: str = "M1") -> list[str]:
        """Pick top N nodes for race/consensus strategies."""
        candidates = []
        for name, h in self.health.items():
            cb = self.circuits.get(name)
            if cb and not cb.allow_request():
                continue
            if h.active_requests >= h.max_concurrent:
                continue

            aff = self.affinity.get(pattern, {}).get(name)
            aff_score = aff.score if aff else 0.3
            eff_weight = h.effective_weight
            pref_bonus = 0.15 if name == preferred else 0
            total = aff_score * 0.5 + eff_weight * 0.3 + pref_bonus * 0.2
            candidates.append((name, total))

        candidates.sort(key=lambda x: -x[1])
        return [c[0] for c in candidates[:count]]

    def acquire(self, node: str):
        """Mark a request as in-flight."""
        if node in self.health:
            self.health[node].active_requests += 1

    def release(self, node: str):
        """Mark a request as complete."""
        if node in self.health:
            self.health[node].active_requests = max(0, self.health[node].active_requests - 1)

    def record(self, node: str, pattern: str = "", success: bool = True,
               latency_ms: float = 0, quality: float = 0.5):
        """Record a dispatch result — updates circuit, health, and affinity."""
        # Circuit breaker
        cb = self.circuits.get(node)
        if cb:
            if success:
                cb.record_success()
            else:
                cb.record_failure()

        # Health
        h = self.health.get(node)
        if h:
            h.total_calls += 1
            if success:
                h.total_success += 1
            h.update_latency(latency_ms)

        # Affinity
        if pattern:
            aff = self.affinity.get(pattern, {}).get(node)
            if not aff:
                aff = PatternAffinity(pattern=pattern, node=node)
                self.affinity[pattern][node] = aff
            aff.calls += 1
            if success:
                aff.successes += 1
            aff.avg_quality = (aff.avg_quality * (aff.calls - 1) + quality) / aff.calls
            aff.avg_latency_ms = (aff.avg_latency_ms * (aff.calls - 1) + latency_ms) / aff.calls
            sr = aff.successes / max(1, aff.calls)
            aff.score = sr * 0.5 + min(1, aff.avg_quality) * 0.3 + max(0, 1 - aff.avg_latency_ms / 30000) * 0.2

    def get_status(self) -> dict:
        """Full router status for dashboard."""
        nodes = {}
        for name, h in self.health.items():
            cb = self.circuits.get(name)
            nodes[name] = {
                "circuit": cb.state.value if cb else "unknown",
                "failure_count": cb.failure_count if cb else 0,
                "success_rate": round(h.success_rate * 100, 1),
                "ema_latency_ms": round(h.ema_latency_ms),
                "active_requests": h.active_requests,
                "max_concurrent": h.max_concurrent,
                "effective_weight": round(h.effective_weight, 3),
                "total_calls": h.total_calls,
            }

        affinities = {}
        for pattern, node_map in self.affinity.items():
            affinities[pattern] = {
                n: {"score": round(a.score, 3), "calls": a.calls, "success_rate": round(a.successes / max(1, a.calls) * 100, 1)}
                for n, a in sorted(node_map.items(), key=lambda x: -x[1].score)
            }

        return {
            "nodes": nodes,
            "affinities": affinities,
            "total_nodes": len(nodes),
            "healthy_nodes": sum(1 for n, cb in self.circuits.items() if cb.allow_request()),
            "open_circuits": [n for n, cb in self.circuits.items() if cb.state == CircuitState.OPEN],
        }

    def get_recommendations(self) -> list[dict]:
        """Auto-generated routing recommendations."""
        recs = []

        for name, cb in self.circuits.items():
            if cb.state == CircuitState.OPEN:
                recs.append({
                    "type": "circuit_open",
                    "node": name,
                    "severity": "high",
                    "message": f"{name} circuit OPEN ({cb.failure_count} failures). Traffic rerouted.",
                })

        for name, h in self.health.items():
            if h.total_calls > 10 and h.success_rate < 0.5:
                recs.append({
                    "type": "low_success",
                    "node": name,
                    "severity": "high",
                    "message": f"{name} success rate {h.success_rate:.0%} — consider disabling.",
                })
            if h.ema_latency_ms > 30000 and h.total_calls > 5:
                recs.append({
                    "type": "high_latency",
                    "node": name,
                    "severity": "medium",
                    "message": f"{name} avg latency {h.ema_latency_ms:.0f}ms — route to faster node.",
                })
            if h.active_requests >= h.max_concurrent:
                recs.append({
                    "type": "at_capacity",
                    "node": name,
                    "severity": "medium",
                    "message": f"{name} at max concurrent ({h.max_concurrent}). Queue growing.",
                })

        # Check for pattern with no good nodes
        for pattern, node_map in self.affinity.items():
            best = max(node_map.values(), key=lambda a: a.score) if node_map else None
            if best and best.score < 0.3 and best.calls > 5:
                recs.append({
                    "type": "weak_pattern",
                    "node": best.node,
                    "pattern": pattern,
                    "severity": "medium",
                    "message": f"Pattern '{pattern}' best node '{best.node}' score only {best.score:.2f}",
                })

        return recs


# Singleton
_router: Optional[AdaptiveRouter] = None

def get_router() -> AdaptiveRouter:
    global _router
    if _router is None:
        _router = AdaptiveRouter()
    return _router
