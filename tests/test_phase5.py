"""Phase 5 Tests — Auto-Optimizer, Event Bus, Metrics Aggregator, MCP Handlers."""

import asyncio
import json
import time
import pytest


# ═══════════════════════════════════════════════════════════════════════════
# AUTO-OPTIMIZER
# ═══════════════════════════════════════════════════════════════════════════

class TestAutoOptimizer:
    def test_singleton_exists(self):
        from src.auto_optimizer import auto_optimizer
        assert auto_optimizer is not None

    def test_optimize_returns_list(self):
        from src.auto_optimizer import AutoOptimizer
        opt = AutoOptimizer()
        result = opt.force_optimize()
        assert isinstance(result, list)

    def test_disabled_returns_empty(self):
        from src.auto_optimizer import AutoOptimizer
        opt = AutoOptimizer()
        opt.enable(False)
        assert opt.optimize() == []

    def test_history_empty_initially(self):
        from src.auto_optimizer import AutoOptimizer
        opt = AutoOptimizer()
        assert opt.get_history() == []

    def test_stats_structure(self):
        from src.auto_optimizer import AutoOptimizer
        opt = AutoOptimizer()
        stats = opt.get_stats()
        assert "enabled" in stats
        assert "total_adjustments" in stats
        assert "min_interval_s" in stats
        assert "by_module" in stats

    def test_cooldown_prevents_double_optimize(self):
        from src.auto_optimizer import AutoOptimizer
        opt = AutoOptimizer()
        opt._min_interval_s = 9999
        opt.optimize()  # runs, sets last_optimize
        opt._last_optimize = time.time()  # force timestamp
        result = opt.optimize()  # should be blocked by cooldown
        assert result == []

    def test_force_optimize_bypasses_cooldown(self):
        from src.auto_optimizer import AutoOptimizer
        opt = AutoOptimizer()
        opt._min_interval_s = 9999
        opt.optimize()
        result = opt.force_optimize()  # bypasses cooldown
        assert isinstance(result, list)

    def test_enable_toggle(self):
        from src.auto_optimizer import AutoOptimizer
        opt = AutoOptimizer()
        opt.enable(False)
        assert not opt._enabled
        opt.enable(True)
        assert opt._enabled


# ═══════════════════════════════════════════════════════════════════════════
# EVENT BUS
# ═══════════════════════════════════════════════════════════════════════════

class TestEventBus:
    def test_singleton_exists(self):
        from src.event_bus import event_bus
        assert event_bus is not None

    def test_subscribe_and_emit(self):
        from src.event_bus import EventBus
        bus = EventBus()
        received = []

        async def handler(data):
            received.append(data)

        bus.subscribe("test.event", handler)
        count = asyncio.run(bus.emit("test.event", {"key": "value"}))
        assert count == 1
        assert len(received) == 1
        assert received[0]["key"] == "value"

    def test_wildcard_pattern(self):
        from src.event_bus import EventBus
        bus = EventBus()
        received = []

        async def handler(data):
            received.append(data)

        bus.subscribe("cluster.*", handler)
        asyncio.run(bus.emit("cluster.node_offline", {"node": "M2"}))
        asyncio.run(bus.emit("cluster.node_online", {"node": "M1"}))
        asyncio.run(bus.emit("trading.signal", {}))  # should NOT match
        assert len(received) == 2

    def test_unsubscribe(self):
        from src.event_bus import EventBus
        bus = EventBus()
        received = []

        async def handler(data):
            received.append(data)

        unsub = bus.subscribe("test", handler)
        asyncio.run(bus.emit("test", {}))
        assert len(received) == 1
        unsub()
        asyncio.run(bus.emit("test", {}))
        assert len(received) == 1  # no new events after unsub

    def test_priority_order(self):
        from src.event_bus import EventBus
        bus = EventBus()
        order = []

        async def low(data):
            order.append("low")

        async def high(data):
            order.append("high")

        bus.subscribe("test", low, priority=0)
        bus.subscribe("test", high, priority=10)
        asyncio.run(bus.emit("test", {}))
        assert order == ["high", "low"]

    def test_no_match_returns_zero(self):
        from src.event_bus import EventBus
        bus = EventBus()
        count = asyncio.run(bus.emit("nonexistent", {}))
        assert count == 0

    def test_clear(self):
        from src.event_bus import EventBus
        bus = EventBus()

        async def noop(data):
            pass

        bus.subscribe("test", noop)
        assert bus.subscriber_count() == 1
        bus.clear()
        assert bus.subscriber_count() == 0

    def test_stats(self):
        from src.event_bus import EventBus
        bus = EventBus()

        async def noop(data):
            pass

        bus.subscribe("a", noop)
        asyncio.run(bus.emit("a", {}))
        asyncio.run(bus.emit("b", {}))
        stats = bus.get_stats()
        assert stats["total_subscriptions"] == 1
        assert stats["total_events_emitted"] == 2
        assert stats["event_counts"]["a"] == 1
        assert stats["event_counts"]["b"] == 1

    def test_get_events(self):
        from src.event_bus import EventBus
        bus = EventBus()
        asyncio.run(bus.emit("evt1", {}))
        asyncio.run(bus.emit("evt2", {"x": 1}))
        events = bus.get_events(limit=10)
        assert len(events) == 2
        assert events[0]["event"] == "evt1"
        assert events[1]["event"] == "evt2"

    def test_handler_error_does_not_crash(self):
        from src.event_bus import EventBus
        bus = EventBus()

        async def bad_handler(data):
            raise ValueError("boom")

        async def good_handler(data):
            data["ok"] = True

        bus.subscribe("test", bad_handler)
        bus.subscribe("test", good_handler)
        result = {}
        count = asyncio.run(bus.emit("test", result))
        assert count == 1  # only good_handler succeeded


