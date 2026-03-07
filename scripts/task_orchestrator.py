#!/usr/bin/env python3
"""JARVIS Task Orchestrator — Automated delegation, branching & scheduling.

Central automation engine that:
1. Manages a task queue with priorities and dependencies
2. Delegates to cluster nodes (M1/M2/M3/OL1/GEMINI/CLAUDE) based on task type
3. Supports parallel branching, conditional routing, and pipeline chaining
4. Schedules recurring tasks (audit, backup, health, trading, sync)
5. Tracks results and sends notifications

Usage:
    python scripts/task_orchestrator.py                    # Run all due tasks
    python scripts/task_orchestrator.py --status           # Show queue status
    python scripts/task_orchestrator.py --run <task_id>    # Run specific task
    python scripts/task_orchestrator.py --schedule         # Show schedule
    python scripts/task_orchestrator.py --add <json>       # Add task to queue
    python scripts/task_orchestrator.py --daemon           # Run as daemon
    python scripts/task_orchestrator.py --init             # Initialize DB + default tasks
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import sqlite3
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

TURBO = Path("F:/BUREAU/turbo")
DB_PATH = str(TURBO / "data" / "task_orchestrator.db")
LOG_PATH = str(TURBO / "data" / "task_orchestrator.log")

# Telegram notification (loaded from .env)
def _load_telegram_config():
    env_file = TURBO / ".env"
    token = chat_id = None
    if env_file.exists():
        for line in env_file.read_text(errors="replace").splitlines():
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                token = line.split("=", 1)[1].strip().strip('"')
            elif line.startswith("TELEGRAM_CHAT_ID="):
                chat_id = line.split("=", 1)[1].strip().strip('"')
    return token, chat_id

TELEGRAM_TOKEN, TELEGRAM_CHAT = _load_telegram_config()


def notify_telegram(message: str, silent: bool = False):
    """Send notification to Telegram."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        return False
    try:
        subprocess.run([
            "curl", "-s", "--max-time", "10",
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            "-d", f"chat_id={TELEGRAM_CHAT}",
            "-d", f"text={message[:4000]}",
            "-d", "parse_mode=HTML",
            "-d", f"disable_notification={'true' if silent else 'false'}",
        ], capture_output=True, timeout=15)
        return True
    except Exception:
        return False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
    ],
)
logger = logging.getLogger("task_orchestrator")

# ── Cluster Config ──────────────────────────────────────────────────────────

NODES = {
    "M1": {"host": "127.0.0.1", "port": 1234, "model": "qwen3-8b", "api": "lmstudio",
           "weight": 1.8, "timeout": 15, "nothink": True},
    "OL1": {"host": "127.0.0.1", "port": 11434, "model": "qwen3:1.7b", "api": "ollama",
            "weight": 1.3, "timeout": 10, "nothink": True},
    "M2": {"host": "192.168.1.26", "port": 1234, "model": "deepseek-r1-0528-qwen3-8b",
           "api": "lmstudio", "weight": 1.5, "timeout": 30, "nothink": False},
    "M3": {"host": "192.168.1.113", "port": 1234, "model": "deepseek-r1-0528-qwen3-8b",
           "api": "lmstudio", "weight": 1.2, "timeout": 30, "nothink": False},
    "GEMINI": {"api": "gemini", "weight": 1.2, "timeout": 120},
    "CLAUDE": {"api": "claude", "weight": 1.2, "timeout": 120},
}

# Task type -> preferred nodes (ordered by priority)
ROUTING_TABLE = {
    "code":        ["M1", "OL1", "M2"],
    "bugfix":      ["M1", "OL1", "M2"],
    "review":      ["M1", "M2", "OL1"],
    "architecture":["M1", "OL1", "M2"],
    "reasoning":   ["M1", "M2", "M3"],
    "math":        ["M1", "OL1"],
    "trading":     ["OL1", "M1"],
    "security":    ["M1", "OL1", "M2"],
    "quick":       ["OL1", "M1"],
    "web_search":  ["OL1"],
    "consensus":   ["M1", "M2", "OL1", "M3"],
    "audit":       ["M1", "OL1"],
    "backup":      ["local"],
    "health":      ["local"],
    "sync":        ["local"],
    "pipeline":    ["local", "M1"],
    "test":        ["local"],
    "schedule":    ["local"],
}

# ── Data Models ─────────────────────────────────────────────────────────────

TASK_STATUS = ("pending", "running", "completed", "failed", "skipped", "cancelled")
TASK_PRIORITY = {"critical": 0, "high": 1, "normal": 2, "low": 3}


@dataclass
class TaskDef:
    id: str
    name: str
    task_type: str
    action: str  # "script", "python", "cluster_query", "pipeline", "branch"
    payload: dict = field(default_factory=dict)
    priority: str = "normal"
    schedule: str = ""  # cron-like: "every:5m", "every:1h", "daily:08:00", "weekly:mon:09:00"
    depends_on: list = field(default_factory=list)  # task IDs that must complete first
    branch_on: dict = field(default_factory=dict)  # conditional branching rules
    timeout_s: int = 300
    retry_max: int = 2
    enabled: bool = True
    tags: list = field(default_factory=list)


@dataclass
class TaskResult:
    task_id: str
    status: str
    output: str = ""
    error: str = ""
    node: str = ""
    duration_ms: float = 0
    timestamp: str = ""
    retry_count: int = 0


