"""MAJ complete etoile.db — JARVIS HEXA_CORE 2026-02-24.

Ajoute CLAUDE comme 6e noeud, ia-bridge/ia-consensus, routing MAJ,
outils manquants, commandes vocales, memories, metrics, consensus_log.
"""

import sqlite3
import re
import os
import json
from datetime import datetime

DB_PATH = r"F:\BUREAU\etoile.db"
TURBO_SRC = r"F:\BUREAU\turbo\src"


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


# ── 2a: Table agents — Ajouter CLAUDE ────────────────────────────────────
def add_claude_agent(conn):
    c = conn.cursor()
    c.execute("SELECT name FROM agents WHERE name='CLAUDE'")
    if c.fetchone():
        print("[agents] CLAUDE deja present — SKIP")
        return 0
    c.execute("""
        INSERT INTO agents (name, url, type, model, status, latency_ms, last_check, gpu_count, vram_gb, created_at)
        VALUES ('CLAUDE', 'claude-proxy.js', 'claude_cli', 'opus,sonnet,haiku', 'online', 18000, datetime('now'), 0, 0, datetime('now'))
    """)
    print("[agents] CLAUDE ajoute")
    return 1


# ── 2b: Table map — Ajouter noeud CLAUDE ─────────────────────────────────
def add_claude_node(conn):
    c = conn.cursor()
    c.execute("SELECT id FROM map WHERE entity_type='node' AND entity_name='CLAUDE'")
    if c.fetchone():
        print("[map:node] CLAUDE deja present — SKIP")
        return 0
    c.execute("""
        INSERT INTO map (entity_type, entity_name, parent, status, metadata)
        VALUES ('node', 'CLAUDE', 'cluster', 'online',
                '{"proxy": "claude-proxy.js", "models": "opus,sonnet,haiku", "weight": 1.2, "spawn_not_execFile": true}')
    """)
    print("[map:node] CLAUDE ajoute")
    return 1


# ── 2c: Table map — Ajouter agents SDK manquants ─────────────────────────
def add_missing_agents(conn):
    c = conn.cursor()
    agents_to_add = [
        ("ia-bridge", "agents.py", "Orchestrateur multi-noeuds Sonnet — bridge_mesh/query, gemini_query, consensus, lm_query, ollama_web_search"),
        ("ia-consensus", "agents.py", "Consensus multi-source Sonnet — vote pondere M1=1.5,GEMINI=1.2,M2=1.0,OL1=0.8,M3=0.5"),
    ]
    added = 0
    for name, parent, desc in agents_to_add:
        c.execute("SELECT id FROM map WHERE entity_type='agent' AND entity_name=?", (name,))
        if c.fetchone():
            print(f"[map:agent] {name} deja present — SKIP")
            continue
        c.execute(
            "INSERT INTO map (entity_type, entity_name, parent, status, metadata) VALUES ('agent', ?, ?, 'active', ?)",
            (name, parent, json.dumps({"description": desc})),
        )
        print(f"[map:agent] {name} ajoute")
        added += 1
    return added


