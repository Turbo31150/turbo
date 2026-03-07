"""Tests for src/executor.py — JARVIS command executor.

Covers: execute_command dispatcher, pipeline execution, hotkey execution,
trading script post-processing, skill execution, PS script generators,
process_voice_input, HOTKEY_MAP structure.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from dataclasses import dataclass
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.commands import JarvisCommand


# ===========================================================================
# PS script generators (pure functions, no mocks)
# ===========================================================================

class TestPSScriptGenerators:
    def test_win_hotkey_ps(self):
        from src.executor import _win_hotkey_ps
        ps = _win_hotkey_ps("D")
        assert "keybd_event" in ps
        assert "0x5B" in ps  # Win key
        vk_d = ord("D")
        assert str(vk_d) in ps

    def test_win_arrow_ps(self):
        from src.executor import _win_arrow_ps
        ps = _win_arrow_ps("LEFT")
        assert "0x25" in ps  # VK_LEFT
        assert "0x5B" in ps  # Win key

    def test_win_tab_ps(self):
        from src.executor import _win_tab_ps
        ps = _win_tab_ps()
        assert "0x09" in ps  # VK_TAB
        assert "0x5B" in ps

    def test_ctrl_win_arrow_ps(self):
        from src.executor import _ctrl_win_arrow_ps
        ps = _ctrl_win_arrow_ps("RIGHT")
        assert "0x27" in ps  # VK_RIGHT
        assert "0x11" in ps  # VK_CONTROL
        assert "0x5B" in ps  # Win key

    def test_win_semicolon_ps(self):
        from src.executor import _win_semicolon_ps
        ps = _win_semicolon_ps()
        assert "0xBA" in ps  # VK_OEM_1

    def test_win_shift_s_ps(self):
        from src.executor import _win_shift_s_ps
        ps = _win_shift_s_ps()
        assert "0x10" in ps  # VK_SHIFT
        assert "0x53" in ps  # VK_S


# ===========================================================================
# HOTKEY_MAP structure
# ===========================================================================

class TestHotkeyMap:
    def test_map_not_empty(self):
        from src.executor import HOTKEY_MAP
        assert len(HOTKEY_MAP) > 30

    def test_media_keys(self):
        from src.executor import HOTKEY_MAP
        assert "media_play_pause" in HOTKEY_MAP
        assert "media_next" in HOTKEY_MAP
        assert "volume_up" in HOTKEY_MAP
        assert "volume_mute" in HOTKEY_MAP

    def test_keyboard_shortcuts(self):
        from src.executor import HOTKEY_MAP
        assert "ctrl+c" in HOTKEY_MAP
        assert "ctrl+v" in HOTKEY_MAP
        assert "ctrl+z" in HOTKEY_MAP
        assert "alt+tab" in HOTKEY_MAP

    def test_win_combos(self):
        from src.executor import HOTKEY_MAP
        assert "win+d" in HOTKEY_MAP
        assert "win+e" in HOTKEY_MAP
        assert "win+left" in HOTKEY_MAP
        assert "win+shift+s" in HOTKEY_MAP

    def test_all_values_are_strings(self):
        from src.executor import HOTKEY_MAP
        for key, val in HOTKEY_MAP.items():
            assert isinstance(val, str), f"HOTKEY_MAP[{key}] is not a string"
            assert len(val) > 5, f"HOTKEY_MAP[{key}] is suspiciously short"


# ===========================================================================
# _execute_hotkey
# ===========================================================================

class TestExecuteHotkey:
    def test_known_hotkey(self):
        from src.executor import _execute_hotkey
        with patch("src.executor.run_powershell", return_value={"success": True, "stdout": "", "stderr": ""}):
            result = _execute_hotkey("ctrl+c")
        assert "execute" in result.lower()

    def test_unknown_hotkey(self):
        from src.executor import _execute_hotkey
        result = _execute_hotkey("nonexistent_key_combo")
        assert "inconnu" in result.lower()

    def test_hotkey_failure(self):
        from src.executor import _execute_hotkey
        with patch("src.executor.run_powershell", return_value={"success": False, "stdout": "", "stderr": "Access denied"}):
            result = _execute_hotkey("ctrl+c")
        assert "erreur" in result.lower()


# ===========================================================================
# execute_command
# ===========================================================================

class TestExecuteCommand:
    @pytest.mark.asyncio
    async def test_exit(self):
        from src.executor import execute_command
        cmd = JarvisCommand("exit", "system", "Exit", ["exit"], "exit", "")
        result = await execute_command(cmd, {})
        assert result == "__EXIT__"

    @pytest.mark.asyncio
    async def test_list_commands(self):
        from src.executor import execute_command
        cmd = JarvisCommand("help", "system", "Help", ["help"], "list_commands", "")
        result = await execute_command(cmd, {})
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_repeat(self):
        from src.executor import execute_command
        cmd = JarvisCommand("repeat", "system", "Repeat", ["repete"], "jarvis_repeat", "")
        result = await execute_command(cmd, {})
        assert result == "__REPEAT__"

    @pytest.mark.asyncio
    async def test_app_open_success(self):
        from src.executor import execute_command
        cmd = JarvisCommand("open_chrome", "app", "Open Chrome", ["ouvre chrome"], "app_open", "chrome")
        with patch("src.executor.run_powershell", return_value={"success": True, "stdout": "", "stderr": ""}):
            result = await execute_command(cmd, {})
        assert "ouverte" in result.lower()

    @pytest.mark.asyncio
    async def test_app_open_failure(self):
        from src.executor import execute_command
        cmd = JarvisCommand("open_app", "app", "Open App", ["ouvre app"], "app_open", "fake_app")
        with patch("src.executor.run_powershell", return_value={"success": False, "stdout": "", "stderr": "not found"}):
            result = await execute_command(cmd, {})
        assert "impossible" in result.lower()

    @pytest.mark.asyncio
    async def test_ms_settings(self):
        from src.executor import execute_command
        cmd = JarvisCommand("settings", "system", "Settings", ["parametres"], "ms_settings", "ms-settings:display")
        with patch("src.executor.run_powershell", return_value={"success": True, "stdout": "", "stderr": ""}):
            result = await execute_command(cmd, {})
        assert "parametres" in result.lower()

    @pytest.mark.asyncio
    async def test_hotkey(self):
        from src.executor import execute_command
        cmd = JarvisCommand("copy", "edit", "Copy", ["copie"], "hotkey", "ctrl+c")
        with patch("src.executor.run_powershell", return_value={"success": True, "stdout": "", "stderr": ""}):
            result = await execute_command(cmd, {})
        assert "execute" in result.lower()

    @pytest.mark.asyncio
    async def test_browser_navigate(self):
        from src.executor import execute_command
        cmd = JarvisCommand("goto", "nav", "Navigate", ["va sur"], "browser", "navigate:github.com")
        with patch("src.executor.run_powershell", return_value={"success": True, "stdout": "", "stderr": ""}):
            result = await execute_command(cmd, {})
        assert "navigation" in result.lower()

    @pytest.mark.asyncio
    async def test_browser_search(self):
        from src.executor import execute_command
        cmd = JarvisCommand("search", "nav", "Search", ["cherche"], "browser", "search:python tutorial")
        with patch("src.executor.run_powershell", return_value={"success": True, "stdout": "", "stderr": ""}):
            result = await execute_command(cmd, {})
        assert "recherche" in result.lower()

    @pytest.mark.asyncio
    async def test_powershell_action(self):
        from src.executor import execute_command
        cmd = JarvisCommand("ps", "system", "PS", ["ps"], "powershell", "Get-Date")
        with patch("src.executor.run_powershell", return_value={"success": True, "stdout": "2026-03-07", "stderr": ""}):
            result = await execute_command(cmd, {})
        assert "execute" in result.lower()
        assert "2026" in result

    @pytest.mark.asyncio
    async def test_jarvis_tool(self):
        from src.executor import execute_command
        cmd = JarvisCommand("tool", "jarvis", "Tool", ["tool"], "jarvis_tool", "system_info")
        result = await execute_command(cmd, {})
        assert result == "__TOOL__system_info"

    @pytest.mark.asyncio
    async def test_unknown_action_type(self):
        from src.executor import execute_command
        cmd = JarvisCommand("unknown", "x", "X", ["x"], "nonexistent_type", "x")
        result = await execute_command(cmd, {})
        assert "inconnu" in result.lower()

    @pytest.mark.asyncio
    async def test_params_substitution(self):
        from src.executor import execute_command
        cmd = JarvisCommand("open", "app", "Open", ["ouvre"], "app_open", "{app}")
        with patch("src.executor.run_powershell", return_value={"success": True, "stdout": "", "stderr": ""}):
            result = await execute_command(cmd, {"app": "chrome"})
        assert "chrome" in result.lower()


# ===========================================================================
# _execute_pipeline
# ===========================================================================

class TestExecutePipeline:
    @pytest.mark.asyncio
    async def test_single_step(self):
        from src.executor import _execute_pipeline
        with patch("src.executor.run_powershell", return_value={"success": True, "stdout": "OK", "stderr": ""}):
            result = await _execute_pipeline("powershell:Get-Date", {})
        assert "execute" in result.lower()

    @pytest.mark.asyncio
    async def test_multiple_steps(self):
        from src.executor import _execute_pipeline
        with patch("src.executor.run_powershell", return_value={"success": True, "stdout": "OK", "stderr": ""}):
            result = await _execute_pipeline("powershell:cmd1;;powershell:cmd2", {})
        assert "|" in result  # Steps joined by |

    @pytest.mark.asyncio
    async def test_sleep_step(self):
        from src.executor import _execute_pipeline
        with patch("src.executor.run_powershell", return_value={"success": True, "stdout": "OK", "stderr": ""}):
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                result = await _execute_pipeline("sleep:0.01;;powershell:echo ok", {})
                mock_sleep.assert_called_once_with(0.01)

    @pytest.mark.asyncio
    async def test_invalid_step(self):
        from src.executor import _execute_pipeline
        result = await _execute_pipeline("no_colon_here", {})
        assert "invalide" in result.lower()

    @pytest.mark.asyncio
    async def test_nested_pipeline_blocked(self):
        from src.executor import _execute_pipeline
        result = await _execute_pipeline("pipeline:nested;;powershell:ok", {})
        assert "non supportee" in result.lower() or "pipeline" in result.lower()

    @pytest.mark.asyncio
    async def test_empty_pipeline(self):
        from src.executor import _execute_pipeline
        result = await _execute_pipeline("", {})
        assert "pipeline execute" in result.lower()

    @pytest.mark.asyncio
    async def test_params_in_pipeline(self):
        from src.executor import _execute_pipeline
        with patch("src.executor.run_powershell", return_value={"success": True, "stdout": "OK", "stderr": ""}):
            result = await _execute_pipeline("powershell:echo {name}", {"name": "test"})
        assert "execute" in result.lower()


# ===========================================================================
# _postprocess_trading_script
# ===========================================================================

class TestPostprocessTradingScript:
    def test_non_trading_script(self):
        from src.executor import _postprocess_trading_script
        result = _postprocess_trading_script("random_script", "some output")
        assert result is None

    def test_trading_script_no_signals(self):
        from src.executor import _postprocess_trading_script
        with patch("src.executor.parse_sniper_json", return_value=None):
            result = _postprocess_trading_script("scan_sniper", "bad output")
        assert result is None

    def test_trading_script_empty_signals(self):
        from src.executor import _postprocess_trading_script
        with patch("src.executor.parse_sniper_json", return_value={"signals": []}):
            result = _postprocess_trading_script("scan_sniper", "{}")
        assert result is None

    def test_trading_script_with_signals(self):
        from src.executor import _postprocess_trading_script
        data = {"signals": [{"symbol": "BTCUSDT", "score": 85}]}
        with patch("src.executor.parse_sniper_json", return_value=data), \
             patch("src.executor.format_telegram_signals", return_value="TG msg"), \
             patch("src.executor.format_chat_signals", return_value="Chat formatted"), \
             patch("src.trading.send_telegram", return_value=True):
            result = _postprocess_trading_script("scan_sniper", '{"signals": []}')
        assert result == "Chat formatted"

    def test_trading_script_telegram_error(self):
        from src.executor import _postprocess_trading_script
        data = {"signals": [{"symbol": "BTCUSDT"}]}
        with patch("src.executor.parse_sniper_json", return_value=data), \
             patch("src.executor.format_telegram_signals", side_effect=ImportError("no trading")), \
             patch("src.executor.format_chat_signals", return_value="Chat ok"):
            result = _postprocess_trading_script("mexc_scanner", '{}')
        assert result == "Chat ok"


# ===========================================================================
# execute_skill_step / execute_skill
# ===========================================================================

@dataclass
class FakeSkillStep:
    tool: str = "test_tool"
    args: dict = None
    description: str = "Test step"

    def __post_init__(self):
        if self.args is None:
            self.args = {}


@dataclass
class FakeSkill:
    name: str = "test_skill"
    steps: list = None

    def __post_init__(self):
        if self.steps is None:
            self.steps = [FakeSkillStep()]


class TestSkillExecution:
    @pytest.mark.asyncio
    async def test_execute_skill_step_success(self):
        from src.executor import execute_skill_step
        mcp_call = AsyncMock(return_value="result ok")
        step = FakeSkillStep()
        with patch("src.skills.log_action"):
            result = await execute_skill_step(step, mcp_call)
        assert result == "result ok"

    @pytest.mark.asyncio
    async def test_execute_skill_step_error(self):
        from src.executor import execute_skill_step
        mcp_call = AsyncMock(side_effect=ValueError("tool failed"))
        step = FakeSkillStep()
        with patch("src.skills.log_action"):
            result = await execute_skill_step(step, mcp_call)
        assert "erreur" in result.lower()

    @pytest.mark.asyncio
    async def test_execute_skill_all_success(self):
        from src.executor import execute_skill
        mcp_call = AsyncMock(return_value="OK")
        skill = FakeSkill(steps=[FakeSkillStep(), FakeSkillStep(tool="other")])
        with patch("src.skills.log_action"), \
             patch("src.skills.record_skill_use"):
            result = await execute_skill(skill, mcp_call)
        assert "termine" in result.lower()
        assert "erreur" not in result.lower()

    @pytest.mark.asyncio
    async def test_execute_skill_with_error(self):
        from src.executor import execute_skill
        mcp_call = AsyncMock(return_value="ERREUR: something broke")
        skill = FakeSkill(steps=[FakeSkillStep()])
        with patch("src.skills.log_action"), \
             patch("src.skills.record_skill_use"):
            result = await execute_skill(skill, mcp_call)
        assert "erreurs" in result.lower()


# ===========================================================================
# process_voice_input
# ===========================================================================

class TestProcessVoiceInput:
    @pytest.mark.asyncio
    async def test_no_match_returns_freeform(self):
        from src.executor import process_voice_input
        with patch("src.executor.correct_voice_text", return_value="hello jarvis"), \
             patch("src.executor.match_command", return_value=(None, {}, 0.3)), \
             patch("src.executor._record_execution"):
            result, score = await process_voice_input("hello jarvis")
        assert result.startswith("__FREEFORM__")

    @pytest.mark.asyncio
    async def test_matched_command_executes(self):
        from src.executor import process_voice_input
        cmd = JarvisCommand("exit_cmd", "system", "Exit", ["exit"], "exit", "")
        with patch("src.executor.correct_voice_text", return_value="exit"), \
             patch("src.executor.match_command", return_value=(cmd, {}, 0.95)), \
             patch("src.executor._record_execution"):
            result, score = await process_voice_input("exit")
        assert result == "__EXIT__"

    @pytest.mark.asyncio
    async def test_confirm_command(self):
        from src.executor import process_voice_input
        cmd = JarvisCommand("danger", "system", "Danger", ["danger"], "powershell", "rm -rf /", confirm=True)
        with patch("src.executor.correct_voice_text", return_value="danger"), \
             patch("src.executor.match_command", return_value=(cmd, {}, 0.9)), \
             patch("src.executor._record_execution"):
            result, score = await process_voice_input("danger")
        assert result.startswith("__CONFIRM__")
