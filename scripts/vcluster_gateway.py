
import asyncio
import httpx
import time
import os
import json
import logging

# Configuration des nœuds
NODES = {
    "M1": {"url": "http://127.0.0.1:1234", "type": "lmstudio", "priority": 1},
    "OL1": {"url": "http://127.0.0.1:11434", "type": "ollama", "priority": 2},
    "M2": {"url": "http://192.168.1.26:1234", "type": "lmstudio", "priority": 3},
}

class VClusterGateway:
    def __init__(self):
        self.active_nodes = {}
        self.logger = logging.getLogger("jarvis.vcluster")

    async def check_node(self, name, info):
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                path = "/api/v1/models" if info["type"] == "lmstudio" else "/api/tags"
                resp = await client.get(info["url"] + path)
                if resp.status_code == 200:
                    return name, True
        except:
            pass
        return name, False

    async def refresh_topology(self):
        tasks = [self.check_node(name, info) for name, info in NODES.items()]
        results = await asyncio.gather(*tasks)
        self.active_nodes = {name: NODES[name] for name, status in results if status}
        print(f"[VCLUSTER] Topology refreshed: {list(self.active_nodes.keys())}")

    async def query(self, prompt, model=None, task="general"):
        if not self.active_nodes:
            await self.refresh_topology()
        
        # Pick best node (simplifié: premier actif par priorité)
        sorted_nodes = sorted(self.active_nodes.items(), key=lambda x: x[1]["priority"])
        if not sorted_nodes:
            return {"error": "No nodes online"}
        
        node_name, node_info = sorted_nodes[0]
        print(f"[VCLUSTER] Routing to {node_name} ({node_info['type']})")
        
        # Forwarding logic (placeholder for full OpenAI/Ollama proxy)
        return {"node": node_name, "status": "routed"}

if __name__ == "__main__":
    gw = VClusterGateway()
    asyncio.run(gw.refresh_topology())
