"""JARVIS Cluster Benchmark — 7-phase comprehensive cluster test.

Tests: node health, inference quality, consensus, bridge routing,
agent definitions, stress throughput, error detection.

Output: data/benchmark_report.json
Usage: python benchmark_cluster.py [--quick]
       --quick = phases 1, 2, 5, 7 only
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = r"F:\BUREAU\turbo"
os.chdir(PROJECT_ROOT)
sys.path.insert(0, PROJECT_ROOT)

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import httpx
from src.config import config
from src.tools import extract_lms_output, _strip_thinking_tags


# ══════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class PhaseResult:
    name: str
    score: float = 0.0
    duration_ms: int = 0
    details: dict = field(default_factory=dict)
    issues: list = field(default_factory=list)


@dataclass
class BenchmarkReport:
    version: str = config.version
    timestamp: str = ""
    duration_ms: int = 0
    phases: dict = field(default_factory=dict)
    issues: list = field(default_factory=list)
    recommendations: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)


TEST_PROMPT = "Explique en 2 phrases ce qu'est un MoE en IA."
SIMPLE_PROMPT = "Reponds uniquement: bonjour"


def _lm_headers(node) -> dict[str, str]:
    """Get auth headers for an LM Studio node."""
    return node.auth_headers if hasattr(node, "auth_headers") else {}


def _print(msg: str, end: str = "\n"):
    try:
        print(msg, end=end, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("ascii", errors="replace").decode(), end=end, flush=True)


# ══════════════════════════════════════════════════════════════════════════
# PHASE 1 — NODE HEALTH
# ══════════════════════════════════════════════════════════════════════════

async def phase_health() -> PhaseResult:
    _print("\n=== PHASE 1: Health Check ===")
    result = PhaseResult(name="1_health")
    t0 = time.monotonic()
    nodes_status = {}
    online = 0
    total = len(config.lm_nodes) + len(config.ollama_nodes) + 1  # +1 Gemini

    async with httpx.AsyncClient(timeout=5) as c:
        # LM Studio nodes
        for n in config.lm_nodes:
            try:
                r = await c.get(f"{n.url}/api/v1/models", headers=_lm_headers(n))
                r.raise_for_status()
                models = [m["key"] for m in r.json().get("models", []) if m.get("loaded_instances")]
                nodes_status[n.name] = {
                    "status": "ONLINE", "models": models,
                    "gpus": n.gpus, "vram_gb": n.vram_gb,
                }
                online += 1
                _print(f"  [OK] {n.name} -- {len(models)} modeles, {n.gpus} GPU, {n.vram_gb}GB")
            except Exception as e:
                nodes_status[n.name] = {"status": "OFFLINE", "error": str(e)}
                _print(f"  [--] {n.name} -- OFFLINE ({e})")

        # Ollama nodes
        for n in config.ollama_nodes:
            try:
                r = await c.get(f"{n.url}/api/tags")
                r.raise_for_status()
                models = [m["name"] for m in r.json().get("models", [])]
                nodes_status[n.name] = {"status": "ONLINE", "models": models}
                online += 1
                _print(f"  [OK] {n.name} -- {len(models)} modeles [Ollama]")
            except Exception as e:
                nodes_status[n.name] = {"status": "OFFLINE", "error": str(e)}
                _print(f"  [--] {n.name} -- OFFLINE ({e})")

    # Gemini
    try:
        proc = await asyncio.create_subprocess_exec(
            "node", config.gemini_node.proxy_path, "--ping",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
        output = stdout.decode(errors="replace").strip()
        if proc.returncode == 0 or output:
            nodes_status["GEMINI"] = {"status": "ONLINE", "models": config.gemini_node.models}
            online += 1
            _print(f"  [OK] GEMINI -- {', '.join(config.gemini_node.models)}")
        else:
            nodes_status["GEMINI"] = {"status": "OFFLINE"}
            _print(f"  [--] GEMINI -- OFFLINE")
    except Exception as e:
        nodes_status["GEMINI"] = {"status": "OFFLINE", "error": str(e)}
        _print(f"  [--] GEMINI -- OFFLINE ({e})")

    # GPU stats
    gpu_info = None
    try:
        from src.cluster_startup import _get_gpu_stats
        gpus = _get_gpu_stats()
        if gpus:
            total_vram = sum(g["vram_total_mb"] for g in gpus)
            used_vram = sum(g["vram_used_mb"] for g in gpus)
            gpu_info = {
                "count": len(gpus), "total_vram_mb": total_vram,
                "used_vram_mb": used_vram,
                "utilization_pct": round(used_vram / max(total_vram, 1) * 100),
            }
            _print(f"  GPU: {len(gpus)} detectes, {used_vram}MB / {total_vram}MB VRAM")
    except Exception:
        pass

    result.score = online / max(total, 1)
    result.duration_ms = int((time.monotonic() - t0) * 1000)
    result.details = {"nodes": nodes_status, "online": online, "total": total, "gpu": gpu_info}
    _print(f"  Score: {result.score:.0%} ({online}/{total} en ligne) -- {result.duration_ms}ms")
    return result


# ══════════════════════════════════════════════════════════════════════════
# PHASE 2 — INFERENCE
# ══════════════════════════════════════════════════════════════════════════

async def phase_inference() -> PhaseResult:
    _print("\n=== PHASE 2: Individual Inference ===")
    result = PhaseResult(name="2_inference")
    t0 = time.monotonic()
    tests = []
    ok_count = 0

    async with httpx.AsyncClient(timeout=60) as c:
        # LM Studio nodes
        for n in config.lm_nodes:
            test = {"node": n.name, "model": n.default_model}
            try:
                t1 = time.monotonic()
                r = await c.post(f"{n.url}/api/v1/chat", json={
                    "model": n.default_model, "input": TEST_PROMPT,
                    "temperature": 0.3, "max_output_tokens": 512,
                    "stream": False, "store": False,
                }, headers=_lm_headers(n))
                r.raise_for_status()
                latency = int((time.monotonic() - t1) * 1000)
                raw_data = r.json()
                content = extract_lms_output(raw_data)

                # Check for issues
                has_think = "<think>" in json.dumps(raw_data)
                is_empty = not content.strip()

                test.update({
                    "status": "OK", "latency_ms": latency,
                    "output_len": len(content), "has_think_tags": has_think,
                    "is_empty": is_empty, "preview": content[:100],
                })
                if is_empty:
                    result.issues.append({"severity": "critical", "node": n.name, "detail": "Reponse vide apres extraction"})
                    _print(f"  [!!] {n.name} -- {latency}ms -- REPONSE VIDE (think tags?)")
                elif has_think:
                    result.issues.append({"severity": "warning", "node": n.name, "detail": "Think tags detectes dans raw output"})
                    _print(f"  [OK] {n.name} -- {latency}ms -- {len(content)} chars (think tags strippees)")
                    ok_count += 1
                else:
                    _print(f"  [OK] {n.name} -- {latency}ms -- {len(content)} chars")
                    ok_count += 1
            except Exception as e:
                test.update({"status": "ERREUR", "error": str(e)})
                _print(f"  [--] {n.name} -- ERREUR: {e}")
            tests.append(test)

        # Ollama
        for n in config.ollama_nodes:
            test = {"node": n.name, "model": n.default_model}
            try:
                t1 = time.monotonic()
                r = await c.post(f"{n.url}/api/chat", json={
                    "model": n.default_model,
                    "messages": [{"role": "user", "content": TEST_PROMPT}],
                    "stream": False, "think": False,
                    "options": {"temperature": 0.3, "num_predict": 512},
                })
                r.raise_for_status()
                latency = int((time.monotonic() - t1) * 1000)
                content = r.json()["message"]["content"]
                content = _strip_thinking_tags(content)
                test.update({
                    "status": "OK", "latency_ms": latency,
                    "output_len": len(content), "preview": content[:100],
                })
                ok_count += 1
                _print(f"  [OK] {n.name} -- {latency}ms -- {len(content)} chars")
            except Exception as e:
                test.update({"status": "ERREUR", "error": str(e)})
                _print(f"  [--] {n.name} -- ERREUR: {e}")
            tests.append(test)

    # Gemini
    test = {"node": "GEMINI", "model": config.gemini_node.default_model}
    try:
        t1 = time.monotonic()
        proc = await asyncio.create_subprocess_exec(
            "node", config.gemini_node.proxy_path, TEST_PROMPT,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
        latency = int((time.monotonic() - t1) * 1000)
        content = _strip_thinking_tags(stdout.decode(errors="replace").strip())
        if proc.returncode != 0 and not content:
            test.update({"status": "ERREUR", "error": f"exit {proc.returncode}"})
            _print(f"  [--] GEMINI -- exit {proc.returncode}")
        else:
            test.update({
                "status": "OK", "latency_ms": latency,
                "output_len": len(content), "preview": content[:100],
            })
            ok_count += 1
            _print(f"  [OK] GEMINI -- {latency}ms -- {len(content)} chars")
    except Exception as e:
        test.update({"status": "ERREUR", "error": str(e)})
        _print(f"  [--] GEMINI -- ERREUR: {e}")
    tests.append(test)

    total = len(tests)
    result.score = ok_count / max(total, 1)
    result.duration_ms = int((time.monotonic() - t0) * 1000)
    result.details = {"tests": tests, "ok": ok_count, "total": total}
    _print(f"  Score: {result.score:.0%} ({ok_count}/{total}) -- {result.duration_ms}ms")
    return result


# ══════════════════════════════════════════════════════════════════════════
# PHASE 3 — CONSENSUS
# ══════════════════════════════════════════════════════════════════════════

async def phase_consensus() -> PhaseResult:
    _print("\n=== PHASE 3: Consensus Testing ===")
    result = PhaseResult(name="3_consensus")
    t0 = time.monotonic()
    tests = []
    ok_count = 0

    configs = [
        ("2-nodes", "M1,OL1"),
        ("3-nodes", "M1,M2,OL1"),
        ("4-nodes", "M1,M2,OL1,GEMINI"),
    ]

    client = httpx.AsyncClient(timeout=120)
    try:
        for label, nodes_str in configs:
            names = nodes_str.split(",")
            test = {"label": label, "nodes": nodes_str}
            t1 = time.monotonic()

            async def _query_node(name: str) -> str:
                upper = name.upper()
                try:
                    if upper == "GEMINI":
                        proc = await asyncio.create_subprocess_exec(
                            "node", config.gemini_node.proxy_path, TEST_PROMPT,
                            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                        )
                        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
                        output = stdout.decode(errors="replace").strip()
                        if proc.returncode != 0 and not output:
                            return f"[{name}] ERREUR (exit {proc.returncode})"
                        return f"[{name}] {_strip_thinking_tags(output)[:200]}"

                    ol_node = config.get_ollama_node(name)
                    if ol_node:
                        r = await client.post(f"{ol_node.url}/api/chat", json={
                            "model": ol_node.default_model,
                            "messages": [{"role": "user", "content": TEST_PROMPT}],
                            "stream": False, "think": False,
                            "options": {"temperature": 0.3, "num_predict": 512},
                        }, timeout=60)
                        r.raise_for_status()
                        return f"[{name}] {_strip_thinking_tags(r.json()['message']['content'])[:200]}"

                    node = config.get_node(name)
                    if not node:
                        return f"[{name}] ERREUR: inconnu"
                    r = await client.post(f"{node.url}/api/v1/chat", json={
                        "model": node.default_model, "input": TEST_PROMPT,
                        "temperature": 0.3, "max_output_tokens": 512,
                        "stream": False, "store": False,
                    }, timeout=60, headers=_lm_headers(node))
                    r.raise_for_status()
                    return f"[{name}] {extract_lms_output(r.json())[:200]}"
                except asyncio.TimeoutError:
                    return f"[{name}] TIMEOUT"
                except Exception as e:
                    return f"[{name}] ERREUR: {e}"

            results_raw = await asyncio.gather(*[_query_node(n) for n in names], return_exceptions=True)
            responses = []
            for r in results_raw:
                responses.append(str(r) if isinstance(r, Exception) else r)

            latency = int((time.monotonic() - t1) * 1000)
            errors = [r for r in responses if "ERREUR" in r or "TIMEOUT" in r]
            empty = [r for r in responses if not r.split("] ", 1)[-1].strip() or "Pas de reponse" in r]
            node_ok = len(responses) - len(errors) - len(empty)

            test.update({
                "latency_ms": latency, "responses_count": len(responses),
                "ok": node_ok, "errors": len(errors), "empty": len(empty),
            })

            if empty:
                result.issues.append({"severity": "critical", "test": label, "detail": f"{len(empty)} reponses vides"})
            if errors:
                result.issues.append({"severity": "warning", "test": label, "detail": f"{len(errors)} erreurs"})

            is_ok = node_ok >= len(names) - 1  # Allow 1 failure
            if is_ok:
                ok_count += 1
            _print(f"  [{'+' if is_ok else '!'}] {label} -- {latency}ms -- {node_ok}/{len(names)} OK")
            tests.append(test)
    finally:
        await client.aclose()

    result.score = ok_count / max(len(configs), 1)
    result.duration_ms = int((time.monotonic() - t0) * 1000)
    result.details = {"tests": tests}
    _print(f"  Score: {result.score:.0%} -- {result.duration_ms}ms")
    return result


# ══════════════════════════════════════════════════════════════════════════
# PHASE 4 — BRIDGE
# ══════════════════════════════════════════════════════════════════════════

async def phase_bridge() -> PhaseResult:
    _print("\n=== PHASE 4: Bridge Routing ===")
    result = PhaseResult(name="4_bridge")
    t0 = time.monotonic()
    tests = []
    ok_count = 0

    task_types = list(config.routing.keys())
    for tt in task_types:
        nodes = config.route(tt)
        test = {"task_type": tt, "expected_nodes": nodes}

        if not nodes:
            test["status"] = "NO_ROUTE"
            result.issues.append({"severity": "warning", "detail": f"Pas de route pour {tt}"})
            tests.append(test)
            continue

        first = nodes[0].upper()
        reachable = False
        try:
            if first == "GEMINI":
                proc = await asyncio.create_subprocess_exec(
                    "node", config.gemini_node.proxy_path, "--ping",
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
                reachable = proc.returncode == 0 or bool(stdout.decode().strip())
            elif config.get_ollama_node(first):
                ol = config.get_ollama_node(first)
                async with httpx.AsyncClient(timeout=3) as c:
                    r = await c.get(f"{ol.url}/api/tags")
                    reachable = r.status_code == 200
            else:
                node = config.get_node(nodes[0])
                if node:
                    async with httpx.AsyncClient(timeout=3) as c:
                        r = await c.get(f"{node.url}/api/v1/models", headers=_lm_headers(node))
                        reachable = r.status_code == 200
        except Exception:
            pass

        test["first_node_reachable"] = reachable
        test["status"] = "OK" if reachable else "UNREACHABLE"
        if reachable:
            ok_count += 1
        _print(f"  [{'OK' if reachable else '--'}] {tt} -> {nodes[0]} ({'reachable' if reachable else 'offline'})")
        tests.append(test)

    # Bridge mesh test
    _print("  Testing bridge_mesh (M1,OL1)...")
    mesh_test = {"type": "bridge_mesh", "nodes": "M1,OL1"}
    try:
        t1 = time.monotonic()
        responses = []
        async with httpx.AsyncClient(timeout=60) as c:
            for name in ["M1", "OL1"]:
                ol = config.get_ollama_node(name)
                if ol:
                    r = await c.post(f"{ol.url}/api/chat", json={
                        "model": ol.default_model,
                        "messages": [{"role": "user", "content": SIMPLE_PROMPT}],
                        "stream": False, "think": False,
                    })
                    r.raise_for_status()
                    responses.append(f"[{name}] OK")
                else:
                    node = config.get_node(name)
                    if node:
                        r = await c.post(f"{node.url}/api/v1/chat", json={
                            "model": node.default_model, "input": SIMPLE_PROMPT,
                            "temperature": 0.3, "max_output_tokens": 64,
                            "stream": False, "store": False,
                        }, headers=_lm_headers(node))
                        r.raise_for_status()
                        responses.append(f"[{name}] OK")
        mesh_latency = int((time.monotonic() - t1) * 1000)
        mesh_test.update({"status": "OK", "latency_ms": mesh_latency, "responses": len(responses)})
        _print(f"  [OK] bridge_mesh -- {mesh_latency}ms -- {len(responses)} reponses")
    except Exception as e:
        mesh_test.update({"status": "ERREUR", "error": str(e)})
        _print(f"  [--] bridge_mesh -- ERREUR: {e}")
    tests.append(mesh_test)

    total = len(task_types) + 1
    result.score = ok_count / max(len(task_types), 1)
    result.duration_ms = int((time.monotonic() - t0) * 1000)
    result.details = {"tests": tests, "task_types_tested": len(task_types)}
    _print(f"  Score: {result.score:.0%} -- {result.duration_ms}ms")
    return result


# ══════════════════════════════════════════════════════════════════════════
# PHASE 5 — AGENTS VALIDATION
# ══════════════════════════════════════════════════════════════════════════

async def phase_agents() -> PhaseResult:
    _print("\n=== PHASE 5: Agent Definitions ===")
    result = PhaseResult(name="5_agents")
    t0 = time.monotonic()
    from src.agents import JARVIS_AGENTS
    from src.mcp_server import TOOL_DEFINITIONS

    mcp_tools = {name for name, _, _, _ in TOOL_DEFINITIONS}
    agents_info = {}
    mismatches = []
    ok_count = 0

    for name, agent in JARVIS_AGENTS.items():
        info = {"model": agent.model, "tools_count": len(agent.tools)}
        missing_tools = []
        for t in agent.tools:
            if t.startswith("mcp__jarvis__"):
                tool_name = t.replace("mcp__jarvis__", "")
                if tool_name not in mcp_tools:
                    missing_tools.append(tool_name)
        info["missing_mcp_tools"] = missing_tools
        if missing_tools:
            mismatches.append({"agent": name, "missing": missing_tools})
            result.issues.append({"severity": "warning", "agent": name, "detail": f"Outils MCP manquants: {missing_tools}"})
            _print(f"  [!!] {name} ({agent.model}) -- {len(agent.tools)} tools -- MANQUANTS: {missing_tools}")
        else:
            ok_count += 1
            _print(f"  [OK] {name} ({agent.model}) -- {len(agent.tools)} tools")
        agents_info[name] = info

    mcp_tool_count = len(TOOL_DEFINITIONS)
    _print(f"  MCP tools: {mcp_tool_count}")

    result.score = ok_count / max(len(JARVIS_AGENTS), 1)
    result.duration_ms = int((time.monotonic() - t0) * 1000)
    result.details = {
        "agents": agents_info, "mismatches": mismatches,
        "mcp_tool_count": mcp_tool_count, "agent_count": len(JARVIS_AGENTS),
    }
    _print(f"  Score: {result.score:.0%} -- {result.duration_ms}ms")
    return result


# ══════════════════════════════════════════════════════════════════════════
# PHASE 6 — STRESS TEST
# ══════════════════════════════════════════════════════════════════════════

async def phase_stress() -> PhaseResult:
    _print("\n=== PHASE 6: Stress Test (10 parallel consensus) ===")
    result = PhaseResult(name="6_stress")
    t0 = time.monotonic()

    async def _single_consensus(idx: int) -> dict:
        t1 = time.monotonic()
        responses = []
        try:
            async with httpx.AsyncClient(timeout=60) as c:
                node = config.get_node("M1")
                if node:
                    r = await c.post(f"{node.url}/api/v1/chat", json={
                        "model": node.default_model, "input": SIMPLE_PROMPT,
                        "temperature": 0.3, "max_output_tokens": 64,
                        "stream": False, "store": False,
                    }, headers=_lm_headers(node))
                    r.raise_for_status()
                    responses.append("M1:OK")
                ol = config.get_ollama_node("OL1")
                if ol:
                    r = await c.post(f"{ol.url}/api/chat", json={
                        "model": ol.default_model,
                        "messages": [{"role": "user", "content": SIMPLE_PROMPT}],
                        "stream": False, "think": False,
                    })
                    r.raise_for_status()
                    responses.append("OL1:OK")
            return {"idx": idx, "status": "OK", "latency_ms": int((time.monotonic() - t1) * 1000), "responses": len(responses)}
        except Exception as e:
            return {"idx": idx, "status": "ERREUR", "latency_ms": int((time.monotonic() - t1) * 1000), "error": str(e)}

    tasks = [_single_consensus(i) for i in range(10)]
    results_raw = await asyncio.gather(*tasks, return_exceptions=True)

    calls = []
    errors = 0
    latencies = []
    for r in results_raw:
        if isinstance(r, Exception):
            calls.append({"status": "EXCEPTION", "error": str(r)})
            errors += 1
        else:
            calls.append(r)
            if r["status"] == "OK":
                latencies.append(r["latency_ms"])
            else:
                errors += 1

    total_ms = int((time.monotonic() - t0) * 1000)
    throughput = len(calls) / (total_ms / 1000) if total_ms > 0 else 0
    avg_latency = int(sum(latencies) / max(len(latencies), 1))

    result.score = (len(calls) - errors) / max(len(calls), 1)
    result.duration_ms = total_ms
    result.details = {
        "calls": len(calls), "ok": len(calls) - errors, "errors": errors,
        "avg_latency_ms": avg_latency,
        "min_latency_ms": min(latencies) if latencies else 0,
        "max_latency_ms": max(latencies) if latencies else 0,
        "throughput_calls_per_sec": round(throughput, 2),
    }
    _print(f"  {len(calls) - errors}/{len(calls)} OK -- avg {avg_latency}ms -- {throughput:.1f} calls/s")
    _print(f"  Score: {result.score:.0%} -- {total_ms}ms")
    return result


# ══════════════════════════════════════════════════════════════════════════
# PHASE 7 — ERROR DETECTION
# ══════════════════════════════════════════════════════════════════════════

async def phase_errors() -> PhaseResult:
    _print("\n=== PHASE 7: Error Detection ===")
    result = PhaseResult(name="7_errors")
    t0 = time.monotonic()
    checks = []
    issues_found = 0

    # Check 1: extract_lms_output with thinking tags
    _print("  [1] extract_lms_output thinking tags...")
    test_data = {"output": [
        {"type": "reasoning", "content": "thinking deeply..."},
        {"type": "message", "content": "<think>internal thoughts</think>La vraie reponse"},
    ]}
    extracted = extract_lms_output(test_data)
    ok = extracted == "La vraie reponse"
    checks.append({"check": "extract_thinking_tags", "pass": ok, "result": extracted[:100]})
    _print(f"  {'[OK]' if ok else '[!!]'} extract_lms_output: '{extracted[:50]}'")
    if not ok:
        issues_found += 1

    # Check 2: extract_lms_output with string output
    test_data2 = {"output": "<think>blah</think>Direct string output"}
    extracted2 = extract_lms_output(test_data2)
    ok2 = extracted2 == "Direct string output"
    checks.append({"check": "extract_string_output", "pass": ok2, "result": extracted2[:100]})
    _print(f"  {'[OK]' if ok2 else '[!!]'} extract string output: '{extracted2[:50]}'")
    if not ok2:
        issues_found += 1

    # Check 3: extract_lms_output OpenAI fallback
    test_data3 = {"choices": [{"message": {"content": "OpenAI format"}}]}
    extracted3 = extract_lms_output(test_data3)
    ok3 = extracted3 == "OpenAI format"
    checks.append({"check": "extract_openai_fallback", "pass": ok3, "result": extracted3[:100]})
    _print(f"  {'[OK]' if ok3 else '[!!]'} extract OpenAI fallback: '{extracted3[:50]}'")
    if not ok3:
        issues_found += 1

    # Check 4: Tool count
    _print("  [4] Tool count consistency...")
    from src.mcp_server import TOOL_DEFINITIONS
    mcp_count = len(TOOL_DEFINITIONS)
    checks.append({"check": "mcp_tool_count", "count": mcp_count})
    _print(f"  [OK] MCP server: {mcp_count} outils")

    # Check 5: Routing integrity
    _print("  [5] Routing integrity...")
    consensus_nodes = config.routing.get("consensus", [])
    ok5 = len(consensus_nodes) >= 3
    checks.append({"check": "routing_consensus", "pass": ok5, "nodes": consensus_nodes})
    _print(f"  {'[OK]' if ok5 else '[!!]'} consensus route: {consensus_nodes}")
    if not ok5:
        issues_found += 1

    # Check 6: No localhost in node URLs
    _print("  [6] localhost check...")
    localhost_found = False
    for n in config.lm_nodes:
        if "localhost" in n.url:
            localhost_found = True
            result.issues.append({"severity": "critical", "detail": f"{n.name} utilise localhost"})
    for n in config.ollama_nodes:
        if "localhost" in n.url:
            localhost_found = True
            result.issues.append({"severity": "critical", "detail": f"{n.name} utilise localhost"})
    checks.append({"check": "no_localhost", "pass": not localhost_found})
    _print(f"  {'[OK]' if not localhost_found else '[!!]'} localhost check")
    if localhost_found:
        issues_found += 1

    # Check 7: Agent tool references
    _print("  [7] Agent tool references...")
    from src.agents import JARVIS_AGENTS
    mcp_tools = {name for name, _, _, _ in TOOL_DEFINITIONS}
    agent_issues = []
    for aname, agent in JARVIS_AGENTS.items():
        for t in agent.tools:
            if t.startswith("mcp__jarvis__"):
                tool_name = t.replace("mcp__jarvis__", "")
                if tool_name not in mcp_tools:
                    agent_issues.append(f"{aname}: {tool_name}")
    ok7 = len(agent_issues) == 0
    checks.append({"check": "agent_tool_refs", "pass": ok7, "issues": agent_issues})
    _print(f"  {'[OK]' if ok7 else '[!!]'} Agent tool refs{': ' + str(agent_issues) if agent_issues else ''}")
    if not ok7:
        issues_found += 1

    # Check 8: commander_routing has consensus key
    _print("  [8] commander_routing consensus...")
    has_consensus = "consensus" in config.commander_routing
    checks.append({"check": "commander_routing_consensus", "pass": has_consensus})
    _print(f"  {'[OK]' if has_consensus else '[!!]'} commander_routing has 'consensus' key")
    if not has_consensus:
        issues_found += 1

    total_checks = len(checks)
    passed = total_checks - issues_found
    result.score = passed / max(total_checks, 1)
    result.duration_ms = int((time.monotonic() - t0) * 1000)
    result.details = {"checks": checks, "passed": passed, "total": total_checks}
    _print(f"  Score: {result.score:.0%} ({passed}/{total_checks}) -- {result.duration_ms}ms")
    return result


# ══════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════

async def run_benchmark(quick: bool = False):
    _print(f"=== JARVIS Cluster Benchmark v{config.version} ===")
    _print(f"Mode: {'QUICK (1,2,5,7)' if quick else 'COMPLET (1-7)'}")
    t0 = time.monotonic()

    report = BenchmarkReport()
    report.timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")

    # Phase 1 -- Health (always)
    p1 = await phase_health()
    report.phases["1_health"] = asdict(p1)
    report.issues.extend(p1.issues)

    # Phase 2 -- Inference (always)
    p2 = await phase_inference()
    report.phases["2_inference"] = asdict(p2)
    report.issues.extend(p2.issues)

    if not quick:
        # Phase 3 -- Consensus
        p3 = await phase_consensus()
        report.phases["3_consensus"] = asdict(p3)
        report.issues.extend(p3.issues)

        # Phase 4 -- Bridge
        p4 = await phase_bridge()
        report.phases["4_bridge"] = asdict(p4)
        report.issues.extend(p4.issues)

    # Phase 5 -- Agents (always)
    p5 = await phase_agents()
    report.phases["5_agents"] = asdict(p5)
    report.issues.extend(p5.issues)

    if not quick:
        # Phase 6 -- Stress
        p6 = await phase_stress()
        report.phases["6_stress"] = asdict(p6)
        report.issues.extend(p6.issues)

    # Phase 7 -- Errors (always)
    p7 = await phase_errors()
    report.phases["7_errors"] = asdict(p7)
    report.issues.extend(p7.issues)

    # Summary
    total_ms = int((time.monotonic() - t0) * 1000)
    report.duration_ms = total_ms
    scores = [p["score"] for p in report.phases.values()]
    avg_score = sum(scores) / max(len(scores), 1)
    critical = [i for i in report.issues if i.get("severity") == "critical"]
    warnings = [i for i in report.issues if i.get("severity") == "warning"]

    report.summary = {
        "phases_run": len(report.phases),
        "avg_score": round(avg_score, 3),
        "critical_issues": len(critical),
        "warnings": len(warnings),
    }

    # Recommendations
    if critical:
        report.recommendations.append(f"CRITIQUE: {len(critical)} problemes critiques a corriger")
    for issue in critical:
        report.recommendations.append(f"  - {issue.get('detail', str(issue))}")

    # Write report
    report_path = Path("data/benchmark_report.json")
    report_path.parent.mkdir(exist_ok=True)
    report_path.write_text(
        json.dumps(asdict(report), indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    _print(f"\n{'='*60}")
    _print(f"BENCHMARK TERMINE -- {total_ms}ms")
    _print(f"Score moyen: {avg_score:.0%}")
    _print(f"Phases: {len(report.phases)} | Critiques: {len(critical)} | Warnings: {len(warnings)}")
    _print(f"Rapport: {report_path.absolute()}")
    _print(f"{'='*60}")


def main():
    quick = "--quick" in sys.argv
    asyncio.run(run_benchmark(quick=quick))


if __name__ == "__main__":
    main()
