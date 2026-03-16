"""Phase 24 Tests — Registry Manager, Service Controller, Disk Monitor, MCP Handlers."""

import asyncio
import json
try:
    import winreg
except ImportError:
    winreg = None  # type: ignore[assignment]
import pytest


# ═══════════════════════════════════════════════════════════════════════════
# REGISTRY MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestRegistryManager:
    @staticmethod
    def _make():
        from src.registry_manager import RegistryManager
        return RegistryManager()

    def test_singleton_exists(self):
        from src.registry_manager import registry_manager
        assert registry_manager is not None

    def test_read_known_value(self):
        rm = self._make()
        result = rm.read_value("HKCU", r"Environment", "Path")
        # Path should exist for most users
        assert "value" in result or "error" in result

    def test_read_nonexistent(self):
        rm = self._make()
        result = rm.read_value("HKCU", r"Software\NonExistent12345", "x")
        assert "error" in result

    def test_read_invalid_hive(self):
        rm = self._make()
        result = rm.read_value("INVALID", r"path", "name")
        assert "error" in result

    def test_list_values(self):
        rm = self._make()
        values = rm.list_values("HKCU", r"Environment")
        assert isinstance(values, list)

    def test_list_subkeys(self):
        rm = self._make()
        subkeys = rm.list_subkeys("HKCU", r"Software")
        assert isinstance(subkeys, list)
        assert len(subkeys) > 0

    def test_write_and_delete(self):
        rm = self._make()
        path = r"Software\JARVISTest24"
        wrote = rm.write_value("HKCU", path, "test_val", "hello")
        if wrote:
            result = rm.read_value("HKCU", path, "test_val")
            assert result.get("value") == "hello"
            rm.delete_value("HKCU", path, "test_val")
            # Cleanup: delete key
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
            except Exception:
                pass

    def test_add_favorite(self):
        rm = self._make()
        fav = rm.add_favorite("test_fav", "HKCU", r"Software", "Test bookmark")
        assert fav.name == "test_fav"
        assert len(rm.list_favorites()) == 1

    def test_remove_favorite(self):
        rm = self._make()
        rm.add_favorite("tmp", "HKCU", r"Software")
        assert rm.remove_favorite("tmp")
        assert not rm.remove_favorite("tmp")

    def test_search_values(self):
        rm = self._make()
        results = rm.search_values("HKCU", r"Environment", "path")
        assert isinstance(results, list)

    def test_export_key(self):
        rm = self._make()
        export = rm.export_key("HKCU", r"Environment")
        assert "values" in export
        assert "subkeys" in export
        assert "exported_at" in export

    def test_events_recorded(self):
        rm = self._make()
        rm.read_value("HKCU", r"Environment", "Path")
        events = rm.get_events()
        assert len(events) >= 1

    def test_stats(self):
        rm = self._make()
        rm.add_favorite("f1", "HKCU", r"Software")
        stats = rm.get_stats()
        assert stats["total_favorites"] == 1
        assert "HKCU" in stats["supported_hives"]

    def test_hives_mapping(self):
        from src.registry_manager import HIVES
        assert "HKCU" in HIVES
        assert "HKLM" in HIVES


# ═══════════════════════════════════════════════════════════════════════════
# SERVICE CONTROLLER
# ═══════════════════════════════════════════════════════════════════════════

class TestServiceController:
    @staticmethod
    def _make():
        from src.service_controller import ServiceController
        return ServiceController()

    def test_singleton_exists(self):
        from src.service_controller import service_controller
        assert service_controller is not None

    def test_list_services(self):
        sc = self._make()
        services = sc.list_services()
        assert isinstance(services, list)
        assert len(services) > 0

    def test_list_running(self):
        sc = self._make()
        running = sc.list_services(state="running")
        assert isinstance(running, list)

    def test_get_service_existing(self):
        sc = self._make()
        # Spooler (Print Spooler) should exist on most Windows
        info = sc.get_service("Spooler")
        assert info["exists"] is True or info.get("error")

    def test_get_service_nonexistent(self):
        sc = self._make()
        info = sc.get_service("NonExistentService12345")
        assert info["exists"] is False

    def test_search_services(self):
        sc = self._make()
        results = sc.search("Windows")
        assert isinstance(results, list)

    def test_watch_unwatch(self):
        sc = self._make()
        # Watch a likely-existing service
        services = sc.list_services(state="running")
        if services:
            name = services[0]["name"]
            assert sc.watch(name)
            assert len(sc.list_watched()) == 1
            assert sc.unwatch(name)
            assert len(sc.list_watched()) == 0

    def test_watch_nonexistent(self):
        sc = self._make()
        assert not sc.watch("NonExistentService12345")

    def test_unwatch_nonexistent(self):
        sc = self._make()
        assert not sc.unwatch("NonExistent12345")

    def test_check_watched_empty(self):
        sc = self._make()
        changes = sc.check_watched()
        assert isinstance(changes, list)
        assert len(changes) == 0

    def test_get_events_empty(self):
        sc = self._make()
        events = sc.get_events()
        assert isinstance(events, list)

    def test_get_stats(self):
        sc = self._make()
        stats = sc.get_stats()
        assert "total_events" in stats
        assert "watched_services" in stats

    def test_service_info_dataclass(self):
        from src.service_controller import ServiceInfo
        si = ServiceInfo(name="test", display_name="Test Service", status="RUNNING")
        assert si.name == "test"
        assert si.status == "RUNNING"


# ═══════════════════════════════════════════════════════════════════════════
# DISK MONITOR
# ═══════════════════════════════════════════════════════════════════════════

