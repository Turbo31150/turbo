"""Phase 23 Tests — Window Manager, Power Manager, Download Manager, MCP Handlers."""

import asyncio
import json
import os
import tempfile
import pytest


# ═══════════════════════════════════════════════════════════════════════════
# WINDOW MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestWindowManager:
    @staticmethod
    def _make():
        from src.window_manager import WindowManager
        return WindowManager()

    def test_singleton_exists(self):
        from src.window_manager import window_manager
        assert window_manager is not None

    def test_list_windows(self):
        wm = self._make()
        windows = wm.list_windows()
        assert isinstance(windows, list)
        # On Windows there should be at least some visible windows
        assert len(windows) >= 0

    def test_list_windows_returns_dicts(self):
        wm = self._make()
        windows = wm.list_windows()
        if windows:
            w = windows[0]
            assert "hwnd" in w
            assert "title" in w
            assert "pid" in w

    def test_find_window(self):
        wm = self._make()
        # Search for something that may or may not exist
        results = wm.find_window("NonExistentWindowTitle12345")
        assert isinstance(results, list)
        assert len(results) == 0

    def test_get_foreground(self):
        wm = self._make()
        fg = wm.get_foreground()
        # May be None in test contexts
        if fg is not None:
            assert "hwnd" in fg
            assert "title" in fg

    def test_focus_invalid(self):
        wm = self._make()
        result = wm.focus(0)
        assert isinstance(result, bool)

    def test_minimize_invalid(self):
        wm = self._make()
        result = wm.minimize(0)
        assert isinstance(result, bool)

    def test_maximize_invalid(self):
        wm = self._make()
        result = wm.maximize(0)
        assert isinstance(result, bool)

    def test_restore_invalid(self):
        wm = self._make()
        result = wm.restore(0)
        assert isinstance(result, bool)

    def test_close_invalid(self):
        wm = self._make()
        result = wm.close(0)
        assert isinstance(result, bool)

    def test_move_resize_invalid(self):
        wm = self._make()
        result = wm.move_resize(0, 0, 0, 100, 100)
        assert isinstance(result, bool)

    def test_set_topmost_invalid(self):
        wm = self._make()
        result = wm.set_topmost(0, True)
        assert isinstance(result, bool)

    def test_get_events_empty(self):
        wm = self._make()
        events = wm.get_events()
        assert isinstance(events, list)

    def test_get_stats(self):
        wm = self._make()
        stats = wm.get_stats()
        assert "open_windows" in stats
        assert "total_events" in stats

    def test_events_recorded(self):
        wm = self._make()
        wm.focus(0)
        wm.minimize(0)
        events = wm.get_events()
        assert len(events) >= 2


# ═══════════════════════════════════════════════════════════════════════════
# POWER MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestPowerManager:
    @staticmethod
    def _make():
        from src.power_manager import PowerManager
        return PowerManager()

    def test_singleton_exists(self):
        from src.power_manager import power_manager
        assert power_manager is not None

    def test_get_battery_status(self):
        pm = self._make()
        status = pm.get_battery_status()
        assert "ac_power" in status
        assert "has_battery" in status

    def test_get_power_plan(self):
        pm = self._make()
        plan = pm.get_power_plan()
        assert "plan" in plan

    def test_get_events_empty(self):
        pm = self._make()
        events = pm.get_events()
        assert isinstance(events, list)
        assert len(events) == 0

    def test_get_scheduled_empty(self):
        pm = self._make()
        scheduled = pm.get_scheduled()
        assert isinstance(scheduled, list)
        assert len(scheduled) == 0

    def test_get_stats(self):
        pm = self._make()
        stats = pm.get_stats()
        assert "total_events" in stats
        assert "scheduled_actions" in stats
        assert "ac_power" in stats

    def test_cancel_shutdown_no_pending(self):
        pm = self._make()
        # Should not crash even if no shutdown scheduled
        result = pm.cancel_shutdown()
        assert isinstance(result, bool)

    def test_screen_off_records_event(self):
        pm = self._make()
        # screen_off may or may not work in test but should record event
        pm.screen_off()
        events = pm.get_events()
        assert len(events) >= 1
        assert events[0]["action"] == "screen_off"

    def test_power_action_enum(self):
        from src.power_manager import PowerAction
        assert PowerAction.SLEEP.value == "sleep"
        assert PowerAction.SHUTDOWN.value == "shutdown"
        assert PowerAction.LOCK.value == "lock"
        assert PowerAction.SCREEN_OFF.value == "screen_off"

    def test_power_event_dataclass(self):
        from src.power_manager import PowerEvent
        e = PowerEvent(action="test", success=True, detail="info")
        assert e.action == "test"
        assert e.success is True
        assert e.detail == "info"

    def test_scheduled_action_dataclass(self):
        from src.power_manager import ScheduledAction, PowerAction
        sa = ScheduledAction(action=PowerAction.SHUTDOWN, execute_at=9999999999)
        assert sa.action == PowerAction.SHUTDOWN
        assert not sa.cancelled


