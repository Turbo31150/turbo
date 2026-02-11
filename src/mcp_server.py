"""JARVIS MCP Server — Standalone stdio server (52 tools).

Run directly: python -m src.mcp_server
Used by the Claude Agent SDK as an external subprocess MCP server.
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

import httpx
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# ── Config import (inline to avoid circular deps) ──────────────────────────

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
from src.config import config, SCRIPTS, PATHS


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _text(text: str) -> list[TextContent]:
    return [TextContent(type="text", text=text)]


def _error(text: str) -> list[TextContent]:
    return [TextContent(type="text", text=f"ERREUR: {text}")]


def _ps_sync(cmd: str) -> str:
    """Run a PowerShell command synchronously and return output."""
    import subprocess
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command", cmd],
        capture_output=True, text=True, timeout=30,
    )
    return r.stdout.strip() if r.returncode == 0 else f"ERREUR: {r.stderr.strip()}"


async def _ps(cmd: str) -> str:
    """Run a PowerShell command in a thread pool (non-blocking)."""
    return await asyncio.to_thread(_ps_sync, cmd)


async def _run(func, *args):
    """Run a blocking function in a thread pool to avoid blocking the event loop."""
    return await asyncio.to_thread(func, *args)


# ═══════════════════════════════════════════════════════════════════════════
# TOOL HANDLERS
# ═══════════════════════════════════════════════════════════════════════════

async def handle_lm_query(args: dict) -> list[TextContent]:
    node = config.get_node(args.get("node", "M1"))
    if not node:
        return _error(f"Noeud inconnu: {args.get('node')}")
    model = args.get("model", node.default_model)
    try:
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post(f"{node.url}/v1/chat/completions", json={
                "model": model,
                "messages": [{"role": "user", "content": args["prompt"]}],
                "temperature": config.temperature,
                "max_tokens": config.max_tokens,
            })
            r.raise_for_status()
            return _text(f"[{node.name}/{model}] {r.json()['choices'][0]['message']['content']}")
    except httpx.ConnectError:
        return _error(f"Noeud {node.name} hors ligne")
    except Exception as e:
        return _error(str(e))


async def handle_lm_models(args: dict) -> list[TextContent]:
    url = config.get_node_url(args.get("node", "M1"))
    if not url:
        return _error("Noeud inconnu")
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{url}/v1/models")
            r.raise_for_status()
            models = [m["id"] for m in r.json().get("data", [])]
            return _text(f"Modeles: {', '.join(models) if models else 'aucun'}")
    except Exception as e:
        return _error(str(e))


async def handle_lm_cluster_status(args: dict) -> list[TextContent]:
    results, online = [], 0
    async with httpx.AsyncClient(timeout=5) as c:
        for n in config.lm_nodes:
            try:
                r = await c.get(f"{n.url}/v1/models")
                r.raise_for_status()
                cnt = len(r.json().get("data", []))
                results.append(f"  {n.name} ({n.role}): ONLINE — {cnt} modeles, {n.gpus} GPU, {n.vram_gb}GB VRAM")
                online += 1
            except Exception:
                results.append(f"  {n.name} ({n.role}): OFFLINE")
    header = f"Cluster: {online}/{len(config.lm_nodes)} noeuds en ligne"
    return _text(f"{header}\n" + "\n".join(results))


async def handle_consensus(args: dict) -> list[TextContent]:
    prompt = args["prompt"]
    nodes = args.get("nodes", "M1,M2,M3").split(",")
    responses = []
    async with httpx.AsyncClient(timeout=60) as c:
        for name in nodes:
            node = config.get_node(name.strip())
            if not node:
                continue
            try:
                r = await c.post(f"{node.url}/v1/chat/completions", json={
                    "model": node.default_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3, "max_tokens": 2048,
                })
                r.raise_for_status()
                text = r.json()["choices"][0]["message"]["content"]
                responses.append(f"[{node.name}] {text}")
            except Exception as e:
                responses.append(f"[{node.name}] ERREUR: {e}")
    return _text(f"Consensus ({len(responses)} sources):\n" + "\n---\n".join(responses))


async def handle_run_script(args: dict) -> list[TextContent]:
    name = args["name"]
    if name not in SCRIPTS:
        return _error(f"Script inconnu: {name}. Disponibles: {', '.join(SCRIPTS.keys())}")
    import subprocess
    def _do():
        r = subprocess.run(
            [sys.executable, str(SCRIPTS[name])] + args.get("args", "").split(),
            capture_output=True, text=True, timeout=120, cwd=str(SCRIPTS[name].parent),
        )
        return r.stdout[:4000] if r.returncode == 0 else f"ERREUR: {r.stderr[:2000]}"
    try:
        return _text(await asyncio.to_thread(_do))
    except Exception as e:
        return _error(str(e))


async def handle_list_scripts(args: dict) -> list[TextContent]:
    lines = [f"  {k}: {v}" for k, v in SCRIPTS.items()]
    return _text(f"Scripts ({len(SCRIPTS)}):\n" + "\n".join(lines))


async def handle_list_project_paths(args: dict) -> list[TextContent]:
    lines = [f"  {k}: {v}" for k, v in PATHS.items()]
    return _text(f"Projets ({len(PATHS)}):\n" + "\n".join(lines))


# ── Windows tools (delegate to PowerShell via thread pool) ─────────────────

async def handle_open_app(args: dict) -> list[TextContent]:
    from src.windows import open_application
    return _text(await _run(open_application, args["name"]))

async def handle_close_app(args: dict) -> list[TextContent]:
    from src.windows import close_application
    return _text(await _run(close_application, args["name"]))

async def handle_open_url(args: dict) -> list[TextContent]:
    from src.windows import open_url
    return _text(await _run(open_url, args["url"]))

async def handle_list_processes(args: dict) -> list[TextContent]:
    from src.windows import list_processes
    return _text(await _run(list_processes, args.get("filter", "")))

async def handle_kill_process(args: dict) -> list[TextContent]:
    from src.windows import kill_process
    return _text(await _run(kill_process, args["name"]))

async def handle_list_windows(args: dict) -> list[TextContent]:
    from src.windows import list_windows
    return _text(await _run(list_windows))

async def handle_focus_window(args: dict) -> list[TextContent]:
    from src.windows import focus_window
    return _text(await _run(focus_window, args["title"]))

async def handle_minimize_window(args: dict) -> list[TextContent]:
    from src.windows import minimize_window
    return _text(await _run(minimize_window, args["title"]))

async def handle_maximize_window(args: dict) -> list[TextContent]:
    from src.windows import maximize_window
    return _text(await _run(maximize_window, args["title"]))

async def handle_send_keys(args: dict) -> list[TextContent]:
    from src.windows import send_keys
    return _text(await _run(send_keys, args["keys"]))

async def handle_type_text(args: dict) -> list[TextContent]:
    from src.windows import type_text
    return _text(await _run(type_text, args["text"]))

async def handle_press_hotkey(args: dict) -> list[TextContent]:
    from src.windows import press_hotkey
    return _text(await _run(press_hotkey, args["keys"]))

async def handle_mouse_click(args: dict) -> list[TextContent]:
    from src.windows import mouse_click
    return _text(await _run(mouse_click, args.get("x", 0), args.get("y", 0), args.get("button", "left")))

async def handle_clipboard_get(args: dict) -> list[TextContent]:
    from src.windows import clipboard_get
    return _text(await _run(clipboard_get))

async def handle_clipboard_set(args: dict) -> list[TextContent]:
    from src.windows import clipboard_set
    return _text(await _run(clipboard_set, args["text"]))

async def handle_open_folder(args: dict) -> list[TextContent]:
    from src.windows import open_folder
    return _text(await _run(open_folder, args["path"]))

async def handle_list_folder(args: dict) -> list[TextContent]:
    from src.windows import list_folder
    return _text(await _run(list_folder, args["path"]))

async def handle_create_folder(args: dict) -> list[TextContent]:
    from src.windows import create_folder
    return _text(await _run(create_folder, args["path"]))

async def handle_copy_item(args: dict) -> list[TextContent]:
    from src.windows import copy_item
    return _text(await _run(copy_item, args["source"], args["destination"]))

async def handle_move_item(args: dict) -> list[TextContent]:
    from src.windows import move_item
    return _text(await _run(move_item, args["source"], args["destination"]))

async def handle_delete_item(args: dict) -> list[TextContent]:
    from src.windows import delete_item
    return _text(await _run(delete_item, args["path"]))

async def handle_read_text_file(args: dict) -> list[TextContent]:
    from src.windows import read_file
    return _text(await _run(read_file, args["path"]))

async def handle_write_text_file(args: dict) -> list[TextContent]:
    from src.windows import write_file
    return _text(await _run(write_file, args["path"], args["content"]))

async def handle_search_files(args: dict) -> list[TextContent]:
    from src.windows import search_files
    return _text(await _run(search_files, args["path"], args["pattern"]))

async def handle_volume_up(args: dict) -> list[TextContent]:
    from src.windows import volume_up
    return _text(await _run(volume_up))

async def handle_volume_down(args: dict) -> list[TextContent]:
    from src.windows import volume_down
    return _text(await _run(volume_down))

async def handle_volume_mute(args: dict) -> list[TextContent]:
    from src.windows import volume_mute
    return _text(await _run(volume_mute))

async def handle_screenshot(args: dict) -> list[TextContent]:
    from src.windows import screenshot
    return _text(await _run(screenshot, args.get("path", "")))

async def handle_screen_resolution(args: dict) -> list[TextContent]:
    from src.windows import get_screen_resolution
    return _text(await _run(get_screen_resolution))

async def handle_system_info(args: dict) -> list[TextContent]:
    from src.windows import get_system_info
    result = await _run(get_system_info)
    if isinstance(result, dict):
        lines = [f"{k}: {v}" for k, v in result.items()]
        return _text("\n".join(lines))
    return _text(str(result))

async def handle_gpu_info(args: dict) -> list[TextContent]:
    from src.windows import get_gpu_info
    return _text(await _run(get_gpu_info))

async def handle_network_info(args: dict) -> list[TextContent]:
    from src.windows import get_network_info
    return _text(await _run(get_network_info))

async def handle_powershell_run(args: dict) -> list[TextContent]:
    return _text(await _ps(args["command"]))

async def handle_lock_screen(args: dict) -> list[TextContent]:
    from src.windows import lock_screen
    return _text(await _run(lock_screen))

async def handle_shutdown_pc(args: dict) -> list[TextContent]:
    from src.windows import shutdown_pc
    return _text(await _run(shutdown_pc, args.get("delay", 0)))

async def handle_restart_pc(args: dict) -> list[TextContent]:
    from src.windows import restart_pc
    return _text(await _run(restart_pc, args.get("delay", 0)))

async def handle_sleep_pc(args: dict) -> list[TextContent]:
    from src.windows import sleep_pc
    return _text(await _run(sleep_pc))

async def handle_list_services(args: dict) -> list[TextContent]:
    from src.windows import list_services
    return _text(await _run(list_services, args.get("filter", "")))

async def handle_start_service(args: dict) -> list[TextContent]:
    from src.windows import start_service
    return _text(await _run(start_service, args["name"]))

async def handle_stop_service(args: dict) -> list[TextContent]:
    from src.windows import stop_service
    return _text(await _run(stop_service, args["name"]))

async def handle_wifi_networks(args: dict) -> list[TextContent]:
    from src.windows import get_wifi_networks
    return _text(await _run(get_wifi_networks))

async def handle_ping(args: dict) -> list[TextContent]:
    from src.windows import ping_host
    return _text(await _run(ping_host, args["host"]))

async def handle_get_ip(args: dict) -> list[TextContent]:
    from src.windows import get_ip_address
    return _text(await _run(get_ip_address))

async def handle_registry_read(args: dict) -> list[TextContent]:
    from src.windows import registry_get
    return _text(await _run(registry_get, args["path"], args["name"]))

async def handle_registry_write(args: dict) -> list[TextContent]:
    from src.windows import registry_set
    return _text(await _run(registry_set, args["path"], args["name"], args["value"]))

async def handle_notify(args: dict) -> list[TextContent]:
    from src.windows import notify_windows
    return _text(await _run(notify_windows, args["title"], args["message"]))

async def handle_speak(args: dict) -> list[TextContent]:
    await _ps(f'Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; $s.Speak("{args["text"]}")')
    return _text(f"Parle: {args['text']}")

async def handle_scheduled_tasks(args: dict) -> list[TextContent]:
    return _text(await _ps("Get-ScheduledTask | Where-Object {$_.State -ne 'Disabled'} | Select-Object TaskName, State, TaskPath | Format-Table -AutoSize | Out-String"))


# ── Trading execution tools ────────────────────────────────────────────────

async def handle_trading_pending_signals(args: dict) -> list[TextContent]:
    from src.trading import get_pending_signals
    min_score = args.get("min_score")
    limit = int(args.get("limit", 10))
    signals = await _run(get_pending_signals, min_score, None, limit)
    return _text(json.dumps(signals, default=str, ensure_ascii=False, indent=2))


async def handle_trading_execute_signal(args: dict) -> list[TextContent]:
    from src.trading import execute_signal
    signal_id = int(args["signal_id"])
    dry_run_str = str(args.get("dry_run", "true")).lower()
    dry_run = dry_run_str in ("true", "1", "yes", "oui")
    result = await _run(execute_signal, signal_id, dry_run)
    return _text(json.dumps(result, default=str, ensure_ascii=False, indent=2))


async def handle_trading_positions(args: dict) -> list[TextContent]:
    from src.trading import get_mexc_positions
    positions = await _run(get_mexc_positions)
    return _text(json.dumps(positions, default=str, ensure_ascii=False, indent=2))


async def handle_trading_status(args: dict) -> list[TextContent]:
    from src.trading import pipeline_status
    status = await _run(pipeline_status)
    return _text(json.dumps(status, default=str, ensure_ascii=False, indent=2))


async def handle_trading_close_position(args: dict) -> list[TextContent]:
    from src.trading import close_position
    result = await _run(close_position, args["symbol"])
    return _text(json.dumps(result, default=str, ensure_ascii=False, indent=2))


# ── Skills & Pipelines ─────────────────────────────────────────────────────

async def handle_list_skills(args: dict) -> list[TextContent]:
    from src.skills import format_skills_list
    return _text(await _run(format_skills_list))

async def handle_create_skill(args: dict) -> list[TextContent]:
    from src.skills import add_skill, Skill, SkillStep
    steps = []
    for s in json.loads(args.get("steps", "[]")):
        steps.append(SkillStep(
            tool=s["tool"],
            args=s.get("args", {}),
            description=s.get("description", ""),
        ))
    if not steps:
        return _error("Aucune etape definie pour le skill.")
    triggers = [t.strip() for t in args.get("triggers", args["name"]).split(",")]
    skill = Skill(
        name=args["name"],
        description=args.get("description", ""),
        triggers=triggers,
        steps=steps,
        category=args.get("category", "custom"),
    )
    add_skill(skill)
    return _text(f"Skill '{skill.name}' cree avec {len(steps)} etapes. Triggers: {', '.join(triggers)}")

async def handle_remove_skill(args: dict) -> list[TextContent]:
    from src.skills import remove_skill
    ok = await _run(remove_skill, args["name"])
    return _text(f"Skill '{args['name']}' supprime." if ok else f"Skill '{args['name']}' introuvable.")

async def handle_suggest_actions(args: dict) -> list[TextContent]:
    from src.skills import suggest_next_actions
    suggestions = suggest_next_actions(args.get("context", "general"))
    return _text("Suggestions:\n" + "\n".join(f"  - {s}" for s in suggestions))

async def handle_action_history(args: dict) -> list[TextContent]:
    from src.skills import get_action_history
    history = get_action_history(int(args.get("limit", 20)))
    if not history:
        return _text("Aucun historique d'actions.")
    lines = []
    for h in history[-10:]:
        status = "OK" if h.get("success") else "FAIL"
        lines.append(f"  [{status}] {h['action']}: {h['result'][:80]}")
    return _text(f"Historique ({len(history)} actions):\n" + "\n".join(lines))


# ═══════════════════════════════════════════════════════════════════════════
# TOOL REGISTRY
# ═══════════════════════════════════════════════════════════════════════════

TOOL_DEFINITIONS: list[tuple[str, str, dict, Any]] = [
    # LM Studio (4)
    ("lm_query", "Interroger un noeud LM Studio.", {"prompt": "string", "node": "string", "model": "string"}, handle_lm_query),
    ("lm_models", "Lister les modeles charges sur un noeud.", {"node": "string"}, handle_lm_models),
    ("lm_cluster_status", "Sante de tous les noeuds du cluster.", {}, handle_lm_cluster_status),
    ("consensus", "Consensus multi-IA sur une question.", {"prompt": "string", "nodes": "string"}, handle_consensus),
    # Scripts (3)
    ("run_script", "Executer un script indexe.", {"name": "string", "args": "string"}, handle_run_script),
    ("list_scripts", "Lister tous les scripts indexes.", {}, handle_list_scripts),
    ("list_project_paths", "Lister les chemins des projets.", {}, handle_list_project_paths),
    # Apps (3)
    ("open_app", "Ouvrir une application.", {"name": "string"}, handle_open_app),
    ("close_app", "Fermer une application.", {"name": "string"}, handle_close_app),
    ("open_url", "Ouvrir une URL dans le navigateur.", {"url": "string"}, handle_open_url),
    # Processes (2)
    ("list_processes", "Lister les processus.", {"filter": "string"}, handle_list_processes),
    ("kill_process", "Tuer un processus.", {"name": "string"}, handle_kill_process),
    # Windows (4)
    ("list_windows", "Lister les fenetres ouvertes.", {}, handle_list_windows),
    ("focus_window", "Focus sur une fenetre.", {"title": "string"}, handle_focus_window),
    ("minimize_window", "Minimiser une fenetre.", {"title": "string"}, handle_minimize_window),
    ("maximize_window", "Maximiser une fenetre.", {"title": "string"}, handle_maximize_window),
    # Keyboard/Mouse (4)
    ("send_keys", "Envoyer des touches clavier.", {"keys": "string"}, handle_send_keys),
    ("type_text", "Taper du texte.", {"text": "string"}, handle_type_text),
    ("press_hotkey", "Raccourci clavier.", {"keys": "string"}, handle_press_hotkey),
    ("mouse_click", "Clic souris.", {"x": "number", "y": "number", "button": "string"}, handle_mouse_click),
    # Clipboard (2)
    ("clipboard_get", "Lire le presse-papier.", {}, handle_clipboard_get),
    ("clipboard_set", "Ecrire dans le presse-papier.", {"text": "string"}, handle_clipboard_set),
    # Files (9)
    ("open_folder", "Ouvrir un dossier dans Explorer.", {"path": "string"}, handle_open_folder),
    ("list_folder", "Lister le contenu d'un dossier.", {"path": "string"}, handle_list_folder),
    ("create_folder", "Creer un dossier.", {"path": "string"}, handle_create_folder),
    ("copy_item", "Copier un fichier/dossier.", {"source": "string", "destination": "string"}, handle_copy_item),
    ("move_item", "Deplacer un fichier/dossier.", {"source": "string", "destination": "string"}, handle_move_item),
    ("delete_item", "Supprimer un fichier/dossier.", {"path": "string"}, handle_delete_item),
    ("read_text_file", "Lire un fichier texte.", {"path": "string"}, handle_read_text_file),
    ("write_text_file", "Ecrire un fichier texte.", {"path": "string", "content": "string"}, handle_write_text_file),
    ("search_files", "Chercher des fichiers.", {"path": "string", "pattern": "string"}, handle_search_files),
    # Audio (3)
    ("volume_up", "Augmenter le volume.", {}, handle_volume_up),
    ("volume_down", "Baisser le volume.", {}, handle_volume_down),
    ("volume_mute", "Couper/activer le son.", {}, handle_volume_mute),
    # Screen (2)
    ("screenshot", "Capture d'ecran.", {"path": "string"}, handle_screenshot),
    ("screen_resolution", "Resolution de l'ecran.", {}, handle_screen_resolution),
    # System (8)
    ("system_info", "Informations systeme.", {}, handle_system_info),
    ("gpu_info", "Informations GPU.", {}, handle_gpu_info),
    ("network_info", "Informations reseau.", {}, handle_network_info),
    ("powershell_run", "Executer une commande PowerShell.", {"command": "string"}, handle_powershell_run),
    ("lock_screen", "Verrouiller l'ecran.", {}, handle_lock_screen),
    ("shutdown_pc", "Eteindre le PC.", {"delay": "number"}, handle_shutdown_pc),
    ("restart_pc", "Redemarrer le PC.", {"delay": "number"}, handle_restart_pc),
    ("sleep_pc", "Mettre en veille.", {}, handle_sleep_pc),
    # Services (3)
    ("list_services", "Lister les services Windows.", {"filter": "string"}, handle_list_services),
    ("start_service", "Demarrer un service.", {"name": "string"}, handle_start_service),
    ("stop_service", "Arreter un service.", {"name": "string"}, handle_stop_service),
    # Network (3)
    ("wifi_networks", "Scanner les reseaux Wi-Fi.", {}, handle_wifi_networks),
    ("ping", "Ping un hote.", {"host": "string"}, handle_ping),
    ("get_ip", "Obtenir l'adresse IP.", {}, handle_get_ip),
    # Registry (2)
    ("registry_read", "Lire une valeur du registre.", {"path": "string", "name": "string"}, handle_registry_read),
    ("registry_write", "Ecrire une valeur dans le registre.", {"path": "string", "name": "string", "value": "string"}, handle_registry_write),
    # Notifications/Voice (3)
    ("notify", "Envoyer une notification Windows.", {"title": "string", "message": "string"}, handle_notify),
    ("speak", "Synthese vocale TTS.", {"text": "string"}, handle_speak),
    ("scheduled_tasks", "Lister les taches planifiees.", {}, handle_scheduled_tasks),
    # Trading Execution (5)
    ("trading_pending_signals", "Signaux trading en attente (score >= seuil, frais).", {"min_score": "number", "limit": "number"}, handle_trading_pending_signals),
    ("trading_execute_signal", "Executer un signal (dry_run par defaut).", {"signal_id": "number", "dry_run": "boolean"}, handle_trading_execute_signal),
    ("trading_positions", "Positions ouvertes sur MEXC Futures.", {}, handle_trading_positions),
    ("trading_status", "Status global du pipeline trading.", {}, handle_trading_status),
    ("trading_close_position", "Fermer une position ouverte.", {"symbol": "string"}, handle_trading_close_position),
    # Skills & Pipelines (5)
    ("list_skills", "Lister les skills/pipelines JARVIS appris.", {}, handle_list_skills),
    ("create_skill", "Creer un nouveau skill/pipeline.", {"name": "string", "description": "string", "triggers": "string", "steps": "json_array", "category": "string"}, handle_create_skill),
    ("remove_skill", "Supprimer un skill.", {"name": "string"}, handle_remove_skill),
    ("suggest_actions", "Suggerer des actions selon le contexte.", {"context": "string"}, handle_suggest_actions),
    ("action_history", "Historique des actions executees.", {"limit": "number"}, handle_action_history),
]

# Build handler map
HANDLERS: dict[str, Any] = {}
for name, desc, schema, handler in TOOL_DEFINITIONS:
    HANDLERS[name] = handler


def _build_input_schema(params: dict) -> dict:
    """Convert simple param dict to JSON Schema."""
    if not params:
        return {"type": "object", "properties": {}}
    props = {}
    for k, v in params.items():
        if v == "string":
            props[k] = {"type": "string"}
        elif v == "number":
            props[k] = {"type": "number"}
        elif v == "boolean":
            props[k] = {"type": "boolean"}
        else:
            props[k] = {"type": "string"}
    return {"type": "object", "properties": props}


# ═══════════════════════════════════════════════════════════════════════════
# MCP SERVER SETUP
# ═══════════════════════════════════════════════════════════════════════════

app = Server("jarvis")


@app.list_tools()
async def list_tools() -> list[Tool]:
    tools = []
    for name, desc, schema, _ in TOOL_DEFINITIONS:
        tools.append(Tool(
            name=name,
            description=desc,
            inputSchema=_build_input_schema(schema),
        ))
    return tools


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    handler = HANDLERS.get(name)
    if not handler:
        return _error(f"Outil inconnu: {name}")
    try:
        return await handler(arguments)
    except Exception as e:
        return _error(f"{name}: {e}")


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
