"""Comprehensive tests for src/commands.py core functions.

Tests cover:
- correct_voice_text: voice correction with word + phrase replacements
- similarity: SequenceMatcher + bag-of-words hybrid scoring
- match_command: exact, parameterized, substring, fuzzy matching
- get_commands_by_category: filtering by category
- format_commands_help: help text generation
- record_command_execution: analytics recording with sqlite mock
- Edge cases: empty text, no commands, zero score, missing DB
"""

from __future__ import annotations

import importlib
import json
import re
import sys
from dataclasses import dataclass, field
from unittest.mock import MagicMock, call, patch

import pytest


# ---------------------------------------------------------------------------
# Module-level setup: mock heavy dependencies before importing src.commands
# ---------------------------------------------------------------------------

# We need to isolate src.commands from the real database and config.
# Strategy: mock src.config, mock sqlite3.connect, then import the module
# fresh so its module-level code (_load_commands_from_db, etc.) uses our mocks.


@pytest.fixture(scope="module")
def commands_module():
    """Import src.commands with all DB access and heavy deps mocked.

    Returns the module object so tests can access its functions and globals.
    """
    # Save any pre-existing module references
    saved_modules = {}
    modules_to_mock = [
        "src.commands",
        "src.commands_pipelines",
        "src.commands_navigation",
        "src.commands_maintenance",
        "src.commands_dev",
    ]
    for mod_name in modules_to_mock:
        if mod_name in sys.modules:
            saved_modules[mod_name] = sys.modules.pop(mod_name)

    # Mock src.config.PATHS
    mock_config = MagicMock()
    mock_config.PATHS = {"turbo": "/home/turbo/jarvis-m1-ops"}

    # Mock sqlite3 to return empty results (no DB needed)
    mock_sqlite3 = MagicMock()
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = []
    mock_conn.row_factory = None
    mock_sqlite3.connect.return_value = mock_conn
    mock_sqlite3.Row = object  # sentinel for row_factory
    mock_sqlite3.Error = Exception  # needed for except clauses

    # Inject mocks
    original_config = sys.modules.get("src.config")
    sys.modules["src.config"] = mock_config

    # Mock extension modules to prevent imports
    for ext in modules_to_mock[1:]:
        sys.modules[ext] = MagicMock(
            PIPELINE_COMMANDS=[],
            NAVIGATION_COMMANDS=[],
            MAINTENANCE_COMMANDS=[],
            DEV_COMMANDS=[],
        )

    # Patch sqlite3 inside the commands module namespace
    with patch.dict("sys.modules", {"sqlite3": mock_sqlite3}):
        # Force fresh import
        import src.commands as mod
        importlib.reload(mod)

    # Restore extension mocks cleanup (keep module loaded)
    for ext in modules_to_mock[1:]:
        if ext in sys.modules and isinstance(sys.modules[ext], MagicMock):
            del sys.modules[ext]

    # Restore original config
    if original_config is not None:
        sys.modules["src.config"] = original_config
    else:
        sys.modules.pop("src.config", None)

    yield mod

    # Cleanup: remove cached module so other tests are not affected
    sys.modules.pop("src.commands", None)


@pytest.fixture
def cmd_mod(commands_module):
    """Per-test fixture that resets module state (trigger index, commands list)."""
    mod = commands_module
    # Reset trigger index so each test builds fresh
    mod._trigger_index_built = False
    mod._trigger_exact.clear()
    mod._trigger_param.clear()
    return mod


def _make_cmd(name="test_cmd", category="test", description="A test command",
              triggers=None, action_type="script", action="echo test",
              params=None, confirm=False):
    """Helper to create a JarvisCommand without importing from module."""
    from src.commands import JarvisCommand
    return JarvisCommand(
        name=name,
        category=category,
        description=description,
        triggers=triggers or ["test command"],
        action_type=action_type,
        action=action,
        params=params or [],
        confirm=confirm,
    )


# ===========================================================================
# 1. correct_voice_text
# ===========================================================================

