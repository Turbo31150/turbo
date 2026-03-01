"""Pipeline Code Review automatique via OL1 qwen3-coder:480b-cloud.

Workflow: M1 produit du code → ce module l'envoie automatiquement au 480b
pour review approfondie (bugs, securite, performance, style).
Fallback: kimi-k2.5:cloud (reasoning) → qwen3:14b (local).

Usage standalone:
    uv run python -m src.code_review_480b "def foo(): ..."
    uv run python -m src.code_review_480b --file script.py
    uv run python -m src.code_review_480b --diff  (git diff staged)

Usage API (depuis tools.py / mcp_server.py):
    from src.code_review_480b import review_code, review_diff
    result = await review_code(code_str)
    result = await review_diff()
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any

import httpx

OLLAMA_URL = "http://127.0.0.1:11434"

# Modeles par ordre de priorite
REVIEW_MODELS = [
    ("gpt-oss:120b-cloud", 180.0),       # Primary: 120B CHAMPION 100/100 51tok/s
    ("devstral-2:123b-cloud", 180.0),    # Fallback #1: 123B code 96.5/100
    ("qwen3-coder:480b-cloud", 180.0),   # Fallback #2: 480B code
    ("kimi-k2.5:cloud", 120.0),          # Fallback #3: reasoning profond
    ("qwen3:14b", 90.0),                 # Fallback local: raisonnement
]

REVIEW_SYSTEM = """Tu es un expert code reviewer senior. Analyse le code fourni et produis un rapport structure.

FORMAT DE SORTIE (JSON strict):
{
  "score": 0-100,
  "verdict": "APPROVE" | "NEEDS_WORK" | "REJECT",
  "bugs": [{"line": N, "severity": "critical|major|minor", "desc": "..."}],
  "security": [{"type": "...", "desc": "...", "fix": "..."}],
  "performance": [{"desc": "...", "suggestion": "..."}],
  "style": [{"desc": "...", "suggestion": "..."}],
  "summary": "Resume en 2-3 phrases"
}

REGLES:
- Sois precis: cite les numeros de lignes
- Priorise: bugs critiques > securite > performance > style
- Score: 90+ = excellent, 70-89 = bon, 50-69 = passable, <50 = problematique
- Si le code est court ou trivial, dis-le et score haut
- Reponds UNIQUEMENT en JSON valide, pas de texte autour"""

DIFF_REVIEW_SYSTEM = """Tu es un expert code reviewer senior. Analyse ce diff git et produis un rapport structure.

FORMAT DE SORTIE (JSON strict):
{
  "score": 0-100,
  "verdict": "APPROVE" | "NEEDS_WORK" | "REJECT",
  "changes_analysis": "Resume des changements",
  "bugs": [{"file": "...", "line": N, "severity": "critical|major|minor", "desc": "..."}],
  "security": [{"type": "...", "desc": "...", "fix": "..."}],
  "improvements": [{"desc": "...", "suggestion": "..."}],
  "summary": "Resume en 2-3 phrases"
}

