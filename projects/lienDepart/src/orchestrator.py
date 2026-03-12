"""lienDepart — Orchestrateur multi-patterns: pipeline, domino, vectoriel, matriciel."""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)

from src.agents import AGENTS, AGENT_TIERS
from src.health import AgentHealthRegistry
from src.resilience import resilient_call, DeadLetterQueue

VERSION = "1.1.0"

SYSTEM_PROMPT = f"""\
Tu es lienDepart v{VERSION}, hyper-orchestrateur multi-agents distribue.
Reponds TOUJOURS en francais. Sois concis et efficace.

## Architecture: 14 Agents en 4 Tiers

### Tier 1 — Noyau (toujours actifs)
- `architect` (Opus) — Decompose les problemes, choisit le pattern d'orchestration
- `executor` (Haiku) — Execute les actions rapidement, zero analyse
- `validator` (Sonnet) — Valide tout output avec score 0.0-1.0

### Tier 2 — Specialistes (a la demande)
- `coder` (Sonnet) — Code Python/TS/PowerShell/SQL
- `researcher` (Sonnet) — Recherche web, synthese, verification croisee
- `data-analyst` (Sonnet) — SQL, CSV, statistiques, tendances
- `trader` (Sonnet) — Trading MEXC Futures, signaux, analyse technique
- `sysadmin` (Haiku) — Admin Windows, GPU, reseau, PowerShell

### Tier 3 — Meta-orchestration (patterns avances)
- `pipeline-mgr` (Sonnet) — Chaines sequentielles A→B→C avec contexte
- `vector-mgr` (Sonnet) — Parallelisme N agents meme tache, fusion
- `domino-mgr` (Sonnet) — Cascades conditionnelles, arbre d'events
- `matrix-mgr` (Opus) — Croisement NxM agents x inputs, validation exhaustive

### Tier 4 — Autonomes
- `sentinel` (Haiku) — Monitoring GPU/disque/latence, alertes
- `learner` (Haiku) — Detection patterns, optimisation, auto-skills

## 4 Patterns d'Orchestration

### PIPELINE (sequentiel)
Quand: etapes dependantes, chaque sortie alimente la suivante
```
architect → coder → validator
```
Dispatch: Task(agent="pipeline-mgr", prompt="plan: [etape1, etape2, etape3]")

### VECTORIEL (parallele)
Quand: meme tache, plusieurs perspectives, fusion des resultats
```
      ┌→ coder ────┐
task ─┤→ researcher ├→ fusion
      └→ analyst ──┘
```
Dispatch: 3x Task en parallele dans le MEME message

### DOMINO (cascade)
Quand: un resultat declenche des actions conditionnelles
```
sentinel → [alerte GPU → sysadmin]
         → [alerte trading → trader]
         → [alerte disque → executor]
```
Dispatch: Task(agent="domino-mgr", prompt="arbre de cascade")

### MATRICIEL (croisement exhaustif)
Quand: validation multi-criteres, decision complexe
```
           | coder | researcher | analyst |
input_1    |  r11  |    r12     |   r13   |
input_2    |  r21  |    r22     |   r23   |
input_3    |  r31  |    r32     |   r33   |
```
Dispatch: Task(agent="matrix-mgr", prompt="agents + inputs")

## Protocole d'Execution

1. TOUTE requete complexe → Task(agent="architect") d'abord
2. Architect renvoie un plan avec le pattern optimal
3. Executer le plan selon le pattern choisi
4. TOUJOURS finir par Task(agent="validator") pour scorer le resultat
5. Si score < 0.6 → retry avec un plan alternatif

## Regles de Performance
- Max 4 Task paralleles par message (limite SDK)
- Haiku pour les taches simples (vitesse)
- Sonnet pour les taches moyennes (equilibre)
- Opus UNIQUEMENT pour architect et matrix-mgr (precision critique)
- Chaque agent produit un output structure (JSON prefere)
"""