# ── 2d: Table map — Ajouter routing rules manquantes ─────────────────────
def add_routing_rules(conn):
    c = conn.cursor()

    # Routing standard (14 regles)
    std_rules = {
        "short_answer": {"nodes": ["OL1", "M3"]},
        "deep_analysis": {"nodes": ["M2", "GEMINI"]},
        "trading_signal": {"nodes": ["OL1", "M2"]},
        "code_generation": {"nodes": ["M2", "M3"]},
        "validation": {"nodes": ["M2", "OL1"]},
        "critical": {"nodes": ["M2", "OL1", "GEMINI"]},
        "web_research": {"nodes": ["OL1"]},
        "reasoning": {"nodes": ["CLAUDE", "M2"]},
        "voice_correction": {"nodes": ["OL1"]},
        "auto_learn": {"nodes": ["OL1", "M2"]},
        "embedding": {"nodes": ["M1"]},
        "consensus": {"nodes": ["M2", "OL1", "M3", "M1", "GEMINI", "CLAUDE"]},
        "architecture": {"nodes": ["GEMINI", "CLAUDE", "M2"]},
        "bridge": {"nodes": ["M2", "OL1", "M3", "M1", "GEMINI", "CLAUDE"]},
    }

    # Commander routing (8 regles)
    cmd_rules = {
        "cmd_code": {"agent": "ia-fast", "ia": "M2", "role": "coder", "reviewer": "M3"},
        "cmd_analyse": {"agent": "ia-deep", "ia": "M2", "role": "analyzer"},
        "cmd_trading": {"agent": "ia-trading", "ia": "OL1", "role": "scanner", "validator": "M2"},
        "cmd_systeme": {"agent": "ia-system", "ia": None, "role": "executor"},
        "cmd_web": {"agent": None, "ia": "OL1", "role": "searcher", "synthesizer": "M2"},
        "cmd_simple": {"agent": None, "ia": "OL1", "role": "responder"},
        "cmd_architecture": {"agent": "ia-bridge", "ia": "GEMINI", "role": "analyzer", "reviewer": "M2"},
        "cmd_consensus": {"agent": "ia-consensus", "ia": "M2", "role": "analyzer"},
    }

    added = 0
    for name, meta in {**std_rules, **cmd_rules}.items():
        entity_name = f"routing_{name}"
        c.execute("SELECT id, metadata FROM map WHERE entity_type='routing_rule' AND entity_name=?", (entity_name,))
        row = c.fetchone()
        if row:
            # Update metadata if it changed
            old_meta = row[1] or "{}"
            new_meta = json.dumps(meta)
            if old_meta != new_meta:
                c.execute("UPDATE map SET metadata=?, updated_at=datetime('now') WHERE id=?", (new_meta, row[0]))
                print(f"[map:routing_rule] {entity_name} MIS A JOUR")
                added += 1
            else:
                print(f"[map:routing_rule] {entity_name} deja present — SKIP")
        else:
            c.execute(
                "INSERT INTO map (entity_type, entity_name, parent, metadata) VALUES ('routing_rule', ?, 'config', ?)",
                (entity_name, json.dumps(meta)),
            )
            print(f"[map:routing_rule] {entity_name} ajoute")
            added += 1
    return added


# ── 2e: Table map — Ajouter outils MCP manquants ─────────────────────────
def add_missing_tools(conn):
    c = conn.cursor()

    # 75 outils reels dans tools.py
    real_tools = [
        "bridge_mesh", "bridge_query", "clipboard_get", "clipboard_set", "close_app",
        "consensus", "copy_item", "create_folder", "delete_item", "focus_window",
        "gemini_query", "get_ip", "gpu_info", "kill_process", "list_folder",
        "list_processes", "list_project_paths", "list_scripts", "list_services",
        "list_windows", "lm_benchmark", "lm_cluster_status", "lm_gpu_stats",
        "lm_list_mcp_servers", "lm_load_model", "lm_mcp_query", "lm_models",
        "lm_perf_metrics", "lm_query", "lm_switch_coder", "lm_switch_dev",
        "lm_unload_model", "lock_screen", "maximize_window", "minimize_window",
        "mouse_click", "move_item", "network_info", "notify", "ollama_models",
        "ollama_pull", "ollama_query", "ollama_status", "ollama_subagents",
        "ollama_trading_analysis", "ollama_web_search", "open_app", "open_folder",
        "open_url", "ping", "powershell_run", "press_hotkey", "read_text_file",
        "registry_read", "registry_write", "restart_pc", "run_script",
        "scheduled_tasks", "screen_resolution", "screenshot", "search_files",
        "send_keys", "shutdown_pc", "sleep_pc", "speak", "start_service",
        "stop_service", "system_audit", "system_info", "type_text", "volume_down",
        "volume_mute", "volume_up", "wifi_networks", "write_text_file",
    ]

    # Get existing tools in map
    c.execute("SELECT entity_name FROM map WHERE entity_type='tool'")
    existing = {r[0] for r in c.fetchall()}

    added = 0
    for tool_name in real_tools:
        if tool_name in existing:
            continue
        c.execute(
            "INSERT INTO map (entity_type, entity_name, parent, status) VALUES ('tool', ?, 'tools.py', 'active')",
            (tool_name,),
        )
        print(f"[map:tool] {tool_name} ajoute")
        added += 1

    print(f"[map:tool] Total existants: {len(existing)}, ajoutes: {added}, total final: {len(existing) + added}")
    return added


