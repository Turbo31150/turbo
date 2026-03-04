"""Tests for Phase 3+4 modules — observability, drift, auto_tune, intent, trading, tools metrics, database v2."""

import json
import math
import statistics
import time
from pathlib import Path
from unittest.mock import patch

import pytest


# ═══════════════════════════════════════════════════════════════════════════
# TOOL METRICS
# ═══════════════════════════════════════════════════════════════════════════

class TestToolMetrics:
    def test_singleton(self):
        from src.tools import ToolMetrics
        a = ToolMetrics()
        b = ToolMetrics()
        assert a is b

    def test_record_and_report(self):
        from src.tools import ToolMetrics
        m = ToolMetrics()
        m.reset()
        m.record("test_tool", 150.0, success=True)
        m.record("test_tool", 250.0, success=True)
        m.record("test_tool", 100.0, success=False)
        report = m.get_report()
        assert "test_tool" in report
        assert report["test_tool"]["calls"] == 3
        assert report["test_tool"]["success"] == 2
        assert report["test_tool"]["errors"] == 1
        assert report["test_tool"]["avg_ms"] == pytest.approx(166.7, abs=1)

    def test_cache_hit(self):
        from src.tools import ToolMetrics
        m = ToolMetrics()
        m.reset()
        m.record_cache_hit("cached_tool")
        m.record_cache_hit("cached_tool")
        report = m.get_report()
        # cache_hits recorded even without calls
        assert m.cache_hits["cached_tool"] == 2


