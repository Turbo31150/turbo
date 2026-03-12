"""JARVIS VRAM Optimizer — monitors and optimizes GPU memory usage.

Detects VRAM pressure, suggests/executes model unloads, tracks usage patterns.

Usage:
    from src.vram_optimizer import vram_optimizer
    await vram_optimizer.check_and_optimize()
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("jarvis.vram_optimizer")

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class GPUState:
    """Current GPU state."""
    name: str
    temp_c: int
    vram_used_mb: int
    vram_total_mb: int
    utilization_pct: int
    vram_pct: float


class VRAMOptimizer:
    """Monitors VRAM and optimizes model loading."""

    # Thresholds
    VRAM_WARN_PCT = 90.0
    VRAM_CRIT_PCT = 95.0
    TEMP_WARN_C = 75
    TEMP_CRIT_C = 85

    def __init__(self):
        self._history: list[dict] = []
        self._max_history = 100

    def get_gpu_state(self) -> list[GPUState]:
        """Get current GPU state via nvidia-smi."""
        try:
            r = subprocess.run(
                ["nvidia-smi",
                 "--query-gpu=name,temperature.gpu,memory.used,memory.total,utilization.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5
            )
            gpus = []
            for line in r.stdout.strip().split("\n"):
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 5:
                    vram_used = int(parts[2])
                    vram_total = int(parts[3])
                    gpus.append(GPUState(
                        name=parts[0],
                        temp_c=int(parts[1]),
                        vram_used_mb=vram_used,
                        vram_total_mb=vram_total,
                        utilization_pct=int(parts[4]),
                        vram_pct=round(vram_used / vram_total * 100, 1) if vram_total > 0 else 0,
                    ))
            return gpus
        except Exception as e:
            logger.warning("nvidia-smi failed: %s", e)
            return []

    def get_loaded_models(self) -> list[dict]:
        """Get currently loaded models from LM Studio M1."""
        import urllib.request
        try:
            with urllib.request.urlopen("http://127.0.0.1:1234/api/v1/models", timeout=5) as r:
                data = json.loads(r.read().decode())
            return [
                {"id": m.get("id", ""), "loaded": bool(m.get("loaded_instances"))}
                for m in data.get("data", [])
            ]
        except Exception:
            return []

    async def check_and_optimize(self) -> dict:
        """Check VRAM state and optimize if needed."""
        gpus = self.get_gpu_state()
        if not gpus:
            return {"status": "no_gpu", "actions": []}

        actions: list[str] = []
        alerts: list[str] = []
        gpu = gpus[0]  # Primary GPU

        # Record history
        self._history.append({
            "ts": time.time(),
            "vram_pct": gpu.vram_pct,
            "temp_c": gpu.temp_c,
            "util_pct": gpu.utilization_pct,
        })
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        # Check VRAM pressure
        if gpu.vram_pct >= self.VRAM_CRIT_PCT:
            alerts.append(f"CRITICAL: VRAM {gpu.vram_pct}% ({gpu.vram_used_mb}/{gpu.vram_total_mb}MB)")
            # Suggest unloading non-essential models
            models = self.get_loaded_models()
            loaded = [m for m in models if m["loaded"]]
            if len(loaded) > 1:
                actions.append(f"Consider unloading {len(loaded)-1} secondary models to free VRAM")
        elif gpu.vram_pct >= self.VRAM_WARN_PCT:
            alerts.append(f"WARNING: VRAM {gpu.vram_pct}% — approaching limit")

        # Check temperature
        if gpu.temp_c >= self.TEMP_CRIT_C:
            alerts.append(f"CRITICAL: GPU temp {gpu.temp_c}C — OVERHEATING")
            actions.append("Reduce GPU load immediately")
        elif gpu.temp_c >= self.TEMP_WARN_C:
            alerts.append(f"WARNING: GPU temp {gpu.temp_c}C — warm")

        # Trend analysis
        trend = self._analyze_trend()

        result = {
            "status": "critical" if any("CRITICAL" in a for a in alerts) else
                      "warning" if alerts else "healthy",
            "gpu": {
                "name": gpu.name,
                "temp_c": gpu.temp_c,
                "vram_used_mb": gpu.vram_used_mb,
                "vram_total_mb": gpu.vram_total_mb,
                "vram_pct": gpu.vram_pct,
                "utilization_pct": gpu.utilization_pct,
            },
            "alerts": alerts,
            "actions": actions,
            "trend": trend,
        }
        return result

    def _analyze_trend(self) -> dict:
        """Analyze VRAM usage trend from history."""
        if len(self._history) < 5:
            return {"direction": "insufficient_data", "samples": len(self._history)}

        recent = self._history[-5:]
        older = self._history[-10:-5] if len(self._history) >= 10 else self._history[:5]

        recent_avg = sum(h["vram_pct"] for h in recent) / len(recent)
        older_avg = sum(h["vram_pct"] for h in older) / len(older)
        diff = recent_avg - older_avg

        if diff > 2:
            direction = "increasing"
        elif diff < -2:
            direction = "decreasing"
        else:
            direction = "stable"

        return {
            "direction": direction,
            "recent_avg_pct": round(recent_avg, 1),
            "change_pct": round(diff, 1),
            "samples": len(self._history),
        }

    def get_report(self) -> dict:
        """Full VRAM optimization report."""
        gpus = self.get_gpu_state()
        models = self.get_loaded_models()
        trend = self._analyze_trend()
        return {
            "gpus": [{"name": g.name, "temp_c": g.temp_c, "vram_pct": g.vram_pct,
                       "vram_used_mb": g.vram_used_mb, "vram_total_mb": g.vram_total_mb}
                      for g in gpus],
            "loaded_models": models,
            "trend": trend,
            "history_samples": len(self._history),
        }


# Singleton
vram_optimizer = VRAMOptimizer()
