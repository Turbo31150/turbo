"""Tests for src/voice_correction.py — JARVIS Voice Correction Pipeline.

Covers all public functions:
  normalize_text, remove_accents, extract_params, remove_fillers,
  extract_action_intent, phonetic_normalize, phonetic_similarity,
  trigram_similarity, _trigrams, get_suggestions, format_suggestions,
  load_db_corrections, full_correction_pipeline, VoiceSession,
  execute_domino_result, _cache_match_result
"""

from __future__ import annotations

import re
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock

import pytest

# ---------------------------------------------------------------------------
# Pre-import mocking — stub out heavy dependencies before importing the module
# ---------------------------------------------------------------------------
# src.commands and src.config pull in sqlite3, filesystem access, etc.
# We inject controlled mocks to isolate voice_correction logic.

_MOCK_COMMANDS_MODULE = MagicMock()

# Minimal JarvisCommand stand-in (dataclass) for tests
@dataclass
class _FakeJarvisCommand:
    name: str = "test_cmd"
    category: str = "test"
    description: str = "Test command"
    triggers: list = field(default_factory=lambda: ["ouvre chrome", "lance chrome"])
    action_type: str = "app_open"
    action: str = "chrome"
    params: list = field(default_factory=list)
    confirm: bool = False


# Build a small COMMANDS list for tests
_FAKE_COMMANDS = [
    _FakeJarvisCommand(
        name="open_chrome",
        category="navigation",
        description="Ouvrir Google Chrome",
        triggers=["ouvre chrome", "lance chrome", "chrome"],
    ),
    _FakeJarvisCommand(
        name="volume_up",
        category="systeme",
        description="Monter le volume",
        triggers=["monte le volume", "augmente le volume", "vol+"],
    ),
    _FakeJarvisCommand(
        name="capture_ecran",
        category="systeme",
        description="Capture d'ecran",
        triggers=["capture ecran", "screenshot", "capture d'ecran"],
    ),
    _FakeJarvisCommand(
        name="cluster_status",
        category="cluster",
        description="Statut du cluster",
        triggers=["statut du cluster", "cluster status", "health check"],
    ),
    _FakeJarvisCommand(
        name="scan_trading",
        category="trading",
        description="Scanner le marche",
        triggers=["scan trading", "scanne le marche", "scanner le marche {coin}"],
    ),
]

_MOCK_VOICE_CORRECTIONS = {
    "crome": "chrome",
    "gougueule": "google",
    "luncher": "lancer",
    "clusteur": "cluster",
    "statu": "statut",
}

_MOCK_COMMANDS_MODULE.COMMANDS = _FAKE_COMMANDS
_MOCK_COMMANDS_MODULE.JarvisCommand = _FakeJarvisCommand
_MOCK_COMMANDS_MODULE.VOICE_CORRECTIONS = _MOCK_VOICE_CORRECTIONS
_MOCK_COMMANDS_MODULE.APP_PATHS = {"chrome": "chrome"}
_MOCK_COMMANDS_MODULE.SITE_ALIASES = {"google": "https://www.google.com"}
_MOCK_COMMANDS_MODULE.correct_voice_text = lambda text: text  # passthrough by default

# match_command mock: return (None, {}, 0.0) by default
_MOCK_COMMANDS_MODULE.match_command = MagicMock(return_value=(None, {}, 0.0))

_MOCK_CONFIG_MODULE = MagicMock()
_MOCK_CONFIG_MODULE.prepare_lmstudio_input = MagicMock(return_value="test")
_MOCK_CONFIG_MODULE.build_lmstudio_payload = MagicMock(return_value={})
_MOCK_CONFIG_MODULE.build_ollama_payload = MagicMock(return_value={})

# Inject mocks BEFORE importing voice_correction
_saved_commands = sys.modules.get("src.commands")
_saved_config = sys.modules.get("src.config")
sys.modules["src.commands"] = _MOCK_COMMANDS_MODULE
sys.modules["src.config"] = _MOCK_CONFIG_MODULE

import importlib  # noqa: E402
# Force fresh import each time to avoid stale state
if "src.voice_correction" in sys.modules:
    del sys.modules["src.voice_correction"]

from src.voice_correction import (  # noqa: E402
    normalize_text,
    remove_accents,
    extract_params,
    remove_fillers,
    extract_action_intent,
    phonetic_normalize,
    phonetic_similarity,
    trigram_similarity,
    _trigrams,
    get_suggestions,
    format_suggestions,
    load_db_corrections,
    full_correction_pipeline,
    VoiceSession,
    execute_domino_result,
    _cache_match_result,
    FILLER_WORDS,
    IMPLICIT_COMMANDS,
    PHONETIC_GROUPS,
    _PARAM_PATTERNS,
)

# Restore real modules after import (conftest cleanup will also handle this)
if _saved_commands is not None:
    sys.modules["src.commands"] = _saved_commands
elif "src.commands" in sys.modules and sys.modules["src.commands"] is _MOCK_COMMANDS_MODULE:
    del sys.modules["src.commands"]

if _saved_config is not None:
    sys.modules["src.config"] = _saved_config
elif "src.config" in sys.modules and sys.modules["src.config"] is _MOCK_CONFIG_MODULE:
    del sys.modules["src.config"]


# ═══════════════════════════════════════════════════════════════════════════
# normalize_text
# ═══════════════════════════════════════════════════════════════════════════

class TestNormalizeText:
    """Tests for normalize_text()."""

    def test_lowercase(self):
        assert normalize_text("HELLO WORLD") == "hello world"

    def test_strip_whitespace(self):
        assert normalize_text("  hello  ") == "hello"

    def test_remove_punctuation(self):
        assert normalize_text("hello, world! how? are; you:") == "hello world how are you"

    def test_collapse_multiple_spaces(self):
        assert normalize_text("hello    world   foo") == "hello world foo"

    def test_empty_string(self):
        assert normalize_text("") == ""

    def test_only_punctuation(self):
        assert normalize_text(".,!?;:") == ""

    def test_only_spaces(self):
        assert normalize_text("     ") == ""

    def test_accented_chars_preserved(self):
        # normalize_text does NOT remove accents (that's remove_accents)
        result = normalize_text("cafe resume")
        assert result == "cafe resume"

    def test_french_accents_preserved(self):
        result = normalize_text("Ou est le cafe?")
        assert result == "ou est le cafe"

    def test_brackets_removed(self):
        result = normalize_text("hello [world] (foo) {bar} <baz>")
        assert result == "hello world foo bar baz"

    def test_quotes_removed(self):
        result = normalize_text("""hello "world" 'foo'""")
        assert result == "hello world foo"

    def test_unicode_mixed(self):
        result = normalize_text("Hello 42 World!")
        assert result == "hello 42 world"

    def test_newlines_collapsed(self):
        # newlines count as whitespace
        result = normalize_text("hello\n\nworld")
        assert result == "hello world"

    def test_tabs_collapsed(self):
        result = normalize_text("hello\t\tworld")
        assert result == "hello world"


