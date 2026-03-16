"""
M3 BRIDGE — Client pour piloter M3 (JARVIS-CLUSTER) depuis M1.
Adapte de github.com/Turbo31150/JARVIS-CLUSTER/m1-bridge/m1_client.py
pour le cluster turbo existant (httpx, asyncio, FastAPI integration).

M3 = HP Z4 G4, Xeon W-2123, 32GB, GTX 1660 SUPER 6GB
     deepseek-r1-0528-qwen3-8b @ 31.7 t/s
     API JARVIS-CLUSTER :8765 (FastAPI REST + WebSocket)
     LM Studio :1234 (inference directe)
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("M3-Bridge")

# ─── Configuration ────────────────────────────────────────────────────────────

M3_HOST = "192.168.1.113"
M3_API_PORT = 8765
M3_LMS_PORT = 1234

M2_HOST = "192.168.1.26"
M2_LMS_PORT = 1234

CLUSTER_NODES = {
    "M1": {"host": "127.0.0.1", "lms_port": 1234, "role": "master", "model": "qwen3-8b"},
    "M2": {"host": M2_HOST, "lms_port": M2_LMS_PORT, "role": "worker", "model": "deepseek-r1-0528-qwen3-8b"},
    "M3": {"host": M3_HOST, "lms_port": M3_LMS_PORT, "api_port": M3_API_PORT, "role": "worker", "model": "deepseek-r1-0528-qwen3-8b"},
    "OL1": {"host": "127.0.0.1", "port": 11434, "role": "fast", "model": "qwen3:1.7b"},
}

TIMEOUT = httpx.Timeout(30.0, connect=5.0)


# ─── M3 Client (JARVIS-CLUSTER API :8765) ────────────────────────────────────

class M3Client:
    """Client REST pour l'API JARVIS-CLUSTER sur M3 (port 8765)."""

    def __init__(self, host: str = M3_HOST, port: int = M3_API_PORT):
        self.base_url = f"http://{host}:{port}"
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=TIMEOUT)
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ── REST Endpoints ────────────────────────────────────────────────────────

    async def get_status(self) -> Dict:
        """Status complet de M3."""
        c = await self._get_client()
        r = await c.get("/status")
        r.raise_for_status()
        return r.json()

    async def health(self) -> Dict:
        """Health check rapide."""
        c = await self._get_client()
        r = await c.get("/health")
        r.raise_for_status()
        return r.json()

    async def send_task(self, description: str, priority: int = 1) -> Dict:
        """Envoyer une tache a M3 pour execution via le workflow 4-stage."""
        c = await self._get_client()
        r = await c.post("/task", json={
            "description": description,
            "source": "M1",
            "priority": priority,
        })
        r.raise_for_status()
        return r.json()

    async def get_task(self, task_id: str) -> Dict:
        """Status d'une tache specifique."""
        c = await self._get_client()
        r = await c.get(f"/task/{task_id}")
        r.raise_for_status()
        return r.json()

    async def list_tasks(self) -> Dict:
        """Lister toutes les taches."""
        c = await self._get_client()
        r = await c.get("/tasks")
        r.raise_for_status()
        return r.json()

    async def execute_command(self, command: str, params: Optional[dict] = None) -> Dict:
        """Executer une commande directe sur M3."""
        c = await self._get_client()
        r = await c.post("/command", json={
            "command": command,
            "params": params or {},
            "target_node": "M3",
        })
        r.raise_for_status()
        return r.json()

    async def call_mcp_tool(self, tool_name: str, params: Optional[dict] = None) -> Dict:
        """Appeler un outil MCP trading sur M3."""
        c = await self._get_client()
        r = await c.post(f"/mcp/{tool_name}", json=params or {})
        r.raise_for_status()
        return r.json()

    async def get_cluster_info(self) -> Dict:
        """Info cluster vue depuis M3."""
        c = await self._get_client()
        r = await c.get("/cluster")
        r.raise_for_status()
        return r.json()

    # ── High-Level Trading Commands ───────────────────────────────────────────

    async def scan_mexc(self) -> Dict:
        """Scanner MEXC Futures via MCP sur M3."""
        return await self.call_mcp_tool("scan_mexc")

    async def get_positions(self) -> Dict:
        """Positions ouvertes."""
        return await self.call_mcp_tool("get_positions")

    async def check_margins(self) -> Dict:
        """Verifier les marges."""
        return await self.call_mcp_tool("check_margins")

    async def run_consensus(self, query: str) -> Dict:
        """Consensus Multi-IA sur M3 (deepseek-r1 + phi + cloud models)."""
        return await self.send_task(f"Consensus Multi-IA: {query}")

    async def send_telegram_alert(self, message: str) -> Dict:
        """Envoyer alerte Telegram via M3."""
        return await self.call_mcp_tool("send_telegram", {"message": message})


# ─── Cluster Manager (pilote TOUS les nodes depuis M1) ───────────────────────

