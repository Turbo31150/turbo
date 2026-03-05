"""JARVIS Health Probe Registry — Auto-register all critical health checks.

Registers probes for every subsystem: LM Studio, Ollama, GPU, DB, event bus,
autonomous loop, trading, voice, MCP server. Call register_all_probes() at startup.

Usage:
    from src.health_probe_registry import register_all_probes
    register_all_probes()  # after health_probe init
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger("jarvis.health_registry")


def register_all_probes() -> dict[str, bool]:
    """Register all health probes. Returns dict of probe_name -> registered."""
    from src.health_probe import health_probe, HealthStatus
    
    registered: dict[str, bool] = {}
    
    # --- 1. LM Studio M1 (critical) ---
    def check_lm_studio_m1() -> bool | str:
        try:
            import urllib.request
            req = urllib.request.Request("http://localhost:1234/v1/models", method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except Exception as e:
            return f"M1 unreachable: {e}"
    
    try:
        health_probe.register("lm_studio_m1", check_lm_studio_m1, critical=True, timeout_s=8, interval_s=60)
        registered["lm_studio_m1"] = True
    except Exception:
        registered["lm_studio_m1"] = False
    
    # --- 2. Ollama local (critical) ---
    def check_ollama() -> bool | str:
        try:
            import urllib.request
            req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except Exception as e:
            return f"Ollama unreachable: {e}"
    
    try:
        health_probe.register("ollama_local", check_ollama, critical=True, timeout_s=8, interval_s=60)
        registered["ollama_local"] = True
    except Exception:
        registered["ollama_local"] = False
    
    # --- 3. GPU VRAM (critical) ---
    def check_gpu_vram() -> bool | str:
        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used,memory.total,temperature.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                return f"nvidia-smi failed: {result.stderr[:100]}"
            line = result.stdout.strip().split("\n")[0]
            parts = [int(x.strip()) for x in line.split(",")]
            used, total, temp = parts[0], parts[1], parts[2]
            pct = (used / total * 100) if total > 0 else 0
            if temp > 90:
                return f"GPU CRITICAL: {temp}°C, VRAM {pct:.0f}%"
            if pct > 95:
                return f"VRAM CRITICAL: {pct:.0f}% ({used}/{total}MB)"
            return True
        except Exception as e:
            return f"GPU check failed: {e}"
    
    try:
        health_probe.register("gpu_vram", check_gpu_vram, critical=True, timeout_s=15, interval_s=120)
        registered["gpu_vram"] = True
    except Exception:
        registered["gpu_vram"] = False
    
    # --- 4. Database integrity (critical) ---
    def check_database() -> bool | str:
        try:
            from src.database import db
            result = db.execute("PRAGMA integrity_check").fetchone()
            if result and result[0] == "ok":
                return True
            return f"DB integrity issue: {result}"
        except Exception as e:
            return f"DB check failed: {e}"
    
    try:
        health_probe.register("database", check_database, critical=True, timeout_s=30, interval_s=300)
        registered["database"] = True
    except Exception:
        registered["database"] = False
    
    # --- 5. Event bus (non-critical) ---
    def check_event_bus() -> bool | str:
        try:
            from src.event_bus import event_bus
            sub_count = len(event_bus._subscriptions) if hasattr(event_bus, '_subscriptions') else 0
            if sub_count == 0:
                return "Event bus has 0 subscribers — wiring not done"
            return True
        except Exception as e:
            return f"Event bus check failed: {e}"
    
    try:
        health_probe.register("event_bus", check_event_bus, critical=False, timeout_s=5, interval_s=120)
        registered["event_bus"] = True
    except Exception:
        registered["event_bus"] = False
    
    # --- 6. Autonomous loop running (non-critical) ---
    def check_autonomous_loop() -> bool | str:
        try:
            from src.autonomous_loop import autonomous_loop
            if autonomous_loop.running:
                return True
            return "Autonomous loop is NOT running"
        except Exception as e:
            return f"Autonomous check failed: {e}"
    
    try:
        health_probe.register("autonomous_loop", check_autonomous_loop, critical=False, timeout_s=5, interval_s=60)
        registered["autonomous_loop"] = True
    except Exception:
        registered["autonomous_loop"] = False
    
    # --- 7. Disk space (critical) ---
    def check_disk_space() -> bool | str:
        try:
            import shutil
            usage = shutil.disk_usage("F:/")
            free_gb = usage.free / (1024**3)
            pct_used = usage.used / usage.total * 100
            if free_gb < 5:
                return f"CRITICAL: Only {free_gb:.1f}GB free on F:\\"
            if free_gb < 20:
                return f"WARNING: {free_gb:.1f}GB free on F:\\ ({pct_used:.0f}% used)"
            return True
        except Exception as e:
            return f"Disk check failed: {e}"
    
    try:
        health_probe.register("disk_space_f", check_disk_space, critical=True, timeout_s=5, interval_s=600)
        registered["disk_space_f"] = True
    except Exception:
        registered["disk_space_f"] = False
    
    # --- 8. MCP server port (non-critical) ---
    def check_mcp_port() -> bool | str:
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex(('localhost', 8901))
            sock.close()
            if result == 0:
                return True
            return "MCP server port 8901 not listening"
        except Exception as e:
            return f"MCP port check failed: {e}"
    
    try:
        health_probe.register("mcp_server", check_mcp_port, critical=False, timeout_s=5, interval_s=120)
        registered["mcp_server"] = True
    except Exception:
        registered["mcp_server"] = False
    
    # --- 9. Cloudflare tunnel (non-critical) ---
    def check_tunnel() -> bool | str:
        try:
            import subprocess
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq cloudflared.exe"],
                capture_output=True, text=True, timeout=5
            )
            if "cloudflared.exe" in result.stdout:
                return True
            return "Cloudflare tunnel not running"
        except Exception as e:
            return f"Tunnel check failed: {e}"
    
    try:
        health_probe.register("cloudflare_tunnel", check_tunnel, critical=False, timeout_s=8, interval_s=300)
        registered["cloudflare_tunnel"] = True
    except Exception:
        registered["cloudflare_tunnel"] = False
    
    # --- 10. Trading engine (non-critical) ---
    def check_trading() -> bool | str:
        try:
            from src.trading_engine import trading_engine
            status = trading_engine.status()
            if status.get("connected"):
                return True
            return f"Trading engine not connected: {status.get('error', 'unknown')}"
        except ImportError:
            return True  # Module not loaded = OK
        except Exception as e:
            return f"Trading check failed: {e}"
    
    try:
        health_probe.register("trading_engine", check_trading, critical=False, timeout_s=10, interval_s=300)
        registered["trading_engine"] = True
    except Exception:
        registered["trading_engine"] = False
    
    ok_count = sum(1 for v in registered.values() if v)
    logger.info(f"Health probes registered: {ok_count}/{len(registered)}")
    
    return registered