# ── 2f: Table map — Ajouter claude_query dans mcp_tool ───────────────────
def add_claude_mcp_tool(conn):
    c = conn.cursor()
    c.execute("SELECT id FROM map WHERE entity_type='mcp_tool' AND entity_name='claude_query'")
    if c.fetchone():
        print("[map:mcp_tool] claude_query deja present — SKIP")
        return 0
    c.execute("""
        INSERT INTO map (entity_type, entity_name, parent, status, metadata)
        VALUES ('mcp_tool', 'claude_query', 'claude-proxy.js', 'active',
                '{"description": "Query Claude Code CLI via proxy — raisonnement cloud"}')
    """)
    print("[map:mcp_tool] claude_query ajoute")
    return 1


# ── 2g: Table map — Recount commandes vocales ────────────────────────────
def recount_vocal_commands(conn):
    c = conn.cursor()

    # Scan all 5 command files
    cmd_files = [
        "commands.py", "commands_pipelines.py", "commands_navigation.py",
        "commands_maintenance.py", "commands_dev.py",
    ]

    all_cmd_names = set()
    for f in cmd_files:
        path = os.path.join(TURBO_SRC, f)
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as fh:
            content = fh.read()
        names = re.findall(r'JarvisCommand\(\s*"([^"]+)"', content)
        names += re.findall(r"JarvisCommand\(\s*'([^']+)'", content)
        all_cmd_names.update(names)

    # Get existing vocal commands in map
    c.execute("SELECT entity_name FROM map WHERE entity_type='vocal_command'")
    existing = {r[0] for r in c.fetchall()}

    # Add missing commands
    missing = all_cmd_names - existing
    added = 0
    for cmd_name in sorted(missing):
        c.execute(
            "INSERT INTO map (entity_type, entity_name, parent, status) VALUES ('vocal_command', ?, 'commands', 'active')",
            (cmd_name,),
        )
        added += 1

    print(f"[map:vocal_command] Existants: {len(existing)}, nouveaux: {added}, total: {len(existing) + added}")
    if added > 0:
        print(f"  Exemples: {sorted(missing)[:10]}...")
    return added