class ClusterBridge:
    """
    Gestionnaire centralise — pilote M3 via API :8765
    et M2/M3 via LM Studio :1234 pour l'inference directe.
    """

    def __init__(self):
        self.m3 = M3Client()
        self._http: Optional[httpx.AsyncClient] = None

    async def _get_http(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=TIMEOUT)
        return self._http

    async def close(self):
        await self.m3.close()
        if self._http and not self._http.is_closed:
            await self._http.aclose()

    # ── Health ────────────────────────────────────────────────────────────────

    async def health_all(self) -> Dict[str, Dict]:
        """Health check de tous les nodes en parallele."""
        results = {}

        async def check_lms(node_id: str, host: str, port: int):
            try:
                c = await self._get_http()
                r = await c.get(f"http://{host}:{port}/api/v1/models", timeout=5.0)
                data = r.json()
                loaded = [m["id"] for m in data.get("data", data.get("models", [])) if m.get("loaded_instances")]
                results[node_id] = {"status": "online", "models": loaded, "latency_ms": r.elapsed.total_seconds() * 1000}
            except Exception as e:
                results[node_id] = {"status": "offline", "error": str(e)}

        async def check_ollama(node_id: str, host: str, port: int):
            try:
                c = await self._get_http()
                r = await c.get(f"http://{host}:{port}/api/tags", timeout=5.0)
                models = [m["name"] for m in r.json().get("models", [])]
                results[node_id] = {"status": "online", "models": models, "latency_ms": r.elapsed.total_seconds() * 1000}
            except Exception as e:
                results[node_id] = {"status": "offline", "error": str(e)}

        async def check_m3_api():
            try:
                data = await self.m3.health()
                results["M3-API"] = {"status": "online", **data}
            except Exception as e:
                results["M3-API"] = {"status": "offline", "error": str(e)}

        await asyncio.gather(
            check_lms("M1", "127.0.0.1", 1234),
            check_lms("M2", M2_HOST, M2_LMS_PORT),
            check_lms("M3", M3_HOST, M3_LMS_PORT),
            check_ollama("OL1", "127.0.0.1", 11434),
            check_m3_api(),
            return_exceptions=True,
        )
        return results

    # ── Inference directe LM Studio ───────────────────────────────────────────

    async def query_node(self, node_id: str, prompt: str, max_tokens: int = 512, temperature: float = 0.3) -> Dict:
        """Query un node LM Studio directement (bypass M3 API)."""
        cfg = CLUSTER_NODES.get(node_id)
        if not cfg:
            return {"error": f"Node {node_id} inconnu"}

        c = await self._get_http()
        host = cfg["host"]
        port = cfg.get("lms_port", cfg.get("port", 1234))

        if node_id == "OL1":
            # Ollama
            r = await c.post(f"http://{host}:{port}/api/chat", json={
                "model": cfg["model"],
                "messages": [{"role": "user", "content": prompt}],
                "stream": False, "think": False,
                "options": {"num_predict": max_tokens},
            })
            data = r.json()
            return {"text": data.get("message", {}).get("content", ""), "node": node_id, "model": cfg["model"]}
        else:
            # LM Studio
            nothink = "" if "deepseek" in cfg["model"] else "/nothink\n"
            r = await c.post(f"http://{host}:{port}/api/v1/chat", json={
                "model": cfg["model"],
                "input": f"{nothink}{prompt}",
                "temperature": temperature,
                "max_output_tokens": max_tokens,
                "stream": False, "store": False,
            })
            data = r.json()
            # Extract message content (skip reasoning blocks)
            for o in reversed(data.get("output", [])):
                if o.get("type") == "message":
                    content = o.get("content", "")
                    if isinstance(content, list):
                        content = content[0].get("text", "") if content else ""
                    return {"text": content, "node": node_id, "model": cfg["model"]}
            return {"text": "", "node": node_id, "model": cfg["model"], "error": "no message block"}

    # ── Task dispatch via M3 API ──────────────────────────────────────────────

    async def dispatch_to_m3(self, description: str, priority: int = 1) -> Dict:
        """Envoyer une tache au workflow 4-stage de M3."""
        try:
            return await self.m3.send_task(description, priority)
        except Exception as e:
            logger.error(f"M3 dispatch failed: {e}")
            return {"error": str(e)}

    async def consensus(self, query: str) -> Dict:
        """Consensus Multi-IA via M3 (4-stage workflow)."""
        try:
            return await self.m3.run_consensus(query)
        except Exception as e:
            logger.error(f"M3 consensus failed: {e}")
            return {"error": str(e)}


# ─── Singleton ────────────────────────────────────────────────────────────────

_bridge: Optional[ClusterBridge] = None


def get_bridge() -> ClusterBridge:
    """Singleton global du bridge cluster."""
    global _bridge
    if _bridge is None:
        _bridge = ClusterBridge()
    return _bridge
