"""Tests for src/reflection_engine.py — ReflectionEngine, Insight, get_reflection."""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Helpers — build engine with mocked DB so tests run in isolation
# ---------------------------------------------------------------------------

def _make_engine():
    """Create a ReflectionEngine with sqlite3 mocked out (no real DB access)."""
    with patch("src.reflection_engine.sqlite3") as _mock_sql:
        _mock_sql.connect.return_value = MagicMock()
        from src.reflection_engine import ReflectionEngine
        engine = ReflectionEngine()
    return engine


def _mock_db_with_rows(execute_side_effects):
    """Return a MagicMock db connection that yields specified query results.

    *execute_side_effects* is a list of return values for successive
    db.execute(...).fetchone() / .fetchall() calls.  Each element should
    be a MagicMock whose .fetchone()/.fetchall() is configured.
    """
    mock_db = MagicMock()
    mock_db.execute.side_effect = execute_side_effects
    return mock_db


def _fetchone_result(value):
    """Build a MagicMock cursor whose .fetchone() returns a 1-tuple."""
    cur = MagicMock()
    cur.fetchone.return_value = (value,)
    return cur


def _fetchone_none():
    """Build a cursor whose .fetchone()[0] returns None (empty AVG)."""
    cur = MagicMock()
    cur.fetchone.return_value = (None,)
    return cur


def _fetchall_result(rows):
    """Build a cursor whose .fetchall() returns *rows*."""
    cur = MagicMock()
    cur.fetchall.return_value = rows
    return cur


# ============================================================================
# Insight dataclass
# ============================================================================

class TestInsight:
    def test_basic_creation(self):
        from src.reflection_engine import Insight
        ins = Insight(
            category="quality", severity="info",
            title="test", description="desc",
        )
        assert ins.category == "quality"
        assert ins.severity == "info"
        assert ins.metric_value == 0
        assert ins.recommendation == ""
        assert ins.data == {}

    def test_full_creation(self):
        from src.reflection_engine import Insight
        ins = Insight(
            category="performance", severity="critical",
            title="Slow", description="Very slow",
            metric_value=42.5,
            recommendation="Fix it",
            data={"node": "M1"},
        )
        assert ins.metric_value == 42.5
        assert ins.data["node"] == "M1"


# ============================================================================
# ReflectionEngine.__init__ / _ensure_table
# ============================================================================

class TestEnsureTable:
    def test_creates_table_on_init(self):
        """__init__ calls _ensure_table which runs CREATE TABLE IF NOT EXISTS."""
        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_db = MagicMock()
            mock_sql.connect.return_value = mock_db
            from src.reflection_engine import ReflectionEngine
            engine = ReflectionEngine()
            mock_db.execute.assert_called_once()
            sql_arg = mock_db.execute.call_args[0][0]
            assert "CREATE TABLE IF NOT EXISTS reflection_log" in sql_arg
            mock_db.commit.assert_called_once()
            mock_db.close.assert_called_once()

    def test_ensure_table_exception_swallowed(self):
        """_ensure_table swallows exceptions gracefully."""
        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_sql.connect.side_effect = Exception("DB error")
            from src.reflection_engine import ReflectionEngine
            # Should not raise
            engine = ReflectionEngine()


# ============================================================================
# ReflectionEngine.reflect
# ============================================================================

