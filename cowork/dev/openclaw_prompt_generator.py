#!/usr/bin/env python3
"""OpenClaw Prompt Generator — generates optimized prompts for all 40 OpenClaw agents."""

import argparse
import json
import os
import sqlite3
import urllib.request
import urllib.error
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "etoile.db")
PROMPT_DIR = os.path.expanduser(r"~\.openclaw\workspace\prompts")
OPENCLAW_URL = "http://127.0.0.1:18789"

FALLBACK_CHAIN = ["M1/qwen3-8b", "OL1/qwen3:1.7b", "M2/deepseek-r1", "GEMINI/flash"]

# Pattern category -> OpenClaw agent name mapping
PATTERN_AGENT_MAP = {
    "PAT_CW_WIN_MONITOR": "win-monitor",
    "PAT_CW_WIN_SECURITY": "win-security",
    "PAT_CW_WIN_AUTOMATION": "win-automation",
    "PAT_CW_WIN_NETWORK": "win-network",
    "PAT_CW_WIN_DISK": "win-disk",
    "PAT_CW_WIN_PROCESS": "win-process",
    "PAT_CW_WIN_REGISTRY": "win-registry",
    "PAT_CW_WIN_SERVICE": "win-service",
    "PAT_CW_WIN_THERMAL": "win-thermal",
    "PAT_CW_WIN_POWER": "win-power",
    "PAT_CW_JARVIS_CORE": "jarvis-core",
    "PAT_CW_JARVIS_VOICE": "jarvis-voice",
    "PAT_CW_JARVIS_NLP": "jarvis-nlp",
    "PAT_CW_JARVIS_MEMORY": "jarvis-memory",
    "PAT_CW_JARVIS_DEPLOY": "jarvis-deploy",
    "PAT_CW_JARVIS_CONFIG": "jarvis-config",
    "PAT_CW_JARVIS_HEALTH": "jarvis-health",
    "PAT_CW_JARVIS_SKILL": "jarvis-skill",
    "PAT_CW_IA_GENERATION": "ia-generation",
    "PAT_CW_IA_OPTIMIZATION": "ia-optimization",
    "PAT_CW_IA_LEARNING": "ia-learning",
    "PAT_CW_IA_BENCHMARK": "ia-benchmark",
    "PAT_CW_IA_ROUTING": "ia-routing",
    "PAT_CW_IA_PROMPT": "ia-prompt",
    "PAT_CW_IA_ENSEMBLE": "ia-ensemble",
    "PAT_CW_IA_FEEDBACK": "ia-feedback",
    "PAT_CW_TRADING": "trading-analyst",
    "PAT_CW_COMMS": "comms-handler",
    "PAT_CW_CLUSTER": "cluster-manager",
    "PAT_CW_BROWSER": "browser-agent",
    "PAT_CW_DATA": "data-manager",
    "PAT_CW_AUTONOMOUS_SCHED": "auto-scheduler",
    "PAT_CW_AUTONOMOUS_HEAL": "auto-healer",
    "PAT_CW_DEVOPS": "devops-runner",
    "PAT_CW_SOCIAL": "social-agent",
    "PAT_CW_SECURITY": "security-auditor",
    "PAT_CW_DOCKER": "docker-manager",
    "PAT_CW_TELEGRAM": "telegram-bot",
    "PAT_CW_EMAIL": "email-handler",
    "PAT_CW_PIPELINE": "pipeline-orchestrator",
}

KNOWN_AGENTS = list(PATTERN_AGENT_MAP.values())


def get_db(path=DB_PATH):
    """Open etoile.db, ensure required tables exist."""
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS memories "
        "(id INTEGER PRIMARY KEY, category TEXT, key TEXT, value TEXT, "
        "created_at TEXT, updated_at TEXT)"
    )
    conn.commit()
    return conn


def load_patterns(conn):
    """Read PAT_CW_* patterns from agent_patterns table."""
    try:
        rows = conn.execute(
            "SELECT pattern_id, description, scripts FROM agent_patterns "
            "WHERE pattern_id LIKE 'PAT_CW_%'"
        ).fetchall()
        return {r[0]: {"description": r[1], "scripts": r[2]} for r in rows}
    except sqlite3.OperationalError:
        return {}


def load_script_mapping(conn):
    """Read cowork_script_mapping for tool lists."""
    try:
        rows = conn.execute(
            "SELECT pattern_id, script_path, description FROM cowork_script_mapping"
        ).fetchall()
        mapping = {}
        for pid, spath, desc in rows:
            mapping.setdefault(pid, []).append({"script": spath, "description": desc or ""})
        return mapping
    except sqlite3.OperationalError:
        return {}