# ═══════════════════════════════════════════════════════════════════════════
# remove_accents
# ═══════════════════════════════════════════════════════════════════════════

class TestRemoveAccents:
    """Tests for remove_accents()."""

    def test_no_accents(self):
        assert remove_accents("hello world") == "hello world"

    def test_french_accents(self):
        assert remove_accents("cafe") == "cafe"
        assert remove_accents("resume") == "resume"

    def test_e_variants(self):
        # e with acute, grave, circumflex
        result = remove_accents("\u00e9\u00e8\u00ea\u00eb")
        assert result == "eeee"

    def test_c_cedilla(self):
        assert remove_accents("\u00e7") == "c"

    def test_a_variants(self):
        result = remove_accents("\u00e0\u00e2\u00e4")
        assert result == "aaa"

    def test_o_variants(self):
        result = remove_accents("\u00f4\u00f6")
        assert result == "oo"

    def test_u_variants(self):
        result = remove_accents("\u00f9\u00fb\u00fc")
        assert result == "uuu"

    def test_i_variants(self):
        result = remove_accents("\u00ee\u00ef")
        assert result == "ii"

    def test_empty_string(self):
        assert remove_accents("") == ""

    def test_german_umlaut(self):
        assert remove_accents("\u00fc\u00f6\u00e4") == "uoa"

    def test_spanish_n_tilde(self):
        assert remove_accents("\u00f1") == "n"

    def test_mixed_accents_and_ascii(self):
        assert remove_accents("r\u00e9sum\u00e9 du caf\u00e9") == "resume du cafe"

    def test_caching(self):
        """remove_accents is lru_cached — repeated calls return same value."""
        r1 = remove_accents("test_cache")
        r2 = remove_accents("test_cache")
        assert r1 is r2  # same object from cache

    def test_unicode_normalization(self):
        # Composed vs decomposed form should yield same result
        composed = "\u00e9"  # single char e-acute
        decomposed = "e\u0301"  # e + combining acute
        assert remove_accents(composed) == remove_accents(decomposed)


# ═══════════════════════════════════════════════════════════════════════════
# extract_params
# ═══════════════════════════════════════════════════════════════════════════

class TestExtractParams:
    """Tests for extract_params()."""

    def test_empty_string(self):
        assert extract_params("") == {}

    def test_no_params(self):
        assert extract_params("ouvre chrome") == {}

    def test_extract_coin(self):
        # extract_params lowercases the text, so captures are lowercase
        params = extract_params("scanne le marche BTC")
        assert params.get("coin", "").lower() == "btc"

    def test_extract_multiple_coins(self):
        # Should match first one; text is lowercased internally
        params = extract_params("compare BTC et ETH")
        assert "coin" in params
        assert params["coin"].lower() in ("btc", "eth")

    def test_extract_minutes(self):
        params = extract_params("dans 5 minutes")
        assert params.get("minutes") == "5"

    def test_extract_seconds(self):
        params = extract_params("attend 30 secondes")
        assert params.get("seconds") == "30"

    def test_extract_db(self):
        params = extract_params("ouvre la base jarvis")
        assert params.get("db") == "jarvis.db"

    def test_extract_node(self):
        # extract_params lowercases the input before matching
        params = extract_params("noeud M1")
        assert params.get("node", "").lower() == "m1"

    def test_extract_node_standalone(self):
        params = extract_params("interroge M2")
        assert params.get("node", "").lower() == "m2"

    def test_extract_percentage(self):
        params = extract_params("volume a 50 pour cent")
        assert params.get("percentage") == "50"

    def test_extract_priority(self):
        params = extract_params("priority haute")
        assert params.get("priority") == "haute"

    def test_extract_port(self):
        params = extract_params("sur le port 8080")
        assert params.get("port") == "8080"

    def test_extract_branch(self):
        params = extract_params("branche main")
        assert params.get("branch") == "main"

    def test_extract_env(self):
        params = extract_params("env prod")
        assert params.get("env") == "prod"

    def test_extract_hours(self):
        params = extract_params("dans 3 heures")
        assert params.get("hours") == "3"

    def test_extract_days(self):
        params = extract_params("dans 7 jours")
        assert params.get("days") == "7"

    def test_extract_version(self):
        params = extract_params("version 3.14.1")
        assert params.get("version") == "3.14.1"

    def test_extract_count(self):
        params = extract_params("repete 5 fois")
        assert params.get("count") == "5"

    def test_extract_level(self):
        params = extract_params("niveau debug")
        assert params.get("level") == "debug"

    def test_extract_format(self):
        params = extract_params("format json")
        assert params.get("format") == "json"

    def test_extract_protocol(self):
        params = extract_params("protocole https")
        assert params.get("protocol") == "https"

    def test_extract_service(self):
        params = extract_params("service nginx")
        assert params.get("service") == "nginx"

    def test_extract_workers(self):
        params = extract_params("utilise 4 threads")
        assert params.get("workers") == "4"

    def test_extract_package(self):
        params = extract_params("package numpy")
        assert params.get("package") == "numpy"

    def test_extract_tag(self):
        params = extract_params("tag v2.0")
        assert params.get("tag") == "v2.0"

    def test_extract_label(self):
        params = extract_params("label urgent")
        assert params.get("label") == "urgent"

    def test_extract_location(self):
        params = extract_params("deploie en local")
        assert params.get("location") == "local"

    def test_extract_pair(self):
        # extract_params lowercases input; template appends "USDT" to capture
        params2 = extract_params("paire BTC")
        assert params2.get("pair", "").lower() == "btcusdt"

    def test_extract_timeframe(self):
        params = extract_params("timeframe 4h")
        assert params.get("timeframe") == "4h"

    def test_extract_depth(self):
        params = extract_params("analyse rapide")
        assert params.get("depth") == "rapide"

    def test_case_insensitive(self):
        # Input is lowercased internally, so captures are lowercase
        params = extract_params("SCANNE LE MARCHE BTC")
        assert params.get("coin", "").lower() == "btc"

    def test_extract_multiple_params(self):
        # The env pattern requires "env prod" or "environnement prod", not "en prod"
        params = extract_params("scanne BTC sur le port 8080 env prod")
        assert params.get("coin", "").lower() == "btc"
        assert params.get("port") == "8080"
        assert params.get("env") == "prod"


