"""JARVIS Dynamic Agent Spawner — Create agents from DB patterns at runtime.

Reads agent_patterns from etoile.db and creates executable PatternAgent instances
for ALL registered patterns (76+), not just the 20 hardcoded ones.

Features:
  - Load patterns from DB into live agents
  - Cowork-backed agents (execute scripts for cw-* patterns)
  - Auto-system-prompt generation per category
  - Sync DB -> memory agents
  - Register new patterns discovered by the system

Usage:
    from src.dynamic_agents import DynamicAgentSpawner, get_spawner
    spawner = get_spawner()
    agents = spawner.load_all()
    result = await spawner.dispatch("win_monitoring", "Check GPU temps")
"""

from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx


__all__ = [
    "DynamicAgent",
    "DynamicAgentSpawner",
    "get_spawner",
]

logger = logging.getLogger("jarvis.dynamic_agents")

DB_PATH = "F:/BUREAU/turbo/etoile.db"

# System prompts by category prefix
CATEGORY_PROMPTS = {
    "win_": "Tu es un expert Windows. PowerShell, services, registre, fichiers. Reponds avec des commandes executables.",
    "jarvis_": "Tu es le coeur de JARVIS. Orchestration, pipelines, dashboards, intelligence. Optimise et ameliore.",
    "ia_": "Tu es un expert IA. Machine learning, NLP, optimisation, inference. Analyse et genere.",
    "cw-win": "Tu geres les scripts Windows du workspace OpenClaw. Automatisation, monitoring, desktop.",
    "cw-jarvis": "Tu geres les scripts JARVIS du workspace OpenClaw. Core, dashboards, pipelines, NLP.",
    "cw-ia": "Tu geres les scripts IA du workspace OpenClaw. Analyse, generation, apprentissage, orchestration.",
    "cw-trading": "Tu geres les scripts trading du workspace OpenClaw. Signaux, portfolio, risk management.",
    "cw-cluster": "Tu geres les scripts cluster du workspace OpenClaw. Noeuds, GPU, load balancing.",
    "cw-browser": "Tu geres les scripts browser du workspace OpenClaw. Navigation, scraping, automation web.",
    "cw-comms": "Tu geres les communications. Telegram, email, notifications.",
    "cw-data": "Tu geres les donnees. Backup, sync, migration, nettoyage.",
    "cw-devtools": "Tu geres les outils de dev. Linting, testing, CI/CD, scripts utilitaires.",
    "cw-routing": "Tu geres le routage des agents. Dispatch, load balancing, failover.",
    "cw-file-watch": "Tu surveilles les fichiers. Changements, synchronisation, triggers.",
    "discovered-": "Tu traites les patterns decouverts par le systeme. Adapte-toi au contexte du prompt.",
    "fix_": "Tu corriges les erreurs des autres agents. Analyse l'echec et propose une meilleure reponse.",
    "cross_": "Tu combines plusieurs sources. Synthese multi-agent, comparaison, merge d'outputs.",
}

# Model mapping from DB model names to NODES keys
MODEL_TO_NODE = {
    "qwen3-8b": "M1",
    "qwen3:1.7b": "OL1",
    "deepseek-r1-0528-qwen3-8b": "M2",
}


@dataclass
class DynamicAgent:
    """A dynamically-spawned agent from DB pattern."""
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

    def to_pattern_agent(self):
        """Convert to a PatternAgent for execution."""
        from src.pattern_agents import PatternAgent
        return PatternAgent(
            pattern_id=f"DYN_{self.pattern_type.upper()}",
            pattern_type=self.pattern_type,
            agent_id=self.agent_id,
            system_prompt=self.system_prompt,
            primary_node=self.node,
            fallback_nodes=self.fallback_nodes,
            strategy=self.strategy,
            priority=5,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )


