#!/usr/bin/env python3
"""COWORK MCP Bridge — Expose cowork scripts as MCP tool handlers.

Integrates with JARVIS mcp_server.py to make all 332+ cowork scripts
accessible via MCP tool calls, routed through pattern agents.

Usage:
    # Import in mcp_server.py:
    from cowork.cowork_mcp_bridge import CoworkBridge
    bridge = CoworkBridge()
    result = bridge.handle("cowork_dispatch", {"query": "thermal monitoring"})
    result = bridge.handle("cowork_execute", {"script": "win_thermal_monitor"})
    result = bridge.handle("cowork_list", {"pattern": "PAT_CW_WIN_MONITORING"})
"""

import sqlite3
import subprocess
import sys
import os
import json
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent
DEV_PATH = BASE / "dev"
DB_PATH = BASE.parent / "etoile.db"
PYTHON = sys.executable


class CoworkBridge:
    """MCP bridge for COWORK scripts."""

    def __init__(self, db_path=None):
        self.db_path = str(db_path or DB_PATH)

    def handle(self, tool_name: str, params: dict) -> dict:
        """Route MCP tool calls to appropriate handler."""
        handlers = {
            "cowork_dispatch": self._dispatch,
            "cowork_execute": self._execute,
            "cowork_list": self._list,
            "cowork_status": self._status,
            "cowork_test": self._test,
            "cowork_gaps": self._gaps,
            "cowork_anticipate": self._anticipate,
        }
        handler = handlers.get(tool_name)
        if not handler:
            return {"error": f"Unknown tool: {tool_name}", "available": list(handlers.keys())}
        try:
            return handler(params)
        except Exception as e:
            return {"error": str(e), "tool": tool_name}

    def _dispatch(self, params: dict) -> dict:
        """Find best scripts for a query."""
        import re
        query = params.get("query", "")
        if not query:
            return {"error": "query parameter required"}

        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        patterns = db.execute("""
            SELECT pattern_id, agent_id, keywords, description, strategy, priority
            FROM agent_patterns WHERE pattern_id LIKE 'PAT_CW_%'
        """).fetchall()

        query_words = set(re.findall(r'\w+', query.lower()))
        scores = []
        for pat in patterns:
            keywords = set((pat["keywords"] or "").split(","))
            desc_words = set(re.findall(r'\w+', (pat["description"] or "").lower()))
            score = len(query_words & keywords) + len(query_words & desc_words) * 0.5
            if score > 0:
                scripts = db.execute("""
                    SELECT script_name FROM cowork_script_mapping
                    WHERE pattern_id = ? AND status = 'active'
                """, (pat["pattern_id"],)).fetchall()
                scores.append({
                    "pattern_id": pat["pattern_id"],
                    "agent_id": pat["agent_id"],
                    "description": pat["description"],
                    "score": round(score, 2),
                    "scripts": [r["script_name"] for r in scripts]
                })

        scores.sort(key=lambda x: -x["score"])
        db.close()
        return {"query": query, "matches": scores[:5]}

    def _execute(self, params: dict) -> dict:
        """Execute a cowork script."""
        script = params.get("script", "")
        args = params.get("args", ["--once"])
        timeout = params.get("timeout", 60)

        script_path = DEV_PATH / f"{script}.py"
        if not script_path.exists():
            return {"error": f"Script not found: {script}"}

        try:
            result = subprocess.run(
                [PYTHON, str(script_path)] + args,
                capture_output=True, text=True, timeout=timeout, cwd=str(DEV_PATH)
            )
            return {
                "script": script,
                "success": result.returncode == 0,
                "stdout": result.stdout[-3000:] if result.stdout else "",
                "stderr": result.stderr[-500:] if result.stderr else "",
                "returncode": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"script": script, "error": "timeout", "success": False}

    def _list(self, params: dict) -> dict:
        """List scripts, optionally filtered by pattern."""
        pattern = params.get("pattern", "")
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row

        if pattern:
            rows = db.execute("""
                SELECT script_name, pattern_id FROM cowork_script_mapping
                WHERE pattern_id = ? AND status = 'active'
            """, (pattern,)).fetchall()
        else:
            rows = db.execute("""
                SELECT script_name, pattern_id FROM cowork_script_mapping
                WHERE status = 'active' ORDER BY pattern_id, script_name
            """).fetchall()

        db.close()
        return {"scripts": [dict(r) for r in rows], "count": len(rows)}

    def _status(self, params: dict) -> dict:
        """Get cowork system status."""
        db = sqlite3.connect(self.db_path)
        total_patterns = db.execute(
            "SELECT COUNT(*) FROM agent_patterns WHERE pattern_id LIKE 'PAT_CW_%'"
        ).fetchone()[0]
        total_scripts = db.execute(
            "SELECT COUNT(*) FROM cowork_script_mapping WHERE status = 'active'"
        ).fetchone()[0]
        total_dispatches = db.execute(
            "SELECT COUNT(*) FROM agent_dispatch_log"
        ).fetchone()[0]

        # Script file check
        script_files = len(list(DEV_PATH.glob("*.py")))
        db.close()

        return {
            "cowork_patterns": total_patterns,
            "mapped_scripts": total_scripts,
            "script_files": script_files,
            "total_dispatches": total_dispatches,
            "status": "operational"
        }

    def _test(self, params: dict) -> dict:
        """Test a script (syntax + --help)."""
        script = params.get("script", "")
        script_path = DEV_PATH / f"{script}.py"
        if not script_path.exists():
            return {"error": f"Script not found: {script}"}

        # Syntax check
        try:
            with open(script_path, 'r', encoding='utf-8', errors='ignore') as f:
                compile(f.read(), str(script_path), 'exec')
        except SyntaxError as e:
            return {"script": script, "syntax": "FAIL", "error": str(e)}

        # --help test
        try:
            r = subprocess.run(
                [PYTHON, str(script_path), "--help"],
                capture_output=True, text=True, timeout=10, cwd=str(DEV_PATH)
            )
            return {
                "script": script,
                "syntax": "OK",
                "help": "OK" if r.returncode == 0 else "FAIL",
                "help_output": r.stdout[:500] if r.stdout else ""
            }
        except Exception as e:
            return {"script": script, "syntax": "OK", "help": "ERROR", "error": str(e)}

    def _gaps(self, params: dict) -> dict:
        """Quick gap analysis."""
        all_scripts = {f.stem for f in DEV_PATH.glob("*.py")}
        db = sqlite3.connect(self.db_path)
        mapped = {r[0] for r in db.execute("SELECT script_name FROM cowork_script_mapping").fetchall()}
        unmapped = sorted(all_scripts - mapped)

        # Small patterns
        small = db.execute("""
            SELECT pattern_id, COUNT(*) as cnt FROM cowork_script_mapping
            GROUP BY pattern_id ORDER BY cnt ASC LIMIT 5
        """).fetchall()
        db.close()

        return {
            "total_scripts": len(all_scripts),
            "mapped": len(mapped),
            "unmapped": unmapped,
            "smallest_patterns": {r[0]: r[1] for r in small}
        }

    def _anticipate(self, params: dict) -> dict:
        """Quick anticipation from dispatch logs."""
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row

        hot = db.execute("""
            SELECT classified_type, COUNT(*) as cnt
            FROM agent_dispatch_log
            GROUP BY classified_type ORDER BY cnt DESC LIMIT 5
        """).fetchall()

        failing = db.execute("""
            SELECT classified_type, COUNT(*) as fails
            FROM agent_dispatch_log WHERE success = 0
            GROUP BY classified_type ORDER BY fails DESC LIMIT 3
        """).fetchall()
        db.close()

        return {
            "hot_patterns": [dict(r) for r in hot],
            "failing_patterns": [dict(r) for r in failing]
        }


