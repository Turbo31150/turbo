"""Dynamic Agents — Spawn agents from DB patterns at runtime.

Loads agent_patterns from etoile.db, maps models to cluster nodes,
generates system prompts by category, tracks stats.
"""

from __future__ import annotations

import logging
import sqlite3
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.dynamic_agents")

DB_PATH = str(Path(__file__).parent.parent / "data" / "etoile.db")

# ── Model → Node mapping ────────────────────────────────────────────────
MODEL_TO_NODE: dict[str, str] = {
    "qwen3-8b": "M1",
    "gpt-oss-20b": "M1B",
    "deepseek-r1-0528-qwen3-8b": "M2",
    "qwen3:1.7b": "OL1",
    "gpt-oss:120b-cloud": "OL1",
    "devstral-2:123b-cloud": "OL1",
}

# ── Hardcoded pattern types (skip from DB) ───────────────────────────────
_HARDCODED_PATTERNS = {
    "code", "trading", "system", "general", "voice", "web",
    "cluster", "security", "health", "benchmark",
}

# ── Category → system prompt templates ───────────────────────────────────
CATEGORY_PROMPTS: dict[str, str] = {
    "win_monitor": "Tu es un expert Windows monitoring pour JARVIS.",
    "win_service": "Tu es un expert Windows services et processus.",
    "win_security": "Tu es un expert Windows sécurité et audit.",
    "win_network": "Tu es un expert Windows réseau et connectivité.",
    "win_storage": "Tu es un expert Windows stockage et disques.",
    "win_performance": "Tu es un expert Windows performance et optimisation.",
    "ia_training": "Tu es un expert IA training et fine-tuning pour JARVIS.",
    "ia_benchmark": "Tu es un expert IA benchmark et évaluation de modèles.",
    "ia_routing": "Tu es un expert IA routage et dispatch intelligent.",
    "cw-trading-signals": "Tu es un expert trading signals et analyse de marché.",
    "cw-health": "Tu es un expert santé système et monitoring.",
    "cw-deploy": "Tu es un expert déploiement et CI/CD.",
    "linux_monitor": "Tu es un expert Linux monitoring et administration.",
    "linux_security": "Tu es un expert Linux sécurité et hardening.",
    "docker_ops": "Tu es un expert Docker et conteneurs.",
}


@dataclass
class DynamicAgent:
    """A dynamically spawned agent from DB patterns."""
    pattern_type: str
    agent_id: str
    model_primary: str
    model_fallbacks: str
    strategy: str
    system_prompt: str
    node: str
    fallback_nodes: list[str] = field(default_factory=list)
    cowork_scripts: list[str] = field(default_factory=list)
    max_tokens: int = 1024
    temperature: float = 0.3

    def to_pattern_agent(self) -> Any:
        """Convert to a PatternAgent-compatible object."""
        from types import SimpleNamespace
        return SimpleNamespace(
            pattern_type=self.pattern_type,
            primary_node=self.node,
            system_prompt=self.system_prompt,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            model_primary=self.model_primary,
            model_fallbacks=self.model_fallbacks,
            strategy=self.strategy,
        )


class DynamicAgentSpawner:
    """Loads agent patterns from DB and spawns DynamicAgent instances."""

    def __init__(self) -> None:
        self.agents: dict[str, DynamicAgent] = {}
        self._loaded = False

    def load_all(self) -> dict[str, DynamicAgent]:
        """Load all agent patterns from DB, skipping hardcoded ones."""
        self._loaded = True
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM agent_patterns").fetchall()
            conn.close()
        except Exception as e:
            logger.warning("Failed to load dynamic agents: %s", e)
            return {}

        for row in rows:
            pt = row["pattern_type"]
            if pt in _HARDCODED_PATTERNS:
                continue
            model = row["model_primary"] or "qwen3-8b"
            node = MODEL_TO_NODE.get(model, "M1")
            agent_id = row["agent_id"] or pt
            prompt = self._generate_prompt(pt, agent_id)
            self.agents[pt] = DynamicAgent(
                pattern_type=pt,
                agent_id=agent_id,
                model_primary=model,
                model_fallbacks=row["model_fallbacks"] or "",
                strategy=row["strategy"] or "single",
                system_prompt=prompt,
                node=node,
            )
        return self.agents

    def _generate_prompt(self, pattern_type: str, agent_id: str) -> str:
        """Generate a system prompt based on category prefix."""
        # Try exact match first
        if pattern_type in CATEGORY_PROMPTS:
            return CATEGORY_PROMPTS[pattern_type]
        # Try prefix match
        for prefix, prompt in CATEGORY_PROMPTS.items():
            if pattern_type.startswith(prefix.split("_")[0] + "_") or \
               pattern_type.startswith(prefix.split("-")[0] + "-"):
                return prompt
        # Generic fallback
        clean_name = pattern_type.replace("_", " ").replace("-", " ")
        return f"Tu es un expert {clean_name} pour JARVIS. Exécute les tâches avec précision."

    def list_agents(self) -> list[dict[str, Any]]:
        """List all loaded dynamic agents."""
        result = []
        for pt in sorted(self.agents):
            a = self.agents[pt]
            result.append({
                "pattern": a.pattern_type,
                "agent_id": a.agent_id,
                "node": a.node,
                "model": a.model_primary,
                "strategy": a.strategy,
            })
        return result

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about loaded dynamic agents."""
        by_strategy: Counter[str] = Counter()
        by_node: Counter[str] = Counter()
        for a in self.agents.values():
            by_strategy[a.strategy] += 1
            by_node[a.node] += 1
        return {
            "total_dynamic_agents": len(self.agents),
            "loaded": self._loaded,
            "by_strategy": dict(by_strategy),
            "by_node": dict(by_node),
        }


dynamic_agents = DynamicAgentSpawner()