class TestReflect:
    def test_reflect_empty_db_returns_list(self):
        """With an empty DB (all queries return 0/None), reflect returns a list."""
        engine = _make_engine()
        # Patch all _reflect_* methods to return empty lists
        engine._reflect_quality = MagicMock(return_value=[])
        engine._reflect_performance = MagicMock(return_value=[])
        engine._reflect_reliability = MagicMock(return_value=[])
        engine._reflect_efficiency = MagicMock(return_value=[])
        engine._reflect_growth = MagicMock(return_value=[])
        engine._reflect_benchmark_trend = MagicMock(return_value=[])
        engine._log_insight = MagicMock()

        result = engine.reflect()
        assert isinstance(result, list)
        assert len(result) == 0

    def test_reflect_sorts_by_severity(self):
        """Insights are sorted: critical first, then warning, then info."""
        from src.reflection_engine import Insight
        engine = _make_engine()

        info_insight = Insight("a", "info", "I", "info desc")
        warn_insight = Insight("b", "warning", "W", "warn desc")
        crit_insight = Insight("c", "critical", "C", "crit desc")

        engine._reflect_quality = MagicMock(return_value=[info_insight])
        engine._reflect_performance = MagicMock(return_value=[warn_insight])
        engine._reflect_reliability = MagicMock(return_value=[crit_insight])
        engine._reflect_efficiency = MagicMock(return_value=[])
        engine._reflect_growth = MagicMock(return_value=[])
        engine._reflect_benchmark_trend = MagicMock(return_value=[])
        engine._log_insight = MagicMock()

        result = engine.reflect()
        assert len(result) == 3
        assert result[0].severity == "critical"
        assert result[1].severity == "warning"
        assert result[2].severity == "info"

    def test_reflect_logs_top_10(self):
        """reflect() logs at most 10 insights."""
        from src.reflection_engine import Insight
        engine = _make_engine()

        many = [Insight("g", "info", f"T{i}", f"d{i}") for i in range(15)]
        engine._reflect_quality = MagicMock(return_value=many)
        engine._reflect_performance = MagicMock(return_value=[])
        engine._reflect_reliability = MagicMock(return_value=[])
        engine._reflect_efficiency = MagicMock(return_value=[])
        engine._reflect_growth = MagicMock(return_value=[])
        engine._reflect_benchmark_trend = MagicMock(return_value=[])
        engine._log_insight = MagicMock()

        result = engine.reflect()
        assert len(result) == 15
        assert engine._log_insight.call_count == 10

    def test_reflect_calls_all_sub_methods(self):
        """reflect() invokes every sub-reflection method exactly once."""
        engine = _make_engine()
        for name in ("_reflect_quality", "_reflect_performance",
                      "_reflect_reliability", "_reflect_efficiency",
                      "_reflect_growth", "_reflect_benchmark_trend"):
            setattr(engine, name, MagicMock(return_value=[]))
        engine._log_insight = MagicMock()

        engine.reflect()
        for name in ("_reflect_quality", "_reflect_performance",
                      "_reflect_reliability", "_reflect_efficiency",
                      "_reflect_growth", "_reflect_benchmark_trend"):
            getattr(engine, name).assert_called_once()


# ============================================================================
# _reflect_quality
# ============================================================================

class TestReflectQuality:
    def test_quality_improvement(self):
        """Detects quality improvement when recent > older * 1.1."""
        engine = _make_engine()
        # Build a row-factory-enabled mock
        mock_db = MagicMock()
        mock_db.execute.side_effect = [
            _fetchone_result(0.9),   # recent_q
            _fetchone_result(0.5),   # older_q
            _fetchall_result([]),     # worst patterns
        ]
        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            mock_sql.Row = "row_sentinel"
            insights = engine._reflect_quality()

        assert len(insights) >= 1
        assert any(i.title == "Quality improvement detected" for i in insights)

    def test_quality_degradation(self):
        """Detects quality degradation when recent < older * 0.8."""
        engine = _make_engine()
        mock_db = MagicMock()
        mock_db.execute.side_effect = [
            _fetchone_result(0.3),   # recent_q (< 0.5 * 0.8 = 0.4)
            _fetchone_result(0.5),   # older_q
            _fetchall_result([]),     # worst patterns
        ]
        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            mock_sql.Row = "row_sentinel"
            insights = engine._reflect_quality()

        assert len(insights) >= 1
        assert any(i.title == "Quality degradation detected" for i in insights)

    def test_quality_stable_no_insight(self):
        """No quality insight when recent and older are close."""
        engine = _make_engine()
        mock_db = MagicMock()
        mock_db.execute.side_effect = [
            _fetchone_result(0.5),   # recent_q
            _fetchone_result(0.5),   # older_q (same = no trigger)
            _fetchall_result([]),     # worst patterns
        ]
        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            mock_sql.Row = "row_sentinel"
            insights = engine._reflect_quality()

        # No improvement/degradation insight
        assert not any("improvement" in i.title.lower() or "degradation" in i.title.lower()
                       for i in insights)

    def test_low_quality_pattern(self):
        """Detects low quality patterns (avg < 0.4)."""
        engine = _make_engine()
        mock_db = MagicMock()
        row = {"pattern": "code_gen", "q": 0.2, "n": 10}
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: row[key]
        mock_db.execute.side_effect = [
            _fetchone_result(0.0),   # recent_q (0 => no trend insight)
            _fetchone_result(0.0),   # older_q
            _fetchall_result([mock_row]),
        ]
        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            mock_sql.Row = "row_sentinel"
            insights = engine._reflect_quality()

        assert any("Low quality pattern" in i.title for i in insights)

    def test_quality_db_error_returns_empty(self):
        """DB errors in _reflect_quality are swallowed, returns []."""
        engine = _make_engine()
        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_sql.connect.side_effect = Exception("DB gone")
            insights = engine._reflect_quality()
        assert insights == []

    def test_quality_null_values(self):
        """Handles NULL AVG results from DB (empty table)."""
        engine = _make_engine()
        mock_db = MagicMock()
        mock_db.execute.side_effect = [
            _fetchone_none(),       # recent_q = None -> 0
            _fetchone_none(),       # older_q = None -> 0
            _fetchall_result([]),   # worst patterns
        ]
        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            mock_sql.Row = "row_sentinel"
            insights = engine._reflect_quality()

        # With both 0, no trend insight is generated (0 and 0 fail the `if recent_q and older_q` check)
        assert insights == []


