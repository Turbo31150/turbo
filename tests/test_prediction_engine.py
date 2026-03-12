"""Tests for JARVIS Prediction Engine — src/prediction_engine.py

Comprehensive tests covering:
- Module imports and constants
- PredictionEngine initialization
- record_action (recording user actions)
- predict_next (weighted scoring, caching, edge cases)
- pre_warm (async pre-execution)
- get_user_profile (profile deduction)
- get_stats (statistics)
- cleanup (old pattern removal)
- Error handling and edge cases
"""

import sys
import json
import time
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch, call

import pytest

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# We must mock sqlite3.connect BEFORE importing the module, because
# prediction_engine.py creates a global singleton that calls _init_db()
# on import, which would try to connect to the real database.
# ---------------------------------------------------------------------------

_mock_connection = MagicMock()
_mock_connection.__enter__ = MagicMock(return_value=_mock_connection)
_mock_connection.__exit__ = MagicMock(return_value=False)
_mock_connection.executescript = MagicMock()
_mock_connection.execute = MagicMock()

_connect_patcher = patch("sqlite3.connect", return_value=_mock_connection)
_connect_patcher.start()

from src.prediction_engine import (
    PredictionEngine,
    prediction_engine,
    DB_PATH,
    CREATE_TABLE_SQL,
    CREATE_INDEX_SQL,
)

_connect_patcher.stop()


# ---------------------------------------------------------------------------
# Helper to build a fresh PredictionEngine with a mocked DB
# ---------------------------------------------------------------------------

def _make_engine():
    """Create a PredictionEngine with a fully mocked sqlite3 layer."""
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.executescript = MagicMock()
    mock_conn.execute = MagicMock()

    with patch("src.prediction_engine.sqlite3.connect", return_value=mock_conn):
        engine = PredictionEngine(db_path="/tmp/fake_test.db")

    # Replace _conn so all subsequent calls use the mock
    engine._conn = MagicMock(return_value=mock_conn)
    return engine, mock_conn


# ===========================================================================
# Test: Module-level imports and constants
# ===========================================================================

class TestModuleImports:
    """Verify that the module exposes expected symbols."""

    def test_prediction_engine_class_exists(self):
        assert PredictionEngine is not None

    def test_global_singleton_exists(self):
        assert prediction_engine is not None
        assert isinstance(prediction_engine, PredictionEngine)

    def test_db_path_is_pathlib(self):
        assert isinstance(DB_PATH, Path)
        assert "etoile.db" in str(DB_PATH)

    def test_create_table_sql_content(self):
        assert "user_patterns" in CREATE_TABLE_SQL
        assert "CREATE TABLE IF NOT EXISTS" in CREATE_TABLE_SQL

    def test_create_index_sql_content(self):
        assert "idx_patterns_hour_weekday" in CREATE_INDEX_SQL
        assert "idx_patterns_action" in CREATE_INDEX_SQL


# ===========================================================================
# Test: Initialization
# ===========================================================================

class TestInit:
    """Verify constructor and _init_db behavior."""

    def test_custom_db_path(self):
        engine, _ = _make_engine()
        assert engine._db_path == Path("/tmp/fake_test.db")

    def test_default_db_path(self):
        with patch("src.prediction_engine.sqlite3.connect", return_value=_mock_connection):
            engine = PredictionEngine()
        assert engine._db_path == DB_PATH

    def test_init_creates_table(self):
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.executescript = MagicMock()

        with patch("src.prediction_engine.sqlite3.connect", return_value=mock_conn):
            PredictionEngine(db_path="/tmp/init_test.db")

        mock_conn.executescript.assert_called_once()
        script_arg = mock_conn.executescript.call_args[0][0]
        assert "user_patterns" in script_arg

    def test_init_db_failure_logged_not_raised(self):
        with patch("src.prediction_engine.sqlite3.connect", side_effect=Exception("disk error")):
            # Should NOT raise — error is caught and logged
            engine = PredictionEngine(db_path="/tmp/broken.db")
        assert engine._db_path == Path("/tmp/broken.db")

    def test_cache_starts_empty(self):
        engine, _ = _make_engine()
        assert engine._cache == {}
        assert engine._cache_ts == 0
        assert engine._cache_ttl == 300.0


# ===========================================================================
# Test: record_action
# ===========================================================================

