"""Integration tests for MCP Server Phase 3/4 tool handlers.

Tests the actual handler functions (not the MCP transport layer).
Each handler returns list[TextContent] — we verify structure and JSON validity.
"""

import asyncio
import json
import pytest

# ═══════════════════════════════════════════════════════════════════════════
# OBSERVABILITY TOOLS
# ═══════════════════════════════════════════════════════════════════════════


class TestObservabilityTools:
    def _run(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_observability_report(self):
        from src.mcp_server import handle_observability_report
        result = self._run(handle_observability_report({}))
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert isinstance(data, dict)

    def test_observability_heatmap(self):
        from src.mcp_server import handle_observability_heatmap
        result = self._run(handle_observability_heatmap({}))
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert isinstance(data, (dict, list))

    def test_observability_alerts(self):
        from src.mcp_server import handle_observability_alerts
        result = self._run(handle_observability_alerts({}))
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert isinstance(data, (dict, list))


# ═══════════════════════════════════════════════════════════════════════════
# DRIFT TOOLS
# ═══════════════════════════════════════════════════════════════════════════


class TestDriftTools:
    def _run(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_drift_check(self):
        from src.mcp_server import handle_drift_check
        result = self._run(handle_drift_check({}))
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert isinstance(data, dict)

    def test_drift_model_health_all(self):
        from src.mcp_server import handle_drift_model_health
        result = self._run(handle_drift_model_health({}))
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert isinstance(data, dict)

    def test_drift_model_health_specific(self):
        from src.mcp_server import handle_drift_model_health
        result = self._run(handle_drift_model_health({"model": "M1"}))
        assert len(result) == 1

    def test_drift_reroute(self):
        from src.mcp_server import handle_drift_reroute
        result = self._run(handle_drift_reroute({
            "task_type": "code",
            "candidates": "M1,M2,OL1",
        }))
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert "reordered" in data or "degraded" in data or isinstance(data, dict)


# ═══════════════════════════════════════════════════════════════════════════
# AUTO-TUNE TOOLS
# ═══════════════════════════════════════════════════════════════════════════


class TestAutoTuneTools:
    def _run(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_auto_tune_status(self):
        from src.mcp_server import handle_auto_tune_status
        result = self._run(handle_auto_tune_status({}))
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert isinstance(data, dict)

    def test_auto_tune_sample(self):
        from src.mcp_server import handle_auto_tune_sample
        result = self._run(handle_auto_tune_sample({}))
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert isinstance(data, dict)

    def test_auto_tune_cooldown(self):
        from src.mcp_server import handle_auto_tune_cooldown
        result = self._run(handle_auto_tune_cooldown({
            "node": "M1",
            "seconds": 5,
        }))
        assert len(result) == 1


# ═══════════════════════════════════════════════════════════════════════════
# INTENT CLASSIFICATION TOOL
# ═══════════════════════════════════════════════════════════════════════════


class TestIntentTools:
    def _run(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_intent_classify(self):
        from src.mcp_server import handle_intent_classify
        result = self._run(handle_intent_classify({"text": "ouvre chrome"}))
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert isinstance(data, (dict, list))

    def test_intent_classify_empty(self):
        from src.mcp_server import handle_intent_classify
        result = self._run(handle_intent_classify({"text": ""}))
        assert len(result) == 1


# ═══════════════════════════════════════════════════════════════════════════
# TRADING STRATEGY TOOLS
# ═══════════════════════════════════════════════════════════════════════════


class TestTradingStrategyTools:
    def _run(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_strategy_rankings(self):
        try:
            from src.mcp_server import handle_trading_strategy_rankings
        except ImportError:
            pytest.skip("handle_trading_strategy_rankings not found")
        result = self._run(handle_trading_strategy_rankings({}))
        assert len(result) == 1


# ═══════════════════════════════════════════════════════════════════════════
# ORCHESTRATOR V2 INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════


class TestOrchestratorV2Integration:
    """Test that orchestrator_v2 integrates correctly with other modules."""

    def test_record_call_updates_all_subsystems(self):
        from src.orchestrator_v2 import OrchestratorV2
        ov2 = OrchestratorV2()
        # This should not raise even if subsystems have no data
        ov2.record_call("M1", latency_ms=50, success=True, tokens=100, quality=0.95)
        ov2.record_call("M2", latency_ms=200, success=False, tokens=10, quality=0.3)

        # Verify node stats recorded
        stats = ov2.get_node_stats()
        assert stats["M1"]["success_rate"] == 1.0
        assert stats["M2"]["success_rate"] == 0.0

    def test_full_dashboard_structure(self):
        from src.orchestrator_v2 import OrchestratorV2
        ov2 = OrchestratorV2()
        dash = ov2.get_dashboard()

        # All required keys present
        assert "observability" in dash
        assert "drift" in dash
        assert "auto_tune" in dash
        assert "health_score" in dash
        assert "node_stats" in dash
        assert "budget" in dash

        # Health score is valid
        assert 0 <= dash["health_score"] <= 100

        # Budget has required fields
        budget = dash["budget"]
        assert "total_tokens" in budget
        assert "total_calls" in budget
        assert "session_duration_s" in budget

    def test_routing_matrix_all_types(self):
        from src.orchestrator_v2 import ROUTING_MATRIX, OrchestratorV2
        ov2 = OrchestratorV2()

        for task_type, entries in ROUTING_MATRIX.items():
            # Each entry is (node, weight)
            assert len(entries) > 0, f"Empty routing for {task_type}"
            for node, weight in entries:
                assert isinstance(node, str)
                assert isinstance(weight, (int, float))
                assert weight > 0

            # get_best_node should work for each type
            candidates = [n for n, _ in entries]
            best = ov2.get_best_node(candidates, task_type)
            assert best in candidates

    def test_fallback_chain_respects_exclude(self):
        from src.orchestrator_v2 import OrchestratorV2
        ov2 = OrchestratorV2()
        chain = ov2.fallback_chain("code", exclude={"M1", "M2"})
        assert "M1" not in chain
        assert "M2" not in chain

    def test_weighted_score_differentiates_nodes(self):
        from src.orchestrator_v2 import OrchestratorV2
        ov2 = OrchestratorV2()
        # Record very different performance
        for _ in range(10):
            ov2.record_call("good_node", latency_ms=20, success=True, quality=1.0)
            ov2.record_call("bad_node", latency_ms=900, success=False, quality=0.1)

        good = ov2.weighted_score("good_node", "simple")
        bad = ov2.weighted_score("bad_node", "simple")
        assert good > bad, f"good={good} should be > bad={bad}"