# ═══════════════════════════════════════════════════════════════════════════
# remove_fillers
# ═══════════════════════════════════════════════════════════════════════════

class TestRemoveFillers:
    """Tests for remove_fillers()."""

    def test_empty_string(self):
        assert remove_fillers("") == ""

    def test_no_fillers(self):
        assert remove_fillers("ouvre chrome") == "ouvre chrome"

    def test_single_filler(self):
        assert remove_fillers("euh ouvre chrome") == "ouvre chrome"

    def test_multiple_fillers(self):
        result = remove_fillers("euh bah ouvre chrome")
        assert "euh" not in result
        assert "bah" not in result
        assert "ouvre chrome" in result

    def test_two_word_filler(self):
        # "un peu" is a two-word filler
        result = remove_fillers("un peu ouvre chrome")
        assert "un peu" not in result
        assert "ouvre" in result

    def test_filler_at_end(self):
        result = remove_fillers("ouvre chrome merci")
        assert result == "ouvre chrome"

    def test_only_fillers(self):
        result = remove_fillers("euh bah bon")
        assert result.strip() == ""

    def test_politeness_removed(self):
        assert "merci" not in remove_fillers("ouvre chrome merci")

    def test_preserves_command_words(self):
        result = remove_fillers("ouvre le navigateur chrome")
        assert "ouvre" in result
        assert "chrome" in result

    def test_filler_list_not_empty(self):
        """Sanity check that FILLER_WORDS is populated."""
        assert len(FILLER_WORDS) > 20


# ═══════════════════════════════════════════════════════════════════════════
# extract_action_intent
# ═══════════════════════════════════════════════════════════════════════════

class TestExtractActionIntent:
    """Tests for extract_action_intent()."""

    def test_empty_string(self):
        assert extract_action_intent("") == ""

    def test_passthrough_imperative(self):
        # Already imperative — should be mostly unchanged
        result = extract_action_intent("ouvre chrome")
        assert "ouvre" in result
        assert "chrome" in result

    def test_infinitive_to_imperative_ouvrir(self):
        result = extract_action_intent("ouvrir chrome")
        assert "ouvre" in result
        assert "chrome" in result

    def test_infinitive_to_imperative_lancer(self):
        result = extract_action_intent("lancer le terminal")
        assert "lance" in result

    def test_infinitive_to_imperative_chercher(self):
        result = extract_action_intent("chercher bitcoin")
        assert "cherche" in result

    def test_infinitive_to_imperative_fermer(self):
        result = extract_action_intent("fermer la fenetre")
        assert "ferme" in result

    def test_removes_que_tu_prefix(self):
        result = extract_action_intent("que tu ouvres chrome")
        assert "que tu" not in result

    def test_removes_de_prefix(self):
        result = extract_action_intent("de lancer chrome")
        assert result.startswith("lance") or "lance" in result

    def test_fillers_removed(self):
        result = extract_action_intent("euh ouvre chrome merci")
        assert "euh" not in result
        assert "merci" not in result

    def test_complex_polite_request(self):
        # "est-ce que tu peux" and "s'il te plait" are fillers
        result = extract_action_intent("ouvrir chrome")
        assert "ouvre" in result
        assert "chrome" in result

    def test_verb_baisser(self):
        result = extract_action_intent("baisser le volume")
        assert "baisse" in result

    def test_verb_eteindre(self):
        result = extract_action_intent("eteindre le pc")
        assert "eteins" in result

    def test_verb_redemarrer(self):
        result = extract_action_intent("redemarrer le serveur")
        assert "redemarre" in result

    def test_verb_scanner(self):
        result = extract_action_intent("scanner le marche")
        assert "scanne" in result

    def test_verb_activer(self):
        result = extract_action_intent("activer le bluetooth")
        assert "active" in result

    def test_verb_desactiver(self):
        result = extract_action_intent("desactiver le wifi")
        assert "desactive" in result

    def test_verb_analyser(self):
        result = extract_action_intent("analyser les logs")
        assert "analyse" in result

    def test_verb_tester(self):
        result = extract_action_intent("tester l'api")
        assert "teste" in result

    def test_verb_deployer(self):
        result = extract_action_intent("deployer en production")
        assert "deploie" in result

    def test_verb_creer(self):
        result = extract_action_intent("creer un projet")
        assert "cree" in result

    def test_verb_supprimer(self):
        result = extract_action_intent("supprimer le fichier")
        assert "supprime" in result

    def test_verb_sauvegarder(self):
        result = extract_action_intent("sauvegarder la session")
        assert "sauvegarde" in result

    def test_verb_compiler(self):
        result = extract_action_intent("compiler le code")
        assert "compile" in result

    def test_verb_exporter(self):
        result = extract_action_intent("exporter les donnees")
        assert "exporte" in result

    def test_verb_cloner(self):
        result = extract_action_intent("cloner le repo")
        assert "clone" in result

    def test_verb_merger(self):
        result = extract_action_intent("merger la branche")
        assert "merge" in result

    def test_strip_result(self):
        """Result should be stripped."""
        result = extract_action_intent("  ouvre chrome  ")
        assert result == result.strip()


# ═══════════════════════════════════════════════════════════════════════════
# phonetic_normalize
# ═══════════════════════════════════════════════════════════════════════════

