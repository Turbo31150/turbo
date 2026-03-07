"""JARVIS Commander v2 — Orchestration intelligente avec routage adaptatif.

Claude ne fait JAMAIS le travail lui-meme. Il ORDONNE, VERIFIE et ORCHESTRE.

v2 adds:
- Adaptive routing: track success rate per agent per task_type
- Progressive thermal throttling (curve, not binary)
- Task dependency graph with topological sort
- Cost estimation per task (token count × model cost)
- Re-dispatch budget tracking

Flow:
1. classify_task()  -> M1 + embedding cache + heuristic fallback
2. decompose_task() -> TaskUnit[] avec routage adaptatif
3. topological_sort -> Optimal parallel dispatch order
4. Claude dispatche  -> Via Task (subagents) + lm_query/consensus
5. verify_quality() -> ia-check valide (score 0-1)
6. record_routing()  -> Update agent performance stats
7. synthesize()     -> Reponse finale unifiee avec attribution
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import httpx


__all__ = [
    "AgentStats",
    "CommanderResult",
    "TaskUnit",
    "build_commander_enrichment",
    "build_synthesis_prompt",
    "build_verification_prompt",
    "decompose_task",
    "estimate_task_cost",
    "format_commander_header",
    "get_best_agent_for",
    "get_thermal_throttle_factor",
    "record_routing",
    "topological_sort_tasks",
]

logger = logging.getLogger("jarvis.commander")

_ROUTING_STATS_FILE = Path(__file__).resolve().parent.parent / "data" / "routing_stats.json"


# ══════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class TaskUnit:
    """Unite de travail a dispatcher."""
    id: str
    prompt: str
    task_type: str           # code, analyse, trading, systeme, web, simple
    target: str              # ia-deep, ia-fast, ia-check, ia-trading, ia-system, M1, M2, OL1, GEMINI
    priority: int = 1        # 1=haute, 3=basse
    depends_on: list[str] = field(default_factory=list)
    result: str | None = None
    status: str = "pending"  # pending, running, done, failed
    quality_score: float = 0.0
    estimated_cost: float = 0.0  # estimated token cost
    actual_duration_ms: float = 0.0


@dataclass
class CommanderResult:
    """Resultat complet d'une orchestration."""
    tasks: list[TaskUnit]
    synthesis: str
    quality_score: float
    total_time_ms: int
    agents_used: list[str]
    total_cost: float = 0.0


# ══════════════════════════════════════════════════════════════════════════
# ADAPTIVE ROUTING — Track agent performance per task type
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class AgentStats:
    """Performance stats for an agent on a specific task type."""
    successes: int = 0
    failures: int = 0
    total_duration_ms: float = 0
    total_quality: float = 0

    @property
    def success_rate(self) -> float:
        total = self.successes + self.failures
        return self.successes / max(1, total)

    @property
    def avg_quality(self) -> float:
        return self.total_quality / max(1, self.successes + self.failures)

    @property
    def avg_duration_ms(self) -> float:
        return self.total_duration_ms / max(1, self.successes + self.failures)

    def to_dict(self) -> dict:
        return {
            "successes": self.successes, "failures": self.failures,
            "total_duration_ms": round(self.total_duration_ms, 1),
            "total_quality": round(self.total_quality, 3),
        }

    @classmethod
    def from_dict(cls, d: dict) -> AgentStats:
        return cls(**{k: d.get(k, 0) for k in ("successes", "failures", "total_duration_ms", "total_quality")})


