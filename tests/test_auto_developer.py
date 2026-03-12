"""Tests for src/auto_developer.py — Autonomous code generation pipeline.

Covers: GapAnalysis, GeneratedCommand dataclasses, AutoDeveloper
(analyze_gaps, generate_command, test_generated, _register_command,
run_cycle, _save_state, get_stats), auto_developer singleton.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.auto_developer import GapAnalysis, GeneratedCommand, AutoDeveloper, auto_developer


# ===========================================================================
# GapAnalysis
# ===========================================================================

class TestGapAnalysis:
    def test_defaults(self):
        g = GapAnalysis(pattern="ouvre spotify", count=5, examples=["ouvre spotify"])
        assert g.category == "unknown"
        assert g.description == ""

    def test_with_all_fields(self):
        g = GapAnalysis(
            pattern="lance music", count=3,
            examples=["lance music", "joue music"],
            category="media", description="Play music",
        )
        assert g.category == "media"


# ===========================================================================
# GeneratedCommand
# ===========================================================================

class TestGeneratedCommand:
    def test_defaults(self):
        cmd = GeneratedCommand(
            name="play_music", category="media",
            description="Play music", triggers=["joue musique"],
            action_type="app_open", action="spotify",
        )
        assert cmd.source == "auto_developer"
        assert cmd.confidence == 0.0
        assert cmd.tested is False

    def test_with_confidence(self):
        cmd = GeneratedCommand(
            "cmd", "cat", "desc", ["t"], "powershell", "echo hi",
            confidence=0.85, tested=True,
        )
        assert cmd.confidence == 0.85
        assert cmd.tested is True


# ===========================================================================
# AutoDeveloper — init
# ===========================================================================

class TestInit:
    def test_defaults(self):
        dev = AutoDeveloper()
        assert dev._generated == []
        assert dev._cycle_log == []

    def test_singleton(self):
        assert auto_developer is not None
        assert isinstance(auto_developer, AutoDeveloper)


# ===========================================================================
# AutoDeveloper — test_generated
# ===========================================================================

class TestTestGenerated:
    @pytest.mark.asyncio
    async def test_valid_command(self):
        dev = AutoDeveloper()
        cmd = GeneratedCommand(
            name="test_cmd", category="systeme",
            description="Test", triggers=["test"],
            action_type="powershell", action="echo hello",
        )
        assert await dev.test_generated(cmd) is True
        assert cmd.tested is True

    @pytest.mark.asyncio
    async def test_empty_name(self):
        dev = AutoDeveloper()
        cmd = GeneratedCommand("", "cat", "desc", ["t"], "powershell", "echo")
        assert await dev.test_generated(cmd) is False

    @pytest.mark.asyncio
    async def test_empty_triggers(self):
        dev = AutoDeveloper()
        cmd = GeneratedCommand("cmd", "cat", "desc", [], "powershell", "echo")
        assert await dev.test_generated(cmd) is False

    @pytest.mark.asyncio
    async def test_empty_action(self):
        dev = AutoDeveloper()
        cmd = GeneratedCommand("cmd", "cat", "desc", ["t"], "powershell", "")
        assert await dev.test_generated(cmd) is False

    @pytest.mark.asyncio
    async def test_invalid_action_type(self):
        dev = AutoDeveloper()
        cmd = GeneratedCommand("cmd", "cat", "desc", ["t"], "invalid_type", "echo")
        assert await dev.test_generated(cmd) is False

    @pytest.mark.asyncio
    async def test_dangerous_rm_rf(self):
        dev = AutoDeveloper()
        cmd = GeneratedCommand("cmd", "cat", "desc", ["t"], "bash", "rm -rf /")
        assert await dev.test_generated(cmd) is False

    @pytest.mark.asyncio
    async def test_dangerous_format(self):
        dev = AutoDeveloper()
        cmd = GeneratedCommand("cmd", "cat", "desc", ["t"], "powershell", "format C:")
        assert await dev.test_generated(cmd) is False

    @pytest.mark.asyncio
    async def test_dangerous_shutdown(self):
        dev = AutoDeveloper()
        cmd = GeneratedCommand("cmd", "cat", "desc", ["t"], "powershell", "Stop-Computer -Force")
        assert await dev.test_generated(cmd) is False

    @pytest.mark.asyncio
    async def test_valid_action_types(self):
        dev = AutoDeveloper()
        for atype in ("powershell", "hotkey", "python", "browser", "app_open",
                       "bash", "ms_settings", "pipeline", "script"):
            cmd = GeneratedCommand("cmd", "cat", "desc", ["t"], atype, "safe_action")
            assert await dev.test_generated(cmd) is True


# ===========================================================================
# AutoDeveloper — _register_command
# ===========================================================================

class TestRegisterCommand:
    def test_register_new(self):
        dev = AutoDeveloper()
        cmd = GeneratedCommand("new_cmd", "systeme", "desc", ["trigger"], "powershell", "echo")

        mock_commands = []
        with patch("src.commands.COMMANDS", mock_commands), \
             patch("src.commands.JarvisCommand") as MockJC:
            MockJC.return_value = MagicMock()
            result = dev._register_command(cmd)

        assert result is True

    def test_name_collision_auto_prefix(self):
        dev = AutoDeveloper()
        cmd = GeneratedCommand("existing", "systeme", "desc", ["trigger"], "powershell", "echo")

        existing_cmd = MagicMock()
        existing_cmd.name = "existing"
        mock_commands = [existing_cmd]

        with patch("src.commands.COMMANDS", mock_commands), \
             patch("src.commands.JarvisCommand") as MockJC:
            MockJC.return_value = MagicMock()
            result = dev._register_command(cmd)

        # Should have been renamed to auto_existing
        assert cmd.name == "auto_existing"


# ===========================================================================
# AutoDeveloper — generate_command
# ===========================================================================

class TestGenerateCommand:
    @pytest.mark.asyncio
    async def test_no_cluster_response(self):
        dev = AutoDeveloper()
        gap = GapAnalysis("test", 3, ["test"])

        with patch.object(dev, "_cluster_query", new_callable=AsyncMock, return_value=None):
            result = await dev.generate_command(gap)

        assert result is None

    @pytest.mark.asyncio
    async def test_valid_json_response(self):
        dev = AutoDeveloper()
        gap = GapAnalysis("ouvre spotify", 5, ["ouvre spotify"])
        json_response = '{"name": "open_spotify", "category": "app", "description": "Open Spotify", "triggers": ["ouvre spotify"], "action_type": "app_open", "action": "spotify"}'

        with patch.object(dev, "_cluster_query", new_callable=AsyncMock, return_value=json_response):
            result = await dev.generate_command(gap)

        assert result is not None
        assert result.name == "open_spotify"
        assert result.action_type == "app_open"
        assert result.confidence == 0.7

    @pytest.mark.asyncio
    async def test_invalid_json_response(self):
        dev = AutoDeveloper()
        gap = GapAnalysis("test", 3, ["test"])

        with patch.object(dev, "_cluster_query", new_callable=AsyncMock, return_value="not json"):
            result = await dev.generate_command(gap)

        assert result is None

    @pytest.mark.asyncio
    async def test_code_block_json(self):
        dev = AutoDeveloper()
        gap = GapAnalysis("test", 3, ["test"])
        response = '```json\n{"name": "test_cmd", "category": "systeme", "description": "Test", "triggers": ["test"], "action_type": "powershell", "action": "echo test"}\n```'

        with patch.object(dev, "_cluster_query", new_callable=AsyncMock, return_value=response):
            result = await dev.generate_command(gap)

        assert result is not None
        assert result.name == "test_cmd"


# ===========================================================================
# AutoDeveloper — _save_state / get_stats
# ===========================================================================

class TestStateAndStats:
    def test_get_stats_empty(self):
        dev = AutoDeveloper()
        stats = dev.get_stats()
        assert stats["generated_commands"] == 0
        assert stats["total_cycles"] == 0
        assert stats["last_cycle"] is None

    def test_get_stats_with_data(self):
        dev = AutoDeveloper()
        dev._generated = [MagicMock(), MagicMock()]
        dev._cycle_log = [{"gaps": 3, "generated": 2}]
        stats = dev.get_stats()
        assert stats["generated_commands"] == 2
        assert stats["total_cycles"] == 1

    def test_save_state_no_crash(self):
        dev = AutoDeveloper()
        with patch.object(Path, "write_text"):
            with patch.object(Path, "mkdir"):
                dev._save_state()


# ===========================================================================
# AutoDeveloper — run_cycle
# ===========================================================================

class TestRunCycle:
    @pytest.mark.asyncio
    async def test_no_gaps(self):
        dev = AutoDeveloper()
        with patch.object(dev, "analyze_gaps", new_callable=AsyncMock, return_value=[]), \
             patch.object(dev, "_save_state"):
            report = await dev.run_cycle()
        assert report["gaps"] == 0
        assert report["generated"] == 0
        assert report["duration_s"] >= 0

    @pytest.mark.asyncio
    async def test_full_cycle(self):
        dev = AutoDeveloper()
        gaps = [GapAnalysis("ouvre spotify", 5, ["ouvre spotify"])]
        cmd = GeneratedCommand("open_spotify", "app", "Open", ["ouvre spotify"], "app_open", "spotify")

        with patch.object(dev, "analyze_gaps", new_callable=AsyncMock, return_value=gaps), \
             patch.object(dev, "generate_command", new_callable=AsyncMock, return_value=cmd), \
             patch.object(dev, "test_generated", new_callable=AsyncMock, return_value=True), \
             patch.object(dev, "_register_command", return_value=True), \
             patch.object(dev, "_save_state"):
            report = await dev.run_cycle(max_gaps=1)

        assert report["gaps"] == 1
        assert report["generated"] == 1
        assert report["tested"] == 1
        assert report["registered"] == 1