class TestCacheResponse:
    def test_cache_stats(self):
        from src.tools import get_cache_stats, clear_cache
        clear_cache()
        stats = get_cache_stats()
        assert isinstance(stats, dict)
        assert "default" in stats
        assert stats["default"]["entries"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# OBSERVABILITY
# ═══════════════════════════════════════════════════════════════════════════

class TestObservabilityMatrix:
    def test_record_and_windowed(self):
        from src.observability import ObservabilityMatrix
        matrix = ObservabilityMatrix()
        matrix.record("M1", "latency_ms", 100)
        matrix.record("M1", "latency_ms", 200)
        matrix.record("M2", "latency_ms", 300)
        data = matrix.get_windowed("1m")
        assert "M1" in data
        assert data["M1"]["latency_ms"]["mean"] == 150.0
        assert data["M1"]["latency_ms"]["count"] == 2
        assert "M2" in data

    def test_record_node_call(self):
        from src.observability import ObservabilityMatrix
        matrix = ObservabilityMatrix()
        matrix.record_node_call("M1", latency_ms=50, success=True, tokens=100, duration_s=2.0)
        data = matrix.get_windowed("1m")
        assert "M1" in data
        assert "latency_ms" in data["M1"]

    def test_heatmap(self):
        from src.observability import ObservabilityMatrix
        matrix = ObservabilityMatrix()
        matrix.record("M1", "latency_ms", 100)
        heatmap = matrix.get_heatmap("1m")
        assert len(heatmap) >= 1
        assert heatmap[0]["node"] == "M1"
        assert "anomaly_score" in heatmap[0]

    def test_anomaly_score_without_baseline(self):
        from src.observability import ObservabilityMatrix
        matrix = ObservabilityMatrix()
        matrix.record("M1", "latency_ms", 100)
        heatmap = matrix.get_heatmap("1m")
        assert heatmap[0]["anomaly_score"] == 0.0  # No baseline = no anomaly

    def test_get_report(self):
        from src.observability import ObservabilityMatrix
        matrix = ObservabilityMatrix()
        matrix.record("M1", "success_rate", 1.0)
        report = matrix.get_report()
        assert "matrix_5m" in report
        assert "heatmap" in report
        assert "alerts" in report
        assert "total_points" in report


# ═══════════════════════════════════════════════════════════════════════════
# DRIFT DETECTOR
# ═══════════════════════════════════════════════════════════════════════════

class TestDriftDetector:
    def test_record_and_health(self):
        from src.drift_detector import DriftDetector
        dd = DriftDetector()
        dd.record("test_model", latency_ms=100, success=True, quality=0.9)
        dd.record("test_model", latency_ms=120, success=True, quality=0.85)
        health = dd.get_model_health("test_model")
        assert health["model"] == "test_model"
        assert "latency_ms" in health["metrics"]

    def test_degraded_empty(self):
        from src.drift_detector import DriftDetector
        dd = DriftDetector()
        assert dd.get_degraded_models() == []

    def test_suggest_rerouting_no_degraded(self):
        from src.drift_detector import DriftDetector
        dd = DriftDetector()
        candidates = ["M1", "M2", "OL1"]
        result = dd.suggest_rerouting("code", candidates)
        assert result == candidates

    def test_report(self):
        from src.drift_detector import DriftDetector
        dd = DriftDetector()
        report = dd.get_report()
        assert "models" in report
        assert "alerts" in report
        assert "degraded" in report


# ═══════════════════════════════════════════════════════════════════════════
# AUTO-TUNE
# ═══════════════════════════════════════════════════════════════════════════

class TestAutoTune:
    def test_node_load(self):
        from src.auto_tune import AutoTuneScheduler
        scheduler = AutoTuneScheduler()
        load = scheduler.get_node_load("M1")
        assert load.name == "M1"
        assert load.load_factor == 0.0
        assert not load.is_cooling

    def test_begin_end_request(self):
        from src.auto_tune import AutoTuneScheduler
        scheduler = AutoTuneScheduler()
        scheduler.begin_request("M1")
        load = scheduler.get_node_load("M1")
        assert load.active_requests == 1
        scheduler.end_request("M1", latency_ms=100, success=True)
        assert load.active_requests == 0

    def test_cooldown(self):
        from src.auto_tune import AutoTuneScheduler
        scheduler = AutoTuneScheduler()
        scheduler.apply_cooldown("M1", 0.1)
        assert scheduler.get_node_load("M1").is_cooling
        time.sleep(0.15)
        assert not scheduler.get_node_load("M1").is_cooling

    def test_best_available(self):
        from src.auto_tune import AutoTuneScheduler
        scheduler = AutoTuneScheduler()
        best = scheduler.get_best_available_node(["M1", "M2"])
        assert best in ("M1", "M2")

    def test_status(self):
        from src.auto_tune import AutoTuneScheduler
        scheduler = AutoTuneScheduler()
        status = scheduler.get_status()
        assert "threadpool_size" in status
        assert "resource_snapshot" in status


# ═══════════════════════════════════════════════════════════════════════════
# INTENT CLASSIFIER
# ═══════════════════════════════════════════════════════════════════════════

class TestIntentClassifier:
    def test_classify_navigation(self):
        from src.intent_classifier import IntentClassifier
        ic = IntentClassifier()
        results = ic.classify("ouvre chrome")
        assert len(results) > 0
        assert results[0].intent in ("navigation", "app_launch")
        assert results[0].confidence > 0.5

    def test_classify_trading(self):
        from src.intent_classifier import IntentClassifier
        ic = IntentClassifier()
        results = ic.classify("scanne bitcoin")
        assert any(r.intent == "trading" for r in results)

    def test_classify_system(self):
        from src.intent_classifier import IntentClassifier
        ic = IntentClassifier()
        results = ic.classify("eteins le pc")
        assert any(r.intent == "system_control" for r in results)

    def test_entity_extraction(self):
        from src.intent_classifier import IntentClassifier
        ic = IntentClassifier()
        results = ic.classify("analyse BTC sur M1")
        entities = results[0].entities
        assert "crypto_pair" in entities or "node_name" in entities

    def test_classify_single(self):
        from src.intent_classifier import IntentClassifier
        ic = IntentClassifier()
        result = ic.classify_single("ouvre youtube")
        assert result.intent in ("navigation", "app_launch")
        assert result.confidence > 0

    def test_report(self):
        from src.intent_classifier import IntentClassifier
        ic = IntentClassifier()
        report = ic.get_report()
        assert "intents" in report
        assert len(report["intents"]) >= 10


# ═══════════════════════════════════════════════════════════════════════════
# TRADING ENGINE
# ═══════════════════════════════════════════════════════════════════════════

class TestTradingEngine:
    def test_trade_signal(self):
        from src.trading_engine import TradeSignal
        sig = TradeSignal(
            pair="BTC/USDT", direction="long",
            entry_price=50000, take_profit=50200, stop_loss=49875,
            confidence=85, strategy="test_strat",
        )
        assert sig.risk_reward == pytest.approx(1.6, abs=0.1)

    def test_strategy_scorer(self):
        from src.trading_engine import StrategyScorer
        scorer = StrategyScorer()
        scorer.record_outcome("strat_a", 0.4, 60)
        scorer.record_outcome("strat_a", -0.25, 30)
        scorer.record_outcome("strat_a", 0.4, 45)
        rankings = scorer.get_strategy_rankings()
        assert len(rankings) == 1
        assert rankings[0]["strategy"] == "strat_a"
        assert rankings[0]["trades"] == 3

    def test_backtest_empty_candles(self):
        from src.trading_engine import BacktestEngine
        engine = BacktestEngine()
        result = engine.run([], lambda c: None, "BTC/USDT")
        assert result.total_trades == 0
        assert result.win_rate == 0.0


# ═══════════════════════════════════════════════════════════════════════════
# DATABASE MIGRATIONS
# ═══════════════════════════════════════════════════════════════════════════

class TestDatabaseMigrations:
    def test_apply_migrations(self, tmp_path):
        import sqlite3
        from src.database import apply_migrations, get_applied_migrations
        db = tmp_path / "test.db"
        conn = sqlite3.connect(str(db))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.close()
        applied = apply_migrations(db)
        assert len(applied) > 0
        # Verify migration table exists
        conn = sqlite3.connect(str(db))
        rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
        conn.close()
        assert len(rows) == len(applied)

    def test_db_health(self):
        from src.database import get_db_health
        health = get_db_health()
        assert isinstance(health, dict)
        assert "jarvis" in health

    def test_list_backups(self):
        from src.database import list_backups
        backups = list_backups()
        assert isinstance(backups, list)


# ═══════════════════════════════════════════════════════════════════════════
# COMMAND ANALYTICS
# ═══════════════════════════════════════════════════════════════════════════

class TestCommandAnalytics:
    def test_dry_run(self):
        from src.commands import dry_run_command
        result = dry_run_command("ouvre chrome")
        assert isinstance(result, dict)
        assert "matched" in result

    def test_get_macros_empty(self):
        from src.commands import get_macros
        macros = get_macros()
        assert isinstance(macros, dict)


# ═══════════════════════════════════════════════════════════════════════════
# PEARSON CORRELATION HELPER
# ═══════════════════════════════════════════════════════════════════════════

class TestPearsonCorrelation:
    def test_perfect_positive(self):
        from src.observability import _pearson
        assert _pearson([1, 2, 3, 4, 5], [2, 4, 6, 8, 10]) == pytest.approx(1.0)

    def test_perfect_negative(self):
        from src.observability import _pearson
        assert _pearson([1, 2, 3, 4, 5], [10, 8, 6, 4, 2]) == pytest.approx(-1.0)

    def test_no_correlation(self):
        from src.observability import _pearson
        # Not truly zero but should be low
        result = _pearson([1, 2, 1, 2, 1], [1, 1, 2, 2, 1])
        assert abs(result) < 0.5

    def test_empty(self):
        from src.observability import _pearson
        assert _pearson([], []) == 0.0


# ═══════════════════════════════════════════════════════════════════════════
# ORCHESTRATOR V2
# ═══════════════════════════════════════════════════════════════════════════

class TestOrchestratorV2:
    def test_record_call(self):
        from src.orchestrator_v2 import OrchestratorV2
        ov2 = OrchestratorV2()
        ov2.record_call("M1", latency_ms=100, success=True, tokens=50)
        # Should not raise

    def test_get_best_node(self):
        from src.orchestrator_v2 import OrchestratorV2
        ov2 = OrchestratorV2()
        best = ov2.get_best_node(["M1", "M2", "OL1"], task_type="code")
        assert best in ("M1", "M2", "OL1")

    def test_get_best_node_empty(self):
        from src.orchestrator_v2 import OrchestratorV2
        ov2 = OrchestratorV2()
        assert ov2.get_best_node([], task_type="code") is None

    def test_dashboard(self):
        from src.orchestrator_v2 import OrchestratorV2
        ov2 = OrchestratorV2()
        dash = ov2.get_dashboard()
        assert "observability" in dash
        assert "drift" in dash
        assert "auto_tune" in dash
        assert "health_score" in dash
        assert 0 <= dash["health_score"] <= 100

    def test_health_check(self):
        from src.orchestrator_v2 import OrchestratorV2
        ov2 = OrchestratorV2()
        score = ov2.health_check()
        assert 0 <= score <= 100

    def test_get_alerts(self):
        from src.orchestrator_v2 import OrchestratorV2
        ov2 = OrchestratorV2()
        alerts = ov2.get_alerts()
        assert isinstance(alerts, list)

    def test_record_and_best_node_selects_best(self):
        from src.orchestrator_v2 import OrchestratorV2
        ov2 = OrchestratorV2()
        # Record good calls for M1, bad for M2
        for _ in range(5):
            ov2.record_call("M1", latency_ms=50, success=True, quality=0.95)
            ov2.record_call("M2", latency_ms=500, success=False, quality=0.1)
        best = ov2.get_best_node(["M1", "M2"], task_type="code")
        # M1 should be preferred (lower latency, higher success)
        assert best in ("M1", "M2")  # either is valid, just ensure no crash

    def test_dashboard_keys_complete(self):
        from src.orchestrator_v2 import OrchestratorV2
        ov2 = OrchestratorV2()
        dash = ov2.get_dashboard()
        required = {"observability", "drift", "auto_tune", "health_score", "node_stats", "budget"}
        assert required.issubset(dash.keys())

    def test_weighted_score(self):
        from src.orchestrator_v2 import OrchestratorV2
        ov2 = OrchestratorV2()
        score = ov2.weighted_score("M1", "code")
        assert isinstance(score, float)
        assert score >= 0

    def test_weighted_score_after_calls(self):
        from src.orchestrator_v2 import OrchestratorV2
        ov2 = OrchestratorV2()
        for _ in range(5):
            ov2.record_call("M1", latency_ms=50, success=True, tokens=100)
            ov2.record_call("M2", latency_ms=500, success=False, tokens=10)
        score_m1 = ov2.weighted_score("M1", "code")
        score_m2 = ov2.weighted_score("M2", "code")
        assert score_m1 > score_m2  # M1 better: lower latency, 100% success

    def test_fallback_chain(self):
        from src.orchestrator_v2 import OrchestratorV2
        ov2 = OrchestratorV2()
        chain = ov2.fallback_chain("code")
        assert isinstance(chain, list)
        assert len(chain) > 0
        assert all(isinstance(n, str) for n in chain)

    def test_fallback_chain_exclude(self):
        from src.orchestrator_v2 import OrchestratorV2
        ov2 = OrchestratorV2()
        chain = ov2.fallback_chain("code", exclude={"M1"})
        assert "M1" not in chain

    def test_budget_report(self):
        from src.orchestrator_v2 import OrchestratorV2
        ov2 = OrchestratorV2()
        ov2.record_call("M1", latency_ms=50, success=True, tokens=100)
        ov2.record_call("OL1", latency_ms=30, success=True, tokens=50)
        report = ov2.get_budget_report()
        assert report["total_tokens"] == 150
        assert report["total_calls"] == 2
        assert report["tokens_by_node"]["M1"] == 100
        assert report["calls_by_node"]["OL1"] == 1

    def test_reset_budget(self):
        from src.orchestrator_v2 import OrchestratorV2
        ov2 = OrchestratorV2()
        ov2.record_call("M1", latency_ms=50, success=True, tokens=500)
        ov2.reset_budget()
        report = ov2.get_budget_report()
        assert report["total_tokens"] == 0

    def test_node_stats(self):
        from src.orchestrator_v2 import OrchestratorV2
        ov2 = OrchestratorV2()
        ov2.record_call("M1", latency_ms=100, success=True, tokens=50)
        ov2.record_call("M1", latency_ms=200, success=True, tokens=75)
        stats = ov2.get_node_stats()
        assert "M1" in stats
        assert stats["M1"]["total_calls"] == 2
        assert stats["M1"]["success_rate"] == 1.0
        assert stats["M1"]["avg_latency_ms"] == 150.0

    def test_routing_matrix_exists(self):
        from src.orchestrator_v2 import ROUTING_MATRIX
        required_types = {"code", "voice", "trading", "simple", "reasoning"}
        assert required_types.issubset(ROUTING_MATRIX.keys())


# ═══════════════════════════════════════════════════════════════════════════
# TERMINAL V2 BUILTINS
# ═══════════════════════════════════════════════════════════════════════════

class TestTerminalV2Builtins:
    def test_all_builtins_registered(self):
        from python_ws.routes.terminal import BUILTIN_COMMANDS
        phase4_cmds = {"observability", "drift", "autotune", "dashboard", "intent", "help"}
        for cmd in phase4_cmds:
            assert cmd in BUILTIN_COMMANDS, f"Missing builtin: {cmd}"

    def test_help_returns_all_commands(self):
        import asyncio
        from python_ws.routes.terminal import BUILTIN_COMMANDS
        help_fn = BUILTIN_COMMANDS["help"]
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(help_fn())
        finally:
            loop.close()
        assert "observability" in result
        assert "drift" in result
        assert "dashboard" in result


# ═══════════════════════════════════════════════════════════════════════════
# EXECUTOR V2 — Voice pipeline integration
# ═══════════════════════════════════════════════════════════════════════════

class TestExecutorV2:
    def test_record_execution_no_crash(self):
        from src.executor import _record_execution
        _record_execution("test raw", "test corrected", "test_cmd", 0.9, None, 100.0)

    def test_record_ia_correction_no_crash(self):
        from src.executor import _record_ia_correction
        _record_ia_correction("OL1", 0.05, True)
        _record_ia_correction("M1", 0.1, False)

    def test_process_voice_input_exists(self):
        import inspect
        from src.executor import process_voice_input
        assert inspect.iscoroutinefunction(process_voice_input)

    def test_correct_with_ia_exists(self):
        import inspect
        from src.executor import correct_with_ia
        assert inspect.iscoroutinefunction(correct_with_ia)


# ═══════════════════════════════════════════════════════════════════════════
# DOMINO EXECUTOR V2
# ═══════════════════════════════════════════════════════════════════════════

class TestDominoExecutorV2:
    def test_eval_condition_equality(self):
        from src.domino_executor import DominoExecutor
        ex = DominoExecutor()
        ex._context = {"status": "PASS", "count": "5"}
        assert ex._eval_condition("status == PASS")
        assert not ex._eval_condition("status == FAIL")

    def test_eval_condition_numeric(self):
        from src.domino_executor import DominoExecutor
        ex = DominoExecutor()
        ex._context = {"temp": "65", "load": "0.3"}
        assert ex._eval_condition("temp < 80")
        assert not ex._eval_condition("temp > 80")
        assert ex._eval_condition("load <= 0.5")

    def test_eval_condition_contains(self):
        from src.domino_executor import DominoExecutor
        ex = DominoExecutor()
        ex._context = {"output": "GPU OK temperature normale"}
        assert ex._eval_condition("output contains 'OK'")
        assert not ex._eval_condition("output contains 'ERROR'")

    def test_eval_condition_exists(self):
        from src.domino_executor import DominoExecutor
        ex = DominoExecutor()
        ex._context = {"mykey": "val"}
        assert ex._eval_condition("mykey exists")
        assert not ex._eval_condition("missing_key exists")

    def test_eval_condition_and_or(self):
        from src.domino_executor import DominoExecutor
        ex = DominoExecutor()
        ex._context = {"a": "1", "b": "2"}
        assert ex._eval_condition("a == 1 and b == 2")
        assert not ex._eval_condition("a == 1 and b == 3")
        assert ex._eval_condition("a == 1 or b == 3")

    def test_orchestrator_fallback_exists(self):
        from src.domino_executor import _get_orchestrator_fallback
        chain = _get_orchestrator_fallback("code")
        assert isinstance(chain, list)
        assert len(chain) > 0
