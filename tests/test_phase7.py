"""Phase 7 Tests — Config Manager, Audit Trail, Cluster Diagnostics, MCP Handlers."""

import asyncio
import json
import tempfile
import time
from pathlib import Path
import pytest


# ═══════════════════════════════════════════════════════════════════════════
# CONFIG MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestConfigManager:
    @staticmethod
    def _make_config():
        from src.config_manager import ConfigManager
        tmpdir = tempfile.mkdtemp()
        return ConfigManager(config_path=Path(tmpdir) / "test_config.json")

    def test_singleton_exists(self):
        from src.config_manager import config_manager
        assert config_manager is not None

    def test_defaults_loaded(self):
        cm = self._make_config()
        assert cm.get("cluster.timeout_s") == 120
        assert cm.get("trading.leverage") == 10
        assert cm.get("voice.tts_voice") == "fr-FR-HenriNeural"

    def test_get_dotted_path(self):
        cm = self._make_config()
        weight = cm.get("cluster.nodes.M1.weight")
        assert weight == 1.8

    def test_get_default(self):
        cm = self._make_config()
        assert cm.get("nonexistent.path", "fallback") == "fallback"

    def test_set_and_get(self):
        cm = self._make_config()
        cm.set("cluster.nodes.M1.weight", 2.0)
        assert cm.get("cluster.nodes.M1.weight") == 2.0

    def test_set_creates_path(self):
        cm = self._make_config()
        cm.set("new.deep.key", "value")
        assert cm.get("new.deep.key") == "value"

    def test_history_recorded(self):
        cm = self._make_config()
        cm.set("trading.leverage", 20)
        history = cm.get_history()
        assert len(history) >= 1
        assert history[-1]["key"] == "trading.leverage"
        assert history[-1]["old"] == 10
        assert history[-1]["new"] == 20

    def test_get_section(self):
        cm = self._make_config()
        trading = cm.get_section("trading")
        assert "leverage" in trading
        assert "dry_run" in trading

    def test_get_all(self):
        cm = self._make_config()
        all_cfg = cm.get_all()
        assert "cluster" in all_cfg
        assert "routing" in all_cfg

    def test_reset_section(self):
        cm = self._make_config()
        cm.set("trading.leverage", 999)
        cm.reset_section("trading")
        assert cm.get("trading.leverage") == 10

    def test_reload_no_change(self):
        cm = self._make_config()
        assert not cm.reload()  # no external change

    def test_stats(self):
        cm = self._make_config()
        stats = cm.get_stats()
        assert "sections" in stats
        assert "total_changes" in stats
        assert "cluster" in stats["sections"]

    def test_persistence(self):
        tmpdir = tempfile.mkdtemp()
        path = Path(tmpdir) / "persist.json"
        from src.config_manager import ConfigManager
        cm1 = ConfigManager(config_path=path)
        cm1.set("test.key", "saved")
        cm2 = ConfigManager(config_path=path)
        assert cm2.get("test.key") == "saved"


# ═══════════════════════════════════════════════════════════════════════════
# AUDIT TRAIL
# ═══════════════════════════════════════════════════════════════════════════

class TestAuditTrail:
    @staticmethod
    def _make_trail():
        from src.audit_trail import AuditTrail
        tmpdir = tempfile.mkdtemp()
        return AuditTrail(db_path=Path(tmpdir) / "test_audit.db")

    def test_singleton_exists(self):
        from src.audit_trail import audit_trail
        assert audit_trail is not None

    def test_log_and_search(self):
        at = self._make_trail()
        eid = at.log("mcp_call", "handle_lm_query", {"node": "M1"}, source="test")
        assert isinstance(eid, str)
        results = at.search(action_type="mcp_call")
        assert len(results) == 1
        assert results[0]["action"] == "handle_lm_query"

    def test_search_by_source(self):
        at = self._make_trail()
        at.log("api", "request", source="electron")
        at.log("api", "request", source="voice")
        results = at.search(source="electron")
        assert len(results) == 1

    def test_search_by_query(self):
        at = self._make_trail()
        at.log("mcp", "lm_query", {"prompt": "fix Python bug"})
        at.log("mcp", "lm_models", {})
        results = at.search(query="Python")
        assert len(results) == 1

    def test_get_entry(self):
        at = self._make_trail()
        eid = at.log("test", "action")
        entry = at.get_entry(eid)
        assert entry is not None
        assert entry["action_type"] == "test"
        assert at.get_entry("nope") is None

    def test_stats(self):
        at = self._make_trail()
        at.log("a", "x", source="s1")
        at.log("b", "y", source="s2")
        stats = at.get_stats(hours=1)
        assert stats["total_recent"] == 2
        assert "a" in stats["by_type"]

    def test_cleanup(self):
        at = self._make_trail()
        at.log("old", "entry")
        import sqlite3
        with sqlite3.connect(str(at._db_path)) as conn:
            conn.execute("UPDATE audit_log SET ts = 0")
        cleaned = at.cleanup(days=1)
        assert cleaned == 1

    def test_duration_and_success(self):
        at = self._make_trail()
        at.log("api", "slow_call", duration_ms=5000, success=False)
        results = at.search()
        assert results[0]["duration_ms"] == 5000
        assert results[0]["success"] is False


