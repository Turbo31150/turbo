"""JARVIS Commander Mode — Claude = Pure Orchestrateur.

Claude ne fait JAMAIS le travail lui-meme. Il ORDONNE, VERIFIE et ORCHESTRE.
Ce module fournit les structures de donnees et fonctions utilitaires
pour le mode commandant.

Flow:
1. classify_task()  -> M1 classifie le type (code/analyse/trading/systeme/web/simple)
2. decompose_task() -> Decompose en TaskUnit[] avec routage automatique
3. Claude dispatche  -> Via Task (subagents) + lm_query/consensus (IAs directes)
4. verify_quality() -> ia-check valide (score 0-1)
5. synthesize()     -> Reponse finale unifiee avec attribution
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field


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


@dataclass
class CommanderResult:
    """Resultat complet d'une orchestration."""
    tasks: list[TaskUnit]
    synthesis: str
    quality_score: float
    total_time_ms: int
    agents_used: list[str]


# ══════════════════════════════════════════════════════════════════════════
# CLASSIFICATION
# ══════════════════════════════════════════════════════════════════════════

CLASSIFY_PROMPT = """\
Classifie cette demande en UNE categorie:
- code: ecriture/modification de code, debug, refactoring
- analyse: investigation, architecture, logs, strategie
- trading: signaux, positions, marche crypto, scanner
- systeme: fichiers, apps, Windows, processus, PowerShell
- web: recherche internet, infos actuelles, documentation
- simple: question directe, reponse courte, calcul, traduction

Reponds UNIQUEMENT avec le mot-cle (un seul mot)."""

VALID_TYPES = {"code", "analyse", "trading", "systeme", "web", "simple"}


async def classify_task(prompt: str) -> str:
    """Classifie via M1 qwen3-30b (mode fast, <1s).

    Reutilise _local_ia_analyze de orchestrator.py mais avec CLASSIFY_PROMPT.
    Fallback: heuristiques par mots-cles.
    """
    from src.config import config
    from src.tools import _get_client

    node = config.get_node("M1")
    if node:
        try:
            client = await _get_client()
            r = await client.post(f"{node.url}/api/v1/chat", json={
                "model": node.default_model,
                "input": prompt,
                "system_prompt": CLASSIFY_PROMPT,
                "temperature": 0.1,
                "max_output_tokens": 32,
                "stream": False,
                "store": False,
            }, timeout=config.fast_timeout)
            r.raise_for_status()
            from src.tools import extract_lms_output
            content = extract_lms_output(r.json()).strip().lower()
            # Strip thinking tags if present
            if content.startswith("<think>"):
                think_end = content.find("</think>")
                if think_end != -1:
                    content = content[think_end + 8:].strip()
            # Extract first word only
            word = content.split()[0].rstrip(".,;:!?") if content else ""
            if word in VALID_TYPES:
                return word
        except Exception:
            pass

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

    # 2. Systeme — commandes d'action, word-boundary pour mots ambigus
    system_exact = ("ouvre", "ouvrir", "ferme", "fermer", "fichier", "dossier",
                    "processus", "powershell", "registre", "volume",
                    "ecran", "fenetre", "lance ", "lancer",
                    "installer", "desinstaller", "windows",
                    "reduis", "monte le", "baisse le", "redemarre", "eteins",
                    "capture", "screenshot", "bureau")
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
    """Re-route une cible si M1 est en surchauffe thermique.

    - critical: M1 -> M2 (code) ou OL1 (web/simple) ou GEMINI (analyse)
    - warning: M1 reste, mais les taches code vont sur M2
    """
    if thermal_status.get("status") == "critical" and target == "M1":
        return "M2"  # Deporter vers M2
    if thermal_status.get("status") == "critical" and target == "ia-deep":
        return "ia-deep"  # Agent reste, mais il utilisera M2 via lm_query
    return target


def decompose_task(prompt: str, classification: str) -> list[TaskUnit]:
    """Decompose en sous-taches avec routage automatique.

    Utilise la matrice commander_routing de config.py pour determiner
    les agents et IAs a assigner. Applique le re-routage thermique si GPU surchauffe.
    """
    from src.config import config
    from src.cluster_startup import check_thermal_status

    # Check thermique GPU
    thermal = check_thermal_status()

    routing = config.commander_routing.get(classification, [])
    if not routing:
        # Fallback: simple task sur M1
        target = _apply_thermal_rerouting("M1", thermal)
        return [TaskUnit(
            id="t1", prompt=prompt, task_type=classification,
            target=target, priority=1,
        )]

    tasks: list[TaskUnit] = []
    for i, route in enumerate(routing):
        agent = route["agent"]
        ia = route["ia"]
        role = route["role"]
        target = agent or ia or "M1"

        # Re-routage thermique sur les IAs directes (pas les agents SDK)
        if not agent and ia:
            target = _apply_thermal_rerouting(ia, thermal)

        # Adapter le prompt selon le role
        task_prompt = _build_task_prompt(prompt, role, classification)

        # En surchauffe critique, ajouter un avertissement au prompt
        if thermal.get("status") == "critical":
            task_prompt = (
                f"[ALERTE THERMIQUE: GPU {thermal['max_temp']}C] "
                f"{task_prompt}"
            )

        task = TaskUnit(
            id=f"t{i+1}",
            prompt=task_prompt,
            task_type=classification,
            target=target,
            priority=1 if role in ("coder", "executor", "scanner", "analyzer") else 2,
        )

        # Les reviewers/validators dependent des taches principales
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
    """Header d'affichage pour le mode commandant."""
    from src.cluster_startup import check_thermal_status

    targets = [t.target for t in tasks]
    thermal = check_thermal_status()
    thermal_tag = ""
    if thermal["status"] == "critical":
        thermal_tag = f" | THERMAL CRITICAL {thermal['max_temp']}C"
    elif thermal["status"] == "warning":
        thermal_tag = f" | THERMAL WARN {thermal['max_temp']}C"

    return (
        f"[COMMANDANT] Type={classification} | "
        f"{len(tasks)} sous-taches | "
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
