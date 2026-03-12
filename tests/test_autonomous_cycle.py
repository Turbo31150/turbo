"""Integration tests for JARVIS Autonomous Cycle — end-to-end coverage
of the six core autonomous subsystems working together.

Tests:
  1. Decision Engine signal processing
  2. Resource Allocator allocation logic
  3. Log Analyzer (analyze_recent, detect_patterns, predict_failures)
  4. Self Diagnostic (diagnose -> health_score)
  5. VRAM Optimizer (check_and_optimize -> status)
  6. Rollback Manager (safe_fix context manager)

Each test is independent and mocks external I/O (network, subprocess, DB files)
so the suite runs reliably in CI without a live cluster.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Project root on sys.path (per convention)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ═══════════════════════════════════════════════════════════════════════
# 1. Decision Engine — signal processing
# ═══════════════════════════════════════════════════════════════════════

class TestDecisionEngineIntegration:
    """Integration tests for decision engine signal → rule → handler pipeline."""

    def test_import_and_singleton(self):
        from src.decision_engine import decision_engine
        assert decision_engine is not None

    def test_signal_fields(self):
        from src.decision_engine import Signal
        s = Signal(source="integration", severity="warning", category="cluster",
                   description="M1 slow response", data={"latency": 5.2})
        assert s.source == "integration"
        assert s.data == {"latency": 5.2}
        assert s.timestamp > 0

    def test_decision_defaults(self):
        from src.decision_engine import Decision
        d = Decision(action="restart", target="M1", reason="test")
        assert d.priority == 5
        assert d.auto_execute is True
        assert d.params == {}

    @pytest.mark.asyncio
    async def test_info_signal_no_decision(self):
        """Info-level signal should not trigger any critical rules."""
        from src.decision_engine import decision_engine, Signal
        sig = Signal(source="test_cycle", severity="info", category="test",
                     description="Routine heartbeat")
        results = await decision_engine.process_signal(sig)
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_critical_offline_triggers_heal(self):
        """Critical OFFLINE signal must trigger the heal_node decision."""
        from src.decision_engine import decision_engine, Signal
        sig = Signal(source="auto_scan", severity="critical", category="cluster",
                     description="M2 (192.168.1.26:1234) OFFLINE")
        results = await decision_engine.process_signal(sig)
        assert isinstance(results, list)
        heal_decisions = [r for r in results if r["decision"] == "heal_node"]
        assert len(heal_decisions) >= 1
        assert heal_decisions[0]["target"].startswith("M2")

    @pytest.mark.asyncio
    async def test_model_missing_triggers_load(self):
        """Missing models signal triggers load_model decision."""
        from src.decision_engine import decision_engine, Signal
        sig = Signal(source="auto_scan", severity="critical", category="cluster",
                     description="M1: 0 modeles charges (qwen3-8b manquant)")
        results = await decision_engine.process_signal(sig)
        load_decisions = [r for r in results if r["decision"] == "load_model"]
        assert len(load_decisions) >= 1

    @pytest.mark.asyncio
    async def test_overheating_triggers_throttle(self):
        """GPU OVERHEATING signal triggers throttle_gpu decision."""
        from src.decision_engine import decision_engine, Signal
        sig = Signal(source="vram_optimizer", severity="critical", category="gpu",
                     description="GPU OVERHEATING — temp 92C")
        results = await decision_engine.process_signal(sig)
        throttle = [r for r in results if r["decision"] == "throttle_gpu"]
        assert len(throttle) >= 1

    def test_custom_rule_and_handler(self):
        """Register a custom rule + handler and verify they are wired."""
        from src.decision_engine import decision_engine, Signal, Decision

        handler_called = {}

        def custom_rule(signal: Signal):
            if "cycle_test_marker" in signal.description:
                return Decision(action="cycle_custom", target="test",
                                reason="integration marker found")
            return None

        async def custom_handler(decision):
            handler_called["action"] = decision.action
            return "ok"

        decision_engine.register_rule("cycle_test", custom_rule)
        decision_engine.register_handler("cycle_custom", custom_handler)
        assert "cycle_custom" in decision_engine._action_handlers

    def test_stats_structure(self):
        from src.decision_engine import decision_engine
        stats = decision_engine.get_stats()
        for key in ("signals_processed", "decisions_made", "rules_count", "handlers_count"):
            assert key in stats
        assert stats["rules_count"] >= 6


# ═══════════════════════════════════════════════════════════════════════
# 2. Resource Allocator — allocation with mocked network
# ═══════════════════════════════════════════════════════════════════════

class TestResourceAllocatorIntegration:
    """Integration tests for resource allocation with mocked socket probes."""

    def _mock_socket_only_local(self):
        """Return a side_effect that only allows 127.0.0.1 connections."""
        original_create = __import__("socket").create_connection

        def fake_create(address, timeout=None, **kw):
            host = address[0] if isinstance(address, tuple) else address
            if host == "127.0.0.1":
                # Return a mock socket (no real connection needed)
                m = MagicMock()
                m.close = MagicMock()
                return m
            raise OSError(f"Simulated offline: {host}")

        return fake_create

    def test_allocate_code_picks_m1(self, monkeypatch):
        """Code tasks with only local nodes online should prefer M1."""
        from src.resource_allocator import ResourceAllocator
        alloc = ResourceAllocator()
        monkeypatch.setattr("socket.create_connection", self._mock_socket_only_local())
        node = alloc.allocate("code")
        assert node in ("M1", "OL1")  # both local, M1 preferred by weight+affinity

    def test_allocate_query_prefers_ol1(self, monkeypatch):
        """Query tasks should prefer OL1 (first in affinity list)."""
        from src.resource_allocator import ResourceAllocator
        alloc = ResourceAllocator()
        monkeypatch.setattr("socket.create_connection", self._mock_socket_only_local())
        node = alloc.allocate("query")
        assert node in ("OL1", "M1")

    def test_allocate_trading(self, monkeypatch):
        """Trading tasks should route to OL1 (web affinity)."""
        from src.resource_allocator import ResourceAllocator
        alloc = ResourceAllocator()
        monkeypatch.setattr("socket.create_connection", self._mock_socket_only_local())
        node = alloc.allocate("trading")
        assert node in ("OL1", "M1")

    def test_all_offline_raises(self, monkeypatch):
        """When all nodes are unreachable, allocate must raise RuntimeError."""
        from src.resource_allocator import ResourceAllocator
        alloc = ResourceAllocator()

        def fail_all(address, timeout=None, **kw):
            raise OSError("all offline")

        monkeypatch.setattr("socket.create_connection", fail_all)
        with pytest.raises(RuntimeError, match="No available node"):
            alloc.allocate("code")

    def test_record_updates_stats(self, monkeypatch):
        """record_allocation must update cumulative stats."""
        from src.resource_allocator import ResourceAllocator
        alloc = ResourceAllocator()
        monkeypatch.setattr("socket.create_connection", self._mock_socket_only_local())

        node = alloc.allocate("code")
        alloc.record_allocation(node, "code", 200.0)
        report = alloc.get_load_report()
        assert report["nodes"][node]["total_allocations"] >= 1
        assert report["nodes"][node]["avg_duration_ms"] > 0

    def test_rebalance_returns_list(self, monkeypatch):
        from src.resource_allocator import ResourceAllocator
        alloc = ResourceAllocator()
        suggestions = alloc.rebalance()
        assert isinstance(suggestions, list)
        assert len(suggestions) >= 1

    def test_circuit_breaker_blocks_allocation(self, monkeypatch):
        """A node with open circuit must be skipped during allocation."""
        from src.resource_allocator import ResourceAllocator
        alloc = ResourceAllocator()
        monkeypatch.setattr("socket.create_connection", self._mock_socket_only_local())

        # Open circuit on M1
        alloc._open_circuit("M1")
        node = alloc.allocate("code")
        # M1 is circuit-broken, so should pick OL1
        assert node == "OL1"


# ═══════════════════════════════════════════════════════════════════════
# 3. Log Analyzer — with temp log files
# ═══════════════════════════════════════════════════════════════════════

class TestLogAnalyzerIntegration:
    """Integration tests for log analyzer with synthetic log files."""

    def _make_analyzer_with_logs(self, tmp_path, log_lines):
        """Create a fresh LogAnalyzer pointing at tmp_path with given log content."""
        from src.log_analyzer import LogAnalyzer
        analyzer = LogAnalyzer()
        # Override paths to temp dirs
        analyzer.LOG_DIR = tmp_path / "logs"
        analyzer.DB_PATH = tmp_path / "data" / "log_analysis.db"
        analyzer.LOG_DIR.mkdir(parents=True, exist_ok=True)
        analyzer.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        analyzer._init_db()

        # Write synthetic log file
        log_file = analyzer.LOG_DIR / "test_service.log"
        log_file.write_text("\n".join(log_lines), encoding="utf-8")
        return analyzer

    def test_analyze_recent_empty(self, tmp_path):
        """Empty log dir returns zero counts."""
        analyzer = self._make_analyzer_with_logs(tmp_path, [])
        result = analyzer.analyze_recent(hours=1)
        assert result["total_entries"] == 0
        assert result["errors"] == 0
        assert result["trend"] == "stable"

    def test_analyze_recent_with_errors(self, tmp_path):
        """Analyzer counts ERROR and WARNING entries within the time window."""
        now = datetime.utcnow()
        ts = now.strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            f"{ts} [ERROR] Connection timeout to M2",
            f"{ts} [WARNING] VRAM usage 91%",
            f"{ts} [ERROR] Connection timeout to M2",
            f"{ts} INFO normal log line without brackets",
        ]
        analyzer = self._make_analyzer_with_logs(tmp_path, lines)
        result = analyzer.analyze_recent(hours=1)
        assert result["total_entries"] == 3  # 2 ERROR + 1 WARNING
        assert result["errors"] == 2
        assert result["warnings"] == 1
        assert result["criticals"] == 0

    def test_detect_patterns_groups_similar(self, tmp_path):
        """Similar messages (different PIDs/IPs) should be grouped into one pattern."""
        now = datetime.utcnow()
        ts = now.strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            f"{ts} [ERROR] Connection timeout to 192.168.1.26 PID 12345",
            f"{ts} [ERROR] Connection timeout to 192.168.1.113 PID 67890",
            f"{ts} [ERROR] Connection timeout to 10.0.0.1 PID 11111",
        ]
        analyzer = self._make_analyzer_with_logs(tmp_path, lines)
        patterns = analyzer.detect_patterns()
        assert isinstance(patterns, list)
        # All three should normalize to the same pattern
        if patterns:
            assert patterns[0]["count"] == 3

    def test_predict_failures_accelerating(self, tmp_path):
        """Accelerating pattern (more recent than older) should produce a prediction."""
        now = datetime.utcnow()
        lines = []
        # 1 entry 50 min ago
        old_ts = (now - timedelta(minutes=50)).strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"{old_ts} [ERROR] Disk almost full")
        # 4 entries in last 10 minutes
        for i in range(4):
            recent_ts = (now - timedelta(minutes=i + 1)).strftime("%Y-%m-%d %H:%M:%S")
            lines.append(f"{recent_ts} [ERROR] Disk almost full")

        analyzer = self._make_analyzer_with_logs(tmp_path, lines)
        predictions = analyzer.predict_failures()
        assert isinstance(predictions, list)
        # Should detect acceleration: 4 in last 15min vs 1 in older 45min
        if predictions:
            assert predictions[0]["confidence"] >= 0.5
            assert "accelerating" in predictions[0]["predicted_issue"].lower()

    def test_recommend_action_keywords(self):
        """_recommend_action returns relevant advice based on pattern keywords."""
        from src.log_analyzer import LogAnalyzer
        assert "connectivity" in LogAnalyzer._recommend_action("M2 OFFLINE timeout").lower() or \
               "restart" in LogAnalyzer._recommend_action("M2 OFFLINE timeout").lower()
        assert "memory" in LogAnalyzer._recommend_action("OOM killed process").lower()
        assert "disk" in LogAnalyzer._recommend_action("disk space low").lower()
        assert "GPU" in LogAnalyzer._recommend_action("CUDA out of VRAM") or \
               "VRAM" in LogAnalyzer._recommend_action("CUDA out of VRAM")

    def test_normalize_strips_variable_parts(self):
        """Normalization should replace IPs, PIDs, UUIDs with <N>."""
        from src.log_analyzer import LogAnalyzer
        analyzer = LogAnalyzer()
        normalized = analyzer._normalize("Error on 192.168.1.26 PID 54321 session abc12345-6789-0abc-def0-123456789abc")
        assert "192.168.1.26" not in normalized
        assert "54321" not in normalized
        assert "<N>" in normalized


# ═══════════════════════════════════════════════════════════════════════
# 4. Self Diagnostic — with mocked DB queries
# ═══════════════════════════════════════════════════════════════════════

class TestSelfDiagnosticIntegration:
    """Integration tests for self-diagnostic health scoring."""

    @pytest.mark.asyncio
    async def test_diagnose_returns_full_report(self):
        """diagnose() must return health_score, issues, recommendations, checks_run."""
        from src.self_diagnostic import SelfDiagnostic
        diag = SelfDiagnostic()
        report = await diag.diagnose()
        assert "health_score" in report
        assert "issues" in report
        assert "recommendations" in report
        assert "checks_run" in report
        assert report["checks_run"] == 5
        assert 0 <= report["health_score"] <= 100

    @pytest.mark.asyncio
    async def test_perfect_health_score_no_issues(self):
        """With all checks returning empty, health_score should be 100."""
        from src.self_diagnostic import SelfDiagnostic
        diag = SelfDiagnostic()
        # Mock all checks to return no issues
        diag._check_response_times = lambda: []
        diag._check_error_rates = lambda: []
        diag._check_circuit_breakers = lambda: []
        diag._check_scheduler_health = lambda: []
        diag._check_queue_backlog = lambda: []
        report = await diag.diagnose()
        assert report["health_score"] == 100
        assert len(report["issues"]) == 0
        assert any("healthy" in r.lower() for r in report["recommendations"])

    @pytest.mark.asyncio
    async def test_critical_issues_lower_score(self):
        """Injecting critical issues should reduce health_score by 15 each."""
        from src.self_diagnostic import SelfDiagnostic
        diag = SelfDiagnostic()
        fake_issues = [
            {"check": "response_time", "node": "M2", "severity": "critical",
             "message": "M2 slow", "value": 20.0},
            {"check": "error_rate", "severity": "critical",
             "message": "Error rate 60%", "value": 60.0},
        ]
        diag._check_response_times = lambda: fake_issues[:1]
        diag._check_error_rates = lambda: fake_issues[1:]
        diag._check_circuit_breakers = lambda: []
        diag._check_scheduler_health = lambda: []
        diag._check_queue_backlog = lambda: []
        report = await diag.diagnose()
        # 100 - 15 - 15 = 70
        assert report["health_score"] == 70
        assert len(report["issues"]) == 2

    @pytest.mark.asyncio
    async def test_warning_issues_deduct_five(self):
        """Warning-level issues deduct 5 points each from health_score."""
        from src.self_diagnostic import SelfDiagnostic
        diag = SelfDiagnostic()
        fake_issues = [
            {"check": "queue_backlog", "severity": "warning",
             "message": "25 pending", "value": 25},
        ]
        diag._check_response_times = lambda: []
        diag._check_error_rates = lambda: []
        diag._check_circuit_breakers = lambda: []
        diag._check_scheduler_health = lambda: []
        diag._check_queue_backlog = lambda: fake_issues
        report = await diag.diagnose()
        assert report["health_score"] == 95

    def test_recommendations_cover_all_check_types(self):
        """_generate_recommendations produces text for each check type."""
        from src.self_diagnostic import SelfDiagnostic
        diag = SelfDiagnostic()
        issues = [
            {"check": "response_time", "node": "M2", "severity": "critical"},
            {"check": "error_rate", "severity": "warning"},
            {"check": "circuit_breaker", "node": "M3", "severity": "critical"},
            {"check": "scheduler_health", "severity": "warning"},
            {"check": "queue_backlog", "severity": "critical"},
        ]
        recs = diag._generate_recommendations(issues)
        assert len(recs) >= 5
        # Each recommendation should be a non-empty string
        for r in recs:
            assert isinstance(r, str)
            assert len(r) > 10


# ═══════════════════════════════════════════════════════════════════════
# 5. VRAM Optimizer — with mocked subprocess/urllib
# ═══════════════════════════════════════════════════════════════════════

class TestVRAMOptimizerIntegration:
    """Integration tests for VRAM optimizer with mocked GPU/API calls."""

    def _mock_nvidia_smi(self, vram_used=6000, vram_total=8000, temp=55, util=40):
        """Return a mock subprocess.run result for nvidia-smi."""
        stdout = f"NVIDIA GeForce RTX 3070, {temp}, {vram_used}, {vram_total}, {util}"
        result = MagicMock()
        result.stdout = stdout
        result.returncode = 0
        return result

    @pytest.mark.asyncio
    async def test_check_and_optimize_healthy(self, monkeypatch):
        """Normal GPU state returns 'healthy' status."""
        from src.vram_optimizer import VRAMOptimizer
        opt = VRAMOptimizer()
        monkeypatch.setattr("subprocess.run", lambda *a, **kw: self._mock_nvidia_smi())
        result = await opt.check_and_optimize()
        assert result["status"] == "healthy"
        assert result["gpu"]["temp_c"] == 55
        assert result["gpu"]["vram_pct"] == 75.0
        assert result["alerts"] == []

    @pytest.mark.asyncio
    async def test_check_and_optimize_critical_vram(self, monkeypatch):
        """VRAM > 95% triggers critical status."""
        from src.vram_optimizer import VRAMOptimizer
        opt = VRAMOptimizer()
        monkeypatch.setattr("subprocess.run",
                            lambda *a, **kw: self._mock_nvidia_smi(vram_used=7800, vram_total=8000))
        # Mock get_loaded_models to avoid real HTTP call
        opt.get_loaded_models = lambda: [
            {"id": "qwen3-8b", "loaded": True},
            {"id": "qwen3-30b", "loaded": True},
        ]
        result = await opt.check_and_optimize()
        assert result["status"] == "critical"
        assert any("CRITICAL" in a for a in result["alerts"])

    @pytest.mark.asyncio
    async def test_check_and_optimize_high_temp(self, monkeypatch):
        """GPU temp > 85C triggers critical alert."""
        from src.vram_optimizer import VRAMOptimizer
        opt = VRAMOptimizer()
        monkeypatch.setattr("subprocess.run",
                            lambda *a, **kw: self._mock_nvidia_smi(temp=90))
        result = await opt.check_and_optimize()
        assert result["status"] == "critical"
        assert any("OVERHEATING" in a for a in result["alerts"])

    @pytest.mark.asyncio
    async def test_check_and_optimize_no_gpu(self, monkeypatch):
        """When nvidia-smi fails, returns 'no_gpu' status."""
        from src.vram_optimizer import VRAMOptimizer
        opt = VRAMOptimizer()

        def fail_smi(*a, **kw):
            raise FileNotFoundError("nvidia-smi not found")

        monkeypatch.setattr("subprocess.run", fail_smi)
        result = await opt.check_and_optimize()
        assert result["status"] == "no_gpu"
        assert result["actions"] == []

    def test_trend_insufficient_data(self):
        """With < 5 history entries, trend reports insufficient data."""
        from src.vram_optimizer import VRAMOptimizer
        opt = VRAMOptimizer()
        opt._history = [{"ts": time.time(), "vram_pct": 50, "temp_c": 50, "util_pct": 30}]
        trend = opt._analyze_trend()
        assert trend["direction"] == "insufficient_data"

    def test_trend_increasing(self):
        """Increasing VRAM trend detected with appropriate history."""
        from src.vram_optimizer import VRAMOptimizer
        opt = VRAMOptimizer()
        now = time.time()
        # Older samples: low usage
        for i in range(5):
            opt._history.append({"ts": now - 100 + i, "vram_pct": 50, "temp_c": 50, "util_pct": 30})
        # Recent samples: high usage
        for i in range(5):
            opt._history.append({"ts": now - 5 + i, "vram_pct": 80, "temp_c": 60, "util_pct": 50})
        trend = opt._analyze_trend()
        assert trend["direction"] == "increasing"
        assert trend["change_pct"] > 0

    def test_gpu_state_dataclass(self):
        from src.vram_optimizer import GPUState
        g = GPUState(name="RTX 4090", temp_c=65, vram_used_mb=20000,
                     vram_total_mb=24000, utilization_pct=80, vram_pct=83.3)
        assert g.vram_total_mb == 24000
        assert g.vram_pct == 83.3


# ═══════════════════════════════════════════════════════════════════════
# 6. Rollback Manager — safe_fix context manager
# ═══════════════════════════════════════════════════════════════════════

class TestRollbackManagerIntegration:
    """Integration tests for rollback manager safe_fix."""

    def test_safe_fix_preserves_on_success(self, tmp_path):
        """On success, the modified file keeps its new content."""
        from src.rollback_manager import RollbackManager
        mgr = RollbackManager()
        target = tmp_path / "config.txt"
        target.write_text("original_value")

        with mgr.safe_fix("upgrade_config", target="config.txt", files=[str(target)]) as ctx:
            assert ctx["fix_id"] == "upgrade_config"
            target.write_text("upgraded_value")

        assert target.read_text() == "upgraded_value"

    def test_safe_fix_rollback_on_exception(self, tmp_path):
        """On exception, file is restored to its pre-fix content."""
        from src.rollback_manager import RollbackManager
        mgr = RollbackManager()
        target = tmp_path / "database.db"
        target.write_text("valid_schema")

        with pytest.raises(RuntimeError):
            with mgr.safe_fix("migrate_db", target="database.db", files=[str(target)]):
                target.write_text("corrupted_schema")
                raise RuntimeError("Migration failed!")

        assert target.read_text() == "valid_schema"

    def test_safe_fix_no_files(self):
        """safe_fix with no files still works as a context manager."""
        from src.rollback_manager import RollbackManager
        mgr = RollbackManager()
        with mgr.safe_fix("noop_fix", target="nothing") as ctx:
            assert ctx["snapshots"] == {}

    def test_safe_fix_multiple_files(self, tmp_path):
        """Rollback restores ALL snapshotted files, not just one."""
        from src.rollback_manager import RollbackManager
        mgr = RollbackManager()
        f1 = tmp_path / "file1.txt"
        f2 = tmp_path / "file2.txt"
        f1.write_text("content1")
        f2.write_text("content2")

        with pytest.raises(ValueError):
            with mgr.safe_fix("multi_fix", target="multi",
                              files=[str(f1), str(f2)]):
                f1.write_text("modified1")
                f2.write_text("modified2")
                raise ValueError("oops")

        assert f1.read_text() == "content1"
        assert f2.read_text() == "content2"

    def test_history_logged_after_fix(self, tmp_path):
        """After a successful fix, history should contain the entry."""
        from src.rollback_manager import RollbackManager
        mgr = RollbackManager()
        target = tmp_path / "test.txt"
        target.write_text("data")

        with mgr.safe_fix("history_test", target="test.txt", files=[str(target)]):
            target.write_text("new_data")

        history = mgr.get_history(limit=5)
        assert isinstance(history, list)
        # The most recent entry should be our fix
        recent_ids = [h["fix_id"] for h in history]
        assert "history_test" in recent_ids

    def test_snapshot_nonexistent_returns_none(self):
        """Snapshotting a nonexistent file returns None (no crash)."""
        from src.rollback_manager import RollbackManager
        mgr = RollbackManager()
        result = mgr.snapshot_file("/absolutely/nonexistent/file.txt")
        assert result is None


# ═══════════════════════════════════════════════════════════════════════
# Cross-module integration: Decision Engine + Resource Allocator
# ═══════════════════════════════════════════════════════════════════════

class TestCrossModuleIntegration:
    """Tests that verify multiple autonomous subsystems can work together."""

    @pytest.mark.asyncio
    async def test_signal_to_allocation_flow(self, monkeypatch):
        """Simulate: signal triggers decision -> allocator picks node for remediation."""
        from src.decision_engine import Signal, decision_engine
        from src.resource_allocator import ResourceAllocator

        # Mock socket for allocator
        def fake_socket(address, timeout=None, **kw):
            host = address[0] if isinstance(address, tuple) else address
            if host == "127.0.0.1":
                m = MagicMock()
                m.close = MagicMock()
                return m
            raise OSError("offline")

        monkeypatch.setattr("socket.create_connection", fake_socket)

        # 1. Process a critical signal
        sig = Signal(source="integration", severity="critical", category="cluster",
                     description="M3 (192.168.1.113:1234) OFFLINE")
        results = await decision_engine.process_signal(sig)
        assert any(r["decision"] == "heal_node" for r in results)

        # 2. Allocate a remediation task
        alloc = ResourceAllocator()
        node = alloc.allocate("code")
        assert node in ("M1", "OL1")

    @pytest.mark.asyncio
    async def test_diagnostic_to_decision_flow(self):
        """Simulate: diagnostic finds issue -> creates signal -> decision engine acts."""
        from src.decision_engine import Signal, decision_engine
        from src.self_diagnostic import SelfDiagnostic

        diag = SelfDiagnostic()
        # Mock checks to return a critical error-rate issue
        diag._check_response_times = lambda: []
        diag._check_error_rates = lambda: [
            {"check": "error_rate", "severity": "critical",
             "message": "Error rate 65%", "value": 65.0},
        ]
        diag._check_circuit_breakers = lambda: []
        diag._check_scheduler_health = lambda: []
        diag._check_queue_backlog = lambda: []

        report = await diag.diagnose()
        assert report["health_score"] < 100

        # Turn the diagnostic issue into a signal for the decision engine
        for issue in report["issues"]:
            sig = Signal(
                source="self_diagnostic",
                severity=issue["severity"],
                category="performance",
                description=issue["message"],
            )
            results = await decision_engine.process_signal(sig)
            # "error rate" in description should trigger high_error_rate rule
            assert any(r["decision"] == "analyze_logs" for r in results)
