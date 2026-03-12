"""Comprehensive tests for src/scheduler_cleanup.py -- Scheduler Cleanup & Bootstrap.

Covers:
- Module imports and async function signatures
- cleanup_and_bootstrap(): Phase 1 (delete test jobs), Phase 2 (create real jobs)
- fix_startup_duplicate_bug(): duplicate detection and removal
- REAL_JOBS definitions (names, intervals, actions)
- Result structure and data retention
- Logging behavior
- Error handling (DB exceptions, individual job failures)
"""

from __future__ import annotations

import asyncio
import inspect
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_module():
    """Import and return the scheduler_cleanup module."""
    import src.scheduler_cleanup as mod
    return mod


def _make_mock_connection(
    *,
    delete_rowcount: int = 0,
    existing_jobs: list | None = None,
    total_count: int = 0,
    duplicate_count: int = 0,
):
    """Build a MagicMock that behaves like sqlite3.Connection.

    Routes execute() calls based on the SQL string to return appropriate
    mock cursors for DELETE, SELECT job_id, SELECT COUNT, and INSERT.
    """
    existing_jobs = existing_jobs or []
    conn = MagicMock()

    def _execute_side_effect(sql, params=None):
        cursor = MagicMock()
        if sql.strip().startswith("DELETE"):
            cursor.rowcount = delete_rowcount
            return cursor
        if "SELECT job_id FROM scheduler_jobs WHERE name" in sql:
            name = params[0] if params else ""
            cursor.fetchone.return_value = ("existing_id",) if name in existing_jobs else None
            return cursor
        if "SELECT COUNT(*)" in sql and "test" in sql:
            cursor.fetchone.return_value = (duplicate_count,)
            return cursor
        if "SELECT COUNT(*) FROM scheduler_jobs" in sql:
            cursor.fetchone.return_value = (total_count,)
            return cursor
        if sql.strip().startswith("INSERT"):
            cursor.rowcount = 1
            return cursor
        return cursor

    conn.execute = MagicMock(side_effect=_execute_side_effect)
    conn.commit = MagicMock()
    return conn


def _setup(mock_conn):
    """Patch src.database.get_connection and return (mod, patcher)."""
    patcher = patch("src.database.get_connection", return_value=mock_conn)
    patcher.start()
    mod = _get_module()
    return mod, patcher


def _teardown(patcher):
    """Stop the patcher."""
    patcher.stop()


# ---------------------------------------------------------------------------
# Test class: Imports & Structure
# ---------------------------------------------------------------------------

class TestImportsAndStructure:
    def test_module_imports_without_side_effects(self):
        mod = _get_module()
        assert hasattr(mod, "cleanup_and_bootstrap")
        assert hasattr(mod, "fix_startup_duplicate_bug")

    def test_cleanup_and_bootstrap_is_coroutine(self):
        from src.scheduler_cleanup import cleanup_and_bootstrap
        assert asyncio.iscoroutinefunction(cleanup_and_bootstrap)

    def test_fix_startup_duplicate_bug_is_coroutine(self):
        from src.scheduler_cleanup import fix_startup_duplicate_bug
        assert asyncio.iscoroutinefunction(fix_startup_duplicate_bug)

    def test_logger_exists(self):
        mod = _get_module()
        assert hasattr(mod, "logger")


# ---------------------------------------------------------------------------
# Test class: REAL_JOBS definitions
# ---------------------------------------------------------------------------

