"""JARVIS Orchestrator - Core engine using ClaudeSDKClient."""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    HookMatcher,
    HookContext,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)

from src.config import config, JARVIS_VERSION
from src.agents import JARVIS_AGENTS
from src.output import JARVIS_OUTPUT_SCHEMA


SYSTEM_PROMPT = f"""\
Tu es JARVIS v{JARVIS_VERSION}, orchestrateur IA distribue sur un cluster de 3 machines.
Reponds TOUJOURS en francais. Sois concis — tes sorties alimentent un pipeline vocal.

## Architecture
- Moteur: CLAUDE (Agent SDK) + LM Studio local (DUAL_CORE)
- Cluster: 16 GPU, 105 GB VRAM total
  - M1 (192.168.1.85) — 6 GPU, 36 GB VRAM — analyse profonde (qwen3-30b)
  - M2 (192.168.1.26) — 3 GPU, 24 GB VRAM — inference rapide (nemotron-3-nano)
  - M3 (192.168.1.113) — 2 GPU, 16 GB VRAM — validation (mistral-7b)

## Tools MCP Jarvis (69 outils — prefixe mcp__jarvis__)

### IA & Cluster (4)
lm_query, lm_models, lm_cluster_status, consensus

### Scripts & Projets (3)
run_script, list_scripts, list_project_paths

### Applications (3)
open_app, close_app, open_url

### Processus (2)
list_processes, kill_process

### Fenetres Windows (4)
list_windows, focus_window, minimize_window, maximize_window

### Clavier & Souris (4)
send_keys, type_text, press_hotkey, mouse_click

### Presse-papier (2)
clipboard_get, clipboard_set

### Fichiers & Dossiers (9)
open_folder, list_folder, create_folder, copy_item, move_item,
delete_item, read_text_file, write_text_file, search_files

### Audio (3)
volume_up, volume_down, volume_mute

### Ecran (2)
screenshot, screen_resolution

### Systeme (8)
system_info, gpu_info, network_info, powershell_run,
lock_screen, shutdown_pc, restart_pc, sleep_pc

### Services (3)
list_services, start_service, stop_service

### Reseau (3)
wifi_networks, ping, get_ip

### Registre (2)
registry_read, registry_write

### Notifications & Voix (3)
notify, speak, scheduled_tasks

### Trading Execution (5)
trading_pending_signals — Signaux en attente (score >= seuil, frais)
trading_execute_signal — Executer un signal (dry_run=true par defaut, JAMAIS live sans confirmation)
trading_positions — Positions ouvertes MEXC Futures
trading_status — Status global pipeline (signaux, trades, PnL)
trading_close_position — Fermer une position ouverte

### Skills & Pipelines (5)
list_skills, create_skill, remove_skill, suggest_actions, action_history

### Brain — Apprentissage Autonome (4)
brain_status — Etat du cerveau (patterns, skills appris)
brain_analyze — Analyser les patterns d'utilisation et suggerer des skills
brain_suggest — Demander au cluster IA de creer un nouveau skill
brain_learn — Auto-apprendre: detecter et creer des skills automatiquement

## Subagents (via Task)
- `ia-deep` (Opus) — Analyse approfondie, architecture, strategie
- `ia-fast` (Haiku) — Code, execution rapide, commandes
- `ia-check` (Sonnet) — Validation, tests, score de qualite
- `ia-trading` (Sonnet) — Trading MEXC Futures, scanners, breakout
- `ia-system` (Haiku) — Operations systeme Windows, PowerShell, fichiers

## Trading Config
- Exchange: MEXC Futures | Levier: {config.leverage}x
- Paires: {', '.join(p.split('/')[0] for p in config.pairs)}
- TP: {config.tp_percent}% | SL: {config.sl_percent}%

## Projets indexes
- carV1: scanners, strategies, orchestrateurs, GPU pipeline
- trading_v2: MCP v3.5 (70+ tools), scripts trading, voice system
- prod_intensive: pipeline autonome intensif
- turbo: ce projet (Agent SDK)

## Protocole
1. Decomposer les requetes complexes en micro-taches → dispatcher aux subagents
2. Pour les decisions critiques: consensus (min 2 sources: subagents + LM Studio)
3. Structurer la sortie en JSON JARVIS quand demande
4. Mode Voice-First: phrases courtes, pas de markdown, reponses directes
5. Ecrire sur le systeme de fichiers via les tools Read/Write/Edit/Bash
6. Reporter le consensus_score dans chaque output structurée
7. IMPORTANT: Max 4 outils MCP jarvis en parallele (limite transport stdio). Si >4 outils, batch par groupes de 3-4.

## Routage IA
- Reponse courte → M3, M2
- Analyse profonde → M1
- Signal trading → M2, M1
- Code → M2
- Validation → M3
- Critique/Consensus → M1, M2, M3
"""