REGLES:
- Focus sur les CHANGEMENTS (lignes + et -), pas le contexte existant
- Cite fichier:ligne pour chaque issue
- Detecte: regressions, variables inutilisees, imports manquants, edge cases
- Reponds UNIQUEMENT en JSON valide"""


@dataclass
class ReviewResult:
    """Resultat d'une review de code."""
    model: str
    score: int
    verdict: str
    bugs: list[dict]
    security: list[dict]
    performance: list[dict]
    style: list[dict]
    summary: str
    latency_ms: int
    raw: str

    @property
    def has_issues(self) -> bool:
        return bool(self.bugs or self.security)

    @property
    def critical_count(self) -> int:
        return sum(1 for b in self.bugs if b.get("severity") == "critical")

    def format_report(self) -> str:
        """Format human-readable report."""
        lines = [
            f"{'='*60}",
            f"  CODE REVIEW — {self.model}",
            f"  Score: {self.score}/100 | Verdict: {self.verdict}",
            f"  Latence: {self.latency_ms}ms",
            f"{'='*60}",
        ]
        if self.summary:
            lines.append(f"\n  {self.summary}")
        if self.bugs:
            lines.append(f"\n  BUGS ({len(self.bugs)}):")
            for b in self.bugs:
                sev = b.get("severity", "?").upper()
                line = b.get("line", "?")
                lines.append(f"    [{sev}] L{line}: {b.get('desc', '?')}")
        if self.security:
            lines.append(f"\n  SECURITE ({len(self.security)}):")
            for s in self.security:
                lines.append(f"    [{s.get('type','?')}] {s.get('desc','?')}")
                if s.get("fix"):
                    lines.append(f"      Fix: {s['fix']}")
        if self.performance:
            lines.append(f"\n  PERFORMANCE ({len(self.performance)}):")
            for p in self.performance:
                lines.append(f"    - {p.get('desc','?')}")
        if self.style:
            lines.append(f"\n  STYLE ({len(self.style)}):")
            for s in self.style:
                lines.append(f"    - {s.get('desc','?')}")
        lines.append(f"\n{'='*60}")
        return "\n".join(lines)


def _parse_review(raw: str, model: str, latency_ms: int) -> ReviewResult:
    """Parse la reponse JSON du modele en ReviewResult."""
    # Extraire le JSON du contenu (peut etre entoure de ```json ... ```)
    text = raw.strip()
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0].strip()

    # Trouver le premier { et dernier }
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end+1]

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return ReviewResult(
            model=model, score=50, verdict="PARSE_ERROR",
            bugs=[], security=[], performance=[], style=[],
            summary=f"Impossible de parser la reponse JSON. Raw: {raw[:200]}",
            latency_ms=latency_ms, raw=raw,
        )

    return ReviewResult(
        model=model,
        score=data.get("score", 50),
        verdict=data.get("verdict", "UNKNOWN"),
        bugs=data.get("bugs", []),
        security=data.get("security", []),
        performance=data.get("performance", data.get("improvements", [])),
        style=data.get("style", []),
        summary=data.get("summary", data.get("changes_analysis", "")),
        latency_ms=latency_ms,
        raw=raw,
    )


async def _query_ollama(prompt: str, system: str, model: str, timeout: float) -> tuple[str, int]:
    """Query Ollama et retourne (content, latency_ms)."""
    t0 = time.monotonic()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "think": False,
                "options": {"num_predict": 2048, "temperature": 0.1},
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data.get("message", {}).get("content", "")
        latency = int((time.monotonic() - t0) * 1000)
        return content, latency


async def review_code(
    code: str,
    models: list[tuple[str, float]] | None = None,
    context: str = "",
) -> ReviewResult:
    """Review du code avec fallback chain.

    Args:
        code: Code source a reviewer
        models: Liste de (model_name, timeout) — defaut REVIEW_MODELS
        context: Contexte additionnel (nom fichier, description, etc.)

    Returns:
        ReviewResult avec score, verdict, bugs, securite, etc.
    """
    if models is None:
        models = REVIEW_MODELS

    prompt = f"Review ce code:\n\n```\n{code}\n```"
    if context:
        prompt = f"{context}\n\n{prompt}"

    last_error = None
    for model, timeout in models:
        try:
            content, latency = await _query_ollama(prompt, REVIEW_SYSTEM, model, timeout)
            return _parse_review(content, model, latency)
        except Exception as e:
            last_error = e
            continue

    return ReviewResult(
        model="FAILED", score=0, verdict="ERROR",
        bugs=[], security=[], performance=[], style=[],
        summary=f"Tous les modeles ont echoue. Derniere erreur: {last_error}",
        latency_ms=0, raw="",
    )


