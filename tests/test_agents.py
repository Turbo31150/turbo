"""Tests for JARVIS agents module."""

import pytest

try:
    from src.agents import JARVIS_AGENTS
    HAS_SDK = True
except ImportError:
    HAS_SDK = False
    JARVIS_AGENTS = {}

pytestmark = pytest.mark.skipif(not HAS_SDK, reason="claude_agent_sdk not installed")


class TestAgentRegistry:
    def test_agent_count(self):
        """v10.4 should have 13 agents (8 original + 5 new)."""
        assert len(JARVIS_AGENTS) == 13

    def test_original_agents_present(self):
        original = ["ia-deep", "ia-fast", "ia-check", "ia-trading",
                     "ia-system", "ia-bridge", "ia-consensus", "ia-dict"]
        for name in original:
            assert name in JARVIS_AGENTS, f"Missing original agent: {name}"

    def test_new_agents_present(self):
        new = ["ia-research", "ia-devops", "ia-security", "ia-data", "ia-creative"]
        for name in new:
            assert name in JARVIS_AGENTS, f"Missing new agent: {name}"

    def test_agents_have_tools(self):
        for name, agent in JARVIS_AGENTS.items():
            assert len(agent.tools) > 0, f"Agent {name} has no tools"

    def test_agents_have_prompt(self):
        for name, agent in JARVIS_AGENTS.items():
            assert len(agent.prompt) > 50, f"Agent {name} prompt too short"

    def test_agents_have_model(self):
        valid_models = {"opus", "sonnet", "haiku"}
        for name, agent in JARVIS_AGENTS.items():
            assert agent.model in valid_models, f"Agent {name} has invalid model: {agent.model}"

    def test_ia_deep_uses_opus(self):
        assert JARVIS_AGENTS["ia-deep"].model == "opus"

    def test_ia_fast_uses_haiku(self):
        assert JARVIS_AGENTS["ia-fast"].model == "haiku"

    def test_ia_security_has_security_tools(self):
        agent = JARVIS_AGENTS["ia-security"]
        assert "Read" in agent.tools
        assert "Grep" in agent.tools

    def test_ia_data_has_sql_tools(self):
        agent = JARVIS_AGENTS["ia-data"]
        assert "mcp__jarvis__sql_query" in agent.tools

    def test_ia_research_has_web_tools(self):
        agent = JARVIS_AGENTS["ia-research"]
        assert "WebSearch" in agent.tools or "mcp__jarvis__ollama_web_search" in agent.tools
