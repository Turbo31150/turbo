"""
Configuration Example pour JARVIS Tray Manager
Copier en config.py et adapter vos paramètres.
"""

# WebSocket Configuration
WS_CONFIG = {
    "host": "127.0.0.1",
    "port": 9742,
    "url": "ws://127.0.0.1:9742",
    "reconnect_max_attempts": 5,
    "reconnect_base_delay": 2,  # secondes
    "ping_interval": 20,  # secondes
}

# Database Configuration
DB_CONFIG = {
    "path": "/home/turbo/jarvis-m1-ops/jarvis.db",
    "max_history": 1000,
    "cleanup_interval": 3600,  # secondes
}

# Notification Configuration
NOTIFICATION_CONFIG = {
    "spam_window": 30,  # secondes
    "max_per_category": 1,
    "default_ttl": 300,  # secondes
    "enabled": True,
}

# System Tray Configuration
TRAY_CONFIG = {
    "icon_size": 64,
    "icon_update_interval": 5,  # secondes
    "menu_title": "JARVIS v10.6",
    "startup_in_system_tray": True,
}

# Telegram Integration
TELEGRAM_CONFIG = {
    "enabled": False,  # Mettre True si configuré
    "token": "YOUR_TELEGRAM_BOT_TOKEN",
    "chat_id": "YOUR_TELEGRAM_CHAT_ID",
    "export_critical_only": True,
}

# Logging Configuration
LOGGING_CONFIG = {
    "level": "INFO",
    "file": "/home/turbo/jarvis-m1-ops/logs/tray.log",
    "max_bytes": 10485760,  # 10MB
    "backup_count": 5,
}

# Thresholds d'alerte
ALERT_THRESHOLDS = {
    "gpu_temp_warning": 70,  # °C
    "gpu_temp_critical": 80,  # °C
    "gpu_utilization_warning": 85,  # %
    "memory_warning": 85,  # %
    "min_nodes_active": 5,  # sur 6
}

# Préférences par défaut
DEFAULT_PREFERENCES = {
    "voice_enabled": True,
    "notifications_enabled": True,
    "telegram_notifications": False,
    "dark_theme": True,
}