class TestCorrectVoiceText:
    """Tests for the correct_voice_text function."""

    def test_empty_string(self, cmd_mod):
        """Empty string returns empty string."""
        assert cmd_mod.correct_voice_text("") == ""

    def test_none_returns_none(self, cmd_mod):
        """None input returns None (falsy pass-through)."""
        result = cmd_mod.correct_voice_text(None)
        assert result is None

    def test_lowercases_and_strips(self, cmd_mod):
        """Text is lowercased and stripped."""
        result = cmd_mod.correct_voice_text("  HELLO WORLD  ")
        assert result == "hello world"

    def test_word_level_correction(self, cmd_mod):
        """Single-word corrections from VOICE_CORRECTIONS dict."""
        # Inject a test correction
        cmd_mod.VOICE_CORRECTIONS["jarviss"] = "jarvis"
        cmd_mod._PHRASE_CORRECTIONS = []  # force rebuild
        result = cmd_mod.correct_voice_text("Jarviss")
        assert result == "jarvis"
        # Cleanup
        del cmd_mod.VOICE_CORRECTIONS["jarviss"]

    def test_phrase_correction(self, cmd_mod):
        """Multi-word phrase corrections are applied."""
        cmd_mod.VOICE_CORRECTIONS["ouvre le chrome"] = "ouvre chrome"
        cmd_mod._PHRASE_CORRECTIONS = []  # force rebuild
        result = cmd_mod.correct_voice_text("Ouvre le Chrome")
        assert result == "ouvre chrome"
        # Cleanup
        del cmd_mod.VOICE_CORRECTIONS["ouvre le chrome"]
        cmd_mod._PHRASE_CORRECTIONS = []

    def test_multiple_corrections_applied(self, cmd_mod):
        """Multiple word corrections applied in sequence."""
        cmd_mod.VOICE_CORRECTIONS["ouverture"] = "ouvre"
        cmd_mod.VOICE_CORRECTIONS["navigateur"] = "chrome"
        cmd_mod._PHRASE_CORRECTIONS = []
        result = cmd_mod.correct_voice_text("Ouverture Navigateur")
        assert result == "ouvre chrome"
        # Cleanup
        del cmd_mod.VOICE_CORRECTIONS["ouverture"]
        del cmd_mod.VOICE_CORRECTIONS["navigateur"]

    def test_no_correction_needed(self, cmd_mod):
        """Text without matching corrections passes through unchanged (lowered)."""
        cmd_mod._PHRASE_CORRECTIONS = []
        result = cmd_mod.correct_voice_text("hello world")
        assert result == "hello world"

    def test_whitespace_only(self, cmd_mod):
        """Whitespace-only string becomes empty after strip/split."""
        result = cmd_mod.correct_voice_text("   ")
        assert result == ""


# ===========================================================================
# 2. similarity
# ===========================================================================

class TestSimilarity:
    """Tests for the similarity function (hybrid SequenceMatcher + bag-of-words)."""

    def test_identical_strings(self, cmd_mod):
        """Identical strings yield 1.0."""
        assert cmd_mod.similarity("hello world", "hello world") == 1.0

    def test_identical_case_insensitive(self, cmd_mod):
        """Case differences should not affect score."""
        assert cmd_mod.similarity("Hello World", "hello world") == 1.0

    def test_completely_different(self, cmd_mod):
        """Completely different strings yield low score."""
        score = cmd_mod.similarity("abcdef", "xyz123")
        assert score < 0.2

    def test_empty_strings(self, cmd_mod):
        """Two empty strings yield 1.0 from SequenceMatcher."""
        assert cmd_mod.similarity("", "") == 1.0

    def test_one_empty_one_not(self, cmd_mod):
        """One empty, one non-empty yields 0.0."""
        assert cmd_mod.similarity("", "hello") == 0.0
        assert cmd_mod.similarity("hello", "") == 0.0

    def test_word_order_invariance(self, cmd_mod):
        """Reversed word order should still score high via bag-of-words."""
        score = cmd_mod.similarity("ouvre chrome", "chrome ouvre")
        # Bag-of-words: jaccard=1.0, coverage=1.0 -> bow=1.0
        assert score == 1.0

    def test_partial_overlap(self, cmd_mod):
        """Partial word overlap gives intermediate score."""
        score = cmd_mod.similarity("ouvre chrome navigateur", "ouvre chrome")
        assert 0.4 < score < 1.0

    def test_returns_float(self, cmd_mod):
        """Return type is float."""
        result = cmd_mod.similarity("a", "b")
        assert isinstance(result, float)

    def test_score_between_0_and_1(self, cmd_mod):
        """Score is always in [0.0, 1.0]."""
        test_pairs = [
            ("hello", "world"),
            ("abc", "abcdef"),
            ("test command", "testing commands"),
        ]
        for a, b in test_pairs:
            score = cmd_mod.similarity(a, b)
            assert 0.0 <= score <= 1.0, f"Score {score} out of range for ({a!r}, {b!r})"

    def test_single_char_strings(self, cmd_mod):
        """Single character comparison."""
        assert cmd_mod.similarity("a", "a") == 1.0
        assert cmd_mod.similarity("a", "b") < 1.0


