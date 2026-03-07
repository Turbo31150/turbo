"""Auto Auditor — Automated codebase audit engine.

Full-spectrum audit: code quality, test coverage, security patterns,
complexity, dead code, TODOs, and before/after improvement tracking.
Runs locally without external deps. Cluster-augmented when available.
Designed for JARVIS total automation.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


__all__ = [
    "AuditEvent",
    "AuditFinding",
    "AuditReport",
    "AutoAuditor",
]

logger = logging.getLogger("jarvis.auto_auditor")

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# ── Security patterns to detect ──────────────────────────────────────────────
SECURITY_PATTERNS = [
    (r'(?:password|passwd|pwd)\s*=\s*["\'][^"\']+["\']', "hardcoded_password"),
    (r'(?:token|api_key|secret)\s*=\s*["\'][^"\']+["\']', "hardcoded_secret"),
    (r'(?<!\w)eval\s*\(', "eval_usage"),
    (r'(?<!\w)exec\s*\(', "exec_usage"),
    (r'subprocess\.(?:call|run|Popen)\s*\([^)]*shell\s*=\s*True', "shell_injection_risk"),
    (r'os\.system\s*\(', "os_system_usage"),
    (r'__import__\s*\(', "dynamic_import"),
    (r'pickle\.loads?\s*\(', "pickle_deserialization"),
    (r'yaml\.(?:load|unsafe_load)\s*\(', "unsafe_yaml_load"),
    (r'# ?TODO|# ?FIXME|# ?HACK|# ?XXX', "todo_marker"),
]

COMPILED_PATTERNS = [(re.compile(p, re.IGNORECASE), name) for p, name in SECURITY_PATTERNS]

# Files where shell=True / eval / exec are expected by design
SECURITY_EXEMPTIONS = {
    "domino_executor", "domino_pipelines", "commands_pipelines",
    "cowork_engine", "code_review_480b", "jarvis_core",
}


@dataclass
class AuditFinding:
    """A single audit finding."""
    category: str  # security, quality, complexity, coverage, dead_code
    severity: str  # critical, major, minor, info
    file: str
    line: int = 0
    message: str = ""
    pattern: str = ""


@dataclass
class AuditReport:
    """Complete audit report."""
    timestamp: float = field(default_factory=time.time)
    duration_ms: int = 0
    total_modules: int = 0
    total_test_files: int = 0
    total_lines: int = 0
    test_coverage_ratio: float = 0.0
    findings: list[AuditFinding] = field(default_factory=list)
    module_stats: list[dict] = field(default_factory=list)
    summary: dict = field(default_factory=dict)

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "critical")

    @property
    def major_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "major")

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms,
            "total_modules": self.total_modules,
            "total_test_files": self.total_test_files,
            "total_lines": self.total_lines,
            "test_coverage_ratio": self.test_coverage_ratio,
            "critical_count": self.critical_count,
            "major_count": self.major_count,
            "total_findings": len(self.findings),
            "findings_by_category": self._group_by("category"),
            "findings_by_severity": self._group_by("severity"),
            "summary": self.summary,
        }

    def _group_by(self, attr: str) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for f in self.findings:
            counts[getattr(f, attr)] += 1
        return dict(counts)


@dataclass
class AuditEvent:
    """Record of an audit action."""
    action: str
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True


class AutoAuditor:
    """Automated codebase audit engine."""

    def __init__(self, project_root: Path | None = None):
        self._root = project_root or Path("F:/BUREAU/turbo")
        self._events: list[AuditEvent] = []
        self._reports: list[AuditReport] = []
        self._lock = threading.Lock()

    # ── Full Audit ────────────────────────────────────────────────────────

    def run_full_audit(self) -> AuditReport:
        """Run complete audit: quality + security + coverage + complexity."""
        t0 = time.monotonic()
        report = AuditReport()

        # 1. Scan modules
        src_dir = self._root / "src"
        tests_dir = self._root / "tests"
        modules = self._scan_modules(src_dir)
        test_files = self._scan_test_files(tests_dir)

        report.total_modules = len(modules)
        report.total_test_files = len(test_files)
        report.total_lines = sum(m["lines"] for m in modules)
        report.module_stats = modules

        # 2. Test coverage ratio
        tested_names = {t.stem.replace("test_", "") for t in test_files}
        module_names = {m["name"] for m in modules}
        covered = module_names & tested_names
        report.test_coverage_ratio = round(len(covered) / max(len(module_names), 1) * 100, 1)

        # 3. Find untested modules
        untested = sorted(module_names - tested_names)
        for name in untested:
            mod = next((m for m in modules if m["name"] == name), None)
            lines = mod["lines"] if mod else 0
            severity = "major" if lines > 100 else "minor"
            report.findings.append(AuditFinding(
                category="coverage", severity=severity,
                file=f"src/{name}.py", message=f"No test file ({lines}L)",
            ))

        # 4. Security scan
        for mod in modules:
            self._scan_security(mod["path"], report)

        # 5. Complexity scan
        for mod in modules:
            self._scan_complexity(mod, report)

        # 6. Summary
        report.duration_ms = int((time.monotonic() - t0) * 1000)
        report.summary = {
            "score": self._calculate_score(report),
            "tested_ratio_pct": report.test_coverage_ratio,
            "untested_modules": len(untested),
            "security_issues": sum(1 for f in report.findings if f.category == "security"),
            "complexity_warnings": sum(1 for f in report.findings if f.category == "complexity"),
            "todo_count": sum(1 for f in report.findings if f.pattern == "todo_marker"),
        }

        with self._lock:
            self._reports.append(report)
            self._events.append(AuditEvent(
                action="full_audit", success=True,
                detail=f"score={report.summary['score']}, {len(report.findings)} findings",
            ))

        return report

    # ── Scanners ──────────────────────────────────────────────────────────

    def _scan_modules(self, src_dir: Path) -> list[dict]:
        """Scan all Python modules in src/."""
        modules = []
        if not src_dir.exists():
            return modules
        for f in sorted(src_dir.glob("*.py")):
            if f.name.startswith("__"):
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
                lines = content.count("\n") + 1
                functions = len(re.findall(r'^(?:    )?def \w+', content, re.MULTILINE))
                classes = len(re.findall(r'^class \w+', content, re.MULTILINE))
                imports = len(re.findall(r'^(?:import|from)\s', content, re.MULTILINE))
                modules.append({
                    "name": f.stem,
                    "path": str(f),
                    "lines": lines,
                    "functions": functions,
                    "classes": classes,
                    "imports": imports,
                })
            except Exception as e:
                logger.debug("scan error %s: %s", f, e)
        return modules

    def _scan_test_files(self, tests_dir: Path) -> list[Path]:
        """Scan test files."""
        if not tests_dir.exists():
            return []
        return sorted(tests_dir.glob("test_*.py"))

    def _scan_security(self, filepath: str, report: AuditReport) -> None:
        """Scan a file for security patterns."""
        try:
            file_stem = Path(filepath).stem
            is_exempt = file_stem in SECURITY_EXEMPTIONS
            content = Path(filepath).read_text(encoding="utf-8", errors="replace")
            for lineno, line in enumerate(content.splitlines(), 1):
                for pattern, name in COMPILED_PATTERNS:
                    if pattern.search(line):
                        # Downgrade severity for exempt files (executors, etc.)
                        if is_exempt and name in ("shell_injection_risk", "eval_usage", "exec_usage", "os_system_usage"):
                            severity = "info"
                        elif name == "todo_marker":
                            severity = "info"
                        elif name in ("hardcoded_password", "hardcoded_secret", "shell_injection_risk"):
                            severity = "critical"
                        elif name in ("eval_usage", "exec_usage", "pickle_deserialization", "unsafe_yaml_load"):
                            severity = "major"
                        else:
                            severity = "minor"
                        report.findings.append(AuditFinding(
                            category="security" if name != "todo_marker" else "quality",
                            severity=severity,
                            file=filepath, line=lineno,
                            message=line.strip()[:120],
                            pattern=name,
                        ))
        except Exception:
            pass

    def _scan_complexity(self, mod: dict, report: AuditReport) -> None:
        """Flag modules with high complexity indicators."""
        lines = mod["lines"]
        functions = mod["functions"]

        if lines > 500:
            report.findings.append(AuditFinding(
                category="complexity", severity="major",
                file=mod["path"], message=f"Very large module: {lines} lines",
            ))
        elif lines > 200:
            report.findings.append(AuditFinding(
                category="complexity", severity="minor",
                file=mod["path"], message=f"Large module: {lines} lines",
            ))

        if functions > 30:
            report.findings.append(AuditFinding(
                category="complexity", severity="minor",
                file=mod["path"],
                message=f"Many functions: {functions} (consider splitting)",
            ))

    def _calculate_score(self, report: AuditReport) -> int:
        """Calculate overall audit score 0-100.

        Weighted: security critical=-10, major=-3, complexity/quality minor=-0.2.
        Bonus for high test coverage. Complexity findings are soft penalties
        since large modules are normal in big projects.
        """
        score = 100.0
        for f in report.findings:
            if f.severity == "critical":
                score -= 10
            elif f.severity == "major" and f.category == "security":
                score -= 3
            elif f.severity == "major" and f.category == "coverage":
                score -= 1.5
            elif f.severity == "major" and f.category == "complexity":
                score -= 0.5
            elif f.severity == "minor":
                score -= 0.1
            elif f.severity == "info":
                pass  # no penalty
        # Bonus for test coverage
        score += report.test_coverage_ratio * 0.15
        if report.test_coverage_ratio < 50:
            score -= 10
        return max(0, min(100, int(score)))

    # ── Comparison ────────────────────────────────────────────────────────

    def compare_reports(self, before: AuditReport, after: AuditReport) -> dict[str, Any]:
        """Compare two audit reports (before/after improvement)."""
        b = before.to_dict()
        a = after.to_dict()
        return {
            "score_before": b["summary"].get("score", 0),
            "score_after": a["summary"].get("score", 0),
            "score_delta": a["summary"].get("score", 0) - b["summary"].get("score", 0),
            "findings_before": b["total_findings"],
            "findings_after": a["total_findings"],
            "findings_delta": a["total_findings"] - b["total_findings"],
            "critical_before": b["critical_count"],
            "critical_after": a["critical_count"],
            "coverage_before": b.get("test_coverage_ratio", 0),
            "coverage_after": a.get("test_coverage_ratio", 0),
            "improved": a["summary"].get("score", 0) > b["summary"].get("score", 0),
        }

    # ── Quick scans ───────────────────────────────────────────────────────

    def scan_file(self, filepath: str) -> list[dict]:
        """Quick security scan of a single file."""
        report = AuditReport()
        self._scan_security(filepath, report)
        return [{"severity": f.severity, "line": f.line, "pattern": f.pattern,
                 "message": f.message} for f in report.findings]

    def get_untested_modules(self) -> list[dict]:
        """List modules without corresponding test files."""
        modules = self._scan_modules(self._root / "src")
        test_files = self._scan_test_files(self._root / "tests")
        tested = {t.stem.replace("test_", "") for t in test_files}
        untested = []
        for m in modules:
            if m["name"] not in tested:
                untested.append({"name": m["name"], "lines": m["lines"], "path": m["path"]})
        return sorted(untested, key=lambda x: -x["lines"])

    def get_largest_modules(self, top: int = 20) -> list[dict]:
        """Get largest modules by line count."""
        modules = self._scan_modules(self._root / "src")
        return sorted(modules, key=lambda x: -x["lines"])[:top]

    # ── Pytest integration ────────────────────────────────────────────────

    def run_tests(self, timeout: int = 120) -> dict[str, Any]:
        """Run pytest and return summary."""
        try:
            result = subprocess.run(
                ["python", "-m", "pytest", "--tb=no", "-q", "--no-header"],
                capture_output=True, text=True, timeout=timeout,
                cwd=str(self._root), encoding="utf-8", errors="replace",
                creationflags=_NO_WINDOW,
            )
            output = result.stdout + result.stderr
            # Parse "X passed, Y failed, Z skipped"
            match = re.search(r'(\d+) passed', output)
            passed = int(match.group(1)) if match else 0
            match = re.search(r'(\d+) failed', output)
            failed = int(match.group(1)) if match else 0
            match = re.search(r'(\d+) skipped', output)
            skipped = int(match.group(1)) if match else 0
            self._record("run_tests", True, f"{passed} passed, {failed} failed")
            return {
                "passed": passed, "failed": failed, "skipped": skipped,
                "total": passed + failed + skipped,
                "returncode": result.returncode,
                "success": result.returncode == 0,
            }
        except Exception as e:
            self._record("run_tests", False, str(e))
            return {"passed": 0, "failed": 0, "skipped": 0, "total": 0,
                    "returncode": -1, "success": False, "error": str(e)}

    # ── Events / Stats ────────────────────────────────────────────────────

    def _record(self, action: str, success: bool, detail: str = "") -> None:
        with self._lock:
            self._events.append(AuditEvent(action=action, success=success, detail=detail))

    def get_events(self, limit: int = 50) -> list[dict]:
        with self._lock:
            return [
                {"action": e.action, "timestamp": e.timestamp,
                 "success": e.success, "detail": e.detail}
                for e in self._events[-limit:]
            ]

    def get_reports(self) -> list[dict]:
        """Get all audit report summaries."""
        with self._lock:
            return [r.to_dict() for r in self._reports]

    def get_stats(self) -> dict:
        with self._lock:
            return {
                "total_audits": len(self._reports),
                "total_events": len(self._events),
                "last_score": self._reports[-1].summary.get("score", 0) if self._reports else None,
            }


# ── Singleton ─────────────────────────────────────────────────────────────────
auto_auditor = AutoAuditor()