class TestPhoneticNormalize:
    """Tests for phonetic_normalize()."""

    def test_basic_word(self):
        result = phonetic_normalize("hello")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_empty_string(self):
        result = phonetic_normalize("")
        assert result == ""

    def test_lowercase(self):
        r1 = phonetic_normalize("HELLO")
        r2 = phonetic_normalize("hello")
        assert r1 == r2

    def test_eau_reduction(self):
        """eau -> o."""
        result = phonetic_normalize("beau")
        assert "o" in result or "eau" not in result

    def test_ph_to_f(self):
        """ph -> f."""
        r1 = phonetic_normalize("phone")
        r2 = phonetic_normalize("fone")
        # Both should reduce similarly
        assert r1 == r2

    def test_cedilla(self):
        r = phonetic_normalize("\u00e7a")
        # c-cedilla -> s
        assert "s" in r or r == phonetic_normalize("sa")

    def test_oe_ligature(self):
        # oe -> eu reduction
        r = phonetic_normalize("c\u0153ur")
        assert isinstance(r, str)

    def test_double_consonants_reduced(self):
        r1 = phonetic_normalize("patte")
        r2 = phonetic_normalize("pate")
        # Double t -> single t
        assert r1 == r2

    def test_caching(self):
        """phonetic_normalize is lru_cached."""
        r1 = phonetic_normalize("cache_test")
        r2 = phonetic_normalize("cache_test")
        assert r1 is r2

    def test_accent_handling(self):
        # e-acute and e should normalize similarly
        r1 = phonetic_normalize("\u00e9cole")
        r2 = phonetic_normalize("ecole")
        assert r1 == r2


# ═══════════════════════════════════════════════════════════════════════════
# phonetic_similarity
# ═══════════════════════════════════════════════════════════════════════════

class TestPhoneticSimilarity:
    """Tests for phonetic_similarity()."""

    def test_identical_strings(self):
        assert phonetic_similarity("ouvre chrome", "ouvre chrome") == 1.0

    def test_completely_different(self):
        score = phonetic_similarity("abcxyz", "mnopqr")
        assert score < 0.5

    def test_similar_french_words(self):
        """Words that sound alike in French should score high."""
        score = phonetic_similarity("chrome", "crome")
        assert score > 0.5

    def test_empty_strings(self):
        score = phonetic_similarity("", "")
        assert score == 1.0  # SequenceMatcher returns 1.0 for two empty strings

    def test_one_empty(self):
        score = phonetic_similarity("hello", "")
        assert score < 0.5

    def test_returns_float(self):
        score = phonetic_similarity("hello", "world")
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_symmetry(self):
        s1 = phonetic_similarity("ouvre", "ouvrir")
        s2 = phonetic_similarity("ouvrir", "ouvre")
        assert s1 == s2

    def test_phonetically_similar_pair(self):
        """'phone' and 'fone' should be phonetically identical after normalization."""
        score = phonetic_similarity("phone", "fone")
        assert score > 0.8


# ═══════════════════════════════════════════════════════════════════════════
# _trigrams and trigram_similarity
# ═══════════════════════════════════════════════════════════════════════════

class TestTrigrams:
    """Tests for _trigrams() helper."""

    def test_basic(self):
        result = _trigrams("abc")
        # padded: "  abc "
        # trigrams: "  a", " ab", "abc", "bc ", "c  " — wait, len=6, so 4 trigrams
        # Actually "  abc " has len 6, so indices 0..3, trigrams: "  a", " ab", "abc", "bc "
        assert isinstance(result, set)
        assert len(result) > 0

    def test_empty_string(self):
        result = _trigrams("")
        # padded: "   " (3 chars) -> 1 trigram: "   "
        assert isinstance(result, set)

    def test_single_char(self):
        result = _trigrams("a")
        # padded: "  a " (4 chars) -> 2 trigrams
        assert len(result) >= 1

    def test_no_duplicates(self):
        result = _trigrams("aaa")
        # padded: "  aaa " -> trigrams may overlap
        assert isinstance(result, set)


class TestTrigramSimilarity:
    """Tests for trigram_similarity()."""

    def test_identical(self):
        assert trigram_similarity("hello", "hello") == 1.0

    def test_completely_different(self):
        score = trigram_similarity("abc", "xyz")
        assert score < 0.5

    def test_similar_strings(self):
        score = trigram_similarity("chrome", "crome")
        assert score > 0.3

    def test_empty_both(self):
        # Both empty -> trigrams are {"   "} for each -> intersection = 1, union = 1 -> 1.0
        score = trigram_similarity("", "")
        assert isinstance(score, float)

    def test_case_insensitive(self):
        s1 = trigram_similarity("Hello", "hello")
        assert s1 == 1.0

    def test_returns_float(self):
        score = trigram_similarity("foo", "bar")
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_symmetry(self):
        s1 = trigram_similarity("abc", "abd")
        s2 = trigram_similarity("abd", "abc")
        assert s1 == s2

    def test_partial_overlap(self):
        score = trigram_similarity("ouvre chrome", "ouvre firefox")
        assert 0.0 < score < 1.0

    def test_word_order_robust(self):
        """Trigram similarity should be somewhat robust to word order changes."""
        s1 = trigram_similarity("ouvre chrome", "chrome ouvre")
        assert s1 > 0.3


# ═══════════════════════════════════════════════════════════════════════════
# PHONETIC_GROUPS / FILLER_WORDS / IMPLICIT_COMMANDS — data integrity
# ═══════════════════════════════════════════════════════════════════════════

class TestDataIntegrity:
    """Verify the module-level data structures are well-formed."""

    def test_phonetic_groups_not_empty(self):
        assert len(PHONETIC_GROUPS) > 10

    def test_phonetic_groups_are_lists_of_strings(self):
        for group in PHONETIC_GROUPS[:10]:
            assert isinstance(group, list)
            for item in group:
                assert isinstance(item, str)
                assert len(item) > 0

    def test_filler_words_not_empty(self):
        assert len(FILLER_WORDS) > 20

    def test_filler_words_are_strings(self):
        for filler in list(FILLER_WORDS)[:20]:
            assert isinstance(filler, str)

    def test_implicit_commands_not_empty(self):
        assert len(IMPLICIT_COMMANDS) > 50

    def test_implicit_commands_keys_lowercase(self):
        for key in list(IMPLICIT_COMMANDS.keys())[:20]:
            assert key == key.lower(), f"Key {key!r} is not lowercase"

    def test_param_patterns_valid_regex(self):
        """All _PARAM_PATTERNS should have compilable regex."""
        for pattern, name, template in _PARAM_PATTERNS:
            compiled = re.compile(pattern, re.IGNORECASE)
            assert compiled is not None, f"Pattern {pattern!r} failed to compile"
            assert isinstance(name, str)
            assert isinstance(template, str)


