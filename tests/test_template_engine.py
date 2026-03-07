"""Tests for src/template_engine.py — Dynamic content generation.

Covers: TemplateEngine (register, unregister, set_global, render, render_named,
list_templates, get_stats, _process_vars, _process_if, _process_for, _eval_cond),
template_engine singleton.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.template_engine import TemplateEngine, template_engine


# ===========================================================================
# TemplateEngine — register / unregister
# ===========================================================================

class TestRegister:
    def test_register_and_list(self):
        te = TemplateEngine()
        te.register("greeting", "Hello {{ name }}!")
        templates = te.list_templates()
        assert len(templates) == 1
        assert templates[0]["name"] == "greeting"

    def test_unregister(self):
        te = TemplateEngine()
        te.register("temp", "text")
        assert te.unregister("temp") is True
        assert te.list_templates() == []

    def test_unregister_nonexistent(self):
        te = TemplateEngine()
        assert te.unregister("nope") is False


# ===========================================================================
# TemplateEngine — render (variable substitution)
# ===========================================================================

class TestRenderVars:
    def test_simple_var(self):
        te = TemplateEngine()
        result = te.render("Hello {{ name }}!", {"name": "Turbo"})
        assert result == "Hello Turbo!"

    def test_multiple_vars(self):
        te = TemplateEngine()
        result = te.render("{{ a }} + {{ b }}", {"a": "1", "b": "2"})
        assert result == "1 + 2"

    def test_dot_notation(self):
        te = TemplateEngine()
        result = te.render("{{ user.name }}", {"user": {"name": "JARVIS"}})
        assert result == "JARVIS"

    def test_missing_var(self):
        te = TemplateEngine()
        result = te.render("Hello {{ name }}!")
        assert result == "Hello !"

    def test_global_var(self):
        te = TemplateEngine()
        te.set_global("version", "12.4")
        result = te.render("v{{ version }}")
        assert result == "v12.4"

    def test_context_overrides_global(self):
        te = TemplateEngine()
        te.set_global("name", "global")
        result = te.render("{{ name }}", {"name": "local"})
        assert result == "local"


# ===========================================================================
# TemplateEngine — render (conditionals)
# ===========================================================================

class TestRenderIf:
    def test_if_true(self):
        te = TemplateEngine()
        result = te.render("{% if show %}visible{% endif %}", {"show": True})
        assert result == "visible"

    def test_if_false(self):
        te = TemplateEngine()
        result = te.render("{% if show %}visible{% endif %}", {"show": False})
        assert result == ""

    def test_if_negation(self):
        te = TemplateEngine()
        result = te.render("{% if !hide %}shown{% endif %}", {"hide": False})
        assert result == "shown"

    def test_if_not_keyword(self):
        te = TemplateEngine()
        result = te.render("{% if not hide %}shown{% endif %}", {"hide": False})
        assert result == "shown"

    def test_if_equals(self):
        te = TemplateEngine()
        result = te.render("{% if mode == 'dark' %}dark{% endif %}", {"mode": "dark"})
        assert result == "dark"

    def test_if_greater(self):
        te = TemplateEngine()
        result = te.render("{% if score > 50 %}pass{% endif %}", {"score": 80})
        assert result == "pass"

    def test_if_less(self):
        te = TemplateEngine()
        result = te.render("{% if temp < 90 %}ok{% endif %}", {"temp": 60})
        assert result == "ok"


# ===========================================================================
# TemplateEngine — render (for loops)
# ===========================================================================

class TestRenderFor:
    def test_for_loop(self):
        te = TemplateEngine()
        result = te.render(
            "{% for item in items %}{{ item }},{% endfor %}",
            {"items": ["a", "b", "c"]}
        )
        assert result == "a,b,c,"

    def test_for_loop_empty(self):
        te = TemplateEngine()
        result = te.render(
            "{% for x in things %}{{ x }}{% endfor %}",
            {"things": []}
        )
        assert result == ""

    def test_nested_vars_in_loop(self):
        te = TemplateEngine()
        result = te.render(
            "{% for n in names %}Hello {{ n }}! {% endfor %}",
            {"names": ["A", "B"]}
        )
        assert result == "Hello A! Hello B! "


# ===========================================================================
# TemplateEngine — render_named
# ===========================================================================

class TestRenderNamed:
    def test_success(self):
        te = TemplateEngine()
        te.register("greet", "Hi {{ who }}")
        result = te.render_named("greet", {"who": "Turbo"})
        assert result == "Hi Turbo"

    def test_nonexistent(self):
        te = TemplateEngine()
        assert te.render_named("nope") is None


# ===========================================================================
# TemplateEngine — stats
# ===========================================================================

class TestStats:
    def test_stats(self):
        te = TemplateEngine()
        te.register("a", "template")
        te.set_global("g", "val")
        te.render("{{ x }}", {"x": 1})
        stats = te.get_stats()
        assert stats["total_templates"] == 1
        assert stats["global_vars"] == 1
        assert stats["render_count"] == 1


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert template_engine is not None
        assert isinstance(template_engine, TemplateEngine)
