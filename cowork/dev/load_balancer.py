#!/usr/bin/env python3
"""load_balancer.py

Batch 4.2 – Répartiteur de charge intelligent pour le cluster.

Fonctionnalités :
* **Benchmark** (`--once`) : mesure la latence (temps de connexion + temps de réponse) de chaque nœud
  (M1 127.0.0.1:1234, M2 192.168.1.26:1234, OL1 127.0.0.1:11434).
* **Routing** (`--route "prompt"`) : en fonction du benchmark le plus récent, sélectionne le nœud
  optimal selon un facteur de poids :
  * M1 = 1.8
  * M2 = 1.4
  * OL1 = 1.3
* Utilise uniquement la bibliothèque standard : `urllib.request`, `json`, `time`, `argparse`.

Usage :
    python load_balancer.py --once
    python load_balancer.py --route "Quel est le prix du Bitcoin ?"
"""

import argparse
import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, Tuple

# Configuration des nœuds
NODES = {
    "M1": {"host": "127.0.0.1", "port": 1234, "weight": 1.8, "type": "lmstudio", "model": "qwen3-8b"},
    "M2": {"host": "192.168.1.26", "port": 1234, "weight": 1.4, "type": "lmstudio", "model": "deepseek-coder-v2-lite-instruct"},
    "OL1": {"host": "127.0.0.1", "port": 11434, "weight": 1.3, "type": "ollama", "model": "qwen3:1.7b"},
}

def _ping_payload(node: Dict) -> bytes:
    if node["type"] == "ollama":
        return json.dumps({"model": node["model"], "messages": [{"role": "user", "content": "ping"}], "stream": False}).encode()
    return json.dumps({"model": node["model"], "input": "/nothink\nping", "max_output_tokens": 5, "stream": False, "store": False}).encode()

def _url(node: Dict) -> str:
    if node["type"] == "ollama":
        return f"http://{node['host']}:{node['port']}/api/chat"
    return f"http://{node['host']}:{node['port']}/api/v1/chat"

def measure_node(node_name: str, config: Dict) -> Tuple[float, int]:
    """Mesure la latence (en ms) et la taille de la réponse (bytes).
    Retourne (latency_ms, response_bytes).
    """
    url = _url(config)
    payload = _ping_payload(config)
    start = time.time()
    try:
        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = resp.read()
    except Exception as e:
        # En cas d'erreur, on renvoie une latence très élevée
        print(f"[load_balancer] {node_name} unreachable: {e}")
        return (float('inf'), 0)
    latency_ms = (time.time() - start) * 1000.0
    return (latency_ms, len(data))

def benchmark() -> Dict[str, Dict[str, float]]:
    """Effectue le benchmark sur tous les nœuds et renvoie un dict avec latence et taille.
    """
    results = {}
    for name, cfg in NODES.items():
        latency, size = measure_node(name, cfg)
        results[name] = {"latency_ms": latency, "response_bytes": size}
        print(f"[load_balancer] {name}: latency={latency:.1f} ms, size={size} B")
    return results

def choose_best_node(benchmark_data: Dict[str, Dict[str, float]]) -> str:
    """Choisit le nœud optimal selon le poids et la latence.
    Score = latency_ms / weight (plus petit = meilleur).
    """
    best_node = None
    best_score = float('inf')
    for name, metrics in benchmark_data.items():
        weight = NODES[name]["weight"]
        latency = metrics["latency_ms"]
        if latency == float('inf'):
            continue  # nœud indisponible
        score = latency / weight
        if score < best_score:
            best_score = score
            best_node = name
    return best_node

def route_prompt(prompt: str, benchmark_data: Dict[str, Dict[str, float]]) -> None:
    """Envoie le prompt au nœud choisi et affiche la réponse brute.
    """
    node = choose_best_node(benchmark_data)
    if not node:
        print("[load_balancer] Aucun nœud disponible pour le routing.")
        return
    cfg = NODES[node]
    url = _url(cfg)
    if cfg["type"] == "ollama":
        payload = json.dumps({"model": cfg["model"], "messages": [{"role": "user", "content": prompt}], "stream": False}).encode()
    else:
        payload = json.dumps({"model": cfg["model"], "input": f"/nothink\n{prompt}", "max_output_tokens": 256, "stream": False, "store": False}).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            answer = resp.read().decode("utf-8")
        print(f"[load_balancer] Prompt routé vers {node} (weight={cfg['weight']})")
        print(answer)
    except Exception as e:
        print(f"[load_balancer] Erreur lors du routage vers {node}: {e}")

def main():
    parser = argparse.ArgumentParser(description="Load balancer intelligent pour le cluster IA")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--once", action="store_true", help="Effectuer le benchmark (latence) une fois")
    group.add_argument("--route", metavar="PROMPT", help="Routage du prompt vers le nœud optimal")
    args = parser.parse_args()

    if args.once:
        benchmark()
    else:
        # Benchmark préalable pour disposer de données fraîches
        data = benchmark()
        route_prompt(args.route, data)

if __name__ == "__main__":
    main()
