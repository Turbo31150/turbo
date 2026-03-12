"""Tests for src/windows_feature_manager.py — Windows optional features.

Covers: WindowsFeature, FeatureEvent, WindowsFeatureManager (list_features,
list_enabled, list_disabled, search, is_enabled, count_by_state,
get_events, get_stats), windows_feature_manager singleton.
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

from src.windows_feature_manager import (
    WindowsFeature, FeatureEvent, WindowsFeatureManager, windows_feature_manager,
)

FEATURES_JSON = json.dumps([
    {"FeatureName": "Microsoft-Windows-Subsystem-Linux", "State": 2},
    {"FeatureName": "Microsoft-Hyper-V", "State": 0},
    {"FeatureName": "Containers", "State": "Enabled"},
])


class TestDataclasses:
    def test_feature(self):
        f = WindowsFeature(name="WSL")
        assert f.state == ""

    def test_event(self):
        e = FeatureEvent(action="list_features")
        assert e.success is True


class TestListFeatures:
    def test_success(self):
        wfm = WindowsFeatureManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = FEATURES_JSON
        with patch("subprocess.run", return_value=mock_result):
            features = wfm.list_features()
        assert len(features) == 3
        assert features[0]["state"] == "Enabled"
        assert features[1]["state"] == "Disabled"
        assert features[2]["state"] == "Enabled"

    def test_failure(self):
        wfm = WindowsFeatureManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            assert wfm.list_features() == []


class TestFilterFeatures:
    def test_list_enabled(self):
        wfm = WindowsFeatureManager()
        fake = [{"name": "WSL", "state": "Enabled"}, {"name": "HV", "state": "Disabled"}]
        with patch.object(wfm, "list_features", return_value=fake):
            assert len(wfm.list_enabled()) == 1

    def test_list_disabled(self):
        wfm = WindowsFeatureManager()
        fake = [{"name": "WSL", "state": "Enabled"}, {"name": "HV", "state": "Disabled"}]
        with patch.object(wfm, "list_features", return_value=fake):
            assert len(wfm.list_disabled()) == 1

    def test_search(self):
        wfm = WindowsFeatureManager()
        fake = [{"name": "WSL"}, {"name": "Hyper-V"}]
        with patch.object(wfm, "list_features", return_value=fake):
            assert len(wfm.search("wsl")) == 1

    def test_is_enabled(self):
        wfm = WindowsFeatureManager()
        fake = [{"name": "WSL", "state": "Enabled"}]
        with patch.object(wfm, "list_features", return_value=fake):
            assert wfm.is_enabled("WSL") is True
            assert wfm.is_enabled("nope") is False

    def test_count_by_state(self):
        wfm = WindowsFeatureManager()
        fake = [{"state": "Enabled"}, {"state": "Enabled"}, {"state": "Disabled"}]
        with patch.object(wfm, "list_features", return_value=fake):
            counts = wfm.count_by_state()
        assert counts["Enabled"] == 2
        assert counts["Disabled"] == 1


class TestEventsStats:
    def test_events_empty(self):
        assert WindowsFeatureManager().get_events() == []

    def test_stats(self):
        assert WindowsFeatureManager().get_stats()["total_events"] == 0


class TestSingleton:
    def test_exists(self):
        assert isinstance(windows_feature_manager, WindowsFeatureManager)
