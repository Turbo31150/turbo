"""Phase 25 Tests — Audio Controller, Startup Manager, Screen Capture, MCP Handlers."""

import asyncio
import json
import os
import tempfile
import pytest


# ═══════════════════════════════════════════════════════════════════════════
# AUDIO CONTROLLER
# ═══════════════════════════════════════════════════════════════════════════

class TestAudioController:
    @staticmethod
    def _make():
        from src.audio_controller import AudioController
        return AudioController()

    def test_singleton_exists(self):
        from src.audio_controller import audio_controller
        assert audio_controller is not None

    def test_save_preset(self):
        ac = self._make()
        ac.save_preset("quiet", 20)
        presets = ac.list_presets()
        assert len(presets) == 1
        assert presets[0]["name"] == "quiet"
        assert presets[0]["volume"] == 20

    def test_save_preset_clamp(self):
        ac = self._make()
        ac.save_preset("max", 150)
        presets = ac.list_presets()
        assert presets[0]["volume"] == 100

    def test_delete_preset(self):
        ac = self._make()
        ac.save_preset("tmp", 50)
        assert ac.delete_preset("tmp")
        assert not ac.delete_preset("tmp")

    def test_load_preset_not_found(self):
        ac = self._make()
        result = ac.load_preset("nonexistent")
        assert not result["success"]

    def test_get_events_empty(self):
        ac = self._make()
        events = ac.get_events()
        assert isinstance(events, list)
        assert len(events) == 0

    def test_record_event(self):
        ac = self._make()
        ac._record("test_action", True, "detail")
        events = ac.get_events()
        assert len(events) == 1
        assert events[0]["action"] == "test_action"

    def test_get_stats(self):
        ac = self._make()
        ac.save_preset("p1", 30)
        ac._record("test", True)
        stats = ac.get_stats()
        assert stats["total_presets"] == 1
        assert stats["total_events"] == 1

    def test_audio_event_dataclass(self):
        from src.audio_controller import AudioEvent
        e = AudioEvent(action="mute", success=True, detail="ok")
        assert e.action == "mute"

    def test_audio_device_dataclass(self):
        from src.audio_controller import AudioDevice
        d = AudioDevice(name="Speakers", device_type="playback")
        assert d.name == "Speakers"
        assert not d.is_default


# ═══════════════════════════════════════════════════════════════════════════
# STARTUP MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestStartupManager:
    @staticmethod
    def _make():
        from src.startup_manager import StartupManager
        return StartupManager()

    def test_singleton_exists(self):
        from src.startup_manager import startup_manager
        assert startup_manager is not None

    def test_list_entries_user(self):
        sm = self._make()
        entries = sm.list_entries("user")
        assert isinstance(entries, list)

    def test_list_entries_invalid_scope(self):
        sm = self._make()
        entries = sm.list_entries("invalid_scope")
        assert entries == []

    def test_list_all(self):
        sm = self._make()
        entries = sm.list_all()
        assert isinstance(entries, list)

    def test_add_and_remove_entry(self):
        sm = self._make()
        name = "JARVISTest25_Startup"
        added = sm.add_entry(name, "notepad.exe", "user")
        if added:
            entries = sm.list_entries("user")
            found = any(e["name"] == name for e in entries)
            assert found
            assert sm.remove_entry(name, "user")

    def test_remove_nonexistent(self):
        sm = self._make()
        assert not sm.remove_entry("NonExistentStartup12345", "user")

    def test_add_invalid_scope(self):
        sm = self._make()
        assert not sm.add_entry("test", "cmd.exe", "invalid")

    def test_search(self):
        sm = self._make()
        results = sm.search("NonExistentProgram12345")
        assert isinstance(results, list)
        assert len(results) == 0

    def test_backup(self):
        sm = self._make()
        backup = sm.backup("user")
        assert isinstance(backup, list)

    def test_get_disabled_empty(self):
        sm = self._make()
        disabled = sm.get_disabled()
        assert isinstance(disabled, list)
        assert len(disabled) == 0

    def test_get_events_empty(self):
        sm = self._make()
        events = sm.get_events()
        assert isinstance(events, list)

    def test_get_stats(self):
        sm = self._make()
        stats = sm.get_stats()
        assert "total_events" in stats
        assert "user_entries" in stats
        assert "disabled_entries" in stats

    def test_startup_entry_dataclass(self):
        from src.startup_manager import StartupEntry
        e = StartupEntry(name="test", command="cmd.exe", scope="user")
        assert e.enabled is True

    def test_startup_keys(self):
        from src.startup_manager import STARTUP_KEYS
        assert "user" in STARTUP_KEYS
        assert "machine" in STARTUP_KEYS


