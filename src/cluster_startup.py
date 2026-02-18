"""JARVIS Cluster Startup — Boot-time cluster optimization.

Guarantees optimal state on M1 + M2 + Ollama at every JARVIS launch:
- Auto-start LM Studio server if stopped
- Load required models with GPU max, flash attention, optimal context
- Unload blacklisted/wasteful models
- Warmup inference to pre-fill KV cache
- Benchmark latency for routing decisions
- Verify Ollama readiness
- Retry with exponential backoff on failures
"""

from __future__ import annotations

import asyncio
import re
import subprocess
import sys
import time
from typing import Any

import httpx

from src.config import config

LMS_CLI = r"C:\Users\franc\.lmstudio\bin\lms.exe"

# ── M1 Model Policy ──────────────────────────────────────────────────────
# Models loaded at boot with optimal settings
M1_REQUIRED = {
    "qwen/qwen3-30b-a3b-2507": {
        "gpu": "max",
        "context": 32768,
        "parallel": 4,
    },
}

# Models NEVER loaded on M1 (waste VRAM, worse quality)
M1_BLACKLIST = {"nvidia/nemotron-3-nano", "zai-org/glm-4.7-flash"}

# ── M1 On-demand models (available but not loaded at boot) ────────────────
M1_AVAILABLE = {
    "qwen/qwen3-coder-30b",         # Code specialise (18.63 GB)
    "mistralai/devstral-small-2-2512",  # Dev tasks (15.21 GB)
    "openai/gpt-oss-20b",           # General purpose (12.11 GB)
}

# ── Warmup prompts (pre-fill KV cache + verify inference) ─────────────────
WARMUP_PROMPT = "Reponds OK."
WARMUP_MAX_TOKENS = 5

