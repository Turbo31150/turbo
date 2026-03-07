"""JARVIS Event Bus Wiring -- Auto-connect all modules via event bus.

This module wires up all critical event subscribers so that JARVIS modules
communicate automatically. Import and call wire_all() at startup.

Usage:
    from src.event_bus_wiring import wire_all
    await wire_all()  # in FastAPI startup or main.py
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

logger = logging.getLogger("jarvis.wiring")


async def wire_all() -> dict[str, int]:
    """Wire all event bus subscribers. Returns count of subscriptions per category."""
    from src.event_bus import event_bus
    
    counts: dict[str, int] = {}
    
    # ---------------------------------------------------
    # 1. DRIFT DETECTION ? Auto-reroute on model degradation
    # ---------------------------------------------------
    async def on_drift_detected(data: dict[str, Any]) -> None:
        """When drift detector finds model quality drop, reroute traffic."""
        try:
            from src.orchestrator_v2 import orchestrator_v2
            model = data.get("model", "unknown")
            severity = data.get("severity", "warning")
            logger.warning(f"Drift detected on {model} (severity={severity}), triggering reroute")
            
            # Notify via notification hub
            await _notify(f"?? Drift qualit dtect sur {model} -- reroutage automatique", "warning")
            
            # Emit reroute event
            await event_bus.emit("orchestrator.reroute_triggered", {
                "reason": "drift", "model": model, "severity": severity,
                "ts": time.time()
            })
        except Exception as e:
            logger.error(f"Drift handler error: {e}")
    
    event_bus.subscribe("drift.*", on_drift_detected, priority=10)
    event_bus.subscribe("model.quality_drop", on_drift_detected, priority=10)
    counts["drift"] = 2
    
    # ---------------------------------------------------
    # 2. CLUSTER HEALTH ? Alert + self-heal on node failure
    # ---------------------------------------------------
    async def on_node_offline(data: dict[str, Any]) -> None:
        """Node went offline -- alert and attempt self-heal."""
        try:
            node = data.get("node", "unknown")
            logger.critical(f"Node {node} went OFFLINE")
            await _notify(f"?? Nud {node} hors ligne -- tentative de rcupration", "critical")
            
            # Emit self-heal request
            await event_bus.emit("cluster.heal_requested", {
                "node": node, "reason": "offline", "ts": time.time()
            })
        except Exception as e:
            logger.error(f"Node offline handler error: {e}")
    
    async def on_node_online(data: dict[str, Any]) -> None:
        """Node came back online."""
        node = data.get("node", "unknown")
        logger.info(f"Node {node} is back ONLINE")
        await _notify(f"?? Nud {node} de retour en ligne", "info")
    
    event_bus.subscribe("cluster.node_offline", on_node_offline, priority=10)
    event_bus.subscribe("cluster.node_online", on_node_online, priority=5)
    counts["cluster"] = 2
    
    # ---------------------------------------------------
    # 3. GPU MONITORING ? Auto-unload on overload
    # ---------------------------------------------------
    async def on_gpu_overload(data: dict[str, Any]) -> None:
        """GPU overloaded -- unload heaviest model or throttle."""
        try:
            temp = data.get("temperature", 0)
            vram_pct = data.get("vram_percent", 0)
            logger.warning(f"GPU overload: temp={temp}C, VRAM={vram_pct}%")
            await _notify(f"??? GPU surcharg: {temp}C, VRAM {vram_pct}%", "warning")
            
            if temp > 85 or vram_pct > 95:
                await event_bus.emit("gpu.emergency_unload", {
                    "temp": temp, "vram_pct": vram_pct, "ts": time.time()
                })
        except Exception as e:
            logger.error(f"GPU overload handler error: {e}")
    
    event_bus.subscribe("gpu.overload", on_gpu_overload, priority=10)
    event_bus.subscribe("gpu.temperature_critical", on_gpu_overload, priority=10)
    counts["gpu"] = 2
    
    # ---------------------------------------------------
    # 4. TRADING ? Alert on high-score signals + risk
    # ---------------------------------------------------
    async def on_trading_signal(data: dict[str, Any]) -> None:
        """High-score trading signal detected."""
        try:
            symbol = data.get("symbol", "?")
            score = data.get("score", 0)
            direction = data.get("direction", "?")
            if score >= 80:
                await _notify(
                    f"?? Signal fort: {symbol} {direction} score={score}", 
                    "critical" if score >= 90 else "warning"
                )
        except Exception as e:
            logger.error(f"Trading signal handler error: {e}")
    
    async def on_trading_risk(data: dict[str, Any]) -> None:
        """Trading risk alert (drawdown, liquidation proximity)."""
        try:
            msg = data.get("message", "Risque trading dtect")
            await _notify(f"?? {msg}", "critical")
        except Exception as e:
            logger.error(f"Trading risk handler error: {e}")
    
    event_bus.subscribe("trading.signal_detected", on_trading_signal, priority=8)
    event_bus.subscribe("trading.risk_alert", on_trading_risk, priority=10)
    counts["trading"] = 2
    
    # ---------------------------------------------------
    # 5. PATTERN DETECTION ? Auto-create skills
    # ---------------------------------------------------
    async def on_pattern_detected(data: dict[str, Any]) -> None:
        """Brain detected a usage pattern -- auto-create skill if confidence > 0.8."""
        try:
            pattern = data.get("pattern", "")
            confidence = data.get("confidence", 0)
            if confidence >= 0.8:
                logger.info(f"Auto-creating skill from pattern: {pattern} (conf={confidence})")
                await _notify(
                    f"?? Nouveau pattern dtect (conf={confidence:.0%}): {pattern}", "info"
                )
                await event_bus.emit("brain.skill_auto_created", {
                    "pattern": pattern, "confidence": confidence, "ts": time.time()
                })
        except Exception as e:
            logger.error(f"Pattern handler error: {e}")
    
    event_bus.subscribe("brain.pattern_detected", on_pattern_detected, priority=5)
    counts["brain"] = 1
    
    # ---------------------------------------------------
    # 6. AUTONOMOUS LOOP ? Log task results + escalate failures
    # ---------------------------------------------------
    async def on_task_failed(data: dict[str, Any]) -> None:
        """Autonomous task failed -- escalate after 3 consecutive failures."""
        try:
            task = data.get("task", "unknown")
            fail_count = data.get("fail_count", 1)
            error = data.get("error", "")
            if fail_count >= 3:
                await _notify(
                    f"?? Tche autonome '{task}' en chec x{fail_count}: {error}", "critical"
                )
            elif fail_count >= 2:
                logger.warning(f"Task {task} failed {fail_count} times: {error}")
        except Exception as e:
            logger.error(f"Task failure handler error: {e}")
    
    event_bus.subscribe("autonomous.task_failed", on_task_failed, priority=8)
    event_bus.subscribe("autonomous.task_error", on_task_failed, priority=8)
    counts["autonomous"] = 2
    
    # ---------------------------------------------------
    # 7. SECURITY ? Alert on suspicious activity
    # ---------------------------------------------------
    async def on_security_alert(data: dict[str, Any]) -> None:
        """Security event detected."""
        try:
            msg = data.get("message", "Alerte scurit")
            level = data.get("level", "warning")
            await _notify(f"??? {msg}", level)
        except Exception as e:
            logger.error(f"Security handler error: {e}")
    
    event_bus.subscribe("security.*", on_security_alert, priority=10)
    counts["security"] = 1
    
    # ---------------------------------------------------
    # 8. AUDIT LOGGER ? Log ALL events for analysis
    # ---------------------------------------------------
    async def on_any_event(data: dict[str, Any]) -> None:
        """Log all events for audit trail and pattern analysis."""
        try:
            from src.audit_trail import audit_trail
            event_type = data.get("_event_type", "unknown")
            audit_trail.log(
                action_type="event_bus",
                source="event_bus_wiring",
                detail=f"{event_type}: {str(data)[:200]}",
                status="ok"
            )
        except Exception:
            pass  # Never break on audit logging
    
    event_bus.subscribe("*", on_any_event, priority=-10)  # Lowest priority = runs last
    counts["audit"] = 1
    
    # ---------------------------------------------------
    # 9. VOICE COMMANDS ? Log vocal interactions for learning
    # ---------------------------------------------------
    async def on_voice_command(data: dict[str, Any]) -> None:
        """Voice command processed -- store for pattern learning."""
        try:
            from src.skills import log_action
            text = data.get("text", "")
            intent = data.get("intent", "")
            confidence = data.get("confidence", 0)
            if text:
                log_action("voice_command", f"{intent}: {text[:100]}", confidence > 0.5)
        except Exception:
            pass
    
    event_bus.subscribe("voice.command_processed", on_voice_command, priority=3)
    counts["voice"] = 1
    
    # ---------------------------------------------------
    # 10. BUDGET ? Alert when token budget is running low
    # ---------------------------------------------------
    async def on_budget_warning(data: dict[str, Any]) -> None:
        """Token budget running low."""
        try:
            used_pct = data.get("used_percent", 0)
            remaining = data.get("remaining_tokens", 0)
            await _notify(
                f"?? Budget tokens: {used_pct:.0f}% utilis, {remaining} restants", "warning"
            )
        except Exception as e:
            logger.error(f"Budget handler error: {e}")
    
    event_bus.subscribe("budget.warning", on_budget_warning, priority=5)
    event_bus.subscribe("budget.exhausted", on_budget_warning, priority=10)
    counts["budget"] = 2
    
    total = sum(counts.values())
    logger.info(f"Event bus wired: {total} subscribers across {len(counts)} categories")
    
    return counts


async def _notify(message: str, level: str = "info") -> None:
    """Send notification through notification hub (if available)."""
    try:
        from src.notification_hub import notification_hub
        notification_hub.dispatch(
            message=message, level=level, source="event_bus_wiring"
        )
    except Exception:
        logger.info(f"[NOTIF/{level}] {message}")


async def status() -> dict[str, Any]:
    """Return wiring status."""
    from src.event_bus import event_bus
    return {
        "subscriptions": len(event_bus._subscriptions) if hasattr(event_bus, '_subscriptions') else 0,
        "total_events": getattr(event_bus, 'total_events', 0),
        "categories": ["drift", "cluster", "gpu", "trading", "brain", 
                       "autonomous", "security", "audit", "voice", "budget"]
    }

