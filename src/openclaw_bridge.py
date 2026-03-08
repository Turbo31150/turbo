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
    # Code & Development — all code/bug/dev → @coding agent
    "code_dev": "coding",
    "code": "coding",
    "debug": "coding",
    "refactor": "coding",
    "test": "coding",
    "devops": "devops-ci",
    "deploy": "devops-ci",

    # System & Infrastructure
    "system_control": "system-ops",
    "system": "system-ops",
    "cluster_ops": "system-ops",
    "windows": "windows",

    # Trading — trading/crypto/MEXC → @trading agent
    "trading": "trading",
    "trading_scan": "trading-scanner",
    "crypto": "trading",

    # Analysis & Reasoning — deep reasoning/architecture → @deep-work agent
    "analysis": "data-analyst",
    "reasoning": "deep-work",
    "math": "deep-work",
    "architecture": "deep-work",
    "data": "data-analyst",

    # Communication & Content — quick questions → @fast-chat agent (OL1)
    "query": "fast-chat",
    "simple": "fast-chat",
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

    # Security & Audit — security/audit → @securite-audit agent
    "security": "securite-audit",
    "audit": "securite-audit",

    # Research — web search → @ol1-web agent
    "web": "ol1-web",
    "search": "ol1-web",
    "research": "recherche-synthese",

    # Consensus → @consensus-master agent
    "consensus": "consensus-master",
    "critical": "consensus-master",
}

