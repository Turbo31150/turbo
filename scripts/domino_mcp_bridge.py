#!/usr/bin/env python3
"""MCP Bridge for JARVIS Domino Pipelines — 405 pre-encoded action cascades.

Exposes domino pipelines as MCP tools for OpenClaw agents.
No model needed for execution — pure keyword→action sequences.
"""
import sys
import json
import subprocess
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Import domino pipelines
from src.domino_pipelines import DOMINO_PIPELINES, find_domino

app = Server("jarvis-domino")

PYTHON = sys.executable
TURBO_DIR = Path(__file__).parent.parent


@app.list_tools()
async def list_tools():
    return [
        Tool(
            name="domino_find",
            description="Find domino pipeline by voice trigger or keyword. Returns matching pipeline with steps. 405 pipelines available across 107 categories.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Voice trigger or keyword to search (e.g. 'bonjour jarvis', 'gpu check', 'trading scan')"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="domino_execute",
            description="Execute a domino pipeline by ID. Runs all steps in sequence (powershell, curl, python, etc). No AI model needed.",
            inputSchema={
                "type": "object",
                "properties": {
                    "pipeline_id": {
                        "type": "string",
                        "description": "Pipeline ID to execute"
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "If true, show steps without executing (default: false)"
                    }
                },
                "required": ["pipeline_id"]
            }
        ),
        Tool(
            name="domino_list",
            description="List domino pipelines. Filter by category or keyword. Shows pipeline IDs, triggers, and step counts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Filter by category (e.g. 'monitoring', 'trading', 'routine_matin')"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default 20)"
                    }
                }
            }
        ),
        Tool(
            name="domino_categories",
            description="List all domino pipeline categories with counts. 107 categories, 405 pipelines total.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="keyword_action",
            description="Execute instant keyword shortcuts. No AI model needed — direct system action. Keywords: gpu, disk, ram, health, boot, alert, temp, processes, network, services",
            inputSchema={
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "Keyword: gpu|disk|ram|health|boot|alert|temp|processes|network|services|uptime"
                    }
                },
                "required": ["keyword"]
            }
        )
    ]


KEYWORD_ACTIONS = {
    "gpu": 'powershell.exe -NoProfile -Command "nvidia-smi --query-gpu=index,name,temperature.gpu,utilization.gpu,memory.used,memory.total --format=csv,noheader"',
    "disk": 'powershell.exe -NoProfile -Command "Get-PSDrive -PSProvider FileSystem | Select-Object Name,@{N=\'Used(GB)\';E={[math]::Round($_.Used/1GB,1)}},@{N=\'Free(GB)\';E={[math]::Round($_.Free/1GB,1)}} | Format-Table -AutoSize"',
    "ram": 'powershell.exe -NoProfile -Command "Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 10 Name,@{N=\'RAM(MB)\';E={[math]::Round($_.WorkingSet64/1MB)}} | Format-Table -AutoSize"',
    "health": f'curl -s --max-time 3 http://127.0.0.1:9742/api/tools/execute -H "Content-Type: application/json" -d "{{/"tool_name/":/"jarvis_cluster_health/",/"arguments/":{{}}}}"',
    "boot": f'curl -s --max-time 3 http://127.0.0.1:9742/api/tools/execute -H "Content-Type: application/json" -d "{{/"tool_name/":/"jarvis_boot_status/",/"arguments/":{{}}}}"',
    "alert": f'curl -s --max-time 3 http://127.0.0.1:9742/api/tools/execute -H "Content-Type: application/json" -d "{{/"tool_name/":/"jarvis_alerts_active/",/"arguments/":{{}}}}"',
    "temp": 'powershell.exe -NoProfile -Command "nvidia-smi --query-gpu=index,temperature.gpu,fan.speed,power.draw --format=csv,noheader"',
    "processes": 'powershell.exe -NoProfile -Command "Get-Process | Sort-Object CPU -Descending | Select-Object -First 15 Name,CPU,@{N=\'RAM(MB)\';E={[math]::Round($_.WorkingSet64/1MB)}} | Format-Table -AutoSize"',
    "network": 'powershell.exe -NoProfile -Command "Get-NetTCPConnection -State Listen | Select-Object LocalPort,OwningProcess | Sort-Object LocalPort | Format-Table -AutoSize"',
    "services": 'powershell.exe -NoProfile -Command "netstat -ano | findstr LISTENING | findstr -E /\":(1234|11434|18789|18800|9742|8080|8901)/\" "',
    "uptime": 'powershell.exe -NoProfile -Command "(Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime | Select-Object Days,Hours,Minutes"',
}


