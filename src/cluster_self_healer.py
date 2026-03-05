"""JARVIS Cluster Self-Healer — Automatic node recovery and failover.

When a cluster node goes down, the self-healer:
1. Detects the failure via health probes or event bus
2. Attempts restart (LM Studio / Ollama)
3. Reroutes traffic to healthy nodes
4. Escalates if recovery fails after N attempts

Usage:
    from src.cluster_self_healer import cluster_healer
    await cluster_healer.handle_node_failure("M1")
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jarvis.self_healer")


@dataclass
class RecoveryAttempt:
    """Record of a recovery attempt."""
    node: str
    action: str
    success: bool
    duration_ms: float
    error: str = ""
    ts: float = field(default_factory=time.time)


@dataclass
class NodeConfig:
    """Configuration for a known cluster node."""
    name: str
    node_type: str  # "lm_studio" | "ollama" | "remote"
    url: str
    restart_command: str | None = None
    max_retries: int = 3
    retry_delay_s: float = 30.0


NODE_CONFIGS: dict[str, NodeConfig] = {
    "M1": NodeConfig(
        name="M1", node_type="lm_studio",
        url="http://localhost:1234",
        restart_command='Start-Process "C:\\Program Files\\LM Studio\\LM Studio.exe" -WindowStyle Minimized',
        max_retries=3, retry_delay_s=30.0
    ),
    "ollama": NodeConfig(
        name="ollama", node_type="ollama",
        url="http://localhost:11434",
        restart_command="ollama serve",
        max_retries=3, retry_delay_s=15.0
    ),
    "ollama_cloud": NodeConfig(
        name="ollama_cloud", node_type="remote",
        url="https://api.ollama.com",
        max_retries=2, retry_delay_s=60.0
    ),
    "gemini": NodeConfig(
        name="gemini", node_type="remote",
        url="https://generativelanguage.googleapis.com",
        max_retries=2, retry_delay_s=60.0
    ),
}


class ClusterSelfHealer:
    """Automatic cluster recovery system."""
    
    def __init__(self):
        self.recovery_history: list[RecoveryAttempt] = []
        self._max_history = 200
        self._active_recoveries: set[str] = set()
        self.stats = {
            "total_recoveries": 0, "successful": 0, "failed": 0,
            "nodes_restarted": 0, "traffic_rerouted": 0
        }
    
    async def handle_node_failure(self, node: str, error: str = "") -> dict[str, Any]:
        """Handle a node failure: attempt recovery then reroute."""
        if node in self._active_recoveries:
            return {"status": "already_recovering", "node": node}
        
        self._active_recoveries.add(node)
        start = time.time()
        result: dict[str, Any] = {"node": node, "actions": [], "recovered": False}
        
        try:
            config = NODE_CONFIGS.get(node)
            if not config:
                logger.warning(f"Unknown node {node}, only rerouting")
                await self._reroute_traffic(node)
                result["actions"].append("rerouted (unknown node)")
                return result
            
            logger.warning(f"=== Recovery started for {node} ===")
            
            # Step 1: Reroute traffic immediately
            await self._reroute_traffic(node)
            result["actions"].append("traffic_rerouted")
            self.stats["traffic_rerouted"] += 1
            
            # Step 2: Attempt restart (local nodes only)
            if config.node_type in ("lm_studio", "ollama") and config.restart_command:
                for attempt in range(1, config.max_retries + 1):
                    logger.info(f"Recovery attempt {attempt}/{config.max_retries} for {node}")
                    
                    success = await self._restart_node(config)
                    rec = RecoveryAttempt(
                        node=node,
                        action=f"restart_attempt_{attempt}",
                        success=success,
                        duration_ms=round((time.time() - start) * 1000, 1),
                        error="" if success else "restart failed"
                    )
                    self.recovery_history.append(rec)
                    
                    if success:
                        # Verify it's actually responding
                        await asyncio.sleep(5)
                        if await self._verify_node(config):
                            result["recovered"] = True
                            result["actions"].append(f"restarted (attempt {attempt})")
                            self.stats["successful"] += 1
                            self.stats["nodes_restarted"] += 1
                            
                            # Re-enable traffic
                            await self._restore_traffic(node)
                            result["actions"].append("traffic_restored")
                            
                            # Emit recovery event
                            await self._emit("cluster.node_recovered", {
                                "node": node, "attempts": attempt
                            })
                            break
                    
                    if attempt < config.max_retries:
                        await asyncio.sleep(config.retry_delay_s)
                
                if not result["recovered"]:
                    self.stats["failed"] += 1
                    await self._escalate(node, "All restart attempts failed")
                    result["actions"].append("escalated")
            
            elif config.node_type == "remote":
                # Remote nodes: just wait and retry
                result["actions"].append("remote_node_will_auto_recover")
                await self._emit("cluster.remote_node_down", {
                    "node": node, "url": config.url
                })
            
            self.stats["total_recoveries"] += 1
            result["duration_ms"] = round((time.time() - start) * 1000, 1)
            
        except Exception as e:
            logger.error(f"Recovery error for {node}: {e}")
            result["error"] = str(e)
        finally:
            self._active_recoveries.discard(node)
            if len(self.recovery_history) > self._max_history:
                self.recovery_history = self.recovery_history[-self._max_history:]
        
        return result
    
    async def _restart_node(self, config: NodeConfig) -> bool:
        """Attempt to restart a local node."""
        try:
            if not config.restart_command:
                return False
            
            if config.node_type == "lm_studio":
                # PowerShell restart
                proc = await asyncio.create_subprocess_exec(
                    "powershell", "-Command", config.restart_command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await asyncio.wait_for(proc.communicate(), timeout=30)
                return proc.returncode == 0
            
            elif config.node_type == "ollama":
                # Start ollama serve in background
                proc = await asyncio.create_subprocess_exec(
                    "cmd", "/c", "start", "/b", config.restart_command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await asyncio.wait_for(proc.communicate(), timeout=15)
                return True  # ollama serve returns immediately
            
            return False
        except Exception as e:
            logger.error(f"Restart failed for {config.name}: {e}")
            return False
    
    async def _verify_node(self, config: NodeConfig) -> bool:
        """Verify a node is responding after restart."""
        try:
            import urllib.request
            check_url = f"{config.url}/v1/models" if config.node_type == "lm_studio" else f"{config.url}/api/tags"
            req = urllib.request.Request(check_url, method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except Exception:
            return False
    
    async def _reroute_traffic(self, failed_node: str) -> None:
        """Reroute traffic away from failed node."""
        try:
            from src.load_balancer import load_balancer
            # Add to exclusion set
            if hasattr(load_balancer, '_excluded'):
                load_balancer._excluded.add(failed_node)
            logger.info(f"Traffic rerouted away from {failed_node}")
        except Exception as e:
            logger.error(f"Reroute failed: {e}")
    
    async def _restore_traffic(self, node: str) -> None:
        """Restore traffic to recovered node."""
        try:
            from src.load_balancer import load_balancer
            if hasattr(load_balancer, '_excluded'):
                load_balancer._excluded.discard(node)
            logger.info(f"Traffic restored to {node}")
        except Exception as e:
            logger.error(f"Restore failed: {e}")
    
    async def _escalate(self, node: str, reason: str) -> None:
        """Escalate unrecoverable failure."""
        try:
            from src.notification_hub import notification_hub
            notification_hub.dispatch(
                message=f"?? ESCALATION: Nœud {node} irrécupérable — {reason}",
                level="critical",
                source="cluster_self_healer"
            )
        except Exception:
            logger.critical(f"ESCALATION: Node {node} unrecoverable: {reason}")
        
        await self._emit("cluster.escalation", {
            "node": node, "reason": reason
        })
    
    async def _emit(self, event_type: str, data: dict[str, Any]) -> None:
        """Emit event to bus."""
        try:
            from src.event_bus import event_bus
            data["ts"] = time.time()
            await event_bus.emit(event_type, data)
        except Exception:
            pass
    
    def status(self) -> dict[str, Any]:
        """Current healer status."""
        return {
            "active_recoveries": list(self._active_recoveries),
            "stats": self.stats,
            "recent_history": [
                {"node": r.node, "action": r.action, "success": r.success,
                 "duration_ms": r.duration_ms}
                for r in self.recovery_history[-10:]
            ],
            "known_nodes": list(NODE_CONFIGS.keys())
        }


# Singleton
cluster_healer = ClusterSelfHealer()