class TestRecordAction:
    """Verify action recording and cache invalidation."""

    def test_record_action_inserts_row(self):
        engine, mock_conn = _make_engine()

        with patch("src.prediction_engine.datetime") as mock_dt, \
             patch("src.prediction_engine.time") as mock_time:
            mock_now = MagicMock()
            mock_now.hour = 14
            mock_now.weekday.return_value = 2
            mock_dt.now.return_value = mock_now
            mock_time.time.return_value = 1700000000.0

            engine.record_action("trading_scan", {"source": "voice"})

        mock_conn.execute.assert_called_once()
        args = mock_conn.execute.call_args
        sql = args[0][0]
        params = args[0][1]
        assert "INSERT INTO user_patterns" in sql
        assert params[0] == "trading_scan"
        assert params[1] == 14   # hour
        assert params[2] == 2    # weekday
        assert '"source": "voice"' in params[3]  # context JSON

    def test_record_action_none_context(self):
        engine, mock_conn = _make_engine()

        with patch("src.prediction_engine.datetime") as mock_dt, \
             patch("src.prediction_engine.time") as mock_time:
            mock_now = MagicMock()
            mock_now.hour = 8
            mock_now.weekday.return_value = 0
            mock_dt.now.return_value = mock_now
            mock_time.time.return_value = 1700000001.0

            engine.record_action("health_check")

        params = mock_conn.execute.call_args[0][1]
        assert params[3] == "{}"  # empty context

    def test_record_action_invalidates_cache(self):
        engine, _ = _make_engine()
        engine._cache_ts = 9999999999.0  # future timestamp = cache valid

        with patch("src.prediction_engine.datetime") as mock_dt, \
             patch("src.prediction_engine.time"):
            mock_now = MagicMock()
            mock_now.hour = 10
            mock_now.weekday.return_value = 3
            mock_dt.now.return_value = mock_now
            engine.record_action("test_action")

        assert engine._cache_ts == 0  # cache invalidated

    def test_record_action_db_error_does_not_raise(self):
        engine, mock_conn = _make_engine()
        mock_conn.execute.side_effect = Exception("DB write error")

        with patch("src.prediction_engine.datetime") as mock_dt:
            mock_now = MagicMock()
            mock_now.hour = 12
            mock_now.weekday.return_value = 4
            mock_dt.now.return_value = mock_now
            # Should not raise
            engine.record_action("failing_action")


# ===========================================================================
# Test: predict_next
# ===========================================================================

