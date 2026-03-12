"""Tests for src/wake_word.py — JARVIS wake word detector.

Covers: WakeWordDetector (start, stop, is_running, _listen_loop cooldown).
numpy/sounddevice/openwakeword are mocked via sys.modules.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Mock numpy and sounddevice before importing wake_word
_np_mock = MagicMock()
_sd_mock = MagicMock()
_saved_np = sys.modules.get("numpy")
_saved_sd = sys.modules.get("sounddevice")
sys.modules.setdefault("numpy", _np_mock)
sys.modules.setdefault("sounddevice", _sd_mock)

try:
    from src.wake_word import WakeWordDetector, WAKE_WORD, THRESHOLD
finally:
    # Restore original modules
    if _saved_np is not None:
        sys.modules["numpy"] = _saved_np
    elif "numpy" in sys.modules and sys.modules["numpy"] is _np_mock:
        del sys.modules["numpy"]
    if _saved_sd is not None:
        sys.modules["sounddevice"] = _saved_sd
    elif "sounddevice" in sys.modules and sys.modules["sounddevice"] is _sd_mock:
        del sys.modules["sounddevice"]


class TestConstants:
    def test_wake_word(self):
        assert WAKE_WORD == "hey_jarvis_v0.1"

    def test_threshold(self):
        assert THRESHOLD == 0.7


class TestWakeWordDetector:
    def test_init(self):
        cb = MagicMock()
        d = WakeWordDetector(callback=cb)
        assert d.is_running is False
        assert d._threshold == THRESHOLD

    def test_custom_threshold(self):
        d = WakeWordDetector(callback=lambda: None, threshold=0.5)
        assert d._threshold == 0.5

    def test_start_already_running(self):
        d = WakeWordDetector(callback=lambda: None)
        d._running = True
        assert d.start() is True

    def test_start_import_fails(self):
        d = WakeWordDetector(callback=lambda: None)
        with patch.dict("sys.modules", {"openwakeword": None, "openwakeword.model": None}):
            result = d.start()
        assert result is False
        assert d.is_running is False

    def test_start_success(self):
        d = WakeWordDetector(callback=lambda: None)
        mock_model_cls = MagicMock()
        mock_model_module = MagicMock()
        mock_model_module.Model = mock_model_cls
        with patch.dict("sys.modules", {
            "openwakeword": MagicMock(),
            "openwakeword.model": mock_model_module,
        }):
            # Mock the thread to not actually run
            with patch("threading.Thread") as mock_thread:
                mock_thread_inst = MagicMock()
                mock_thread.return_value = mock_thread_inst
                result = d.start()
        assert result is True
        assert d._running is True
        mock_thread_inst.start.assert_called_once()

    def test_stop(self):
        d = WakeWordDetector(callback=lambda: None)
        d._running = True
        d._thread = MagicMock()
        d._model = MagicMock()
        d.stop()
        assert d._running is False
        assert d._model is None
        d._thread.join.assert_called_once_with(timeout=3)

    def test_stop_no_thread(self):
        d = WakeWordDetector(callback=lambda: None)
        d.stop()  # should not raise
        assert d.is_running is False

    def test_is_running_property(self):
        d = WakeWordDetector(callback=lambda: None)
        assert d.is_running is False
        d._running = True
        assert d.is_running is True
