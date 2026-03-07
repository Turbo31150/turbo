"""Tests for src/commands.py — Command registry, matching, analytics, macros.

Covers: JarvisCommand dataclass, correct_voice_text, similarity,
match_command, get_commands_by_category, format_commands_help,
dry_run_command, record_command_execution, register_macro, expand_macro,
APP_PATHS, SITE_ALIASES.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.commands import (
    JarvisCommand, similarity, correct_voice_text,
    match_command, get_commands_by_category, format_commands_help,
    dry_run_command, register_macro, get_macros, expand_macro,
    APP_PATHS, SITE_ALIASES, COMMANDS,
    _build_phrase_corrections, _build_trigger_index,
)


# ===========================================================================
# JarvisCommand dataclass
# ===========================================================================

class TestJarvisCommand:
    def test_basic(self):
        cmd = JarvisCommand(
            name="test", category="systeme", description="Test cmd",
            triggers=["test"], action_type="powershell", action="echo hi",
        )
        assert cmd.name == "test"
        assert cmd.params == []
        assert cmd.confirm is False

    def test_with_params(self):
        cmd = JarvisCommand(
            name="open", category="app", description="Open app",
            triggers=["ouvre {app}"], action_type="app_open",
            action="{app}", params=["app"], confirm=True,
        )
        assert cmd.params == ["app"]
        assert cmd.confirm is True


# ===========================================================================
# APP_PATHS & SITE_ALIASES
# ===========================================================================

class TestConstants:
    def test_app_paths_not_empty(self):
        assert len(APP_PATHS) >= 20

    def test_common_apps(self):
        for app in ("chrome", "code", "terminal", "notepad"):
            assert app in APP_PATHS

    def test_site_aliases_not_empty(self):
        assert len(SITE_ALIASES) >= 15

    def test_common_sites(self):
        for site in ("google", "youtube", "github", "linkedin"):
            assert site in SITE_ALIASES
            assert SITE_ALIASES[site].startswith("http")


# ===========================================================================
# similarity
# ===========================================================================

class TestSimilarity:
    def test_identical(self):
        assert similarity("hello", "hello") == 1.0

    def test_empty_strings(self):
        # SequenceMatcher("", "") returns 1.0 (identical empty sequences)
        assert similarity("", "") == 1.0

    def test_completely_different(self):
        score = similarity("abcdef", "xyz123")
        assert score < 0.3

    def test_similar(self):
        score = similarity("ouvre chrome", "ouvrir chrome")
        assert score > 0.6

    def test_word_order(self):
        # Bag-of-words should handle reordering
        score = similarity("chrome ouvre", "ouvre chrome")
        assert score > 0.7

    def test_case_insensitive(self):
        s1 = similarity("Hello World", "hello world")
        s2 = similarity("hello world", "hello world")
        assert s1 == s2

    def test_partial_match(self):
        score = similarity("ouvre le navigateur chrome", "ouvre chrome")
        assert score > 0.4


# ===========================================================================
# correct_voice_text
# ===========================================================================

class TestCorrectVoiceText:
    def test_empty(self):
        assert correct_voice_text("") == ""

    def test_none(self):
        assert correct_voice_text(None) is None

    def test_lowercase_strip(self):
        result = correct_voice_text("  HELLO WORLD  ")
        # Should at least lowercase and strip
        assert result == result.lower().strip()

    def test_preserves_unknown_words(self):
        result = correct_voice_text("xyzzyplugh")
        assert "xyzzyplugh" in result


# ===========================================================================
# match_command
# ===========================================================================

class TestMatchCommand:
    def test_no_match(self):
        cmd, params, score = match_command("xyzzy random nonsense 12345")
        # Score should be below threshold
        assert score < 0.55 or cmd is None

    def test_returns_tuple(self):
        result = match_command("test")
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_exact_match_high_score(self):
        # If there are commands loaded, try matching one
        if COMMANDS:
            trigger = COMMANDS[0].triggers[0]
            cmd, params, score = match_command(trigger)
            if cmd:
                assert score >= 0.85

    def test_threshold_parameter(self):
        cmd, params, score = match_command("blabla", threshold=0.99)
        assert cmd is None


# ===========================================================================
# get_commands_by_category
# ===========================================================================

class TestGetCommandsByCategory:
    def test_all_commands(self):
        all_cmds = get_commands_by_category()
        assert isinstance(all_cmds, list)
        assert len(all_cmds) == len(COMMANDS)

    def test_filter_nonexistent(self):
        result = get_commands_by_category("nonexistent_category_xyz")
        assert result == []

    def test_filter_returns_subset(self):
        if COMMANDS:
            cat = COMMANDS[0].category
            filtered = get_commands_by_category(cat)
            assert all(c.category == cat for c in filtered)
            assert len(filtered) <= len(COMMANDS)


# ===========================================================================
# format_commands_help
# ===========================================================================

class TestFormatCommandsHelp:
    def test_returns_string(self):
        result = format_commands_help()
        assert isinstance(result, str)

    def test_contains_header(self):
        result = format_commands_help()
        assert "Commandes JARVIS" in result or "disponibles" in result

    def test_contains_categories(self):
        if COMMANDS:
            result = format_commands_help()
            # Should have at least one category
            assert "->" in result or ":" in result


# ===========================================================================
# dry_run_command
# ===========================================================================

class TestDryRunCommand:
    def test_no_match(self):
        result = dry_run_command("xyzzy random nonsense 12345")
        assert isinstance(result, dict)
        assert result["matched"] is False
        assert "score" in result
        assert "input" in result

    def test_match_returns_details(self):
        if COMMANDS:
            trigger = COMMANDS[0].triggers[0]
            result = dry_run_command(trigger)
            if result["matched"]:
                assert "command" in result
                assert "category" in result
                assert "action_type" in result
                assert "confidence" in result


# ===========================================================================
# Macros
# ===========================================================================

class TestMacros:
    def test_get_macros_empty(self):
        macros = get_macros()
        assert isinstance(macros, dict)

    def test_register_macro_unknown_command(self):
        with pytest.raises(ValueError, match="Unknown command"):
            register_macro("bad_macro", ["nonexistent_cmd_xyz"])

    def test_register_and_expand(self):
        if len(COMMANDS) >= 2:
            names = [COMMANDS[0].name, COMMANDS[1].name]
            register_macro("test_macro", names)
            macros = get_macros()
            assert "test_macro" in macros
            assert macros["test_macro"] == names
            expanded = expand_macro("test_macro")
            assert len(expanded) == 2
            assert expanded[0].name == names[0]

    def test_expand_nonexistent(self):
        result = expand_macro("nonexistent_macro")
        assert result == []


# ===========================================================================
# record_command_execution (DB-dependent, mock)
# ===========================================================================

class TestRecordCommandExecution:
    def test_record_does_not_raise(self):
        from src.commands import record_command_execution
        # Should not raise even if DB is unavailable
        record_command_execution("test_cmd", duration_ms=100, success=True)

    def test_get_analytics(self):
        from src.commands import get_command_analytics
        result = get_command_analytics(top_n=5)
        assert isinstance(result, list)

    def test_get_unused(self):
        from src.commands import get_unused_commands
        result = get_unused_commands(days=1)
        assert isinstance(result, list)


# ===========================================================================
# _build_trigger_index
# ===========================================================================

class TestTriggerIndex:
    def test_build_does_not_raise(self):
        _build_trigger_index()  # Should not raise

    def test_idempotent(self):
        _build_trigger_index()
        _build_trigger_index()  # Second call should be no-op
