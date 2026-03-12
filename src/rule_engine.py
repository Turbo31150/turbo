"""Rule Engine — Condition-based rule evaluation with actions, priorities, and groups."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Callable


@dataclass
class Rule:
    name: str
    condition: Callable[[dict], bool]
    action: Callable[[dict], Any]
    priority: int = 0  # higher = first
    group: str = "default"
    enabled: bool = True
    description: str = ""
    fire_count: int = 0
    last_fired: float = 0.0
    created_at: float = field(default_factory=time.time)


class RuleEngine:
    """Evaluate rules against context and execute matching actions."""

    def __init__(self):
        self._rules: dict[str, Rule] = {}
        self._evaluation_log: list[dict] = []
        self._max_log = 500
        self._lock = Lock()

    # ── Rule Management ─────────────────────────────────────────────
    def add_rule(self, name: str, condition: Callable[[dict], bool],
                 action: Callable[[dict], Any], priority: int = 0,
                 group: str = "default", description: str = "") -> Rule:
        rule = Rule(
            name=name, condition=condition, action=action,
            priority=priority, group=group, description=description,
        )
        with self._lock:
            self._rules[name] = rule
        return rule

    def remove_rule(self, name: str) -> bool:
        with self._lock:
            return self._rules.pop(name, None) is not None

    def enable_rule(self, name: str) -> bool:
        r = self._rules.get(name)
        if not r:
            return False
        r.enabled = True
        return True

    def disable_rule(self, name: str) -> bool:
        r = self._rules.get(name)
        if not r:
            return False
        r.enabled = False
        return True

    def get_rule(self, name: str) -> Rule | None:
        return self._rules.get(name)

    def list_rules(self, group: str | None = None) -> list[dict]:
        with self._lock:
            rules = list(self._rules.values())
            if group:
                rules = [r for r in rules if r.group == group]
            rules.sort(key=lambda r: r.priority, reverse=True)
            return [
                {
                    "name": r.name, "priority": r.priority, "group": r.group,
                    "enabled": r.enabled, "description": r.description,
                    "fire_count": r.fire_count,
                }
                for r in rules
            ]

    def list_groups(self) -> list[str]:
        with self._lock:
            return list(set(r.group for r in self._rules.values()))

    # ── Evaluation ──────────────────────────────────────────────────
    def evaluate(self, context: dict, group: str | None = None,
                 first_match: bool = False) -> list[dict]:
        """Evaluate all matching rules against context.

        Args:
            context: Data dict passed to conditions and actions
            group: Only evaluate rules in this group
            first_match: Stop after first matching rule

        Returns:
            List of results from fired rules
        """
        with self._lock:
            rules = [r for r in self._rules.values() if r.enabled]
            if group:
                rules = [r for r in rules if r.group == group]
            rules.sort(key=lambda r: r.priority, reverse=True)

        results = []
        for rule in rules:
            try:
                if rule.condition(context):
                    result = rule.action(context)
                    with self._lock:
                        rule.fire_count += 1
                        rule.last_fired = time.time()
                        self._log_eval(rule.name, True, context)
                    results.append({
                        "rule": rule.name, "fired": True, "result": result,
                    })
                    if first_match:
                        break
            except Exception as exc:
                with self._lock:
                    self._log_eval(rule.name, False, context, str(exc))
                results.append({
                    "rule": rule.name, "fired": False, "error": str(exc),
                })
        return results

    def evaluate_first(self, context: dict, group: str | None = None) -> dict | None:
        """Evaluate and return only the first matching rule result."""
        results = self.evaluate(context, group=group, first_match=True)
        return results[0] if results else None

    # ── Log ─────────────────────────────────────────────────────────
    def _log_eval(self, rule_name: str, fired: bool, context: dict,
                  error: str = "") -> None:
        self._evaluation_log.append({
            "rule": rule_name, "fired": fired,
            "context_keys": list(context.keys()),
            "error": error, "timestamp": time.time(),
        })
        if len(self._evaluation_log) > self._max_log:
            self._evaluation_log = self._evaluation_log[-self._max_log:]

    def get_evaluation_log(self, limit: int = 50) -> list[dict]:
        with self._lock:
            return self._evaluation_log[-limit:]

    # ── Stats ───────────────────────────────────────────────────────
    def get_stats(self) -> dict:
        with self._lock:
            total = len(self._rules)
            enabled = sum(1 for r in self._rules.values() if r.enabled)
            groups = set(r.group for r in self._rules.values())
            total_fires = sum(r.fire_count for r in self._rules.values())
            return {
                "total_rules": total,
                "enabled": enabled,
                "disabled": total - enabled,
                "groups": len(groups),
                "total_fires": total_fires,
                "evaluation_log_size": len(self._evaluation_log),
            }


rule_engine = RuleEngine()