# ============================================================================
# _reflect_performance
# ============================================================================

class TestReflectPerformance:
    def test_high_latency_warning(self):
        """Generates warning when avg pipeline > 30000ms."""
        engine = _make_engine()
        mock_db = MagicMock()
        mock_db.execute.side_effect = [
            _fetchone_result(35000),  # avg_pipe
            _fetchall_result([]),     # slow_nodes
        ]
        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            insights = engine._reflect_performance()

        assert any("High average pipeline latency" in i.title for i in insights)
        assert insights[0].severity == "warning"

    def test_excellent_performance(self):
        """Generates info when avg pipeline < 5000ms."""
        engine = _make_engine()
        mock_db = MagicMock()
        mock_db.execute.side_effect = [
            _fetchone_result(3000),  # avg_pipe
            _fetchall_result([]),    # slow_nodes
        ]
        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            insights = engine._reflect_performance()

        assert any("Excellent pipeline performance" in i.title for i in insights)

    def test_slow_node_detection(self):
        """Detects individual slow nodes (>20000ms avg)."""
        engine = _make_engine()
        mock_db = MagicMock()
        mock_db.execute.side_effect = [
            _fetchone_result(10000),                    # avg_pipe (mid-range, no global insight)
            _fetchall_result([("M3", 25000, 5)]),       # slow_nodes: node, lat, n
        ]
        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            insights = engine._reflect_performance()

        assert any("Slow node: M3" in i.title for i in insights)

    def test_performance_db_error(self):
        """DB errors in _reflect_performance are swallowed."""
        engine = _make_engine()
        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_sql.connect.side_effect = Exception("DB error")
            insights = engine._reflect_performance()
        assert insights == []

    def test_no_data_no_insight(self):
        """With avg_pipe = 0 (NULL), no performance insight."""
        engine = _make_engine()
        mock_db = MagicMock()
        mock_db.execute.side_effect = [
            _fetchone_none(),        # avg_pipe = None -> 0
            _fetchall_result([]),    # slow_nodes
        ]
        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            insights = engine._reflect_performance()
        # avg_pipe == 0, doesn't match >30000 or (>0 and <5000)
        assert insights == []


# ============================================================================
# _reflect_reliability
# ============================================================================

