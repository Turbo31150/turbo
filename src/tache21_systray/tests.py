"""
Tests unitaires pour JARVIS Tache 21
Validation des composants système tray et notifications.
"""

import asyncio
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import tempfile

from notification_center import (
    Notification,
    NotificationPriority,
    NotificationCategory,
    NotificationCenter,
    PriorityQueue,
)
from systray_manager import (
    NotificationThrottler,
    ClusterMonitor,
    DynamicIconGenerator,
)


class TestNotification(unittest.TestCase):
    """Tests pour la classe Notification."""

    def test_notification_creation(self):
        """Crée une notification basique."""
        notif = Notification(
            title="Test",
            message="Message de test",
            category="system",
            level="INFO",
        )
        self.assertEqual(notif.title, "Test")
        self.assertEqual(notif.category, "system")
        self.assertFalse(notif.read)

    def test_notification_expiry(self):
        """Vérifie l'expiration des notifications."""
        # Crée une notification expirée
        past = datetime.now() - timedelta(seconds=400)
        notif = Notification(
            title="Old",
            timestamp=past.isoformat(),
            ttl_seconds=300,
        )
        self.assertTrue(notif.is_expired())

        # Crée une notification récente
        now = datetime.now()
        notif2 = Notification(
            title="New",
            timestamp=now.isoformat(),
            ttl_seconds=300,
        )
        self.assertFalse(notif2.is_expired())

    def test_notification_to_dict(self):
        """Convertit une notification en dict."""
        notif = Notification(
            id=1,
            title="Test",
            message="Message",
            category="cluster",
            level="WARNING",
        )
        d = notif.to_dict()
        self.assertEqual(d["title"], "Test")
        self.assertEqual(d["category"], "cluster")
        self.assertIn("id", d)


class TestNotificationThrottler(unittest.TestCase):
    """Tests pour le throttler anti-spam."""

    def setUp(self):
        self.throttler = NotificationThrottler(window_seconds=1)

    def test_first_notification_allowed(self):
        """La première notification est toujours acceptée."""
        self.assertTrue(self.throttler.can_notify("test"))

    def test_rapid_notifications_blocked(self):
        """Les notifications rapides sont bloquées."""
        self.assertTrue(self.throttler.can_notify("test"))
        self.assertFalse(self.throttler.can_notify("test"))
        self.assertFalse(self.throttler.can_notify("test"))

    def test_different_categories_allowed(self):
        """Les notifications de catégories différentes passent."""
        self.assertTrue(self.throttler.can_notify("cat1"))
        self.assertTrue(self.throttler.can_notify("cat2"))
        self.assertFalse(self.throttler.can_notify("cat1"))
        self.assertTrue(self.throttler.can_notify("cat3"))

    def test_throttle_window_expiry(self):
        """Vérifie l'expiration de la fenêtre."""
        import time

        self.assertTrue(self.throttler.can_notify("test"))
        time.sleep(1.1)
        self.assertTrue(self.throttler.can_notify("test"))


class TestClusterMonitor(unittest.TestCase):
    """Tests pour le monitoring du cluster."""

    def setUp(self):
        self.monitor = ClusterMonitor()

    def test_initial_status(self):
        """Vérifie le statut initial."""
        self.assertEqual(self.monitor.current_status, "OK")
        self.assertEqual(self.monitor.status_color, "green")

    def test_status_update_ok(self):
        """Teste l'update OK."""
        self.monitor.update_from_ws({
            "nodes_active": 6,
            "gpu_temp": 45.0,
        })
        self.assertEqual(self.monitor.current_status, "OK")
        self.assertEqual(self.monitor.status_color, "green")

    def test_status_update_warning(self):
        """Teste l'update WARNING."""
        self.monitor.update_from_ws({
            "nodes_active": 5,
            "gpu_temp": 75.0,
        })
        self.assertEqual(self.monitor.current_status, "WARNING")
        self.assertEqual(self.monitor.status_color, "orange")

    def test_status_update_critical(self):
        """Teste l'update CRITICAL."""
        self.monitor.update_from_ws({
            "nodes_active": 4,
            "gpu_temp": 85.0,
        })
        self.assertEqual(self.monitor.current_status, "CRITICAL")
        self.assertEqual(self.monitor.status_color, "red")

    def test_tooltip_generation(self):
        """Vérifie la génération du tooltip."""
        tooltip = self.monitor.get_tooltip()
        self.assertIn("JARVIS v10.6", tooltip)
        self.assertIn("nodes", tooltip)
        self.assertIn("GPU", tooltip)
        self.assertIn("Status", tooltip)


