"""
Exemple d'intégration JARVIS Tache 21
Montre comment intégrer le système tray avec les autres composants JARVIS.
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, Any

from notification_center import (
    NotificationCenter,
    NotificationPriority,
    NotificationCategory,
)
from systray_manager import TrayManager


class JARVISIntegration:
    """Intègre Tache 21 avec le reste de JARVIS."""

    def __init__(self):
        self.tray_manager = TrayManager()
        self.notif_center = NotificationCenter()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    async def handle_cluster_event(self, event: Dict[str, Any]):
        """Traite les événements du cluster."""
        nodes_active = event.get("nodes_active", 0)
        gpu_temp = event.get("gpu_temp", 0)

        # Update le monitor
        self.tray_manager.cluster.update_from_ws(event)

        # Crée une notification si nécessaire
        if gpu_temp > 80:
            await self.notif_center.add_notification(
                title="GPU CRITICAL",
                message=f"Temperature: {gpu_temp}°C",
                category=NotificationCategory.CLUSTER.value,
                level="CRITICAL",
                priority=NotificationPriority.CRITICAL.value,
            )
        elif gpu_temp > 70:
            await self.notif_center.add_notification(
                title="GPU Warning",
                message=f"Temperature: {gpu_temp}°C",
                category=NotificationCategory.CLUSTER.value,
                level="WARNING",
                priority=NotificationPriority.HIGH.value,
            )

        if nodes_active < 5:
            await self.notif_center.add_notification(
                title="Cluster Degraded",
                message=f"Only {nodes_active}/6 nodes active",
                category=NotificationCategory.CLUSTER.value,
                level="WARNING",
                priority=NotificationPriority.HIGH.value,
            )

    async def handle_trading_signal(self, signal: Dict[str, Any]):
        """Traite les signaux de trading."""
        signal_type = signal.get("type", "unknown")
        pair = signal.get("pair", "")
        score = signal.get("score", 0)

        # Détermine le niveau
        level = "INFO"
        priority = NotificationPriority.NORMAL.value

        if score >= 0.8:
            level = "CRITICAL"
            priority = NotificationPriority.CRITICAL.value
        elif score >= 0.6:
            level = "WARNING"
            priority = NotificationPriority.HIGH.value

        await self.notif_center.add_notification(
            title=f"Trading Signal: {pair}",
            message=f"{signal_type} | Score: {score:.2f}",
            category=NotificationCategory.TRADING.value,
            level=level,
            priority=priority,
        )

        # Update stats
        self.tray_manager.trading_stats.signals_pending = signal.get(
            "pending_count", 0
        )

    async def handle_voice_command(self, command: Dict[str, Any]):
        """Traite les commandes vocales."""
        text = command.get("text", "")
        confidence = command.get("confidence", 0)

        if confidence < 0.5:
            await self.notif_center.add_notification(
                title="Voice Recognition",
                message=f"Low confidence: {text} ({confidence:.1%})",
                category=NotificationCategory.VOICE.value,
                level="WARNING",
                priority=NotificationPriority.NORMAL.value,
            )

    async def handle_system_error(self, error: Dict[str, Any]):
        """Traite les erreurs système."""
        error_type = error.get("type", "unknown")
        message = error.get("message", "")
        component = error.get("component", "unknown")

        await self.notif_center.add_notification(
            title=f"System Error: {component}",
            message=f"{error_type}: {message}",
            category=NotificationCategory.ERROR.value,
            level="CRITICAL",
            priority=NotificationPriority.CRITICAL.value,
        )

    async def process_event(self, event: Dict[str, Any]):
        """Traite un événement générique."""
        event_type = event.get("type")

        handlers = {
            "cluster_update": self.handle_cluster_event,
            "trading_signal": self.handle_trading_signal,
            "voice_command": self.handle_voice_command,
            "system_error": self.handle_system_error,
        }

        handler = handlers.get(event_type)
        if handler:
            await handler(event)

    async def get_system_status(self) -> Dict[str, Any]:
        """Retourne le statut système complet."""
        stats = await self.notif_center.get_stats()

        return {
            "timestamp": datetime.now().isoformat(),
            "cluster": {
                "status": self.tray_manager.cluster.current_status,
                "nodes_active": self.tray_manager.cluster.stats.nodes_active,
                "nodes_total": self.tray_manager.cluster.stats.nodes_total,
                "gpu_temp": self.tray_manager.cluster.stats.gpu_temp,
                "gpu_utilization": self.tray_manager.cluster.stats.gpu_utilization,
            },
            "trading": {
                "signals_pending": self.tray_manager.trading_stats.signals_pending,
                "positions_open": self.tray_manager.trading_stats.positions_open,
                "pnl_today": self.tray_manager.trading_stats.pnl_today,
                "win_rate": self.tray_manager.trading_stats.win_rate,
            },
            "notifications": stats,
            "preferences": {
                "voice_enabled": self.tray_manager.voice_enabled,
                "notifications_enabled": self.tray_manager.notifications_enabled,
            },
        }

    def run(self):
        """Lance JARVIS Tray avec intégration."""
        self.tray_manager.run()

    def stop(self):
        """Arrête proprement."""
        self.tray_manager.ws_listener.stop()
        self.loop.run_until_complete(self.notif_center.cleanup())


# Exemples d'utilisation
async def example_cluster_monitoring():
    """Exemple: monitoring cluster."""
    print("=" * 60)
    print("EXEMPLE: Cluster Monitoring")
    print("=" * 60 + "\n")

    integration = JARVISIntegration()

    # Simule un événement cluster
    cluster_event = {
        "type": "cluster_update",
        "nodes_active": 5,
        "gpu_temp": 75.5,
        "gpu_utilization": 65.0,
    }

    print(f"Event: {json.dumps(cluster_event, indent=2)}\n")
    await integration.handle_cluster_event(cluster_event)

    # Récupère le statut
    status = await integration.get_system_status()
    print(f"Status: {json.dumps(status, indent=2)}\n")

    await integration.notif_center.cleanup()


async def example_trading_alerts():
    """Exemple: alertes trading."""
    print("=" * 60)
    print("EXEMPLE: Trading Alerts")
    print("=" * 60 + "\n")

    integration = JARVISIntegration()

    signals = [
        {
            "type": "trading_signal",
            "pair": "BTC/USDT",
            "score": 0.92,
            "pending_count": 3,
        },
        {
            "type": "trading_signal",
            "pair": "ETH/USDT",
            "score": 0.55,
            "pending_count": 4,
        },
    ]

    for signal in signals:
        print(f"Signal: {json.dumps(signal, indent=2)}")
        await integration.handle_trading_signal(signal)
        print()

    # Historique
    history = integration.notif_center.get_history(
        category=NotificationCategory.TRADING.value
    )
    print(f"Trading Notifications History: {len(history)} notifications\n")

    for notif in history[:3]:
        print(f"  • {notif.timestamp}: {notif.title}")

    await integration.notif_center.cleanup()


async def example_error_handling():
    """Exemple: gestion d'erreurs."""
    print("=" * 60)
    print("EXEMPLE: Error Handling")
    print("=" * 60 + "\n")

    integration = JARVISIntegration()

    errors = [
        {
            "type": "system_error",
            "component": "GPU",
            "error_type": "OverTemperature",
            "message": "GPU temperature exceeded safe limit",
        },
        {
            "type": "system_error",
            "component": "WebSocket",
            "error_type": "ConnectionLost",
            "message": "Lost connection to cluster node M1",
        },
    ]

    for error in errors:
        print(f"Error: {json.dumps(error, indent=2)}")
        await integration.handle_system_error(error)
        print()

    # Notifications en attente
    pending = await integration.notif_center.get_all_pending()
    print(f"Pending Notifications: {len(pending)}\n")

    for notif in pending:
        print(f"  • [{notif.level}] {notif.title}")

    await integration.notif_center.cleanup()


def run_examples():
    """Lance tous les exemples."""
    print("\n" + "=" * 60)
    print("JARVIS TACHE 21 - EXEMPLES D'INTÉGRATION")
    print("=" * 60 + "\n")

    asyncio.run(example_cluster_monitoring())
    print("\n")

    asyncio.run(example_trading_alerts())
    print("\n")

    asyncio.run(example_error_handling())

    print("\n" + "=" * 60)
    print("✓ Tous les exemples exécutés")
    print("=" * 60)


if __name__ == "__main__":
    run_examples()