# ── Keyword patterns for fast classification (no ML needed) ─────────────────
_FAST_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Code & Development (highest priority for code-related messages)
    (re.compile(r"(?:code|programme|fonction|classe|script|bug|fix|debug|refactor|parser|ecris?\s+(?:un|une|le|la)|implemente|genere)", re.I), "code_dev"),
    (re.compile(r"(?:explique\s+(?:le\s+)?(?:role|code|fonction|module)|fichiers?\s+modifi|combien\s+de\s+(?:tests?|modules?)|nombre\s+de\s+(?:modules?|fichiers?|lignes?))", re.I), "code_dev"),
    # Security/Audit — BEFORE cluster_ops so "audit securite du cluster" matches security
    (re.compile(r"(?:securite|audit|vulnerabilite|owasp|credentials|faille|pentest|permissions)", re.I), "security"),
    # Trading scanner — specific patterns BEFORE generic trading
    (re.compile(r"(?:scan\s+march|signaux?\s+forts?|top\s+crypto|rankings?\s+(?:trading|crypto)|trading\s+scan)", re.I), "trading_scan"),
    # Trading — generic crypto/trading keywords
    (re.compile(r"(?:trade|trading|btc|eth|sol|doge|pepe|xrp|ada|avax|link|crypto|mexc|signal(?:aux)?|positions?\s+ouverte|score\s+trading|momentum|futures|leverage)", re.I), "trading"),
    # Cluster/System ops
    (re.compile(r"(?:cluster|noeud|node|gpu|vram|sante|health|diagnostic|boot|modeles?\s+charg|temperature|cpu|ram|charge\s+(?:cpu|ram|systeme)|memoire\s+(?:ram|disponible)|combien\s+de\s+modeles)", re.I), "cluster_ops"),
    # Architecture/Deep reasoning
    (re.compile(r"(?:architecture|design pattern|systeme distribue|microservice|schema|raisonnement\s+profond)", re.I), "architecture"),
    # Pipeline
    (re.compile(r"(?:pipeline|domino|routine|workflow|maintenance)", re.I), "pipeline"),
    # Windows system
    (re.compile(r"(?:windows|powershell|registre|(?<!\w)service(?!s?\s+distribu)|processus|disque|defender)", re.I), "windows"),
    # Reasoning/Math
    (re.compile(r"(?:raisonnement|logique|mathematique|calcul|equation|preuve)", re.I), "reasoning"),
    # Data analysis
    (re.compile(r"(?:analyse|compare|rapport|statistique|tendance|donnees|sql|resume\s+(?:les|la|le|ce))", re.I), "analysis"),
    # Web search
    (re.compile(r"(?:cherche|recherche|web|internet|actualite|trouve|mises?\s+a\s+jour|meteo|temps\s+(?:qu.il\s+fait|fait.il)|news)", re.I), "web"),
    # Translation
    (re.compile(r"(?:traduis|traduction|translate|anglais|english)", re.I), "translation"),
    # DevOps
    (re.compile(r"(?:git|commit|push|deploy|ci|cd|docker|build)", re.I), "devops"),
    # Consensus
    (re.compile(r"(?:consensus|vote|arbitrage|decision critique)", re.I), "consensus"),
    # Creative
    (re.compile(r"(?:idee|brainstorm|creatif|invente|propose|imagine|blague|raconte)", re.I), "creative"),
    # Documentation
    (re.compile(r"(?:documente|readme|changelog|api doc|guide)", re.I), "doc"),
    # Voice
    (re.compile(r"(?:voix|vocal|whisper|tts|microphone|ecoute)", re.I), "voice_control"),
    # Simple greetings (lowest priority)
    (re.compile(r"(?:bonjour|salut|coucou|hey|bonsoir|comment\s+(?:ca\s+va|vas?\s+tu)|quelle\s+heure)", re.I), "simple"),
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

        # Very short greetings only → quick-dispatch
        if len(text_lower) < 6:
            return "simple", 0.9

        matches: list[tuple[str, float]] = []
        for pattern, intent in _FAST_PATTERNS:
            all_matches = pattern.findall(text_lower)
            if all_matches:
                # Score based on total match coverage + bonus for multiple hits
                total_chars = sum(len(m) if isinstance(m, str) else len(m[0]) for m in all_matches)
                coverage = total_chars / max(1, len(text_lower))
                multi_bonus = min(0.1, 0.05 * (len(all_matches) - 1))
                score = 0.7 + min(0.25, coverage) + multi_bonus
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

    async def execute(self, text: str) -> dict[str, Any]:
        """Full pipeline: classify → match command → execute → return result.

        This is the single entry point that connects everything:
        OpenClaw classification + command matching + real system execution.
        """
        t0 = time.monotonic()
        route = self.route(text)

        # Skip command execution for greetings/questions → go straight to model
        _skip_commands = route.intent in ("simple", "question", "creative")

        # Try command execution (2658 pipelines + 853 voice commands)
        if not _skip_commands:
            try:
                from src.commands import match_command
                from src.executor import execute_command
                cmd, params, conf = match_command(text)
                if cmd and conf >= 0.7:
                    result = await execute_command(cmd, params or {})
                    if not result.startswith("__"):  # Skip sentinels
                        return {
                            "source": "command",
                            "agent": route.agent,
                            "intent": route.intent,
                            "content": result,
                            "command": cmd.name,
                            "action_type": cmd.action_type,
                            "latency_ms": (time.monotonic() - t0) * 1000,
                        }
            except (ImportError, Exception) as e:
                logger.debug("Command execution failed: %s", e)

        # Fallback: dispatch to cluster model
        try:
            from src.dispatch_engine import DispatchEngine
            engine = DispatchEngine()
            pattern = route.intent if route.intent in (
                "code_dev", "code", "trading", "analysis", "reasoning",
            ) else "simple"
            dr = await engine.dispatch(pattern, text)
            return {
                "source": "model",
                "agent": route.agent,
                "intent": route.intent,
                "content": dr.content,
                "model": dr.node,
                "latency_ms": (time.monotonic() - t0) * 1000,
            }
        except (ImportError, Exception) as e:
            return {
                "source": "error",
                "agent": route.agent,
                "intent": route.intent,
                "content": f"Execution failed: {e}",
                "latency_ms": (time.monotonic() - t0) * 1000,
            }

    async def execute_via_openclaw(
        self,
        text: str,
        channel: str = "last",
        deliver: bool = False,
        timeout_s: int = 120,
    ) -> dict[str, Any]:
        """Route and delegate to a specialized OpenClaw agent via the gateway CLI.

        This uses `openclaw agent --agent <id> --message "..."` to delegate
        to the correct specialized agent, matching the BOOT.md routing matrix.

        Args:
            text: The message to route and delegate
            channel: Delivery channel (default "last" = same as incoming)
            deliver: If True, deliver the agent's reply to the channel
            timeout_s: Timeout in seconds for the agent command

        Returns:
            Dict with agent, intent, content, and metadata
        """
        import asyncio
        import shlex

        t0 = time.monotonic()
        route = self.route(text)

        # Agents that should be handled locally (not delegated)
        _local_intents = {"cluster_ops", "windows", "system_control", "system"}
        if route.intent in _local_intents:
            return await self.execute(text)

        # Build openclaw agent command
        cmd_parts = [
            "openclaw", "agent",
            "--agent", route.agent,
            "--message", text,
        ]
        if deliver:
            cmd_parts.extend(["--deliver", "--channel", channel])
        cmd_parts.append("--json")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd_parts,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout_s
            )

            latency_ms = (time.monotonic() - t0) * 1000

            if proc.returncode == 0 and stdout:
                import json as _json
                try:
                    result_data = _json.loads(stdout.decode("utf-8", errors="replace"))
                    content = result_data.get("output", result_data.get("content", stdout.decode()))
                except (_json.JSONDecodeError, ValueError):
                    content = stdout.decode("utf-8", errors="replace").strip()

                return {
                    "source": "openclaw_agent",
                    "agent": route.agent,
                    "intent": route.intent,
                    "confidence": route.confidence,
                    "content": content,
                    "delivered": deliver,
                    "channel": channel,
                    "latency_ms": latency_ms,
                }
            else:
                # Fallback to local execution
                logger.warning(
                    "OpenClaw agent %s failed (rc=%s): %s",
                    route.agent, proc.returncode,
                    stderr.decode("utf-8", errors="replace")[:200] if stderr else "no stderr",
                )
                return await self.execute(text)

        except asyncio.TimeoutError:
            logger.warning("OpenClaw agent %s timed out after %ds", route.agent, timeout_s)
            return await self.execute(text)
        except (OSError, FileNotFoundError) as e:
            logger.warning("OpenClaw CLI not available: %s", e)
            return await self.execute(text)

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
