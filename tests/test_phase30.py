"""Phase 30 Tests — Certificate Manager, Virtual Desktop, Notification Manager, MCP Handlers."""

import asyncio
import json
import pytest


# ═══════════════════════════════════════════════════════════════════════════
# CERTIFICATE MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestCertificateManager:
    @staticmethod
    def _make():
        from src.certificate_manager import CertificateManager
        return CertificateManager()

    def test_singleton_exists(self):
        from src.certificate_manager import certificate_manager
        assert certificate_manager is not None

    def test_get_events_empty(self):
        cm = self._make()
        events = cm.get_events()
        assert isinstance(events, list)
        assert len(events) == 0

    def test_record_event(self):
        cm = self._make()
        cm._record("test", True, "ok")
        events = cm.get_events()
        assert len(events) == 1
        assert events[0]["action"] == "test"

    def test_cert_info_dataclass(self):
        from src.certificate_manager import CertInfo
        c = CertInfo(subject="CN=Test", issuer="CN=CA", thumbprint="ABC123")
        assert c.subject == "CN=Test"
        assert c.store == ""

    def test_cert_event_dataclass(self):
        from src.certificate_manager import CertEvent
        e = CertEvent(action="list")
        assert e.action == "list"
        assert e.success is True

    def test_known_stores(self):
        from src.certificate_manager import CERT_STORES
        assert len(CERT_STORES) >= 3
        assert any("Root" in s for s in CERT_STORES)

    def test_list_stores(self):
        cm = self._make()
        stores = cm.list_stores()
        assert isinstance(stores, list)
        assert len(stores) >= 3

    def test_get_stats_structure(self):
        cm = self._make()
        stats = cm.get_stats()
        assert "total_events" in stats
        assert "known_stores" in stats

    def test_search_with_mock(self):
        cm = self._make()
        cm.list_certs = lambda store="": [
            {"subject": "CN=Test", "thumbprint": "A"},
            {"subject": "CN=Other", "thumbprint": "B"},
        ]
        results = cm.search("test")
        assert len(results) == 1


# ═══════════════════════════════════════════════════════════════════════════
# VIRTUAL DESKTOP
# ═══════════════════════════════════════════════════════════════════════════

class TestVirtualDesktop:
    @staticmethod
    def _make():
        from src.virtual_desktop import VirtualDesktopManager
        return VirtualDesktopManager()

    def test_singleton_exists(self):
        from src.virtual_desktop import virtual_desktop
        assert virtual_desktop is not None

    def test_get_events_empty(self):
        vd = self._make()
        events = vd.get_events()
        assert isinstance(events, list)
        assert len(events) == 0

    def test_record_event(self):
        vd = self._make()
        vd._record("test", True, "ok")
        events = vd.get_events()
        assert len(events) == 1

    def test_desktop_info_dataclass(self):
        from src.virtual_desktop import DesktopInfo
        d = DesktopInfo(index=0, name="Desktop 1", is_current=True)
        assert d.index == 0
        assert d.is_current is True

    def test_desktop_event_dataclass(self):
        from src.virtual_desktop import DesktopEvent
        e = DesktopEvent(action="list")
        assert e.action == "list"
        assert e.success is True

    def test_get_screen_info(self):
        vd = self._make()
        from unittest.mock import patch
        metrics = {0: 1920, 1: 1080, 78: 3840, 79: 1080, 80: 2}
        with patch("src.virtual_desktop.user32") as mock_u32:
            mock_u32.GetSystemMetrics.side_effect = lambda idx: metrics.get(idx, 0)
            info = vd.get_screen_info()
        assert "width" in info
        assert "height" in info
        assert info["width"] > 0
        assert info["monitors"] >= 1

    def test_get_stats_structure(self):
        vd = self._make()
        stats = vd.get_stats()
        assert "total_events" in stats