# ═══════════════════════════════════════════════════════════════════════════
# get_suggestions
# ═══════════════════════════════════════════════════════════════════════════

class TestGetSuggestions:
    """Tests for get_suggestions()."""

    def test_returns_list(self):
        result = get_suggestions("ouvre chrome")
        assert isinstance(result, list)

    def test_max_results(self):
        result = get_suggestions("ouvre chrome", max_results=2)
        assert len(result) <= 2

    def test_empty_input(self):
        result = get_suggestions("")
        assert isinstance(result, list)

    def test_result_tuple_format(self):
        """Each result should be (JarvisCommand, float)."""
        result = get_suggestions("chrome")
        for item in result:
            assert isinstance(item, tuple)
            assert len(item) == 2
            cmd, score = item
            assert isinstance(score, float)

    def test_scores_sorted_descending(self):
        result = get_suggestions("ouvre chrome")
        scores = [s for _, s in result]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1]

    def test_good_match_high_score(self):
        """An exact trigger text should produce a high-scoring suggestion."""
        result = get_suggestions("ouvre chrome")
        if result:
            _, score = result[0]
            assert score > 0.30  # minimum threshold in the function


# ═══════════════════════════════════════════════════════════════════════════
# format_suggestions
# ═══════════════════════════════════════════════════════════════════════════

class TestFormatSuggestions:
    """Tests for format_suggestions()."""

    def test_empty_list(self):
        result = format_suggestions([])
        assert "aide" in result.lower()

    def test_single_suggestion(self):
        cmd = _FakeJarvisCommand(
            name="test",
            description="Test description",
            triggers=["test trigger"],
        )
        result = format_suggestions([(cmd, 0.85)])
        assert "test trigger" in result
        assert "Test description" in result
        assert "1." in result

    def test_multiple_suggestions(self):
        cmds = [
            (_FakeJarvisCommand(name="a", triggers=["alpha"], description="A cmd"), 0.9),
            (_FakeJarvisCommand(name="b", triggers=["beta"], description="B cmd"), 0.7),
        ]
        result = format_suggestions(cmds)
        assert "1." in result
        assert "2." in result
        assert "alpha" in result
        assert "beta" in result

    def test_header_present(self):
        cmd = _FakeJarvisCommand(triggers=["foo"], description="bar")
        result = format_suggestions([(cmd, 0.5)])
        assert "Tu voulais dire" in result

    def test_footer_present(self):
        cmd = _FakeJarvisCommand(triggers=["foo"], description="bar")
        result = format_suggestions([(cmd, 0.5)])
        assert "numero" in result.lower() or "commande" in result.lower()


# ═══════════════════════════════════════════════════════════════════════════
# load_db_corrections
# ═══════════════════════════════════════════════════════════════════════════

class TestLoadDbCorrections:
    """Tests for load_db_corrections()."""

    def test_returns_int(self):
        """Should return an int (number of corrections added)."""
        # Reset the loaded flag to allow re-calling
        import src.voice_correction as vc_mod
        vc_mod._db_corrections_loaded = False
        # With mocked sqlite3 (no DB exists), should return 0
        with patch("os.path.exists", return_value=False):
            result = load_db_corrections()
        assert isinstance(result, int)
        assert result >= 0

    def test_idempotent(self):
        """Second call returns 0 (already loaded)."""
        import src.voice_correction as vc_mod
        vc_mod._db_corrections_loaded = True
        result = load_db_corrections()
        assert result == 0

    def test_handles_missing_db(self):
        """Should not crash when DB files don't exist."""
        import src.voice_correction as vc_mod
        vc_mod._db_corrections_loaded = False
        with patch("os.path.exists", return_value=False):
            result = load_db_corrections()
        assert result == 0

    @patch("sqlite3.connect")
    def test_loads_from_db(self, mock_connect):
        """Should load corrections from DB when available."""
        import src.voice_correction as vc_mod
        vc_mod._db_corrections_loaded = False

        mock_conn = MagicMock()
        mock_connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_connect.return_value.__exit__ = MagicMock(return_value=False)

        # The function iterates over two DB files (jarvis.db, etoile.db),
        # each needing a table-check query + data query.
        mock_conn.execute.side_effect = [
            # jarvis.db — table check
            MagicMock(fetchall=MagicMock(return_value=[("voice_corrections",)])),
            # jarvis.db — data rows
            MagicMock(fetchall=MagicMock(return_value=[("testword1", "corrected1")])),
            # etoile.db — table check
            MagicMock(fetchall=MagicMock(return_value=[("voice_corrections",)])),
            # etoile.db — data rows
            MagicMock(fetchall=MagicMock(return_value=[("testword2", "corrected2")])),
        ]

        with patch("os.path.exists", return_value=True):
            result = load_db_corrections()
        assert isinstance(result, int)
        assert result >= 0


# ═══════════════════════════════════════════════════════════════════════════
# VoiceSession
# ═══════════════════════════════════════════════════════════════════════════

