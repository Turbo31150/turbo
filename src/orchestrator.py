"""JARVIS Orchestrator - Core engine using ClaudeSDKClient."""

from __future__ import annotations

import asyncio
import sys
from typing import Any

import httpx

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
Tu es JARVIS v{JARVIS_VERSION}, orchestrateur IA distribue sur un cluster de 2 machines + Ollama cloud.
Reponds TOUJOURS en francais. Sois concis — tes sorties alimentent un pipeline vocal.

## Architecture
- Moteur: CLAUDE (Agent SDK) + LM Studio local + Ollama (TRI_CORE)
- Cluster LM Studio: 9 GPU, ~70 GB VRAM total (M1 + M2)
  - M1 (10.5.0.2:1234) — 6 GPU (RTX 2060 12GB + 4x GTX 1660S 6GB + RTX 3080 10GB) = 46GB VRAM
    - qwen3-30b PERMANENT (18.56 GB, MoE 3B actifs, ctx 32K, 4 parallel, flash attention)
    - On-demand: qwen3-coder-30b (code), devstral (dev), gpt-oss-20b (general)
  - M2 (192.168.1.26:1234) — 3 GPU, 24GB VRAM — deepseek-coder-v2-lite (code rapide)
- Ollama (127.0.0.1:11434) — qwen3:1.7b local + cloud (minimax-m2.5, glm-5, kimi-k2.5)

## Tools MCP Jarvis (83 outils — prefixe mcp__jarvis__)

### IA & Cluster LM Studio (4)
lm_query — Interroger LM Studio. Args: prompt, node, model, mode (fast/deep/default)
lm_models, lm_cluster_status, consensus

### LM Studio Model Management (7)
lm_load_model — Charger un modele sur M1 (on-demand)
lm_unload_model — Decharger un modele
lm_switch_coder — Basculer en mode code (qwen3-coder-30b)
lm_switch_dev — Basculer en mode dev (devstral)
lm_gpu_stats — Statistiques GPU VRAM detaillees
lm_benchmark — Benchmark latence inference
lm_perf_metrics — Metriques de performance (latences moyennes)

### Ollama Local (4)
ollama_query, ollama_models, ollama_pull, ollama_status

### Ollama Cloud — Web Search + Sous-agents (3)
ollama_web_search — Recherche web NATIVE via modeles cloud
ollama_subagents — 3 sous-agents paralleles (minimax + glm + kimi)
ollama_trading_analysis — 3 agents trading paralleles (scanner + analyste + stratege)

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
trading_pending_signals, trading_execute_signal, trading_positions,
trading_status, trading_close_position

### Skills & Pipelines (5)
list_skills, create_skill, remove_skill, suggest_actions, action_history

### Brain — Apprentissage Autonome (4)
brain_status, brain_analyze, brain_suggest, brain_learn

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

## Protocole
1. Decomposer les requetes complexes en micro-taches → dispatcher aux subagents
2. TOUJOURS utiliser le cluster IA local (M1 qwen3-30b) pour analyser AVANT d'agir
3. Pour les decisions critiques: consensus (min 2 sources: M1 + OL1)
4. Mode Voice-First: phrases courtes, pas de markdown, reponses directes
5. IMPORTANT: Max 4 outils MCP jarvis en parallele (limite stdio). Batch par groupes de 3-4.
6. Pour le code: utiliser lm_switch_coder puis lm_query avec qwen3-coder-30b
7. Pour les recherches web: utiliser ollama_web_search (recherche web NATIVE)
8. Pour les analyses complexes: utiliser ollama_subagents (3 agents paralleles)
9. Monitorer les performances: lm_perf_metrics + lm_gpu_stats regulierement
10. Auto-apprentissage: brain_learn pour detecter et creer des skills automatiquement

## Routage IA (auto-tune par latence)
- Reponse courte → M1 (qwen3-30b MoE rapide, mode=fast)
- Analyse profonde → M1 (mode=deep, 16K tokens)
- Code → M2 (deepseek-coder) ou M1 (qwen3-coder-30b on-demand)
- Signal trading → M1, OL1 (parallele)
- Recherche web → OL1 (cloud avec recherche web native)
- Correction vocale → OL1 (qwen3:1.7b local, ultra-rapide)
"""


COMMANDER_PROMPT = f"""\
Tu es JARVIS v{JARVIS_VERSION}, COMMANDANT IA distribue.

