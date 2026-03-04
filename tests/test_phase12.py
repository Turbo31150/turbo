"""Phase 12 Tests — Notification Hub, Feature Flags, Backup Manager, MCP Handlers."""

import asyncio
import json
import tempfile
import time
from pathlib import Path
import pytest


# ═══════════════════════════════════════════════════════════════════════════
# NOTIFICATION HUB
# ═══════════════════════════════════════════════════════════════════════════

class TestNotificationHub:
    @staticmethod
    def _make():
        from src.notification_hub import NotificationHub
        return NotificationHub(log_dir=Path(tempfile.mkdtemp()) / "notif")

    def test_singleton_exists(self):
        from src.notification_hub import notification_hub
        assert notification_hub is not None

    def test_default_channels(self):
        nh = self._make()
        channels = nh.get_channels()
        names = [c["name"] for c in channels]
        assert "console" in names
        assert "file" in names

    def test_send_returns_count(self):
        nh = self._make()
        sent = nh.send("test message", level="info")
        assert sent >= 1  # at least console

    def test_send_warning_both_channels(self):
        nh = self._make()
        sent = nh.send("warning msg", level="warning")
        assert sent >= 2  # console + file

    def test_level_filter(self):
        nh = self._make()
        nh.add_channel("high_only", "console", min_level="critical")
        sent = nh.send("low msg", level="info")
        # high_only should NOT fire for info
        channels = nh.get_channels()
        high_ch = [c for c in channels if c["name"] == "high_only"][0]
        assert high_ch["sent_count"] == 0

    def test_throttle(self):
        nh = self._make()
        nh.add_channel("throttled", "console", throttle_s=10.0)
        nh.send("first", level="info")
        nh.send("second", level="info")  # should be throttled
        channels = nh.get_channels()
        ch = [c for c in channels if c["name"] == "throttled"][0]
        assert ch["sent_count"] == 1  # only first

    def test_disable_channel(self):
        nh = self._make()
        nh.enable_channel("console", False)
        sent = nh.send("test", level="warning")
        # console disabled, only file (warning level)
        channels = nh.get_channels()
        console = [c for c in channels if c["name"] == "console"][0]
        assert console["sent_count"] == 0

    def test_template(self):
        nh = self._make()
        nh.register_template("alert", "[{source}] {message}")
        nh.send("fire!", level="warning", source="GPU", template="alert")
        history = nh.get_history(1)
        assert "[GPU] fire!" in history[0]["message"]

    def test_history(self):
        nh = self._make()
        nh.send("msg1")
        nh.send("msg2")
        history = nh.get_history()
        assert len(history) >= 2

    def test_history_filter_level(self):
        nh = self._make()
        nh.send("info msg", level="info")
        nh.send("warn msg", level="warning")
        history = nh.get_history(level="warning")
        assert all(h["level"] == "warning" for h in history)

    def test_custom_handler(self):
        nh = self._make()
        received = []
        nh.add_channel("custom", "custom", handler=lambda n: received.append(n.message))
        nh.send("hello custom")
        assert "hello custom" in received

    def test_remove_channel(self):
        nh = self._make()
        assert nh.remove_channel("console")
        assert not nh.remove_channel("nonexistent")

    def test_stats(self):
        nh = self._make()
        nh.send("stat msg")
        stats = nh.get_stats()
        assert stats["total_channels"] >= 2
        assert stats["total_sent"] >= 1


# ═══════════════════════════════════════════════════════════════════════════
# FEATURE FLAGS
# ═══════════════════════════════════════════════════════════════════════════