# ===========================================================================
# 3. match_command
# ===========================================================================

class TestMatchCommand:
    """Tests for the match_command function — exact, regex, substring, fuzzy."""

    def test_no_commands_returns_none(self, cmd_mod):
        """With no commands loaded, match returns None."""
        cmd_mod.COMMANDS.clear()
        cmd_mod._trigger_index_built = False
        cmd, params, score = cmd_mod.match_command("anything")
        assert cmd is None
        assert params == {}

    def test_exact_match(self, cmd_mod):
        """Exact trigger match yields confidence 1.0."""
        test_cmd = _make_cmd(
            name="open_chrome",
            triggers=["ouvre chrome"],
            action="start chrome",
        )
        cmd_mod.COMMANDS.clear()
        cmd_mod.COMMANDS.append(test_cmd)
        cmd_mod._trigger_index_built = False

        matched, params, score = cmd_mod.match_command("ouvre chrome")
        assert matched is not None
        assert matched.name == "open_chrome"
        assert score == 1.0
        assert params == {}

    def test_exact_match_case_insensitive(self, cmd_mod):
        """Exact match is case-insensitive."""
        test_cmd = _make_cmd(
            name="open_chrome",
            triggers=["ouvre chrome"],
        )
        cmd_mod.COMMANDS.clear()
        cmd_mod.COMMANDS.append(test_cmd)
        cmd_mod._trigger_index_built = False

        matched, params, score = cmd_mod.match_command("OUVRE CHROME")
        assert matched is not None
        assert score == 1.0

    def test_parameterized_match(self, cmd_mod):
        """Parameterized trigger extracts parameters."""
        test_cmd = _make_cmd(
            name="search_web",
            triggers=["cherche {query}"],
            params=["query"],
        )
        cmd_mod.COMMANDS.clear()
        cmd_mod.COMMANDS.append(test_cmd)
        cmd_mod._trigger_index_built = False

        matched, params, score = cmd_mod.match_command("cherche intelligence artificielle")
        assert matched is not None
        assert matched.name == "search_web"
        assert params.get("query") == "intelligence artificielle"
        assert score == 0.95

    def test_substring_match(self, cmd_mod):
        """Substring match gives score 0.90 when trigger is contained in input."""
        test_cmd = _make_cmd(
            name="status_check",
            triggers=["statut systeme"],
        )
        cmd_mod.COMMANDS.clear()
        cmd_mod.COMMANDS.append(test_cmd)
        cmd_mod._trigger_index_built = False

        matched, params, score = cmd_mod.match_command("montre le statut systeme complet")
        assert matched is not None
        assert matched.name == "status_check"
        assert score == 0.90

    def test_fuzzy_match_above_threshold(self, cmd_mod):
        """Fuzzy match above threshold returns the command."""
        test_cmd = _make_cmd(
            name="open_chrome",
            triggers=["ouvre chrome"],
        )
        cmd_mod.COMMANDS.clear()
        cmd_mod.COMMANDS.append(test_cmd)
        cmd_mod._trigger_index_built = False

        # Slight typo — should still fuzzy match
        matched, params, score = cmd_mod.match_command("ouvr chrome")
        assert matched is not None
        assert matched.name == "open_chrome"
        assert score >= 0.55

    def test_fuzzy_match_below_threshold_returns_none(self, cmd_mod):
        """Fuzzy match below threshold returns None."""
        test_cmd = _make_cmd(
            name="open_chrome",
            triggers=["ouvre chrome"],
        )
        cmd_mod.COMMANDS.clear()
        cmd_mod.COMMANDS.append(test_cmd)
        cmd_mod._trigger_index_built = False

        matched, params, score = cmd_mod.match_command("xyz completely unrelated")
        assert matched is None

    def test_custom_threshold(self, cmd_mod):
        """Custom threshold parameter affects matching."""
        test_cmd = _make_cmd(
            name="open_chrome",
            triggers=["ouvre chrome"],
        )
        cmd_mod.COMMANDS.clear()
        cmd_mod.COMMANDS.append(test_cmd)
        cmd_mod._trigger_index_built = False

        # With very high threshold, fuzzy won't match
        matched, params, score = cmd_mod.match_command("ouvr chrom", threshold=0.99)
        assert matched is None

    def test_empty_input(self, cmd_mod):
        """Empty string input returns None (or very low score)."""
        test_cmd = _make_cmd(
            name="open_chrome",
            triggers=["ouvre chrome"],
        )
        cmd_mod.COMMANDS.clear()
        cmd_mod.COMMANDS.append(test_cmd)
        cmd_mod._trigger_index_built = False

        matched, params, score = cmd_mod.match_command("")
        # Empty string should either be None or have very low score
        if matched is not None:
            assert score < 0.55

    def test_multiple_commands_best_match(self, cmd_mod):
        """With multiple commands, the best match is selected."""
        cmd1 = _make_cmd(name="open_chrome", triggers=["ouvre chrome"])
        cmd2 = _make_cmd(name="open_firefox", triggers=["ouvre firefox"])
        cmd_mod.COMMANDS.clear()
        cmd_mod.COMMANDS.extend([cmd1, cmd2])
        cmd_mod._trigger_index_built = False

        matched, _, score = cmd_mod.match_command("ouvre chrome")
        assert matched.name == "open_chrome"
        assert score == 1.0

    def test_voice_correction_applied_before_match(self, cmd_mod):
        """Voice corrections are applied before matching."""
        cmd_mod.VOICE_CORRECTIONS["ouvrir"] = "ouvre"
        cmd_mod._PHRASE_CORRECTIONS = []
        test_cmd = _make_cmd(name="open_chrome", triggers=["ouvre chrome"])
        cmd_mod.COMMANDS.clear()
        cmd_mod.COMMANDS.append(test_cmd)
        cmd_mod._trigger_index_built = False

        matched, _, score = cmd_mod.match_command("ouvrir chrome")
        assert matched is not None
        assert matched.name == "open_chrome"
        assert score == 1.0

        # Cleanup
        del cmd_mod.VOICE_CORRECTIONS["ouvrir"]

    def test_returns_tuple_of_three(self, cmd_mod):
        """match_command always returns a 3-tuple."""
        cmd_mod.COMMANDS.clear()
        cmd_mod._trigger_index_built = False
        result = cmd_mod.match_command("anything")
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_score_zero_no_commands(self, cmd_mod):
        """With no commands, score should be 0."""
        cmd_mod.COMMANDS.clear()
        cmd_mod._trigger_index_built = False
        _, _, score = cmd_mod.match_command("test")
        assert score == 0.0

    def test_multi_param_trigger(self, cmd_mod):
        """Trigger with multiple parameters extracts all."""
        test_cmd = _make_cmd(
            name="copy_file",
            triggers=["copie {source} vers {dest}"],
            params=["source", "dest"],
        )
        cmd_mod.COMMANDS.clear()
        cmd_mod.COMMANDS.append(test_cmd)
        cmd_mod._trigger_index_built = False

        matched, params, score = cmd_mod.match_command("copie fichier.txt vers backup")
        assert matched is not None
        assert matched.name == "copy_file"
        assert "source" in params
        assert "dest" in params


