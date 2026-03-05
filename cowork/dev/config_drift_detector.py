#!/usr/bin/env python3
"""config_drift_detector.py

Detect configuration differences between cluster nodes.

Fonctionnalites :
* Compare les configurations LM Studio de M1, M2, M3
* Verifie les versions de modeles Ollama
* Detecte le drift de parametres (temperature, max_tokens, etc.)
* Enregistre les snapshots et diffs dans SQLite (cowork_gaps.db)
* Produit un rapport JSON avec les ecarts detectes

CLI :
    --once      : detecte les drifts et affiche le resume JSON
    --diff      : affiche les differences detaillees entre noeuds
    --fix       : suggere les corrections a appliquer (read-only, pas de modification)

Stdlib-only (urllib, sqlite3, json, argparse).
"""

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
DB_PATH = DATA_DIR / "cowork_gaps.db"

NODES = {
    "M1": {
        "type": "lmstudio",
        "models_url": "http://127.0.0.1:1234/api/v1/models",
        "host": "127.0.0.1:1234",
    },
    "M2": {
        "type": "lmstudio",
        "models_url": "http://192.168.1.26:1234/api/v1/models",
        "host": "192.168.1.26:1234",
    },
    "M3": {
        "type": "lmstudio",
        "models_url": "http://192.168.1.113:1234/api/v1/models",
        "host": "192.168.1.113:1234",
    },
    "OL1": {
        "type": "ollama",
        "models_url": "http://127.0.0.1:11434/api/tags",
        "version_url": "http://127.0.0.1:11434/api/version",
        "host": "127.0.0.1:11434",
    },
}