async def review_diff(diff_text: str | None = None) -> ReviewResult:
    """Review d'un diff git.

    Args:
        diff_text: Diff a reviewer. Si None, utilise `git diff --staged` puis `git diff`.
    """
    if diff_text is None:
        # Try staged first, then unstaged
        result = subprocess.run(
            ["git", "diff", "--staged"], capture_output=True, text=True, cwd="F:/BUREAU/turbo"
        )
        diff_text = result.stdout.strip()
        if not diff_text:
            result = subprocess.run(
                ["git", "diff"], capture_output=True, text=True, cwd="F:/BUREAU/turbo"
            )
            diff_text = result.stdout.strip()
        if not diff_text:
            return ReviewResult(
                model="N/A", score=100, verdict="NO_CHANGES",
                bugs=[], security=[], performance=[], style=[],
                summary="Aucun changement detecte (git diff vide).",
                latency_ms=0, raw="",
            )

    prompt = f"Review ce diff git:\n\n```diff\n{diff_text[:8000]}\n```"
    if len(diff_text) > 8000:
        prompt += f"\n\n(diff tronque, {len(diff_text)} chars total)"

    last_error = None
    for model, timeout in REVIEW_MODELS:
        try:
            content, latency = await _query_ollama(prompt, DIFF_REVIEW_SYSTEM, model, timeout)
            return _parse_review(content, model, latency)
        except Exception as e:
            last_error = e
            continue

    return ReviewResult(
        model="FAILED", score=0, verdict="ERROR",
        bugs=[], security=[], performance=[], style=[],
        summary=f"Tous les modeles ont echoue: {last_error}",
        latency_ms=0, raw="",
    )


async def review_file(filepath: str) -> ReviewResult:
    """Review un fichier entier."""
    with open(filepath, "r", encoding="utf-8") as f:
        code = f.read()
    return await review_code(code, context=f"Fichier: {filepath}")


async def dual_review(code: str, context: str = "") -> tuple[ReviewResult, ReviewResult]:
    """Double review: 480b (code) + kimi (reasoning) en parallele."""
    prompt = f"Review ce code:\n\n```\n{code}\n```"
    if context:
        prompt = f"{context}\n\n{prompt}"

    async def _single(model: str, timeout: float) -> ReviewResult:
        try:
            content, latency = await _query_ollama(prompt, REVIEW_SYSTEM, model, timeout)
            return _parse_review(content, model, latency)
        except Exception as e:
            return ReviewResult(
                model=model, score=0, verdict="ERROR",
                bugs=[], security=[], performance=[], style=[],
                summary=str(e), latency_ms=0, raw="",
            )

    r_primary, r_secondary = await asyncio.gather(
        _single("gpt-oss:120b-cloud", 180.0),
        _single("devstral-2:123b-cloud", 180.0),
    )
    return r_primary, r_secondary


# ── CLI ──────────────────────────────────────────────────────────────────────

async def _main():
    import argparse
    parser = argparse.ArgumentParser(description="Code Review via OL1-480b")
    parser.add_argument("code", nargs="?", help="Code a reviewer (inline)")
    parser.add_argument("--file", "-f", help="Fichier a reviewer")
    parser.add_argument("--diff", "-d", action="store_true", help="Review git diff")
    parser.add_argument("--dual", action="store_true", help="Double review 480b + kimi")
    parser.add_argument("--json", "-j", action="store_true", help="Output JSON")
    args = parser.parse_args()

    if args.diff:
        print("Analyse du diff git...")
        result = await review_diff()
    elif args.file:
        print(f"Review de {args.file}...")
        result = await review_file(args.file)
    elif args.code:
        if args.dual:
            print("Double review 480b + kimi...")
            r1, r2 = await dual_review(args.code)
            if args.json:
                print(json.dumps({"review_480b": r1.__dict__, "review_kimi": r2.__dict__}, indent=2, default=str))
            else:
                print(r1.format_report())
                print(r2.format_report())
            return
        result = await review_code(args.code)
    else:
        # Read from stdin
        code = sys.stdin.read()
        if not code.strip():
            parser.print_help()
            return
        result = await review_code(code)

    if args.json:
        print(json.dumps(result.__dict__, indent=2, default=str))
    else:
        print(result.format_report())


if __name__ == "__main__":
    asyncio.run(_main())
