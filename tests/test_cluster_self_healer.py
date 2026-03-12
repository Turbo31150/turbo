"""Tests for src/cluster_self_healer.py -- ClusterSelfHealer, NodeConfig, RecoveryAttempt.

All external dependencies (subprocess, urllib, event_bus, load_balancer,
notification_hub) are mocked.  No network, no process spawning.
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cluster_self_healer import (
    ClusterSelfHealer,
    NODE_CONFIGS,
    NodeConfig,
    RecoveryAttempt,
    cluster_healer,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def healer() -> ClusterSelfHealer:
    """Fresh healer instance for each test."""
    return ClusterSelfHealer()


@pytest.fixture()
def m1_config() -> NodeConfig:
    return NODE_CONFIGS["M1"]


@pytest.fixture()
def ollama_config() -> NodeConfig:
    return NODE_CONFIGS["ollama"]


# ---------------------------------------------------------------------------
# 1. Import & data-structure sanity
# ---------------------------------------------------------------------------

class TestImportsAndDataclasses:
    """Verify module-level objects and dataclass behaviour."""

    def test_import_cluster_healer_singleton(self):
        assert cluster_healer is not None
        assert isinstance(cluster_healer, ClusterSelfHealer)

    def test_node_configs_contains_expected_keys(self):
        assert "M1" in NODE_CONFIGS
        assert "ollama" in NODE_CONFIGS
        assert "ollama_cloud" in NODE_CONFIGS
        assert "gemini" in NODE_CONFIGS

    def test_node_config_m1_uses_127(self):
        cfg = NODE_CONFIGS["M1"]
        assert "127.0.0.1" in cfg.url
        assert cfg.node_type == "lm_studio"

    def test_node_config_ollama_uses_127(self):
        cfg = NODE_CONFIGS["ollama"]
        assert "127.0.0.1" in cfg.url
        assert cfg.node_type == "ollama"

    def test_recovery_attempt_defaults(self):
        ra = RecoveryAttempt(node="M1", action="restart", success=True, duration_ms=123.4)
        assert ra.error == ""
        assert ra.ts > 0
        assert ra.node == "M1"

    def test_node_config_defaults(self):
        nc = NodeConfig(name="test", node_type="remote", url="http://127.0.0.1:9999")
        assert nc.restart_command is None
        assert nc.max_retries == 3
        assert nc.retry_delay_s == 30.0


# ---------------------------------------------------------------------------
# 2. status()
# ---------------------------------------------------------------------------

class TestStatus:

    def test_status_keys(self, healer: ClusterSelfHealer):
        s = healer.status()
        assert "active_recoveries" in s
        assert "stats" in s
        assert "recent_history" in s
        assert "known_nodes" in s

    def test_status_recent_history_limits_to_10(self, healer: ClusterSelfHealer):
        for i in range(25):
            healer.recovery_history.append(
                RecoveryAttempt(node="X", action=f"a{i}", success=True, duration_ms=1.0)
            )
        s = healer.status()
        assert len(s["recent_history"]) == 10

    def test_status_known_nodes_matches_configs(self, healer: ClusterSelfHealer):
        s = healer.status()
        assert set(s["known_nodes"]) == set(NODE_CONFIGS.keys())


# ---------------------------------------------------------------------------
# 3. handle_node_failure -- unknown node
# ---------------------------------------------------------------------------

class TestHandleUnknownNode:

    @pytest.mark.asyncio
    async def test_unknown_node_reroutes(self, healer: ClusterSelfHealer):
        with patch.object(healer, "_reroute_traffic", new_callable=AsyncMock) as mock_rr:
            result = await healer.handle_node_failure("NONEXISTENT")
            mock_rr.assert_awaited_once_with("NONEXISTENT")
            assert "rerouted (unknown node)" in result["actions"]
            assert result["recovered"] is False


# ---------------------------------------------------------------------------
# 4. handle_node_failure -- duplicate guard
# ---------------------------------------------------------------------------

class TestDuplicateRecovery:

    @pytest.mark.asyncio
    async def test_already_recovering_returns_early(self, healer: ClusterSelfHealer):
        healer._active_recoveries.add("M1")
        result = await healer.handle_node_failure("M1")
        assert result["status"] == "already_recovering"
        assert result["node"] == "M1"


# ---------------------------------------------------------------------------
# 5. handle_node_failure -- remote node path
# ---------------------------------------------------------------------------

class TestRemoteNodeFailure:

    @pytest.mark.asyncio
    async def test_remote_node_reroutes_and_emits(self, healer: ClusterSelfHealer):
        with (
            patch.object(healer, "_reroute_traffic", new_callable=AsyncMock) as mock_rr,
            patch.object(healer, "_emit", new_callable=AsyncMock) as mock_emit,
        ):
            result = await healer.handle_node_failure("gemini")
            mock_rr.assert_awaited_once_with("gemini")
            # Should emit remote_node_down event
            mock_emit.assert_any_await(
                "cluster.remote_node_down",
                {"node": "gemini", "url": NODE_CONFIGS["gemini"].url},
            )
            assert "remote_node_will_auto_recover" in result["actions"]
            assert "traffic_rerouted" in result["actions"]
            assert result["recovered"] is False


# ---------------------------------------------------------------------------
# 6. handle_node_failure -- successful restart on first attempt
# ---------------------------------------------------------------------------

class TestSuccessfulRestart:

    @pytest.mark.asyncio
    async def test_m1_recovers_first_attempt(self, healer: ClusterSelfHealer):
        with (
            patch.object(healer, "_reroute_traffic", new_callable=AsyncMock),
            patch.object(healer, "_restore_traffic", new_callable=AsyncMock) as mock_restore,
            patch.object(healer, "_restart_node", new_callable=AsyncMock, return_value=True),
            patch.object(healer, "_verify_node", new_callable=AsyncMock, return_value=True),
            patch.object(healer, "_emit", new_callable=AsyncMock) as mock_emit,
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await healer.handle_node_failure("M1")

            assert result["recovered"] is True
            assert "restarted (attempt 1)" in result["actions"]
            assert "traffic_restored" in result["actions"]
            mock_restore.assert_awaited_once_with("M1")
            mock_emit.assert_any_await(
                "cluster.node_recovered", {"node": "M1", "attempts": 1}
            )
            assert healer.stats["successful"] == 1
            assert healer.stats["nodes_restarted"] == 1


# ---------------------------------------------------------------------------
# 7. handle_node_failure -- recovery fails all attempts then escalates
# ---------------------------------------------------------------------------

class TestEscalation:

    @pytest.mark.asyncio
    async def test_all_retries_fail_then_escalate(self, healer: ClusterSelfHealer):
        with (
            patch.object(healer, "_reroute_traffic", new_callable=AsyncMock),
            patch.object(healer, "_restart_node", new_callable=AsyncMock, return_value=False),
            patch.object(healer, "_escalate", new_callable=AsyncMock) as mock_esc,
            patch.object(healer, "_emit", new_callable=AsyncMock),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await healer.handle_node_failure("M1")

            assert result["recovered"] is False
            assert "escalated" in result["actions"]
            mock_esc.assert_awaited_once()
            assert healer.stats["failed"] == 1

    @pytest.mark.asyncio
    async def test_restart_ok_but_verify_fails_retries(self, healer: ClusterSelfHealer):
        """restart_node returns True but verify_node returns False -> retries then escalates."""
        with (
            patch.object(healer, "_reroute_traffic", new_callable=AsyncMock),
            patch.object(healer, "_restart_node", new_callable=AsyncMock, return_value=True),
            patch.object(healer, "_verify_node", new_callable=AsyncMock, return_value=False),
            patch.object(healer, "_escalate", new_callable=AsyncMock) as mock_esc,
            patch.object(healer, "_emit", new_callable=AsyncMock),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await healer.handle_node_failure("M1")

            assert result["recovered"] is False
            assert "escalated" in result["actions"]
            mock_esc.assert_awaited_once()
            # Should have recorded max_retries attempts
            restart_actions = [r for r in healer.recovery_history if r.node == "M1"]
            assert len(restart_actions) == NODE_CONFIGS["M1"].max_retries


# ---------------------------------------------------------------------------
# 8. _restart_node -- LM Studio path
# ---------------------------------------------------------------------------

class TestRestartNode:

    @pytest.mark.asyncio
    async def test_restart_lm_studio_success(self, healer: ClusterSelfHealer, m1_config: NodeConfig):
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
            with patch("asyncio.wait_for", return_value=(b"", b"")):
                result = await healer._restart_node(m1_config)

        assert result is True

    @pytest.mark.asyncio
    async def test_restart_lm_studio_failure(self, healer: ClusterSelfHealer, m1_config: NodeConfig):
        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(b"", b"error"))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with patch("asyncio.wait_for", return_value=(b"", b"error")):
                result = await healer._restart_node(m1_config)

        # returncode != 0 -> False
        assert result is False

    @pytest.mark.asyncio
    async def test_restart_ollama_always_true(self, healer: ClusterSelfHealer, ollama_config: NodeConfig):
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with patch("asyncio.wait_for", return_value=(b"", b"")):
                result = await healer._restart_node(ollama_config)

        # ollama path always returns True
        assert result is True

    @pytest.mark.asyncio
    async def test_restart_no_command_returns_false(self, healer: ClusterSelfHealer):
        cfg = NodeConfig(name="none", node_type="lm_studio", url="http://127.0.0.1:9999")
        assert cfg.restart_command is None
        result = await healer._restart_node(cfg)
        assert result is False

    @pytest.mark.asyncio
    async def test_restart_exception_returns_false(self, healer: ClusterSelfHealer, m1_config: NodeConfig):
        with patch("asyncio.create_subprocess_exec", side_effect=OSError("exec fail")):
            result = await healer._restart_node(m1_config)
        assert result is False


# ---------------------------------------------------------------------------
# 9. _verify_node
# ---------------------------------------------------------------------------

class TestVerifyNode:

    @pytest.mark.asyncio
    async def test_verify_lm_studio_200(self, healer: ClusterSelfHealer, m1_config: NodeConfig):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = await healer._verify_node(m1_config)
        assert result is True

    @pytest.mark.asyncio
    async def test_verify_ollama_200(self, healer: ClusterSelfHealer, ollama_config: NodeConfig):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = await healer._verify_node(ollama_config)
        assert result is True

    @pytest.mark.asyncio
    async def test_verify_network_error_returns_false(self, healer: ClusterSelfHealer, m1_config: NodeConfig):
        with patch("urllib.request.urlopen", side_effect=ConnectionError("refused")):
            result = await healer._verify_node(m1_config)
        assert result is False


# ---------------------------------------------------------------------------
# 10. _reroute_traffic / _restore_traffic
# ---------------------------------------------------------------------------

class TestTrafficManagement:

    @pytest.mark.asyncio
    async def test_reroute_adds_to_excluded(self, healer: ClusterSelfHealer):
        mock_lb = MagicMock()
        mock_lb._excluded = set()
        with patch.dict("sys.modules", {"src.load_balancer": MagicMock(load_balancer=mock_lb)}):
            await healer._reroute_traffic("M1")
        assert "M1" in mock_lb._excluded

    @pytest.mark.asyncio
    async def test_restore_removes_from_excluded(self, healer: ClusterSelfHealer):
        mock_lb = MagicMock()
        mock_lb._excluded = {"M1"}
        with patch.dict("sys.modules", {"src.load_balancer": MagicMock(load_balancer=mock_lb)}):
            await healer._restore_traffic("M1")
        assert "M1" not in mock_lb._excluded

    @pytest.mark.asyncio
    async def test_reroute_handles_import_error(self, healer: ClusterSelfHealer):
        """If load_balancer import fails, should not raise."""
        with patch.dict("sys.modules", {"src.load_balancer": None}):
            # Should not raise
            await healer._reroute_traffic("M1")

    @pytest.mark.asyncio
    async def test_restore_handles_import_error(self, healer: ClusterSelfHealer):
        with patch.dict("sys.modules", {"src.load_balancer": None}):
            await healer._restore_traffic("M1")


# ---------------------------------------------------------------------------
# 11. _escalate
# ---------------------------------------------------------------------------

class TestEscalate:

    @pytest.mark.asyncio
    async def test_escalate_dispatches_notification(self, healer: ClusterSelfHealer):
        mock_hub = MagicMock()
        mock_hub.dispatch = MagicMock()
        with (
            patch.dict("sys.modules", {"src.notification_hub": MagicMock(notification_hub=mock_hub)}),
            patch.object(healer, "_emit", new_callable=AsyncMock) as mock_emit,
        ):
            await healer._escalate("M1", "all retries exhausted")
            mock_hub.dispatch.assert_called_once()
            call_kwargs = mock_hub.dispatch.call_args
            assert "M1" in str(call_kwargs)
            mock_emit.assert_awaited_once_with(
                "cluster.escalation",
                {"node": "M1", "reason": "all retries exhausted"},
            )

    @pytest.mark.asyncio
    async def test_escalate_handles_import_error(self, healer: ClusterSelfHealer):
        """If notification_hub import fails, should still emit event and not raise."""
        with (
            patch.dict("sys.modules", {"src.notification_hub": None}),
            patch.object(healer, "_emit", new_callable=AsyncMock) as mock_emit,
        ):
            await healer._escalate("M1", "reason")
            mock_emit.assert_awaited_once()


# ---------------------------------------------------------------------------
# 12. _emit
# ---------------------------------------------------------------------------

class TestEmit:

    @pytest.mark.asyncio
    async def test_emit_calls_event_bus(self, healer: ClusterSelfHealer):
        mock_bus = AsyncMock()
        mock_bus.emit = AsyncMock()
        with patch.dict("sys.modules", {"src.event_bus": MagicMock(event_bus=mock_bus)}):
            await healer._emit("test.event", {"key": "val"})
            mock_bus.emit.assert_awaited_once()
            call_args = mock_bus.emit.call_args[0]
            assert call_args[0] == "test.event"
            assert "ts" in call_args[1]  # ts injected

    @pytest.mark.asyncio
    async def test_emit_swallows_errors(self, healer: ClusterSelfHealer):
        with patch.dict("sys.modules", {"src.event_bus": None}):
            # Must not raise
            await healer._emit("test.event", {})


# ---------------------------------------------------------------------------
# 13. History trimming
# ---------------------------------------------------------------------------

class TestHistoryTrimming:

    @pytest.mark.asyncio
    async def test_history_trimmed_after_max(self, healer: ClusterSelfHealer):
        healer._max_history = 5
        for i in range(10):
            healer.recovery_history.append(
                RecoveryAttempt(node="X", action=f"a{i}", success=True, duration_ms=1.0)
            )

        with (
            patch.object(healer, "_reroute_traffic", new_callable=AsyncMock),
            patch.object(healer, "_emit", new_callable=AsyncMock),
        ):
            await healer.handle_node_failure("gemini")

        assert len(healer.recovery_history) <= healer._max_history


# ---------------------------------------------------------------------------
# 14. Stats tracking
# ---------------------------------------------------------------------------

class TestStatsTracking:

    def test_initial_stats_zeroed(self, healer: ClusterSelfHealer):
        assert healer.stats["total_recoveries"] == 0
        assert healer.stats["successful"] == 0
        assert healer.stats["failed"] == 0
        assert healer.stats["nodes_restarted"] == 0
        assert healer.stats["traffic_rerouted"] == 0

    @pytest.mark.asyncio
    async def test_traffic_rerouted_incremented(self, healer: ClusterSelfHealer):
        with (
            patch.object(healer, "_reroute_traffic", new_callable=AsyncMock),
            patch.object(healer, "_emit", new_callable=AsyncMock),
        ):
            await healer.handle_node_failure("gemini")
        assert healer.stats["traffic_rerouted"] == 1
        assert healer.stats["total_recoveries"] == 1


# ---------------------------------------------------------------------------
# 15. Concurrent recovery guard (integration-like)
# ---------------------------------------------------------------------------

class TestConcurrencyGuard:

    @pytest.mark.asyncio
    async def test_concurrent_calls_second_is_blocked(self, healer: ClusterSelfHealer):
        """If two recoveries for the same node fire, the second returns immediately."""
        gate = asyncio.Event()

        original_reroute = healer._reroute_traffic

        async def slow_reroute(node: str) -> None:
            await gate.wait()

        with (
            patch.object(healer, "_reroute_traffic", side_effect=slow_reroute),
            patch.object(healer, "_emit", new_callable=AsyncMock),
        ):
            task1 = asyncio.create_task(healer.handle_node_failure("gemini"))
            await asyncio.sleep(0.01)  # let task1 start

            result2 = await healer.handle_node_failure("gemini")
            assert result2["status"] == "already_recovering"

            gate.set()
            result1 = await task1
            assert "traffic_rerouted" in result1["actions"]


# ---------------------------------------------------------------------------
# 16. active_recoveries cleaned up on exception
# ---------------------------------------------------------------------------

class TestCleanup:

    @pytest.mark.asyncio
    async def test_active_recovery_cleared_on_exception(self, healer: ClusterSelfHealer):
        with patch.object(
            healer, "_reroute_traffic", new_callable=AsyncMock, side_effect=RuntimeError("boom")
        ):
            result = await healer.handle_node_failure("gemini")
            assert "boom" in result.get("error", "")
        # Must have been cleaned up in finally
        assert "gemini" not in healer._active_recoveries


# ---------------------------------------------------------------------------
# 17. Ollama node recovery second attempt succeeds
# ---------------------------------------------------------------------------

class TestOllamaRecoverySecondAttempt:

    @pytest.mark.asyncio
    async def test_ollama_recovers_second_attempt(self, healer: ClusterSelfHealer):
        restart_call_count = 0

        async def restart_side_effect(config):
            nonlocal restart_call_count
            restart_call_count += 1
            return restart_call_count >= 2  # fail first, succeed second

        verify_call_count = 0

        async def verify_side_effect(config):
            nonlocal verify_call_count
            verify_call_count += 1
            return verify_call_count >= 1  # pass every time verify is called

        with (
            patch.object(healer, "_reroute_traffic", new_callable=AsyncMock),
            patch.object(healer, "_restore_traffic", new_callable=AsyncMock),
            patch.object(healer, "_restart_node", side_effect=restart_side_effect),
            patch.object(healer, "_verify_node", side_effect=verify_side_effect),
            patch.object(healer, "_emit", new_callable=AsyncMock),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await healer.handle_node_failure("ollama")

            assert result["recovered"] is True
            assert "restarted (attempt 2)" in result["actions"]
            assert healer.stats["successful"] == 1


# ---------------------------------------------------------------------------
# 18. handle_node_failure returns duration_ms
# ---------------------------------------------------------------------------

class TestDuration:

    @pytest.mark.asyncio
    async def test_result_contains_duration_ms(self, healer: ClusterSelfHealer):
        with (
            patch.object(healer, "_reroute_traffic", new_callable=AsyncMock),
            patch.object(healer, "_emit", new_callable=AsyncMock),
        ):
            result = await healer.handle_node_failure("gemini")
        assert "duration_ms" in result
        assert isinstance(result["duration_ms"], float)
        assert result["duration_ms"] >= 0
