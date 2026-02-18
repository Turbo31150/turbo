"""JARVIS MCP Tools — Complete toolkit: LM Studio, Windows, files, browser, trading.

Optimizations:
- Shared httpx client pool (persistent connections, HTTP/2 ready)
- Retry with exponential backoff on transient errors
- Auto-warmup on first inference call
- LM Studio model management tools (load/unload/switch)
- GPU monitoring tool
- Performance metrics tracking
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import time
from typing import Any

import httpx
from claude_agent_sdk import tool, create_sdk_mcp_server

from src.config import config, SCRIPTS, PATHS


# ═══════════════════════════════════════════════════════════════════════════
# CONNECTION POOL — Shared async client for all LM Studio/Ollama calls
# ═══════════════════════════════════════════════════════════════════════════

_HTTP_POOL: httpx.AsyncClient | None = None
_POOL_LOCK = asyncio.Lock()


async def _get_client() -> httpx.AsyncClient:
    """Get or create the shared httpx client with connection pooling."""
    global _HTTP_POOL
    if _HTTP_POOL is None or _HTTP_POOL.is_closed:
        async with _POOL_LOCK:
            if _HTTP_POOL is None or _HTTP_POOL.is_closed:
                _HTTP_POOL = httpx.AsyncClient(
                    timeout=httpx.Timeout(
                        connect=config.connect_timeout,
                        read=config.inference_timeout,
                        write=10.0,
                        pool=5.0,
                    ),
                    limits=httpx.Limits(
                        max_connections=20,
                        max_keepalive_connections=10,
                        keepalive_expiry=300,
                    ),
                )
    return _HTTP_POOL


async def _retry_request(
    method: str, url: str, json: dict | None = None,
    max_retries: int = 2, timeout: float | None = None,
) -> httpx.Response:
    """Execute HTTP request with retry and exponential backoff."""
    client = await _get_client()
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            kwargs: dict[str, Any] = {"url": url}
            if json:
                kwargs["json"] = json
            if timeout:
                kwargs["timeout"] = timeout
            if method == "GET":
                r = await client.get(**kwargs)
            else:
                r = await client.post(**kwargs)
            r.raise_for_status()
            return r
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            last_error = e
            if attempt < max_retries:
                await asyncio.sleep(0.5 * (2 ** attempt))
        except httpx.HTTPStatusError:
            raise
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                await asyncio.sleep(0.5 * (2 ** attempt))
    raise last_error or ConnectionError("Request failed")


# ═══════════════════════════════════════════════════════════════════════════
# PERFORMANCE METRICS
# ═══════════════════════════════════════════════════════════════════════════

_METRICS: dict[str, list[float]] = {}


def _track_latency(node: str, latency_ms: float) -> None:
    """Track latency for auto-tune routing."""
    if node not in _METRICS:
        _METRICS[node] = []
    _METRICS[node].append(latency_ms)
    # Keep last 20 measurements
    if len(_METRICS[node]) > 20:
        _METRICS[node] = _METRICS[node][-20:]
    # Update config auto-tune cache
    config.update_latency(node, int(latency_ms))


# ═══════════════════════════════════════════════════════════════════════════
# LM STUDIO TOOLS
# ═══════════════════════════════════════════════════════════════════════════

@tool("lm_query", "Interroger un noeud LM Studio. Args: prompt, node (M1/M2), model (optionnel), mode (fast/deep/default).", {"prompt": str, "node": str, "model": str, "mode": str})
async def lm_query(args: dict[str, Any]) -> dict[str, Any]:
    prompt = args["prompt"]
    node = config.get_node(args.get("node", "M1"))
    if not node:
        return _error(f"Noeud inconnu: {args.get('node')}")
    model = args.get("model", node.default_model)
    mode = args.get("mode", "default")

    # Adapt parameters to mode
    max_tokens = {
        "fast": config.fast_max_tokens,
        "deep": config.deep_max_tokens,
    }.get(mode, config.max_tokens)
    timeout = config.get_timeout(mode)
    temp = 0.2 if mode == "fast" else config.temperature

    try:
        t0 = time.monotonic()
        r = await _retry_request("POST", f"{node.url}/api/v1/chat", json={
            "model": model,
            "input": prompt,
            "temperature": temp,
            "max_output_tokens": max_tokens,
            "stream": False,
            "store": False,
        }, timeout=timeout)
        latency = (time.monotonic() - t0) * 1000
        _track_latency(node.name, latency)
        data = r.json()
        content = data["output"][0]["content"]
        usage = data.get("stats", {})
        return _text(
            f"[{node.name}/{model}] {content}\n"
            f"--- {int(latency)}ms | {usage.get('total_output_tokens', '?')} tokens"
        )
    except httpx.ConnectError:
        return _error(f"Noeud {node.name} hors ligne ({node.url})")
    except httpx.ReadTimeout:
        return _error(f"Timeout {node.name} ({timeout}s) — essaie mode=fast pour limiter les tokens")
    except Exception as e:
        return _error(f"Erreur LM Studio: {e}")


@tool("lm_models", "Lister les modeles charges sur un noeud LM Studio.", {"node": str})
async def lm_models(args: dict[str, Any]) -> dict[str, Any]:
    url = config.get_node_url(args.get("node", "M1"))
    if not url:
        return _error("Noeud inconnu")
    try:
        r = await _retry_request("GET", f"{url}/api/v1/models", timeout=config.health_timeout)
        models = [m["key"] for m in r.json().get("models", []) if m.get("loaded_instances")]
        return _text(f"Modeles: {', '.join(models) if models else 'aucun'}")
    except Exception as e:
        return _error(str(e))


@tool("lm_cluster_status", "Sante de tous les noeuds du cluster (LM Studio + Ollama) avec metriques.", {})
async def lm_cluster_status(args: dict[str, Any]) -> dict[str, Any]:
    results, online = [], 0
    total_nodes = len(config.lm_nodes) + len(config.ollama_nodes)
    total_models = 0
    client = await _get_client()

    for n in config.lm_nodes:
        try:
            t0 = time.monotonic()
            r = await client.get(f"{n.url}/api/v1/models", timeout=config.health_timeout)
            r.raise_for_status()
            latency = int((time.monotonic() - t0) * 1000)
            models = [m["key"] for m in r.json().get("models", []) if m.get("loaded_instances")]
            cnt = len(models)
            total_models += cnt
            online += 1
            _track_latency(n.name, latency)
            avg = int(sum(_METRICS.get(n.name, [latency])) / max(len(_METRICS.get(n.name, [1])), 1))
            results.append(
                f"  [OK] {n.name} ({n.role}) — {n.gpus} GPU, {n.vram_gb}GB — "
                f"{cnt} modeles — {latency}ms (avg {avg}ms)\n"
                f"       Modeles: {', '.join(models)}"
            )
        except Exception:
            results.append(f"  [--] {n.name} ({n.role}) — hors ligne")

    for n in config.ollama_nodes:
        try:
            t0 = time.monotonic()
            r = await client.get(f"{n.url}/api/tags", timeout=config.health_timeout)
            r.raise_for_status()
            latency = int((time.monotonic() - t0) * 1000)
            models = [m["name"] for m in r.json().get("models", [])]
            cnt = len(models)
            total_models += cnt
            online += 1
            results.append(
                f"  [OK] {n.name} ({n.role}) — {cnt} modeles — {latency}ms [Ollama]\n"
                f"       Modeles: {', '.join(models)}"
            )
        except Exception:
            results.append(f"  [--] {n.name} ({n.role}) — hors ligne [Ollama]")

    return _text(
        f"Cluster: {online}/{total_nodes} en ligne, {total_models} modeles\n"
        + "\n".join(results)
    )


@tool("consensus", "Consensus multi-noeuds IA. Args: prompt, nodes (M1,M2,OL1).", {"prompt": str, "nodes": str})
async def consensus(args: dict[str, Any]) -> dict[str, Any]:
    prompt = args["prompt"]
    names = [n.strip() for n in args.get("nodes", "M1,OL1").split(",")]
    responses = []
    client = await _get_client()

    async def _query_node(name: str) -> str:
        ol_node = config.get_ollama_node(name)
        if ol_node:
            try:
                r = await client.post(f"{ol_node.url}/api/chat", json={
                    "model": ol_node.default_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False, "think": False,
                    "options": {"temperature": config.temperature, "num_predict": config.max_tokens},
                }, timeout=config.inference_timeout)
                r.raise_for_status()
                return f"[{name}/{ol_node.default_model}] {r.json()['message']['content']}"
            except Exception as e:
                return f"[{name}/Ollama] ERREUR: {e}"

        node = config.get_node(name)
        if not node:
            return f"[{name}] ERREUR: inconnu"
        try:
            r = await client.post(f"{node.url}/api/v1/chat", json={
                "model": node.default_model,
                "input": prompt,
                "temperature": config.temperature,
                "max_output_tokens": config.max_tokens,
                "stream": False,
                "store": False,
            }, timeout=config.inference_timeout)
            r.raise_for_status()
            return f"[{name}/{node.default_model}] {r.json()['output'][0]['content']}"
        except Exception as e:
            return f"[{name}] ERREUR: {e}"

    # Run all queries in parallel
    results = await asyncio.gather(*[_query_node(n) for n in names], return_exceptions=True)
    for r in results:
        responses.append(str(r) if isinstance(r, Exception) else r)

    return _text("Consensus:\n\n" + "\n\n---\n\n".join(responses))


# ═══════════════════════════════════════════════════════════════════════════
# LM STUDIO MODEL MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════

LMS_CLI = r"C:\Users\franc\.lmstudio\bin\lms.exe"


@tool("lm_load_model", "Charger un modele sur M1. Args: model, context, parallel.", {"model": str, "context": int, "parallel": int})
async def lm_load_model(args: dict[str, Any]) -> dict[str, Any]:
    from src.cluster_startup import load_model_on_demand
    model = args["model"]
    context = args.get("context", 16384)
    parallel = args.get("parallel", 2)
    result = await load_model_on_demand(model, context=context, parallel=parallel)
    if result["ok"]:
        bench = result.get("bench", {})
        return _text(f"Modele {model} charge — {bench.get('latency_ms', '?')}ms warmup")
    return _error(f"Echec chargement {model}: {result.get('status', '?')}")


@tool("lm_unload_model", "Decharger un modele de M1. Args: model.", {"model": str})
async def lm_unload_model(args: dict[str, Any]) -> dict[str, Any]:
    from src.cluster_startup import _lms_unload
    model = args["model"]
    ok = _lms_unload(model)
    return _text(f"Modele {model} {'decharge' if ok else 'echec decharge'}")


@tool("lm_switch_coder", "Basculer M1 en mode code (charge qwen3-coder-30b).", {})
async def lm_switch_coder(args: dict[str, Any]) -> dict[str, Any]:
    from src.cluster_startup import switch_to_coder_mode
    result = await switch_to_coder_mode()
    return _text(f"Mode coder: {result['status']}") if result["ok"] else _error(f"Echec: {result['status']}")


@tool("lm_switch_dev", "Basculer M1 en mode dev (charge devstral).", {})
async def lm_switch_dev(args: dict[str, Any]) -> dict[str, Any]:
    from src.cluster_startup import switch_to_dev_mode
    result = await switch_to_dev_mode()
    return _text(f"Mode dev: {result['status']}") if result["ok"] else _error(f"Echec: {result['status']}")


@tool("lm_gpu_stats", "Statistiques GPU detaillees (VRAM, utilisation, temperature).", {})
async def lm_gpu_stats(args: dict[str, Any]) -> dict[str, Any]:
    from src.cluster_startup import _get_gpu_stats
    gpus = _get_gpu_stats()
    if not gpus:
        return _error("nvidia-smi non disponible")
    lines = []
    total_used = sum(g["vram_used_mb"] for g in gpus)
    total_avail = sum(g["vram_total_mb"] for g in gpus)
    lines.append(f"VRAM Total: {total_used}MB / {total_avail}MB ({round(total_used/max(total_avail,1)*100)}%)\n")
    for g in gpus:
        bar = "#" * int(g["vram_pct"] / 5) + "." * (20 - int(g["vram_pct"] / 5))
        lines.append(f"GPU{g['index']} {g['name']} [{bar}] {g['vram_used_mb']}MB/{g['vram_total_mb']}MB ({g['vram_pct']}%) | util={g['gpu_util']}%")
    return _text("\n".join(lines))


@tool("lm_benchmark", "Benchmark latence M1/M2/OL1 avec inference reelle.", {"nodes": str})
async def lm_benchmark(args: dict[str, Any]) -> dict[str, Any]:
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
                _track_latency(name, bench["latency_ms"])
            else:
                results.append(f"  {name}: ECHEC — {bench.get('error', '?')}")
    return _text("Benchmark:\n" + "\n".join(results))


@tool("lm_perf_metrics", "Metriques de performance du cluster (latences moyennes, requetes).", {})
async def lm_perf_metrics(args: dict[str, Any]) -> dict[str, Any]:
    if not _METRICS:
        return _text("Aucune metrique collectee. Lance lm_benchmark d'abord.")
    lines = ["Metriques de performance:"]
    for node, latencies in _METRICS.items():
        avg = int(sum(latencies) / len(latencies))
        mn = int(min(latencies))
        mx = int(max(latencies))
        lines.append(f"  {node}: avg={avg}ms min={mn}ms max={mx}ms ({len(latencies)} requetes)")
    return _text("\n".join(lines))


# ═══════════════════════════════════════════════════════════════════════════
# OLLAMA TOOLS
# ═══════════════════════════════════════════════════════════════════════════

@tool("ollama_query", "Interroger Ollama (local ou cloud). Args: prompt, model (defaut: qwen3:1.7b).", {"prompt": str, "model": str})
async def ollama_query(args: dict[str, Any]) -> dict[str, Any]:
    node = config.get_ollama_node("OL1")
    if not node:
        return _error("Noeud Ollama OL1 non configure")
    model = args.get("model", node.default_model)
    try:
        t0 = time.monotonic()
        r = await _retry_request("POST", f"{node.url}/api/chat", json={
            "model": model,
            "messages": [{"role": "user", "content": args["prompt"]}],
            "stream": False, "think": False,
            "options": {"temperature": config.temperature, "num_predict": config.max_tokens},
        })
        latency = int((time.monotonic() - t0) * 1000)
        return _text(f"[OL1/{model}] {r.json()['message']['content']} --- {latency}ms")
    except httpx.ConnectError:
        return _error("Ollama hors ligne (127.0.0.1:11434)")
    except Exception as e:
        return _error(f"Erreur Ollama: {e}")


@tool("ollama_models", "Lister les modeles Ollama disponibles (locaux + cloud).", {})
async def ollama_models(args: dict[str, Any]) -> dict[str, Any]:
    node = config.get_ollama_node("OL1")
    if not node:
        return _error("Noeud Ollama OL1 non configure")
    try:
        r = await _retry_request("GET", f"{node.url}/api/tags", timeout=config.health_timeout)
        models = [m["name"] for m in r.json().get("models", [])]
        return _text(f"Modeles Ollama: {', '.join(models) if models else 'aucun'}")
    except Exception as e:
        return _error(f"Erreur Ollama: {e}")


@tool("ollama_pull", "Telecharger un modele Ollama. Args: model_name.", {"model_name": str})
async def ollama_pull(args: dict[str, Any]) -> dict[str, Any]:
    node = config.get_ollama_node("OL1")
    if not node:
        return _error("Noeud Ollama OL1 non configure")
    model_name = args["model_name"]
    try:
        client = await _get_client()
        r = await client.post(f"{node.url}/api/pull", json={"name": model_name, "stream": False}, timeout=600)
        r.raise_for_status()
        return _text(f"Modele '{model_name}' telecharge avec succes.")
    except Exception as e:
        return _error(f"Erreur pull Ollama: {e}")


@tool("ollama_status", "Sante du backend Ollama: version, modeles, status.", {})
async def ollama_status(args: dict[str, Any]) -> dict[str, Any]:
    node = config.get_ollama_node("OL1")
    if not node:
        return _error("Noeud Ollama OL1 non configure")
    try:
        r = await _retry_request("GET", f"{node.url}/api/tags", timeout=config.health_timeout)
        data = r.json()
        models = [m["name"] for m in data.get("models", [])]
        return _text(
            f"Ollama OL1: ONLINE\n"
            f"  URL: {node.url}\n"
            f"  Modeles: {len(models)} ({', '.join(models) if models else 'aucun'})\n"
            f"  Role: {node.role}"
        )
    except httpx.ConnectError:
        return _error("Ollama OL1: OFFLINE (127.0.0.1:11434)")
    except Exception as e:
        return _error(f"Erreur Ollama status: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# OLLAMA CLOUD — Web Search + Sub-agents
# ═══════════════════════════════════════════════════════════════════════════

CLOUD_MODELS = ["minimax-m2.5:cloud", "glm-5:cloud", "kimi-k2.5:cloud"]


async def _ollama_cloud_query(
    prompt: str, model: str, timeout: float = 60.0, system: str | None = None,
) -> str:
    """Query an Ollama cloud model with fallback to local qwen3:1.7b.

    If the cloud model returns 404/401 (not installed or not authenticated),
    falls back to the local qwen3:1.7b model automatically.
    """
    node = config.get_ollama_node("OL1")
    if not node:
        raise ConnectionError("Ollama OL1 non configure")
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    # Try cloud model first
    try:
        r = await _retry_request("POST", f"{node.url}/api/chat", json={
            "model": model, "messages": messages,
            "stream": False, "think": False,
            "options": {"temperature": 0.3, "num_predict": config.max_tokens},
        }, timeout=timeout)
        msg = r.json()["message"]
        content = msg.get("content", "")
        if not content and msg.get("thinking"):
            content = msg["thinking"]
        return content
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (404, 401) and model != "qwen3:1.7b":
            # Fallback to local model
            r = await _retry_request("POST", f"{node.url}/api/chat", json={
                "model": "qwen3:1.7b", "messages": messages,
                "stream": False, "think": False,
                "options": {"temperature": 0.3, "num_predict": config.max_tokens},
            }, timeout=timeout)
            msg = r.json()["message"]
            content = msg.get("content", "")
            if not content and msg.get("thinking"):
                content = msg["thinking"]
            return f"[FALLBACK qwen3:1.7b] {content}"
        raise


@tool(
    "ollama_web_search",
    "Recherche web via Ollama cloud (minimax-m2.5). Les modeles cloud ont la recherche web integree. Args: query, model.",
    {"query": str, "model": str},
)
async def ollama_web_search(args: dict[str, Any]) -> dict[str, Any]:
    model = args.get("model", "minimax-m2.5:cloud")
    query = args["query"]
    system = (
        "Tu es un assistant de recherche. Utilise ta capacite de recherche web "
        "pour trouver des informations actualisees. Reponds en francais avec des "
        "donnees precises, chiffres et sources quand possible."
    )
    try:
        result = await _ollama_cloud_query(query, model, timeout=60, system=system)
        return _text(f"[WEB/{model}] {result}")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            return _error("Ollama cloud non authentifie. Lance 'ollama signin' pour te connecter.")
        return _error(f"Erreur web search: {e}")
    except Exception as e:
        return _error(f"Erreur web search: {e}")


@tool(
    "ollama_subagents",
    "Lancer 3 sous-agents Ollama cloud en parallele sur un sujet. Chaque agent (minimax, glm, kimi) analyse un aspect different. Args: task, aspects.",
    {"task": str, "aspects": str},
)
async def ollama_subagents(args: dict[str, Any]) -> dict[str, Any]:
    task = args["task"]
    aspects_raw = args.get("aspects", "")

    if aspects_raw:
        aspects = [a.strip() for a in aspects_raw.split(",")][:3]
    else:
        aspects = ["analyse technique", "donnees actuelles", "recommandation"]
    while len(aspects) < 3:
        aspects.append(f"perspective {len(aspects)+1}")

    system = (
        "Tu es un sous-agent specialise. Analyse le sujet sous l'angle specifie. "
        "Sois precis, concis et factuel. Reponds en francais."
    )

    async def _run_agent(model: str, aspect: str) -> str:
        prompt = f"TACHE: {task}\nANGLE D'ANALYSE: {aspect}\n\nAnalyse ce sujet sous cet angle specifique."
        try:
            result = await _ollama_cloud_query(prompt, model, timeout=90, system=system)
            return f"[{model.split(':')[0].upper()} — {aspect}]\n{result}"
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                return f"[{model}] Non authentifie — lance 'ollama signin'"
            return f"[{model}] Erreur: {e}"
        except Exception as e:
            return f"[{model}] Erreur: {e}"

    tasks = [
        _run_agent(CLOUD_MODELS[i % len(CLOUD_MODELS)], aspects[i])
        for i in range(len(aspects))
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    output_parts = []
    for r in results:
        output_parts.append(f"[ERREUR] {r}" if isinstance(r, Exception) else str(r))

    return _text(
        f"=== SOUS-AGENTS OLLAMA ({len(aspects)} paralleles) ===\n\n"
        + "\n\n---\n\n".join(output_parts)
    )


@tool(
    "ollama_trading_analysis",
    "Analyse trading parallele via 3 sous-agents cloud: scanner marche, analyse technique, recommandation. Args: pair, timeframe.",
    {"pair": str, "timeframe": str},
)
async def ollama_trading_analysis(args: dict[str, Any]) -> dict[str, Any]:
    pair = args.get("pair", "BTC/USDT")
    timeframe = args.get("timeframe", "1h")

    agents_config = [
        ("minimax-m2.5:cloud", "SCANNER", f"Recherche les dernieres donnees de marche pour {pair}. Prix actuel, volume 24h, variation, funding rate. Donne les chiffres exacts."),
        ("glm-5:cloud", "ANALYSTE", f"Analyse technique de {pair} en {timeframe}. RSI, MACD, supports/resistances, tendance. Base-toi sur les donnees recentes."),
        ("kimi-k2.5:cloud", "STRATEGE", f"Recommandation trading pour {pair} en {timeframe}. Entry, TP, SL, direction (long/short), score de confiance 0-100. Justifie brievement."),
    ]

    system = "Tu es un expert trading crypto. Reponds en francais, sois precis et concis."

    async def _run(model: str, role: str, prompt: str) -> str:
        try:
            result = await _ollama_cloud_query(prompt, model, timeout=90, system=system)
            return f"[{role}] {result}"
        except Exception as e:
            return f"[{role}] Erreur: {e}"

    results = await asyncio.gather(*[_run(m, r, p) for m, r, p in agents_config])

    return _text(
        f"=== TRADING ANALYSIS {pair} ({timeframe}) — 3 AGENTS ===\n\n"
        + "\n\n---\n\n".join(results)
    )


# ═══════════════════════════════════════════════════════════════════════════
# SCRIPTS & PROJETS
# ═══════════════════════════════════════════════════════════════════════════

@tool("run_script", "Executer un script Python indexe. Args: script_name, args.", {"script_name": str, "args": str})
async def run_script(args: dict[str, Any]) -> dict[str, Any]:
    name = args["script_name"]
    path = SCRIPTS.get(name)
    if not path:
        return _error(f"Script inconnu: {name}. Disponibles: {', '.join(sorted(SCRIPTS))}")
    if not path.exists():
        return _error(f"Fichier absent: {path}")
    try:
        cmd = [sys.executable, str(path)]
        if args.get("args"):
            cmd.extend(args["args"].split())
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=str(path.parent))
        out = r.stdout[-3000:] if len(r.stdout) > 3000 else r.stdout
        if r.returncode != 0:
            out += f"\n[STDERR] {r.stderr[-1000:]}"
        return _text(f"[{name}] exit={r.returncode}\n{out}")
    except subprocess.TimeoutExpired:
        return _error(f"Timeout 120s: {name}")
    except Exception as e:
        return _error(str(e))


@tool("list_scripts", "Lister les scripts Python disponibles.", {})
async def list_scripts(args: dict[str, Any]) -> dict[str, Any]:
    lines = [f"  [{'OK' if p.exists() else 'ABSENT'}] {n}: {p}" for n, p in sorted(SCRIPTS.items())]
    return _text("Scripts:\n" + "\n".join(lines))


@tool("list_project_paths", "Lister les dossiers projets indexes.", {})
async def list_project_paths(args: dict[str, Any]) -> dict[str, Any]:
    lines = [f"  [{'OK' if p.exists() else 'ABSENT'}] {n}: {p}" for n, p in sorted(PATHS.items())]
    return _text("Projets:\n" + "\n".join(lines))


# ═══════════════════════════════════════════════════════════════════════════
# WINDOWS — APPLICATIONS
# ═══════════════════════════════════════════════════════════════════════════

@tool("open_app", "Ouvrir une application par nom. Args: name, args.", {"name": str, "args": str})
async def open_app(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import open_application
    return _text(open_application(args["name"], args.get("args", "")))


@tool("close_app", "Fermer une application par nom de processus. Args: name.", {"name": str})
async def close_app(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import close_application
    return _text(close_application(args["name"]))


@tool("open_url", "Ouvrir une URL dans le navigateur. Args: url, browser.", {"url": str, "browser": str})
async def open_url_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import open_url
    return _text(open_url(args["url"], args.get("browser", "chrome")))


# ═══════════════════════════════════════════════════════════════════════════
# WINDOWS — PROCESSUS
# ═══════════════════════════════════════════════════════════════════════════

@tool("list_processes", "Lister les processus Windows. Args: filter.", {"filter": str})
async def list_processes_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import list_processes
    procs = list_processes(args.get("filter"))
    if not procs:
        return _text("Aucun processus.")
    lines = [f"  {p.get('Name','?')} (PID {p.get('Id','?')}) — {round(p.get('WorkingSet64',0)/1048576,1)} MB" for p in procs[:30]]
    return _text(f"Processus ({len(procs)}):\n" + "\n".join(lines))


@tool("kill_process", "Arreter un processus par nom ou PID. Args: target.", {"target": str})
async def kill_process_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import kill_process
    return _text(kill_process(args["target"]))


# ═══════════════════════════════════════════════════════════════════════════
# WINDOWS — FENETRES
# ═══════════════════════════════════════════════════════════════════════════

@tool("list_windows", "Lister toutes les fenetres visibles avec leurs titres.", {})
async def list_windows_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import list_windows
    return _text(list_windows())


@tool("focus_window", "Mettre une fenetre au premier plan. Args: title.", {"title": str})
async def focus_window_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import focus_window
    return _text(focus_window(args["title"]))


@tool("minimize_window", "Minimiser une fenetre. Args: title.", {"title": str})
async def minimize_window_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import minimize_window
    return _text(minimize_window(args["title"]))


@tool("maximize_window", "Maximiser une fenetre. Args: title.", {"title": str})
async def maximize_window_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import maximize_window
    return _text(maximize_window(args["title"]))


# ═══════════════════════════════════════════════════════════════════════════
# WINDOWS — CLAVIER & SOURIS
# ═══════════════════════════════════════════════════════════════════════════

@tool("send_keys", "Envoyer des touches clavier a la fenetre active. Args: keys.", {"keys": str})
async def send_keys_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import send_keys
    return _text(send_keys(args["keys"]))


@tool("type_text", "Taper du texte dans la fenetre active. Args: text.", {"text": str})
async def type_text_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import type_text
    return _text(type_text(args["text"]))


@tool("press_hotkey", "Appuyer sur un raccourci clavier (ctrl+c, alt+tab, win+d). Args: keys.", {"keys": str})
async def press_hotkey_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import press_hotkey
    return _text(press_hotkey(args["keys"]))


@tool("mouse_click", "Cliquer a des coordonnees ecran. Args: x, y.", {"x": int, "y": int})
async def mouse_click_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import mouse_click
    return _text(mouse_click(args["x"], args["y"]))


# ═══════════════════════════════════════════════════════════════════════════
# WINDOWS — CLIPBOARD
# ═══════════════════════════════════════════════════════════════════════════

@tool("clipboard_get", "Lire le contenu du presse-papier.", {})
async def clipboard_get_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import clipboard_get
    return _text(f"Presse-papier: {clipboard_get()}")


@tool("clipboard_set", "Ecrire dans le presse-papier. Args: text.", {"text": str})
async def clipboard_set_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import clipboard_set
    return _text(clipboard_set(args["text"]))


# ═══════════════════════════════════════════════════════════════════════════
# WINDOWS — FICHIERS
# ═══════════════════════════════════════════════════════════════════════════

@tool("open_folder", "Ouvrir un dossier dans l'Explorateur. Args: path.", {"path": str})
async def open_folder_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import open_folder
    return _text(open_folder(args["path"]))


@tool("list_folder", "Lister le contenu d'un dossier. Args: path, pattern.", {"path": str, "pattern": str})
async def list_folder_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import list_folder
    return _text(list_folder(args["path"], args.get("pattern", "*")))


@tool("create_folder", "Creer un nouveau dossier. Args: path.", {"path": str})
async def create_folder_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import create_folder
    return _text(create_folder(args["path"]))


@tool("copy_item", "Copier un fichier ou dossier. Args: source, dest.", {"source": str, "dest": str})
async def copy_item_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import copy_item
    return _text(copy_item(args["source"], args["dest"]))


@tool("move_item", "Deplacer un fichier ou dossier. Args: source, dest.", {"source": str, "dest": str})
async def move_item_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import move_item
    return _text(move_item(args["source"], args["dest"]))


@tool("delete_item", "Supprimer un fichier (vers la corbeille). Args: path.", {"path": str})
async def delete_item_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import delete_item
    return _text(delete_item(args["path"]))


@tool("read_text_file", "Lire un fichier texte. Args: path, lines.", {"path": str, "lines": int})
async def read_text_file_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import read_file
    return _text(read_file(args["path"], args.get("lines", 50)))


@tool("write_text_file", "Ecrire dans un fichier texte. Args: path, content.", {"path": str, "content": str})
async def write_text_file_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import write_file
    return _text(write_file(args["path"], args["content"]))


@tool("search_files", "Chercher des fichiers recursivement. Args: path, pattern.", {"path": str, "pattern": str})
async def search_files_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import search_files
    return _text(search_files(args["path"], args["pattern"]))


# ═══════════════════════════════════════════════════════════════════════════
# WINDOWS — AUDIO
# ═══════════════════════════════════════════════════════════════════════════

@tool("volume_up", "Augmenter le volume systeme.", {})
async def volume_up_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import volume_up
    return _text(volume_up())


@tool("volume_down", "Baisser le volume systeme.", {})
async def volume_down_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import volume_down
    return _text(volume_down())


@tool("volume_mute", "Basculer muet/son.", {})
async def volume_mute_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import volume_mute
    return _text(volume_mute())


# ═══════════════════════════════════════════════════════════════════════════
# WINDOWS — ECRAN
# ═══════════════════════════════════════════════════════════════════════════

@tool("screenshot", "Prendre une capture d'ecran. Args: filename.", {"filename": str})
async def screenshot_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import screenshot
    return _text(screenshot(args.get("filename", "")))


@tool("screen_resolution", "Obtenir la resolution de l'ecran.", {})
async def screen_resolution_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import get_screen_resolution
    return _text(get_screen_resolution())


# ═══════════════════════════════════════════════════════════════════════════
# WINDOWS — SYSTEME
# ═══════════════════════════════════════════════════════════════════════════

@tool("system_info", "Infos systeme completes: CPU, RAM, GPU, disques, uptime.", {})
async def system_info_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import get_system_info
    info = get_system_info()
    return _text("Systeme:\n" + "\n".join(f"  {k}: {v}" for k, v in info.items()))


@tool("gpu_info", "Infos detaillees GPU (VRAM, driver).", {})
async def gpu_info_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import get_gpu_info
    return _text(get_gpu_info())


@tool("network_info", "Adresses IP et interfaces reseau.", {})
async def network_info_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import get_network_info
    return _text(get_network_info())


@tool("powershell_run", "Executer une commande PowerShell. Args: command.", {"command": str})
async def powershell_run_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import run_powershell
    r = run_powershell(args["command"], timeout=60)
    out = r["stdout"] if r["success"] else f"ERREUR: {r['stderr']}"
    return _text(f"[PS] exit={r['exit_code']}\n{out}")


@tool("lock_screen", "Verrouiller le PC.", {})
async def lock_screen_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import lock_screen
    return _text(lock_screen())


@tool("shutdown_pc", "Eteindre le PC.", {})
async def shutdown_pc_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import shutdown_pc
    return _text(shutdown_pc())


@tool("restart_pc", "Redemarrer le PC.", {})
async def restart_pc_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import restart_pc
    return _text(restart_pc())


@tool("sleep_pc", "Mettre le PC en veille.", {})
async def sleep_pc_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import sleep_pc
    return _text(sleep_pc())


# ═══════════════════════════════════════════════════════════════════════════
# WINDOWS — SERVICES
# ═══════════════════════════════════════════════════════════════════════════

@tool("list_services", "Lister les services Windows. Args: filter.", {"filter": str})
async def list_services_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import list_services
    return _text(list_services(args.get("filter", "")))


@tool("start_service", "Demarrer un service Windows. Args: name.", {"name": str})
async def start_service_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import start_service
    return _text(start_service(args["name"]))


@tool("stop_service", "Arreter un service Windows. Args: name.", {"name": str})
async def stop_service_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import stop_service
    return _text(stop_service(args["name"]))


# ═══════════════════════════════════════════════════════════════════════════
# WINDOWS — RESEAU
# ═══════════════════════════════════════════════════════════════════════════

@tool("wifi_networks", "Lister les reseaux WiFi disponibles.", {})
async def wifi_networks_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import get_wifi_networks
    return _text(get_wifi_networks())


@tool("ping", "Ping un hote. Args: host.", {"host": str})
async def ping_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import ping_host
    return _text(ping_host(args["host"]))


@tool("get_ip", "Obtenir les adresses IP locales.", {})
async def get_ip_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import get_ip_address
    return _text(get_ip_address())


# ═══════════════════════════════════════════════════════════════════════════
# WINDOWS — REGISTRE
# ═══════════════════════════════════════════════════════════════════════════

@tool("registry_read", "Lire une valeur du registre Windows. Args: path, name.", {"path": str, "name": str})
async def registry_read_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import registry_get
    return _text(registry_get(args["path"], args.get("name", "")))


@tool("registry_write", "Ecrire une valeur dans le registre. Args: path, name, value, type.", {"path": str, "name": str, "value": str, "type": str})
async def registry_write_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import registry_set
    return _text(registry_set(args["path"], args["name"], args["value"], args.get("type", "String")))


# ═══════════════════════════════════════════════════════════════════════════
# WINDOWS — NOTIFICATIONS & VOIX
# ═══════════════════════════════════════════════════════════════════════════

@tool("notify", "Notification toast Windows. Args: title, message.", {"title": str, "message": str})
async def notify_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import notify_windows
    ok = notify_windows(args.get("title", "JARVIS"), args.get("message", ""))
    return _text(f"Notification {'OK' if ok else 'echouee'}")


@tool("speak", "Synthese vocale Windows SAPI. Args: text.", {"text": str})
async def speak_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.voice import speak_text
    ok = await speak_text(args.get("text", ""))
    return _text(f"Parole {'OK' if ok else 'echouee'}")


@tool("scheduled_tasks", "Lister les taches planifiees Windows. Args: filter.", {"filter": str})
async def scheduled_tasks_tool(args: dict[str, Any]) -> dict[str, Any]:
    from src.windows import list_scheduled_tasks
    return _text(list_scheduled_tasks(args.get("filter", "")))


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _text(text: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}]}

def _error(text: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}], "is_error": True}


# ═══════════════════════════════════════════════════════════════════════════
# ASSEMBLE MCP SERVER — ALL TOOLS (83 tools)
# ═══════════════════════════════════════════════════════════════════════════

jarvis_server = create_sdk_mcp_server(
    name="jarvis",
    version="3.2.0",
    tools=[
        # LM Studio (4)
        lm_query, lm_models, lm_cluster_status, consensus,
        # LM Studio Model Management (7)
        lm_load_model, lm_unload_model, lm_switch_coder, lm_switch_dev,
        lm_gpu_stats, lm_benchmark, lm_perf_metrics,
        # Ollama local (4)
        ollama_query, ollama_models, ollama_pull, ollama_status,
        # Ollama Cloud — Web Search + Sub-agents (3)
        ollama_web_search, ollama_subagents, ollama_trading_analysis,
        # Scripts & projets (3)
        run_script, list_scripts, list_project_paths,
        # Applications (3)
        open_app, close_app, open_url_tool,
        # Processus (2)
        list_processes_tool, kill_process_tool,
        # Fenetres (4)
        list_windows_tool, focus_window_tool, minimize_window_tool, maximize_window_tool,
        # Clavier & souris (4)
        send_keys_tool, type_text_tool, press_hotkey_tool, mouse_click_tool,
        # Clipboard (2)
        clipboard_get_tool, clipboard_set_tool,
        # Fichiers (8)
        open_folder_tool, list_folder_tool, create_folder_tool,
        copy_item_tool, move_item_tool, delete_item_tool,
        read_text_file_tool, write_text_file_tool, search_files_tool,
        # Audio (3)
        volume_up_tool, volume_down_tool, volume_mute_tool,
        # Ecran (2)
        screenshot_tool, screen_resolution_tool,
        # Systeme (7)
        system_info_tool, gpu_info_tool, network_info_tool, powershell_run_tool,
        lock_screen_tool, shutdown_pc_tool, restart_pc_tool, sleep_pc_tool,
        # Services (3)
        list_services_tool, start_service_tool, stop_service_tool,
        # Reseau (3)
        wifi_networks_tool, ping_tool, get_ip_tool,
        # Registre (2)
        registry_read_tool, registry_write_tool,
        # Notifications & voix (3)
        notify_tool, speak_tool, scheduled_tasks_tool,
    ],
)
