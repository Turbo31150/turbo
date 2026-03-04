"""
JARVIS Notification Center v1.0
Centre de notifications avec historique, filtrage, priorités et export Telegram.
"""

import asyncio
import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from enum import Enum
from collections import deque
import json
import httpx

# Configuration
NOTIF_DB = Path("F:/BUREAU/turbo/jarvis.db")
TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
MAX_HISTORY = 1000
DEFAULT_TTL_SECONDS = 300


class NotificationPriority(Enum):
    LOW = 3
    NORMAL = 2
    HIGH = 1
    CRITICAL = 0


class NotificationCategory(Enum):
    CLUSTER = "cluster"
    TRADING = "trading"
    VOICE = "voice"
    SYSTEM = "system"
    ERROR = "error"


@dataclass
class Notification:
    id: Optional[int] = None
    timestamp: Optional[str] = None
    category: str = "system"
    level: str = "INFO"
    title: str = ""
    message: str = ""
    priority: int = NotificationPriority.NORMAL.value
    ttl_seconds: int = DEFAULT_TTL_SECONDS
    read: bool = False
    sent_to_telegram: bool = False

    def is_expired(self) -> bool:
        """Vérifie si la notification a expiré."""
        if not self.timestamp:
            return False
        try:
            ts = datetime.fromisoformat(self.timestamp)
            return datetime.now() - ts > timedelta(seconds=self.ttl_seconds)
        except Exception:
            return False

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return asdict(self)


class PriorityQueue:
    """Queue de notifications avec priorités."""

    def __init__(self, maxlen: int = MAX_HISTORY):
        self.queue: deque[Notification] = deque(maxlen=maxlen)
        self.lock = asyncio.Lock()

    async def add(self, notification: Notification):
        """Ajoute une notification à la queue."""
        async with self.lock:
            # Insère à la bonne position selon priorité
            inserted = False
            for i, notif in enumerate(self.queue):
                if notification.priority < notif.priority:
                    self.queue.insert(i, notification)
                    inserted = True
                    break
            if not inserted:
                self.queue.append(notification)

    async def get_next(self) -> Optional[Notification]:
        """Récupère la notification suivante."""
        async with self.lock:
            if self.queue:
                return self.queue.popleft()
            return None

    async def peek(self) -> Optional[Notification]:
        """Affiche la prochaine notification sans la retirer."""
        async with self.lock:
            if self.queue:
                return self.queue[0]
            return None

    async def get_all(self) -> List[Notification]:
        """Retourne toutes les notifications actuelles."""
        async with self.lock:
            return list(self.queue)

    async def clear_expired(self):
        """Supprime les notifications expirées."""
        async with self.lock:
            self.queue = deque(
                [n for n in self.queue if not n.is_expired()],
                maxlen=self.queue.maxlen,
            )


