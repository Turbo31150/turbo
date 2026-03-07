"""Tests for auto_fixer module."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.auto_fixer import AutoFixer, FixResult


@pytest.fixture
def fixer(tmp_path):
    """Create AutoFixer with temp project root."""
    src = tmp_path / "src"
    src.mkdir()
    tests = tmp_path / "tests"
    tests.mkdir()
    return AutoFixer(project_root=tmp_path)


@pytest.fixture
def sample_module(tmp_path):
    """Create a sample module without docstring."""
    src = tmp_path / "src"
    src.mkdir(exist_ok=True)
    f = src / "sample.py"
    f.write_text(
        "import os\nimport sys\n\n"
        "def hello():\n    pass\n\n"
        "def world():\n    pass\n\n"
        "class Foo:\n    pass\n\n"
        "def bar():\n    pass\n",
        encoding="utf-8",
    )
    return f


class TestFixResult:
    def test_creation(self):
        r = FixResult("test.py", "add_docstring", True, "done", 1)
        assert r.file == "test.py"
        assert r.fix_type == "add_docstring"
        assert r.applied is True
        assert r.lines_changed == 1

    def test_defaults(self):
        r = FixResult("test.py", "add_all", False)
        assert r.message == ""
        assert r.lines_changed == 0


class TestAddDocstring:
    def test_adds_docstring(self, fixer, sample_module):
        result = fixer._fix_add_docstring(str(sample_module))
        assert result.applied is True
        content = sample_module.read_text()
        assert '"""Sample module."""' in content

    def test_skips_existing_docstring(self, fixer, tmp_path):
        src = tmp_path / "src"
        src.mkdir(exist_ok=True)
        f = src / "has_doc.py"
        f.write_text('"""Already here."""\nimport os\n', encoding="utf-8")
        result = fixer._fix_add_docstring(str(f))
        assert result.applied is False

    def test_skips_shebang(self, fixer, tmp_path):
        src = tmp_path / "src"
        src.mkdir(exist_ok=True)
        f = src / "shebang.py"
        f.write_text("#!/usr/bin/env python\nimport os\n", encoding="utf-8")
        result = fixer._fix_add_docstring(str(f))
        assert result.applied is False


class TestAddAllExport:
    def test_adds_all(self, fixer, sample_module):
        result = fixer._fix_add_all_export(str(sample_module))
        assert result.applied is True
        content = sample_module.read_text()
        assert "__all__" in content
        assert '"hello"' in content
        assert '"Foo"' in content

    def test_skips_existing_all(self, fixer, tmp_path):
        src = tmp_path / "src"
        src.mkdir(exist_ok=True)
        f = src / "has_all.py"
        f.write_text('__all__ = ["foo"]\ndef foo():\n    pass\n', encoding="utf-8")
        result = fixer._fix_add_all_export(str(f))
        assert result.applied is False

    def test_skips_no_public(self, fixer, tmp_path):
        src = tmp_path / "src"
        src.mkdir(exist_ok=True)
        f = src / "private.py"
        f.write_text("def _private():\n    pass\n", encoding="utf-8")
        result = fixer._fix_add_all_export(str(f))
        assert result.applied is False


class TestFlagLongFunctions:
    def test_flags_long(self, fixer, tmp_path):
        src = tmp_path / "src"
        src.mkdir(exist_ok=True)
        f = src / "long.py"
        # Create a function with 100+ lines
        lines = ["def long_func():\n"]
        lines.extend(["    pass\n"] * 100)
        lines.append("\ndef short():\n    pass\n")
        f.write_text("".join(lines), encoding="utf-8")
        result = fixer._fix_flag_long_functions(str(f))
        assert result.applied is True
        assert "long_func" in result.message

    def test_no_long_functions(self, fixer, tmp_path):
        src = tmp_path / "src"
        src.mkdir(exist_ok=True)
        f = src / "short.py"
        f.write_text("def short():\n    pass\n", encoding="utf-8")
        result = fixer._fix_flag_long_functions(str(f))
        assert result.applied is False


class TestMeasureFunctionLengths:
    def test_measures(self, fixer):
        code = "def a():\n    pass\n\ndef b():\n    x = 1\n    y = 2\n    return x + y\n"
        lengths = fixer._measure_function_lengths(code)
        assert "a" in lengths
        assert "b" in lengths
        assert lengths["a"] == 3  # lines 0-2 (def, pass, empty), next func at line 3
        assert lengths["b"] == 4  # lines 3-6


class TestGetApplicableFixes:
    def test_identifies_fixes(self, fixer, sample_module):
        from src.auto_auditor import AuditReport
        report = AuditReport()
        fixes = fixer._get_applicable_fixes(str(sample_module), report)
        assert "add_docstring" in fixes

    def test_nonexistent_file(self, fixer):
        from src.auto_auditor import AuditReport
        report = AuditReport()
        fixes = fixer._get_applicable_fixes("/nonexistent/file.py", report)
        assert fixes == []


class TestGetFixStats:
    def test_empty(self, fixer):
        stats = fixer.get_fix_stats()
        assert stats["total"] == 0
        assert stats["applied"] == 0

    def test_with_fixes(self, fixer):
        fixer._fixes = [
            FixResult("a.py", "add_docstring", True, "", 1),
            FixResult("b.py", "add_docstring", False, "skip", 0),
            FixResult("c.py", "add_all_export", True, "", 5),
        ]
        stats = fixer.get_fix_stats()
        assert stats["total"] == 3
        assert stats["applied"] == 2
        assert stats["skipped"] == 1
        assert stats["lines_changed"] == 6


class TestGetFixes:
    def test_returns_dicts(self, fixer):
        fixer._fixes = [FixResult("a.py", "test", True, "ok", 2)]
        fixes = fixer.get_fixes()
        assert len(fixes) == 1
        assert fixes[0]["file"] == "a.py"
        assert fixes[0]["applied"] is True
