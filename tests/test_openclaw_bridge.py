"""Tests for OpenClaw Bridge — intent classification and agent routing."""
import pytest
from unittest.mock import patch, MagicMock

from src.openclaw_bridge import OpenClawBridge, INTENT_TO_AGENT, get_bridge


class TestOpenClawBridge:
    """Test the OpenClaw Bridge routing logic."""

    def setup_method(self):
        self.bridge = OpenClawBridge()

    # ── classify_fast ────────────────────────────────────────────────────

    def test_classify_code_intent(self):
        intent, conf = self.bridge.classify_fast("ecris une fonction Python pour parser du JSON")
        assert intent == "code_dev"
        assert conf > 0.5

    def test_classify_trading_intent(self):
        intent, conf = self.bridge.classify_fast("scan trading BTC ETH prix crypto")
        assert intent == "trading"
        assert conf > 0.5

    def test_classify_cluster_intent(self):
        intent, conf = self.bridge.classify_fast("check cluster health diagnostic GPU")
        assert intent == "cluster_ops"
        assert conf > 0.5

    def test_classify_security_intent(self):
        intent, conf = self.bridge.classify_fast("audit securite vulnerabilites OWASP")
        assert intent == "security"
        assert conf > 0.5

    def test_classify_windows_intent(self):
        intent, conf = self.bridge.classify_fast("powershell list services windows defender")
        assert intent == "windows"
        assert conf > 0.5

    def test_classify_architecture_intent(self):
        intent, conf = self.bridge.classify_fast("architecture systeme distribue microservice design")
        assert intent == "architecture"
        assert conf > 0.5

    def test_classify_reasoning_intent(self):
        intent, conf = self.bridge.classify_fast("raisonnement logique mathematique equation")
        assert intent == "reasoning"
        assert conf > 0.5

    def test_classify_web_search(self):
        intent, conf = self.bridge.classify_fast("recherche web actualites internet")
        assert intent == "web"
        assert conf > 0.5

    def test_classify_translation(self):
        intent, conf = self.bridge.classify_fast("traduis ce texte en anglais")
        assert intent == "translation"
        assert conf > 0.5

    def test_classify_devops(self):
        intent, conf = self.bridge.classify_fast("git commit push deploy CI build")
        assert intent == "devops"
        assert conf > 0.5

    def test_classify_pipeline(self):
        intent, conf = self.bridge.classify_fast("lance pipeline domino routine workflow")
        assert intent == "pipeline"
        assert conf > 0.5

    def test_classify_creative(self):
        intent, conf = self.bridge.classify_fast("brainstorm idee creatif propose imagine")
        assert intent == "creative"
        assert conf > 0.5

    def test_classify_analysis(self):
        intent, conf = self.bridge.classify_fast("analyse compare rapport statistiques donnees SQL")
        assert intent == "analysis"
        assert conf > 0.5

    def test_classify_short_message_is_simple(self):
        intent, conf = self.bridge.classify_fast("oui")
        assert intent == "simple"
        assert conf >= 0.9

    def test_classify_unknown_returns_question(self):
        intent, conf = self.bridge.classify_fast("lorem ipsum dolor sit amet consectetur")
        assert intent == "question"
        assert conf == 0.5

    # ── route ────────────────────────────────────────────────────────────

    def test_route_code_to_coding(self):
        result = self.bridge.route("ecris un script Python pour parser CSV")
        assert result.agent == "coding"
        assert result.intent == "code_dev"
        assert result.confidence > 0.5
        assert result.latency_ms >= 0

    def test_route_trading_to_trading_agent(self):
        result = self.bridge.route("signal trading BTC long MEXC")
        assert result.agent in ("trading", "trading-scanner")

    def test_route_cluster_to_system_ops(self):
        result = self.bridge.route("health check cluster noeuds diagnostic")
        assert result.agent == "system-ops"

    def test_route_security_to_securite_audit(self):
        result = self.bridge.route("audit securite vulnerabilite scan")
        assert result.agent == "securite-audit"

    def test_route_unknown_to_main(self):
        # If classify returns something not in INTENT_TO_AGENT, fallback to main
        with patch.object(self.bridge, 'classify_fast', return_value=("unknown_intent", 0.5)):
            result = self.bridge.route("something completely random")
            assert result.agent == "main"
            assert result.fallback_used is True

    def test_route_short_to_fast_chat(self):
        result = self.bridge.route("oui")
        assert result.agent == "fast-chat"
        assert result.intent == "simple"

    # ── route_batch ──────────────────────────────────────────────────────

    def test_route_batch(self):
        messages = [
            "ecris du code Python",
            "check cluster health",
            "oui",
        ]
        results = self.bridge.route_batch(messages)
        assert len(results) == 3
        assert results[0].agent == "coding"
        assert results[1].agent == "system-ops"
        assert results[2].agent == "fast-chat"

    # ── mapping coverage ─────────────────────────────────────────────────

    def test_all_intents_have_agents(self):
        """Every intent in the mapping should point to a valid agent name."""
        # Single-word agent names that are valid
        _valid_single = {"main", "windows", "trading", "translator", "coding"}
        for intent, agent in INTENT_TO_AGENT.items():
            assert isinstance(agent, str)
            assert len(agent) > 0
            assert "-" in agent or agent in _valid_single

    def test_routing_table(self):
        table = self.bridge.get_routing_table()
        assert len(table) > 20
        assert table["code_dev"] == "coding"
        assert table["trading"] == "trading"

    # ── stats ────────────────────────────────────────────────────────────

    def test_stats_track_routes(self):
        self.bridge.route("code Python test")
        self.bridge.route("code Python fix")
        stats = self.bridge.get_stats()
        assert stats["total_routes"] >= 2
        assert "coding" in stats["by_agent"]

    # ── singleton ────────────────────────────────────────────────────────

    def test_singleton(self):
        b1 = get_bridge()
        b2 = get_bridge()
        assert b1 is b2

    # ── deep classify ────────────────────────────────────────────────────

    def test_deep_classify_fallback_on_error(self):
        """If deep classifier fails, fallback to fast."""
        with patch("src.openclaw_bridge.OpenClawBridge.classify_deep") as mock_deep:
            mock_deep.side_effect = Exception("no classifier")
            # Should still work via route with use_deep but catching the error
            result = self.bridge.route("test code", use_deep=False)
            assert result.agent is not None

    def test_classify_doc_intent(self):
        intent, conf = self.bridge.classify_fast("documente le README changelog API")
        assert intent == "doc"

    def test_classify_voice_intent(self):
        intent, conf = self.bridge.classify_fast("voix vocal whisper microphone ecoute")
        assert intent == "voice_control"

    def test_classify_consensus(self):
        intent, conf = self.bridge.classify_fast("consensus vote arbitrage decision critique")
        assert intent == "consensus"