def _safe_print(text: str, **kwargs):
    """Print text safely on Windows cp1252 consoles."""
    try:
        print(text, **kwargs)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "utf-8"
        print(text.encode(enc, errors="replace").decode(enc, errors="replace"), **kwargs)


async def log_tool_use(
    input_data: dict[str, Any],
    tool_use_id: str | None,
    context: HookContext,
) -> dict[str, Any]:
    """Log tool usage for audit trail."""
    tool_name = input_data.get("tool_name", "unknown")
    _safe_print(f"  [HOOK] Tool: {tool_name}")
    return {}


def _jarvis_mcp_config() -> dict:
    """Build MCP stdio server config for JARVIS tools."""
    import sys
    from pathlib import Path
    server_script = str(Path(__file__).resolve().parent / "mcp_server.py")
    return {
        "type": "stdio",
        "command": sys.executable,
        "args": [server_script],
        "env": {},
    }


def build_options(cwd: str | None = None) -> ClaudeAgentOptions:
    """Build ClaudeAgentOptions for the JARVIS orchestrator."""
    return ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        permission_mode="acceptEdits",
        allowed_tools=[
            # Claude Code tools
            "Read", "Write", "Edit", "Bash", "Glob", "Grep",
            "WebSearch", "WebFetch", "Task",
            # JARVIS MCP — all 69 tools authorized
            "mcp__jarvis__*",
        ],
        mcp_servers={"jarvis": _jarvis_mcp_config()},
        agents=JARVIS_AGENTS,
        cwd=cwd,
    )


async def run_once(prompt: str, cwd: str | None = None) -> str | None:
    """Single-shot query: send prompt, collect full result."""
    options = build_options(cwd or "F:/BUREAU/turbo")

    from claude_agent_sdk import query

    result_text: str | None = None
    collected: list[str] = []
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
                _safe_print(f"\n  [JARVIS] Cost: ${message.total_cost_usd or 0:.4f} | "
                            f"Turns: {message.num_turns} | "
                            f"Duration: {message.duration_ms}ms")
    except (ExceptionGroup, BaseExceptionGroup) as eg:
        # SDK transport cleanup errors — non-fatal
        for exc in eg.exceptions:
            if "cancel scope" in str(exc).lower() or "ProcessTransport" in str(exc):
                pass  # Ignore transport/scope close errors
            else:
                raise
    except RuntimeError as e:
        if "cancel scope" in str(e).lower():
            pass  # Ignore anyio cancel scope cleanup error
        else:
            raise

    if result_text is None and collected:
        result_text = "".join(collected)
    return result_text


async def run_interactive(cwd: str | None = None) -> None:
    """Interactive REPL mode with continuous conversation."""
    options = build_options(cwd)

    print(f"=== JARVIS v{JARVIS_VERSION} | DUAL_CORE | Interactive ===")
    print("Commands: 'exit' to quit, 'status' for cluster check\n")

    async with ClaudeSDKClient(options=options) as client:
        while True:
            try:
                user_input = input("\n[JARVIS] > ")
            except (EOFError, KeyboardInterrupt):
                break

            if not user_input.strip():
                continue
            if user_input.strip().lower() == "exit":
                break
            if user_input.strip().lower() == "status":
                user_input = "Use the lm_cluster_status tool and report the results."

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

    _safe_print("\n[JARVIS] Session terminee.")


