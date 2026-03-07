"""Tests for src/cowork_bridge.py — Index, execute, search cowork scripts.

Covers: CoworkScript, ExecutionResult dataclasses, CoworkBridge
(CATEGORY_PATTERN_MAP, _index_scripts, list_scripts, search,
execute, execute_by_pattern, get_stats, get_execution_history),
get_bridge singleton.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.cowork_bridge import (
    CoworkScript, ExecutionResult, CoworkBridge, COWORK_PATHS,
)


# ===========================================================================
# CoworkScript
# ===========================================================================

class TestCoworkScript:
    def test_defaults(self):
        s = CoworkScript(
            name="test_script", path="/tmp/test.py",
            category="general", description="A test",
            size_bytes=1000, has_once=True, has_help=False,
        )
        assert s.keywords == []
        assert s.has_once is True

    def test_with_keywords(self):
        s = CoworkScript(
            name="ia_ensemble", path="/p", category="ia",
            description="Ensemble", size_bytes=500,
            has_once=True, has_help=True,
            keywords=["ensemble", "voter"],
        )
        assert s.keywords == ["ensemble", "voter"]


# ===========================================================================
# ExecutionResult
# ===========================================================================

class TestExecutionResult:
    def test_success(self):
        r = ExecutionResult(
            script="test", exit_code=0, stdout="OK",
            stderr="", duration_ms=150, success=True,
        )
        assert r.success is True
        assert r.args == []

    def test_failure(self):
        r = ExecutionResult(
            script="bad", exit_code=1, stdout="",
            stderr="Error", duration_ms=50, success=False,
            args=["--once"],
        )
        assert r.success is False
        assert r.args == ["--once"]


# ===========================================================================
# CATEGORY_PATTERN_MAP
# ===========================================================================

class TestCategoryPatternMap:
    def test_has_categories(self):
        expected = {"win", "jarvis", "ia", "cluster", "trading",
                    "telegram", "voice", "browser", "email", "general"}
        assert expected.issubset(set(CoworkBridge.CATEGORY_PATTERN_MAP.keys()))

    def test_values_are_strings(self):
        for cat, pat in CoworkBridge.CATEGORY_PATTERN_MAP.items():
            assert isinstance(pat, str)


# ===========================================================================
# CoworkBridge — init with mocked filesystem
# ===========================================================================

class TestCoworkBridgeInit:
    def test_init_no_path(self):
        with patch("src.cowork_bridge.sqlite3"), \
             patch.object(CoworkBridge, "_find_cowork_path"), \
             patch.object(CoworkBridge, "_index_scripts"):
            bridge = CoworkBridge()
            assert bridge._scripts == {}
            assert bridge._execution_history == []


# ===========================================================================
# CoworkBridge — list_scripts
# ===========================================================================

class TestListScripts:
    def setup_method(self):
        with patch("src.cowork_bridge.sqlite3"), \
             patch.object(CoworkBridge, "_find_cowork_path"), \
             patch.object(CoworkBridge, "_index_scripts"):
            self.bridge = CoworkBridge()
        # Manually populate scripts
        self.bridge._scripts = {
            "ia_test": CoworkScript("ia_test", "/p/ia_test.py", "ia", "Test IA", 100, True, False, ["test"]),
            "win_fix": CoworkScript("win_fix", "/p/win_fix.py", "win", "Fix Windows", 200, True, True, ["fix"]),
            "jarvis_boot": CoworkScript("jarvis_boot", "/p/jarvis_boot.py", "jarvis", "Boot", 300, False, False, ["boot"]),
        }

    def test_all(self):
        result = self.bridge.list_scripts()
        assert len(result) == 3

    def test_filter_category(self):
        result = self.bridge.list_scripts(category="ia")
        assert len(result) == 1
        assert result[0]["name"] == "ia_test"

    def test_filter_nonexistent(self):
        result = self.bridge.list_scripts(category="nonexistent")
        assert result == []

    def test_result_format(self):
        result = self.bridge.list_scripts()
        for r in result:
            assert "name" in r
            assert "category" in r
            assert "has_once" in r


# ===========================================================================
# CoworkBridge — search
# ===========================================================================

class TestSearch:
    def setup_method(self):
        with patch("src.cowork_bridge.sqlite3"), \
             patch.object(CoworkBridge, "_find_cowork_path"), \
             patch.object(CoworkBridge, "_index_scripts"):
            self.bridge = CoworkBridge()
        self.bridge._scripts = {
            "ia_thermal_monitor": CoworkScript("ia_thermal_monitor", "/p/i.py", "ia", "Monitor GPU thermal", 100, True, False, ["thermal", "monitor"]),
            "win_disk_cleanup": CoworkScript("win_disk_cleanup", "/p/w.py", "win", "Cleanup disk space", 200, True, True, ["disk", "cleanup"]),
            "ia_health_check": CoworkScript("ia_health_check", "/p/h.py", "ia", "Health check cluster", 150, True, False, ["health", "check"]),
        }

    def test_name_match(self):
        results = self.bridge.search("thermal")
        assert len(results) >= 1
        assert results[0]["name"] == "ia_thermal_monitor"

    def test_keyword_match(self):
        results = self.bridge.search("health")
        assert any(r["name"] == "ia_health_check" for r in results)

    def test_description_match(self):
        results = self.bridge.search("disk space")
        assert any(r["name"] == "win_disk_cleanup" for r in results)

    def test_no_match(self):
        results = self.bridge.search("xyzzy_nonexistent")
        assert results == []

    def test_limit(self):
        results = self.bridge.search("ia", limit=1)
        assert len(results) <= 1

    def test_result_has_score(self):
        results = self.bridge.search("monitor")
        assert all("score" in r for r in results)
        # Scores should be sorted descending
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)


# ===========================================================================
# CoworkBridge — execute
# ===========================================================================

class TestExecute:
    def setup_method(self):
        with patch("src.cowork_bridge.sqlite3"), \
             patch.object(CoworkBridge, "_find_cowork_path"), \
             patch.object(CoworkBridge, "_index_scripts"):
            self.bridge = CoworkBridge()
        self.bridge._cowork_path = Path("/tmp/cowork")

    def test_script_not_found(self):
        result = self.bridge.execute("nonexistent_script")
        assert result.success is False
        assert result.exit_code == -1
        assert "not found" in result.stderr

    def test_execute_success(self):
        self.bridge._scripts["test"] = CoworkScript(
            "test", "/tmp/cowork/test.py", "general", "Test", 100, True, False,
        )
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "OK"
        mock_proc.stderr = ""

        with patch("src.cowork_bridge.subprocess.run", return_value=mock_proc), \
             patch.object(self.bridge, "_log_execution"):
            result = self.bridge.execute("test")

        assert result.success is True
        assert result.exit_code == 0

    def test_execute_timeout(self):
        import subprocess
        self.bridge._scripts["slow"] = CoworkScript(
            "slow", "/tmp/cowork/slow.py", "general", "Slow", 100, True, False,
        )

        with patch("src.cowork_bridge.subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 60)), \
             patch.object(self.bridge, "_log_execution"):
            result = self.bridge.execute("slow", timeout_s=60)

        assert result.success is False
        assert result.exit_code == -2
        assert "Timeout" in result.stderr


# ===========================================================================
# CoworkBridge — execute_by_pattern
# ===========================================================================

class TestExecuteByPattern:
    def setup_method(self):
        with patch("src.cowork_bridge.sqlite3"), \
             patch.object(CoworkBridge, "_find_cowork_path"), \
             patch.object(CoworkBridge, "_index_scripts"):
            self.bridge = CoworkBridge()

    def test_no_matching_category(self):
        results = self.bridge.execute_by_pattern("nonexistent_pattern")
        assert results == []


# ===========================================================================
# CoworkBridge — get_stats
# ===========================================================================

class TestGetStats:
    def setup_method(self):
        with patch("src.cowork_bridge.sqlite3"), \
             patch.object(CoworkBridge, "_find_cowork_path"), \
             patch.object(CoworkBridge, "_index_scripts"):
            self.bridge = CoworkBridge()
        self.bridge._scripts = {
            "a": CoworkScript("a", "/p", "ia", "d", 100, True, False),
            "b": CoworkScript("b", "/p", "win", "d", 200, False, True),
            "c": CoworkScript("c", "/p", "ia", "d", 150, True, True),
        }

    def test_basic(self):
        stats = self.bridge.get_stats()
        assert stats["total_scripts"] == 3
        assert stats["with_once_flag"] == 2
        assert stats["with_help"] == 2
        assert stats["categories"]["ia"] == 2
        assert stats["categories"]["win"] == 1


# ===========================================================================
# CoworkBridge — get_execution_history
# ===========================================================================

class TestGetExecutionHistory:
    def test_db_error(self):
        with patch("src.cowork_bridge.sqlite3") as mock_sql, \
             patch.object(CoworkBridge, "_find_cowork_path"), \
             patch.object(CoworkBridge, "_index_scripts"):
            mock_sql.connect.side_effect = Exception("DB")
            bridge = CoworkBridge()
            history = bridge.get_execution_history()
        assert history == []
