#!/usr/bin/env python3
"""model_health_checker.py

Deep health check of loaded models on the JARVIS cluster.

Fonctionnalites :
* Verifie chaque noeud cluster (M1, M2, M3, OL1) — pas juste un ping
  mais une inference reelle avec un prompt de test
* Mesure le temps de reponse, le debit (tokens/sec), la qualite de sortie
* Detecte les modeles charges, leur taille memoire
* Enregistre les resultats dans SQLite (cowork_gaps.db)
* Produit un rapport JSON

CLI :
    --once      : check tous les noeuds et affiche le resume JSON
    --node M1   : check un noeud specifique (M1, M2, M3, OL1)
    --all       : check detaille de tous les noeuds avec inference

Stdlib-only (urllib, sqlite3, json, argparse, time).
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

TEST_PROMPT = "Reply with exactly: OK HEALTHY. Nothing else."
TEST_PROMPT_QUALITY = "What is 7 * 8? Reply with just the number."

NODES = {
    "M1": {
        "name": "M1",
        "host": "127.0.0.1",
        "port": 1234,
        "type": "lmstudio",
        "models_url": "http://127.0.0.1:1234/api/v1/models",
        "chat_url": "http://127.0.0.1:1234/api/v1/chat",
        "model_id": "qwen3-8b",
        "timeout": 15,
    },
    "M2": {
        "name": "M2",
        "host": "192.168.1.26",
        "port": 1234,
        "type": "lmstudio",
        "models_url": "http://192.168.1.26:1234/api/v1/models",
        "chat_url": "http://192.168.1.26:1234/api/v1/chat",
        "model_id": "deepseek-coder-v2-lite-instruct",
        "timeout": 30,
    },
    "M3": {
        "name": "M3",
        "host": "192.168.1.113",
        "port": 1234,
        "type": "lmstudio",
        "models_url": "http://192.168.1.113:1234/api/v1/models",
        "chat_url": "http://192.168.1.113:1234/api/v1/chat",
        "model_id": "mistral-7b-instruct-v0.3",
        "timeout": 30,
    },
    "OL1": {
        "name": "OL1",
        "host": "127.0.0.1",
        "port": 11434,
        "type": "ollama",
        "models_url": "http://127.0.0.1:11434/api/tags",
        "chat_url": "http://127.0.0.1:11434/api/chat",
        "model_id": "qwen3:1.7b",
        "timeout": 15,
    },
}

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
def init_db(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS model_health_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            node TEXT NOT NULL,
            status TEXT NOT NULL,
            ping_ms INTEGER,
            inference_ms INTEGER,
            tokens_per_sec REAL,
            response_text TEXT,
            quality_score INTEGER,
            models_loaded INTEGER,
            error TEXT
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
def http_request(url: str, data: dict | None = None, timeout: int = 10) -> tuple:
    """Make an HTTP request. Returns (status_code, response_dict, elapsed_ms)."""
    start = time.time()
    try:
        if data is not None:
            body = json.dumps(data).encode("utf-8")
            req = urllib.request.Request(
                url, data=body,
                headers={"Content-Type": "application/json"}
            )
        else:
            req = urllib.request.Request(url)

        with urllib.request.urlopen(req, timeout=timeout) as resp:
            elapsed = int((time.time() - start) * 1000)
            raw = resp.read().decode("utf-8")
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = {"raw": raw}
            return resp.status, parsed, elapsed
    except urllib.error.HTTPError as e:
        elapsed = int((time.time() - start) * 1000)
        return e.code, {"error": str(e)}, elapsed
    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        return 0, {"error": str(e)}, elapsed

# ---------------------------------------------------------------------------
# Node Checks
# ---------------------------------------------------------------------------
def check_models_loaded(node: dict) -> dict:
    """Check how many models are loaded on a node."""
    status, resp, elapsed = http_request(node["models_url"], timeout=5)
    if status != 200:
        return {"loaded": 0, "models": [], "ping_ms": elapsed, "error": resp.get("error", "unreachable")}

    if node["type"] == "lmstudio":
        models = resp.get("data", resp.get("models", []))
        loaded = [m for m in models if m.get("loaded_instances")]
        return {
            "loaded": len(loaded),
            "models": [m.get("id", "unknown") for m in loaded],
            "total_available": len(models),
            "ping_ms": elapsed,
        }
    elif node["type"] == "ollama":
        models = resp.get("models", [])
        return {
            "loaded": len(models),
            "models": [m.get("name", "unknown") for m in models],
            "ping_ms": elapsed,
        }
    return {"loaded": 0, "models": [], "ping_ms": elapsed}


def run_inference(node: dict, prompt: str) -> dict:
    """Run actual inference on a node and measure performance."""
    if node["type"] == "lmstudio":
        payload = {
            "model": node["model_id"],
            "input": f"/nothink\n{prompt}",
            "temperature": 0.1,
            "max_output_tokens": 64,
            "stream": False,
            "store": False,
        }
    elif node["type"] == "ollama":
        payload = {
            "model": node["model_id"],
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "think": False,
        }
    else:
        return {"error": f"Unknown node type: {node['type']}"}

    status, resp, elapsed = http_request(node["chat_url"], payload, timeout=node["timeout"])

    if status != 200:
        return {
            "status": "error",
            "inference_ms": elapsed,
            "error": resp.get("error", f"HTTP {status}"),
        }

    # Extract response text
    text = ""
    tokens = 0
    if node["type"] == "lmstudio":
        output_list = resp.get("output", [])
        for block in reversed(output_list):
            if block.get("type") == "message":
                for content in block.get("content", []):
                    text = content.get("text", "")
                    break
                break
        usage = resp.get("usage", {})
        tokens = usage.get("output_tokens", len(text.split()))
    elif node["type"] == "ollama":
        text = resp.get("message", {}).get("content", "")
        tokens = resp.get("eval_count", len(text.split()))

    tps = tokens / (elapsed / 1000.0) if elapsed > 0 else 0

    return {
        "status": "ok",
        "inference_ms": elapsed,
        "response_text": text.strip()[:200],
        "tokens": tokens,
        "tokens_per_sec": round(tps, 1),
    }


def assess_quality(response_text: str) -> int:
    """Score response quality 0-100 based on the math test."""
    text = response_text.strip().lower()
    # The expected answer is 56
    if "56" in text:
        return 100
    # Partial credit if it's a number
    try:
        num = int("".join(c for c in text if c.isdigit())[:5])
        if num == 56:
            return 100
        return 30
    except (ValueError, IndexError):
        return 0


def check_node(node_name: str) -> dict:
    """Perform a full health check on a single node."""
    if node_name not in NODES:
        return {"node": node_name, "status": "unknown", "error": f"Unknown node: {node_name}"}

    node = NODES[node_name]
    result = {
        "node": node_name,
        "endpoint": f"{node['host']}:{node['port']}",
        "type": node["type"],
        "timestamp": datetime.now().isoformat(),
    }

    # Step 1: Check models loaded
    models_info = check_models_loaded(node)
    result["models"] = models_info

    if models_info.get("error"):
        result["status"] = "offline"
        result["error"] = models_info["error"]
        result["ping_ms"] = models_info.get("ping_ms", 0)
        return result

    result["ping_ms"] = models_info["ping_ms"]

    # Step 2: Run inference test
    inference = run_inference(node, TEST_PROMPT)
    result["inference"] = inference

    if inference.get("status") == "error":
        result["status"] = "degraded"
        result["error"] = inference.get("error", "inference failed")
        return result

    # Step 3: Quality check (math test)
    quality_inference = run_inference(node, TEST_PROMPT_QUALITY)
    quality_score = 0
    if quality_inference.get("status") == "ok":
        quality_score = assess_quality(quality_inference.get("response_text", ""))
    result["quality_score"] = quality_score
    result["quality_response"] = quality_inference.get("response_text", "")

    # Step 4: Overall status
    tps = inference.get("tokens_per_sec", 0)
    latency = inference.get("inference_ms", 99999)

    if tps > 10 and quality_score >= 50 and latency < 10000:
        result["status"] = "healthy"
    elif tps > 1 and latency < 30000:
        result["status"] = "slow"
    else:
        result["status"] = "degraded"

    result["inference_ms"] = latency
    result["tokens_per_sec"] = tps

    return result

# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------
def action_check(node_name: str | None = None, all_nodes: bool = False) -> dict:
    """Run health checks and persist results."""
    conn = get_db()
    targets = list(NODES.keys()) if (all_nodes or node_name is None) else [node_name.upper()]

    results = {
        "timestamp": datetime.now().isoformat(),
        "action": "health_check",
        "nodes": {},
        "summary": {"healthy": 0, "slow": 0, "degraded": 0, "offline": 0},
    }

    for name in targets:
        check = check_node(name)
        results["nodes"][name] = check
        status = check.get("status", "unknown")
        if status in results["summary"]:
            results["summary"][status] += 1

        # Persist to DB
        conn.execute("""
            INSERT INTO model_health_checks
            (timestamp, node, status, ping_ms, inference_ms, tokens_per_sec,
             response_text, quality_score, models_loaded, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            check["timestamp"],
            name,
            status,
            check.get("ping_ms"),
            check.get("inference_ms"),
            check.get("tokens_per_sec"),
            check.get("inference", {}).get("response_text"),
            check.get("quality_score"),
            check.get("models", {}).get("loaded"),
            check.get("error"),
        ))

    conn.commit()
    conn.close()

    total = len(targets)
    healthy = results["summary"]["healthy"]
    results["summary"]["total"] = total
    results["summary"]["health_pct"] = round(healthy / max(total, 1) * 100, 1)

    return results

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Deep health check of loaded models on the JARVIS cluster."
    )
    parser.add_argument("--once", action="store_true",
                        help="Check all nodes and output JSON summary")
    parser.add_argument("--node", type=str, choices=["M1", "M2", "M3", "OL1"],
                        help="Check a specific node")
    parser.add_argument("--all", action="store_true",
                        help="Detailed check of all nodes with inference test")
    args = parser.parse_args()

    if not any([args.once, args.node, args.all]):
        parser.print_help()
        sys.exit(1)

    if args.node:
        result = action_check(node_name=args.node)
    elif args.all:
        result = action_check(all_nodes=True)
    elif args.once:
        result = action_check(all_nodes=True)
    else:
        parser.print_help()
        sys.exit(1)

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