def _safe_print(text: str, **kwargs):
    try:
        print(text, **kwargs)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "utf-8"
        print(text.encode(enc, errors="replace").decode(enc, errors="replace"), **kwargs)


def build_options(cwd: str | None = None) -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        permission_mode="acceptEdits",
        allowed_tools=[
            "Read", "Write", "Edit", "Bash", "Glob", "Grep",
            "WebSearch", "WebFetch", "Task",
        ],
        agents=AGENTS,
        cwd=cwd or "F:/BUREAU/lienDepart",
    )


async def run_once(prompt: str, cwd: str | None = None) -> str | None:
    options = build_options(cwd)
    from claude_agent_sdk import query

    collected: list[str] = []
    result_text: str | None = None
    try:
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        collected.append(block.text)
                        _safe_print(block.text, end="", flush=True)
                    elif isinstance(block, ToolUseBlock):
                        _safe_print(f"\n  [TOOL] {block.name}", flush=True)
            if isinstance(message, ResultMessage):
                result_text = message.result
                _safe_print(
                    f"\n  [lienDepart] Cost: ${message.total_cost_usd or 0:.4f} | "
                    f"Turns: {message.num_turns} | Duration: {message.duration_ms}ms"
                )
    except (ExceptionGroup, BaseExceptionGroup) as eg:
        for exc in eg.exceptions:
            if "cancel scope" in str(exc).lower() or "ProcessTransport" in str(exc):
                pass
            else:
                raise
    except RuntimeError as e:
        if "cancel scope" not in str(e).lower():
            raise

    if result_text is None and collected:
        result_text = "".join(collected)
    return result_text


async def run_interactive(cwd: str | None = None) -> None:
    options = build_options(cwd)

    _safe_print(f"=== lienDepart v{VERSION} | 14 Agents | 4 Patterns ===")
    _safe_print("Patterns: pipeline | vectoriel | domino | matriciel")
    _safe_print("Commands: 'exit' to quit, 'agents' to list, 'status' for health, 'health' for agent health, 'dlq' for dead letters\n")

    async with ClaudeSDKClient(options=options) as client:
        while True:
            try:
                user_input = input("\n[lienDepart] > ")
            except (EOFError, KeyboardInterrupt):
                break

            stripped = user_input.strip()
            if not stripped:
                continue
            if stripped.lower() == "exit":
                break
            if stripped.lower() == "agents":
                for name, agent in AGENTS.items():
                    tier = (
                        "T1-NOYAU" if name in ("architect", "executor", "validator")
                        else "T2-SPEC" if name in ("coder", "researcher", "data-analyst", "trader", "sysadmin")
                        else "T3-META" if name.endswith("-mgr")
                        else "T4-AUTO"
                    )
                    _safe_print(f"  [{tier}] {name:15s} ({agent.model}) — {agent.description[:60]}")
                continue
            if stripped.lower() == "status":
                user_input = (
                    "Lance l'agent sentinel pour faire un health check complet du systeme: "
                    "GPU, disque, processus, latence API. Rapport structure."
                )
            if stripped.lower() == "health":
                registry = AgentHealthRegistry.instance()
                table = await registry.format_health_table()
                _safe_print(table)
                continue
            if stripped.lower() == "dlq":
                dlq = DeadLetterQueue()
                items = await dlq.list_all()
                if not items:
                    _safe_print("  [DLQ] Aucune tache en echec.")
                else:
                    for i, item in enumerate(items):
                        _safe_print(f"  [{i}] {item.get('agent', '?')} — {item.get('error', '?')[:80]}")
                continue

            await client.query(user_input)
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            _safe_print(block.text, end="", flush=True)
                        elif isinstance(block, ToolUseBlock):
                            _safe_print(f"\n  [TOOL] {block.name}", flush=True)
                if isinstance(message, ResultMessage):
                    if message.total_cost_usd:
                        _safe_print(f"\n  [$] {message.total_cost_usd:.4f} USD", flush=True)

    _safe_print("\n[lienDepart] Session terminee.")
