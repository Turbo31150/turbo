"""Tests for src/perplexity_bridge.py — Perplexity <-> JARVIS bridge.

Covers: InteractionRecord, PerplexityBridge (learn_from_interaction,
suggest_improvement, create_skill_from_analysis, get_context_for_query,
_analyze_for_skill, status), perplexity_bridge singleton.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.perplexity_bridge import (
    InteractionRecord, PerplexityBridge, perplexity_bridge,
)


# ===========================================================================
# InteractionRecord
# ===========================================================================

class TestInteractionRecord:
    def test_defaults(self):
        r = InteractionRecord(prompt="hello", response_summary="world")
        assert r.tools_used == []
        assert r.context == {}
        assert r.ts > 0
        assert r.improvements_suggested == []

    def test_with_data(self):
        r = InteractionRecord(
            prompt="search AI", response_summary="results",
            tools_used=["web_search", "code_gen"],
            context={"source": "perplexity"},
        )
        assert len(r.tools_used) == 2
        assert r.context["source"] == "perplexity"


# ===========================================================================
# PerplexityBridge — init
# ===========================================================================

class TestInit:
    def test_defaults(self):
        pb = PerplexityBridge()
        assert pb.interactions == []
        assert pb.improvements_pending == []
        assert pb.skills_created == 0
        assert pb.memories_stored == 0


# ===========================================================================
# PerplexityBridge — learn_from_interaction
# ===========================================================================

class TestLearnFromInteraction:
    @pytest.mark.asyncio
    async def test_stores_interaction(self):
        pb = PerplexityBridge()
        mock_memory = MagicMock()
        mock_brain = MagicMock()
        mock_bus = MagicMock()
        mock_bus.emit = AsyncMock()

        with patch.dict("sys.modules", {
            "src.agent_memory": MagicMock(agent_memory=mock_memory),
            "src.brain": MagicMock(brain=mock_brain),
            "src.event_bus": MagicMock(event_bus=mock_bus),
        }):
            result = await pb.learn_from_interaction("test prompt", "test response")

        assert result["stored"] is True
        assert result["interaction_count"] == 1
        assert pb.memories_stored == 1
        assert len(pb.interactions) == 1

    @pytest.mark.asyncio
    async def test_with_tools(self):
        pb = PerplexityBridge()
        with patch.dict("sys.modules", {
            "src.agent_memory": MagicMock(agent_memory=MagicMock()),
            "src.brain": MagicMock(brain=MagicMock()),
            "src.event_bus": MagicMock(event_bus=MagicMock(emit=AsyncMock())),
        }):
            result = await pb.learn_from_interaction(
                "search", "found", tools_used=["web_search"],
            )
        assert result["stored"] is True
        assert pb.interactions[0].tools_used == ["web_search"]

    @pytest.mark.asyncio
    async def test_memory_error_graceful(self):
        pb = PerplexityBridge()
        mock_memory = MagicMock()
        mock_memory.store.side_effect = Exception("DB error")
        with patch.dict("sys.modules", {
            "src.agent_memory": MagicMock(agent_memory=mock_memory),
            "src.brain": MagicMock(brain=MagicMock()),
            "src.event_bus": MagicMock(event_bus=MagicMock(emit=AsyncMock())),
        }):
            result = await pb.learn_from_interaction("test", "response")
        # Should still work, just not store the memory
        assert result["stored"] is True
        assert pb.memories_stored == 0

    @pytest.mark.asyncio
    async def test_truncates_response(self):
        pb = PerplexityBridge()
        with patch.dict("sys.modules", {
            "src.agent_memory": MagicMock(agent_memory=MagicMock()),
            "src.brain": MagicMock(brain=MagicMock()),
            "src.event_bus": MagicMock(event_bus=MagicMock(emit=AsyncMock())),
        }):
            await pb.learn_from_interaction("q", "x" * 1000)
        assert len(pb.interactions[0].response_summary) == 500


# ===========================================================================
# PerplexityBridge — suggest_improvement
# ===========================================================================

class TestSuggestImprovement:
    @pytest.mark.asyncio
    async def test_stores_improvement(self):
        pb = PerplexityBridge()
        with patch.dict("sys.modules", {
            "src.agent_memory": MagicMock(agent_memory=MagicMock()),
            "src.event_bus": MagicMock(event_bus=MagicMock(emit=AsyncMock())),
        }):
            result = await pb.suggest_improvement("voice", "Add streaming STT")

        assert result["stored"] is True
        assert result["area"] == "voice"
        assert result["pending_improvements"] == 1
        assert len(pb.improvements_pending) == 1

    @pytest.mark.asyncio
    async def test_with_code_snippet(self):
        pb = PerplexityBridge()
        with patch.dict("sys.modules", {
            "src.agent_memory": MagicMock(agent_memory=MagicMock()),
            "src.event_bus": MagicMock(event_bus=MagicMock(emit=AsyncMock())),
        }):
            result = await pb.suggest_improvement(
                "trading", "Add stop loss", priority=9,
                code_snippet="def stop_loss(): pass",
            )
        assert pb.improvements_pending[0]["priority"] == 9
        assert pb.improvements_pending[0]["code_snippet"] is not None

    @pytest.mark.asyncio
    async def test_memory_error_graceful(self):
        pb = PerplexityBridge()
        mock_memory = MagicMock()
        mock_memory.store.side_effect = Exception("fail")
        with patch.dict("sys.modules", {
            "src.agent_memory": MagicMock(agent_memory=mock_memory),
            "src.event_bus": MagicMock(event_bus=MagicMock(emit=AsyncMock())),
        }):
            result = await pb.suggest_improvement("cluster", "Fix M2")
        assert result["stored"] is True  # still returns stored


# ===========================================================================
# PerplexityBridge — create_skill_from_analysis
# ===========================================================================

class TestCreateSkillFromAnalysis:
    @pytest.mark.asyncio
    async def test_success(self):
        pb = PerplexityBridge()
        mock_brain = MagicMock()
        with patch.dict("sys.modules", {
            "src.brain": MagicMock(brain=mock_brain),
            "src.event_bus": MagicMock(event_bus=MagicMock(emit=AsyncMock())),
        }):
            result = await pb.create_skill_from_analysis(
                name="auto_search", description="Auto web search",
                triggers=["search", "find"], steps=[{"action": "web_search"}],
            )
        assert result["created"] is True
        assert result["name"] == "auto_search"
        assert pb.skills_created == 1

    @pytest.mark.asyncio
    async def test_brain_error(self):
        pb = PerplexityBridge()
        mock_brain = MagicMock()
        mock_brain.create_skill.side_effect = Exception("DB error")
        with patch.dict("sys.modules", {
            "src.brain": MagicMock(brain=mock_brain),
            "src.event_bus": MagicMock(event_bus=MagicMock(emit=AsyncMock())),
        }):
            result = await pb.create_skill_from_analysis(
                name="bad_skill", description="x",
                triggers=["x"], steps=[],
            )
        assert result["created"] is False
        assert "error" in result


# ===========================================================================
# PerplexityBridge — get_context_for_query
# ===========================================================================

class TestGetContextForQuery:
    @pytest.mark.asyncio
    async def test_basic(self):
        pb = PerplexityBridge()
        with patch.dict("sys.modules", {
            "src.agent_memory": MagicMock(agent_memory=MagicMock(search=MagicMock(return_value=[]))),
        }):
            ctx = await pb.get_context_for_query("test query")
        assert ctx["query"] == "test query"
        assert ctx["recent_interactions"] == []
        assert ctx["pending_improvements"] == 0

    @pytest.mark.asyncio
    async def test_with_interactions(self):
        pb = PerplexityBridge()
        pb.interactions = [
            InteractionRecord("q1", "r1", tools_used=["tool1"]),
            InteractionRecord("q2", "r2", tools_used=["tool2"]),
        ]
        with patch.dict("sys.modules", {
            "src.agent_memory": MagicMock(agent_memory=MagicMock(search=MagicMock(return_value=[]))),
        }):
            ctx = await pb.get_context_for_query("find something")
        assert len(ctx["recent_interactions"]) == 2

    @pytest.mark.asyncio
    async def test_memory_error_graceful(self):
        pb = PerplexityBridge()
        with patch.dict("sys.modules", {
            "src.agent_memory": MagicMock(agent_memory=MagicMock(
                search=MagicMock(side_effect=Exception("fail"))
            )),
        }):
            ctx = await pb.get_context_for_query("test")
        assert ctx["relevant_memories"] == []

    @pytest.mark.asyncio
    async def test_truncates_query(self):
        pb = PerplexityBridge()
        with patch.dict("sys.modules", {
            "src.agent_memory": MagicMock(agent_memory=MagicMock(search=MagicMock(return_value=[]))),
        }):
            ctx = await pb.get_context_for_query("x" * 500)
        assert len(ctx["query"]) == 200


# ===========================================================================
# PerplexityBridge — _analyze_for_skill
# ===========================================================================

class TestAnalyzeForSkill:
    @pytest.mark.asyncio
    async def test_too_few_interactions(self):
        pb = PerplexityBridge()
        pb.interactions = [InteractionRecord("q", "r")]
        record = InteractionRecord("q2", "r2")
        result = await pb._analyze_for_skill(record)
        assert result is None

    @pytest.mark.asyncio
    async def test_no_frequent_tools(self):
        pb = PerplexityBridge()
        pb.interactions = [
            InteractionRecord("q1", "r1", tools_used=["a"]),
            InteractionRecord("q2", "r2", tools_used=["b"]),
            InteractionRecord("q3", "r3", tools_used=["c"]),
        ]
        result = await pb._analyze_for_skill(pb.interactions[-1])
        assert result is None

    @pytest.mark.asyncio
    async def test_frequent_tools_detected(self):
        pb = PerplexityBridge()
        pb.interactions = [
            InteractionRecord("q1", "r1", tools_used=["web_search"]),
            InteractionRecord("q2", "r2", tools_used=["web_search"]),
            InteractionRecord("q3", "r3", tools_used=["web_search"]),
        ]
        result = await pb._analyze_for_skill(pb.interactions[-1])
        assert result is not None
        assert "web_search" in result


# ===========================================================================
# PerplexityBridge — status
# ===========================================================================

class TestStatus:
    def test_empty(self):
        pb = PerplexityBridge()
        s = pb.status()
        assert s["total_interactions"] == 0
        assert s["memories_stored"] == 0
        assert s["skills_created"] == 0
        assert s["improvements_pending"] == 0
        assert s["recent_tools"] == []

    def test_with_data(self):
        pb = PerplexityBridge()
        pb.interactions = [
            InteractionRecord("q", "r", tools_used=["web_search", "code_gen"]),
        ]
        pb.memories_stored = 5
        pb.skills_created = 2
        pb.improvements_pending = [{"area": "voice"}]
        s = pb.status()
        assert s["total_interactions"] == 1
        assert s["memories_stored"] == 5
        assert s["skills_created"] == 2
        assert s["improvements_pending"] == 1
        assert set(s["recent_tools"]) == {"web_search", "code_gen"}


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert perplexity_bridge is not None
        assert isinstance(perplexity_bridge, PerplexityBridge)