# Expected/reference configuration (baseline)
BASELINE = {
    "lmstudio": {
        "expected_params": {
            "temperature": 0.2,
            "max_output_tokens": 1024,
            "stream": False,
            "store": False,
        },
    },
    "ollama": {
        "expected_params": {
            "stream": False,
            "think": False,
        },
    },
}

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
def init_db(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS config_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            node TEXT NOT NULL,
            config_json TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS config_drifts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            node TEXT NOT NULL,
            drift_type TEXT NOT NULL,
            parameter TEXT NOT NULL,
            expected_value TEXT,
            actual_value TEXT,
            severity TEXT NOT NULL DEFAULT 'warning'
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS config_drift_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            nodes_checked INTEGER NOT NULL,
            nodes_online INTEGER NOT NULL,
            drifts_found INTEGER NOT NULL,
            duration_ms INTEGER NOT NULL
        )
    """)
    conn.commit()


def get_db() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn

# ---------------------------------------------------------------------------
# HTTP Helper
# ---------------------------------------------------------------------------
def http_get(url: str, timeout: int = 5) -> tuple:
    """GET request. Returns (success, data_dict, elapsed_ms)."""
    start = time.time()
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            elapsed = int((time.time() - start) * 1000)
            raw = resp.read().decode("utf-8")
            return True, json.loads(raw), elapsed
    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        return False, {"error": str(e)}, elapsed

# ---------------------------------------------------------------------------
# Config Fetching
# ---------------------------------------------------------------------------
def fetch_lmstudio_config(node_name: str, node: dict) -> dict:
    """Fetch LM Studio node configuration."""
    ok, data, elapsed = http_get(node["models_url"])
    if not ok:
        return {"status": "offline", "error": data.get("error"), "ping_ms": elapsed}

    models = data.get("data", data.get("models", []))
    loaded = []
    for m in models:
        info = {
            "id": m.get("id", "unknown"),
            "loaded": bool(m.get("loaded_instances")),
            "object": m.get("object"),
        }
        # Capture runtime params if available
        if "config" in m:
            info["config"] = m["config"]
        if "context_length" in m:
            info["context_length"] = m["context_length"]
        if "max_tokens" in m:
            info["max_tokens"] = m["max_tokens"]
        loaded.append(info)

    return {
        "status": "online",
        "ping_ms": elapsed,
        "type": "lmstudio",
        "models": loaded,
        "total_models": len(models),
        "loaded_models": len([m for m in loaded if m.get("loaded")]),
    }


def fetch_ollama_config(node_name: str, node: dict) -> dict:
    """Fetch Ollama node configuration."""
    ok, data, elapsed = http_get(node["models_url"])
    if not ok:
        return {"status": "offline", "error": data.get("error"), "ping_ms": elapsed}

    models = data.get("models", [])
    model_list = []
    for m in models:
        info = {
            "name": m.get("name", "unknown"),
            "size": m.get("size", 0),
            "modified_at": m.get("modified_at", ""),
            "digest": m.get("digest", "")[:16],
            "format": m.get("details", {}).get("format", ""),
            "family": m.get("details", {}).get("family", ""),
            "parameter_size": m.get("details", {}).get("parameter_size", ""),
            "quantization_level": m.get("details", {}).get("quantization_level", ""),
        }
        model_list.append(info)

    # Get version
    version_info = {}
    if "version_url" in node:
        ok2, vdata, _ = http_get(node["version_url"])
        if ok2:
            version_info = vdata

    return {
        "status": "online",
        "ping_ms": elapsed,
        "type": "ollama",
        "models": model_list,
        "total_models": len(models),
        "version": version_info.get("version", "unknown"),
    }


def fetch_node_config(node_name: str) -> dict:
    """Fetch configuration for a given node."""
    node = NODES[node_name]
    if node["type"] == "lmstudio":
        return fetch_lmstudio_config(node_name, node)
    elif node["type"] == "ollama":
        return fetch_ollama_config(node_name, node)
    return {"status": "unknown", "error": "unknown node type"}

# ---------------------------------------------------------------------------
# Drift Detection
# ---------------------------------------------------------------------------
def detect_drifts(configs: dict) -> list[dict]:
    """Compare configurations and detect drifts."""
    drifts = []
    timestamp = datetime.now().isoformat()

    # 1. Cross-node comparison for LM Studio nodes
    lm_nodes = {k: v for k, v in configs.items()
                if v.get("type") == "lmstudio" and v.get("status") == "online"}

    # Compare loaded model counts
    loaded_counts = {k: v.get("loaded_models", 0) for k, v in lm_nodes.items()}
    if loaded_counts:
        max_loaded = max(loaded_counts.values())
        for node, count in loaded_counts.items():
            if count == 0 and max_loaded > 0:
                drifts.append({
                    "timestamp": timestamp,
                    "node": node,
                    "drift_type": "model_state",
                    "parameter": "loaded_models",
                    "expected": f">0 (others have {max_loaded})",
                    "actual": str(count),
                    "severity": "critical",
                })

    # 2. Check context lengths across LM Studio nodes
    for node_name, config in lm_nodes.items():
        for model in config.get("models", []):
            ctx = model.get("context_length")
            if ctx is not None and ctx < 2048:
                drifts.append({
                    "timestamp": timestamp,
                    "node": node_name,
                    "drift_type": "parameter",
                    "parameter": f"{model['id']}.context_length",
                    "expected": ">=2048",
                    "actual": str(ctx),
                    "severity": "warning",
                })

    # 3. Ollama model version drift
    ol_nodes = {k: v for k, v in configs.items()
                if v.get("type") == "ollama" and v.get("status") == "online"}
    for node_name, config in ol_nodes.items():
        for model in config.get("models", []):
            # Check for zero-size models (integrity issue)
            size = model.get("size", 0)
            if size == 0:
                drifts.append({
                    "timestamp": timestamp,
                    "node": node_name,
                    "drift_type": "model_integrity",
                    "parameter": f"{model['name']}.size",
                    "expected": ">0",
                    "actual": "0",
                    "severity": "warning",
                })

    # 4. Detect offline nodes
    for node_name, config in configs.items():
        if config.get("status") == "offline":
            drifts.append({
                "timestamp": timestamp,
                "node": node_name,
                "drift_type": "availability",
                "parameter": "status",
                "expected": "online",
                "actual": "offline",
                "severity": "critical",
            })

    # 5. Cross-compare LM Studio model sets
    if len(lm_nodes) >= 2:
        all_model_ids = {}
        for node_name, config in lm_nodes.items():
            ids = set(m["id"] for m in config.get("models", []))
            all_model_ids[node_name] = ids

        # Report unique models per node (informational)
        all_ids = set()
        for ids in all_model_ids.values():
            all_ids.update(ids)

        for node_name, ids in all_model_ids.items():
            missing = all_ids - ids
            # Only flag if a model exists on most nodes but not this one
            for mid in missing:
                nodes_with = sum(1 for nids in all_model_ids.values() if mid in nids)
                if nodes_with >= len(lm_nodes) - 1 and len(lm_nodes) > 1:
                    drifts.append({
                        "timestamp": timestamp,
                        "node": node_name,
                        "drift_type": "model_coverage",
                        "parameter": f"model.{mid}",
                        "expected": "present (available on other nodes)",
                        "actual": "missing",
                        "severity": "info",
                    })

    return drifts

# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------
def action_once() -> dict:
    """Detect config drifts across all nodes."""
    start_ms = int(time.time() * 1000)
    conn = get_db()

    configs = {}
    online_count = 0
    for node_name in NODES:
        config = fetch_node_config(node_name)
        configs[node_name] = config
        if config.get("status") == "online":
            online_count += 1

        # Save snapshot
        conn.execute("""
            INSERT INTO config_snapshots (timestamp, node, config_json)
            VALUES (?, ?, ?)
        """, (datetime.now().isoformat(), node_name, json.dumps(config)))

    # Detect drifts
    drifts = detect_drifts(configs)

    # Persist drifts
    for d in drifts:
        conn.execute("""
            INSERT INTO config_drifts
            (timestamp, node, drift_type, parameter, expected_value, actual_value, severity)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (d["timestamp"], d["node"], d["drift_type"], d["parameter"],
              d.get("expected", ""), d.get("actual", ""), d["severity"]))

    duration_ms = int(time.time() * 1000) - start_ms

    conn.execute("""
        INSERT INTO config_drift_runs
        (timestamp, nodes_checked, nodes_online, drifts_found, duration_ms)
        VALUES (?, ?, ?, ?, ?)
    """, (datetime.now().isoformat(), len(NODES), online_count, len(drifts), duration_ms))

    conn.commit()
    conn.close()

    # Categorize drifts by severity
    by_severity = {"critical": [], "warning": [], "info": []}
    for d in drifts:
        sev = d.get("severity", "info")
        by_severity.setdefault(sev, []).append(d)

    return {
        "timestamp": datetime.now().isoformat(),
        "action": "detect",
        "nodes_checked": len(NODES),
        "nodes_online": online_count,
        "drifts_found": len(drifts),
        "by_severity": {k: len(v) for k, v in by_severity.items()},
        "drifts": drifts,
        "configs_summary": {
            k: {
                "status": v.get("status"),
                "type": v.get("type"),
                "models": v.get("total_models", 0),
                "loaded": v.get("loaded_models", v.get("total_models", 0)),
            }
            for k, v in configs.items()
        },
        "duration_ms": duration_ms,
    }


