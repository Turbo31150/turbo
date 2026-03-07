"""Tests for src/cowork_proactive.py — Need-driven script execution.

Covers: SystemNeed, ExecutionPlan dataclasses, CoworkProactive
(NEED_SCRIPT_MAP, detect_needs, plan_execution, execute_plan,
anticipate, run_proactive, get_stats).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.cowork_proactive import SystemNeed, ExecutionPlan, CoworkProactive, get_proactive


# ===========================================================================
# SystemNeed
# ===========================================================================

class TestSystemNeed:
    def test_defaults(self):
        need = SystemNeed(
            category="monitoring", urgency="high",
            description="Test need", source="quality_gate",
        )
        assert need.suggested_scripts == []
        assert need.data == {}

    def test_with_scripts(self):
        need = SystemNeed(
            category="security", urgency="critical",
            description="Breach", source="health",
            suggested_scripts=["audit_scanner", "firewall_check"],
            data={"node": "M1"},
        )
        assert len(need.suggested_scripts) == 2
        assert need.data["node"] == "M1"

    def test_all_urgencies(self):
        for u in ("critical", "high", "medium", "low"):
            need = SystemNeed("cat", u, "desc", "src")
            assert need.urgency == u


# ===========================================================================
# ExecutionPlan
# ===========================================================================

class TestExecutionPlan:
    def test_defaults(self):
        plan = ExecutionPlan(
            needs=[], scripts_to_run=[], estimated_duration_s=0,
        )
        assert plan.created_at == 0

    def test_with_data(self):
        needs = [SystemNeed("mon", "high", "d", "s")]
        scripts = [{"name": "check_health", "args": ["--once"], "timeout": 30}]
        plan = ExecutionPlan(
            needs=needs, scripts_to_run=scripts,
            estimated_duration_s=15.0, created_at=time.time(),
        )
        assert len(plan.needs) == 1
        assert len(plan.scripts_to_run) == 1
        assert plan.estimated_duration_s == 15.0
        assert plan.created_at > 0


# ===========================================================================
# NEED_SCRIPT_MAP
# ===========================================================================

class TestNeedScriptMap:
    def test_all_categories_present(self):
        expected = {"monitoring", "optimization", "security", "trading",
                    "system", "intelligence", "automation", "data", "voice", "web"}
        assert expected.issubset(set(CoworkProactive.NEED_SCRIPT_MAP.keys()))

    def test_each_has_keywords(self):
        for cat, terms in CoworkProactive.NEED_SCRIPT_MAP.items():
            assert len(terms) >= 3, f"{cat}: too few keywords"
            assert all(isinstance(t, str) for t in terms)

    def test_monitoring_terms(self):
        terms = CoworkProactive.NEED_SCRIPT_MAP["monitoring"]
        assert "health" in terms
        assert "monitor" in terms

    def test_security_terms(self):
        terms = CoworkProactive.NEED_SCRIPT_MAP["security"]
        assert "audit" in terms
        assert "security" in terms


# ===========================================================================
# CoworkProactive — detect_needs (mocked DB)
# ===========================================================================

class TestDetectNeeds:
    def setup_method(self):
        with patch("src.cowork_proactive.sqlite3"):
            self.pro = CoworkProactive()

    def test_returns_list(self):
        with patch.object(self.pro, "_needs_from_quality_gate", return_value=[]), \
             patch.object(self.pro, "_needs_from_health", return_value=[]), \
             patch.object(self.pro, "_needs_from_dispatch", return_value=[]), \
             patch.object(self.pro, "_needs_from_self_improvement", return_value=[]), \
             patch.object(self.pro, "_needs_from_benchmark_trend", return_value=[]), \
             patch.object(self.pro, "_needs_from_timeout_patterns", return_value=[]):
            needs = self.pro.detect_needs()
        assert isinstance(needs, list)
        assert len(needs) == 0

    def test_sorted_by_urgency(self):
        low = SystemNeed("a", "low", "d", "s")
        crit = SystemNeed("b", "critical", "d", "s")
        high = SystemNeed("c", "high", "d", "s")
        med = SystemNeed("d", "medium", "d", "s")

        with patch.object(self.pro, "_needs_from_quality_gate", return_value=[low, med]), \
             patch.object(self.pro, "_needs_from_health", return_value=[crit]), \
             patch.object(self.pro, "_needs_from_dispatch", return_value=[high]), \
             patch.object(self.pro, "_needs_from_self_improvement", return_value=[]), \
             patch.object(self.pro, "_needs_from_benchmark_trend", return_value=[]), \
             patch.object(self.pro, "_needs_from_timeout_patterns", return_value=[]):
            needs = self.pro.detect_needs()

        assert len(needs) == 4
        assert needs[0].urgency == "critical"
        assert needs[1].urgency == "high"
        assert needs[2].urgency == "medium"
        assert needs[3].urgency == "low"

    def test_aggregates_all_sources(self):
        n1 = SystemNeed("a", "high", "d", "quality_gate")
        n2 = SystemNeed("b", "medium", "d", "health")

        with patch.object(self.pro, "_needs_from_quality_gate", return_value=[n1]), \
             patch.object(self.pro, "_needs_from_health", return_value=[n2]), \
             patch.object(self.pro, "_needs_from_dispatch", return_value=[]), \
             patch.object(self.pro, "_needs_from_self_improvement", return_value=[]), \
             patch.object(self.pro, "_needs_from_benchmark_trend", return_value=[]), \
             patch.object(self.pro, "_needs_from_timeout_patterns", return_value=[]):
            needs = self.pro.detect_needs()

        sources = {n.source for n in needs}
        assert "quality_gate" in sources
        assert "health" in sources


# ===========================================================================
# CoworkProactive — _needs_from_quality_gate
# ===========================================================================

class TestNeedsFromQualityGate:
    def test_latency_gate_failure(self):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"pattern": "code", "failed_gates": "latency", "n": 6},
        ]
        mock_db.execute.return_value = mock_cursor
        mock_db.row_factory = None

        with patch("src.cowork_proactive.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            mock_sql.Row = None
            pro = CoworkProactive()
            needs = pro._needs_from_quality_gate()

        assert len(needs) >= 1
        assert needs[0].category == "optimization"
        assert needs[0].urgency == "high"  # n > 5

    def test_structure_gate_failure(self):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"pattern": "reasoning", "failed_gates": "structure", "n": 3},
        ]
        mock_db.execute.return_value = mock_cursor

        with patch("src.cowork_proactive.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            pro = CoworkProactive()
            needs = pro._needs_from_quality_gate()

        assert len(needs) >= 1
        assert needs[0].category == "intelligence"

    def test_db_error_returns_empty(self):
        with patch("src.cowork_proactive.sqlite3") as mock_sql:
            mock_sql.connect.side_effect = Exception("DB locked")
            pro = CoworkProactive()
            needs = pro._needs_from_quality_gate()
        assert needs == []


# ===========================================================================
# CoworkProactive — _needs_from_health
# ===========================================================================

class TestNeedsFromHealth:
    def test_open_circuit_breaker(self):
        mock_router = MagicMock()
        mock_router.get_status.return_value = {
            "nodes": {
                "M2": {"circuit_breaker": "open"},
                "M1": {"circuit_breaker": "closed"},
            }
        }

        with patch("src.cowork_proactive.sqlite3"):
            pro = CoworkProactive()

        with patch("src.adaptive_router.get_router", return_value=mock_router):
            needs = pro._needs_from_health()

        assert len(needs) == 1
        assert needs[0].urgency == "critical"
        assert needs[0].data["node"] == "M2"

    def test_all_closed_no_needs(self):
        mock_router = MagicMock()
        mock_router.get_status.return_value = {
            "nodes": {"M1": {"circuit_breaker": "closed"}}
        }

        with patch("src.cowork_proactive.sqlite3"):
            pro = CoworkProactive()

        with patch("src.adaptive_router.get_router", return_value=mock_router):
            needs = pro._needs_from_health()

        assert needs == []

    def test_import_error_returns_empty(self):
        with patch("src.cowork_proactive.sqlite3"):
            pro = CoworkProactive()

        with patch.dict("sys.modules", {"src.adaptive_router": None}):
            needs = pro._needs_from_health()
        assert needs == []


# ===========================================================================
# CoworkProactive — plan_execution
# ===========================================================================

class TestPlanExecution:
    def test_empty_needs(self):
        with patch("src.cowork_proactive.sqlite3"):
            pro = CoworkProactive()
        plan = pro.plan_execution([])
        assert plan.scripts_to_run == [] or len(plan.scripts_to_run) == 0

    def test_plan_with_bridge_unavailable(self):
        with patch("src.cowork_proactive.sqlite3"):
            pro = CoworkProactive()
        needs = [SystemNeed("monitoring", "high", "test", "test")]

        with patch.dict("sys.modules", {"src.cowork_bridge": None}):
            plan = pro.plan_execution(needs)

        assert plan.estimated_duration_s == 0
        assert plan.scripts_to_run == []

    def test_plan_limits_to_10(self):
        mock_bridge = MagicMock()
        mock_bridge.search.return_value = [
            {"name": f"script_{i}", "has_once": True, "score": 0.8}
            for i in range(5)
        ]

        with patch("src.cowork_proactive.sqlite3"):
            pro = CoworkProactive()

        needs = [SystemNeed(f"cat{i}", "high", "d", "s") for i in range(20)]

        with patch("src.cowork_bridge.get_bridge", return_value=mock_bridge):
            plan = pro.plan_execution(needs)

        assert len(plan.scripts_to_run) <= 10

    def test_plan_sorted_by_urgency(self):
        mock_bridge = MagicMock()
        mock_bridge.search.side_effect = lambda term, limit=3: [
            {"name": f"{term}_script", "has_once": True, "score": 0.5}
        ]

        with patch("src.cowork_proactive.sqlite3"):
            pro = CoworkProactive()

        needs = [
            SystemNeed("monitoring", "low", "d", "s"),
            SystemNeed("security", "critical", "d", "s"),
        ]

        with patch("src.cowork_bridge.get_bridge", return_value=mock_bridge):
            plan = pro.plan_execution(needs)

        if len(plan.scripts_to_run) >= 2:
            assert plan.scripts_to_run[0]["urgency"] == "critical"


# ===========================================================================
# CoworkProactive — execute_plan
# ===========================================================================

class TestExecutePlan:
    def test_dry_run(self):
        with patch("src.cowork_proactive.sqlite3"):
            pro = CoworkProactive()

        needs = [SystemNeed("mon", "high", "d", "s")]
        scripts = [{"name": "script_a", "args": ["--once"], "timeout": 30,
                     "need": "mon", "urgency": "high", "score": 0.8}]
        plan = ExecutionPlan(needs=needs, scripts_to_run=scripts,
                             estimated_duration_s=15, created_at=time.time())

        result = pro.execute_plan(plan, dry_run=True)
        assert result["dry_run"] is True
        assert result["scripts_planned"] == 1
        assert "script_a" in result["scripts"]

    def test_bridge_error(self):
        with patch("src.cowork_proactive.sqlite3"):
            pro = CoworkProactive()

        plan = ExecutionPlan(needs=[], scripts_to_run=[{"name": "x", "args": [], "timeout": 10,
                                                         "need": "n", "urgency": "low", "score": 0}],
                             estimated_duration_s=10)

        with patch.dict("sys.modules", {"src.cowork_bridge": None}):
            result = pro.execute_plan(plan)
        assert "error" in result

    def test_execution_success(self):
        mock_result = MagicMock()
        mock_result.script = "script_a"
        mock_result.success = True
        mock_result.duration_ms = 150
        mock_result.stdout = "OK"

        mock_bridge = MagicMock()
        mock_bridge.execute.return_value = mock_result

        with patch("src.cowork_proactive.sqlite3"):
            pro = CoworkProactive()

        needs = [SystemNeed("mon", "high", "d", "s")]
        scripts = [{"name": "script_a", "args": ["--once"], "timeout": 30,
                     "need": "mon", "urgency": "high", "score": 0.8}]
        plan = ExecutionPlan(needs=needs, scripts_to_run=scripts,
                             estimated_duration_s=15, created_at=time.time())

        with patch("src.cowork_bridge.get_bridge", return_value=mock_bridge), \
             patch.object(pro, "_log"), \
             patch.object(pro, "_emit"):
            result = pro.execute_plan(plan)

        assert result["scripts_executed"] == 1
        assert result["scripts_ok"] == 1
        assert result["success_rate"] == 1.0
        assert len(result["results"]) == 1
        assert result["results"][0]["success"] is True


# ===========================================================================
# CoworkProactive — anticipate
# ===========================================================================

class TestAnticipate:
    def test_db_error_returns_empty(self):
        with patch("src.cowork_proactive.sqlite3") as mock_sql:
            mock_sql.connect.side_effect = Exception("DB err")
            pro = CoworkProactive()
            result = pro.anticipate()
        assert result["predictions"] == []
        assert result["count"] == 0

    def test_no_data_returns_empty(self):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_db.execute.return_value = mock_cursor

        with patch("src.cowork_proactive.sqlite3") as mock_sql:
            mock_sql.connect.return_value = mock_db
            pro = CoworkProactive()
            result = pro.anticipate()

        assert result["count"] == 0


# ===========================================================================
# CoworkProactive — run_proactive
# ===========================================================================

class TestRunProactive:
    def test_dry_run_full_cycle(self):
        with patch("src.cowork_proactive.sqlite3"):
            pro = CoworkProactive()

        with patch.object(pro, "detect_needs", return_value=[]), \
             patch.object(pro, "plan_execution", return_value=ExecutionPlan([], [], 0)), \
             patch.object(pro, "execute_plan", return_value={"dry_run": True, "scripts_planned": 0, "scripts": []}), \
             patch.object(pro, "anticipate", return_value={"predictions": [], "count": 0}):
            result = pro.run_proactive(dry_run=True)

        assert "anticipation" in result

    def test_max_scripts_limits(self):
        with patch("src.cowork_proactive.sqlite3"):
            pro = CoworkProactive()

        scripts = [{"name": f"s{i}", "args": [], "timeout": 10,
                     "need": "n", "urgency": "low", "score": 0}
                    for i in range(20)]
        plan = ExecutionPlan([], scripts, 300)

        with patch.object(pro, "detect_needs", return_value=[]), \
             patch.object(pro, "plan_execution", return_value=plan), \
             patch.object(pro, "execute_plan", return_value={"ok": True}) as mock_exec, \
             patch.object(pro, "anticipate", return_value={"predictions": [], "count": 0}):
            pro.run_proactive(max_scripts=3)

        # plan.scripts_to_run should be truncated to 3
        call_plan = mock_exec.call_args[0][0]
        assert len(call_plan.scripts_to_run) == 3


# ===========================================================================
# CoworkProactive — get_stats
# ===========================================================================

class TestGetStats:
    def test_db_error(self):
        with patch("src.cowork_proactive.sqlite3") as mock_sql:
            mock_sql.connect.side_effect = Exception("DB")
            pro = CoworkProactive()
            stats = pro.get_stats()
        assert stats["total_orchestrations"] == 0

    def test_with_data(self):
        with patch("src.cowork_proactive.sqlite3") as mock_sql:
            pro = CoworkProactive()
            # Reset mock for get_stats calls
            mock_db = MagicMock()
            mock_db.execute.side_effect = [
                MagicMock(fetchone=MagicMock(return_value=(42,))),
                MagicMock(fetchone=MagicMock(return_value=(0.85,))),
            ]
            mock_sql.connect.return_value = mock_db
            stats = pro.get_stats()

        assert stats["total_orchestrations"] == 42
        assert stats["avg_success_rate"] == 0.85


# ===========================================================================
# get_proactive singleton
# ===========================================================================

class TestGetProactive:
    def test_returns_instance(self):
        with patch("src.cowork_proactive.sqlite3"):
            import src.cowork_proactive as mod
            mod._proactive = None
            pro = get_proactive()
            assert isinstance(pro, CoworkProactive)

    def test_singleton(self):
        with patch("src.cowork_proactive.sqlite3"):
            import src.cowork_proactive as mod
            mod._proactive = None
            p1 = get_proactive()
            p2 = get_proactive()
            assert p1 is p2