class TestPredictNext:
    """Verify prediction logic, scoring weights, caching, and edge cases."""

    def _setup_query_results(self, mock_conn, exact, hourly, adjacent):
        """Configure mock_conn.execute to return different results per query."""
        # Each row must behave like sqlite3.Row with dict-like access
        def make_rows(data):
            rows = []
            for action, cnt in data:
                row = MagicMock()
                row.__getitem__ = lambda self, key, a=action, c=cnt: a if key == "action" else c
                rows.append(row)
            return rows

        call_count = {"n": 0}
        results = [make_rows(exact), make_rows(hourly), make_rows(adjacent)]

        def execute_side_effect(sql, params=None):
            cursor = MagicMock()
            cursor.fetchall.return_value = results[call_count["n"]]
            call_count["n"] += 1
            return cursor

        mock_conn.execute = execute_side_effect

    def test_predict_next_weighted_scoring(self):
        engine, mock_conn = _make_engine()
        mock_conn.row_factory = None

        self._setup_query_results(
            mock_conn,
            exact=[("trading_scan", 10)],   # score: 10 * 3.0 = 30
            hourly=[("trading_scan", 5), ("health_check", 8)],  # 5*1.5=7.5 / 8*1.5=12
            adjacent=[("trading_scan", 2)],  # 2 * 0.5 = 1
        )

        with patch("src.prediction_engine.time") as mock_time:
            mock_time.time.return_value = 0  # force cache miss
            predictions = engine.predict_next(n=5, hour=14, weekday=2)

        assert len(predictions) >= 1
        # trading_scan: 30 + 7.5 + 1 = 38.5 should be top
        assert predictions[0]["action"] == "trading_scan"
        assert predictions[0]["score"] == 38.5
        assert predictions[0]["confidence"] == 1.0  # max score = 1.0

    def test_predict_next_returns_n_results(self):
        engine, mock_conn = _make_engine()
        mock_conn.row_factory = None

        self._setup_query_results(
            mock_conn,
            exact=[("a", 10), ("b", 8), ("c", 5)],
            hourly=[],
            adjacent=[],
        )

        with patch("src.prediction_engine.time") as mock_time:
            mock_time.time.return_value = 0
            result = engine.predict_next(n=2, hour=10, weekday=1)

        assert len(result) == 2
        assert result[0]["action"] == "a"
        assert result[1]["action"] == "b"

    def test_predict_next_empty_db(self):
        engine, mock_conn = _make_engine()
        mock_conn.row_factory = None

        self._setup_query_results(mock_conn, exact=[], hourly=[], adjacent=[])

        with patch("src.prediction_engine.time") as mock_time:
            mock_time.time.return_value = 0
            result = engine.predict_next(n=3, hour=5, weekday=0)

        assert result == []

    def test_predict_next_uses_cache(self):
        engine, mock_conn = _make_engine()
        engine._cache = {"14_2": [
            {"action": "cached_action", "confidence": 0.9, "score": 10.0, "reason": "hour=14 weekday=2"},
        ]}
        engine._cache_ts = time.time() + 9999  # far future = cache valid
        engine._cache_ttl = 300.0

        with patch("src.prediction_engine.time") as mock_time:
            mock_time.time.return_value = time.time()
            result = engine.predict_next(n=3, hour=14, weekday=2)

        assert len(result) == 1
        assert result[0]["action"] == "cached_action"
        # DB should NOT have been queried
        mock_conn.execute.assert_not_called()

    def test_predict_next_reason_format(self):
        engine, mock_conn = _make_engine()
        mock_conn.row_factory = None

        self._setup_query_results(
            mock_conn,
            exact=[("action_x", 3)],
            hourly=[],
            adjacent=[],
        )

        with patch("src.prediction_engine.time") as mock_time:
            mock_time.time.return_value = 0
            result = engine.predict_next(n=1, hour=22, weekday=6)

        assert result[0]["reason"] == "hour=22 weekday=6"

    def test_predict_next_db_error_returns_empty(self):
        engine, mock_conn = _make_engine()
        # Make _conn() return a context manager that raises on execute
        failing_conn = MagicMock()
        failing_conn.__enter__ = MagicMock(return_value=failing_conn)
        failing_conn.__exit__ = MagicMock(return_value=False)
        failing_conn.execute = MagicMock(side_effect=Exception("DB read error"))
        engine._conn = MagicMock(return_value=failing_conn)

        with patch("src.prediction_engine.time") as mock_time:
            mock_time.time.return_value = 0
            result = engine.predict_next(n=3, hour=10, weekday=1)

        assert result == []

    def test_predict_next_adjacent_hour_wrapping(self):
        """Hour 0 should query adjacent hours 23 and 1."""
        engine, mock_conn = _make_engine()
        mock_conn.row_factory = None

        call_params = []
        call_idx = {"n": 0}

        def capture_execute(sql, params=None):
            call_params.append(params)
            cursor = MagicMock()
            cursor.fetchall.return_value = []
            return cursor

        mock_conn.execute = capture_execute

        with patch("src.prediction_engine.time") as mock_time:
            mock_time.time.return_value = 0
            engine.predict_next(n=3, hour=0, weekday=0)

        # Third call is the adjacent hours query
        assert len(call_params) == 3
        adj_params = call_params[2]
        assert adj_params == (23, 1)  # (0-1)%24=23, (0+1)%24=1

    def test_predict_next_confidence_normalization(self):
        engine, mock_conn = _make_engine()
        mock_conn.row_factory = None

        self._setup_query_results(
            mock_conn,
            exact=[("top", 10), ("mid", 5)],
            hourly=[],
            adjacent=[],
        )

        with patch("src.prediction_engine.time") as mock_time:
            mock_time.time.return_value = 0
            result = engine.predict_next(n=5, hour=12, weekday=3)

        # top: 30/30 = 1.0, mid: 15/30 = 0.5
        assert result[0]["confidence"] == 1.0
        assert result[1]["confidence"] == 0.5

    def test_predict_next_uses_current_time_when_no_args(self):
        engine, mock_conn = _make_engine()
        mock_conn.row_factory = None

        call_params = []

        def capture_execute(sql, params=None):
            call_params.append(params)
            cursor = MagicMock()
            cursor.fetchall.return_value = []
            return cursor

        mock_conn.execute = capture_execute

        with patch("src.prediction_engine.datetime") as mock_dt, \
             patch("src.prediction_engine.time") as mock_time:
            mock_now = MagicMock()
            mock_now.hour = 17
            mock_now.weekday.return_value = 4
            mock_dt.now.return_value = mock_now
            mock_time.time.return_value = 0
            engine.predict_next(n=1)

        # First call: exact match query (hour=17, weekday=4)
        assert call_params[0] == (17, 4)


