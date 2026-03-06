"""Tests for JARVIS agents module.

Uses importlib.reload to avoid state pollution from other test modules
that mock claude_agent_sdk.
"""

import sys
import importlib
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# Ensure clean claude_agent_sdk before first import
if "claude_agent_sdk" in sys.modules:
    _saved_sdk = sys.modules["claude_agent_sdk"]
    if isinstance(_saved_sdk, MagicMock):
        del sys.modules["claude_agent_sdk"]

try:
    from src.agents import JARVIS_AGENTS
    HAS_SDK = True
except ImportError:
    HAS_SDK = False
    JARVIS_AGENTS = {}

pytestmark = pytest.mark.skipif(not HAS_SDK, reason="claude_agent_sdk not installed")


@pytest.fixture(scope="module")
def agents():
    """Load agents once per module, handling mock pollution."""
    # If claude_agent_sdk was mocked by another test, purge and reload
    if "claude_agent_sdk" in sys.modules and isinstance(sys.modules["claude_agent_sdk"], MagicMock):
        del sys.modules["claude_agent_sdk"]
    if "src.agents" in sys.modules:
        importlib.reload(sys.modules["src.agents"])
    from src.agents import JARVIS_AGENTS
    return JARVIS_AGENTS


class TestAgentRegistry:
    def test_agent_count(self, agents):
        assert len(agents) == 13

    def test_original_agents_present(self, agents):
        for name in ["ia-deep", "ia-fast", "ia-check", "ia-trading",
                      "ia-system", "ia-bridge", "ia-consensus", "ia-dict"]:
            assert name in agents, f"Missing: {name}"

    def test_new_agents_present(self, agents):
        for name in ["ia-research", "ia-devops", "ia-security", "ia-data", "ia-creative"]:
            assert name in agents, f"Missing: {name}"

    def test_agents_have_tools(self, agents):
        for name, agent in agents.items():
            assert len(agent.tools) > 0, f"{name} has no tools"

    def test_agents_have_prompt(self, agents):
        for name, agent in agents.items():
            assert len(agent.prompt) > 50, f"{name} prompt too short"

    def test_agents_have_model(self, agents):
        valid = {"opus", "sonnet", "haiku"}
        for name, agent in agents.items():
            assert agent.model in valid, f"{name}: invalid model {agent.model}"

    def test_ia_deep_uses_opus(self, agents):
        assert agents["ia-deep"].model == "opus"

    def test_ia_fast_uses_haiku(self, agents):
        assert agents["ia-fast"].model == "haiku"

    def test_ia_security_has_security_tools(self, agents):
        assert "Read" in agents["ia-security"].tools
        assert "Grep" in agents["ia-security"].tools

    def test_ia_data_has_sql_tools(self, agents):
        assert "mcp__jarvis__sql_query" in agents["ia-data"].tools

    def test_ia_research_has_web_tools(self, agents):
        a = agents["ia-research"]
        assert "WebSearch" in a.tools or "mcp__jarvis__ollama_web_search" in a.tools