# ── Strip ANSI escape codes from lms.exe output ──────────────────────────
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\[\\?25[hl]")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _log(msg: str, level: str = "INFO") -> None:
    """Structured log for startup."""
    print(f"  [{level}] {msg}", flush=True)


# ═══════════════════════════════════════════════════════════════════════════
# LM Studio CLI Operations
# ═══════════════════════════════════════════════════════════════════════════

def _lms_server_status() -> bool:
    """Check if LM Studio server is running."""
    try:
        r = subprocess.run(
            [LMS_CLI, "server", "status"],
            capture_output=True, timeout=10, encoding="utf-8", errors="replace",
        )
        output = _strip_ansi(r.stdout + r.stderr).lower()
        return "running" in output and "not running" not in output
    except Exception:
        return False


def _lms_server_start() -> bool:
    """Start LM Studio server on port 1234."""
    try:
        r = subprocess.run(
            [LMS_CLI, "server", "start"],
            capture_output=True, timeout=30, encoding="utf-8", errors="replace",
        )
        output = _strip_ansi(r.stdout + r.stderr).lower()
        return "success" in output or "already running" in output
    except Exception:
        return False


def _lms_ps() -> list[dict[str, str]]:
    """Get loaded models with metadata (name, size, context, status)."""
    try:
        r = subprocess.run(
            [LMS_CLI, "ps"],
            capture_output=True, timeout=10, encoding="utf-8", errors="replace",
        )
        output = _strip_ansi(r.stdout + r.stderr)
        models = []
        for line in output.splitlines()[1:]:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 2 and "/" in parts[0]:
                model = {"id": parts[0]}
                # Parse remaining fields if available
                for p in parts[1:]:
                    if "GB" in p:
                        model["size"] = p
                    elif p.isdigit() and int(p) > 1000:
                        model["context"] = p
                    elif p in ("IDLE", "RUNNING", "LOADING"):
                        model["status"] = p
                models.append(model)
        return models
    except Exception:
        return []


def _lms_ps_ids() -> list[str]:
    """Get just the model IDs of loaded models."""
    return [m["id"] for m in _lms_ps()]


def _lms_unload(model: str) -> bool:
    """Unload a model from M1."""
    try:
        r = subprocess.run(
            [LMS_CLI, "unload", model],
            capture_output=True, timeout=30, encoding="utf-8", errors="replace",
        )
        output = _strip_ansi(r.stdout + r.stderr)
        return "unloaded" in output.lower() or "not loaded" in output.lower()
    except Exception:
        return False


def _lms_load(
    model: str,
    gpu: str = "max",
    context: int = 32768,
    parallel: int = 4,
) -> bool:
    """Load a model on M1 with optimal settings (no TTL = permanent)."""
    try:
        cmd = [
            LMS_CLI, "load", model,
            "--gpu", gpu,
            "-c", str(context),
            "--parallel", str(parallel),
            "-y",
        ]
        r = subprocess.run(
            cmd, capture_output=True, timeout=180, encoding="utf-8", errors="replace",
        )
        combined = _strip_ansi(r.stdout + r.stderr).lower()
        return "loaded successfully" in combined or "already loaded" in combined
    except subprocess.TimeoutExpired:
        _log(f"Timeout chargement {model} (180s)", "WARN")
        return False
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════════════════
# Inference Warmup & Benchmarking
# ═══════════════════════════════════════════════════════════════════════════

async def _warmup_model(url: str, model: str, timeout: float = 15.0) -> dict[str, Any]:
    """Warmup a model and return latency benchmark.

    Returns: {"ok": bool, "latency_ms": int, "tokens_per_sec": float}
    """
    try:
        t0 = time.monotonic()
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.post(f"{url}/api/v1/chat", json={
                "model": model,
                "input": WARMUP_PROMPT,
                "temperature": 0.1,
                "max_output_tokens": WARMUP_MAX_TOKENS,
                "stream": False,
                "store": False,
            })
            r.raise_for_status()
            latency = int((time.monotonic() - t0) * 1000)
            data = r.json()
            stats = data.get("stats", {})
            completion_tokens = stats.get("total_output_tokens", 1)
            tps = completion_tokens / max((time.monotonic() - t0), 0.01)
            return {"ok": True, "latency_ms": latency, "tokens_per_sec": round(tps, 1)}
    except Exception as e:
        return {"ok": False, "latency_ms": -1, "tokens_per_sec": 0, "error": str(e)}


async def _warmup_ollama(url: str, model: str, timeout: float = 10.0) -> dict[str, Any]:
    """Warmup an Ollama model."""
    try:
        t0 = time.monotonic()
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.post(f"{url}/api/chat", json={
                "model": model,
                "messages": [{"role": "user", "content": WARMUP_PROMPT}],
                "stream": False, "think": False,
                "options": {"temperature": 0.1, "num_predict": WARMUP_MAX_TOKENS},
            })
            r.raise_for_status()
            latency = int((time.monotonic() - t0) * 1000)
            return {"ok": True, "latency_ms": latency}
    except Exception as e:
        return {"ok": False, "latency_ms": -1, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════
# GPU Monitoring
# ═══════════════════════════════════════════════════════════════════════════

def _get_gpu_stats() -> list[dict[str, Any]]:
    """Get GPU VRAM usage + temperature via nvidia-smi."""
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,memory.used,memory.total,utilization.gpu,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, timeout=10, encoding="utf-8", errors="replace",
        )
        gpus = []
        for line in r.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 6:
                temp = int(parts[5]) if parts[5].isdigit() else -1
                gpus.append({
                    "index": int(parts[0]),
                    "name": parts[1],
                    "vram_used_mb": int(parts[2]),
                    "vram_total_mb": int(parts[3]),
                    "gpu_util": int(parts[4]),
                    "temp_c": temp,
                    "vram_free_mb": int(parts[3]) - int(parts[2]),
                    "vram_pct": round(int(parts[2]) / max(int(parts[3]), 1) * 100, 1),
                })
        return gpus
    except Exception:
        return []


def check_thermal_status() -> dict[str, Any]:
    """Verifie l'etat thermique des GPU pour le routage commandant.

    Returns:
        {"ok": bool, "max_temp": int, "status": "normal"|"warning"|"critical",
         "hot_gpus": [...], "recommendation": str}
    """
    gpus = _get_gpu_stats()
    if not gpus:
        return {"ok": True, "max_temp": -1, "status": "unknown", "hot_gpus": [], "recommendation": ""}

    temps = [g["temp_c"] for g in gpus if g["temp_c"] >= 0]
    if not temps:
        return {"ok": True, "max_temp": -1, "status": "unknown", "hot_gpus": [], "recommendation": ""}

    max_temp = max(temps)
    hot_gpus = [g for g in gpus if g["temp_c"] >= config.gpu_thermal_warning]
    critical_gpus = [g for g in gpus if g["temp_c"] >= config.gpu_thermal_critical]

    if critical_gpus:
        return {
            "ok": False,
            "max_temp": max_temp,
            "status": "critical",
            "hot_gpus": [{"index": g["index"], "name": g["name"], "temp": g["temp_c"]} for g in critical_gpus],
            "recommendation": "Deporter taches vers M2/OL1/GEMINI",
        }
    elif hot_gpus:
        return {
            "ok": True,
            "max_temp": max_temp,
            "status": "warning",
            "hot_gpus": [{"index": g["index"], "name": g["name"], "temp": g["temp_c"]} for g in hot_gpus],
            "recommendation": "Reduire charge M1, preferer M2 pour code",
        }
    else:
        return {
            "ok": True,
            "max_temp": max_temp,
            "status": "normal",
            "hot_gpus": [],
            "recommendation": "",
        }


# ═══════════════════════════════════════════════════════════════════════════
# Ollama Checks
# ═══════════════════════════════════════════════════════════════════════════

async def _check_ollama() -> dict[str, Any]:
    """Verify Ollama is running, list available models."""
    ol = config.get_ollama_node("OL1")
    if not ol:
        return {"ok": False, "error": "OL1 non configure"}
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{ol.url}/api/tags")
            r.raise_for_status()
            models = [m["name"] for m in r.json().get("models", [])]
            has_correction = any("qwen3" in m for m in models)
            return {
                "ok": True,
                "models": models,
                "count": len(models),
                "has_correction_model": has_correction,
            }
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════
# M2 Remote Checks
# ═══════════════════════════════════════════════════════════════════════════

async def _check_m2() -> dict[str, Any]:
    """Check M2 connectivity and loaded models."""
    m2 = config.get_node("M2")
    if not m2:
        return {"ok": False, "error": "M2 non configure"}
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{m2.url}/api/v1/models")
            r.raise_for_status()
            models = [m["key"] for m in r.json().get("models", []) if m.get("loaded_instances")]
            has_coder = any("deepseek" in m or "coder" in m for m in models)
            return {
                "ok": True,
                "models": models,
                "count": len(models),
                "has_coder": has_coder,
            }
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════
# Main Startup Sequence
# ═══════════════════════════════════════════════════════════════════════════

async def ensure_cluster_ready(
    warmup: bool = True,
    benchmark: bool = True,
    verbose: bool = True,
) -> dict[str, Any]:
    """Ensure the cluster is in optimal state. Returns detailed status report.

    Sequence:
    1. Auto-start LM Studio server if not running
    2. Unload blacklisted models from M1
    3. Load required models on M1 (with retry)
    4. Warmup M1 model (pre-fill KV cache)
    5. Check M2 connectivity and models
    6. Warmup M2 if available
    7. Verify Ollama readiness + warmup
    8. Collect GPU stats
    9. Benchmark latency for routing
    """
    report: dict[str, Any] = {"timestamp": time.strftime("%H:%M:%S")}

    if verbose:
        print("=" * 55)
        print("  JARVIS Cluster Startup — Optimization Sequence")
        print("=" * 55)

    # ── Step 1: Ensure LM Studio server is running ────────────────────
    if not _lms_server_status():
        _log("LM Studio server arrete — demarrage...")
        ok = _lms_server_start()
        report["server_start"] = "OK" if ok else "ECHEC"
        if ok:
            _log("Serveur demarre sur port 1234", "OK")
            await asyncio.sleep(2)  # Wait for server to be ready
        else:
            _log("Impossible de demarrer le serveur!", "ERREUR")
            report["fatal"] = "server_start_failed"
            return report
    else:
        report["server_start"] = "deja actif"
        if verbose:
            _log("Serveur LM Studio actif", "OK")

    # ── Step 2: Check currently loaded models ─────────────────────────
    loaded = _lms_ps_ids()
    report["m1_initial"] = loaded.copy()
    if verbose:
        _log(f"M1 modeles charges: {', '.join(loaded) if loaded else 'aucun'}")

    # ── Step 3: Unload blacklisted models ─────────────────────────────
    unloaded = []
    for model_id in loaded:
        if model_id in M1_BLACKLIST:
            ok = _lms_unload(model_id)
            unloaded.append(model_id)
            if verbose:
                _log(f"Unload {model_id}: {'OK' if ok else 'ECHEC'}")
    report["m1_unloaded"] = unloaded

    # ── Step 4: Load required models with retry ───────────────────────
    loaded_after = _lms_ps_ids()
    loaded_bases = {m.split(":")[0] if ":" in m and m.split(":")[-1].isdigit() else m for m in loaded_after}

    for model, opts in M1_REQUIRED.items():
        if model in loaded_bases:
            report[f"load_{model}"] = "deja charge"
            if verbose:
                _log(f"{model}: deja charge", "OK")
            continue

        # Try loading with retry (max 2 attempts)
        for attempt in range(2):
            if verbose:
                _log(f"Chargement {model} (tentative {attempt + 1})...")
            ok = _lms_load(model, **opts)
            if ok:
                report[f"load_{model}"] = "OK"
                if verbose:
                    _log(f"{model}: charge (GPU={opts['gpu']}, ctx={opts['context']}, parallel={opts['parallel']})", "OK")
                break
            if attempt == 0:
                await asyncio.sleep(3)  # Wait before retry
        else:
            report[f"load_{model}"] = "ECHEC (2 tentatives)"
            _log(f"{model}: ECHEC apres 2 tentatives", "ERREUR")

    # ── Step 5: Warmup M1 ─────────────────────────────────────────────
    if warmup:
        m1 = config.get_node("M1")
        if m1:
            for model in M1_REQUIRED:
                if verbose:
                    _log(f"Warmup {model}...")
                bench = await _warmup_model(m1.url, model)
                report[f"warmup_{model}"] = bench
                if bench["ok"] and verbose:
                    _log(f"Warmup OK — {bench['latency_ms']}ms, {bench['tokens_per_sec']} tok/s", "OK")
                elif not bench["ok"] and verbose:
                    _log(f"Warmup ECHEC: {bench.get('error', '?')}", "WARN")

    # ── Step 6: Check M2 ──────────────────────────────────────────────
    m2_status = await _check_m2()
    report["m2"] = m2_status
    if verbose:
        if m2_status["ok"]:
            _log(f"M2: ONLINE ({m2_status['count']} modeles) — coder={'OUI' if m2_status['has_coder'] else 'NON'}", "OK")
        else:
            _log(f"M2: OFFLINE ({m2_status.get('error', '')})", "WARN")

    # Warmup M2 if available
    if warmup and m2_status["ok"]:
        m2_node = config.get_node("M2")
        if m2_node:
            bench = await _warmup_model(m2_node.url, m2_node.default_model)
            report["warmup_m2"] = bench
            if bench["ok"] and verbose:
                _log(f"M2 warmup: {bench['latency_ms']}ms, {bench['tokens_per_sec']} tok/s", "OK")

    # ── Step 7: Check Ollama ──────────────────────────────────────────
    ollama_status = await _check_ollama()
    report["ollama"] = ollama_status
    if verbose:
        if ollama_status["ok"]:
            _log(f"Ollama: {ollama_status['count']} modeles — correction={'OUI' if ollama_status['has_correction_model'] else 'NON'}", "OK")
        else:
            _log(f"Ollama: OFFLINE ({ollama_status.get('error', '')})", "WARN")

    # Warmup Ollama correction model
    if warmup and ollama_status["ok"] and ollama_status.get("has_correction_model"):
        ol = config.get_ollama_node("OL1")
        if ol:
            bench = await _warmup_ollama(ol.url, "qwen3:1.7b")
            report["warmup_ollama"] = bench
            if bench["ok"] and verbose:
                _log(f"Ollama warmup: {bench['latency_ms']}ms", "OK")

    # ── Step 8: GPU stats + thermal check ──────────────────────────────
    gpus = _get_gpu_stats()
    report["gpus"] = gpus
    if verbose and gpus:
        total_used = sum(g["vram_used_mb"] for g in gpus)
        total_avail = sum(g["vram_total_mb"] for g in gpus)
        _log(f"VRAM: {total_used}MB / {total_avail}MB ({round(total_used/max(total_avail,1)*100)}%)")
        for g in gpus:
            bar = "#" * int(g["vram_pct"] / 5) + "." * (20 - int(g["vram_pct"] / 5))
            temp_str = f" {g['temp_c']}C" if g.get("temp_c", -1) >= 0 else ""
            _log(f"  GPU{g['index']} {g['name'][:20]:20s} [{bar}] {g['vram_used_mb']}MB/{g['vram_total_mb']}MB ({g['vram_pct']}%){temp_str}")

    # Thermal status
    thermal = check_thermal_status()
    report["thermal"] = thermal
    if verbose and thermal["status"] != "unknown":
        if thermal["status"] == "critical":
            _log(f"THERMAL CRITIQUE: {thermal['max_temp']}C — {thermal['recommendation']}", "ERREUR")
        elif thermal["status"] == "warning":
            _log(f"THERMAL WARNING: {thermal['max_temp']}C — {thermal['recommendation']}", "WARN")
        else:
            _log(f"Thermal: {thermal['max_temp']}C (normal)", "OK")

    # ── Step 9: Final state ───────────────────────────────────────────
    final = _lms_ps()
    report["m1_final"] = final

    if verbose:
        print("=" * 55)
        # Summary line
        m1_ok = any(m.get("id") == "qwen/qwen3-30b-a3b-2507" for m in final)
        m2_ok = m2_status["ok"]
        ol_ok = ollama_status["ok"]
        status = "OPTIMAL" if (m1_ok and m2_ok and ol_ok) else "PARTIEL" if m1_ok else "DEGRADE"
        _log(f"Cluster: {status} | M1={'OK' if m1_ok else 'KO'} M2={'OK' if m2_ok else 'KO'} OL={'OK' if ol_ok else 'KO'}", status)
        print("=" * 55)

    report["status"] = "OPTIMAL" if all([
        any(m.get("id") == "qwen/qwen3-30b-a3b-2507" for m in final),
        m2_status["ok"],
        ollama_status["ok"],
    ]) else "PARTIEL"

    return report


# ═══════════════════════════════════════════════════════════════════════════
# On-Demand Model Loading (for hot-swapping)
# ═══════════════════════════════════════════════════════════════════════════

async def load_model_on_demand(
    model: str,
    gpu: str = "max",
    context: int = 16384,
    parallel: int = 2,
    unload_others: bool = False,
) -> dict[str, Any]:
    """Load a model on-demand (e.g., qwen3-coder-30b for coding tasks).

    If unload_others=True, unloads all other models first to free VRAM.
    """
    if model not in M1_AVAILABLE and model not in M1_REQUIRED:
        return {"ok": False, "error": f"Modele non disponible: {model}"}

    loaded = _lms_ps_ids()
    if model in loaded:
        return {"ok": True, "status": "deja charge"}

    if unload_others:
        for m in loaded:
            _lms_unload(m)
        await asyncio.sleep(2)

    ok = _lms_load(model, gpu, context, parallel)
    if ok:
        m1 = config.get_node("M1")
        if m1:
            bench = await _warmup_model(m1.url, model)
            return {"ok": True, "status": "charge + warmup", "bench": bench}
    return {"ok": ok, "status": "charge" if ok else "echec"}


async def switch_to_coder_mode() -> dict[str, Any]:
    """Switch M1 to coding mode: load qwen3-coder-30b alongside qwen3-30b."""
    return await load_model_on_demand(
        "qwen/qwen3-coder-30b",
        gpu="max", context=16384, parallel=2,
    )


async def switch_to_dev_mode() -> dict[str, Any]:
    """Switch M1 to dev mode: load devstral for development tasks."""
    return await load_model_on_demand(
        "mistralai/devstral-small-2-2512",
        gpu="max", context=16384, parallel=2,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Quick Health Check (lightweight, for periodic monitoring)
# ═══════════════════════════════════════════════════════════════════════════

async def quick_health_check() -> dict[str, str]:
    """Fast health check (no warmup, no GPU stats). For periodic use."""
    status = {}

    # M1
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            r = await c.get(f"{config.get_node_url('M1')}/api/v1/models")
            r.raise_for_status()
            models = [m["key"] for m in r.json().get("models", []) if m.get("loaded_instances")]
            has_main = any("qwen3-30b" in m for m in models)
            status["m1"] = f"OK ({len(models)} modeles)" if has_main else f"WARN (pas de qwen3-30b)"
    except Exception:
        status["m1"] = "OFFLINE"

    # M2
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            r = await c.get(f"{config.get_node_url('M2')}/api/v1/models")
            r.raise_for_status()
            status["m2"] = "OK"
    except Exception:
        status["m2"] = "OFFLINE"

    # Ollama
    try:
        ol = config.get_ollama_node("OL1")
        if ol:
            async with httpx.AsyncClient(timeout=3) as c:
                r = await c.get(f"{ol.url}/api/tags")
                r.raise_for_status()
                status["ollama"] = "OK"
    except Exception:
        status["ollama"] = "OFFLINE"

    return status


def print_startup_report(report: dict[str, Any]) -> None:
    """Print a concise startup report (legacy compat)."""
    print("=" * 55)
    print("  JARVIS Cluster Status")
    print("=" * 55)
    for key, val in report.items():
        if key in ("gpus", "m1_initial", "m1_final", "timestamp"):
            continue
        if isinstance(val, dict):
            status = "OK" if val.get("ok") else "!!"
            summary = f"latence={val.get('latency_ms', '?')}ms" if "latency_ms" in val else str(val)
            print(f"  [{status}] {key}: {summary}")
        else:
            label = key.replace("_", " ").title()
            if isinstance(val, str):
                status = "OK" if any(w in val for w in ("OK", "charge", "ONLINE", "pret", "actif")) else "!!"
            else:
                status = "OK"
            print(f"  [{status}] {label}: {val}")
    print("=" * 55)