class TestDynamicIconGenerator(unittest.TestCase):
    """Tests pour le générateur d'icônes."""

    def test_create_green_icon(self):
        """Crée une icône verte."""
        icon = DynamicIconGenerator.create_icon("green")
        self.assertIsNotNone(icon)
        self.assertEqual(icon.size, (64, 64))

    def test_create_orange_icon(self):
        """Crée une icône orange."""
        icon = DynamicIconGenerator.create_icon("orange")
        self.assertIsNotNone(icon)
        self.assertEqual(icon.size, (64, 64))

    def test_create_red_icon(self):
        """Crée une icône rouge."""
        icon = DynamicIconGenerator.create_icon("red")
        self.assertIsNotNone(icon)
        self.assertEqual(icon.size, (64, 64))

    def test_custom_size(self):
        """Crée une icône avec taille personnalisée."""
        icon = DynamicIconGenerator.create_icon(size=128)
        self.assertEqual(icon.size, (128, 128))


class TestPriorityQueue(unittest.TestCase):
    """Tests pour la queue prioritaire."""

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.queue = PriorityQueue()

    def tearDown(self):
        self.loop.close()

    def test_priority_ordering(self):
        """Vérifie l'ordre des priorités."""
        async def test():
            notif_normal = Notification(
                title="Normal",
                priority=NotificationPriority.NORMAL.value,
            )
            notif_high = Notification(
                title="High",
                priority=NotificationPriority.HIGH.value,
            )
            notif_critical = Notification(
                title="Critical",
                priority=NotificationPriority.CRITICAL.value,
            )

            await self.queue.add(notif_normal)
            await self.queue.add(notif_critical)
            await self.queue.add(notif_high)

            # Récupère dans l'ordre de priorité
            n1 = await self.queue.get_next()
            n2 = await self.queue.get_next()
            n3 = await self.queue.get_next()

            self.assertEqual(n1.title, "Critical")
            self.assertEqual(n2.title, "High")
            self.assertEqual(n3.title, "Normal")

        self.loop.run_until_complete(test())

    def test_queue_operations(self):
        """Teste les opérations de queue."""
        async def test():
            notif = Notification(title="Test")
            await self.queue.add(notif)

            # Peek
            peeked = await self.queue.peek()
            self.assertEqual(peeked.title, "Test")

            # Get
            retrieved = await self.queue.get_next()
            self.assertEqual(retrieved.title, "Test")

            # Empty
            empty = await self.queue.peek()
            self.assertIsNone(empty)

        self.loop.run_until_complete(test())


class TestNotificationCenter(unittest.TestCase):
    """Tests pour le centre de notifications."""

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        # DB temporaire
        self.temp_db = tempfile.NamedTemporaryFile(
            suffix=".db",
            delete=False,
        ).name
        self.center = NotificationCenter(Path(self.temp_db))

    def tearDown(self):
        self.loop.close()
        Path(self.temp_db).unlink(missing_ok=True)

    def test_add_notification(self):
        """Ajoute une notification."""
        async def test():
            notif = await self.center.add_notification(
                title="Test",
                message="Message",
                category="system",
                level="INFO",
            )
            self.assertIsNotNone(notif)
            self.assertEqual(notif.title, "Test")

        self.loop.run_until_complete(test())

    def test_notification_filtering(self):
        """Teste le filtrage par catégorie."""
        async def test():
            # Désactive la catégorie 'system'
            self.center.set_filter("system", enabled=False)

            notif = await self.center.add_notification(
                title="System Alert",
                category="system",
            )
            self.assertIsNone(notif)

            # Ajoute dans une catégorie active
            notif2 = await self.center.add_notification(
                title="Cluster Alert",
                category="cluster",
            )
            self.assertIsNotNone(notif2)

        self.loop.run_until_complete(test())

    def test_get_stats(self):
        """Vérifie les stats du centre."""
        async def test():
            await self.center.add_notification(
                title="Alert 1",
                level="INFO",
            )
            await self.center.add_notification(
                title="Alert 2",
                level="WARNING",
            )

            stats = await self.center.get_stats()
            self.assertEqual(stats["pending_count"], 2)
            self.assertIn("INFO", stats["pending_by_level"])
            self.assertIn("WARNING", stats["pending_by_level"])

        self.loop.run_until_complete(test())


# Suite de tests
def suite():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestNotification))
    suite.addTests(loader.loadTestsFromTestCase(TestNotificationThrottler))
    suite.addTests(loader.loadTestsFromTestCase(TestClusterMonitor))
    suite.addTests(loader.loadTestsFromTestCase(TestDynamicIconGenerator))
    suite.addTests(loader.loadTestsFromTestCase(TestPriorityQueue))
    suite.addTests(loader.loadTestsFromTestCase(TestNotificationCenter))

    return suite


if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite())