# ===========================================================================
# 4. get_commands_by_category
# ===========================================================================

class TestGetCommandsByCategory:
    """Tests for get_commands_by_category."""

    def test_filter_by_category(self, cmd_mod):
        """Filtering by category returns only matching commands."""
        cmd1 = _make_cmd(name="cmd1", category="navigation")
        cmd2 = _make_cmd(name="cmd2", category="systeme")
        cmd3 = _make_cmd(name="cmd3", category="navigation")
        cmd_mod.COMMANDS.clear()
        cmd_mod.COMMANDS.extend([cmd1, cmd2, cmd3])

        result = cmd_mod.get_commands_by_category("navigation")
        assert len(result) == 2
        assert all(c.category == "navigation" for c in result)

    def test_no_category_returns_all(self, cmd_mod):
        """None category returns all commands."""
        cmd1 = _make_cmd(name="cmd1", category="navigation")
        cmd2 = _make_cmd(name="cmd2", category="systeme")
        cmd_mod.COMMANDS.clear()
        cmd_mod.COMMANDS.extend([cmd1, cmd2])

        result = cmd_mod.get_commands_by_category(None)
        assert len(result) == 2

    def test_empty_string_category_returns_all(self, cmd_mod):
        """Empty string category returns all (falsy check)."""
        cmd1 = _make_cmd(name="cmd1", category="navigation")
        cmd_mod.COMMANDS.clear()
        cmd_mod.COMMANDS.append(cmd1)

        result = cmd_mod.get_commands_by_category("")
        assert len(result) == 1  # empty string is falsy -> returns all

    def test_nonexistent_category(self, cmd_mod):
        """Non-existent category returns empty list."""
        cmd1 = _make_cmd(name="cmd1", category="navigation")
        cmd_mod.COMMANDS.clear()
        cmd_mod.COMMANDS.append(cmd1)

        result = cmd_mod.get_commands_by_category("nonexistent")
        assert result == []

    def test_no_commands_loaded(self, cmd_mod):
        """Empty commands list returns empty for any query."""
        cmd_mod.COMMANDS.clear()
        assert cmd_mod.get_commands_by_category("navigation") == []
        assert cmd_mod.get_commands_by_category(None) == []