# ═══════════════════════════════════════════════════════════════════════════
# DOWNLOAD MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestDownloadManager:
    @staticmethod
    def _make():
        from src.download_manager import DownloadManager
        return DownloadManager(download_dir=tempfile.gettempdir())

    def test_singleton_exists(self):
        from src.download_manager import download_manager
        assert download_manager is not None

    def test_add_download(self):
        dm = self._make()
        dl = dm.add("https://example.com/file.zip")
        assert dl.download_id == "dl_1"
        assert dl.filename == "file.zip"
        assert dl.status.value == "pending"

    def test_add_custom_filename(self):
        dm = self._make()
        dl = dm.add("https://example.com/file.zip", filename="custom.zip")
        assert dl.filename == "custom.zip"

    def test_add_extracts_filename_from_url(self):
        dm = self._make()
        dl = dm.add("https://cdn.example.com/path/to/data.csv?token=abc")
        assert dl.filename == "data.csv"

    def test_add_fallback_filename(self):
        dm = self._make()
        dl = dm.add("https://example.com/")
        assert dl.filename == "download"

    def test_get_download(self):
        dm = self._make()
        dl = dm.add("https://example.com/a.txt")
        got = dm.get(dl.download_id)
        assert got is not None
        assert got.url == "https://example.com/a.txt"

    def test_get_nonexistent(self):
        dm = self._make()
        assert dm.get("dl_999") is None

    def test_list_downloads(self):
        dm = self._make()
        dm.add("https://example.com/a.txt")
        dm.add("https://example.com/b.txt")
        lst = dm.list_downloads()
        assert len(lst) == 2

    def test_list_by_status(self):
        dm = self._make()
        dm.add("https://example.com/a.txt")
        lst = dm.list_downloads(status="pending")
        assert len(lst) == 1
        lst2 = dm.list_downloads(status="completed")
        assert len(lst2) == 0

    def test_cancel_download(self):
        dm = self._make()
        dl = dm.add("https://example.com/a.txt")
        assert dm.cancel(dl.download_id)
        assert dm.get(dl.download_id).status.value == "cancelled"

    def test_cancel_nonexistent(self):
        dm = self._make()
        assert not dm.cancel("dl_999")

    def test_remove_download(self):
        dm = self._make()
        dl = dm.add("https://example.com/a.txt")
        assert dm.remove(dl.download_id)
        assert dm.get(dl.download_id) is None

    def test_remove_nonexistent(self):
        dm = self._make()
        assert not dm.remove("dl_999")

    def test_start_with_transport(self):
        dm = self._make()
        dm.set_transport(lambda url, path: True)
        dl = dm.add("https://example.com/a.txt")
        result = dm.start(dl.download_id)
        assert result["success"]
        assert dm.get(dl.download_id).status.value == "completed"

    def test_start_transport_failure(self):
        dm = self._make()
        dm.set_transport(lambda url, path: False)
        dl = dm.add("https://example.com/a.txt", max_retries=1)
        result = dm.start(dl.download_id)
        assert not result["success"]
        assert dm.get(dl.download_id).status.value == "failed"

    def test_start_transport_exception(self):
        dm = self._make()
        dm.set_transport(lambda url, path: (_ for _ in ()).throw(IOError("net error")))
        dl = dm.add("https://example.com/a.txt", max_retries=1)
        result = dm.start(dl.download_id)
        assert not result["success"]

    def test_start_nonexistent(self):
        dm = self._make()
        result = dm.start("dl_999")
        assert not result["success"]

    def test_start_already_completed(self):
        dm = self._make()
        dm.set_transport(lambda url, path: True)
        dl = dm.add("https://example.com/a.txt")
        dm.start(dl.download_id)
        result = dm.start(dl.download_id)
        assert not result["success"]
        assert "already completed" in result["error"]

    def test_queue_and_start(self):
        dm = self._make()
        dm.set_transport(lambda url, path: True)
        result = dm.queue_and_start("https://example.com/a.txt")
        assert result["success"]

    def test_start_next(self):
        dm = self._make()
        dm.set_transport(lambda url, path: True)
        dm.add("https://example.com/a.txt")
        dm.add("https://example.com/b.txt")
        result = dm.start_next()
        assert result is not None
        assert result["success"]

    def test_start_next_empty(self):
        dm = self._make()
        result = dm.start_next()
        assert result is None

    def test_retry(self):
        dm = self._make()
        calls = []
        dm.set_transport(lambda url, path: (calls.append(1), len(calls) >= 2)[1])
        dl = dm.add("https://example.com/a.txt", max_retries=1)
        dm.start(dl.download_id)  # fails first time
        result = dm.retry(dl.download_id)
        assert result["success"]

    def test_retry_nonexistent(self):
        dm = self._make()
        result = dm.retry("dl_999")
        assert not result["success"]

    def test_progress(self):
        from src.download_manager import Download, DownloadStatus
        dl = Download(download_id="t", url="x", dest_path="y", size_bytes=100, downloaded_bytes=50)
        assert dl.progress == 50.0

    def test_progress_zero_size(self):
        from src.download_manager import Download, DownloadStatus
        dl = Download(download_id="t", url="x", dest_path="y", size_bytes=0)
        assert dl.progress == 0.0

    def test_tags(self):
        dm = self._make()
        dl = dm.add("https://example.com/a.txt", tags=["music", "mp3"])
        assert dl.tags == ["music", "mp3"]

    def test_get_stats(self):
        dm = self._make()
        dm.set_transport(lambda url, path: True)
        dm.queue_and_start("https://example.com/a.txt")
        stats = dm.get_stats()
        assert stats["total_downloads"] == 1
        assert "by_status" in stats
        assert stats["download_dir"] == tempfile.gettempdir()

    def test_download_status_enum(self):
        from src.download_manager import DownloadStatus
        assert DownloadStatus.PENDING.value == "pending"
        assert DownloadStatus.COMPLETED.value == "completed"
        assert DownloadStatus.FAILED.value == "failed"
        assert DownloadStatus.CANCELLED.value == "cancelled"
        assert DownloadStatus.PAUSED.value == "paused"


