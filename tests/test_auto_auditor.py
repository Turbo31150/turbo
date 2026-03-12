"""Tests for src/auto_auditor.py — Automated codebase audit engine.

Covers: AuditFinding, AuditReport, AuditEvent, AutoAuditor (run_full_audit,
scan_file, get_untested_modules, get_largest_modules, compare_reports,
run_tests, get_events, get_reports, get_stats), auto_auditor singleton.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.auto_auditor import (
    AuditFinding, AuditReport, AuditEvent, AutoAuditor,
    auto_auditor, COMPILED_PATTERNS,
)


class TestAuditFinding:
    def test_creation(self):
        f = AuditFinding(category="security", severity="critical", file="test.py")
        assert f.line == 0
        assert f.message == ""


class TestAuditReport:
    def test_defaults(self):
        r = AuditReport()
        assert r.critical_count == 0
        assert r.major_count == 0

    def test_counts(self):
        r = AuditReport(findings=[
            AuditFinding(category="security", severity="critical", file="a.py"),
            AuditFinding(category="security", severity="critical", file="b.py"),
            AuditFinding(category="quality", severity="major", file="c.py"),
        ])
        assert r.critical_count == 2
        assert r.major_count == 1

    def test_to_dict(self):
        r = AuditReport(total_modules=10, total_lines=1000)
        r.summary = {"score": 85}
        d = r.to_dict()
        assert d["total_modules"] == 10
        assert d["total_lines"] == 1000

    def test_group_by(self):
        r = AuditReport(findings=[
            AuditFinding(category="security", severity="critical", file="a.py"),
            AuditFinding(category="security", severity="major", file="b.py"),
            AuditFinding(category="quality", severity="minor", file="c.py"),
        ])
        d = r.to_dict()
        assert d["findings_by_category"]["security"] == 2
        assert d["findings_by_severity"]["critical"] == 1


class TestAutoAuditorScanModules:
    def test_scan_modules(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "mod_a.py").write_text("def foo():\n    pass\n\ndef bar():\n    pass\n")
        (src / "mod_b.py").write_text("class MyClass:\n    pass\n")
        (src / "__init__.py").write_text("")  # should be skipped

        auditor = AutoAuditor(project_root=tmp_path)
        modules = auditor._scan_modules(src)
        names = [m["name"] for m in modules]
        assert "mod_a" in names
        assert "mod_b" in names
        assert "__init__" not in names

        mod_a = next(m for m in modules if m["name"] == "mod_a")
        assert mod_a["functions"] == 2

    def test_scan_nonexistent_dir(self, tmp_path):
        auditor = AutoAuditor(project_root=tmp_path)
        assert auditor._scan_modules(tmp_path / "nope") == []


class TestAutoAuditorSecurity:
    def test_detect_hardcoded_password(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "bad.py").write_text('password = "secret123"\n')

        auditor = AutoAuditor(project_root=tmp_path)
        report = AuditReport()
        auditor._scan_security(str(src / "bad.py"), report)
        assert any(f.pattern == "hardcoded_password" for f in report.findings)
        assert any(f.severity == "critical" for f in report.findings)

    def test_detect_eval(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "risky.py").write_text('result = eval(user_input)\n')

        auditor = AutoAuditor(project_root=tmp_path)
        report = AuditReport()
        auditor._scan_security(str(src / "risky.py"), report)
        assert any(f.pattern == "eval_usage" for f in report.findings)

    def test_detect_todo(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "wip.py").write_text('# TODO: fix this\n')

        auditor = AutoAuditor(project_root=tmp_path)
        report = AuditReport()
        auditor._scan_security(str(src / "wip.py"), report)
        assert any(f.pattern == "todo_marker" for f in report.findings)
        assert any(f.category == "quality" for f in report.findings)

    def test_clean_file(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "clean.py").write_text('def hello():\n    return "world"\n')

        auditor = AutoAuditor(project_root=tmp_path)
        report = AuditReport()
        auditor._scan_security(str(src / "clean.py"), report)
        assert len(report.findings) == 0


class TestAutoAuditorComplexity:
    def test_large_module(self):
        auditor = AutoAuditor()
        report = AuditReport()
        auditor._scan_complexity(
            {"name": "big", "path": "src/big.py", "lines": 1200, "functions": 10}, report)
        assert any(f.category == "complexity" and f.severity == "major" for f in report.findings)

    def test_medium_module(self):
        auditor = AutoAuditor()
        report = AuditReport()
        auditor._scan_complexity(
            {"name": "med", "path": "src/med.py", "lines": 500, "functions": 10}, report)
        assert any(f.severity == "minor" for f in report.findings)

    def test_small_module(self):
        auditor = AutoAuditor()
        report = AuditReport()
        auditor._scan_complexity(
            {"name": "small", "path": "src/small.py", "lines": 50, "functions": 3}, report)
        assert len(report.findings) == 0

    def test_many_functions(self):
        auditor = AutoAuditor()
        report = AuditReport()
        auditor._scan_complexity(
            {"name": "funcs", "path": "src/funcs.py", "lines": 100, "functions": 35}, report)
        assert any("functions" in f.message.lower() for f in report.findings)


class TestFullAudit:
    def test_full_audit(self, tmp_path):
        src = tmp_path / "src"
        tests = tmp_path / "tests"
        src.mkdir()
        tests.mkdir()
        (src / "module_a.py").write_text("def foo():\n    pass\n")
        (src / "module_b.py").write_text("def bar():\n    pass\n")
        (tests / "test_module_a.py").write_text("def test_foo():\n    pass\n")

        auditor = AutoAuditor(project_root=tmp_path)
        report = auditor.run_full_audit()

        assert report.total_modules == 2
        assert report.total_test_files == 1
        assert report.test_coverage_ratio == 50.0
        assert report.summary["score"] > 0
        # module_b is untested
        assert any(f.category == "coverage" and "module_b" in f.file for f in report.findings)


class TestScanFile:
    def test_scan_file(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text('token = "abc123"\n# TODO fix\n')

        auditor = AutoAuditor()
        findings = auditor.scan_file(str(f))
        patterns = [f["pattern"] for f in findings]
        assert "hardcoded_secret" in patterns
        assert "todo_marker" in patterns


class TestGetUntestedModules:
    def test_untested(self, tmp_path):
        src = tmp_path / "src"
        tests = tmp_path / "tests"
        src.mkdir()
        tests.mkdir()
        (src / "covered.py").write_text("pass\n")
        (src / "uncovered.py").write_text("pass\n" * 50)
        (tests / "test_covered.py").write_text("pass\n")

        auditor = AutoAuditor(project_root=tmp_path)
        untested = auditor.get_untested_modules()
        assert len(untested) == 1
        assert untested[0]["name"] == "uncovered"


class TestCompareReports:
    def test_compare(self):
        before = AuditReport(summary={"score": 60}, findings=[
            AuditFinding(category="security", severity="critical", file="a.py"),
        ])
        before.test_coverage_ratio = 40.0
        after = AuditReport(summary={"score": 85}, findings=[])
        after.test_coverage_ratio = 70.0

        auditor = AutoAuditor()
        cmp = auditor.compare_reports(before, after)
        assert cmp["score_delta"] == 25
        assert cmp["improved"] is True
        assert cmp["findings_before"] == 1
        assert cmp["findings_after"] == 0


class TestRunTests:
    def test_run_tests_success(self):
        auditor = AutoAuditor()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "150 passed, 2 skipped in 4.5s"
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result):
            result = auditor.run_tests()
        assert result["passed"] == 150
        assert result["success"] is True

    def test_run_tests_failure(self):
        auditor = AutoAuditor()
        with patch("subprocess.run", side_effect=Exception("timeout")):
            result = auditor.run_tests()
        assert result["success"] is False


class TestEventsStats:
    def test_events_empty(self):
        assert AutoAuditor().get_events() == []

    def test_stats(self):
        assert AutoAuditor().get_stats()["total_audits"] == 0

    def test_reports_empty(self):
        assert AutoAuditor().get_reports() == []


class TestSingleton:
    def test_exists(self):
        assert isinstance(auto_auditor, AutoAuditor)