# ═══════════════════════════════════════════════════════════════════════════
# CLUSTER DIAGNOSTICS
# ═══════════════════════════════════════════════════════════════════════════

class TestClusterDiagnostics:
    def test_singleton_exists(self):
        from src.cluster_diagnostics import cluster_diagnostics
        assert cluster_diagnostics is not None

    def test_run_diagnostic_structure(self):
        from src.cluster_diagnostics import ClusterDiagnostics
        cd = ClusterDiagnostics()
        report = cd.run_diagnostic()
        assert "grade" in report
        assert "scores" in report
        assert "problems" in report
        assert "recommendations" in report
        assert "sections" in report
        assert report["grade"] in ("A", "B", "C", "D", "F")

    def test_diagnostic_sections(self):
        from src.cluster_diagnostics import ClusterDiagnostics
        cd = ClusterDiagnostics()
        report = cd.run_diagnostic()
        expected_sections = {"orchestrator", "load_balancer", "autonomous_loop", "alerts", "data", "event_bus"}
        assert expected_sections.issubset(set(report["sections"].keys()))

    def test_scores_overall(self):
        from src.cluster_diagnostics import ClusterDiagnostics
        cd = ClusterDiagnostics()
        report = cd.run_diagnostic()
        assert "overall" in report["scores"]
        assert 0 <= report["scores"]["overall"] <= 100

    def test_get_last_report(self):
        from src.cluster_diagnostics import ClusterDiagnostics
        cd = ClusterDiagnostics()
        assert cd.get_last_report() == {}
        cd.run_diagnostic()
        assert cd.get_last_report() != {}

    def test_history(self):
        from src.cluster_diagnostics import ClusterDiagnostics
        cd = ClusterDiagnostics()
        cd.run_diagnostic()
        cd.run_diagnostic()
        history = cd.get_history()
        assert len(history) == 2

    def test_quick_status(self):
        from src.cluster_diagnostics import ClusterDiagnostics
        cd = ClusterDiagnostics()
        status = cd.get_quick_status()
        assert "health_score" in status
        assert "active_alerts" in status
        assert "loop_running" in status


# ═══════════════════════════════════════════════════════════════════════════
# MCP HANDLERS — Phase 7
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPHandlersPhase7:
    def test_config_get(self):
        from src.mcp_server import handle_config_get
        result = asyncio.run(handle_config_get({"key": "cluster.timeout_s"}))
        data = json.loads(result[0].text)
        assert data == 120

    def test_config_set(self):
        from src.mcp_server import handle_config_set
        result = asyncio.run(handle_config_set({"key": "test.mcp.key", "value": '"hello"'}))
        assert "set" in result[0].text.lower()

    def test_config_reload(self):
        from src.mcp_server import handle_config_reload
        result = asyncio.run(handle_config_reload({}))
        assert "reloaded" in result[0].text.lower()

    def test_config_stats(self):
        from src.mcp_server import handle_config_stats
        result = asyncio.run(handle_config_stats({}))
        data = json.loads(result[0].text)
        assert "sections" in data

    def test_audit_log(self):
        from src.mcp_server import handle_audit_log
        result = asyncio.run(handle_audit_log({
            "action_type": "test", "action": "mcp_test", "source": "test",
        }))
        assert "logged" in result[0].text.lower()

    def test_audit_search(self):
        from src.mcp_server import handle_audit_search
        result = asyncio.run(handle_audit_search({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_audit_stats(self):
        from src.mcp_server import handle_audit_stats
        result = asyncio.run(handle_audit_stats({}))
        data = json.loads(result[0].text)
        assert "total_recent" in data

    def test_diagnostics_run(self):
        from src.mcp_server import handle_diagnostics_run
        result = asyncio.run(handle_diagnostics_run({}))
        data = json.loads(result[0].text)
        assert "grade" in data

    def test_diagnostics_quick(self):
        from src.mcp_server import handle_diagnostics_quick
        result = asyncio.run(handle_diagnostics_quick({}))
        data = json.loads(result[0].text)
        assert "health_score" in data

    def test_diagnostics_history(self):
        from src.mcp_server import handle_diagnostics_history
        result = asyncio.run(handle_diagnostics_history({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)


# ═══════════════════════════════════════════════════════════════════════════
# TOOL COUNT PHASE 7
# ═══════════════════════════════════════════════════════════════════════════

class TestToolCountPhase7:
    def test_tool_count_at_least_149(self):
        """139 + 4 config + 3 audit + 3 diagnostics = 149."""
        from src.mcp_server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 149, f"Expected >= 149 tools, got {len(TOOL_DEFINITIONS)}"

    def test_no_duplicate_tool_names(self):
        from src.mcp_server import TOOL_DEFINITIONS
        names = [t[0] for t in TOOL_DEFINITIONS]
        dupes = [n for n in names if names.count(n) > 1]
        assert len(names) == len(set(names)), f"Duplicate tools: {set(dupes)}"
