"""Tests for src/intent_classifier.py — ML-like intent detection for voice commands.

Covers: IntentResult, INTENT_PATTERNS, ENTITY_PATTERNS, IntentClassifier
(classify, classify_single, _extract_entities, record_feedback, get_accuracy,
get_report), intent_classifier singleton.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Prevent loading stats from disk
with patch("src.intent_classifier.IntentClassifier._load_stats"):
    from src.intent_classifier import (
        IntentResult, INTENT_PATTERNS, ENTITY_PATTERNS,
        IntentClassifier, intent_classifier,
    )


# ===========================================================================
# IntentResult
# ===========================================================================

class TestIntentResult:
    def test_defaults(self):
        r = IntentResult(intent="query", confidence=0.8)
        assert r.entities == {}
        assert r.source == "rule"


# ===========================================================================
# Pattern Coverage
# ===========================================================================

class TestPatterns:
    def test_intent_patterns_exist(self):
        expected = {"navigation", "app_launch", "file_ops", "system_control",
                    "trading", "cluster_ops", "code_dev", "voice_control",
                    "query", "pipeline"}
        assert expected.issubset(set(INTENT_PATTERNS.keys()))

    def test_entity_patterns_exist(self):
        assert "url" in ENTITY_PATTERNS
        assert "crypto_pair" in ENTITY_PATTERNS
        assert "node_name" in ENTITY_PATTERNS


# ===========================================================================
# IntentClassifier — classify
# ===========================================================================

class TestClassify:
    def _make_classifier(self):
        with patch.object(IntentClassifier, "_load_stats"):
            return IntentClassifier()

    def test_navigation(self):
        ic = self._make_classifier()
        results = ic.classify("ouvre chrome sur google")
        assert results[0].intent == "navigation"
        assert results[0].confidence >= 0.8

    def test_trading(self):
        ic = self._make_classifier()
        results = ic.classify("scanne les signaux crypto btc")
        assert results[0].intent == "trading"

    def test_code_dev(self):
        ic = self._make_classifier()
        results = ic.classify("git commit et push le code")
        assert results[0].intent == "code_dev"

    def test_cluster_ops(self):
        ic = self._make_classifier()
        results = ic.classify("cluster M1 check status health")
        assert results[0].intent == "cluster_ops"

    def test_voice_control(self):
        ic = self._make_classifier()
        results = ic.classify("jarvis arrete d'ecouter")
        assert results[0].intent == "voice_control"

    def test_system_control(self):
        ic = self._make_classifier()
        results = ic.classify("eteins l'ordinateur")
        assert results[0].intent == "system_control"

    def test_fallback_query(self):
        ic = self._make_classifier()
        results = ic.classify("xyzabc random gibberish 12345")
        assert results[0].intent == "query"
        assert results[0].confidence < 0.5

    def test_top_n(self):
        ic = self._make_classifier()
        results = ic.classify("ouvre chrome", top_n=5)
        assert len(results) <= 5

    def test_context_boost(self):
        ic = self._make_classifier()
        ic._context = ["trading"]
        results = ic.classify("analyse les signaux crypto")
        # Trading should get context boost
        trading_result = [r for r in results if r.intent == "trading"]
        assert len(trading_result) == 1


# ===========================================================================
# IntentClassifier — classify_single
# ===========================================================================

class TestClassifySingle:
    def test_single(self):
        with patch.object(IntentClassifier, "_load_stats"):
            ic = IntentClassifier()
        result = ic.classify_single("ouvre youtube")
        assert isinstance(result, IntentResult)
        assert result.intent == "navigation"


# ===========================================================================
# IntentClassifier — _extract_entities
# ===========================================================================

class TestExtractEntities:
    def test_url(self):
        with patch.object(IntentClassifier, "_load_stats"):
            ic = IntentClassifier()
        entities = ic._extract_entities("va sur https://example.com")
        assert entities.get("url") == "https://example.com"

    def test_crypto_pair(self):
        with patch.object(IntentClassifier, "_load_stats"):
            ic = IntentClassifier()
        entities = ic._extract_entities("analyse BTC maintenant")
        assert entities.get("crypto_pair") == "BTC"

    def test_node_name(self):
        with patch.object(IntentClassifier, "_load_stats"):
            ic = IntentClassifier()
        entities = ic._extract_entities("check M1 health")
        assert entities.get("node_name") == "M1"

    def test_file_path(self):
        with patch.object(IntentClassifier, "_load_stats"):
            ic = IntentClassifier()
        entities = ic._extract_entities("ouvre C:\\Users\\test.txt")
        assert "file_path" in entities


# ===========================================================================
# IntentClassifier — feedback & accuracy
# ===========================================================================

class TestFeedback:
    def test_record_feedback(self):
        with patch.object(IntentClassifier, "_load_stats"), \
             patch.object(IntentClassifier, "_save_stats"):
            ic = IntentClassifier()
        ic.record_feedback("test", "query", True)
        ic.record_feedback("test", "query", False)
        accuracy = ic.get_accuracy()
        assert accuracy["query"] == 0.5

    def test_get_accuracy_empty(self):
        with patch.object(IntentClassifier, "_load_stats"):
            ic = IntentClassifier()
        assert ic.get_accuracy() == {}


# ===========================================================================
# IntentClassifier — get_report
# ===========================================================================

class TestReport:
    def test_report_structure(self):
        with patch.object(IntentClassifier, "_load_stats"):
            ic = IntentClassifier()
        report = ic.get_report()
        assert "intents" in report
        assert "accuracy" in report
        assert "total_classifications" in report
        assert "recent_context" in report
        assert len(report["intents"]) == len(INTENT_PATTERNS)


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert intent_classifier is not None
        assert isinstance(intent_classifier, IntentClassifier)
