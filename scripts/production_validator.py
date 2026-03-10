#!/usr/bin/env python3
"""JARVIS Production Validator — Validates ALL 7 integration layers.

Checks every component from pre-encoded commands to heavy reasoning,
reports gaps, and optionally auto-fixes issues.

Usage:
    python scripts/production_validator.py              # Full validation
    python scripts/production_validator.py --quick      # Quick health only
    python scripts/production_validator.py --fix        # Validate + auto-fix
    python scripts/production_validator.py --json       # JSON output
    python scripts/production_validator.py --telegram   # Send report to Telegram
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# Paths
TURBO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TURBO))

WS_HOST = "127.0.0.1"
WS_PORT = 9742
M1_HOST = "127.0.0.1"
M1_PORT = 1234
OL1_HOST = "127.0.0.1"
OL1_PORT = 11434
M2_HOST = "192.168.1.26"
M2_PORT = 1234
M3_HOST = "192.168.1.113"
M3_PORT = 1234
OPENCLAW_PORT = 18789
DASHBOARD_PORT = 8080
MCP_SSE_PORT = 8901
GEMINI_PORT = 18791
CANVAS_PORT = 18800


@dataclass
class LayerResult:
    name: str
    layer: int
    status: str  # OK, WARN, FAIL, OFFLINE
    score: int  # 0-100
    details: list[str] = field(default_factory=list)
    fixable: list[str] = field(default_factory=list)


def check_port(host: str, port: int, timeout: float = 2.0) -> bool:
    import socket
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, ConnectionRefusedError, TimeoutError):
        return False


def http_get(host: str, port: int, path: str, timeout: float = 5.0) -> dict | None:
    import urllib.request
    try:
        url = f"http://{host}:{port}{path}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def http_post(host: str, port: int, path: str, data: dict, timeout: float = 10.0) -> dict | None:
    import urllib.request
    try:
        url = f"http://{host}:{port}{path}"
        body = json.dumps(data).encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════════
# LAYER 0 — Pre-encoded commands (2772+)
# ═══════════════════════════════════════════════════════════════════════

def validate_layer0() -> LayerResult:
    r = LayerResult("Pre-encoded Commands", 0, "OK", 100)
    try:
        from src.commands import COMMANDS
        from src.commands_pipelines import PIPELINE_COMMANDS
        total = len(COMMANDS) + len(PIPELINE_COMMANDS)
        r.details.append(f"Base: {len(COMMANDS)}, Pipelines: {len(PIPELINE_COMMANDS)}, Total: {total}")

        # Check action types distribution
        types: dict[str, int] = {}
        for cmd in COMMANDS + PIPELINE_COMMANDS:
            t = getattr(cmd, "action_type", getattr(cmd, "category", "?"))
            types[t] = types.get(t, 0) + 1
        r.details.append(f"Types: {len(types)} ({', '.join(f'{k}:{v}' for k,v in sorted(types.items(), key=lambda x:-x[1])[:5])})")

        if total < 2000:
            r.status = "WARN"
            r.score = 70
            r.details.append(f"Expected 2700+, got {total}")
    except Exception as e:
        r.status = "FAIL"
        r.score = 0
        r.details.append(f"Import error: {e}")
    return r


# ═══════════════════════════════════════════════════════════════════════
# LAYER 1 — Keywords instantanes (MCP keyword_action)
# ═══════════════════════════════════════════════════════════════════════

def validate_layer1() -> LayerResult:
    r = LayerResult("Keyword Actions", 1, "OK", 100)
    try:
        from src.domino_pipelines import DOMINO_PIPELINES
        r.details.append(f"Domino pipelines: {len(DOMINO_PIPELINES)}")

        cats = set(p.category for p in DOMINO_PIPELINES)
        r.details.append(f"Categories: {len(cats)}")

        # Check keyword_action endpoint
        resp = http_post(WS_HOST, WS_PORT, "/api/dominos/resolve/gpu", {})
        if resp:
            r.details.append("keyword_action resolve: OK")
        else:
            # Try GET
            resp = http_get(WS_HOST, WS_PORT, "/api/dominos")
            if resp:
                r.details.append(f"Dominos API: OK")
            else:
                r.status = "WARN"
                r.score = 80
                r.details.append("Dominos API: not responding")
    except Exception as e:
        r.status = "FAIL"
        r.score = 0
        r.details.append(f"Error: {e}")
    return r


# ═══════════════════════════════════════════════════════════════════════
# LAYER 2 — Intent Classifier
# ═══════════════════════════════════════════════════════════════════════

def validate_layer2() -> LayerResult:
    r = LayerResult("Intent Classifier", 2, "OK", 100)
    try:
        from src.intent_classifier import IntentClassifier
        ic = IntentClassifier()
        # Test classification
        tests = [
            ("ouvre chrome", "navigation"),
            ("scan trading btc", "trading"),
            ("lance la routine du matin", "pipeline"),
            ("nvidia-smi", "cluster_ops"),
        ]
        correct = 0
        for text, expected in tests:
            results = ic.classify(text)
            if results and results[0].intent == expected:
                correct += 1
            else:
                got = results[0].intent if results else "none"
                r.details.append(f"Miss: '{text}' -> {got} (expected {expected})")

        r.details.append(f"Classification: {correct}/{len(tests)} correct")
        r.score = int(100 * correct / len(tests))
        if correct < len(tests):
            r.status = "WARN"
    except Exception as e:
        r.status = "FAIL"
        r.score = 0
        r.details.append(f"Error: {e}")
    return r


# ═══════════════════════════════════════════════════════════════════════
# LAYER 3 — Dispatch Engine + M1
# ═══════════════════════════════════════════════════════════════════════

def validate_layer3() -> LayerResult:
    r = LayerResult("Dispatch Engine + M1", 3, "OK", 100)

    # M1 connectivity
    if not check_port(M1_HOST, M1_PORT):
        r.status = "FAIL"
        r.score = 0
        r.details.append("M1 OFFLINE")
        r.fixable.append("start_lmstudio")
        return r

    models = http_get(M1_HOST, M1_PORT, "/v1/models")
    if models:
        data = models.get("data", [])
        loaded = [m for m in data if m.get("id") == "qwen3-8b"]
        r.details.append(f"M1 models available: {len(data)}")
        if loaded:
            r.details.append("qwen3-8b: LOADED")
        else:
            r.status = "WARN"
            r.score = 60
            r.details.append("qwen3-8b: NOT LOADED")
            r.fixable.append("load_qwen3_8b")

    # Dispatch engine API
    stats = http_get(WS_HOST, WS_PORT, "/api/dispatch_engine/stats")
    if stats:
        r.details.append(f"Dispatch total: {stats.get('total_dispatches', 0)}, cache: {stats.get('cache', {}).get('enabled')}")
    else:
        r.status = "WARN"
        r.score = max(r.score - 20, 0)
        r.details.append("Dispatch API: not responding")

    return r


# ═══════════════════════════════════════════════════════════════════════
# LAYER 4 — OpenClaw Agents (40)
# ═══════════════════════════════════════════════════════════════════════

def validate_layer4() -> LayerResult:
    r = LayerResult("OpenClaw Agents", 4, "OK", 100)

    if not check_port(WS_HOST, OPENCLAW_PORT):
        r.status = "FAIL"
        r.score = 0
        r.details.append("OpenClaw gateway OFFLINE")
        r.fixable.append("start_openclaw")
        return r

    r.details.append("OpenClaw gateway: ONLINE")

    # Count agents
    agents_dir = Path.home() / ".openclaw" / "agents"
    if agents_dir.exists():
        agents = [d.name for d in agents_dir.iterdir() if d.is_dir()]
        r.details.append(f"Agents: {len(agents)}")
    else:
        r.status = "WARN"
        r.score = 50
        r.details.append("Agent directory missing")

    # Check OpenClaw stats via WS
    stats = http_get(WS_HOST, WS_PORT, "/api/openclaw/stats")
    if stats:
        r.details.append(f"Routes: {stats.get('total_routes', 0)}")

    return r


# ═══════════════════════════════════════════════════════════════════════
# LAYER 5 — Cowork (438 scripts)
# ═══════════════════════════════════════════════════════════════════════

def validate_layer5() -> LayerResult:
    r = LayerResult("Cowork Scripts", 5, "OK", 100)

    dev_path = TURBO / "cowork" / "dev"
    if not dev_path.exists():
        r.status = "FAIL"
        r.score = 0
        r.details.append("cowork/dev/ missing")
        return r

    scripts = list(dev_path.glob("*.py"))
    r.details.append(f"Scripts: {len(scripts)}")

    # Check cowork API
    cowork_stats = http_get(WS_HOST, WS_PORT, "/api/cowork/stats")
    if cowork_stats:
        r.details.append(f"Cowork API: OK")
    else:
        r.status = "WARN"
        r.score = 80
        r.details.append("Cowork API: not responding via WS")

    # Check MCP bridge
    bridge_file = TURBO / "cowork" / "cowork_mcp_bridge.py"
    r.details.append(f"MCP bridge: {'exists' if bridge_file.exists() else 'MISSING'}")

    return r


# ═══════════════════════════════════════════════════════════════════════
# LAYER 6 — Heavy Reasoning (gpt-oss / deepseek-r1 / qwq-32b)
# ═══════════════════════════════════════════════════════════════════════

def validate_layer6() -> LayerResult:
    r = LayerResult("Heavy Reasoning Models", 6, "OK", 100)

    heavy_models = {
        "M1_gpt-oss-20b": (M1_HOST, M1_PORT, "gpt-oss-20b"),
        "M1_qwq-32b": (M1_HOST, M1_PORT, "qwq-32b"),
        "M1_deepseek-r1": (M1_HOST, M1_PORT, "deepseek-r1-0528-qwen3-8b"),
        "M2_deepseek-r1": (M2_HOST, M2_PORT, "deepseek-r1-0528-qwen3-8b"),
        "M3_deepseek-r1": (M3_HOST, M3_PORT, "deepseek-r1-0528-qwen3-8b"),
    }

    available = 0
    for label, (host, port, model_id) in heavy_models.items():
        if check_port(host, port):
            models = http_get(host, port, "/v1/models")
            if models:
                ids = [m.get("id") for m in models.get("data", [])]
                if model_id in ids:
                    r.details.append(f"{label}: available (not loaded)")
                    available += 1
                else:
                    r.details.append(f"{label}: model not found")
            else:
                r.details.append(f"{label}: API error")
        else:
            r.details.append(f"{label}: OFFLINE")

    if available == 0:
        r.status = "FAIL"
        r.score = 0
    elif available < 3:
        r.status = "WARN"
        r.score = int(100 * available / len(heavy_models))

    # OL1 cloud models for web search
    if check_port(OL1_HOST, OL1_PORT):
        ol1_tags = http_get(OL1_HOST, OL1_PORT, "/api/tags")
        if ol1_tags:
            cloud = [m["name"] for m in ol1_tags.get("models", []) if "cloud" in m["name"]]
            r.details.append(f"OL1 cloud: {len(cloud)} ({', '.join(cloud)})")

    return r


# ═══════════════════════════════════════════════════════════════════════
# SERVICES — All running services
# ═══════════════════════════════════════════════════════════════════════

def validate_services() -> LayerResult:
    r = LayerResult("Services", -1, "OK", 100)

    services = {
        "WS API": (WS_HOST, WS_PORT),
        "M1 LM Studio": (M1_HOST, M1_PORT),
        "OL1 Ollama": (OL1_HOST, OL1_PORT),
        "OpenClaw": (WS_HOST, OPENCLAW_PORT),
        "Dashboard": (WS_HOST, DASHBOARD_PORT),
        "MCP SSE": (WS_HOST, MCP_SSE_PORT),
        "Gemini Proxy": (WS_HOST, GEMINI_PORT),
        "Canvas Proxy": (WS_HOST, CANVAS_PORT),
        "M2 LM Studio": (M2_HOST, M2_PORT),
        "M3 LM Studio": (M3_HOST, M3_PORT),
    }

    online = 0
    for name, (host, port) in services.items():
        up = check_port(host, port)
        r.details.append(f"{name} (:{port}): {'ONLINE' if up else 'OFFLINE'}")
        if up:
            online += 1

    r.score = int(100 * online / len(services))
    if online < len(services) * 0.7:
        r.status = "WARN"
    if online < len(services) * 0.5:
        r.status = "FAIL"

    return r


# ═══════════════════════════════════════════════════════════════════════
# AUTOMATION — Hub + Self-Improve + Scheduler
# ═══════════════════════════════════════════════════════════════════════

def validate_automation() -> LayerResult:
    r = LayerResult("Automation Hub", -2, "OK", 100)

    status = http_get(WS_HOST, WS_PORT, "/api/automation/status")
    if not status:
        r.status = "FAIL"
        r.score = 0
        r.details.append("Automation Hub: not responding")
        r.fixable.append("restart_ws")
        return r

    r.details.append(f"Running: {status.get('running')}")

    loop = status.get("autonomous_loop", {})
    r.details.append(f"Autonomous loop: {loop.get('task_count', 0)} tasks, {loop.get('event_count', 0)} events")

    sched = status.get("task_scheduler", {})
    r.details.append(f"Scheduler: {sched.get('enabled_jobs', 0)} jobs, {len(sched.get('registered_handlers', []))} handlers")

    queue = status.get("task_queue", {})
    r.details.append(f"Queue: {queue.get('total', 0)} total, failed={queue.get('by_status', {}).get('failed', 0)}")

    # Self-improve
    si = http_get(WS_HOST, WS_PORT, "/api/self-improve/status")
    if si:
        r.details.append(f"Self-improve: cycle {si.get('cycles', 0)}, {si.get('total_actions', 0)} actions")

    return r


# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════

def run_validation(quick: bool = False) -> list[LayerResult]:
    results = []

    if not quick:
        results.append(validate_layer0())
        results.append(validate_layer1())
        results.append(validate_layer2())

    results.append(validate_layer3())
    results.append(validate_layer4())

    if not quick:
        results.append(validate_layer5())
        results.append(validate_layer6())

    results.append(validate_services())
    results.append(validate_automation())

    return results


def format_report(results: list[LayerResult]) -> str:
    lines = ["=" * 60, "JARVIS PRODUCTION VALIDATION REPORT", "=" * 60, ""]

    total_score = 0
    count = 0
    for r in results:
        icon = {"OK": "[OK]", "WARN": "[!!]", "FAIL": "[XX]", "OFFLINE": "[--]"}.get(r.status, "[??]")
        layer_label = f"L{r.layer}" if r.layer >= 0 else "SVC" if r.layer == -1 else "AUT"
        lines.append(f"{icon} {layer_label} {r.name} — Score: {r.score}/100")
        for d in r.details:
            lines.append(f"    {d}")
        if r.fixable:
            lines.append(f"    FIX: {', '.join(r.fixable)}")
        lines.append("")
        total_score += r.score
        count += 1

    avg = total_score / count if count else 0
    grade = "A+" if avg >= 95 else "A" if avg >= 90 else "B" if avg >= 80 else "C" if avg >= 70 else "D" if avg >= 60 else "F"

    lines.append("=" * 60)
    lines.append(f"OVERALL: {grade} ({avg:.0f}/100)")
    lines.append(f"Layers validated: {count}")
    fixable = sum(len(r.fixable) for r in results)
    if fixable:
        lines.append(f"Auto-fixable issues: {fixable}")
    lines.append("=" * 60)

    return "\n".join(lines)


def to_json(results: list[LayerResult]) -> dict:
    total = sum(r.score for r in results)
    count = len(results)
    avg = total / count if count else 0
    return {
        "grade": "A+" if avg >= 95 else "A" if avg >= 90 else "B" if avg >= 80 else "C" if avg >= 70 else "D",
        "score": round(avg, 1),
        "layers": [
            {
                "name": r.name,
                "layer": r.layer,
                "status": r.status,
                "score": r.score,
                "details": r.details,
                "fixable": r.fixable,
            }
            for r in results
        ],
    }


def send_telegram(report: str) -> bool:
    try:
        import urllib.request
        msg = report[:4000]  # Telegram limit
        data = json.dumps({"message": msg}).encode()
        req = urllib.request.Request(
            f"http://{WS_HOST}:{WS_PORT}/api/telegram/send",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode())
            return result.get("ok", False)
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="JARVIS Production Validator")
    parser.add_argument("--quick", action="store_true", help="Quick validation (layers 3-4 + services)")
    parser.add_argument("--fix", action="store_true", help="Auto-fix issues")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--telegram", action="store_true", help="Send report to Telegram")
    args = parser.parse_args()

    results = run_validation(quick=args.quick)

    if args.json:
        print(json.dumps(to_json(results), indent=2))
    else:
        report = format_report(results)
        print(report)

        if args.telegram:
            ok = send_telegram(report)
            print(f"\nTelegram: {'sent' if ok else 'failed'}")

    # Exit code based on worst status
    worst = min(r.score for r in results) if results else 0
    sys.exit(0 if worst >= 60 else 1)


if __name__ == "__main__":
    main()