def _load_routing_stats() -> dict[str, dict[str, AgentStats]]:
    """Load routing stats: {task_type: {agent: AgentStats}}."""
    if _ROUTING_STATS_FILE.exists():
        try:
            data = json.loads(_ROUTING_STATS_FILE.read_text(encoding="utf-8"))
            return {
                ttype: {agent: AgentStats.from_dict(stats) for agent, stats in agents.items()}
                for ttype, agents in data.items()
            }
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_routing_stats(db: dict[str, dict[str, AgentStats]]):
    _ROUTING_STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {ttype: {a: s.to_dict() for a, s in agents.items()} for ttype, agents in db.items()}
    _ROUTING_STATS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def record_routing(task_type: str, agent: str, success: bool, quality: float = 0.5, duration_ms: float = 0):
    """Record the outcome of a routing decision for adaptive learning."""
    db = _load_routing_stats()
    if task_type not in db:
        db[task_type] = {}
    if agent not in db[task_type]:
        db[task_type][agent] = AgentStats()

    stats = db[task_type][agent]
    if success:
        stats.successes += 1
    else:
        stats.failures += 1
    stats.total_duration_ms += duration_ms
    stats.total_quality += quality
    _save_routing_stats(db)


def get_best_agent_for(task_type: str, candidates: list[str]) -> str:
    """Get the best agent for a task type based on historical performance."""
    db = _load_routing_stats()
    type_stats = db.get(task_type, {})

    if not type_stats:
        return candidates[0] if candidates else "M1"

    scored = []
    for agent in candidates:
        stats = type_stats.get(agent)
        if stats and (stats.successes + stats.failures) >= 3:
            # Weighted: 60% success rate + 40% quality
            score = 0.6 * stats.success_rate + 0.4 * stats.avg_quality
            scored.append((agent, score))

    if scored:
        scored.sort(key=lambda x: -x[1])
        return scored[0][0]

    return candidates[0] if candidates else "M1"


# ══════════════════════════════════════════════════════════════════════════
# PROGRESSIVE THERMAL THROTTLING
# ══════════════════════════════════════════════════════════════════════════

def get_thermal_throttle_factor(temp_c: float) -> float:
    """Progressive throttle: 0-65C=1.0, 65-75C=linear, 75-85C=steep, 85C+=0.1.

    Returns a factor [0.1, 1.0] used to reduce load on hot nodes.
    """
    if temp_c <= 65:
        return 1.0
    if temp_c <= 75:
        return 1.0 - 0.3 * ((temp_c - 65) / 10)  # 1.0 → 0.7
    if temp_c <= 85:
        return 0.7 - 0.6 * ((temp_c - 75) / 10)  # 0.7 → 0.1
    return 0.1


# ══════════════════════════════════════════════════════════════════════════
# COST ESTIMATION
# ══════════════════════════════════════════════════════════════════════════

# Approximate cost per 1K tokens (in USD for reference, actual = free for local)
MODEL_COSTS = {
    "M1": 0.0, "M2": 0.0, "M3": 0.0, "OL1": 0.0,
    "GEMINI": 0.005, "CLAUDE": 0.015,
    "ia-deep": 0.015, "ia-fast": 0.003, "ia-check": 0.008,
}


def estimate_task_cost(prompt: str, target: str, max_output_tokens: int = 1024) -> float:
    """Estimate cost based on prompt length and target model."""
    input_tokens = len(prompt.split()) * 1.3  # rough estimate
    total_tokens = input_tokens + max_output_tokens
    cost_per_k = MODEL_COSTS.get(target, 0.01)
    return (total_tokens / 1000) * cost_per_k


# ══════════════════════════════════════════════════════════════════════════
# TOPOLOGICAL SORT
# ══════════════════════════════════════════════════════════════════════════

def topological_sort_tasks(tasks: list[TaskUnit]) -> list[list[TaskUnit]]:
    """Sort tasks by dependency graph, return execution waves.

    Each wave contains tasks that can be executed in parallel.
    """
    task_map = {t.id: t for t in tasks}
    in_degree = {t.id: 0 for t in tasks}
    graph: dict[str, list[str]] = defaultdict(list)

    for t in tasks:
        for dep in t.depends_on:
            if dep in task_map:
                graph[dep].append(t.id)
                in_degree[t.id] += 1

    waves = []
    remaining = set(in_degree.keys())

    while remaining:
        # Find all tasks with no pending dependencies
        wave_ids = [tid for tid in remaining if in_degree[tid] == 0]
        if not wave_ids:
            # Cycle detected — force remaining into one wave
            wave_ids = list(remaining)

        wave = [task_map[tid] for tid in wave_ids]
        wave.sort(key=lambda t: t.priority)
        waves.append(wave)

        for tid in wave_ids:
            remaining.discard(tid)
            for successor in graph.get(tid, []):
                in_degree[successor] -= 1

    return waves


