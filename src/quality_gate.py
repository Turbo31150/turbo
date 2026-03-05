"""JARVIS Quality Gate — Enforces minimum quality standards before output delivery.

Gates:
  - Content length gate (per pattern)
  - Structure gate (code blocks, headers, lists)
  - Relevance gate (prompt-output keyword overlap)
  - Confidence gate (no hedging, no errors)
  - Latency gate (max acceptable response time)
  - Hallucination gate (detects nonsensical outputs)

Usage:
    from src.quality_gate import QualityGate, get_gate
    gate = get_gate()
    verdict = gate.evaluate("code", prompt, content, latency_ms=1500)
    if verdict.passed:
        return content
    else:
        retry with different node
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("jarvis.quality_gate")

DB_PATH = "F:/BUREAU/turbo/etoile.db"


@dataclass
class GateResult:
    """Result of quality gate evaluation."""
    passed: bool
    overall_score: float       # 0-1
    gates: dict                # gate_name -> {passed, score, reason}
    failed_gates: list[str]
    suggestions: list[str]
    retry_recommended: bool
    suggested_node: str = ""


@dataclass
class GateConfig:
    """Quality gate thresholds."""
    min_content_length: dict = field(default_factory=lambda: {
        "simple": 5, "code": 50, "analysis": 100, "architecture": 100,
        "reasoning": 50, "math": 20, "trading": 50, "security": 80,
        "creative": 30, "system": 10, "data": 30, "devops": 30,
        "default": 20,
    })
    max_latency_ms: dict = field(default_factory=lambda: {
        "simple": 5000, "code": 30000, "analysis": 30000, "reasoning": 60000,
        "default": 30000,
    })
    min_relevance: float = 0.15   # Minimum keyword overlap
    min_overall_score: float = 0.4
    max_error_keywords: int = 2


class QualityGate:
    """Enforces minimum quality standards on dispatch outputs."""

    # Hallucination indicators
    HALLUCINATION_PATTERNS = [
        r"je suis (un|une) (IA|intelligence artificielle|modele)",
        r"en tant qu'(IA|assistant)",
        r"I'm (an AI|a language model)",
        r"As an AI",
        r"\b(lorem ipsum)\b",
    ]

    ERROR_KEYWORDS = [
        "error", "erreur", "exception", "traceback", "failed",
        "impossible", "cannot", "undefined", "null", "NaN",
    ]

    def __init__(self, config: Optional[GateConfig] = None):
        self.config = config or GateConfig()
        self._stats = {"evaluated": 0, "passed": 0, "failed": 0}
        self._ensure_table()

    def _ensure_table(self):
        try:
            db = sqlite3.connect(DB_PATH)
            db.execute("""
                CREATE TABLE IF NOT EXISTS quality_gate_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern TEXT, passed INTEGER,
                    overall_score REAL, failed_gates TEXT,
                    node TEXT, timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            db.commit()
            db.close()
        except Exception:
            pass

    def evaluate(self, pattern: str, prompt: str, content: str,
                 latency_ms: float = 0, node: str = "") -> GateResult:
        """Evaluate output against all quality gates."""
        gates = {}
        failed = []
        suggestions = []

        # Gate 1: Content Length
        min_len = self.config.min_content_length.get(
            pattern, self.config.min_content_length["default"]
        )
        length_ok = len(content) >= min_len
        gates["length"] = {
            "passed": length_ok,
            "score": min(1.0, len(content) / max(1, min_len * 3)),
            "reason": f"Length {len(content)} {'>=': length_ok} {min_len} min" if length_ok
                      else f"Too short: {len(content)} < {min_len}",
        }
        if not length_ok:
            failed.append("length")
            suggestions.append(f"Output trop court ({len(content)} chars, min={min_len})")

        # Gate 2: Structure
        structure_score = self._evaluate_structure(pattern, content)
        structure_ok = structure_score >= 0.3
        gates["structure"] = {
            "passed": structure_ok,
            "score": structure_score,
            "reason": "Good structure" if structure_ok else "Poor structure",
        }
        if not structure_ok:
            failed.append("structure")
            suggestions.append("Output manque de structure (code blocks, listes, sections)")

        # Gate 3: Relevance
        relevance = self._evaluate_relevance(prompt, content)
        relevance_ok = relevance >= self.config.min_relevance
        gates["relevance"] = {
            "passed": relevance_ok,
            "score": relevance,
            "reason": f"Relevance {relevance:.2f}" + (" (low)" if not relevance_ok else ""),
        }
        if not relevance_ok:
            failed.append("relevance")
            suggestions.append("Output peu pertinent par rapport au prompt")

        # Gate 4: Confidence
        confidence = self._evaluate_confidence(content)
        confidence_ok = confidence >= 0.4
        gates["confidence"] = {
            "passed": confidence_ok,
            "score": confidence,
            "reason": "Confident" if confidence_ok else "Low confidence / errors detected",
        }
        if not confidence_ok:
            failed.append("confidence")
            suggestions.append("Output contient des erreurs ou du hedging excessif")

        # Gate 5: Latency
        max_lat = self.config.max_latency_ms.get(
            pattern, self.config.max_latency_ms["default"]
        )
        latency_ok = latency_ms <= max_lat if latency_ms > 0 else True
        gates["latency"] = {
            "passed": latency_ok,
            "score": max(0, 1.0 - latency_ms / max(1, max_lat * 2)) if latency_ms > 0 else 1.0,
            "reason": f"{latency_ms:.0f}ms" + (" (slow)" if not latency_ok else ""),
        }
        if not latency_ok:
            failed.append("latency")
            suggestions.append(f"Reponse trop lente ({latency_ms:.0f}ms > {max_lat}ms)")

        # Gate 6: Hallucination
        halluc_score = self._evaluate_hallucination(content)
        halluc_ok = halluc_score >= 0.7
        gates["hallucination"] = {
            "passed": halluc_ok,
            "score": halluc_score,
            "reason": "Clean" if halluc_ok else "Possible hallucination detected",
        }
        if not halluc_ok:
            failed.append("hallucination")
            suggestions.append("Possible hallucination detectee dans l'output")

        # Overall score
        weights = {"length": 0.2, "structure": 0.15, "relevance": 0.25,
                    "confidence": 0.2, "latency": 0.1, "hallucination": 0.1}
        overall = sum(gates[g]["score"] * weights.get(g, 0.1) for g in gates)

        passed = overall >= self.config.min_overall_score and len(failed) <= 1

        # Stats
        self._stats["evaluated"] += 1
        if passed:
            self._stats["passed"] += 1
        else:
            self._stats["failed"] += 1

        result = GateResult(
            passed=passed,
            overall_score=round(overall, 3),
            gates=gates,
            failed_gates=failed,
            suggestions=suggestions,
            retry_recommended=not passed and len(failed) <= 3,
            suggested_node=self._suggest_better_node(pattern, node, failed) if not passed else "",
        )

        # Log
        self._log(pattern, result, node)

        return result

    def _evaluate_structure(self, pattern: str, content: str) -> float:
        """Score content structure 0-1."""
        score = 0.3  # base
        lines = content.split("\n")

        if len(lines) > 1:
            score += 0.15
        if len(lines) > 5:
            score += 0.1

        has_code = "```" in content
        has_lists = any(l.strip().startswith(("-", "*", "1.", "2.")) for l in lines)
        has_headers = any(l.strip().startswith("#") for l in lines)

        if pattern == "code" and has_code:
            score += 0.3
        elif has_lists:
            score += 0.15
        elif has_headers:
            score += 0.15

        if "def " in content or "class " in content or "function " in content:
            score += 0.1 if pattern == "code" else 0.05

        return min(1.0, score)

    def _evaluate_relevance(self, prompt: str, content: str) -> float:
        """Score relevance as keyword overlap between prompt and content."""
        prompt_words = set(re.findall(r'\b\w{3,}\b', prompt.lower()))
        content_words = set(re.findall(r'\b\w{3,}\b', content.lower()))

        if not prompt_words:
            return 0.5

        stopwords = {"les", "des", "une", "est", "pour", "dans", "avec", "que", "qui",
                      "pas", "the", "and", "for", "with", "this", "that"}
        prompt_words -= stopwords
        content_words -= stopwords

        if not prompt_words:
            return 0.5

        overlap = len(prompt_words & content_words)
        return min(1.0, overlap / len(prompt_words))

    def _evaluate_confidence(self, content: str) -> float:
        """Score output confidence (no hedging, no errors)."""
        score = 0.8
        lower = content.lower()

        # Error keywords
        error_count = sum(1 for kw in self.ERROR_KEYWORDS if kw in lower)
        score -= 0.15 * min(error_count, self.config.max_error_keywords)

        # Hedging
        hedging = ["peut-etre", "je pense", "il semble", "probablement",
                    "possibly", "might be", "I think", "perhaps"]
        hedge_count = sum(1 for h in hedging if h in lower)
        score -= 0.1 * min(hedge_count, 3)

        # Apologies
        if any(a in lower for a in ["desole", "sorry", "apologize"]):
            score -= 0.15

        return max(0, min(1.0, score))

    def _evaluate_hallucination(self, content: str) -> float:
        """Detect potential hallucinations."""
        score = 1.0

        for pattern in self.HALLUCINATION_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                score -= 0.2

        # Repetition detection (same sentence repeated)
        sentences = [s.strip() for s in content.split(".") if len(s.strip()) > 20]
        if sentences:
            unique = set(sentences)
            if len(unique) < len(sentences) * 0.7:
                score -= 0.3

        return max(0, score)

    def _suggest_better_node(self, pattern: str, current_node: str,
                             failed_gates: list[str]) -> str:
        """Suggest a better node based on failure type."""
        if "latency" in failed_gates:
            return "M1"  # Fastest local
        if "length" in failed_gates or "structure" in failed_gates:
            return "M1B"  # Deeper model for better output
        if "relevance" in failed_gates:
            return "gpt-oss"  # Best quality cloud
        return ""

    def _log(self, pattern: str, result: GateResult, node: str):
        try:
            db = sqlite3.connect(DB_PATH)
            db.execute("""
                INSERT INTO quality_gate_log
                (pattern, passed, overall_score, failed_gates, node)
                VALUES (?, ?, ?, ?, ?)
            """, (pattern, int(result.passed), result.overall_score,
                  ",".join(result.failed_gates), node))
            db.commit()
            db.close()
        except Exception:
            pass

    def get_stats(self) -> dict:
        """Gate evaluation stats."""
        return {
            **self._stats,
            "pass_rate": round(self._stats["passed"] / max(1, self._stats["evaluated"]), 3),
        }

    def get_gate_report(self) -> dict:
        """Detailed gate report from DB."""
        try:
            db = sqlite3.connect(DB_PATH)
            db.row_factory = sqlite3.Row
            total = db.execute("SELECT COUNT(*) FROM quality_gate_log").fetchone()[0]
            by_pattern = db.execute("""
                SELECT pattern, COUNT(*) as n,
                       SUM(CASE WHEN passed THEN 1 ELSE 0 END) as ok,
                       AVG(overall_score) as avg_score
                FROM quality_gate_log GROUP BY pattern ORDER BY n DESC
            """).fetchall()
            common_failures = db.execute("""
                SELECT failed_gates, COUNT(*) as n
                FROM quality_gate_log WHERE NOT passed
                GROUP BY failed_gates ORDER BY n DESC LIMIT 10
            """).fetchall()
            db.close()

            return {
                "total_evaluated": total,
                "by_pattern": [
                    {"pattern": r["pattern"], "count": r["n"],
                     "pass_rate": round(r["ok"] / max(1, r["n"]), 3),
                     "avg_score": round(r["avg_score"] or 0, 3)}
                    for r in by_pattern
                ],
                "common_failures": [
                    {"gates": r["failed_gates"], "count": r["n"]}
                    for r in common_failures
                ],
            }
        except Exception:
            return {"total_evaluated": 0}


# Singleton
_gate: Optional[QualityGate] = None

def get_gate() -> QualityGate:
    global _gate
    if _gate is None:
        _gate = QualityGate()
    return _gate
