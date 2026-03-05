"""JARVIS Pattern Agents — 14 specialized agents, one per pattern type.

Each agent encapsulates:
  - System prompt tuned for its domain
  - Preferred node + fallback chain
  - Strategy (single/race/consensus/category)
  - Quality scoring specific to its domain
  - Auto-learning from dispatch_log results

Usage:
    from src.pattern_agents import PatternAgentRegistry
    registry = PatternAgentRegistry()
    result = await registry.dispatch("code", "Ecris un parser JSON Python")
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx

logger = logging.getLogger("jarvis.pattern_agents")

# ── Node configs ────────────────────────────────────────────────────────────
NODES = {
    "M1": {
        "url": "http://127.0.0.1:1234/api/v1/chat",
        "type": "lmstudio",
        "model": "qwen3-8b",
        "prefix": "/nothink\n",
        "max_tokens": 1024,
        "weight": 1.8,
    },
    "M1B": {
        "url": "http://127.0.0.1:1234/api/v1/chat",
        "type": "lmstudio",
        "model": "gpt-oss-20b",
        "prefix": "/nothink\n",
        "max_tokens": 2048,
        "weight": 1.7,
    },
    "M2": {
        "url": "http://192.168.1.26:1234/api/v1/chat",
        "type": "lmstudio",
        "model": "deepseek-r1-0528-qwen3-8b",
        "prefix": "",
        "max_tokens": 2048,
        "weight": 1.5,
    },
    "M3": {
        "url": "http://192.168.1.113:1234/api/v1/chat",
        "type": "lmstudio",
        "model": "deepseek-r1-0528-qwen3-8b",
        "prefix": "",
        "max_tokens": 2048,
        "weight": 1.2,
    },
    "OL1": {
        "url": "http://127.0.0.1:11434/api/chat",
        "type": "ollama",
        "model": "qwen3:1.7b",
        "weight": 1.3,
    },
    "gpt-oss": {
        "url": "http://127.0.0.1:11434/api/chat",
        "type": "ollama",
        "model": "gpt-oss:120b-cloud",
        "weight": 1.9,
    },
    "devstral": {
        "url": "http://127.0.0.1:11434/api/chat",
        "type": "ollama",
        "model": "devstral-2:123b-cloud",
        "weight": 1.5,
    },
    "minimax": {
        "url": "http://127.0.0.1:11434/api/chat",
        "type": "ollama",
        "model": "minimax-m2.5:cloud",
        "weight": 1.0,
    },
}


@dataclass
class AgentResult:
    content: str
    node: str
    model: str
    latency_ms: float
    tokens: int
    ok: bool
    strategy: str
    pattern: str
    error: str = ""
    quality_score: float = 0.0
    metadata: Optional[dict] = None


@dataclass
class PatternAgent:
    """A specialized agent for one pattern type."""
    pattern_id: str
    pattern_type: str
    agent_id: str
    system_prompt: str
    primary_node: str
    fallback_nodes: list[str]
    strategy: str  # single, race, consensus, category, chain
    priority: int
    keywords: list[str] = field(default_factory=list)
    max_tokens: int = 1024
    temperature: float = 0.3

    # Dynamic timeout configuration (seconds)
    # Based on adaptive_timeout_manager analysis: code/M1 p95=59s needs >60s
    PATTERN_TIMEOUT = {
        "simple": 15, "classifier": 15,
        "code": 90, "creative": 75, "system": 60, "web": 60,
        "devops": 60, "math": 90, "trading": 75,
        "analysis": 120, "architecture": 120, "security": 120,
        "data": 120, "reasoning": 150, "large": 150,
    }
    NODE_TIMEOUT_FACTOR = {
        "M1": 1.0, "M1B": 2.0, "OL1": 1.0,
        "M2": 2.0, "M3": 2.5,
        "gpt-oss": 2.0, "devstral": 2.0, "minimax": 1.5,
    }

    def _calc_timeout(self, node_name: str, prompt: str) -> float:
        """Calculate dynamic timeout based on pattern + node + prompt length.

        Like a door: open it just long enough for the message to pass through.
        Simple message (walking through) = short timeout.
        Complex message (carrying boxes) = longer timeout.
        """
        base = self.PATTERN_TIMEOUT.get(self.pattern_type, 60)
        factor = self.NODE_TIMEOUT_FACTOR.get(node_name, 1.5)
        # Add time for long prompts (1s per 500 chars over 1000)
        prompt_extra = max(0, (len(prompt) - 1000) / 500)
        timeout = base * factor + prompt_extra
        return max(10, min(180, timeout))  # clamp 10s-180s

    # Context window limits per node (in tokens, ~4 chars per token)
    NODE_CTX_LIMITS = {
        "M1": 32000, "M1B": 25000, "M2": 27000, "M3": 25000,
        "OL1": 32000, "gpt-oss": 128000, "devstral": 128000,
        "minimax": 128000,
    }
    # Min output tokens per node (reasoning models need more space)
    NODE_MIN_OUTPUT = {
        "M2": 2048, "M3": 2048,  # deepseek-r1 needs reasoning space
    }

    def _adapt_max_tokens(self, node_name: str, prompt: str) -> int:
        """Adapt max_output_tokens to avoid context size overflow.

        Estimates prompt tokens and reserves space for output within the
        node's context window. Prevents 'Context size exceeded' errors.
        """
        ctx_limit = self.NODE_CTX_LIMITS.get(node_name, 32000)
        # Rough token estimate: ~4 chars per token for mixed fr/en
        prompt_tokens_est = len(prompt) // 4 + 50  # +50 for system prompt overhead
        available = ctx_limit - prompt_tokens_est
        # Ensure at least 256 tokens for output, cap at configured max_tokens
        min_out = self.NODE_MIN_OUTPUT.get(node_name, 256)
        adapted = max(min_out, min(self.max_tokens, available))
        # If prompt is already >80% of context, aggressively limit output
        if prompt_tokens_est > ctx_limit * 0.8:
            adapted = min(512, available)
        return adapted

    async def execute(self, client: httpx.AsyncClient, prompt: str) -> AgentResult:
        """Execute this agent's strategy."""
        full_prompt = f"{self.system_prompt}\n\nUser: {prompt}" if self.system_prompt else prompt

        if self.strategy == "single":
            return await self._single(client, full_prompt)
        elif self.strategy == "race":
            return await self._race(client, full_prompt)
        elif self.strategy == "consensus":
            return await self._consensus(client, full_prompt)
        elif self.strategy == "category":
            return await self._category(client, full_prompt)
        elif self.strategy == "chain":
            return await self._chain(client, full_prompt)
        else:
            return await self._single(client, full_prompt)

    async def _call_node(self, client: httpx.AsyncClient, node_name: str, prompt: str) -> AgentResult:
        node = NODES.get(node_name)
        if not node:
            return AgentResult("", node_name, "?", 0, 0, False, self.strategy, self.pattern_type, error=f"Unknown node: {node_name}")

        timeout = self._calc_timeout(node_name, prompt)
        t0 = time.perf_counter()
        try:
            if node["type"] == "lmstudio":
                # Adapt max_output_tokens to avoid context overflow
                max_tok = self._adapt_max_tokens(node_name, prompt)
                body = {
                    "model": node["model"],
                    "input": f"{node.get('prefix', '')}{prompt}",
                    "temperature": self.temperature,
                    "max_output_tokens": max_tok,
                    "stream": False,
                    "store": False,
                }
                r = await client.post(node["url"], json=body, timeout=timeout)
                data = r.json()
                # Check for context size exceeded error
                if data.get("error"):
                    err_msg = str(data["error"])
                    if "context" in err_msg.lower() or "exceeded" in err_msg.lower():
                        # Context overflow: truncate prompt and retry with fewer tokens
                        truncated = prompt[:len(prompt)//2]
                        body["input"] = f"{node.get('prefix', '')}{truncated}"
                        body["max_output_tokens"] = min(max_tok, 512)
                        r = await client.post(node["url"], json=body, timeout=timeout)
                        data = r.json()
                content = ""
                for o in data.get("output", []):
                    if o.get("type") == "message":
                        c = o.get("content", "")
                        if isinstance(c, list):
                            content = c[0].get("text", "") if c else ""
                        else:
                            content = str(c)
            else:  # ollama
                body = {
                    "model": node["model"],
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "think": False,
                }
                r = await client.post(node["url"], json=body, timeout=timeout)
                data = r.json()
                content = data.get("message", {}).get("content", "")

            ms = (time.perf_counter() - t0) * 1000
            tokens = len(content.split())
            quality = self._score_quality(prompt, content)
            return AgentResult(content, node_name, node["model"], ms, tokens, bool(content), self.strategy, self.pattern_type, quality_score=quality)

        except Exception as e:
            ms = (time.perf_counter() - t0) * 1000
            return AgentResult("", node_name, node.get("model", "?"), ms, 0, False, self.strategy, self.pattern_type, error=str(e)[:200])

    async def _single(self, client, prompt) -> AgentResult:
        result = await self._call_node(client, self.primary_node, prompt)
        if result.ok:
            return result
        for fb in self.fallback_nodes:
            result = await self._call_node(client, fb, prompt)
            if result.ok:
                result.strategy = f"single:fallback={fb}"
                return result
        return result

    async def _race(self, client, prompt) -> AgentResult:
        all_nodes = [self.primary_node] + self.fallback_nodes[:3]
        tasks = [self._call_node(client, n, prompt) for n in all_nodes]
        results = await asyncio.gather(*tasks)
        ok = [r for r in results if r.ok]
        if ok:
            # Score = quality * node_weight / (latency_ms / 1000)
            # Balances quality, node reliability weight, and speed
            def race_score(r):
                w = NODES.get(r.node, {}).get("weight", 1.0)
                q = max(0.1, r.quality_score)
                lat_s = max(0.5, r.latency_ms / 1000)
                return q * w / lat_s
            best = max(ok, key=race_score)
            runners = ",".join(r.node for r in ok if r.node != best.node)
            best.strategy = f"race:winner={best.node}" + (f":vs={runners}" if runners else "")
            return best
        return results[0]

    async def _consensus(self, client, prompt) -> AgentResult:
        nodes = [self.primary_node] + self.fallback_nodes[:1]
        tasks = [self._call_node(client, n, prompt) for n in nodes]
        results = await asyncio.gather(*tasks)
        ok = [r for r in results if r.ok]
        if len(ok) >= 2:
            # Weighted: pick highest quality * weight
            for r in ok:
                w = NODES.get(r.node, {}).get("weight", 1.0)
                r.quality_score = r.quality_score * w
            best = max(ok, key=lambda r: r.quality_score)
            best.strategy = f"consensus:{'+'.join(r.node for r in ok)}"
            return best
        elif ok:
            return ok[0]
        return results[0] if results else AgentResult("", "?", "?", 0, 0, False, "consensus", self.pattern_type)

    async def _category(self, client, prompt) -> AgentResult:
        result = await self._call_node(client, self.primary_node, prompt)
        if result.ok and result.quality_score >= 0.3:
            return result
        # Quality fallback
        for fb in self.fallback_nodes:
            result = await self._call_node(client, fb, prompt)
            if result.ok:
                result.strategy = f"category:fallback={fb}"
                return result
        return result

    async def _chain(self, client, prompt) -> AgentResult:
        r1 = await self._call_node(client, self.primary_node, prompt)
        if not r1.ok:
            return r1
        verify_prompt = f"Verifie et ameliore si necessaire:\nQuestion: {prompt[:200]}\nReponse: {r1.content[:500]}"
        r2 = await self._call_node(client, self.fallback_nodes[0] if self.fallback_nodes else self.primary_node, verify_prompt)
        if r2.ok:
            r2.latency_ms += r1.latency_ms
            r2.strategy = f"chain:{r1.node}->{r2.node}"
            return r2
        return r1

    def _score_quality(self, prompt: str, content: str) -> float:
        if not content:
            return 0.0
        prompt_words = len(prompt.split())
        content_words = len(content.split())
        score = 0.0

        # Length score: adequate response length
        if content_words < 3:
            score += 0.05
        elif content_words < 10:
            score += 0.15
        else:
            score += min(0.35, 0.15 + content_words / max(1, prompt_words * 5))

        # Structure score: code blocks, lists, headers
        has_code = "```" in content or "def " in content or "class " in content
        has_list = any(content.count(c) >= 2 for c in ["1)", "1.", "- ", "* "])
        has_headers = "###" in content or "##" in content
        struct_bonus = 0.15 * has_code + 0.1 * has_list + 0.05 * has_headers
        score += min(0.3, struct_bonus)

        # Relevance: keyword overlap between prompt and content
        prompt_kw = set(prompt.lower().split())
        content_kw = set(content.lower().split())
        overlap = len(prompt_kw & content_kw) / max(1, len(prompt_kw))
        score += min(0.2, overlap * 0.3)

        # Anti-hallucination penalty
        bad_phrases = ["en tant qu'ia", "je ne peux pas", "je suis un modele", "i cannot"]
        if any(bp in content.lower() for bp in bad_phrases):
            score *= 0.5

        return round(min(1.0, score), 3)


# ── AGENT DEFINITIONS ───────────────────────────────────────────────────────

AGENT_CONFIGS = [
    PatternAgent(
        pattern_id="PAT_TASK_ROUTER",
        pattern_type="classifier",
        agent_id="task-router",
        system_prompt="Tu es un classificateur de taches. Analyse la demande et identifie: le type (code/analyse/math/system/trading/creative/web/security/architecture/data/devops/reasoning/simple), la complexite (nano/micro/small/medium/large/xl), et le meilleur noeud de traitement.",
        primary_node="M1",
        fallback_nodes=["OL1"],
        strategy="single",  # benchmark: single fastest for classification
        priority=1,
        keywords=["classifie", "route", "dispatch", "quel agent", "type de tache"],
    ),
    PatternAgent(
        pattern_id="PAT_QUICK_DISPATCH",
        pattern_type="simple",
        agent_id="quick-dispatch",
        system_prompt="Reponds de facon ultra-concise et rapide. Pas d'explication superflue.",
        primary_node="OL1",
        fallback_nodes=["M1"],
        strategy="single",
        priority=2,
        keywords=["bonjour", "merci", "oui", "non", "ok", "date", "heure", "salut"],
        max_tokens=256,
    ),
    PatternAgent(
        pattern_id="PAT_WEB_RESEARCHER",
        pattern_type="web",
        agent_id="web-researcher",
        system_prompt="Tu es un assistant de recherche web. Fournis des informations a jour et verifiees.",
        primary_node="minimax",
        fallback_nodes=["M1", "OL1"],
        strategy="single",
        priority=2,
        keywords=["recherche", "web", "internet", "actualite", "news", "prix", "meteo"],
    ),
    PatternAgent(
        pattern_id="PAT_CODE_CHAMPION",
        pattern_type="code",
        agent_id="code-champion",
        system_prompt="Expert programmation. Reponds UNIQUEMENT avec du code executable. Pas d'explication sauf si demande. Python prefere. Inclus les imports.",
        primary_node="M1",
        fallback_nodes=["gpt-oss", "devstral", "OL1"],
        strategy="race",  # benchmark-v2: race M1+cloud (was 47% with category — cloud backup for complex code)
        priority=3,
        keywords=["ecris", "code", "fonction", "classe", "script", "debug", "fix", "refactor", "python", "javascript"],
        max_tokens=2048,
    ),
    PatternAgent(
        pattern_id="PAT_ANALYSIS_ENGINE",
        pattern_type="analysis",
        agent_id="analysis-engine",
        system_prompt="Analyste expert. Reponds directement avec: 1) Donnees factuelles 2) Tableau comparatif si applicable 3) Verdict clair. Pas d'introduction ni conclusion generique.",
        primary_node="M1",
        fallback_nodes=["gpt-oss", "devstral", "OL1"],
        strategy="race",  # benchmark-v2: race M1+cloud for complex analysis (was 22% with category)
        priority=3,
        keywords=["compare", "analyse", "avantages", "inconvenients", "benchmark", "audit", "rapport"],
        max_tokens=2048,
    ),
    PatternAgent(
        pattern_id="PAT_SYSTEM_OPS",
        pattern_type="system",
        agent_id="system-ops",
        system_prompt="Tu es un admin systeme Windows expert. PowerShell, services, GPU, disques, monitoring, cluster. Reponds avec des commandes executables.",
        primary_node="M1",
        fallback_nodes=["OL1"],
        strategy="single",  # benchmark: single 100% vs category 86%
        priority=3,
        keywords=["gpu", "cpu", "ram", "disque", "service", "process", "powershell", "windows", "monitoring"],
    ),
    PatternAgent(
        pattern_id="PAT_CREATIVE_WRITER",
        pattern_type="creative",
        agent_id="creative-writer",
        system_prompt="Tu es un ecrivain creatif. Poemes, histoires, dialogues, articles. Style vivant et original.",
        primary_node="M1",
        fallback_nodes=["OL1"],
        strategy="race",  # benchmark: race 100% Q=1.0 vs single 91%
        priority=3,
        keywords=["ecris", "poeme", "histoire", "article", "blog", "scenario", "dialogue", "creatif"],
    ),
    PatternAgent(
        pattern_id="PAT_MATH_SOLVER",
        pattern_type="math",
        agent_id="math-solver",
        system_prompt="Tu es un mathematicien. Resous les problemes etape par etape. Montre ton raisonnement. Verifie tes calculs.",
        primary_node="M1",  # benchmark: M1 faster+reliable vs M2 timeout
        fallback_nodes=["OL1"],
        strategy="single",  # benchmark: single best for math on M1
        priority=3,
        keywords=["calcule", "equation", "derivee", "integrale", "probabilite", "matrice", "statistique"],
        max_tokens=2048,
    ),
    PatternAgent(
        pattern_id="PAT_DATA_ENGINEER",
        pattern_type="data",
        agent_id="data-engineer",
        system_prompt="Data engineer. Reponds avec du code SQL/Python executable directement. Schema si necessaire. Pas de theorie, que du pratique.",
        primary_node="M1",
        fallback_nodes=["gpt-oss", "devstral", "OL1"],
        strategy="race",  # benchmark-v2: race M1+cloud (was 30% with single — timeout issues on complex queries)
        priority=3,
        keywords=["sql", "requete", "base", "donnees", "table", "index", "etl", "csv", "json", "sqlite"],
        max_tokens=2048,
    ),
    PatternAgent(
        pattern_id="PAT_DEVOPS_OPS",
        pattern_type="devops",
        agent_id="devops-ops",
        system_prompt="Tu es un DevOps engineer. Docker, CI/CD, git, deployment, monitoring, infrastructure. Solutions pratiques.",
        primary_node="M1",
        fallback_nodes=["OL1"],
        strategy="single",  # benchmark: single fastest for devops
        priority=3,
        keywords=["docker", "ci", "cd", "deploy", "pipeline", "github", "actions", "kubernetes", "git"],
    ),
    PatternAgent(
        pattern_id="PAT_DEEP_REASONING",
        pattern_type="reasoning",
        agent_id="deep-reasoning",
        system_prompt="Expert raisonnement. Decompose en etapes numerotees. Chaque etape: affirmation + justification. Conclusion claire a la fin.",
        primary_node="M1",
        fallback_nodes=["gpt-oss", "M2", "OL1"],
        strategy="race",  # benchmark-v2: race M1+cloud (was 45% with single — cloud models better at deep reasoning)
        priority=4,
        keywords=["pourquoi", "prouve", "demontre", "logique", "dilemme", "strategie", "optimal"],
        max_tokens=2048,
        temperature=0.2,
    ),
    PatternAgent(
        pattern_id="PAT_TRADING_ANALYST",
        pattern_type="trading",
        agent_id="trading-analyst",
        system_prompt="Analyste trading MEXC 10x futures. Reponds avec: 1) Signal (LONG/SHORT/WAIT) 2) Entree/TP/SL precis 3) Score confiance 0-100. Donnees chiffrees uniquement.",
        primary_node="M1",
        fallback_nodes=["gpt-oss", "OL1"],
        strategy="race",  # benchmark-v2: race M1+cloud (was 55% — cloud better at complex analysis)
        priority=4,
        keywords=["trading", "btc", "crypto", "rsi", "macd", "futures", "tp", "sl", "mexc"],
    ),
    PatternAgent(
        pattern_id="PAT_SECURITY_AUDITOR",
        pattern_type="security",
        agent_id="security-auditor",
        system_prompt="Expert cybersecurite. Reponds avec: 1) Vulnerabilites identifiees 2) Severite (CRITICAL/HIGH/MEDIUM/LOW) 3) Correction precise. Code corrige si applicable. Pas de blabla.",
        primary_node="M1",
        fallback_nodes=["gpt-oss", "devstral", "OL1"],
        strategy="race",  # benchmark-v2: race M1+cloud (was 20.3% — needs cloud backup)
        priority=4,
        keywords=["securite", "owasp", "injection", "xss", "csrf", "auth", "chiffrement", "audit"],
        max_tokens=2048,
    ),
    PatternAgent(
        pattern_id="PAT_ARCHITECT",
        pattern_type="architecture",
        agent_id="architect",
        system_prompt="Architecte logiciel. Reponds avec: 1) Diagramme textuel (ASCII/Mermaid) 2) Composants + responsabilites 3) Trade-offs. Pas de cours magistral, va droit au schema.",
        primary_node="M1",
        fallback_nodes=["gpt-oss", "devstral", "OL1"],
        strategy="race",  # benchmark-v2: race M1+cloud (was 7.8% — worst pattern, needs aggressive retry)
        priority=4,
        keywords=["architecture", "microservices", "design", "pattern", "scalable", "event", "cqrs", "saga"],
        max_tokens=2048,
    ),
    # ── JARVIS Domain Agents (6 new) ─────────────────────────────────────
    PatternAgent(
        pattern_id="PAT_VOICE_PROCESSOR",
        pattern_type="voice",
        agent_id="voice-processor",
        system_prompt="Tu geres le pipeline vocal JARVIS: commandes vocales, TTS, STT, audio. Reponds avec les actions a executer.",
        primary_node="M1",
        fallback_nodes=["OL1"],
        strategy="single",
        priority=3,
        keywords=["voix", "vocal", "parle", "dis", "prononce", "tts", "whisper", "audio", "micro"],
        max_tokens=512,
    ),
    PatternAgent(
        pattern_id="PAT_EMAIL_MANAGER",
        pattern_type="email",
        agent_id="email-manager",
        system_prompt="Tu geres les emails JARVIS: lecture IMAP, resume, filtrage, reponses. Gmail miningexpert31 + franckdelmas00.",
        primary_node="M1",
        fallback_nodes=["OL1"],
        strategy="single",
        priority=3,
        keywords=["email", "mail", "inbox", "envoie", "message", "gmail", "imap"],
    ),
    PatternAgent(
        pattern_id="PAT_AUTOMATION",
        pattern_type="automation",
        agent_id="automation-engine",
        system_prompt="Tu geres l'automatisation JARVIS: crons, pipelines, workflows, taches planifiees. 48 crons, 79 scripts COWORK.",
        primary_node="M1",
        fallback_nodes=["OL1"],
        strategy="category",
        priority=3,
        keywords=["automatise", "cron", "schedule", "tache", "planifie", "batch", "pipeline", "workflow"],
    ),
    PatternAgent(
        pattern_id="PAT_LEARNING",
        pattern_type="learning",
        agent_id="learning-engine",
        system_prompt="Tu geres l'auto-apprentissage JARVIS: feedback, finetuning, amelioration continue, autolearn engine.",
        primary_node="M1",
        fallback_nodes=["OL1"],
        strategy="single",
        priority=4,
        keywords=["apprends", "ameliore", "optimise", "entrainement", "finetuning", "feedback"],
    ),
    PatternAgent(
        pattern_id="PAT_MONITORING",
        pattern_type="monitoring",
        agent_id="monitoring-agent",
        system_prompt="Tu monitores le cluster JARVIS: health checks, alertes, seuils, GPU temp, VRAM, services. Reponds avec le statut.",
        primary_node="M1",
        fallback_nodes=["OL1"],
        strategy="single",
        priority=2,
        keywords=["monitore", "surveille", "alerte", "seuil", "health", "status", "dashboard"],
    ),
    PatternAgent(
        pattern_id="PAT_OPTIMIZER",
        pattern_type="optimization",
        agent_id="optimizer-agent",
        system_prompt="Tu optimises les performances JARVIS: latence, throughput, cache, memoire, routing. Propose des ameliorations concretes.",
        primary_node="M1",
        fallback_nodes=["OL1"],
        strategy="single",
        priority=3,
        keywords=["optimise", "performance", "latence", "throughput", "cache", "memory", "vitesse"],
    ),
    # ── Size-based agents (complexity routing) ────────────────────────────
    PatternAgent(
        pattern_id="PAT_NANO",
        pattern_type="nano",
        agent_id="nano-handler",
        system_prompt="Reponds en 1 phrase maximum. Ultra-concis.",
        primary_node="OL1",
        fallback_nodes=["M1"],
        strategy="single",
        priority=1,
        keywords=[],  # Classified by size, not keywords
        max_tokens=128,
    ),
    PatternAgent(
        pattern_id="PAT_MICRO",
        pattern_type="micro",
        agent_id="micro-handler",
        system_prompt="Reponds brievement, 2-3 phrases max. Va droit au but.",
        primary_node="OL1",
        fallback_nodes=["M1"],
        strategy="single",
        priority=1,
        keywords=[],
        max_tokens=256,
    ),
    PatternAgent(
        pattern_id="PAT_SMALL",
        pattern_type="small",
        agent_id="small-handler",
        system_prompt="Reponds de facon concise et structuree. Paragraphe court.",
        primary_node="M1",
        fallback_nodes=["OL1"],
        strategy="single",
        priority=2,
        keywords=[],
        max_tokens=512,
    ),
    PatternAgent(
        pattern_id="PAT_MEDIUM",
        pattern_type="medium",
        agent_id="medium-handler",
        system_prompt="Reponds avec detail et structure. Sections si necessaire.",
        primary_node="M1",
        fallback_nodes=["gpt-oss", "OL1"],
        strategy="race",
        priority=3,
        keywords=[],
        max_tokens=1024,
    ),
    PatternAgent(
        pattern_id="PAT_LARGE",
        pattern_type="large",
        agent_id="large-handler",
        system_prompt="Reponds de facon exhaustive et structuree. Sections, listes, code si applicable. Analyse approfondie.",
        primary_node="M1",
        fallback_nodes=["gpt-oss", "devstral"],
        strategy="race",
        priority=4,
        keywords=[],
        max_tokens=2048,
    ),
    PatternAgent(
        pattern_id="PAT_XL",
        pattern_type="xl",
        agent_id="xl-handler",
        system_prompt="Reponds de facon tres detaillee. Architecture complete, code complet, analyse multi-facettes. Prends le temps necessaire.",
        primary_node="gpt-oss",
        fallback_nodes=["M1", "devstral"],
        strategy="race",
        priority=5,
        keywords=[],
        max_tokens=4096,
        temperature=0.2,
    ),
]


class PatternAgentRegistry:
    """Registry of all pattern agents with smart dispatch."""

    def __init__(self, db_path: str = "F:/BUREAU/turbo/etoile.db"):
        self.agents: dict[str, PatternAgent] = {a.pattern_type: a for a in AGENT_CONFIGS}
        self.db_path = db_path
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient()
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def classify(self, prompt: str) -> str:
        """Classify a prompt into a pattern type using keyword matching."""
        prompt_lower = prompt.lower()
        scores: dict[str, int] = {}
        for ptype, agent in self.agents.items():
            score = sum(1 for kw in agent.keywords if kw in prompt_lower)
            if score > 0:
                scores[ptype] = score
        if scores:
            return max(scores, key=scores.get)
        # Default heuristics
        if any(w in prompt_lower for w in ["def ", "class ", "import ", "```", "function"]):
            return "code"
        if len(prompt.split()) < 5:
            return "simple"
        return "analysis"  # default for unknown

    async def dispatch(self, pattern_type: str, prompt: str) -> AgentResult:
        """Dispatch to the right agent and log result."""
        agent = self.agents.get(pattern_type)
        if not agent:
            agent = self.agents.get(self.classify(prompt), self.agents["simple"])

        client = await self._get_client()
        result = await agent.execute(client, prompt)

        # Log to SQLite (async-safe via thread)
        self._log_dispatch(result, prompt)
        return result

    async def dispatch_auto(self, prompt: str) -> AgentResult:
        """Auto-classify then dispatch."""
        pattern = self.classify(prompt)
        return await self.dispatch(pattern, prompt)

    async def dispatch_multi(self, tasks: list[tuple[str, str]], max_parallel: int = 8) -> list[AgentResult]:
        """Dispatch multiple tasks in parallel. Each task is (pattern_type, prompt)."""
        sem = asyncio.Semaphore(max_parallel)

        async def _run(ptype, prompt):
            async with sem:
                return await self.dispatch(ptype, prompt)

        return await asyncio.gather(*[_run(pt, p) for pt, p in tasks])

    async def benchmark_agent(self, pattern_type: str, prompts: list[str]) -> dict:
        """Benchmark a single agent across multiple prompts."""
        results = []
        for p in prompts:
            r = await self.dispatch(pattern_type, p)
            results.append(r)

        ok = [r for r in results if r.ok]
        return {
            "pattern": pattern_type,
            "total": len(results),
            "ok": len(ok),
            "rate": len(ok) / max(1, len(results)),
            "avg_ms": sum(r.latency_ms for r in ok) / max(1, len(ok)),
            "avg_quality": sum(r.quality_score for r in ok) / max(1, len(ok)),
            "avg_tokens": sum(r.tokens for r in ok) / max(1, len(ok)),
        }

    def _log_dispatch(self, result: AgentResult, prompt: str):
        try:
            db = sqlite3.connect(self.db_path)
            db.execute(
                """INSERT INTO agent_dispatch_log
                (request_text, classified_type, agent_id, model_used, node, strategy,
                 latency_ms, tokens_in, tokens_out, success, error_msg, quality_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (prompt[:500], result.pattern, f"pat-{result.pattern}",
                 result.model, result.node, result.strategy,
                 result.latency_ms, len(prompt.split()), result.tokens,
                 1 if result.ok else 0,
                 result.error[:200] if result.error else None,
                 result.quality_score)
            )
            db.commit()
            db.close()
        except Exception as e:
            logger.warning(f"Failed to log dispatch: {e}")

    def auto_optimize_strategies(self) -> dict:
        """Analyze dispatch history and optimize strategies per pattern.

        For each pattern, compares success rates of different strategies used
        and switches to the best-performing one.
        """
        changes = {}
        try:
            db = sqlite3.connect(self.db_path)
            db.row_factory = sqlite3.Row
            # Get strategy performance per pattern
            rows = db.execute("""
                SELECT classified_type as pattern,
                       CASE
                           WHEN strategy LIKE 'race:%' THEN 'race'
                           WHEN strategy LIKE 'single%' THEN 'single'
                           WHEN strategy LIKE 'consensus%' THEN 'consensus'
                           WHEN strategy LIKE 'category%' THEN 'category'
                           ELSE strategy
                       END as strat,
                       COUNT(*) as n,
                       SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) as ok,
                       AVG(latency_ms) as avg_lat,
                       AVG(quality_score) as avg_q
                FROM agent_dispatch_log
                WHERE id > (SELECT COALESCE(MAX(id),0) - 500 FROM agent_dispatch_log)
                GROUP BY classified_type, strat
                HAVING n >= 3
                ORDER BY classified_type, ok * 1.0 / n DESC
            """).fetchall()
            db.close()

            # Group by pattern and find best strategy
            by_pattern = {}
            for r in rows:
                p = r["pattern"]
                if p not in by_pattern:
                    by_pattern[p] = []
                by_pattern[p].append({
                    "strategy": r["strat"], "n": r["n"],
                    "rate": r["ok"] / max(1, r["n"]),
                    "avg_lat": r["avg_lat"] or 0,
                    "avg_q": r["avg_q"] or 0,
                })

            for pattern, strats in by_pattern.items():
                if len(strats) < 2:
                    continue
                best = max(strats, key=lambda s: s["rate"])
                current_agent = self.agents.get(pattern)
                if not current_agent:
                    continue
                current_strat = current_agent.strategy
                # Normalize current strategy name
                norm_current = current_strat.split(":")[0] if ":" in current_strat else current_strat
                if best["strategy"] != norm_current and best["rate"] > 0.6:
                    changes[pattern] = {
                        "from": norm_current,
                        "to": best["strategy"],
                        "rate_improvement": f"{best['rate']*100:.0f}%",
                    }
                    current_agent.strategy = best["strategy"]

        except Exception as e:
            changes["error"] = str(e)

        return changes

    def list_agents(self) -> list[dict]:
        """List all registered agents."""
        return [
            {
                "pattern_id": a.pattern_id,
                "type": a.pattern_type,
                "agent": a.agent_id,
                "node": a.primary_node,
                "strategy": a.strategy,
                "priority": a.priority,
                "keywords": a.keywords[:5],
            }
            for a in sorted(self.agents.values(), key=lambda a: a.priority)
        ]


# ── CLI ─────────────────────────────────────────────────────────────────────

async def _main():
    import sys
    registry = PatternAgentRegistry()

    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
        pattern = registry.classify(prompt)
        print(f"Pattern: {pattern}")
        result = await registry.dispatch(pattern, prompt)
        print(f"Node: {result.node} | Model: {result.model} | {result.latency_ms:.0f}ms | {result.tokens} tokens | Quality: {result.quality_score}")
        print(f"\n{result.content[:500]}")
    else:
        # List all agents
        print(f"{'Pattern':<16} {'Agent':<20} {'Node':<8} {'Strategy':<12} {'Prio':<5}")
        print("-" * 65)
        for a in registry.list_agents():
            print(f"{a['type']:<16} {a['agent']:<20} {a['node']:<8} {a['strategy']:<12} {a['priority']:<5}")

    await registry.close()

if __name__ == "__main__":
    asyncio.run(_main())
