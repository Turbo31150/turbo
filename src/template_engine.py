"""Template Engine — Dynamic content generation.

Simple template engine with variable substitution,
conditionals ({% if %}), and loops ({% for %}).
Used for generating reports, prompts, emails.
"""

from __future__ import annotations

import logging
import re
import threading
from typing import Any

logger = logging.getLogger("jarvis.template_engine")


class TemplateEngine:
    """Lightweight template engine with variables, conditions, loops."""

    def __init__(self):
        self._templates: dict[str, str] = {}
        self._globals: dict[str, Any] = {}
        self._lock = threading.Lock()
        self._render_count = 0

    def register(self, name: str, template: str) -> None:
        """Register a named template."""
        with self._lock:
            self._templates[name] = template

    def unregister(self, name: str) -> bool:
        with self._lock:
            return self._templates.pop(name, None) is not None

    def set_global(self, key: str, value: Any) -> None:
        """Set a global variable available in all templates."""
        self._globals[key] = value

    def render(self, template: str, context: dict | None = None) -> str:
        """Render a template string with given context."""
        ctx = {**self._globals, **(context or {})}
        with self._lock:
            self._render_count += 1
        result = self._process(template, ctx)
        return result

    def render_named(self, name: str, context: dict | None = None) -> str | None:
        """Render a registered template by name."""
        tmpl = self._templates.get(name)
        if tmpl is None:
            return None
        return self.render(tmpl, context)

    def list_templates(self) -> list[dict]:
        return [
            {"name": n, "length": len(t), "preview": t[:60]}
            for n, t in self._templates.items()
        ]

    def get_stats(self) -> dict:
        return {
            "total_templates": len(self._templates),
            "global_vars": len(self._globals),
            "render_count": self._render_count,
        }

    # ── Processing ────────────────────────────────────────────────

    def _process(self, template: str, ctx: dict) -> str:
        # Process for loops: {% for item in items %}...{% endfor %}
        result = self._process_for(template, ctx)
        # Process conditionals: {% if cond %}...{% endif %}
        result = self._process_if(result, ctx)
        # Process variables: {{ var }}
        result = self._process_vars(result, ctx)
        return result

    def _process_vars(self, template: str, ctx: dict) -> str:
        def replace_var(match):
            key = match.group(1).strip()
            # Support dot notation: obj.attr
            parts = key.split(".")
            val = ctx
            for p in parts:
                if isinstance(val, dict):
                    val = val.get(p, "")
                else:
                    val = getattr(val, p, "")
            return str(val)
        return re.sub(r"\{\{\s*(.+?)\s*\}\}", replace_var, template)

    def _process_if(self, template: str, ctx: dict) -> str:
        pattern = r"\{%\s*if\s+(.+?)\s*%\}(.*?)\{%\s*endif\s*%\}"
        def replace_if(match):
            cond = match.group(1).strip()
            body = match.group(2)
            # Evaluate condition
            if self._eval_cond(cond, ctx):
                return self._process(body, ctx)
            return ""
        return re.sub(pattern, replace_if, template, flags=re.DOTALL)

    def _process_for(self, template: str, ctx: dict) -> str:
        pattern = r"\{%\s*for\s+(\w+)\s+in\s+(\w+)\s*%\}(.*?)\{%\s*endfor\s*%\}"
        def replace_for(match):
            var_name = match.group(1)
            list_name = match.group(2)
            body = match.group(3)
            items = ctx.get(list_name, [])
            parts = []
            for item in items:
                local_ctx = {**ctx, var_name: item}
                parts.append(self._process(body, local_ctx))
            return "".join(parts)
        return re.sub(pattern, replace_for, template, flags=re.DOTALL)

    def _eval_cond(self, cond: str, ctx: dict) -> bool:
        """Simple condition evaluation: var, !var, var == 'value', var > N."""
        cond = cond.strip()
        # Negation
        if cond.startswith("!") or cond.startswith("not "):
            inner = cond.lstrip("!").replace("not ", "", 1).strip()
            return not self._eval_cond(inner, ctx)
        # Comparison ==
        if "==" in cond:
            left, right = cond.split("==", 1)
            left_val = str(ctx.get(left.strip(), ""))
            right_val = right.strip().strip("'\"")
            return left_val == right_val
        # Comparison >
        if ">" in cond:
            left, right = cond.split(">", 1)
            try:
                return float(ctx.get(left.strip(), 0)) > float(right.strip())
            except (ValueError, TypeError):
                return False
        # Comparison <
        if "<" in cond:
            left, right = cond.split("<", 1)
            try:
                return float(ctx.get(left.strip(), 0)) < float(right.strip())
            except (ValueError, TypeError):
                return False
        # Truthiness
        val = ctx.get(cond, None)
        return bool(val)


# ── Singleton ────────────────────────────────────────────────────────────────
template_engine = TemplateEngine()
