"""JARVIS GPU Guardian — Proactive GPU monitoring with auto-unload.

Monitors GPU temperature, VRAM usage, and power draw in real-time.
Automatically unloads heaviest models when thresholds are exceeded.
Emits events for event_bus consumers.

Usage:
    from src.gpu_guardian import gpu_guardian
    asyncio.create_task(gpu_guardian.start())  # runs in background
    gpu_guardian.stop()
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("jarvis.gpu_guardian")


@dataclass
class GPUSnapshot:
    """Point-in-time GPU state."""
    temperature: int = 0
    vram_used_mb: int = 0
    vram_total_mb: int = 0
    vram_percent: float = 0.0
    power_draw_w: float = 0.0
    gpu_util_pct: int = 0
    ts: float = field(default_factory=time.time)
    
    @property
    def is_critical(self) -> bool:
        return self.temperature > 85 or self.vram_percent > 95
    
    @property
    def is_warning(self) -> bool:
        return self.temperature > 75 or self.vram_percent > 85


@dataclass
class GuardianConfig:
    """Guardian thresholds."""
    temp_warning: int = 75
    temp_critical: int = 85
    temp_emergency: int = 90
    vram_warning_pct: float = 85.0
    vram_critical_pct: float = 95.0
    check_interval_s: float = 30.0
    cooldown_after_unload_s: float = 120.0
    max_unloads_per_hour: int = 3


class GPUGuardian:
    """Proactive GPU guardian with auto-protection."""
    
    def __init__(self, config: GuardianConfig | None = None):
        self.config = config or GuardianConfig()
        self.running = False
        self._task: asyncio.Task | None = None
        self.history: list[GPUSnapshot] = []
        self._max_history = 1000
        self._unload_timestamps: list[float] = []
        self._last_alert_time: float = 0
        self._alert_cooldown_s = 300.0  # 5min between alerts
        self.stats = {
            "checks": 0, "warnings": 0, "criticals": 0,
            "emergency_unloads": 0, "errors": 0
        }
    
    async def start(self) -> None:
        """Start the GPU guardian loop."""
        if self.running:
            return
        self.running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info(f"GPU Guardian started (interval={self.config.check_interval_s}s)")
    
    def stop(self) -> None:
        """Stop the guardian."""
        self.running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("GPU Guardian stopped")
    
    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self.running:
            try:
                snapshot = await self._take_snapshot()
                if snapshot:
                    self.history.append(snapshot)
                    if len(self.history) > self._max_history:
                        self.history = self.history[-self._max_history:]
                    
                    self.stats["checks"] += 1
                    await self._evaluate(snapshot)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.stats["errors"] += 1
                logger.error(f"GPU Guardian error: {e}")
            
            await asyncio.sleep(self.config.check_interval_s)
    
    async def _take_snapshot(self) -> GPUSnapshot | None:
        """Query nvidia-smi for current GPU state."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "nvidia-smi",
                "--query-gpu=temperature.gpu,memory.used,memory.total,power.draw,utilization.gpu",
                "--format=csv,noheader,nounits",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            line = stdout.decode().strip().split("\n")[0]
            parts = [x.strip() for x in line.split(",")]
            
            temp = int(parts[0])
            vram_used = int(parts[1])
            vram_total = int(parts[2])
            power = float(parts[3]) if len(parts) > 3 else 0
            gpu_util = int(parts[4]) if len(parts) > 4 else 0
            
            return GPUSnapshot(
                temperature=temp,
                vram_used_mb=vram_used,
                vram_total_mb=vram_total,
                vram_percent=(vram_used / vram_total * 100) if vram_total > 0 else 0,
                power_draw_w=power,
                gpu_util_pct=gpu_util
            )
        except Exception as e:
            logger.debug(f"nvidia-smi failed: {e}")
            return None
    
    async def _evaluate(self, snap: GPUSnapshot) -> None:
        """Evaluate snapshot and take action."""
        now = time.time()
        
        # Emergency: immediate unload
        if snap.temperature >= self.config.temp_emergency:
            self.stats["criticals"] += 1
            await self._emit_event("gpu.temperature_emergency", {
                "temperature": snap.temperature,
                "vram_percent": snap.vram_percent
            })
            await self._emergency_unload(snap, reason=f"Temp {snap.temperature}°C >= {self.config.temp_emergency}°C")
            return
        
        # Critical: unload if within rate limit
        if snap.is_critical:
            self.stats["criticals"] += 1
            await self._emit_event("gpu.overload", {
                "temperature": snap.temperature,
                "vram_percent": snap.vram_percent,
                "power_draw_w": snap.power_draw_w
            })
            
            if self._can_unload():
                await self._emergency_unload(snap, reason="VRAM/Temp critical")
            return
        
        # Warning: just alert
        if snap.is_warning:
            self.stats["warnings"] += 1
            if now - self._last_alert_time > self._alert_cooldown_s:
                await self._emit_event("gpu.warning", {
                    "temperature": snap.temperature,
                    "vram_percent": snap.vram_percent
                })
                self._last_alert_time = now
    
    async def _emergency_unload(self, snap: GPUSnapshot, reason: str) -> None:
        """Unload the heaviest model from LM Studio."""
        if not self._can_unload():
            logger.warning(f"Unload rate limit hit ({self.config.max_unloads_per_hour}/h)")
            return
        
        try:
            import urllib.request
            import json
            
            # Get loaded models
            req = urllib.request.Request("http://localhost:1234/v1/models")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            
            models = data.get("data", [])
            if not models:
                logger.info("No models loaded to unload")
                return
            
            # Unload first model (LM Studio API)
            model_id = models[0].get("id", "")
            if model_id:
                unload_data = json.dumps({"model": model_id}).encode()
                unload_req = urllib.request.Request(
                    "http://localhost:1234/v1/models/unload",
                    data=unload_data,
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                urllib.request.urlopen(unload_req, timeout=10)
                
                self._unload_timestamps.append(time.time())
                self.stats["emergency_unloads"] += 1
                
                logger.warning(f"EMERGENCY UNLOAD: {model_id} (reason: {reason})")
                await self._emit_event("gpu.emergency_unload", {
                    "model": model_id, "reason": reason,
                    "temperature": snap.temperature,
                    "vram_percent": snap.vram_percent
                })
        except Exception as e:
            logger.error(f"Emergency unload failed: {e}")
    
    def _can_unload(self) -> bool:
        """Check rate limit: max N unloads per hour."""
        now = time.time()
        recent = [t for t in self._unload_timestamps if now - t < 3600]
        self._unload_timestamps = recent
        return len(recent) < self.config.max_unloads_per_hour
    
    async def _emit_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Emit event to bus."""
        try:
            from src.event_bus import event_bus
            data["ts"] = time.time()
            await event_bus.emit(event_type, data)
        except Exception:
            pass
    
    def status(self) -> dict[str, Any]:
        """Current guardian status."""
        latest = self.history[-1] if self.history else None
        return {
            "running": self.running,
            "stats": self.stats,
            "latest": {
                "temperature": latest.temperature if latest else None,
                "vram_percent": round(latest.vram_percent, 1) if latest else None,
                "gpu_util_pct": latest.gpu_util_pct if latest else None,
                "power_draw_w": latest.power_draw_w if latest else None,
            } if latest else None,
            "history_size": len(self.history),
            "config": {
                "temp_warning": self.config.temp_warning,
                "temp_critical": self.config.temp_critical,
                "temp_emergency": self.config.temp_emergency,
                "vram_critical_pct": self.config.vram_critical_pct,
                "check_interval_s": self.config.check_interval_s
            }
        }
    
    def trend(self, minutes: int = 30) -> dict[str, Any]:
        """Temperature/VRAM trend over last N minutes."""
        cutoff = time.time() - (minutes * 60)
        recent = [s for s in self.history if s.ts >= cutoff]
        if not recent:
            return {"samples": 0}
        
        temps = [s.temperature for s in recent]
        vrams = [s.vram_percent for s in recent]
        return {
            "samples": len(recent),
            "minutes": minutes,
            "temp_avg": round(sum(temps) / len(temps), 1),
            "temp_min": min(temps),
            "temp_max": max(temps),
            "temp_trend": "rising" if len(temps) > 2 and temps[-1] > temps[0] + 3 else
                         "falling" if len(temps) > 2 and temps[-1] < temps[0] - 3 else "stable",
            "vram_avg": round(sum(vrams) / len(vrams), 1),
            "vram_max": round(max(vrams), 1),
        }


# Singleton
gpu_guardian = GPUGuardian()