# ── 2h: Table memories — MAJ info perimee ─────────────────────────────────
def update_memories(conn):
    c = conn.cursor()
    changes = 0

    # Update SDK agents list
    c.execute("SELECT id FROM memories WHERE category='sdk' AND key='agents_list'")
    row = c.fetchone()
    if row:
        c.execute(
            "UPDATE memories SET value=?, confidence=1.0, updated_at=datetime('now') WHERE id=?",
            ("ia-deep(Opus) ia-fast(Haiku) ia-check(Sonnet) ia-trading(Sonnet) ia-system(Haiku) ia-bridge(Sonnet) ia-consensus(Sonnet)", row[0]),
        )
        print("[memories] sdk/agents_list mis a jour (5 -> 7 agents)")
        changes += 1

    # Update SDK version
    c.execute("SELECT id FROM memories WHERE category='sdk' AND key='version'")
    row = c.fetchone()
    if row:
        c.execute(
            "UPDATE memories SET value=?, confidence=1.0, updated_at=datetime('now') WHERE id=?",
            ("Claude Agent SDK Python v0.1.35, 7 agents, 75 outils MCP (tools.py v3.4.0+)", row[0]),
        )
        print("[memories] sdk/version mis a jour (83 -> 75 outils, 5 -> 7 agents)")
        changes += 1

    # Update cluster total_gpu
    c.execute("SELECT id FROM memories WHERE category='cluster' AND key='total_gpu'")
    row = c.fetchone()
    if row:
        c.execute(
            "UPDATE memories SET value=?, confidence=1.0, updated_at=datetime('now') WHERE id=?",
            ("10 GPU, ~78 GB VRAM across 3 physical nodes + Gemini cloud + Claude cloud", row[0]),
        )
        print("[memories] cluster/total_gpu mis a jour (9->10 GPU, 70->78 VRAM)")
        changes += 1

    # Add CLAUDE node memory
    c.execute("SELECT id FROM memories WHERE category='cluster' AND key='claude_config'")
    if not c.fetchone():
        c.execute("""
            INSERT INTO memories (category, key, value, source, confidence, created_at, updated_at)
            VALUES ('cluster', 'claude_config',
                    'CLAUDE: claude-proxy.js, opus/sonnet/haiku, spawn (PAS execFile), env CLAUDE* sanitise, w=1.2, ~12-18s',
                    'config.py', 1.0, datetime('now'), datetime('now'))
        """)
        print("[memories] cluster/claude_config ajoute")
        changes += 1

    # Update M2 status (was offline, now online per benchmark)
    c.execute("SELECT id FROM memories WHERE category='status' AND key='m2_offline'")
    row = c.fetchone()
    if row:
        c.execute(
            "UPDATE memories SET value=?, key=?, updated_at=datetime('now') WHERE id=?",
            ("M2 (192.168.1.26) online — CHAMPION 92%, 1.3s, deepseek-coder", "m2_status", row[0]),
        )
        print("[memories] status/m2_offline -> m2_status (online)")
        changes += 1

    return changes


# ── 2i: Table metrics — Ajouter CLAUDE ────────────────────────────────────
def add_claude_metrics(conn):
    c = conn.cursor()
    metrics = [
        ("CLAUDE", "avg_latency", 18000.0, "ms"),
        ("CLAUDE", "weight", 1.2, "multiplier"),
        ("CLAUDE", "benchmark_score", 74.0, "%"),
        ("CLAUDE", "status", 1.0, "bool"),
    ]
    added = 0
    for agent, mtype, value, unit in metrics:
        c.execute("SELECT id FROM metrics WHERE agent=? AND metric_type=?", (agent, mtype))
        if c.fetchone():
            print(f"[metrics] {agent}/{mtype} deja present — SKIP")
            continue
        c.execute(
            "INSERT INTO metrics (agent, metric_type, value, unit, recorded_at) VALUES (?, ?, ?, ?, datetime('now'))",
            (agent, mtype, value, unit),
        )
        print(f"[metrics] {agent}/{mtype}={value} ajoute")
        added += 1

    # Update cluster totals
    c.execute("UPDATE metrics SET value=6.0, recorded_at=datetime('now') WHERE agent='cluster' AND metric_type='nodes_total'")
    c.execute("UPDATE metrics SET value=10.0, recorded_at=datetime('now') WHERE agent='cluster' AND metric_type='total_gpu'")
    c.execute("UPDATE metrics SET value=78.0, recorded_at=datetime('now') WHERE agent='cluster' AND metric_type='total_vram_gb'")
    print("[metrics] cluster totals mis a jour (6 nodes, 10 GPU, 78 VRAM)")
    return added