# ═══════════════════════════════════════════════════════════════════════════
# METRICS AGGREGATOR
# ═══════════════════════════════════════════════════════════════════════════

class TestMetricsAggregator:
    def test_singleton_exists(self):
        from src.metrics_aggregator import metrics_aggregator
        assert metrics_aggregator is not None

    def test_snapshot_structure(self):
        from src.metrics_aggregator import MetricsAggregator
        ma = MetricsAggregator()
        snap = ma.snapshot()
        assert "ts" in snap
        assert "orchestrator" in snap
        assert "load_balancer" in snap
        assert "autonomous_loop" in snap
        assert "agent_memory" in snap
        assert "conversations" in snap
        assert "proactive" in snap
        assert "optimizer" in snap
        assert "event_bus" in snap

    def test_sample_respects_interval(self):
        from src.metrics_aggregator import MetricsAggregator
        ma = MetricsAggregator()
        s1 = ma.sample()
        assert s1 is not None  # first sample always works
        s2 = ma.sample()
        assert s2 is None  # too soon

    def test_history_empty_initially(self):
        from src.metrics_aggregator import MetricsAggregator
        ma = MetricsAggregator()
        assert ma.get_history() == []

    def test_history_after_sample(self):
        from src.metrics_aggregator import MetricsAggregator
        ma = MetricsAggregator()
        ma.sample()
        history = ma.get_history()
        assert len(history) == 1

    def test_get_latest(self):
        from src.metrics_aggregator import MetricsAggregator
        ma = MetricsAggregator()
        assert ma.get_latest() is None
        ma.sample()
        latest = ma.get_latest()
        assert latest is not None
        assert "ts" in latest

    def test_summary(self):
        from src.metrics_aggregator import MetricsAggregator
        ma = MetricsAggregator()
        summary = ma.get_summary()
        assert "sample_count" in summary
        assert "max_samples" in summary
        assert "sample_interval_s" in summary


# ═══════════════════════════════════════════════════════════════════════════
# MCP HANDLERS — Phase 5
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPHandlersPhase5:
    def test_optimizer_optimize(self):
        from src.mcp_server import handle_optimizer_optimize
        result = asyncio.run(handle_optimizer_optimize({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_optimizer_history(self):
        from src.mcp_server import handle_optimizer_history
        result = asyncio.run(handle_optimizer_history({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_optimizer_stats(self):
        from src.mcp_server import handle_optimizer_stats
        result = asyncio.run(handle_optimizer_stats({}))
        data = json.loads(result[0].text)
        assert "enabled" in data

    def test_eventbus_emit(self):
        from src.mcp_server import handle_eventbus_emit
        result = asyncio.run(handle_eventbus_emit({"event": "test.mcp", "data": "{}"}))
        assert "emitted" in result[0].text.lower()

    def test_eventbus_stats(self):
        from src.mcp_server import handle_eventbus_stats
        result = asyncio.run(handle_eventbus_stats({}))
        data = json.loads(result[0].text)
        assert "total_subscriptions" in data

    def test_metrics_snapshot(self):
        from src.mcp_server import handle_metrics_snapshot
        result = asyncio.run(handle_metrics_snapshot({}))
        data = json.loads(result[0].text)
        assert "ts" in data
        assert "orchestrator" in data

    def test_metrics_history(self):
        from src.mcp_server import handle_metrics_history
        result = asyncio.run(handle_metrics_history({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_metrics_summary(self):
        from src.mcp_server import handle_metrics_summary
        result = asyncio.run(handle_metrics_summary({}))
        data = json.loads(result[0].text)
        assert "sample_count" in data


# ═══════════════════════════════════════════════════════════════════════════
# TOOL COUNT PHASE 5
# ═══════════════════════════════════════════════════════════════════════════

class TestToolCountPhase5:
    def test_tool_count_at_least_126(self):
        """118 base + 3 optimizer + 2 eventbus + 3 metrics = 126."""
        from src.mcp_server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 126, f"Expected >= 126 tools, got {len(TOOL_DEFINITIONS)}"

    def test_no_duplicate_tool_names(self):
        from src.mcp_server import TOOL_DEFINITIONS
        names = [t[0] for t in TOOL_DEFINITIONS]
        dupes = [n for n in names if names.count(n) > 1]
        assert len(names) == len(set(names)), f"Duplicate tools: {set(dupes)}"