# Tool definitions for MCP registration
COWORK_TOOLS = [
    {
        "name": "cowork_dispatch",
        "description": "Find COWORK scripts matching a query",
        "parameters": {"query": "str (required) — natural language query"}
    },
    {
        "name": "cowork_execute",
        "description": "Execute a COWORK script by name",
        "parameters": {"script": "str (required)", "args": "list (optional)", "timeout": "int (optional, default 60)"}
    },
    {
        "name": "cowork_list",
        "description": "List COWORK scripts, optionally filtered by pattern",
        "parameters": {"pattern": "str (optional) — pattern_id filter"}
    },
    {
        "name": "cowork_status",
        "description": "Get COWORK system status",
        "parameters": {}
    },
    {
        "name": "cowork_test",
        "description": "Test a COWORK script (syntax + --help)",
        "parameters": {"script": "str (required)"}
    },
    {
        "name": "cowork_gaps",
        "description": "Identify coverage gaps in COWORK",
        "parameters": {}
    },
    {
        "name": "cowork_anticipate",
        "description": "Predict next needs from dispatch patterns",
        "parameters": {}
    },
]


if __name__ == "__main__":
    bridge = CoworkBridge()
    import sys
    if len(sys.argv) > 1:
        tool = sys.argv[1]
        params = {}
        if len(sys.argv) > 2:
            params = {"query": " ".join(sys.argv[2:])} if tool == "cowork_dispatch" else {"script": sys.argv[2]}
        result = bridge.handle(tool, params)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        result = bridge.handle("cowork_status", {})
        print(json.dumps(result, indent=2, ensure_ascii=False))
