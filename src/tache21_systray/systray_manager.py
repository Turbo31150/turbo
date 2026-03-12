"""
JARVIS System Tray Manager v1.0
Windows 10/11 system tray integration avec notifications natives.
Support WebSocket temps réel, persistent preferences, dynamic icons.
"""

import asyncio
import threading
import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict

import pystray
from PIL import Image, ImageDraw
import websockets
from plyer import notification as plyer_notification

# Configuration
TRAY_DB = Path("/home/turbo/jarvis-m1-ops/jarvis.db")
WS_URL = "ws://127.0.0.1:9742"
ICON_SIZE = 64
NOTIF_SPAM_WINDOW = 30  # secondes
MAX_NOTIF_PER_CATEGORY = 1  # par fenêtre


class NotificationLevel(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class ClusterStats:
    nodes_total: int = 6
    nodes_active: int = 5
    gpu_temp: float = 45.0
    gpu_utilization: float = 60.0
    memory_used: float = 12.5
    memory_total: float = 24.0
    models_loaded: int = 8


@dataclass
class TradingStats:
    signals_pending: int = 3
    positions_open: int = 2
    pnl_today: float = 145.50
    win_rate: float = 62.5
    last_trade: str = "2026-03-04 14:23:15"


class NotificationThrottler:
    """Évite le spam de notifications."""

    def __init__(self, window_seconds: int = NOTIF_SPAM_WINDOW):
        self.window = window_seconds
        self.last_notif: Dict[str, float] = defaultdict(float)

    def can_notify(self, category: str) -> bool:
        now = datetime.now().timestamp()
        last = self.last_notif.get(category, 0)
        if (now - last) >= self.window:
            self.last_notif[category] = now
            return True
        return False


class TrayDatabase:
    """Gère la persistence SQLite des préférences."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS preferences (
                    id TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    level TEXT,
                    category TEXT,
                    title TEXT,
                    message TEXT
                )
            """)
            conn.commit()

    def get_preference(self, key: str, default: Any = None) -> Any:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT value FROM preferences WHERE id = ?", (key,)
                )
                row = cursor.fetchone()
                if row:
                    return json.loads(row[0])
                return default
        except Exception as e:
            logging.error(f"DB read error: {e}")
            return default

    def set_preference(self, key: str, value: Any):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO preferences (id, value) VALUES (?, ?)",
                    (key, json.dumps(value)),
                )
                conn.commit()
        except Exception as e:
            logging.error(f"DB write error: {e}")

    def log_notification(self, level: str, category: str, title: str, message: str):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """INSERT INTO notifications (level, category, title, message)
                       VALUES (?, ?, ?, ?)""",
                    (level, category, title, message),
                )
                conn.commit()
        except Exception as e:
            logging.error(f"Notification log error: {e}")


