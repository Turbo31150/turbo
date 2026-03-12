"""Tests for src/startup_wiring.py — Bootstrap and shutdown orchestration.

Covers: is_bootstrapped, _safe_step, bootstrap_jarvis (idempotent),
shutdown_jarvis.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import src.startup_wiring as sw


# ===========================================================================
# is_bootstrapped
# ===========================================================================

class TestIsBootstrapped:
    def setup_method(self):
        sw._BOOTSTRAP_DONE = False

    def test_initially_false(self):
        assert sw.is_bootstrapped() is False

    def test_after_set_true(self):
        sw._BOOTSTRAP_DONE = True
        assert sw.is_bootstrapped() is True


# ===========================================================================
# _safe_step
# ===========================================================================

class TestSafeStep:
    @pytest.mark.asyncio
    async def test_success(self):
        results = {"errors": []}
        async def good_step():
            return {"ok": True}
        result = await sw._safe_step("Good", 1, 5, results, good_step)
        assert result == {"ok": True}
        assert len(results["errors"]) == 0

    @pytest.mark.asyncio
    async def test_failure(self):
        results = {"errors": []}
        async def bad_step():
            raise RuntimeError("boom")
        result = await sw._safe_step("Bad", 2, 5, results, bad_step)
        assert "error" in result
        assert "boom" in result["error"]
        assert len(results["errors"]) == 1
        assert "Bad" in results["errors"][0]

    @pytest.mark.asyncio
    async def test_multiple_failures(self):
        results = {"errors": []}
        async def fail():
            raise ValueError("fail")
        await sw._safe_step("S1", 1, 3, results, fail)
        await sw._safe_step("S2", 2, 3, results, fail)
        assert len(results["errors"]) == 2


# ===========================================================================
# bootstrap_jarvis — idempotent
# ===========================================================================

class TestBootstrapIdempotent:
    def setup_method(self):
        sw._BOOTSTRAP_DONE = False

    @pytest.mark.asyncio
    async def test_already_bootstrapped(self):
        sw._BOOTSTRAP_DONE = True
        result = await sw.bootstrap_jarvis()
        assert result["status"] == "already_bootstrapped"

    @pytest.mark.asyncio
    async def test_timeout(self):
        sw._BOOTSTRAP_DONE = False
        with patch("src.startup_wiring._bootstrap_internal", new_callable=AsyncMock,
                    side_effect=asyncio.TimeoutError()):
            with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
                result = await sw.bootstrap_jarvis(timeout_s=0.01)
        assert result["success"] is False
        assert "timeout" in result["error"].lower()


# ===========================================================================
# shutdown_jarvis
# ===========================================================================

class TestShutdownJarvis:
    def setup_method(self):
        sw._BOOTSTRAP_DONE = True

    @pytest.mark.asyncio
    async def test_shutdown_resets_flag(self):
        mock_sched = MagicMock()
        mock_sched.stop = AsyncMock()
        mock_sentinel = MagicMock()
        mock_guardian = MagicMock()
        mock_loop = MagicMock()
        mock_bus = MagicMock()
        mock_bus.emit = AsyncMock()

        with patch.dict("sys.modules", {
            "src.task_scheduler": MagicMock(task_scheduler=mock_sched),
            "src.trading_sentinel": MagicMock(trading_sentinel=mock_sentinel),
            "src.gpu_guardian": MagicMock(gpu_guardian=mock_guardian),
            "src.autonomous_loop": MagicMock(autonomous_loop=mock_loop),
            "src.event_bus": MagicMock(event_bus=mock_bus),
        }):
            result = await sw.shutdown_jarvis()
        assert sw._BOOTSTRAP_DONE is False
        assert "duration_ms" in result

    @pytest.mark.asyncio
    async def test_shutdown_handles_errors(self):
        with patch.dict("sys.modules", {
            "src.task_scheduler": None,
            "src.trading_sentinel": None,
            "src.gpu_guardian": None,
            "src.autonomous_loop": None,
            "src.event_bus": None,
        }):
            result = await sw.shutdown_jarvis()
        assert sw._BOOTSTRAP_DONE is False
        assert "duration_ms" in result