# ═══════════════════════════════════════════════════════════════════════════
# SCREEN CAPTURE
# ═══════════════════════════════════════════════════════════════════════════

class TestScreenCapture:
    @staticmethod
    def _make():
        from src.screen_capture import ScreenCapture
        return ScreenCapture(save_dir=tempfile.mkdtemp())

    def test_singleton_exists(self):
        from src.screen_capture import screen_capture
        assert screen_capture is not None

    def test_get_screen_size(self):
        sc = self._make()
        from unittest.mock import patch
        with patch("src.screen_capture.user32") as mock_u32:
            mock_u32.GetSystemMetrics.side_effect = lambda idx: {0: 1920, 1: 1080}.get(idx, 0)
            size = sc.get_screen_size()
        assert size["width"] > 0
        assert size["height"] > 0

    def test_get_virtual_screen(self):
        sc = self._make()
        from unittest.mock import patch
        metrics = {76: 0, 77: 0, 78: 3840, 79: 1080}
        with patch("src.screen_capture.user32") as mock_u32:
            mock_u32.GetSystemMetrics.side_effect = lambda idx: metrics.get(idx, 0)
            vs = sc.get_virtual_screen()
        assert "width" in vs
        assert vs["width"] > 0

    def test_get_monitor_count(self):
        sc = self._make()
        from unittest.mock import patch
        with patch("src.screen_capture.user32") as mock_u32:
            mock_u32.GetSystemMetrics.return_value = 2
            count = sc.get_monitor_count()
        assert count >= 1

    def test_capture_full(self):
        sc = self._make()
        from unittest.mock import patch, MagicMock
        with patch("src.screen_capture.user32") as mock_u32, \
             patch("src.screen_capture.gdi32") as mock_gdi:
            mock_u32.GetSystemMetrics.side_effect = lambda idx: {0: 1920, 1: 1080}.get(idx, 0)
            mock_u32.GetDC.return_value = 1
            mock_gdi.CreateCompatibleDC.return_value = 2
            mock_gdi.CreateCompatibleBitmap.return_value = 3
            mock_gdi.SelectObject.return_value = 0
            mock_gdi.BitBlt.return_value = 1
            mock_gdi.GetDIBits.return_value = 1080
            cap = sc.capture_full()
        assert cap is not None
        assert os.path.exists(cap.filepath)
        assert cap.size_bytes > 0
        # Cleanup
        os.remove(cap.filepath)

    def test_capture_region(self):
        sc = self._make()
        cap = sc.capture_region(0, 0, 100, 100)
        assert cap is not None
        assert cap.width == 100
        assert cap.height == 100
        assert cap.region == (0, 0, 100, 100)
        os.remove(cap.filepath)

    def test_list_captures(self):
        sc = self._make()
        sc.capture_region(0, 0, 50, 50)
        caps = sc.list_captures()
        assert len(caps) == 1
        # Cleanup
        os.remove(caps[0]["filepath"])

    def test_get_capture(self):
        sc = self._make()
        cap = sc.capture_region(0, 0, 50, 50)
        got = sc.get_capture(cap.capture_id)
        assert got is not None
        assert got.capture_id == cap.capture_id
        os.remove(cap.filepath)

    def test_delete_capture(self):
        sc = self._make()
        cap = sc.capture_region(0, 0, 50, 50)
        assert os.path.exists(cap.filepath)
        assert sc.delete_capture(cap.capture_id)
        assert not os.path.exists(cap.filepath)
        assert sc.get_capture(cap.capture_id) is None

    def test_delete_nonexistent(self):
        sc = self._make()
        assert not sc.delete_capture("cap_999")

    def test_get_events(self):
        sc = self._make()
        sc.capture_region(0, 0, 50, 50)
        events = sc.get_events()
        assert len(events) >= 1
        # Cleanup
        caps = sc.list_captures()
        for c in caps:
            try:
                os.remove(c["filepath"])
            except OSError:
                pass

    def test_get_stats(self):
        sc = self._make()
        from unittest.mock import patch
        metrics = {0: 1920, 1: 1080, 80: 2}
        with patch("src.screen_capture.user32") as mock_u32:
            mock_u32.GetSystemMetrics.side_effect = lambda idx: metrics.get(idx, 0)
            stats = sc.get_stats()
        assert "total_captures" in stats
        assert "screen_width" in stats
        assert "monitor_count" in stats
        assert stats["monitor_count"] >= 1

    def test_capture_info_dataclass(self):
        from src.screen_capture import CaptureInfo
        ci = CaptureInfo(capture_id="t", filepath="/tmp/x.bmp", width=100, height=100)
        assert ci.size_bytes == 0