# ══════════════════════════════════════════════════════════════════════════
# CLASSIFICATION
# ══════════════════════════════════════════════════════════════════════════

CLASSIFY_PROMPT = """\
Classifie cette demande en UNE categorie:
- code: ecriture/modification de code, debug, refactoring
- analyse: investigation, architecture, logs, strategie
- trading: signaux, positions, marche crypto, scanner
- systeme: fichiers, apps, Windows, processus, PowerShell, cluster, GPU, boot, diagnostic, statut systeme, noeuds, services, alertes, taches autonomes, JARVIS
- web: recherche internet, infos actuelles, documentation
- simple: question directe, reponse courte, calcul, traduction

Reponds UNIQUEMENT avec le mot-cle (un seul mot)."""

VALID_TYPES = {"code", "analyse", "trading", "systeme", "web", "simple"}


async def classify_task(prompt: str) -> str:
    """Classifie via M1 qwen3-8b (fast, 0.6-1.7s).

    Reutilise _local_ia_analyze de orchestrator.py mais avec CLASSIFY_PROMPT.
    Fallback: heuristiques par mots-cles.
    """
    from src.config import config, prepare_lmstudio_input, build_lmstudio_payload
    from src.tools import _get_client

    node = config.get_node("M1")
    if node:
        try:
            client = await _get_client()
            r = await client.post(f"{node.url}/api/v1/chat", json=build_lmstudio_payload(
                node.default_model,
                prepare_lmstudio_input(prompt, node.name, node.default_model),
                temperature=0.1, max_output_tokens=32,
                system_prompt=CLASSIFY_PROMPT,
            ), timeout=config.fast_timeout)
            r.raise_for_status()
            from src.tools import extract_lms_output
            content = extract_lms_output(r.json()).strip().lower()
            # Find first valid type anywhere in the response
            # (M1 may wrap answer in markdown or add explanatory text)
            for token in content.split():
                cleaned = token.strip("*_.,;:!?`\"'()[]")
                if cleaned in VALID_TYPES:
                    return cleaned
        except (httpx.HTTPError, OSError, KeyError, ValueError, asyncio.TimeoutError) as exc:
            logger.debug("classify_task M1 failed: %s", exc)

    # Fallback: heuristiques par mots-cles
    return _classify_heuristic(prompt)


def _has_word(text: str, word: str) -> bool:
    """Check if word exists as standalone word (not substring) in text.

    'sol' matches 'sol' but NOT 'solana' or 'console'.
    """
    import re
    return bool(re.search(r'\b' + re.escape(word) + r'\b', text))


