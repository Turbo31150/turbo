"""JARVIS Dashboard Server — Cluster monitoring en temps reel.

Serveur HTTP Python (stdlib only, zero dependance externe).
Sert le dashboard HTML + proxy les appels API vers M1/M2/OL1.

Usage: uv run python dashboard/server.py
URL:   http://127.0.0.1:8080
"""

import http.server
import json
import os
import threading
import time
import urllib.request
import urllib.error
from pathlib import Path

PORT = 8080
DASHBOARD_DIR = Path(__file__).parent

# Config cluster — IP directes, PAS localhost
AGENTS = {
    "M1": {
        "url": "http://10.5.0.2:1234",
        "api_key": "sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7",
        "type": "lm_studio",
        "model": "qwen/qwen3-8b",
        "role": "Rapide + analyse",
        "gpus": 6, "vram_gb": 46,
    },
    "M2": {
        "url": "http://192.168.1.26:1234",
        "api_key": "sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4",
        "type": "lm_studio",
        "model": "deepseek-coder-v2-lite-instruct",
        "role": "Code rapide",
        "gpus": 3, "vram_gb": 24,
    },
    "OL1": {
        "url": "http://127.0.0.1:11434",
        "api_key": None,
        "type": "ollama",
        "model": "qwen3:1.7b",
        "role": "Taches legeres + cloud",
        "gpus": 0, "vram_gb": 0,
    },
}

# Cache des resultats (mis a jour en background)
_cluster_state = {"agents": {}, "last_update": 0}
_state_lock = threading.Lock()


def _check_lm_studio(name: str, agent: dict) -> dict:
    """Check un noeud LM Studio."""
    result = {
        "name": name, "status": "offline", "models": [],
        "model_count": 0, "latency_ms": 0,
        "type": agent["type"], "role": agent["role"],
        "default_model": agent["model"],
        "gpus": agent["gpus"], "vram_gb": agent["vram_gb"],
    }
    try:
        start = time.time()
        req = urllib.request.Request(
            f"{agent['url']}/api/v1/models",
            headers={"Authorization": f"Bearer {agent['api_key']}"},
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
            latency = int((time.time() - start) * 1000)
            models = [m.get("key", "?") for m in data.get("models", []) if m.get("loaded_instances")]
            result.update({
                "status": "online",
                "models": models,
                "model_count": len(models),
                "latency_ms": latency,
            })
    except Exception:
        pass
    return result


def _check_ollama(name: str, agent: dict) -> dict:
    """Check un noeud Ollama."""
    result = {
        "name": name, "status": "offline", "models": [],
        "model_count": 0, "latency_ms": 0,
        "type": agent["type"], "role": agent["role"],
        "default_model": agent["model"],
        "gpus": agent["gpus"], "vram_gb": agent["vram_gb"],
    }
    try:
        start = time.time()
        req = urllib.request.Request(f"{agent['url']}/api/tags")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
            latency = int((time.time() - start) * 1000)
            models = [m.get("name", "?") for m in data.get("models", [])]
            result.update({
                "status": "online",
                "models": models,
                "model_count": len(models),
                "latency_ms": latency,
            })
    except Exception:
        pass
    return result


def _update_cluster_state():
    """Background thread: poll tous les agents toutes les 5s."""
    while True:
        agents = {}
        for name, agent in AGENTS.items():
            if agent["type"] == "ollama":
                agents[name] = _check_ollama(name, agent)
            else:
                agents[name] = _check_lm_studio(name, agent)

        with _state_lock:
            _cluster_state["agents"] = agents
            _cluster_state["last_update"] = time.time()

        time.sleep(5)


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    """Handler HTTP: sert les fichiers statiques + API JSON."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DASHBOARD_DIR), **kwargs)

    def do_GET(self):
        if self.path == "/api/cluster":
            self._send_json()
        elif self.path == "/" or self.path == "":
            self.path = "/index.html"
            super().do_GET()
        else:
            super().do_GET()

    def _send_json(self):
        with _state_lock:
            data = json.dumps(_cluster_state, ensure_ascii=False)
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data.encode("utf-8"))

    def log_message(self, format, *args):
        pass  # Silencieux


def main():
    # Lancer le polling en background
    t = threading.Thread(target=_update_cluster_state, daemon=True)
    t.start()

    # Premier poll immediat
    time.sleep(1)

    server = http.server.HTTPServer(("127.0.0.1", PORT), DashboardHandler)
    print(f"JARVIS Dashboard: http://127.0.0.1:{PORT}")
    print(f"API Cluster:      http://127.0.0.1:{PORT}/api/cluster")
    print("Ctrl+C pour arreter")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard arrete.")
        server.server_close()


if __name__ == "__main__":
    main()