## REGLE ABSOLUE
Tu ne fais JAMAIS le travail toi-meme. Tu ORDONNES, VERIFIES et ORCHESTRES.
Pour TOUTE demande, tu DOIS deleguer aux agents et IAs locales.

## Tes Ordres
Pour TOUTE demande:
1. CLASSIFIE la tache (code/analyse/trading/systeme/web/simple)
2. DECOMPOSE en sous-taches atomiques
3. DISPATCHE aux agents et IAs en PARALLELE:
   - ia-deep (Task): analyse profonde, architecture, strategie
   - ia-fast (Task): code, edits, execution rapide
   - ia-check (Task): validation, review, score qualite
   - ia-trading (Task): trading MEXC, scanners, breakout
   - ia-system (Task): operations Windows, PowerShell, fichiers
   - mcp__jarvis__lm_query: interroger M1 (qwen3-30b) ou M2 (deepseek-coder) directement
   - mcp__jarvis__consensus: consensus multi-IA (M1+OL1)
   - mcp__jarvis__ollama_web_search: recherche web via cloud
   - mcp__jarvis__ollama_subagents: 3 sous-agents paralleles (minimax+glm+kimi)
4. COLLECTE tous les resultats
5. VERIFIE la qualite via ia-check (score 0-1)
6. Si score < 0.7 → RE-DISPATCHE les taches faibles (max 2 cycles)
7. SYNTHETISE la reponse finale avec attribution [AGENT/modele]

## Cluster IA
- M1 (10.5.0.2:1234) — 6 GPU 46GB — qwen3-30b permanent (lm_query node=M1)
- M2 (192.168.1.26:1234) — 3 GPU 24GB — deepseek-coder (lm_query node=M2)
- OL1 (127.0.0.1:11434) — Ollama cloud (ollama_web_search, ollama_subagents)

## Subagents (via Task)
- `ia-deep` (Opus) — Analyse approfondie, architecture
- `ia-fast` (Haiku) — Code, execution rapide
- `ia-check` (Sonnet) — Validation, tests, score qualite
- `ia-trading` (Sonnet) — Trading MEXC Futures
- `ia-system` (Haiku) — Operations systeme Windows

## Trading Config
- Exchange: MEXC Futures | Levier: {config.leverage}x
- Paires: {', '.join(p.split('/')[0] for p in config.pairs)}
- TP: {config.tp_percent}% | SL: {config.sl_percent}%

## Format Reponse
[SYNTHESE COMMANDANT]
- Resume concis avec attribution [AGENT/modele] pour chaque contribution
- Score qualite global (0-1)
- Liste des agents utilises
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


def build_options(cwd: str | None = None, commander: bool = True) -> ClaudeAgentOptions:
    """Build ClaudeAgentOptions for the JARVIS orchestrator.

    Args:
        cwd: Working directory.
        commander: If True (default), use COMMANDER_PROMPT (Claude = pure orchestrateur).
    """
    return ClaudeAgentOptions(
        system_prompt=COMMANDER_PROMPT if commander else SYSTEM_PROMPT,
        permission_mode="acceptEdits",
        allowed_tools=[
            # Claude Code tools
            "Read", "Write", "Edit", "Bash", "Glob", "Grep",
            "WebSearch", "WebFetch", "Task",
            # JARVIS MCP — all 83 tools authorized
            "mcp__jarvis__*",
        ],
        mcp_servers={"jarvis": _jarvis_mcp_config()},
        agents=JARVIS_AGENTS,
        cwd=cwd,
    )