def _classify_heuristic(prompt: str) -> str:
    """Classification par mots-cles quand M1 est indisponible.

    Priorite: code-override > web-override > trading > systeme > analyse > code > web > simple.
    Utilise _has_word() pour les mots courts (evite 'sol' dans 'solana').
    """
    p = prompt.lower()

    # Priority overrides: contextes forts qui dominent tout
    # "debug/bug/segfault + trading" = code, pas trading
    code_strong = ("debug", "segfault", "bug ", "fix ", "patch ", "refactor")
    if any(kw in p for kw in code_strong):
        return "code"

    # "actualite/news/cherche + crypto" = web, pas trading
    web_strong = ("actualite", "news ", "dernieres nouvelles", "info sur")
    if any(kw in p for kw in web_strong):
        return "web"

    # 1. Trading — mots specifiques, word-boundary pour mots courts
    trading_exact = ("trading", "trade", "signal", "mexc", "breakout", "sniper",
                     "scalping", "scalp", "futures", "usdt", "binance",
                     "take profit", "stop loss")
    trading_words = ("btc", "eth", "sol", "crypto", "paire", "levier", "short")
    if any(kw in p for kw in trading_exact) or any(_has_word(p, w) for w in trading_words):
        return "trading"

    # 2. Systeme — commandes d'action + JARVIS cluster/boot/GPU
    system_exact = ("ouvre", "ouvrir", "ferme", "fermer", "fichier", "dossier",
                    "processus", "powershell", "registre", "volume",
                    "ecran", "fenetre", "lance ", "lancer",
                    "installer", "desinstaller", "windows",
                    "reduis", "monte le", "baisse le", "redemarre", "eteins",
                    "capture", "screenshot", "bureau",
                    "cluster", "noeud", "noeuds", "node ", "nodes",
                    "boot", "demarrage", "autonome", "tache autonome",
                    "gpu", "vram", "temperature gpu", "alerte", "alertes",
                    "orchestrateur", "orchestrator", "statut", "status",
                    "sante ", "health", "jarvis")
    system_words = ("app", "systeme", "service")
    if any(kw in p for kw in system_exact) or any(_has_word(p, w) for w in system_words):
        return "systeme"

    # 3. Analyse — investigation, strategie, logs
    analyse_kw = ("analyse", "analyser", "architecture", "strategie",
                  "investigation", "optimise", "optimiser", "performance",
                  "log ", "logs", "diagnostic", "planifi", "compare",
                  "evalue", "evaluer", "benchmark", "profil", "audit")
    if any(kw in p for kw in analyse_kw):
        return "analyse"

    # 4. Code — creation/modification de code
    code_kw = ("code", "coder", "fonction", "function", "class ", "erreur",
               "error", "refactor", "script", "python", "import ",
               "variable", "modifier le code", "ecrire", "editer",
               "compiler", "cree un", "creer", "serveur", "api ", "fastapi",
               "endpoint", "module", "package", "library", "pip ", "npm",
               "typescript", "javascript", "rust ", "java ", "sql ", "html",
               "css ", "react", "django", "flask", "jwt", "auth",
               "developpe", "developper", "implementer", "implemente")
    if any(kw in p for kw in code_kw):
        return "code"

    # 5. Web — recherche internet
    web_kw = ("cherche", "recherche", "google", "web ", "internet", "site ",
              "documentation", "url", "lien", "wikipedia")
    if any(kw in p for kw in web_kw):
        return "web"

    return "simple"


# ══════════════════════════════════════════════════════════════════════════
# DECOMPOSITION
# ══════════════════════════════════════════════════════════════════════════

def _apply_thermal_rerouting(target: str, thermal_status: dict) -> str:
    """Re-route with progressive thermal throttling.

    Uses get_thermal_throttle_factor() for smooth degradation:
    - factor > 0.7: no rerouting (normal operation)
    - factor 0.3-0.7: reroute heavy tasks (code) to backup
    - factor < 0.3: reroute everything to fallback
    """
    max_temp = thermal_status.get("max_temp", 0)
    factor = get_thermal_throttle_factor(max_temp)

    if factor > 0.7:
        return target  # Normal

    # Check circuit breaker availability for fallback
    from src.circuit_breaker import cluster_breakers

    if factor <= 0.3:
        # Severe: cascade fallback
        fallback_map = {"M1": "M2", "M2": "M3", "M3": "OL1"}
        fallback = fallback_map.get(target, target)
        if cluster_breakers.can_execute(fallback):
            logger.info("Thermal reroute %s → %s (factor=%.2f, temp=%dC)", target, fallback, factor, max_temp)
            return fallback
    elif factor <= 0.7 and target in ("M1", "M2"):
        # Moderate: reroute heavy tasks, keep simple ones
        if cluster_breakers.can_execute("M2") and target == "M1":
            return "M2"

    return target