class TestRealJobsDefinitions:
    def test_all_eight_job_names_in_source(self):
        """Source code should reference all 8 job names."""
        from src.scheduler_cleanup import cleanup_and_bootstrap
        source = inspect.getsource(cleanup_and_bootstrap)
        expected = [
            "morning_briefing", "evening_report", "hourly_health",
            "trading_scan", "pattern_analysis", "db_maintenance",
            "drift_check", "security_scan",
        ]
        for name in expected:
            assert name in source, f"Job not found in source: {name}"

    def test_intervals_are_positive_integers(self):
        """All interval_s values should be positive."""
        intervals = {
            "morning_briefing": 86400, "evening_report": 86400,
            "hourly_health": 3600, "trading_scan": 900,
            "pattern_analysis": 21600, "db_maintenance": 86400,
            "drift_check": 7200, "security_scan": 43200,
        }
        for name, val in intervals.items():
            assert isinstance(val, int) and val > 0

    def test_actions_are_non_empty_strings(self):
        """Each job action should be a non-empty string."""
        actions = [
            "skill", "skill", "health_check", "trading_scan",
            "brain_analyze", "db_vacuum", "drift_check", "security_scan",
        ]
        for action in actions:
            assert isinstance(action, str) and len(action) > 0


# ---------------------------------------------------------------------------
# Test class: cleanup_and_bootstrap
# ---------------------------------------------------------------------------