async def run_once(prompt: str, cwd: str | None = None) -> str | None:
    """Single-shot query with Commander pipeline: classify -> decompose -> enrich -> dispatch."""
    from src.commander import classify_task, decompose_task, build_commander_enrichment, format_commander_header

    options = build_options(cwd or "F:/BUREAU/turbo")

    # Commander pipeline: classify + decompose + enrich
    classification = await classify_task(prompt)
    tasks = decompose_task(prompt, classification)
    header = format_commander_header(classification, tasks)
    _safe_print(header, flush=True)
    enriched = build_commander_enrichment(prompt, classification, tasks)

    from claude_agent_sdk import query

    result_text: str | None = None
    collected: list[str] = []
    try:
        async for message in query(prompt=enriched, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        collected.append(block.text)
                        _safe_print(block.text, end="", flush=True)
                    elif isinstance(block, ToolUseBlock):
                        _safe_print(f"\n  [DISPATCH] {block.name}", flush=True)
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
    """Interactive REPL mode — Commander pipeline permanent."""
    from src.commander import classify_task, decompose_task, build_commander_enrichment, format_commander_header

    options = build_options(cwd)

    print(f"=== JARVIS v{JARVIS_VERSION} | MODE COMMANDANT | Interactive ===")
    print("Claude = orchestrateur pur. Agents + IAs font le travail.")
    print("Commands: 'exit' pour quitter, 'status' pour cluster check\n")

    async with ClaudeSDKClient(options=options) as client:
        while True:
            try:
                user_input = input("\n[COMMANDANT] > ")
            except (EOFError, KeyboardInterrupt):
                break

            if not user_input.strip():
                continue
            if user_input.strip().lower() == "exit":
                break
            if user_input.strip().lower() == "status":
                user_input = "Use lm_cluster_status and report results."

            # Commander pipeline: classify -> decompose -> enrich
            classification = await classify_task(user_input)
            tasks = decompose_task(user_input, classification)
            header = format_commander_header(classification, tasks)
            _safe_print(header, flush=True)
            enriched = build_commander_enrichment(user_input, classification, tasks)

            await client.query(enriched)

            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            _safe_print(block.text, end="", flush=True)
                        elif isinstance(block, ToolUseBlock):
                            _safe_print(f"\n  [DISPATCH] {block.name}", flush=True)
                if isinstance(message, ResultMessage):
                    if message.total_cost_usd:
                        _safe_print(f"\n  [$] {message.total_cost_usd:.4f} USD", flush=True)

    _safe_print("\n[JARVIS] Session terminee.")


async def run_commander(cwd: str | None = None) -> None:
    """Commander mode: Claude ne fait que deleguer aux agents et IAs.

    Claude recoit le COMMANDER_PROMPT et DOIT utiliser Task + lm_query +
    consensus pour dispatcher le travail. Il ne traite RIEN lui-meme.
    """
    from src.commander import classify_task, decompose_task, build_commander_enrichment, format_commander_header

    options = build_options(cwd)
    options.system_prompt = COMMANDER_PROMPT

    print(f"=== JARVIS v{JARVIS_VERSION} | MODE COMMANDANT | Claude = Orchestrateur ===")
    print("Claude ne fait que deleguer. Agents + IAs font le travail.")
    print("Commands: 'exit' pour quitter, 'status' pour cluster check\n")

    async with ClaudeSDKClient(options=options) as client:
        while True:
            try:
                user_input = input("\n[COMMANDANT] > ")
            except (EOFError, KeyboardInterrupt):
                break

            if not user_input.strip():
                continue
            if user_input.strip().lower() == "exit":
                break
            if user_input.strip().lower() == "status":
                user_input = "Use lm_cluster_status and report results."

            # Step 1: Classify via M1 (fast, <1s)
            _safe_print("[COMMANDANT] Classification en cours...", flush=True)
            classification = await classify_task(user_input)
            _safe_print(f"[COMMANDANT] Type: {classification}", flush=True)

            # Step 2: Decompose into TaskUnits
            tasks = decompose_task(user_input, classification)
            header = format_commander_header(classification, tasks)
            _safe_print(header, flush=True)

            # Step 3: Build enriched prompt for Claude
            enriched = build_commander_enrichment(user_input, classification, tasks)

            # Step 4: Send to Claude — it will dispatch via Task/lm_query/consensus
            await client.query(enriched)

            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            _safe_print(block.text, end="", flush=True)
                        elif isinstance(block, ToolUseBlock):
                            _safe_print(f"\n  [DISPATCH] {block.name}", flush=True)
                if isinstance(message, ResultMessage):
                    if message.total_cost_usd:
                        _safe_print(f"\n  [$] {message.total_cost_usd:.4f} USD | "
                                    f"Turns: {message.num_turns}", flush=True)

    _safe_print("\n[JARVIS] Session commandant terminee.")


_KNOWLEDGE_CACHE: str | None = None


def _load_knowledge() -> str:
    """Load the compact M1 knowledge prompt (~2.3KB, cached in memory).

    Loads from data/jarvis_m1_prompt.txt (generated by gen_compact_prompt.py).
    Falls back to a minimal inline summary if the file is missing.
    """
    global _KNOWLEDGE_CACHE
    if _KNOWLEDGE_CACHE is not None:
        return _KNOWLEDGE_CACHE

    from pathlib import Path
    prompt_path = Path(__file__).resolve().parent.parent / "data" / "jarvis_m1_prompt.txt"
    if prompt_path.exists():
        _KNOWLEDGE_CACHE = prompt_path.read_text(encoding="utf-8")
    else:
        # Fallback: generate minimal summary from code
        from collections import defaultdict
        from src.commands import COMMANDS
        categories: dict[str, list] = defaultdict(list)
        for cmd in COMMANDS:
            categories[cmd.category].append(cmd)
        lines = [f"JARVIS v{JARVIS_VERSION} | {len(COMMANDS)} cmds vocales"]
        for cat, cmds in sorted(categories.items()):
            top = [c.triggers[0] for c in cmds[:5]]
            extra = f" +{len(cmds)-5}" if len(cmds) > 5 else ""
            lines.append(f"{cat}({len(cmds)}): {' | '.join(top)}{extra}")
        lines.append("")
        lines.append("Si commande: ACTION=nom_commande")
        lines.append("Si outil: OUTIL=nom_outil(args)")
        lines.append("Sinon reponds en francais, concis.")
        _KNOWLEDGE_CACHE = "\n".join(lines)
    return _KNOWLEDGE_CACHE


async def _local_ia_analyze(query: str, timeout: float = 10.0) -> str | None:
    """Query LM Studio M1 to analyze user intent with compact knowledge.

    Uses qwen3-30b (MoE 3B actifs, ctx 32K, 6 GPU, 46GB VRAM, flash attention).
    Timeout 10s — prompt compact + flash attention = inference rapide.
    Retry once on transient error. Falls back to Ollama if M1 offline.
    """
    from src.tools import _get_client

    system_msg = _load_knowledge()
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": query},
    ]

    # Try LM Studio M1 first (qwen3-30b, 6 GPU, 46GB VRAM)
    node = config.get_node("M1")
    if node:
        for attempt in range(2):
            try:
                client = await _get_client()
                r = await client.post(f"{node.url}/api/v1/chat", json={
                    "model": node.default_model,
                    "input": query,
                    "system_prompt": system_msg,
                    "temperature": 0.2,
                    "max_output_tokens": config.fast_max_tokens,
                    "stream": False,
                    "store": False,
                }, timeout=timeout)
                r.raise_for_status()
                from src.tools import extract_lms_output
                content = extract_lms_output(r.json()).strip()
                # Remove thinking tags if present (qwen3 sometimes wraps in <think>)
                if content.startswith("<think>"):
                    think_end = content.find("</think>")
                    if think_end != -1:
                        content = content[think_end + 8:].strip()
                return content
            except Exception:
                if attempt == 0:
                    await asyncio.sleep(0.5)

    # Fallback: Ollama (native API with think:false for speed)
    ol = config.get_ollama_node("OL1")
    if ol:
        try:
            client = await _get_client()
            r = await client.post(f"{ol.url}/api/chat", json={
                "model": ol.default_model,
                "messages": messages,
                "stream": False, "think": False,
                "options": {"temperature": 0.3, "num_predict": config.fast_max_tokens},
            }, timeout=timeout)
            r.raise_for_status()
            return r.json()["message"]["content"].strip()
        except Exception:
            pass
    return None


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
    from src.voice import listen_voice, speak_text, HAS_KEYBOARD, PTT_KEY, check_microphone, start_whisper, stop_whisper
    from src.commands import correct_voice_text, match_command, format_commands_help
    from src.executor import execute_command, execute_skill, process_voice_input, correct_with_ia
    from src.voice_correction import full_correction_pipeline, VoiceSession, format_suggestions
    from src.skills import find_skill, load_skills, format_skills_list, suggest_next_actions, log_action

    options = build_options(cwd)
    session = VoiceSession()
    pending_confirm: tuple | None = None

    # Start persistent Whisper worker (loads model once)
    _safe_print("[JARVIS] Chargement Whisper (faster-whisper CUDA)...")
    whisper_ok = start_whisper()
    if not whisper_ok:
        _safe_print("[WARN] Whisper worker failed — transcription sera plus lente")

    # Load skills on startup
    skills = load_skills()
    from src.commands import COMMANDS
    n_cmds = len(COMMANDS)
    n_tools = len(__import__("src.mcp_server", fromlist=["TOOL_DEFINITIONS"]).TOOL_DEFINITIONS)
    has_mic = check_microphone()
    if has_mic:
        ptt_label = f"Push-to-talk: {PTT_KEY.upper()}" if HAS_KEYBOARD else "Ecoute continue"
        mode_label = "MODE VOCAL"
    else:
        ptt_label = "Clavier + TTS (pas de micro)"
        mode_label = "MODE HYBRIDE"
        _safe_print("[WARN] Aucun micro detecte — fallback clavier + TTS")
    _safe_print(f"=== JARVIS v{JARVIS_VERSION} | {mode_label} | {n_cmds} commandes ===")
    _safe_print(f"{n_tools} outils MCP | {len(skills)} skills | {ptt_label}")
    if has_mic:
        await speak_text(f"JARVIS actif. {len(skills)} skills, {n_cmds} commandes. Maintiens controle pour parler.")
    else:
        await speak_text(f"JARVIS actif en mode hybride. {len(skills)} skills. Tape tes commandes.")

    async with ClaudeSDKClient(options=options) as client:
        while True:
            print("\n[JARVIS] Ecoute...", flush=True)
            raw_text = await listen_voice(timeout=15.0, use_ptt=True)

            if not raw_text:
                continue

            print(f"[VOICE RAW] {raw_text}", flush=True)
            session.last_raw = raw_text

            # ── Wake word + conversational detection ──────────────────────
            # Regex handles all Whisper punctuation: "Jarvis, ...", "Jarvis! ..."
            import re
            _JARVIS_RE = re.compile(
                r'^((?:hey |ok |dis |bonjour |salut )?jarvis)[,.:;!?\s]*',
                re.IGNORECASE,
            )
            _CONV_STARTERS = (
                "j'ai une question", "jai une question", "une question", "question",
                "j'ai besoin", "jai besoin", "aide moi", "aide-moi",
                "j'ai un probleme", "jai un probleme", "j'ai un souci",
                "je veux te demander", "je voudrais", "je veux savoir",
                "tu peux m'aider", "help", "j'ai quelque chose",
                "est-ce que tu peux", "dis-moi", "dis moi",
            )

            stripped = raw_text.strip().lower()
            m = _JARVIS_RE.match(stripped)

            if m:
                after = stripped[m.end():].strip().rstrip("?!.,;:")
                if not after:
                    # "jarvis" seul → demande la commande
                    await speak_text("Quelle est ta question ou action?")
                    print("[WAKE] Activation — en attente de commande", flush=True)
                    continue
                # Conversationnel court SEULEMENT (< 6 mots) → demande plus
                # Phrases longues = vraies questions → laisser passer au pipeline
                if len(after.split()) < 6 and (after in _CONV_STARTERS or any(after == cs for cs in _CONV_STARTERS)):
                    await speak_text("Oui, dis-moi?")
                    print(f"[WAKE] Conversationnel: {after} — en attente", flush=True)
                    continue
                # Commande ou question apres "jarvis" → strip et traiter
                raw_text = raw_text.strip()[m.end():].strip()
                print(f"[WAKE] Prefixe retire → {raw_text}", flush=True)
            else:
                # Pas de "jarvis" — check conversationnel court seulement
                check = stripped.rstrip("?!.,;:")
                if len(check.split()) < 6 and (check in _CONV_STARTERS or any(check == cs for cs in _CONV_STARTERS)):
                    await speak_text("Dis-moi, quelle est ta question?")
                    print(f"[CONV] Conversationnel → en attente", flush=True)
                    continue

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

            # Exit command — strict match only (>= 0.85) to avoid accidental exits
            if cmd and cmd.name == "jarvis_stop" and confidence >= 0.85:
                await speak_text("Session vocale terminee. A bientot.")
                break
            elif cmd and cmd.name == "jarvis_stop" and confidence < 0.85:
                # Faux positif probable — ignorer le match stop
                cmd = None
                print(f"[SAFE] jarvis_stop ignore (confidence={confidence:.2f} < 0.85)", flush=True)

            # Help command — include skills
            if cmd and cmd.name == "jarvis_aide":
                help_text = format_commands_help()
                skills_text = format_skills_list()
                print(help_text, flush=True)
                print("\n" + skills_text, flush=True)
                await speak_text(f"J'ai {len(load_skills())} skills et {n_cmds} commandes. Regarde l'ecran.")
                continue

            # Check for skill match BEFORE command execution (only if pipeline found a command-like input)
            intent_text = cr["intent"] or cr["corrected"] or raw_text
            skill, skill_score = find_skill(intent_text)
            if skill and skill_score >= 0.72:
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

            # Low confidence with suggestions → propose ONLY if pipeline found a plausible match
            # Skip if method="freeform" (no good match = don't show noisy suggestions)
            if (cr["suggestions"] and confidence < 0.65
                    and cr["method"] == "suggestion" and check_microphone()):
                session.last_suggestions = cr["suggestions"]
                sug_text = format_suggestions(cr["suggestions"])
                print(sug_text, flush=True)
                top = cr["suggestions"][0][0]
                await speak_text(f"Tu voulais dire: {top.triggers[0]}? Dis oui, ou repete ta commande.")
                pending_confirm = (top, {})
                continue

            # No match → MODE COMMANDANT (M1 pre-analyse + Claude dispatche)
            freeform = cr["intent"] or cr["corrected"] or raw_text
            session.add_to_history(freeform)

            try:
                # Step 1: Ask local IA (M1/qwen3-30b) for analysis
                print(f"[FREEFORM] → IA locale (M1): {freeform}", flush=True)
                local_response = await _local_ia_analyze(freeform)

                if local_response:
                    print(f"[LOCAL IA] {local_response[:200]}", flush=True)

                    # If the local IA gives a direct answer (no tool needed), use it
                    needs_tools = any(kw in local_response.lower() for kw in [
                        "outil", "tool", "mcp", "execute", "lancer", "ouvrir", "fermer",
                        "powershell", "script", "fichier", "dossier", "trading", "cluster",
                    ])

                    if not needs_tools:
                        # Local IA answered directly — no need for Claude
                        await speak_text(local_response[:500])
                        continue

                    # Step 2: Commander pattern — Claude dispatche aux agents/IAs
                    enriched = (
                        f"MODE COMMANDANT. Demande utilisateur: \"{freeform}\"\n"
                        f"Pre-analyse M1: {local_response}\n\n"
                        f"ORDRES: Decompose cette tache et dispatche aux agents/IAs. "
                        f"Ne traite RIEN toi-meme. Delegue TOUT.\n"
                        f"Resume le resultat en francais, concis (pipeline vocal)."
                    )
                    print(f"[FREEFORM] → Claude COMMANDANT (enrichi par M1)", flush=True)
                else:
                    # M1 indisponible → Claude commandant sans pre-analyse
                    enriched = (
                        f"MODE COMMANDANT. Demande utilisateur: \"{freeform}\"\n\n"
                        f"ORDRES: Decompose cette tache et dispatche aux agents/IAs. "
                        f"Ne traite RIEN toi-meme. Delegue TOUT.\n"
                        f"Resume le resultat en francais, concis (pipeline vocal)."
                    )
                    print(f"[FREEFORM] → Claude COMMANDANT (direct): {freeform}", flush=True)

                await client.query(enriched)
                rp = []
                async for msg in client.receive_response():
                    if isinstance(msg, AssistantMessage):
                        for b in msg.content:
                            if isinstance(b, TextBlock):
                                rp.append(b.text)
                                print(b.text, end="", flush=True)
                            elif isinstance(b, ToolUseBlock):
                                print(f"\n  [DISPATCH] {b.name}", flush=True)
                    if isinstance(msg, ResultMessage):
                        if msg.total_cost_usd:
                            print(f"\n  [$] {msg.total_cost_usd:.4f} USD", flush=True)
                fr = "".join(rp).strip()
                if fr:
                    await speak_text(fr[:500])
            except Exception as e:
                print(f"\n  [ERREUR FREEFORM] {e}", flush=True)
                await speak_text("Desole, une erreur s'est produite. Repete ta demande.")

    stop_whisper()
    _safe_print("\n[JARVIS] Session vocale terminee.")