def decompose_task(prompt: str, classification: str) -> list[TaskUnit]:
    """Decompose en sous-taches avec routage adaptatif v2.

    Uses adaptive routing (historical performance), progressive thermal
    throttling, cost estimation, and topological ordering.
    """
    from src.config import config
    from src.cluster_startup import check_thermal_status

    thermal = check_thermal_status()

    routing = config.commander_routing.get(classification, [])
    if not routing:
        target = _apply_thermal_rerouting("M1", thermal)
        # Use adaptive routing if available
        best = get_best_agent_for(classification, ["M1", "M2", "OL1"])
        target = _apply_thermal_rerouting(best, thermal)
        cost = estimate_task_cost(prompt, target)
        return [TaskUnit(
            id="t1", prompt=prompt, task_type=classification,
            target=target, priority=1, estimated_cost=cost,
        )]

    tasks: list[TaskUnit] = []
    for i, route in enumerate(routing):
        agent = route["agent"]
        ia = route["ia"]
        role = route["role"]
        target = agent or ia or "M1"

        # Adaptive routing: prefer best performer for this task type
        if not agent and ia:
            candidates = [ia] + [n for n in ["M1", "M2", "OL1", "M3"] if n != ia]
            target = get_best_agent_for(classification, candidates)
            target = _apply_thermal_rerouting(target, thermal)

        task_prompt = _build_task_prompt(prompt, role, classification)

        # Thermal warning in prompt
        max_temp = thermal.get("max_temp", 0)
        factor = get_thermal_throttle_factor(max_temp)
        if factor < 0.5:
            task_prompt = f"[ALERTE THERMIQUE: GPU {max_temp}C, throttle={factor:.0%}] {task_prompt}"

        cost = estimate_task_cost(task_prompt, target)

        task = TaskUnit(
            id=f"t{i+1}",
            prompt=task_prompt,
            task_type=classification,
            target=target,
            priority=1 if role in ("coder", "executor", "scanner", "analyzer") else 2,
            estimated_cost=cost,
        )

        if role in ("reviewer", "validator", "synthesizer"):
            main_ids = [t.id for t in tasks if t.priority == 1]
            task.depends_on = main_ids
            task.priority = 2

        tasks.append(task)

    return tasks


def _build_task_prompt(prompt: str, role: str, classification: str) -> str:
    """Construit le prompt adapte au role de l'agent."""
    role_prefixes = {
        "coder": f"Ecris le code pour: {prompt}\nProduis du code fonctionnel et complet.",
        "reviewer": f"Review et valide ce travail: {prompt}\nDonne un score de qualite 0-1 et liste les problemes.",
        "analyzer": f"Analyse en profondeur: {prompt}\nStructure ton analyse avec sections claires.",
        "scanner": f"Scanne et collecte les donnees pour: {prompt}\nDonne des chiffres precis.",
        "web_data": f"Recherche web pour: {prompt}\nDonnees actuelles avec sources.",
        "validator": f"Valide et verifie: {prompt}\nScore de confiance 0-1.",
        "executor": f"Execute cette action systeme: {prompt}\nRapporte le resultat.",
        "searcher": f"Recherche web: {prompt}\nResultats structures avec sources.",
        "synthesizer": f"Synthetise les informations sur: {prompt}\nResume concis avec les points cles.",
        "responder": f"{prompt}",
    }
    return role_prefixes.get(role, prompt)


# ══════════════════════════════════════════════════════════════════════════
# QUALITY VERIFICATION
# ══════════════════════════════════════════════════════════════════════════

MAX_REDISPATCH_CYCLES = 2


def build_verification_prompt(tasks: list[TaskUnit]) -> str:
    """Construit le prompt de verification pour ia-check."""
    results_text = "\n\n".join(
        f"[{t.target}] ({t.task_type}/{t.id}):\n{t.result or 'PAS DE RESULTAT'}"
        for t in tasks if t.status == "done"
    )
    return (
        f"VERIFICATION QUALITE — Analyse ces resultats d'agents:\n\n"
        f"{results_text}\n\n"
        f"Pour chaque resultat, donne:\n"
        f"1. Score qualite (0.0 a 1.0)\n"
        f"2. Problemes identifies\n"
        f"3. Score global\n"
        f"Reponds en JSON: {{\"scores\": {{\"t1\": 0.8, ...}}, \"global\": 0.85, \"issues\": [...]}}"
    )