class NotificationDatabase:
    """Gère la persistence de l'historique."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialise les tables si nécessaire."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS notifications (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        category TEXT,
                        level TEXT,
                        title TEXT,
                        message TEXT,
                        priority INTEGER DEFAULT 2,
                        ttl_seconds INTEGER DEFAULT 300,
                        read INTEGER DEFAULT 0,
                        sent_to_telegram INTEGER DEFAULT 0
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS notification_filters (
                        id TEXT PRIMARY KEY,
                        category TEXT,
                        enabled INTEGER DEFAULT 1,
                        min_level TEXT DEFAULT 'INFO'
                    )
                """)
                conn.commit()
        except Exception as e:
            logging.error(f"DB init error: {e}")

    def save_notification(self, notif: Notification) -> int:
        """Sauvegarde une notification."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """INSERT INTO notifications
                       (category, level, title, message, priority, ttl_seconds, read)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        notif.category,
                        notif.level,
                        notif.title,
                        notif.message,
                        notif.priority,
                        notif.ttl_seconds,
                        int(notif.read),
                    ),
                )
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logging.error(f"Save notification error: {e}")
            return 0

    def get_history(
        self,
        category: Optional[str] = None,
        limit: int = 100,
    ) -> List[Notification]:
        """Récupère l'historique avec filtres."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = "SELECT * FROM notifications WHERE 1=1"
                params = []

                if category:
                    query += " AND category = ?"
                    params.append(category)

                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)

                cursor = conn.execute(query, params)
                rows = cursor.fetchall()

                notifications = []
                for row in rows:
                    notif = Notification(
                        id=row[0],
                        timestamp=row[1],
                        category=row[2],
                        level=row[3],
                        title=row[4],
                        message=row[5],
                        priority=row[6],
                        ttl_seconds=row[7],
                        read=bool(row[8]),
                        sent_to_telegram=bool(row[9]),
                    )
                    notifications.append(notif)

                return notifications
        except Exception as e:
            logging.error(f"Get history error: {e}")
            return []

    def mark_read(self, notification_id: int):
        """Marque une notification comme lue."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "UPDATE notifications SET read = 1 WHERE id = ?",
                    (notification_id,),
                )
                conn.commit()
        except Exception as e:
            logging.error(f"Mark read error: {e}")

    def mark_sent_telegram(self, notification_id: int):
        """Marque une notification comme envoyée à Telegram."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "UPDATE notifications SET sent_to_telegram = 1 WHERE id = ?",
                    (notification_id,),
                )
                conn.commit()
        except Exception as e:
            logging.error(f"Mark sent error: {e}")


class TelegramExporter:
    """Exporte les notifications vers Telegram."""

    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        self.token = token or "YOUR_BOT_TOKEN"
        self.chat_id = chat_id or "YOUR_CHAT_ID"
        self.enabled = bool(token and chat_id)
        self.client = httpx.AsyncClient(timeout=10.0)

    async def send_notification(self, notif: Notification) -> bool:
        """Envoie une notification à Telegram."""
        if not self.enabled:
            return False

        try:
            emoji_map = {
                "CRITICAL": "🚨",
                "WARNING": "⚠️",
                "INFO": "ℹ️",
                "ERROR": "❌",
            }
            emoji = emoji_map.get(notif.level, "📌")

            message = (
                f"{emoji} <b>{notif.title}</b>\n"
                f"Category: {notif.category}\n"
                f"Level: {notif.level}\n"
                f"─────────────────\n"
                f"{notif.message}\n"
                f"<i>{notif.timestamp}</i>"
            )

            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            response = await self.client.post(
                url,
                json={
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": "HTML",
                },
            )

            return response.status_code == 200
        except Exception as e:
            logging.error(f"Telegram send error: {e}")
            return False

    async def close(self):
        """Ferme le client HTTP."""
        await self.client.aclose()


class NotificationCenter:
    """Centre de notifications principal."""

    def __init__(
        self,
        db_path: Path = NOTIF_DB,
        telegram_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
    ):
        self.db = NotificationDatabase(db_path)
        self.queue = PriorityQueue()
        self.telegram = TelegramExporter(telegram_token, telegram_chat_id)
        self.filters: Dict[str, Dict[str, Any]] = {}
        self._load_filters()

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler("F:/BUREAU/turbo/logs/notifications.log"),
                logging.StreamHandler(),
            ],
        )

    def _load_filters(self):
        """Charge les filtres depuis la DB."""
        try:
            with sqlite3.connect(self.db.db_path) as conn:
                cursor = conn.execute("SELECT * FROM notification_filters")
                for row in cursor:
                    self.filters[row[1]] = {
                        "enabled": bool(row[2]),
                        "min_level": row[3],
                    }
        except Exception as e:
            logging.error(f"Load filters error: {e}")

    def set_filter(self, category: str, enabled: bool, min_level: str = "INFO"):
        """Configure un filtre de catégorie."""
        try:
            with sqlite3.connect(self.db.db_path) as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO notification_filters
                       (id, category, enabled, min_level)
                       VALUES (?, ?, ?, ?)""",
                    (f"filter_{category}", category, int(enabled), min_level),
                )
                conn.commit()
            self.filters[category] = {"enabled": enabled, "min_level": min_level}
        except Exception as e:
            logging.error(f"Set filter error: {e}")

    def _should_process(self, notification: Notification) -> bool:
        """Détermine si la notification doit être traitée."""
        if notification.category not in self.filters:
            return True

        filter_config = self.filters[notification.category]
        if not filter_config["enabled"]:
            return False

        # Vérifie le niveau minimum
        level_order = ["INFO", "WARNING", "CRITICAL", "ERROR"]
        min_level = filter_config.get("min_level", "INFO")

        try:
            notif_level_idx = level_order.index(notification.level)
            min_level_idx = level_order.index(min_level)
            return notif_level_idx >= min_level_idx
        except ValueError:
            return True

    async def add_notification(
        self,
        title: str,
        message: str,
        category: str = "system",
        level: str = "INFO",
        priority: int = NotificationPriority.NORMAL.value,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> Optional[Notification]:
        """Ajoute une notification."""
        notif = Notification(
            category=category,
            level=level,
            title=title,
            message=message,
            priority=priority,
            ttl_seconds=ttl_seconds,
            timestamp=datetime.now().isoformat(),
        )

        if not self._should_process(notif):
            logging.debug(f"Notification filtered: {title}")
            return None

        # Sauvegarde en DB
        notif.id = self.db.save_notification(notif)

        # Ajoute à la queue
        await self.queue.add(notif)

        # Export Telegram si CRITICAL
        if level == "CRITICAL":
            asyncio.create_task(self._export_telegram(notif))

        return notif

    async def _export_telegram(self, notif: Notification):
        """Exporte vers Telegram en arrière-plan."""
        success = await self.telegram.send_notification(notif)
        if success and notif.id:
            self.db.mark_sent_telegram(notif.id)

    async def get_next_notification(self) -> Optional[Notification]:
        """Récupère la prochaine notification."""
        await self.queue.clear_expired()
        notif = await self.queue.get_next()

        if notif and notif.id:
            self.db.mark_read(notif.id)

        return notif

    async def get_all_pending(self) -> List[Notification]:
        """Retourne toutes les notifications en attente."""
        await self.queue.clear_expired()
        return await self.queue.get_all()

    def get_history(
        self,
        category: Optional[str] = None,
        limit: int = 100,
    ) -> List[Notification]:
        """Retourne l'historique."""
        return self.db.get_history(category, limit)

    async def get_stats(self) -> Dict[str, Any]:
        """Retourne les stats du centre."""
        pending = await self.get_all_pending()
        history = self.get_history(limit=1000)

        pending_by_level = {}
        for notif in pending:
            level = notif.level
            pending_by_level[level] = pending_by_level.get(level, 0) + 1

        return {
            "pending_count": len(pending),
            "pending_by_level": pending_by_level,
            "history_total": len(history),
            "telegram_enabled": self.telegram.enabled,
        }

    async def cleanup(self):
        """Nettoie les ressources."""
        await self.queue.clear_expired()
        await self.telegram.close()


# Utilisation simple
async def example_usage():
    """Exemple d'utilisation."""
    center = NotificationCenter()

    # Ajoute une notification
    await center.add_notification(
        title="GPU Temperature Alert",
        message="GPU temperature reached 85°C",
        category="cluster",
        level="WARNING",
        priority=NotificationPriority.HIGH.value,
    )

    # Récupère la prochaine
    notif = await center.get_next_notification()
    if notif:
        print(f"Next: {notif.title}")

    # Stats
    stats = await center.get_stats()
    print(f"Stats: {json.dumps(stats, indent=2)}")

    await center.cleanup()


if __name__ == "__main__":
    asyncio.run(example_usage())
