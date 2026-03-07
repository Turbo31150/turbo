"""Command Router — Natural language command routing.

Maps user text (voice or typed) to registered actions using
keyword matching, regex patterns, and scoring.
"""

from __future__ import annotations

import re
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine


__all__ = [
    "CommandRouter",
    "MatchResult",
    "Route",
]

logger = logging.getLogger("jarvis.command_router")

ActionFunc = Callable[..., Coroutine[Any, Any, Any] | Any]


@dataclass
class Route:
    """A registered command route."""
    name: str
    keywords: list[str]
    patterns: list[re.Pattern]
    handler: ActionFunc
    category: str = "general"
    priority: int = 0
    description: str = ""
    call_count: int = 0
    last_called: float = 0.0


@dataclass
class MatchResult:
    """Result of matching user input to a route."""
    route: Route
    score: float
    matched_by: str  # "keyword", "pattern", "exact"
    captures: dict[str, str] = field(default_factory=dict)


class CommandRouter:
    """Routes natural language commands to handlers."""

    def __init__(self):
        self._routes: dict[str, Route] = {}
        self._history: list[dict] = []
        self._max_history = 200

    def register(
        self,
        name: str,
        handler: ActionFunc,
        keywords: list[str] | None = None,
        patterns: list[str] | None = None,
        category: str = "general",
        priority: int = 0,
        description: str = "",
    ) -> None:
        """Register a command route."""
        compiled = [re.compile(p, re.IGNORECASE) for p in (patterns or [])]
        self._routes[name] = Route(
            name=name,
            keywords=[k.lower() for k in (keywords or [])],
            patterns=compiled,
            handler=handler,
            category=category,
            priority=priority,
            description=description,
        )

    def unregister(self, name: str) -> bool:
        return self._routes.pop(name, None) is not None

    def match(self, text: str, top_n: int = 3) -> list[MatchResult]:
        """Find matching routes for input text. Returns top N sorted by score."""
        text_lower = text.lower().strip()
        results: list[MatchResult] = []

        for route in self._routes.values():
            best_score = 0.0
            matched_by = ""
            captures: dict[str, str] = {}

            # Exact match on name
            if text_lower == route.name.lower():
                best_score = 1.0
                matched_by = "exact"

            # Keyword matching
            if best_score < 1.0:
                kw_score = self._keyword_score(text_lower, route.keywords)
                if kw_score > best_score:
                    best_score = kw_score
                    matched_by = "keyword"

            # Pattern matching
            for pat in route.patterns:
                m = pat.search(text)
                if m:
                    pat_score = 0.9 + (route.priority * 0.01)
                    if pat_score > best_score:
                        best_score = pat_score
                        matched_by = "pattern"
                        captures = m.groupdict()

            if best_score > 0.1:
                results.append(MatchResult(
                    route=route, score=min(best_score, 1.0),
                    matched_by=matched_by, captures=captures,
                ))

        results.sort(key=lambda r: (-r.score, -r.route.priority))
        return results[:top_n]

    def route(self, text: str) -> MatchResult | None:
        """Find the best matching route. Returns None if no match above threshold."""
        matches = self.match(text, top_n=1)
        if matches and matches[0].score >= 0.3:
            result = matches[0]
            result.route.call_count += 1
            result.route.last_called = time.time()
            self._record_history(text, result)
            return result
        return None

    @staticmethod
    def _keyword_score(text: str, keywords: list[str]) -> float:
        if not keywords:
            return 0.0
        words = set(text.split())
        matched = sum(1 for kw in keywords if kw in words or kw in text)
        return matched / len(keywords) * 0.8

    def _record_history(self, text: str, result: MatchResult) -> None:
        self._history.append({
            "ts": time.time(),
            "input": text,
            "route": result.route.name,
            "score": round(result.score, 3),
            "matched_by": result.matched_by,
        })
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    def get_routes(self) -> list[dict]:
        """List all registered routes."""
        return [
            {
                "name": r.name,
                "category": r.category,
                "keywords": r.keywords,
                "patterns": [p.pattern for p in r.patterns],
                "description": r.description,
                "call_count": r.call_count,
                "priority": r.priority,
            }
            for r in self._routes.values()
        ]

    def get_history(self, limit: int = 50) -> list[dict]:
        return self._history[-limit:]

    def get_stats(self) -> dict:
        return {
            "total_routes": len(self._routes),
            "categories": list(set(r.category for r in self._routes.values())),
            "total_calls": sum(r.call_count for r in self._routes.values()),
            "history_size": len(self._history),
        }


# ── Singleton ────────────────────────────────────────────────────────────────
command_router = CommandRouter()