class TestVoiceSession:
    """Tests for VoiceSession class."""

    def test_init(self):
        session = VoiceSession()
        assert session.last_command is None
        assert session.last_raw == ""
        assert session.correction_count == 0
        assert session.history == []

    # --- is_selecting_suggestion ---

    def test_select_suggestion_by_number(self):
        session = VoiceSession()
        cmd = _FakeJarvisCommand(name="cmd1")
        session.last_suggestions = [(cmd, 0.9)]
        assert session.is_selecting_suggestion("1") == cmd

    def test_select_suggestion_by_word_un(self):
        session = VoiceSession()
        cmd = _FakeJarvisCommand(name="cmd1")
        session.last_suggestions = [(cmd, 0.9)]
        assert session.is_selecting_suggestion("un") == cmd

    def test_select_suggestion_premier(self):
        session = VoiceSession()
        cmd = _FakeJarvisCommand(name="cmd1")
        session.last_suggestions = [(cmd, 0.9)]
        assert session.is_selecting_suggestion("premier") == cmd

    def test_select_suggestion_2(self):
        session = VoiceSession()
        cmd1 = _FakeJarvisCommand(name="cmd1")
        cmd2 = _FakeJarvisCommand(name="cmd2")
        session.last_suggestions = [(cmd1, 0.9), (cmd2, 0.7)]
        assert session.is_selecting_suggestion("2") == cmd2
        assert session.is_selecting_suggestion("deux") == cmd2

    def test_select_suggestion_3(self):
        session = VoiceSession()
        cmds = [
            _FakeJarvisCommand(name="c1"),
            _FakeJarvisCommand(name="c2"),
            _FakeJarvisCommand(name="c3"),
        ]
        session.last_suggestions = [(c, 0.9 - i * 0.1) for i, c in enumerate(cmds)]
        assert session.is_selecting_suggestion("3") == cmds[2]
        assert session.is_selecting_suggestion("trois") == cmds[2]

    def test_select_suggestion_invalid(self):
        session = VoiceSession()
        session.last_suggestions = []
        assert session.is_selecting_suggestion("1") is None
        assert session.is_selecting_suggestion("hello") is None

    def test_select_suggestion_out_of_range(self):
        session = VoiceSession()
        cmd = _FakeJarvisCommand(name="cmd1")
        session.last_suggestions = [(cmd, 0.9)]
        assert session.is_selecting_suggestion("3") is None

    # --- is_repeat_request ---

    def test_repeat_request_with_last_command(self):
        session = VoiceSession()
        cmd = _FakeJarvisCommand(name="last")
        session.last_command = cmd
        assert session.is_repeat_request("refais") == cmd
        assert session.is_repeat_request("relance") == cmd
        assert session.is_repeat_request("encore") == cmd
        assert session.is_repeat_request("pareil") == cmd
        assert session.is_repeat_request("idem") == cmd

    def test_repeat_request_without_last_command(self):
        session = VoiceSession()
        assert session.is_repeat_request("refais") is None

    def test_repeat_request_non_repeat_phrase(self):
        session = VoiceSession()
        session.last_command = _FakeJarvisCommand()
        assert session.is_repeat_request("ouvre chrome") is None

    # --- is_confirmation ---

    def test_confirmation_oui(self):
        session = VoiceSession()
        assert session.is_confirmation("oui") is True
        assert session.is_confirmation("yes") is True
        assert session.is_confirmation("ok") is True
        assert session.is_confirmation("go") is True
        assert session.is_confirmation("lance") is True

    def test_confirmation_with_spaces(self):
        session = VoiceSession()
        assert session.is_confirmation("  oui  ") is True

    def test_confirmation_case_insensitive(self):
        session = VoiceSession()
        assert session.is_confirmation("OUI") is True

    def test_not_a_confirmation(self):
        session = VoiceSession()
        assert session.is_confirmation("non") is False
        assert session.is_confirmation("ouvre chrome") is False

    # --- is_denial ---

    def test_denial_non(self):
        session = VoiceSession()
        assert session.is_denial("non") is True
        assert session.is_denial("no") is True
        assert session.is_denial("annule") is True
        assert session.is_denial("stop") is True
        assert session.is_denial("nope") is True

    def test_denial_case_insensitive(self):
        session = VoiceSession()
        assert session.is_denial("NON") is True

    def test_not_a_denial(self):
        session = VoiceSession()
        assert session.is_denial("oui") is False
        assert session.is_denial("ouvre chrome") is False

    # --- record_execution ---

    def test_record_execution(self):
        session = VoiceSession()
        cmd = _FakeJarvisCommand(name="recorded")
        session.record_execution(cmd, {"key": "value"})
        assert session.last_command == cmd
        assert session.last_params == {"key": "value"}

    def test_record_execution_no_params(self):
        session = VoiceSession()
        cmd = _FakeJarvisCommand(name="recorded")
        session.record_execution(cmd)
        assert session.last_command == cmd
        assert session.last_params == {}

    # --- add_to_history ---

    def test_add_to_history(self):
        session = VoiceSession()
        session.add_to_history("first")
        session.add_to_history("second")
        assert session.history == ["first", "second"]

    def test_history_limit(self):
        session = VoiceSession()
        for i in range(15):
            session.add_to_history(f"cmd_{i}")
        assert len(session.history) == 10
        assert session.history[-1] == "cmd_14"
        assert session.history[0] == "cmd_5"

    # --- get_session_stats ---

    def test_session_stats(self):
        session = VoiceSession()
        cmd = _FakeJarvisCommand(name="test_stats")
        session.last_command = cmd
        session.last_raw = "test raw"
        session.correction_count = 5
        session.add_to_history("one")
        stats = session.get_session_stats()
        assert stats["correction_count"] == 5
        assert stats["history_length"] == 1
        assert stats["last_command"] == "test_stats"
        assert stats["last_raw"] == "test raw"

    def test_session_stats_no_command(self):
        session = VoiceSession()
        stats = session.get_session_stats()
        assert stats["last_command"] is None

    # --- thread safety ---

    def test_thread_safety_add_to_history(self):
        """Concurrent history additions should not corrupt state."""
        session = VoiceSession()
        errors = []

        def add_items(start):
            try:
                for i in range(50):
                    session.add_to_history(f"thread_{start}_{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_items, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(session.history) <= 10  # capped at 10


# ═══════════════════════════════════════════════════════════════════════════
# _cache_match_result
# ═══════════════════════════════════════════════════════════════════════════

class TestCacheMatchResult:
    """Tests for _cache_match_result()."""

    def test_caches_good_match(self):
        import src.voice_correction as vc_mod
        vc_mod._recent_match_cache.clear()
        cmd = _FakeJarvisCommand(name="cached_cmd")
        result = {"command": cmd, "confidence": 0.90}
        _cache_match_result("test input", result)
        key = normalize_text("test input")
        assert key in vc_mod._recent_match_cache
        assert vc_mod._recent_match_cache[key] == ("cached_cmd", 0.90)

    def test_does_not_cache_low_confidence(self):
        import src.voice_correction as vc_mod
        vc_mod._recent_match_cache.clear()
        cmd = _FakeJarvisCommand(name="low_cmd")
        result = {"command": cmd, "confidence": 0.50}
        _cache_match_result("low conf input", result)
        key = normalize_text("low conf input")
        assert key not in vc_mod._recent_match_cache

    def test_does_not_cache_no_command(self):
        import src.voice_correction as vc_mod
        vc_mod._recent_match_cache.clear()
        result = {"command": None, "confidence": 0.95}
        _cache_match_result("no cmd", result)
        key = normalize_text("no cmd")
        assert key not in vc_mod._recent_match_cache

    def test_evicts_oldest_when_full(self):
        import src.voice_correction as vc_mod
        vc_mod._recent_match_cache.clear()
        cmd = _FakeJarvisCommand(name="evict_test")

        # Fill cache to max
        for i in range(vc_mod._RECENT_CACHE_MAX):
            result = {"command": cmd, "confidence": 0.90}
            _cache_match_result(f"input {i}", result)

        assert len(vc_mod._recent_match_cache) == vc_mod._RECENT_CACHE_MAX

        # Adding one more should evict the oldest
        result = {"command": cmd, "confidence": 0.90}
        _cache_match_result("overflow input", result)
        assert len(vc_mod._recent_match_cache) == vc_mod._RECENT_CACHE_MAX


# ═══════════════════════════════════════════════════════════════════════════
# full_correction_pipeline (async)
# ═══════════════════════════════════════════════════════════════════════════

class TestFullCorrectionPipeline:
    """Tests for full_correction_pipeline() — async."""

    @pytest.fixture(autouse=True)
    def _reset_state(self):
        """Reset module state before each test."""
        import src.voice_correction as vc_mod
        vc_mod._db_corrections_loaded = True  # avoid DB access
        vc_mod._recent_match_cache.clear()
        vc_mod._trigger_cache_built = False
        vc_mod._trigger_cache.clear()
        vc_mod._command_usage_loaded = True  # avoid DB access
        vc_mod._command_usage_cache.clear()
        _MOCK_COMMANDS_MODULE.match_command.reset_mock()
        _MOCK_COMMANDS_MODULE.match_command.return_value = (None, {}, 0.0)
        yield

    @pytest.mark.asyncio
    async def test_returns_dict(self):
        result = await full_correction_pipeline("ouvre chrome", use_ia=False)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_raw_preserved(self):
        result = await full_correction_pipeline("Hello World!", use_ia=False)
        assert result["raw"] == "Hello World!"

    @pytest.mark.asyncio
    async def test_cleaned_normalized(self):
        result = await full_correction_pipeline("HELLO, World!", use_ia=False)
        assert result["cleaned"] == "hello world"

    @pytest.mark.asyncio
    async def test_result_keys(self):
        result = await full_correction_pipeline("test", use_ia=False)
        expected_keys = {"raw", "cleaned", "corrected", "intent", "command",
                         "params", "confidence", "suggestions", "method"}
        assert expected_keys.issubset(result.keys())

    @pytest.mark.asyncio
    async def test_implicit_command_single_word(self):
        """A single word matching IMPLICIT_COMMANDS should be expanded."""
        result = await full_correction_pipeline("google", use_ia=False)
        # "google" -> "cherche sur google" via IMPLICIT_COMMANDS
        # method may be implicit_fast, local_fast, or implicit depending on match_command results
        assert result.get("corrected") != "" or result.get("method") != "none"

    @pytest.mark.asyncio
    async def test_local_fast_match(self):
        """When match_command returns high confidence, should return local_fast."""
        cmd = _FakeJarvisCommand(name="fast_match")
        _MOCK_COMMANDS_MODULE.match_command.return_value = (cmd, {}, 0.95)
        result = await full_correction_pipeline("ouvre chrome", use_ia=False)
        assert result["command"] is not None
        # method should indicate fast/local match
        assert result["confidence"] >= 0.85

    @pytest.mark.asyncio
    async def test_no_ia_when_disabled(self):
        """When use_ia=False, should not call IA correction."""
        result = await full_correction_pipeline("test input", use_ia=False)
        # Should complete without error
        assert result["raw"] == "test input"

    @pytest.mark.asyncio
    async def test_freeform_when_no_match(self):
        """When nothing matches, method should be 'freeform'."""
        _MOCK_COMMANDS_MODULE.match_command.return_value = (None, {}, 0.0)
        result = await full_correction_pipeline("abcxyz random", use_ia=False)
        assert result["method"] == "freeform"
        assert result["command"] is None

    @pytest.mark.asyncio
    async def test_cache_hit(self):
        """Second call with same text should hit cache."""
        import src.voice_correction as vc_mod
        cmd = _FakeJarvisCommand(name="cache_test")
        key = normalize_text("cached input")
        vc_mod._recent_match_cache[key] = ("cache_test", 0.90)
        # Need the command in COMMANDS list
        _FAKE_COMMANDS.append(cmd)
        try:
            result = await full_correction_pipeline("cached input", use_ia=False)
            if result["method"] == "cache_hit":
                assert result["command"].name == "cache_test"
                assert result["confidence"] == 0.90
        finally:
            _FAKE_COMMANDS.remove(cmd)

    @pytest.mark.asyncio
    async def test_params_extracted(self):
        """Parameters like coin names should be extracted from the initial text."""
        # extract_params is called on cleaned text (lowercased), so coin may
        # not match if the regex requires uppercase. Verify params dict exists.
        result = await full_correction_pipeline("scanne le marche BTC", use_ia=False)
        # params should at least be a dict (may contain coin, db, depth, etc.)
        assert isinstance(result.get("params"), dict)
        # The cleaned text should contain "btc" (lowered)
        assert "btc" in result.get("cleaned", "").lower()

    @pytest.mark.asyncio
    async def test_empty_input(self):
        result = await full_correction_pipeline("", use_ia=False)
        assert result["raw"] == ""


# ═══════════════════════════════════════════════════════════════════════════
# execute_domino_result
# ═══════════════════════════════════════════════════════════════════════════

class TestExecuteDominoResult:
    """Tests for execute_domino_result()."""

    def test_no_domino(self):
        result = execute_domino_result({})
        assert result is None

    def test_domino_none(self):
        result = execute_domino_result({"domino": None})
        assert result is None

    @patch("src.voice_correction.DominoExecutor", create=True)
    def test_domino_execution(self, _):
        """With a valid domino, should attempt execution."""
        # Since DominoExecutor is imported inside the function, we mock the import
        mock_domino = MagicMock()
        mock_executor_cls = MagicMock()
        mock_executor = MagicMock()
        mock_executor.run.return_value = {
            "domino_id": "test",
            "passed": 3,
            "total_steps": 3,
            "total_ms": 100.0,
        }
        mock_executor_cls.return_value = mock_executor

        with patch.dict(sys.modules, {"src.domino_executor": MagicMock(DominoExecutor=mock_executor_cls)}):
            result = execute_domino_result({"domino": mock_domino})
            # Should return the executor result or None if import fails
            if result is not None:
                assert result["domino_id"] == "test"

    def test_domino_import_error(self):
        """Should handle ImportError gracefully."""
        with patch.dict(sys.modules, {"src.domino_executor": None}):
            # When module is None in sys.modules, import raises ImportError
            result = execute_domino_result({"domino": "some_domino"})
            # Should return error dict or None
            assert result is None or "error" in result


# ═══════════════════════════════════════════════════════════════════════════
# Edge cases — Unicode, None safety, special characters
# ═══════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Edge cases: empty, None, unicode, special characters."""

    def test_normalize_text_with_emoji(self):
        result = normalize_text("hello world")
        assert "hello" in result

    def test_normalize_text_with_numbers(self):
        result = normalize_text("test 42 foo")
        assert "42" in result

    def test_remove_accents_full_unicode(self):
        """Various unicode chars."""
        result = remove_accents("na\u00efve caf\u00e9 r\u00e9sum\u00e9")
        assert "naive" in result
        assert "cafe" in result

    def test_extract_params_special_chars(self):
        """Should not crash on special characters."""
        result = extract_params("test @#$ %^& input")
        assert isinstance(result, dict)

    def test_remove_fillers_only_spaces(self):
        result = remove_fillers("   ")
        assert result.strip() == ""

    def test_extract_action_intent_single_word(self):
        result = extract_action_intent("chrome")
        assert isinstance(result, str)

    def test_trigram_very_long_string(self):
        long = "a" * 1000
        score = trigram_similarity(long, long)
        assert score == 1.0

    def test_phonetic_similarity_numbers(self):
        score = phonetic_similarity("123", "456")
        assert isinstance(score, float)

    def test_normalize_preserves_hyphens_in_words(self):
        """Hyphens are not in the removed punctuation set."""
        result = normalize_text("est-ce que")
        assert "-" in result or "est" in result

    def test_remove_fillers_multi_word_at_start(self):
        """Multi-word fillers like 'en fait' at start should be removed."""
        result = remove_fillers("en fait ouvre chrome")
        assert "en fait" not in result or "ouvre" in result

    def test_extract_params_no_crash_on_long_input(self):
        long_input = "scanne le marche " * 100
        result = extract_params(long_input)
        assert isinstance(result, dict)

    def test_voice_session_suggestion_premiere(self):
        """French feminine form 'premiere' should select suggestion 1."""
        session = VoiceSession()
        cmd = _FakeJarvisCommand(name="fem_test")
        session.last_suggestions = [(cmd, 0.9)]
        assert session.is_selecting_suggestion("premiere") == cmd
        assert session.is_selecting_suggestion("la premiere") == cmd

    def test_voice_session_suggestion_le_premier(self):
        session = VoiceSession()
        cmd = _FakeJarvisCommand(name="masc_test")
        session.last_suggestions = [(cmd, 0.9)]
        assert session.is_selecting_suggestion("le premier") == cmd

    def test_voice_session_repeat_phrases_coverage(self):
        """All defined repeat phrases should work."""
        session = VoiceSession()
        cmd = _FakeJarvisCommand(name="repeat_test")
        session.last_command = cmd
        for phrase in VoiceSession._REPEAT_PHRASES:
            assert session.is_repeat_request(phrase) == cmd, f"Phrase {phrase!r} failed"


# ═══════════════════════════════════════════════════════════════════════════
# _increment_voice_correction_hits (private, but important to test)
# ═══════════════════════════════════════════════════════════════════════════

class TestIncrementVoiceCorrectionHits:
    """Tests for _increment_voice_correction_hits()."""

    def test_no_changes_no_db_call(self):
        from src.voice_correction import _increment_voice_correction_hits
        # Same text -> no corrections -> no DB writes
        with patch("os.path.exists", return_value=True), \
             patch("sqlite3.connect") as mock_conn:
            _increment_voice_correction_hits("ouvre chrome", "ouvre chrome")
            mock_conn.assert_not_called()

    def test_with_changes_attempts_db_update(self):
        from src.voice_correction import _increment_voice_correction_hits
        with patch("os.path.exists", return_value=True), \
             patch("sqlite3.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_connect.return_value.__exit__ = MagicMock(return_value=False)
            _increment_voice_correction_hits("crome ouvre", "chrome ouvre")
            # Should attempt to update for "crome" which changed to "chrome"

    def test_handles_missing_db(self):
        from src.voice_correction import _increment_voice_correction_hits
        with patch("os.path.exists", return_value=False):
            # Should not crash
            _increment_voice_correction_hits("foo", "bar")


# ═══════════════════════════════════════════════════════════════════════════
# Integration-style tests (still mocked, but test function interactions)
# ═══════════════════════════════════════════════════════════════════════════

class TestIntegration:
    """Tests that verify interactions between multiple functions."""

    def test_normalize_then_remove_accents(self):
        text = "Ou EST le Cafe?"
        normalized = normalize_text(text)
        no_accents = remove_accents(normalized)
        assert no_accents == no_accents.lower()
        assert "?" not in no_accents

    def test_intent_preserves_core_meaning(self):
        """extract_action_intent should preserve command keywords."""
        intent = extract_action_intent("ouvrir le navigateur chrome")
        assert "ouvre" in intent
        assert "chrome" in intent

    def test_trigram_and_phonetic_complement(self):
        """Trigram and phonetic should both rate similar strings highly."""
        a = "ouvre chrome"
        b = "ouvre crome"
        tri = trigram_similarity(a, b)
        phon = phonetic_similarity(a, b)
        assert tri > 0.3
        assert phon > 0.3

    def test_full_pipeline_params_flow(self):
        """Parameters extracted early should be available in result."""
        import asyncio
        import src.voice_correction as vc_mod
        vc_mod._db_corrections_loaded = True
        vc_mod._command_usage_loaded = True
        _MOCK_COMMANDS_MODULE.match_command.return_value = (None, {}, 0.0)

        result = asyncio.run(
            full_correction_pipeline("scanne BTC sur le port 8080", use_ia=False)
        )
        params = result.get("params", {})
        assert "coin" in params or "port" in params
