"""Tests for src/power_manager.py — Windows power control and monitoring.

Covers: PowerAction, PowerEvent, ScheduledAction, PowerManager (lock_screen,
screen_off, sleep, schedule_shutdown, cancel_shutdown, get_battery_status,
get_power_plan, get_events, get_scheduled, get_stats), power_manager singleton.
All ctypes and subprocess calls are mocked.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.power_manager import (
    PowerAction, PowerEvent, ScheduledAction, PowerManager, power_manager,
)


# ===========================================================================
# Enums / Dataclasses
# ===========================================================================

class TestPowerAction:
    def test_values(self):
        assert PowerAction.SLEEP.value == "sleep"
        assert PowerAction.SHUTDOWN.value == "shutdown"
        assert PowerAction.RESTART.value == "restart"
        assert PowerAction.LOCK.value == "lock"
        assert PowerAction.SCREEN_OFF.value == "screen_off"


class TestPowerEvent:
    def test_defaults(self):
        e = PowerEvent(action="sleep")
        assert e.scheduled is False
        assert e.delay_seconds == 0
        assert e.success is True
        assert e.detail == ""
        assert e.timestamp > 0


class TestScheduledAction:
    def test_defaults(self):
        s = ScheduledAction(action=PowerAction.SHUTDOWN, execute_at=1000.0)
        assert s.cancelled is False
        assert s.created_at > 0


# ===========================================================================
# PowerManager — lock_screen (mocked ctypes)
# ===========================================================================

class TestLockScreen:
    def test_success(self):
        pm = PowerManager()
        with patch("src.power_manager.ctypes") as mock_ct:
            mock_ct.windll.user32.LockWorkStation.return_value = 1
            assert pm.lock_screen() is True
        events = pm.get_events()
        assert events[-1]["action"] == "lock"
        assert events[-1]["success"] is True

    def test_exception(self):
        pm = PowerManager()
        with patch("src.power_manager.ctypes") as mock_ct:
            mock_ct.windll.user32.LockWorkStation.side_effect = Exception("fail")
            assert pm.lock_screen() is False
        events = pm.get_events()
        assert events[-1]["success"] is False


# ===========================================================================
# PowerManager — screen_off (mocked ctypes)
# ===========================================================================

class TestScreenOff:
    def test_success(self):
        pm = PowerManager()
        with patch("src.power_manager.ctypes") as mock_ct:
            mock_ct.windll.user32.SendMessageW.return_value = 0
            assert pm.screen_off() is True

    def test_exception(self):
        pm = PowerManager()
        with patch("src.power_manager.ctypes") as mock_ct:
            mock_ct.windll.user32.SendMessageW.side_effect = Exception("fail")
            assert pm.screen_off() is False


# ===========================================================================
# PowerManager — sleep (mocked subprocess)
# ===========================================================================

class TestSleep:
    def test_success(self):
        pm = PowerManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            assert pm.sleep() is True

    def test_exception(self):
        pm = PowerManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            assert pm.sleep() is False


# ===========================================================================
# PowerManager — schedule_shutdown / cancel_shutdown (mocked subprocess)
# ===========================================================================

class TestShutdown:
    def test_schedule_shutdown(self):
        pm = PowerManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            result = pm.schedule_shutdown(delay_seconds=120)
        assert result["success"] is True
        assert result["action"] == "shutdown"
        assert result["delay"] == 120
        scheduled = pm.get_scheduled()
        assert len(scheduled) == 1
        assert scheduled[0]["action"] == "shutdown"

    def test_schedule_restart(self):
        pm = PowerManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            result = pm.schedule_shutdown(delay_seconds=60, restart=True)
        assert result["action"] == "restart"
        scheduled = pm.get_scheduled()
        assert scheduled[0]["action"] == "restart"

    def test_schedule_shutdown_exception(self):
        pm = PowerManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            result = pm.schedule_shutdown()
        assert result["success"] is False
        assert "error" in result

    def test_cancel_shutdown(self):
        pm = PowerManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            pm.schedule_shutdown(60)
            assert pm.cancel_shutdown() is True
        scheduled = pm.get_scheduled()
        assert scheduled[0]["cancelled"] is True

    def test_cancel_shutdown_exception(self):
        pm = PowerManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            assert pm.cancel_shutdown() is False


# ===========================================================================
# PowerManager — get_battery_status (mocked ctypes)
# ===========================================================================

class TestBattery:
    def test_battery_status(self):
        pm = PowerManager()
        with patch("src.power_manager.ctypes") as mock_ct:
            # Mock the structure creation and GetSystemPowerStatus
            mock_ct.Structure = type("Structure", (), {"_fields_": []})
            mock_ct.wintypes.DWORD = int
            mock_ct.c_byte = int

            def fake_get_status(ref):
                obj = ref._obj_ if hasattr(ref, '_obj_') else ref
                obj.ACLineStatus = 1
                obj.BatteryFlag = 0
                obj.BatteryLifePercent = 85
                obj.BatteryLifeTime = 0xFFFFFFFF
                obj.BatteryFullLifeTime = 0xFFFFFFFF

            mock_ct.windll.kernel32.GetSystemPowerStatus.side_effect = fake_get_status
            mock_ct.byref.return_value = MagicMock()
            # The function calls ctypes internally, we need to mock more deeply
            # Instead, test the fallback path
        # Test exception fallback
        pm2 = PowerManager()
        with patch("src.power_manager.ctypes") as mock_ct:
            mock_ct.Structure = type("S", (), {})
            mock_ct.windll.kernel32.GetSystemPowerStatus.side_effect = Exception("no battery")
            result = pm2.get_battery_status()
        assert result["ac_power"] is True
        assert result["has_battery"] is False


# ===========================================================================
# PowerManager — get_power_plan (mocked subprocess)
# ===========================================================================

class TestPowerPlan:
    def test_get_plan(self):
        pm = PowerManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Power Scheme GUID: 381b4222  (Balanced)"
        with patch("subprocess.run", return_value=mock_result):
            result = pm.get_power_plan()
        assert "Balanced" in result["plan"]

    def test_get_plan_failure(self):
        pm = PowerManager()
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch("subprocess.run", return_value=mock_result):
            result = pm.get_power_plan()
        assert result["plan"] == "unknown"

    def test_get_plan_exception(self):
        pm = PowerManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            result = pm.get_power_plan()
        assert result["plan"] == "unknown"


# ===========================================================================
# PowerManager — events / stats
# ===========================================================================

class TestEventsAndStats:
    def test_events_empty(self):
        pm = PowerManager()
        assert pm.get_events() == []

    def test_events_recorded(self):
        pm = PowerManager()
        pm._record("test", True, "detail")
        events = pm.get_events()
        assert len(events) == 1
        assert events[0]["action"] == "test"

    def test_stats(self):
        pm = PowerManager()
        pm._record("a", True)
        with patch.object(pm, "get_battery_status", return_value={
            "ac_power": True, "battery_percent": None, "has_battery": False
        }):
            stats = pm.get_stats()
        assert stats["total_events"] == 1
        assert stats["scheduled_actions"] == 0
        assert stats["ac_power"] is True


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert power_manager is not None
        assert isinstance(power_manager, PowerManager)