# ═══════════════════════════════════════════════════════════════════════════
# MCP HANDLERS — Phase 25
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPHandlersPhase25:
    def test_audictl_presets(self):
        from src.mcp_server import handle_audictl_presets
        result = asyncio.run(handle_audictl_presets({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_audictl_events(self):
        from src.mcp_server import handle_audictl_events
        result = asyncio.run(handle_audictl_events({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_audictl_stats(self):
        from src.mcp_server import handle_audictl_stats
        result = asyncio.run(handle_audictl_stats({}))
        data = json.loads(result[0].text)
        assert "total_presets" in data

    def test_startup_list(self):
        from src.mcp_server import handle_startup_list
        result = asyncio.run(handle_startup_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_startup_events(self):
        from src.mcp_server import handle_startup_events
        result = asyncio.run(handle_startup_events({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_startup_stats(self):
        from src.mcp_server import handle_startup_stats
        result = asyncio.run(handle_startup_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data

    def test_scrcap_list(self):
        from src.mcp_server import handle_scrcap_list
        result = asyncio.run(handle_scrcap_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_scrcap_events(self):
        from src.mcp_server import handle_scrcap_events
        result = asyncio.run(handle_scrcap_events({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_scrcap_stats(self):
        from unittest.mock import patch
        metrics = {0: 1920, 1: 1080, 80: 2}
        with patch("src.screen_capture.user32") as mock_u32:
            mock_u32.GetSystemMetrics.side_effect = lambda idx: metrics.get(idx, 0)
            from src.mcp_server import handle_scrcap_stats
            result = asyncio.run(handle_scrcap_stats({}))
        data = json.loads(result[0].text)
        assert "total_captures" in data


# ═══════════════════════════════════════════════════════════════════════════
# TOOL COUNT PHASE 25
# ═══════════════════════════════════════════════════════════════════════════

class TestToolCountPhase25:
    def test_tool_count_at_least_339(self):
        """330 + 3 audictl + 3 startup + 3 scrcap = 339."""
        from src.mcp_server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 339, f"Expected >= 339 tools, got {len(TOOL_DEFINITIONS)}"

    def test_no_duplicate_tool_names(self):
        from src.mcp_server import TOOL_DEFINITIONS
        names = [t[0] for t in TOOL_DEFINITIONS]
        dupes = [n for n in names if names.count(n) > 1]
        assert len(names) == len(set(names)), f"Duplicate tools: {set(dupes)}"
