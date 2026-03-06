"""JARVIS MCP Server — Standalone stdio server (87 tools).

Run directly: python -m src.mcp_server
Used by the Claude Agent SDK as an external subprocess MCP server.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.mcp_server")

import httpx
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Shared httpx client — avoids creating/destroying connections per request.
# Individual calls override timeout via method kwarg when needed.
_http: httpx.AsyncClient | None = None
_http_lock = asyncio.Lock()


async def _get_http() -> httpx.AsyncClient:
    global _http
    async with _http_lock:
        if _http is None or _http.is_closed:
            _http = httpx.AsyncClient(
                timeout=120,
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=40),
            )
        return _http

# ── Config import (inline to avoid circular deps) ──────────────────────────

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
from src.config import config, SCRIPTS, PATHS, prepare_lmstudio_input, build_lmstudio_payload, build_ollama_payload
from src.security import sanitize_mcp_args, mcp_limiter, audit_log


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _text(text: str) -> list[TextContent]:
    return [TextContent(type="text", text=text)]


def _error(text: str) -> list[TextContent]:
    return [TextContent(type="text", text=f"ERREUR: {text}")]


def _safe_int(val, default: int) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


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


async def _run(func: Any, *args: Any) -> Any:
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
        c = await _get_http()
        r = await c.post(f"{node.url}/api/v1/chat", json=build_lmstudio_payload(
            model, prepare_lmstudio_input(args["prompt"], node.name, model),
            temperature=config.temperature, max_output_tokens=config.max_tokens,
        ), headers=node.auth_headers)
        r.raise_for_status()
        from src.tools import extract_lms_output
        return _text(f"[{node.name}/{model}] {extract_lms_output(r.json())}")
    except httpx.ConnectError:
        return _error(f"Noeud {node.name} hors ligne")
    except (httpx.HTTPError, OSError, KeyError, ValueError) as e:
        return _error(str(e))


async def handle_lm_models(args: dict) -> list[TextContent]:
    node = config.get_node(args.get("node", "M1"))
    if not node:
        return _error("Noeud inconnu")
    try:
        c = await _get_http()
        r = await c.get(f"{node.url}/api/v1/models", headers=node.auth_headers, timeout=10)
        r.raise_for_status()
        models = [m["key"] for m in r.json().get("models", []) if m.get("loaded_instances")]
        return _text(f"Modeles: {', '.join(models) if models else 'aucun'}")
    except (httpx.HTTPError, OSError, KeyError, json.JSONDecodeError) as e:
        return _error(str(e))


async def handle_lm_cluster_status(args: dict) -> list[TextContent]:
    results, online = [], 0
    total_nodes = len(config.lm_nodes) + len(config.ollama_nodes) + 1  # +1 for Gemini
    c = await _get_http()
    for n in config.lm_nodes:
        try:
            r = await c.get(f"{n.url}/api/v1/models", headers=n.auth_headers, timeout=5)
            r.raise_for_status()
            cnt = len([m for m in r.json().get("models", []) if m.get("loaded_instances")])
            results.append(f"  {n.name} ({n.role}): ONLINE — {cnt} modeles, {n.gpus} GPU, {n.vram_gb}GB VRAM")
            online += 1
        except (httpx.HTTPError, OSError) as exc:
            logger.debug("cluster_status %s offline: %s", n.name, exc)
            results.append(f"  {n.name} ({n.role}): OFFLINE")
    for n in config.ollama_nodes:
        try:
            r = await c.get(f"{n.url}/api/tags", timeout=5)
            r.raise_for_status()
            cnt = len(r.json().get("models", []))
            results.append(f"  {n.name} ({n.role}): ONLINE — {cnt} modeles [Ollama]")
            online += 1
        except (httpx.HTTPError, OSError) as exc:
            logger.debug("cluster_status %s offline: %s", n.name, exc)
            results.append(f"  {n.name} ({n.role}): OFFLINE [Ollama]")
    # Gemini check via simple proxy call
    try:
        proc = await asyncio.create_subprocess_exec(
            "node", config.gemini_node.proxy_path, "ping",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        _, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        if proc.returncode == 0:
            results.append(f"  GEMINI ({config.gemini_node.role}): ONLINE — {', '.join(config.gemini_node.models)} [Proxy]")
            online += 1
        else:
            results.append(f"  GEMINI ({config.gemini_node.role}): OFFLINE [Proxy]")
    except (asyncio.TimeoutError, FileNotFoundError, OSError) as exc:
        logger.debug("cluster_status GEMINI offline: %s", exc)
        results.append(f"  GEMINI ({config.gemini_node.role}): OFFLINE [Proxy]")
    header = f"Cluster: {online}/{total_nodes} noeuds en ligne"
    return _text(f"{header}\n" + "\n".join(results))


async def handle_system_audit(args: dict) -> list[TextContent]:
    """Full cluster audit — 10 sections + scores."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "system_audit",
        str(Path(__file__).parent.parent / "scripts" / "system_audit.py")
    )
    if spec is None or spec.loader is None:
        return _text("ERREUR: system_audit.py introuvable")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    mode = args.get("mode", "full")
    quick = mode == "quick"
    report = await mod.run_audit(quick=quick)
    text = mod.format_report(report)
    return _text(text)


async def handle_consensus(args: dict) -> list[TextContent]:
    from src.tools import extract_lms_output, _strip_thinking_tags
    prompt = args["prompt"]
    nodes = args.get("nodes", "M1,M2,OL1").split(",")
    per_timeout = _safe_int(args.get("timeout_per_node"), 60)
    responses = []

    async def _query_node(name: str) -> str:
        name = name.strip()
        upper = name.upper()

        if upper == "GEMINI":
            try:
                proc = await asyncio.create_subprocess_exec(
                    "node", config.gemini_node.proxy_path, prompt,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=per_timeout)
                output = stdout.decode(errors="replace").strip()
                if proc.returncode != 0 and not output:
                    return f"[GEMINI] ERREUR (exit {proc.returncode})"
                return f"[GEMINI/{config.gemini_node.default_model}] {_strip_thinking_tags(output)}"
            except asyncio.TimeoutError:
                return f"[GEMINI] TIMEOUT ({per_timeout}s)"
            except (OSError, ValueError) as e:
                return f"[GEMINI] ERREUR: {e}"

        ol_node = config.get_ollama_node(name)
        if ol_node:
            try:
                c = await _get_http()
                r = await asyncio.wait_for(c.post(f"{ol_node.url}/api/chat", json=build_ollama_payload(
                    ol_node.default_model, [{"role": "user", "content": prompt}],
                )), timeout=per_timeout)
                r.raise_for_status()
                text = _strip_thinking_tags(r.json()["message"]["content"])
                return f"[{ol_node.name}/Ollama] {text}"
            except asyncio.TimeoutError:
                return f"[{ol_node.name}/Ollama] TIMEOUT ({per_timeout}s)"
            except (httpx.HTTPError, OSError, KeyError, json.JSONDecodeError) as e:
                return f"[{ol_node.name}/Ollama] ERREUR: {e}"

        node = config.get_node(name)
        if not node:
            return f"[{name}] ERREUR: inconnu"
        input_text = prepare_lmstudio_input(prompt, node.name, node.default_model)

        try:
            c = await _get_http()
            r = await asyncio.wait_for(c.post(f"{node.url}/api/v1/chat", json=build_lmstudio_payload(
                node.default_model, input_text,
            ), headers=node.auth_headers), timeout=per_timeout)
            r.raise_for_status()
            text = extract_lms_output(r.json())
            return f"[{node.name}] {text}"
        except asyncio.TimeoutError:
            return f"[{name}] TIMEOUT ({per_timeout}s)"
        except (httpx.HTTPError, OSError, KeyError, ValueError) as e:
            return f"[{node.name}] ERREUR: {e}"

    results = await asyncio.gather(*[_query_node(n) for n in nodes], return_exceptions=True)
    for r in results:
        responses.append(str(r) if isinstance(r, Exception) else r)
    # Weighted voting info
    weights = config.node_weights
    weight_info = " | ".join(f"{n.strip()}={weights.get(n.strip(), 1.0)}" for n in nodes)
    return _text(f"Consensus ({len(responses)} sources, poids: {weight_info}):\n" + "\n---\n".join(responses))


# ── Gemini + Bridge handlers ─────────────────────────────────────────────

async def handle_gemini_query(args: dict) -> list[TextContent]:
    prompt = args["prompt"]
    json_mode = str(args.get("json_mode", "false")).lower() == "true"

    cmd = ["node", config.gemini_node.proxy_path]
    if json_mode:
        cmd.append("--json")
    cmd.append(prompt)

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=config.gemini_node.timeout_ms / 1000,
        )
        output = stdout.decode(errors="replace").strip()
        if proc.returncode != 0 and not output:
            err = stderr.decode(errors="replace").strip()
            return _error(f"Gemini erreur (exit {proc.returncode}): {err[:500]}")
        from src.tools import _strip_thinking_tags
        return _text(f"[GEMINI/{config.gemini_node.default_model}] {_strip_thinking_tags(output)}")
    except asyncio.TimeoutError:
        return _error(f"Gemini timeout ({config.gemini_node.timeout_ms / 1000}s)")
    except (OSError, ValueError) as e:
        return _error(f"Erreur Gemini: {e}")


async def handle_bridge_query(args: dict) -> list[TextContent]:
    prompt = args["prompt"]
    task_type = args.get("task_type", "short_answer")
    preferred = args.get("preferred_node", "")

    if preferred:
        nodes = [preferred] + [n for n in config.route(task_type) if n != preferred]
    else:
        nodes = config.route(task_type)
    if not nodes:
        nodes = ["M1"]

    c = await _get_http()
    for name in nodes:
        upper = name.upper()
        try:
            if upper == "GEMINI":
                result = await handle_gemini_query({"prompt": prompt})
                if result and not any("ERREUR" in tc.text for tc in result):
                    return result
                continue

            ol_node = config.get_ollama_node(name)
            if ol_node:
                r = await c.post(f"{ol_node.url}/api/chat", json=build_ollama_payload(
                    ol_node.default_model, [{"role": "user", "content": prompt}],
                ))
                r.raise_for_status()
                return _text(f"[{name}/{ol_node.default_model}] {r.json()['message']['content']}")

            node = config.get_node(name)
            if not node:
                continue
            input_text = prepare_lmstudio_input(prompt, node.name, node.default_model)
            r = await c.post(f"{node.url}/api/v1/chat", json=build_lmstudio_payload(
                node.default_model, input_text,
            ), headers=node.auth_headers)
            r.raise_for_status()
            from src.tools import extract_lms_output
            return _text(f"[{name}/{node.default_model}] {extract_lms_output(r.json())}")
        except (httpx.HTTPError, asyncio.TimeoutError, OSError) as exc:
            logger.debug("bridge_query %s failed: %s", name, exc)
            continue
    return _error(f"Tous les noeuds ont echoue: {nodes}")


async def handle_bridge_mesh(args: dict) -> list[TextContent]:
    prompt = args["prompt"]
    names = [n.strip() for n in args.get("nodes", "M1,M2,OL1,GEMINI").split(",")]
    per_timeout = _safe_int(args.get("timeout_per_node"), 60)
    responses = []
    ok_count = 0

    async def _query_one(name: str) -> str:
        upper = name.upper()
        try:
            if upper == "GEMINI":
                proc = await asyncio.create_subprocess_exec(
                    "node", config.gemini_node.proxy_path, prompt,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=per_timeout)
                output = stdout.decode(errors="replace").strip()
                if proc.returncode != 0 and not output:
                    return f"[GEMINI] ERREUR (exit {proc.returncode})"
                from src.tools import _strip_thinking_tags
                return f"[GEMINI/{config.gemini_node.default_model}] {_strip_thinking_tags(output)}"

            c = await _get_http()
            ol_node = config.get_ollama_node(name)
            if ol_node:
                r = await asyncio.wait_for(c.post(f"{ol_node.url}/api/chat", json=build_ollama_payload(
                    ol_node.default_model, [{"role": "user", "content": prompt}],
                )), timeout=per_timeout)
                r.raise_for_status()
                return f"[{name}/{ol_node.default_model}] {r.json()['message']['content']}"

            node = config.get_node(name)
            if not node:
                return f"[{name}] ERREUR: noeud inconnu"
            input_text = prepare_lmstudio_input(prompt, node.name, node.default_model)
            r = await asyncio.wait_for(c.post(f"{node.url}/api/v1/chat", json=build_lmstudio_payload(
                node.default_model, input_text,
            ), headers=node.auth_headers), timeout=per_timeout)
            r.raise_for_status()
            from src.tools import extract_lms_output
            return f"[{name}/{node.default_model}] {extract_lms_output(r.json())}"
        except asyncio.TimeoutError:
            return f"[{name}] TIMEOUT ({per_timeout}s)"
        except (httpx.HTTPError, OSError, KeyError, ValueError) as e:
            return f"[{name}] ERREUR: {e}"

    results = await asyncio.gather(*[_query_one(n) for n in names], return_exceptions=True)
    for r in results:
        text = str(r) if isinstance(r, Exception) else r
        responses.append(text)
        if "ERREUR" not in text and "TIMEOUT" not in text:
            ok_count += 1

    return _text(f"Bridge Mesh ({ok_count}/{len(names)} OK):\n\n" + "\n\n---\n\n".join(responses))


# ── Ollama handlers ─────────────────────────────────────────────────────

async def handle_ollama_query(args: dict) -> list[TextContent]:
    node = config.get_ollama_node("OL1")
    if not node:
        return _error("Noeud Ollama OL1 non configure")
    model = args.get("model", node.default_model)
    try:
        c = await _get_http()
        r = await c.post(f"{node.url}/api/chat", json={
            "model": model,
            "messages": [{"role": "user", "content": args["prompt"]}],
            "stream": False, "think": False,
            "options": {"temperature": config.temperature, "num_predict": config.max_tokens},
        })
        r.raise_for_status()
        return _text(f"[OL1/{model}] {r.json()['message']['content']}")
    except httpx.ConnectError:
        return _error("Ollama hors ligne (127.0.0.1:11434)")
    except (httpx.HTTPError, OSError, KeyError, json.JSONDecodeError) as e:
        return _error(str(e))


async def handle_ollama_models(args: dict) -> list[TextContent]:
    node = config.get_ollama_node("OL1")
    if not node:
        return _error("Noeud Ollama OL1 non configure")
    try:
        c = await _get_http()
        r = await c.get(f"{node.url}/api/tags", timeout=10)
        r.raise_for_status()
        models = [m["name"] for m in r.json().get("models", [])]
        return _text(f"Modeles Ollama: {', '.join(models) if models else 'aucun'}")
    except (httpx.HTTPError, OSError, KeyError, json.JSONDecodeError) as e:
        return _error(str(e))


async def handle_ollama_pull(args: dict) -> list[TextContent]:
    node = config.get_ollama_node("OL1")
    if not node:
        return _error("Noeud Ollama OL1 non configure")
    model_name = args["model_name"]
    try:
        c = await _get_http()
        r = await c.post(f"{node.url}/api/pull", json={"name": model_name, "stream": False}, timeout=600)
        r.raise_for_status()
        return _text(f"Modele '{model_name}' telecharge.")
    except (httpx.HTTPError, OSError) as e:
        return _error(str(e))


async def handle_ollama_status(args: dict) -> list[TextContent]:
    node = config.get_ollama_node("OL1")
    if not node:
        return _error("Noeud Ollama OL1 non configure")
    try:
        c = await _get_http()
        r = await c.get(f"{node.url}/api/tags", timeout=5)
        r.raise_for_status()
        data = r.json()
        models = [m["name"] for m in data.get("models", [])]
        return _text(
            f"Ollama OL1: ONLINE\n"
            f"  URL: {node.url}\n"
            f"  Modeles: {len(models)} ({', '.join(models) if models else 'aucun'})\n"
            f"  Role: {node.role}"
        )
    except httpx.ConnectError:
        return _error("Ollama OL1: OFFLINE")
    except (httpx.HTTPError, OSError, KeyError, json.JSONDecodeError) as e:
        return _error(str(e))


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
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        return _error(str(e))


async def handle_list_scripts(args: dict) -> list[TextContent]:
    lines = [f"  {k}: {v}" for k, v in SCRIPTS.items()]
    return _text(f"Scripts ({len(SCRIPTS)}):\n" + "\n".join(lines))


async def handle_trading_pipeline_v2(args: dict) -> list[TextContent]:
    """Pipeline GPU Trading AI v2.2 — 100 strategies + consensus 5 IA."""
    import subprocess
    script = SCRIPTS.get("trading_v2_pipeline")
    if not script or not script.exists():
        return _error("Script trading_v2_pipeline absent")
    cmd_args = [sys.executable, str(script)]
    coins = args.get("coins", 50)
    top = args.get("top", 5)
    cmd_args.extend(["--coins", str(coins), "--top", str(top)])
    if args.get("quick"):
        cmd_args.append("--quick")
    if args.get("no_ai"):
        cmd_args.append("--no-ai")
    if args.get("json_output"):
        cmd_args.append("--json")
    def _do():
        import os
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        r = subprocess.run(cmd_args, capture_output=True, text=True,
                           timeout=300, cwd=str(script.parent), env=env)
        return r.stdout[:5000] if r.returncode == 0 else f"ERREUR (exit={r.returncode}):\n{r.stderr[:2000]}"
    try:
        return _text(await asyncio.to_thread(_do))
    except subprocess.TimeoutExpired:
        return _error("Timeout 300s: pipeline GPU v2.2")
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        return _error(str(e))


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
    cmd = args["command"]
    logger.info("[MCP] powershell_run invoked: %.200s", cmd)
    return _text(await _ps(cmd))

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
    text = str(args.get("text", ""))[:2000]
    # Single-quoted PS string: only ' needs escaping (doubled to '')
    safe = text.replace("'", "''")
    ps_cmd = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$s.Speak('{safe}')"
    )
    await _ps(ps_cmd)
    return _text(f"Parle: {text[:100]}")

async def handle_scheduled_tasks(args: dict) -> list[TextContent]:
    return _text(await _ps("Get-ScheduledTask | Where-Object {$_.State -ne 'Disabled'} | Select-Object TaskName, State, TaskPath | Format-Table -AutoSize | Out-String"))


# ── Trading execution tools ────────────────────────────────────────────────

async def handle_trading_pending_signals(args: dict) -> list[TextContent]:
    from src.trading import get_pending_signals
    min_score = args.get("min_score")
    limit = _safe_int(args.get("limit"), 10)
    signals = await _run(get_pending_signals, min_score, None, limit)
    return _text(json.dumps(signals, default=str, ensure_ascii=False, indent=2))


async def handle_trading_execute_signal(args: dict) -> list[TextContent]:
    from src.trading import execute_signal
    signal_id = _safe_int(args.get("signal_id"), 0)
    if not signal_id:
        return _error("signal_id must be a valid integer")
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

    # Parse steps: can be JSON array or pipe-separated string
    steps_raw = args.get("steps", "")
    if not steps_raw:
        return _error("Paramettre 'steps' requis.")

    # Try to parse as JSON array first
    try:
        steps_data = json.loads(steps_raw)
        if not isinstance(steps_data, list):
            steps_data = [steps_data]
    except (json.JSONDecodeError, ValueError):
        # Fallback: parse as pipe-separated string (simple tool names)
        steps_data = [{"tool": t.strip()} for t in steps_raw.split("|") if t.strip()]

    for s in steps_data:
        if isinstance(s, str):
            # Simple tool name
            steps.append(SkillStep(tool=s, args={}, description=""))
        elif isinstance(s, dict):
            # Complex step with args/description
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
    history = get_action_history(_safe_int(args.get("limit"), 20))
    if not history:
        return _text("Aucun historique d'actions.")
    lines = []
    for h in history[-10:]:
        status = "OK" if h.get("success") else "FAIL"
        lines.append(f"  [{status}] {h['action']}: {h['result'][:80]}")
    return _text(f"Historique ({len(history)} actions):\n" + "\n".join(lines))


# ── LM Studio MCP + Model Management + GPU + Benchmark ──────────────────

async def handle_lm_mcp_query(args: dict) -> list[TextContent]:
    from src.tools import extract_lms_output
    node = config.get_node(args.get("node", "M1"))
    if not node:
        return _error(f"Noeud inconnu: {args.get('node')}")
    model = args.get("model", node.default_model)
    server_names = [s.strip() for s in args.get("servers", "huggingface").split(",")]
    allowed_tools_raw = args.get("allowed_tools", "")
    allowed_tools = [t.strip() for t in allowed_tools_raw.split(",") if t.strip()] or None
    integrations = config.get_mcp_integrations(server_names, allowed_tools)
    if not integrations:
        return _error(f"Aucun serveur MCP valide: {server_names}")
    try:
        c = await _get_http()
        r = await c.post(f"{node.url}/api/v1/chat", json={
            "model": model, "input": args["prompt"],
            "integrations": integrations,
            "context_length": args.get("context_length", node.context_length),
            "temperature": config.temperature,
            "max_output_tokens": config.max_tokens,
            "stream": False, "store": False,
        }, headers=node.auth_headers)
        r.raise_for_status()
        data = r.json()
        content = extract_lms_output(data)
        tool_calls = [o for o in data.get("output", []) if isinstance(o, dict) and o.get("type") == "tool_call"]
        tc_info = f" | {len(tool_calls)} tool_call(s)" if tool_calls else ""
        return _text(f"[{node.name}/{model} +MCP:{','.join(server_names)}] {content}{tc_info}")
    except (httpx.HTTPError, OSError, KeyError, ValueError, json.JSONDecodeError) as e:
        return _error(str(e))


async def handle_lm_list_mcp_servers(args: dict) -> list[TextContent]:
    lines = []
    for name, srv in config.mcp_servers.items():
        stype = srv.get("type", "?")
        url = srv.get("server_url", srv.get("id", "?"))
        lines.append(f"  {name}: [{stype}] {url}")
    return _text("Serveurs MCP:\n" + "\n".join(lines))


async def handle_lm_load_model(args: dict) -> list[TextContent]:
    from src.cluster_startup import load_model_on_demand
    model = args["model"]
    context = _safe_int(args.get("context"), 16384)
    parallel = _safe_int(args.get("parallel"), 2)
    result = await load_model_on_demand(model, context=context, parallel=parallel)
    if result["ok"]:
        bench = result.get("bench", {})
        return _text(f"Modele {model} charge — {bench.get('latency_ms', '?')}ms warmup")
    return _error(f"Echec chargement {model}: {result.get('status', '?')}")


async def handle_lm_unload_model(args: dict) -> list[TextContent]:
    from src.cluster_startup import _lms_unload
    model = args["model"]
    ok = await _run(_lms_unload, model)
    return _text(f"Modele {model} {'decharge' if ok else 'echec decharge'}")


async def handle_lm_switch_coder(args: dict) -> list[TextContent]:
    from src.cluster_startup import switch_to_coder_mode
    result = await switch_to_coder_mode()
    return _text(f"Mode coder: {result['status']}") if result["ok"] else _error(f"Echec: {result['status']}")


async def handle_lm_switch_dev(args: dict) -> list[TextContent]:
    from src.cluster_startup import switch_to_dev_mode
    result = await switch_to_dev_mode()
    return _text(f"Mode dev: {result['status']}") if result["ok"] else _error(f"Echec: {result['status']}")


async def handle_lm_gpu_stats(args: dict) -> list[TextContent]:
    from src.cluster_startup import _get_gpu_stats
    gpus = await _run(_get_gpu_stats)
    if not gpus:
        return _error("nvidia-smi non disponible")
    lines = []
    total_used = sum(g["vram_used_mb"] for g in gpus)
    total_avail = sum(g["vram_total_mb"] for g in gpus)
    lines.append(f"VRAM Total: {total_used}MB / {total_avail}MB ({round(total_used/max(total_avail,1)*100)}%)")
    for g in gpus:
        bar = "#" * int(g["vram_pct"] / 5) + "." * (20 - int(g["vram_pct"] / 5))
        lines.append(f"GPU{g['index']} {g['name']} [{bar}] {g['vram_used_mb']}MB/{g['vram_total_mb']}MB ({g['vram_pct']}%)")
    return _text("\n".join(lines))


async def handle_lm_benchmark(args: dict) -> list[TextContent]:
    from src.cluster_startup import _warmup_model, _warmup_ollama
    nodes = [n.strip() for n in args.get("nodes", "M1,M2,OL1").split(",")]
    results = []
    for name in nodes:
        ol = config.get_ollama_node(name)
        if ol:
            bench = await _warmup_ollama(ol.url, ol.default_model)
            results.append(f"  {name} (Ollama/{ol.default_model}): {'OK' if bench['ok'] else 'ECHEC'} — {bench['latency_ms']}ms")
            continue
        node = config.get_node(name)
        if node:
            bench = await _warmup_model(node.url, node.default_model)
            if bench["ok"]:
                results.append(f"  {name} ({node.default_model}): OK — {bench['latency_ms']}ms, {bench['tokens_per_sec']} tok/s")
            else:
                results.append(f"  {name}: ECHEC — {bench.get('error', '?')}")
    return _text("Benchmark:\n" + "\n".join(results))


# ── Ollama Cloud tools ──────────────────────────────────────────────────

async def _ollama_cloud_query_mcp(prompt: str, model: str, timeout: float = 60.0, system: str | None = None) -> str:
    """Query Ollama cloud model for mcp_server handlers."""
    node = config.get_ollama_node("OL1")
    if not node:
        raise ConnectionError("Ollama OL1 non configure")
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    c = await _get_http()
    r = await c.post(f"{node.url}/api/chat", json={
        "model": model, "messages": messages,
        "stream": False, "think": False,
        "options": {"temperature": 0.3, "num_predict": config.max_tokens},
    }, timeout=timeout)
    r.raise_for_status()
    return r.json()["message"].get("content", "")


async def handle_ollama_web_search(args: dict) -> list[TextContent]:
    model = args.get("model", "minimax-m2.5:cloud")
    system = "Tu es un assistant de recherche. Utilise ta capacite de recherche web. Reponds en francais avec des donnees precises."
    try:
        result = await _ollama_cloud_query_mcp(args["query"], model, timeout=60, system=system)
        return _text(f"[WEB/{model}] {result}")
    except (httpx.HTTPError, OSError, KeyError, ValueError, json.JSONDecodeError) as e:
        return _error(f"Erreur web search: {e}")


async def handle_ollama_subagents(args: dict) -> list[TextContent]:
    task = args["task"]
    aspects_raw = args.get("aspects", "")
    aspects = [a.strip() for a in aspects_raw.split(",")][:3] if aspects_raw else ["analyse technique", "donnees actuelles", "recommandation"]
    while len(aspects) < 3:
        aspects.append(f"perspective {len(aspects)+1}")
    cloud_models = ["minimax-m2.5:cloud", "glm-5:cloud", "kimi-k2.5:cloud"]
    system = "Tu es un sous-agent specialise. Analyse le sujet sous l'angle specifie. Sois precis, concis. Reponds en francais."

    async def _run_agent(model: str, aspect: str) -> str:
        prompt = f"TACHE: {task}\nANGLE: {aspect}\n\nAnalyse ce sujet sous cet angle."
        try:
            result = await _ollama_cloud_query_mcp(prompt, model, timeout=90, system=system)
            return f"[{model.split(':')[0].upper()} — {aspect}]\n{result}"
        except (httpx.HTTPError, OSError, ValueError, json.JSONDecodeError) as e:
            return f"[{model}] Erreur: {e}"

    results = await asyncio.gather(*[_run_agent(cloud_models[i % 3], aspects[i]) for i in range(len(aspects))])
    output_parts = [str(r) if isinstance(r, Exception) else r for r in results]
    return _text(f"=== SOUS-AGENTS OLLAMA ({len(aspects)} paralleles) ===\n\n" + "\n\n---\n\n".join(output_parts))


async def handle_ollama_trading_analysis(args: dict) -> list[TextContent]:
    pair = args.get("pair", "BTC/USDT")
    timeframe = args.get("timeframe", "1h")
    agents_config = [
        ("minimax-m2.5:cloud", "SCANNER", f"Recherche les dernieres donnees de marche pour {pair}. Prix actuel, volume 24h, variation."),
        ("glm-5:cloud", "ANALYSTE", f"Analyse technique de {pair} en {timeframe}. RSI, MACD, supports/resistances."),
        ("kimi-k2.5:cloud", "STRATEGE", f"Recommandation trading pour {pair} en {timeframe}. Entry, TP, SL, score 0-100."),
    ]
    system = "Tu es un expert trading crypto. Reponds en francais, sois precis et concis."

    async def _run(model: str, role: str, prompt: str) -> str:
        try:
            result = await _ollama_cloud_query_mcp(prompt, model, timeout=90, system=system)
            return f"[{role}] {result}"
        except (httpx.HTTPError, OSError, ValueError, json.JSONDecodeError) as e:
            return f"[{role}] Erreur: {e}"

    results = await asyncio.gather(*[_run(m, r, p) for m, r, p in agents_config])
    return _text(f"=== TRADING ANALYSIS {pair} ({timeframe}) — 3 AGENTS ===\n\n" + "\n\n---\n\n".join(results))


# ── Brain (Autonomous Learning) ──────────────────────────────────────────

async def handle_brain_status(args: dict) -> list[TextContent]:
    from src.brain import format_brain_report
    return _text(await _run(format_brain_report))

async def handle_brain_analyze(args: dict) -> list[TextContent]:
    from src.brain import analyze_and_learn
    auto_raw = args.get("auto_create", "false")
    # Accepte booléen ET string ("true"/"false")
    if isinstance(auto_raw, bool):
        auto = auto_raw
    else:
        auto = str(auto_raw).lower() == "true"
    min_conf = float(args.get("min_confidence", 0.6))
    report = await _run(analyze_and_learn, auto, min_conf)
    lines = [
        f"Analyse cerveau JARVIS:",
        f"  Patterns detectes: {report['patterns_found']}",
        f"  Skills total: {report['total_skills']}",
        f"  Historique: {report['history_size']} actions",
    ]
    if report["patterns"]:
        lines.append("  Patterns:")
        for p in report["patterns"]:
            lines.append(f"    - {p['suggested_name']}: {p['count']}x (conf={p['confidence']:.0%})")
            lines.append(f"      Actions: {', '.join(p['actions'][:3])}")
    if report["skills_created"]:
        lines.append(f"  Skills auto-crees: {', '.join(report['skills_created'])}")
    return _text("\n".join(lines))

async def handle_brain_suggest(args: dict) -> list[TextContent]:
    from src.brain import cluster_suggest_skill
    context = args.get("context", "general")
    node_url = args.get("node_url", "http://127.0.0.1:1234")
    suggestion = await cluster_suggest_skill(context, node_url)
    if suggestion is None:
        return _text("Pas de suggestion disponible (cluster IA injoignable).")
    return _text(json.dumps(suggestion, ensure_ascii=False, indent=2))

async def handle_brain_learn(args: dict) -> list[TextContent]:
    """Auto-detect patterns and create skills if confident enough."""
    from src.brain import analyze_and_learn
    report = await _run(analyze_and_learn, True, 0.5)
    if report["skills_created"]:
        return _text(f"Skills auto-appris: {', '.join(report['skills_created'])}. "
                     f"Total: {report['total_skills']} skills.")
    elif report["patterns"]:
        return _text(f"{report['patterns_found']} patterns detectes mais confiance insuffisante. "
                     f"Continue a utiliser JARVIS pour renforcer les patterns.")
    else:
        return _text("Pas assez d'historique pour apprendre. Continue a utiliser JARVIS.")


# ── Domino Executor handlers ───────────────────────────────────────────────

def _domino_run_sync(domino_id: str) -> dict:
    """Run a domino pipeline synchronously (for thread pool)."""
    from src.domino_pipelines import find_domino, DOMINO_PIPELINES
    from src.domino_executor import DominoExecutor

    # Find by ID or trigger text
    domino = None
    for d in DOMINO_PIPELINES:
        if d.id == domino_id:
            domino = d
            break
    if not domino:
        domino = find_domino(domino_id)
    if not domino:
        return {"error": f"Domino introuvable: {domino_id}"}

    executor = DominoExecutor()
    return executor.run(domino)


async def handle_execute_domino(args: dict) -> list[TextContent]:
    """Execute un domino pipeline par ID ou texte de trigger."""
    domino_id = args.get("domino_id", "").strip()
    if not domino_id:
        return _error("domino_id requis (ID ou texte de commande)")
    try:
        result = await asyncio.to_thread(_domino_run_sync, domino_id)
        if "error" in result:
            return _error(result["error"])
        summary = (
            f"Domino {result['domino_id']} — "
            f"{result['passed']} PASS / {result['failed']} FAIL / {result['skipped']} SKIP "
            f"({result['total_steps']} steps en {result['total_ms']:.0f}ms)"
        )
        return _text(summary)
    except (ImportError, OSError, ValueError, RuntimeError) as e:
        return _error(f"Domino execution failed: {e}")