async def run_hybrid(cwd: str | None = None) -> None:
    """Hybrid mode: keyboard input with full voice pipeline (correction, skills, brain).

    Same as run_voice but uses keyboard input instead of microphone.
    Perfect for testing without audio hardware.
    """
    from src.commands import correct_voice_text, match_command, format_commands_help
    from src.executor import execute_command
    from src.voice_correction import full_correction_pipeline, VoiceSession, format_suggestions
    from src.skills import find_skill, load_skills, format_skills_list, suggest_next_actions, log_action

    options = build_options(cwd)
    session = VoiceSession()
    pending_confirm: tuple | None = None

    skills = load_skills()
    from src.commands import COMMANDS
    n_cmds = len(COMMANDS)
    _safe_print(f"=== JARVIS v{JARVIS_VERSION} | MODE COMMANDANT HYBRIDE (clavier) ===")
    _safe_print(f"83 outils MCP | {len(skills)} skills | {n_cmds} commandes")
    _safe_print("Tape tes commandes comme si tu parlais. 'exit' pour quitter.\n")

    async with ClaudeSDKClient(options=options) as client:
        while True:
            try:
                raw_text = input("\n[JARVIS] > ")
            except (EOFError, KeyboardInterrupt):
                break

            if not raw_text or not raw_text.strip():
                continue

            raw_text = raw_text.strip()
            session.last_raw = raw_text

            # Handle pending confirmation
            if pending_confirm is not None:
                cmd, params = pending_confirm
                pending_confirm = None
                if session.is_confirmation(raw_text):
                    result = await execute_command(cmd, params)
                    _safe_print(f"[EXEC] {result}")
                    continue
                elif session.is_denial(raw_text):
                    _safe_print("Commande annulee.")
                    continue

            # Full correction pipeline
            cr = await full_correction_pipeline(raw_text)
            _safe_print(f"[PIPELINE] method={cr['method']} confidence={cr['confidence']:.2f}")
            if cr["corrected"] != raw_text.lower().strip():
                _safe_print(f"[CORRECTED] {cr['corrected']}")
            if cr["intent"] and cr["intent"] != cr["corrected"]:
                _safe_print(f"[INTENT] {cr['intent']}")

            cmd = cr["command"]
            params = cr["params"]
            confidence = cr["confidence"]

            # Exit
            if cmd and cmd.name == "jarvis_stop":
                _safe_print("Session terminee. A bientot.")
                break

            # Help
            if cmd and cmd.name == "jarvis_aide":
                _safe_print(format_commands_help())
                _safe_print("\n" + format_skills_list())
                continue

            # Check for skill match
            intent_text = cr["intent"] or cr["corrected"] or raw_text
            skill, skill_score = find_skill(intent_text)
            if skill and skill_score >= 0.72:
                _safe_print(f"[SKILL] {skill.name} (score={skill_score:.2f}, {len(skill.steps)} etapes)")
                session.add_to_history(intent_text)

                if hasattr(skill, 'confirm') and skill.confirm:
                    pending_confirm = (skill, {})
                    _safe_print(f"Confirme le skill {skill.name}: {skill.description}? (oui/non)")
                    continue

                _safe_print(f"Lancement du skill {skill.name}...")
                skill_prompt = (
                    f"Execute le skill '{skill.name}': {skill.description}. "
                    f"Etapes: " + "; ".join(
                        f"{i+1}) {s.tool}({s.args})" if s.args else f"{i+1}) {s.tool}"
                        for i, s in enumerate(skill.steps)
                    ) + ". Execute chaque etape avec les outils MCP et resume les resultats."
                )
                await client.query(skill_prompt)
                rp = []
                async for msg in client.receive_response():
                    if isinstance(msg, AssistantMessage):
                        for b in msg.content:
                            if isinstance(b, TextBlock):
                                rp.append(b.text)
                                _safe_print(b.text, end="", flush=True)
                            elif isinstance(b, ToolUseBlock):
                                _safe_print(f"\n  [TOOL] {b.name}", flush=True)
                    if isinstance(msg, ResultMessage):
                        if msg.total_cost_usd:
                            _safe_print(f"\n  [$] {msg.total_cost_usd:.4f} USD", flush=True)
                fr = "".join(rp).strip()
                if fr:
                    log_action(f"skill:{skill.name}", fr[:200], True)
                suggestions = suggest_next_actions(intent_text)
                if suggestions:
                    _safe_print(f"\n[SUGGESTIONS] {', '.join(s.split(' — ')[0] for s in suggestions)}")
                continue

            # High confidence match
            if cmd and confidence >= 0.65:
                session.add_to_history(cr["intent"])

                if cmd.confirm:
                    pending_confirm = (cmd, params)
                    _safe_print(f"Confirme: {cmd.description}? (oui/non)")
                    continue

                result = await execute_command(cmd, params)

                if result == "__EXIT__":
                    _safe_print("Session terminee.")
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
                                    _safe_print(b.text, end="", flush=True)
                    fr = "".join(rp).strip()
                elif not result.startswith("__"):
                    _safe_print(f"[EXEC] {result}")
                continue

            # Low confidence with suggestions — only if pipeline found a plausible match
            if cr["suggestions"] and confidence < 0.65 and cr["method"] == "suggestion":
                session.last_suggestions = cr["suggestions"]
                sug_text = format_suggestions(cr["suggestions"])
                _safe_print(sug_text)
                top = cr["suggestions"][0][0]
                _safe_print(f"Tu voulais dire: {top.triggers[0]}? (oui/non)")
                pending_confirm = (top, {})
                continue

            # No match → MODE COMMANDANT (M1 pre-analyse + Claude dispatche)
            from src.commander import classify_task as _classify, decompose_task as _decompose, build_commander_enrichment as _enrich, format_commander_header as _header
            freeform = cr["intent"] or cr["corrected"] or raw_text
            session.add_to_history(freeform)

            # Commander pipeline: classify -> decompose -> enrich
            _safe_print(f"[FREEFORM] -> Commandant: {freeform}")
            _cls = await _classify(freeform)
            _tasks = _decompose(freeform, _cls)
            _safe_print(_header(_cls, _tasks), flush=True)

            # Pre-analyse M1
            local_response = await _local_ia_analyze(freeform)
            if local_response:
                _safe_print(f"[LOCAL IA] {local_response[:200]}", flush=True)
                # Reponse directe si pas d'outil necessaire
                needs_tools = any(kw in local_response.lower() for kw in [
                    "outil", "tool", "mcp", "execute", "lancer", "ouvrir", "fermer",
                    "powershell", "script", "fichier", "dossier", "trading", "cluster",
                ])
                if not needs_tools:
                    _safe_print(f"[LOCAL] {local_response}")
                    continue

            enriched = _enrich(freeform, _cls, _tasks, pre_analysis=local_response)
            await client.query(enriched)
            rp = []
            async for msg in client.receive_response():
                if isinstance(msg, AssistantMessage):
                    for b in msg.content:
                        if isinstance(b, TextBlock):
                            rp.append(b.text)
                            _safe_print(b.text, end="", flush=True)
                        elif isinstance(b, ToolUseBlock):
                            _safe_print(f"\n  [DISPATCH] {b.name}", flush=True)
                if isinstance(msg, ResultMessage):
                    if msg.total_cost_usd:
                        _safe_print(f"\n  [$] {msg.total_cost_usd:.4f} USD", flush=True)

    _safe_print("\n[JARVIS] Session hybride terminee.")