class DynamicAgentSpawner:
    """Load and manage dynamic agents from DB patterns."""

    def __init__(self):
        self.agents: dict[str, DynamicAgent] = {}
        self._loaded = False

    def load_all(self) -> dict[str, DynamicAgent]:
        """Load all patterns from DB and create dynamic agents."""
        try:
            db = sqlite3.connect(DB_PATH)
            db.row_factory = sqlite3.Row
            rows = db.execute("""
                SELECT pattern_type, agent_id, model_primary, model_fallbacks, strategy
                FROM agent_patterns ORDER BY pattern_type
            """).fetchall()
            db.close()

            # Get existing hardcoded patterns to skip
            from src.pattern_agents import PatternAgentRegistry
            reg = PatternAgentRegistry()
            hardcoded = set(reg.agents.keys())

            for row in rows:
                pt = row["pattern_type"]
                if pt in hardcoded:
                    continue  # Already has a code agent

                # Determine node from model
                model = row["model_primary"] or "qwen3-8b"
                node = MODEL_TO_NODE.get(model, "M1")

                # Determine fallback nodes
                fallbacks_str = row["model_fallbacks"] or ""
                fb_nodes = []
                for fb_model in fallbacks_str.split(","):
                    fb_model = fb_model.strip()
                    if fb_model:
                        fb_node = MODEL_TO_NODE.get(fb_model, "")
                        if fb_node and fb_node != node:
                            fb_nodes.append(fb_node)
                if not fb_nodes:
                    fb_nodes = ["M1"] if node != "M1" else ["OL1"]

                # Generate system prompt
                system_prompt = self._generate_prompt(pt, row["agent_id"])

                # Check for cowork scripts
                cowork_scripts = self._find_cowork_scripts(pt)

                agent = DynamicAgent(
                    pattern_type=pt,
                    agent_id=row["agent_id"],
                    model_primary=model,
                    model_fallbacks=fallbacks_str,
                    strategy=row["strategy"] or "single",
                    system_prompt=system_prompt,
                    node=node,
                    fallback_nodes=fb_nodes,
                    cowork_scripts=cowork_scripts,
                    max_tokens=2048 if "reasoning" in pt or "analysis" in pt else 1024,
                )
                self.agents[pt] = agent

            self._loaded = True
            logger.info(f"Loaded {len(self.agents)} dynamic agents from DB")
            return self.agents

        except Exception as e:
            logger.error(f"Failed to load dynamic agents: {e}")
            return {}

    def _generate_prompt(self, pattern_type: str, agent_id: str) -> str:
        """Generate a system prompt for a pattern type."""
        for prefix, prompt in CATEGORY_PROMPTS.items():
            if pattern_type.startswith(prefix) or agent_id.startswith(prefix):
                return prompt

        # Generic prompt based on pattern name
        words = pattern_type.replace("_", " ").replace("-", " ")
        return f"Tu es un expert en {words}. Analyse la demande et fournis une reponse precise et actionable."

    def _find_cowork_scripts(self, pattern_type: str) -> list[str]:
        """Find cowork scripts matching a pattern type."""
        try:
            from src.cowork_bridge import get_bridge
            bridge = get_bridge()
            results = bridge.search(pattern_type.replace("_", " "), limit=5)
            return [r["name"] for r in results]
        except Exception:
            return []

    async def dispatch(self, pattern_type: str, prompt: str):
        """Dispatch to a dynamic agent."""
        if not self._loaded:
            self.load_all()

        agent = self.agents.get(pattern_type)
        if not agent:
            return {"error": f"No dynamic agent for pattern '{pattern_type}'",
                    "available": list(self.agents.keys())[:20]}

        pa = agent.to_pattern_agent()
        async with httpx.AsyncClient() as client:
            result = await pa.execute(client, prompt)
            return {
                "content": result.content,
                "node": result.node,
                "model": result.model,
                "latency_ms": result.latency_ms,
                "quality": result.quality_score,
                "ok": result.ok,
                "strategy": result.strategy,
                "pattern": pattern_type,
                "agent_id": agent.agent_id,
                "cowork_scripts": agent.cowork_scripts,
            }

    async def dispatch_with_cowork(self, pattern_type: str, prompt: str):
        """Dispatch to agent AND run relevant cowork scripts."""
        agent_result = await self.dispatch(pattern_type, prompt)

        cowork_results = []
        agent = self.agents.get(pattern_type)
        if agent and agent.cowork_scripts:
            try:
                from src.cowork_bridge import get_bridge
                bridge = get_bridge()
                for script_name in agent.cowork_scripts[:2]:
                    cr = bridge.execute(script_name, ["--once"], timeout_s=30)
                    cowork_results.append({
                        "script": cr.script,
                        "success": cr.success,
                        "duration_ms": cr.duration_ms,
                        "output_preview": cr.stdout[:200] if cr.stdout else "",
                    })
            except Exception as e:
                cowork_results.append({"error": str(e)})

        return {
            "agent": agent_result,
            "cowork": cowork_results,
        }

    def register_to_registry(self) -> int:
        """Register all dynamic agents into the live PatternAgentRegistry."""
        if not self._loaded:
            self.load_all()

        try:
            from src.pattern_agents import PatternAgentRegistry
            reg = PatternAgentRegistry()
            count = 0
            for pt, agent in self.agents.items():
                if pt not in reg.agents:
                    reg.agents[pt] = agent.to_pattern_agent()
                    count += 1
            logger.info(f"Registered {count} dynamic agents into PatternAgentRegistry")
            return count
        except Exception as e:
            logger.error(f"Failed to register dynamic agents: {e}")
            return 0

    def get_stats(self) -> dict:
        """Dynamic agent stats."""
        if not self._loaded:
            self.load_all()

        by_strategy = {}
        by_node = {}
        with_cowork = 0
        for agent in self.agents.values():
            by_strategy[agent.strategy] = by_strategy.get(agent.strategy, 0) + 1
            by_node[agent.node] = by_node.get(agent.node, 0) + 1
            if agent.cowork_scripts:
                with_cowork += 1

        return {
            "total_dynamic_agents": len(self.agents),
            "loaded": self._loaded,
            "by_strategy": by_strategy,
            "by_node": by_node,
            "with_cowork_scripts": with_cowork,
            "patterns": sorted(self.agents.keys()),
        }

    def list_agents(self) -> list[dict]:
        """List all dynamic agents."""
        if not self._loaded:
            self.load_all()

        return [
            {
                "pattern": a.pattern_type,
                "agent_id": a.agent_id,
                "node": a.node,
                "strategy": a.strategy,
                "model": a.model_primary,
                "cowork_scripts": len(a.cowork_scripts),
                "system_prompt_preview": a.system_prompt[:80],
            }
            for a in sorted(self.agents.values(), key=lambda a: a.pattern_type)
        ]


# Singleton
_spawner: Optional[DynamicAgentSpawner] = None

def get_spawner() -> DynamicAgentSpawner:
    global _spawner
    if _spawner is None:
        _spawner = DynamicAgentSpawner()
    return _spawner
