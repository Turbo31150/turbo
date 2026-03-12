"""JARVIS Auto-Improve Pipeline — Total automation.

Cycle: Audit → Identify worst modules → Review → Track improvements → Re-audit → Report.
Usage:
    python scripts/auto_improve.py                    # Full cycle
    python scripts/auto_improve.py --audit-only       # Just audit
    python scripts/auto_improve.py --report           # Show last report
    python scripts/auto_improve.py --compare          # Compare last 2 audits
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.auto_auditor import AutoAuditor


def print_header(text: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")


def print_finding(f: dict, idx: int) -> None:
    sev = f.get("severity", "?").upper()
    cat = f.get("category", "?")
    file = Path(f.get("file", "")).name
    line = f.get("line", 0)
    msg = f.get("message", "")[:80]
    pattern = f.get("pattern", "")
    loc = f"{file}:{line}" if line else file
    print(f"  {idx:3}. [{sev:8}] {cat:10} {loc:30} {pattern or msg}")


def run_audit(auditor: AutoAuditor) -> dict:
    """Run full audit and display results."""
    print_header("JARVIS AUTO-AUDIT")
    print("  Scanning...", flush=True)

    report = auditor.run_full_audit()
    d = report.to_dict()

    print(f"\n  Score:      {d['summary']['score']}/100")
    print(f"  Modules:    {d['total_modules']}")
    print(f"  Test files: {d['total_test_files']}")
    print(f"  Lines:      {d['total_lines']:,}")
    print(f"  Coverage:   {d['test_coverage_ratio']}%")
    print(f"  Duration:   {d['duration_ms']}ms")
    print(f"\n  Findings:   {d['total_findings']}")
    print(f"    Critical: {d['critical_count']}")
    print(f"    Major:    {d['major_count']}")
    print(f"    By category: {d['findings_by_category']}")

    # Show critical + major findings
    important = [f for f in report.findings if f.severity in ("critical", "major")]
    if important:
        print(f"\n  Top findings ({len(important)}):")
        for i, f in enumerate(important[:20], 1):
            print_finding({
                "severity": f.severity, "category": f.category,
                "file": f.file, "line": f.line,
                "message": f.message, "pattern": f.pattern,
            }, i)

    # Show untested modules
    untested = auditor.get_untested_modules()
    if untested:
        print(f"\n  Untested modules ({len(untested)}):")
        for u in untested[:10]:
            print(f"    - {u['name']} ({u['lines']}L)")

    # Save report
    report_path = ROOT / "data" / "audit_reports"
    report_path.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    filepath = report_path / f"audit_{ts}.json"
    filepath.write_text(json.dumps(d, indent=2, default=str), encoding="utf-8")
    print(f"\n  Report saved: {filepath}")

    return d


def run_tests(auditor: AutoAuditor) -> dict:
    """Run pytest and display results."""
    print_header("PYTEST")
    print("  Running tests...", flush=True)
    result = auditor.run_tests(timeout=180)
    print(f"  Passed:  {result['passed']}")
    print(f"  Failed:  {result['failed']}")
    print(f"  Skipped: {result['skipped']}")
    print(f"  Success: {'YES' if result['success'] else 'NO'}")
    return result


def compare_reports() -> None:
    """Compare last 2 audit reports."""
    report_path = ROOT / "data" / "audit_reports"
    if not report_path.exists():
        print("  No audit reports found.")
        return
    reports = sorted(report_path.glob("audit_*.json"))
    if len(reports) < 2:
        print("  Need at least 2 reports to compare.")
        return

    r1 = json.loads(reports[-2].read_text())
    r2 = json.loads(reports[-1].read_text())

    print_header("BEFORE / AFTER COMPARISON")
    print(f"  Before: {reports[-2].name}")
    print(f"  After:  {reports[-1].name}")
    print()

    metrics = [
        ("Score", r1["summary"].get("score", 0), r2["summary"].get("score", 0)),
        ("Critical", r1["critical_count"], r2["critical_count"]),
        ("Major", r1["major_count"], r2["major_count"]),
        ("Findings", r1["total_findings"], r2["total_findings"]),
        ("Coverage %", r1["test_coverage_ratio"], r2["test_coverage_ratio"]),
        ("Modules", r1["total_modules"], r2["total_modules"]),
        ("Test files", r1["total_test_files"], r2["total_test_files"]),
    ]

    print(f"  {'Metric':<15} {'Before':>10} {'After':>10} {'Delta':>10}")
    print(f"  {'-'*50}")
    for name, before, after in metrics:
        delta = after - before
        arrow = "+" if delta > 0 else "" if delta == 0 else ""
        print(f"  {name:<15} {before:>10} {after:>10} {arrow}{delta:>9}")

    improved = r2["summary"].get("score", 0) > r1["summary"].get("score", 0)
    print(f"\n  Verdict: {'IMPROVED' if improved else 'REGRESSION or UNCHANGED'}")


def show_last_report() -> None:
    """Show last audit report."""
    report_path = ROOT / "data" / "audit_reports"
    if not report_path.exists():
        print("  No audit reports found.")
        return
    reports = sorted(report_path.glob("audit_*.json"))
    if not reports:
        print("  No audit reports found.")
        return
    data = json.loads(reports[-1].read_text())
    print_header(f"LAST REPORT: {reports[-1].name}")
    print(json.dumps(data["summary"], indent=2))


def main():
    parser = argparse.ArgumentParser(description="JARVIS Auto-Improve Pipeline")
    parser.add_argument("--audit-only", action="store_true", help="Run audit only")
    parser.add_argument("--test-only", action="store_true", help="Run tests only")
    parser.add_argument("--report", action="store_true", help="Show last report")
    parser.add_argument("--compare", action="store_true", help="Compare last 2 audits")
    args = parser.parse_args()

    auditor = AutoAuditor()

    if args.report:
        show_last_report()
        return

    if args.compare:
        compare_reports()
        return

    if args.test_only:
        run_tests(auditor)
        return

    # Full cycle: audit + tests
    audit_result = run_audit(auditor)
    if not args.audit_only:
        test_result = run_tests(auditor)

    print_header("SUMMARY")
    print(f"  Audit score: {audit_result['summary']['score']}/100")
    if not args.audit_only:
        print(f"  Tests: {test_result['passed']} passed, {test_result['failed']} failed")
    print(f"  Coverage: {audit_result['test_coverage_ratio']}%")
    print(f"\n  Run --compare after improvements to see delta.")


if __name__ == "__main__":
    main()