class TestDiskMonitor:
    @staticmethod
    def _make():
        from src.disk_monitor import DiskMonitor
        return DiskMonitor()

    def test_singleton_exists(self):
        from src.disk_monitor import disk_monitor
        assert disk_monitor is not None

    def test_list_drives(self):
        dm = self._make()
        drives = dm.list_drives()
        assert isinstance(drives, list)
        assert len(drives) >= 1
        # C: should exist
        c_drive = [d for d in drives if d["letter"] == "C"]
        assert len(c_drive) == 1
        assert c_drive[0]["total_gb"] > 0

    def test_get_drive(self):
        dm = self._make()
        info = dm.get_drive("C")
        assert info["letter"] == "C"
        assert info["total_gb"] > 0
        assert info["free_gb"] >= 0

    def test_get_drive_nonexistent(self):
        dm = self._make()
        info = dm.get_drive("Z")
        # May have error or just 0 values
        assert "letter" in info

    def test_set_threshold(self):
        dm = self._make()
        dm.set_threshold("C", 95.0)
        stats = dm.get_stats()
        assert "C" in stats["thresholds"]
        assert stats["thresholds"]["C"] == 95.0

    def test_remove_threshold(self):
        dm = self._make()
        dm.set_threshold("C", 90.0)
        assert dm.remove_threshold("C")
        assert not dm.remove_threshold("C")

    def test_check_thresholds(self):
        dm = self._make()
        dm.set_threshold("C", 1.0)  # Very low threshold, should trigger
        alerts = dm.check_thresholds()
        assert len(alerts) >= 1
        assert alerts[0]["drive"] == "C"

    def test_check_thresholds_no_trigger(self):
        dm = self._make()
        dm.set_threshold("C", 99.9)  # Very high, unlikely to trigger
        alerts = dm.check_thresholds()
        # May or may not trigger depending on disk usage
        assert isinstance(alerts, list)

    def test_get_alerts(self):
        dm = self._make()
        alerts = dm.get_alerts()
        assert isinstance(alerts, list)

    def test_take_snapshot(self):
        dm = self._make()
        snap = dm.take_snapshot()
        assert snap.snapshot_id == "dsnap_1"
        assert len(snap.drives) >= 1

    def test_list_snapshots(self):
        dm = self._make()
        dm.take_snapshot()
        dm.take_snapshot()
        snaps = dm.list_snapshots()
        assert len(snaps) == 2

    def test_compare_snapshots(self):
        dm = self._make()
        s1 = dm.take_snapshot()
        s2 = dm.take_snapshot()
        diff = dm.compare_snapshots(s1.snapshot_id, s2.snapshot_id)
        assert "changes" in diff

    def test_compare_nonexistent(self):
        dm = self._make()
        diff = dm.compare_snapshots("dsnap_999", "dsnap_998")
        assert "error" in diff

    def test_get_stats(self):
        dm = self._make()
        stats = dm.get_stats()
        assert "drive_count" in stats
        assert stats["drive_count"] >= 1
        assert "total_space_gb" in stats
        assert "total_free_gb" in stats

    def test_drive_types(self):
        from src.disk_monitor import DRIVE_TYPES
        assert DRIVE_TYPES[3] == "fixed"
        assert DRIVE_TYPES[2] == "removable"


# ═══════════════════════════════════════════════════════════════════════════
# MCP HANDLERS — Phase 24
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPHandlersPhase24:
    def test_regmgr_favorites(self):
        from src.mcp_server import handle_regmgr_favorites
        result = asyncio.run(handle_regmgr_favorites({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_regmgr_events(self):
        from src.mcp_server import handle_regmgr_events
        result = asyncio.run(handle_regmgr_events({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_regmgr_stats(self):
        from src.mcp_server import handle_regmgr_stats
        result = asyncio.run(handle_regmgr_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data

    def test_svcctl_list(self):
        from src.mcp_server import handle_svcctl_list
        result = asyncio.run(handle_svcctl_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_svcctl_events(self):
        from src.mcp_server import handle_svcctl_events
        result = asyncio.run(handle_svcctl_events({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_svcctl_stats(self):
        from src.mcp_server import handle_svcctl_stats
        result = asyncio.run(handle_svcctl_stats({}))
        data = json.loads(result[0].text)
        assert "total_events" in data

    def test_diskmon_drives(self):
        from src.mcp_server import handle_diskmon_drives
        result = asyncio.run(handle_diskmon_drives({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_diskmon_alerts(self):
        from src.mcp_server import handle_diskmon_alerts
        result = asyncio.run(handle_diskmon_alerts({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_diskmon_stats(self):
        from src.mcp_server import handle_diskmon_stats
        result = asyncio.run(handle_diskmon_stats({}))
        data = json.loads(result[0].text)
        assert "drive_count" in data


# ═══════════════════════════════════════════════════════════════════════════
# TOOL COUNT PHASE 24
# ═══════════════════════════════════════════════════════════════════════════

class TestToolCountPhase24:
    def test_tool_count_at_least_330(self):
        """321 + 3 regmgr + 3 svcctl + 3 diskmon = 330."""
        from src.mcp_server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 330, f"Expected >= 330 tools, got {len(TOOL_DEFINITIONS)}"

    def test_no_duplicate_tool_names(self):
        from src.mcp_server import TOOL_DEFINITIONS
        names = [t[0] for t in TOOL_DEFINITIONS]
        dupes = [n for n in names if names.count(n) > 1]
        assert len(names) == len(set(names)), f"Duplicate tools: {set(dupes)}"