def fetch_openclaw_agents():
    """Try to get live agent list from OpenClaw gateway."""
    try:
        req = urllib.request.Request(f"{OPENCLAW_URL}/agents", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            if isinstance(data, list):
                return [a.get("name", a.get("id", "")) for a in data]
            return data.get("agents", KNOWN_AGENTS)
    except Exception:
        return KNOWN_AGENTS


def build_prompt(agent_name, pattern_id, pattern_data, tools):
    """Generate a structured prompt dict for one agent."""
    desc = pattern_data.get("description", f"Agent responsible for {agent_name} tasks.")
    tool_list = tools if tools else [{"script": "N/A", "description": "No mapped scripts"}]

    return {
        "agent": agent_name,
        "pattern": pattern_id,
        "generated_at": datetime.now().isoformat(),
        "prompt": {
            "system_role": (
                f"You are {agent_name}, a specialized OpenClaw agent in the JARVIS cluster. "
                f"Your domain: {desc}. Execute tasks autonomously, report structured JSON results. "
                f"Always validate inputs before execution. Log errors with context."
            ),
            "tools": [
                {"name": os.path.basename(t["script"]), "path": t["script"],
                 "purpose": t["description"]}
                for t in tool_list
            ],
            "input_format": {
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "Task description"},
                    "params": {"type": "object", "description": "Task-specific parameters"},
                    "priority": {"type": "integer", "enum": [1, 2, 3], "default": 2},
                },
                "required": ["task"],
            },
            "output_format": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["success", "error", "partial"]},
                    "agent": {"type": "string"},
                    "result": {"type": "object"},
                    "duration_ms": {"type": "integer"},
                    "fallback_used": {"type": "string", "nullable": True},
                },
                "required": ["status", "agent", "result"],
            },
            "fallback_chain": FALLBACK_CHAIN,
            "examples": [
                {
                    "input": {"task": f"Run {agent_name} health check", "priority": 1},
                    "output": {
                        "status": "success",
                        "agent": agent_name,
                        "result": {"healthy": True, "details": "All checks passed"},
                        "duration_ms": 450,
                        "fallback_used": None,
                    },
                }
            ],
        },
    }


def save_to_db(conn, prompts):
    """Save all prompts to etoile.db memories table."""
    now = datetime.now().isoformat()
    for p in prompts:
        key = f"prompt_{p['agent']}"
        value = json.dumps(p, ensure_ascii=False)
        existing = conn.execute(
            "SELECT id FROM memories WHERE category='openclaw_prompts' AND key=?", (key,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE memories SET value=?, updated_at=? WHERE id=?",
                (value, now, existing[0]),
            )
        else:
            conn.execute(
                "INSERT INTO memories (category, key, value, created_at, updated_at) "
                "VALUES ('openclaw_prompts', ?, ?, ?, ?)",
                (key, value, now, now),
            )
    conn.commit()
    print(f"[DB] Saved {len(prompts)} prompts to etoile.db")


def save_to_filesystem(prompts):
    """Write one JSON file per agent to the prompts directory."""
    os.makedirs(PROMPT_DIR, exist_ok=True)
    for p in prompts:
        path = os.path.join(PROMPT_DIR, f"{p['agent']}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(p, f, indent=2, ensure_ascii=False)
    print(f"[FS] Wrote {len(prompts)} files to {PROMPT_DIR}")


def generate_all(conn):
    """Generate prompts for all 40 agents."""
    patterns = load_patterns(conn)
    scripts = load_script_mapping(conn)
    agents = fetch_openclaw_agents()
    prompts = []

    for pat_id, agent_name in PATTERN_AGENT_MAP.items():
        pat_data = patterns.get(pat_id, {"description": f"{agent_name} operations"})
        tools = scripts.get(pat_id, [])
        prompts.append(build_prompt(agent_name, pat_id, pat_data, tools))

    # Include any live agents not in the static map
    mapped_names = set(PATTERN_AGENT_MAP.values())
    for name in agents:
        if name not in mapped_names:
            prompts.append(build_prompt(name, "PAT_CW_UNKNOWN",
                                        {"description": f"{name} agent"}, []))
    return prompts


def cmd_once(args):
    conn = get_db()
    prompts = generate_all(conn)
    save_to_db(conn, prompts)
    save_to_filesystem(prompts)
    conn.close()
    print(f"[DONE] Generated {len(prompts)} prompts (--once)")


def cmd_agent(args):
    conn = get_db()
    patterns = load_patterns(conn)
    scripts = load_script_mapping(conn)
    name = args.agent
    pat_id = None
    for pid, aname in PATTERN_AGENT_MAP.items():
        if aname == name:
            pat_id = pid
            break
    if not pat_id:
        pat_id = "PAT_CW_UNKNOWN"
    pat_data = patterns.get(pat_id, {"description": f"{name} operations"})
    tools = scripts.get(pat_id, [])
    prompt = build_prompt(name, pat_id, pat_data, tools)
    save_to_db(conn, [prompt])
    save_to_filesystem([prompt])
    conn.close()
    print(json.dumps(prompt, indent=2, ensure_ascii=False))


def cmd_export(args):
    conn = get_db()
    prompts = generate_all(conn)
    conn.close()
    out = args.export if isinstance(args.export, str) and args.export != "True" else "openclaw_prompts.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(prompts, f, indent=2, ensure_ascii=False)
    print(f"[EXPORT] {len(prompts)} prompts -> {out}")


def cmd_list(args):
    conn = get_db()
    rows = conn.execute(
        "SELECT key, updated_at FROM memories WHERE category='openclaw_prompts' ORDER BY key"
    ).fetchall()
    conn.close()
    if not rows:
        print("[LIST] No prompts in DB. Run --once first.")
        return
    print(f"{'Agent':<30} {'Updated':<25}")
    print("-" * 55)
    for key, updated in rows:
        name = key.replace("prompt_", "")
        print(f"{name:<30} {updated or 'N/A':<25}")
    print(f"\nTotal: {len(rows)} prompts")


def main():
    parser = argparse.ArgumentParser(description="OpenClaw Prompt Generator")
    parser.add_argument("--once", action="store_true", help="Generate all prompts, save to DB + FS")
    parser.add_argument("--agent", type=str, help="Generate for a specific agent name")
    parser.add_argument("--export", nargs="?", const="openclaw_prompts.json",
                        help="Export all prompts to JSON file")
    parser.add_argument("--list", action="store_true", help="List all generated prompts")
    args = parser.parse_args()

    if args.agent:
        cmd_agent(args)
    elif args.once:
        cmd_once(args)
    elif args.export is not None:
        cmd_export(args)
    elif args.list:
        cmd_list(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
