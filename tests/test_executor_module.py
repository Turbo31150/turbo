"""Tests for JARVIS Executor module -- src/executor.py

Covers: execute_command (all action_types), execute_skill_step, execute_skill,
        process_voice_input, correct_with_ia, _execute_pipeline, _postprocess_trading_script,
        _execute_hotkey, edge cases (unknown command, exceptions, timeouts).

All external dependencies (run_powershell, commands, skills, config, httpx) are mocked.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Project root on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Lightweight stubs for dataclasses used by executor
# ---------------------------------------------------------------------------

@dataclass
class FakeJarvisCommand:
    """Minimal JarvisCommand stub matching src/commands.JarvisCommand."""
    name: str = "test_cmd"
    category: str = "test"
    description: str = "Test command"
    triggers: list = field(default_factory=list)
    action_type: str = "exit"
    action: str = ""
    params: list = field(default_factory=list)
    confirm: bool = False


@dataclass
class FakeSkillStep:
    """Minimal SkillStep stub matching src/skills.SkillStep."""
    tool: str = "test_tool"
    args: dict = field(default_factory=dict)
    description: str = ""
    wait_for_result: bool = True


@dataclass
class FakeSkill:
    """Minimal Skill stub matching src/skills.Skill."""
    name: str = "test_skill"
    description: str = "A test skill"
    triggers: list = field(default_factory=list)
    steps: list = field(default_factory=list)
    category: str = "custom"
    created_at: float = 0.0
    usage_count: int = 0
    last_used: float = 0.0
    success_rate: float = 1.0


# ---------------------------------------------------------------------------
# Module-level mock setup -- mock heavy dependencies before importing executor
# ---------------------------------------------------------------------------

_mock_commands = MagicMock()
_mock_commands.JarvisCommand = FakeJarvisCommand
_mock_commands.APP_PATHS = {"notepad": "notepad.exe", "chrome": "chrome.exe"}
_mock_commands.SITE_ALIASES = {"google": "https://www.google.com"}
_mock_commands.match_command = MagicMock(return_value=(None, {}, 0.0))
_mock_commands.correct_voice_text = MagicMock(side_effect=lambda t: t)
_mock_commands.format_commands_help = MagicMock(return_value="Aide: commandes disponibles")
_mock_commands.record_command_execution = MagicMock()

_mock_windows = MagicMock()
_mock_windows.run_powershell = MagicMock(return_value={"success": True, "stdout": "OK", "stderr": ""})

_mock_config = MagicMock()
_mock_config.SCRIPTS = {}

_mock_signal_formatter = MagicMock()
_mock_signal_formatter.parse_sniper_json = MagicMock(return_value=None)
_mock_signal_formatter.format_telegram_signals = MagicMock(return_value="signals")
_mock_signal_formatter.format_chat_signals = MagicMock(return_value="chat signals")

_mock_skills = MagicMock()
_mock_skills.log_action = MagicMock()
_mock_skills.record_skill_use = MagicMock()
_mock_skills.SkillStep = FakeSkillStep
_mock_skills.Skill = FakeSkill

_mock_intent = MagicMock()
_mock_intent.intent_classifier = MagicMock()
_mock_intent.intent_classifier.classify_single = MagicMock(return_value={"intent": "command", "confidence": 0.9})


@pytest.fixture(autouse=True)
def _patch_executor_deps():
    """Patch all heavy imports before importing/reloading executor."""
    patches = {
        "src.commands": _mock_commands,
        "src.windows": _mock_windows,
        "src.config": _mock_config,
        "src.signal_formatter": _mock_signal_formatter,
        "src.skills": _mock_skills,
        "src.intent_classifier": _mock_intent,
    }
    with patch.dict("sys.modules", patches):
        # Force reimport to pick up mocked modules
        if "src.executor" in sys.modules:
            del sys.modules["src.executor"]
        import src.executor  # noqa: F401
        # Reset mocks before each test
        _mock_windows.run_powershell.reset_mock()
        _mock_windows.run_powershell.return_value = {"success": True, "stdout": "OK", "stderr": ""}
        _mock_commands.match_command.reset_mock()
        _mock_commands.correct_voice_text.reset_mock()
        _mock_commands.correct_voice_text.side_effect = lambda t: t
        _mock_commands.format_commands_help.reset_mock()
        _mock_commands.format_commands_help.return_value = "Aide: commandes disponibles"
        _mock_commands.record_command_execution.reset_mock()
        _mock_skills.log_action.reset_mock()
        _mock_skills.record_skill_use.reset_mock()
        _mock_signal_formatter.parse_sniper_json.reset_mock()
        _mock_signal_formatter.parse_sniper_json.return_value = None
        yield


def _get_executor():
    """Return the patched executor module."""
    return sys.modules["src.executor"]


# =========================================================================
# 1. execute_command -- action_type routing
# =========================================================================

class TestExecuteCommandExit:
    """action_type == 'exit' returns __EXIT__."""

    @pytest.mark.asyncio
    async def test_exit(self):
        mod = _get_executor()
        cmd = FakeJarvisCommand(action_type="exit")
        result = await mod.execute_command(cmd, {})
        assert result == "__EXIT__"


class TestExecuteCommandListCommands:
    """action_type == 'list_commands' calls format_commands_help."""

    @pytest.mark.asyncio
    async def test_list_commands(self):
        mod = _get_executor()
        cmd = FakeJarvisCommand(action_type="list_commands")
        result = await mod.execute_command(cmd, {})
        assert result == "Aide: commandes disponibles"
        _mock_commands.format_commands_help.assert_called_once()


class TestExecuteCommandRepeat:
    """action_type == 'jarvis_repeat' returns __REPEAT__."""

    @pytest.mark.asyncio
    async def test_repeat(self):
        mod = _get_executor()
        cmd = FakeJarvisCommand(action_type="jarvis_repeat")
        result = await mod.execute_command(cmd, {})
        assert result == "__REPEAT__"


class TestExecuteCommandAppOpen:
    """action_type == 'app_open' opens an app via run_powershell."""

    @pytest.mark.asyncio
    async def test_app_open_success(self):
        mod = _get_executor()
        cmd = FakeJarvisCommand(action_type="app_open", action="notepad")
        result = await mod.execute_command(cmd, {})
        assert "notepad" in result.lower() or "ouverte" in result.lower()
        _mock_windows.run_powershell.assert_called_once()

    @pytest.mark.asyncio
    async def test_app_open_failure(self):
        _mock_windows.run_powershell.return_value = {"success": False, "stdout": "", "stderr": "Not found"}
        mod = _get_executor()
        cmd = FakeJarvisCommand(action_type="app_open", action="notepad")
        result = await mod.execute_command(cmd, {})
        assert "impossible" in result.lower() or "Not found" in result

    @pytest.mark.asyncio
    async def test_app_open_with_params(self):
        mod = _get_executor()
        cmd = FakeJarvisCommand(action_type="app_open", action="{app}")
        result = await mod.execute_command(cmd, {"app": "chrome"})
        assert "chrome" in result.lower() or "ouverte" in result.lower()


class TestExecuteCommandMsSettings:
    """action_type == 'ms_settings' opens a settings URI."""

    @pytest.mark.asyncio
    async def test_ms_settings_success(self):
        mod = _get_executor()
        cmd = FakeJarvisCommand(action_type="ms_settings", action="ms-settings:display")
        result = await mod.execute_command(cmd, {})
        assert "ms-settings:display" in result
        assert "ouverts" in result.lower() or "parametres" in result.lower()

    @pytest.mark.asyncio
    async def test_ms_settings_failure(self):
        _mock_windows.run_powershell.return_value = {"success": False, "stdout": "", "stderr": "access denied"}
        mod = _get_executor()
        cmd = FakeJarvisCommand(action_type="ms_settings", action="ms-settings:display")
        result = await mod.execute_command(cmd, {})
        assert "erreur" in result.lower() or "access denied" in result


class TestExecuteCommandHotkey:
    """action_type == 'hotkey' runs a hotkey through _execute_hotkey."""

    @pytest.mark.asyncio
    async def test_hotkey_known(self):
        mod = _get_executor()
        cmd = FakeJarvisCommand(action_type="hotkey", action="media_play_pause")
        result = await mod.execute_command(cmd, {})
        assert "media_play_pause" in result
        assert "execute" in result.lower()

    @pytest.mark.asyncio
    async def test_hotkey_unknown(self):
        mod = _get_executor()
        cmd = FakeJarvisCommand(action_type="hotkey", action="nonexistent_key")
        result = await mod.execute_command(cmd, {})
        assert "inconnu" in result.lower()

    @pytest.mark.asyncio
    async def test_hotkey_failure(self):
        _mock_windows.run_powershell.return_value = {"success": False, "stdout": "", "stderr": "error hotkey"}
        mod = _get_executor()
        cmd = FakeJarvisCommand(action_type="hotkey", action="ctrl+c")
        result = await mod.execute_command(cmd, {})
        assert "erreur" in result.lower()

    @pytest.mark.asyncio
    async def test_hotkey_with_param_substitution(self):
        mod = _get_executor()
        cmd = FakeJarvisCommand(action_type="hotkey", action="{key}")
        result = await mod.execute_command(cmd, {"key": "volume_up"})
        assert "volume_up" in result
        assert "execute" in result.lower()


class TestExecuteCommandBrowser:
    """action_type == 'browser' handles navigate: and search:."""

    @pytest.mark.asyncio
    async def test_browser_navigate_full_url(self):
        mod = _get_executor()
        cmd = FakeJarvisCommand(action_type="browser", action="navigate:https://example.com")
        result = await mod.execute_command(cmd, {})
        assert "example.com" in result
        assert "navigation" in result.lower()

    @pytest.mark.asyncio
    async def test_browser_navigate_alias(self):
        mod = _get_executor()
        cmd = FakeJarvisCommand(action_type="browser", action="navigate:google")
        result = await mod.execute_command(cmd, {})
        assert "google" in result.lower()

    @pytest.mark.asyncio
    async def test_browser_navigate_bare_domain(self):
        mod = _get_executor()
        cmd = FakeJarvisCommand(action_type="browser", action="navigate:example.com")
        result = await mod.execute_command(cmd, {})
        # Should prepend https://
        call_args = _mock_windows.run_powershell.call_args[0][0]
        assert "https://example.com" in call_args

    @pytest.mark.asyncio
    async def test_browser_navigate_failure(self):
        _mock_windows.run_powershell.return_value = {"success": False, "stdout": "", "stderr": "chrome not found"}
        mod = _get_executor()
        cmd = FakeJarvisCommand(action_type="browser", action="navigate:example.com")
        result = await mod.execute_command(cmd, {})
        assert "erreur" in result.lower()

    @pytest.mark.asyncio
    async def test_browser_search(self):
        mod = _get_executor()
        cmd = FakeJarvisCommand(action_type="browser", action="search:python asyncio")
        result = await mod.execute_command(cmd, {})
        assert "python asyncio" in result
        assert "recherche" in result.lower()

    @pytest.mark.asyncio
    async def test_browser_search_failure(self):
        _mock_windows.run_powershell.return_value = {"success": False, "stdout": "", "stderr": "err"}
        mod = _get_executor()
        cmd = FakeJarvisCommand(action_type="browser", action="search:test")
        result = await mod.execute_command(cmd, {})
        assert "erreur" in result.lower()

    @pytest.mark.asyncio
    async def test_browser_with_params(self):
        mod = _get_executor()
        cmd = FakeJarvisCommand(action_type="browser", action="search:{query}")
        result = await mod.execute_command(cmd, {"query": "hello world"})
        assert "hello world" in result


class TestExecuteCommandPowershell:
    """action_type == 'powershell' runs arbitrary PowerShell."""

    @pytest.mark.asyncio
    async def test_powershell_success(self):
        _mock_windows.run_powershell.return_value = {"success": True, "stdout": "hello", "stderr": ""}
        mod = _get_executor()
        cmd = FakeJarvisCommand(action_type="powershell", action="echo hello")
        result = await mod.execute_command(cmd, {})
        assert "hello" in result
        assert "executee" in result.lower()

    @pytest.mark.asyncio
    async def test_powershell_success_empty_stdout(self):
        _mock_windows.run_powershell.return_value = {"success": True, "stdout": "", "stderr": ""}
        mod = _get_executor()
        cmd = FakeJarvisCommand(action_type="powershell", action="echo hello")
        result = await mod.execute_command(cmd, {})
        assert "OK" in result

    @pytest.mark.asyncio
    async def test_powershell_truncates_long_output(self):
        _mock_windows.run_powershell.return_value = {"success": True, "stdout": "x" * 300, "stderr": ""}
        mod = _get_executor()
        cmd = FakeJarvisCommand(action_type="powershell", action="long output")
        result = await mod.execute_command(cmd, {})
        # stdout[:200]
        assert len(result) < 300

    @pytest.mark.asyncio
    async def test_powershell_failure(self):
        _mock_windows.run_powershell.return_value = {"success": False, "stdout": "", "stderr": "access denied"}
        mod = _get_executor()
        cmd = FakeJarvisCommand(action_type="powershell", action="restricted")
        result = await mod.execute_command(cmd, {})
        assert "erreur" in result.lower()

    @pytest.mark.asyncio
    async def test_powershell_param_substitution_escapes_quotes(self):
        mod = _get_executor()
        cmd = FakeJarvisCommand(action_type="powershell", action="echo '{msg}'")
        result = await mod.execute_command(cmd, {"msg": "it's done"})
        call_args = _mock_windows.run_powershell.call_args[0][0]
        assert "it''s done" in call_args  # single quotes escaped


class TestExecuteCommandScript:
    """action_type == 'script' runs a Python script."""

    @pytest.mark.asyncio
    async def test_script_not_found(self):
        mod = _get_executor()
        mod.SCRIPTS = {}
        cmd = FakeJarvisCommand(action_type="script", action="nonexistent")
        result = await mod.execute_command(cmd, {})
        assert "introuvable" in result.lower()

    @pytest.mark.asyncio
    async def test_script_path_not_exists(self):
        fake_path = MagicMock()
        fake_path.exists.return_value = False
        mod = _get_executor()
        mod.SCRIPTS = {"myscript": fake_path}
        cmd = FakeJarvisCommand(action_type="script", action="myscript")
        result = await mod.execute_command(cmd, {})
        assert "introuvable" in result.lower()

    @pytest.mark.asyncio
    async def test_script_success(self):
        fake_path = MagicMock()
        fake_path.exists.return_value = True
        fake_path.parent = Path("/fake")
        fake_result = MagicMock()
        fake_result.stdout = "Script output"
        fake_result.returncode = 0
        mod = _get_executor()
        mod.SCRIPTS = {"myscript": fake_path}

        async def fake_to_thread(fn, *args, **kwargs):
            return fake_result

        with patch.object(asyncio, "to_thread", side_effect=fake_to_thread):
            cmd = FakeJarvisCommand(action_type="script", action="myscript")
            result = await mod.execute_command(cmd, {})
        assert "myscript" in result
        assert "termine" in result.lower()

    @pytest.mark.asyncio
    async def test_script_timeout(self):
        fake_path = MagicMock()
        fake_path.exists.return_value = True
        fake_path.parent = Path("/fake")
        mod = _get_executor()
        mod.SCRIPTS = {"slow": fake_path}

        async def fake_to_thread(fn, *args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="test", timeout=600)

        with patch.object(asyncio, "to_thread", side_effect=fake_to_thread):
            cmd = FakeJarvisCommand(action_type="script", action="slow")
            result = await mod.execute_command(cmd, {})
        assert "timeout" in result.lower()

    @pytest.mark.asyncio
    async def test_script_os_error(self):
        fake_path = MagicMock()
        fake_path.exists.return_value = True
        fake_path.parent = Path("/fake")
        mod = _get_executor()
        mod.SCRIPTS = {"broken": fake_path}

        async def fake_to_thread(fn, *args, **kwargs):
            raise OSError("Permission denied")

        with patch.object(asyncio, "to_thread", side_effect=fake_to_thread):
            cmd = FakeJarvisCommand(action_type="script", action="broken")
            result = await mod.execute_command(cmd, {})
        assert "erreur" in result.lower()

    @pytest.mark.asyncio
    async def test_script_truncates_long_output(self):
        fake_path = MagicMock()
        fake_path.exists.return_value = True
        fake_path.parent = Path("/fake")
        fake_result = MagicMock()
        fake_result.stdout = "x" * 1000
        fake_result.returncode = 0
        mod = _get_executor()
        mod.SCRIPTS = {"big": fake_path}

        async def fake_to_thread(fn, *args, **kwargs):
            return fake_result

        with patch.object(asyncio, "to_thread", side_effect=fake_to_thread):
            cmd = FakeJarvisCommand(action_type="script", action="big")
            result = await mod.execute_command(cmd, {})
        # Output truncated to last 500 chars
        assert len(result) < 600

    @pytest.mark.asyncio
    async def test_script_trading_postprocess(self):
        """Trading scripts get special JSON parsing."""
        fake_path = MagicMock()
        fake_path.exists.return_value = True
        fake_path.parent = Path("/fake")
        fake_result = MagicMock()
        fake_result.stdout = '{"signals": [{"pair": "BTC"}]}'
        fake_result.returncode = 0
        _mock_signal_formatter.parse_sniper_json.return_value = {"signals": [{"pair": "BTC"}]}
        _mock_signal_formatter.format_chat_signals.return_value = "BTC signal detected"
        mod = _get_executor()
        mod.SCRIPTS = {"scan_sniper": fake_path}

        async def fake_to_thread(fn, *args, **kwargs):
            return fake_result

        with patch.object(asyncio, "to_thread", side_effect=fake_to_thread):
            # Mock trading telegram import inside _postprocess_trading_script
            with patch.dict("sys.modules", {"src.trading": MagicMock()}):
                cmd = FakeJarvisCommand(action_type="script", action="scan_sniper")
                result = await mod.execute_command(cmd, {})
        assert result == "BTC signal detected"


class TestExecuteCommandJarvisTool:
    """action_type == 'jarvis_tool' returns __TOOL__ prefix."""

    @pytest.mark.asyncio
    async def test_jarvis_tool(self):
        mod = _get_executor()
        cmd = FakeJarvisCommand(action_type="jarvis_tool", action="status")
        result = await mod.execute_command(cmd, {})
        assert result == "__TOOL__status"

    @pytest.mark.asyncio
    async def test_jarvis_tool_with_params(self):
        mod = _get_executor()
        cmd = FakeJarvisCommand(action_type="jarvis_tool", action="{action}_now")
        result = await mod.execute_command(cmd, {"action": "restart"})
        assert result == "__TOOL__restart_now"


class TestExecuteCommandUnknownType:
    """Unknown action_type returns error message."""

    @pytest.mark.asyncio
    async def test_unknown_action_type(self):
        mod = _get_executor()
        cmd = FakeJarvisCommand(action_type="teleport")
        result = await mod.execute_command(cmd, {})
        assert "inconnu" in result.lower()
        assert "teleport" in result


# =========================================================================
# 2. _execute_pipeline
# =========================================================================

class TestExecutePipeline:
    """Pipeline execution: multi-step, sleep, nested protection."""

    @pytest.mark.asyncio
    async def test_pipeline_basic(self):
        mod = _get_executor()
        cmd = FakeJarvisCommand(action_type="pipeline", action="exit:;; list_commands:")
        # Each step creates a sub JarvisCommand and calls execute_command
        result = await mod.execute_command(cmd, {})
        # __EXIT__ and __REPEAT__ start with __ so they are filtered
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_pipeline_empty(self):
        mod = _get_executor()
        result = await mod._execute_pipeline("", {})
        assert "pipeline execute" in result.lower()

    @pytest.mark.asyncio
    async def test_pipeline_invalid_step(self):
        mod = _get_executor()
        result = await mod._execute_pipeline("no_colon_here", {})
        assert "invalide" in result.lower()

    @pytest.mark.asyncio
    async def test_pipeline_nested_rejected(self):
        mod = _get_executor()
        result = await mod._execute_pipeline("pipeline:something", {})
        assert "non supportee" in result.lower()

    @pytest.mark.asyncio
    async def test_pipeline_sleep_step(self):
        mod = _get_executor()
        with patch.object(asyncio, "sleep", new=AsyncMock()) as mock_sleep:
            result = await mod._execute_pipeline("sleep:0.01", {})
            mock_sleep.assert_awaited_once_with(0.01)
        assert "pipeline execute" in result.lower()

    @pytest.mark.asyncio
    async def test_pipeline_sleep_invalid_duration(self):
        mod = _get_executor()
        # Should not raise, just log and continue
        result = await mod._execute_pipeline("sleep:abc", {})
        assert "pipeline execute" in result.lower()

    @pytest.mark.asyncio
    async def test_pipeline_param_substitution(self):
        mod = _get_executor()
        cmd = FakeJarvisCommand(action_type="pipeline", action="jarvis_tool:{tool_name}")
        result = await mod.execute_command(cmd, {"tool_name": "health"})
        # __TOOL__health starts with __ so filtered -> "Pipeline execute"
        assert isinstance(result, str)


# =========================================================================
# 3. execute_skill_step
# =========================================================================

class TestExecuteSkillStep:
    """Single skill step execution with mcp_call callback."""

    @pytest.mark.asyncio
    async def test_skill_step_success(self):
        mod = _get_executor()
        step = FakeSkillStep(tool="volume_up", args={"level": 80}, description="Volume up")
        mcp_call = AsyncMock(return_value="Volume set to 80")
        result = await mod.execute_skill_step(step, mcp_call)
        assert result == "Volume set to 80"
        mcp_call.assert_awaited_once_with("volume_up", {"level": 80})
        _mock_skills.log_action.assert_called_once()

    @pytest.mark.asyncio
    async def test_skill_step_mcp_raises_oserror(self):
        mod = _get_executor()
        step = FakeSkillStep(tool="broken_tool", args={})
        mcp_call = AsyncMock(side_effect=OSError("connection refused"))
        result = await mod.execute_skill_step(step, mcp_call)
        assert "erreur" in result.lower()
        assert "broken_tool" in result

    @pytest.mark.asyncio
    async def test_skill_step_mcp_raises_timeout(self):
        mod = _get_executor()
        step = FakeSkillStep(tool="slow_tool", args={})
        mcp_call = AsyncMock(side_effect=TimeoutError("timed out"))
        result = await mod.execute_skill_step(step, mcp_call)
        assert "erreur" in result.lower()

    @pytest.mark.asyncio
    async def test_skill_step_mcp_raises_valueerror(self):
        mod = _get_executor()
        step = FakeSkillStep(tool="bad_args", args={"x": "y"})
        mcp_call = AsyncMock(side_effect=ValueError("invalid arg"))
        result = await mod.execute_skill_step(step, mcp_call)
        assert "erreur" in result.lower()
        _mock_skills.log_action.assert_called()
        # log_action called with success=False
        call_args = _mock_skills.log_action.call_args
        assert call_args[0][2] is False

    @pytest.mark.asyncio
    async def test_skill_step_mcp_raises_keyerror(self):
        mod = _get_executor()
        step = FakeSkillStep(tool="missing_key", args={})
        mcp_call = AsyncMock(side_effect=KeyError("key"))
        result = await mod.execute_skill_step(step, mcp_call)
        assert "erreur" in result.lower()

    @pytest.mark.asyncio
    async def test_skill_step_mcp_raises_typeerror(self):
        mod = _get_executor()
        step = FakeSkillStep(tool="type_err", args={})
        mcp_call = AsyncMock(side_effect=TypeError("bad type"))
        result = await mod.execute_skill_step(step, mcp_call)
        assert "erreur" in result.lower()

    @pytest.mark.asyncio
    async def test_skill_step_mcp_raises_runtimeerror(self):
        mod = _get_executor()
        step = FakeSkillStep(tool="runtime_err", args={})
        mcp_call = AsyncMock(side_effect=RuntimeError("runtime fail"))
        result = await mod.execute_skill_step(step, mcp_call)
        assert "erreur" in result.lower()


# =========================================================================
# 4. execute_skill
# =========================================================================

class TestExecuteSkill:
    """Full skill pipeline execution."""

    @pytest.mark.asyncio
    async def test_skill_all_steps_success(self):
        mod = _get_executor()
        steps = [
            FakeSkillStep(tool="step1", args={}, description="First step"),
            FakeSkillStep(tool="step2", args={}, description="Second step"),
        ]
        skill = FakeSkill(name="deploy", steps=steps)
        mcp_call = AsyncMock(return_value="done")
        result = await mod.execute_skill(skill, mcp_call)
        assert "deploy" in result
        assert "termine" in result.lower()
        assert "erreurs" not in result.lower()
        assert mcp_call.await_count == 2
        _mock_skills.record_skill_use.assert_called_once_with("deploy", True)

    @pytest.mark.asyncio
    async def test_skill_with_error_step(self):
        mod = _get_executor()
        steps = [
            FakeSkillStep(tool="ok_step", args={}, description="Works"),
            FakeSkillStep(tool="bad_step", args={}, description="Fails"),
        ]
        skill = FakeSkill(name="partial", steps=steps)

        async def mock_mcp(tool, args):
            if tool == "bad_step":
                raise OSError("connection lost")
            return "success"

        result = await mod.execute_skill(skill, mock_mcp)
        assert "partial" in result
        assert "erreurs" in result.lower()
        _mock_skills.record_skill_use.assert_called_once_with("partial", False)

    @pytest.mark.asyncio
    async def test_skill_empty_steps(self):
        mod = _get_executor()
        skill = FakeSkill(name="empty", steps=[])
        mcp_call = AsyncMock()
        result = await mod.execute_skill(skill, mcp_call)
        assert "empty" in result
        assert "termine" in result.lower()
        mcp_call.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_skill_step_numbering(self):
        """Verify step numbers appear as [1/N], [2/N], etc."""
        mod = _get_executor()
        steps = [
            FakeSkillStep(tool="a", description="Alpha"),
            FakeSkillStep(tool="b", description="Beta"),
            FakeSkillStep(tool="c", description="Gamma"),
        ]
        skill = FakeSkill(name="numbered", steps=steps)
        mcp_call = AsyncMock(return_value="ok")
        result = await mod.execute_skill(skill, mcp_call)
        assert "[1/3]" in result
        assert "[2/3]" in result
        assert "[3/3]" in result

    @pytest.mark.asyncio
    async def test_skill_result_truncated(self):
        """Long MCP results are truncated to 150 chars in output."""
        mod = _get_executor()
        steps = [FakeSkillStep(tool="verbose", description="Verbose")]
        skill = FakeSkill(name="trunc", steps=steps)
        mcp_call = AsyncMock(return_value="x" * 300)
        result = await mod.execute_skill(skill, mcp_call)
        # The "OK: " prefix + 150 chars max
        lines = result.split("\n")
        ok_line = [l for l in lines if l.strip().startswith("OK:")]
        assert len(ok_line) == 1
        # 150 + "  OK: " = 156 max
        assert len(ok_line[0].strip()) <= 156


# =========================================================================
# 5. process_voice_input
# =========================================================================

class TestProcessVoiceInput:
    """Voice input pipeline: correct -> match -> execute."""

    @pytest.mark.asyncio
    async def test_no_match_returns_freeform(self):
        _mock_commands.match_command.return_value = (None, {}, 0.3)
        mod = _get_executor()
        result, score = await mod.process_voice_input("ouvre le truc")
        assert result.startswith("__FREEFORM__")
        assert "ouvre le truc" in result
        assert score == 0.3

    @pytest.mark.asyncio
    async def test_matched_command_executed(self):
        cmd = FakeJarvisCommand(action_type="exit", name="quitter")
        _mock_commands.match_command.return_value = (cmd, {}, 0.95)
        mod = _get_executor()
        result, score = await mod.process_voice_input("quitter jarvis")
        assert result == "__EXIT__"
        assert score == 0.95

    @pytest.mark.asyncio
    async def test_confirmation_required(self):
        cmd = FakeJarvisCommand(
            action_type="powershell", action="shutdown /s",
            name="shutdown", description="Eteindre le PC",
            confirm=True,
        )
        _mock_commands.match_command.return_value = (cmd, {}, 0.9)
        mod = _get_executor()
        result, score = await mod.process_voice_input("eteins le pc")
        assert result.startswith("__CONFIRM__")
        assert "shutdown" in result
        assert "Eteindre le PC" in result

    @pytest.mark.asyncio
    async def test_voice_correction_applied(self):
        _mock_commands.correct_voice_text.side_effect = lambda t: t.replace("jarvice", "jarvis")
        cmd = FakeJarvisCommand(action_type="exit", name="quitter")
        _mock_commands.match_command.return_value = (cmd, {}, 0.9)
        mod = _get_executor()
        result, score = await mod.process_voice_input("jarvice quitte")
        # correct_voice_text should have been called
        _mock_commands.correct_voice_text.assert_called_once_with("jarvice quitte")

    @pytest.mark.asyncio
    async def test_intent_classifier_failure_does_not_crash(self):
        """Even if intent classifier raises, process continues."""
        _mock_intent.intent_classifier.classify_single.side_effect = RuntimeError("classifier down")
        _mock_commands.match_command.return_value = (None, {}, 0.1)
        mod = _get_executor()
        result, score = await mod.process_voice_input("random text")
        assert result.startswith("__FREEFORM__")

    @pytest.mark.asyncio
    async def test_analytics_recorded_on_match(self):
        cmd = FakeJarvisCommand(action_type="exit", name="quitter")
        _mock_commands.match_command.return_value = (cmd, {}, 0.85)
        mod = _get_executor()
        with patch.object(mod, "_record_execution") as mock_record:
            result, score = await mod.process_voice_input("quitter")
            mock_record.assert_called_once()
            call_args = mock_record.call_args
            assert call_args[0][0] == "quitter"  # raw_text
            assert call_args[0][2] == "quitter"  # command_name


# =========================================================================
# 6. _execute_hotkey (sync helper)
# =========================================================================

class TestExecuteHotkey:
    """Direct tests for _execute_hotkey function."""

    def test_known_hotkey(self):
        mod = _get_executor()
        result = mod._execute_hotkey("ctrl+c")
        assert "ctrl+c" in result
        assert "execute" in result.lower()

    def test_unknown_hotkey(self):
        mod = _get_executor()
        result = mod._execute_hotkey("super_mega_key")
        assert "inconnu" in result.lower()

    def test_hotkey_powershell_failure(self):
        _mock_windows.run_powershell.return_value = {"success": False, "stdout": "", "stderr": "access denied stuff"}
        mod = _get_executor()
        result = mod._execute_hotkey("volume_up")
        assert "erreur" in result.lower()


# =========================================================================
# 7. _postprocess_trading_script
# =========================================================================

class TestPostprocessTradingScript:
    """Trading script JSON parsing and Telegram notification."""

    def test_non_trading_script_returns_none(self):
        mod = _get_executor()
        result = mod._postprocess_trading_script("regular_script", "some output")
        assert result is None

    def test_trading_script_no_signals(self):
        _mock_signal_formatter.parse_sniper_json.return_value = None
        mod = _get_executor()
        result = mod._postprocess_trading_script("scan_sniper", "{}")
        assert result is None

    def test_trading_script_empty_signals(self):
        _mock_signal_formatter.parse_sniper_json.return_value = {"signals": []}
        mod = _get_executor()
        result = mod._postprocess_trading_script("scan_sniper", "{}")
        assert result is None

    def test_trading_script_with_signals(self):
        _mock_signal_formatter.parse_sniper_json.return_value = {"signals": [{"pair": "ETH"}]}
        _mock_signal_formatter.format_chat_signals.return_value = "ETH signal"
        mod = _get_executor()
        with patch.dict("sys.modules", {"src.trading": MagicMock()}):
            result = mod._postprocess_trading_script("scan_sniper", '{"signals":[]}')
        assert result == "ETH signal"

    def test_trading_script_telegram_import_error(self):
        """Even if Telegram fails, chat signals are still returned."""
        _mock_signal_formatter.parse_sniper_json.return_value = {"signals": [{"pair": "SOL"}]}
        _mock_signal_formatter.format_chat_signals.return_value = "SOL signal"
        mod = _get_executor()
        # Make the import of src.trading fail
        broken_trading = MagicMock()
        broken_trading.send_telegram.side_effect = RuntimeError("telegram down")
        with patch.dict("sys.modules", {"src.trading": broken_trading}):
            result = mod._postprocess_trading_script("mexc_scanner", '{"signals":[]}')
        assert result == "SOL signal"

    def test_trading_script_mexc_scanner(self):
        _mock_signal_formatter.parse_sniper_json.return_value = {"signals": [{"pair": "BTC"}]}
        _mock_signal_formatter.format_chat_signals.return_value = "BTC scan"
        mod = _get_executor()
        with patch.dict("sys.modules", {"src.trading": MagicMock()}):
            result = mod._postprocess_trading_script("mexc_scanner", '{"signals":[]}')
        assert result == "BTC scan"


# =========================================================================
# 8. HOTKEY_MAP constants
# =========================================================================

class TestHotkeyMap:
    """Verify HOTKEY_MAP contains expected entries."""

    def test_media_keys_present(self):
        mod = _get_executor()
        for key in ("media_play_pause", "media_next", "media_previous", "media_stop"):
            assert key in mod.HOTKEY_MAP

    def test_volume_keys_present(self):
        mod = _get_executor()
        for key in ("volume_up", "volume_down", "volume_mute"):
            assert key in mod.HOTKEY_MAP

    def test_ctrl_combos_present(self):
        mod = _get_executor()
        for key in ("ctrl+c", "ctrl+v", "ctrl+z", "ctrl+s"):
            assert key in mod.HOTKEY_MAP

    def test_win_combos_present(self):
        mod = _get_executor()
        for key in ("win+d", "win+e", "win+l", "win+r"):
            assert key in mod.HOTKEY_MAP


# =========================================================================
# 9. correct_with_ia (async IA correction with fallback)
# =========================================================================

class TestCorrectWithIA:
    """Tests for IA-powered voice correction with node fallback."""

    @pytest.mark.asyncio
    async def test_fallback_to_static_correction(self):
        """When all nodes fail, falls back to correct_voice_text."""
        mod = _get_executor()
        # Make config return None for all nodes
        _mock_config.config = MagicMock()
        _mock_config.config.get_ollama_node.return_value = None
        _mock_config.config.get_lm_node.return_value = None
        _mock_config.build_ollama_payload = MagicMock()
        with patch.dict("sys.modules", {"src.orchestrator_v2": MagicMock()}):
            result = await mod.correct_with_ia("bonjour jarvice")
        assert result == "bonjour jarvice"  # static correction (identity in our mock)

    @pytest.mark.asyncio
    async def test_ol1_success(self):
        """OL1 node returns corrected text."""
        import httpx as real_httpx

        mod = _get_executor()
        _mock_config.config = MagicMock()
        ol_node = MagicMock()
        ol_node.url = "http://127.0.0.1:11434"
        _mock_config.config.get_ollama_node.return_value = ol_node
        _mock_config.build_ollama_payload = MagicMock(return_value={"model": "qwen3:1.7b", "messages": []})

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"message": {"content": "bonjour jarvis"}}
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)

        mock_ac_instance = AsyncMock()
        mock_ac_instance.__aenter__ = AsyncMock(return_value=mock_client)
        mock_ac_instance.__aexit__ = AsyncMock(return_value=False)

        # orchestrator_v2.get_best_node must return "OL1" (string) not MagicMock
        mock_orch_mod = MagicMock()
        mock_orch_mod.orchestrator_v2.get_best_node.return_value = "OL1"

        with patch.object(real_httpx, "AsyncClient", return_value=mock_ac_instance):
            with patch.dict("sys.modules", {"src.orchestrator_v2": mock_orch_mod}):
                result = await mod.correct_with_ia("bonjour jarvice")
        assert result == "bonjour jarvis"


# =========================================================================
# 10. _record_execution (analytics, best-effort)
# =========================================================================

class TestRecordExecution:
    """_record_execution never raises even if dependencies fail."""

    def test_record_execution_calls_analytics(self):
        mod = _get_executor()
        # Should not raise even with mocked dependencies
        mod._record_execution("raw", "corrected", "cmd_name", 0.9, None, 100.0)
        _mock_commands.record_command_execution.assert_called()

    def test_record_execution_unmatched(self):
        mod = _get_executor()
        mod._record_execution("raw", "corrected", None, 0.2, None, 0.0)
        call_args = _mock_commands.record_command_execution.call_args
        assert call_args[0][0] == "__unmatched__"

    def test_record_execution_exception_swallowed(self):
        _mock_commands.record_command_execution.side_effect = RuntimeError("db locked")
        mod = _get_executor()
        # Should not raise
        mod._record_execution("raw", "corrected", "cmd", 0.5, None, 0.0)


# =========================================================================
# 11. Edge cases
# =========================================================================

class TestEdgeCases:
    """Edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_empty_params_dict(self):
        mod = _get_executor()
        cmd = FakeJarvisCommand(action_type="powershell", action="echo test")
        result = await mod.execute_command(cmd, {})
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_none_params_script(self):
        """Script action handles None params gracefully (uses 'or {}')."""
        fake_path = MagicMock()
        fake_path.exists.return_value = True
        fake_path.parent = Path("/fake")
        fake_result = MagicMock()
        fake_result.stdout = "ok"
        fake_result.returncode = 0
        mod = _get_executor()
        mod.SCRIPTS = {"test": fake_path}

        async def fake_to_thread(fn, *args, **kwargs):
            return fake_result

        with patch.object(asyncio, "to_thread", side_effect=fake_to_thread):
            cmd = FakeJarvisCommand(action_type="script", action="test")
            # Pass None -- executor does `for k, v in (params or {}).items()`
            result = await mod.execute_command(cmd, None)
        assert "test" in result

    @pytest.mark.asyncio
    async def test_browser_unknown_action(self):
        """Browser action that is neither navigate: nor search: returns None/falls through."""
        mod = _get_executor()
        cmd = FakeJarvisCommand(action_type="browser", action="download:file.zip")
        result = await mod.execute_command(cmd, {})
        # Falls through to unknown action type
        assert "inconnu" in result.lower()

    @pytest.mark.asyncio
    async def test_concurrent_execute_commands(self):
        """Multiple execute_command calls can run concurrently."""
        mod = _get_executor()
        cmds = [
            FakeJarvisCommand(action_type="exit"),
            FakeJarvisCommand(action_type="jarvis_repeat"),
            FakeJarvisCommand(action_type="list_commands"),
        ]
        results = await asyncio.gather(
            *[mod.execute_command(c, {}) for c in cmds]
        )
        assert results[0] == "__EXIT__"
        assert results[1] == "__REPEAT__"
        assert results[2] == "Aide: commandes disponibles"

    @pytest.mark.asyncio
    async def test_app_open_single_quote_escaping(self):
        """Single quotes in app names are escaped for PowerShell safety."""
        mod = _get_executor()
        cmd = FakeJarvisCommand(action_type="app_open", action="note'pad")
        await mod.execute_command(cmd, {})
        call_args = _mock_windows.run_powershell.call_args[0][0]
        assert "note''pad" in call_args

    @pytest.mark.asyncio
    async def test_process_voice_input_empty_text(self):
        """Empty text goes through correction and matching."""
        _mock_commands.match_command.return_value = (None, {}, 0.0)
        mod = _get_executor()
        result, score = await mod.process_voice_input("")
        assert result.startswith("__FREEFORM__")
        assert score == 0.0