# ===========================================================================
# Test: pre_warm (async)
# ===========================================================================

class TestPreWarm:
    """Verify async pre-warming logic."""

    @pytest.mark.asyncio
    async def test_pre_warm_returns_dict(self):
        engine, _ = _make_engine()
        engine.predict_next = MagicMock(return_value=[])

        result = await engine.pre_warm()
        assert "predictions" in result
        assert "warmed" in result
        assert result["predictions"] == 0
        assert result["warmed"] == []

    @pytest.mark.asyncio
    async def test_pre_warm_skips_low_confidence(self):
        engine, _ = _make_engine()
        engine.predict_next = MagicMock(return_value=[
            {"action": "health_check", "confidence": 0.3, "score": 5.0, "reason": "h=10 wd=1"},
        ])

        result = await engine.pre_warm()
        # confidence 0.3 < 0.6 threshold, so nothing warmed
        assert result["warmed"] == []

    @pytest.mark.asyncio
    async def test_pre_warm_trading_action_passes(self):
        engine, _ = _make_engine()
        engine.predict_next = MagicMock(return_value=[
            {"action": "trading_scan", "confidence": 0.9, "score": 30.0, "reason": "h=10 wd=1"},
        ])

        result = await engine.pre_warm()
        # trading_scan is handled by a pass statement, so not appended to warmed
        assert "trading_scan" not in result["warmed"]

    @pytest.mark.asyncio
    async def test_pre_warm_health_check_success(self):
        engine, _ = _make_engine()
        engine.predict_next = MagicMock(return_value=[
            {"action": "health_check", "confidence": 0.8, "score": 20.0, "reason": "h=10 wd=1"},
        ])

        with patch("src.orchestrator_v2.orchestrator_v2") as mock_orch:
            mock_orch.health_check = MagicMock(return_value={"status": "ok"})
            result = await engine.pre_warm()

        assert "health_check" in result["warmed"]

    @pytest.mark.asyncio
    async def test_pre_warm_handles_import_error(self):
        engine, _ = _make_engine()
        engine.predict_next = MagicMock(return_value=[
            {"action": "health_check", "confidence": 0.9, "score": 25.0, "reason": "h=10 wd=1"},
        ])

        # Simulate import failure for orchestrator_v2
        with patch.dict("sys.modules", {"src.orchestrator_v2": None}):
            result = await engine.pre_warm()

        # Should not crash, health_check just won't be in warmed
        assert "health_check" not in result["warmed"]


# ===========================================================================
# Test: get_user_profile
# ===========================================================================

