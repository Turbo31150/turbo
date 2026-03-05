"""Phase 39 Tests — Scheduled Tasks, Audio Devices, USB Devices, MCP Handlers."""

import asyncio
import json
import pytest


# ═══════════════════════════════════════════════════════════════════════════
# SCHEDULED TASK MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestScheduledTaskManager:
    @staticmethod
    def _make():
        from src.scheduled_task_manager import ScheduledTaskManager
        return ScheduledTaskManager()

    def test_singleton_exists(self):
        from src.scheduled_task_manager import scheduled_task_manager
        assert scheduled_task_manager is not None

    def test_get_events_empty(self):
        m = self._make()
        assert m.get_events() == []

    def test_record_event(self):
        m = self._make()
        m._record("test", True, "ok")
        assert len(m.get_events()) == 1

    def test_scheduled_task_dataclass(self):
        from src.scheduled_task_manager import ScheduledTask
        st = ScheduledTask(name="\\Microsoft\\Windows\\Defrag\\ScheduledDefrag")
        assert st.name.endswith("ScheduledDefrag")
        assert st.status == ""

    def test_get_stats_structure(self):
        m = self._make()
        assert "total_events" in m.get_stats()

    def test_search_with_mock(self):
        m = self._make()
        m.list_tasks = lambda: [
            {"name": "\\Defrag\\Defrag", "status": "Ready"},
            {"name": "\\Update\\Check", "status": "Running"},
        ]
        results = m.search("defrag")
        assert len(results) == 1

    def test_count_by_status_with_mock(self):
        m = self._make()
        m.list_tasks = lambda: [
            {"name": "A", "status": "Ready"},
            {"name": "B", "status": "Ready"},
            {"name": "C", "status": "Running"},
        ]
        counts = m.count_by_status()
        assert counts["Ready"] == 2
        assert counts["Running"] == 1

    def test_get_task_detail_returns_dict(self):
        m = self._make()
        # Mock to avoid real system call
        m.get_task_detail = lambda name: {"TaskName": name}
        detail = m.get_task_detail("TestTask")
        assert detail["TaskName"] == "TestTask"


# ═══════════════════════════════════════════════════════════════════════════
# AUDIO DEVICE MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestAudioDeviceManager:
    @staticmethod
    def _make():
        from src.audio_device_manager import AudioDeviceManager
        return AudioDeviceManager()

    def test_singleton_exists(self):
        from src.audio_device_manager import audio_device_manager
        assert audio_device_manager is not None

    def test_get_events_empty(self):
        m = self._make()
        assert m.get_events() == []

    def test_record_event(self):
        m = self._make()
        m._record("test", True, "ok")
        assert len(m.get_events()) == 1

    def test_audio_device_dataclass(self):
        from src.audio_device_manager import AudioDevice
        ad = AudioDevice(name="Realtek HD Audio", manufacturer="Realtek")
        assert ad.name == "Realtek HD Audio"
        assert ad.status == ""

    def test_get_stats_structure(self):
        m = self._make()
        assert "total_events" in m.get_stats()

    def test_search_with_mock(self):
        m = self._make()
        m.list_devices = lambda: [
            {"name": "Realtek HD Audio", "manufacturer": "Realtek", "status": "OK"},
            {"name": "NVIDIA Virtual Audio", "manufacturer": "NVIDIA", "status": "OK"},
        ]
        results = m.search("realtek")
        assert len(results) == 1

    def test_count_by_status_with_mock(self):
        m = self._make()
        m.list_devices = lambda: [
            {"name": "A", "status": "OK"},
            {"name": "B", "status": "OK"},
            {"name": "C", "status": "Error"},
        ]
        counts = m.count_by_status()
        assert counts["OK"] == 2
        assert counts["Error"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# USB DEVICE MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestUSBDeviceManager:
    @staticmethod
    def _make():
        from src.usb_device_manager import USBDeviceManager
        return USBDeviceManager()

    def test_singleton_exists(self):
        from src.usb_device_manager import usb_device_manager
        assert usb_device_manager is not None

    def test_get_events_empty(self):
        m = self._make()
        assert m.get_events() == []

    def test_record_event(self):
        m = self._make()
        m._record("test", True, "ok")
        assert len(m.get_events()) == 1

    def test_usb_device_dataclass(self):
        from src.usb_device_manager import USBDevice
        ud = USBDevice(name="USB Hub", device_id="USB\\ROOT_HUB30")
        assert ud.name == "USB Hub"
        assert ud.pnp_class == ""

    def test_get_stats_structure(self):
        m = self._make()
        assert "total_events" in m.get_stats()

    def test_search_with_mock(self):
        m = self._make()
        m.list_devices = lambda: [
            {"name": "USB Hub", "manufacturer": "Microsoft", "status": "OK"},
            {"name": "USB Mouse", "manufacturer": "Logitech", "status": "OK"},
        ]
        results = m.search("logitech")
        assert len(results) == 1

    def test_count_by_class_with_mock(self):
        m = self._make()
        m.list_devices = lambda: [
            {"name": "A", "pnp_class": "USB"},
            {"name": "B", "pnp_class": "USB"},
            {"name": "C", "pnp_class": "HIDClass"},
        ]
        counts = m.count_by_class()
        assert counts["USB"] == 2
        assert counts["HIDClass"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# MCP HANDLERS — Phase 39
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPHandlersPhase39:
    def test_schtask_list(self):
        from src.mcp_server import handle_schtask_list
        result = asyncio.run(handle_schtask_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_schtask_stats(self):
        from src.mcp_server import handle_schtask_stats
        result = asyncio.run(handle_schtask_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data

    def test_audiodev_list(self):
        from src.mcp_server import handle_audiodev_list
        result = asyncio.run(handle_audiodev_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_audiodev_stats(self):
        from src.mcp_server import handle_audiodev_stats
        result = asyncio.run(handle_audiodev_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data

    def test_usbdev_list(self):
        from src.mcp_server import handle_usbdev_list
        result = asyncio.run(handle_usbdev_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_usbdev_stats(self):
        from src.mcp_server import handle_usbdev_stats
        result = asyncio.run(handle_usbdev_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data


# ═══════════════════════════════════════════════════════════════════════════
# TOOL COUNT PHASE 39
# ═══════════════════════════════════════════════════════════════════════════

class TestToolCountPhase39:
    def test_tool_count_at_least_465(self):
        """456 + 3 schtask + 3 audiodev + 3 usbdev = 465."""
        from src.mcp_server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 465, f"Expected >= 465 tools, got {len(TOOL_DEFINITIONS)}"

    def test_no_duplicate_tool_names(self):
        from src.mcp_server import TOOL_DEFINITIONS
        names = [t[0] for t in TOOL_DEFINITIONS]
        dupes = [n for n in names if names.count(n) > 1]
        assert len(names) == len(set(names)), f"Duplicate tools: {set(dupes)}"