async def run_voice(cwd: str | None = None) -> None:
    """Voice-First mode with pre-registered commands and IA fallback.

    Flow:
    1. Listen to voice input (Whisper STT)
    2. Correct transcription errors (local dict + IA correction)
    3. Match against pre-registered commands (fuzzy matching)
    4. If match found → execute directly (fast path)
    5. If no match → send to Claude orchestrator (IA path)
    6. Speak the response (Windows SAPI TTS)
    """
    from src.voice import listen_voice, speak_text
    from src.commands import correct_voice_text, match_command, format_commands_help
    from src.executor import execute_command, execute_skill, process_voice_input, correct_with_ia
    from src.voice_correction import full_correction_pipeline, VoiceSession, format_suggestions
    from src.skills import find_skill, load_skills, format_skills_list, suggest_next_actions, log_action

    options = build_options(cwd)
    session = VoiceSession()
    pending_confirm: tuple | None = None

    # Load skills on startup
    skills = load_skills()
    print(f"=== JARVIS v{JARVIS_VERSION} | MODE VOCAL ===")
    print(f"57 outils MCP | {len(skills)} skills | Correction vocale IA")
    await speak_text(f"JARVIS actif. {len(skills)} skills charges. Que veux-tu faire?")

    async with ClaudeSDKClient(options=options) as client:
        while True:
            print("\n[JARVIS] Ecoute...", flush=True)
            raw_text = await listen_voice(timeout=15.0)

            if not raw_text:
                continue

            print(f"[VOICE RAW] {raw_text}", flush=True)
            session.last_raw = raw_text

            # Handle pending confirmation
            if pending_confirm is not None:
                cmd, params = pending_confirm
                pending_confirm = None
                if session.is_confirmation(raw_text):
                    result = await execute_command(cmd, params)
                    print(f"[EXEC] {result}", flush=True)
                    await speak_text(result if not result.startswith("__") else "OK")
                    continue
                elif session.is_denial(raw_text):
                    await speak_text("Commande annulee.")
                    continue

            # Check if selecting from previous suggestions
            sel = session.is_selecting_suggestion(raw_text)
            if sel:
                print(f"[SELECT] {sel.name}", flush=True)
                if sel.confirm:
                    pending_confirm = (sel, {})
                    await speak_text(f"Confirme: {sel.description}? Dis oui ou non.")
                    continue
                result = await execute_command(sel, {})
                if not result.startswith("__"):
                    await speak_text(result)
                continue

            # Full correction pipeline
            cr = await full_correction_pipeline(raw_text)
            print(f"[PIPELINE] method={cr['method']} confidence={cr['confidence']:.2f}", flush=True)
            if cr["corrected"] != raw_text.lower().strip():
                print(f"[CORRECTED] {cr['corrected']}", flush=True)
            if cr["intent"] and cr["intent"] != cr["corrected"]:
                print(f"[INTENT] {cr['intent']}", flush=True)

            cmd = cr["command"]
            params = cr["params"]
            confidence = cr["confidence"]

            # Exit command
            if cmd and cmd.name == "jarvis_stop":
                await speak_text("Session vocale terminee. A bientot.")
                break

            # Help command — include skills
            if cmd and cmd.name == "jarvis_aide":
                help_text = format_commands_help()
                skills_text = format_skills_list()
                print(help_text, flush=True)
                print("\n" + skills_text, flush=True)
                await speak_text(f"J'ai {len(load_skills())} skills et 80 commandes. Regarde l'ecran.")
                continue

            # Check for skill match BEFORE command execution
            intent_text = cr["intent"] or cr["corrected"] or raw_text
            skill, skill_score = find_skill(intent_text)
            if skill and skill_score >= 0.65:
                print(f"[SKILL] {skill.name} (score={skill_score:.2f}, {len(skill.steps)} etapes)", flush=True)
                session.add_to_history(intent_text)

                if hasattr(skill, 'confirm') and skill.confirm:
                    pending_confirm = (skill, {})
                    await speak_text(f"Confirme le skill {skill.name}: {skill.description}? Dis oui ou non.")
                    continue

                await speak_text(f"Lancement du skill {skill.name}.")

                # Execute skill via Claude (send as freeform with context)
                skill_prompt = (
                    f"Execute le skill '{skill.name}': {skill.description}. "
                    f"Etapes: " + "; ".join(
                        f"{i+1}) {s.tool}({s.args})" if s.args else f"{i+1}) {s.tool}"
                        for i, s in enumerate(skill.steps)
                    ) + ". Execute chaque etape avec les outils MCP et resume les resultats."
                )
                print(f"[SKILL PROMPT] {skill_prompt[:100]}...", flush=True)
                await client.query(skill_prompt)
                rp = []
                async for msg in client.receive_response():
                    if isinstance(msg, AssistantMessage):
                        for b in msg.content:
                            if isinstance(b, TextBlock):
                                rp.append(b.text)
                                print(b.text, end="", flush=True)
                            elif isinstance(b, ToolUseBlock):
                                print(f"\n  [TOOL] {b.name}", flush=True)
                    if isinstance(msg, ResultMessage):
                        if msg.total_cost_usd:
                            print(f"\n  [$] {msg.total_cost_usd:.4f} USD", flush=True)
                fr = "".join(rp).strip()
                if fr:
                    await speak_text(fr[:500])
                    log_action(f"skill:{skill.name}", fr[:200], True)

                # Suggest next actions
                suggestions = suggest_next_actions(intent_text)
                if suggestions:
                    print(f"\n[SUGGESTIONS] {', '.join(s.split(' — ')[0] for s in suggestions)}", flush=True)
                continue

            # High confidence match → execute
            if cmd and confidence >= 0.65:
                session.add_to_history(cr["intent"])

                if cmd.confirm:
                    pending_confirm = (cmd, params)
                    await speak_text(f"Confirme: {cmd.description}? Dis oui ou non.")
                    continue

                result = await execute_command(cmd, params)

                if result == "__EXIT__":
                    await speak_text("Session terminee.")
                    break
                elif result.startswith("__TOOL__"):
                    tool_action = result[len("__TOOL__"):]
                    prompt = f"Utilise l'outil mcp__jarvis__{tool_action} et rapporte le resultat en francais."
                    await client.query(prompt)
                    rp = []
                    async for msg in client.receive_response():
                        if isinstance(msg, AssistantMessage):
                            for b in msg.content:
                                if isinstance(b, TextBlock):
                                    rp.append(b.text)
                                    print(b.text, end="", flush=True)
                    fr = "".join(rp).strip()
                    if fr:
                        await speak_text(fr[:500])
                elif not result.startswith("__"):
                    print(f"[EXEC] {result}", flush=True)
                    await speak_text(result)
                continue

            # Low confidence with suggestions → propose
            if cr["suggestions"] and confidence < 0.65:
                session.last_suggestions = cr["suggestions"]
                sug_text = format_suggestions(cr["suggestions"])
                print(sug_text, flush=True)
                # Voice: just say the top suggestion
                top = cr["suggestions"][0][0]
                await speak_text(f"Tu voulais dire: {top.triggers[0]}? Dis oui, ou repete ta commande.")
                pending_confirm = (top, {})
                continue

            # No match at all → send to Claude as freeform
            freeform = cr["intent"] or cr["corrected"] or raw_text
            print(f"[FREEFORM] → Claude: {freeform}", flush=True)
            session.add_to_history(freeform)
            await client.query(freeform)
            rp = []
            async for msg in client.receive_response():
                if isinstance(msg, AssistantMessage):
                    for b in msg.content:
                        if isinstance(b, TextBlock):
                            rp.append(b.text)
                            print(b.text, end="", flush=True)
                        elif isinstance(b, ToolUseBlock):
                            print(f"\n  [TOOL] {b.name}", flush=True)
                if isinstance(msg, ResultMessage):
                    if msg.total_cost_usd:
                        print(f"\n  [$] {msg.total_cost_usd:.4f} USD", flush=True)
            fr = "".join(rp).strip()
            if fr:
                await speak_text(fr[:500])

    print("\n[JARVIS] Session vocale terminee.")
