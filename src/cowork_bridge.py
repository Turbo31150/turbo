"""JARVIS Cowork Bridge — Index, execute and orchestrate 331 cowork scripts.

Connects jarvis-cowork (OpenClaw workspace) with the JARVIS turbo pipeline:
  - Auto-indexes all 331 scripts by category (win_*, jarvis_*, ia_*)
  - Executes scripts via subprocess with timeout
  - Maps script capabilities to pattern agents
  - Provides search and discovery
  - Tracks execution history

Usage:
    from src.cowork_bridge import CoworkBridge, get_bridge
    bridge = get_bridge()
    scripts = bridge.list_scripts(category="ia")
    result = bridge.execute("ia_ensemble_voter", args=["--once"])
    search = bridge.search("thermal monitor")
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


__all__ = [
    "CoworkBridge",
    "CoworkScript",
    "ExecutionResult",
    "get_bridge",
]

logger = logging.getLogger("jarvis.cowork_bridge")

DB_PATH = str(Path(__file__).resolve().parent.parent / "data" / "etoile.db")

# Cowork script locations (in order of preference)
COWORK_PATHS = [
    Path("C:/Users/franc/.openclaw/workspace/dev"),
    Path("/home/turbo/jarvis-m1-ops/cowork/dev"),
]


@dataclass
class CoworkScript:
    """Metadata for a cowork script."""
    name: str           # Filename without .py
    path: str           # Full path
    category: str       # win, jarvis, ia, or general
    description: str    # First line of docstring
    size_bytes: int
    has_once: bool      # Supports --once flag
    has_help: bool      # Supports --help flag
    keywords: list[str] = field(default_factory=list)


@dataclass
class ExecutionResult:
    """Result of executing a cowork script."""
    script: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    success: bool
    args: list[str] = field(default_factory=list)


class CoworkBridge:
    """Bridge between cowork scripts and JARVIS pipeline."""

    # Category-to-pattern mapping
    CATEGORY_PATTERN_MAP = {
        "win": "system",
        "jarvis": "automation",
        "ia": "reasoning",
        "cluster": "system",
        "trading": "trading",
        "telegram": "automation",
        "voice": "voice",
        "browser": "web",
        "email": "email",
        "general": "automation",
    }

    def __init__(self):
        self._scripts: dict[str, CoworkScript] = {}
        self._execution_history: list[dict] = []
        self._cowork_path: Optional[Path] = None
        self._ensure_table()
        self._find_cowork_path()
        self._index_scripts()

    def _ensure_table(self):
        try:
            db = sqlite3.connect(DB_PATH)
            db.execute("""
                CREATE TABLE IF NOT EXISTS cowork_execution_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    script TEXT, args TEXT, exit_code INTEGER,
                    duration_ms REAL, success INTEGER,
                    stdout_preview TEXT, stderr_preview TEXT,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            db.commit()
            db.close()
        except Exception:
            pass

    def _find_cowork_path(self):
        """Find the cowork scripts directory."""
        for p in COWORK_PATHS:
            if p.exists() and any(p.glob("*.py")):
                self._cowork_path = p
                return
        logger.warning("No cowork path found")

    def _index_scripts(self):
        """Index all cowork scripts."""
        if not self._cowork_path:
            return

        for py_file in sorted(self._cowork_path.glob("*.py")):
            name = py_file.stem
            if name.startswith("__"):
                continue

            # Determine category
            if name.startswith("win_"):
                category = "win"
            elif name.startswith("jarvis_"):
                category = "jarvis"
            elif name.startswith("ia_"):
                category = "ia"
            elif name.startswith(("cluster_", "node_", "model_")):
                category = "cluster"
            elif name.startswith(("trading_", "signal_", "portfolio_", "risk_")):
                category = "trading"
            elif name.startswith("telegram_"):
                category = "telegram"
            elif name.startswith(("voice_", "tts_")):
                category = "voice"
            elif name.startswith("browser_"):
                category = "browser"
            elif name.startswith(("email_", "report_")):
                category = "email"
            else:
                category = "general"

            # Extract description from docstring
            description = ""
            has_once = False
            has_help = False
            try:
                with open(py_file, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read(2000)  # First 2KB
                    # Extract first docstring line
                    match = re.search(r'"""(.+?)[\n"]', content)
                    if match:
                        description = match.group(1).strip()
                    has_once = "--once" in content
                    has_help = "argparse" in content or "--help" in content
            except Exception:
                pass

            # Keywords from name
            keywords = [w for w in name.split("_") if len(w) > 2]

            self._scripts[name] = CoworkScript(
                name=name,
                path=str(py_file),
                category=category,
                description=description,
                size_bytes=py_file.stat().st_size,
                has_once=has_once,
                has_help=has_help,
                keywords=keywords,
            )

    def list_scripts(self, category: Optional[str] = None) -> list[dict]:
        """List scripts, optionally filtered by category."""
        scripts = self._scripts.values()
        if category:
            scripts = [s for s in scripts if s.category == category]

        return [
            {
                "name": s.name,
                "category": s.category,
                "description": s.description,
                "has_once": s.has_once,
                "keywords": s.keywords,
            }
            for s in sorted(scripts, key=lambda s: s.name)
        ]

    def search(self, query: str, limit: int = 20) -> list[dict]:
        """Search scripts by name, description, or keywords."""
        query_lower = query.lower()
        query_words = set(query_lower.split())

        scored = []
        for s in self._scripts.values():
            score = 0
            name_lower = s.name.lower()
            desc_lower = s.description.lower()

            # Exact name match
            if query_lower in name_lower:
                score += 10
            # Word matches in name
            for w in query_words:
                if w in name_lower:
                    score += 3
            # Word matches in description
            for w in query_words:
                if w in desc_lower:
                    score += 2
            # Keyword matches
            for w in query_words:
                if w in s.keywords:
                    score += 4

            if score > 0:
                scored.append((score, s))

        scored.sort(key=lambda x: -x[0])
        return [
            {
                "name": s.name, "category": s.category,
                "description": s.description, "score": score,
                "has_once": s.has_once,
            }
            for score, s in scored[:limit]
        ]

    def execute(self, script_name: str, args: Optional[list[str]] = None,
                timeout_s: float = 60.0) -> ExecutionResult:
        """Execute a cowork script."""
        script = self._scripts.get(script_name)
        if not script:
            return ExecutionResult(
                script=script_name, exit_code=-1,
                stdout="", stderr=f"Script not found: {script_name}",
                duration_ms=0, success=False,
            )

        cmd_args = args or ["--once"]
        cmd = ["python", script.path] + cmd_args

        t0 = time.time()
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=timeout_s, cwd=str(self._cowork_path),
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            duration = (time.time() - t0) * 1000

            result = ExecutionResult(
                script=script_name,
                exit_code=proc.returncode,
                stdout=proc.stdout[:5000],
                stderr=proc.stderr[:2000],
                duration_ms=duration,
                success=proc.returncode == 0,
                args=cmd_args,
            )
        except subprocess.TimeoutExpired:
            duration = (time.time() - t0) * 1000
            result = ExecutionResult(
                script=script_name, exit_code=-2,
                stdout="", stderr=f"Timeout after {timeout_s}s",
                duration_ms=duration, success=False, args=cmd_args,
            )
        except Exception as e:
            result = ExecutionResult(
                script=script_name, exit_code=-3,
                stdout="", stderr=str(e),
                duration_ms=0, success=False, args=cmd_args,
            )

        # Log
        self._log_execution(result)
        self._execution_history.append({
            "script": result.script, "success": result.success,
            "duration_ms": result.duration_ms,
        })
        if len(self._execution_history) > 500:
            self._execution_history = self._execution_history[-500:]

        return result

    def execute_by_pattern(self, pattern: str, limit: int = 3) -> list[ExecutionResult]:
        """Execute relevant scripts for a pattern type."""
        # Find scripts matching the pattern
        matching_category = None
        for cat, pat in self.CATEGORY_PATTERN_MAP.items():
            if pat == pattern:
                matching_category = cat
                break

        if not matching_category:
            return []

        scripts = [s for s in self._scripts.values()
                    if s.category == matching_category and s.has_once]
        scripts = scripts[:limit]

        results = []
        for s in scripts:
            results.append(self.execute(s.name, ["--once"], timeout_s=30))

        return results

    def get_stats(self) -> dict:
        """Cowork bridge statistics."""
        categories = {}
        for s in self._scripts.values():
            categories[s.category] = categories.get(s.category, 0) + 1

        return {
            "total_scripts": len(self._scripts),
            "cowork_path": str(self._cowork_path) if self._cowork_path else None,
            "categories": categories,
            "with_once_flag": sum(1 for s in self._scripts.values() if s.has_once),
            "with_help": sum(1 for s in self._scripts.values() if s.has_help),
            "executions": len(self._execution_history),
            "recent_success_rate": (
                sum(1 for e in self._execution_history[-50:] if e["success"])
                / max(1, min(50, len(self._execution_history)))
            ),
        }

    def get_execution_history(self, script: Optional[str] = None,
                               limit: int = 50) -> list[dict]:
        """Get execution history."""
        try:
            db = sqlite3.connect(DB_PATH)
            db.row_factory = sqlite3.Row
            if script:
                rows = db.execute("""
                    SELECT * FROM cowork_execution_log
                    WHERE script = ? ORDER BY id DESC LIMIT ?
                """, (script, limit)).fetchall()
            else:
                rows = db.execute("""
                    SELECT * FROM cowork_execution_log ORDER BY id DESC LIMIT ?
                """, (limit,)).fetchall()
            db.close()
            return [dict(r) for r in rows]
        except Exception:
            return []

    def _log_execution(self, result: ExecutionResult):
        try:
            db = sqlite3.connect(DB_PATH)
            db.execute("""
                INSERT INTO cowork_execution_log
                (script, args, exit_code, duration_ms, success,
                 stdout_preview, stderr_preview)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                result.script, json.dumps(result.args),
                result.exit_code, result.duration_ms,
                int(result.success),
                result.stdout[:500], result.stderr[:500],
            ))
            db.commit()
            db.close()
        except Exception:
            pass


# Singleton
_bridge: Optional[CoworkBridge] = None

def get_bridge() -> CoworkBridge:
    global _bridge
    if _bridge is None:
        _bridge = CoworkBridge()
    return _bridge