class TestReflectReliability:
    def test_low_success_rate_critical(self):
        """Success rate < 80% with >20 dispatches triggers critical."""
        engine = _make_engine()
        mock_db = MagicMock()
        mock_db.execute.side_effect = [
            _fetchone_result(100),   # total
            _fetchone_result(60),    # ok (60% < 80%)
            _fetchone_result(5),     # fallback count
        ]
        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            insights = engine._reflect_reliability()

        assert any(i.severity == "critical" and "Low overall success rate" in i.title
                    for i in insights)

    def test_excellent_reliability(self):
        """Success rate >= 95% with >20 dispatches triggers info."""
        engine = _make_engine()
        mock_db = MagicMock()
        mock_db.execute.side_effect = [
            _fetchone_result(100),   # total
            _fetchone_result(97),    # ok (97%)
            _fetchone_result(2),     # fallback count (2%)
        ]
        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            insights = engine._reflect_reliability()

        assert any("Excellent reliability" in i.title for i in insights)

    def test_high_fallback_rate(self):
        """Fallback rate > 20% triggers warning."""
        engine = _make_engine()
        mock_db = MagicMock()
        mock_db.execute.side_effect = [
            _fetchone_result(100),   # total
            _fetchone_result(85),    # ok (85%, no critical but not excellent)
            _fetchone_result(30),    # fallback count (30% > 20%)
        ]
        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            insights = engine._reflect_reliability()

        assert any("High fallback rate" in i.title for i in insights)

    def test_too_few_dispatches_no_insight(self):
        """With total <= 20, no reliability insight is generated."""
        engine = _make_engine()
        mock_db = MagicMock()
        mock_db.execute.side_effect = [
            _fetchone_result(10),    # total (<=20)
            _fetchone_result(5),     # ok
            _fetchone_result(1),     # fallback
        ]
        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            insights = engine._reflect_reliability()

        # Neither low nor excellent check triggers with total <= 20
        assert not any("success rate" in i.title.lower() for i in insights)


# ============================================================================
# _reflect_efficiency
# ============================================================================

class TestReflectEfficiency:
    def test_over_reliance_warning(self):
        """Over-reliance (>80%) on single node triggers warning."""
        engine = _make_engine()
        mock_db = MagicMock()
        mock_db.execute.side_effect = [
            _fetchall_result([("M1", 90), ("OL1", 10)]),   # node_usage
            _fetchone_result(5),                             # enriched
        ]
        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            insights = engine._reflect_efficiency()

        assert any("Over-reliance" in i.title for i in insights)

    def test_low_enrichment(self):
        """Low enrichment rate (<10%) triggers info."""
        engine = _make_engine()
        mock_db = MagicMock()
        mock_db.execute.side_effect = [
            _fetchall_result([("M1", 15), ("OL1", 10)]),   # node_usage (total=25)
            _fetchone_result(1),                             # enriched (1/25 = 4%)
        ]
        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            insights = engine._reflect_efficiency()

        assert any("Low memory enrichment" in i.title for i in insights)

    def test_no_node_usage_no_insight(self):
        """Empty node usage produces no insights."""
        engine = _make_engine()
        mock_db = MagicMock()
        mock_db.execute.side_effect = [
            _fetchall_result([]),    # node_usage empty
            _fetchone_result(0),     # enriched
        ]
        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            insights = engine._reflect_efficiency()

        assert insights == []


# ============================================================================
# _reflect_growth
# ============================================================================

class TestReflectGrowth:
    def test_system_scale_always_present(self):
        """Growth reflection always produces a 'System scale' insight."""
        engine = _make_engine()
        mock_db = MagicMock()
        mock_db.execute.side_effect = [
            _fetchone_result(50),    # total_patterns
            _fetchone_result(200),   # total_dispatches
            _fetchone_result(5),     # unique_recent
        ]
        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            insights = engine._reflect_growth()

        assert any("System scale" in i.title for i in insights)
        scale = [i for i in insights if "System scale" in i.title][0]
        assert "50 patterns" in scale.description
        assert "200 dispatches" in scale.description

    def test_many_unused_patterns(self):
        """Detects when <20% of patterns are used recently."""
        engine = _make_engine()
        mock_db = MagicMock()
        mock_db.execute.side_effect = [
            _fetchone_result(100),   # total_patterns
            _fetchone_result(500),   # total_dispatches
            _fetchone_result(10),    # unique_recent (10/100 = 10%)
        ]
        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            insights = engine._reflect_growth()

        assert any("unused patterns" in i.title.lower() for i in insights)

    def test_growth_db_error(self):
        """DB error in _reflect_growth is swallowed."""
        engine = _make_engine()
        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_sql.connect.side_effect = Exception("DB error")
            insights = engine._reflect_growth()
        assert insights == []


# ============================================================================
# _reflect_benchmark_trend
# ============================================================================

