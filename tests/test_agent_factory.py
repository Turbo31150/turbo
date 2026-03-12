"""Tests for src/agent_factory.py — Agent auto-creation and evolution.

Covers: AgentEvolution dataclass, pattern discovery, node tuning,
strategy tuning, stats update, report generation.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agent_factory import AgentFactory, AgentEvolution


def _create_factory_db(db_path: str, patterns: list[dict] | None = None, logs: list[dict] | None = None):
    db = sqlite3.connect(db_path)
    db.execute("""
        CREATE TABLE IF NOT EXISTS agent_patterns (
            pattern_id TEXT PRIMARY KEY,
            agent_id TEXT, pattern_type TEXT UNIQUE, keywords TEXT,
            description TEXT, model_primary TEXT, model_fallbacks TEXT,
            strategy TEXT DEFAULT 'category', priority INTEGER DEFAULT 3,
            avg_latency_ms REAL DEFAULT 0, success_rate REAL DEFAULT 0,
            total_calls INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS agent_dispatch_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            classified_type TEXT, node TEXT, request_text TEXT,
            success INTEGER DEFAULT 1, quality_score REAL DEFAULT 0.5,
            latency_ms REAL DEFAULT 500, strategy TEXT DEFAULT 'single',
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    if patterns:
        for p in patterns:
            db.execute(
                """INSERT INTO agent_patterns
                   (pattern_id, agent_id, pattern_type, keywords, description,
                    model_primary, model_fallbacks, strategy, priority)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (p.get("pattern_id", f"PAT_{p['pattern_type'].upper()}"),
                 p.get("agent_id", p["pattern_type"]),
                 p["pattern_type"],
                 p.get("keywords", p["pattern_type"]),
                 p.get("description", f"Agent for {p['pattern_type']}"),
                 p.get("model_primary", "qwen3-8b"),
                 p.get("model_fallbacks", ""),
                 p.get("strategy", "category"),
                 p.get("priority", 3)),
            )
    if logs:
        for l in logs:
            db.execute(
                "INSERT INTO agent_dispatch_log (classified_type, node, success, quality_score, latency_ms, strategy) VALUES (?, ?, ?, ?, ?, ?)",
                (l.get("type", "code"), l.get("node", "M1"),
                 l.get("success", 1), l.get("quality", 0.5),
                 l.get("latency", 500), l.get("strategy", "single")),
            )
    db.commit()
    db.close()


# ===========================================================================
# Dataclass
# ===========================================================================

class TestAgentEvolution:
    def test_basic_creation(self):
        e = AgentEvolution("code", "create", "none", "PAT_CODE", "new agent", 0.8)
        assert e.pattern_type == "code"
        assert e.action == "create"
        assert e.confidence == 0.8

    def test_tune_node(self):
        e = AgentEvolution("math", "tune_node", "M1", "OL1", "better perf", 0.9)
        assert e.old_value == "M1"
        assert e.new_value == "OL1"


# ===========================================================================
# Discover new patterns
# ===========================================================================

class TestDiscoverPatterns:
    def test_no_new_patterns(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_factory_db(db_path,
            patterns=[{"pattern_type": "code"}],
            logs=[{"type": "code", "node": "M1"} for _ in range(10)],
        )
        factory = AgentFactory(db_path=db_path)
        evolutions = factory.analyze_and_evolve()
        creates = [e for e in evolutions if e.action == "create"]
        assert len(creates) == 0

    def test_discover_new_pattern(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_factory_db(db_path,
            patterns=[{"pattern_type": "code"}],
            logs=[{"type": "new_pattern", "node": "M1", "success": 1} for _ in range(8)],
        )
        factory = AgentFactory(db_path=db_path)
        evolutions = factory.analyze_and_evolve()
        creates = [e for e in evolutions if e.action == "create"]
        assert len(creates) == 1
        assert creates[0].pattern_type == "new_pattern"

    def test_minimum_dispatches_required(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        # Only 3 dispatches, minimum is 5
        _create_factory_db(db_path,
            patterns=[],
            logs=[{"type": "rare_pattern"} for _ in range(3)],
        )
        factory = AgentFactory(db_path=db_path)
        evolutions = factory.analyze_and_evolve()
        creates = [e for e in evolutions if e.action == "create"]
        assert len(creates) == 0

    def test_created_pattern_in_db(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_factory_db(db_path,
            patterns=[],
            logs=[{"type": "auto_created", "node": "M1", "success": 1} for _ in range(6)],
        )
        factory = AgentFactory(db_path=db_path)
        factory.analyze_and_evolve()
        db = sqlite3.connect(db_path)
        row = db.execute("SELECT * FROM agent_patterns WHERE pattern_type='auto_created'").fetchone()
        db.close()
        assert row is not None


# ===========================================================================
# Tune nodes
# ===========================================================================

class TestTuneNodes:
    def test_no_tuning_single_node(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_factory_db(db_path,
            patterns=[{"pattern_type": "code", "model_primary": "qwen3-8b"}],
            logs=[{"type": "code", "node": "M1"} for _ in range(10)],
        )
        factory = AgentFactory(db_path=db_path)
        evolutions = factory.analyze_and_evolve()
        tunes = [e for e in evolutions if e.action == "tune_node"]
        assert len(tunes) == 0

    def test_tune_when_better_node(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        logs = []
        # M1 with 60% success
        for _ in range(6):
            logs.append({"type": "code", "node": "M1", "success": 1, "latency": 500, "quality": 0.7})
        for _ in range(4):
            logs.append({"type": "code", "node": "M1", "success": 0, "latency": 5000, "quality": 0.2})
        # OL1 with 100% success
        for _ in range(5):
            logs.append({"type": "code", "node": "OL1", "success": 1, "latency": 300, "quality": 0.9})
        _create_factory_db(db_path,
            patterns=[{"pattern_type": "code", "model_primary": "M1"}],
            logs=logs,
        )
        factory = AgentFactory(db_path=db_path)
        evolutions = factory.analyze_and_evolve()
        tunes = [e for e in evolutions if e.action == "tune_node"]
        # OL1 should be suggested as better
        assert len(tunes) >= 1


# ===========================================================================
# Tune strategies
# ===========================================================================

class TestTuneStrategies:
    def test_no_tuning_single_strategy(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_factory_db(db_path,
            patterns=[{"pattern_type": "code", "strategy": "single"}],
            logs=[{"type": "code", "strategy": "single"} for _ in range(10)],
        )
        factory = AgentFactory(db_path=db_path)
        evolutions = factory.analyze_and_evolve()
        strat = [e for e in evolutions if e.action == "tune_strategy"]
        assert len(strat) == 0

    def test_tune_when_better_strategy(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        logs = []
        # "single" with 50% success, low quality
        for _ in range(5):
            logs.append({"type": "code", "node": "M1", "strategy": "single", "success": 1, "quality": 0.3})
        for _ in range(5):
            logs.append({"type": "code", "node": "M1", "strategy": "single", "success": 0, "quality": 0.1})
        # "race" with 100% success, high quality
        for _ in range(5):
            logs.append({"type": "code", "node": "M1", "strategy": "race", "success": 1, "quality": 0.9})
        _create_factory_db(db_path,
            patterns=[{"pattern_type": "code", "strategy": "single"}],
            logs=logs,
        )
        factory = AgentFactory(db_path=db_path)
        evolutions = factory.analyze_and_evolve()
        strat = [e for e in evolutions if e.action == "tune_strategy"]
        assert len(strat) >= 1


# ===========================================================================
# Update stats
# ===========================================================================

class TestUpdateStats:
    def test_stats_updated(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_factory_db(db_path,
            patterns=[{"pattern_type": "code"}],
            logs=[{"type": "code", "latency": 1000, "success": 1, "quality": 0.8} for _ in range(5)],
        )
        factory = AgentFactory(db_path=db_path)
        factory.analyze_and_evolve()
        db = sqlite3.connect(db_path)
        row = db.execute("SELECT total_calls, avg_latency_ms, success_rate FROM agent_patterns WHERE pattern_type='code'").fetchone()
        db.close()
        assert row[0] == 5  # total_calls
        assert row[1] == pytest.approx(1000, abs=1)  # avg_latency_ms
        assert row[2] == pytest.approx(1.0, abs=0.01)  # success_rate


# ===========================================================================
# Generate report
# ===========================================================================

class TestReport:
    def test_report_structure(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_factory_db(db_path,
            patterns=[{"pattern_type": "code"}, {"pattern_type": "math"}],
            logs=[{"type": "code", "node": "M1"} for _ in range(3)],
        )
        factory = AgentFactory(db_path=db_path)
        report = factory.generate_report()
        assert "timestamp" in report
        assert report["total_patterns"] == 2
        assert report["total_dispatches"] == 3
        assert "patterns" in report
        assert "best_combos" in report
        assert "dispatch_breakdown" in report

    def test_report_empty_db(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_factory_db(db_path)
        factory = AgentFactory(db_path=db_path)
        report = factory.generate_report()
        assert report["total_patterns"] == 0
        assert report["total_dispatches"] == 0

    def test_best_combos(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        logs = [{"type": "code", "node": "M1", "success": 1, "quality": 0.9, "strategy": "single"} for _ in range(5)]
        _create_factory_db(db_path, patterns=[], logs=logs)
        factory = AgentFactory(db_path=db_path)
        report = factory.generate_report()
        assert len(report["best_combos"]) >= 1
        assert report["best_combos"][0]["classified_type"] == "code"


# ===========================================================================
# Error handling
# ===========================================================================

class TestErrorHandling:
    def test_db_error_graceful(self):
        factory = AgentFactory(db_path="/nonexistent/path.db")
        with pytest.raises(Exception):
            factory.analyze_and_evolve()