async def handle_list_dominos(args: dict) -> list[TextContent]:
    """Liste tous les domino pipelines disponibles."""
    try:
        from src.domino_pipelines import DOMINO_PIPELINES
        category = args.get("category", "").strip().lower()
        dominos = DOMINO_PIPELINES
        if category:
            dominos = [d for d in dominos if d.category == category]
        lines = [f"{len(dominos)} dominos" + (f" (categorie: {category})" if category else "") + ":"]
        for d in dominos:
            triggers = ", ".join(d.triggers[:3]) if d.triggers else "—"
            lines.append(f"  {d.id} [{d.category}] {d.description} | triggers: {triggers} | {len(d.steps)} steps")
        return _text("\n".join(lines))
    except ImportError as e:
        return _error(f"domino_pipelines non disponible: {e}")


async def handle_domino_stats(args: dict) -> list[TextContent]:
    """Statistiques d'execution des dominos (historique SQLite)."""
    try:
        from src.domino_executor import DominoLogger
        db_logger = DominoLogger()
        limit = _safe_int(args.get("limit"), 20)
        with sqlite3.connect(db_logger.db_path) as conn:
            conn.row_factory = sqlite3.Row
            runs = conn.execute(
                "SELECT DISTINCT run_id, domino_id, MIN(ts) as started, COUNT(*) as steps, "
                "SUM(CASE WHEN status='PASS' THEN 1 ELSE 0 END) as passed, "
                "SUM(CASE WHEN status='FAIL' THEN 1 ELSE 0 END) as failed, "
                "SUM(duration_ms) as total_ms "
                "FROM domino_logs GROUP BY run_id ORDER BY started DESC LIMIT ?",
                (limit,)
            ).fetchall()
        if not runs:
            return _text("Aucun historique domino.")
        lines = [f"{len(runs)} dernieres executions:"]
        for r in runs:
            lines.append(
                f"  {r['domino_id']} | {r['passed']}/{r['steps']} PASS | "
                f"{r['failed']} FAIL | {r['total_ms']:.0f}ms | {r['started']}"
            )
        return _text("\n".join(lines))
    except (sqlite3.Error, ImportError, OSError) as e:
        return _error(f"domino_stats: {e}")


# ── Dictionary CRUD handler ────────────────────────────────────────────────

_DICT_VALID_CATS = {
    "system", "media", "navigation", "trading", "dev", "ia",
    "communication", "productivity", "entertainment", "accessibility",
    "fichiers", "daily", "cluster", "voice", "custom",
}
_DICT_VALID_ACTS = {
    "powershell", "curl", "python", "pipeline", "condition",
    "system", "media", "browser", "voice", "shortcut", "script",
}
_DICT_TABLES = {"pipeline_dictionary", "domino_chains", "voice_corrections"}
_SAFE_COL_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