class TestFeatureFlags:
    @staticmethod
    def _make():
        from src.feature_flags import FeatureFlagManager
        return FeatureFlagManager(store_path=Path(tempfile.mkdtemp()) / "flags.json")

    def test_singleton_exists(self):
        from src.feature_flags import feature_flags
        assert feature_flags is not None

    def test_create_and_check(self):
        ff = self._make()
        ff.create("dark_mode", enabled=True)
        assert ff.is_enabled("dark_mode")

    def test_disabled_flag(self):
        ff = self._make()
        ff.create("beta", enabled=False)
        assert not ff.is_enabled("beta")

    def test_nonexistent_flag(self):
        ff = self._make()
        assert not ff.is_enabled("nope")

    def test_toggle(self):
        ff = self._make()
        ff.create("toggle_me", enabled=False)
        ff.toggle("toggle_me")
        assert ff.is_enabled("toggle_me")

    def test_toggle_explicit(self):
        ff = self._make()
        ff.create("explicit", enabled=True)
        ff.toggle("explicit", enabled=False)
        assert not ff.is_enabled("explicit")

    def test_delete(self):
        ff = self._make()
        ff.create("temp", enabled=True)
        assert ff.delete("temp")
        assert not ff.is_enabled("temp")

    def test_whitelist(self):
        ff = self._make()
        ff.create("vip", enabled=True, percentage=0.0, whitelist=["node_A"])
        assert ff.is_enabled("vip", context="node_A")  # whitelisted
        assert not ff.is_enabled("vip", context="node_B")  # 0% rollout

    def test_blacklist(self):
        ff = self._make()
        ff.create("global", enabled=True, blacklist=["banned_node"])
        assert not ff.is_enabled("global", context="banned_node")
        assert ff.is_enabled("global", context="ok_node")

    def test_time_window_not_started(self):
        ff = self._make()
        future = time.time() + 3600
        ff.create("future", enabled=True, start_ts=future)
        assert not ff.is_enabled("future")

    def test_time_window_expired(self):
        ff = self._make()
        past = time.time() - 3600
        ff.create("expired", enabled=True, end_ts=past)
        assert not ff.is_enabled("expired")

    def test_percentage_deterministic(self):
        ff = self._make()
        ff.create("rollout", enabled=True, percentage=50.0)
        # Same context should always give same result
        r1 = ff.is_enabled("rollout", context="user_123")
        r2 = ff.is_enabled("rollout", context="user_123")
        assert r1 == r2

    def test_list_flags(self):
        ff = self._make()
        ff.create("a", enabled=True)
        ff.create("b", enabled=False)
        flags = ff.list_flags()
        assert len(flags) == 2
        names = [f["name"] for f in flags]
        assert "a" in names

    def test_get_flag(self):
        ff = self._make()
        ff.create("detail", enabled=True, description="A test flag")
        flag = ff.get_flag("detail")
        assert flag["description"] == "A test flag"

    def test_persistence(self):
        tmpdir = tempfile.mkdtemp()
        path = Path(tmpdir) / "persist_flags.json"
        from src.feature_flags import FeatureFlagManager
        ff1 = FeatureFlagManager(store_path=path)
        ff1.create("persisted", enabled=True, description="saved")
        ff2 = FeatureFlagManager(store_path=path)
        assert ff2.is_enabled("persisted")

    def test_check_count(self):
        ff = self._make()
        ff.create("counted", enabled=True)
        ff.is_enabled("counted")
        ff.is_enabled("counted")
        flag = ff.get_flag("counted")
        assert flag["check_count"] == 2

    def test_stats(self):
        ff = self._make()
        ff.create("s1", enabled=True)
        ff.create("s2", enabled=False)
        ff.is_enabled("s1")
        stats = ff.get_stats()
        assert stats["total_flags"] == 2
        assert stats["enabled"] == 1
        assert stats["disabled"] == 1
        assert stats["total_checks"] >= 1