# ── 2j: Table consensus_log — Ajouter tests du jour ──────────────────────
def add_consensus_logs(conn):
    c = conn.cursor()
    logs = [
        (
            "meilleur langage web scraping",
            "OL1,M3,GEMINI,CLAUDE",
            "OL1,M3,GEMINI,CLAUDE",
            "Python unanime #1, JavaScript #2, Go vs Ruby #3 (cloud vs local bias)",
            0.95,
        ),
        (
            "meilleur framework web python 2026 (3 runs stabilite)",
            "OL1,M3,GEMINI,CLAUDE",
            "OL1,M3,GEMINI,CLAUDE",
            "FastAPI unanime #1, Django #2, Flask #3 — stabilite intra-agent 95% — clivage local/cloud sur ordre #1/#2",
            0.95,
        ),
    ]
    added = 0
    for query, queried, responded, verdict, confidence in logs:
        c.execute("SELECT id FROM consensus_log WHERE query=?", (query,))
        if c.fetchone():
            print(f"[consensus_log] '{query[:40]}...' deja present — SKIP")
            continue
        c.execute("""
            INSERT INTO consensus_log (timestamp, query, nodes_queried, nodes_responded, verdict, confidence)
            VALUES (datetime('now'), ?, ?, ?, ?, ?)
        """, (query, queried, responded, verdict, confidence))
        print(f"[consensus_log] '{query[:40]}...' ajoute")
        added += 1
    return added


# ── 2k: Table api_keys — Entree CLAUDE ───────────────────────────────────
def add_claude_api_key(conn):
    c = conn.cursor()
    c.execute("SELECT id FROM api_keys WHERE service='claude_cli'")
    if c.fetchone():
        print("[api_keys] claude_cli deja present — SKIP")
        return 0
    c.execute("""
        INSERT INTO api_keys (service, key_name, key_value, endpoint, status)
        VALUES ('claude_cli', 'Claude Code Auth', 'cli-auth-local', 'claude-proxy.js', 'active')
    """)
    print("[api_keys] claude_cli ajoute")
    return 1


# ── MAIN ──────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("MAJ etoile.db — JARVIS HEXA_CORE 2026-02-24")
    print("=" * 60)
    print()

    conn = connect()
    total_changes = 0

    try:
        total_changes += add_claude_agent(conn)
        print()
        total_changes += add_claude_node(conn)
        print()
        total_changes += add_missing_agents(conn)
        print()
        total_changes += add_routing_rules(conn)
        print()
        total_changes += add_missing_tools(conn)
        print()
        total_changes += add_claude_mcp_tool(conn)
        print()
        total_changes += recount_vocal_commands(conn)
        print()
        total_changes += update_memories(conn)
        print()
        total_changes += add_claude_metrics(conn)
        print()
        total_changes += add_consensus_logs(conn)
        print()
        total_changes += add_claude_api_key(conn)
        print()

        conn.commit()
        print("=" * 60)
        print(f"COMMIT OK — {total_changes} modifications")
        print("=" * 60)

        # ── Rapport de verification ──
        print("\n=== RAPPORT DE VERIFICATION ===\n")

        c = conn.cursor()

        c.execute("SELECT entity_type, COUNT(*) FROM map GROUP BY entity_type ORDER BY COUNT(*) DESC")
        print("Map par entity_type:")
        for etype, count in c.fetchall():
            print(f"  {etype}: {count}")

        print()
        c.execute("SELECT COUNT(*) FROM agents")
        print(f"Agents total: {c.fetchone()[0]}")
        c.execute("SELECT name, type, status FROM agents ORDER BY name")
        for name, atype, status in c.fetchall():
            print(f"  {name} ({atype}) — {status}")

        print()
        c.execute("SELECT category, key, value FROM memories WHERE category IN ('sdk', 'cluster') ORDER BY category, key")
        print("Memories SDK/cluster:")
        for cat, key, val in c.fetchall():
            print(f"  [{cat}] {key}: {val[:80]}...")

        print()
        c.execute("SELECT agent, metric_type, value, unit FROM metrics WHERE agent='CLAUDE'")
        print("Metrics CLAUDE:")
        for agent, mt, val, unit in c.fetchall():
            print(f"  {mt}: {val} {unit}")

        print()
        c.execute("SELECT COUNT(*) FROM consensus_log")
        print(f"Consensus logs: {c.fetchone()[0]}")

    except Exception as e:
        conn.rollback()
        print(f"\nERREUR — ROLLBACK: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