class DynamicIconGenerator:
    """Génère des icônes dynamiques basées sur le status."""

    @staticmethod
    def create_icon(
        status_color: str = "green",
        text: str = "J",
        size: int = ICON_SIZE,
    ) -> Image.Image:
        """Crée une icône avec couleur et texte."""
        color_map = {
            "green": (34, 139, 34),
            "orange": (255, 165, 0),
            "red": (220, 20, 60),
        }

        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Cercle de fond
        color = color_map.get(status_color, color_map["green"])
        draw.ellipse([5, 5, size - 5, size - 5], fill=color)

        # Texte au centre
        try:
            draw.text(
                (size // 2, size // 2),
                text,
                fill=(255, 255, 255),
                anchor="mm",
            )
        except Exception:
            pass

        return img


class ClusterMonitor:
    """Monitore l'état du cluster."""

    def __init__(self):
        self.stats = ClusterStats()
        self.current_status = "OK"
        self.status_color = "green"

    def update_from_ws(self, data: Dict[str, Any]):
        """Met à jour les stats depuis WebSocket."""
        try:
            if "nodes_active" in data:
                self.stats.nodes_active = data["nodes_active"]
            if "gpu_temp" in data:
                self.stats.gpu_temp = data["gpu_temp"]
            if "gpu_utilization" in data:
                self.stats.gpu_utilization = data["gpu_utilization"]

            # Détermine le statut global
            if self.stats.gpu_temp > 80:
                self.current_status = "CRITICAL"
                self.status_color = "red"
            elif self.stats.gpu_temp > 70 or self.stats.nodes_active < 5:
                self.current_status = "WARNING"
                self.status_color = "orange"
            else:
                self.current_status = "OK"
                self.status_color = "green"
        except Exception as e:
            logging.error(f"Cluster update error: {e}")

    def get_tooltip(self) -> str:
        """Retourne le tooltip avec stats actuelles."""
        return (
            f"JARVIS v10.6\n"
            f"{self.stats.nodes_active}/{self.stats.nodes_total} nodes\n"
            f"GPU {self.stats.gpu_temp:.0f}°C ({self.stats.gpu_utilization:.0f}%)\n"
            f"RAM {self.stats.memory_used:.1f}GB/{self.stats.memory_total:.1f}GB\n"
            f"Models: {self.stats.models_loaded}\n"
            f"Status: {self.current_status}"
        )


class WebSocketListener:
    """Écoute les événements WebSocket."""

    def __init__(
        self,
        cluster_monitor: ClusterMonitor,
        throttler: NotificationThrottler,
        db: TrayDatabase,
        on_notification: callable = None,
    ):
        self.cluster = cluster_monitor
        self.throttler = throttler
        self.db = db
        self.on_notification = on_notification
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.thread: Optional[threading.Thread] = None
        self.running = False

    def start(self):
        """Démarre le listener en thread séparé."""
        self.running = True
        self.thread = threading.Thread(daemon=True, target=self._run_async_loop)
        self.thread.start()

    def stop(self):
        """Arrête le listener."""
        self.running = False
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)

    def _run_async_loop(self):
        """Exécute la boucle d'événements asyncio."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._listen_ws())

    async def _listen_ws(self):
        """Connecte et écoute les événements WebSocket."""
        reconnect_count = 0
        max_reconnects = 5

        while self.running and reconnect_count < max_reconnects:
            try:
                async with websockets.connect(WS_URL, ping_interval=20) as ws:
                    reconnect_count = 0
                    logging.info(f"WebSocket connected to {WS_URL}")

                    async for message in ws:
                        if not self.running:
                            break

                        try:
                            data = json.loads(message)
                            await self._handle_event(data)
                        except json.JSONDecodeError:
                            logging.error(f"Invalid JSON: {message}")
                        except Exception as e:
                            logging.error(f"Event handling error: {e}")

            except websockets.exceptions.WebSocketException as e:
                reconnect_count += 1
                wait_time = min(2**reconnect_count, 30)
                logging.warning(
                    f"WS error: {e}. Reconnecting in {wait_time}s ({reconnect_count}/{max_reconnects})"
                )
                await asyncio.sleep(wait_time)
            except Exception as e:
                logging.error(f"WebSocket error: {e}")
                await asyncio.sleep(5)

    async def _handle_event(self, data: Dict[str, Any]):
        """Traite les événements reçus."""
        event_type = data.get("type")
        category = data.get("category", "system")
        level = data.get("level", "INFO")

        # Update cluster stats
        if event_type == "cluster_update":
            self.cluster.update_from_ws(data)

        # Handle notifications
        if "notification" in data and self.throttler.can_notify(category):
            title = data.get("title", "JARVIS")
            message = data.get("message", "")
            self.db.log_notification(level, category, title, message)

            if self.on_notification:
                self.on_notification(level, title, message)


class TrayManager:
    """Gère le system tray et les interactions UI."""

    def __init__(self):
        self.cluster = ClusterMonitor()
        self.trading_stats = TradingStats()
        self.throttler = NotificationThrottler()
        self.db = TrayDatabase(TRAY_DB)
        self.icon: Optional[pystray.Icon] = None
        self.ws_listener = WebSocketListener(
            self.cluster,
            self.throttler,
            self.db,
            on_notification=self._show_notification,
        )

        # Chargement préférences
        self.voice_enabled = self.db.get_preference("voice_enabled", True)
        self.notifications_enabled = self.db.get_preference("notifications_enabled", True)

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler("/home/turbo/jarvis-m1-ops/logs/tray.log"),
                logging.StreamHandler(),
            ],
        )

    def create_menu(self) -> pystray.Menu:
        """Crée le menu contextuel."""
        return pystray.Menu(
            pystray.MenuItem(
                f"📊 Cluster Status (v{self.cluster.stats.nodes_active}/{self.cluster.stats.nodes_total})",
                self._show_cluster_status,
            ),
            pystray.MenuItem(
                f"💰 Trading ({self.trading_stats.signals_pending} signaux)",
                self._show_trading_status,
            ),
            pystray.MenuItem(
                f"🔥 GPU Monitor ({self.cluster.stats.gpu_temp:.0f}°C)",
                self._show_gpu_monitor,
            ),
            pystray.MenuItem(
                f"🎤 Voice {'ON' if self.voice_enabled else 'OFF'}",
                self._toggle_voice,
            ),
            pystray.MenuItem(
                "─" * 40,
            ),
            pystray.MenuItem("Quit JARVIS", self._quit_app),
        )

    def _show_cluster_status(self, icon, item):
        """Affiche le statut du cluster."""
        msg = (
            f"CLUSTER STATUS\n"
            f"━━━━━━━━━━━━━━━\n"
            f"Active Nodes: {self.cluster.stats.nodes_active}/{self.cluster.stats.nodes_total}\n"
            f"GPU Temp: {self.cluster.stats.gpu_temp:.1f}°C\n"
            f"GPU Usage: {self.cluster.stats.gpu_utilization:.0f}%\n"
            f"RAM: {self.cluster.stats.memory_used:.1f}GB/{self.cluster.stats.memory_total:.1f}GB\n"
            f"Models Loaded: {self.cluster.stats.models_loaded}\n"
            f"Status: {self.cluster.current_status}"
        )
        plyer_notification(
            title="JARVIS Cluster Status",
            message=msg,
            timeout=10,
        )

    def _show_trading_status(self, icon, item):
        """Affiche le statut du trading."""
        msg = (
            f"TRADING STATUS\n"
            f"━━━━━━━━━━━━━━\n"
            f"Pending Signals: {self.trading_stats.signals_pending}\n"
            f"Open Positions: {self.trading_stats.positions_open}\n"
            f"PnL Today: ${self.trading_stats.pnl_today:.2f}\n"
            f"Win Rate: {self.trading_stats.win_rate:.1f}%\n"
            f"Last Trade: {self.trading_stats.last_trade}"
        )
        plyer_notification(
            title="JARVIS Trading Status",
            message=msg,
            timeout=10,
        )

    def _show_gpu_monitor(self, icon, item):
        """Affiche le monitoring GPU."""
        msg = (
            f"GPU MONITORING\n"
            f"━━━━━━━━━━━━━━\n"
            f"Temperature: {self.cluster.stats.gpu_temp:.1f}°C\n"
            f"Utilization: {self.cluster.stats.gpu_utilization:.0f}%\n"
            f"Memory: {self.cluster.stats.memory_used:.1f}GB\n"
            f"Models Running: {self.cluster.stats.models_loaded}"
        )
        plyer_notification(
            title="GPU Monitor",
            message=msg,
            timeout=10,
        )

    def _toggle_voice(self, icon, item):
        """Bascule le mode voice."""
        self.voice_enabled = not self.voice_enabled
        self.db.set_preference("voice_enabled", self.voice_enabled)
        status = "ACTIVÉ" if self.voice_enabled else "DÉSACTIVÉ"
        plyer_notification(
            title="Voice Assistant",
            message=f"Mode voice {status}",
            timeout=3,
        )

    def _show_notification(
        self, level: str, title: str, message: str
    ):
        """Affiche une notification native."""
        if not self.notifications_enabled:
            return

        try:
            plyer_notification(
                title=title,
                message=message,
                timeout=5 if level == "INFO" else 10,
            )
        except Exception as e:
            logging.error(f"Notification error: {e}")

    def _quit_app(self, icon, item):
        """Quitte l'application."""
        self.ws_listener.stop()
        if self.icon:
            self.icon.stop()

    def run(self):
        """Lance le system tray."""
        try:
            # Démarre le WebSocket listener
            self.ws_listener.start()

            # Crée l'icône
            icon_image = DynamicIconGenerator.create_icon(
                status_color=self.cluster.status_color
            )

            self.icon = pystray.Icon(
                "JARVIS",
                icon_image,
                title="JARVIS v10.6",
                menu=self.create_menu(),
            )

            # Update periodic icon
            def update_icon():
                while self.icon and self.icon.visible:
                    try:
                        icon_image = DynamicIconGenerator.create_icon(
                            status_color=self.cluster.status_color
                        )
                        self.icon.icon = icon_image
                        self.icon.title = self.cluster.get_tooltip()
                    except Exception as e:
                        logging.error(f"Icon update error: {e}")
                    asyncio.sleep(5)

            update_thread = threading.Thread(daemon=True, target=update_icon)
            update_thread.start()

            self.icon.run()

        except Exception as e:
            logging.error(f"Tray manager error: {e}")
            self.ws_listener.stop()


def main():
    """Point d'entrée principal."""
    manager = TrayManager()
    manager.run()


if __name__ == "__main__":
    main()
