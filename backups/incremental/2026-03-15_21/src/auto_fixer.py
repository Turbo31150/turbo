"""Auto Fixer — Automated code improvement engine.

Analyzes audit findings and applies safe, automated fixes:
- Add missing __all__ exports
- Flag long functions for splitting
- Add type hints stubs
- Track all changes with before/after snapshots

Designed for JARVIS total automation pipeline.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.auto_auditor import AutoAuditor, AuditReport
from src.code_improvement_tracker import CodeImprovementTracker

logger = logging.getLogger("jarvis.auto_fixer")


@dataclass
class FixResult:
    """Result of an auto-fix attempt."""
    file: str
    fix_type: str
    applied: bool
    message: str = ""
    lines_changed: int = 0


class AutoFixer:
    """Automated code improvement engine."""

    def __init__(self, project_root: Path | None = None):
        self._root = project_root or Path("/home/turbo/jarvis-m1-ops")
        self._auditor = AutoAuditor(self._root)
        self._tracker = CodeImprovementTracker()
        self._fixes: list[FixResult] = []

    def run_fix_cycle(self, dry_run: bool = False) -> dict[str, Any]:
        """Full fix cycle: audit → snapshot → fix → re-audit → compare."""
        t0 = time.monotonic()

        # 1. Before audit
        before = self._auditor.run_full_audit()
        before_score = before.summary.get("score", 0)

        # 2. Snapshot files we'll modify
        targets = self._identify_targets(before)

        # 3. Apply fixes
        for target in targets:
            self._tracker.snapshot_before(target["file"])

        if dry_run:
            # In dry-run, record what would be done without applying
            for target in targets:
                for fix_type in target["fixes"]:
                    self._fixes.append(FixResult(
                        target["file"], fix_type, False,
                        f"[DRY RUN] Would apply {fix_type}",
                    ))
        else:
            self._apply_fixes(targets, before)

        # 4. After audit
        after = self._auditor.run_full_audit()
        after_score = after.summary.get("score", 0)

        # 5. Snapshot after
        for target in targets:
            self._tracker.snapshot_after(target["file"])

        # 6. Compare
        comparison = self._auditor.compare_reports(before, after)
        summary = self._tracker.get_improvement_summary()

        duration = int((time.monotonic() - t0) * 1000)

        return {
            "duration_ms": duration,
            "before_score": before_score,
            "after_score": after_score,
            "score_delta": after_score - before_score,
            "fixes_attempted": len(self._fixes),
            "fixes_applied": sum(1 for f in self._fixes if f.applied),
            "fixes": [{"file": f.file, "type": f.fix_type,
                       "applied": f.applied, "message": f.message}
                      for f in self._fixes],
            "comparison": comparison,
            "improvement_summary": summary,
            "dry_run": dry_run,
        }

    def _identify_targets(self, report: AuditReport) -> list[dict]:
        """Identify files that can be improved."""
        targets = []
        seen = set()

        # Scan ALL src/ modules, not just those with findings
        src_dir = self._root / "src"
        if src_dir.exists():
            for f in sorted(src_dir.glob("*.py")):
                if f.name.startswith("__"):
                    continue
                filepath = str(f)
                if filepath in seen:
                    continue
                fixes = self._get_applicable_fixes(filepath, report)
                if fixes:
                    seen.add(filepath)
                    targets.append({"file": filepath, "fixes": fixes})

        return targets

    def _get_applicable_fixes(self, filepath: str, report: AuditReport) -> list[str]:
        """Determine which fixes can be applied to a file."""
        fixes = []
        p = Path(filepath)
        if not p.exists():
            return fixes

        try:
            content = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return fixes

        # Fix 1: Missing module docstring
        if not content.strip().startswith('"""') and not content.strip().startswith("'''"):
            if not content.strip().startswith("#!"):
                fixes.append("add_docstring")

        # Fix 2: Missing __all__ for large public modules
        lines = content.count("\n") + 1
        if lines > 100 and "__all__" not in content:
            public_funcs = re.findall(r'^(?:def|class)\s+([a-zA-Z]\w*)', content, re.MULTILINE)
            if len(public_funcs) >= 3:
                fixes.append("add_all_export")

        # Fix 3: Long functions (>80 lines) — flag only
        func_lengths = self._measure_function_lengths(content)
        long_funcs = [name for name, length in func_lengths.items() if length > 80]
        if long_funcs:
            fixes.append("flag_long_functions")

        return fixes

    def _measure_function_lengths(self, content: str) -> dict[str, int]:
        """Measure function lengths in a file."""
        lines = content.splitlines()
        func_lengths: dict[str, int] = {}
        current_func = None
        func_start = 0
        func_indent = 0

        for i, line in enumerate(lines):
            match = re.match(r'^(\s*)(def|class)\s+(\w+)', line)
            if match:
                # Close previous function
                if current_func:
                    func_lengths[current_func] = i - func_start

                indent = len(match.group(1))
                current_func = match.group(3)
                func_start = i
                func_indent = indent

        # Close last function
        if current_func:
            func_lengths[current_func] = len(lines) - func_start

        return func_lengths

    def _apply_fixes(self, targets: list[dict], report: AuditReport) -> None:
        """Apply safe fixes to target files."""
        for target in targets:
            filepath = target["file"]
            for fix_type in target["fixes"]:
                try:
                    if fix_type == "add_docstring":
                        result = self._fix_add_docstring(filepath)
                    elif fix_type == "add_all_export":
                        result = self._fix_add_all_export(filepath)
                    elif fix_type == "flag_long_functions":
                        result = self._fix_flag_long_functions(filepath)
                    else:
                        result = FixResult(filepath, fix_type, False, "Unknown fix type")
                    self._fixes.append(result)
                except Exception as e:
                    self._fixes.append(FixResult(filepath, fix_type, False, str(e)))

    def _fix_add_docstring(self, filepath: str) -> FixResult:
        """Add missing module docstring."""
        p = Path(filepath)
        content = p.read_text(encoding="utf-8", errors="replace")

        # Don't add if already has one
        stripped = content.lstrip()
        if stripped.startswith('"""') or stripped.startswith("'''") or stripped.startswith("#!"):
            return FixResult(filepath, "add_docstring", False, "Already has docstring")

        module_name = p.stem.replace("_", " ").title()
        docstring = f'"""{module_name} module."""\n\n'

        # Insert after encoding declaration or shebang if present
        lines = content.splitlines(True)
        insert_pos = 0
        for i, line in enumerate(lines):
            if line.startswith("#") and i < 3:
                insert_pos = i + 1
            elif line.strip().startswith("from __future__"):
                insert_pos = i
                break
            else:
                break

        lines.insert(insert_pos, docstring)
        p.write_text("".join(lines), encoding="utf-8")

        return FixResult(filepath, "add_docstring", True,
                         f"Added module docstring", lines_changed=1)

    def _fix_add_all_export(self, filepath: str) -> FixResult:
        """Add __all__ export list."""
        p = Path(filepath)
        content = p.read_text(encoding="utf-8", errors="replace")

        if "__all__" in content:
            return FixResult(filepath, "add_all_export", False, "Already has __all__")

        # Find public symbols
        public = re.findall(r'^(?:def|class)\s+([A-Z]\w*|[a-z]\w*)', content, re.MULTILINE)
        public = [name for name in public if not name.startswith("_")]

        if not public:
            return FixResult(filepath, "add_all_export", False, "No public symbols")

        # Insert after imports (skip past docstrings and import block)
        lines = content.splitlines(True)
        insert_pos = 0
        in_docstring = False
        docstring_char = None
        for i, line in enumerate(lines):
            stripped = line.strip()
            # Track multiline docstrings
            if not in_docstring:
                for dc in ('"""', "'''"):
                    if stripped.startswith(dc):
                        if stripped.count(dc) >= 2:
                            # Single-line docstring like """..."""
                            insert_pos = i + 1
                        else:
                            in_docstring = True
                            docstring_char = dc
                            insert_pos = i + 1
                        break
                else:
                    if stripped.startswith(("import ", "from ")) or stripped == "" or stripped.startswith("#"):
                        insert_pos = i + 1
                    elif stripped and not stripped.startswith(("import ", "from ", "#")):
                        break
            else:
                # Inside multiline docstring — keep going
                insert_pos = i + 1
                if docstring_char and docstring_char in stripped:
                    in_docstring = False
                    docstring_char = None

        all_line = "\n__all__ = [\n"
        for name in sorted(set(public)):
            all_line += f'    "{name}",\n'
        all_line += "]\n\n"

        lines.insert(insert_pos, all_line)
        p.write_text("".join(lines), encoding="utf-8")

        return FixResult(filepath, "add_all_export", True,
                         f"Added __all__ with {len(public)} exports",
                         lines_changed=len(public) + 3)

    def _fix_flag_long_functions(self, filepath: str) -> FixResult:
        """Flag long functions — report only, no modification."""
        p = Path(filepath)
        content = p.read_text(encoding="utf-8", errors="replace")
        func_lengths = self._measure_function_lengths(content)
        long = {n: l for n, l in func_lengths.items() if l > 80}

        if not long:
            return FixResult(filepath, "flag_long_functions", False, "No long functions")

        names = ", ".join(f"{n}({l}L)" for n, l in sorted(long.items(), key=lambda x: -x[1]))
        return FixResult(filepath, "flag_long_functions", True,
                         f"Flagged: {names}", lines_changed=0)

    def get_fixes(self) -> list[dict]:
        """Get all fix results."""
        return [{"file": f.file, "type": f.fix_type,
                 "applied": f.applied, "message": f.message,
                 "lines_changed": f.lines_changed}
                for f in self._fixes]

    def get_fix_stats(self) -> dict:
        """Get fix statistics."""
        return {
            "total": len(self._fixes),
            "applied": sum(1 for f in self._fixes if f.applied),
            "skipped": sum(1 for f in self._fixes if not f.applied),
            "lines_changed": sum(f.lines_changed for f in self._fixes),
            "by_type": self._count_by_type(),
        }

    def _count_by_type(self) -> dict[str, int]:
        """Count fixes by type."""
        counts: dict[str, int] = {}
        for f in self._fixes:
            key = f"{f.fix_type}_{'applied' if f.applied else 'skipped'}"
            counts[key] = counts.get(key, 0) + 1
        return counts