# ===========================================================================
# 5. format_commands_help
# ===========================================================================

class TestFormatCommandsHelp:
    """Tests for format_commands_help."""

    def test_basic_format(self, cmd_mod):
        """Help text contains header, category, and command info."""
        test_cmd = _make_cmd(
            name="open_chrome",
            category="navigation",
            description="Ouvre Google Chrome",
            triggers=["ouvre chrome"],
        )
        cmd_mod.COMMANDS.clear()
        cmd_mod.COMMANDS.append(test_cmd)

        result = cmd_mod.format_commands_help()
        assert "Commandes JARVIS disponibles:" in result
        assert "Navigation Web" in result  # mapped category name
        assert "ouvre chrome" in result
        assert "Ouvre Google Chrome" in result

    def test_multiple_categories(self, cmd_mod):
        """Multiple categories are listed separately."""
        cmd1 = _make_cmd(name="cmd1", category="navigation",
                         triggers=["nav cmd"], description="Nav")
        cmd2 = _make_cmd(name="cmd2", category="systeme",
                         triggers=["sys cmd"], description="Sys")
        cmd_mod.COMMANDS.clear()
        cmd_mod.COMMANDS.extend([cmd1, cmd2])

        result = cmd_mod.format_commands_help()
        assert "Navigation Web" in result
        assert "Systeme Windows" in result

    def test_unknown_category_uses_raw_name(self, cmd_mod):
        """Unknown category name is used as-is."""
        test_cmd = _make_cmd(
            name="cmd1",
            category="custom_category",
            triggers=["custom trigger"],
            description="Custom desc",
        )
        cmd_mod.COMMANDS.clear()
        cmd_mod.COMMANDS.append(test_cmd)

        result = cmd_mod.format_commands_help()
        assert "custom_category" in result

    def test_no_commands_just_header(self, cmd_mod):
        """Empty commands list produces only the header."""
        cmd_mod.COMMANDS.clear()
        result = cmd_mod.format_commands_help()
        assert "Commandes JARVIS disponibles:" in result
        # No category lines after header
        lines = result.strip().split("\n")
        assert len(lines) == 1

    def test_returns_string(self, cmd_mod):
        """Return type is str."""
        cmd_mod.COMMANDS.clear()
        result = cmd_mod.format_commands_help()
        assert isinstance(result, str)


# ===========================================================================
# 6. record_command_execution
# ===========================================================================