# ═══════════════════════════════════════════════════════════════════════════
# NOTIFICATION MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestNotificationManager:
    @staticmethod
    def _make():
        from src.notification_manager import NotificationManager
        return NotificationManager()

    def test_singleton_exists(self):
        from src.notification_manager import notification_manager
        assert notification_manager is not None

    def test_get_events_empty(self):
        nm = self._make()
        events = nm.get_events()
        assert isinstance(events, list)
        assert len(events) == 0

    def test_record_event(self):
        nm = self._make()
        nm._record("test", True, "ok")
        events = nm.get_events()
        assert len(events) == 1

    def test_notification_dataclass(self):
        from src.notification_manager import Notification
        n = Notification(title="Test", message="Hello")
        assert n.title == "Test"
        assert n.priority == "normal"
        assert n.sent is False

    def test_notif_event_dataclass(self):
        from src.notification_manager import NotifEvent
        e = NotifEvent(action="send")
        assert e.action == "send"
        assert e.success is True

    def test_list_templates(self):
        nm = self._make()
        templates = nm.list_templates()
        assert "info" in templates
        assert "warning" in templates
        assert "error" in templates

    def test_add_template(self):
        nm = self._make()
        nm.add_template("custom", "Custom Alert", "high")
        templates = nm.list_templates()
        assert "custom" in templates
        assert templates["custom"]["priority"] == "high"

    def test_get_history_empty(self):
        nm = self._make()
        history = nm.get_history()
        assert isinstance(history, list)
        assert len(history) == 0

    def test_clear_history(self):
        nm = self._make()
        nm._history.append(
            __import__("src.notification_manager", fromlist=["Notification"]).Notification(
                title="T", message="M"))
        count = nm.clear_history()
        assert count == 1
        assert len(nm.get_history()) == 0

    def test_search_history(self):
        nm = self._make()
        Notif = __import__("src.notification_manager", fromlist=["Notification"]).Notification
        nm._history.append(Notif(title="Alert", message="Disk full"))
        nm._history.append(Notif(title="Info", message="Update OK"))
        results = nm.search_history("disk")
        assert len(results) == 1

    def test_get_stats_structure(self):
        nm = self._make()
        stats = nm.get_stats()
        assert "total_notifications" in stats
        assert "sent_success" in stats
        assert "templates" in stats


# ═══════════════════════════════════════════════════════════════════════════
# MCP HANDLERS — Phase 30
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPHandlersPhase30:
    def test_certmgr_events(self):
        from src.mcp_server import handle_certmgr_events
        result = asyncio.run(handle_certmgr_events({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_certmgr_stats(self):
        from src.mcp_server import handle_certmgr_stats
        result = asyncio.run(handle_certmgr_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data

    def test_vdesk_events(self):
        from src.mcp_server import handle_vdesk_events
        result = asyncio.run(handle_vdesk_events({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_vdesk_stats(self):
        from src.mcp_server import handle_vdesk_stats
        result = asyncio.run(handle_vdesk_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data

    def test_notifmgr_events(self):
        from src.mcp_server import handle_notifmgr_events
        result = asyncio.run(handle_notifmgr_events({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_notifmgr_stats(self):
        from src.mcp_server import handle_notifmgr_stats
        result = asyncio.run(handle_notifmgr_stats({}))
        data = json.loads(result[0].text)
        assert "total_notifications" in data


# ═══════════════════════════════════════════════════════════════════════════
# TOOL COUNT PHASE 30
# ═══════════════════════════════════════════════════════════════════════════

class TestToolCountPhase30:
    def test_tool_count_at_least_384(self):
        """375 + 3 certmgr + 3 vdesk + 3 notifmgr = 384."""
        from src.mcp_server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 384, f"Expected >= 384 tools, got {len(TOOL_DEFINITIONS)}"

    def test_no_duplicate_tool_names(self):
        from src.mcp_server import TOOL_DEFINITIONS
        names = [t[0] for t in TOOL_DEFINITIONS]
        dupes = [n for n in names if names.count(n) > 1]
        assert len(names) == len(set(names)), f"Duplicate tools: {set(dupes)}"
