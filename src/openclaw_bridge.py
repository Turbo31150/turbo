"""JARVIS OpenClaw Bridge — Routes messages to the optimal OpenClaw agent.

Connects the existing dispatch infrastructure (intent_classifier, adaptive_router,
dispatch_engine) to OpenClaw's 40 agents. Auto-classifies incoming messages and
dispatches to the right specialized agent.

BEFORE (manual routing):
  - All messages go to 'main' agent
  - No specialization, no parallel processing
  - OpenClaw agents idle

AFTER (auto-routing):
  - Messages classified by intent
  - Dispatched to optimal agent (code→code-champion, trading→trading, etc.)
  - Fallback chain: specialized agent → main → OL1
  - Metrics tracked in etoile.db

Usage:
    from src.openclaw_bridge import get_bridge
    bridge = get_bridge()
    result = await bridge.route("analyse le code de dispatch_engine.py")
"""
from __future__ import annotations

import logging
import re
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


__all__ = [
    "OpenClawBridge",
    "RouteResult",
    "get_bridge",
]

logger = logging.getLogger("jarvis.openclaw_bridge")

_ETOILE_DB = Path(__file__).resolve().parent.parent / "data" / "etoile.db"

# ── Intent → OpenClaw Agent mapping ─────────────────────────────────────────
# Maps classified intents to the best OpenClaw agent for that task.

INTENT_TO_AGENT: dict[str, str] = {
    # Code & Development
    "code_dev": "code-champion",
    "code": "code-champion",
    "debug": "debug-detective",
    "refactor": "deep-work",
    "test": "code-champion",
    "devops": "devops-ci",
    "deploy": "devops-ci",

    # System & Infrastructure
    "system_control": "system-ops",
    "system": "system-ops",
    "cluster_ops": "system-ops",
    "windows": "windows",

    # Trading
    "trading": "trading",
    "trading_scan": "trading-scanner",
    "crypto": "trading-scanner",

    # Analysis & Reasoning
    "analysis": "analysis-engine",
    "reasoning": "deep-reasoning",
    "math": "deep-reasoning",
    "architecture": "gemini-pro",
    "data": "data-analyst",

    # Communication & Content
    "query": "fast-chat",
    "simple": "quick-dispatch",
    "question": "fast-chat",
    "creative": "creative-brainstorm",
    "translation": "translator",
    "doc": "doc-writer",

    # Voice & Pipeline
    "voice_control": "voice-assistant",
    "pipeline": "pipeline-monitor",
    "navigation": "fast-chat",
    "app_launch": "windows",
    "file_ops": "windows",

    # Security & Audit
    "security": "securite-audit",
    "audit": "securite-audit",

    # Research
    "web": "ol1-web",
    "search": "recherche-synthese",
    "research": "recherche-synthese",

    # Consensus (multi-agent)
    "consensus": "consensus-master",
    "critical": "consensus-master",
}

# ── Keyword patterns for fast classification (no ML needed) ─────────────────
_FAST_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(?:code|programme|fonction|classe|module|script|bug|fix|debug|refactor|test|parser|ecris?\s+(?:un|une|le|la)|implemente|genere)", re.I), "code_dev"),
    (re.compile(r"(?:trade|trading|btc|eth|sol|crypto|mexc|signal|scan)", re.I), "trading"),
    (re.compile(r"(?:cluster|noeud|node|gpu|vram|sante|health|diagnostic|boot)", re.I), "cluster_ops"),
    (re.compile(r"(?:pipeline|domino|routine|workflow|maintenance)", re.I), "pipeline"),
    (re.compile(r"(?:securite|audit|vulnerabilite|owasp|credentials|token)", re.I), "security"),
    (re.compile(r"(?:architecture|design pattern|systeme distribue|microservice|schema)", re.I), "architecture"),
    (re.compile(r"(?:windows|powershell|registre|(?<!\w)service(?!s?\s+distribu)|processus|disque|defender)", re.I), "windows"),
    (re.compile(r"(?:raisonnement|logique|mathematique|calcul|equation|preuve)", re.I), "reasoning"),
    (re.compile(r"(?:analyse|compare|rapport|statistique|tendance|donnees|sql)", re.I), "analysis"),
    (re.compile(r"(?:cherche|recherche|web|internet|actualite|trouve)", re.I), "web"),
    (re.compile(r"(?:traduis|traduction|translate|anglais|english)", re.I), "translation"),
    (re.compile(r"(?:git|commit|push|deploy|ci|cd|docker|build)", re.I), "devops"),
    (re.compile(r"(?:consensus|vote|arbitrage|decision critique)", re.I), "consensus"),
    (re.compile(r"(?:idee|brainstorm|creatif|invente|propose|imagine)", re.I), "creative"),
    (re.compile(r"(?:documente|readme|changelog|api doc|guide)", re.I), "doc"),
    (re.compile(r"(?:voix|vocal|whisper|tts|microphone|ecoute)", re.I), "voice_control"),
]