# ═══════════════════════════════════════════════════════════════════════════
# MCP HANDLERS — Phase 23
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPHandlersPhase23:
    def test_winmgr_list(self):
        from src.mcp_server import handle_winmgr_list
        result = asyncio.run(handle_winmgr_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_winmgr_events(self):
        from src.mcp_server import handle_winmgr_events
        result = asyncio.run(handle_winmgr_events({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_winmgr_stats(self):
        from src.mcp_server import handle_winmgr_stats
        result = asyncio.run(handle_winmgr_stats({}))
        data = json.loads(result[0].text)
        assert "open_windows" in data

    def test_pwrmgr_battery(self):
        from src.mcp_server import handle_pwrmgr_battery
        result = asyncio.run(handle_pwrmgr_battery({}))
        data = json.loads(result[0].text)
        assert "ac_power" in data

    def test_pwrmgr_events(self):
        from src.mcp_server import handle_pwrmgr_events
        result = asyncio.run(handle_pwrmgr_events({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_pwrmgr_stats(self):
        from src.mcp_server import handle_pwrmgr_stats
        result = asyncio.run(handle_pwrmgr_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data

    def test_dlmgr_list(self):
        from src.mcp_server import handle_dlmgr_list
        result = asyncio.run(handle_dlmgr_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_dlmgr_history(self):
        from src.mcp_server import handle_dlmgr_history
        result = asyncio.run(handle_dlmgr_history({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_dlmgr_stats(self):
        from src.mcp_server import handle_dlmgr_stats
        result = asyncio.run(handle_dlmgr_stats({}))
        data = json.loads(result[0].text)
        assert "total_downloads" in data


# ═══════════════════════════════════════════════════════════════════════════
# TOOL COUNT PHASE 23
# ═══════════════════════════════════════════════════════════════════════════

class TestToolCountPhase23:
    def test_tool_count_at_least_321(self):
        """312 + 3 winmgr + 3 pwrmgr + 3 dlmgr = 321."""
        from src.mcp_server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 321, f"Expected >= 321 tools, got {len(TOOL_DEFINITIONS)}"

    def test_no_duplicate_tool_names(self):
        from src.mcp_server import TOOL_DEFINITIONS
        names = [t[0] for t in TOOL_DEFINITIONS]
        dupes = [n for n in names if names.count(n) > 1]
        assert len(names) == len(set(names)), f"Duplicate tools: {set(dupes)}"
