"""JARVIS Prompt Optimizer — Learns which prompt styles produce best quality per pattern.

Analyzes dispatch history to identify:
  - Optimal prompt length per pattern
  - Keywords that correlate with higher quality
  - System prompt templates that perform best
  - Prompt enrichment strategies (context, examples, constraints)

Usage:
    from src.agent_prompt_optimizer import PromptOptimizer, get_optimizer
    opt = get_optimizer()
    enhanced = opt.optimize("code", "Ecris un parser JSON")
    insights = opt.get_insights("code")
"""

from __future__ import annotations

import logging
import re
import sqlite3
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Optional


__all__ = [
    "PromptInsight",
    "PromptOptimizer",
    "PromptTemplate",
    "get_optimizer",
]

logger = logging.getLogger("jarvis.prompt_optimizer")

DB_PATH = "F:/BUREAU/turbo/etoile.db"


@dataclass
class PromptInsight:
    """Analysis of prompt effectiveness for a pattern."""
    pattern: str
    optimal_length_range: tuple[int, int]  # (min, max) chars
    high_quality_keywords: list[str]       # Words that correlate with quality > 0.7
    low_quality_keywords: list[str]        # Words that correlate with quality < 0.4
    best_prefix: str                        # Most effective prompt prefix
    avg_quality_with_context: float         # Quality when context was included
    avg_quality_without_context: float      # Quality without context
    sample_size: int
    recommended_strategy: str


@dataclass
class PromptTemplate:
    """Optimized prompt template for a pattern."""
    pattern: str
    system_prompt: str
    user_prefix: str
    constraints: list[str]
    examples_count: int
    max_length_hint: int
    effectiveness: float  # 0-1 based on historical data


