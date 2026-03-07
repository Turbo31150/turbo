"""Tests for src/agent_collaboration.py — Inter-agent messaging and delegation.

Covers: AgentMessage, CollaborationResult (summary), AgentBus (ask, delegate,
chain, parallel_ask, debate, subscribe, _notify_subscribers, get_message_log,
get_stats), get_bus singleton.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

with patch("src.pattern_agents.PatternAgentRegistry"):
    from src.agent_collaboration import (
        AgentMessage, CollaborationResult, AgentBus, get_bus,
    )


# ===========================================================================
# AgentMessage
# ===========================================================================

class TestAgentMessage:
    def test_defaults(self):
        m = AgentMessage(msg_id="m1", from_agent="orch", to_agent="code",
                         content="Write code")
        assert m.msg_type == "request"
        assert m.context == {}
        assert m.timestamp > 0
        assert m.response is None
        assert m.latency_ms == 0
        assert m.ok is False


# ===========================================================================
# CollaborationResult
# ===========================================================================

class TestCollaborationResult:
    def test_summary(self):
        r = CollaborationResult(
            chain=["code", "security"],
            messages=[],
            final_content="done",
            total_latency_ms=1500,
            ok=True,
            steps_ok=2,
            steps_total=2,
        )
        s = r.summary
        assert "code -> security" in s
        assert "2/2" in s
        assert "1500ms" in s

    def test_partial_success(self):
        r = CollaborationResult(
            chain=["a", "b", "c"],
            messages=[],
            final_content="partial",
            total_latency_ms=3000,
            ok=True,
            steps_ok=2,
            steps_total=3,
        )
        assert "2/3" in r.summary


# ===========================================================================
# AgentBus — ask
# ===========================================================================

class TestAsk:
    @pytest.mark.asyncio
    async def test_basic_ask(self):
        with patch("src.agent_collaboration.PatternAgentRegistry") as MockReg:
            bus = AgentBus()
        mock_result = MagicMock()
        mock_result.content = "def hello(): pass"
        mock_result.latency_ms = 500
        mock_result.ok = True
        bus.registry.dispatch = AsyncMock(return_value=mock_result)

        msg = await bus.ask("code", "Write a function")
        assert msg.ok is True
        assert msg.response == "def hello(): pass"
        assert msg.to_agent == "code"
        assert msg.latency_ms == 500

    @pytest.mark.asyncio
    async def test_ask_with_context(self):
        with patch("src.agent_collaboration.PatternAgentRegistry"):
            bus = AgentBus()
        mock_result = MagicMock()
        mock_result.content = "ok"
        mock_result.latency_ms = 100
        mock_result.ok = True
        bus.registry.dispatch = AsyncMock(return_value=mock_result)

        msg = await bus.ask("code", "Write parser", context={"lang": "python"})
        # Context should have been enriched into the prompt
        call_args = bus.registry.dispatch.call_args
        assert "python" in call_args[0][1]  # enriched prompt

    @pytest.mark.asyncio
    async def test_ask_logs_message(self):
        with patch("src.agent_collaboration.PatternAgentRegistry"):
            bus = AgentBus()
        mock_result = MagicMock()
        mock_result.content = "result"
        mock_result.latency_ms = 200
        mock_result.ok = True
        bus.registry.dispatch = AsyncMock(return_value=mock_result)

        await bus.ask("code", "test")
        assert len(bus._message_log) == 1


# ===========================================================================
# AgentBus — delegate
# ===========================================================================

class TestDelegate:
    @pytest.mark.asyncio
    async def test_delegate(self):
        with patch("src.agent_collaboration.PatternAgentRegistry"):
            bus = AgentBus()
        mock_result = MagicMock()
        mock_result.content = "done"
        mock_result.latency_ms = 300
        mock_result.ok = True
        bus.registry.dispatch = AsyncMock(return_value=mock_result)

        msg = await bus.delegate("code", "security", "Check for XSS")
        assert msg.msg_type == "delegate"
        assert msg.from_agent == "code"


# ===========================================================================
# AgentBus — chain
# ===========================================================================

class TestChain:
    @pytest.mark.asyncio
    async def test_successful_chain(self):
        with patch("src.agent_collaboration.PatternAgentRegistry"):
            bus = AgentBus()
        mock_result = MagicMock()
        mock_result.content = "step output"
        mock_result.latency_ms = 100
        mock_result.ok = True
        bus.registry.dispatch = AsyncMock(return_value=mock_result)

        result = await bus.chain(["code", "security"], "Build API")
        assert result.ok is True
        assert result.steps_ok == 2
        assert result.steps_total == 2
        assert result.final_content == "step output"

    @pytest.mark.asyncio
    async def test_chain_with_failure(self):
        with patch("src.agent_collaboration.PatternAgentRegistry"):
            bus = AgentBus()

        call_count = [0]
        async def mock_dispatch(pattern, prompt):
            call_count[0] += 1
            r = MagicMock()
            r.latency_ms = 100
            if call_count[0] == 2:
                r.content = ""
                r.ok = False
            else:
                r.content = "output"
                r.ok = True
            return r

        bus.registry.dispatch = mock_dispatch
        result = await bus.chain(["code", "security", "analysis"], "task")
        assert result.steps_ok == 2  # 1st and 3rd succeed
        assert result.steps_total == 3
        assert result.ok is True

    @pytest.mark.asyncio
    async def test_chain_all_fail(self):
        with patch("src.agent_collaboration.PatternAgentRegistry"):
            bus = AgentBus()
        mock_result = MagicMock()
        mock_result.content = ""
        mock_result.latency_ms = 50
        mock_result.ok = False
        bus.registry.dispatch = AsyncMock(return_value=mock_result)

        result = await bus.chain(["code", "security"], "task")
        assert result.ok is False
        assert "failed" in result.final_content


# ===========================================================================
# AgentBus — parallel_ask
# ===========================================================================

class TestParallelAsk:
    @pytest.mark.asyncio
    async def test_parallel(self):
        with patch("src.agent_collaboration.PatternAgentRegistry"):
            bus = AgentBus()
        mock_result = MagicMock()
        mock_result.content = "ok"
        mock_result.latency_ms = 100
        mock_result.ok = True
        bus.registry.dispatch = AsyncMock(return_value=mock_result)

        results = await bus.parallel_ask(["code", "math", "analysis"], "test")
        assert len(results) == 3
        assert all(r.ok for r in results)


# ===========================================================================
# AgentBus — debate
# ===========================================================================

class TestDebate:
    @pytest.mark.asyncio
    async def test_debate(self):
        with patch("src.agent_collaboration.PatternAgentRegistry"):
            bus = AgentBus()
        mock_result = MagicMock()
        mock_result.content = "my opinion"
        mock_result.latency_ms = 200
        mock_result.ok = True
        bus.registry.dispatch = AsyncMock(return_value=mock_result)

        result = await bus.debate(["code", "security"], "Best practice?", rounds=2)
        assert result.ok is True
        assert result.steps_total == 4  # 2 agents × 2 rounds
        assert result.steps_ok == 4


# ===========================================================================
# AgentBus — subscribe
# ===========================================================================

class TestSubscribe:
    @pytest.mark.asyncio
    async def test_subscriber_notified(self):
        with patch("src.agent_collaboration.PatternAgentRegistry"):
            bus = AgentBus()
        mock_result = MagicMock()
        mock_result.content = "ok"
        mock_result.latency_ms = 50
        mock_result.ok = True
        bus.registry.dispatch = AsyncMock(return_value=mock_result)

        notifications = []
        bus.subscribe("code", lambda msg: notifications.append(msg))
        await bus.ask("code", "test")
        assert len(notifications) == 1

    @pytest.mark.asyncio
    async def test_subscriber_error_graceful(self):
        with patch("src.agent_collaboration.PatternAgentRegistry"):
            bus = AgentBus()
        mock_result = MagicMock()
        mock_result.content = "ok"
        mock_result.latency_ms = 50
        mock_result.ok = True
        bus.registry.dispatch = AsyncMock(return_value=mock_result)

        bus.subscribe("code", lambda msg: (_ for _ in ()).throw(ValueError("boom")))
        await bus.ask("code", "test")  # should not raise


# ===========================================================================
# AgentBus — get_message_log / get_stats
# ===========================================================================

class TestLogAndStats:
    @pytest.mark.asyncio
    async def test_message_log(self):
        with patch("src.agent_collaboration.PatternAgentRegistry"):
            bus = AgentBus()
        mock_result = MagicMock()
        mock_result.content = "result"
        mock_result.latency_ms = 100
        mock_result.ok = True
        bus.registry.dispatch = AsyncMock(return_value=mock_result)

        await bus.ask("code", "test1")
        await bus.ask("math", "test2")
        log = bus.get_message_log()
        assert len(log) == 2
        assert log[0]["to"] == "code"
        assert log[1]["to"] == "math"

    def test_stats_empty(self):
        with patch("src.agent_collaboration.PatternAgentRegistry"):
            bus = AgentBus()
        stats = bus.get_stats()
        assert stats["total_messages"] == 0
        assert stats["success_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_stats_with_data(self):
        with patch("src.agent_collaboration.PatternAgentRegistry"):
            bus = AgentBus()
        mock_result = MagicMock()
        mock_result.content = "ok"
        mock_result.latency_ms = 200
        mock_result.ok = True
        bus.registry.dispatch = AsyncMock(return_value=mock_result)

        await bus.ask("code", "t1")
        await bus.ask("code", "t2")
        stats = bus.get_stats()
        assert stats["total_messages"] == 2
        assert stats["success_rate"] == 1.0
        assert stats["avg_latency_ms"] == 200


# ===========================================================================
# get_bus singleton
# ===========================================================================

class TestGetBus:
    def test_returns_instance(self):
        with patch("src.agent_collaboration.PatternAgentRegistry"):
            import src.agent_collaboration as mod
            mod._bus = None
            bus = get_bus()
            assert isinstance(bus, AgentBus)

    def test_same_instance(self):
        with patch("src.agent_collaboration.PatternAgentRegistry"):
            import src.agent_collaboration as mod
            mod._bus = None
            b1 = get_bus()
            b2 = get_bus()
            assert b1 is b2
