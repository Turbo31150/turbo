#!/usr/bin/env python3
"""prompt_router.py — Route les prompts vers le meilleur modele du cluster.

Analyse le contenu du prompt et le dirige vers le noeud IA optimal:
M1 (code/math), OL1 (rapide), M2 (reasoning), M3 (fallback).

Usage:
    python dev/prompt_router.py --route "ecris une fonction python"
    python dev/prompt_router.py --benchmark "question test"
    python dev/prompt_router.py --stats
    python dev/prompt_router.py --nodes
"""
import argparse
import json
import re
import sqlite3
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "router.db"

# ---------------------------------------------------------------------------
# Cluster nodes
# ---------------------------------------------------------------------------
NODES = {
    "M1": {
        "url": "http://127.0.0.1:1234/api/v1/chat",
        "model": "qwen3-8b",
        "format": "lm_studio",
        "weight": 1.8,
        "specialties": ["code", "math", "reasoning"],
        "speed": "fast",
    },
    "OL1-fast": {
        "url": "http://127.0.0.1:11434/api/chat",
        "model": "qwen3:1.7b",
        "format": "ollama",
        "weight": 1.3,
        "specialties": ["simple", "quick"],
        "speed": "ultra_fast",
    },
    "M2": {
        "url": "http://192.168.1.26:1234/api/v1/chat",
        "model": "deepseek-r1-0528-qwen3-8b",
        "format": "lm_studio",
        "weight": 1.4,
        "specialties": ["debug", "review"],
        "speed": "medium",
    },
    "M3": {
        "url": "http://192.168.1.113:1234/api/v1/chat",
        "model": "deepseek-r1-0528-qwen3-8b",
        "format": "lm_studio",
        "weight": 0.8,
        "specialties": ["general", "validation"],
        "speed": "slow",
    },
    "M3": {
        "url": "http://192.168.1.113:1234/api/v1/chat",
        "model": "deepseek-r1-0528-qwen3-8b",
        "format": "lm_studio",
        "weight": 1.2,
        "specialties": ["reasoning", "general"],
        "speed": "slow",
    },
}

# ---------------------------------------------------------------------------
# Routing rules
# ---------------------------------------------------------------------------
ROUTING = {
    "code":      {"primary": "M1",      "secondary": "M2",      "reason": "Code: M1 champion local"},
    "debug":     {"primary": "M2",      "secondary": "M1",      "reason": "Debug: M2 deepseek-r1 reasoning"},
    "review":    {"primary": "M1",      "secondary": "M2",      "reason": "Review: M1 champion local"},
    "math":      {"primary": "M1",      "secondary": "OL1-fast","reason": "Math: M1 100% raisonnement"},
    "simple":    {"primary": "OL1-fast","secondary": "M1",      "reason": "Simple: OL1 ultra-rapide"},
    "archi":     {"primary": "M1",      "secondary": "M2",      "reason": "Architecture: M1 + M2 reasoning"},
    "security":  {"primary": "M1",      "secondary": "M2",      "reason": "Securite: M1 audit"},
    "general":   {"primary": "M1",      "secondary": "OL1-fast","reason": "General: M1 polyvalent"},
    "trading":   {"primary": "OL1-fast","secondary": "M1",      "reason": "Trading: OL1 rapide"},
}

KEYWORDS = {
    "code":     ["code", "python", "function", "classe", "script", "programme", "ecris", "genere", "implement"],
    "debug":    ["bug", "erreur", "fix", "debug", "crash", "traceback", "exception", "corrige"],
    "review":   ["review", "revue", "analyse", "audit", "qualite", "ameliore", "optimise"],
    "math":     ["calcul", "math", "equation", "nombre", "statistique", "probabilite", "formule"],
    "simple":   ["bonjour", "salut", "oui", "non", "ok", "merci", "comment ca va", "status"],
    "archi":    ["architecture", "design", "pattern", "structure", "schema", "diagramme"],
    "security": ["securite", "security", "vulnerability", "injection", "xss", "auth", "chiffrement"],
    "trading":  ["trading", "crypto", "bitcoin", "signal", "marche", "prix", "chart"],
}

def classify_prompt(text: str) -> str:
    """Classifie un prompt par categorie."""
    text_lower = text.lower()
    scores = {}
    for cat, keywords in KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[cat] = score
    if scores:
        return max(scores, key=scores.get)
    # Default by length
    if len(text) < 30:
        return "simple"
    return "general"