class TestRecordCommandExecution:
    """Tests for record_command_execution with mocked sqlite3."""

    def test_basic_recording(self, cmd_mod):
        """Records a command execution to the analytics DB."""
        mock_conn = MagicMock()
        with patch.object(cmd_mod._sqlite3, "connect", return_value=mock_conn):
            cmd_mod.record_command_execution("test_cmd", duration_ms=150.5, success=True)

        mock_conn.execute.assert_called_once()
        args = mock_conn.execute.call_args
        sql = args[0][0]
        assert "INSERT INTO command_analytics" in sql
        values = args[0][1]
        assert values[0] == "test_cmd"        # command_name
        assert values[1] == 150.5              # duration_ms
        assert values[2] == 1                  # success=True -> 1
        assert values[3] == "voice"            # default source
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_failure_recording(self, cmd_mod):
        """Records failed execution with success=0."""
        mock_conn = MagicMock()
        with patch.object(cmd_mod._sqlite3, "connect", return_value=mock_conn):
            cmd_mod.record_command_execution("test_cmd", success=False)

        values = mock_conn.execute.call_args[0][1]
        assert values[2] == 0  # success=False -> 0

    def test_custom_source(self, cmd_mod):
        """Custom source parameter is recorded."""
        mock_conn = MagicMock()
        with patch.object(cmd_mod._sqlite3, "connect", return_value=mock_conn):
            cmd_mod.record_command_execution("test_cmd", source="keyboard")

        values = mock_conn.execute.call_args[0][1]
        assert values[3] == "keyboard"

    def test_params_serialized_as_json(self, cmd_mod):
        """Params dict is JSON-serialized."""
        mock_conn = MagicMock()
        test_params = {"query": "test", "target": "chrome"}
        with patch.object(cmd_mod._sqlite3, "connect", return_value=mock_conn):
            cmd_mod.record_command_execution("test_cmd", params=test_params)

        values = mock_conn.execute.call_args[0][1]
        assert json.loads(values[4]) == test_params

    def test_none_params_becomes_empty_json(self, cmd_mod):
        """None params becomes empty JSON object."""
        mock_conn = MagicMock()
        with patch.object(cmd_mod._sqlite3, "connect", return_value=mock_conn):
            cmd_mod.record_command_execution("test_cmd", params=None)

        values = mock_conn.execute.call_args[0][1]
        assert json.loads(values[4]) == {}

    def test_db_error_silenced(self, cmd_mod):
        """sqlite3.Error is caught silently (no exception raised)."""
        with patch.object(cmd_mod._sqlite3, "connect", side_effect=cmd_mod._sqlite3.Error("DB locked")):
            # Should not raise
            cmd_mod.record_command_execution("test_cmd")

    def test_timestamp_is_float(self, cmd_mod):
        """Timestamp is a float (time.time())."""
        mock_conn = MagicMock()
        with patch.object(cmd_mod._sqlite3, "connect", return_value=mock_conn):
            cmd_mod.record_command_execution("test_cmd")

        values = mock_conn.execute.call_args[0][1]
        assert isinstance(values[5], float)  # timestamp

    def test_default_duration_is_zero(self, cmd_mod):
        """Default duration_ms is 0."""
        mock_conn = MagicMock()
        with patch.object(cmd_mod._sqlite3, "connect", return_value=mock_conn):
            cmd_mod.record_command_execution("test_cmd")

        values = mock_conn.execute.call_args[0][1]
        assert values[1] == 0  # duration_ms default


# ===========================================================================
# 7. Edge cases & integration
# ===========================================================================