# ══════════════════════════════════════════════════════════════════════════
# SYNTHESIS
# ══════════════════════════════════════════════════════════════════════════

def build_synthesis_prompt(tasks: list[TaskUnit], quality_score: float) -> str:
    """Construit le prompt de synthese finale."""
    results_parts = []
    agents_used = set()
    for t in tasks:
        if t.status == "done" and t.result:
            results_parts.append(f"[{t.target}] {t.result}")
            agents_used.add(t.target)

    results_text = "\n\n---\n\n".join(results_parts)
    return (
        f"SYNTHESE COMMANDANT — Combine ces resultats en une reponse unifiee:\n\n"
        f"{results_text}\n\n"
        f"Score qualite global: {quality_score:.2f}\n"
        f"Agents utilises: {', '.join(sorted(agents_used))}\n\n"
        f"Produis une reponse concise avec attribution [AGENT/modele] pour chaque contribution."
    )


def format_commander_header(classification: str, tasks: list[TaskUnit]) -> str:
    """Header d'affichage pour le mode commandant v2."""
    from src.cluster_startup import check_thermal_status

    targets = [t.target for t in tasks]
    thermal = check_thermal_status()

    # Progressive thermal display
    max_temp = thermal.get("max_temp", 0)
    factor = get_thermal_throttle_factor(max_temp)
    thermal_tag = ""
    if factor < 0.3:
        thermal_tag = f" | THERMAL CRITICAL {max_temp}C ({factor:.0%})"
    elif factor < 0.7:
        thermal_tag = f" | THERMAL WARN {max_temp}C ({factor:.0%})"

    # Execution waves
    waves = topological_sort_tasks(tasks)
    wave_info = f" | {len(waves)} waves" if len(waves) > 1 else ""

    # Cost estimate
    total_cost = sum(t.estimated_cost for t in tasks)
    cost_tag = f" | ~${total_cost:.4f}" if total_cost > 0 else ""

    return (
        f"[COMMANDANT v2] Type={classification} | "
        f"{len(tasks)} sous-taches{wave_info}{cost_tag} | "
        f"Dispatch: {', '.join(targets)}{thermal_tag}"
    )


# ══════════════════════════════════════════════════════════════════════════
# COMMANDER PROMPT BUILDER
# ══════════════════════════════════════════════════════════════════════════

def build_commander_enrichment(
    user_prompt: str,
    classification: str,
    tasks: list[TaskUnit],
    pre_analysis: str | None = None,
) -> str:
    """Construit le prompt enrichi pour Claude en mode commandant.

    Claude recoit ce prompt et DOIT dispatcher aux agents/IAs.
    """
    task_list = "\n".join(
        f"  {t.id}. [{t.target}] ({t.task_type}) prio={t.priority} "
        f"{'DEPENDS:'+','.join(t.depends_on) if t.depends_on else ''}\n"
        f"     -> {t.prompt[:200]}"
        for t in tasks
    )

    parts = [
        f"MODE COMMANDANT. Classification: {classification}",
        f"Demande utilisateur: \"{user_prompt}\"",
    ]
    if pre_analysis:
        parts.append(f"Pre-analyse M1: {pre_analysis}")

    parts.append(f"\nPLAN DE DISPATCH ({len(tasks)} taches):\n{task_list}")
    parts.append(
        "\nORDRES:\n"
        "1. Dispatche CHAQUE tache ci-dessus a l'agent/IA indique\n"
        "2. Lance les taches sans dependances EN PARALLELE\n"
        "3. Collecte les resultats\n"
        "4. Dispatche ia-check pour valider (score 0-1)\n"
        "5. Si score < 0.7 → re-dispatche les taches faibles (max 2 cycles)\n"
        "6. Synthetise avec attribution [AGENT/modele]\n"
        "\nNe traite RIEN toi-meme. Delegue TOUT."
    )

    return "\n\n".join(parts)