class TestGetUserProfile:
    """Verify user profile deduction from patterns."""

    def test_get_user_profile_full(self):
        engine, mock_conn = _make_engine()
        mock_conn.row_factory = None

        # Configure mock to return different results for each query
        call_idx = {"n": 0}
        total_row = MagicMock()
        total_row.__getitem__ = lambda self, key: 150

        hour_row = MagicMock()
        hour_row.__getitem__ = lambda self, key: 14 if key == "hour" else 50

        action_row = MagicMock()
        action_row.__getitem__ = lambda self, key: "trading_scan" if key == "action" else 30

        day_row = MagicMock()
        day_row.__getitem__ = lambda self, key: 2 if key == "weekday" else 40

        recent_row = MagicMock()
        recent_row.__getitem__ = lambda self, key: "gpu_info" if key == "action" else 1700000000.0

        results = [
            [total_row],       # total count
            [hour_row],        # active hours
            [action_row],      # top actions
            [day_row],         # active days
            [recent_row],      # recent
        ]

        def execute_side_effect(sql, params=None):
            cursor = MagicMock()
            cursor.fetchone.return_value = results[call_idx["n"]][0] if results[call_idx["n"]] else None
            cursor.fetchall.return_value = results[call_idx["n"]]
            call_idx["n"] += 1
            return cursor

        mock_conn.execute = execute_side_effect

        profile = engine.get_user_profile()

        assert profile["total_actions"] == 150
        assert len(profile["active_hours"]) >= 1
        assert profile["active_hours"][0]["hour"] == 14
        assert profile["top_actions"][0]["action"] == "trading_scan"
        assert profile["active_days"][0]["day"] == "Mercredi"  # weekday 2 = Mercredi
        assert profile["recent"][0]["action"] == "gpu_info"

    def test_get_user_profile_db_error(self):
        engine, mock_conn = _make_engine()
        failing_conn = MagicMock()
        failing_conn.__enter__ = MagicMock(return_value=failing_conn)
        failing_conn.__exit__ = MagicMock(return_value=False)
        failing_conn.execute = MagicMock(side_effect=Exception("DB crash"))
        engine._conn = MagicMock(return_value=failing_conn)

        profile = engine.get_user_profile()
        assert "error" in profile
        assert "DB crash" in profile["error"]

    def test_day_names_mapping(self):
        """Verify the French day name mapping for all 7 weekdays."""
        engine, mock_conn = _make_engine()
        mock_conn.row_factory = None

        expected_days = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]

        for wd_idx, expected_name in enumerate(expected_days):
            call_idx = {"n": 0}

            total_row = MagicMock()
            total_row.__getitem__ = lambda self, key: 1

            hour_row = MagicMock()
            hour_row.__getitem__ = lambda self, key: 0 if key == "hour" else 1

            action_row = MagicMock()
            action_row.__getitem__ = lambda self, key: "x" if key == "action" else 1

            day_row = MagicMock()
            # Capture wd_idx in a closure
            day_row.__getitem__ = (lambda wd=wd_idx: lambda self, key: wd if key == "weekday" else 1)()

            recent_row = MagicMock()
            recent_row.__getitem__ = lambda self, key: "x" if key == "action" else 0.0

            results = [[total_row], [hour_row], [action_row], [day_row], [recent_row]]

            def execute_side_effect(sql, params=None):
                cursor = MagicMock()
                cursor.fetchone.return_value = results[call_idx["n"]][0]
                cursor.fetchall.return_value = results[call_idx["n"]]
                call_idx["n"] += 1
                return cursor

            mock_conn.execute = execute_side_effect

            profile = engine.get_user_profile()
            assert profile["active_days"][0]["day"] == expected_name, (
                f"weekday {wd_idx} should map to {expected_name}"
            )


# ===========================================================================
# Test: get_stats
# ===========================================================================

class TestGetStats:
    """Verify statistics retrieval."""

    def test_get_stats_normal(self):
        engine, mock_conn = _make_engine()

        call_idx = {"n": 0}
        stats_values = [42, 7, 1700000099.0]  # total, unique, latest

        def execute_side_effect(sql, params=None):
            cursor = MagicMock()
            row = MagicMock()
            row.__getitem__ = (lambda v=stats_values[call_idx["n"]]: lambda self, idx: v)()
            cursor.fetchone.return_value = row
            call_idx["n"] += 1
            return cursor

        mock_conn.execute = execute_side_effect

        stats = engine.get_stats()
        assert stats["total_patterns"] == 42
        assert stats["unique_actions"] == 7
        assert stats["latest_record"] == 1700000099.0
        assert stats["cache_entries"] == 0

    def test_get_stats_with_cache(self):
        engine, mock_conn = _make_engine()
        engine._cache = {"10_1": [], "14_3": []}

        call_idx = {"n": 0}
        stats_values = [0, 0, None]

        def execute_side_effect(sql, params=None):
            cursor = MagicMock()
            row = MagicMock()
            row.__getitem__ = (lambda v=stats_values[call_idx["n"]]: lambda self, idx: v)()
            cursor.fetchone.return_value = row
            call_idx["n"] += 1
            return cursor

        mock_conn.execute = execute_side_effect

        stats = engine.get_stats()
        assert stats["cache_entries"] == 2

    def test_get_stats_db_error(self):
        engine, mock_conn = _make_engine()
        failing_conn = MagicMock()
        failing_conn.__enter__ = MagicMock(return_value=failing_conn)
        failing_conn.__exit__ = MagicMock(return_value=False)
        failing_conn.execute = MagicMock(side_effect=Exception("Stats error"))
        engine._conn = MagicMock(return_value=failing_conn)

        stats = engine.get_stats()
        assert "error" in stats


# ===========================================================================
# Test: cleanup
# ===========================================================================