class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_similarity_with_special_characters(self, cmd_mod):
        """Similarity handles special characters gracefully."""
        score = cmd_mod.similarity("c'est l'heure", "c'est l'heure")
        assert score == 1.0

    def test_similarity_unicode(self, cmd_mod):
        """Similarity works with unicode/accented characters."""
        score = cmd_mod.similarity("demarrer", "demarrer")
        assert score == 1.0

    def test_match_command_with_only_whitespace(self, cmd_mod):
        """Match command with whitespace-only input."""
        test_cmd = _make_cmd(name="cmd1", triggers=["test"])
        cmd_mod.COMMANDS.clear()
        cmd_mod.COMMANDS.append(test_cmd)
        cmd_mod._trigger_index_built = False

        matched, params, score = cmd_mod.match_command("   ")
        # After correction: lowered + stripped = ""
        # Should not match meaningfully
        if matched is not None:
            assert score < 0.55

    def test_trigger_index_built_once(self, cmd_mod):
        """Trigger index is built on first call and reused."""
        test_cmd = _make_cmd(name="cmd1", triggers=["index test"])
        cmd_mod.COMMANDS.clear()
        cmd_mod.COMMANDS.append(test_cmd)
        cmd_mod._trigger_index_built = False

        cmd_mod.match_command("index test")
        assert cmd_mod._trigger_index_built is True

        # Calling again should not clear/rebuild
        cmd_mod.match_command("index test")
        assert cmd_mod._trigger_index_built is True

    def test_duplicate_triggers_first_wins(self, cmd_mod):
        """If two commands share a trigger, the first one registered wins."""
        cmd1 = _make_cmd(name="first", triggers=["shared trigger"])
        cmd2 = _make_cmd(name="second", triggers=["shared trigger"])
        cmd_mod.COMMANDS.clear()
        cmd_mod.COMMANDS.extend([cmd1, cmd2])
        cmd_mod._trigger_index_built = False

        matched, _, score = cmd_mod.match_command("shared trigger")
        assert matched.name == "first"  # first registered wins
        assert score == 1.0

    def test_get_commands_by_category_preserves_order(self, cmd_mod):
        """Filtered results maintain insertion order."""
        cmds = [_make_cmd(name=f"cmd{i}", category="nav") for i in range(5)]
        cmd_mod.COMMANDS.clear()
        cmd_mod.COMMANDS.extend(cmds)

        result = cmd_mod.get_commands_by_category("nav")
        assert [c.name for c in result] == [f"cmd{i}" for i in range(5)]

    def test_format_help_uses_first_trigger(self, cmd_mod):
        """Help text shows only the first trigger of each command."""
        test_cmd = _make_cmd(
            name="multi_trigger",
            category="app",
            triggers=["first trigger", "second trigger", "third trigger"],
            description="Multi-trigger command",
        )
        cmd_mod.COMMANDS.clear()
        cmd_mod.COMMANDS.append(test_cmd)

        result = cmd_mod.format_commands_help()
        assert "first trigger" in result
        # Second/third triggers not in the help (only first)
        assert "second trigger" not in result

    def test_correct_voice_text_phrase_longer_first(self, cmd_mod):
        """Phrase corrections are sorted longest-first to avoid partial matches."""
        cmd_mod.VOICE_CORRECTIONS["ouvre le"] = "ouvre"
        cmd_mod.VOICE_CORRECTIONS["ouvre le navigateur chrome"] = "ouvre chrome"
        cmd_mod._PHRASE_CORRECTIONS = []  # force rebuild

        result = cmd_mod.correct_voice_text("ouvre le navigateur chrome")
        # Longest phrase should match first
        assert result == "ouvre chrome"

        # Cleanup
        del cmd_mod.VOICE_CORRECTIONS["ouvre le"]
        del cmd_mod.VOICE_CORRECTIONS["ouvre le navigateur chrome"]
        cmd_mod._PHRASE_CORRECTIONS = []


# ===========================================================================
# 8. JarvisCommand dataclass
# ===========================================================================

class TestJarvisCommand:
    """Tests for the JarvisCommand dataclass structure."""

    def test_default_params_empty_list(self, cmd_mod):
        """Default params is an empty list."""
        cmd = cmd_mod.JarvisCommand(
            name="test", category="test", description="test",
            triggers=["test"], action_type="script", action="echo",
        )
        assert cmd.params == []

    def test_default_confirm_false(self, cmd_mod):
        """Default confirm is False."""
        cmd = cmd_mod.JarvisCommand(
            name="test", category="test", description="test",
            triggers=["test"], action_type="script", action="echo",
        )
        assert cmd.confirm is False

    def test_dataclass_fields(self, cmd_mod):
        """All expected fields are accessible."""
        cmd = cmd_mod.JarvisCommand(
            name="n", category="c", description="d",
            triggers=["t"], action_type="at", action="a",
            params=["p"], confirm=True,
        )
        assert cmd.name == "n"
        assert cmd.category == "c"
        assert cmd.description == "d"
        assert cmd.triggers == ["t"]
        assert cmd.action_type == "at"
        assert cmd.action == "a"
        assert cmd.params == ["p"]
        assert cmd.confirm is True


