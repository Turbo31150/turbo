"""Tests for src/audio_controller.py — Linux audio volume and device management.

Covers: AudioEvent, AudioDevice, AudioController (presets CRUD, _record,
get_events, get_stats), audio_controller singleton.
Note: actual volume/device operations use subprocess and are mocked.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.audio_controller import (
    AudioEvent, AudioDevice, AudioController, audio_controller,
)


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestAudioEvent:
    def test_defaults(self):
        e = AudioEvent(action="mute")
        assert e.success is True
        assert e.detail == ""
        assert e.timestamp > 0


class TestAudioDevice:
    def test_defaults(self):
        d = AudioDevice(name="Speakers")
        assert d.device_id == ""
        assert d.device_type == ""
        assert d.is_default is False


# ===========================================================================
# AudioController — Presets
# ===========================================================================

class TestPresets:
    def test_save_and_list(self):
        ac = AudioController()
        ac.save_preset("quiet", 20)
        ac.save_preset("loud", 80)
        presets = ac.list_presets()
        assert len(presets) == 2
        assert any(p["name"] == "quiet" and p["volume"] == 20 for p in presets)

    def test_save_clamps(self):
        ac = AudioController()
        ac.save_preset("min", -10)
        ac.save_preset("max", 200)
        presets = {p["name"]: p["volume"] for p in ac.list_presets()}
        assert presets["min"] == 0
        assert presets["max"] == 100

    def test_delete_preset(self):
        ac = AudioController()
        ac.save_preset("test", 50)
        assert ac.delete_preset("test") is True
        assert ac.delete_preset("test") is False

    def test_load_preset_not_found(self):
        ac = AudioController()
        result = ac.load_preset("nope")
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_load_preset_success(self):
        ac = AudioController()
        ac.save_preset("quiet", 20)
        with patch("subprocess.run"):
            result = ac.load_preset("quiet")
        assert result["preset"] == "quiet"
        assert result["volume"] == 20


# ===========================================================================
# AudioController — volume/mute (mocked subprocess for Linux pactl/amixer)
# ===========================================================================

class TestVolumeControl:
    def test_set_volume_pactl(self):
        ac = AudioController()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = ac.set_volume(50)
        assert result is True
        assert mock_run.called

    def test_set_volume_clamps(self):
        ac = AudioController()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            ac.set_volume(150)  # should clamp to 100
        events = ac.get_events()
        assert any("100" in e["detail"] for e in events)

    def test_mute(self):
        ac = AudioController()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = ac.mute()
        assert result is True

    def test_unmute(self):
        ac = AudioController()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = ac.unmute()
        assert result is True

    def test_get_volume_error(self):
        ac = AudioController()
        with patch("subprocess.run", side_effect=Exception("fail")):
            result = ac.get_volume()
        assert result["volume"] == -1


# ===========================================================================
# AudioController — events / stats
# ===========================================================================

class TestEventsAndStats:
    def test_events_empty(self):
        ac = AudioController()
        assert ac.get_events() == []

    def test_events_recorded(self):
        ac = AudioController()
        ac._record("test_action", True, "detail")
        events = ac.get_events()
        assert len(events) == 1
        assert events[0]["action"] == "test_action"

    def test_stats(self):
        ac = AudioController()
        ac._record("a", True)
        ac.save_preset("quiet", 20)
        stats = ac.get_stats()
        assert stats["total_events"] == 1
        assert stats["total_presets"] == 1


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert audio_controller is not None
        assert isinstance(audio_controller, AudioController)
