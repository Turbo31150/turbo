"""JARVIS Terminal API — WebSocket + REST endpoint for Electron terminal.

Handles command execution from the integrated terminal component.
Routes commands to appropriate cluster nodes or local handlers.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time

import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

logger = logging.getLogger("jarvis.terminal")

router = APIRouter(prefix="/api", tags=["terminal"])


class TerminalCommand(BaseModel):
    command: str


class TerminalResponse(BaseModel):
    output: str = ""
    error: str = ""
    duration_ms: float = 0


# ── Built-in commands ────────────────────────────────────────────────────

BUILTIN_COMMANDS = {}


def builtin(name: str):
    """Register a built-in terminal command."""
    def decorator(func):
        BUILTIN_COMMANDS[name] = func
        return func
    return decorator


@builtin("status")
async def cmd_status() -> str:
    """Cluster status summary."""
    nodes = {"M1": "http://127.0.0.1:1234", "OL1": "http://127.0.0.1:11434"}
    results = []
    async with httpx.AsyncClient(timeout=3) as client:
        for name, url in nodes.items():
            try:
                endpoint = f"{url}/api/v1/models" if "1234" in url else f"{url}/api/tags"
                r = await client.get(endpoint)
                if r.status_code == 200:
                    data = r.json()
                    if "data" in data:
                        loaded = sum(1 for m in data["data"] if m.get("loaded_instances", 0) > 0)
                        results.append(f"  {name}: ONLINE ({loaded} models loaded)")
                    elif "models" in data:
                        results.append(f"  {name}: ONLINE ({len(data['models'])} models)")
                else:
                    results.append(f"  {name}: ERROR (HTTP {r.status_code})")
            except Exception:
                results.append(f"  {name}: OFFLINE")

    return "Cluster Status:\n" + "\n".join(results)


@builtin("gpu")
async def cmd_gpu() -> str:
    """GPU temperatures and VRAM usage."""
    import subprocess
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,temperature.gpu,memory.used,memory.total,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0:
            lines = ["GPU Status:"]
            for line in r.stdout.strip().split("\n"):
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 6:
                    idx, name, temp, mem_used, mem_total, util = parts[:6]
                    lines.append(
                        f"  GPU {idx} ({name}): {temp}°C | "
                        f"VRAM {mem_used}/{mem_total} MB | {util}% util"
                    )
            return "\n".join(lines)
        return "nvidia-smi failed"
    except FileNotFoundError:
        return "nvidia-smi not found"
    except Exception as e:
        return f"GPU query error: {e}"


@builtin("models")
async def cmd_models() -> str:
    """List loaded models."""
    results = ["Loaded Models:"]
    async with httpx.AsyncClient(timeout=3) as client:
        # M1
        try:
            r = await client.get("http://127.0.0.1:1234/api/v1/models")
            data = r.json()
            for m in data.get("data", data.get("models", [])):
                loaded = m.get("loaded_instances", 0)
                if loaded > 0:
                    mid = m.get("id", m.get("model", "unknown"))
                    results.append(f"  M1: {mid} (x{loaded})")
        except Exception:
            results.append("  M1: OFFLINE")

        # OL1
        try:
            r = await client.get("http://127.0.0.1:11434/api/tags")
            for m in r.json().get("models", []):
                results.append(f"  OL1: {m['name']}")
        except Exception:
            results.append("  OL1: OFFLINE")

    return "\n".join(results)


@builtin("security")
async def cmd_security() -> str:
    """Security score and status."""
    try:
        from src.security import calculate_security_score
        score = calculate_security_score()
        lines = [f"Security Score: {score['score']}/100 (Grade {score['grade']})"]
        for key, val in score["details"].items():
            lines.append(f"  {key}: {val}")
        return "\n".join(lines)
    except Exception as e:
        return f"Security check error: {e}"


@builtin("cache")
async def cmd_cache() -> str:
    """Cache statistics."""
    try:
        from src.cache import cluster_cache
        stats = cluster_cache.get_stats()
        lines = [f"Cluster Cache: {stats['size']}/{stats['max_size']} entries"]
        lines.append(f"  Hit rate: {stats['hit_rate']}")
        lines.append(f"  Hits: {stats['hits']} | Misses: {stats['misses']}")
        lines.append(f"  Evictions: {stats['evictions']} | Expirations: {stats['expirations']}")
        if stats.get("by_node"):
            lines.append(f"  By node: {stats['by_node']}")
        return "\n".join(lines)
    except Exception as e:
        return f"Cache error: {e}"


@builtin("signals")
async def cmd_signals() -> str:
    """Pending trading signals."""
    try:
        from src.trading import get_pending_signals
        signals = get_pending_signals(limit=5)
        if not signals:
            return "No pending signals"
        lines = ["Pending Signals:"]
        for s in signals:
            lines.append(
                f"  #{s['id']} {s['symbol']} {s['direction']} "
                f"score={s['score']} price={s.get('price', 'N/A')}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Signals error: {e}"


@builtin("positions")
async def cmd_positions() -> str:
    """Open trading positions."""
    try:
        from src.trading import get_open_positions
        positions = get_open_positions()
        if not positions:
            return "No open positions"
        lines = ["Open Positions:"]
        for p in positions:
            lines.append(
                f"  {p['symbol']} {p['direction']} "
                f"entry={p.get('entry_price', 'N/A')} pnl={p.get('pnl', 0):.4f}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Positions error: {e}"


@builtin("breakers")
async def cmd_breakers() -> str:
    """Circuit breaker status."""
    try:
        from src.circuit_breaker import cluster_breakers
        statuses = cluster_breakers.get_all_status()
        if not statuses:
            return "No circuit breakers registered"
        lines = ["Circuit Breakers:"]
        for s in statuses:
            lines.append(
                f"  {s['node']}: {s['state']} "
                f"(failures={s['consecutive_failures']}, "
                f"tripped={s['times_tripped']}x)"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Breakers error: {e}"


@builtin("metrics")
async def cmd_metrics() -> str:
    """Cluster performance metrics."""
    try:
        from src.metrics import metrics
        stats = metrics.get_node_stats(hours=1)
        if not stats.get("nodes"):
            return "No metrics data (last 1h)"
        lines = [f"Cluster Metrics (last {stats['period_hours']}h):"]
        for node, data in stats["nodes"].items():
            lines.append(
                f"  {node}: {data['calls']} calls, "
                f"avg={data['avg_latency_ms']}ms, "
                f"success={data['success_rate']}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Metrics error: {e}"


@builtin("audit")
async def cmd_audit() -> str:
    """Recent security audit events."""
    try:
        from src.security import audit_log
        events = audit_log.get_recent(10)
        if not events:
            return "No audit events"
        lines = ["Recent Security Events:"]
        for e in events:
            ts = time.strftime("%H:%M:%S", time.localtime(e["timestamp"]))
            lines.append(f"  [{ts}] {e['severity']:7s} {e['event_type']}: {e['details'][:60]}")
        return "\n".join(lines)
    except Exception as e:
        return f"Audit error: {e}"


# ── Phase 3/4 built-in commands ─────────────────────────────────────────


@builtin("observability")
async def cmd_observability() -> str:
    """Observability matrix report."""
    try:
        from src.observability import observability_matrix
        report = observability_matrix.get_report()
        lines = ["Observability Matrix:"]
        nodes = report.get("nodes", {})
        if not nodes:
            lines.append("  No node data recorded yet")
        for name, data in nodes.items():
            calls = data.get("total_calls", 0)
            avg_lat = data.get("avg_latency_ms", 0)
            success = data.get("success_rate", 0)
            lines.append(f"  {name}: {calls} calls, avg={avg_lat:.0f}ms, success={success:.0%}")
        alerts = report.get("alerts", [])
        if alerts:
            lines.append(f"  Alerts: {len(alerts)}")
        return "\n".join(lines)
    except Exception as e:
        return f"Observability error: {e}"


@builtin("drift")
async def cmd_drift() -> str:
    """Drift detection report."""
    try:
        from src.drift_detector import drift_detector
        report = drift_detector.get_report()
        degraded = report.get("degraded_models", [])
        alerts = report.get("alerts", [])
        lines = ["Drift Detection:"]
        lines.append(f"  Degraded models: {', '.join(degraded) if degraded else 'none'}")
        lines.append(f"  Active alerts: {len(alerts)}")
        for a in alerts[:5]:
            lines.append(f"    - {a.get('model', '?')}: {a.get('message', '?')}")
        return "\n".join(lines)
    except Exception as e:
        return f"Drift error: {e}"


@builtin("autotune")
async def cmd_autotune() -> str:
    """Auto-tune scheduler status."""
    try:
        from src.auto_tune import auto_tune
        status = auto_tune.get_status()
        lines = ["Auto-Tune Status:"]
        snap = status.get("resource_snapshot", {})
        lines.append(f"  CPU: {snap.get('cpu_percent', 0):.1f}% | Memory: {snap.get('memory_percent', 0):.1f}%")
        nodes = status.get("node_loads", {})
        for name, load in nodes.items():
            lines.append(f"  {name}: load={load.get('active_requests', 0)}, cooling={load.get('is_cooling', False)}")
        return "\n".join(lines)
    except Exception as e:
        return f"AutoTune error: {e}"


@builtin("dashboard")
async def cmd_dashboard() -> str:
    """Combined cluster dashboard (orchestrator v2)."""
    try:
        from src.orchestrator_v2 import orchestrator_v2
        dash = orchestrator_v2.get_dashboard()
        health = dash.get("health_score", -1)
        lines = [f"Cluster Dashboard (health: {health}/100):"]
        obs = dash.get("observability", {})
        nodes = obs.get("nodes", {})
        if nodes:
            lines.append(f"  Monitored nodes: {len(nodes)}")
        drift = dash.get("drift", {})
        degraded = drift.get("degraded_models", [])
        if degraded:
            lines.append(f"  Degraded: {', '.join(degraded)}")
        else:
            lines.append("  All models healthy")
        tune = dash.get("auto_tune", {})
        snap = tune.get("resource_snapshot", {})
        if snap:
            lines.append(f"  CPU: {snap.get('cpu_percent', 0):.0f}% | Mem: {snap.get('memory_percent', 0):.0f}%")
        return "\n".join(lines)
    except Exception as e:
        return f"Dashboard error: {e}"


@builtin("intent")
async def cmd_intent() -> str:
    """Intent classifier info."""
    try:
        from src.intent_classifier import intent_classifier
        info = intent_classifier.get_info()
        lines = ["Intent Classifier:"]
        lines.append(f"  Intents: {info.get('num_intents', '?')}")
        lines.append(f"  Patterns: {info.get('num_patterns', '?')}")
        lines.append(f"  Default threshold: {info.get('threshold', '?')}")
        return "\n".join(lines)
    except Exception as e:
        return f"Intent error: {e}"


@builtin("help")
async def cmd_help() -> str:
    """List all available terminal commands."""
    lines = ["Available commands:"]
    for name, handler in sorted(BUILTIN_COMMANDS.items()):
        doc = (handler.__doc__ or "").split("\n")[0].strip()
        lines.append(f"  {name:14s} {doc}")
    return "\n".join(lines)


# ── REST endpoint ────────────────────────────────────────────────────────

@router.post("/terminal", response_model=TerminalResponse)
async def execute_terminal_command(cmd: TerminalCommand):
    """Execute a terminal command and return the result."""
    start = time.monotonic()
    command = cmd.command.strip().lower()

    # Check built-in commands
    parts = command.split()
    cmd_name = parts[0] if parts else ""

    handler = BUILTIN_COMMANDS.get(cmd_name)
    if handler:
        try:
            output = await handler()
            duration = (time.monotonic() - start) * 1000
            return TerminalResponse(output=output, duration_ms=round(duration, 1))
        except Exception as e:
            duration = (time.monotonic() - start) * 1000
            return TerminalResponse(error=str(e), duration_ms=round(duration, 1))

    # Unknown command — try sending to cluster as a query
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                "http://127.0.0.1:11434/api/chat",
                json={
                    "model": "qwen3:1.7b",
                    "messages": [{"role": "user", "content": command}],
                    "stream": False,
                    "think": False,
                    "options": {"num_predict": 256},
                },
            )
            if r.status_code == 200:
                content = r.json().get("message", {}).get("content", "")
                duration = (time.monotonic() - start) * 1000
                return TerminalResponse(output=content, duration_ms=round(duration, 1))
    except Exception:
        pass

    duration = (time.monotonic() - start) * 1000
    return TerminalResponse(
        error=f"Unknown command: {cmd_name}. Type 'help' for available commands.",
        duration_ms=round(duration, 1),
    )


# ── WebSocket endpoint for streaming ─────────────────────────────────────

@router.websocket("/terminal/ws")
async def terminal_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time terminal interaction."""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                command = msg.get("command", "").strip()
                if not command:
                    continue

                # Execute command
                cmd_name = command.split()[0].lower()
                handler = BUILTIN_COMMANDS.get(cmd_name)
                if handler:
                    output = await handler()
                    await websocket.send_json({"type": "output", "text": output})
                else:
                    await websocket.send_json({
                        "type": "error",
                        "text": f"Unknown: {cmd_name}. Type 'help'.",
                    })
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "text": "Invalid JSON"})
    except WebSocketDisconnect:
        pass
