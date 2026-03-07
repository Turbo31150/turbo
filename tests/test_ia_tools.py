"""Tests for src/ia_tools.py — OpenAI function-calling schemas for IA tools.

Covers: TOOLS list, TOOLS_BY_NAME index, _SCOPES, get_tools_for_scope
(all/minimal/system/specific), get_tool_meta.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ia_tools import (
    TOOLS, TOOLS_BY_NAME, get_tools_for_scope, get_tool_meta,
)


# ===========================================================================
# TOOLS list structure
# ===========================================================================

class TestToolsStructure:
    def test_tools_nonempty(self):
        assert len(TOOLS) >= 20

    def test_each_tool_has_type_function(self):
        for t in TOOLS:
            assert t["type"] == "function"

    def test_each_tool_has_function_block(self):
        for t in TOOLS:
            fn = t["function"]
            assert "name" in fn
            assert "description" in fn
            assert "parameters" in fn

    def test_each_tool_has_meta(self):
        for t in TOOLS:
            meta = t.get("_meta", {})
            assert "method" in meta
            assert "path" in meta
            assert "scope" in meta

    def test_parameters_is_object(self):
        for t in TOOLS:
            params = t["function"]["parameters"]
            assert params["type"] == "object"
            assert "properties" in params
            assert "required" in params

    def test_no_duplicate_names(self):
        names = [t["function"]["name"] for t in TOOLS]
        assert len(names) == len(set(names))

    def test_all_names_prefixed(self):
        for t in TOOLS:
            assert t["function"]["name"].startswith("jarvis_")


# ===========================================================================
# TOOLS_BY_NAME
# ===========================================================================

class TestToolsByName:
    def test_index_complete(self):
        assert len(TOOLS_BY_NAME) == len(TOOLS)

    def test_lookup(self):
        tool = TOOLS_BY_NAME.get("jarvis_autonomous_status")
        assert tool is not None
        assert tool["function"]["name"] == "jarvis_autonomous_status"

    def test_lookup_missing(self):
        assert TOOLS_BY_NAME.get("nonexistent") is None


# ===========================================================================
# get_tools_for_scope
# ===========================================================================

class TestGetToolsForScope:
    def test_scope_all(self):
        result = get_tools_for_scope("all")
        assert len(result) == len(TOOLS)
        # _meta should be stripped
        for t in result:
            assert "_meta" not in t

    def test_scope_minimal(self):
        result = get_tools_for_scope("minimal")
        assert len(result) == 4
        names = {t["function"]["name"] for t in result}
        assert "jarvis_autonomous_status" in names
        assert "jarvis_diagnostics_quick" in names
        assert "jarvis_alerts_active" in names
        assert "jarvis_cluster_health" in names

    def test_scope_system(self):
        result = get_tools_for_scope("system")
        assert len(result) >= 10
        names = {t["function"]["name"] for t in result}
        # system scope includes autonomous, cluster, diagnostics
        assert "jarvis_autonomous_status" in names
        assert "jarvis_cluster_health" in names
        assert "jarvis_diagnostics_quick" in names

    def test_scope_autonomous(self):
        result = get_tools_for_scope("autonomous")
        assert len(result) >= 3
        names = {t["function"]["name"] for t in result}
        assert "jarvis_autonomous_status" in names
        assert "jarvis_run_task" in names

    def test_scope_cluster(self):
        result = get_tools_for_scope("cluster")
        assert len(result) >= 2
        names = {t["function"]["name"] for t in result}
        assert "jarvis_cluster_health" in names

    def test_scope_unknown(self):
        result = get_tools_for_scope("nonexistent_scope")
        assert result == []

    def test_meta_stripped_in_output(self):
        for scope in ("all", "minimal", "system", "autonomous"):
            for t in get_tools_for_scope(scope):
                assert "_meta" not in t


# ===========================================================================
# get_tool_meta
# ===========================================================================

class TestGetToolMeta:
    def test_existing_tool(self):
        meta = get_tool_meta("jarvis_autonomous_status")
        assert meta["method"] == "GET"
        assert meta["path"] == "/api/autonomous/status"
        assert meta["scope"] == "autonomous"

    def test_run_task_meta(self):
        meta = get_tool_meta("jarvis_run_task")
        assert meta["method"] == "POST"
        assert "{task_name}" in meta["path"]

    def test_missing_tool(self):
        assert get_tool_meta("nonexistent") == {}

    def test_all_meta_have_method(self):
        for name in TOOLS_BY_NAME:
            meta = get_tool_meta(name)
            assert meta["method"] in ("GET", "POST")


# ===========================================================================
# Specific tools validation
# ===========================================================================

class TestSpecificTools:
    def test_jarvis_remember_has_required_content(self):
        tool = TOOLS_BY_NAME["jarvis_remember"]
        params = tool["function"]["parameters"]
        assert "content" in params["required"]

    def test_jarvis_recall_has_required_query(self):
        tool = TOOLS_BY_NAME["jarvis_recall"]
        params = tool["function"]["parameters"]
        assert "query" in params["required"]

    def test_jarvis_cowork_execute_has_required_script(self):
        tool = TOOLS_BY_NAME["jarvis_cowork_execute"]
        params = tool["function"]["parameters"]
        assert "script" in params["required"]

    def test_jarvis_boot_phase_has_optional_phase(self):
        tool = TOOLS_BY_NAME["jarvis_boot_phase"]
        params = tool["function"]["parameters"]
        assert "phase" in params["properties"]
        assert params["required"] == []

    def test_destructive_tools_exist(self):
        destructive = {"jarvis_cowork_execute", "jarvis_db_maintenance", "jarvis_pipeline_execute"}
        for name in destructive:
            assert name in TOOLS_BY_NAME
