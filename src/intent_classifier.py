"""JARVIS Intent Classifier v1 — ML-like intent detection for voice commands.

Classifies voice input into intent categories with confidence scoring.
Supports multi-intent detection, context-aware routing, and feedback learning.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.intent_classifier")

_DATA_DIR = Path(__file__).parent.parent / "data"
_INTENT_STATS_FILE = _DATA_DIR / "intent_stats.json"


@dataclass
class IntentResult:
    """Classification result for a single intent."""
    intent: str
    confidence: float
    entities: dict[str, str] = field(default_factory=dict)
    source: str = "rule"  # "rule", "keyword", "context", "learned"


# ═══════════════════════════════════════════════════════════════════════════
# INTENT DEFINITIONS — Keyword patterns per intent category
# ═══════════════════════════════════════════════════════════════════════════

INTENT_PATTERNS: dict[str, list[str]] = {
    "navigation": [
        r"\b(ouvre|va sur|navigue|affiche|montre)\b.*\b(chrome|firefox|navigateur|google|youtube|github|gmail)\b",
        r"\b(ouvre|va sur)\b.*\b(site|page|url|lien)\b",
    ],
    "app_launch": [
        r"\b(ouvre|lance|demarre|execute)\b.*\b(vscode|pycharm|terminal|notepad|explorer|task manager)\b",
        r"\b(lance|ouvre)\b.*\b(application|app|programme|logiciel)\b",
    ],
    "file_ops": [
        r"\b(ouvre|cree|supprime|copie|deplace|renomme)\b.*\b(fichier|dossier|repertoire|document)\b",
        r"\b(sauvegarde|restaure)\b",
        r"\bbackup\b.*\b(fichier|dossier|donnees|disque|base|projet)\b",
        r"\bbackup\b",
    ],
    "system_control": [
        r"\b(eteins|redemarre|verrouille|mets en veille)\b",
        r"\b(shutdown|restart|lock|sleep)\b",
        r"\b(volume|son|luminosite|ecran)\b",
    ],
    "trading": [
        r"\b(scanne?|analyse|signal|trading|bitcoin|btc|eth|crypto)\b",
        r"\b(mexc|binance|position|ordre|take profit|stop loss)\b",
        r"\b(marche|bull|bear|tendance|momentum|rsi|macd)\b",
    ],
    "cluster_ops": [
        r"\b(cluster|noeud|node|agent|m1|m2|m3|ol1|gemini)\b.*\b(check|status|health|ping)\b",
        r"\b(diagnostic|audit|heal|repare)\b.*\b(cluster|noeuds?|noeud)\b",
        r"\b(charge|load|unload|swap)\b.*\b(modele|model)\b",
        r"\b(nvidia-smi|nvtop|gpu|vram|cuda|temperature|thermal)\b",
    ],
    "code_dev": [
        r"\b(code|programme|fonction|classe|module|api|endpoint|parser|script)\b",
        r"\b(git|commit|push|pull|merge|branch|deploy|deploie)\b",
        r"\b(test|debug|fix|bug|erreur|error|refactor)\b",
        r"\b(ecris|implemente|genere|cree|developpe)\b.*\b(un|une|le|la|des)\b",
    ],
    "voice_control": [
        r"\b(jarvis|ecoute|arrete|tais-toi|stop|pause|continue|repete)\b",
        r"\b(mode|silence|vocal|voix|muet)\b",
    ],
    "reasoning": [
        r"\bcombien\b.*\b(jours?|temps|faut|metres?|heures?|minutes?)\b",
        r"\b(raisonne|raisonnement|logique|enigme|puzzle|devinette)\b",
        r"\b(si|supposons|imagine)\b.*\b(alors|combien|quel|quelle)\b",
        r"\b(calcule|resous|trouve)\b.*\b(equation|probleme|solution)\b",
        r"\b(monte|grimpe|descend|avance|recule)\b.*\b(combien|jours?|temps|metres?)\b",
        r"\b(probabilite|proba|chance|stats?|statistique)\b",
        r"\b(prouve|demontre|verifie)\b.*\b(que|si|pourquoi)\b",
    ],
    "query": [
        r"\b(qu.est.ce|c.est quoi|explique|comment|pourquoi|combien|qui est)\b",
        r"\b(recherche|cherche|trouve|web|internet)\b",
    ],
    "pipeline": [
        r"\b(pipeline|domino|sequence|enchaine|execute)\b.*\b(etapes?|steps?|actions?)\b",
        r"\b(lance|demarre|execute)\b.*\b(pipeline|domino|routine|workflow|backup)\b",
        r"\b(pipeline|domino)\b",
    ],
    "automation": [
        r"\b(automatise|schedule|planifie|programme|cron)\b",
        r"\b(auto[_-]?improve|auto[_-]?heal|auto[_-]?fix|auto[_-]?deploy|auto[_-]?scan)\b",
        r"\b(production.?valid|validator|validation|bootstrap|daemon)\b",
    ],
    "monitoring": [
        r"\b(dashboard|metriques?|metrics?|tableau.?de.?bord|stats?)\b.*\b(systeme|cluster|jarvis)\b",
        r"\b(scan|diagnostic|health.?score|health.?check)\b.*\b(complet|systeme|jarvis|cluster)\b",
        r"\b(monitor|surveillance|observe|surveille)\b",
        r"\b(cpu|ram|memoire|ressources?)\b.*\b(systeme|utilisation|charge|usage)\b",
        r"\b(self.?diagnostic|auto.?diagnostic|diagnostique.?toi)\b",
        r"\b(cache)\b.*\b(dispatch|stats?|performance)\b",
    ],
    "autonomous": [
        r"\b(cycle.?autonome|autonomous.?cycle|lance.?le.?cycle)\b",
        r"\b(watchdog|surveille.?tout|boucle.?autonome)\b",
        r"\b(auto.?ameliore|self.?improve|ameliore.?toi)\b",
        r"\b(benchmark|performance.?api|teste.?endpoints?)\b",
        r"\b(grade|note.?globale|score.?sante)\b",
        r"\b(predictions?|previsions?.?pannes?|log.?predictions?)\b",
    ],
    "telegram": [
        r"\b(telegram|commande.?telegram|envoie.?commande)\b",
        r"\b(message|notif|notification)\b.*\b(telegram|bot|turbo)\b",
    ],
}

# Entity extraction patterns
ENTITY_PATTERNS: dict[str, str] = {
    "app_name": r"(?:ouvre|lance|demarre)\s+(\w+)",
    "url": r"(https?://\S+)",
    "file_path": r"([A-Za-z]:\\[^\s]+|/[^\s]+)",
    "crypto_pair": r"\b(BTC|ETH|SOL|SUI|PEPE|DOGE|XRP|ADA|AVAX|LINK)\b",
    "node_name": r"\b(M[123]|OL1|GEMINI|CLAUDE)\b",
    "model_name": r"\b(qwen3-8b|qwen3-30b|gpt-oss-20b|qwq-32b|deepseek-r1|devstral)\b",
    "pipeline_name": r"\b(domino_\w+|pipeline_\w+)\b",
    "number": r"\b(\d+(?:\.\d+)?)\b",
}


class IntentClassifier:
    """Classifies voice input into intents with confidence scoring."""

    def __init__(self):
        self._compiled: dict[str, list[re.Pattern]] = {}
        self._entity_compiled: dict[str, re.Pattern] = {}
        self._stats: dict[str, dict[str, int]] = defaultdict(lambda: {"correct": 0, "total": 0})
        self._context: list[str] = []  # Recent intents for context
        self._compile_patterns()
        self._load_stats()

    def _compile_patterns(self):
        for intent, patterns in INTENT_PATTERNS.items():
            self._compiled[intent] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]
        for entity, pattern in ENTITY_PATTERNS.items():
            self._entity_compiled[entity] = re.compile(pattern, re.IGNORECASE)

    def classify(self, text: str, top_n: int = 3) -> list[IntentResult]:
        """Classify text into intents with confidence scores.

        Returns top N results sorted by confidence.
        Supports multi-intent detection.
        """
        text_lower = text.lower().strip()
        scores: dict[str, float] = {}

        # Rule-based matching — multi-match bonus for specificity
        for intent, patterns in self._compiled.items():
            match_count = 0
            for pattern in patterns:
                if pattern.search(text_lower):
                    match_count += 1
            if match_count > 0:
                max_score = 0.85 + 0.03 * (match_count - 1)  # bonus per extra match
                scores[intent] = max_score

        # Context boost: if last intent matches, slight confidence increase
        if self._context:
            last = self._context[-1]
            if last in scores:
                scores[last] = min(1.0, scores[last] + 0.05)

        # Learned accuracy boost
        for intent in scores:
            stats = self._stats.get(intent, {})
            if stats.get("total", 0) >= 5:
                accuracy = stats["correct"] / stats["total"]
                scores[intent] *= (0.8 + 0.2 * accuracy)

        # If no pattern matched, fallback to "query"
        if not scores:
            scores["query"] = 0.4

        # Extract entities
        entities = self._extract_entities(text)

        # Build results
        results = []
        for intent, confidence in sorted(scores.items(), key=lambda x: -x[1])[:top_n]:
            source = "rule" if confidence >= 0.8 else ("context" if intent == self._context[-1:] else "keyword")
            results.append(IntentResult(
                intent=intent,
                confidence=round(confidence, 3),
                entities=entities,
                source=source,
            ))

        # Update context
        if results:
            self._context.append(results[0].intent)
            if len(self._context) > 10:
                self._context = self._context[-10:]

        return results

    def classify_single(self, text: str) -> IntentResult:
        """Classify and return the top intent only."""
        results = self.classify(text, top_n=1)
        return results[0] if results else IntentResult(intent="unknown", confidence=0.0)

    def _extract_entities(self, text: str) -> dict[str, str]:
        """Extract named entities from text."""
        entities = {}
        for entity_name, pattern in self._entity_compiled.items():
            match = pattern.search(text)
            if match:
                entities[entity_name] = match.group(1) if match.groups() else match.group(0)
        return entities

    def record_feedback(self, text: str, predicted_intent: str, correct: bool):
        """Record classification feedback for learning."""
        stats = self._stats[predicted_intent]
        stats["total"] += 1
        if correct:
            stats["correct"] += 1
        self._save_stats()

    def get_accuracy(self) -> dict[str, float]:
        """Get classification accuracy per intent."""
        return {
            intent: round(s["correct"] / s["total"], 3) if s["total"] > 0 else 0.0
            for intent, s in self._stats.items()
        }

    def get_report(self) -> dict:
        """Full classifier report."""
        return {
            "intents": list(INTENT_PATTERNS.keys()),
            "accuracy": self.get_accuracy(),
            "total_classifications": sum(s["total"] for s in self._stats.values()),
            "recent_context": self._context[-5:],
        }

    def _save_stats(self):
        try:
            _INTENT_STATS_FILE.write_text(json.dumps(dict(self._stats), indent=2))
        except (OSError, ValueError):
            pass

    def _load_stats(self):
        try:
            data = json.loads(_INTENT_STATS_FILE.read_text())
            for intent, stats in data.items():
                self._stats[intent] = stats
        except (FileNotFoundError, json.JSONDecodeError):
            pass


# Global singleton
intent_classifier = IntentClassifier()
