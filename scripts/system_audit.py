"""JARVIS System Audit — Full cluster health, security, and readiness analysis.

Scans all cluster nodes (M1/M2/M3/OL1/GEMINI), local GPUs, system resources,
network ports, persistence, and produces a scored report.

Usage:
    uv run python scripts/system_audit.py           # Full report + auto-save
    uv run python scripts/system_audit.py --json     # JSON output only
    uv run python scripts/system_audit.py --quick    # Skip slow checks (M1)
    uv run python scripts/system_audit.py --save     # Force save to data/
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import config, JARVIS_VERSION

# ── Constants ────────────────────────────────────────────────────────────────

AUDIT_TIMEOUT = 5.0      # seconds per node check
GEMINI_TIMEOUT = 45.0    # Gemini proxy ~30-40s via API (cold start)

KNOWN_PORTS = {
    "127.0.0.1": [1234, 11434, 8080, 9742, 5678],
    "192.168.1.26": [1234],
    "192.168.1.113": [1234],
    "10.5.0.2": [1234],
}

DATA_DIR = Path("F:/BUREAU/turbo/data")
PROJECT_ROOT = Path("F:/BUREAU/turbo")


# ═══════════════════════════════════════════════════════════════════════════════
# TASK 1: Core data collection — Node health checks
# ═══════════════════════════════════════════════════════════════════════════════

async def check_lm_node(node) -> dict:
    """Check an LM Studio node health via GET /api/v1/models.

    Args:
        node: LMStudioNode instance with .name, .url, .role, .auth_headers

    Returns:
        dict with: name, url, role, status, latency_ms, error, models
    """
    import httpx

    result = {
        "name": node.name,
        "url": node.url,
        "role": node.role,
        "status": "OFFLINE",
        "latency_ms": 0,
        "error": None,
        "models": [],
    }

    try:
        t0 = time.monotonic()
        async with httpx.AsyncClient(timeout=AUDIT_TIMEOUT) as client:
            resp = await client.get(
                f"{node.url}/api/v1/models",
                headers=node.auth_headers,
            )
            latency = (time.monotonic() - t0) * 1000
            result["latency_ms"] = round(latency, 1)

            if resp.status_code == 200:
                data = resp.json()
                models_list = data.get("data", data.get("models", []))
                loaded = []
                for m in models_list:
                    info = {
                        "id": m.get("key", m.get("id", "unknown")),
                        "loaded": bool(m.get("loaded_instances")),
                    }
                    loaded.append(info)
                result["models"] = loaded
                result["status"] = "ONLINE"
            else:
                result["status"] = "OFFLINE"
                result["error"] = f"HTTP {resp.status_code}"
    except httpx.TimeoutException:
        result["status"] = "TIMEOUT"
        result["error"] = f"Timeout after {AUDIT_TIMEOUT}s"
    except Exception as e:
        result["status"] = "OFFLINE"
        result["error"] = str(e)

    return result


async def check_ollama(node) -> dict:
    """Check an Ollama node health via GET /api/tags.

    Args:
        node: OllamaNode instance with .name, .url, .role

    Returns:
        dict with: name, url, role, status, latency_ms, error, models
    """
    import httpx

    result = {
        "name": node.name,
        "url": node.url,
        "role": node.role,
        "status": "OFFLINE",
        "latency_ms": 0,
        "error": None,
        "models": [],
    }

    try:
        t0 = time.monotonic()
        async with httpx.AsyncClient(timeout=AUDIT_TIMEOUT) as client:
            resp = await client.get(f"{node.url}/api/tags")
            latency = (time.monotonic() - t0) * 1000
            result["latency_ms"] = round(latency, 1)

            if resp.status_code == 200:
                data = resp.json()
                models_list = data.get("models", [])
                result["models"] = [
                    {"name": m.get("name", "unknown"), "size": m.get("size", 0)}
                    for m in models_list
                ]
                result["status"] = "ONLINE"
            else:
                result["status"] = "OFFLINE"
                result["error"] = f"HTTP {resp.status_code}"
    except httpx.TimeoutException:
        result["status"] = "TIMEOUT"
        result["error"] = f"Timeout after {AUDIT_TIMEOUT}s"
    except Exception as e:
        result["status"] = "OFFLINE"
        result["error"] = str(e)

    return result


async def check_gemini(gemini_node) -> dict:
    """Check Gemini proxy health via subprocess 'node gemini-proxy.js ping'.

    Args:
        gemini_node: GeminiNode instance with .name, .proxy_path, .role

    Returns:
        dict with: name, proxy_path, role, status, latency_ms, error, models
    """
    result = {
        "name": gemini_node.name,
        "proxy_path": gemini_node.proxy_path,
        "role": gemini_node.role,
        "status": "OFFLINE",
        "latency_ms": 0,
        "error": None,
        "models": gemini_node.models if hasattr(gemini_node, "models") else [],
    }

    proxy_path = Path(gemini_node.proxy_path)
    if not proxy_path.exists():
        result["error"] = f"Proxy not found: {gemini_node.proxy_path}"
        return result

    try:
        t0 = time.monotonic()
        proc = await asyncio.create_subprocess_exec(
            "node", str(proxy_path), "ping",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=GEMINI_TIMEOUT
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            result["status"] = "TIMEOUT"
            result["error"] = f"Timeout after {GEMINI_TIMEOUT}s"
            return result

        latency = (time.monotonic() - t0) * 1000
        result["latency_ms"] = round(latency, 1)

        if proc.returncode == 0:
            result["status"] = "ONLINE"
        else:
            result["status"] = "OFFLINE"
            err_text = stderr.decode(errors="replace").strip()
            result["error"] = err_text[:200] if err_text else f"Exit code {proc.returncode}"
    except FileNotFoundError:
        result["error"] = "node not found in PATH"
    except Exception as e:
        result["error"] = str(e)

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# TASK 2: System info collection — GPU, OS, ports
# ═══════════════════════════════════════════════════════════════════════════════

async def check_gpu_local() -> list[dict]:
    """Query local GPUs via nvidia-smi.

    Returns:
        List of dicts with: index, name, temperature, memory_used_mb,
        memory_total_mb, utilization_percent
    """
    gpus = []
    try:
        proc = await asyncio.create_subprocess_exec(
            "nvidia-smi",
            "--query-gpu=index,name,temperature.gpu,memory.used,memory.total,utilization.gpu",
            "--format=csv,noheader,nounits",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=AUDIT_TIMEOUT)

        if proc.returncode == 0:
            for line in stdout.decode().strip().split("\n"):
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 6:
                    gpus.append({
                        "index": int(parts[0]),
                        "name": parts[1],
                        "temperature": int(parts[2]),
                        "memory_used_mb": int(parts[3]),
                        "memory_total_mb": int(parts[4]),
                        "utilization_percent": int(parts[5]),
                    })
    except asyncio.TimeoutError:
        pass
    except FileNotFoundError:
        pass  # nvidia-smi not available
    except Exception:
        pass

    return gpus


async def check_system_info() -> dict:
    """Collect OS and disk info via PowerShell.

    Returns:
        dict with: os_version, ram_total_gb, ram_free_gb, disks
    """
    result = {
        "os_version": "unknown",
        "ram_total_gb": 0,
        "ram_free_gb": 0,
        "disks": [],
    }

    ps_script = (
        "Get-CimInstance Win32_OperatingSystem | "
        "ForEach-Object { "
        "  $r = @{ Caption=$_.Caption; TotalVisibleMemorySize=$_.TotalVisibleMemorySize; FreePhysicalMemory=$_.FreePhysicalMemory }; "
        "  $r | ConvertTo-Json -Compress "
        "}; "
        "Write-Host '---DISKS---'; "
        "Get-PSDrive -PSProvider FileSystem | "
        "ForEach-Object { "
        "  @{ Name=$_.Name; UsedGB=[math]::Round($_.Used/1GB,1); FreeGB=[math]::Round($_.Free/1GB,1) } | ConvertTo-Json -Compress "
        "}"
    )

    try:
        proc = await asyncio.create_subprocess_exec(
            "powershell", "-NoProfile", "-Command", ps_script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=AUDIT_TIMEOUT)

        if proc.returncode == 0:
            output = stdout.decode(errors="replace")
            parts = output.split("---DISKS---")

            # Parse OS info
            if len(parts) >= 1:
                os_line = parts[0].strip()
                if os_line:
                    try:
                        os_data = json.loads(os_line)
                        result["os_version"] = os_data.get("Caption", "unknown")
                        total_kb = os_data.get("TotalVisibleMemorySize", 0)
                        free_kb = os_data.get("FreePhysicalMemory", 0)
                        result["ram_total_gb"] = round(total_kb / 1048576, 1)
                        result["ram_free_gb"] = round(free_kb / 1048576, 1)
                    except json.JSONDecodeError:
                        pass

            # Parse disk info
            if len(parts) >= 2:
                disk_lines = parts[1].strip()
                for line in disk_lines.split("\n"):
                    line = line.strip()
                    if line.startswith("{"):
                        try:
                            disk = json.loads(line)
                            result["disks"].append({
                                "name": disk.get("Name", "?"),
                                "used_gb": disk.get("UsedGB", 0),
                                "free_gb": disk.get("FreeGB", 0),
                            })
                        except json.JSONDecodeError:
                            pass
    except asyncio.TimeoutError:
        result["error"] = "PowerShell timeout"
    except Exception as e:
        result["error"] = str(e)

    return result


async def check_ports() -> dict:
    """Scan known ports for open connections.

    Returns:
        dict of host -> list of {port, open}
    """
    results = {}

    async def _check_one(host: str, port: int) -> dict:
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=2.0,
            )
            writer.close()
            await writer.wait_closed()
            return {"port": port, "open": True}
        except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
            return {"port": port, "open": False}

    tasks = []
    host_port_pairs = []
    for host, ports in KNOWN_PORTS.items():
        for port in ports:
            tasks.append(_check_one(host, port))
            host_port_pairs.append((host, port))

    scan_results = await asyncio.gather(*tasks)

    for (host, _), scan in zip(host_port_pairs, scan_results):
        if host not in results:
            results[host] = []
        results[host].append(scan)

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# TASK 3: Analysis layer — SPOF, security, scores, run_audit
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_spof(nodes: list[dict]) -> list[dict]:
    """Detect Single Points of Failure in the cluster.

    Checks:
    - Single LM Studio node online
    - GEMINI as single proxy (no redundancy)
    - M1 sole embedding provider
    - OL1 sole web search provider
    - Master (localhost) as sole orchestrator

    Returns:
        List of SPOF dicts with: component, risk, severity (high/medium/low), mitigation
    """
    spofs = []

    # Count online LM nodes
    lm_online = [n for n in nodes if n.get("url") and n["status"] == "ONLINE"]
    if len(lm_online) <= 1:
        spofs.append({
            "component": "LM Studio Cluster",
            "risk": f"Only {len(lm_online)} LM node(s) online — single point of failure for inference",
            "severity": "high",
            "mitigation": "Ensure M2 (champion) + M3 (fallback) are both running",
        })

    # GEMINI single proxy
    gemini_nodes = [n for n in nodes if n["name"] == "GEMINI"]
    if gemini_nodes:
        spofs.append({
            "component": "GEMINI Proxy",
            "risk": "Single proxy instance (gemini-proxy.js) — no redundancy",
            "severity": "medium",
            "mitigation": "Consider a secondary proxy or direct API fallback",
        })

    # M1 sole embedding
    embedding_routes = config.routing.get("embedding", [])
    if embedding_routes == ["M1"]:
        m1_status = next((n["status"] for n in nodes if n["name"] == "M1"), "OFFLINE")
        spofs.append({
            "component": "Embedding (M1)",
            "risk": f"M1 is sole embedding provider (status: {m1_status}) — no fallback",
            "severity": "high" if m1_status != "ONLINE" else "medium",
            "mitigation": "Add OL1 nomic or M2 as embedding fallback",
        })

    # OL1 sole web search
    web_routes = config.routing.get("web_research", [])
    if web_routes == ["OL1"]:
        ol1_status = next((n["status"] for n in nodes if n["name"] == "OL1"), "OFFLINE")
        spofs.append({
            "component": "Web Search (OL1)",
            "risk": f"OL1 is sole web search provider (status: {ol1_status})",
            "severity": "medium",
            "mitigation": "Add GEMINI as web search fallback",
        })

    # Master orchestrator (localhost)
    spofs.append({
        "component": "Master Orchestrator",
        "risk": "Single localhost orchestrator — no HA/failover",
        "severity": "low",
        "mitigation": "Acceptable for development; consider distributed orchestration for production",
    })

    return spofs


def analyze_security(nodes: list[dict], ports: dict) -> list[dict]:
    """Analyze security posture.

    Checks:
    - Exposed ports on non-localhost interfaces
    - API keys hardcoded in config (not from env)

    Returns:
        List of security issue dicts with: issue, severity, details
    """
    import os

    issues = []

    # Check exposed ports on non-localhost
    for host, port_list in ports.items():
        if host == "127.0.0.1":
            continue
        open_ports = [p for p in port_list if p["open"]]
        if open_ports:
            port_nums = [str(p["port"]) for p in open_ports]
            issues.append({
                "issue": f"Exposed ports on {host}",
                "severity": "medium",
                "details": f"Open ports: {', '.join(port_nums)} — accessible on LAN",
            })

    # Check API key hardcoding
    for node in config.lm_nodes:
        if node.api_key:
            env_key = os.getenv(f"LM_STUDIO_{node.name[1:]}_KEY")
            if not env_key or node.api_key == env_key:
                # Key came from hardcoded default, not a separate env override
                issues.append({
                    "issue": f"API key for {node.name} uses hardcoded default",
                    "severity": "low",
                    "details": "Key is in config.py default — prefer LM_STUDIO_*_KEY env var",
                })

    # Check if any LM nodes lack auth
    for node in config.lm_nodes:
        if not node.api_key:
            issues.append({
                "issue": f"No API key for {node.name}",
                "severity": "low",
                "details": f"{node.name} at {node.url} accepts unauthenticated requests",
            })

    return issues


def analyze_persistence() -> dict:
    """Check critical data paths exist and are healthy.

    Returns:
        dict with: paths checked and their status
    """
    checks = {
        "data/": DATA_DIR,
        "LMSTUDIO_BACKUP/": Path("F:/BUREAU/LMSTUDIO_BACKUP"),
        "etoile.db": DATA_DIR / "etoile.db",
        "jarvis.db": DATA_DIR / "jarvis.db",
        "logs/": PROJECT_ROOT / "logs",
    }

    result = {}
    for label, path in checks.items():
        exists = path.exists()
        size = 0
        if exists and path.is_file():
            size = path.stat().st_size
        result[label] = {
            "path": str(path),
            "exists": exists,
            "size_bytes": size,
        }

    return result


def compute_scores(
    nodes: list[dict],
    gpus: list[dict],
    ports: dict,
    persistence: dict,
) -> dict:
    """Compute 6 readiness scores (0-100).

    Scores:
    - stability: Node uptime + latency quality
    - resilience: Redundancy + fallback paths
    - security: Auth + exposure posture
    - scalability: GPU count + VRAM headroom
    - multimodal: Coverage of capabilities (code, web, vision, embedding)
    - observability: Logging, metrics, persistence
    """
    scores = {}

    # ── Stability (node uptime + latency) ─────────────────────────────────
    total_nodes = len(nodes)
    online_nodes = sum(1 for n in nodes if n["status"] == "ONLINE")
    avg_latency = 0
    online_latencies = [n["latency_ms"] for n in nodes if n["status"] == "ONLINE" and n["latency_ms"] > 0]
    if online_latencies:
        avg_latency = sum(online_latencies) / len(online_latencies)

    uptime_score = (online_nodes / max(total_nodes, 1)) * 70
    latency_score = max(0, 30 - (avg_latency / 100))  # penalty for high latency
    scores["stability"] = min(100, round(uptime_score + latency_score))

    # ── Resilience (redundancy + fallback) ────────────────────────────────
    lm_online = sum(1 for n in nodes if n.get("url") and n["status"] == "ONLINE")
    ollama_online = sum(1 for n in nodes if n["name"].startswith("OL") and n["status"] == "ONLINE")
    gemini_ok = any(n["name"] == "GEMINI" and n["status"] == "ONLINE" for n in nodes)

    resilience = 0
    resilience += min(40, lm_online * 15)  # up to 40 for LM nodes
    resilience += 20 if ollama_online > 0 else 0
    resilience += 20 if gemini_ok else 0
    # Bonus for diverse routing
    routing_types = len(config.routing)
    resilience += min(20, routing_types * 2)
    scores["resilience"] = min(100, round(resilience))

    # ── Security ──────────────────────────────────────────────────────────
    sec_score = 80  # start optimistic
    for host, port_list in ports.items():
        if host != "127.0.0.1":
            open_count = sum(1 for p in port_list if p["open"])
            sec_score -= open_count * 10
    # Penalize missing auth
    for node in config.lm_nodes:
        if not node.api_key:
            sec_score -= 5
    scores["security"] = max(0, min(100, round(sec_score)))

    # ── Scalability (GPU + VRAM) ──────────────────────────────────────────
    gpu_count = len(gpus)
    total_vram_mb = sum(g["memory_total_mb"] for g in gpus) if gpus else 0
    total_vram_gb = total_vram_mb / 1024

    scale = 0
    scale += min(40, gpu_count * 8)  # up to 40 for 5 GPUs
    scale += min(40, total_vram_gb * 1.2)  # up to 40 for ~33GB VRAM
    # Bonus for cluster breadth (different machines)
    unique_hosts = set()
    for n in nodes:
        url = n.get("url", "")
        if "://" in url:
            host = url.split("://")[1].split(":")[0]
            unique_hosts.add(host)
    scale += min(20, len(unique_hosts) * 5)
    scores["scalability"] = min(100, round(scale))

    # ── Multimodal (capability coverage) ──────────────────────────────────
    caps = {
        "code_generation": False,
        "embedding": False,
        "web_research": False,
        "architecture": False,
        "trading_signal": False,
        "voice_correction": False,
    }
    for task_type, node_names in config.routing.items():
        if task_type in caps:
            # Check if at least one routed node is online
            for nn in node_names:
                if any(n["name"] == nn and n["status"] == "ONLINE" for n in nodes):
                    caps[task_type] = True
                    break

    covered = sum(1 for v in caps.values() if v)
    scores["multimodal"] = round((covered / max(len(caps), 1)) * 100)

    # ── Observability (logging, persistence, dashboard) ───────────────────
    obs = 0
    # Check persistence paths
    for label, info in persistence.items():
        if info["exists"]:
            obs += 15
    # Cap at 75 from persistence, add 25 for dashboard port
    obs = min(75, obs)
    localhost_ports = ports.get("127.0.0.1", [])
    dashboard_up = any(p["port"] == 8080 and p["open"] for p in localhost_ports)
    if dashboard_up:
        obs += 25
    scores["observability"] = min(100, round(obs))

    return scores


async def run_audit(quick: bool = False) -> dict:
    """Run the complete system audit.

    Args:
        quick: If True, skip slow nodes (M1) to speed up the audit.

    Returns:
        Complete audit report dict.
    """
    t0 = time.monotonic()

    # ── Collect all data in parallel ──────────────────────────────────────
    tasks = {}

    # Node health checks
    for node in config.lm_nodes:
        if quick and node.name == "M1":
            continue
        tasks[f"lm_{node.name}"] = check_lm_node(node)

    for node in config.ollama_nodes:
        tasks[f"ollama_{node.name}"] = check_ollama(node)

    tasks["gemini"] = check_gemini(config.gemini_node)

    # System checks
    tasks["gpus"] = check_gpu_local()
    tasks["system_info"] = check_system_info()
    tasks["ports"] = check_ports()

    # Run all in parallel
    keys = list(tasks.keys())
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    collected = {}
    for k, r in zip(keys, results):
        if isinstance(r, Exception):
            collected[k] = {"error": str(r)}
        else:
            collected[k] = r

    # ── Unpack results ────────────────────────────────────────────────────
    nodes = []
    for k, v in collected.items():
        if k.startswith("lm_") or k.startswith("ollama_") or k == "gemini":
            if isinstance(v, dict) and "name" in v:
                nodes.append(v)

    # If M1 was skipped, add a placeholder
    if quick:
        m1_node = config.get_node("M1")
        if m1_node:
            nodes.append({
                "name": "M1",
                "url": m1_node.url,
                "role": m1_node.role,
                "status": "SKIPPED",
                "latency_ms": 0,
                "error": "Skipped in quick mode",
                "models": [],
            })

    gpus = collected.get("gpus", [])
    if isinstance(gpus, dict) and "error" in gpus:
        gpus = []
    system_info = collected.get("system_info", {})
    if (not isinstance(system_info, dict)) or ("error" in system_info and "os_version" not in system_info):
        system_info = {"os_version": "unknown", "ram_total_gb": 0, "ram_free_gb": 0, "disks": []}
    ports = collected.get("ports", {})
    if not isinstance(ports, dict):
        ports = {}

    # ── Analysis ──────────────────────────────────────────────────────────
    persistence = analyze_persistence()
    spofs = analyze_spof(nodes)
    security = analyze_security(nodes, ports)
    scores = compute_scores(nodes, gpus, ports, persistence)

    elapsed = round((time.monotonic() - t0) * 1000)

    report = {
        "timestamp": datetime.now().isoformat(),
        "version": JARVIS_VERSION,
        "audit_duration_ms": elapsed,
        "quick_mode": quick,
        "nodes": nodes,
        "gpus": gpus,
        "system_info": system_info,
        "ports": ports,
        "persistence": persistence,
        "spofs": spofs,
        "security": security,
        "scores": scores,
    }

    return report


# ═══════════════════════════════════════════════════════════════════════════════
# TASK 4: Report formatter + CLI
# ═══════════════════════════════════════════════════════════════════════════════

def format_report(report: dict) -> str:
    """Format audit report as a human-readable text document.

    10 sections:
    1. Executive Summary
    2. Architecture Map (ASCII tree)
    3. Node Health Table
    4. Topology
    5. Multimodal Matrix
    6. Risks (SPOFs)
    7. Security
    8. Performance (GPU + latency)
    9. Persistence
    10. Readiness Scores (visual bars)
    """
    lines = []

    def section(title: str, num: int):
        lines.append("")
        lines.append(f"{'=' * 70}")
        lines.append(f"  {num}. {title}")
        lines.append(f"{'=' * 70}")

    # Header
    lines.append(f"JARVIS SYSTEM AUDIT REPORT v{report.get('version', '?')}")
    lines.append(f"Generated: {report.get('timestamp', 'unknown')}")
    lines.append(f"Duration: {report.get('audit_duration_ms', 0)}ms")
    if report.get("quick_mode"):
        lines.append("Mode: QUICK (slow nodes skipped)")
    lines.append("")

    # ── 1. Executive Summary ──────────────────────────────────────────────
    section("EXECUTIVE SUMMARY", 1)
    nodes = report.get("nodes", [])
    online = sum(1 for n in nodes if n["status"] == "ONLINE")
    total = len(nodes)
    gpus = report.get("gpus", [])
    scores = report.get("scores", {})
    avg_score = round(sum(scores.values()) / max(len(scores), 1)) if scores else 0

    lines.append(f"  Cluster: {online}/{total} nodes online")
    lines.append(f"  GPUs: {len(gpus)} detected locally")
    total_vram = sum(g.get("memory_total_mb", 0) for g in gpus)
    lines.append(f"  VRAM: {total_vram / 1024:.1f} GB total")
    lines.append(f"  Average readiness score: {avg_score}/100")
    sys_info = report.get("system_info", {})
    lines.append(f"  OS: {sys_info.get('os_version', 'unknown')}")
    lines.append(f"  RAM: {sys_info.get('ram_total_gb', 0):.1f} GB total, {sys_info.get('ram_free_gb', 0):.1f} GB free")

    # ── 2. Architecture Map ───────────────────────────────────────────────
    section("ARCHITECTURE MAP", 2)
    lines.append("  JARVIS Turbo Cluster")
    lines.append("  |")
    lines.append("  +-- [Master] 127.0.0.1 (Orchestrator)")
    lines.append("  |   +-- Claude SDK (7 agents)")
    lines.append("  |   +-- MCP Server (87 tools)")
    lines.append("  |   +-- Voice Pipeline v2")
    lines.append("  |   +-- Dashboard :8080")
    lines.append("  |   +-- Electron :9742")
    lines.append("  |   +-- n8n :5678")
    lines.append("  |")

    for n in nodes:
        status_icon = "OK" if n["status"] == "ONLINE" else "!!" if n["status"] == "TIMEOUT" else "--"
        url_or_proxy = n.get("url", n.get("proxy_path", "?"))
        model_count = len(n.get("models", []))
        lines.append(f"  +-- [{status_icon}] {n['name']} ({url_or_proxy})")
        lines.append(f"  |   role: {n.get('role', '?')}, models: {model_count}, latency: {n.get('latency_ms', 0):.0f}ms")

    # ── 3. Node Health Table ──────────────────────────────────────────────
    section("NODE HEALTH", 3)
    lines.append(f"  {'Node':<8} {'Status':<10} {'Latency':<12} {'Models':<8} {'Role'}")
    lines.append(f"  {'----':<8} {'------':<10} {'-------':<12} {'------':<8} {'----'}")
    for n in nodes:
        status = n["status"]
        latency = f"{n['latency_ms']:.0f}ms" if n["latency_ms"] > 0 else "---"
        models = str(len(n.get("models", [])))
        lines.append(f"  {n['name']:<8} {status:<10} {latency:<12} {models:<8} {n.get('role', '?')}")
        if n.get("error"):
            lines.append(f"           error: {n['error']}")

    # ── 4. Topology ───────────────────────────────────────────────────────
    section("TOPOLOGY", 4)
    # Group by host
    host_nodes = {}
    for n in nodes:
        url = n.get("url", "")
        if "://" in url:
            host = url.split("://")[1].split(":")[0]
        elif n["name"] == "GEMINI":
            host = "localhost (proxy)"
        else:
            host = "unknown"
        if host not in host_nodes:
            host_nodes[host] = []
        host_nodes[host].append(n["name"])

    for host, names in host_nodes.items():
        lines.append(f"  {host}: {', '.join(names)}")

    # Port scan results
    lines.append("")
    lines.append("  Port scan:")
    for host, port_list in report.get("ports", {}).items():
        open_ports = [p for p in port_list if p["open"]]
        closed_ports = [p for p in port_list if not p["open"]]
        open_str = ", ".join(str(p["port"]) for p in open_ports) if open_ports else "none"
        closed_str = ", ".join(str(p["port"]) for p in closed_ports) if closed_ports else "none"
        lines.append(f"    {host}: open=[{open_str}] closed=[{closed_str}]")

    # ── 5. Multimodal Matrix ──────────────────────────────────────────────
    section("MULTIMODAL MATRIX", 5)
    lines.append(f"  {'Capability':<22} {'Route':<25} {'Status'}")
    lines.append(f"  {'----------':<22} {'-----':<25} {'------'}")

    for task_type, node_names in sorted(config.routing.items()):
        route_str = " -> ".join(node_names)
        # Check if primary is online
        primary = node_names[0] if node_names else "?"
        primary_online = any(
            n["name"] == primary and n["status"] == "ONLINE" for n in nodes
        )
        status = "READY" if primary_online else "DEGRADED"
        lines.append(f"  {task_type:<22} {route_str:<25} {status}")

    # ── 6. Risks (SPOFs) ─────────────────────────────────────────────────
    section("RISKS (SPOF ANALYSIS)", 6)
    spofs = report.get("spofs", [])
    if not spofs:
        lines.append("  No SPOFs detected.")
    else:
        for s in spofs:
            sev_label = {"high": "[!!!]", "medium": "[!! ]", "low": "[!  ]"}.get(
                s["severity"], "[?  ]"
            )
            lines.append(f"  {sev_label} {s['component']}")
            lines.append(f"         Risk: {s['risk']}")
            lines.append(f"         Fix:  {s['mitigation']}")

    # ── 7. Security ───────────────────────────────────────────────────────
    section("SECURITY", 7)
    security = report.get("security", [])
    if not security:
        lines.append("  No security issues detected.")
    else:
        for issue in security:
            sev_label = {"high": "[!!!]", "medium": "[!! ]", "low": "[!  ]"}.get(
                issue["severity"], "[?  ]"
            )
            lines.append(f"  {sev_label} {issue['issue']}")
            lines.append(f"         {issue['details']}")

    # ── 8. Performance ────────────────────────────────────────────────────
    section("PERFORMANCE", 8)

    # GPU details
    if gpus:
        lines.append(f"  {'GPU':<4} {'Name':<28} {'Temp':<7} {'VRAM Used':<14} {'Util'}")
        lines.append(f"  {'---':<4} {'----':<28} {'----':<7} {'---------':<14} {'----'}")
        for g in gpus:
            vram_str = f"{g['memory_used_mb']}MB/{g['memory_total_mb']}MB"
            lines.append(
                f"  {g['index']:<4} {g['name']:<28} {g['temperature']}C   {vram_str:<14} {g['utilization_percent']}%"
            )
    else:
        lines.append("  No local GPUs detected (nvidia-smi not available or no NVIDIA GPUs)")

    # Node latency ranking
    lines.append("")
    lines.append("  Node latency ranking:")
    ranked = sorted(
        [n for n in nodes if n["status"] == "ONLINE"],
        key=lambda n: n["latency_ms"],
    )
    for i, n in enumerate(ranked, 1):
        lines.append(f"    {i}. {n['name']}: {n['latency_ms']:.0f}ms")

    # ── 9. Persistence ────────────────────────────────────────────────────
    section("PERSISTENCE", 9)
    persistence = report.get("persistence", {})
    for label, info in persistence.items():
        status = "OK" if info["exists"] else "MISSING"
        size_str = ""
        if info.get("size_bytes", 0) > 0:
            size_mb = info["size_bytes"] / (1024 * 1024)
            size_str = f" ({size_mb:.1f} MB)"
        lines.append(f"  [{status:^7}] {label}{size_str}")
        lines.append(f"           {info['path']}")

    # ── 10. Readiness Scores ──────────────────────────────────────────────
    section("READINESS SCORES", 10)
    for metric, score in scores.items():
        bar_len = score // 5  # 20 chars max
        bar = "#" * bar_len + "-" * (20 - bar_len)
        lines.append(f"  {metric:<16} [{bar}] {score:>3}/100")

    # Overall
    lines.append("")
    avg_score = round(sum(scores.values()) / max(len(scores), 1)) if scores else 0
    lines.append(f"  OVERALL READINESS: {avg_score}/100")

    # Grade
    if avg_score >= 90:
        grade = "A+"
    elif avg_score >= 80:
        grade = "A"
    elif avg_score >= 70:
        grade = "B"
    elif avg_score >= 60:
        grade = "C"
    elif avg_score >= 50:
        grade = "D"
    else:
        grade = "F"
    lines.append(f"  GRADE: {grade}")

    lines.append("")
    lines.append(f"{'=' * 70}")
    lines.append(f"  End of JARVIS System Audit Report")
    lines.append(f"{'=' * 70}")

    return "\n".join(lines)


def save_report(report: dict) -> Path:
    """Save audit report as JSON to data/audit_YYYY-MM-DD_HHmm.json.

    Returns:
        Path to the saved file.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    filename = f"audit_{ts}.json"
    filepath = DATA_DIR / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)

    return filepath


async def main():
    """CLI entry point with argparse."""
    parser = argparse.ArgumentParser(
        description="JARVIS System Audit — Full cluster health analysis"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output raw JSON instead of formatted report",
    )
    parser.add_argument(
        "--quick", action="store_true",
        help="Skip slow nodes (M1) for faster audit",
    )
    parser.add_argument(
        "--save", action="store_true",
        help="Force save report to data/ directory",
    )

    args = parser.parse_args()

    # Run audit
    report = await run_audit(quick=args.quick)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    else:
        text = format_report(report)
        print(text)

    # Auto-save (always in non-json mode, or when --save is used)
    if args.save or not args.json:
        filepath = save_report(report)
        if not args.json:
            print(f"\nReport saved to: {filepath}")

    return report


if __name__ == "__main__":
    asyncio.run(main())