class TestReflectBenchmarkTrend:
    def test_benchmark_reached(self):
        """Latest benchmark >= 80% triggers info."""
        engine = _make_engine()
        mock_db = MagicMock()
        rows = [(0.85, 10, "2026-01-01")]
        mock_db.execute.return_value = _fetchall_result(rows).fetchall.return_value and MagicMock()
        mock_db.execute.return_value.fetchall.return_value = rows
        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            insights = engine._reflect_benchmark_trend()

        assert any("Benchmark target reached" in i.title for i in insights)

    def test_benchmark_critically_low(self):
        """Latest benchmark < 60% triggers critical."""
        engine = _make_engine()
        mock_db = MagicMock()
        rows = [(0.45, 10, "2026-01-01")]
        mock_db.execute.return_value.fetchall.return_value = rows
        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            insights = engine._reflect_benchmark_trend()

        assert any("Benchmark critically low" in i.title for i in insights)
        assert any(i.severity == "critical" for i in insights)

    def test_benchmark_improving_trend(self):
        """Detects improving trend over 3+ runs (first - last > 0.1)."""
        engine = _make_engine()
        mock_db = MagicMock()
        # rows[0] = latest, rows[-1] = oldest => trend = 0.9 - 0.6 = 0.3
        rows = [(0.9, 10, "t3"), (0.8, 10, "t2"), (0.6, 10, "t1")]
        mock_db.execute.return_value.fetchall.return_value = rows
        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            insights = engine._reflect_benchmark_trend()

        assert any("Benchmark improving" in i.title for i in insights)

    def test_benchmark_declining_trend(self):
        """Detects declining trend (first - last < -0.1)."""
        engine = _make_engine()
        mock_db = MagicMock()
        rows = [(0.5, 10, "t3"), (0.7, 10, "t2"), (0.8, 10, "t1")]
        mock_db.execute.return_value.fetchall.return_value = rows
        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            insights = engine._reflect_benchmark_trend()

        assert any("Benchmark declining" in i.title for i in insights)

    def test_no_benchmark_data(self):
        """No benchmark rows => no insights."""
        engine = _make_engine()
        mock_db = MagicMock()
        mock_db.execute.return_value.fetchall.return_value = []
        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            insights = engine._reflect_benchmark_trend()

        assert insights == []

    def test_benchmark_db_error(self):
        """DB error is swallowed."""
        engine = _make_engine()
        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_sql.connect.side_effect = Exception("DB error")
            insights = engine._reflect_benchmark_trend()
        assert insights == []


# ============================================================================
# timeline_analysis
# ============================================================================

class TestTimelineAnalysis:
    def test_no_data_in_period(self):
        """Returns 'No data in period' message when no rows match."""
        engine = _make_engine()
        mock_db = MagicMock()
        mock_db.execute.return_value.fetchall.return_value = []
        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            mock_sql.Row = "row_sentinel"
            result = engine.timeline_analysis(hours=24)

        assert result["dispatches"] == 0
        assert result["message"] == "No data in period"
        assert result["period_hours"] == 24

    def test_with_data(self):
        """Returns computed stats when data is present."""
        engine = _make_engine()
        mock_db = MagicMock()

        row1 = {
            "pattern": "code", "node": "M1", "quality": 0.8,
            "latency_ms": 1000, "pipeline_ms": 2000,
            "success": True, "fallback_used": False, "enriched": True,
            "timestamp": "2026-01-01 12:00:00",
        }
        row2 = {
            "pattern": "simple", "node": "OL1", "quality": 0.6,
            "latency_ms": 500, "pipeline_ms": 1000,
            "success": True, "fallback_used": True, "enriched": False,
            "timestamp": "2026-01-01 13:00:00",
        }

        mock_row1 = MagicMock()
        mock_row1.__getitem__ = lambda self, key: row1[key]
        mock_row2 = MagicMock()
        mock_row2.__getitem__ = lambda self, key: row2[key]

        mock_db.execute.return_value.fetchall.return_value = [mock_row1, mock_row2]

        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            mock_sql.Row = "row_sentinel"
            result = engine.timeline_analysis(hours=48)

        assert result["period_hours"] == 48
        assert result["dispatches"] == 2
        assert result["success_rate"] == 1.0
        assert result["avg_quality"] == round((0.8 + 0.6) / 2, 3)
        assert result["avg_latency_ms"] == round((1000 + 500) / 2, 0)
        assert result["avg_pipeline_ms"] == round((2000 + 1000) / 2, 0)
        assert result["fallback_rate"] == 0.5
        assert result["enrichment_rate"] == 0.5
        assert set(result["patterns_used"]) == {"code", "simple"}
        assert set(result["nodes_used"]) == {"M1", "OL1"}

    def test_with_null_quality_and_latency(self):
        """Rows with None quality/latency are excluded from averages."""
        engine = _make_engine()
        mock_db = MagicMock()

        row1 = {
            "pattern": "code", "node": "M1", "quality": None,
            "latency_ms": None, "pipeline_ms": None,
            "success": False, "fallback_used": False, "enriched": False,
            "timestamp": "2026-01-01 12:00:00",
        }
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: row1[key]
        mock_db.execute.return_value.fetchall.return_value = [mock_row]

        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            mock_sql.Row = "row_sentinel"
            result = engine.timeline_analysis(hours=24)

        assert result["dispatches"] == 1
        assert result["avg_quality"] == 0
        assert result["avg_latency_ms"] == 0
        assert result["avg_pipeline_ms"] == 0
        assert result["success_rate"] == 0.0

    def test_db_error_returns_error_dict(self):
        """DB errors return a dict with 'error' key."""
        engine = _make_engine()
        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_sql.connect.side_effect = Exception("Connection refused")
            result = engine.timeline_analysis(hours=24)

        assert "error" in result
        assert "Connection refused" in result["error"]

    def test_custom_hours(self):
        """Verifies hours parameter is passed to the SQL query."""
        engine = _make_engine()
        mock_db = MagicMock()
        mock_db.execute.return_value.fetchall.return_value = []
        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            mock_sql.Row = "row_sentinel"
            result = engine.timeline_analysis(hours=168)

        assert result["period_hours"] == 168
        # Verify the SQL parameter
        call_args = mock_db.execute.call_args
        assert "-168 hours" in call_args[0][1][0]