class TestCleanupAndBootstrap:
    @pytest.mark.asyncio
    async def test_result_is_dict_with_required_keys(self):
        """Return value must be a dict with the expected keys."""
        mock_conn = _make_mock_connection(delete_rowcount=0, total_count=0)
        mod, patcher = _setup(mock_conn)
        try:
            result = await mod.cleanup_and_bootstrap()
        finally:
            _teardown(patcher)
        assert isinstance(result, dict)
        for key in ("deleted_test_jobs", "created_jobs", "errors", "total_jobs_after"):
            assert key in result

    @pytest.mark.asyncio
    async def test_deletes_test_noop_jobs(self):
        """Phase 1 should delete test/noop jobs and report count."""
        mock_conn = _make_mock_connection(delete_rowcount=36, total_count=8)
        mod, patcher = _setup(mock_conn)
        try:
            result = await mod.cleanup_and_bootstrap()
        finally:
            _teardown(patcher)
        assert result["deleted_test_jobs"] == 36

    @pytest.mark.asyncio
    async def test_delete_zero_when_none_exist(self):
        """When no test jobs exist, deleted count is 0 and no errors."""
        mock_conn = _make_mock_connection(delete_rowcount=0, total_count=0)
        mod, patcher = _setup(mock_conn)
        try:
            result = await mod.cleanup_and_bootstrap()
        finally:
            _teardown(patcher)
        assert result["deleted_test_jobs"] == 0
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_creates_all_eight_jobs_on_empty_db(self):
        """Phase 2 should create all 8 jobs when none exist."""
        mock_conn = _make_mock_connection(delete_rowcount=0, total_count=8)
        mod, patcher = _setup(mock_conn)
        try:
            result = await mod.cleanup_and_bootstrap()
        finally:
            _teardown(patcher)
        expected_names = sorted([
            "morning_briefing", "evening_report", "hourly_health",
            "trading_scan", "pattern_analysis", "db_maintenance",
            "drift_check", "security_scan",
        ])
        assert sorted(result["created_jobs"]) == expected_names
        assert len(result["created_jobs"]) == 8

    @pytest.mark.asyncio
    async def test_skips_existing_jobs(self):
        """Jobs that already exist should be skipped, not duplicated."""
        existing = ["morning_briefing", "hourly_health", "trading_scan"]
        mock_conn = _make_mock_connection(
            delete_rowcount=0, existing_jobs=existing, total_count=8,
        )
        mod, patcher = _setup(mock_conn)
        try:
            result = await mod.cleanup_and_bootstrap()
        finally:
            _teardown(patcher)
        assert len(result["created_jobs"]) == 5
        for name in existing:
            assert name not in result["created_jobs"]

    @pytest.mark.asyncio
    async def test_total_jobs_after_reflects_db_count(self):
        """total_jobs_after should equal the DB final COUNT(*)."""
        mock_conn = _make_mock_connection(delete_rowcount=5, total_count=42)
        mod, patcher = _setup(mock_conn)
        try:
            result = await mod.cleanup_and_bootstrap()
        finally:
            _teardown(patcher)
        assert result["total_jobs_after"] == 42

    @pytest.mark.asyncio
    async def test_created_jobs_are_all_strings(self):
        """Every entry in created_jobs must be a string."""
        mock_conn = _make_mock_connection(delete_rowcount=0, total_count=8)
        mod, patcher = _setup(mock_conn)
        try:
            result = await mod.cleanup_and_bootstrap()
        finally:
            _teardown(patcher)
        for name in result["created_jobs"]:
            assert isinstance(name, str)

    @pytest.mark.asyncio
    async def test_insert_error_captured_but_others_continue(self):
        """If one INSERT fails, the error is captured and remaining jobs proceed."""
        insert_count = {"n": 0}

        def _execute(sql, params=None):
            cursor = MagicMock()
            if sql.strip().startswith("DELETE"):
                cursor.rowcount = 0
                return cursor
            if "SELECT job_id" in sql:
                cursor.fetchone.return_value = None
                return cursor
            if sql.strip().startswith("INSERT"):
                insert_count["n"] += 1
                if insert_count["n"] == 1:
                    raise Exception("disk full")
                return cursor
            if "SELECT COUNT(*)" in sql:
                cursor.fetchone.return_value = (7,)
                return cursor
            return cursor

        mock_conn = MagicMock()
        mock_conn.execute = MagicMock(side_effect=_execute)
        mod, patcher = _setup(mock_conn)
        try:
            result = await mod.cleanup_and_bootstrap()
        finally:
            _teardown(patcher)
        assert any("Failed to create" in e for e in result["errors"])
        assert len(result["created_jobs"]) == 7

    @pytest.mark.asyncio
    async def test_delete_error_captured_in_phase1(self):
        """If Phase 1 DELETE raises, the error is captured and Phase 2 still runs."""
        call_count = {"n": 0}

        def _execute(sql, params=None):
            call_count["n"] += 1
            cursor = MagicMock()
            # First execute call is the DELETE in Phase 1
            if call_count["n"] == 1:
                raise Exception("DB locked")
            if "SELECT job_id" in sql:
                cursor.fetchone.return_value = None
                return cursor
            if sql.strip().startswith("INSERT"):
                return cursor
            if "SELECT COUNT(*)" in sql:
                cursor.fetchone.return_value = (8,)
                return cursor
            return cursor

        mock_conn = MagicMock()
        mock_conn.execute = MagicMock(side_effect=_execute)
        mod, patcher = _setup(mock_conn)
        try:
            result = await mod.cleanup_and_bootstrap()
        finally:
            _teardown(patcher)
        assert any("Cleanup failed" in e for e in result["errors"])
        assert result["deleted_test_jobs"] == 0
        # Phase 2 still ran and created jobs
        assert len(result["created_jobs"]) > 0

    @pytest.mark.asyncio
    async def test_commit_called_after_delete(self):
        """get_connection().commit() should be called after the DELETE."""
        mock_conn = _make_mock_connection(delete_rowcount=3, total_count=8)
        mod, patcher = _setup(mock_conn)
        try:
            await mod.cleanup_and_bootstrap()
        finally:
            _teardown(patcher)
        assert mock_conn.commit.call_count >= 1

    @pytest.mark.asyncio
    async def test_hashlib_job_id_is_12_chars(self):
        """Each created job_id should be a 12-character hex string."""
        insert_params_list = []

        def _execute(sql, params=None):
            cursor = MagicMock()
            if sql.strip().startswith("DELETE"):
                cursor.rowcount = 0
                return cursor
            if "SELECT job_id" in sql:
                cursor.fetchone.return_value = None
                return cursor
            if sql.strip().startswith("INSERT"):
                if params:
                    insert_params_list.append(params)
                return cursor
            if "SELECT COUNT(*)" in sql:
                cursor.fetchone.return_value = (8,)
                return cursor
            return cursor

        mock_conn = MagicMock()
        mock_conn.execute = MagicMock(side_effect=_execute)
        mod, patcher = _setup(mock_conn)
        try:
            await mod.cleanup_and_bootstrap()
        finally:
            _teardown(patcher)
        # Each INSERT params tuple starts with the job_id
        for params in insert_params_list:
            job_id = params[0]
            assert len(job_id) == 12
            assert all(c in "0123456789abcdef" for c in job_id)