@dataclass
class RouteResult:
    """Result of routing a message to an OpenClaw agent."""
    agent: str
    intent: str
    confidence: float
    fallback_used: bool = False
    latency_ms: float = 0.0
    source: str = "fast"  # "fast" (regex), "classifier" (ML-like), "fallback"


class OpenClawBridge:
    """Routes messages to the optimal OpenClaw agent based on content analysis."""

    def __init__(self):
        self._stats: dict[str, dict[str, Any]] = {}
        self._db_initialized = False
        self._db_lock = threading.Lock()

    def classify_fast(self, text: str) -> tuple[str, float]:
        """Fast regex-based classification. Returns (intent, confidence)."""
        text_lower = text.lower().strip()

        # Very short messages → quick-dispatch
        if len(text_lower) < 10:
            return "simple", 0.9

        matches: list[tuple[str, float]] = []
        for pattern, intent in _FAST_PATTERNS:
            m = pattern.search(text_lower)
            if m:
                # Score based on match coverage
                coverage = len(m.group()) / max(1, len(text_lower))
                score = 0.7 + min(0.25, coverage)
                matches.append((intent, score))

        if not matches:
            return "question", 0.5  # Default: general question

        # Return highest scoring match
        matches.sort(key=lambda x: -x[1])
        return matches[0]

    def classify_deep(self, text: str) -> tuple[str, float]:
        """Deep classification using intent_classifier module."""
        try:
            from src.intent_classifier import IntentClassifier
            clf = IntentClassifier()
            results = clf.classify(text, top_n=1)
            if results:
                return results[0].intent, results[0].confidence
        except Exception as e:
            logger.debug("Deep classifier unavailable: %s", e)
        return self.classify_fast(text)

    def route(self, text: str, use_deep: bool = False) -> RouteResult:
        """Route a message to the best OpenClaw agent.

        Args:
            text: The message to route
            use_deep: If True, use deep classification (slower but more accurate)

        Returns:
            RouteResult with agent name, intent, and confidence
        """
        t0 = time.monotonic()

        if use_deep:
            intent, confidence = self.classify_deep(text)
            source = "classifier"
        else:
            intent, confidence = self.classify_fast(text)
            source = "fast"

        # Map intent to agent
        agent = INTENT_TO_AGENT.get(intent)
        fallback_used = False

        if not agent:
            agent = "main"
            fallback_used = True
            source = "fallback"

        latency_ms = (time.monotonic() - t0) * 1000

        result = RouteResult(
            agent=agent,
            intent=intent,
            confidence=confidence,
            fallback_used=fallback_used,
            latency_ms=latency_ms,
            source=source,
        )

        # Record metric
        self._record(result)

        return result

    def route_batch(self, messages: list[str]) -> list[RouteResult]:
        """Route multiple messages in batch."""
        return [self.route(msg) for msg in messages]

    def get_agent_for_intent(self, intent: str) -> str:
        """Direct intent-to-agent lookup."""
        return INTENT_TO_AGENT.get(intent, "main")

    def get_routing_table(self) -> dict[str, str]:
        """Return the full intent→agent mapping."""
        return dict(INTENT_TO_AGENT)

    def get_stats(self) -> dict[str, Any]:
        """Return routing statistics."""
        return {
            "total_routes": sum(s.get("count", 0) for s in self._stats.values()),
            "by_agent": {
                agent: {
                    "count": s.get("count", 0),
                    "avg_confidence": round(s.get("total_conf", 0) / max(1, s.get("count", 1)), 2),
                    "fallback_count": s.get("fallback", 0),
                }
                for agent, s in sorted(self._stats.items(), key=lambda x: -x[1].get("count", 0))
            },
        }

    def _record(self, result: RouteResult):
        """Record routing metric in memory + SQLite."""
        if result.agent not in self._stats:
            self._stats[result.agent] = {"count": 0, "total_conf": 0.0, "fallback": 0}
        s = self._stats[result.agent]
        s["count"] += 1
        s["total_conf"] += result.confidence
        if result.fallback_used:
            s["fallback"] += 1

        # Persist to SQLite (non-blocking)
        self._persist(result)

    def _ensure_db(self):
        if self._db_initialized:
            return
        with self._db_lock:
            if self._db_initialized:
                return
            try:
                with sqlite3.connect(str(_ETOILE_DB), timeout=5) as conn:
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS openclaw_routing (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            ts REAL NOT NULL,
                            agent TEXT NOT NULL,
                            intent TEXT NOT NULL,
                            confidence REAL NOT NULL,
                            fallback INTEGER NOT NULL DEFAULT 0,
                            latency_ms REAL NOT NULL DEFAULT 0,
                            source TEXT NOT NULL DEFAULT 'fast'
                        )
                    """)
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_ocr_ts ON openclaw_routing(ts)")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_ocr_agent ON openclaw_routing(agent)")
                    conn.commit()
                self._db_initialized = True
            except (sqlite3.Error, OSError) as e:
                logger.warning("openclaw_routing DB init failed: %s", e)

    def _persist(self, result: RouteResult):
        """Write routing metric to SQLite in background thread."""
        def _write():
            try:
                self._ensure_db()
                with sqlite3.connect(str(_ETOILE_DB), timeout=5) as conn:
                    conn.execute(
                        "INSERT INTO openclaw_routing (ts, agent, intent, confidence, fallback, latency_ms, source) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (time.time(), result.agent, result.intent, result.confidence,
                         int(result.fallback_used), result.latency_ms, result.source),
                    )
                    conn.commit()
            except (sqlite3.Error, OSError) as e:
                logger.debug("openclaw_routing write failed: %s", e)
        threading.Thread(target=_write, daemon=True).start()

    def get_routing_history(self, hours: int = 24, limit: int = 200) -> list[dict]:
        """Read recent routing decisions from SQLite."""
        try:
            self._ensure_db()
            since = time.time() - hours * 3600
            with sqlite3.connect(str(_ETOILE_DB), timeout=5) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT * FROM openclaw_routing WHERE ts >= ? ORDER BY ts DESC LIMIT ?",
                    (since, limit),
                ).fetchall()
            return [dict(r) for r in rows]
        except (sqlite3.Error, OSError) as e:
            logger.warning("openclaw_routing read failed: %s", e)
            return []

    def get_routing_analytics(self) -> dict[str, Any]:
        """Analytics: agent usage, avg confidence, most/least used agents."""
        try:
            self._ensure_db()
            with sqlite3.connect(str(_ETOILE_DB), timeout=5) as conn:
                conn.row_factory = sqlite3.Row

                by_agent = conn.execute("""
                    SELECT agent, COUNT(*) as n, AVG(confidence) as avg_conf,
                           SUM(fallback) as fallbacks, AVG(latency_ms) as avg_ms
                    FROM openclaw_routing
                    GROUP BY agent ORDER BY n DESC
                """).fetchall()

                by_intent = conn.execute("""
                    SELECT intent, COUNT(*) as n, AVG(confidence) as avg_conf
                    FROM openclaw_routing
                    GROUP BY intent ORDER BY n DESC
                """).fetchall()

                total = conn.execute("SELECT COUNT(*) FROM openclaw_routing").fetchone()[0]

            return {
                "total_routes": total,
                "by_agent": [
                    {"agent": r["agent"], "count": r["n"],
                     "avg_confidence": round(r["avg_conf"], 2),
                     "fallback_rate": round((r["fallbacks"] or 0) / max(1, r["n"]), 2),
                     "avg_latency_ms": round(r["avg_ms"] or 0, 1)}
                    for r in by_agent
                ],
                "by_intent": [
                    {"intent": r["intent"], "count": r["n"],
                     "avg_confidence": round(r["avg_conf"], 2)}
                    for r in by_intent
                ],
            }
        except (sqlite3.Error, OSError) as e:
            return {"error": str(e)}


# Singleton
_bridge: Optional[OpenClawBridge] = None

def get_bridge() -> OpenClawBridge:
    global _bridge
    if _bridge is None:
        _bridge = OpenClawBridge()
    return _bridge