# ============================================================================
# get_summary
# ============================================================================

class TestGetSummary:
    def test_full_summary(self):
        """Returns all expected keys with properly computed values."""
        engine = _make_engine()
        mock_db = MagicMock()
        mock_db.execute.side_effect = [
            _fetchone_result(100),   # total pipeline dispatches
            _fetchone_result(90),    # ok (success)
            _fetchone_result(0.85),  # avg quality
            _fetchone_result(50),    # agent_patterns count
            _fetchone_result(200),   # agent_dispatch_log count
            _fetchone_result(80),    # gate total
            _fetchone_result(70),    # gate pass
            _fetchone_result(10),    # imp total
            _fetchone_result(7),     # imp applied
        ]
        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            result = engine.get_summary()

        assert result["total_pipeline_dispatches"] == 100
        assert result["success_rate"] == 0.9
        assert result["avg_quality"] == 0.85
        assert result["total_patterns"] == 50
        assert result["total_dispatches"] == 200
        assert result["gate_pass_rate"] == round(70 / 80, 3)
        assert result["improvements_applied"] == 7
        assert result["improvements_total"] == 10
        # system_health = min(100, (90/100)*50 + 0.85*50) = min(100, 45 + 42.5) = 87.5
        assert result["system_health"] == 87.5

    def test_summary_empty_db(self):
        """Empty DB (all zeros) returns valid summary."""
        engine = _make_engine()
        mock_db = MagicMock()
        mock_db.execute.side_effect = [
            _fetchone_result(0),     # total
            _fetchone_result(0),     # ok
            _fetchone_none(),        # avg quality (NULL -> 0)
            _fetchone_result(0),     # patterns
            _fetchone_result(0),     # dispatches
            _fetchone_result(0),     # gate total
            _fetchone_result(0),     # gate pass
            _fetchone_result(0),     # imp total
            _fetchone_result(0),     # imp applied
        ]
        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            result = engine.get_summary()

        assert result["total_pipeline_dispatches"] == 0
        assert result["success_rate"] == 0.0
        assert result["avg_quality"] == 0
        assert result["system_health"] == 0.0

    def test_summary_self_improvement_table_missing(self):
        """If self_improvement_log table doesn't exist, defaults to 0."""
        engine = _make_engine()
        mock_db = MagicMock()
        call_count = [0]

        def side_effect_fn(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 7:
                # First 7 calls succeed: total, ok, avg_q, patterns, dispatches, gate_total, gate_pass
                values = [100, 90, 0.85, 50, 200, 80, 70]
                return _fetchone_result(values[call_count[0] - 1])
            else:
                # self_improvement_log queries fail
                raise Exception("no such table: self_improvement_log")

        mock_db.execute.side_effect = side_effect_fn
        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            result = engine.get_summary()

        assert result["improvements_applied"] == 0
        assert result["improvements_total"] == 0

    def test_summary_db_error(self):
        """Total DB failure returns error dict."""
        engine = _make_engine()
        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_sql.connect.side_effect = Exception("DB locked")
            result = engine.get_summary()

        assert "error" in result
        assert "DB locked" in result["error"]


# ============================================================================
# get_stats
# ============================================================================

class TestGetStats:
    def test_stats_with_data(self):
        """Returns total, by_severity, and by_category dicts."""
        engine = _make_engine()
        mock_db = MagicMock()
        mock_db.execute.side_effect = [
            _fetchone_result(25),                                          # total
            _fetchall_result([("info", 15), ("warning", 8), ("critical", 2)]),  # by_severity
            _fetchall_result([("quality", 10), ("performance", 8), ("growth", 7)]),  # by_category
        ]
        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            result = engine.get_stats()

        assert result["total_insights"] == 25
        assert result["by_severity"] == {"info": 15, "warning": 8, "critical": 2}
        assert result["by_category"] == {"quality": 10, "performance": 8, "growth": 7}

    def test_stats_empty_db(self):
        """Empty reflection_log returns 0 total and empty dicts."""
        engine = _make_engine()
        mock_db = MagicMock()
        mock_db.execute.side_effect = [
            _fetchone_result(0),     # total
            _fetchall_result([]),     # by_severity
            _fetchall_result([]),     # by_category
        ]
        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            result = engine.get_stats()

        assert result["total_insights"] == 0
        assert result["by_severity"] == {}
        assert result["by_category"] == {}

    def test_stats_db_error(self):
        """DB error returns fallback dict with total_insights=0."""
        engine = _make_engine()
        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_sql.connect.side_effect = Exception("DB error")
            result = engine.get_stats()

        assert result == {"total_insights": 0}


# ============================================================================
# _log_insight
# ============================================================================

class TestLogInsight:
    def test_logs_to_db(self):
        """_log_insight inserts into reflection_log."""
        from src.reflection_engine import Insight
        engine = _make_engine()
        ins = Insight("quality", "info", "Test Title", "desc",
                      metric_value=0.9, recommendation="Keep going")

        mock_db = MagicMock()
        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            engine._log_insight(ins)

        mock_db.execute.assert_called_once()
        args = mock_db.execute.call_args[0]
        assert "INSERT INTO reflection_log" in args[0]
        assert args[1] == ("quality", "info", "Test Title", 0.9, "Keep going")
        mock_db.commit.assert_called_once()
        mock_db.close.assert_called_once()

    def test_log_insight_db_error_swallowed(self):
        """DB error during logging is silently swallowed."""
        from src.reflection_engine import Insight
        engine = _make_engine()
        ins = Insight("quality", "info", "Title", "desc")

        with patch("src.reflection_engine.sqlite3") as mock_sql:
            mock_sql.connect.side_effect = Exception("DB error")
            # Should not raise
            engine._log_insight(ins)


# ============================================================================
# get_reflection (module-level singleton)
# ============================================================================

class TestGetReflection:
    def test_returns_engine(self):
        """get_reflection() returns a ReflectionEngine instance."""
        import src.reflection_engine as mod
        with patch.object(mod, "sqlite3"):
            # Reset the singleton
            mod._reflection = None
            engine = mod.get_reflection()
            assert isinstance(engine, mod.ReflectionEngine)

    def test_singleton_pattern(self):
        """get_reflection() returns the same instance on repeated calls."""
        import src.reflection_engine as mod
        with patch.object(mod, "sqlite3"):
            mod._reflection = None
            e1 = mod.get_reflection()
            e2 = mod.get_reflection()
            assert e1 is e2

    def test_resets_with_none(self):
        """Setting _reflection to None creates a fresh instance."""
        import src.reflection_engine as mod
        with patch.object(mod, "sqlite3"):
            mod._reflection = None
            e1 = mod.get_reflection()
            mod._reflection = None
            e2 = mod.get_reflection()
            assert e1 is not e2