async def handle_dict_crud(args: dict) -> list[TextContent]:
    import sqlite3 as _sql
    from datetime import datetime as _dt

    operation = (args.get("operation") or "").lower()
    table = (args.get("table") or "pipeline_dictionary").lower()
    data_raw = args.get("data", "{}")
    if isinstance(data_raw, str):
        try:
            data = json.loads(data_raw)
        except json.JSONDecodeError:
            return _error("data must be a valid JSON string")
    else:
        data = data_raw

    if table not in _DICT_TABLES:
        return _error(f"Invalid table: {table}. Valid: {sorted(_DICT_TABLES)}")

    db_path = str(Path(__file__).resolve().parent.parent / "data" / "etoile.db")
    if not Path(db_path).exists():
        return _error(f"Database not found: {db_path}")

    def _do():
        conn = _sql.connect(db_path)
        conn.row_factory = _sql.Row
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            if operation == "stats":
                counts = {}
                for t in _DICT_TABLES:
                    if not t.isidentifier():
                        raise ValueError(f"Unsafe table name: {t}")
                    counts[t] = conn.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
                return json.dumps(counts, indent=2)

            if operation == "search":
                q = (data.get("query") or "").lower().strip()
                limit = _safe_int(data.get("limit"), 20)
                if not q:
                    return "ERROR: data.query is required"
                if table == "pipeline_dictionary":
                    rows = conn.execute(
                        "SELECT * FROM pipeline_dictionary WHERE trigger_phrase LIKE ? OR pipeline_id LIKE ? LIMIT ?",
                        (f"%{q}%", f"%{q}%", limit)).fetchall()
                elif table == "domino_chains":
                    rows = conn.execute(
                        "SELECT * FROM domino_chains WHERE trigger_cmd LIKE ? OR next_cmd LIKE ? LIMIT ?",
                        (f"%{q}%", f"%{q}%", limit)).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM voice_corrections WHERE wrong LIKE ? OR correct LIKE ? LIMIT ?",
                        (f"%{q}%", f"%{q}%", limit)).fetchall()
                result = [dict(r) for r in rows]
                return json.dumps(result, ensure_ascii=False, indent=2, default=str) if result else "No results"

            if operation == "add":
                if table == "pipeline_dictionary":
                    trigger = (data.get("trigger_phrase") or data.get("name", "")).strip()
                    cat = data.get("category", "custom").lower()
                    act = data.get("action_type", "pipeline").lower()
                    if cat not in _DICT_VALID_CATS:
                        return f"ERROR: Invalid category: {cat}"
                    if act not in _DICT_VALID_ACTS:
                        return f"ERROR: Invalid action_type: {act}"
                    existing = conn.execute("SELECT id FROM pipeline_dictionary WHERE trigger_phrase = ?", (trigger,)).fetchone()
                    if existing:
                        return f"ERROR: Trigger '{trigger}' exists (id={existing['id']})"
                    pid = trigger.lower().replace(" ", "_")
                    conn.execute(
                        "INSERT INTO pipeline_dictionary (pipeline_id, trigger_phrase, steps, category, action_type, agents_involved, avg_duration_ms, usage_count, created_at) VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?)",
                        (pid, trigger, data.get("steps", ""), cat, act, data.get("agents_involved", ""), _dt.now().isoformat()))
                    conn.commit()
                    nid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                    return f"OK: Added id={nid}, trigger='{trigger}'"
                elif table == "domino_chains":
                    tc = data.get("trigger_cmd", "").strip()
                    nc = data.get("next_cmd", "").strip()
                    if not tc or not nc:
                        return "ERROR: trigger_cmd and next_cmd required"
                    conn.execute(
                        "INSERT INTO domino_chains (trigger_cmd, condition, next_cmd, delay_ms, auto, description) VALUES (?, ?, ?, ?, ?, ?)",
                        (tc, data.get("condition", ""), nc, _safe_int(data.get("delay_ms"), 0),
                         1 if data.get("auto", True) else 0, data.get("description", "")))
                    conn.commit()
                    nid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                    return f"OK: Added chain id={nid}, {tc} -> {nc}"
                else:
                    w = data.get("wrong", "").strip()
                    c = data.get("correct", "").strip()
                    if not w or not c:
                        return "ERROR: wrong and correct required"
                    ex = conn.execute("SELECT id FROM voice_corrections WHERE wrong = ?", (w,)).fetchone()
                    if ex:
                        conn.execute("UPDATE voice_corrections SET correct = ?, category = ? WHERE id = ?",
                                     (c, data.get("category", "general"), ex["id"]))
                        conn.commit()
                        return f"OK: Updated id={ex['id']}, '{w}' -> '{c}'"
                    conn.execute("INSERT INTO voice_corrections (wrong, correct, category, hit_count) VALUES (?, ?, ?, 0)",
                                 (w, c, data.get("category", "general")))
                    conn.commit()
                    nid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                    return f"OK: Added correction id={nid}, '{w}' -> '{c}'"

            if operation == "edit":
                rid = data.get("id")
                fields = data.get("fields", {})
                if not rid or not fields:
                    return "ERROR: data.id and data.fields required"
                bad = [k for k in fields if not _SAFE_COL_RE.match(k)]
                if bad:
                    return f"ERROR: Invalid column name(s): {bad}"
                sets = [f"{k} = ?" for k in fields]
                vals = list(fields.values()) + [int(rid)]
                cur = conn.execute(f"UPDATE [{table}] SET {', '.join(sets)} WHERE id = ?", vals)
                conn.commit()
                return f"OK: Updated {cur.rowcount} row(s) in {table}" if cur.rowcount else f"ERROR: No record id={rid}"

            if operation == "delete":
                rid = data.get("id")
                if not rid:
                    return "ERROR: data.id required"
                cur = conn.execute(f"DELETE FROM [{table}] WHERE id = ?", (int(rid),))
                conn.commit()
                return f"OK: Deleted {cur.rowcount} row(s)" if cur.rowcount else f"ERROR: No record id={rid}"

            return f"ERROR: Unknown operation: {operation}. Valid: add, edit, delete, search, stats"
        finally:
            conn.close()

    try:
        result = await asyncio.to_thread(_do)
        if result.startswith("ERROR:"):
            return _error(result[7:])
        return _text(result)
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as e:
        return _error(f"dict_crud: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# SECURITY & ANALYTICS HANDLERS (v10.6)
# ═══════════════════════════════════════════════════════════════════════════

async def handle_security_score(args: dict) -> list[TextContent]:
    from src.security import calculate_security_score
    result = await asyncio.to_thread(calculate_security_score)
    return _text(json.dumps(result, indent=2))


async def handle_security_audit_log(args: dict) -> list[TextContent]:
    limit = _safe_int(args.get("limit"), 50)
    severity = args.get("severity")
    events = await asyncio.to_thread(audit_log.get_recent, limit, severity)
    return _text(json.dumps(events, indent=2, default=str))


async def handle_security_scan(args: dict) -> list[TextContent]:
    """Scan for common security issues in the cluster configuration."""
    issues = []

    # Check for plaintext API keys in config
    from src.config import config as cfg
    for node in cfg.lm_nodes:
        if node.api_key and not node.api_key.startswith("enc:"):
            issues.append(f"WARNING: {node.name} API key stored in plaintext")

    # Check for open ports without auth
    if not any(n.api_key for n in cfg.lm_nodes):
        issues.append("WARNING: No LM Studio nodes use authentication")

    # Check Ollama (no auth by default)
    issues.append("INFO: Ollama (OL1) does not support authentication (local only)")

    # Check for .env file
    import pathlib
    env_path = pathlib.Path("F:/BUREAU/turbo/.env")
    if env_path.exists():
        issues.append("OK: .env file exists for secret management")
    else:
        issues.append("WARNING: No .env file found — secrets may be hardcoded")

    # Check encryption key
    from src.security import _FERNET_KEY_FILE
    if _FERNET_KEY_FILE.exists():
        issues.append("OK: Fernet encryption key exists")
    else:
        issues.append("WARNING: No encryption key — credentials not encrypted")

    from src.security import calculate_security_score
    score = calculate_security_score()

    return _text(json.dumps({
        "issues": issues,
        "score": score,
        "recommendations": [
            "Enable TLS between cluster nodes",
            "Rotate API keys every 24h",
            "Add CORS restrictions to WebSocket server",
            "Enable request signing for inter-node communication",
        ],
    }, indent=2))


async def handle_cluster_analytics(args: dict) -> list[TextContent]:
    """Cluster performance metrics from tool execution logs."""
    hours = _safe_int(args.get("hours"), 24)
    import time
    cutoff = time.time() - hours * 3600

    # Read from security audit log for now
    events = await asyncio.to_thread(audit_log.get_recent, 1000)
    tool_calls = [e for e in events if e["event_type"] == "tool_call" and e["timestamp"] > cutoff]
    errors = [e for e in events if e["event_type"] == "tool_error" and e["timestamp"] > cutoff]

    # Tool usage breakdown
    tool_usage: dict[str, int] = {}
    for e in tool_calls:
        t = e.get("tool_name", "unknown")
        tool_usage[t] = tool_usage.get(t, 0) + 1

    return _text(json.dumps({
        "period_hours": hours,
        "total_calls": len(tool_calls),
        "total_errors": len(errors),
        "error_rate": f"{len(errors) / max(1, len(tool_calls)) * 100:.1f}%",
        "tool_usage": dict(sorted(tool_usage.items(), key=lambda x: x[1], reverse=True)[:20]),
    }, indent=2))


async def handle_voice_analytics(args: dict) -> list[TextContent]:
    """Voice pipeline statistics."""
    from src.voice import _command_cache
    import threading

    cache_size = len(_command_cache)
    cache_max = 200

    # Get voice correction stats from etoile.db
    stats = {}
    try:
        def _get_stats():
            conn = sqlite3.connect("F:/BUREAU/turbo/data/etoile.db")
            try:
                corrections = conn.execute("SELECT COUNT(*) FROM voice_corrections").fetchone()[0]
                dominos = conn.execute("SELECT COUNT(*) FROM domino_chains").fetchone()[0]
                pipelines = conn.execute("SELECT COUNT(*) FROM pipeline_dictionary").fetchone()[0]
                top_corrections = conn.execute(
                    "SELECT wrong, correct, hit_count FROM voice_corrections ORDER BY hit_count DESC LIMIT 10"
                ).fetchall()
                return {
                    "total_corrections": corrections,
                    "total_dominos": dominos,
                    "total_pipelines": pipelines,
                    "top_corrections": [
                        {"wrong": r[0], "correct": r[1], "hits": r[2]}
                        for r in top_corrections
                    ],
                }
            finally:
                conn.close()
        stats = await asyncio.to_thread(_get_stats)
    except (sqlite3.Error, OSError):
        stats = {"error": "Could not read etoile.db"}

    return _text(json.dumps({
        "cache_size": cache_size,
        "cache_max": cache_max,
        "cache_hit_rate": f"{cache_size / max(1, cache_max) * 100:.0f}% capacity",
        **stats,
    }, indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# OBSERVABILITY (3) — v10.6
# ═══════════════════════════════════════════════════════════════════════════

async def handle_observability_report(args: dict) -> list[TextContent]:
    """Full observability matrix report."""
    from src.observability import observability_matrix
    report = observability_matrix.get_report()
    return _text(json.dumps(report, indent=2, default=str))


async def handle_observability_heatmap(args: dict) -> list[TextContent]:
    """Heatmap data for cluster metrics."""
    from src.observability import observability_matrix
    window = args.get("window", "5m")
    return _text(json.dumps(observability_matrix.get_heatmap(window), indent=2))


async def handle_observability_alerts(args: dict) -> list[TextContent]:
    """Active anomaly alerts."""
    from src.observability import observability_matrix
    threshold = float(args.get("threshold", 0.7))
    return _text(json.dumps(observability_matrix.get_alerts(threshold), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# DRIFT DETECTION (3) — v10.6
# ═══════════════════════════════════════════════════════════════════════════

async def handle_drift_check(args: dict) -> list[TextContent]:
    """Check model drift status."""
    from src.drift_detector import drift_detector
    return _text(json.dumps(drift_detector.get_report(), indent=2, default=str))


async def handle_drift_model_health(args: dict) -> list[TextContent]:
    """Health status for a specific model."""
    from src.drift_detector import drift_detector
    model = args.get("model", "")
    if not model:
        return _text(json.dumps(drift_detector.get_all_health(), indent=2, default=str))
    return _text(json.dumps(drift_detector.get_model_health(model), indent=2, default=str))


async def handle_drift_reroute(args: dict) -> list[TextContent]:
    """Suggest rerouting based on drift analysis."""
    from src.drift_detector import drift_detector
    task_type = args.get("task_type", "code")
    candidates = [c.strip() for c in args.get("candidates", "M1,M2,OL1,GEMINI").split(",")]
    reordered = drift_detector.suggest_rerouting(task_type, candidates)
    degraded = drift_detector.get_degraded_models()
    return _text(json.dumps({"task_type": task_type, "order": reordered, "degraded": degraded}))


# ═══════════════════════════════════════════════════════════════════════════
# AUTO-TUNE (3) — v10.6
# ═══════════════════════════════════════════════════════════════════════════

async def handle_auto_tune_status(args: dict) -> list[TextContent]:
    """Auto-tune scheduler status."""
    from src.auto_tune import auto_tune
    return _text(json.dumps(auto_tune.get_status(), indent=2))


async def handle_auto_tune_sample(args: dict) -> list[TextContent]:
    """Take a resource sample (CPU, GPU, memory)."""
    from src.auto_tune import auto_tune
    snap = await asyncio.to_thread(auto_tune.sample)
    return _text(json.dumps({
        "cpu": snap.cpu_percent, "memory": snap.memory_percent,
        "gpu_temp": snap.gpu_temp_c, "gpu_util": snap.gpu_util_percent,
        "vram_used_mb": snap.gpu_memory_used_mb, "vram_total_mb": snap.gpu_memory_total_mb,
    }))


async def handle_auto_tune_cooldown(args: dict) -> list[TextContent]:
    """Apply cooldown to a node."""
    from src.auto_tune import auto_tune
    node = args.get("node", "")
    seconds = float(args.get("seconds", 30))
    if not node:
        return _error("node parameter required")
    auto_tune.apply_cooldown(node, seconds)
    return _text(f"Node {node} in cooldown for {seconds}s")


# ═══════════════════════════════════════════════════════════════════════════
# TRADING V3 (3) — v10.6
# ═══════════════════════════════════════════════════════════════════════════

async def handle_trading_backtest_list(args: dict) -> list[TextContent]:
    """List saved backtest results."""
    from src.trading_engine import backtest_engine
    results = backtest_engine.list_results()
    return _text(json.dumps(results[:20], indent=2))


async def handle_trading_strategy_rankings(args: dict) -> list[TextContent]:
    """Get strategy rankings by performance."""
    from src.trading_engine import strategy_scorer
    top_n = _safe_int(args.get("top_n"), 10)
    return _text(json.dumps(strategy_scorer.get_strategy_rankings(top_n), indent=2))


async def handle_trading_flow_status(args: dict) -> list[TextContent]:
    """Active trading flow status."""
    from src.trading_engine import trading_flow
    return _text(json.dumps(trading_flow.get_active_flows(), indent=2, default=str))


# ═══════════════════════════════════════════════════════════════════════════
# INTENT CLASSIFIER (2) — v10.6
# ═══════════════════════════════════════════════════════════════════════════

async def handle_intent_classify(args: dict) -> list[TextContent]:
    """Classify voice/text intent."""
    from src.intent_classifier import intent_classifier
    text = args.get("text", "")
    if not text:
        return _error("text parameter required")
    results = intent_classifier.classify(text)
    return _text(json.dumps([
        {"intent": r.intent, "confidence": r.confidence, "entities": r.entities, "source": r.source}
        for r in results
    ], indent=2))


async def handle_intent_report(args: dict) -> list[TextContent]:
    """Intent classifier accuracy report."""
    from src.intent_classifier import intent_classifier
    return _text(json.dumps(intent_classifier.get_report(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# TOOL METRICS (3) — v10.6
# ═══════════════════════════════════════════════════════════════════════════

async def handle_tool_metrics_report(args: dict) -> list[TextContent]:
    """MCP tool performance metrics."""
    from src.tools import get_tool_metrics_report
    return _text(json.dumps(get_tool_metrics_report(), indent=2))


async def handle_cache_stats(args: dict) -> list[TextContent]:
    """Response cache statistics."""
    from src.tools import get_cache_stats
    return _text(json.dumps(get_cache_stats(), indent=2))


async def handle_cache_clear(args: dict) -> list[TextContent]:
    """Clear response cache."""
    from src.tools import clear_cache
    category = args.get("category")
    clear_cache(category)
    return _text(f"Cache cleared{' (' + category + ')' if category else ' (all)'}")


# ═══════════════════════════════════════════════════════════════════════════
# DATABASE MAINTENANCE (2) — v10.6
# ═══════════════════════════════════════════════════════════════════════════

async def handle_db_health(args: dict) -> list[TextContent]:
    """Database health check."""
    from src.database import get_db_health
    return _text(json.dumps(await asyncio.to_thread(get_db_health), indent=2))


async def handle_db_maintenance(args: dict) -> list[TextContent]:
    """Run database maintenance (VACUUM + ANALYZE)."""
    from src.database import auto_maintenance
    force = args.get("force", False)
    result = await asyncio.to_thread(auto_maintenance, force)
    return _text(json.dumps(result, indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# ORCHESTRATOR V2 — Phase 4
# ═══════════════════════════════════════════════════════════════════════════

async def handle_orch_dashboard(args: dict) -> list[TextContent]:
    """Full orchestrator_v2 dashboard (observability + drift + tune + routing + budget)."""
    from src.orchestrator_v2 import orchestrator_v2
    return _text(json.dumps(orchestrator_v2.get_dashboard(), indent=2, default=str))


async def handle_orch_node_stats(args: dict) -> list[TextContent]:
    """Per-node runtime statistics (calls, success rate, latency, tokens)."""
    from src.orchestrator_v2 import orchestrator_v2
    return _text(json.dumps(orchestrator_v2.get_node_stats(), indent=2, default=str))


async def handle_orch_budget(args: dict) -> list[TextContent]:
    """Token budget report for current session."""
    from src.orchestrator_v2 import orchestrator_v2
    return _text(json.dumps(orchestrator_v2.get_budget_report(), indent=2))


async def handle_orch_reset_budget(args: dict) -> list[TextContent]:
    """Reset session token budget counters."""
    from src.orchestrator_v2 import orchestrator_v2
    orchestrator_v2.reset_budget()
    return _text("Budget reset OK")


async def handle_orch_fallback(args: dict) -> list[TextContent]:
    """Get drift-aware fallback chain for a task type."""
    from src.orchestrator_v2 import orchestrator_v2
    task_type = args.get("task_type", "code")
    exclude = set(args.get("exclude", "").split(",")) - {""}
    chain = orchestrator_v2.fallback_chain(task_type, exclude=exclude)
    return _text(json.dumps({"task_type": task_type, "chain": chain}, indent=2))


async def handle_orch_best_node(args: dict) -> list[TextContent]:
    """Pick the best node for a task type using weighted scoring + drift filtering."""
    from src.orchestrator_v2 import orchestrator_v2, ROUTING_MATRIX
    task_type = args.get("task_type", "code")
    matrix_entry = ROUTING_MATRIX.get(task_type, ROUTING_MATRIX.get("simple", []))
    candidates = [n for n, _ in matrix_entry]
    best = orchestrator_v2.get_best_node(candidates, task_type)
    scores = {n: orchestrator_v2.weighted_score(n, task_type) for n in candidates}
    return _text(json.dumps({"task_type": task_type, "best": best, "scores": scores}, indent=2))


async def handle_orch_record_call(args: dict) -> list[TextContent]:
    """Manually record a call for a node (for testing/calibration)."""
    from src.orchestrator_v2 import orchestrator_v2
    node = args.get("node", "M1")
    latency_ms = float(args.get("latency_ms", 100))
    success = args.get("success", True)
    tokens = _safe_int(args.get("tokens"), 0)
    quality = float(args.get("quality", 1.0))
    orchestrator_v2.record_call(node, latency_ms, success, tokens, quality)
    return _text(f"Recorded call for {node}: {latency_ms}ms, success={success}, tokens={tokens}")


async def handle_orch_health(args: dict) -> list[TextContent]:
    """Cluster health score 0-100 (observability 40% + drift 30% + tune 30%)."""
    from src.orchestrator_v2 import orchestrator_v2
    score = orchestrator_v2.health_check()
    alerts = orchestrator_v2.get_alerts()
    return _text(json.dumps({"health_score": score, "alerts": alerts}, indent=2, default=str))


async def handle_orch_routing_matrix(args: dict) -> list[TextContent]:
    """Show the full routing matrix (task_type -> node preferences + weights)."""
    from src.orchestrator_v2 import ROUTING_MATRIX
    matrix = {k: [{"node": n, "weight": w} for n, w in v] for k, v in ROUTING_MATRIX.items()}
    return _text(json.dumps(matrix, indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# TASK QUEUE — Phase 4 Vague 2
# ═══════════════════════════════════════════════════════════════════════════

async def handle_task_enqueue(args: dict) -> list[TextContent]:
    """Add a task to the smart queue."""
    from src.task_queue import task_queue
    prompt = args.get("prompt", "")
    if not prompt:
        return _error("missing 'prompt'")
    task_id = task_queue.enqueue(
        prompt,
        task_type=args.get("task_type", "code"),
        priority=_safe_int(args.get("priority"), 5),
    )
    return _text(f"Task {task_id} enqueued")


async def handle_task_list(args: dict) -> list[TextContent]:
    """List pending tasks."""
    from src.task_queue import task_queue
    return _text(json.dumps(task_queue.list_pending(_safe_int(args.get("limit"), 20)), indent=2, default=str))


async def handle_task_status(args: dict) -> list[TextContent]:
    """Get task queue stats."""
    from src.task_queue import task_queue
    return _text(json.dumps(task_queue.get_stats(), indent=2))


async def handle_task_cancel(args: dict) -> list[TextContent]:
    """Cancel a pending task."""
    from src.task_queue import task_queue
    task_id = args.get("task_id", "")
    ok = task_queue.cancel(task_id)
    return _text(f"Task {task_id} {'cancelled' if ok else 'not found or not pending'}")


# ═══════════════════════════════════════════════════════════════════════════
# NOTIFICATIONS — Phase 4 Vague 2
# ═══════════════════════════════════════════════════════════════════════════

async def handle_notif_send(args: dict) -> list[TextContent]:
    """Send a notification."""
    from src.notifier import notifier
    message = args.get("message", "")
    if not message:
        return _error("missing 'message'")
    ok = await notifier.alert(message, level=args.get("level", "info"), source=args.get("source", "mcp"))
    return _text(f"Notification {'sent' if ok else 'rate-limited'}")


async def handle_notif_history(args: dict) -> list[TextContent]:
    """Get notification history."""
    from src.notifier import notifier
    return _text(json.dumps(notifier.get_history(_safe_int(args.get("limit"), 50)), indent=2))


async def handle_notif_stats(args: dict) -> list[TextContent]:
    """Get notification stats."""
    from src.notifier import notifier
    return _text(json.dumps(notifier.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# AUTONOMOUS LOOP — Phase 4 Vague 2
# ═══════════════════════════════════════════════════════════════════════════

async def handle_autonomous_status(args: dict) -> list[TextContent]:
    """Autonomous loop full status."""
    from src.autonomous_loop import autonomous_loop
    return _text(json.dumps(autonomous_loop.get_status(), indent=2, default=str))


async def handle_autonomous_events(args: dict) -> list[TextContent]:
    """Recent autonomous loop events."""
    from src.autonomous_loop import autonomous_loop
    return _text(json.dumps(autonomous_loop.get_events(_safe_int(args.get("limit"), 50)), indent=2, default=str))


async def handle_autonomous_toggle(args: dict) -> list[TextContent]:
    """Enable/disable an autonomous task."""
    from src.autonomous_loop import autonomous_loop
    name = args.get("task_name", "")
    enabled = args.get("enabled", True)
    autonomous_loop.enable(name, enabled)
    return _text(f"Task '{name}' {'enabled' if enabled else 'disabled'}")


# ═══════════════════════════════════════════════════════════════════════════
# AGENT MEMORY — Phase 4 Vague 3
# ═══════════════════════════════════════════════════════════════════════════

async def handle_memory_remember(args: dict) -> list[TextContent]:
    """Store a persistent memory."""
    from src.agent_memory import agent_memory
    content = args.get("content", "")
    if not content:
        return _error("missing 'content'")
    mem_id = agent_memory.remember(
        content,
        category=args.get("category", "general"),
        importance=float(args.get("importance", 1.0)),
    )
    return _text(f"Memory {mem_id} stored")


async def handle_memory_recall(args: dict) -> list[TextContent]:
    """Search memories by similarity."""
    from src.agent_memory import agent_memory
    query = args.get("query", "")
    if not query:
        return _error("missing 'query'")
    results = agent_memory.recall(
        query,
        limit=_safe_int(args.get("limit"), 5),
        category=args.get("category") or None,
    )
    return _text(json.dumps(results, indent=2))


async def handle_memory_list(args: dict) -> list[TextContent]:
    """List all memories."""
    from src.agent_memory import agent_memory
    return _text(json.dumps(
        agent_memory.list_all(args.get("category") or None, _safe_int(args.get("limit"), 50)),
        indent=2,
    ))


async def handle_memory_forget(args: dict) -> list[TextContent]:
    """Delete a memory by ID."""
    from src.agent_memory import agent_memory
    mem_id = _safe_int(args.get("memory_id"), 0)
    ok = agent_memory.forget(mem_id)
    return _text(f"Memory {mem_id} {'deleted' if ok else 'not found'}")


# ═══════════════════════════════════════════════════════════════════════════
# CONVERSATION STORE — Phase 4 Vague 4
# ═══════════════════════════════════════════════════════════════════════════

async def handle_conv_create(args: dict) -> list[TextContent]:
    """Create a new conversation."""
    from src.conversation_store import conversation_store
    conv_id = conversation_store.create(
        title=args.get("title", ""),
        source=args.get("source", "mcp"),
    )
    return _text(f"Conversation {conv_id} created")


async def handle_conv_add_turn(args: dict) -> list[TextContent]:
    """Add a turn to a conversation."""
    from src.conversation_store import conversation_store
    conv_id = args.get("conv_id", "")
    if not conv_id:
        return _error("missing 'conv_id'")
    turn_id = conversation_store.add_turn(
        conv_id, node=args.get("node", ""),
        prompt=args.get("prompt", ""), response=args.get("response", ""),
        latency_ms=float(args.get("latency_ms", 0)),
        tokens=_safe_int(args.get("tokens"), 0),
    )
    return _text(f"Turn {turn_id} added to conversation {conv_id}")


async def handle_conv_list(args: dict) -> list[TextContent]:
    """List recent conversations."""
    from src.conversation_store import conversation_store
    return _text(json.dumps(
        conversation_store.list_conversations(
            limit=_safe_int(args.get("limit"), 20),
            source=args.get("source") or None,
        ),
        indent=2, default=str,
    ))


async def handle_conv_stats(args: dict) -> list[TextContent]:
    """Conversation stats."""
    from src.conversation_store import conversation_store
    return _text(json.dumps(conversation_store.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# LOAD BALANCER — Phase 4 Vague 4
# ═══════════════════════════════════════════════════════════════════════════

async def handle_lb_pick(args: dict) -> list[TextContent]:
    """Pick best node via load balancer."""
    from src.load_balancer import load_balancer
    task_type = args.get("task_type", "code")
    node = load_balancer.pick(task_type)
    load_balancer.release(node)  # release immediately for MCP query
    return _text(json.dumps({"task_type": task_type, "selected_node": node}))


async def handle_lb_status(args: dict) -> list[TextContent]:
    """Load balancer status."""
    from src.load_balancer import load_balancer
    return _text(json.dumps(load_balancer.get_status(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# PROACTIVE AGENT — Phase 4 Vague 4
# ═══════════════════════════════════════════════════════════════════════════

async def handle_proactive_analyze(args: dict) -> list[TextContent]:
    """Run proactive analysis."""
    from src.proactive_agent import proactive_agent
    suggestions = await proactive_agent.analyze()
    return _text(json.dumps(suggestions, indent=2))


async def handle_proactive_dismiss(args: dict) -> list[TextContent]:
    """Dismiss a proactive suggestion."""
    from src.proactive_agent import proactive_agent
    key = args.get("key", "")
    proactive_agent.dismiss(key)
    return _text(f"Suggestion '{key}' dismissed")


# ═══════════════════════════════════════════════════════════════════════════
# AUTO-OPTIMIZER — Phase 5
# ═══════════════════════════════════════════════════════════════════════════

async def handle_optimizer_optimize(args: dict) -> list[TextContent]:
    """Run auto-optimization cycle."""
    from src.auto_optimizer import auto_optimizer
    adjustments = auto_optimizer.force_optimize()
    return _text(json.dumps(adjustments, indent=2, default=str))


async def handle_optimizer_history(args: dict) -> list[TextContent]:
    """Get optimization history."""
    from src.auto_optimizer import auto_optimizer
    limit = int(args.get("limit", 50))
    return _text(json.dumps(auto_optimizer.get_history(limit), indent=2, default=str))


async def handle_optimizer_stats(args: dict) -> list[TextContent]:
    """Get optimizer stats."""
    from src.auto_optimizer import auto_optimizer
    return _text(json.dumps(auto_optimizer.get_stats(), indent=2, default=str))


# ═══════════════════════════════════════════════════════════════════════════
# EVENT BUS — Phase 5
# ═══════════════════════════════════════════════════════════════════════════

async def handle_eventbus_emit(args: dict) -> list[TextContent]:
    """Emit an event on the bus."""
    from src.event_bus import event_bus
    event = args.get("event", "")
    data_str = args.get("data", "{}")
    try:
        data = json.loads(data_str)
    except Exception:
        data = {"raw": data_str}
    count = await event_bus.emit(event, data)
    return _text(f"Event '{event}' emitted to {count} handlers")


async def handle_eventbus_stats(args: dict) -> list[TextContent]:
    """Get event bus stats."""
    from src.event_bus import event_bus
    return _text(json.dumps(event_bus.get_stats(), indent=2, default=str))


# ═══════════════════════════════════════════════════════════════════════════
# METRICS AGGREGATOR — Phase 5
# ═══════════════════════════════════════════════════════════════════════════

async def handle_metrics_snapshot(args: dict) -> list[TextContent]:
    """Take a real-time metrics snapshot."""
    from src.metrics_aggregator import metrics_aggregator
    return _text(json.dumps(metrics_aggregator.snapshot(), indent=2, default=str))


async def handle_metrics_history(args: dict) -> list[TextContent]:
    """Get metrics history."""
    from src.metrics_aggregator import metrics_aggregator
    minutes = int(args.get("minutes", 60))
    return _text(json.dumps(metrics_aggregator.get_history(minutes), indent=2, default=str))


async def handle_metrics_summary(args: dict) -> list[TextContent]:
    """Get metrics aggregator summary."""
    from src.metrics_aggregator import metrics_aggregator
    return _text(json.dumps(metrics_aggregator.get_summary(), indent=2, default=str))


# ═══════════════════════════════════════════════════════════════════════════
# CONFIG MANAGER — Phase 7
# ═══════════════════════════════════════════════════════════════════════════

async def handle_config_get(args: dict) -> list[TextContent]:
    """Get a config value."""
    from src.config_manager import config_manager
    key = args.get("key", "")
    if key:
        return _text(json.dumps(config_manager.get(key), indent=2, default=str))
    return _text(json.dumps(config_manager.get_all(), indent=2, default=str))


async def handle_config_set(args: dict) -> list[TextContent]:
    """Set a config value."""
    from src.config_manager import config_manager
    key = args.get("key", "")
    value_str = args.get("value", "")
    try:
        value = json.loads(value_str)
    except Exception:
        value = value_str
    config_manager.set(key, value)
    return _text(f"Config '{key}' set to {value}")


async def handle_config_reload(args: dict) -> list[TextContent]:
    """Hot-reload config."""
    from src.config_manager import config_manager
    reloaded = config_manager.reload()
    return _text(f"Config reloaded: {reloaded}")


async def handle_config_stats(args: dict) -> list[TextContent]:
    """Config stats."""
    from src.config_manager import config_manager
    return _text(json.dumps(config_manager.get_stats(), indent=2, default=str))


# ═══════════════════════════════════════════════════════════════════════════
# AUDIT TRAIL — Phase 7
# ═══════════════════════════════════════════════════════════════════════════

async def handle_audit_log(args: dict) -> list[TextContent]:
    """Log an audit entry."""
    from src.audit_trail import audit_trail
    entry_id = audit_trail.log(
        action_type=args.get("action_type", "manual"),
        action=args.get("action", ""),
        source=args.get("source", "mcp"),
        details=json.loads(args.get("details", "{}")),
    )
    return _text(f"Audit logged: {entry_id}")


async def handle_audit_search(args: dict) -> list[TextContent]:
    """Search audit log."""
    from src.audit_trail import audit_trail
    results = audit_trail.search(
        action_type=args.get("action_type"),
        source=args.get("source"),
        query=args.get("query"),
        limit=int(args.get("limit", 20)),
    )
    return _text(json.dumps(results, indent=2, default=str))


async def handle_audit_stats(args: dict) -> list[TextContent]:
    """Audit stats."""
    from src.audit_trail import audit_trail
    return _text(json.dumps(audit_trail.get_stats(), indent=2, default=str))


# ═══════════════════════════════════════════════════════════════════════════
# CLUSTER DIAGNOSTICS — Phase 7
# ═══════════════════════════════════════════════════════════════════════════

async def handle_diagnostics_run(args: dict) -> list[TextContent]:
    """Run full cluster diagnostic."""
    from src.cluster_diagnostics import cluster_diagnostics
    report = cluster_diagnostics.run_diagnostic()
    return _text(json.dumps(report, indent=2, default=str))


async def handle_diagnostics_quick(args: dict) -> list[TextContent]:
    """Quick cluster status."""
    from src.cluster_diagnostics import cluster_diagnostics
    return _text(json.dumps(cluster_diagnostics.get_quick_status(), indent=2, default=str))


async def handle_diagnostics_history(args: dict) -> list[TextContent]:
    """Diagnostic history."""
    from src.cluster_diagnostics import cluster_diagnostics
    return _text(json.dumps(cluster_diagnostics.get_history(), indent=2, default=str))


# ═══════════════════════════════════════════════════════════════════════════
# WORKFLOW ENGINE — Phase 6
# ═══════════════════════════════════════════════════════════════════════════

async def handle_workflow_create(args: dict) -> list[TextContent]:
    """Create a workflow."""
    from src.workflow_engine import workflow_engine
    steps = json.loads(args.get("steps", "[]"))
    wf_id = workflow_engine.create(args.get("name", "unnamed"), steps)
    return _text(f"Workflow created: {wf_id}")


async def handle_workflow_list(args: dict) -> list[TextContent]:
    """List workflows."""
    from src.workflow_engine import workflow_engine
    return _text(json.dumps(workflow_engine.list_workflows(int(args.get("limit", 20))), indent=2, default=str))


async def handle_workflow_execute(args: dict) -> list[TextContent]:
    """Execute a workflow."""
    from src.workflow_engine import workflow_engine
    wf_id = args.get("workflow_id", "")
    run_id = await workflow_engine.execute(wf_id)
    run = workflow_engine.get_run(run_id)
    return _text(json.dumps(run, indent=2, default=str))


async def handle_workflow_stats(args: dict) -> list[TextContent]:
    """Workflow engine stats."""
    from src.workflow_engine import workflow_engine
    return _text(json.dumps(workflow_engine.get_stats(), indent=2, default=str))


# ═══════════════════════════════════════════════════════════════════════════
# SESSION MANAGER — Phase 6
# ═══════════════════════════════════════════════════════════════════════════

async def handle_session_create(args: dict) -> list[TextContent]:
    """Create a session."""
    from src.session_manager import session_manager
    sid = session_manager.create(args.get("source", "mcp"))
    return _text(f"Session created: {sid}")


async def handle_session_context(args: dict) -> list[TextContent]:
    """Get session context."""
    from src.session_manager import session_manager
    sid = args.get("session_id", "")
    ctx = session_manager.get_context(sid)
    return _text(json.dumps(ctx, indent=2, default=str))


async def handle_session_list(args: dict) -> list[TextContent]:
    """List sessions."""
    from src.session_manager import session_manager
    return _text(json.dumps(session_manager.list_sessions(int(args.get("limit", 20))), indent=2, default=str))


async def handle_session_stats(args: dict) -> list[TextContent]:
    """Session stats."""
    from src.session_manager import session_manager
    return _text(json.dumps(session_manager.get_stats(), indent=2, default=str))


# ═══════════════════════════════════════════════════════════════════════════
# ALERT MANAGER — Phase 6
# ═══════════════════════════════════════════════════════════════════════════

async def handle_alert_fire(args: dict) -> list[TextContent]:
    """Fire an alert."""
    from src.alert_manager import alert_manager
    ok = await alert_manager.fire(
        key=args.get("key", ""), message=args.get("message", ""),
        level=args.get("level", "info"), source=args.get("source", "mcp"),
    )
    return _text(f"Alert fired: {ok}")


async def handle_alert_active(args: dict) -> list[TextContent]:
    """Get active alerts."""
    from src.alert_manager import alert_manager
    return _text(json.dumps(alert_manager.get_active(args.get("level")), indent=2, default=str))


async def handle_alert_acknowledge(args: dict) -> list[TextContent]:
    """Acknowledge an alert."""
    from src.alert_manager import alert_manager
    ok = alert_manager.acknowledge(args.get("key", ""))
    return _text(f"Acknowledged: {ok}")


async def handle_alert_resolve(args: dict) -> list[TextContent]:
    """Resolve an alert."""
    from src.alert_manager import alert_manager
    ok = alert_manager.resolve(args.get("key", ""))
    return _text(f"Resolved: {ok}")


async def handle_alert_stats(args: dict) -> list[TextContent]:
    """Alert stats."""
    from src.alert_manager import alert_manager
    return _text(json.dumps(alert_manager.get_stats(), indent=2, default=str))


# ═══════════════════════════════════════════════════════════════════════════
# RATE LIMITER — Phase 8
# ═══════════════════════════════════════════════════════════════════════════

async def handle_ratelimit_check(args: dict) -> list[TextContent]:
    """Check if a request to a node is allowed."""
    from src.rate_limiter import rate_limiter
    node = args.get("node", "M1")
    allowed = rate_limiter.allow(node)
    return _text(json.dumps({"node": node, "allowed": allowed}))


async def handle_ratelimit_stats(args: dict) -> list[TextContent]:
    """Rate limiter stats for all nodes."""
    from src.rate_limiter import rate_limiter
    return _text(json.dumps(rate_limiter.get_all_stats(), indent=2))


async def handle_ratelimit_configure(args: dict) -> list[TextContent]:
    """Configure rate limit for a node."""
    from src.rate_limiter import rate_limiter
    node = args.get("node", "M1")
    rps = float(args.get("rps", 10))
    burst = float(args.get("burst", rps * 2))
    rate_limiter.configure_node(node, rps, burst)
    return _text(f"Rate limit configured: {node} → {rps} rps, burst {burst}")


# ═══════════════════════════════════════════════════════════════════════════
# TASK SCHEDULER — Phase 8
# ═══════════════════════════════════════════════════════════════════════════

async def handle_scheduler_list(args: dict) -> list[TextContent]:
    """List scheduled jobs."""
    from src.task_scheduler import task_scheduler
    return _text(json.dumps(task_scheduler.list_jobs(), indent=2, default=str))


async def handle_scheduler_add(args: dict) -> list[TextContent]:
    """Add a scheduled job."""
    from src.task_scheduler import task_scheduler
    job_id = task_scheduler.add_job(
        name=args.get("name", "unnamed"),
        action=args.get("action", "noop"),
        interval_s=float(args.get("interval_s", 60)),
        params=json.loads(args.get("params", "{}")),
        one_shot=bool(args.get("one_shot", False)),
    )
    return _text(f"Job added: {job_id}")


async def handle_scheduler_remove(args: dict) -> list[TextContent]:
    """Remove a scheduled job."""
    from src.task_scheduler import task_scheduler
    ok = task_scheduler.remove_job(args.get("job_id", ""))
    return _text("Job removed" if ok else "Job not found")


async def handle_scheduler_stats(args: dict) -> list[TextContent]:
    """Scheduler stats."""
    from src.task_scheduler import task_scheduler
    return _text(json.dumps(task_scheduler.get_stats(), indent=2, default=str))


# ═══════════════════════════════════════════════════════════════════════════
# HEALTH DASHBOARD — Phase 8
# ═══════════════════════════════════════════════════════════════════════════

async def handle_health_full(args: dict) -> list[TextContent]:
    """Full health dashboard report."""
    from src.health_dashboard import health_dashboard
    return _text(json.dumps(health_dashboard.collect(), indent=2, default=str))


async def handle_health_summary(args: dict) -> list[TextContent]:
    """Lightweight health summary."""
    from src.health_dashboard import health_dashboard
    return _text(json.dumps(health_dashboard.get_summary(), indent=2, default=str))


async def handle_health_history(args: dict) -> list[TextContent]:
    """Health report history."""
    from src.health_dashboard import health_dashboard
    return _text(json.dumps(health_dashboard.get_history(), indent=2, default=str))


# ═══════════════════════════════════════════════════════════════════════════
# PLUGIN MANAGER — Phase 9
# ═══════════════════════════════════════════════════════════════════════════

async def handle_plugin_list(args: dict) -> list[TextContent]:
    """List loaded plugins."""
    from src.plugin_manager import plugin_manager
    return _text(json.dumps(plugin_manager.list_plugins(), indent=2, default=str))


async def handle_plugin_discover(args: dict) -> list[TextContent]:
    """Discover available plugins."""
    from src.plugin_manager import plugin_manager
    discovered = plugin_manager.discover()
    return _text(json.dumps(discovered))


async def handle_plugin_stats(args: dict) -> list[TextContent]:
    """Plugin manager stats."""
    from src.plugin_manager import plugin_manager
    return _text(json.dumps(plugin_manager.get_stats(), indent=2, default=str))


# ═══════════════════════════════════════════════════════════════════════════
# COMMAND ROUTER — Phase 9
# ═══════════════════════════════════════════════════════════════════════════

async def handle_cmd_route(args: dict) -> list[TextContent]:
    """Route a natural language command."""
    from src.command_router import command_router
    text = args.get("text", "")
    result = command_router.route(text)
    if result:
        return _text(json.dumps({
            "route": result.route.name,
            "score": round(result.score, 3),
            "matched_by": result.matched_by,
            "captures": result.captures,
        }))
    return _text(json.dumps({"route": None, "message": "No matching route"}))


async def handle_cmd_routes(args: dict) -> list[TextContent]:
    """List all command routes."""
    from src.command_router import command_router
    return _text(json.dumps(command_router.get_routes(), indent=2, default=str))


async def handle_cmd_stats(args: dict) -> list[TextContent]:
    """Command router stats."""
    from src.command_router import command_router
    return _text(json.dumps(command_router.get_stats(), indent=2, default=str))


# ═══════════════════════════════════════════════════════════════════════════
# RESOURCE MONITOR — Phase 9
# ═══════════════════════════════════════════════════════════════════════════

async def handle_resource_sample(args: dict) -> list[TextContent]:
    """Take a resource snapshot (CPU, RAM, GPU, Disk)."""
    from src.resource_monitor import resource_monitor
    snap = resource_monitor.sample()
    return _text(json.dumps(snap, indent=2, default=str))


async def handle_resource_latest(args: dict) -> list[TextContent]:
    """Get latest resource snapshot."""
    from src.resource_monitor import resource_monitor
    return _text(json.dumps(resource_monitor.get_latest(), indent=2, default=str))


async def handle_resource_stats(args: dict) -> list[TextContent]:
    """Resource monitor stats."""
    from src.resource_monitor import resource_monitor
    return _text(json.dumps(resource_monitor.get_stats(), indent=2, default=str))


# ═══════════════════════════════════════════════════════════════════════════
# CACHE MANAGER — Phase 11
# ═══════════════════════════════════════════════════════════════════════════

async def handle_cache_get(args: dict) -> list[TextContent]:
    """Get a cached value."""
    from src.cache_manager import cache_manager
    key = args.get("key", "")
    ns = args.get("namespace", "default")
    val = cache_manager.get(key, ns)
    return _text(json.dumps({"key": key, "value": val, "hit": val is not None}))


async def handle_cache_set(args: dict) -> list[TextContent]:
    """Set a cache value."""
    from src.cache_manager import cache_manager
    key = args.get("key", "")
    value = args.get("value", "")
    ns = args.get("namespace", "default")
    ttl = float(args.get("ttl_s", 300))
    cache_manager.set(key, value, ns, ttl)
    return _text(f"Cached: {key} in {ns}")


async def handle_cache_mgr_stats(args: dict) -> list[TextContent]:
    """Cache manager stats (L1/L2 hit rates)."""
    from src.cache_manager import cache_manager
    return _text(json.dumps(cache_manager.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# SECRET VAULT — Phase 11
# ═══════════════════════════════════════════════════════════════════════════

async def handle_vault_list(args: dict) -> list[TextContent]:
    """List secret keys (no values)."""
    from src.secret_vault import secret_vault
    return _text(json.dumps(secret_vault.list_entries(), indent=2, default=str))


async def handle_vault_stats(args: dict) -> list[TextContent]:
    """Vault stats."""
    from src.secret_vault import secret_vault
    return _text(json.dumps(secret_vault.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# DEPENDENCY GRAPH — Phase 11
# ═══════════════════════════════════════════════════════════════════════════

async def handle_depgraph_show(args: dict) -> list[TextContent]:
    """Show full dependency graph."""
    from src.dependency_graph import dep_graph
    return _text(json.dumps(dep_graph.get_graph(), indent=2))


async def handle_depgraph_impact(args: dict) -> list[TextContent]:
    """Impact analysis for a module."""
    from src.dependency_graph import dep_graph
    node = args.get("node", "")
    affected = dep_graph.impact_analysis(node)
    return _text(json.dumps({"node": node, "affected": affected, "count": len(affected)}))


async def handle_depgraph_order(args: dict) -> list[TextContent]:
    """Startup order (topological sort)."""
    from src.dependency_graph import dep_graph
    try:
        order = dep_graph.topological_sort()
        return _text(json.dumps(order))
    except ValueError as e:
        return _error(str(e))


async def handle_depgraph_stats(args: dict) -> list[TextContent]:
    """Dependency graph stats."""
    from src.dependency_graph import dep_graph
    return _text(json.dumps(dep_graph.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# RETRY MANAGER — Phase 10
# ═══════════════════════════════════════════════════════════════════════════

async def handle_retry_stats(args: dict) -> list[TextContent]:
    """Retry manager stats with circuit breaker states."""
    from src.retry_manager import retry_manager
    return _text(json.dumps(retry_manager.get_stats(), indent=2, default=str))


async def handle_retry_reset(args: dict) -> list[TextContent]:
    """Reset all circuit breakers."""
    from src.retry_manager import retry_manager
    retry_manager.reset_all()
    return _text("All circuit breakers reset")


# ═══════════════════════════════════════════════════════════════════════════
# DATA PIPELINE — Phase 10
# ═══════════════════════════════════════════════════════════════════════════

async def handle_data_pipeline_list(args: dict) -> list[TextContent]:
    """List data pipelines."""
    from src.data_pipeline import data_pipeline
    return _text(json.dumps(data_pipeline.list_pipelines(), indent=2, default=str))


async def handle_pipeline_history(args: dict) -> list[TextContent]:
    """Data pipeline execution history."""
    from src.data_pipeline import data_pipeline
    return _text(json.dumps(data_pipeline.get_history(), indent=2, default=str))


async def handle_pipeline_stats(args: dict) -> list[TextContent]:
    """Data pipeline stats."""
    from src.data_pipeline import data_pipeline
    return _text(json.dumps(data_pipeline.get_stats(), indent=2, default=str))


# ═══════════════════════════════════════════════════════════════════════════
# SERVICE REGISTRY — Phase 10
# ═══════════════════════════════════════════════════════════════════════════

async def handle_service_register(args: dict) -> list[TextContent]:
    """Register a service."""
    from src.service_registry import service_registry
    name = args.get("name", "")
    url = args.get("url", "")
    stype = args.get("service_type", "generic")
    service_registry.register(name, url, stype)
    return _text(f"Service '{name}' registered at {url}")


async def handle_service_list(args: dict) -> list[TextContent]:
    """List registered services."""
    from src.service_registry import service_registry
    return _text(json.dumps(service_registry.list_services(), indent=2, default=str))


async def handle_service_heartbeat(args: dict) -> list[TextContent]:
    """Send heartbeat for a service."""
    from src.service_registry import service_registry
    name = args.get("name", "")
    ok = service_registry.heartbeat(name)
    return _text(f"Heartbeat {'OK' if ok else 'FAIL'} for {name}")


async def handle_service_stats(args: dict) -> list[TextContent]:
    """Service registry stats."""
    from src.service_registry import service_registry
    return _text(json.dumps(service_registry.get_stats(), indent=2, default=str))


# ═══════════════════════════════════════════════════════════════════════════
# NOTIFICATION HUB — Phase 12
# ═══════════════════════════════════════════════════════════════════════════

async def handle_notif_channels(args: dict) -> list[TextContent]:
    """List notification channels."""
    from src.notification_hub import notification_hub
    return _text(json.dumps(notification_hub.get_channels(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# FEATURE FLAGS — Phase 12
# ═══════════════════════════════════════════════════════════════════════════

async def handle_flag_list(args: dict) -> list[TextContent]:
    """List all feature flags."""
    from src.feature_flags import feature_flags
    return _text(json.dumps(feature_flags.list_flags(), indent=2))


async def handle_flag_check(args: dict) -> list[TextContent]:
    """Check if a feature flag is enabled."""
    from src.feature_flags import feature_flags
    name = args.get("name", "")
    context = args.get("context")
    enabled = feature_flags.is_enabled(name, context)
    return _text(json.dumps({"flag": name, "enabled": enabled}))


async def handle_flag_toggle(args: dict) -> list[TextContent]:
    """Toggle a feature flag."""
    from src.feature_flags import feature_flags
    name = args.get("name", "")
    enabled = args.get("enabled")
    if enabled is not None:
        enabled = str(enabled).lower() in ("true", "1", "yes")
    ok = feature_flags.toggle(name, enabled)
    return _text(f"Flag '{name}' {'toggled' if ok else 'not found'}")


async def handle_flag_stats(args: dict) -> list[TextContent]:
    """Feature flag stats."""
    from src.feature_flags import feature_flags
    return _text(json.dumps(feature_flags.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# BACKUP MANAGER — Phase 12
# ═══════════════════════════════════════════════════════════════════════════

async def handle_backup_list(args: dict) -> list[TextContent]:
    """List all backups."""
    from src.backup_manager import backup_manager
    source = args.get("source")
    return _text(json.dumps(backup_manager.list_backups(source), indent=2, default=str))


async def handle_backup_create(args: dict) -> list[TextContent]:
    """Create a backup of a file."""
    from src.backup_manager import backup_manager
    from pathlib import Path
    source = args.get("source", "")
    tag = args.get("tag", "")
    entry = backup_manager.backup_file(Path(source), tag=tag)
    if entry:
        return _text(json.dumps({"backup_id": entry.backup_id, "status": entry.status, "size": entry.size_bytes}))
    return _text(json.dumps({"error": "Backup failed — source not found"}))


async def handle_backup_stats(args: dict) -> list[TextContent]:
    """Backup manager stats."""
    from src.backup_manager import backup_manager
    return _text(json.dumps(backup_manager.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# SESSION MANAGER V2 — Phase 13
# ═══════════════════════════════════════════════════════════════════════════

async def handle_session_v2_list(args: dict) -> list[TextContent]:
    """List sessions."""
    from src.session_manager_v2 import session_manager_v2
    owner = args.get("owner")
    status = args.get("status")
    return _text(json.dumps(session_manager_v2.list_sessions(owner, status), indent=2, default=str))


async def handle_session_v2_create(args: dict) -> list[TextContent]:
    """Create a new session."""
    from src.session_manager_v2 import session_manager_v2
    owner = args.get("owner", "anonymous")
    s = session_manager_v2.create(owner)
    return _text(json.dumps({"session_id": s.session_id, "owner": s.owner, "status": s.status}))


async def handle_session_v2_stats(args: dict) -> list[TextContent]:
    """Session manager stats."""
    from src.session_manager_v2 import session_manager_v2
    return _text(json.dumps(session_manager_v2.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# QUEUE MANAGER — Phase 13
# ═══════════════════════════════════════════════════════════════════════════

async def handle_queue_list(args: dict) -> list[TextContent]:
    """List queued tasks."""
    from src.queue_manager import queue_manager
    status = args.get("status")
    return _text(json.dumps(queue_manager.list_tasks(status), indent=2, default=str))


async def handle_queue_stats(args: dict) -> list[TextContent]:
    """Queue manager stats."""
    from src.queue_manager import queue_manager
    return _text(json.dumps(queue_manager.get_stats(), indent=2, default=str))


# ═══════════════════════════════════════════════════════════════════════════
# API GATEWAY — Phase 13
# ═══════════════════════════════════════════════════════════════════════════

async def handle_apigw_routes(args: dict) -> list[TextContent]:
    """List API gateway routes."""
    from src.api_gateway import api_gateway
    return _text(json.dumps(api_gateway.get_routes(), indent=2))


async def handle_apigw_clients(args: dict) -> list[TextContent]:
    """List API gateway clients."""
    from src.api_gateway import api_gateway
    return _text(json.dumps(api_gateway.get_clients(), indent=2))


async def handle_apigw_stats(args: dict) -> list[TextContent]:
    """API gateway stats."""
    from src.api_gateway import api_gateway
    return _text(json.dumps(api_gateway.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# TEMPLATE ENGINE — Phase 14
# ═══════════════════════════════════════════════════════════════════════════

async def handle_template_list(args: dict) -> list[TextContent]:
    """List registered templates."""
    from src.template_engine import template_engine
    return _text(json.dumps(template_engine.list_templates(), indent=2))


async def handle_template_render(args: dict) -> list[TextContent]:
    """Render a named template."""
    from src.template_engine import template_engine
    name = args.get("name", "")
    ctx = json.loads(args.get("context", "{}"))
    result = template_engine.render_named(name, ctx)
    if result is None:
        return _text(json.dumps({"error": f"Template '{name}' not found"}))
    return _text(result)


async def handle_template_stats(args: dict) -> list[TextContent]:
    """Template engine stats."""
    from src.template_engine import template_engine
    return _text(json.dumps(template_engine.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# STATE MACHINE — Phase 14
# ═══════════════════════════════════════════════════════════════════════════

async def handle_fsm_list(args: dict) -> list[TextContent]:
    """List all state machines."""
    from src.state_machine import state_machine_mgr
    return _text(json.dumps(state_machine_mgr.list_machines(), indent=2))


async def handle_fsm_stats(args: dict) -> list[TextContent]:
    """State machine stats."""
    from src.state_machine import state_machine_mgr
    return _text(json.dumps(state_machine_mgr.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# LOG AGGREGATOR — Phase 14
# ═══════════════════════════════════════════════════════════════════════════

async def handle_logagg_query(args: dict) -> list[TextContent]:
    """Query aggregated logs."""
    from src.log_aggregator import log_aggregator
    level = args.get("level")
    source = args.get("source")
    search = args.get("search")
    limit = int(args.get("limit", 50))
    return _text(json.dumps(log_aggregator.query(level=level, source=source, search=search, limit=limit), indent=2, default=str))


async def handle_logagg_sources(args: dict) -> list[TextContent]:
    """List log sources."""
    from src.log_aggregator import log_aggregator
    return _text(json.dumps(log_aggregator.get_sources()))


async def handle_logagg_stats(args: dict) -> list[TextContent]:
    """Log aggregator stats."""
    from src.log_aggregator import log_aggregator
    return _text(json.dumps(log_aggregator.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# PERMISSION MANAGER — Phase 15
# ═══════════════════════════════════════════════════════════════════════════

async def handle_perm_roles(args: dict) -> list[TextContent]:
    from src.permission_manager import permission_manager
    return _text(json.dumps(permission_manager.list_roles(), indent=2))


async def handle_perm_users(args: dict) -> list[TextContent]:
    from src.permission_manager import permission_manager
    return _text(json.dumps(permission_manager.list_users(), indent=2))


async def handle_perm_check(args: dict) -> list[TextContent]:
    from src.permission_manager import permission_manager
    user_id = args.get("user_id", "")
    perm = args.get("permission", "")
    allowed = permission_manager.check_permission(user_id, perm)
    return _text(json.dumps({"user_id": user_id, "permission": perm, "allowed": allowed}))


async def handle_perm_stats(args: dict) -> list[TextContent]:
    from src.permission_manager import permission_manager
    return _text(json.dumps(permission_manager.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# ENVIRONMENT MANAGER — Phase 15
# ═══════════════════════════════════════════════════════════════════════════

async def handle_env_profiles(args: dict) -> list[TextContent]:
    from src.env_manager import env_manager
    return _text(json.dumps(env_manager.list_profiles(), indent=2))


async def handle_env_get(args: dict) -> list[TextContent]:
    from src.env_manager import env_manager
    profile = args.get("profile")
    return _text(json.dumps(env_manager.get_profile(profile), indent=2))


async def handle_env_stats(args: dict) -> list[TextContent]:
    from src.env_manager import env_manager
    return _text(json.dumps(env_manager.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# TELEMETRY COLLECTOR — Phase 15
# ═══════════════════════════════════════════════════════════════════════════

async def handle_telemetry_counters(args: dict) -> list[TextContent]:
    from src.telemetry_collector import telemetry
    return _text(json.dumps(telemetry.get_counters(), indent=2))


async def handle_telemetry_gauges(args: dict) -> list[TextContent]:
    from src.telemetry_collector import telemetry
    return _text(json.dumps(telemetry.get_gauges(), indent=2))


async def handle_telemetry_stats(args: dict) -> list[TextContent]:
    from src.telemetry_collector import telemetry
    return _text(json.dumps(telemetry.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# EVENT STORE — Phase 16
# ═══════════════════════════════════════════════════════════════════════════

async def handle_evstore_streams(args: dict) -> list[TextContent]:
    from src.event_store import event_store
    return _text(json.dumps({"streams": event_store.streams()}, indent=2))


async def handle_evstore_events(args: dict) -> list[TextContent]:
    from src.event_store import event_store
    stream = args.get("stream")
    limit = int(args.get("limit", 50))
    if stream:
        events = event_store.get_stream(stream)[-limit:]
    else:
        events = event_store.get_all(limit=limit)
    return _text(json.dumps([
        {"id": e.event_id, "stream": e.stream, "type": e.event_type,
         "version": e.version, "data": e.data, "timestamp": e.timestamp}
        for e in events
    ], indent=2))


async def handle_evstore_stats(args: dict) -> list[TextContent]:
    from src.event_store import event_store
    return _text(json.dumps(event_store.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# WEBHOOK MANAGER — Phase 16
# ═══════════════════════════════════════════════════════════════════════════

async def handle_webhook_list(args: dict) -> list[TextContent]:
    from src.webhook_manager import webhook_manager
    return _text(json.dumps(webhook_manager.list_endpoints(), indent=2))


async def handle_webhook_history(args: dict) -> list[TextContent]:
    from src.webhook_manager import webhook_manager
    name = args.get("name")
    return _text(json.dumps(webhook_manager.get_history(webhook_name=name), indent=2))


async def handle_webhook_stats(args: dict) -> list[TextContent]:
    from src.webhook_manager import webhook_manager
    return _text(json.dumps(webhook_manager.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# HEALTH PROBE — Phase 16
# ═══════════════════════════════════════════════════════════════════════════

async def handle_hprobe_list(args: dict) -> list[TextContent]:
    from src.health_probe import health_probe
    return _text(json.dumps(health_probe.list_probes(), indent=2))


async def handle_hprobe_run(args: dict) -> list[TextContent]:
    from src.health_probe import health_probe
    name = args.get("name")
    if name:
        r = health_probe.run_check(name)
        if not r:
            return _text(json.dumps({"error": "probe not found"}))
        return _text(json.dumps({"name": r.name, "status": r.status.value,
                                  "latency_ms": r.latency_ms, "message": r.message}))
    results = health_probe.run_all()
    return _text(json.dumps([
        {"name": r.name, "status": r.status.value, "latency_ms": r.latency_ms, "message": r.message}
        for r in results
    ], indent=2))


async def handle_hprobe_stats(args: dict) -> list[TextContent]:
    from src.health_probe import health_probe
    return _text(json.dumps(health_probe.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# SERVICE MESH — Phase 17
# ═══════════════════════════════════════════════════════════════════════════

async def handle_mesh_services(args: dict) -> list[TextContent]:
    from src.service_mesh import service_mesh
    return _text(json.dumps(service_mesh.list_services(), indent=2))


async def handle_mesh_names(args: dict) -> list[TextContent]:
    from src.service_mesh import service_mesh
    return _text(json.dumps({"services": service_mesh.list_service_names()}, indent=2))


async def handle_mesh_stats(args: dict) -> list[TextContent]:
    from src.service_mesh import service_mesh
    return _text(json.dumps(service_mesh.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# CONFIG VAULT — Phase 17
# ═══════════════════════════════════════════════════════════════════════════

async def handle_cfgvault_namespaces(args: dict) -> list[TextContent]:
    from src.config_vault import config_vault
    return _text(json.dumps({"namespaces": config_vault.list_namespaces()}, indent=2))


async def handle_cfgvault_keys(args: dict) -> list[TextContent]:
    from src.config_vault import config_vault
    ns = args.get("namespace", "default")
    return _text(json.dumps({"namespace": ns, "keys": config_vault.list_keys(ns)}, indent=2))


async def handle_cfgvault_stats(args: dict) -> list[TextContent]:
    from src.config_vault import config_vault
    return _text(json.dumps(config_vault.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# RULE ENGINE — Phase 17
# ═══════════════════════════════════════════════════════════════════════════

async def handle_rules_list(args: dict) -> list[TextContent]:
    from src.rule_engine import rule_engine
    group = args.get("group")
    return _text(json.dumps(rule_engine.list_rules(group=group), indent=2))


async def handle_rules_groups(args: dict) -> list[TextContent]:
    from src.rule_engine import rule_engine
    return _text(json.dumps({"groups": rule_engine.list_groups()}, indent=2))


async def handle_rules_stats(args: dict) -> list[TextContent]:
    from src.rule_engine import rule_engine
    return _text(json.dumps(rule_engine.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# RETRY POLICY — Phase 18
# ═══════════════════════════════════════════════════════════════════════════

async def handle_retrypol_list(args: dict) -> list[TextContent]:
    from src.retry_policy import retry_manager
    return _text(json.dumps(retry_manager.list_policies(), indent=2))


async def handle_retrypol_history(args: dict) -> list[TextContent]:
    from src.retry_policy import retry_manager
    return _text(json.dumps(retry_manager.get_history(), indent=2))


async def handle_retrypol_stats(args: dict) -> list[TextContent]:
    from src.retry_policy import retry_manager
    return _text(json.dumps(retry_manager.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# MESSAGE BROKER — Phase 18
# ═══════════════════════════════════════════════════════════════════════════

async def handle_broker_topics(args: dict) -> list[TextContent]:
    from src.message_broker import message_broker
    return _text(json.dumps({"topics": message_broker.list_topics()}, indent=2))


async def handle_broker_messages(args: dict) -> list[TextContent]:
    from src.message_broker import message_broker
    topic = args.get("topic")
    return _text(json.dumps(message_broker.get_messages(topic=topic), indent=2))


async def handle_broker_stats(args: dict) -> list[TextContent]:
    from src.message_broker import message_broker
    return _text(json.dumps(message_broker.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# COMMAND REGISTRY — Phase 18
# ═══════════════════════════════════════════════════════════════════════════

async def handle_cmdreg_list(args: dict) -> list[TextContent]:
    from src.command_registry import command_registry
    cat = args.get("category")
    return _text(json.dumps(command_registry.list_commands(category=cat), indent=2))


async def handle_cmdreg_categories(args: dict) -> list[TextContent]:
    from src.command_registry import command_registry
    return _text(json.dumps({"categories": command_registry.list_categories()}, indent=2))


async def handle_cmdreg_stats(args: dict) -> list[TextContent]:
    from src.command_registry import command_registry
    return _text(json.dumps(command_registry.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# PROCESS MANAGER — Phase 19
# ═══════════════════════════════════════════════════════════════════════════

async def handle_procmgr_list(args: dict) -> list[TextContent]:
    from src.process_manager import process_manager
    group = args.get("group")
    return _text(json.dumps(process_manager.list_processes(group=group), indent=2))


async def handle_procmgr_events(args: dict) -> list[TextContent]:
    from src.process_manager import process_manager
    name = args.get("name")
    return _text(json.dumps(process_manager.get_events(name=name), indent=2))


async def handle_procmgr_stats(args: dict) -> list[TextContent]:
    from src.process_manager import process_manager
    return _text(json.dumps(process_manager.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# DATA VALIDATOR — Phase 19
# ═══════════════════════════════════════════════════════════════════════════

async def handle_dataval_schemas(args: dict) -> list[TextContent]:
    from src.data_validator import data_validator
    return _text(json.dumps(data_validator.list_schemas(), indent=2))


async def handle_dataval_history(args: dict) -> list[TextContent]:
    from src.data_validator import data_validator
    return _text(json.dumps(data_validator.get_history(), indent=2))


async def handle_dataval_stats(args: dict) -> list[TextContent]:
    from src.data_validator import data_validator
    return _text(json.dumps(data_validator.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# FILE WATCHER — Phase 19
# ═══════════════════════════════════════════════════════════════════════════

async def handle_fwatch_list(args: dict) -> list[TextContent]:
    from src.file_watcher import file_watcher
    group = args.get("group")
    return _text(json.dumps(file_watcher.list_watches(group=group), indent=2))


async def handle_fwatch_events(args: dict) -> list[TextContent]:
    from src.file_watcher import file_watcher
    name = args.get("watch_name")
    return _text(json.dumps(file_watcher.get_events(watch_name=name), indent=2))


async def handle_fwatch_stats(args: dict) -> list[TextContent]:
    from src.file_watcher import file_watcher
    return _text(json.dumps(file_watcher.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# CLIPBOARD MANAGER — Phase 20
# ═══════════════════════════════════════════════════════════════════════════

async def handle_clipmgr_history(args: dict) -> list[TextContent]:
    from src.clipboard_manager import clipboard_manager
    cat = args.get("category")
    return _text(json.dumps(clipboard_manager.get_history(category=cat), indent=2))


async def handle_clipmgr_search(args: dict) -> list[TextContent]:
    from src.clipboard_manager import clipboard_manager
    q = args.get("query", "")
    return _text(json.dumps(clipboard_manager.search(q), indent=2))


async def handle_clipmgr_stats(args: dict) -> list[TextContent]:
    from src.clipboard_manager import clipboard_manager
    return _text(json.dumps(clipboard_manager.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# SHORTCUT MANAGER — Phase 20
# ═══════════════════════════════════════════════════════════════════════════

async def handle_hotkey_list(args: dict) -> list[TextContent]:
    from src.shortcut_manager import shortcut_manager
    group = args.get("group")
    return _text(json.dumps(shortcut_manager.list_shortcuts(group=group), indent=2))


async def handle_hotkey_activations(args: dict) -> list[TextContent]:
    from src.shortcut_manager import shortcut_manager
    name = args.get("name")
    return _text(json.dumps(shortcut_manager.get_activations(name=name), indent=2))


async def handle_hotkey_stats(args: dict) -> list[TextContent]:
    from src.shortcut_manager import shortcut_manager
    return _text(json.dumps(shortcut_manager.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# SNAPSHOT MANAGER — Phase 20
# ═══════════════════════════════════════════════════════════════════════════

async def handle_snapmgr_list(args: dict) -> list[TextContent]:
    from src.snapshot_manager import snapshot_manager
    tag = args.get("tag")
    return _text(json.dumps(snapshot_manager.list_snapshots(tag=tag), indent=2))


async def handle_snapmgr_restores(args: dict) -> list[TextContent]:
    from src.snapshot_manager import snapshot_manager
    return _text(json.dumps(snapshot_manager.get_restore_history(), indent=2))


async def handle_snapmgr_stats(args: dict) -> list[TextContent]:
    from src.snapshot_manager import snapshot_manager
    return _text(json.dumps(snapshot_manager.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# NETWORK SCANNER — Phase 21
# ═══════════════════════════════════════════════════════════════════════════

async def handle_netscan_profiles(args: dict) -> list[TextContent]:
    from src.network_scanner import network_scanner
    return _text(json.dumps(network_scanner.list_profiles(), indent=2))


async def handle_netscan_history(args: dict) -> list[TextContent]:
    from src.network_scanner import network_scanner
    return _text(json.dumps(network_scanner.get_history(), indent=2))


async def handle_netscan_stats(args: dict) -> list[TextContent]:
    from src.network_scanner import network_scanner
    return _text(json.dumps(network_scanner.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# CRON MANAGER — Phase 21
# ═══════════════════════════════════════════════════════════════════════════

async def handle_cron_list(args: dict) -> list[TextContent]:
    from src.cron_manager import cron_manager
    group = args.get("group")
    return _text(json.dumps(cron_manager.list_jobs(group=group), indent=2))


async def handle_cron_executions(args: dict) -> list[TextContent]:
    from src.cron_manager import cron_manager
    name = args.get("name")
    return _text(json.dumps(cron_manager.get_executions(name=name), indent=2))


async def handle_cron_stats(args: dict) -> list[TextContent]:
    from src.cron_manager import cron_manager
    return _text(json.dumps(cron_manager.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# APP LAUNCHER — Phase 21
# ═══════════════════════════════════════════════════════════════════════════

async def handle_applnch_list(args: dict) -> list[TextContent]:
    from src.app_launcher import app_launcher
    group = args.get("group")
    return _text(json.dumps(app_launcher.list_apps(group=group), indent=2))


async def handle_applnch_history(args: dict) -> list[TextContent]:
    from src.app_launcher import app_launcher
    name = args.get("app_name")
    return _text(json.dumps(app_launcher.get_history(app_name=name), indent=2))


async def handle_applnch_stats(args: dict) -> list[TextContent]:
    from src.app_launcher import app_launcher
    return _text(json.dumps(app_launcher.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# EMAIL SENDER — Phase 22
# ═══════════════════════════════════════════════════════════════════════════

async def handle_emailsend_list(args: dict) -> list[TextContent]:
    from src.email_sender import email_sender
    status = args.get("status")
    return _text(json.dumps(email_sender.list_messages(status=status), indent=2))


async def handle_emailsend_templates(args: dict) -> list[TextContent]:
    from src.email_sender import email_sender
    return _text(json.dumps(email_sender.list_templates(), indent=2))


async def handle_emailsend_stats(args: dict) -> list[TextContent]:
    from src.email_sender import email_sender
    return _text(json.dumps(email_sender.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# SYSTEM PROFILER — Phase 22
# ═══════════════════════════════════════════════════════════════════════════

async def handle_sysprof_profiles(args: dict) -> list[TextContent]:
    from src.system_profiler import system_profiler
    tag = args.get("tag")
    return _text(json.dumps(system_profiler.list_profiles(tag=tag), indent=2))


async def handle_sysprof_benchmarks(args: dict) -> list[TextContent]:
    from src.system_profiler import system_profiler
    return _text(json.dumps(system_profiler.list_benchmarks(), indent=2))


async def handle_sysprof_stats(args: dict) -> list[TextContent]:
    from src.system_profiler import system_profiler
    return _text(json.dumps(system_profiler.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# CONTEXT MANAGER — Phase 22
# ═══════════════════════════════════════════════════════════════════════════

async def handle_ctxmgr_list(args: dict) -> list[TextContent]:
    from src.context_manager import context_manager
    tag = args.get("tag")
    return _text(json.dumps(context_manager.list_contexts(tag=tag), indent=2))


async def handle_ctxmgr_events(args: dict) -> list[TextContent]:
    from src.context_manager import context_manager
    cid = args.get("context_id")
    return _text(json.dumps(context_manager.get_events(context_id=cid), indent=2))


async def handle_ctxmgr_stats(args: dict) -> list[TextContent]:
    from src.context_manager import context_manager
    return _text(json.dumps(context_manager.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# WINDOW MANAGER — Phase 23
# ═══════════════════════════════════════════════════════════════════════════

async def handle_winmgr_list(args: dict) -> list[TextContent]:
    from src.window_manager import window_manager
    visible = args.get("visible_only", "true").lower() != "false"
    return _text(json.dumps(window_manager.list_windows(visible_only=visible), indent=2))


async def handle_winmgr_events(args: dict) -> list[TextContent]:
    from src.window_manager import window_manager
    limit = int(args.get("limit", 50))
    return _text(json.dumps(window_manager.get_events(limit=limit), indent=2))


async def handle_winmgr_stats(args: dict) -> list[TextContent]:
    from src.window_manager import window_manager
    return _text(json.dumps(window_manager.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# POWER MANAGER — Phase 23
# ═══════════════════════════════════════════════════════════════════════════

async def handle_pwrmgr_battery(args: dict) -> list[TextContent]:
    from src.power_manager import power_manager
    return _text(json.dumps(power_manager.get_battery_status(), indent=2))


async def handle_pwrmgr_events(args: dict) -> list[TextContent]:
    from src.power_manager import power_manager
    limit = int(args.get("limit", 50))
    return _text(json.dumps(power_manager.get_events(limit=limit), indent=2))


async def handle_pwrmgr_stats(args: dict) -> list[TextContent]:
    from src.power_manager import power_manager
    return _text(json.dumps(power_manager.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# DOWNLOAD MANAGER — Phase 23
# ═══════════════════════════════════════════════════════════════════════════

async def handle_dlmgr_list(args: dict) -> list[TextContent]:
    from src.download_manager import download_manager
    status = args.get("status")
    return _text(json.dumps(download_manager.list_downloads(status=status), indent=2))


async def handle_dlmgr_history(args: dict) -> list[TextContent]:
    from src.download_manager import download_manager
    return _text(json.dumps(download_manager.list_downloads(limit=100), indent=2))


async def handle_dlmgr_stats(args: dict) -> list[TextContent]:
    from src.download_manager import download_manager
    return _text(json.dumps(download_manager.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# REGISTRY MANAGER — Phase 24
# ═══════════════════════════════════════════════════════════════════════════

async def handle_regmgr_favorites(args: dict) -> list[TextContent]:
    from src.registry_manager import registry_manager
    return _text(json.dumps(registry_manager.list_favorites(), indent=2))


async def handle_regmgr_events(args: dict) -> list[TextContent]:
    from src.registry_manager import registry_manager
    limit = int(args.get("limit", 50))
    return _text(json.dumps(registry_manager.get_events(limit=limit), indent=2))


async def handle_regmgr_stats(args: dict) -> list[TextContent]:
    from src.registry_manager import registry_manager
    return _text(json.dumps(registry_manager.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# SERVICE CONTROLLER — Phase 24
# ═══════════════════════════════════════════════════════════════════════════

async def handle_svcctl_list(args: dict) -> list[TextContent]:
    from src.service_controller import service_controller
    state = args.get("state", "all")
    return _text(json.dumps(service_controller.list_services(state=state), indent=2))


async def handle_svcctl_events(args: dict) -> list[TextContent]:
    from src.service_controller import service_controller
    limit = int(args.get("limit", 50))
    return _text(json.dumps(service_controller.get_events(limit=limit), indent=2))


async def handle_svcctl_stats(args: dict) -> list[TextContent]:
    from src.service_controller import service_controller
    return _text(json.dumps(service_controller.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# DISK MONITOR — Phase 24
# ═══════════════════════════════════════════════════════════════════════════

async def handle_diskmon_drives(args: dict) -> list[TextContent]:
    from src.disk_monitor import disk_monitor
    return _text(json.dumps(disk_monitor.list_drives(), indent=2))


async def handle_diskmon_alerts(args: dict) -> list[TextContent]:
    from src.disk_monitor import disk_monitor
    limit = int(args.get("limit", 50))
    return _text(json.dumps(disk_monitor.get_alerts(limit=limit), indent=2))


async def handle_diskmon_stats(args: dict) -> list[TextContent]:
    from src.disk_monitor import disk_monitor
    return _text(json.dumps(disk_monitor.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# AUDIO CONTROLLER — Phase 25
# ═══════════════════════════════════════════════════════════════════════════

async def handle_audictl_presets(args: dict) -> list[TextContent]:
    from src.audio_controller import audio_controller
    return _text(json.dumps(audio_controller.list_presets(), indent=2))


async def handle_audictl_events(args: dict) -> list[TextContent]:
    from src.audio_controller import audio_controller
    limit = int(args.get("limit", 50))
    return _text(json.dumps(audio_controller.get_events(limit=limit), indent=2))


async def handle_audictl_stats(args: dict) -> list[TextContent]:
    from src.audio_controller import audio_controller
    return _text(json.dumps(audio_controller.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# STARTUP MANAGER — Phase 25
# ═══════════════════════════════════════════════════════════════════════════

async def handle_startup_list(args: dict) -> list[TextContent]:
    from src.startup_manager import startup_manager
    scope = args.get("scope", "user")
    return _text(json.dumps(startup_manager.list_entries(scope=scope), indent=2))


async def handle_startup_events(args: dict) -> list[TextContent]:
    from src.startup_manager import startup_manager
    limit = int(args.get("limit", 50))
    return _text(json.dumps(startup_manager.get_events(limit=limit), indent=2))


async def handle_startup_stats(args: dict) -> list[TextContent]:
    from src.startup_manager import startup_manager
    return _text(json.dumps(startup_manager.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# SCREEN CAPTURE — Phase 25
# ═══════════════════════════════════════════════════════════════════════════

async def handle_scrcap_list(args: dict) -> list[TextContent]:
    from src.screen_capture import screen_capture
    limit = int(args.get("limit", 50))
    return _text(json.dumps(screen_capture.list_captures(limit=limit), indent=2))


async def handle_scrcap_events(args: dict) -> list[TextContent]:
    from src.screen_capture import screen_capture
    limit = int(args.get("limit", 50))
    return _text(json.dumps(screen_capture.get_events(limit=limit), indent=2))


async def handle_scrcap_stats(args: dict) -> list[TextContent]:
    from src.screen_capture import screen_capture
    return _text(json.dumps(screen_capture.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# WIFI MANAGER — Phase 26
# ═══════════════════════════════════════════════════════════════════════════

async def handle_wifimgr_profiles(args: dict) -> list[TextContent]:
    from src.wifi_manager import wifi_manager
    return _text(json.dumps(wifi_manager.list_profiles(), indent=2))


async def handle_wifimgr_events(args: dict) -> list[TextContent]:
    from src.wifi_manager import wifi_manager
    limit = int(args.get("limit", 50))
    return _text(json.dumps(wifi_manager.get_events(limit=limit), indent=2))


async def handle_wifimgr_stats(args: dict) -> list[TextContent]:
    from src.wifi_manager import wifi_manager
    return _text(json.dumps(wifi_manager.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# DISPLAY MANAGER — Phase 26
# ═══════════════════════════════════════════════════════════════════════════

async def handle_dispmgr_list(args: dict) -> list[TextContent]:
    from src.display_manager import display_manager
    return _text(json.dumps(display_manager.list_displays(), indent=2))


async def handle_dispmgr_events(args: dict) -> list[TextContent]:
    from src.display_manager import display_manager
    limit = int(args.get("limit", 50))
    return _text(json.dumps(display_manager.get_events(limit=limit), indent=2))


async def handle_dispmgr_stats(args: dict) -> list[TextContent]:
    from src.display_manager import display_manager
    return _text(json.dumps(display_manager.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# USB MONITOR — Phase 26
# ═══════════════════════════════════════════════════════════════════════════

async def handle_usbmon_events(args: dict) -> list[TextContent]:
    from src.usb_monitor import usb_monitor
    limit = int(args.get("limit", 50))
    return _text(json.dumps(usb_monitor.get_events(limit=limit), indent=2))


async def handle_usbmon_changes(args: dict) -> list[TextContent]:
    from src.usb_monitor import usb_monitor
    return _text(json.dumps(usb_monitor.detect_changes(), indent=2))


async def handle_usbmon_stats(args: dict) -> list[TextContent]:
    from src.usb_monitor import usb_monitor
    return _text(json.dumps(usb_monitor.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# PRINTER MANAGER — Phase 27
# ═══════════════════════════════════════════════════════════════════════════

async def handle_prnmgr_list(args: dict) -> list[TextContent]:
    from src.printer_manager import printer_manager
    return _text(json.dumps(printer_manager.list_printers(), indent=2))


async def handle_prnmgr_events(args: dict) -> list[TextContent]:
    from src.printer_manager import printer_manager
    limit = int(args.get("limit", 50))
    return _text(json.dumps(printer_manager.get_events(limit=limit), indent=2))


async def handle_prnmgr_stats(args: dict) -> list[TextContent]:
    from src.printer_manager import printer_manager
    return _text(json.dumps(printer_manager.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# FIREWALL CONTROLLER — Phase 27
# ═══════════════════════════════════════════════════════════════════════════

async def handle_fwctl_rules(args: dict) -> list[TextContent]:
    from src.firewall_controller import firewall_controller
    direction = args.get("direction", "")
    rules = firewall_controller.list_rules(direction=direction)
    return _text(json.dumps(rules[:100], indent=2))


async def handle_fwctl_events(args: dict) -> list[TextContent]:
    from src.firewall_controller import firewall_controller
    limit = int(args.get("limit", 50))
    return _text(json.dumps(firewall_controller.get_events(limit=limit), indent=2))


async def handle_fwctl_stats(args: dict) -> list[TextContent]:
    from src.firewall_controller import firewall_controller
    return _text(json.dumps(firewall_controller.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# SCHEDULER MANAGER — Phase 27
# ═══════════════════════════════════════════════════════════════════════════

async def handle_schedmgr_list(args: dict) -> list[TextContent]:
    from src.scheduler_manager import scheduler_manager
    folder = args.get("folder", "\\")
    return _text(json.dumps(scheduler_manager.list_tasks(folder=folder), indent=2))


async def handle_schedmgr_events(args: dict) -> list[TextContent]:
    from src.scheduler_manager import scheduler_manager
    limit = int(args.get("limit", 50))
    return _text(json.dumps(scheduler_manager.get_events(limit=limit), indent=2))


async def handle_schedmgr_stats(args: dict) -> list[TextContent]:
    from src.scheduler_manager import scheduler_manager
    return _text(json.dumps(scheduler_manager.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# BLUETOOTH MANAGER — Phase 28
# ═══════════════════════════════════════════════════════════════════════════

async def handle_btmgr_list(args: dict) -> list[TextContent]:
    from src.bluetooth_manager import bluetooth_manager
    return _text(json.dumps(bluetooth_manager.list_devices(), indent=2))


async def handle_btmgr_events(args: dict) -> list[TextContent]:
    from src.bluetooth_manager import bluetooth_manager
    limit = int(args.get("limit", 50))
    return _text(json.dumps(bluetooth_manager.get_events(limit=limit), indent=2))


async def handle_btmgr_stats(args: dict) -> list[TextContent]:
    from src.bluetooth_manager import bluetooth_manager
    return _text(json.dumps(bluetooth_manager.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# EVENT LOG READER — Phase 28
# ═══════════════════════════════════════════════════════════════════════════

async def handle_evtlog_read(args: dict) -> list[TextContent]:
    from src.eventlog_reader import eventlog_reader
    log_name = args.get("log_name", "System")
    max_events = int(args.get("max_events", 50))
    level = args.get("level", "")
    return _text(json.dumps(eventlog_reader.read_log(log_name=log_name, max_events=max_events, level=level), indent=2))


async def handle_evtlog_events(args: dict) -> list[TextContent]:
    from src.eventlog_reader import eventlog_reader
    limit = int(args.get("limit", 50))
    return _text(json.dumps(eventlog_reader.get_events(limit=limit), indent=2))


async def handle_evtlog_stats(args: dict) -> list[TextContent]:
    from src.eventlog_reader import eventlog_reader
    return _text(json.dumps(eventlog_reader.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# FONT MANAGER — Phase 28
# ═══════════════════════════════════════════════════════════════════════════

async def handle_fontmgr_list(args: dict) -> list[TextContent]:
    from src.font_manager import font_manager
    return _text(json.dumps(font_manager.list_fonts(), indent=2))


async def handle_fontmgr_events(args: dict) -> list[TextContent]:
    from src.font_manager import font_manager
    limit = int(args.get("limit", 50))
    return _text(json.dumps(font_manager.get_events(limit=limit), indent=2))


async def handle_fontmgr_stats(args: dict) -> list[TextContent]:
    from src.font_manager import font_manager
    return _text(json.dumps(font_manager.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# NETWORK MONITOR — Phase 29
# ═══════════════════════════════════════════════════════════════════════════

async def handle_netmon_adapters(args: dict) -> list[TextContent]:
    from src.network_monitor import network_monitor
    return _text(json.dumps(network_monitor.list_adapters(), indent=2))


async def handle_netmon_events(args: dict) -> list[TextContent]:
    from src.network_monitor import network_monitor
    limit = int(args.get("limit", 50))
    return _text(json.dumps(network_monitor.get_events(limit=limit), indent=2))


async def handle_netmon_stats(args: dict) -> list[TextContent]:
    from src.network_monitor import network_monitor
    return _text(json.dumps(network_monitor.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# HOSTS MANAGER — Phase 29
# ═══════════════════════════════════════════════════════════════════════════

async def handle_hostsmgr_list(args: dict) -> list[TextContent]:
    from src.hosts_manager import hosts_manager
    return _text(json.dumps(hosts_manager.read_entries(), indent=2))


async def handle_hostsmgr_events(args: dict) -> list[TextContent]:
    from src.hosts_manager import hosts_manager
    limit = int(args.get("limit", 50))
    return _text(json.dumps(hosts_manager.get_events(limit=limit), indent=2))


async def handle_hostsmgr_stats(args: dict) -> list[TextContent]:
    from src.hosts_manager import hosts_manager
    return _text(json.dumps(hosts_manager.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# THEME CONTROLLER — Phase 29
# ═══════════════════════════════════════════════════════════════════════════

async def handle_themectl_get(args: dict) -> list[TextContent]:
    from src.theme_controller import theme_controller
    return _text(json.dumps(theme_controller.get_theme(), indent=2))


async def handle_themectl_events(args: dict) -> list[TextContent]:
    from src.theme_controller import theme_controller
    limit = int(args.get("limit", 50))
    return _text(json.dumps(theme_controller.get_events(limit=limit), indent=2))


async def handle_themectl_stats(args: dict) -> list[TextContent]:
    from src.theme_controller import theme_controller
    return _text(json.dumps(theme_controller.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# CERTIFICATE MANAGER — Phase 30
# ═══════════════════════════════════════════════════════════════════════════

async def handle_certmgr_list(args: dict) -> list[TextContent]:
    from src.certificate_manager import certificate_manager
    store = args.get("store", "Cert:\\LocalMachine\\My")
    return _text(json.dumps(certificate_manager.list_certs(store=store), indent=2))


async def handle_certmgr_events(args: dict) -> list[TextContent]:
    from src.certificate_manager import certificate_manager
    limit = int(args.get("limit", 50))
    return _text(json.dumps(certificate_manager.get_events(limit=limit), indent=2))


async def handle_certmgr_stats(args: dict) -> list[TextContent]:
    from src.certificate_manager import certificate_manager
    return _text(json.dumps(certificate_manager.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# VIRTUAL DESKTOP — Phase 30
# ═══════════════════════════════════════════════════════════════════════════

async def handle_vdesk_list(args: dict) -> list[TextContent]:
    from src.virtual_desktop import virtual_desktop
    return _text(json.dumps(virtual_desktop.list_desktops(), indent=2))


async def handle_vdesk_events(args: dict) -> list[TextContent]:
    from src.virtual_desktop import virtual_desktop
    limit = int(args.get("limit", 50))
    return _text(json.dumps(virtual_desktop.get_events(limit=limit), indent=2))


async def handle_vdesk_stats(args: dict) -> list[TextContent]:
    from src.virtual_desktop import virtual_desktop
    return _text(json.dumps(virtual_desktop.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# NOTIFICATION MANAGER — Phase 30
# ═══════════════════════════════════════════════════════════════════════════

async def handle_notifmgr_history(args: dict) -> list[TextContent]:
    from src.notification_manager import notification_manager
    limit = int(args.get("limit", 50))
    return _text(json.dumps(notification_manager.get_history(limit=limit), indent=2))


async def handle_notifmgr_events(args: dict) -> list[TextContent]:
    from src.notification_manager import notification_manager
    limit = int(args.get("limit", 50))
    return _text(json.dumps(notification_manager.get_events(limit=limit), indent=2))


async def handle_notifmgr_stats(args: dict) -> list[TextContent]:
    from src.notification_manager import notification_manager
    return _text(json.dumps(notification_manager.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# SYSTEM RESTORE — Phase 31
# ═══════════════════════════════════════════════════════════════════════════

async def handle_sysrest_list(args: dict) -> list[TextContent]:
    from src.sysrestore_manager import sysrestore_manager
    return _text(json.dumps(sysrestore_manager.list_points(), indent=2))


async def handle_sysrest_events(args: dict) -> list[TextContent]:
    from src.sysrestore_manager import sysrestore_manager
    limit = int(args.get("limit", 50))
    return _text(json.dumps(sysrestore_manager.get_events(limit=limit), indent=2))


async def handle_sysrest_stats(args: dict) -> list[TextContent]:
    from src.sysrestore_manager import sysrestore_manager
    return _text(json.dumps(sysrestore_manager.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# PERFORMANCE COUNTER — Phase 31
# ═══════════════════════════════════════════════════════════════════════════

async def handle_perfctr_counters(args: dict) -> list[TextContent]:
    from src.perfcounter import perfcounter
    return _text(json.dumps(perfcounter.list_counters(), indent=2))


async def handle_perfctr_events(args: dict) -> list[TextContent]:
    from src.perfcounter import perfcounter
    limit = int(args.get("limit", 50))
    return _text(json.dumps(perfcounter.get_events(limit=limit), indent=2))


async def handle_perfctr_stats(args: dict) -> list[TextContent]:
    from src.perfcounter import perfcounter
    return _text(json.dumps(perfcounter.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# CREDENTIAL VAULT — Phase 31
# ═══════════════════════════════════════════════════════════════════════════

async def handle_credvlt_list(args: dict) -> list[TextContent]:
    from src.credential_vault import credential_vault
    return _text(json.dumps(credential_vault.list_credentials(), indent=2))


async def handle_credvlt_events(args: dict) -> list[TextContent]:
    from src.credential_vault import credential_vault
    limit = int(args.get("limit", 50))
    return _text(json.dumps(credential_vault.get_events(limit=limit), indent=2))


async def handle_credvlt_stats(args: dict) -> list[TextContent]:
    from src.credential_vault import credential_vault
    return _text(json.dumps(credential_vault.get_stats(), indent=2))


# ── Phase 32 — Locale Manager, GPU Monitor, Share Manager ────────────────

async def handle_localemgr_info(args: dict) -> list[TextContent]:
    from src.locale_manager import locale_manager
    info = {
        "system_locale": locale_manager.get_system_locale(),
        "languages": locale_manager.get_user_language(),
        "timezone": locale_manager.get_timezone(),
        "keyboards": locale_manager.get_keyboard_layouts(),
        "date_format": locale_manager.get_date_format(),
    }
    return _text(json.dumps(info, indent=2))


async def handle_localemgr_events(args: dict) -> list[TextContent]:
    from src.locale_manager import locale_manager
    limit = int(args.get("limit", 50))
    return _text(json.dumps(locale_manager.get_events(limit=limit), indent=2))


async def handle_localemgr_stats(args: dict) -> list[TextContent]:
    from src.locale_manager import locale_manager
    return _text(json.dumps(locale_manager.get_stats(), indent=2))


async def handle_gpumon_snapshot(args: dict) -> list[TextContent]:
    from src.gpu_monitor import gpu_monitor
    return _text(json.dumps(gpu_monitor.snapshot(), indent=2))


async def handle_gpumon_events(args: dict) -> list[TextContent]:
    from src.gpu_monitor import gpu_monitor
    limit = int(args.get("limit", 50))
    return _text(json.dumps(gpu_monitor.get_events(limit=limit), indent=2))


async def handle_gpumon_stats(args: dict) -> list[TextContent]:
    from src.gpu_monitor import gpu_monitor
    return _text(json.dumps(gpu_monitor.get_stats(), indent=2))


async def handle_sharemgr_list(args: dict) -> list[TextContent]:
    from src.share_manager import share_manager
    return _text(json.dumps(share_manager.list_shares(), indent=2))


async def handle_sharemgr_events(args: dict) -> list[TextContent]:
    from src.share_manager import share_manager
    limit = int(args.get("limit", 50))
    return _text(json.dumps(share_manager.get_events(limit=limit), indent=2))


async def handle_sharemgr_stats(args: dict) -> list[TextContent]:
    from src.share_manager import share_manager
    return _text(json.dumps(share_manager.get_stats(), indent=2))


# ── Phase 33 — Driver Manager, WMI Explorer, Env Variable Manager ────────

async def handle_drvmgr_list(args: dict) -> list[TextContent]:
    from src.driver_manager import driver_manager
    return _text(json.dumps(driver_manager.list_drivers(), indent=2))


async def handle_drvmgr_events(args: dict) -> list[TextContent]:
    from src.driver_manager import driver_manager
    limit = int(args.get("limit", 50))
    return _text(json.dumps(driver_manager.get_events(limit=limit), indent=2))


async def handle_drvmgr_stats(args: dict) -> list[TextContent]:
    from src.driver_manager import driver_manager
    return _text(json.dumps(driver_manager.get_stats(), indent=2))


async def handle_wmiexp_query(args: dict) -> list[TextContent]:
    from src.wmi_explorer import wmi_explorer
    class_name = args.get("class_name", "Win32_OperatingSystem")
    properties = args.get("properties", "")
    max_results = int(args.get("max_results", 50))
    return _text(json.dumps(wmi_explorer.query_class(class_name, properties, max_results), indent=2))


async def handle_wmiexp_events(args: dict) -> list[TextContent]:
    from src.wmi_explorer import wmi_explorer
    limit = int(args.get("limit", 50))
    return _text(json.dumps(wmi_explorer.get_events(limit=limit), indent=2))


async def handle_wmiexp_stats(args: dict) -> list[TextContent]:
    from src.wmi_explorer import wmi_explorer
    return _text(json.dumps(wmi_explorer.get_stats(), indent=2))


async def handle_envmgr_list(args: dict) -> list[TextContent]:
    from src.env_variable_manager import env_variable_manager
    return _text(json.dumps(env_variable_manager.list_all(), indent=2))


async def handle_envmgr_events(args: dict) -> list[TextContent]:
    from src.env_variable_manager import env_variable_manager
    limit = int(args.get("limit", 50))
    return _text(json.dumps(env_variable_manager.get_events(limit=limit), indent=2))


async def handle_envmgr_stats(args: dict) -> list[TextContent]:
    from src.env_variable_manager import env_variable_manager
    return _text(json.dumps(env_variable_manager.get_stats(), indent=2))


# ── Phase 34 — Pagefile Manager, Time Sync Manager, Disk Health ──────────

async def handle_pgfile_usage(args: dict) -> list[TextContent]:
    from src.pagefile_manager import pagefile_manager
    return _text(json.dumps(pagefile_manager.get_usage(), indent=2))


async def handle_pgfile_events(args: dict) -> list[TextContent]:
    from src.pagefile_manager import pagefile_manager
    limit = int(args.get("limit", 50))
    return _text(json.dumps(pagefile_manager.get_events(limit=limit), indent=2))


async def handle_pgfile_stats(args: dict) -> list[TextContent]:
    from src.pagefile_manager import pagefile_manager
    return _text(json.dumps(pagefile_manager.get_stats(), indent=2))


async def handle_timesync_status(args: dict) -> list[TextContent]:
    from src.time_sync_manager import time_sync_manager
    return _text(json.dumps(time_sync_manager.get_status(), indent=2))


async def handle_timesync_events(args: dict) -> list[TextContent]:
    from src.time_sync_manager import time_sync_manager
    limit = int(args.get("limit", 50))
    return _text(json.dumps(time_sync_manager.get_events(limit=limit), indent=2))


async def handle_timesync_stats(args: dict) -> list[TextContent]:
    from src.time_sync_manager import time_sync_manager
    return _text(json.dumps(time_sync_manager.get_stats(), indent=2))


async def handle_diskhlth_list(args: dict) -> list[TextContent]:
    from src.disk_health import disk_health
    return _text(json.dumps(disk_health.list_disks(), indent=2))


async def handle_diskhlth_events(args: dict) -> list[TextContent]:
    from src.disk_health import disk_health
    limit = int(args.get("limit", 50))
    return _text(json.dumps(disk_health.get_events(limit=limit), indent=2))


async def handle_diskhlth_stats(args: dict) -> list[TextContent]:
    from src.disk_health import disk_health
    return _text(json.dumps(disk_health.get_stats(), indent=2))


# ── Phase 35 — User Accounts, Group Policy, Windows Features ─────────────

async def handle_usracct_list(args: dict) -> list[TextContent]:
    from src.user_account_manager import user_account_manager
    return _text(json.dumps(user_account_manager.list_users(), indent=2))


async def handle_usracct_events(args: dict) -> list[TextContent]:
    from src.user_account_manager import user_account_manager
    limit = int(args.get("limit", 50))
    return _text(json.dumps(user_account_manager.get_events(limit=limit), indent=2))


async def handle_usracct_stats(args: dict) -> list[TextContent]:
    from src.user_account_manager import user_account_manager
    return _text(json.dumps(user_account_manager.get_stats(), indent=2))


async def handle_gpo_rsop(args: dict) -> list[TextContent]:
    from src.group_policy_reader import group_policy_reader
    return _text(json.dumps(group_policy_reader.get_rsop(), indent=2))


async def handle_gpo_events(args: dict) -> list[TextContent]:
    from src.group_policy_reader import group_policy_reader
    limit = int(args.get("limit", 50))
    return _text(json.dumps(group_policy_reader.get_events(limit=limit), indent=2))


async def handle_gpo_stats(args: dict) -> list[TextContent]:
    from src.group_policy_reader import group_policy_reader
    return _text(json.dumps(group_policy_reader.get_stats(), indent=2))


async def handle_winfeat_list(args: dict) -> list[TextContent]:
    from src.windows_feature_manager import windows_feature_manager
    return _text(json.dumps(windows_feature_manager.list_features(), indent=2))


async def handle_winfeat_events(args: dict) -> list[TextContent]:
    from src.windows_feature_manager import windows_feature_manager
    limit = int(args.get("limit", 50))
    return _text(json.dumps(windows_feature_manager.get_events(limit=limit), indent=2))


async def handle_winfeat_stats(args: dict) -> list[TextContent]:
    from src.windows_feature_manager import windows_feature_manager
    return _text(json.dumps(windows_feature_manager.get_stats(), indent=2))


# ── Phase 36 — Memory Diagnostics, System Info, Crash Dump Reader ────────

async def handle_memdiag_modules(args: dict) -> list[TextContent]:
    from src.memory_diagnostics import memory_diagnostics
    return _text(json.dumps(memory_diagnostics.list_modules(), indent=2))


async def handle_memdiag_events(args: dict) -> list[TextContent]:
    from src.memory_diagnostics import memory_diagnostics
    limit = int(args.get("limit", 50))
    return _text(json.dumps(memory_diagnostics.get_events(limit=limit), indent=2))


async def handle_memdiag_stats(args: dict) -> list[TextContent]:
    from src.memory_diagnostics import memory_diagnostics
    return _text(json.dumps(memory_diagnostics.get_stats(), indent=2))


async def handle_sysinfo_profile(args: dict) -> list[TextContent]:
    from src.system_info_collector import system_info_collector
    return _text(json.dumps(system_info_collector.get_full_profile(), indent=2))


async def handle_sysinfo_events(args: dict) -> list[TextContent]:
    from src.system_info_collector import system_info_collector
    limit = int(args.get("limit", 50))
    return _text(json.dumps(system_info_collector.get_events(limit=limit), indent=2))


async def handle_sysinfo_stats(args: dict) -> list[TextContent]:
    from src.system_info_collector import system_info_collector
    return _text(json.dumps(system_info_collector.get_stats(), indent=2))


async def handle_crashdmp_list(args: dict) -> list[TextContent]:
    from src.crash_dump_reader import crash_dump_reader
    return _text(json.dumps(crash_dump_reader.get_crash_summary(), indent=2))


async def handle_crashdmp_events(args: dict) -> list[TextContent]:
    from src.crash_dump_reader import crash_dump_reader
    limit = int(args.get("limit", 50))
    return _text(json.dumps(crash_dump_reader.get_events(limit=limit), indent=2))


async def handle_crashdmp_stats(args: dict) -> list[TextContent]:
    from src.crash_dump_reader import crash_dump_reader
    return _text(json.dumps(crash_dump_reader.get_stats(), indent=2))


# ── Phase 37 — Hotfix Manager, Volume Manager, Defender Status ───────────

async def handle_hotfix_list(args: dict) -> list[TextContent]:
    from src.hotfix_manager import hotfix_manager
    return _text(json.dumps(hotfix_manager.list_hotfixes(), indent=2))


async def handle_hotfix_events(args: dict) -> list[TextContent]:
    from src.hotfix_manager import hotfix_manager
    limit = int(args.get("limit", 50))
    return _text(json.dumps(hotfix_manager.get_events(limit=limit), indent=2))


async def handle_hotfix_stats(args: dict) -> list[TextContent]:
    from src.hotfix_manager import hotfix_manager
    return _text(json.dumps(hotfix_manager.get_stats(), indent=2))


async def handle_volmgr_list(args: dict) -> list[TextContent]:
    from src.volume_manager import volume_manager
    return _text(json.dumps(volume_manager.list_volumes(), indent=2))


async def handle_volmgr_events(args: dict) -> list[TextContent]:
    from src.volume_manager import volume_manager
    limit = int(args.get("limit", 50))
    return _text(json.dumps(volume_manager.get_events(limit=limit), indent=2))


async def handle_volmgr_stats(args: dict) -> list[TextContent]:
    from src.volume_manager import volume_manager
    return _text(json.dumps(volume_manager.get_stats(), indent=2))


async def handle_defender_status(args: dict) -> list[TextContent]:
    from src.defender_status import defender_status
    return _text(json.dumps(defender_status.get_status(), indent=2))


async def handle_defender_events(args: dict) -> list[TextContent]:
    from src.defender_status import defender_status
    limit = int(args.get("limit", 50))
    return _text(json.dumps(defender_status.get_events(limit=limit), indent=2))


async def handle_defender_stats(args: dict) -> list[TextContent]:
    from src.defender_status import defender_status
    return _text(json.dumps(defender_status.get_stats(), indent=2))


# ── Phase 38 — IP Config, Recycle Bin, Installed Apps ────────────────────

async def handle_ipcfg_all(args: dict) -> list[TextContent]:
    from src.ip_config_manager import ip_config_manager
    return _text(json.dumps(ip_config_manager.get_all(), indent=2))


async def handle_ipcfg_events(args: dict) -> list[TextContent]:
    from src.ip_config_manager import ip_config_manager
    limit = int(args.get("limit", 50))
    return _text(json.dumps(ip_config_manager.get_events(limit=limit), indent=2))


async def handle_ipcfg_stats(args: dict) -> list[TextContent]:
    from src.ip_config_manager import ip_config_manager
    return _text(json.dumps(ip_config_manager.get_stats(), indent=2))


async def handle_recyclebin_info(args: dict) -> list[TextContent]:
    from src.recycle_bin_manager import recycle_bin_manager
    return _text(json.dumps(recycle_bin_manager.get_info(), indent=2))


async def handle_recyclebin_events(args: dict) -> list[TextContent]:
    from src.recycle_bin_manager import recycle_bin_manager
    limit = int(args.get("limit", 50))
    return _text(json.dumps(recycle_bin_manager.get_events(limit=limit), indent=2))


async def handle_recyclebin_stats(args: dict) -> list[TextContent]:
    from src.recycle_bin_manager import recycle_bin_manager
    return _text(json.dumps(recycle_bin_manager.get_stats(), indent=2))


async def handle_instapp_list(args: dict) -> list[TextContent]:
    from src.installed_apps_manager import installed_apps_manager
    return _text(json.dumps(installed_apps_manager.list_win32_apps(), indent=2))


async def handle_instapp_events(args: dict) -> list[TextContent]:
    from src.installed_apps_manager import installed_apps_manager
    limit = int(args.get("limit", 50))
    return _text(json.dumps(installed_apps_manager.get_events(limit=limit), indent=2))


async def handle_instapp_stats(args: dict) -> list[TextContent]:
    from src.installed_apps_manager import installed_apps_manager
    return _text(json.dumps(installed_apps_manager.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# Phase 39 — Scheduled Tasks, Audio Devices, USB Devices
# ═══════════════════════════════════════════════════════════════════════════


async def handle_schtask_list(args: dict) -> list[TextContent]:
    from src.scheduled_task_manager import scheduled_task_manager
    return _text(json.dumps(scheduled_task_manager.list_tasks(), indent=2))


async def handle_schtask_events(args: dict) -> list[TextContent]:
    from src.scheduled_task_manager import scheduled_task_manager
    limit = int(args.get("limit", 50))
    return _text(json.dumps(scheduled_task_manager.get_events(limit=limit), indent=2))


async def handle_schtask_stats(args: dict) -> list[TextContent]:
    from src.scheduled_task_manager import scheduled_task_manager
    return _text(json.dumps(scheduled_task_manager.get_stats(), indent=2))


async def handle_audiodev_list(args: dict) -> list[TextContent]:
    from src.audio_device_manager import audio_device_manager
    return _text(json.dumps(audio_device_manager.list_devices(), indent=2))


async def handle_audiodev_events(args: dict) -> list[TextContent]:
    from src.audio_device_manager import audio_device_manager
    limit = int(args.get("limit", 50))
    return _text(json.dumps(audio_device_manager.get_events(limit=limit), indent=2))


async def handle_audiodev_stats(args: dict) -> list[TextContent]:
    from src.audio_device_manager import audio_device_manager
    return _text(json.dumps(audio_device_manager.get_stats(), indent=2))


async def handle_usbdev_list(args: dict) -> list[TextContent]:
    from src.usb_device_manager import usb_device_manager
    return _text(json.dumps(usb_device_manager.list_devices(), indent=2))


async def handle_usbdev_events(args: dict) -> list[TextContent]:
    from src.usb_device_manager import usb_device_manager
    limit = int(args.get("limit", 50))
    return _text(json.dumps(usb_device_manager.get_events(limit=limit), indent=2))


async def handle_usbdev_stats(args: dict) -> list[TextContent]:
    from src.usb_device_manager import usb_device_manager
    return _text(json.dumps(usb_device_manager.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# Phase 43 — Network Adapter, Windows Update, Local Security Policy
# ═══════════════════════════════════════════════════════════════════════════


async def handle_netadapt_list(args: dict) -> list[TextContent]:
    from src.network_adapter_manager import network_adapter_manager
    return _text(json.dumps(network_adapter_manager.list_adapters(), indent=2))


async def handle_netadapt_events(args: dict) -> list[TextContent]:
    from src.network_adapter_manager import network_adapter_manager
    limit = int(args.get("limit", 50))
    return _text(json.dumps(network_adapter_manager.get_events(limit=limit), indent=2))


async def handle_netadapt_stats(args: dict) -> list[TextContent]:
    from src.network_adapter_manager import network_adapter_manager
    return _text(json.dumps(network_adapter_manager.get_stats(), indent=2))


async def handle_winupd_history(args: dict) -> list[TextContent]:
    from src.windows_update_manager import windows_update_manager
    limit = int(args.get("limit", 30))
    return _text(json.dumps(windows_update_manager.get_update_history(limit), indent=2))


async def handle_winupd_events(args: dict) -> list[TextContent]:
    from src.windows_update_manager import windows_update_manager
    limit = int(args.get("limit", 50))
    return _text(json.dumps(windows_update_manager.get_events(limit=limit), indent=2))


async def handle_winupd_stats(args: dict) -> list[TextContent]:
    from src.windows_update_manager import windows_update_manager
    return _text(json.dumps(windows_update_manager.get_stats(), indent=2))


async def handle_secpol_export(args: dict) -> list[TextContent]:
    from src.local_security_policy import local_security_policy
    return _text(json.dumps(local_security_policy.export_policy(), indent=2))


async def handle_secpol_events(args: dict) -> list[TextContent]:
    from src.local_security_policy import local_security_policy
    limit = int(args.get("limit", 50))
    return _text(json.dumps(local_security_policy.get_events(limit=limit), indent=2))


async def handle_secpol_stats(args: dict) -> list[TextContent]:
    from src.local_security_policy import local_security_policy
    return _text(json.dumps(local_security_policy.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# Phase 42 — DNS Client, Storage Pool, Power Plan
# ═══════════════════════════════════════════════════════════════════════════


async def handle_dnscli_servers(args: dict) -> list[TextContent]:
    from src.dns_client_manager import dns_client_manager
    return _text(json.dumps(dns_client_manager.get_server_addresses(), indent=2))


async def handle_dnscli_events(args: dict) -> list[TextContent]:
    from src.dns_client_manager import dns_client_manager
    limit = int(args.get("limit", 50))
    return _text(json.dumps(dns_client_manager.get_events(limit=limit), indent=2))


async def handle_dnscli_stats(args: dict) -> list[TextContent]:
    from src.dns_client_manager import dns_client_manager
    return _text(json.dumps(dns_client_manager.get_stats(), indent=2))


async def handle_storpool_list(args: dict) -> list[TextContent]:
    from src.storage_pool_manager import storage_pool_manager
    return _text(json.dumps(storage_pool_manager.list_pools(), indent=2))


async def handle_storpool_events(args: dict) -> list[TextContent]:
    from src.storage_pool_manager import storage_pool_manager
    limit = int(args.get("limit", 50))
    return _text(json.dumps(storage_pool_manager.get_events(limit=limit), indent=2))


async def handle_storpool_stats(args: dict) -> list[TextContent]:
    from src.storage_pool_manager import storage_pool_manager
    return _text(json.dumps(storage_pool_manager.get_stats(), indent=2))


async def handle_pwrplan_list(args: dict) -> list[TextContent]:
    from src.power_plan_manager import power_plan_manager
    return _text(json.dumps(power_plan_manager.list_plans(), indent=2))


async def handle_pwrplan_events(args: dict) -> list[TextContent]:
    from src.power_plan_manager import power_plan_manager
    limit = int(args.get("limit", 50))
    return _text(json.dumps(power_plan_manager.get_events(limit=limit), indent=2))


async def handle_pwrplan_stats(args: dict) -> list[TextContent]:
    from src.power_plan_manager import power_plan_manager
    return _text(json.dumps(power_plan_manager.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# Phase 41 — Virtual Memory, Event Log Reader, Shadow Copy
# ═══════════════════════════════════════════════════════════════════════════


async def handle_virtmem_status(args: dict) -> list[TextContent]:
    from src.virtual_memory_manager import virtual_memory_manager
    return _text(json.dumps(virtual_memory_manager.get_status(), indent=2))


async def handle_virtmem_events(args: dict) -> list[TextContent]:
    from src.virtual_memory_manager import virtual_memory_manager
    limit = int(args.get("limit", 50))
    return _text(json.dumps(virtual_memory_manager.get_events(limit=limit), indent=2))


async def handle_virtmem_stats(args: dict) -> list[TextContent]:
    from src.virtual_memory_manager import virtual_memory_manager
    return _text(json.dumps(virtual_memory_manager.get_stats(), indent=2))


async def handle_winevt_recent(args: dict) -> list[TextContent]:
    from src.windows_event_log_reader import windows_event_log_reader
    log_name = args.get("log_name", "System")
    max_events = int(args.get("max_events", 20))
    return _text(json.dumps(windows_event_log_reader.get_recent(log_name, max_events), indent=2))


async def handle_winevt_events(args: dict) -> list[TextContent]:
    from src.windows_event_log_reader import windows_event_log_reader
    limit = int(args.get("limit", 50))
    return _text(json.dumps(windows_event_log_reader.get_events(limit=limit), indent=2))


async def handle_winevt_stats(args: dict) -> list[TextContent]:
    from src.windows_event_log_reader import windows_event_log_reader
    return _text(json.dumps(windows_event_log_reader.get_stats(), indent=2))


async def handle_shadowcopy_list(args: dict) -> list[TextContent]:
    from src.shadow_copy_manager import shadow_copy_manager
    return _text(json.dumps(shadow_copy_manager.list_copies(), indent=2))


async def handle_shadowcopy_events(args: dict) -> list[TextContent]:
    from src.shadow_copy_manager import shadow_copy_manager
    limit = int(args.get("limit", 50))
    return _text(json.dumps(shadow_copy_manager.get_events(limit=limit), indent=2))


async def handle_shadowcopy_stats(args: dict) -> list[TextContent]:
    from src.shadow_copy_manager import shadow_copy_manager
    return _text(json.dumps(shadow_copy_manager.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# Phase 40 — Screen Resolution, BIOS Settings, Performance Counters
# ═══════════════════════════════════════════════════════════════════════════


async def handle_screenres_list(args: dict) -> list[TextContent]:
    from src.screen_resolution_manager import screen_resolution_manager
    return _text(json.dumps(screen_resolution_manager.list_displays(), indent=2))


async def handle_screenres_events(args: dict) -> list[TextContent]:
    from src.screen_resolution_manager import screen_resolution_manager
    limit = int(args.get("limit", 50))
    return _text(json.dumps(screen_resolution_manager.get_events(limit=limit), indent=2))


async def handle_screenres_stats(args: dict) -> list[TextContent]:
    from src.screen_resolution_manager import screen_resolution_manager
    return _text(json.dumps(screen_resolution_manager.get_stats(), indent=2))


async def handle_biosinfo_get(args: dict) -> list[TextContent]:
    from src.bios_settings import bios_settings
    return _text(json.dumps(bios_settings.get_info(), indent=2))


async def handle_biosinfo_events(args: dict) -> list[TextContent]:
    from src.bios_settings import bios_settings
    limit = int(args.get("limit", 50))
    return _text(json.dumps(bios_settings.get_events(limit=limit), indent=2))


async def handle_biosinfo_stats(args: dict) -> list[TextContent]:
    from src.bios_settings import bios_settings
    return _text(json.dumps(bios_settings.get_stats(), indent=2))


async def handle_perfmon_snapshot(args: dict) -> list[TextContent]:
    from src.performance_counter import performance_counter
    return _text(json.dumps(performance_counter.snapshot(), indent=2))


async def handle_perfmon_events(args: dict) -> list[TextContent]:
    from src.performance_counter import performance_counter
    limit = int(args.get("limit", 50))
    return _text(json.dumps(performance_counter.get_events(limit=limit), indent=2))


async def handle_perfmon_stats(args: dict) -> list[TextContent]:
    from src.performance_counter import performance_counter
    return _text(json.dumps(performance_counter.get_stats(), indent=2))


# ═══════════════════════════════════════════════════════════════════════════
# TELEGRAM BOT HANDLERS (3)
# ═══════════════════════════════════════════════════════════════════════════

async def handle_telegram_send(args: dict) -> list[TextContent]:
    """Envoyer un message Telegram via le bot."""
    import urllib.request
    message = args.get("message", "")
    if not message:
        return _error("missing 'message'")
    chat_id = args.get("chat_id", "")
    token = os.environ.get("TELEGRAM_TOKEN", "")
    if not chat_id:
        chat_id = os.environ.get("TELEGRAM_CHAT", "")
    if not token:
        return _error("TELEGRAM_TOKEN non configuré dans .env")
    if not chat_id:
        return _error("TELEGRAM_CHAT non configuré dans .env")
    try:
        body = json.dumps({"chat_id": chat_id, "text": message}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode())
        return _text(f"Message envoyé (id: {data.get('result', {}).get('message_id', '?')})")
    except Exception as e:
        return _error(f"Telegram sendMessage: {e}")


async def handle_telegram_status(args: dict) -> list[TextContent]:
    """Statut du bot Telegram (proxy check + bot info)."""
    import urllib.request
    lines = []
    # Check bot identity
    token = os.environ.get("TELEGRAM_TOKEN", "")
    if not token:
        return _error("TELEGRAM_TOKEN non configuré")
    try:
        req = urllib.request.Request(f"https://api.telegram.org/bot{token}/getMe")
        resp = urllib.request.urlopen(req, timeout=5)
        me = json.loads(resp.read().decode()).get("result", {})
        lines.append(f"Bot: @{me.get('username', '?')} ({me.get('first_name', '?')})")
    except Exception as e:
        lines.append(f"Bot: OFFLINE ({e})")
    # Check canvas proxy
    try:
        req = urllib.request.Request("http://127.0.0.1:18800/health")
        resp = urllib.request.urlopen(req, timeout=3)
        health = json.loads(resp.read().decode())
        nodes = health.get("nodes", [])
        online = sum(1 for n in nodes if n.get("status") == "online")
        lines.append(f"Proxy: OK ({online}/{len(nodes)} nœuds online)")
    except Exception:
        lines.append("Proxy: OFFLINE (port 18800)")
    lines.append(f"Chat ID: {os.environ.get('TELEGRAM_CHAT', 'non configuré')}")
    return _text("\n".join(lines))


async def handle_telegram_history(args: dict) -> list[TextContent]:
    """Derniers messages reçus par le bot Telegram (via proxy)."""
    import urllib.request
    limit = _safe_int(args.get("limit"), 20)
    try:
        token = os.environ.get("TELEGRAM_TOKEN", "")
        if not token:
            return _error("TELEGRAM_TOKEN non configuré")
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/getUpdates",
            data=json.dumps({"limit": min(limit, 100), "timeout": 0}).encode(),
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode())
        updates = data.get("result", [])
        if not updates:
            return _text("Aucun message récent.")
        lines = [f"Derniers {len(updates)} messages:"]
        for u in updates[-limit:]:
            msg = u.get("message", {})
            frm = msg.get("from", {})
            txt = msg.get("text", "(no text)")
            name = frm.get("username") or frm.get("first_name") or "?"
            lines.append(f"  [{name}] {txt[:80]}")
        return _text("\n".join(lines))
    except Exception as e:
        return _error(f"Telegram getUpdates: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# BROWSER NAVIGATOR HANDLERS (10)
# ═══════════════════════════════════════════════════════════════════════════

async def handle_browser_open(args: dict) -> list[TextContent]:
    """Open browser, optionally navigate to URL."""
    from src.browser_navigator import browser_nav
    url = args.get("url")
    result = await browser_nav.launch(url=url)
    return _text(json.dumps(result))


async def handle_browser_navigate(args: dict) -> list[TextContent]:
    """Navigate to URL."""
    from src.browser_navigator import browser_nav
    url = args.get("url", "")
    if not url:
        return _error("URL requise")
    result = await browser_nav.navigate(url)
    return _text(json.dumps(result))


async def handle_browser_click(args: dict) -> list[TextContent]:
    """Click element by text."""
    from src.browser_navigator import browser_nav
    text = args.get("text", "")
    if not text:
        return _error("Texte de l'element requis")
    result = await browser_nav.click_text(text)
    return _text(json.dumps(result))


async def handle_browser_scroll(args: dict) -> list[TextContent]:
    """Scroll page."""
    from src.browser_navigator import browser_nav
    direction = args.get("direction", "down")
    amount = _safe_int(args.get("amount"), 500)
    result = await browser_nav.scroll(direction, amount)
    return _text(json.dumps(result))


async def handle_browser_read(args: dict) -> list[TextContent]:
    """Read page content as text."""
    from src.browser_navigator import browser_nav
    max_chars = _safe_int(args.get("max_chars"), 5000)
    text = await browser_nav.read_page(max_chars)
    return _text(text)


async def handle_browser_screenshot(args: dict) -> list[TextContent]:
    """Take a page screenshot."""
    from src.browser_navigator import browser_nav
    path = await browser_nav.screenshot_page()
    return _text(f"Screenshot saved: {path}")


async def handle_browser_back(args: dict) -> list[TextContent]:
    """Go back."""
    from src.browser_navigator import browser_nav
    result = await browser_nav.go_back()
    return _text(json.dumps(result))


async def handle_browser_forward(args: dict) -> list[TextContent]:
    """Go forward."""
    from src.browser_navigator import browser_nav
    result = await browser_nav.go_forward()
    return _text(json.dumps(result))


async def handle_browser_close(args: dict) -> list[TextContent]:
    """Close current tab."""
    from src.browser_navigator import browser_nav
    result = await browser_nav.close_tab()
    return _text(json.dumps(result))


async def handle_browser_move(args: dict) -> list[TextContent]:
    """Move browser to other screen."""
    from src.browser_navigator import browser_nav
    result = await browser_nav.move_to_screen()
    return _text(json.dumps(result))


# ═══════════════════════════════════════════════════════════════════════════
# PREDICTION ENGINE HANDLERS (3)
# ═══════════════════════════════════════════════════════════════════════════

async def handle_prediction_predict(args: dict) -> list[TextContent]:
    """Predict next user actions."""
    from src.prediction_engine import prediction_engine
    n = _safe_int(args.get("n"), 5)
    predictions = prediction_engine.predict_next(n=n)
    return _text(json.dumps(predictions, ensure_ascii=False, indent=2))


async def handle_prediction_profile(args: dict) -> list[TextContent]:
    """Get user activity profile."""
    from src.prediction_engine import prediction_engine
    profile = prediction_engine.get_user_profile()
    return _text(json.dumps(profile, ensure_ascii=False, indent=2))


async def handle_prediction_stats(args: dict) -> list[TextContent]:
    """Prediction engine stats."""
    from src.prediction_engine import prediction_engine
    return _text(json.dumps(prediction_engine.get_stats()))


# ═══════════════════════════════════════════════════════════════════════════
# AUTO-DEVELOPER HANDLERS (2)
# ═══════════════════════════════════════════════════════════════════════════

async def handle_autodev_run_cycle(args: dict) -> list[TextContent]:
    """Run auto-development cycle."""
    from src.auto_developer import auto_developer
    max_gaps = _safe_int(args.get("max_gaps"), 5)
    report = await auto_developer.run_cycle(max_gaps=max_gaps)
    return _text(json.dumps(report, ensure_ascii=False, indent=2))


async def handle_autodev_stats(args: dict) -> list[TextContent]:
    """Auto-developer stats."""
    from src.auto_developer import auto_developer
    return _text(json.dumps(auto_developer.get_stats()))


# ═══════════════════════════════════════════════════════════════════════════
# PATTERN AGENTS HANDLERS (5)
# ═══════════════════════════════════════════════════════════════════════════

async def handle_agent_dispatch(args: dict) -> list[TextContent]:
    """Dispatch a prompt to the best pattern agent."""
    from src.smart_dispatcher import SmartDispatcher
    prompt = args.get("prompt", "")
    pattern = args.get("pattern")
    if not prompt:
        return _error("prompt required")
    d = SmartDispatcher()
    if pattern:
        r = await d.dispatch_typed(pattern, prompt)
    else:
        r = await d.dispatch(prompt)
    await d.close()
    return _text(json.dumps({
        "ok": r.ok, "content": r.content[:2000], "pattern": r.pattern,
        "node": r.node, "model": r.model, "latency_ms": round(r.latency_ms),
        "tokens": r.tokens, "quality": r.quality_score, "strategy": r.strategy,
    }, ensure_ascii=False))


async def handle_agent_classify(args: dict) -> list[TextContent]:
    """Classify a prompt into a pattern type with confidence scoring."""
    from src.pattern_agents import PatternAgentRegistry
    prompt = args.get("prompt", "")
    if not prompt:
        return _error("prompt required")
    reg = PatternAgentRegistry()
    classification = reg.classify_with_confidence(prompt)
    pattern = classification["pattern"]
    agent = reg.agents.get(pattern)
    return _text(json.dumps({
        "pattern": pattern,
        "confidence": classification["confidence"],
        "candidates": classification["candidates"],
        "agent": agent.agent_id if agent else "unknown",
        "node": agent.primary_node if agent else "M1",
        "strategy": agent.strategy if agent else "single",
    }, ensure_ascii=False))


async def handle_agent_list(args: dict) -> list[TextContent]:
    """List all registered pattern agents."""
    from src.pattern_agents import PatternAgentRegistry
    reg = PatternAgentRegistry()
    return _text(json.dumps({"agents": reg.list_agents()}, ensure_ascii=False))


async def handle_agent_routing(args: dict) -> list[TextContent]:
    """Get smart routing report."""
    from src.smart_dispatcher import SmartDispatcher
    d = SmartDispatcher()
    report = d.get_routing_report()
    await d.close()
    return _text(json.dumps(report, ensure_ascii=False, default=str))


async def handle_agent_evolve(args: dict) -> list[TextContent]:
    """Run agent factory evolution."""
    from src.agent_factory import AgentFactory
    f = AgentFactory()
    evolutions = f.analyze_and_evolve()
    return _text(json.dumps({
        "count": len(evolutions),
        "evolutions": [
            {"pattern": e.pattern_type, "action": e.action,
             "old": e.old_value, "new": e.new_value,
             "reason": e.reason, "confidence": e.confidence}
            for e in evolutions
        ]
    }, ensure_ascii=False))


async def handle_pipeline_run(args: dict) -> list[TextContent]:
    """Run a named pipeline (code-review, smart-qa, trading-analysis, etc)."""
    from src.pipeline_composer import run_pipeline
    name = args.get("pipeline", "")
    prompt = args.get("prompt", "")
    if not name or not prompt:
        return _error("pipeline and prompt required")
    result = await run_pipeline(name, prompt)
    return _text(json.dumps({
        "ok": result.ok, "pipeline": result.pipeline_name,
        "total_ms": round(result.total_ms),
        "steps": result.steps,
        "output": result.final_output[:2000],
    }, ensure_ascii=False, default=str))


async def handle_pipeline_list(args: dict) -> list[TextContent]:
    """List available pipelines."""
    from src.pipeline_composer import PIPELINES
    return _text(json.dumps({"pipelines": list(PIPELINES.keys())}))


async def handle_agent_dashboard(args: dict) -> list[TextContent]:
    """Real-time agent monitoring dashboard."""
    from src.agent_monitor import get_monitor
    return _text(json.dumps(get_monitor().get_dashboard(), default=str))


async def handle_routing_optimizer(args: dict) -> list[TextContent]:
    """Routing optimization report with recommendations."""
    from src.routing_optimizer import RoutingOptimizer
    opt = RoutingOptimizer()
    return _text(json.dumps(opt.report(), ensure_ascii=False))


async def handle_adaptive_router_status(args: dict) -> list[TextContent]:
    """Adaptive router: circuits, health, affinities, recommendations."""
    from src.adaptive_router import get_router
    router = get_router()
    status = router.get_status()
    status["recommendations"] = router.get_recommendations()
    return _text(json.dumps(status, default=str, ensure_ascii=False))


async def handle_adaptive_router_pick(args: dict) -> list[TextContent]:
    """Pick optimal node(s) for a pattern."""
    from src.adaptive_router import get_router
    pattern = args.get("pattern", "code")
    count = int(args.get("count", 1))
    router = get_router()
    if count > 1:
        return _text(json.dumps({"nodes": router.pick_nodes(pattern, count=count)}))
    return _text(json.dumps({"node": router.pick_node(pattern)}))


async def handle_pattern_discovery(args: dict) -> list[TextContent]:
    """Discover new patterns from dispatch logs + behavior analysis."""
    from src.pattern_discovery import PatternDiscovery
    d = PatternDiscovery()
    return _text(json.dumps(d.full_report(), default=str, ensure_ascii=False))


async def handle_pattern_discovery_register(args: dict) -> list[TextContent]:
    """Discover and register new patterns in the database."""
    from src.pattern_discovery import PatternDiscovery
    d = PatternDiscovery()
    patterns = d.discover()
    count = d.register_patterns(patterns)
    return _text(json.dumps({"discovered": len(patterns), "registered": count}))


async def handle_orchestrate(args: dict) -> list[TextContent]:
    """Execute an orchestrated workflow (auto, deep-analysis, code-generate, consensus-3, trading-full, security-audit)."""
    from src.agent_orchestrator_v3 import Orchestrator
    prompt = args.get("prompt", "")
    workflow = args.get("workflow", "auto")
    budget_s = float(args.get("budget_s", 60))
    o = Orchestrator()
    r = await o.execute(prompt, workflow=workflow, budget_s=budget_s)
    await o.close()
    return _text(json.dumps({
        "ok": r.ok, "workflow": r.strategy_used,
        "content": r.final_content[:3000],
        "total_ms": round(r.total_latency_ms),
        "steps": len(r.steps), "summary": r.summary,
    }, ensure_ascii=False))


async def handle_orchestrate_consensus(args: dict) -> list[TextContent]:
    """Run consensus across N nodes."""
    from src.agent_orchestrator_v3 import Orchestrator
    prompt = args.get("prompt", "")
    min_agree = int(args.get("min_agree", 2))
    o = Orchestrator()
    r = await o.execute_consensus(prompt, min_agree=min_agree)
    await o.close()
    return _text(json.dumps({
        "ok": r.ok, "content": r.final_content[:3000],
        "total_ms": round(r.total_latency_ms),
        "nodes": r.nodes_used, "agreed": r.metadata.get("agreed", 0),
    }, ensure_ascii=False))


async def handle_orchestrate_race(args: dict) -> list[TextContent]:
    """Race N nodes for fastest response."""
    from src.agent_orchestrator_v3 import Orchestrator
    prompt = args.get("prompt", "")
    pattern = args.get("pattern", "code")
    count = int(args.get("count", 3))
    o = Orchestrator()
    r = await o.execute_race(prompt, pattern=pattern, count=count)
    await o.close()
    return _text(json.dumps({
        "ok": r.ok, "content": r.final_content[:3000],
        "total_ms": round(r.total_latency_ms),
        "winner": r.metadata.get("winner"),
    }, ensure_ascii=False))


async def handle_episodic_recall(args: dict) -> list[TextContent]:
    """Recall relevant episodes from episodic memory."""
    from src.agent_episodic_memory import get_episodic_memory
    query = args.get("query", "")
    top_k = int(args.get("top_k", 5))
    mem = get_episodic_memory()
    episodes = mem.recall(query, top_k=top_k)
    return _text(json.dumps([
        {"pattern": e.pattern, "node": e.node, "preview": e.prompt_preview,
         "ok": e.success, "quality": e.quality, "relevance": round(e.relevance, 2)}
        for e in episodes
    ], ensure_ascii=False))


async def handle_episodic_learn(args: dict) -> list[TextContent]:
    """Learn semantic facts from dispatch history."""
    from src.agent_episodic_memory import get_episodic_memory
    mem = get_episodic_memory()
    learned = mem.learn_from_history()
    return _text(json.dumps({"learned": learned, "total_facts": len(mem._facts)}, ensure_ascii=False))


async def handle_episodic_node(args: dict) -> list[TextContent]:
    """Get episodic memory for a node."""
    from src.agent_episodic_memory import get_episodic_memory
    node = args.get("node", "M1")
    return _text(json.dumps(get_episodic_memory().get_node_memory(node), ensure_ascii=False))


async def handle_episodic_pattern(args: dict) -> list[TextContent]:
    """Get episodic memory for a pattern."""
    from src.agent_episodic_memory import get_episodic_memory
    pattern = args.get("pattern", "code")
    return _text(json.dumps(get_episodic_memory().get_pattern_memory(pattern), ensure_ascii=False))


async def handle_self_improve(args: dict) -> list[TextContent]:
    """Run a self-improvement cycle."""
    from src.agent_self_improve import SelfImprover
    imp = SelfImprover()
    report = await imp.run_cycle()
    return _text(json.dumps({
        "cycle": report.cycle_id,
        "actions": len(report.actions),
        "high_conf": sum(1 for a in report.actions if a.confidence > 0.7),
        "recommendations": report.recommendations,
        "summary": report.summary,
    }, ensure_ascii=False))


async def handle_self_improve_history(args: dict) -> list[TextContent]:
    """Get improvement cycle history."""
    from src.agent_self_improve import SelfImprover
    return _text(json.dumps(SelfImprover().get_history(), default=str, ensure_ascii=False))


async def handle_collab_chain(args: dict) -> list[TextContent]:
    """Run agent collaboration chain."""
    from src.agent_collaboration import get_bus
    agents = [a.strip() for a in args.get("agents", "simple").split(",")]
    prompt = args.get("prompt", "")
    bus = get_bus()
    r = await bus.chain(agents, prompt)
    return _text(json.dumps({
        "ok": r.ok, "content": r.final_content[:2000],
        "chain": r.chain, "steps_ok": r.steps_ok, "summary": r.summary,
    }, ensure_ascii=False))


async def handle_collab_debate(args: dict) -> list[TextContent]:
    """Run multi-agent debate."""
    from src.agent_collaboration import get_bus
    agents = [a.strip() for a in args.get("agents", "code,reasoning").split(",")]
    question = args.get("question", "")
    bus = get_bus()
    r = await bus.debate(agents, question, rounds=2)
    return _text(json.dumps({
        "ok": r.ok, "content": r.final_content[:2000],
        "steps_ok": r.steps_ok, "total_ms": round(r.total_latency_ms),
    }, ensure_ascii=False))


async def handle_health_check(args: dict) -> list[TextContent]:
    """Full health check on all nodes."""
    from src.agent_health_guardian import HealthGuardian
    g = HealthGuardian()
    report = await g.check_all()
    return _text(json.dumps({
        "status": report.overall_status,
        "healthy": report.healthy_nodes, "total": report.total_nodes,
        "alerts": len(report.alerts), "summary": report.summary,
        "nodes": [{"node": n.node, "status": n.status, "ms": round(n.latency_ms)} for n in report.node_checks],
    }, ensure_ascii=False))


async def handle_health_heal(args: dict) -> list[TextContent]:
    """Auto-heal detected issues."""
    from src.agent_health_guardian import HealthGuardian
    g = HealthGuardian()
    healed = await g.auto_heal()
    return _text(json.dumps({"actions": healed}, ensure_ascii=False))


async def handle_benchmark_quick(args: dict) -> list[TextContent]:
    """Run quick benchmark."""
    from src.pattern_benchmark_runner import BenchmarkRunner
    r = BenchmarkRunner()
    report = await r.run_quick()
    await r.close()
    return _text(json.dumps({
        "success_rate": round(report.success_rate * 100, 1),
        "total": report.total_tests, "ok": report.success_count,
        "duration_ms": round(report.duration_ms), "summary": report.summary,
    }, ensure_ascii=False))


async def handle_task_planner(args: dict) -> list[TextContent]:
    """Plan a complex task."""
    from src.agent_task_planner import TaskPlanner
    prompt = args.get("prompt", "")
    p = TaskPlanner()
    plan = p.plan(prompt)
    return _text(json.dumps(p.plan_to_dict(plan), ensure_ascii=False))


async def handle_task_planner_execute(args: dict) -> list[TextContent]:
    """Plan and execute a complex task."""
    from src.agent_task_planner import TaskPlanner
    prompt = args.get("prompt", "")
    p = TaskPlanner()
    plan = p.plan(prompt)
    result = await p.execute_plan(plan)
    await p.close()
    return _text(json.dumps({
        "ok": result.ok, "output": result.final_output[:2000],
        "steps_ok": result.steps_ok, "summary": result.summary,
    }, ensure_ascii=False))


async def handle_feedback_quality(args: dict) -> list[TextContent]:
    """Quality report from feedback loop."""
    from src.agent_feedback_loop import get_feedback
    return _text(json.dumps(get_feedback().get_quality_report(), ensure_ascii=False))


async def handle_feedback_trends(args: dict) -> list[TextContent]:
    """Pattern quality trends."""
    from src.agent_feedback_loop import get_feedback
    trends = get_feedback().get_trends()
    return _text(json.dumps([
        {"pattern": t.pattern, "direction": t.direction,
         "recent": t.recent_quality, "change": t.change_pct}
        for t in trends
    ], ensure_ascii=False))


async def handle_feedback_adjustments(args: dict) -> list[TextContent]:
    """Suggested routing adjustments."""
    from src.agent_feedback_loop import get_feedback
    adj = get_feedback().suggest_adjustments()
    return _text(json.dumps([
        {"pattern": a.pattern, "action": a.action,
         "suggested": a.suggested, "reason": a.reason, "confidence": round(a.confidence, 2)}
        for a in adj
    ], ensure_ascii=False))


# ── Phase 13: Dispatch Engine ────────────────────────────────────────────────

async def handle_dispatch_engine_dispatch(args: dict) -> list[TextContent]:
    from src.dispatch_engine import get_engine
    engine = get_engine()
    result = await engine.dispatch(
        pattern=args.get("pattern", "simple"),
        prompt=args.get("prompt", ""),
        node_override=args.get("node"),
    )
    return _text(json.dumps({
        "pattern": result.pattern, "node": result.node,
        "content": result.content[:2000], "quality": result.quality,
        "latency_ms": round(result.latency_ms, 1),
        "pipeline_ms": round(result.pipeline_ms, 1),
        "success": result.success, "enriched": result.enriched,
        "fallback_used": result.fallback_used,
    }, ensure_ascii=False))


async def handle_dispatch_engine_stats(args: dict) -> list[TextContent]:
    from src.dispatch_engine import get_engine
    return _text(json.dumps(get_engine().get_stats(), ensure_ascii=False))


async def handle_dispatch_engine_report(args: dict) -> list[TextContent]:
    from src.dispatch_engine import get_engine
    return _text(json.dumps(get_engine().get_pipeline_report(), ensure_ascii=False))


async def handle_dispatch_analytics(args: dict) -> list[TextContent]:
    from src.dispatch_engine import get_engine
    return _text(json.dumps(get_engine().get_full_analytics(), ensure_ascii=False))


async def handle_dispatch_auto_optimize(args: dict) -> list[TextContent]:
    from src.pattern_agents import PatternAgentRegistry
    reg = PatternAgentRegistry()
    changes = reg.auto_optimize_strategies()
    return _text(json.dumps(changes, ensure_ascii=False))


async def handle_dispatch_quick_bench(args: dict) -> list[TextContent]:
    from src.pattern_agents import PatternAgentRegistry
    import httpx
    reg = PatternAgentRegistry()
    prompts = {
        "simple": "Bonjour", "code": "Ecris une fonction Python de tri",
        "analysis": "Compare MySQL vs PostgreSQL", "security": "Audit SQL injection",
        "architecture": "Design un systeme de cache distribue",
    }
    results = []
    async with httpx.AsyncClient() as client:
        for pat, prompt in prompts.items():
            agent = reg.agents.get(pat)
            if agent:
                try:
                    r = await agent.execute(client, prompt)
                    results.append({"pattern": pat, "ok": r.ok, "node": r.node, "ms": round(r.latency_ms)})
                except Exception as e:
                    results.append({"pattern": pat, "ok": False, "error": str(e)[:100]})
    ok = sum(1 for r in results if r.get("ok"))
    return _text(json.dumps({"ok": ok, "total": len(results), "rate": f"{ok/max(1,len(results))*100:.0f}%", "results": results}, ensure_ascii=False))


# ── Phase 13: Prompt Optimizer ───────────────────────────────────────────────

async def handle_prompt_optimize(args: dict) -> list[TextContent]:
    from src.agent_prompt_optimizer import get_optimizer
    result = get_optimizer().optimize(args.get("pattern", "simple"), args.get("prompt", ""))
    return _text(json.dumps(result, ensure_ascii=False))


async def handle_prompt_insights(args: dict) -> list[TextContent]:
    from src.agent_prompt_optimizer import get_optimizer
    return _text(json.dumps(get_optimizer().get_insights(args.get("pattern") or None), ensure_ascii=False))


async def handle_prompt_analyze(args: dict) -> list[TextContent]:
    from src.agent_prompt_optimizer import get_optimizer
    return _text(json.dumps(get_optimizer().analyze_prompt(
        args.get("pattern", "simple"), args.get("prompt", "")
    ), ensure_ascii=False))


async def handle_prompt_templates(args: dict) -> list[TextContent]:
    from src.agent_prompt_optimizer import get_optimizer
    return _text(json.dumps(get_optimizer().get_templates(), ensure_ascii=False))


# ── Phase 13: Auto Scaler ───────────────────────────────────────────────────

async def handle_auto_scaler_metrics(args: dict) -> list[TextContent]:
    from src.agent_auto_scaler import get_scaler
    metrics = get_scaler().get_load_metrics()
    return _text(json.dumps({n: {"avg_lat": m.avg_latency_ms, "p95": m.p95_latency_ms,
                                  "err_rate": m.error_rate, "req_5min": m.requests_last_5min}
                              for n, m in metrics.items()}, ensure_ascii=False))


async def handle_auto_scaler_evaluate(args: dict) -> list[TextContent]:
    from src.agent_auto_scaler import get_scaler
    actions = get_scaler().evaluate()
    return _text(json.dumps([{"type": a.action_type, "node": a.target_node,
                               "desc": a.description, "priority": a.priority}
                              for a in actions], ensure_ascii=False))


async def handle_auto_scaler_capacity(args: dict) -> list[TextContent]:
    from src.agent_auto_scaler import get_scaler
    return _text(json.dumps(get_scaler().get_capacity_report(), ensure_ascii=False))


# ── Phase 13: Event Stream ──────────────────────────────────────────────────

async def handle_event_stream_events(args: dict) -> list[TextContent]:
    from src.event_stream import get_stream
    events = get_stream().get_events(args.get("topic") or None, int(args.get("since_id", 0)), 50)
    return _text(json.dumps(events, ensure_ascii=False))


async def handle_event_stream_emit(args: dict) -> list[TextContent]:
    from src.event_stream import get_stream
    eid = get_stream().emit(args.get("topic", "system"), args.get("data", {}), args.get("source", "mcp"))
    return _text(f"Event #{eid} emitted")


async def handle_event_stream_stats(args: dict) -> list[TextContent]:
    from src.event_stream import get_stream
    return _text(json.dumps(get_stream().get_stats(), ensure_ascii=False))


# ── Phase 13: Agent Ensemble ────────────────────────────────────────────────

async def handle_ensemble_execute(args: dict) -> list[TextContent]:
    from src.agent_ensemble import get_ensemble
    result = await get_ensemble().execute(
        pattern=args.get("pattern", "simple"),
        prompt=args.get("prompt", ""),
        nodes=args.get("nodes", "").split(",") if args.get("nodes") else None,
        strategy=args.get("strategy", "best_of_n"),
    )
    return _text(json.dumps({
        "best_node": result.best_output.node,
        "best_score": round(result.best_output.total_score, 3),
        "agreement": round(result.agreement_score, 3),
        "ensemble_size": result.ensemble_size,
        "total_latency_ms": round(result.total_latency_ms, 1),
        "content_preview": result.best_output.content[:500],
    }, ensure_ascii=False))


async def handle_ensemble_stats(args: dict) -> list[TextContent]:
    from src.agent_ensemble import get_ensemble
    return _text(json.dumps(get_ensemble().get_ensemble_stats(), ensure_ascii=False))


# ── Phase 14: Quality Gate ───────────────────────────────────────────────────

async def handle_quality_gate_evaluate(args: dict) -> list[TextContent]:
    from src.quality_gate import get_gate
    result = get_gate().evaluate(
        args.get("pattern", "simple"), args.get("prompt", ""),
        args.get("content", ""), latency_ms=float(args.get("latency_ms", 0)),
    )
    return _text(json.dumps({
        "passed": result.passed, "score": result.overall_score,
        "failed": result.failed_gates, "suggestions": result.suggestions,
    }, ensure_ascii=False))


async def handle_quality_gate_report(args: dict) -> list[TextContent]:
    from src.quality_gate import get_gate
    return _text(json.dumps(get_gate().get_gate_report(), ensure_ascii=False))


# ── Phase 14: Pattern Lifecycle ──────────────────────────────────────────────

async def handle_lifecycle_health(args: dict) -> list[TextContent]:
    from src.pattern_lifecycle import get_lifecycle
    return _text(json.dumps(get_lifecycle().health_report(), ensure_ascii=False, default=str))


async def handle_lifecycle_actions(args: dict) -> list[TextContent]:
    from src.pattern_lifecycle import get_lifecycle
    return _text(json.dumps(get_lifecycle().suggest_actions(), ensure_ascii=False))


async def handle_lifecycle_evolve(args: dict) -> list[TextContent]:
    from src.pattern_lifecycle import get_lifecycle
    ok = get_lifecycle().evolve_pattern(
        args.get("pattern", ""), model=args.get("model"),
        strategy=args.get("strategy"),
    )
    return _text(f"Evolved: {ok}")


# ── Phase 14: Cluster Intelligence ──────────────────────────────────────────

async def handle_intelligence_report(args: dict) -> list[TextContent]:
    from src.cluster_intelligence import get_intelligence
    return _text(json.dumps(get_intelligence().full_report(), ensure_ascii=False, default=str))


async def handle_intelligence_status(args: dict) -> list[TextContent]:
    from src.cluster_intelligence import get_intelligence
    return _text(json.dumps(get_intelligence().quick_status(), ensure_ascii=False))


async def handle_intelligence_actions(args: dict) -> list[TextContent]:
    from src.cluster_intelligence import get_intelligence
    actions = get_intelligence().priority_actions()
    return _text(json.dumps([a.__dict__ for a in actions[:10]], ensure_ascii=False))


# ── Cowork Bridge v2 ────────────────────────────────────────────────────────

async def handle_cowork_v2_list(args: dict) -> list[TextContent]:
    from src.cowork_bridge import get_bridge
    scripts = get_bridge().list_scripts(args.get("category") or None)
    return _text(json.dumps(scripts[:50], ensure_ascii=False))


async def handle_cowork_v2_search(args: dict) -> list[TextContent]:
    from src.cowork_bridge import get_bridge
    results = get_bridge().search(args.get("query", ""), limit=20)
    return _text(json.dumps(results, ensure_ascii=False))


async def handle_cowork_v2_execute(args: dict) -> list[TextContent]:
    from src.cowork_bridge import get_bridge
    result = get_bridge().execute(args.get("script", ""), timeout_s=60)
    return _text(json.dumps({
        "script": result.script, "success": result.success,
        "exit_code": result.exit_code,
        "stdout": result.stdout[:2000], "stderr": result.stderr[:500],
        "duration_ms": round(result.duration_ms, 1),
    }, ensure_ascii=False))


async def handle_cowork_v2_stats(args: dict) -> list[TextContent]:
    from src.cowork_bridge import get_bridge
    return _text(json.dumps(get_bridge().get_stats(), ensure_ascii=False))


# ── Phase 15: Self-Improvement ──────────────────────────────────────────

async def handle_self_improvement_analyze(args: dict) -> list[TextContent]:
    from src.self_improvement import get_improver
    return _text(json.dumps(get_improver().analyze(), ensure_ascii=False, indent=2))

async def handle_self_improvement_suggest(args: dict) -> list[TextContent]:
    from src.self_improvement import get_improver
    actions = get_improver().suggest_improvements()
    data = [{"type": a.action_type, "target": a.target, "description": a.description,
             "priority": a.priority, "params": a.params} for a in actions]
    return _text(json.dumps(data, ensure_ascii=False, indent=2))

async def handle_self_improvement_apply(args: dict) -> list[TextContent]:
    from src.self_improvement import get_improver
    results = get_improver().apply_improvements(
        auto=args.get("auto", False),
        max_actions=int(args.get("max_actions", 5)),
    )
    return _text(json.dumps(results, ensure_ascii=False, indent=2))

async def handle_self_improvement_stats(args: dict) -> list[TextContent]:
    from src.self_improvement import get_improver
    return _text(json.dumps(get_improver().get_stats(), ensure_ascii=False))


# ── Phase 15: Dynamic Agents ───────────────────────────────────────────

async def handle_dynamic_agents_list(args: dict) -> list[TextContent]:
    from src.dynamic_agents import get_spawner
    return _text(json.dumps(get_spawner().list_agents(), ensure_ascii=False, indent=2))

async def handle_dynamic_agents_stats(args: dict) -> list[TextContent]:
    from src.dynamic_agents import get_spawner
    return _text(json.dumps(get_spawner().get_stats(), ensure_ascii=False, indent=2))

async def handle_dynamic_agents_dispatch(args: dict) -> list[TextContent]:
    from src.dynamic_agents import get_spawner
    result = await get_spawner().dispatch(
        args.get("pattern", ""), args.get("prompt", ""),
    )
    return _text(json.dumps(result, ensure_ascii=False, indent=2))

async def handle_dynamic_agents_register(args: dict) -> list[TextContent]:
    from src.dynamic_agents import get_spawner
    count = get_spawner().register_to_registry()
    return _text(json.dumps({"registered": count}))


# ── Phase 15: Cowork Proactive Engine ───────────────────────────────────

async def handle_cowork_proactive_needs(args: dict) -> list[TextContent]:
    from src.cowork_proactive import get_proactive
    needs = get_proactive().detect_needs()
    data = [{"category": n.category, "urgency": n.urgency,
             "description": n.description, "source": n.source} for n in needs]
    return _text(json.dumps(data, ensure_ascii=False, indent=2))

async def handle_cowork_proactive_run(args: dict) -> list[TextContent]:
    from src.cowork_proactive import get_proactive
    result = get_proactive().run_proactive(
        max_scripts=int(args.get("max_scripts", 5)),
        dry_run=args.get("dry_run", True),
    )
    return _text(json.dumps(result, ensure_ascii=False, indent=2))

async def handle_cowork_proactive_anticipate(args: dict) -> list[TextContent]:
    from src.cowork_proactive import get_proactive
    return _text(json.dumps(get_proactive().anticipate(), ensure_ascii=False, indent=2))

async def handle_cowork_proactive_stats(args: dict) -> list[TextContent]:
    from src.cowork_proactive import get_proactive
    return _text(json.dumps(get_proactive().get_stats(), ensure_ascii=False))

async def handle_linkedin_generate(args: dict) -> list[TextContent]:
    """Generate LinkedIn content (post FR + EN + 3 strategic comments)."""
    import subprocess
    idea = args.get("idea", "Les systemes IA distribues multi-GPU")
    topic = args.get("topic", "tech/IA")
    tone = args.get("tone", "expert")
    cmd = [sys.executable, str(Path("cowork/dev/linkedin_content_generator.py")),
           "--idea", idea, "--topic", topic, "--tone", tone, "--json"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                           cwd=str(Path(__file__).resolve().parent.parent))
        if r.returncode == 0:
            return _text(r.stdout)
        return _error(f"linkedin_generate failed: {r.stderr[:500]}")
    except subprocess.TimeoutExpired:
        return _error("linkedin_generate: timeout 300s")

async def handle_timeout_auto_fix(args: dict) -> list[TextContent]:
    """Auto-fix timeout values based on actual dispatch latency data."""
    from cowork.dev.timeout_auto_fixer import analyze_timeouts, suggest_adjustments, apply_adjustments
    dry_run = args.get("dry_run", False)
    pattern_stats, node_stats = analyze_timeouts()
    suggestions = suggest_adjustments(pattern_stats, node_stats)
    applied = apply_adjustments(suggestions, dry_run=dry_run)
    problems = [ps for ps in pattern_stats if ps["timeouts"] > 0]
    return _text(json.dumps({
        "problems": len(problems), "suggestions": len(suggestions),
        "applied": applied, "dry_run": dry_run,
    }, ensure_ascii=False, indent=2))

async def handle_dispatch_integration_test(args: dict) -> list[TextContent]:
    """Run dispatch pipeline integration tests."""
    from cowork.dev.dispatch_integration_test import main as run_tests
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        ok = run_tests()
    return _text(buf.getvalue() + f"\n\nResult: {'ALL PASS' if ok else 'SOME FAILED'}")


# ── Phase 15: Reflection Engine ─────────────────────────────────────────

async def handle_reflection_insights(args: dict) -> list[TextContent]:
    from src.reflection_engine import get_reflection
    insights = get_reflection().reflect()
    data = [{"category": i.category, "severity": i.severity, "title": i.title,
             "description": i.description, "recommendation": i.recommendation}
            for i in insights]
    return _text(json.dumps(data, ensure_ascii=False, indent=2))

async def handle_reflection_summary(args: dict) -> list[TextContent]:
    from src.reflection_engine import get_reflection
    return _text(json.dumps(get_reflection().get_summary(), ensure_ascii=False, indent=2))

async def handle_reflection_timeline(args: dict) -> list[TextContent]:
    from src.reflection_engine import get_reflection
    hours = int(args.get("hours", 24))
    return _text(json.dumps(get_reflection().timeline_analysis(hours), ensure_ascii=False, indent=2))


# ── Phase 16: Pattern Evolution ─────────────────────────────────────────

async def handle_evolution_gaps(args: dict) -> list[TextContent]:
    from src.pattern_evolution import get_evolution
    suggestions = get_evolution().analyze_gaps()
    data = [{"action": s.action, "pattern": s.pattern_type,
             "description": s.description, "confidence": s.confidence}
            for s in suggestions]
    return _text(json.dumps(data, ensure_ascii=False, indent=2))

async def handle_evolution_create(args: dict) -> list[TextContent]:
    from src.pattern_evolution import get_evolution
    result = get_evolution().auto_create_patterns(
        min_confidence=float(args.get("min_confidence", 0.5)),
    )
    return _text(json.dumps(result, ensure_ascii=False, indent=2))

async def handle_evolution_stats(args: dict) -> list[TextContent]:
    from src.pattern_evolution import get_evolution
    return _text(json.dumps(get_evolution().get_stats(), ensure_ascii=False))


# ═══════════════════════════════════════════════════════════════════════════
# TOOL REGISTRY
# ═══════════════════════════════════════════════════════════════════════════

TOOL_DEFINITIONS: list[tuple[str, str, dict, Any]] = [
    # LM Studio (4)
    ("lm_query", "Interroger un noeud LM Studio.", {"prompt": "string", "node": "string", "model": "string"}, handle_lm_query),
    ("lm_models", "Lister les modeles charges sur un noeud.", {"node": "string"}, handle_lm_models),
    ("lm_cluster_status", "Sante de tous les noeuds du cluster (LM Studio + Ollama).", {}, handle_lm_cluster_status),
    ("system_audit", "Audit complet du cluster — 10 sections, risques, scores readiness (0-100).", {"mode": "string (full|quick)"}, handle_system_audit),
    ("consensus", "Consensus multi-IA sur une question.", {"prompt": "string", "nodes": "string", "timeout_per_node": "number"}, handle_consensus),
    # LM Studio MCP (2)
    ("lm_mcp_query", "Interroger LM Studio avec serveurs MCP.", {"prompt": "string", "node": "string", "model": "string", "servers": "string", "allowed_tools": "string", "context_length": "number"}, handle_lm_mcp_query),
    ("lm_list_mcp_servers", "Lister les serveurs MCP disponibles.", {}, handle_lm_list_mcp_servers),
    # Gemini + Bridge Multi-Noeuds (3)
    ("gemini_query", "Interroger Gemini via proxy.", {"prompt": "string", "json_mode": "boolean"}, handle_gemini_query),
    ("bridge_query", "Routage intelligent vers le meilleur noeud.", {"prompt": "string", "task_type": "string", "preferred_node": "string"}, handle_bridge_query),
    ("bridge_mesh", "Requete parallele sur N noeuds.", {"prompt": "string", "nodes": "string", "timeout_per_node": "number"}, handle_bridge_mesh),
    # LM Studio Model Management (5)
    ("lm_load_model", "Charger un modele sur M1.", {"model": "string", "context": "number", "parallel": "number"}, handle_lm_load_model),
    ("lm_unload_model", "Decharger un modele de M1.", {"model": "string"}, handle_lm_unload_model),
    ("lm_switch_coder", "Basculer M1 en mode code.", {}, handle_lm_switch_coder),
    ("lm_switch_dev", "Basculer M1 en mode dev.", {}, handle_lm_switch_dev),
    ("lm_gpu_stats", "Statistiques GPU detaillees.", {}, handle_lm_gpu_stats),
    # Benchmark (1)
    ("lm_benchmark", "Benchmark latence inference.", {"nodes": "string"}, handle_lm_benchmark),
    # Ollama Cloud (4 + 3 cloud)
    ("ollama_query", "Interroger Ollama (local ou cloud).", {"prompt": "string", "model": "string"}, handle_ollama_query),
    ("ollama_models", "Lister les modeles Ollama disponibles.", {}, handle_ollama_models),
    ("ollama_pull", "Telecharger un modele Ollama.", {"model_name": "string"}, handle_ollama_pull),
    ("ollama_status", "Sante du backend Ollama.", {}, handle_ollama_status),
    # Ollama Cloud — Web Search + Sub-agents (3)
    ("ollama_web_search", "Recherche web via Ollama cloud.", {"query": "string", "model": "string"}, handle_ollama_web_search),
    ("ollama_subagents", "3 sous-agents Ollama cloud en parallele.", {"task": "string", "aspects": "string"}, handle_ollama_subagents),
    ("ollama_trading_analysis", "Analyse trading via 3 agents cloud.", {"pair": "string", "timeframe": "string"}, handle_ollama_trading_analysis),
    # Trading AI v2.2 (1)
    ("trading_pipeline_v2", "Pipeline GPU Trading AI v2.2 — 100 strategies + consensus 5 IA.", {"coins": "number", "top": "number", "quick": "boolean", "no_ai": "boolean", "json_output": "boolean"}, handle_trading_pipeline_v2),
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
    # Brain — Autonomous Learning (4)
    ("brain_status", "Status du cerveau JARVIS (patterns, skills appris).", {}, handle_brain_status),
    ("brain_analyze", "Analyser les patterns d'utilisation.", {"auto_create": "boolean", "min_confidence": "number"}, handle_brain_analyze),
    ("brain_suggest", "Demander au cluster IA de suggerer un nouveau skill.", {"context": "string", "node_url": "string"}, handle_brain_suggest),
    ("brain_learn", "Auto-apprendre: detecter patterns et creer skills.", {}, handle_brain_learn),
    # Dictionary CRUD (1)
    ("dict_crud", "CRUD operations on dictionary tables (pipeline_dictionary, domino_chains, voice_corrections). Args: operation (add|edit|delete|search|stats), table, data (JSON string with fields).",
     {"operation": "string", "table": "string", "data": "string"}, handle_dict_crud),
    # Domino Pipelines (3)
    ("execute_domino", "Executer un domino pipeline par ID ou texte de trigger vocal.", {"domino_id": "string"}, handle_execute_domino),
    ("list_dominos", "Lister tous les domino pipelines disponibles.", {"category": "string"}, handle_list_dominos),
    ("domino_stats", "Historique d'execution des dominos.", {"limit": "number"}, handle_domino_stats),
    # Security (3) — v10.6
    ("security_score", "Calculer le score de securite actuel du systeme.", {}, handle_security_score),
    ("security_audit_log", "Consulter les evenements de securite recents.", {"limit": "number", "severity": "string"}, handle_security_audit_log),
    ("security_scan", "Scanner les configurations pour vulnerabilites.", {}, handle_security_scan),
    # Analytics (2) — v10.6
    ("cluster_analytics", "Metriques de performance du cluster (latence, throughput, erreurs).", {"hours": "number"}, handle_cluster_analytics),
    ("voice_analytics", "Statistiques du pipeline vocal (recognition rate, latence, cache hits).", {}, handle_voice_analytics),
    # Observability (3) — v10.6
    ("observability_report", "Rapport complet matrice observabilite (heatmap, correlations, anomalies).", {}, handle_observability_report),
    ("observability_heatmap", "Donnees heatmap pour dashboard (metriques par noeud).", {"window": "string"}, handle_observability_heatmap),
    ("observability_alerts", "Alertes anomalies actives.", {"threshold": "number"}, handle_observability_alerts),
    # Drift Detection (3) — v10.6
    ("drift_check", "Verifier le drift qualite de tous les modeles.", {}, handle_drift_check),
    ("drift_model_health", "Sante d'un modele specifique ou de tous.", {"model": "string"}, handle_drift_model_health),
    ("drift_reroute", "Suggestion de rerouting basee sur le drift.", {"task_type": "string", "candidates": "string"}, handle_drift_reroute),
    # Auto-Tune (3) — v10.6
    ("auto_tune_status", "Status du scheduler auto-tune (CPU, GPU, load, threads).", {}, handle_auto_tune_status),
    ("auto_tune_sample", "Prendre un echantillon de ressources (CPU, GPU, memoire).", {}, handle_auto_tune_sample),
    ("auto_tune_cooldown", "Mettre un noeud en cooldown.", {"node": "string", "seconds": "number"}, handle_auto_tune_cooldown),
    # Trading v3 (3) — v10.6
    ("trading_backtest_list", "Lister les resultats de backtests.", {}, handle_trading_backtest_list),
    ("trading_strategy_rankings", "Classement des strategies par performance.", {"top_n": "number"}, handle_trading_strategy_rankings),
    ("trading_flow_status", "Status des flux trading actifs.", {}, handle_trading_flow_status),
    # Intent Classifier (2) — v10.6
    ("intent_classify", "Classifier l'intent d'un texte/voix.", {"text": "string"}, handle_intent_classify),
    ("intent_report", "Rapport de precision du classifieur d'intents.", {}, handle_intent_report),
    # Tool Metrics (3) — v10.6
    ("tool_metrics_report", "Metriques performance des outils MCP (latence, succes, cache).", {}, handle_tool_metrics_report),
    ("cache_stats", "Statistiques du cache de reponses.", {}, handle_cache_stats),
    ("cache_clear", "Vider le cache de reponses.", {"category": "string"}, handle_cache_clear),
    # Database Maintenance (2) — v10.6
    ("db_health", "Sante des bases de donnees (integrite, taille, maintenance).", {}, handle_db_health),
    ("db_maintenance", "Lancer la maintenance (VACUUM + ANALYZE).", {"force": "boolean"}, handle_db_maintenance),
    # Orchestrator V2 (9) — Phase 4
    ("orch_dashboard", "Dashboard complet orchestrator_v2 (observabilite + drift + tune + routing + budget).", {}, handle_orch_dashboard),
    ("orch_node_stats", "Statistiques par noeud (appels, taux succes, latence, tokens).", {}, handle_orch_node_stats),
    ("orch_budget", "Rapport budget tokens de la session.", {}, handle_orch_budget),
    ("orch_reset_budget", "Reset du budget tokens de la session.", {}, handle_orch_reset_budget),
    ("orch_fallback", "Chaine de fallback drift-aware pour un type de tache.", {"task_type": "string", "exclude": "string"}, handle_orch_fallback),
    ("orch_best_node", "Meilleur noeud pour un type de tache (scoring + drift).", {"task_type": "string"}, handle_orch_best_node),
    ("orch_record_call", "Enregistrer un appel manuellement (calibration).", {"node": "string", "latency_ms": "number", "success": "boolean", "tokens": "number", "quality": "number"}, handle_orch_record_call),
    ("orch_health", "Score sante cluster 0-100 + alertes actives.", {}, handle_orch_health),
    ("orch_routing_matrix", "Afficher la matrice de routage complete.", {}, handle_orch_routing_matrix),
    # Task Queue (4) — Phase 4 Vague 2
    ("task_enqueue", "Ajouter une tache a la queue intelligente.", {"prompt": "string", "task_type": "string", "priority": "number"}, handle_task_enqueue),
    ("task_list", "Lister les taches en attente.", {"limit": "number"}, handle_task_list),
    ("task_status", "Statistiques de la queue de taches.", {}, handle_task_status),
    ("task_cancel", "Annuler une tache en attente.", {"task_id": "string"}, handle_task_cancel),
    # Notifications (3) — Phase 4 Vague 2
    ("notif_send", "Envoyer une notification (info/warning/critical).", {"message": "string", "level": "string", "source": "string"}, handle_notif_send),
    ("notif_history", "Historique des notifications.", {"limit": "number"}, handle_notif_history),
    ("notif_stats", "Statistiques des notifications.", {}, handle_notif_stats),
    # Autonomous Loop (3) — Phase 4 Vague 2
    ("autonomous_status", "Status complet de la boucle autonome.", {}, handle_autonomous_status),
    ("autonomous_events", "Evenements recents de la boucle autonome.", {"limit": "number"}, handle_autonomous_events),
    ("autonomous_toggle", "Activer/desactiver une tache autonome.", {"task_name": "string", "enabled": "boolean"}, handle_autonomous_toggle),
    # Agent Memory (4) — Phase 4 Vague 3
    ("memory_remember", "Stocker un souvenir persistant.", {"content": "string", "category": "string", "importance": "number"}, handle_memory_remember),
    ("memory_recall", "Rechercher dans la memoire par similarite.", {"query": "string", "limit": "number", "category": "string"}, handle_memory_recall),
    ("memory_list", "Lister tous les souvenirs.", {"category": "string", "limit": "number"}, handle_memory_list),
    ("memory_forget", "Supprimer un souvenir.", {"memory_id": "number"}, handle_memory_forget),
    # Conversation Store (4) — Phase 4 Vague 4
    ("conv_create", "Creer une nouvelle conversation.", {"title": "string", "source": "string"}, handle_conv_create),
    ("conv_add_turn", "Ajouter un echange a une conversation.", {"conv_id": "string", "node": "string", "prompt": "string", "response": "string", "latency_ms": "number", "tokens": "number"}, handle_conv_add_turn),
    ("conv_list", "Lister les conversations recentes.", {"limit": "number", "source": "string"}, handle_conv_list),
    ("conv_stats", "Statistiques des conversations.", {}, handle_conv_stats),
    # Load Balancer (2) — Phase 4 Vague 4
    ("lb_pick", "Choisir le meilleur noeud via load balancer.", {"task_type": "string"}, handle_lb_pick),
    ("lb_status", "Status du load balancer (actifs, circuit breakers).", {}, handle_lb_status),
    # Proactive Agent (2) — Phase 4 Vague 4
    ("proactive_analyze", "Lancer l'analyse proactive et obtenir des suggestions.", {}, handle_proactive_analyze),
    ("proactive_dismiss", "Rejeter une suggestion proactive.", {"key": "string"}, handle_proactive_dismiss),
    # Auto-Optimizer (3) — Phase 5
    ("optimizer_optimize", "Lancer un cycle d'auto-optimisation.", {}, handle_optimizer_optimize),
    ("optimizer_history", "Historique des ajustements auto.", {"limit": "number"}, handle_optimizer_history),
    ("optimizer_stats", "Stats de l'auto-optimiseur.", {}, handle_optimizer_stats),
    # Event Bus (2) — Phase 5 Vague 5
    ("eventbus_emit", "Emettre un event sur le bus.", {"event": "string", "data": "string"}, handle_eventbus_emit),
    ("eventbus_stats", "Stats du bus d'evenements.", {}, handle_eventbus_stats),
    # Metrics Aggregator (3) — Phase 5 Vague 5
    ("metrics_snapshot", "Snapshot temps reel de toutes les metriques.", {}, handle_metrics_snapshot),
    ("metrics_history", "Historique des metriques (derniere heure).", {"minutes": "number"}, handle_metrics_history),
    ("metrics_summary", "Resume du metrics aggregator.", {}, handle_metrics_summary),
    # Workflow Engine (4) — Phase 6
    ("workflow_create", "Creer un workflow multi-etapes.", {"name": "string", "steps": "string"}, handle_workflow_create),
    ("workflow_list", "Lister les workflows.", {"limit": "number"}, handle_workflow_list),
    ("workflow_execute", "Executer un workflow.", {"workflow_id": "string"}, handle_workflow_execute),
    ("workflow_stats", "Stats du moteur de workflows.", {}, handle_workflow_stats),
    # Session Manager (4) — Phase 6
    ("session_create", "Creer une session utilisateur.", {"source": "string"}, handle_session_create),
    ("session_context", "Obtenir le contexte d'une session.", {"session_id": "string"}, handle_session_context),
    ("session_list", "Lister les sessions.", {"limit": "number"}, handle_session_list),
    ("session_stats", "Stats des sessions.", {}, handle_session_stats),
    # Alert Manager (5) — Phase 6
    ("alert_fire", "Declencher une alerte.", {"key": "string", "message": "string", "level": "string", "source": "string"}, handle_alert_fire),
    ("alert_active", "Lister les alertes actives.", {"level": "string"}, handle_alert_active),
    ("alert_acknowledge", "Acquitter une alerte.", {"key": "string"}, handle_alert_acknowledge),
    ("alert_resolve", "Resoudre une alerte.", {"key": "string"}, handle_alert_resolve),
    ("alert_stats", "Stats des alertes.", {}, handle_alert_stats),
    # Config Manager (4) — Phase 7
    ("config_get", "Lire une valeur de config.", {"key": "string"}, handle_config_get),
    ("config_set", "Modifier une valeur de config.", {"key": "string", "value": "string"}, handle_config_set),
    ("config_reload", "Hot-reload de la config depuis le disque.", {}, handle_config_reload),
    ("config_stats", "Stats du config manager.", {}, handle_config_stats),
    # Audit Trail (3) — Phase 7
    ("audit_log", "Logger une action dans l'audit trail.", {"action_type": "string", "action": "string", "source": "string", "details": "string"}, handle_audit_log),
    ("audit_search", "Rechercher dans l'audit trail.", {"action_type": "string", "source": "string", "query": "string", "limit": "number"}, handle_audit_search),
    ("audit_stats", "Stats de l'audit trail.", {}, handle_audit_stats),
    # Cluster Diagnostics (3) — Phase 7
    ("diagnostics_run", "Diagnostic complet du cluster avec recommandations.", {}, handle_diagnostics_run),
    ("diagnostics_quick", "Status rapide du cluster.", {}, handle_diagnostics_quick),
    ("diagnostics_history", "Historique des diagnostics.", {}, handle_diagnostics_history),
    # Rate Limiter (3) — Phase 8
    ("ratelimit_check", "Verifier si une requete est autorisee (token bucket).", {"node": "string"}, handle_ratelimit_check),
    ("ratelimit_stats", "Stats du rate limiter (tous les noeuds).", {}, handle_ratelimit_stats),
    ("ratelimit_configure", "Configurer le rate limit d'un noeud.", {"node": "string", "rps": "number", "burst": "number"}, handle_ratelimit_configure),
    # Task Scheduler (4) — Phase 8
    ("scheduler_list", "Lister les jobs planifies.", {}, handle_scheduler_list),
    ("scheduler_add", "Ajouter un job planifie.", {"name": "string", "action": "string", "interval_s": "number", "params": "string", "one_shot": "boolean"}, handle_scheduler_add),
    ("scheduler_remove", "Supprimer un job planifie.", {"job_id": "string"}, handle_scheduler_remove),
    ("scheduler_stats", "Stats du planificateur.", {}, handle_scheduler_stats),
    # Health Dashboard (3) — Phase 8
    ("health_full", "Rapport complet du dashboard sante.", {}, handle_health_full),
    ("health_summary", "Resume rapide de la sante cluster.", {}, handle_health_summary),
    ("health_history", "Historique des rapports sante.", {}, handle_health_history),
    # Plugin Manager (3) — Phase 9
    ("plugin_list", "Lister les plugins charges.", {}, handle_plugin_list),
    ("plugin_discover", "Decouvrir les plugins disponibles.", {}, handle_plugin_discover),
    ("plugin_stats", "Stats du gestionnaire de plugins.", {}, handle_plugin_stats),
    # Command Router (3) — Phase 9
    ("cmd_route", "Router une commande naturelle.", {"text": "string"}, handle_cmd_route),
    ("cmd_routes", "Lister toutes les routes de commandes.", {}, handle_cmd_routes),
    ("cmd_stats", "Stats du routeur de commandes.", {}, handle_cmd_stats),
    # Resource Monitor (3) — Phase 9
    ("resource_sample", "Snapshot ressources systeme (CPU/RAM/GPU/Disque).", {}, handle_resource_sample),
    ("resource_latest", "Dernier snapshot ressources.", {}, handle_resource_latest),
    ("resource_stats", "Stats du moniteur de ressources.", {}, handle_resource_stats),
    # Retry Manager (2) — Phase 10
    ("retry_stats", "Stats du retry manager et circuit breakers.", {}, handle_retry_stats),
    ("retry_reset", "Reset tous les circuit breakers.", {}, handle_retry_reset),
    # Data Pipeline (3) — Phase 10
    ("data_pipeline_list", "Lister les data pipelines.", {}, handle_data_pipeline_list),
    ("pipeline_history", "Historique des executions de pipelines.", {}, handle_pipeline_history),
    ("pipeline_stats", "Stats des data pipelines.", {}, handle_pipeline_stats),
    # Service Registry (4) — Phase 10
    ("service_register", "Enregistrer un service.", {"name": "string", "url": "string", "service_type": "string"}, handle_service_register),
    ("service_list", "Lister les services enregistres.", {}, handle_service_list),
    ("service_heartbeat", "Heartbeat d'un service.", {"name": "string"}, handle_service_heartbeat),
    ("service_stats", "Stats du registre de services.", {}, handle_service_stats),
    # Cache Manager (3) — Phase 11
    ("cache_get", "Lire une valeur en cache.", {"key": "string", "namespace": "string"}, handle_cache_get),
    ("cache_set", "Stocker une valeur en cache.", {"key": "string", "value": "string", "namespace": "string", "ttl_s": "number"}, handle_cache_set),
    ("cache_mgr_stats", "Stats du cache manager (L1/L2 hit rates).", {}, handle_cache_mgr_stats),
    # Secret Vault (2) — Phase 11
    ("vault_list", "Lister les secrets (sans valeurs).", {}, handle_vault_list),
    ("vault_stats", "Stats du coffre-fort.", {}, handle_vault_stats),
    # Dependency Graph (4) — Phase 11
    ("depgraph_show", "Afficher le graphe de dependances.", {}, handle_depgraph_show),
    ("depgraph_impact", "Analyse d'impact si un module tombe.", {"node": "string"}, handle_depgraph_impact),
    ("depgraph_order", "Ordre de demarrage (tri topologique).", {}, handle_depgraph_order),
    ("depgraph_stats", "Stats du graphe de dependances.", {}, handle_depgraph_stats),
    # Notification Hub (+1 channel) — Phase 12
    ("notif_channels", "Lister les canaux de notification.", {}, handle_notif_channels),
    # Feature Flags (4) — Phase 12
    ("flag_list", "Lister les feature flags.", {}, handle_flag_list),
    ("flag_check", "Verifier si un flag est actif.", {"name": "string", "context": "string"}, handle_flag_check),
    ("flag_toggle", "Activer/desactiver un feature flag.", {"name": "string", "enabled": "boolean"}, handle_flag_toggle),
    ("flag_stats", "Stats des feature flags.", {}, handle_flag_stats),
    # Backup Manager (3) — Phase 12
    ("backup_list", "Lister les sauvegardes.", {"source": "string"}, handle_backup_list),
    ("backup_create", "Creer une sauvegarde de fichier.", {"source": "string", "tag": "string"}, handle_backup_create),
    ("backup_stats", "Stats du gestionnaire de sauvegardes.", {}, handle_backup_stats),
    # Session Manager V2 (3) — Phase 13
    ("session_v2_list", "Lister les sessions actives.", {"owner": "string", "status": "string"}, handle_session_v2_list),
    ("session_v2_create", "Creer une nouvelle session.", {"owner": "string"}, handle_session_v2_create),
    ("session_v2_stats", "Stats du gestionnaire de sessions.", {}, handle_session_v2_stats),
    # Queue Manager (2) — Phase 13
    ("queue_list", "Lister les taches en file d'attente.", {"status": "string"}, handle_queue_list),
    ("queue_stats", "Stats de la file d'attente.", {}, handle_queue_stats),
    # API Gateway (3) — Phase 13
    ("apigw_routes", "Lister les routes de l'API gateway.", {}, handle_apigw_routes),
    ("apigw_clients", "Lister les clients de l'API gateway.", {}, handle_apigw_clients),
    ("apigw_stats", "Stats de l'API gateway.", {}, handle_apigw_stats),
    # Template Engine (3) — Phase 14
    ("template_list", "Lister les templates enregistres.", {}, handle_template_list),
    ("template_render", "Rendre un template nomme.", {"name": "string", "context": "string"}, handle_template_render),
    ("template_stats", "Stats du moteur de templates.", {}, handle_template_stats),
    # State Machine (2) — Phase 14
    ("fsm_list", "Lister les machines a etats.", {}, handle_fsm_list),
    ("fsm_stats", "Stats des machines a etats.", {}, handle_fsm_stats),
    # Log Aggregator (3) — Phase 14
    ("logagg_query", "Chercher dans les logs agreges.", {"level": "string", "source": "string", "search": "string", "limit": "number"}, handle_logagg_query),
    ("logagg_sources", "Lister les sources de logs.", {}, handle_logagg_sources),
    ("logagg_stats", "Stats de l'agregateur de logs.", {}, handle_logagg_stats),
    # Permission Manager (4) — Phase 15
    ("perm_roles", "Lister les roles RBAC.", {}, handle_perm_roles),
    ("perm_users", "Lister les utilisateurs et leurs roles.", {}, handle_perm_users),
    ("perm_check", "Verifier une permission.", {"user_id": "string", "permission": "string"}, handle_perm_check),
    ("perm_stats", "Stats du gestionnaire de permissions.", {}, handle_perm_stats),
    # Environment Manager (3) — Phase 15
    ("env_profiles", "Lister les profils d'environnement.", {}, handle_env_profiles),
    ("env_get", "Obtenir les variables d'un profil.", {"profile": "string"}, handle_env_get),
    ("env_stats", "Stats du gestionnaire d'environnements.", {}, handle_env_stats),
    # Telemetry Collector (3) — Phase 15
    ("telemetry_counters", "Lister les compteurs de telemetrie.", {}, handle_telemetry_counters),
    ("telemetry_gauges", "Lister les jauges de telemetrie.", {}, handle_telemetry_gauges),
    ("telemetry_stats", "Stats du collecteur de telemetrie.", {}, handle_telemetry_stats),
    # Event Store (3) — Phase 16
    ("evstore_streams", "Lister les streams d'evenements.", {}, handle_evstore_streams),
    ("evstore_events", "Consulter les evenements d'un stream.", {"stream": "string", "limit": "number"}, handle_evstore_events),
    ("evstore_stats", "Stats de l'event store.", {}, handle_evstore_stats),
    # Webhook Manager (3) — Phase 16
    ("webhook_list", "Lister les webhooks enregistres.", {}, handle_webhook_list),
    ("webhook_history", "Historique des livraisons webhook.", {"name": "string"}, handle_webhook_history),
    ("webhook_stats", "Stats du webhook manager.", {}, handle_webhook_stats),
    # Health Probe (3) — Phase 16
    ("hprobe_list", "Lister les probes de sante.", {}, handle_hprobe_list),
    ("hprobe_run", "Executer un ou tous les health checks.", {"name": "string"}, handle_hprobe_run),
    ("hprobe_stats", "Stats des health probes.", {}, handle_hprobe_stats),
    # Service Mesh (3) — Phase 17
    ("mesh_services", "Lister les instances de service.", {}, handle_mesh_services),
    ("mesh_names", "Lister les noms de services uniques.", {}, handle_mesh_names),
    ("mesh_stats", "Stats du service mesh.", {}, handle_mesh_stats),
    # Config Vault (3) — Phase 17
    ("cfgvault_namespaces", "Lister les namespaces du config vault.", {}, handle_cfgvault_namespaces),
    ("cfgvault_keys", "Lister les cles d'un namespace config vault.", {"namespace": "string"}, handle_cfgvault_keys),
    ("cfgvault_stats", "Stats du config vault.", {}, handle_cfgvault_stats),
    # Rule Engine (3) — Phase 17
    ("rules_list", "Lister les regles du moteur.", {"group": "string"}, handle_rules_list),
    ("rules_groups", "Lister les groupes de regles.", {}, handle_rules_groups),
    ("rules_stats", "Stats du moteur de regles.", {}, handle_rules_stats),
    # Retry Policy (3) — Phase 18
    ("retrypol_list", "Lister les politiques de retry.", {}, handle_retrypol_list),
    ("retrypol_history", "Historique des retries.", {}, handle_retrypol_history),
    ("retrypol_stats", "Stats des politiques de retry.", {}, handle_retrypol_stats),
    # Message Broker (3) — Phase 18
    ("broker_topics", "Lister les topics du broker.", {}, handle_broker_topics),
    ("broker_messages", "Consulter les messages d'un topic.", {"topic": "string"}, handle_broker_messages),
    ("broker_stats", "Stats du message broker.", {}, handle_broker_stats),
    # Command Registry (3) — Phase 18
    ("cmdreg_list", "Lister les commandes enregistrees.", {"category": "string"}, handle_cmdreg_list),
    ("cmdreg_categories", "Lister les categories de commandes.", {}, handle_cmdreg_categories),
    ("cmdreg_stats", "Stats du registre de commandes.", {}, handle_cmdreg_stats),
    # Process Manager (3) — Phase 19
    ("procmgr_list", "Lister les processus manages.", {"group": "string"}, handle_procmgr_list),
    ("procmgr_events", "Historique des evenements processus.", {"name": "string"}, handle_procmgr_events),
    ("procmgr_stats", "Stats du gestionnaire de processus.", {}, handle_procmgr_stats),
    # Data Validator (3) — Phase 19
    ("dataval_schemas", "Lister les schemas de validation.", {}, handle_dataval_schemas),
    ("dataval_history", "Historique des validations.", {}, handle_dataval_history),
    ("dataval_stats", "Stats du validateur de donnees.", {}, handle_dataval_stats),
    # File Watcher (3) — Phase 19
    ("fwatch_list", "Lister les watches fichier actifs.", {"group": "string"}, handle_fwatch_list),
    ("fwatch_events", "Evenements de changement fichier.", {"watch_name": "string"}, handle_fwatch_events),
    ("fwatch_stats", "Stats du file watcher.", {}, handle_fwatch_stats),
    # Clipboard Manager (3) — Phase 20
    ("clipmgr_history", "Historique du presse-papier.", {"category": "string"}, handle_clipmgr_history),
    ("clipmgr_search", "Rechercher dans l'historique clipboard.", {"query": "string"}, handle_clipmgr_search),
    ("clipmgr_stats", "Stats du clipboard manager.", {}, handle_clipmgr_stats),
    # Shortcut Manager (3) — Phase 20
    ("hotkey_list", "Lister les raccourcis clavier.", {"group": "string"}, handle_hotkey_list),
    ("hotkey_activations", "Historique des activations hotkey.", {"name": "string"}, handle_hotkey_activations),
    ("hotkey_stats", "Stats du shortcut manager.", {}, handle_hotkey_stats),
    # Snapshot Manager (3) — Phase 20
    ("snapmgr_list", "Lister les snapshots systeme.", {"tag": "string"}, handle_snapmgr_list),
    ("snapmgr_restores", "Historique des restaurations.", {}, handle_snapmgr_restores),
    ("snapmgr_stats", "Stats du snapshot manager.", {}, handle_snapmgr_stats),
    # Network Scanner (3) — Phase 21
    ("netscan_profiles", "Lister les profils de scan reseau.", {}, handle_netscan_profiles),
    ("netscan_history", "Historique des scans reseau.", {}, handle_netscan_history),
    ("netscan_stats", "Stats du scanner reseau.", {}, handle_netscan_stats),
    # Cron Manager (3) — Phase 21
    ("cron_list", "Lister les taches cron.", {"group": "string"}, handle_cron_list),
    ("cron_executions", "Historique des executions cron.", {"name": "string"}, handle_cron_executions),
    ("cron_stats", "Stats du cron manager.", {}, handle_cron_stats),
    # App Launcher (3) — Phase 21
    ("applnch_list", "Lister les applications enregistrees.", {"group": "string"}, handle_applnch_list),
    ("applnch_history", "Historique des lancements.", {"app_name": "string"}, handle_applnch_history),
    ("applnch_stats", "Stats du lanceur d'applications.", {}, handle_applnch_stats),
    # Email Sender (3) — Phase 22
    ("emailsend_list", "Lister les emails.", {"status": "string"}, handle_emailsend_list),
    ("emailsend_templates", "Lister les templates email.", {}, handle_emailsend_templates),
    ("emailsend_stats", "Stats du systeme email.", {}, handle_emailsend_stats),
    # System Profiler (3) — Phase 22
    ("sysprof_profiles", "Lister les profils systeme.", {"tag": "string"}, handle_sysprof_profiles),
    ("sysprof_benchmarks", "Lister les benchmarks.", {}, handle_sysprof_benchmarks),
    ("sysprof_stats", "Stats du profiler systeme.", {}, handle_sysprof_stats),
    # Context Manager (3) — Phase 22
    ("ctxmgr_list", "Lister les contextes d'execution.", {"tag": "string"}, handle_ctxmgr_list),
    ("ctxmgr_events", "Evenements des contextes.", {"context_id": "string"}, handle_ctxmgr_events),
    ("ctxmgr_stats", "Stats du context manager.", {}, handle_ctxmgr_stats),
    # Window Manager (3) — Phase 23
    ("winmgr_list", "Lister les fenetres ouvertes.", {"visible_only": "boolean"}, handle_winmgr_list),
    ("winmgr_events", "Historique des actions fenetres.", {"limit": "number"}, handle_winmgr_events),
    ("winmgr_stats", "Stats du gestionnaire de fenetres.", {}, handle_winmgr_stats),
    # Power Manager (3) — Phase 23
    ("pwrmgr_battery", "Statut batterie et alimentation.", {}, handle_pwrmgr_battery),
    ("pwrmgr_events", "Historique des actions d'alimentation.", {"limit": "number"}, handle_pwrmgr_events),
    ("pwrmgr_stats", "Stats du power manager.", {}, handle_pwrmgr_stats),
    # Download Manager (3) — Phase 23
    ("dlmgr_list", "Lister les telechargements.", {"status": "string"}, handle_dlmgr_list),
    ("dlmgr_history", "Historique complet des telechargements.", {}, handle_dlmgr_history),
    ("dlmgr_stats", "Stats du gestionnaire de telechargements.", {}, handle_dlmgr_stats),
    # Registry Manager (3) — Phase 24
    ("regmgr_favorites", "Lister les favoris registre.", {}, handle_regmgr_favorites),
    ("regmgr_events", "Historique des operations registre.", {"limit": "number"}, handle_regmgr_events),
    ("regmgr_stats", "Stats du gestionnaire de registre.", {}, handle_regmgr_stats),
    # Service Controller (3) — Phase 24
    ("svcctl_list", "Lister les services Windows.", {"state": "string"}, handle_svcctl_list),
    ("svcctl_events", "Historique des actions services.", {"limit": "number"}, handle_svcctl_events),
    ("svcctl_stats", "Stats du controleur de services.", {}, handle_svcctl_stats),
    # Disk Monitor (3) — Phase 24
    ("diskmon_drives", "Lister les disques et usage.", {}, handle_diskmon_drives),
    ("diskmon_alerts", "Alertes d'espace disque.", {"limit": "number"}, handle_diskmon_alerts),
    ("diskmon_stats", "Stats du moniteur de disques.", {}, handle_diskmon_stats),
    # Audio Controller (3) — Phase 25
    ("audictl_presets", "Lister les presets audio.", {}, handle_audictl_presets),
    ("audictl_events", "Historique des actions audio.", {"limit": "number"}, handle_audictl_events),
    ("audictl_stats", "Stats du controleur audio.", {}, handle_audictl_stats),
    # Startup Manager (3) — Phase 25
    ("startup_list", "Lister les programmes au demarrage.", {"scope": "string"}, handle_startup_list),
    ("startup_events", "Historique des actions startup.", {"limit": "number"}, handle_startup_events),
    ("startup_stats", "Stats du gestionnaire de demarrage.", {}, handle_startup_stats),
    # Screen Capture (3) — Phase 25
    ("scrcap_list", "Lister les captures d'ecran.", {"limit": "number"}, handle_scrcap_list),
    ("scrcap_events", "Historique des captures.", {"limit": "number"}, handle_scrcap_events),
    ("scrcap_stats", "Stats du capture d'ecran.", {}, handle_scrcap_stats),
    # WiFi Manager (3) — Phase 26
    ("wifimgr_profiles", "Lister les profils WiFi sauvegardes.", {}, handle_wifimgr_profiles),
    ("wifimgr_events", "Historique des actions WiFi.", {"limit": "number"}, handle_wifimgr_events),
    ("wifimgr_stats", "Stats du gestionnaire WiFi.", {}, handle_wifimgr_stats),
    # Display Manager (3) — Phase 26
    ("dispmgr_list", "Lister les ecrans connectes.", {}, handle_dispmgr_list),
    ("dispmgr_events", "Historique des actions ecran.", {"limit": "number"}, handle_dispmgr_events),
    ("dispmgr_stats", "Stats du gestionnaire d'ecrans.", {}, handle_dispmgr_stats),
    # USB Monitor (3) — Phase 26
    ("usbmon_events", "Historique USB.", {"limit": "number"}, handle_usbmon_events),
    ("usbmon_changes", "Detecter les changements USB.", {}, handle_usbmon_changes),
    ("usbmon_stats", "Stats du moniteur USB.", {}, handle_usbmon_stats),
    # Printer Manager — Phase 27 (3)
    ("prnmgr_list", "Lister les imprimantes installees.", {}, handle_prnmgr_list),
    ("prnmgr_events", "Historique des evenements imprimante.", {"limit": "number"}, handle_prnmgr_events),
    ("prnmgr_stats", "Stats du gestionnaire d'imprimantes.", {}, handle_prnmgr_stats),
    # Firewall Controller — Phase 27 (3)
    ("fwctl_rules", "Lister les regles de pare-feu Windows.", {"direction": "string"}, handle_fwctl_rules),
    ("fwctl_events", "Historique des evenements pare-feu.", {"limit": "number"}, handle_fwctl_events),
    ("fwctl_stats", "Stats du controleur de pare-feu.", {}, handle_fwctl_stats),
    # Scheduler Manager — Phase 27 (3)
    ("schedmgr_list", "Lister les taches planifiees Windows.", {"folder": "string"}, handle_schedmgr_list),
    ("schedmgr_events", "Historique des evenements planificateur.", {"limit": "number"}, handle_schedmgr_events),
    ("schedmgr_stats", "Stats du gestionnaire de taches planifiees.", {}, handle_schedmgr_stats),
    # Bluetooth Manager — Phase 28 (3)
    ("btmgr_list", "Lister les appareils Bluetooth.", {}, handle_btmgr_list),
    ("btmgr_events", "Historique des evenements Bluetooth.", {"limit": "number"}, handle_btmgr_events),
    ("btmgr_stats", "Stats du gestionnaire Bluetooth.", {}, handle_btmgr_stats),
    # Event Log Reader — Phase 28 (3)
    ("evtlog_read", "Lire le journal d'evenements Windows.", {"log_name": "string", "max_events": "number", "level": "string"}, handle_evtlog_read),
    ("evtlog_events", "Historique des lectures de journaux.", {"limit": "number"}, handle_evtlog_events),
    ("evtlog_stats", "Stats du lecteur de journaux.", {}, handle_evtlog_stats),
    # Font Manager — Phase 28 (3)
    ("fontmgr_list", "Lister les polices installees.", {}, handle_fontmgr_list),
    ("fontmgr_events", "Historique des evenements polices.", {"limit": "number"}, handle_fontmgr_events),
    ("fontmgr_stats", "Stats du gestionnaire de polices.", {}, handle_fontmgr_stats),
    # Network Monitor — Phase 29 (3)
    ("netmon_adapters", "Lister les adaptateurs reseau.", {}, handle_netmon_adapters),
    ("netmon_events", "Historique des evenements reseau.", {"limit": "number"}, handle_netmon_events),
    ("netmon_stats", "Stats du moniteur reseau.", {}, handle_netmon_stats),
    # Hosts Manager — Phase 29 (3)
    ("hostsmgr_list", "Lister les entrees du fichier hosts.", {}, handle_hostsmgr_list),
    ("hostsmgr_events", "Historique des evenements hosts.", {"limit": "number"}, handle_hostsmgr_events),
    ("hostsmgr_stats", "Stats du gestionnaire hosts.", {}, handle_hostsmgr_stats),
    # Theme Controller — Phase 29 (3)
    ("themectl_get", "Obtenir le theme Windows actuel.", {}, handle_themectl_get),
    ("themectl_events", "Historique des evenements theme.", {"limit": "number"}, handle_themectl_events),
    ("themectl_stats", "Stats du controleur de theme.", {}, handle_themectl_stats),
    # Certificate Manager — Phase 30 (3)
    ("certmgr_list", "Lister les certificats Windows.", {"store": "string"}, handle_certmgr_list),
    ("certmgr_events", "Historique des evenements certificats.", {"limit": "number"}, handle_certmgr_events),
    ("certmgr_stats", "Stats du gestionnaire de certificats.", {}, handle_certmgr_stats),
    # Virtual Desktop — Phase 30 (3)
    ("vdesk_list", "Lister les bureaux virtuels.", {}, handle_vdesk_list),
    ("vdesk_events", "Historique des evenements bureaux virtuels.", {"limit": "number"}, handle_vdesk_events),
    ("vdesk_stats", "Stats des bureaux virtuels.", {}, handle_vdesk_stats),
    # Notification Manager — Phase 30 (3)
    ("notifmgr_history", "Historique des notifications envoyees.", {"limit": "number"}, handle_notifmgr_history),
    ("notifmgr_events", "Historique des evenements notifications.", {"limit": "number"}, handle_notifmgr_events),
    ("notifmgr_stats", "Stats du gestionnaire de notifications.", {}, handle_notifmgr_stats),
    # System Restore — Phase 31 (3)
    ("sysrest_list", "Lister les points de restauration systeme.", {}, handle_sysrest_list),
    ("sysrest_events", "Historique des evenements restauration.", {"limit": "number"}, handle_sysrest_events),
    ("sysrest_stats", "Stats du gestionnaire de restauration.", {}, handle_sysrest_stats),
    # Performance Counter — Phase 31 (3)
    ("perfctr_counters", "Lister les compteurs de performance disponibles.", {}, handle_perfctr_counters),
    ("perfctr_events", "Historique des evenements performance.", {"limit": "number"}, handle_perfctr_events),
    ("perfctr_stats", "Stats du compteur de performance.", {}, handle_perfctr_stats),
    # Credential Vault — Phase 31 (3)
    ("credvlt_list", "Lister les credentials stockes (cibles uniquement).", {}, handle_credvlt_list),
    ("credvlt_events", "Historique des evenements vault.", {"limit": "number"}, handle_credvlt_events),
    ("credvlt_stats", "Stats du coffre de credentials.", {}, handle_credvlt_stats),
    # Locale Manager — Phase 32 (3)
    ("localemgr_info", "Infos locale systeme, langues, timezone, claviers, format date.", {}, handle_localemgr_info),
    ("localemgr_events", "Historique des evenements locale.", {"limit": "number"}, handle_localemgr_events),
    ("localemgr_stats", "Stats du gestionnaire de locale.", {}, handle_localemgr_stats),
    # GPU Monitor — Phase 32 (3)
    ("gpumon_snapshot", "Snapshot GPU (NVIDIA smi + WMI fallback).", {}, handle_gpumon_snapshot),
    ("gpumon_events", "Historique des evenements GPU.", {"limit": "number"}, handle_gpumon_events),
    ("gpumon_stats", "Stats du moniteur GPU.", {}, handle_gpumon_stats),
    # Share Manager — Phase 32 (3)
    ("sharemgr_list", "Lister les partages reseau et lecteurs mappes.", {}, handle_sharemgr_list),
    ("sharemgr_events", "Historique des evenements partages.", {"limit": "number"}, handle_sharemgr_events),
    ("sharemgr_stats", "Stats du gestionnaire de partages.", {}, handle_sharemgr_stats),
    # Driver Manager — Phase 33 (3)
    ("drvmgr_list", "Lister les pilotes installes.", {}, handle_drvmgr_list),
    ("drvmgr_events", "Historique des evenements pilotes.", {"limit": "number"}, handle_drvmgr_events),
    ("drvmgr_stats", "Stats du gestionnaire de pilotes.", {}, handle_drvmgr_stats),
    # WMI Explorer — Phase 33 (3)
    ("wmiexp_query", "Requete WMI generique.", {"class_name": "string", "properties": "string", "max_results": "number"}, handle_wmiexp_query),
    ("wmiexp_events", "Historique des evenements WMI.", {"limit": "number"}, handle_wmiexp_events),
    ("wmiexp_stats", "Stats de l'explorateur WMI.", {}, handle_wmiexp_stats),
    # Env Variable Manager — Phase 33 (3)
    ("envmgr_list", "Lister les variables d'environnement (system + user).", {}, handle_envmgr_list),
    ("envmgr_events", "Historique des evenements env.", {"limit": "number"}, handle_envmgr_events),
    ("envmgr_stats", "Stats du gestionnaire de variables.", {}, handle_envmgr_stats),
    # Pagefile Manager — Phase 34 (3)
    ("pgfile_usage", "Usage du pagefile (memoire virtuelle).", {}, handle_pgfile_usage),
    ("pgfile_events", "Historique des evenements pagefile.", {"limit": "number"}, handle_pgfile_events),
    ("pgfile_stats", "Stats du gestionnaire pagefile.", {}, handle_pgfile_stats),
    # Time Sync Manager — Phase 34 (3)
    ("timesync_status", "Statut synchronisation temps NTP/W32Time.", {}, handle_timesync_status),
    ("timesync_events", "Historique des evenements time sync.", {"limit": "number"}, handle_timesync_events),
    ("timesync_stats", "Stats du gestionnaire de synchronisation.", {}, handle_timesync_stats),
    # Disk Health — Phase 34 (3)
    ("diskhlth_list", "Lister les disques physiques avec etat de sante.", {}, handle_diskhlth_list),
    ("diskhlth_events", "Historique des evenements disk health.", {"limit": "number"}, handle_diskhlth_events),
    ("diskhlth_stats", "Stats du moniteur de sante disque.", {}, handle_diskhlth_stats),
    # User Account Manager — Phase 35 (3)
    ("usracct_list", "Lister les comptes utilisateurs locaux.", {}, handle_usracct_list),
    ("usracct_events", "Historique des evenements comptes.", {"limit": "number"}, handle_usracct_events),
    ("usracct_stats", "Stats du gestionnaire de comptes.", {}, handle_usracct_stats),
    # Group Policy Reader — Phase 35 (3)
    ("gpo_rsop", "Resultant Set of Policy (GPO appliquees).", {}, handle_gpo_rsop),
    ("gpo_events", "Historique des evenements GPO.", {"limit": "number"}, handle_gpo_events),
    ("gpo_stats", "Stats du lecteur GPO.", {}, handle_gpo_stats),
    # Windows Feature Manager — Phase 35 (3)
    ("winfeat_list", "Lister les fonctionnalites optionnelles Windows.", {}, handle_winfeat_list),
    ("winfeat_events", "Historique des evenements features.", {"limit": "number"}, handle_winfeat_events),
    ("winfeat_stats", "Stats du gestionnaire de fonctionnalites.", {}, handle_winfeat_stats),
    # Memory Diagnostics — Phase 36 (3)
    ("memdiag_modules", "Lister les modules RAM (slots, vitesse, fabricant).", {}, handle_memdiag_modules),
    ("memdiag_events", "Historique des evenements memoire.", {"limit": "number"}, handle_memdiag_events),
    ("memdiag_stats", "Stats du diagnostic memoire.", {}, handle_memdiag_stats),
    # System Info Collector — Phase 36 (3)
    ("sysinfo_profile", "Profil systeme complet (OS, CPU, BIOS, computer).", {}, handle_sysinfo_profile),
    ("sysinfo_events", "Historique des evenements sysinfo.", {"limit": "number"}, handle_sysinfo_events),
    ("sysinfo_stats", "Stats du collecteur sysinfo.", {}, handle_sysinfo_stats),
    # Crash Dump Reader — Phase 36 (3)
    ("crashdmp_list", "Resume des crash dumps et minidumps.", {}, handle_crashdmp_list),
    ("crashdmp_events", "Historique des evenements crash reader.", {"limit": "number"}, handle_crashdmp_events),
    ("crashdmp_stats", "Stats du lecteur de crash dumps.", {}, handle_crashdmp_stats),
    # Hotfix Manager — Phase 37 (3)
    ("hotfix_list", "Lister les hotfixes/KB installes.", {}, handle_hotfix_list),
    ("hotfix_events", "Historique des evenements hotfix.", {"limit": "number"}, handle_hotfix_events),
    ("hotfix_stats", "Stats du gestionnaire de hotfixes.", {}, handle_hotfix_stats),
    # Volume Manager — Phase 37 (3)
    ("volmgr_list", "Lister les volumes et partitions.", {}, handle_volmgr_list),
    ("volmgr_events", "Historique des evenements volumes.", {"limit": "number"}, handle_volmgr_events),
    ("volmgr_stats", "Stats du gestionnaire de volumes.", {}, handle_volmgr_stats),
    # Defender Status — Phase 37 (3)
    ("defender_status", "Statut Windows Defender (AV, signatures, scans).", {}, handle_defender_status),
    ("defender_events", "Historique des evenements Defender.", {"limit": "number"}, handle_defender_events),
    ("defender_stats", "Stats du moniteur Defender.", {}, handle_defender_stats),
    # IP Config Manager — Phase 38 (3)
    ("ipcfg_all", "Configuration IP complete (interfaces, DNS, DHCP).", {}, handle_ipcfg_all),
    ("ipcfg_events", "Historique des evenements ipconfig.", {"limit": "number"}, handle_ipcfg_events),
    ("ipcfg_stats", "Stats du gestionnaire IP.", {}, handle_ipcfg_stats),
    # Recycle Bin Manager — Phase 38 (3)
    ("recyclebin_info", "Info corbeille (nb items, taille).", {}, handle_recyclebin_info),
    ("recyclebin_events", "Historique des evenements corbeille.", {"limit": "number"}, handle_recyclebin_events),
    ("recyclebin_stats", "Stats du gestionnaire de corbeille.", {}, handle_recyclebin_stats),
    # Installed Apps Manager — Phase 38 (3)
    ("instapp_list", "Lister les applications Win32 installees.", {}, handle_instapp_list),
    ("instapp_events", "Historique des evenements apps.", {"limit": "number"}, handle_instapp_events),
    ("instapp_stats", "Stats du gestionnaire d'applications.", {}, handle_instapp_stats),
    # Scheduled Tasks (3)
    ("schtask_list", "Lister les tâches planifiées Windows.", {}, handle_schtask_list),
    ("schtask_events", "Événements du gestionnaire de tâches planifiées.", {"limit": "number"}, handle_schtask_events),
    ("schtask_stats", "Stats du gestionnaire de tâches planifiées.", {}, handle_schtask_stats),
    # Audio Devices (3)
    ("audiodev_list", "Lister les périphériques audio Windows.", {}, handle_audiodev_list),
    ("audiodev_events", "Événements du gestionnaire audio.", {"limit": "number"}, handle_audiodev_events),
    ("audiodev_stats", "Stats du gestionnaire audio.", {}, handle_audiodev_stats),
    # USB Devices (3)
    ("usbdev_list", "Lister les périphériques USB connectés.", {}, handle_usbdev_list),
    ("usbdev_events", "Événements du gestionnaire USB.", {"limit": "number"}, handle_usbdev_events),
    ("usbdev_stats", "Stats du gestionnaire USB.", {}, handle_usbdev_stats),
    # Screen Resolution (3)
    ("screenres_list", "Lister les écrans et résolutions.", {}, handle_screenres_list),
    ("screenres_events", "Événements du gestionnaire d'écrans.", {"limit": "number"}, handle_screenres_events),
    ("screenres_stats", "Stats du gestionnaire d'écrans.", {}, handle_screenres_stats),
    # BIOS Info (3)
    ("biosinfo_get", "Informations BIOS/UEFI du système.", {}, handle_biosinfo_get),
    ("biosinfo_events", "Événements du lecteur BIOS.", {"limit": "number"}, handle_biosinfo_events),
    ("biosinfo_stats", "Stats du lecteur BIOS.", {}, handle_biosinfo_stats),
    # Performance Counters (3)
    ("perfmon_snapshot", "Snapshot des compteurs de performance Windows.", {}, handle_perfmon_snapshot),
    ("perfmon_events", "Événements du gestionnaire de performance.", {"limit": "number"}, handle_perfmon_events),
    ("perfmon_stats", "Stats du gestionnaire de performance.", {}, handle_perfmon_stats),
    # Virtual Memory (3)
    ("virtmem_status", "Statut mémoire virtuelle Windows.", {}, handle_virtmem_status),
    ("virtmem_events", "Événements du gestionnaire mémoire virtuelle.", {"limit": "number"}, handle_virtmem_events),
    ("virtmem_stats", "Stats du gestionnaire mémoire virtuelle.", {}, handle_virtmem_stats),
    # Windows Event Log (3)
    ("winevt_recent", "Événements récents du journal Windows.", {"log_name": "string", "max_events": "number"}, handle_winevt_recent),
    ("winevt_events", "Historique des lectures du journal.", {"limit": "number"}, handle_winevt_events),
    ("winevt_stats", "Stats du lecteur de journal Windows.", {}, handle_winevt_stats),
    # Shadow Copy (3)
    ("shadowcopy_list", "Lister les copies fantômes (VSS).", {}, handle_shadowcopy_list),
    ("shadowcopy_events", "Événements du gestionnaire de copies fantômes.", {"limit": "number"}, handle_shadowcopy_events),
    ("shadowcopy_stats", "Stats du gestionnaire de copies fantômes.", {}, handle_shadowcopy_stats),
    # DNS Client (3)
    ("dnscli_servers", "Adresses DNS par interface.", {}, handle_dnscli_servers),
    ("dnscli_events", "Événements du gestionnaire DNS client.", {"limit": "number"}, handle_dnscli_events),
    ("dnscli_stats", "Stats du gestionnaire DNS client.", {}, handle_dnscli_stats),
    # Storage Pool (3)
    ("storpool_list", "Lister les pools de stockage Windows.", {}, handle_storpool_list),
    ("storpool_events", "Événements du gestionnaire de pools.", {"limit": "number"}, handle_storpool_events),
    ("storpool_stats", "Stats du gestionnaire de pools.", {}, handle_storpool_stats),
    # Power Plan (3)
    ("pwrplan_list", "Lister les plans d'alimentation.", {}, handle_pwrplan_list),
    ("pwrplan_events", "Événements du gestionnaire d'alimentation.", {"limit": "number"}, handle_pwrplan_events),
    ("pwrplan_stats", "Stats du gestionnaire d'alimentation.", {}, handle_pwrplan_stats),
    # Network Adapter (3)
    ("netadapt_list", "Lister les adaptateurs réseau Windows.", {}, handle_netadapt_list),
    ("netadapt_events", "Événements du gestionnaire d'adaptateurs.", {"limit": "number"}, handle_netadapt_events),
    ("netadapt_stats", "Stats du gestionnaire d'adaptateurs.", {}, handle_netadapt_stats),
    # Windows Update (3)
    ("winupd_history", "Historique des mises à jour Windows.", {"limit": "number"}, handle_winupd_history),
    ("winupd_events", "Événements du gestionnaire de mises à jour.", {"limit": "number"}, handle_winupd_events),
    ("winupd_stats", "Stats du gestionnaire de mises à jour.", {}, handle_winupd_stats),
    # Local Security Policy (3)
    ("secpol_export", "Exporter la politique de sécurité locale.", {}, handle_secpol_export),
    ("secpol_events", "Événements du lecteur de politique.", {"limit": "number"}, handle_secpol_events),
    ("secpol_stats", "Stats du lecteur de politique.", {}, handle_secpol_stats),
    # Telegram Bot (3)
    ("telegram_send", "Envoyer un message Telegram.", {"message": "string", "chat_id": "string"}, handle_telegram_send),
    ("telegram_status", "Statut du bot Telegram et du proxy.", {}, handle_telegram_status),
    ("telegram_history", "Derniers messages reçus par le bot Telegram.", {"limit": "number"}, handle_telegram_history),
    # Browser Navigator (10) — v2.0
    ("browser_open", "Ouvrir le navigateur Playwright.", {"url": "string"}, handle_browser_open),
    ("browser_navigate", "Naviguer vers une URL.", {"url": "string"}, handle_browser_navigate),
    ("browser_click", "Cliquer sur un element par texte.", {"text": "string"}, handle_browser_click),
    ("browser_scroll", "Scroller la page.", {"direction": "string", "amount": "number"}, handle_browser_scroll),
    ("browser_read", "Lire le contenu texte de la page.", {"max_chars": "number"}, handle_browser_read),
    ("browser_screenshot", "Capture d'ecran de la page.", {}, handle_browser_screenshot),
    ("browser_back", "Page precedente.", {}, handle_browser_back),
    ("browser_forward", "Page suivante.", {}, handle_browser_forward),
    ("browser_close_tab", "Fermer l'onglet actif.", {}, handle_browser_close),
    ("browser_move_screen", "Deplacer le navigateur sur l'autre ecran.", {}, handle_browser_move),
    # Prediction Engine (3) — v2.0
    ("prediction_predict", "Predire les prochaines actions utilisateur.", {"n": "number"}, handle_prediction_predict),
    ("prediction_profile", "Profil d'activite de l'utilisateur.", {}, handle_prediction_profile),
    ("prediction_stats", "Stats du moteur predictif.", {}, handle_prediction_stats),
    # Auto-Developer (2) — v2.0
    ("autodev_run_cycle", "Lancer un cycle d'auto-developpement.", {"max_gaps": "number"}, handle_autodev_run_cycle),
    ("autodev_stats", "Stats de l'auto-developpeur.", {}, handle_autodev_stats),
    # Pattern Agents (5) — v11.1
    ("agent_dispatch", "Dispatch intelligent vers le meilleur agent pattern. Auto-classifie si pattern absent.", {"prompt": "string", "pattern": "string"}, handle_agent_dispatch),
    ("agent_classify", "Classifie un prompt en pattern type (code/analysis/trading/...).", {"prompt": "string"}, handle_agent_classify),
    ("agent_list", "Liste les 14 agents pattern avec leur config.", {}, handle_agent_list),
    ("agent_routing", "Rapport de routing intelligent base sur l'historique dispatch.", {}, handle_agent_routing),
    ("agent_evolve", "Evolution automatique des agents: decouverte, tuning, optimisation.", {}, handle_agent_evolve),
    # Pipeline + Monitor (4) — v11.1
    ("pipeline_run", "Executer un pipeline multi-agents (code-review, smart-qa, trading-analysis, architecture-design, devops-deploy).", {"pipeline": "string", "prompt": "string"}, handle_pipeline_run),
    ("pipeline_list", "Lister les pipelines pre-construits disponibles.", {}, handle_pipeline_list),
    ("agent_dashboard", "Dashboard temps reel des 14 agents: metriques, alertes, noeuds.", {}, handle_agent_dashboard),
    ("routing_optimizer", "Rapport optimisation routing avec recommandations.", {}, handle_routing_optimizer),
    ("adaptive_router_status", "Routeur adaptatif: circuits, health, affinites, recommandations.", {}, handle_adaptive_router_status),
    ("adaptive_router_pick", "Choisir le noeud optimal pour un pattern.", {"pattern": "string", "count": "number"}, handle_adaptive_router_pick),
    ("pattern_discovery", "Decouvrir nouveaux patterns depuis les logs + analyse comportement.", {}, handle_pattern_discovery),
    ("pattern_discovery_register", "Decouvrir et enregistrer nouveaux patterns en DB.", {}, handle_pattern_discovery_register),
    ("orchestrate", "Executer un workflow orchestre (auto/deep-analysis/code-generate/consensus-3/trading-full/security-audit).", {"prompt": "string", "workflow": "string", "budget_s": "number"}, handle_orchestrate),
    ("orchestrate_consensus", "Consensus multi-noeuds avec vote pondere.", {"prompt": "string", "min_agree": "number"}, handle_orchestrate_consensus),
    ("orchestrate_race", "Course multi-noeuds: le plus rapide gagne.", {"prompt": "string", "pattern": "string", "count": "number"}, handle_orchestrate_race),
    ("episodic_memory_recall", "Rappeler episodes pertinents depuis la memoire.", {"query": "string", "top_k": "number"}, handle_episodic_recall),
    ("episodic_memory_learn", "Analyser historique et generer faits semantiques.", {}, handle_episodic_learn),
    ("episodic_memory_node", "Memoire d'un noeud specifique.", {"node": "string"}, handle_episodic_node),
    ("episodic_memory_pattern", "Memoire d'un pattern specifique.", {"pattern": "string"}, handle_episodic_pattern),
    ("self_improve_cycle", "Lancer un cycle d'auto-amelioration.", {}, handle_self_improve),
    ("self_improve_history", "Historique des cycles d'amelioration.", {}, handle_self_improve_history),
    ("agent_collab_chain", "Chaine collaborative: agents executent en sequence.", {"agents": "string", "prompt": "string"}, handle_collab_chain),
    ("agent_collab_debate", "Debat multi-agents.", {"agents": "string", "question": "string"}, handle_collab_debate),
    ("health_check", "Health check complet tous noeuds.", {}, handle_health_check),
    ("health_heal", "Auto-healing des problemes detectes.", {}, handle_health_heal),
    ("benchmark_quick", "Benchmark rapide 10 patterns.", {}, handle_benchmark_quick),
    ("task_planner", "Planifier et decomposer une tache complexe.", {"prompt": "string"}, handle_task_planner),
    ("task_planner_execute", "Planifier et executer une tache complexe.", {"prompt": "string"}, handle_task_planner_execute),
    ("feedback_quality", "Rapport qualite de la boucle de retro.", {}, handle_feedback_quality),
    ("feedback_trends", "Tendances qualite par pattern.", {}, handle_feedback_trends),
    ("feedback_adjustments", "Ajustements routage suggerees.", {}, handle_feedback_adjustments),
    # Phase 13: Dispatch Engine (3)
    ("dispatch_engine", "Pipeline unifie: health→route→dispatch→feedback→memory.", {"pattern": "string", "prompt": "string"}, handle_dispatch_engine_dispatch),
    ("dispatch_engine_stats", "Stats pipeline dispatch.", {}, handle_dispatch_engine_stats),
    ("dispatch_engine_report", "Rapport detaille pipeline.", {}, handle_dispatch_engine_report),
    ("dispatch_analytics", "Analytics completes: pipeline + benchmark trend + recommandations.", {}, handle_dispatch_analytics),
    ("dispatch_auto_optimize", "Auto-optimise les strategies de dispatch basee sur donnees historiques.", {}, handle_dispatch_auto_optimize),
    ("dispatch_quick_bench", "Quick benchmark 5 patterns critiques.", {}, handle_dispatch_quick_bench),
    # Phase 13: Prompt Optimizer (4)
    ("prompt_optimize", "Optimiser un prompt pour un pattern.", {"pattern": "string", "prompt": "string"}, handle_prompt_optimize),
    ("prompt_insights", "Insights prompts par pattern.", {"pattern": "string"}, handle_prompt_insights),
    ("prompt_analyze", "Analyser qualite d'un prompt.", {"pattern": "string", "prompt": "string"}, handle_prompt_analyze),
    ("prompt_templates", "Templates prompts optimises.", {}, handle_prompt_templates),
    # Phase 13: Auto Scaler (3)
    ("auto_scaler_metrics", "Metriques charge par noeud.", {}, handle_auto_scaler_metrics),
    ("auto_scaler_evaluate", "Evaluer actions scaling.", {}, handle_auto_scaler_evaluate),
    ("auto_scaler_capacity", "Rapport capacite cluster.", {}, handle_auto_scaler_capacity),
    # Phase 13: Event Stream (3)
    ("event_stream_events", "Evenements recents.", {"topic": "string"}, handle_event_stream_events),
    ("event_stream_emit", "Emettre un evenement.", {"topic": "string"}, handle_event_stream_emit),
    ("event_stream_stats", "Stats flux evenements.", {}, handle_event_stream_stats),
    # Phase 13: Agent Ensemble (2)
    ("ensemble_execute", "Ensemble multi-agents scoring+selection.", {"pattern": "string", "prompt": "string"}, handle_ensemble_execute),
    ("ensemble_stats", "Stats ensemble executions.", {}, handle_ensemble_stats),
    # Phase 14: Quality Gate (2)
    ("quality_gate_evaluate", "Evaluer qualite d'un output.", {"pattern": "string", "prompt": "string", "content": "string"}, handle_quality_gate_evaluate),
    ("quality_gate_report", "Rapport quality gate.", {}, handle_quality_gate_report),
    # Phase 14: Pattern Lifecycle (3)
    ("lifecycle_health", "Rapport sante patterns.", {}, handle_lifecycle_health),
    ("lifecycle_actions", "Actions lifecycle suggerees.", {}, handle_lifecycle_actions),
    ("lifecycle_evolve", "Evoluer un pattern.", {"pattern": "string", "model": "string"}, handle_lifecycle_evolve),
    # Phase 14: Cluster Intelligence (3)
    ("intelligence_report", "Rapport intelligence cluster complet.", {}, handle_intelligence_report),
    ("intelligence_status", "Statut rapide cluster.", {}, handle_intelligence_status),
    ("intelligence_actions", "Actions prioritaires cluster.", {}, handle_intelligence_actions),
    # Cowork Bridge v2 (4)
    ("cowork_v2_list", "Lister scripts cowork (414+ scripts).", {"category": "string"}, handle_cowork_v2_list),
    ("cowork_v2_search", "Chercher un script cowork.", {"query": "string"}, handle_cowork_v2_search),
    ("cowork_v2_execute", "Executer un script cowork.", {"script": "string"}, handle_cowork_v2_execute),
    ("cowork_v2_stats", "Stats cowork bridge.", {}, handle_cowork_v2_stats),
    # Phase 15: Self-Improvement (4)
    ("self_improvement_analyze", "Analyse performance systeme et gate failures.", {}, handle_self_improvement_analyze),
    ("self_improvement_suggest", "Suggestions d'amelioration automatiques.", {}, handle_self_improvement_suggest),
    ("self_improvement_apply", "Appliquer ameliorations (auto ou manuelles).", {"auto": "boolean", "max_actions": "number"}, handle_self_improvement_apply),
    ("self_improvement_stats", "Stats du self-improvement loop.", {}, handle_self_improvement_stats),
    # Phase 15: Dynamic Agents (4)
    ("dynamic_agents_list", "Lister tous les agents dynamiques (76+ patterns).", {}, handle_dynamic_agents_list),
    ("dynamic_agents_stats", "Stats agents dynamiques.", {}, handle_dynamic_agents_stats),
    ("dynamic_agents_dispatch", "Dispatcher vers un agent dynamique.", {"pattern": "string", "prompt": "string"}, handle_dynamic_agents_dispatch),
    ("dynamic_agents_register", "Enregistrer agents dynamiques dans le registry live.", {}, handle_dynamic_agents_register),
    # Phase 15: Cowork Proactive (4)
    ("cowork_proactive_needs", "Detecter les besoins systeme pour execution proactive.", {}, handle_cowork_proactive_needs),
    ("cowork_proactive_run", "Cycle proactif: detecter -> planifier -> executer.", {"max_scripts": "number", "dry_run": "boolean"}, handle_cowork_proactive_run),
    ("cowork_proactive_anticipate", "Predictions de besoins futurs.", {}, handle_cowork_proactive_anticipate),
    ("cowork_proactive_stats", "Stats du moteur proactif.", {}, handle_cowork_proactive_stats),
    ("linkedin_generate", "Generer contenu LinkedIn optimise (post FR + EN + 3 commentaires strategiques).", {"idea": "string", "topic": "string", "tone": "string"}, handle_linkedin_generate),
    ("timeout_auto_fix", "Auto-corriger les timeouts dispatch (analyse latence + ajustement).", {"dry_run": "boolean"}, handle_timeout_auto_fix),
    ("dispatch_integration_test", "Tests d'integration du pipeline dispatch (6 tests).", {}, handle_dispatch_integration_test),
    # Phase 15: Reflection Engine (3)
    ("reflection_insights", "Insights meta-cognitifs: qualite, performance, fiabilite, croissance.", {}, handle_reflection_insights),
    ("reflection_summary", "Resume systeme avec metriques cles.", {}, handle_reflection_summary),
    ("reflection_timeline", "Analyse timeline des dispatches sur N heures.", {"hours": "number"}, handle_reflection_timeline),
    # Phase 16: Pattern Evolution (3)
    ("evolution_gaps", "Analyser les lacunes et suggerer de nouveaux patterns.", {}, handle_evolution_gaps),
    ("evolution_create", "Auto-creer des patterns depuis les suggestions.", {"min_confidence": "number"}, handle_evolution_create),
    ("evolution_stats", "Stats de l'evolution des patterns.", {}, handle_evolution_stats),
]

# ── COWORK MCP Bridge ─────────────────────────────────────────────────
try:
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parent.parent))
    from cowork.cowork_mcp_bridge import CoworkBridge
    _cowork = CoworkBridge()

    async def _cowork_handler(tool_name):
        async def handler(args):
            result = _cowork.handle(tool_name, args)
            return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]
        return handler

    _cowork_tools = [
        ("cowork_dispatch", "Trouve les scripts COWORK matching une requete.", {"query": "string"}, None),
        ("cowork_execute", "Execute un script COWORK par nom.", {"script": "string", "args": "array", "timeout": "integer"}, None),
        ("cowork_list", "Liste les scripts COWORK, filtre optionnel par pattern.", {"pattern": "string"}, None),
        ("cowork_status", "Statut du systeme COWORK (patterns, scripts, dispatches).", {}, None),
        ("cowork_test", "Teste un script COWORK (syntax + --help).", {"script": "string"}, None),
        ("cowork_gaps", "Analyse des lacunes de couverture COWORK.", {}, None),
        ("cowork_anticipate", "Predictions des besoins depuis les patterns de dispatch.", {}, None),
    ]

    for _name, _desc, _schema, _ in _cowork_tools:
        async def _make_handler(tn=_name):
            async def h(args):
                r = _cowork.handle(tn, args)
                return [TextContent(type="text", text=json.dumps(r, indent=2, ensure_ascii=False))]
            return h

        import asyncio as _aio
        _h = _aio.get_event_loop().run_until_complete(_make_handler(_name)) if False else None

        def _sync_handler_factory(tn=_name):
            async def h(args):
                r = _cowork.handle(tn, args)
                return [TextContent(type="text", text=json.dumps(r, indent=2, ensure_ascii=False))]
            return h

        TOOL_DEFINITIONS.append((_name, _desc, _schema, _sync_handler_factory(_name)))

    logger.info("COWORK MCP bridge loaded: 7 tools")
except Exception as _e:
    logger.warning("COWORK MCP bridge not loaded: %s", _e)

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

    # Security: rate limiting
    if not mcp_limiter.allow(name):
        audit_log.log("rate_limit", f"Tool {name} rate limited", severity="warning", tool_name=name)
        return _error(f"{name}: rate limit exceeded, retry in {mcp_limiter.get_retry_after(name):.1f}s")

    # Security: input sanitization
    safe_args = sanitize_mcp_args(name, arguments)

    try:
        result = await handler(safe_args)
        audit_log.log("tool_call", f"{name} OK", tool_name=name)
        return result
    except (KeyError, ValueError, TypeError, OSError, RuntimeError) as e:
        logger.warning("MCP handler %s failed: %s", name, e)
        audit_log.log("tool_error", f"{name}: {e}", severity="warning", tool_name=name)
        return _error(f"{name}: {e}")
    except Exception as e:
        logger.error("MCP handler %s unexpected error: %s", name, e, exc_info=True)
        audit_log.log("tool_error", f"{name}: unexpected {e}", severity="error", tool_name=name)
        return _error(f"{name}: internal error")


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
