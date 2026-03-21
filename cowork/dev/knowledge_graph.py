#!/usr/bin/env python3
"""Build a relationship graph from etoile.db: agents -> patterns -> scripts.

Reads tables: map, agents, agent_patterns, cowork_script_mapping.
Outputs JSON with nodes/edges counts and top connected agents.
Logs execution to etoile.db cowork_execution_log.
"""

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

ETOILE_DB = Path(r"F:\BUREAU\turbo\etoile.db")


def log_run(db_path: Path, script: str, exit_code: int, duration_ms: float,
            success: bool, stdout_preview: str = "", stderr_preview: str = ""):
    """Log execution to cowork_execution_log."""
    try:
        con = sqlite3.connect(str(db_path))
        con.execute(
            "INSERT INTO cowork_execution_log (script,args,exit_code,duration_ms,success,stdout_preview,stderr_preview)"
            " VALUES (?,?,?,?,?,?,?)",
            (script, "--once", exit_code, duration_ms, int(success),
             stdout_preview[:500], stderr_preview[:500]))
        con.commit()
        con.close()
    except Exception:
        pass


def build_graph(db_path: Path) -> dict:
    """Query etoile.db and build the relationship graph."""
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row

    nodes = []
    edges = []
    agent_connections: dict[str, int] = {}

    # Load agents
    agents = {}
    for row in con.execute("SELECT id, name, model, status FROM agents"):
        nid = f"agent:{row['name']}"
        agents[row['name']] = nid
        nodes.append({"id": nid, "type": "agent", "label": row['name'],
                       "model": row['model'], "status": row['status']})
        agent_connections[row['name']] = 0

    # Load map entities
    for row in con.execute("SELECT id, entity_type, entity_name, parent, role, status FROM map"):
        nid = f"map:{row['entity_type']}:{row['entity_name']}"
        nodes.append({"id": nid, "type": "map_entity",
                       "entity_type": row['entity_type'],
                       "label": row['entity_name'], "status": row['status']})
        if row['parent']:
            edges.append({"source": nid, "target": f"map:{row['entity_type']}:{row['parent']}",
                           "relation": "child_of"})

    # Load patterns and link to agents
    patterns = {}
    for row in con.execute("SELECT id, pattern_name, agent_primary, agent_secondary, category FROM agent_patterns"):
        pname = row['pattern_name'] or f"pattern_{row['id']}"
        nid = f"pattern:{pname}"
        patterns[pname] = nid
        nodes.append({"id": nid, "type": "pattern", "label": pname,
                       "category": row['category']})
        for agent_col in ('agent_primary', 'agent_secondary'):
            aname = row[agent_col]
            if aname and aname in agents:
                edges.append({"source": agents[aname], "target": nid,
                               "relation": agent_col})
                agent_connections[aname] = agent_connections.get(aname, 0) + 1

    # Load script mappings and link to patterns
    for row in con.execute("SELECT id, script_name, pattern_id, status FROM cowork_script_mapping"):
        nid = f"script:{row['script_name']}"
        nodes.append({"id": nid, "type": "script", "label": row['script_name'],
                       "status": row['status']})
        pid = row['pattern_id']
        if pid and pid in patterns:
            edges.append({"source": patterns[pid], "target": nid,
                           "relation": "maps_to"})

    con.close()

    # Top connected agents
    top_agents = sorted(agent_connections.items(), key=lambda x: -x[1])[:10]

    return {
        "nodes_count": len(nodes),
        "edges_count": len(edges),
        "node_types": {"agents": sum(1 for n in nodes if n["type"] == "agent"),
                        "patterns": sum(1 for n in nodes if n["type"] == "pattern"),
                        "scripts": sum(1 for n in nodes if n["type"] == "script"),
                        "map_entities": sum(1 for n in nodes if n["type"] == "map_entity")},
        "top_connected_agents": [{"agent": a, "connections": c} for a, c in top_agents],
        "edges_sample": edges[:20],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.parse_args()

    t0 = time.time()
    try:
        result = build_graph(ETOILE_DB)
        output = json.dumps(result, indent=2, ensure_ascii=False)
        print(output)
        duration = (time.time() - t0) * 1000
        log_run(ETOILE_DB, "knowledge_graph.py", 0, duration, True, output[:500])
    except Exception as exc:
        duration = (time.time() - t0) * 1000
        err = str(exc)
        log_run(ETOILE_DB, "knowledge_graph.py", 1, duration, False, stderr_preview=err)
        print(json.dumps({"error": err}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