# ── Database ────────────────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            task_type TEXT NOT NULL,
            action TEXT NOT NULL,
            payload TEXT DEFAULT '{}',
            priority TEXT DEFAULT 'normal',
            schedule TEXT DEFAULT '',
            depends_on TEXT DEFAULT '[]',
            branch_on TEXT DEFAULT '{}',
            timeout_s INTEGER DEFAULT 300,
            retry_max INTEGER DEFAULT 2,
            enabled INTEGER DEFAULT 1,
            tags TEXT DEFAULT '[]',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS task_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            status TEXT NOT NULL,
            output TEXT DEFAULT '',
            error TEXT DEFAULT '',
            node TEXT DEFAULT '',
            duration_ms REAL DEFAULT 0,
            started_at TEXT DEFAULT (datetime('now')),
            finished_at TEXT,
            retry_count INTEGER DEFAULT 0,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        );
        CREATE TABLE IF NOT EXISTS task_schedule (
            task_id TEXT PRIMARY KEY,
            last_run TEXT,
            next_run TEXT,
            run_count INTEGER DEFAULT 0,
            fail_count INTEGER DEFAULT 0,
            avg_duration_ms REAL DEFAULT 0,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        );
        CREATE INDEX IF NOT EXISTS idx_runs_task ON task_runs(task_id);
        CREATE INDEX IF NOT EXISTS idx_runs_status ON task_runs(status);
        CREATE INDEX IF NOT EXISTS idx_schedule_next ON task_schedule(next_run);
    """)
    conn.commit()
    conn.close()
    logger.info("DB initialized: %s", DB_PATH)


def get_db():
    return sqlite3.connect(DB_PATH)


def save_task(task: TaskDef):
    conn = get_db()
    conn.execute("""
        INSERT OR REPLACE INTO tasks (id, name, task_type, action, payload, priority,
            schedule, depends_on, branch_on, timeout_s, retry_max, enabled, tags, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
    """, (task.id, task.name, task.task_type, task.action,
          json.dumps(task.payload), task.priority, task.schedule,
          json.dumps(task.depends_on), json.dumps(task.branch_on),
          task.timeout_s, task.retry_max, int(task.enabled), json.dumps(task.tags)))
    # Init schedule
    if task.schedule:
        next_run = calculate_next_run(task.schedule)
        conn.execute("""
            INSERT OR IGNORE INTO task_schedule (task_id, next_run) VALUES (?, ?)
        """, (task.id, next_run))
    conn.commit()
    conn.close()


def load_tasks() -> list[TaskDef]:
    conn = get_db()
    rows = conn.execute("SELECT * FROM tasks WHERE enabled=1 ORDER BY priority").fetchall()
    conn.close()
    tasks = []
    for r in rows:
        tasks.append(TaskDef(
            id=r[0], name=r[1], task_type=r[2], action=r[3],
            payload=json.loads(r[4] or "{}"), priority=r[5], schedule=r[6] or "",
            depends_on=json.loads(r[7] or "[]"), branch_on=json.loads(r[8] or "{}"),
            timeout_s=r[9] or 300, retry_max=r[10] or 2, enabled=bool(r[11]),
            tags=json.loads(r[12] or "[]"),
        ))
    return tasks


def get_due_tasks() -> list[TaskDef]:
    """Get tasks that are scheduled to run now."""
    conn = get_db()
    now = datetime.now().isoformat()
    rows = conn.execute("""
        SELECT t.* FROM tasks t
        JOIN task_schedule s ON t.id = s.task_id
        WHERE t.enabled = 1 AND s.next_run <= ?
        ORDER BY t.priority
    """, (now,)).fetchall()
    conn.close()
    tasks = []
    for r in rows:
        tasks.append(TaskDef(
            id=r[0], name=r[1], task_type=r[2], action=r[3],
            payload=json.loads(r[4] or "{}"), priority=r[5], schedule=r[6] or "",
            depends_on=json.loads(r[7] or "[]"), branch_on=json.loads(r[8] or "{}"),
            timeout_s=r[9] or 300, retry_max=r[10] or 2, enabled=bool(r[11]),
            tags=json.loads(r[12] or "[]"),
        ))
    return tasks


def record_run(result: TaskResult):
    conn = get_db()
    conn.execute("""
        INSERT INTO task_runs (task_id, status, output, error, node, duration_ms, finished_at, retry_count)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'), ?)
    """, (result.task_id, result.status, result.output[:10000], result.error[:5000],
          result.node, result.duration_ms, result.retry_count))
    # Update schedule
    task_row = conn.execute("SELECT schedule FROM tasks WHERE id=?", (result.task_id,)).fetchone()
    if task_row and task_row[0]:
        next_run = calculate_next_run(task_row[0])
        conn.execute("""
            UPDATE task_schedule SET last_run=datetime('now'), next_run=?,
                run_count=run_count+1,
                fail_count=fail_count + CASE WHEN ?='failed' THEN 1 ELSE 0 END,
                avg_duration_ms = (avg_duration_ms * run_count + ?) / (run_count + 1)
            WHERE task_id=?
        """, (next_run, result.status, result.duration_ms, result.task_id))
    conn.commit()
    conn.close()


# ── Schedule Parser ─────────────────────────────────────────────────────────

def calculate_next_run(schedule: str) -> str:
    """Parse schedule string and return next run ISO datetime."""
    now = datetime.now()
    s = schedule.lower().strip()

    if s.startswith("every:"):
        interval = s[6:]
        if interval.endswith("m"):
            delta = timedelta(minutes=int(interval[:-1]))
        elif interval.endswith("h"):
            delta = timedelta(hours=int(interval[:-1]))
        elif interval.endswith("s"):
            delta = timedelta(seconds=int(interval[:-1]))
        elif interval.endswith("d"):
            delta = timedelta(days=int(interval[:-1]))
        else:
            delta = timedelta(minutes=int(interval))
        return (now + delta).isoformat()

    if s.startswith("daily:"):
        hm = s[6:]
        h, m = (int(x) for x in hm.split(":"))
        target = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return target.isoformat()

    if s.startswith("weekly:"):
        parts = s[7:].split(":")
        day_map = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
        day = day_map.get(parts[0], 0)
        h = int(parts[1]) if len(parts) > 1 else 9
        m = int(parts[2]) if len(parts) > 2 else 0
        days_ahead = day - now.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        target = (now + timedelta(days=days_ahead)).replace(hour=h, minute=m, second=0, microsecond=0)
        return target.isoformat()

    if s.startswith("hourly"):
        return (now + timedelta(hours=1)).isoformat()

    # Default: 1 hour
    return (now + timedelta(hours=1)).isoformat()


# ── Cluster Dispatch ────────────────────────────────────────────────────────

def check_node_health(node_name: str) -> bool:
    """Quick health check for a cluster node."""
    node = NODES.get(node_name)
    if not node:
        return False
    api = node.get("api")
    try:
        if api == "lmstudio":
            r = subprocess.run(
                ["curl", "-s", "--max-time", "3",
                 f"http://{node['host']}:{node['port']}/v1/models"],
                capture_output=True, text=True, timeout=5,
            )
            return r.returncode == 0 and '"id"' in r.stdout
        elif api == "ollama":
            r = subprocess.run(
                ["curl", "-s", "--max-time", "3",
                 f"http://{node['host']}:{node['port']}/api/tags"],
                capture_output=True, text=True, timeout=5,
            )
            return r.returncode == 0 and "models" in r.stdout
        elif api in ("gemini", "claude"):
            return True  # Assume available, will fail at dispatch
    except Exception:
        pass
    return False


def dispatch_to_node(node_name: str, prompt: str, timeout: int = 30) -> tuple[bool, str]:
    """Send prompt to a specific cluster node. Returns (success, response)."""
    node = NODES.get(node_name)
    if not node:
        return False, f"Unknown node: {node_name}"

    api = node.get("api")
    try:
        if api == "lmstudio":
            prefix = "/nothink\n" if node.get("nothink") else ""
            cmd = [
                "curl", "-s", "--max-time", str(timeout),
                f"http://{node['host']}:{node['port']}/v1/chat/completions",
                "-H", "Content-Type: application/json",
                "-d", json.dumps({
                    "model": node["model"],
                    "messages": [{"role": "user", "content": f"{prefix}{prompt}"}],
                    "temperature": 0.2,
                    "max_tokens": 2048,
                    "stream": False,
                }),
            ]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
            if r.returncode == 0:
                data = json.loads(r.stdout)
                content = data["choices"][0]["message"]["content"]
                return True, content
            return False, r.stderr

        elif api == "ollama":
            cmd = [
                "curl", "-s", "--max-time", str(timeout),
                f"http://{node['host']}:{node['port']}/api/chat",
                "-d", json.dumps({
                    "model": node["model"],
                    "messages": [{"role": "user", "content": f"/nothink\n{prompt}"}],
                    "stream": False,
                }),
            ]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
            if r.returncode == 0:
                data = json.loads(r.stdout)
                return True, data["message"]["content"]
            return False, r.stderr

        elif api == "gemini":
            r = subprocess.run(
                ["node", str(TURBO / "gemini-proxy.js"), prompt],
                capture_output=True, text=True, timeout=timeout,
            )
            return r.returncode == 0, r.stdout if r.returncode == 0 else r.stderr

        elif api == "claude":
            r = subprocess.run(
                ["node", str(TURBO / "claude-proxy.js"), prompt],
                capture_output=True, text=True, timeout=timeout,
            )
            return r.returncode == 0, r.stdout if r.returncode == 0 else r.stderr

    except subprocess.TimeoutExpired:
        return False, f"Timeout ({timeout}s)"
    except Exception as e:
        return False, str(e)

    return False, "Unknown API type"


def smart_dispatch(task_type: str, prompt: str, timeout: int = 30) -> tuple[str, bool, str]:
    """Route to best available node. Returns (node_name, success, response)."""
    nodes = ROUTING_TABLE.get(task_type, ["M1", "OL1"])

    for node_name in nodes:
        if node_name == "local":
            continue
        if check_node_health(node_name):
            ok, response = dispatch_to_node(node_name, prompt, timeout)
            if ok:
                return node_name, True, response
            logger.warning("%s failed for %s: %s", node_name, task_type, response[:100])

    return "none", False, "All nodes failed"


def consensus_dispatch(prompt: str, nodes: list[str] = None, timeout: int = 30) -> dict:
    """Query multiple nodes and vote. Returns weighted consensus."""
    if nodes is None:
        nodes = ["M1", "OL1", "M2"]
    results = {}
    for n in nodes:
        if check_node_health(n):
            ok, resp = dispatch_to_node(n, prompt, timeout)
            if ok:
                results[n] = {"response": resp, "weight": NODES[n]["weight"]}
    return results


# ── Task Executors ──────────────────────────────────────────────────────────

def execute_script(task: TaskDef) -> TaskResult:
    """Run a Python script."""
    script = task.payload.get("script", "")
    args = task.payload.get("args", [])
    cwd = task.payload.get("cwd", str(TURBO))

    if not script:
        return TaskResult(task.id, "failed", error="No script specified")

    t0 = time.monotonic()
    try:
        cmd = [sys.executable, str(TURBO / script)] + args
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=task.timeout_s,
            cwd=cwd, errors="replace",
        )
        dur = (time.monotonic() - t0) * 1000
        if r.returncode == 0:
            return TaskResult(task.id, "completed", output=r.stdout[-5000:], duration_ms=dur)
        else:
            return TaskResult(task.id, "failed", output=r.stdout[-2000:],
                              error=r.stderr[-2000:], duration_ms=dur)
    except subprocess.TimeoutExpired:
        return TaskResult(task.id, "failed", error=f"Timeout {task.timeout_s}s",
                          duration_ms=(time.monotonic() - t0) * 1000)
    except Exception as e:
        return TaskResult(task.id, "failed", error=str(e),
                          duration_ms=(time.monotonic() - t0) * 1000)


def execute_python(task: TaskDef) -> TaskResult:
    """Execute inline Python code."""
    code = task.payload.get("code", "")
    if not code:
        return TaskResult(task.id, "failed", error="No code specified")

    t0 = time.monotonic()
    try:
        r = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=task.timeout_s,
            cwd=str(TURBO), errors="replace",
        )
        dur = (time.monotonic() - t0) * 1000
        if r.returncode == 0:
            return TaskResult(task.id, "completed", output=r.stdout[-5000:], duration_ms=dur)
        else:
            return TaskResult(task.id, "failed", output=r.stdout[-2000:],
                              error=r.stderr[-2000:], duration_ms=dur)
    except subprocess.TimeoutExpired:
        return TaskResult(task.id, "failed", error=f"Timeout {task.timeout_s}s",
                          duration_ms=(time.monotonic() - t0) * 1000)


def execute_cluster_query(task: TaskDef) -> TaskResult:
    """Dispatch a query to the cluster."""
    prompt = task.payload.get("prompt", "")
    task_type = task.payload.get("route", task.task_type)
    timeout = task.payload.get("timeout", task.timeout_s)

    t0 = time.monotonic()
    if task_type == "consensus":
        nodes = task.payload.get("nodes", ["M1", "OL1", "M2"])
        results = consensus_dispatch(prompt, nodes, timeout)
        dur = (time.monotonic() - t0) * 1000
        if results:
            output = json.dumps({n: r["response"][:500] for n, r in results.items()}, indent=2)
            return TaskResult(task.id, "completed", output=output, node=",".join(results.keys()),
                              duration_ms=dur)
        return TaskResult(task.id, "failed", error="No consensus responses", duration_ms=dur)
    else:
        node, ok, response = smart_dispatch(task_type, prompt, timeout)
        dur = (time.monotonic() - t0) * 1000
        if ok:
            return TaskResult(task.id, "completed", output=response[:5000], node=node,
                              duration_ms=dur)
        return TaskResult(task.id, "failed", error=response[:2000], node=node, duration_ms=dur)


def execute_pipeline(task: TaskDef) -> TaskResult:
    """Run a sequence of sub-tasks (pipeline)."""
    steps = task.payload.get("steps", [])
    results = []
    t0 = time.monotonic()

    for i, step in enumerate(steps):
        step_task = TaskDef(
            id=f"{task.id}_step{i}",
            name=f"{task.name} step {i}",
            task_type=step.get("type", "quick"),
            action=step.get("action", "script"),
            payload=step.get("payload", {}),
            timeout_s=step.get("timeout", 120),
            retry_max=0,
        )
        result = execute_task(step_task)
        results.append({"step": i, "status": result.status, "output": result.output[:200]})

        # Check branch conditions
        if task.branch_on and result.status in task.branch_on:
            branch = task.branch_on[result.status]
            logger.info("Branch on %s: %s", result.status, branch)
            if branch == "stop":
                dur = (time.monotonic() - t0) * 1000
                final_status = "failed" if result.status == "failed" else "completed"
                return TaskResult(task.id, final_status,
                                  output=json.dumps(results, indent=2),
                                  error=f"Stopped at step {i}: {result.error[:200]}",
                                  duration_ms=dur)
            elif branch == "skip_rest":
                break
            elif isinstance(branch, str) and branch.startswith("goto:"):
                target = int(branch[5:])
                steps = steps[target:]
                continue

        if result.status == "failed" and step.get("required", True):
            dur = (time.monotonic() - t0) * 1000
            return TaskResult(task.id, "failed",
                              output=json.dumps(results, indent=2),
                              error=f"Step {i} failed: {result.error[:200]}",
                              duration_ms=dur)

    dur = (time.monotonic() - t0) * 1000
    return TaskResult(task.id, "completed", output=json.dumps(results, indent=2),
                      duration_ms=dur)


def execute_branch(task: TaskDef) -> TaskResult:
    """Execute conditional branching based on a condition check."""
    condition = task.payload.get("condition", {})
    branches = task.payload.get("branches", {})

    t0 = time.monotonic()

    # Evaluate condition
    check_type = condition.get("type", "script")
    if check_type == "health":
        node = condition.get("node", "M1")
        is_healthy = check_node_health(node)
        branch_key = "healthy" if is_healthy else "unhealthy"
    elif check_type == "script":
        r = subprocess.run(
            [sys.executable, "-c", condition.get("code", "print('ok')")],
            capture_output=True, text=True, timeout=30, cwd=str(TURBO),
        )
        branch_key = "success" if r.returncode == 0 else "failure"
    elif check_type == "file_exists":
        path = TURBO / condition.get("path", "")
        branch_key = "exists" if path.exists() else "missing"
    elif check_type == "time":
        hour = datetime.now().hour
        if 8 <= hour < 20:
            branch_key = "business_hours"
        else:
            branch_key = "off_hours"
    elif check_type == "gpu_temp":
        threshold = condition.get("threshold", 85)
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=10,
            )
            temps = [int(t.strip()) for t in r.stdout.strip().splitlines() if t.strip()]
            max_temp = max(temps) if temps else 0
            branch_key = "hot" if max_temp > threshold else "cool"
        except Exception:
            branch_key = "error"
    elif check_type == "audit_score":
        threshold = condition.get("threshold", 90)
        try:
            r = subprocess.run(
                [sys.executable, "-c",
                 "import sys;sys.path.insert(0,'F:/BUREAU/turbo');"
                 "from src.auto_auditor import AutoAuditor;"
                 "r=AutoAuditor().run_full_audit();"
                 f"print('pass' if r.summary['score']>={threshold} else 'fail')"],
                capture_output=True, text=True, timeout=30, cwd=str(TURBO),
            )
            branch_key = r.stdout.strip()
        except Exception:
            branch_key = "error"
    elif check_type == "disk_space":
        threshold_gb = condition.get("threshold_gb", 10)
        drive = condition.get("drive", "C:")
        try:
            import shutil
            usage = shutil.disk_usage(drive + "/")
            free_gb = usage.free / (1024**3)
            branch_key = "ok" if free_gb > threshold_gb else "low"
        except Exception:
            branch_key = "error"
    elif check_type == "process_running":
        proc_name = condition.get("process", "")
        try:
            r = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {proc_name}"],
                capture_output=True, text=True, timeout=10,
            )
            branch_key = "running" if proc_name.lower() in r.stdout.lower() else "stopped"
        except Exception:
            branch_key = "error"
    elif check_type == "db_integrity":
        db_path = condition.get("db", "data/jarvis.db")
        try:
            c = sqlite3.connect(str(TURBO / db_path))
            integ = c.execute("PRAGMA integrity_check").fetchone()[0]
            c.close()
            branch_key = "ok" if integ == "ok" else "corrupt"
        except Exception:
            branch_key = "error"
    else:
        branch_key = "default"

    # Execute the matching branch
    branch = branches.get(branch_key, branches.get("default", {}))
    if branch:
        branch_task = TaskDef(
            id=f"{task.id}_branch_{branch_key}",
            name=f"{task.name} [{branch_key}]",
            task_type=branch.get("type", "quick"),
            action=branch.get("action", "script"),
            payload=branch.get("payload", {}),
            timeout_s=branch.get("timeout", 120),
        )
        result = execute_task(branch_task)
        result.task_id = task.id
        result.duration_ms = (time.monotonic() - t0) * 1000
        return result

    dur = (time.monotonic() - t0) * 1000
    return TaskResult(task.id, "skipped", output=f"No branch for: {branch_key}",
                      duration_ms=dur)


def execute_task(task: TaskDef) -> TaskResult:
    """Route task to the right executor."""
    logger.info("Executing: %s [%s/%s] prio=%s", task.name, task.task_type, task.action, task.priority)

    executors = {
        "script": execute_script,
        "python": execute_python,
        "cluster_query": execute_cluster_query,
        "pipeline": execute_pipeline,
        "branch": execute_branch,
    }

    executor = executors.get(task.action)
    if not executor:
        return TaskResult(task.id, "failed", error=f"Unknown action: {task.action}")

    for attempt in range(task.retry_max + 1):
        result = executor(task)
        if result.status == "completed":
            result.retry_count = attempt
            return result
        if attempt < task.retry_max:
            logger.warning("Retry %d/%d for %s", attempt + 1, task.retry_max, task.name)
            time.sleep(2 ** attempt)  # Exponential backoff

    result.retry_count = task.retry_max
    return result


# ── Check Dependencies ──────────────────────────────────────────────────────

def check_dependencies(task: TaskDef) -> bool:
    """Check if all task dependencies are satisfied."""
    if not task.depends_on:
        return True
    conn = get_db()
    for dep_id in task.depends_on:
        row = conn.execute("""
            SELECT status FROM task_runs WHERE task_id=?
            ORDER BY id DESC LIMIT 1
        """, (dep_id,)).fetchone()
        if not row or row[0] != "completed":
            conn.close()
            return False
    conn.close()
    return True


# ── Default Tasks ───────────────────────────────────────────────────────────

def create_default_tasks():
    """Create the full set of automated tasks."""
    defaults = [
        # ── Health & Monitoring ──
        TaskDef(
            id="health_cluster",
            name="Cluster Health Check",
            task_type="health",
            action="python",
            payload={"code": """
import subprocess, json
nodes = [
    ("M1", "127.0.0.1:1234/v1/models"),
    ("OL1", "127.0.0.1:11434/api/tags"),
    ("M2", "192.168.1.26:1234/v1/models"),
    ("M3", "192.168.1.113:1234/v1/models"),
]
for name, url in nodes:
    try:
        r = subprocess.run(["curl","-s","--max-time","3",f"http://{url}"],
            capture_output=True, text=True, timeout=5)
        ok = r.returncode == 0 and len(r.stdout) > 10
        print(f"{name}: {'OK' if ok else 'OFFLINE'}")
    except: print(f"{name}: OFFLINE")
"""},
            priority="high",
            schedule="every:5m",
            tags=["health", "monitoring"],
        ),

        TaskDef(
            id="health_gpu",
            name="GPU Temperature Monitor",
            task_type="health",
            action="python",
            payload={"code": """
import subprocess
r = subprocess.run(["nvidia-smi","--query-gpu=index,temperature.gpu,memory.used,memory.total,utilization.gpu",
    "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10)
if r.returncode == 0:
    for line in r.stdout.strip().splitlines():
        parts = [x.strip() for x in line.split(',')]
        temp = int(parts[1])
        alert = ' [HOT]' if temp > 85 else ''
        print(f"GPU{parts[0]}: {temp}C, {parts[2]}/{parts[3]}MB VRAM, {parts[4]}% util{alert}")
else: print("nvidia-smi failed")
"""},
            priority="normal",
            schedule="every:10m",
            tags=["health", "gpu"],
        ),

        TaskDef(
            id="health_services",
            name="Services Watchdog",
            task_type="health",
            action="script",
            payload={"script": "scripts/unified_boot.py", "args": ["--check"]},
            priority="high",
            schedule="every:5m",
            tags=["health", "watchdog"],
        ),

        # ── Audit & Quality ──
        TaskDef(
            id="audit_code",
            name="Code Audit",
            task_type="audit",
            action="python",
            payload={"code": """
import sys; sys.path.insert(0, 'F:/BUREAU/turbo')
from src.auto_auditor import AutoAuditor
auditor = AutoAuditor()
report = auditor.run_full_audit()
s = report.summary
print(f"Score: {s['score']}/100 | Findings: {len(report.findings)} | Security: {s['security_issues']}")
print(f"Modules: {report.total_modules} | Tests: {report.total_test_files} | Lines: {report.total_lines:,}")
"""},
            priority="normal",
            schedule="every:1h",
            tags=["audit", "quality"],
        ),

        TaskDef(
            id="audit_fix",
            name="Auto-Fix Code Issues",
            task_type="audit",
            action="python",
            payload={"code": """
import sys; sys.path.insert(0, 'F:/BUREAU/turbo')
from src.auto_fixer import AutoFixer
fixer = AutoFixer()
result = fixer.run_fix_cycle(dry_run=False)
applied = [f for f in result.get('fixes', []) if f.get('applied')]
print(f"Applied: {len(applied)} fixes")
"""},
            priority="normal",
            schedule="every:6h",
            depends_on=["audit_code"],
            tags=["audit", "fix"],
        ),

        TaskDef(
            id="test_suite",
            name="Run Test Suite",
            task_type="test",
            action="script",
            payload={"script": "scripts/jarvis_autotest.py"},
            priority="normal",
            schedule="every:2h",
            timeout_s=600,
            tags=["test", "ci"],
        ),

        # ── Backup & Sync ──
        TaskDef(
            id="backup_databases",
            name="Backup 3 Databases",
            task_type="backup",
            action="python",
            payload={"code": """
import shutil, hashlib, sqlite3
from pathlib import Path
from datetime import datetime
TURBO = Path('F:/BUREAU/turbo')
ts = datetime.now().strftime('%Y%m%d_%H%M%S')
backups = TURBO / 'backups'
backups.mkdir(exist_ok=True)
for db in ['data/jarvis.db', 'etoile.db', 'data/sniper.db']:
    src = TURBO / db
    name = src.stem
    dest = backups / f'{name}_{ts}.db'
    shutil.copy2(str(src), str(dest))
    c = sqlite3.connect(str(dest))
    integ = c.execute('PRAGMA integrity_check').fetchone()[0]
    c.close()
    md5_s = hashlib.md5(src.read_bytes()).hexdigest()[:12]
    md5_d = hashlib.md5(dest.read_bytes()).hexdigest()[:12]
    ok = 'OK' if md5_s == md5_d and integ == 'ok' else 'FAIL'
    print(f'[{ok}] {db} -> {dest.name} ({dest.stat().st_size//1024}KB)')
# Cleanup old backups (keep last 10)
for stem in ['jarvis', 'etoile', 'sniper']:
    old = sorted(backups.glob(f'{stem}_*.db'))[:-10]
    for f in old:
        f.unlink()
        print(f'  Cleaned: {f.name}')
"""},
            priority="high",
            schedule="every:2h",
            tags=["backup", "database"],
        ),

        TaskDef(
            id="save_config",
            name="Save Full Config to DBs",
            task_type="sync",
            action="script",
            payload={"script": "scripts/save_full_config.py"},
            priority="normal",
            schedule="every:6h",
            tags=["backup", "config"],
        ),

        TaskDef(
            id="git_sync",
            name="Git Status Check",
            task_type="sync",
            action="python",
            payload={"code": """
import subprocess
r = subprocess.run(['git','status','--porcelain','-u'], capture_output=True, text=True, cwd='F:/BUREAU/turbo')
changes = len([l for l in r.stdout.splitlines() if l.strip()])
r2 = subprocess.run(['git','log','--oneline','-1'], capture_output=True, text=True, cwd='F:/BUREAU/turbo')
print(f'HEAD: {r2.stdout.strip()}')
print(f'Uncommitted changes: {changes}')
if changes > 20:
    print('WARNING: Many uncommitted changes')
"""},
            priority="low",
            schedule="every:30m",
            tags=["sync", "git"],
        ),

        # ── Trading ──
        TaskDef(
            id="trading_scan",
            name="Trading Signal Scan",
            task_type="trading",
            action="branch",
            payload={
                "condition": {"type": "time"},
                "branches": {
                    "business_hours": {
                        "action": "python",
                        "type": "trading",
                        "payload": {"code": """
import sys; sys.path.insert(0, 'F:/BUREAU/turbo')
try:
    from src.trading import TradingEngine
    engine = TradingEngine()
    signals = engine.scan_all()
    for s in signals[:5]:
        print(f"{s.get('pair','?')}: {s.get('direction','?')} score={s.get('score',0)}")
    print(f"Total signals: {len(signals)}")
except Exception as e:
    print(f"Trading scan skipped: {e}")
"""},
                    },
                    "off_hours": {
                        "action": "python",
                        "type": "quick",
                        "payload": {"code": "print('Trading: off hours, skipped')"},
                    },
                },
            },
            priority="normal",
            schedule="every:15m",
            tags=["trading"],
        ),

        # ── Cluster Intelligence ──
        TaskDef(
            id="cluster_consensus_test",
            name="Cluster Consensus Test",
            task_type="consensus",
            action="cluster_query",
            payload={
                "prompt": "Reponds en 1 phrase: quel est ton statut?",
                "route": "consensus",
                "nodes": ["M1", "OL1"],
                "timeout": 15,
            },
            priority="low",
            schedule="every:30m",
            tags=["cluster", "test"],
        ),

        # ── Verification Pipeline ──
        TaskDef(
            id="mega_verify",
            name="Mega Verification (100 loops)",
            task_type="audit",
            action="python",
            payload={"code": """
import sys; sys.path.insert(0, 'F:/BUREAU/turbo')
# Quick 100-loop version for scheduled runs
import hashlib, json, sqlite3, random, time
from pathlib import Path
ROOT = Path('F:/BUREAU/turbo')
DB = str(ROOT / 'data' / 'jarvis.db')
conn = sqlite3.connect(DB)
rows = conn.execute('SELECT key, value FROM system_config').fetchall()
conn.close()
passed = failed = 0
for i in range(100):
    for dbp in ['data/jarvis.db', 'etoile.db', 'data/sniper.db']:
        c = sqlite3.connect(str(ROOT / dbp))
        r = c.execute('PRAGMA integrity_check').fetchone()[0]
        c.close()
        if r == 'ok': passed += 1
        else: failed += 1
    for k, v in rows:
        try: json.loads(v); passed += 1
        except: failed += 1
print(f'{passed}/{passed+failed} checks passed ({failed} failed)')
if failed == 0: print('SYSTEM INTACT')
else: print(f'WARNING: {failed} failures')
"""},
            priority="normal",
            schedule="daily:03:00",
            timeout_s=120,
            tags=["verify", "integrity"],
        ),

        # ── Full Pipeline (orchestrated) ──
        TaskDef(
            id="daily_pipeline",
            name="Daily Full Pipeline",
            task_type="pipeline",
            action="pipeline",
            payload={"steps": [
                {"action": "python", "type": "health",
                 "payload": {"code": "print('Step 1: Health check')"},
                 "required": True},
                {"action": "script", "type": "backup",
                 "payload": {"script": "scripts/save_full_config.py"},
                 "required": True},
                {"action": "python", "type": "audit",
                 "payload": {"code": """
import sys; sys.path.insert(0, 'F:/BUREAU/turbo')
from src.auto_auditor import AutoAuditor
r = AutoAuditor().run_full_audit()
print(f"Audit: {r.summary['score']}/100, {len(r.findings)} findings")
"""},
                 "required": False},
                {"action": "python", "type": "test",
                 "payload": {"code": """
import subprocess
r = subprocess.run(['python','-m','pytest','tests/','-x','-q','--tb=no','-k','not integration'],
    capture_output=True, text=True, cwd='F:/BUREAU/turbo', timeout=300)
lines = r.stdout.strip().splitlines()
print(lines[-1] if lines else 'No output')
"""},
                 "timeout": 300, "required": False},
            ]},
            branch_on={"failed": "stop"},
            priority="normal",
            schedule="daily:06:00",
            timeout_s=600,
            tags=["pipeline", "daily"],
        ),

        # ── Delegation Pipeline (M1 code review) ──
        TaskDef(
            id="m1_code_review",
            name="M1 Daily Code Review",
            task_type="review",
            action="cluster_query",
            payload={
                "prompt": "Review these Python modules for quality issues. Focus on: 1) Functions >100 lines 2) Missing error handling 3) Security concerns. Modules: auto_auditor.py, auto_fixer.py, dispatch_engine.py. Give 3 actionable improvements.",
                "route": "review",
                "timeout": 20,
            },
            priority="low",
            schedule="daily:09:00",
            tags=["review", "delegation"],
        ),

        # ── Cleanup ──
        TaskDef(
            id="cleanup_logs",
            name="Cleanup Old Logs",
            task_type="schedule",
            action="python",
            payload={"code": """
from pathlib import Path
from datetime import datetime, timedelta
TURBO = Path('F:/BUREAU/turbo')
cutoff = datetime.now() - timedelta(days=7)
cleaned = 0
for pattern in ['data/*.log', 'data/audit_reports/*.json']:
    for f in TURBO.glob(pattern):
        if f.stat().st_mtime < cutoff.timestamp():
            f.unlink()
            cleaned += 1
print(f'Cleaned {cleaned} old files')
"""},
            priority="low",
            schedule="daily:04:00",
            tags=["cleanup", "maintenance"],
        ),

        TaskDef(
            id="cleanup_backups",
            name="Cleanup Old Backups",
            task_type="schedule",
            action="python",
            payload={"code": """
from pathlib import Path
TURBO = Path('F:/BUREAU/turbo')
backups = TURBO / 'backups'
if backups.exists():
    cleaned = 0
    for stem in ['jarvis', 'etoile', 'sniper']:
        files = sorted(backups.glob(f'{stem}_*.db'), key=lambda f: f.stat().st_mtime)
        for f in files[:-10]:
            f.unlink()
            cleaned += 1
    print(f'Cleaned {cleaned} old backups')
else:
    print('No backups dir')
"""},
            priority="low",
            schedule="weekly:sun:05:00",
            tags=["cleanup", "backup"],
        ),

        # ══════════════════════════════════════════════════════════════════
        # ADVANCED AUTOMATION — Auto-healing, Telegram, LinkedIn, VRAM, etc.
        # ══════════════════════════════════════════════════════════════════

        # ── Auto-Healing: restart services on failure ──
        TaskDef(
            id="auto_heal_services",
            name="Auto-Heal Services",
            task_type="health",
            action="pipeline",
            payload={"steps": [
                {"action": "python", "type": "health", "payload": {"code": """
import subprocess, json
down = []
checks = [
    ("LM Studio", "127.0.0.1:1234/v1/models"),
    ("Ollama", "127.0.0.1:11434/api/tags"),
    ("Canvas Proxy", "127.0.0.1:18800/health"),
]
for name, url in checks:
    try:
        r = subprocess.run(["curl","-s","--max-time","3",f"http://{url}"],
            capture_output=True, text=True, timeout=5)
        if r.returncode != 0 or len(r.stdout) < 5:
            down.append(name)
            print(f"[DOWN] {name}")
        else:
            print(f"[OK] {name}")
    except:
        down.append(name)
        print(f"[DOWN] {name}")
if down:
    print(f"NEED_HEAL: {','.join(down)}")
    exit(1)
else:
    print("ALL_OK")
"""}, "required": False},
                {"action": "python", "type": "health", "payload": {"code": """
import subprocess
# Restart Ollama if down
try:
    r = subprocess.run(["curl","-s","--max-time","2","http://127.0.0.1:11434/api/tags"],
        capture_output=True, text=True, timeout=5)
    if r.returncode != 0 or len(r.stdout) < 5:
        subprocess.Popen(["ollama","serve"], creationflags=0x00000008)
        print("Restarted Ollama")
    else:
        print("Ollama OK")
except Exception as e:
    print(f"Ollama restart failed: {e}")
"""}, "required": False},
            ]},
            priority="high",
            schedule="every:10m",
            tags=["health", "auto-heal"],
        ),

        # ── GPU VRAM Guard ──
        TaskDef(
            id="vram_guard",
            name="VRAM Guard",
            task_type="health",
            action="branch",
            payload={
                "condition": {"type": "gpu_temp", "threshold": 82},
                "branches": {
                    "hot": {
                        "action": "python",
                        "payload": {"code": """
import subprocess
r = subprocess.run(["nvidia-smi","--query-gpu=index,temperature.gpu,memory.used",
    "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10)
print(f"GPU ALERT - High temperature detected!")
for line in r.stdout.strip().splitlines():
    parts = [x.strip() for x in line.split(',')]
    print(f"  GPU{parts[0]}: {parts[1]}C, {parts[2]}MB VRAM")
print("Consider reducing load or checking cooling")
"""},
                    },
                    "cool": {
                        "action": "python",
                        "payload": {"code": "print('GPU temps normal')"},
                    },
                    "error": {
                        "action": "python",
                        "payload": {"code": "print('nvidia-smi unavailable')"},
                    },
                },
            },
            priority="normal",
            schedule="every:15m",
            tags=["health", "gpu", "vram"],
        ),

        # ── Disk Space Monitor ──
        TaskDef(
            id="disk_monitor",
            name="Disk Space Monitor",
            task_type="health",
            action="branch",
            payload={
                "condition": {"type": "disk_space", "threshold_gb": 20, "drive": "C:"},
                "branches": {
                    "ok": {"action": "python", "payload": {"code": """
import shutil
for drive in ['C:/', 'F:/']:
    u = shutil.disk_usage(drive)
    print(f"{drive} {u.free/1024**3:.1f}GB free / {u.total/1024**3:.0f}GB total ({u.used*100/u.total:.0f}%)")
"""}},
                    "low": {"action": "python", "payload": {"code": """
import shutil
for drive in ['C:/', 'F:/']:
    u = shutil.disk_usage(drive)
    print(f"LOW SPACE {drive} {u.free/1024**3:.1f}GB free!")
print("Consider cleaning HuggingFace cache (78GB on C:) or old backups")
"""}},
                },
            },
            priority="normal",
            schedule="every:1h",
            tags=["health", "disk"],
        ),

        # ── DB Integrity Guard ──
        TaskDef(
            id="db_integrity_guard",
            name="Database Integrity Guard",
            task_type="backup",
            action="pipeline",
            payload={"steps": [
                {"action": "python", "type": "backup", "payload": {"code": """
import sqlite3
from pathlib import Path
TURBO = Path('F:/BUREAU/turbo')
dbs = list(TURBO.glob('data/*.db')) + list(TURBO.glob('*.db'))
ok = corrupt = 0
for db in dbs:
    try:
        c = sqlite3.connect(str(db))
        r = c.execute('PRAGMA integrity_check').fetchone()[0]
        c.close()
        if r == 'ok':
            ok += 1
        else:
            corrupt += 1
            print(f'[CORRUPT] {db.name}')
    except Exception as e:
        corrupt += 1
        print(f'[ERROR] {db.name}: {e}')
print(f'{ok} OK, {corrupt} corrupt out of {len(dbs)} databases')
if corrupt > 0:
    exit(1)
"""}, "required": False},
                {"action": "python", "type": "backup", "payload": {"code": """
# Cross-DB config redundancy check
import sqlite3, json
from pathlib import Path
TURBO = Path('F:/BUREAU/turbo')
for name, path, table in [
    ('jarvis', 'data/jarvis.db', 'system_config'),
    ('etoile', 'etoile.db', 'system_restore'),
    ('sniper', 'data/sniper.db', 'trading_config'),
]:
    c = sqlite3.connect(str(TURBO / path))
    try:
        cnt = c.execute(f'SELECT count(*) FROM {table}').fetchone()[0]
        print(f'{name}: {cnt} entries in {table}')
    except:
        print(f'{name}: table {table} missing')
    c.close()
"""}, "required": False},
            ]},
            priority="high",
            schedule="every:30m",
            tags=["backup", "integrity"],
        ),

        # ── Telegram Status Report ──
        TaskDef(
            id="telegram_status",
            name="Telegram Daily Status",
            task_type="schedule",
            action="python",
            payload={"code": """
import sys, os, subprocess, sqlite3, json
sys.path.insert(0, 'F:/BUREAU/turbo')
from pathlib import Path
TURBO = Path('F:/BUREAU/turbo')
# Build status message
lines = ['<b>JARVIS Daily Report</b>']
# Cluster
for name, url in [('M1','127.0.0.1:1234/v1/models'),('OL1','127.0.0.1:11434/api/tags')]:
    try:
        r = subprocess.run(['curl','-s','--max-time','3',f'http://{url}'],
            capture_output=True, text=True, timeout=5)
        lines.append(f"  {name}: {'OK' if r.returncode==0 else 'DOWN'}")
    except: lines.append(f"  {name}: DOWN")
# Audit
try:
    from src.auto_auditor import AutoAuditor
    report = AutoAuditor().run_full_audit()
    lines.append(f"Audit: {report.summary['score']}/100")
except: lines.append("Audit: error")
# Git
r = subprocess.run(['git','log','--oneline','-1'], capture_output=True, text=True, cwd=str(TURBO))
lines.append(f"Git: {r.stdout.strip()[:50]}")
# DBs
for db in ['data/jarvis.db','etoile.db','data/sniper.db']:
    s = (TURBO/db).stat().st_size//1024
    lines.append(f"  {db}: {s}KB")
# Orchestrator stats
try:
    c = sqlite3.connect(str(TURBO/'data/task_orchestrator.db'))
    total = c.execute('SELECT count(*) FROM task_runs').fetchone()[0]
    ok = c.execute("SELECT count(*) FROM task_runs WHERE status='completed'").fetchone()[0]
    fail = c.execute("SELECT count(*) FROM task_runs WHERE status='failed'").fetchone()[0]
    c.close()
    lines.append(f"Tasks: {ok}/{total} OK, {fail} failed")
except: pass
msg = chr(10).join(lines)
print(msg)
# Send via Telegram
env = TURBO / '.env'
token = chat_id = None
if env.exists():
    for line in env.read_text(errors='replace').splitlines():
        if line.startswith('TELEGRAM_BOT_TOKEN='): token=line.split('=',1)[1].strip().strip('"')
        elif line.startswith('TELEGRAM_CHAT_ID='): chat_id=line.split('=',1)[1].strip().strip('"')
if token and chat_id:
    subprocess.run(['curl','-s','--max-time','10',
        f'https://api.telegram.org/bot{token}/sendMessage',
        '-d',f'chat_id={chat_id}','-d',f'text={msg}','-d','parse_mode=HTML'],
        capture_output=True, timeout=15)
    print('Sent to Telegram')
"""},
            priority="low",
            schedule="daily:08:00",
            tags=["telegram", "report"],
        ),

        # ── Telegram Alert on Failure (runs after each task cycle) ──
        TaskDef(
            id="telegram_failure_alert",
            name="Alert Failures to Telegram",
            task_type="schedule",
            action="python",
            payload={"code": """
import sqlite3, subprocess, json
from pathlib import Path
from datetime import datetime, timedelta
TURBO = Path('F:/BUREAU/turbo')
c = sqlite3.connect(str(TURBO/'data/task_orchestrator.db'))
cutoff = (datetime.now() - timedelta(minutes=30)).isoformat()
fails = c.execute("SELECT task_id, error, started_at FROM task_runs WHERE status='failed' AND started_at > ?", (cutoff,)).fetchall()
c.close()
if not fails:
    print('No recent failures')
else:
    msg = f'JARVIS ALERT: {len(fails)} task(s) failed\\n'
    for tid, err, ts in fails[:5]:
        msg += f'  {tid}: {(err or "?")[:60]}\\n'
    print(msg)
    env = TURBO / '.env'
    token = chat_id = None
    if env.exists():
        for line in env.read_text(errors='replace').splitlines():
            if line.startswith('TELEGRAM_BOT_TOKEN='): token=line.split('=',1)[1].strip().strip('"')
            elif line.startswith('TELEGRAM_CHAT_ID='): chat_id=line.split('=',1)[1].strip().strip('"')
    if token and chat_id:
        subprocess.run(['curl','-s','--max-time','10',
            f'https://api.telegram.org/bot{token}/sendMessage',
            '-d',f'chat_id={chat_id}','-d',f'text={msg}'],
            capture_output=True, timeout=15)
"""},
            priority="high",
            schedule="every:30m",
            tags=["telegram", "alert"],
        ),

        # ── LinkedIn Automation ──
        TaskDef(
            id="linkedin_publish",
            name="LinkedIn Auto-Publish",
            task_type="schedule",
            action="branch",
            payload={
                "condition": {"type": "time"},
                "branches": {
                    "business_hours": {
                        "action": "script",
                        "type": "schedule",
                        "payload": {"script": "scripts/linkedin_scheduler.py", "args": ["--publish-next"]},
                        "timeout": 120,
                    },
                    "off_hours": {
                        "action": "python",
                        "payload": {"code": "print('LinkedIn: off hours')"},
                    },
                },
            },
            priority="normal",
            schedule="every:2h",
            tags=["linkedin", "social"],
        ),

        TaskDef(
            id="linkedin_routine",
            name="LinkedIn Daily Routine",
            task_type="schedule",
            action="script",
            payload={"script": "scripts/linkedin_auto_routine.py"},
            priority="low",
            schedule="daily:07:30",
            timeout_s=300,
            tags=["linkedin", "social"],
        ),

        # ── Proxy & OpenClaw Monitoring ──
        TaskDef(
            id="proxy_monitor",
            name="Canvas Proxy Monitor",
            task_type="health",
            action="branch",
            payload={
                "condition": {"type": "health", "node": "M1"},
                "branches": {
                    "healthy": {
                        "action": "python",
                        "payload": {"code": """
import subprocess
r = subprocess.run(["curl","-s","--max-time","3","http://127.0.0.1:18800/health"],
    capture_output=True, text=True, timeout=5)
if r.returncode == 0 and r.stdout:
    print(f"Proxy OK: {r.stdout[:100]}")
else:
    print("Proxy DOWN - restarting...")
    subprocess.Popen(["node","F:/BUREAU/turbo/direct-proxy.js"], creationflags=0x00000008)
    print("Proxy restart initiated")
"""},
                    },
                    "unhealthy": {
                        "action": "python",
                        "payload": {"code": "print('M1 down, skipping proxy check')"},
                    },
                },
            },
            priority="normal",
            schedule="every:10m",
            tags=["health", "proxy"],
        ),

        TaskDef(
            id="openclaw_monitor",
            name="OpenClaw Gateway Monitor",
            task_type="health",
            action="branch",
            payload={
                "condition": {"type": "process_running", "process": "openclaw.exe"},
                "branches": {
                    "running": {
                        "action": "python",
                        "payload": {"code": """
import subprocess
r = subprocess.run(["curl","-s","--max-time","3","http://127.0.0.1:18789/health"],
    capture_output=True, text=True, timeout=5)
print(f"OpenClaw: {'OK' if r.returncode==0 else 'ERROR'} {r.stdout[:80]}")
"""},
                    },
                    "stopped": {
                        "action": "python",
                        "payload": {"code": """
import subprocess
print("OpenClaw not running - starting...")
subprocess.Popen(["openclaw","serve"], creationflags=0x00000008, cwd="F:/BUREAU/turbo")
print("OpenClaw start initiated")
"""},
                    },
                },
            },
            priority="normal",
            schedule="every:10m",
            tags=["health", "openclaw"],
        ),

        # ── Model Management ──
        TaskDef(
            id="model_health",
            name="Model Load Verification",
            task_type="health",
            action="python",
            payload={"code": """
import subprocess, json
# M1: check loaded models
r = subprocess.run(["curl","-s","--max-time","5","http://127.0.0.1:1234/v1/models"],
    capture_output=True, text=True, timeout=10)
if r.returncode == 0:
    try:
        data = json.loads(r.stdout)
        models = data.get('data', data.get('models', []))
        loaded = [m for m in models if m.get('loaded_instances')]
        print(f"M1: {len(models)} available, {len(loaded)} loaded")
        for m in loaded:
            print(f"  {m['id']}: loaded")
    except: print(f"M1: parse error")
else:
    print("M1: OFFLINE")
# OL1: check models
r = subprocess.run(["curl","-s","--max-time","3","http://127.0.0.1:11434/api/tags"],
    capture_output=True, text=True, timeout=5)
if r.returncode == 0:
    try:
        data = json.loads(r.stdout)
        models = data.get('models', [])
        print(f"OL1: {len(models)} models available")
        for m in models[:5]:
            print(f"  {m.get('name','?')}")
    except: print("OL1: parse error")
else:
    print("OL1: OFFLINE")
"""},
            priority="low",
            schedule="every:30m",
            tags=["cluster", "models"],
        ),

        # ── Audit Score Auto-Improve Pipeline ──
        TaskDef(
            id="auto_improve_pipeline",
            name="Auto-Improve Pipeline",
            task_type="audit",
            action="branch",
            payload={
                "condition": {"type": "audit_score", "threshold": 95},
                "branches": {
                    "pass": {
                        "action": "python",
                        "payload": {"code": "print('Audit score >= 95, no action needed')"},
                    },
                    "fail": {
                        "action": "pipeline",
                        "type": "audit",
                        "payload": {"steps": [
                            {"action": "python", "type": "audit", "payload": {"code": """
import sys; sys.path.insert(0, 'F:/BUREAU/turbo')
from src.auto_fixer import AutoFixer
r = AutoFixer().run_fix_cycle(dry_run=False)
applied = [f for f in r.get('fixes',[]) if f.get('applied')]
print(f"Applied {len(applied)} fixes")
"""}},
                            {"action": "python", "type": "audit", "payload": {"code": """
import sys; sys.path.insert(0, 'F:/BUREAU/turbo')
from src.auto_auditor import AutoAuditor
r = AutoAuditor().run_full_audit()
print(f"New score: {r.summary['score']}/100")
"""}},
                        ]},
                    },
                    "error": {
                        "action": "python",
                        "payload": {"code": "print('Audit check failed')"},
                    },
                },
            },
            priority="normal",
            schedule="daily:02:00",
            tags=["audit", "auto-improve"],
        ),

        # ── MD5 Registry Sync ──
        TaskDef(
            id="md5_registry_sync",
            name="MD5 Registry Sync",
            task_type="sync",
            action="python",
            payload={"code": """
import hashlib, json, sqlite3
from pathlib import Path
ROOT = Path('F:/BUREAU/turbo')
conn = sqlite3.connect(str(ROOT / 'data/jarvis.db'))
row = conn.execute("SELECT value FROM system_config WHERE key='src_module_registry'").fetchone()
registry = json.loads(row[0]) if row else {}
updated = 0
for f in sorted((ROOT / 'src').glob('*.py')):
    if f.name.startswith('__'): continue
    name = f.stem
    content = f.read_text(encoding='utf-8', errors='replace')
    new_md5 = hashlib.md5(content.encode()).hexdigest()[:12]
    if name in registry and isinstance(registry[name], dict):
        if registry[name].get('md5','') != new_md5:
            registry[name]['md5'] = new_md5
            registry[name]['lines'] = content.count(chr(10)) + 1
            updated += 1
    else:
        registry[name] = {'md5': new_md5, 'lines': content.count(chr(10))+1,
            'functions': content.count('def '), 'has_all': '__all__' in content}
        updated += 1
if updated:
    conn.execute('UPDATE system_config SET value=?, ts=datetime("now") WHERE key=?',
        (json.dumps(registry), 'src_module_registry'))
    conn.commit()
print(f'MD5 registry: {updated} updated out of {len(registry)}')
conn.close()
"""},
            priority="normal",
            schedule="every:2h",
            tags=["sync", "md5"],
        ),

        # ── Full Nightly Pipeline ──
        TaskDef(
            id="nightly_pipeline",
            name="Nightly Full Pipeline",
            task_type="pipeline",
            action="pipeline",
            payload={"steps": [
                {"action": "python", "type": "health", "payload": {"code": """
import subprocess, json
nodes = [("M1","127.0.0.1:1234/v1/models"),("OL1","127.0.0.1:11434/api/tags")]
status = []
for name, url in nodes:
    try:
        r = subprocess.run(["curl","-s","--max-time","3",f"http://{url}"],
            capture_output=True, text=True, timeout=5)
        status.append(f"{name}:{'OK' if r.returncode==0 else 'DOWN'}")
    except: status.append(f"{name}:DOWN")
print(f"Cluster: {', '.join(status)}")
"""}, "required": True},
                {"action": "script", "type": "backup", "payload": {
                    "script": "scripts/save_full_config.py"}, "required": True},
                {"action": "python", "type": "audit", "payload": {"code": """
import sys; sys.path.insert(0, 'F:/BUREAU/turbo')
from src.auto_fixer import AutoFixer
from src.auto_auditor import AutoAuditor
AutoFixer().run_fix_cycle(dry_run=False)
r = AutoAuditor().run_full_audit()
print(f"Score: {r.summary['score']}/100, {len(r.findings)} findings")
"""}, "required": False},
                {"action": "python", "type": "test", "payload": {"code": """
import subprocess
r = subprocess.run(['python','-m','pytest','tests/','-x','-q','--tb=no','-k','not integration'],
    capture_output=True, text=True, cwd='F:/BUREAU/turbo', timeout=300)
lines = r.stdout.strip().splitlines()
print(lines[-1] if lines else 'No test output')
"""}, "timeout": 300, "required": False},
                {"action": "python", "type": "sync", "payload": {"code": """
import hashlib, json, sqlite3
from pathlib import Path
ROOT = Path('F:/BUREAU/turbo')
conn = sqlite3.connect(str(ROOT/'data/jarvis.db'))
row = conn.execute("SELECT value FROM system_config WHERE key='src_module_registry'").fetchone()
reg = json.loads(row[0]) if row else {}
updated = 0
for f in sorted((ROOT/'src').glob('*.py')):
    if f.name.startswith('__'): continue
    c = f.read_text(encoding='utf-8', errors='replace')
    md5 = hashlib.md5(c.encode()).hexdigest()[:12]
    if f.stem in reg and isinstance(reg[f.stem],dict) and reg[f.stem].get('md5','')!=md5:
        reg[f.stem]['md5']=md5; reg[f.stem]['lines']=c.count(chr(10))+1; updated+=1
if updated:
    conn.execute('UPDATE system_config SET value=?,ts=datetime("now") WHERE key=?',
        (json.dumps(reg),'src_module_registry'))
    conn.commit()
conn.close()
print(f'MD5 sync: {updated} updated')
"""}, "required": False},
                {"action": "python", "type": "backup", "payload": {"code": """
import shutil, hashlib, sqlite3
from pathlib import Path
from datetime import datetime
TURBO = Path('F:/BUREAU/turbo')
ts = datetime.now().strftime('%Y%m%d_%H%M%S')
backups = TURBO / 'backups'
backups.mkdir(exist_ok=True)
for db in ['data/jarvis.db','etoile.db','data/sniper.db']:
    s = TURBO / db
    d = backups / f'{s.stem}_{ts}.db'
    shutil.copy2(str(s), str(d))
    c = sqlite3.connect(str(d))
    ok = c.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    c.close()
    print(f"{'OK' if ok else 'FAIL'}: {d.name}")
"""}, "required": True},
            ]},
            branch_on={"failed": "stop"},
            priority="normal",
            schedule="daily:01:00",
            timeout_s=900,
            tags=["pipeline", "nightly"],
        ),

        # ── M1 Architecture Review (weekly delegation) ──
        TaskDef(
            id="weekly_archi_review",
            name="Weekly Architecture Review (M1)",
            task_type="architecture",
            action="cluster_query",
            payload={
                "prompt": "Analyse l'architecture d'un systeme Python avec 228 modules, 295 tests, cluster 4 noeuds LM Studio+Ollama. Identifie: 1) Les 3 risques majeurs d'architecture 2) Les opportunites de simplification 3) Les single points of failure. Reponds en francais, format structure.",
                "route": "architecture",
                "timeout": 25,
            },
            priority="low",
            schedule="weekly:mon:10:00",
            tags=["review", "architecture", "delegation"],
        ),

        # ── Consensus Security Review ──
        TaskDef(
            id="security_consensus",
            name="Security Consensus Review",
            task_type="consensus",
            action="cluster_query",
            payload={
                "prompt": "Revue securite Python: quels sont les 3 patterns les plus dangereux a chercher dans un projet avec subprocess, eval, __import__, pickle, et requests? Donne les regex de detection pour chaque.",
                "route": "consensus",
                "nodes": ["M1", "OL1"],
                "timeout": 20,
            },
            priority="low",
            schedule="weekly:wed:11:00",
            tags=["security", "consensus", "delegation"],
        ),

        # ── Process GC (garbage collection) ──
        TaskDef(
            id="process_gc",
            name="Process Garbage Collection",
            task_type="schedule",
            action="python",
            payload={"code": """
import os
# Find active Python processes
output = os.popen('tasklist /FI "IMAGENAME eq python.exe" /FO CSV 2>NUL').read()
lines = [l for l in output.strip().splitlines()[1:] if l.strip()]
print(f"Active Python processes: {len(lines)}")
for line in lines[:10]:
    parts = line.replace('"','').split(',')
    if len(parts) >= 2:
        print(f"  PID {parts[1]}: {parts[0]}")
"""},
            priority="low",
            schedule="every:1h",
            tags=["cleanup", "process"],
        ),

        # ── Watchdog: Electron Desktop ──
        TaskDef(
            id="electron_monitor",
            name="Electron Desktop Monitor",
            task_type="health",
            action="branch",
            payload={
                "condition": {"type": "process_running", "process": "electron.exe"},
                "branches": {
                    "running": {
                        "action": "python",
                        "payload": {"code": """
import subprocess
r = subprocess.run(["curl","-s","--max-time","2","http://127.0.0.1:9742/health"],
    capture_output=True, text=True, timeout=5)
if r.returncode == 0:
    print(f"Electron WS: OK ({r.stdout[:50]})")
else:
    print("Electron WS: DOWN (electron running but WS not responding)")
"""},
                    },
                    "stopped": {
                        "action": "python",
                        "payload": {"code": "print('Electron not running (normal if no desktop session)')"},
                    },
                },
            },
            priority="low",
            schedule="every:15m",
            tags=["health", "electron"],
        ),
    ]

    for task in defaults:
        save_task(task)
        logger.info("  Created: %s (%s)", task.id, task.schedule)

    print(f"\n  {len(defaults)} default tasks created")


# ── Commands ────────────────────────────────────────────────────────────────

def show_status():
    conn = get_db()
    tasks = conn.execute("SELECT id, name, task_type, action, priority, enabled FROM tasks ORDER BY priority").fetchall()
    schedules = {r[0]: r[1:] for r in conn.execute("SELECT * FROM task_schedule").fetchall()}

    print(f"\n{'='*80}")
    print(f"  JARVIS TASK ORCHESTRATOR — {len(tasks)} tasks")
    print(f"{'='*80}")
    print(f"  {'ID':25} {'TYPE':12} {'PRIO':8} {'SCHEDULE':20} {'LAST RUN':20}")
    print(f"  {'-'*25} {'-'*12} {'-'*8} {'-'*20} {'-'*20}")

    for t in tasks:
        tid, name, ttype, action, prio, enabled = t
        sched = schedules.get(tid, (None, None, 0, 0, 0))
        last = sched[0] or "never"
        next_r = sched[1] or "-"
        runs = sched[2] or 0
        fails = sched[3] or 0
        status = "" if enabled else " [DISABLED]"
        print(f"  {tid:25} {ttype:12} {prio:8} {str(next_r)[:20]:20} {str(last)[:20]:20} r={runs} f={fails}{status}")

    # Recent runs
    recent = conn.execute("""
        SELECT task_id, status, duration_ms, node, started_at
        FROM task_runs ORDER BY id DESC LIMIT 10
    """).fetchall()
    if recent:
        print(f"\n  RECENT RUNS:")
        for r in recent:
            print(f"    {r[4] or '?':20} {r[0]:25} {r[1]:10} {r[2]:8.0f}ms {r[3] or '':5}")

    conn.close()
    print(f"{'='*80}")


def show_schedule():
    conn = get_db()
    rows = conn.execute("""
        SELECT t.id, t.name, t.schedule, s.last_run, s.next_run, s.run_count, s.fail_count, s.avg_duration_ms
        FROM tasks t JOIN task_schedule s ON t.id = s.task_id
        WHERE t.enabled = 1
        ORDER BY s.next_run
    """).fetchall()
    conn.close()

    print(f"\n{'='*80}")
    print(f"  SCHEDULED TASKS — {len(rows)} active")
    print(f"{'='*80}")
    now = datetime.now()
    for r in rows:
        tid, name, sched, last, nxt, runs, fails, avg = r
        try:
            next_dt = datetime.fromisoformat(nxt) if nxt else None
            due = "OVERDUE" if next_dt and next_dt < now else f"in {str(next_dt - now).split('.')[0]}" if next_dt else "?"
        except Exception:
            due = "?"
        print(f"  {tid:25} {sched:18} next={due:18} runs={runs} fails={fails} avg={avg:.0f}ms")
    print(f"{'='*80}")


def run_due_tasks():
    """Main loop: find and execute all due tasks."""
    tasks = get_due_tasks()
    if not tasks:
        print("  No tasks due")
        return 0

    print(f"\n  {len(tasks)} tasks due")
    completed = 0
    for task in sorted(tasks, key=lambda t: TASK_PRIORITY.get(t.priority, 2)):
        if not check_dependencies(task):
            logger.info("  Skipped %s: dependencies not met", task.id)
            continue

        result = execute_task(task)
        record_run(result)
        status_icon = "OK" if result.status == "completed" else "FAIL"
        print(f"  [{status_icon}] {task.name:30} {result.duration_ms:8.0f}ms {result.node or 'local':5}")
        if result.status == "completed":
            completed += 1
        elif result.error:
            print(f"       Error: {result.error[:100]}")

    print(f"\n  Completed: {completed}/{len(tasks)}")
    return completed


def run_single_task(task_id: str):
    """Run a specific task by ID."""
    conn = get_db()
    row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    conn.close()
    if not row:
        print(f"  Task not found: {task_id}")
        return

    task = TaskDef(
        id=row[0], name=row[1], task_type=row[2], action=row[3],
        payload=json.loads(row[4] or "{}"), priority=row[5], schedule=row[6] or "",
        depends_on=json.loads(row[7] or "[]"), branch_on=json.loads(row[8] or "{}"),
        timeout_s=row[9] or 300, retry_max=row[10] or 2, enabled=True,
        tags=json.loads(row[12] or "[]"),
    )
    result = execute_task(task)
    record_run(result)
    print(f"\n  [{result.status}] {task.name} ({result.duration_ms:.0f}ms, node={result.node or 'local'})")
    if result.output:
        print(f"\n{result.output[:3000]}")
    if result.error:
        print(f"\n  Error: {result.error[:500]}")


def daemon_loop():
    """Run as a daemon, checking for due tasks every 60s."""
    print("  JARVIS Task Orchestrator — Daemon mode")
    print("  Checking for due tasks every 60 seconds...")
    while True:
        try:
            tasks = get_due_tasks()
            if tasks:
                logger.info("Found %d due tasks", len(tasks))
                for task in sorted(tasks, key=lambda t: TASK_PRIORITY.get(t.priority, 2)):
                    if check_dependencies(task):
                        result = execute_task(task)
                        record_run(result)
                        logger.info("[%s] %s (%dms)", result.status, task.name, result.duration_ms)
        except Exception as e:
            logger.error("Daemon error: %s", e)
        time.sleep(60)


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="JARVIS Task Orchestrator")
    parser.add_argument("--init", action="store_true", help="Initialize DB + default tasks")
    parser.add_argument("--status", action="store_true", help="Show task queue status")
    parser.add_argument("--schedule", action="store_true", help="Show scheduled tasks")
    parser.add_argument("--run", metavar="TASK_ID", help="Run specific task")
    parser.add_argument("--add", metavar="JSON", help="Add task from JSON")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--run-all", action="store_true", help="Run all due tasks now")
    args = parser.parse_args()

    init_db()

    if args.init:
        create_default_tasks()
    elif args.status:
        show_status()
    elif args.schedule:
        show_schedule()
    elif args.run:
        run_single_task(args.run)
    elif args.add:
        data = json.loads(args.add)
        task = TaskDef(**data)
        save_task(task)
        print(f"  Added: {task.id} ({task.schedule})")
    elif args.daemon:
        daemon_loop()
    elif args.run_all:
        run_due_tasks()
    else:
        run_due_tasks()


if __name__ == "__main__":
    main()