class PromptOptimizer:
    """Learns and applies optimal prompting strategies."""

    # Default system prompts per pattern (tuned from data)
    SYSTEM_PROMPTS = {
        "code": "Tu es un expert en programmation. Reponds avec du code propre, commente, et fonctionnel.",
        "simple": "Reponds de facon concise et precise en 1-2 phrases.",
        "reasoning": "Raisonne etape par etape avant de donner ta conclusion finale.",
        "math": "Resous le probleme mathematique en montrant chaque etape du calcul.",
        "analysis": "Analyse en profondeur avec structure: contexte, analyse, conclusion.",
        "architecture": "Propose une architecture logicielle avec composants, flux de donnees, et justification.",
        "trading": "Analyse technique avec niveaux cles, tendance, et recommandation actionnable.",
        "security": "Audit de securite structure: vulnerabilites, risques, remediations prioritisees.",
        "system": "Diagnostique et execute la commande systeme demandee. Sois precis et safe.",
        "creative": "Sois creatif et original tout en restant pertinent et structure.",
        "data": "Traite les donnees avec precision. Montre le schema, la transformation, et le resultat.",
        "devops": "Infrastructure as code. Pipeline CI/CD. Monitoring. Deploiement zero-downtime.",
        "web": "Recherche web et synthese des informations trouvees avec sources.",
        "voice": "Reponds de facon naturelle et concise, optimise pour lecture vocale.",
        "email": "Redige un email professionnel, clair et structure.",
        "automation": "Script d'automatisation avec gestion d'erreurs et idempotence.",
        "learning": "Explique de facon pedagogique avec exemples progressifs.",
        "monitoring": "Metriques, alertes, dashboards. Diagnostique base sur les donnees.",
        "optimization": "Optimise pour la performance: mesure, profil, ameliore, verifie.",
    }

    CONSTRAINTS = {
        "code": ["Code executable sans erreur", "Commente les parties complexes", "Gere les cas limites"],
        "simple": ["Maximum 2 phrases", "Pas de jargon"],
        "reasoning": ["Montre le raisonnement", "Conclusion explicite"],
        "trading": ["Niveaux numeriques precis", "Timeframe explicite", "Risk/reward"],
    }

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._insights_cache: dict[str, PromptInsight] = {}
        self._templates_cache: dict[str, PromptTemplate] = {}
        self._ensure_table()
        self._build_insights()

    def _ensure_table(self):
        try:
            db = sqlite3.connect(self.db_path)
            db.execute("""
                CREATE TABLE IF NOT EXISTS prompt_optimization_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern TEXT, original_length INTEGER,
                    optimized_length INTEGER, quality_before REAL,
                    quality_after REAL, optimization_type TEXT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            db.commit()
            db.close()
        except Exception as e:
            logger.warning(f"Failed to create prompt_optimization_log: {e}")

    def _build_insights(self):
        """Build insights from dispatch history."""
        try:
            db = sqlite3.connect(self.db_path)
            db.row_factory = sqlite3.Row
            rows = db.execute("""
                SELECT classified_type as pattern, request_text as prompt,
                       quality_score, success, latency_ms, node
                FROM agent_dispatch_log
                WHERE request_text IS NOT NULL AND request_text != ''
                ORDER BY id DESC LIMIT 2000
            """).fetchall()
            db.close()
        except Exception:
            return

        pattern_data = defaultdict(list)
        for r in rows:
            pattern_data[r["pattern"] or "simple"].append({
                "prompt": r["prompt"] or "",
                "quality": r["quality_score"] or 0,
                "success": bool(r["success"]),
                "length": len(r["prompt"] or ""),
            })

        for pattern, entries in pattern_data.items():
            if len(entries) < 5:
                continue

            # Optimal length range
            high_q = [e for e in entries if e["quality"] > 0.7]
            if high_q:
                lengths = [e["length"] for e in high_q]
                opt_min = max(10, int(sorted(lengths)[len(lengths)//4]))
                opt_max = int(sorted(lengths)[3*len(lengths)//4])
            else:
                opt_min, opt_max = 20, 200

            # Keyword analysis
            high_words = Counter()
            low_words = Counter()
            for e in entries:
                words = set(re.findall(r'\b\w{3,}\b', e["prompt"].lower()))
                if e["quality"] > 0.7:
                    high_words.update(words)
                elif e["quality"] < 0.4:
                    low_words.update(words)

            # Remove common words
            stopwords = {"les", "des", "une", "est", "pour", "dans", "avec", "que", "qui", "pas"}
            high_kw = [w for w, _ in high_words.most_common(10) if w not in stopwords and w not in low_words]
            low_kw = [w for w, _ in low_words.most_common(10) if w not in stopwords and w not in high_words]

            # Context effect
            with_ctx = [e["quality"] for e in entries if "contexte" in e["prompt"].lower() or "context" in e["prompt"].lower()]
            without_ctx = [e["quality"] for e in entries if "contexte" not in e["prompt"].lower() and "context" not in e["prompt"].lower()]

            self._insights_cache[pattern] = PromptInsight(
                pattern=pattern,
                optimal_length_range=(opt_min, opt_max),
                high_quality_keywords=high_kw[:5],
                low_quality_keywords=low_kw[:5],
                best_prefix=self.SYSTEM_PROMPTS.get(pattern, ""),
                avg_quality_with_context=sum(with_ctx) / max(1, len(with_ctx)),
                avg_quality_without_context=sum(without_ctx) / max(1, len(without_ctx)),
                sample_size=len(entries),
                recommended_strategy="single",
            )

    def optimize(self, pattern: str, prompt: str,
                 add_system: bool = True,
                 add_constraints: bool = True) -> dict:
        """Optimize a prompt for the given pattern.

        Returns dict with 'system_prompt', 'user_prompt', 'optimizations_applied'.
        """
        optimizations = []
        system = ""
        user_prompt = prompt

        # System prompt
        if add_system:
            system = self.SYSTEM_PROMPTS.get(pattern, "")
            if system:
                optimizations.append("system_prompt")

        # Constraints
        if add_constraints:
            constraints = self.CONSTRAINTS.get(pattern, [])
            if constraints:
                constraint_text = "\n".join(f"- {c}" for c in constraints)
                user_prompt = f"{user_prompt}\n\nContraintes:\n{constraint_text}"
                optimizations.append("constraints")

        # Length optimization
        insight = self._insights_cache.get(pattern)
        if insight:
            opt_min, opt_max = insight.optimal_length_range
            if len(prompt) < opt_min and pattern not in ("simple", "classifier"):
                user_prompt = f"Detaille ta reponse. {user_prompt}"
                optimizations.append("length_boost")

        # High-quality keyword injection (subtle)
        if insight and insight.high_quality_keywords:
            # Only inject if prompt is very short and lacks specificity
            if len(prompt.split()) < 5 and pattern in ("code", "analysis", "architecture"):
                user_prompt = f"{user_prompt}\nSois precis et structure."
                optimizations.append("specificity_boost")

        return {
            "system_prompt": system,
            "user_prompt": user_prompt,
            "original_prompt": prompt,
            "pattern": pattern,
            "optimizations_applied": optimizations,
            "original_length": len(prompt),
            "optimized_length": len(user_prompt),
        }

    def get_insights(self, pattern: Optional[str] = None) -> dict:
        """Get prompt insights for one or all patterns."""
        if pattern:
            insight = self._insights_cache.get(pattern)
            if not insight:
                return {"pattern": pattern, "status": "no_data"}
            return {
                "pattern": insight.pattern,
                "optimal_length": {"min": insight.optimal_length_range[0],
                                   "max": insight.optimal_length_range[1]},
                "high_quality_keywords": insight.high_quality_keywords,
                "low_quality_keywords": insight.low_quality_keywords,
                "context_effect": {
                    "with_context": round(insight.avg_quality_with_context, 3),
                    "without_context": round(insight.avg_quality_without_context, 3),
                    "improvement": round(
                        insight.avg_quality_with_context - insight.avg_quality_without_context, 3
                    ),
                },
                "sample_size": insight.sample_size,
                "recommended_strategy": insight.recommended_strategy,
            }

        return {
            p: self.get_insights(p) for p in sorted(self._insights_cache.keys())
        }

    def get_templates(self) -> dict:
        """Get all optimized prompt templates."""
        templates = {}
        for pattern, sys_prompt in self.SYSTEM_PROMPTS.items():
            constraints = self.CONSTRAINTS.get(pattern, [])
            insight = self._insights_cache.get(pattern)
            templates[pattern] = {
                "system_prompt": sys_prompt,
                "constraints": constraints,
                "optimal_length": (
                    {"min": insight.optimal_length_range[0],
                     "max": insight.optimal_length_range[1]}
                    if insight else None
                ),
                "high_quality_keywords": (
                    insight.high_quality_keywords if insight else []
                ),
            }
        return templates

    def analyze_prompt(self, pattern: str, prompt: str) -> dict:
        """Analyze a prompt and suggest improvements."""
        suggestions = []
        score = 0.5

        insight = self._insights_cache.get(pattern)
        length = len(prompt)

        # Length check
        if insight:
            opt_min, opt_max = insight.optimal_length_range
            if length < opt_min:
                suggestions.append(f"Prompt trop court ({length} chars). Optimum: {opt_min}-{opt_max}")
                score -= 0.1
            elif length > opt_max * 2:
                suggestions.append(f"Prompt tres long ({length} chars). Optimum: {opt_min}-{opt_max}")
                score -= 0.05

        # Specificity check
        words = prompt.lower().split()
        if len(words) < 3:
            suggestions.append("Prompt trop vague. Ajoute des details specifiques.")
            score -= 0.15

        # Language check
        if pattern in ("code", "architecture") and not any(
            kw in prompt.lower() for kw in ["python", "javascript", "typescript", "rust", "api", "fonction", "class"]
        ):
            suggestions.append("Specifie le langage ou la technologie cible.")
            score -= 0.05

        # High-quality keyword presence
        if insight:
            present = sum(1 for kw in insight.high_quality_keywords if kw in prompt.lower())
            if present > 0:
                score += 0.1 * min(present, 3)
            bad_present = sum(1 for kw in insight.low_quality_keywords if kw in prompt.lower())
            if bad_present > 0:
                suggestions.append(f"Contient {bad_present} mot(s) correles a une faible qualite.")
                score -= 0.05 * bad_present

        # Structure check
        if pattern in ("analysis", "architecture", "security") and len(prompt.split("\n")) < 2:
            suggestions.append("Structure le prompt en sections pour de meilleurs resultats.")

        if not suggestions:
            suggestions.append("Prompt bien structure. Aucune amelioration suggeree.")

        return {
            "pattern": pattern,
            "prompt_length": length,
            "word_count": len(words),
            "estimated_quality": round(max(0, min(1, score)), 2),
            "suggestions": suggestions,
            "optimized": self.optimize(pattern, prompt),
        }

    def refresh(self):
        """Refresh insights from latest data."""
        self._insights_cache.clear()
        self._build_insights()


# Singleton
_optimizer: Optional[PromptOptimizer] = None

def get_optimizer() -> PromptOptimizer:
    global _optimizer
    if _optimizer is None:
        _optimizer = PromptOptimizer()
    return _optimizer
