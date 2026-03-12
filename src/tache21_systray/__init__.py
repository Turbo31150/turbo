"""
JARVIS Tache 21: System Tray & Notification Manager
Windows 10/11 integration avec monitoring temps réel et export Telegram.
"""

from .systray_manager import (
    TrayManager,
    ClusterMonitor,
    NotificationThrottler,
    DynamicIconGenerator,
    WebSocketListener,
    NotificationLevel,
)

from .notification_center import (
    NotificationCenter,
    Notification,
    NotificationPriority,
    NotificationCategory,
    PriorityQueue,
    TelegramExporter,
)

__version__ = "1.0.0"
__all__ = [
    "TrayManager",
    "NotificationCenter",
    "ClusterMonitor",
    "NotificationThrottler",
    "DynamicIconGenerator",
    "WebSocketListener",
    "Notification",
    "NotificationPriority",
    "NotificationCategory",
    "PriorityQueue",
    "TelegramExporter",
    "NotificationLevel",
]