# ═══════════════════════════════════════════════════════════════════════════
# BACKUP MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestBackupManager:
    @staticmethod
    def _make():
        from src.backup_manager import BackupManager
        return BackupManager(backup_dir=Path(tempfile.mkdtemp()) / "backups", max_backups=5)

    def test_singleton_exists(self):
        from src.backup_manager import backup_manager
        assert backup_manager is not None

    def test_backup_file(self):
        bm = self._make()
        # Create a temp file to backup
        tmpf = Path(tempfile.mkdtemp()) / "test.txt"
        tmpf.write_text("hello backup")
        entry = bm.backup_file(tmpf, tag="test")
        assert entry is not None
        assert entry.status == "completed"
        assert entry.size_bytes > 0

    def test_backup_nonexistent(self):
        bm = self._make()
        entry = bm.backup_file(Path("/nonexistent/file.txt"))
        assert entry is None

    def test_restore(self):
        bm = self._make()
        tmpf = Path(tempfile.mkdtemp()) / "restore.txt"
        tmpf.write_text("original data")
        entry = bm.backup_file(tmpf)
        # Modify original
        tmpf.write_text("modified")
        # Restore
        assert bm.restore(entry.backup_id)
        assert tmpf.read_text() == "original data"

    def test_delete_backup(self):
        bm = self._make()
        tmpf = Path(tempfile.mkdtemp()) / "del.txt"
        tmpf.write_text("delete me")
        entry = bm.backup_file(tmpf)
        assert bm.delete_backup(entry.backup_id)
        assert len(bm.list_backups()) == 0

    def test_list_backups(self):
        bm = self._make()
        tmpf = Path(tempfile.mkdtemp()) / "list.txt"
        tmpf.write_text("data")
        bm.backup_file(tmpf, tag="v1")
        bm.backup_file(tmpf, tag="v2")
        backups = bm.list_backups()
        assert len(backups) == 2

    def test_list_filter(self):
        bm = self._make()
        t1 = Path(tempfile.mkdtemp()) / "alpha.txt"
        t2 = Path(tempfile.mkdtemp()) / "beta.txt"
        t1.write_text("a")
        t2.write_text("b")
        bm.backup_file(t1)
        bm.backup_file(t2)
        filtered = bm.list_backups(source_filter="alpha")
        assert len(filtered) == 1

    def test_retention(self):
        bm = self._make()  # max_backups=5
        tmpf = Path(tempfile.mkdtemp()) / "ret.txt"
        tmpf.write_text("retention test")
        for i in range(8):
            bm.backup_file(tmpf, tag=f"v{i}")
        backups = bm.list_backups()
        assert len(backups) <= 5

    def test_backup_dir(self):
        bm = self._make()
        src_dir = Path(tempfile.mkdtemp())
        (src_dir / "sub").mkdir()
        (src_dir / "sub" / "file.txt").write_text("nested")
        entry = bm.backup_dir(src_dir)
        assert entry is not None
        assert entry.status == "completed"

    def test_stats(self):
        bm = self._make()
        tmpf = Path(tempfile.mkdtemp()) / "stats.txt"
        tmpf.write_text("stat data")
        bm.backup_file(tmpf)
        stats = bm.get_stats()
        assert stats["total_backups"] == 1
        assert stats["completed"] == 1
        assert stats["total_size_bytes"] > 0

    def test_manifest_persistence(self):
        tmpdir = tempfile.mkdtemp()
        from src.backup_manager import BackupManager
        bm1 = BackupManager(backup_dir=Path(tmpdir) / "bkp", max_backups=10)
        tmpf = Path(tempfile.mkdtemp()) / "persist.txt"
        tmpf.write_text("persist")
        bm1.backup_file(tmpf)
        bm2 = BackupManager(backup_dir=Path(tmpdir) / "bkp", max_backups=10)
        assert len(bm2.list_backups()) == 1


# ═══════════════════════════════════════════════════════════════════════════
# MCP HANDLERS — Phase 12
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPHandlersPhase12:
    def test_notif_channels(self):
        from src.mcp_server import handle_notif_channels
        result = asyncio.run(handle_notif_channels({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_flag_list(self):
        from src.mcp_server import handle_flag_list
        result = asyncio.run(handle_flag_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_flag_check(self):
        from src.mcp_server import handle_flag_check
        result = asyncio.run(handle_flag_check({"name": "nonexistent_flag"}))
        data = json.loads(result[0].text)
        assert data["enabled"] is False

    def test_flag_toggle(self):
        from src.mcp_server import handle_flag_toggle
        result = asyncio.run(handle_flag_toggle({"name": "no_flag"}))
        assert "not found" in result[0].text.lower()

    def test_flag_stats(self):
        from src.mcp_server import handle_flag_stats
        result = asyncio.run(handle_flag_stats({}))
        data = json.loads(result[0].text)
        assert "total_flags" in data

    def test_backup_list(self):
        from src.mcp_server import handle_backup_list
        result = asyncio.run(handle_backup_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_backup_stats(self):
        from src.mcp_server import handle_backup_stats
        result = asyncio.run(handle_backup_stats({}))
        data = json.loads(result[0].text)
        assert "total_backups" in data


# ═══════════════════════════════════════════════════════════════════════════
# TOOL COUNT PHASE 12
# ═══════════════════════════════════════════════════════════════════════════

class TestToolCountPhase12:
    def test_tool_count_at_least_194(self):
        """186 + 1 notif_channels + 4 flag + 3 backup = 194."""
        from src.mcp_server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 194, f"Expected >= 194 tools, got {len(TOOL_DEFINITIONS)}"

    def test_no_duplicate_tool_names(self):
        from src.mcp_server import TOOL_DEFINITIONS
        names = [t[0] for t in TOOL_DEFINITIONS]
        dupes = [n for n in names if names.count(n) > 1]
        assert len(names) == len(set(names)), f"Duplicate tools: {set(dupes)}"