class TestCleanup:
    """Verify old pattern removal."""

    def test_cleanup_deletes_old_records(self):
        engine, mock_conn = _make_engine()

        cursor_mock = MagicMock()
        cursor_mock.rowcount = 15
        mock_conn.execute.return_value = cursor_mock

        with patch("src.prediction_engine.time") as mock_time:
            mock_time.time.return_value = 1700000000.0
            deleted = engine.cleanup(max_age_days=30)

        assert deleted == 15
        call_args = mock_conn.execute.call_args
        sql = call_args[0][0]
        cutoff = call_args[0][1][0]
        assert "DELETE FROM user_patterns" in sql
        expected_cutoff = 1700000000.0 - (30 * 86400)
        assert cutoff == expected_cutoff

    def test_cleanup_custom_days(self):
        engine, mock_conn = _make_engine()

        cursor_mock = MagicMock()
        cursor_mock.rowcount = 0
        mock_conn.execute.return_value = cursor_mock

        with patch("src.prediction_engine.time") as mock_time:
            mock_time.time.return_value = 2000000000.0
            deleted = engine.cleanup(max_age_days=7)

        assert deleted == 0
        cutoff = mock_conn.execute.call_args[0][1][0]
        assert cutoff == 2000000000.0 - (7 * 86400)

    def test_cleanup_db_error_returns_zero(self):
        engine, mock_conn = _make_engine()
        failing_conn = MagicMock()
        failing_conn.__enter__ = MagicMock(return_value=failing_conn)
        failing_conn.__exit__ = MagicMock(return_value=False)
        failing_conn.execute = MagicMock(side_effect=Exception("Cleanup error"))
        engine._conn = MagicMock(return_value=failing_conn)

        deleted = engine.cleanup(max_age_days=90)
        assert deleted == 0


# ===========================================================================
# Test: Edge cases
# ===========================================================================

class TestEdgeCases:
    """Boundary conditions and special scenarios."""

    def test_predict_next_n_zero(self):
        engine, mock_conn = _make_engine()
        mock_conn.row_factory = None

        call_idx = {"n": 0}

        def execute_side_effect(sql, params=None):
            cursor = MagicMock()
            cursor.fetchall.return_value = []
            return cursor

        mock_conn.execute = execute_side_effect

        with patch("src.prediction_engine.time") as mock_time:
            mock_time.time.return_value = 0
            result = engine.predict_next(n=0, hour=10, weekday=1)

        assert result == []

    def test_record_action_special_characters_in_context(self):
        engine, mock_conn = _make_engine()

        with patch("src.prediction_engine.datetime") as mock_dt, \
             patch("src.prediction_engine.time"):
            mock_now = MagicMock()
            mock_now.hour = 0
            mock_now.weekday.return_value = 6
            mock_dt.now.return_value = mock_now

            engine.record_action("test", {"msg": "hello\nworld\t\"quotes\""})

        params = mock_conn.execute.call_args[0][1]
        ctx = json.loads(params[3])
        assert ctx["msg"] == "hello\nworld\t\"quotes\""

    def test_predict_hour_23_adjacent_wraps(self):
        engine, mock_conn = _make_engine()
        mock_conn.row_factory = None

        call_params = []

        def capture_execute(sql, params=None):
            call_params.append(params)
            cursor = MagicMock()
            cursor.fetchall.return_value = []
            return cursor

        mock_conn.execute = capture_execute

        with patch("src.prediction_engine.time") as mock_time:
            mock_time.time.return_value = 0
            engine.predict_next(n=1, hour=23, weekday=0)

        # Adjacent hours for 23: (22, 0)
        assert call_params[2] == (22, 0)

    def test_cache_ttl_expiry(self):
        engine, mock_conn = _make_engine()
        mock_conn.row_factory = None

        engine._cache = {"10_1": [{"action": "stale", "confidence": 1.0, "score": 10.0, "reason": ""}]}
        engine._cache_ts = 100.0
        engine._cache_ttl = 300.0

        def execute_side_effect(sql, params=None):
            cursor = MagicMock()
            cursor.fetchall.return_value = []
            return cursor

        mock_conn.execute = execute_side_effect

        with patch("src.prediction_engine.time") as mock_time:
            # 100 + 300 = 400; current time 500 > 400 => cache expired
            mock_time.time.return_value = 500.0
            result = engine.predict_next(n=1, hour=10, weekday=1)

        # Cache expired, DB queried (returns empty), so result is empty
        assert result == []

    def test_multiple_record_actions_sequential(self):
        engine, mock_conn = _make_engine()

        with patch("src.prediction_engine.datetime") as mock_dt, \
             patch("src.prediction_engine.time"):
            mock_now = MagicMock()
            mock_now.hour = 9
            mock_now.weekday.return_value = 1
            mock_dt.now.return_value = mock_now

            engine.record_action("action_a")
            engine.record_action("action_b", {"key": "val"})
            engine.record_action("action_c")

        assert mock_conn.execute.call_count == 3