async def _run_cmd(cmd: str, timeout: int = 30) -> str:
    """Run a shell command and return output."""
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(TURBO_DIR)
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        out = stdout.decode("utf-8", errors="replace").strip()
        err = stderr.decode("utf-8", errors="replace").strip()
        if proc.returncode != 0 and err:
            return f"{out}\n[stderr] {err}" if out else f"[stderr] {err}"
        return out or "(no output)"
    except asyncio.TimeoutError:
        return f"[TIMEOUT after {timeout}s]"
    except Exception as e:
        return f"[ERROR] {e}"


async def _execute_pipeline(pipeline, dry_run=False):
    """Execute all steps in a domino pipeline."""
    results = []
    results.append(f"Pipeline: {pipeline.id} ({pipeline.description})")
    results.append(f"Category: {pipeline.category} | Priority: {pipeline.priority}")
    results.append(f"Steps: {len(pipeline.steps)}")
    results.append("---")

    for i, step in enumerate(pipeline.steps, 1):
        if dry_run:
            results.append(f"[{i}] {step.name} ({step.action_type}): {step.action[:100]}")
        else:
            results.append(f"[{i}] Executing: {step.name} ({step.action_type})")
            if step.action_type in ("powershell", "bash"):
                out = await _run_cmd(step.action, timeout=step.timeout_s)
            elif step.action_type == "curl":
                out = await _run_cmd(step.action, timeout=step.timeout_s)
            elif step.action_type == "python":
                out = await _run_cmd(f"{PYTHON} -c \"{step.action}\"", timeout=step.timeout_s)
            elif step.action_type == "tool":
                out = await _run_cmd(step.action, timeout=step.timeout_s)
            elif step.action_type == "condition":
                out = f"[condition] {step.condition or step.action}"
            elif step.action_type == "pipeline":
                out = f"[sub-pipeline] {step.action}"
            else:
                out = f"[unsupported type: {step.action_type}]"
            results.append(f"  → {out[:500]}")

            if step.on_fail == "stop" and "[ERROR]" in out:
                results.append(f"  ⛔ Step failed, pipeline stopped (on_fail=stop)")
                break

    return "\n".join(results)


@app.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "domino_find":
        query = arguments.get("query", "")
        result = find_domino(query)
        if result:
            p = result
            triggers = ", ".join(p.trigger_vocal[:5])
            steps_info = "\n".join(
                f"  [{i}] {s.name} ({s.action_type}): {s.action[:80]}"
                for i, s in enumerate(p.steps, 1)
            )
            return [TextContent(
                type="text",
                text=f"Found: {p.id}\nTriggers: {triggers}\nCategory: {p.category}\nPriority: {p.priority}\nSteps ({len(p.steps)}):\n{steps_info}"
            )]
        return [TextContent(type="text", text=f"No pipeline found for: {query}")]

    elif name == "domino_execute":
        pid = arguments.get("pipeline_id", "")
        dry_run = arguments.get("dry_run", False)
        pipeline = None
        for p in DOMINO_PIPELINES:
            if p.id == pid:
                pipeline = p
                break
        if not pipeline:
            return [TextContent(type="text", text=f"Pipeline not found: {pid}")]
        result = await _execute_pipeline(pipeline, dry_run=dry_run)
        return [TextContent(type="text", text=result)]

    elif name == "domino_list":
        category = arguments.get("category", "")
        limit = arguments.get("limit", 20)
        filtered = DOMINO_PIPELINES
        if category:
            filtered = [p for p in DOMINO_PIPELINES if category.lower() in p.category.lower()]
        lines = []
        for p in filtered[:limit]:
            triggers = ", ".join(p.trigger_vocal[:2])
            lines.append(f"{p.id} [{p.category}] ({len(p.steps)} steps) — {triggers}")
        header = f"{len(filtered)} pipelines"
        if category:
            header += f" in '{category}'"
        return [TextContent(type="text", text=f"{header}:\n" + "\n".join(lines))]

    elif name == "domino_categories":
        cats = {}
        for p in DOMINO_PIPELINES:
            cats[p.category] = cats.get(p.category, 0) + 1
        sorted_cats = sorted(cats.items(), key=lambda x: -x[1])
        lines = [f"{cat}: {count}" for cat, count in sorted_cats]
        return [TextContent(type="text", text=f"{len(cats)} categories, {len(DOMINO_PIPELINES)} pipelines:\n" + "\n".join(lines))]

    elif name == "keyword_action":
        keyword = arguments.get("keyword", "").lower().strip()
        if keyword not in KEYWORD_ACTIONS:
            available = ", ".join(sorted(KEYWORD_ACTIONS.keys()))
            return [TextContent(type="text", text=f"Unknown keyword: {keyword}\nAvailable: {available}")]
        cmd = KEYWORD_ACTIONS[keyword]
        result = await _run_cmd(cmd, timeout=15)
        return [TextContent(type="text", text=f"[{keyword}]\n{result}")]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