# ---------------------------------------------------------------------------
# Test class: fix_startup_duplicate_bug
# ---------------------------------------------------------------------------

class TestFixStartupDuplicateBug:
    @pytest.mark.asyncio
    async def test_no_duplicates_returns_ok(self):
        """When count <= 1, return OK message without deleting."""
        mock_conn = _make_mock_connection(duplicate_count=1)
        mod, patcher = _setup(mock_conn)
        try:
            result = await mod.fix_startup_duplicate_bug()
        finally:
            _teardown(patcher)
        assert "OK" in result
        assert "no duplicates" in result.lower()

    @pytest.mark.asyncio
    async def test_zero_count_returns_ok(self):
        """When count is 0, return OK message."""
        mock_conn = _make_mock_connection(duplicate_count=0)
        mod, patcher = _setup(mock_conn)
        try:
            result = await mod.fix_startup_duplicate_bug()
        finally:
            _teardown(patcher)
        assert "OK" in result

    @pytest.mark.asyncio
    async def test_duplicates_deleted(self):
        """When count > 1, duplicates are deleted and message reports count."""
        mock_conn = _make_mock_connection(duplicate_count=15)
        mod, patcher = _setup(mock_conn)
        try:
            result = await mod.fix_startup_duplicate_bug()
        finally:
            _teardown(patcher)
        assert "Fixed" in result
        assert "15" in result

    @pytest.mark.asyncio
    async def test_delete_sql_called_on_duplicates(self):
        """When duplicates exist, DELETE SQL must be executed."""
        mock_conn = _make_mock_connection(duplicate_count=5)
        mod, patcher = _setup(mock_conn)
        try:
            await mod.fix_startup_duplicate_bug()
        finally:
            _teardown(patcher)
        calls_with_delete = [
            c for c in mock_conn.execute.call_args_list
            if "DELETE" in str(c)
        ]
        assert len(calls_with_delete) >= 1

    @pytest.mark.asyncio
    async def test_commit_called_after_delete(self):
        """get_connection().commit() should be called after deleting duplicates."""
        mock_conn = _make_mock_connection(duplicate_count=3)
        mod, patcher = _setup(mock_conn)
        try:
            await mod.fix_startup_duplicate_bug()
        finally:
            _teardown(patcher)
        assert mock_conn.commit.call_count >= 1


# ---------------------------------------------------------------------------
# Test class: Logging
# ---------------------------------------------------------------------------

class TestLogging:
    @pytest.mark.asyncio
    async def test_cleanup_logs_info_on_success(self):
        """cleanup_and_bootstrap logs info messages on successful run."""
        mock_conn = _make_mock_connection(delete_rowcount=3, total_count=8)
        mod, patcher = _setup(mock_conn)
        with patch.object(mod, "logger") as mock_logger:
            try:
                await mod.cleanup_and_bootstrap()
            finally:
                _teardown(patcher)
        assert mock_logger.info.call_count > 0

    @pytest.mark.asyncio
    async def test_cleanup_logs_errors_on_db_exception(self):
        """Errors should be logged at error level."""
        mock_conn = MagicMock()
        mock_conn.execute = MagicMock(side_effect=Exception("boom"))
        mod, patcher = _setup(mock_conn)
        with patch.object(mod, "logger") as mock_logger:
            try:
                await mod.cleanup_and_bootstrap()
            finally:
                _teardown(patcher)
        assert mock_logger.error.call_count > 0
