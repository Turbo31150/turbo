"""JARVIS Daily Report - Automated system and trading daily summary.

Generates comprehensive daily reports combining:
- Cluster health and performance
- Trading activity and P&L
- GPU usage trends
- Skills/patterns learned
- Alerts and incidents
- Recommendations

Usage:
    from src.daily_report import generate_morning_report, generate_evening_report
    report = await generate_morning_report()
    report = await generate_evening_report()
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

logger = logging.getLogger("jarvis.daily_report")


async def generate_morning_report() -> dict[str, Any]:
    """Generate morning briefing: what happened overnight + today's plan."""
    report: dict[str, Any] = {
        "type": "morning_briefing",
        "ts": time.time(),
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "sections": {}
    }

    # 1. Cluster health
    report["sections"]["cluster"] = await _get_cluster_health()

    # 2. GPU status
    report["sections"]["gpu"] = await _get_gpu_status()

    # 3. Trading positions
    report["sections"]["trading"] = await _get_trading_status()

    # 4. Overnight alerts
    report["sections"]["alerts"] = await _get_recent_alerts(hours=12)

    # 5. Brain activity
    report["sections"]["brain"] = await _get_brain_activity()

    # 6. System resources
    report["sections"]["resources"] = await _get_system_resources()

    # Build summary text
    report["summary"] = _build_summary(report)

    return report


async def generate_evening_report() -> dict[str, Any]:
    """Generate evening report: today's activity + recommendations."""
    report: dict[str, Any] = {
        "type": "evening_report",
        "ts": time.time(),
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "sections": {}
    }

    report["sections"]["cluster"] = await _get_cluster_health()
    report["sections"]["trading"] = await _get_trading_status()
    report["sections"]["daily_alerts"] = await _get_recent_alerts(hours=24)
    report["sections"]["performance"] = await _get_performance_stats()
    report["sections"]["brain"] = await _get_brain_activity()
    report["sections"]["recommendations"] = await _get_recommendations()

    report["summary"] = _build_summary(report)

    return report


async def _get_cluster_health() -> dict[str, Any]:
    try:
        from src.health_probe import health_probe
        results = health_probe.run_all()
        healthy = sum(1 for r in results if r.status.value == "healthy")
        total = len(results)
        return {
            "healthy": healthy, "total": total,
            "score": round(healthy / max(total, 1) * 100),
            "issues": [r.name for r in results if r.status.value != "healthy"]
        }
    except Exception as e:
        return {"error": str(e)}


async def _get_gpu_status() -> dict[str, Any]:
    try:
        from src.gpu_guardian import gpu_guardian
        status = gpu_guardian.status()
        trend = gpu_guardian.trend(minutes=60)
        return {"current": status.get("latest"), "trend_1h": trend, "stats": status.get("stats")}
    except Exception as e:
        return {"error": str(e)}


async def _get_trading_status() -> dict[str, Any]:
    try:
        from src.trading_sentinel import trading_sentinel
        summary = trading_sentinel.summary()
        return {
            "positions_monitored": summary["stats"].get("positions_monitored", 0),
            "alerts_today": summary["stats"].get("alerts_sent", 0),
            "emergency_closes": summary["stats"].get("emergency_closes", 0),
            "recent_alerts": summary.get("recent_alerts", [])[-5:]
        }
    except Exception as e:
        return {"error": str(e)}


async def _get_recent_alerts(hours: int = 24) -> dict[str, Any]:
    try:
        from src.notification_hub import notification_hub
        cutoff = time.time() - (hours * 3600)
        all_notifs = getattr(notification_hub, '_history', [])
        recent = [n for n in all_notifs if getattr(n, 'ts', 0) >= cutoff]
        critical = [n for n in recent if getattr(n, 'level', '') == 'critical']
        return {
            "total": len(recent),
            "critical": len(critical),
            "hours": hours
        }
    except Exception as e:
        return {"error": str(e)}


async def _get_brain_activity() -> dict[str, Any]:
    try:
        from src.brain import brain
        status = brain.status() if hasattr(brain, 'status') else {}
        return {
            "skills_count": status.get("skills_count", 0),
            "patterns_detected": status.get("patterns_detected", 0),
            "actions_logged": status.get("actions_logged", 0)
        }
    except Exception as e:
        return {"error": str(e)}


async def _get_system_resources() -> dict[str, Any]:
    try:
        import shutil
        import psutil
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        disk = shutil.disk_usage("F:/")
        return {
            "cpu_percent": cpu,
            "ram_used_gb": round(mem.used / (1024**3), 1),
            "ram_total_gb": round(mem.total / (1024**3), 1),
            "ram_percent": mem.percent,
            "disk_free_gb": round(disk.free / (1024**3), 1),
            "disk_percent_used": round(disk.used / disk.total * 100, 1)
        }
    except Exception as e:
        return {"error": str(e)}


async def _get_performance_stats() -> dict[str, Any]:
    try:
        from src.smart_retry import retry_stats
        return retry_stats.to_dict()
    except Exception as e:
        return {"error": str(e)}


async def _get_recommendations() -> list[str]:
    recs = []
    try:
        gpu = await _get_gpu_status()
        latest = gpu.get("current", {})
        if latest and latest.get("temperature") and latest["temperature"] > 75:
            recs.append("GPU temperature elevated - consider unloading unused models")
        if latest and latest.get("vram_percent") and latest["vram_percent"] > 85:
            recs.append("VRAM usage high - check loaded models")
    except Exception:
        pass

    try:
        resources = await _get_system_resources()
        if resources.get("disk_free_gb", 100) < 20:
            recs.append(f"Disk space low: {resources['disk_free_gb']}GB free on F:\\")
        if resources.get("ram_percent", 0) > 85:
            recs.append(f"RAM usage high: {resources['ram_percent']}%")
    except Exception:
        pass

    try:
        from src.smart_retry import retry_stats
        stats = retry_stats.to_dict()
        if stats.get("success_rate", 100) < 90:
            recs.append(f"Cluster success rate low: {stats['success_rate']}% - check node health")
    except Exception:
        pass

    if not recs:
        recs.append("All systems nominal - no recommendations")

    return recs


def _build_summary(report: dict[str, Any]) -> str:
    """Build a human-readable summary from report sections."""
    parts = []
    sections = report.get("sections", {})

    cluster = sections.get("cluster", {})
    if cluster and not cluster.get("error"):
        parts.append(f"Cluster: {cluster.get('score', '?')}% sante")

    trading = sections.get("trading", {})
    if trading and not trading.get("error"):
        parts.append(f"Trading: {trading.get('positions_monitored', 0)} positions, {trading.get('alerts_today', 0)} alertes")

    gpu = sections.get("gpu", {})
    current = gpu.get("current", {})
    if current:
        parts.append(f"GPU: {current.get('temperature', '?')}C, VRAM {current.get('vram_percent', '?')}%")

    alerts = sections.get("alerts", sections.get("daily_alerts", {}))
    if alerts and not alerts.get("error"):
        crit = alerts.get("critical", 0)
        if crit > 0:
            parts.append(f"ALERTES: {crit} critiques!")

    return " | ".join(parts) if parts else "Rapport genere"

