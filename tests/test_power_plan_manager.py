"""Tests for src/power_plan_manager.py — Windows power plans.

Covers: PowerPlan, PowerEvent, PowerPlanManager (list_plans, get_active_plan,
get_battery_status, get_events, get_stats), power_plan_manager singleton.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.power_plan_manager import (
    PowerPlan, PowerEvent, PowerPlanManager, power_plan_manager,
)

POWERCFG_OUTPUT = """\
Existing Power Schemes (* Active)
-----------------------------------
Power Scheme GUID: 381b4222-f694-41f0-9685-ff5bb260df2e  (Balanced) *
Power Scheme GUID: 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c  (High performance)
Power Scheme GUID: a1841308-3541-4fab-bc81-f71556f20b4a  (Power saver)
"""

BATTERY_JSON = json.dumps({
    "Name": "Internal Battery",
    "EstimatedChargeRemaining": 85,
    "BatteryStatus": 2,
    "EstimatedRunTime": 240,
})


class TestDataclasses:
    def test_power_plan(self):
        p = PowerPlan(name="Balanced")
        assert p.guid == ""
        assert p.is_active is False

    def test_power_event(self):
        e = PowerEvent(action="list_plans")
        assert e.success is True


class TestListPlans:
    def test_success(self):
        pm = PowerPlanManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = POWERCFG_OUTPUT
        with patch("subprocess.run", return_value=mock_result):
            plans = pm.list_plans()
        assert len(plans) == 3
        assert plans[0]["name"] == "Balanced"
        assert plans[0]["is_active"] is True
        assert plans[1]["name"] == "High performance"
        assert plans[1]["is_active"] is False

    def test_failure(self):
        pm = PowerPlanManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            assert pm.list_plans() == []


class TestGetActivePlan:
    def test_active_found(self):
        pm = PowerPlanManager()
        fake = [
            {"name": "Balanced", "guid": "abc", "is_active": True},
            {"name": "High", "guid": "def", "is_active": False},
        ]
        with patch.object(pm, "list_plans", return_value=fake):
            active = pm.get_active_plan()
        assert active["name"] == "Balanced"

    def test_no_active(self):
        pm = PowerPlanManager()
        with patch.object(pm, "list_plans", return_value=[]):
            active = pm.get_active_plan()
        assert active["name"] == "Unknown"


class TestGetBatteryStatus:
    def test_success(self):
        pm = PowerPlanManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = BATTERY_JSON
        with patch("subprocess.run", return_value=mock_result):
            bat = pm.get_battery_status()
        assert bat["charge_percent"] == 85
        assert bat["estimated_runtime_min"] == 240

    def test_failure(self):
        pm = PowerPlanManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            bat = pm.get_battery_status()
        assert bat["charge_percent"] == 0


class TestEventsStats:
    def test_events_empty(self):
        assert PowerPlanManager().get_events() == []

    def test_stats(self):
        assert PowerPlanManager().get_stats()["total_events"] == 0


class TestSingleton:
    def test_exists(self):
        assert isinstance(power_plan_manager, PowerPlanManager)