def route_prompt(text: str) -> dict:
    """Route un prompt vers le meilleur noeud."""
    category = classify_prompt(text)
    routing = ROUTING.get(category, ROUTING["general"])
    return {
        "category": category,
        "primary": routing["primary"],
        "secondary": routing["secondary"],
        "reason": routing["reason"],
        "node": NODES[routing["primary"]],
    }

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS routes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, prompt_preview TEXT, category TEXT,
        node TEXT, latency_ms INTEGER, success INTEGER,
        tokens_approx INTEGER)""")
    db.commit()
    return db

# ---------------------------------------------------------------------------
# Cluster call
# ---------------------------------------------------------------------------
def call_node(node_name: str, prompt: str) -> dict:
    """Appelle un noeud du cluster."""
    node = NODES.get(node_name)
    if not node:
        return {"error": f"Noeud inconnu: {node_name}"}

    start = time.time()
    try:
        if node["format"] == "lm_studio":
            data = json.dumps({
                "model": node["model"],
                "input": f"/nothink\n{prompt}",
                "temperature": 0.2,
                "max_output_tokens": 2048,
                "stream": False,
                "store": False,
            }).encode()
        else:  # ollama
            data = json.dumps({
                "model": node["model"],
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "think": False,
            }).encode()

        req = urllib.request.Request(node["url"], data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode())
            latency = int((time.time() - start) * 1000)

            if node["format"] == "lm_studio":
                for block in reversed(result.get("output", [])):
                    if block.get("type") == "message":
                        for c in block.get("content", []):
                            if c.get("type") == "output_text":
                                return {"content": c["text"], "node": node_name, "latency_ms": latency}
                return {"content": str(result), "node": node_name, "latency_ms": latency}
            else:
                return {
                    "content": result.get("message", {}).get("content", ""),
                    "node": node_name,
                    "latency_ms": latency,
                }
    except Exception as e:
        return {"error": str(e), "node": node_name, "latency_ms": int((time.time() - start) * 1000)}

def route_and_call(prompt: str, db) -> dict:
    """Route + appelle le meilleur noeud."""
    routing = route_prompt(prompt)
    result = call_node(routing["primary"], prompt)

    # Fallback if error
    if "error" in result:
        result = call_node(routing["secondary"], prompt)

    # Log
    db.execute(
        "INSERT INTO routes (ts, prompt_preview, category, node, latency_ms, success, tokens_approx) VALUES (?,?,?,?,?,?,?)",
        (time.time(), prompt[:100], routing["category"], result.get("node", "unknown"),
         result.get("latency_ms", 0), 0 if "error" in result else 1,
         len(result.get("content", "")) // 4)
    )
    db.commit()

    result["category"] = routing["category"]
    result["reason"] = routing["reason"]
    return result

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="JARVIS Prompt Router — Routage intelligent vers le cluster")
    parser.add_argument("--route", type=str, help="Router et executer un prompt")
    parser.add_argument("--classify", type=str, help="Classifier sans executer")
    parser.add_argument("--benchmark", type=str, help="Tester sur tous les noeuds")
    parser.add_argument("--stats", action="store_true", help="Statistiques de routage")
    parser.add_argument("--nodes", action="store_true", help="Info sur les noeuds")
    args = parser.parse_args()

    db = init_db()

    if args.nodes:
        output = {}
        for name, node in NODES.items():
            output[name] = {
                "model": node["model"],
                "weight": node["weight"],
                "specialties": node["specialties"],
                "speed": node["speed"],
            }
        print(json.dumps(output, indent=2, ensure_ascii=False))
    elif args.classify:
        routing = route_prompt(args.classify)
        print(json.dumps(routing, indent=2, ensure_ascii=False))
    elif args.route:
        result = route_and_call(args.route, db)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.benchmark:
        results = []
        for name in ["M1", "OL1-fast", "M2", "M3"]:
            r = call_node(name, args.benchmark)
            results.append({
                "node": name,
                "latency_ms": r.get("latency_ms", 0),
                "ok": "error" not in r,
                "content_preview": r.get("content", r.get("error", ""))[:100],
            })
        results.sort(key=lambda x: x["latency_ms"])
        print(json.dumps({"prompt": args.benchmark[:50], "results": results}, indent=2, ensure_ascii=False))
    elif args.stats:
        total = db.execute("SELECT COUNT(*) FROM routes").fetchone()[0]
        by_node = db.execute("SELECT node, COUNT(*), AVG(latency_ms) FROM routes GROUP BY node ORDER BY 2 DESC").fetchall()
        by_cat = db.execute("SELECT category, COUNT(*) FROM routes GROUP BY category ORDER BY 2 DESC").fetchall()
        print(json.dumps({
            "total_routes": total,
            "by_node": {n: {"count": c, "avg_latency_ms": round(l)} for n, c, l in by_node},
            "by_category": {c: n for c, n in by_cat},
        }, indent=2, ensure_ascii=False))
    else:
        parser.print_help()

    db.close()

if __name__ == "__main__":
    main()
