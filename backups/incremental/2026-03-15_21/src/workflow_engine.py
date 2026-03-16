"""JARVIS Workflow Engine — Multi-step workflow execution.

Define and execute workflows with sequential/parallel steps, conditions,
retries, and shared variables. SQLite persistence for definitions and runs.

Usage:
    from src.workflow_engine import workflow_engine
    wf_id = workflow_engine.create("Deploy pipeline", steps=[
        {"name": "build", "action": "bash", "params": {"cmd": "npm run build"}},
        {"name": "test", "action": "bash", "params": {"cmd": "npm test"}, "depends_on": ["build"]},
        {"name": "deploy", "action": "bash", "params": {"cmd": "deploy.sh"}, "depends_on": ["test"]},
    ])
    run_id = await workflow_engine.execute(wf_id)
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.workflow")

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "workflows.db"


class WorkflowEngine:
    """Multi-step workflow engine with conditions and retries."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or DB_PATH
        self._init_db()

    def _init_db(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS workflows (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    steps TEXT NOT NULL DEFAULT '[]',
                    variables TEXT NOT NULL DEFAULT '{}',
                    created_at REAL,
                    updated_at REAL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS workflow_runs (
                    id TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    variables TEXT NOT NULL DEFAULT '{}',
                    step_results TEXT NOT NULL DEFAULT '{}',
                    started_at REAL,
                    finished_at REAL,
                    error TEXT DEFAULT '',
                    FOREIGN KEY (workflow_id) REFERENCES workflows(id)
                )
            """)

    def create(self, name: str, steps: list[dict[str, Any]],
               variables: dict[str, Any] | None = None) -> str:
        """Create a workflow definition. Returns workflow ID."""
        wf_id = str(uuid.uuid4())[:8]
        now = time.time()
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute(
                "INSERT INTO workflows (id, name, steps, variables, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (wf_id, name, json.dumps(steps), json.dumps(variables or {}), now, now),
            )
        return wf_id

    def get(self, wf_id: str) -> dict[str, Any] | None:
        """Get a workflow definition."""
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM workflows WHERE id=?", (wf_id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            d["steps"] = json.loads(d["steps"])
            d["variables"] = json.loads(d["variables"])
            return d

    def list_workflows(self, limit: int = 20) -> list[dict[str, Any]]:
        """List workflow definitions."""
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id, name, created_at, updated_at FROM workflows ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def delete(self, wf_id: str) -> bool:
        """Delete a workflow."""
        with sqlite3.connect(str(self._db_path)) as conn:
            c = conn.execute("DELETE FROM workflows WHERE id=?", (wf_id,))
            return c.rowcount > 0

    async def execute(self, wf_id: str, variables: dict[str, Any] | None = None) -> str:
        """Execute a workflow. Returns run ID."""
        wf = self.get(wf_id)
        if not wf:
            raise ValueError(f"Workflow {wf_id} not found")

        run_id = str(uuid.uuid4())[:8]
        run_vars = {**wf.get("variables", {}), **(variables or {})}
        now = time.time()

        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute(
                "INSERT INTO workflow_runs (id, workflow_id, status, variables, started_at) "
                "VALUES (?, ?, 'running', ?, ?)",
                (run_id, wf_id, json.dumps(run_vars), now),
            )

        steps = wf["steps"]
        step_results: dict[str, Any] = {}
        error = ""

        try:
            completed: set[str] = set()
            remaining = list(steps)
            max_iterations = len(steps) * 2  # prevent infinite loops

            for _ in range(max_iterations):
                if not remaining:
                    break

                # Find runnable steps (all dependencies met)
                runnable = []
                still_waiting = []
                for step in remaining:
                    deps = step.get("depends_on", [])
                    if all(d in completed for d in deps):
                        # Check condition
                        condition = step.get("condition")
                        if condition and not self._eval_condition(condition, run_vars, step_results):
                            completed.add(step["name"])
                            step_results[step["name"]] = {"skipped": True, "reason": "condition_false"}
                            continue
                        runnable.append(step)
                    else:
                        still_waiting.append(step)

                if not runnable:
                    if still_waiting:
                        error = f"Deadlock: {[s['name'] for s in still_waiting]} waiting on unmet dependencies"
                    break

                # Execute runnable steps in parallel
                results = await asyncio.gather(
                    *[self._execute_step(step, run_vars) for step in runnable],
                    return_exceptions=True,
                )

                for step, result in zip(runnable, results):
                    name = step["name"]
                    if isinstance(result, Exception):
                        retries = step.get("retries", 0)
                        if retries > 0:
                            step["retries"] = retries - 1
                            still_waiting.append(step)
                            step_results[name] = {"error": str(result), "retries_left": retries - 1}
                        else:
                            step_results[name] = {"error": str(result)}
                            if not step.get("continue_on_error", False):
                                error = f"Step '{name}' failed: {result}"
                                remaining = []
                                break
                            completed.add(name)
                    else:
                        step_results[name] = result
                        completed.add(name)
                        # Update variables with step output
                        if isinstance(result, dict) and "output" in result:
                            run_vars[f"${name}"] = result["output"]

                remaining = still_waiting

        except Exception as e:
            error = str(e)

        # Finalize run
        status = "failed" if error else "completed"
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute(
                "UPDATE workflow_runs SET status=?, step_results=?, variables=?, finished_at=?, error=? WHERE id=?",
                (status, json.dumps(step_results, default=str), json.dumps(run_vars, default=str),
                 time.time(), error, run_id),
            )

        return run_id

    async def _execute_step(self, step: dict[str, Any], variables: dict[str, Any]) -> dict[str, Any]:
        """Execute a single workflow step."""
        action = step.get("action", "noop")
        params = step.get("params", {})
        timeout = step.get("timeout", 30)

        if action == "noop":
            return {"status": "ok", "output": "noop"}

        if action == "bash":
            import subprocess, shlex
            cmd = params.get("cmd", "echo ok")
            # Substitute variables (sanitize values to prevent injection)
            for k, v in variables.items():
                cmd = cmd.replace(k, shlex.quote(str(v)))
            r = await asyncio.wait_for(
                asyncio.to_thread(subprocess.run, cmd, shell=True, capture_output=True, text=True, timeout=timeout),
                timeout=timeout + 5,
            )
            return {"status": "ok" if r.returncode == 0 else "error",
                    "returncode": r.returncode, "output": r.stdout[:1000], "stderr": r.stderr[:500]}

        if action == "cluster_query":
            node = params.get("node", "M1")
            prompt = params.get("prompt", "")
            for k, v in variables.items():
                prompt = prompt.replace(k, str(v))
            import urllib.request
            NODES = {
                "M1": ("http://127.0.0.1:1234/v1/chat/completions", "qwen3-8b", False),
                "M2": ("http://192.168.1.26:1234/v1/chat/completions", "deepseek-r1-0528-qwen3-8b", False),
                "M3": ("http://192.168.1.113:1234/v1/chat/completions", "deepseek-r1-0528-qwen3-8b", False),
                "OL1": ("http://127.0.0.1:11434/api/chat", "qwen3:1.7b", True),
            }
            url, model, is_ollama = NODES.get(node.upper(), NODES["M1"])
            if is_ollama:
                body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False, "think": False})
            else:
                body = json.dumps({"model": model, "messages": [{"role": "user", "content": f"/nothink\n{prompt}"}], "temperature": 0.3, "max_tokens": 2048, "stream": False})
            req = urllib.request.Request(url, data=body.encode(), headers={"Content-Type": "application/json"})
            try:
                resp = await asyncio.to_thread(urllib.request.urlopen, req, timeout=timeout)
                data = json.loads(resp.read().decode())
                if is_ollama:
                    text = data.get("message", {}).get("content", "")
                else:
                    choices = data.get("choices", [])
                    text = choices[0]["message"]["content"] if choices else ""
                import re as _re
                text = _re.sub(r'<think>[\s\S]*?</think>', '', text).strip()
                return {"status": "ok", "output": text[:2000], "node": node, "model": model}
            except Exception as e:
                return {"status": "error", "output": f"cluster_query {node} failed: {e}", "node": node}

        return {"status": "ok", "output": f"Unknown action: {action}"}

    @staticmethod
    def _eval_condition(condition: str, variables: dict, step_results: dict) -> bool:
        """Evaluate a simple condition."""
        try:
            # Simple key=value check
            if "==" in condition:
                key, val = condition.split("==", 1)
                key = key.strip()
                val = val.strip().strip("'\"")
                actual = str(variables.get(key, step_results.get(key, "")))
                return actual == val
            return True
        except Exception:
            return True

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        """Get a workflow run."""
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM workflow_runs WHERE id=?", (run_id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            d["step_results"] = json.loads(d["step_results"])
            d["variables"] = json.loads(d["variables"])
            return d

    def list_runs(self, workflow_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        """List workflow runs."""
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            if workflow_id:
                rows = conn.execute(
                    "SELECT * FROM workflow_runs WHERE workflow_id=? ORDER BY started_at DESC LIMIT ?",
                    (workflow_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM workflow_runs ORDER BY started_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                d["step_results"] = json.loads(d["step_results"])
                d["variables"] = json.loads(d["variables"])
                results.append(d)
            return results

    def get_stats(self) -> dict[str, Any]:
        """Workflow engine stats."""
        with sqlite3.connect(str(self._db_path)) as conn:
            total_wf = conn.execute("SELECT COUNT(*) FROM workflows").fetchone()[0]
            total_runs = conn.execute("SELECT COUNT(*) FROM workflow_runs").fetchone()[0]
            by_status = conn.execute(
                "SELECT status, COUNT(*) FROM workflow_runs GROUP BY status"
            ).fetchall()
            return {
                "total_workflows": total_wf,
                "total_runs": total_runs,
                "runs_by_status": {s: c for s, c in by_status},
            }


# Global singleton
workflow_engine = WorkflowEngine()
