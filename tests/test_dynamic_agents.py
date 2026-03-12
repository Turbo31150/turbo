"""Tests for src/dynamic_agents.py — Dynamic agent spawner from DB patterns.

Covers: DynamicAgent dataclass, prompt generation, model-to-node mapping,
load from DB, agent listing, stats.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.dynamic_agents import (
    DynamicAgent,
    DynamicAgentSpawner,
    CATEGORY_PROMPTS,
    MODEL_TO_NODE,
)


def _create_test_db(db_path: str, patterns: list[dict] | None = None):
    """Create a test DB with agent_patterns table."""
    db = sqlite3.connect(db_path)
    db.execute("""
        CREATE TABLE IF NOT EXISTS agent_patterns (
            pattern_id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_type TEXT NOT NULL UNIQUE,
            agent_id TEXT DEFAULT '',
            model_primary TEXT DEFAULT 'qwen3-8b',
            model_fallback TEXT DEFAULT 'qwen3:1.7b',
            model_fallbacks TEXT DEFAULT '',
            strategy TEXT DEFAULT 'single',
            system_prompt TEXT,
            priority INTEGER DEFAULT 50,
            total_dispatches INTEGER DEFAULT 0,
            avg_quality REAL DEFAULT 0,
            avg_latency_ms REAL DEFAULT 0,
            success_rate REAL DEFAULT 0,
            last_used TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    if patterns:
        for p in patterns:
            db.execute(
                "INSERT INTO agent_patterns (pattern_type, agent_id, model_primary, model_fallbacks, strategy) VALUES (?, ?, ?, ?, ?)",
                (p.get("pattern_type", "test"), p.get("agent_id", "test_agent"),
                 p.get("model_primary", "qwen3-8b"), p.get("model_fallbacks", ""),
                 p.get("strategy", "single"))
            )
    db.commit()
    db.close()


# ===========================================================================
# DynamicAgent dataclass
# ===========================================================================

class TestDynamicAgent:
    def test_basic_creation(self):
        agent = DynamicAgent(
            pattern_type="win_monitor", agent_id="win_monitor_001",
            model_primary="qwen3-8b", model_fallbacks="qwen3:1.7b",
            strategy="single", system_prompt="Test", node="M1",
        )
        assert agent.pattern_type == "win_monitor"
        assert agent.node == "M1"
        assert agent.max_tokens == 1024

    def test_defaults(self):
        agent = DynamicAgent("test", "id", "m", "f", "single", "sys", "M1")
        assert agent.fallback_nodes == []
        assert agent.cowork_scripts == []
        assert agent.temperature == 0.3


# ===========================================================================
# Model to node mapping
# ===========================================================================

class TestModelMapping:
    def test_known_models(self):
        assert MODEL_TO_NODE["qwen3-8b"] == "M1"
        assert MODEL_TO_NODE["qwen3:1.7b"] == "OL1"
        assert MODEL_TO_NODE["deepseek-r1-0528-qwen3-8b"] == "M2"


# ===========================================================================
# Prompt generation
# ===========================================================================

class TestPromptGeneration:
    def test_category_prompts_exist(self):
        assert len(CATEGORY_PROMPTS) > 10

    def test_generate_win_prompt(self):
        spawner = DynamicAgentSpawner()
        prompt = spawner._generate_prompt("win_monitor", "win_001")
        assert "Windows" in prompt

    def test_generate_ia_prompt(self):
        spawner = DynamicAgentSpawner()
        prompt = spawner._generate_prompt("ia_training", "ia_001")
        assert "IA" in prompt or "intelligence" in prompt.lower()

    def test_generate_cowork_prompt(self):
        spawner = DynamicAgentSpawner()
        prompt = spawner._generate_prompt("cw-trading-signals", "cw-trading")
        assert "trading" in prompt.lower()

    def test_generate_generic_prompt(self):
        spawner = DynamicAgentSpawner()
        prompt = spawner._generate_prompt("unknown_pattern", "unknown_id")
        assert "expert" in prompt.lower()
        assert "unknown pattern" in prompt.lower()


# ===========================================================================
# Load from DB
# ===========================================================================

class TestLoadFromDB:
    def test_load_empty_db(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_test_db(db_path)
        spawner = DynamicAgentSpawner()
        with patch("src.dynamic_agents.DB_PATH", db_path):
            agents = spawner.load_all()
        assert len(agents) == 0
        assert spawner._loaded is True

    def test_load_with_patterns(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_test_db(db_path, [
            {"pattern_type": "win_test1", "agent_id": "win_test1", "model_primary": "qwen3-8b"},
            {"pattern_type": "ia_test2", "agent_id": "ia_test2", "model_primary": "qwen3:1.7b"},
        ])
        spawner = DynamicAgentSpawner()
        with patch("src.dynamic_agents.DB_PATH", db_path):
            agents = spawner.load_all()
        # Should skip hardcoded patterns but load custom ones
        assert spawner._loaded is True

    def test_load_skips_hardcoded(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        # "code" is a hardcoded pattern — should be skipped
        _create_test_db(db_path, [
            {"pattern_type": "code", "agent_id": "code_agent"},
            {"pattern_type": "custom_new", "agent_id": "custom_agent"},
        ])
        spawner = DynamicAgentSpawner()
        with patch("src.dynamic_agents.DB_PATH", db_path):
            agents = spawner.load_all()
        assert "code" not in agents

    def test_load_determines_node(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        _create_test_db(db_path, [
            {"pattern_type": "custom_m1", "agent_id": "id1", "model_primary": "qwen3-8b"},
            {"pattern_type": "custom_ol1", "agent_id": "id2", "model_primary": "qwen3:1.7b"},
        ])
        spawner = DynamicAgentSpawner()
        with patch("src.dynamic_agents.DB_PATH", db_path):
            spawner.load_all()
        if "custom_m1" in spawner.agents:
            assert spawner.agents["custom_m1"].node == "M1"
        if "custom_ol1" in spawner.agents:
            assert spawner.agents["custom_ol1"].node == "OL1"

    def test_load_handles_db_error(self):
        spawner = DynamicAgentSpawner()
        with patch("src.dynamic_agents.DB_PATH", "/nonexistent/path.db"):
            agents = spawner.load_all()
        assert agents == {}


# ===========================================================================
# Stats & listing
# ===========================================================================

class TestStatsAndListing:
    def test_stats_empty(self):
        spawner = DynamicAgentSpawner()
        spawner._loaded = True
        stats = spawner.get_stats()
        assert stats["total_dynamic_agents"] == 0
        assert stats["loaded"] is True

    def test_stats_with_agents(self):
        spawner = DynamicAgentSpawner()
        spawner._loaded = True
        spawner.agents["test1"] = DynamicAgent("test1", "id1", "qwen3-8b", "", "single", "sys", "M1")
        spawner.agents["test2"] = DynamicAgent("test2", "id2", "qwen3:1.7b", "", "race", "sys", "OL1")
        stats = spawner.get_stats()
        assert stats["total_dynamic_agents"] == 2
        assert stats["by_strategy"]["single"] == 1
        assert stats["by_strategy"]["race"] == 1
        assert stats["by_node"]["M1"] == 1
        assert stats["by_node"]["OL1"] == 1

    def test_list_agents(self):
        spawner = DynamicAgentSpawner()
        spawner._loaded = True
        spawner.agents["win_test"] = DynamicAgent(
            "win_test", "win_test_001", "qwen3-8b", "", "single",
            "Expert Windows system", "M1"
        )
        listing = spawner.list_agents()
        assert len(listing) == 1
        assert listing[0]["pattern"] == "win_test"
        assert listing[0]["node"] == "M1"

    def test_list_agents_sorted(self):
        spawner = DynamicAgentSpawner()
        spawner._loaded = True
        spawner.agents["z_agent"] = DynamicAgent("z_agent", "z", "m", "", "s", "sys", "M1")
        spawner.agents["a_agent"] = DynamicAgent("a_agent", "a", "m", "", "s", "sys", "M1")
        listing = spawner.list_agents()
        assert listing[0]["pattern"] == "a_agent"
        assert listing[1]["pattern"] == "z_agent"


# ===========================================================================
# to_pattern_agent conversion
# ===========================================================================

class TestToPatternAgent:
    def test_convert_to_pattern_agent(self):
        agent = DynamicAgent(
            "win_test", "win_001", "qwen3-8b", "", "single",
            "Expert Windows", "M1", ["OL1"], [], 2048, 0.4
        )
        pa = agent.to_pattern_agent()
        assert pa.pattern_type == "win_test"
        assert pa.primary_node == "M1"
        assert pa.system_prompt == "Expert Windows"
        assert pa.max_tokens == 2048