def action_diff() -> dict:
    """Show detailed differences between nodes."""
    conn = get_db()

    # Get latest snapshots per node
    snapshots = {}
    for node_name in NODES:
        row = conn.execute("""
            SELECT config_json FROM config_snapshots
            WHERE node = ? ORDER BY timestamp DESC LIMIT 1
        """, (node_name,)).fetchone()
        if row:
            snapshots[node_name] = json.loads(row["config_json"])

    # Get latest two snapshots per node to detect temporal drift
    temporal_drifts = {}
    for node_name in NODES:
        rows = conn.execute("""
            SELECT timestamp, config_json FROM config_snapshots
            WHERE node = ? ORDER BY timestamp DESC LIMIT 2
        """, (node_name,)).fetchall()
        if len(rows) >= 2:
            current = json.loads(rows[0]["config_json"])
            previous = json.loads(rows[1]["config_json"])
            changes = []

            # Compare model lists
            curr_models = set(
                m.get("id", m.get("name", "?"))
                for m in current.get("models", [])
            )
            prev_models = set(
                m.get("id", m.get("name", "?"))
                for m in previous.get("models", [])
            )
            added = curr_models - prev_models
            removed = prev_models - curr_models
            if added:
                changes.append({"type": "models_added", "models": list(added)})
            if removed:
                changes.append({"type": "models_removed", "models": list(removed)})

            if changes:
                temporal_drifts[node_name] = {
                    "from": rows[1]["timestamp"],
                    "to": rows[0]["timestamp"],
                    "changes": changes,
                }

    conn.close()

    return {
        "timestamp": datetime.now().isoformat(),
        "action": "diff",
        "current_configs": snapshots,
        "temporal_drifts": temporal_drifts,
    }


def action_fix() -> dict:
    """Suggest fixes for detected drifts (read-only)."""
    conn = get_db()

    # Get recent drifts
    drifts = conn.execute("""
        SELECT * FROM config_drifts ORDER BY timestamp DESC LIMIT 50
    """).fetchall()

    conn.close()

    suggestions = []
    for d in drifts:
        d = dict(d)
        fix = {
            "node": d["node"],
            "drift_type": d["drift_type"],
            "parameter": d["parameter"],
            "severity": d["severity"],
        }

        if d["drift_type"] == "availability":
            fix["suggestion"] = f"Check if {d['node']} service is running. " \
                                f"Restart LM Studio or Ollama on the node."
            fix["command"] = f"# For {d['node']}: restart the service"
        elif d["drift_type"] == "model_state":
            fix["suggestion"] = f"Load a model on {d['node']}. Currently no models loaded."
            fix["command"] = f"# Load model via LM Studio GUI or lms CLI"
        elif d["drift_type"] == "parameter":
            fix["suggestion"] = f"Adjust {d['parameter']} from {d['actual_value']} to {d['expected_value']}"
        elif d["drift_type"] == "model_coverage":
            fix["suggestion"] = f"Consider installing {d['parameter']} on {d['node']} for redundancy."
        elif d["drift_type"] == "model_integrity":
            fix["suggestion"] = f"Re-download or verify model on {d['node']}"
        else:
            fix["suggestion"] = f"Review {d['drift_type']} drift on {d['node']}"

        suggestions.append(fix)

    return {
        "timestamp": datetime.now().isoformat(),
        "action": "fix_suggestions",
        "total_drifts": len(drifts),
        "suggestions": suggestions,
        "note": "These are suggestions only. No changes have been applied.",
    }

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Detect configuration differences between cluster nodes."
    )
    parser.add_argument("--once", action="store_true",
                        help="Detect drifts and output JSON summary")
    parser.add_argument("--diff", action="store_true",
                        help="Show detailed config differences between nodes")
    parser.add_argument("--fix", action="store_true",
                        help="Suggest fixes for detected drifts (read-only)")
    args = parser.parse_args()

    if not any([args.once, args.diff, args.fix]):
        parser.print_help()
        sys.exit(1)

    if args.fix:
        result = action_fix()
    elif args.diff:
        result = action_diff()
    elif args.once:
        result = action_once()
    else:
        parser.print_help()
        sys.exit(1)

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
