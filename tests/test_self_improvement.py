"""Tests for src/self_improvement.py — SelfImprover, ImprovementAction, get_improver.

Covers: ImprovementAction dataclass, SelfImprover (analyze, suggest_improvements,
apply_improvements, _apply_action, _apply_route_shift, _apply_temp_adjust,
_apply_tokens_adjust, _apply_gate_tune, _log_action, get_history, get_stats,
_analyze_benchmark_data), get_improver singleton.
All external deps (sqlite3, src.quality_gate, src.adaptive_router,
src.pattern_agents) are mocked so tests run in isolation without DB or network.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Helpers — build SelfImprover with mocked DB
# ---------------------------------------------------------------------------

def _make_improver():
    """Create a SelfImprover with sqlite3 mocked out (no real DB)."""
    with patch("src.self_improvement.sqlite3") as mock_sql:
        mock_conn = MagicMock()
        mock_sql.connect.return_value = mock_conn
        from src.self_improvement import SelfImprover
        improver = SelfImprover()
    return improver


def _fake_row(mapping: dict):
    """Create a fake sqlite3.Row-like object that supports [] and keys()."""
    obj = MagicMock()
    obj.__getitem__ = lambda self, key: mapping[key]
    obj.keys.return_value = list(mapping.keys())
    return obj


# ---------------------------------------------------------------------------
# ImprovementAction dataclass
# ---------------------------------------------------------------------------

class TestImprovementAction:
    def test_defaults(self):
        from src.self_improvement import ImprovementAction
        action = ImprovementAction(
            action_type="route_shift", target="M2",
            description="test", priority="high"
        )
        assert action.params == {}
        assert action.applied is False
        assert action.result == ""

    def test_custom_fields(self):
        from src.self_improvement import ImprovementAction
        action = ImprovementAction(
            action_type="temp_adjust", target="code",
            description="lower temp", priority="critical",
            params={"suggested_temp": 0.1}, applied=True, result="ok"
        )
        assert action.action_type == "temp_adjust"
        assert action.params["suggested_temp"] == 0.1
        assert action.applied is True


# ---------------------------------------------------------------------------
# SelfImprover.__init__ / _ensure_table
# ---------------------------------------------------------------------------

class TestEnsureTable:
    def test_creates_table_on_init(self):
        with patch("src.self_improvement.sqlite3") as mock_sql:
            mock_conn = MagicMock()
            mock_sql.connect.return_value = mock_conn
            from src.self_improvement import SelfImprover
            SelfImprover()
            mock_conn.execute.assert_called_once()
            sql = mock_conn.execute.call_args[0][0]
            assert "CREATE TABLE IF NOT EXISTS self_improvement_log" in sql
            mock_conn.commit.assert_called_once()
            mock_conn.close.assert_called_once()

    def test_ensure_table_swallows_errors(self):
        """If DB is unavailable, __init__ should not raise."""
        with patch("src.self_improvement.sqlite3") as mock_sql:
            mock_sql.connect.side_effect = Exception("DB locked")
            from src.self_improvement import SelfImprover
            imp = SelfImprover()  # Should not raise
            assert imp._history == []


# ---------------------------------------------------------------------------
# analyze()
# ---------------------------------------------------------------------------

class TestAnalyze:
    def test_analyze_returns_error_on_db_failure(self):
        imp = _make_improver()
        with patch("src.self_improvement.sqlite3") as mock_sql:
            mock_sql.connect.side_effect = Exception("DB error")
            result = imp.analyze()
        assert "error" in result
        assert "DB error" in result["error"]

    def test_analyze_returns_complete_structure(self):
        """Verify analyze() returns all expected keys with correct types."""
        imp = _make_improver()

        # Build fake DB results
        gate_failures = [_fake_row({
            "pattern": "code", "failed_gates": "length",
            "n": 5, "avg_score": 0.35,
        })]
        node_trends = [_fake_row({
            "node": "M1", "n": 100, "avg_q": 0.85,
            "avg_lat": 5000.0, "success_rate": 95.0, "fallbacks": 2,
        })]
        pattern_quality = [_fake_row({
            "pattern": "simple", "n": 50, "avg_q": 0.9,
            "min_q": 0.6, "max_q": 1.0, "avg_pipe": 3000.0,
        })]
        fallback_stats = [_fake_row({
            "pattern": "code", "node": "M2", "n": 3,
        })]

        mock_conn = MagicMock()
        mock_conn.row_factory = None

        # Map each SQL call to its result
        execute_calls = [
            MagicMock(fetchall=MagicMock(return_value=gate_failures)),     # gate_failures
            MagicMock(fetchall=MagicMock(return_value=node_trends)),       # node_trends
            MagicMock(fetchall=MagicMock(return_value=pattern_quality)),   # pattern_quality
            MagicMock(fetchall=MagicMock(return_value=fallback_stats)),    # fallback_stats
            MagicMock(fetchone=MagicMock(return_value=(200,))),            # total
            MagicMock(fetchone=MagicMock(return_value=(180,))),            # ok_total
            MagicMock(fetchone=MagicMock(return_value=(0.82,))),           # avg_q
        ]
        mock_conn.execute = MagicMock(side_effect=execute_calls)

        with patch("src.self_improvement.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_conn
            mock_sql.Row = "Row"
            result = imp.analyze()

        assert "health_score" in result
        assert "total_dispatches" in result
        assert "success_rate" in result
        assert "avg_quality" in result
        assert "gate_failures" in result
        assert "node_trends" in result
        assert "pattern_quality" in result
        assert "fallback_hotspots" in result
        assert result["total_dispatches"] == 200
        assert result["success_rate"] == 0.9  # 180/200
        assert isinstance(result["gate_failures"], list)
        assert result["gate_failures"][0]["pattern"] == "code"

    def test_analyze_health_score_calculation(self):
        """Verify health_score = min(100, success_pct * 50 + avg_q * 50)."""
        imp = _make_improver()

        mock_conn = MagicMock()
        execute_calls = [
            MagicMock(fetchall=MagicMock(return_value=[])),  # gate_failures
            MagicMock(fetchall=MagicMock(return_value=[])),  # node_trends
            MagicMock(fetchall=MagicMock(return_value=[])),  # pattern_quality
            MagicMock(fetchall=MagicMock(return_value=[])),  # fallback_stats
            MagicMock(fetchone=MagicMock(return_value=(100,))),  # total
            MagicMock(fetchone=MagicMock(return_value=(80,))),   # ok_total
            MagicMock(fetchone=MagicMock(return_value=(0.7,))),  # avg_q
        ]
        mock_conn.execute = MagicMock(side_effect=execute_calls)

        with patch("src.self_improvement.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_conn
            mock_sql.Row = "Row"
            result = imp.analyze()

        # (80/100) * 50 + 0.7 * 50 = 40 + 35 = 75.0
        assert result["health_score"] == 75.0


# ---------------------------------------------------------------------------
# suggest_improvements()
# ---------------------------------------------------------------------------

class TestSuggestImprovements:
    def _make_improver_with_analysis(self, analysis):
        """Helper: create an improver whose analyze() returns given data."""
        imp = _make_improver()
        imp.analyze = MagicMock(return_value=analysis)
        return imp

    def test_returns_empty_on_analysis_error(self):
        imp = self._make_improver_with_analysis({"error": "DB down"})
        # Also need to mock _analyze_benchmark_data and quality_gate import
        actions = imp.suggest_improvements()
        assert actions == []

    def test_route_shift_for_low_success_node(self):
        analysis = {
            "node_trends": [
                {"node": "M3", "success_rate": 50.0, "dispatches": 10,
                 "avg_quality": 0.3, "avg_latency_ms": 5000, "fallbacks": 5}
            ],
            "pattern_quality": [],
            "gate_failures": [],
            "fallback_hotspots": [],
        }
        imp = self._make_improver_with_analysis(analysis)
        imp._analyze_benchmark_data = MagicMock(return_value=[])
        with patch("src.quality_gate.get_gate", side_effect=ImportError):
            actions = imp.suggest_improvements()

        route_shifts = [a for a in actions if a.action_type == "route_shift"]
        assert len(route_shifts) >= 1
        assert route_shifts[0].target == "M3"
        assert route_shifts[0].priority == "high"

    def test_route_shift_for_high_latency_node(self):
        analysis = {
            "node_trends": [
                {"node": "M2", "success_rate": 90.0, "dispatches": 10,
                 "avg_quality": 0.7, "avg_latency_ms": 45000, "fallbacks": 0}
            ],
            "pattern_quality": [],
            "gate_failures": [],
            "fallback_hotspots": [],
        }
        imp = self._make_improver_with_analysis(analysis)
        imp._analyze_benchmark_data = MagicMock(return_value=[])
        with patch("src.quality_gate.get_gate", side_effect=ImportError):
            actions = imp.suggest_improvements()

        route_shifts = [a for a in actions if a.action_type == "route_shift"
                        and a.params.get("avg_latency_ms")]
        assert len(route_shifts) >= 1
        assert route_shifts[0].priority == "medium"

    def test_temp_adjust_for_low_quality_pattern(self):
        analysis = {
            "node_trends": [],
            "pattern_quality": [
                {"pattern": "reasoning", "dispatches": 10, "avg_quality": 0.2,
                 "min_quality": 0.1, "max_quality": 0.3, "avg_pipeline_ms": 8000}
            ],
            "gate_failures": [],
            "fallback_hotspots": [],
        }
        imp = self._make_improver_with_analysis(analysis)
        imp._analyze_benchmark_data = MagicMock(return_value=[])
        with patch("src.quality_gate.get_gate", side_effect=ImportError):
            actions = imp.suggest_improvements()

        temp_adjs = [a for a in actions if a.action_type == "temp_adjust"]
        assert len(temp_adjs) >= 1
        assert temp_adjs[0].params["suggested_temp"] == 0.1

    def test_temp_adjust_for_high_variance_pattern(self):
        analysis = {
            "node_trends": [],
            "pattern_quality": [
                {"pattern": "creative", "dispatches": 10, "avg_quality": 0.6,
                 "min_quality": 0.2, "max_quality": 0.9, "avg_pipeline_ms": 7000}
            ],
            "gate_failures": [],
            "fallback_hotspots": [],
        }
        imp = self._make_improver_with_analysis(analysis)
        imp._analyze_benchmark_data = MagicMock(return_value=[])
        with patch("src.quality_gate.get_gate", side_effect=ImportError):
            actions = imp.suggest_improvements()

        temp_adjs = [a for a in actions if a.action_type == "temp_adjust"]
        assert len(temp_adjs) >= 1
        assert temp_adjs[0].params["suggested_temp"] == 0.15
        assert temp_adjs[0].priority == "medium"

    def test_tokens_adjust_for_fast_low_quality(self):
        analysis = {
            "node_trends": [],
            "pattern_quality": [
                {"pattern": "analysis", "dispatches": 8, "avg_quality": 0.2,
                 "min_quality": 0.1, "max_quality": 0.3, "avg_pipeline_ms": 2000}
            ],
            "gate_failures": [],
            "fallback_hotspots": [],
        }
        imp = self._make_improver_with_analysis(analysis)
        imp._analyze_benchmark_data = MagicMock(return_value=[])
        with patch("src.quality_gate.get_gate", side_effect=ImportError):
            actions = imp.suggest_improvements()

        token_adjs = [a for a in actions if a.action_type == "tokens_adjust"]
        assert len(token_adjs) >= 1
        assert token_adjs[0].params["suggested_max_tokens"] == 2048

    def test_gate_tune_for_length_failures(self):
        analysis = {
            "node_trends": [],
            "pattern_quality": [],
            "gate_failures": [
                {"pattern": "simple", "failed_gates": "length", "count": 5, "avg_score": 0.2}
            ],
            "fallback_hotspots": [],
        }
        imp = self._make_improver_with_analysis(analysis)
        imp._analyze_benchmark_data = MagicMock(return_value=[])
        with patch("src.quality_gate.get_gate", side_effect=ImportError):
            actions = imp.suggest_improvements()

        gate_tunes = [a for a in actions if a.action_type == "gate_tune"]
        assert len(gate_tunes) >= 1
        assert gate_tunes[0].params["gate"] == "length"

    def test_gate_tune_for_latency_failures(self):
        analysis = {
            "node_trends": [],
            "pattern_quality": [],
            "gate_failures": [
                {"pattern": "code", "failed_gates": "latency", "count": 8, "avg_score": 0.4}
            ],
            "fallback_hotspots": [],
        }
        imp = self._make_improver_with_analysis(analysis)
        imp._analyze_benchmark_data = MagicMock(return_value=[])
        with patch("src.quality_gate.get_gate", side_effect=ImportError):
            actions = imp.suggest_improvements()

        gate_tunes = [a for a in actions if a.action_type == "gate_tune"
                      and a.params.get("gate") == "latency"]
        assert len(gate_tunes) >= 1
        assert gate_tunes[0].priority == "high"

    def test_prompt_enhance_for_very_low_quality(self):
        analysis = {
            "node_trends": [],
            "pattern_quality": [
                {"pattern": "web", "dispatches": 10, "avg_quality": 0.15,
                 "min_quality": 0.05, "max_quality": 0.25, "avg_pipeline_ms": 10000}
            ],
            "gate_failures": [],
            "fallback_hotspots": [],
        }
        imp = self._make_improver_with_analysis(analysis)
        imp._analyze_benchmark_data = MagicMock(return_value=[])
        with patch("src.quality_gate.get_gate", side_effect=ImportError):
            actions = imp.suggest_improvements()

        prompts = [a for a in actions if a.action_type == "prompt_enhance"]
        assert len(prompts) >= 1
        assert prompts[0].priority == "critical"

    def test_actions_sorted_by_priority(self):
        analysis = {
            "node_trends": [
                {"node": "M3", "success_rate": 50.0, "dispatches": 10,
                 "avg_quality": 0.3, "avg_latency_ms": 5000, "fallbacks": 5}
            ],
            "pattern_quality": [
                {"pattern": "web", "dispatches": 10, "avg_quality": 0.15,
                 "min_quality": 0.05, "max_quality": 0.25, "avg_pipeline_ms": 10000}
            ],
            "gate_failures": [],
            "fallback_hotspots": [],
        }
        imp = self._make_improver_with_analysis(analysis)
        imp._analyze_benchmark_data = MagicMock(return_value=[])
        with patch("src.quality_gate.get_gate", side_effect=ImportError):
            actions = imp.suggest_improvements()

        prio_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        priorities = [prio_order.get(a.priority, 9) for a in actions]
        assert priorities == sorted(priorities)


# ---------------------------------------------------------------------------
# _analyze_benchmark_data()
# ---------------------------------------------------------------------------

class TestAnalyzeBenchmarkData:
    def test_returns_route_shifts_for_bad_combos(self):
        imp = _make_improver()

        bad_combos = [_fake_row({
            "pattern": "code", "node": "M3", "n": 10, "ok": 2, "avg_lat": 20000,
        })]
        best_nodes = [
            _fake_row({"pattern": "code", "node": "M1", "rate": 0.95, "n": 50}),
            _fake_row({"pattern": "code", "node": "M3", "rate": 0.2, "n": 10}),
        ]

        mock_conn = MagicMock()
        execute_calls = [
            MagicMock(fetchall=MagicMock(return_value=bad_combos)),
            MagicMock(fetchall=MagicMock(return_value=best_nodes)),
        ]
        mock_conn.execute = MagicMock(side_effect=execute_calls)

        with patch("src.self_improvement.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_conn
            mock_sql.Row = "Row"
            actions = imp._analyze_benchmark_data()

        assert len(actions) >= 1
        assert actions[0].action_type == "route_shift"
        assert actions[0].params["from_node"] == "M3"
        assert actions[0].params["to_node"] == "M1"

    def test_returns_empty_on_db_error(self):
        imp = _make_improver()
        with patch("src.self_improvement.sqlite3") as mock_sql:
            mock_sql.connect.side_effect = Exception("DB locked")
            actions = imp._analyze_benchmark_data()
        assert actions == []


# ---------------------------------------------------------------------------
# apply_improvements()
# ---------------------------------------------------------------------------

class TestApplyImprovements:
    def test_auto_applies_critical_and_high(self):
        from src.self_improvement import ImprovementAction
        imp = _make_improver()

        actions = [
            ImprovementAction("route_shift", "M3", "shift away", "critical",
                              params={"from_node": "M3"}),
            ImprovementAction("temp_adjust", "code", "lower temp", "high",
                              params={"pattern": "code", "suggested_temp": 0.1}),
            ImprovementAction("tokens_adjust", "web", "more tokens", "medium",
                              params={"pattern": "web", "suggested_max_tokens": 2048}),
        ]
        imp.suggest_improvements = MagicMock(return_value=actions)
        imp._apply_action = MagicMock(return_value=True)
        imp._log_action = MagicMock()

        results = imp.apply_improvements(auto=True, max_actions=5)

        assert len(results) == 3
        # critical + high should be auto-applied
        assert results[0]["applied"] is True
        assert results[0]["result"] == "auto-applied"
        assert results[1]["applied"] is True
        # medium should NOT be auto-applied
        assert results[2]["applied"] is False
        assert "manual review" in results[2]["result"]

    def test_no_auto_when_auto_false(self):
        from src.self_improvement import ImprovementAction
        imp = _make_improver()

        actions = [
            ImprovementAction("route_shift", "M3", "shift", "critical"),
        ]
        imp.suggest_improvements = MagicMock(return_value=actions)
        imp._apply_action = MagicMock()
        imp._log_action = MagicMock()

        results = imp.apply_improvements(auto=False)

        imp._apply_action.assert_not_called()
        assert results[0]["applied"] is False

    def test_max_actions_limits_output(self):
        from src.self_improvement import ImprovementAction
        imp = _make_improver()

        actions = [ImprovementAction("temp_adjust", f"p{i}", "desc", "high")
                   for i in range(10)]
        imp.suggest_improvements = MagicMock(return_value=actions)
        imp._apply_action = MagicMock(return_value=True)
        imp._log_action = MagicMock()

        results = imp.apply_improvements(auto=True, max_actions=3)
        assert len(results) == 3

    def test_apply_action_failure_marks_failed(self):
        from src.self_improvement import ImprovementAction
        imp = _make_improver()

        actions = [
            ImprovementAction("route_shift", "M3", "shift", "critical"),
        ]
        imp.suggest_improvements = MagicMock(return_value=actions)
        imp._apply_action = MagicMock(return_value=False)
        imp._log_action = MagicMock()

        results = imp.apply_improvements(auto=True)
        assert results[0]["applied"] is False
        assert results[0]["result"] == "failed"


# ---------------------------------------------------------------------------
# _apply_route_shift()
# ---------------------------------------------------------------------------

class TestApplyRouteShift:
    def test_pattern_level_route_shift(self):
        from src.self_improvement import ImprovementAction
        imp = _make_improver()

        action = ImprovementAction(
            "route_shift", "code", "shift code to M1", "high",
            params={"pattern": "code", "from_node": "M3", "to_node": "M1"},
        )

        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = ("qwen3-8b",)

        with patch("src.self_improvement.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_conn
            result = imp._apply_route_shift(action)

        assert result is True
        # Verify UPDATE was called
        update_calls = [c for c in mock_conn.execute.call_args_list
                        if "UPDATE" in str(c)]
        assert len(update_calls) >= 1

    def test_node_level_penalization(self):
        from src.self_improvement import ImprovementAction
        imp = _make_improver()

        action = ImprovementAction(
            "route_shift", "M3", "penalize M3", "high",
            params={"from_node": "M3"},
        )

        mock_router = MagicMock()
        mock_router.penalize_node = MagicMock()

        with patch("src.self_improvement.sqlite3"):
            with patch("src.adaptive_router.get_router", return_value=mock_router):
                result = imp._apply_route_shift(action)

        assert result is True


# ---------------------------------------------------------------------------
# _apply_temp_adjust() / _apply_tokens_adjust()
# ---------------------------------------------------------------------------

class TestApplyTempAndTokens:
    def test_apply_temp_adjust_success(self):
        from src.self_improvement import ImprovementAction
        imp = _make_improver()

        action = ImprovementAction(
            "temp_adjust", "code", "lower temp", "high",
            params={"pattern": "code", "suggested_temp": 0.1},
        )

        mock_agent = MagicMock()
        mock_registry = MagicMock()
        mock_registry.agents = {"code": mock_agent}

        with patch("src.pattern_agents.PatternAgentRegistry", return_value=mock_registry):
            result = imp._apply_temp_adjust(action)

        assert result is True
        assert mock_agent.temperature == 0.1

    def test_apply_temp_adjust_missing_pattern(self):
        from src.self_improvement import ImprovementAction
        imp = _make_improver()

        action = ImprovementAction(
            "temp_adjust", "nonexistent", "lower temp", "high",
            params={"pattern": "nonexistent", "suggested_temp": 0.1},
        )

        mock_registry = MagicMock()
        mock_registry.agents = {}

        with patch("src.pattern_agents.PatternAgentRegistry", return_value=mock_registry):
            result = imp._apply_temp_adjust(action)

        assert result is False

    def test_apply_tokens_adjust_success(self):
        from src.self_improvement import ImprovementAction
        imp = _make_improver()

        action = ImprovementAction(
            "tokens_adjust", "analysis", "more tokens", "medium",
            params={"pattern": "analysis", "suggested_max_tokens": 4096},
        )

        mock_agent = MagicMock()
        mock_registry = MagicMock()
        mock_registry.agents = {"analysis": mock_agent}

        with patch("src.pattern_agents.PatternAgentRegistry", return_value=mock_registry):
            result = imp._apply_tokens_adjust(action)

        assert result is True
        assert mock_agent.max_tokens == 4096


# ---------------------------------------------------------------------------
# _apply_gate_tune()
# ---------------------------------------------------------------------------

class TestApplyGateTune:
    def test_length_gate_tune(self):
        from src.self_improvement import ImprovementAction
        imp = _make_improver()

        action = ImprovementAction(
            "gate_tune", "simple", "lower length", "medium",
            params={"pattern": "simple", "gate": "length",
                    "suggestion": "lower_threshold"},
        )

        mock_gate = MagicMock()
        mock_gate.config.min_content_length = {"simple": 20}

        with patch("src.quality_gate.get_gate", return_value=mock_gate):
            result = imp._apply_gate_tune(action)

        assert result is True
        assert mock_gate.config.min_content_length["simple"] == 10  # 20 // 2

    def test_latency_gate_tune(self):
        from src.self_improvement import ImprovementAction
        imp = _make_improver()

        action = ImprovementAction(
            "gate_tune", "code", "raise latency", "high",
            params={"pattern": "code", "gate": "latency",
                    "suggestion": "raise_threshold_or_faster_node"},
        )

        mock_gate = MagicMock()
        mock_gate.config.max_latency_ms = {"code": 30000}

        with patch("src.quality_gate.get_gate", return_value=mock_gate):
            result = imp._apply_gate_tune(action)

        assert result is True
        assert mock_gate.config.max_latency_ms["code"] == 45000  # 30000 * 1.5

    def test_gate_tune_fails_on_import_error(self):
        from src.self_improvement import ImprovementAction
        imp = _make_improver()

        action = ImprovementAction(
            "gate_tune", "code", "tune", "medium",
            params={"pattern": "code", "gate": "length",
                    "suggestion": "lower_threshold"},
        )

        with patch.dict("sys.modules", {"src.quality_gate": None}):
            result = imp._apply_gate_tune(action)

        assert result is False


# ---------------------------------------------------------------------------
# _log_action()
# ---------------------------------------------------------------------------

class TestLogAction:
    def test_log_action_inserts_to_db(self):
        from src.self_improvement import ImprovementAction
        imp = _make_improver()

        action = ImprovementAction(
            "route_shift", "M3", "test log", "high",
            params={"from_node": "M3"}, applied=True, result="auto-applied",
        )

        mock_conn = MagicMock()
        with patch("src.self_improvement.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_conn
            imp._log_action(action)

        mock_conn.execute.assert_called_once()
        sql = mock_conn.execute.call_args[0][0]
        assert "INSERT INTO self_improvement_log" in sql
        args = mock_conn.execute.call_args[0][1]
        assert args[0] == "route_shift"
        assert args[1] == "M3"
        assert args[5] == 1  # int(True)
        mock_conn.commit.assert_called_once()

    def test_log_action_swallows_errors(self):
        from src.self_improvement import ImprovementAction
        imp = _make_improver()

        action = ImprovementAction("test", "t", "d", "low")
        with patch("src.self_improvement.sqlite3") as mock_sql:
            mock_sql.connect.side_effect = Exception("fail")
            imp._log_action(action)  # Should not raise


# ---------------------------------------------------------------------------
# get_history() / get_stats()
# ---------------------------------------------------------------------------

class TestGetHistoryAndStats:
    def test_get_history_returns_list_of_dicts(self):
        imp = _make_improver()

        fake_row = {"id": 1, "action_type": "route_shift", "target": "M3",
                    "description": "test", "priority": "high", "params": "{}",
                    "applied": 1, "result": "ok", "timestamp": "2026-03-06"}
        mock_row_obj = MagicMock()
        mock_row_obj.keys.return_value = list(fake_row.keys())
        mock_row_obj.__getitem__ = lambda self, key: fake_row[key]
        # dict(row) needs to work — use a real dict via __iter__
        mock_row_obj.__iter__ = lambda self: iter(fake_row)

        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = [fake_row]

        with patch("src.self_improvement.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_conn
            mock_sql.Row = "Row"
            history = imp.get_history(limit=10)

        assert isinstance(history, list)

    def test_get_history_returns_empty_on_error(self):
        imp = _make_improver()
        with patch("src.self_improvement.sqlite3") as mock_sql:
            mock_sql.connect.side_effect = Exception("fail")
            history = imp.get_history()
        assert history == []

    def test_get_stats_returns_structure(self):
        imp = _make_improver()

        mock_conn = MagicMock()
        execute_calls = [
            MagicMock(fetchone=MagicMock(return_value=(25,))),    # total
            MagicMock(fetchone=MagicMock(return_value=(15,))),    # applied
            MagicMock(fetchall=MagicMock(return_value=[
                ("route_shift", 10, 8),
                ("temp_adjust", 15, 7),
            ])),
        ]
        mock_conn.execute = MagicMock(side_effect=execute_calls)

        with patch("src.self_improvement.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_conn
            stats = imp.get_stats()

        assert stats["total_suggestions"] == 25
        assert stats["total_applied"] == 15
        assert stats["apply_rate"] == 0.6  # 15/25
        assert len(stats["by_type"]) == 2

    def test_get_stats_returns_defaults_on_error(self):
        imp = _make_improver()
        with patch("src.self_improvement.sqlite3") as mock_sql:
            mock_sql.connect.side_effect = Exception("fail")
            stats = imp.get_stats()
        assert stats["total_suggestions"] == 0
        assert stats["total_applied"] == 0


# ---------------------------------------------------------------------------
# get_improver() singleton
# ---------------------------------------------------------------------------

class TestGetImprover:
    def test_returns_same_instance(self):
        import src.self_improvement as mod
        with patch("src.self_improvement.sqlite3"):
            mod._improver = None
            a = mod.get_improver()
            b = mod.get_improver()
        assert a is b

    def test_returns_self_improver_type(self):
        from src.self_improvement import SelfImprover
        import src.self_improvement as mod
        with patch("src.self_improvement.sqlite3"):
            mod._improver = None
            imp = mod.get_improver()
        assert isinstance(imp, SelfImprover)
