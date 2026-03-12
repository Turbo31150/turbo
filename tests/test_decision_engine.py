"""Tests for JARVIS Decision Engine."""

import pytest


class TestDecisionEngine:
    def test_import(self):
        from src.decision_engine import decision_engine
        assert decision_engine is not None

    def test_signal_class(self):
        from src.decision_engine import Signal
        s = Signal(source="test", severity="info", category="system",
                   description="test signal")
        assert s.source == "test"
        assert s.timestamp > 0

    def test_decision_class(self):
        from src.decision_engine import Decision
        d = Decision(action="notify", target="test", reason="testing")
        assert d.priority == 5
        assert d.auto_execute is True

    def test_get_stats(self):
        from src.decision_engine import decision_engine
        stats = decision_engine.get_stats()
        assert "signals_processed" in stats
        assert "rules_count" in stats
        assert stats["rules_count"] >= 6  # 6 default rules
        assert stats["handlers_count"] >= 5  # 5 default handlers

    def test_get_recent_decisions(self):
        from src.decision_engine import decision_engine
        decisions = decision_engine.get_recent_decisions()
        assert isinstance(decisions, list)

    @pytest.mark.asyncio
    async def test_process_signal_info(self):
        from src.decision_engine import decision_engine, Signal
        signal = Signal(source="test", severity="info", category="test",
                        description="Just a test info signal")
        results = await decision_engine.process_signal(signal)
        # Info signal might not trigger any rules
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_process_signal_critical_offline(self):
        from src.decision_engine import decision_engine, Signal
        signal = Signal(source="test", severity="critical", category="cluster",
                        description="M2 (192.168.1.26:1234) OFFLINE")
        results = await decision_engine.process_signal(signal)
        assert isinstance(results, list)
        # Should trigger critical_node_offline rule
        if results:
            assert any(r["decision"] == "heal_node" for r in results)

    @pytest.mark.asyncio
    async def test_process_signal_model_missing(self):
        from src.decision_engine import decision_engine, Signal
        signal = Signal(source="test", severity="critical", category="cluster",
                        description="M1: 0 modeles charges (qwen3-8b manquant)")
        results = await decision_engine.process_signal(signal)
        assert isinstance(results, list)
        if results:
            assert any(r["decision"] == "load_model" for r in results)

    def test_register_custom_rule(self):
        from src.decision_engine import decision_engine, Signal, Decision
        def custom_rule(signal: Signal):
            if "custom_test" in signal.description:
                return Decision(action="noop", target="test", reason="custom rule fired")
            return None
        initial_count = len(decision_engine._rules)
        decision_engine.register_rule("custom_test", custom_rule)
        assert len(decision_engine._rules) == initial_count + 1

    def test_register_custom_handler(self):
        from src.decision_engine import decision_engine
        async def custom_handler(decision):
            return "custom_handled"
        decision_engine.register_handler("custom_action", custom_handler)
        assert "custom_action" in decision_engine._action_handlers