# ===========================================================================
# 9. dry_run_command
# ===========================================================================

class TestDryRunCommand:
    """Tests for the dry_run_command preview function."""

    def test_matched_returns_full_info(self, cmd_mod):
        """Matched command returns full preview dict."""
        test_cmd = _make_cmd(
            name="open_chrome",
            category="app",
            description="Ouvre Chrome",
            triggers=["ouvre chrome"],
            action_type="app_open",
            action="start chrome",
            confirm=True,
        )
        cmd_mod.COMMANDS.clear()
        cmd_mod.COMMANDS.append(test_cmd)
        cmd_mod._trigger_index_built = False

        result = cmd_mod.dry_run_command("ouvre chrome")
        assert result["matched"] is True
        assert result["command"] == "open_chrome"
        assert result["category"] == "app"
        assert result["description"] == "Ouvre Chrome"
        assert result["action_type"] == "app_open"
        assert result["action_preview"] == "start chrome"
        assert result["confidence"] == 1.0
        assert result["confirm_required"] is True

    def test_no_match_returns_false(self, cmd_mod):
        """Unmatched input returns matched=False."""
        cmd_mod.COMMANDS.clear()
        cmd_mod._trigger_index_built = False

        result = cmd_mod.dry_run_command("rien a voir")
        assert result["matched"] is False
        assert "score" in result

    def test_param_substitution_in_preview(self, cmd_mod):
        """Parameters are substituted in the action preview."""
        test_cmd = _make_cmd(
            name="search",
            triggers=["cherche {query}"],
            action="google.com/search?q={query}",
            params=["query"],
        )
        cmd_mod.COMMANDS.clear()
        cmd_mod.COMMANDS.append(test_cmd)
        cmd_mod._trigger_index_built = False

        result = cmd_mod.dry_run_command("cherche python tutoriel")
        assert result["matched"] is True
        assert "python tutoriel" in result["action_preview"]
        assert "{query}" not in result["action_preview"]


# ===========================================================================
# 10. Macros
# ===========================================================================

class TestMacros:
    """Tests for macro registration and expansion."""

    def test_register_and_get_macro(self, cmd_mod):
        """Register a macro and retrieve it."""
        cmd1 = _make_cmd(name="step1")
        cmd2 = _make_cmd(name="step2")
        cmd_mod.COMMANDS.clear()
        cmd_mod.COMMANDS.extend([cmd1, cmd2])
        cmd_mod._MACROS.clear()

        cmd_mod.register_macro("my_macro", ["step1", "step2"], "Test macro")
        macros = cmd_mod.get_macros()
        assert "my_macro" in macros
        assert macros["my_macro"] == ["step1", "step2"]

    def test_register_macro_unknown_command_raises(self, cmd_mod):
        """Registering a macro with unknown command raises ValueError."""
        cmd_mod.COMMANDS.clear()
        cmd_mod._MACROS.clear()

        with pytest.raises(ValueError, match="Unknown command"):
            cmd_mod.register_macro("bad_macro", ["nonexistent_cmd"])

    def test_expand_macro(self, cmd_mod):
        """Expanding a macro returns the constituent commands."""
        cmd1 = _make_cmd(name="step1")
        cmd2 = _make_cmd(name="step2")
        cmd_mod.COMMANDS.clear()
        cmd_mod.COMMANDS.extend([cmd1, cmd2])
        cmd_mod._MACROS.clear()
        cmd_mod._MACROS["my_macro"] = ["step1", "step2"]

        expanded = cmd_mod.expand_macro("my_macro")
        assert len(expanded) == 2
        assert expanded[0].name == "step1"
        assert expanded[1].name == "step2"

    def test_expand_nonexistent_macro(self, cmd_mod):
        """Expanding a non-existent macro returns empty list."""
        cmd_mod._MACROS.clear()
        assert cmd_mod.expand_macro("nope") == []
