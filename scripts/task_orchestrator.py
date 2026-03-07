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
import socket
import sqlite3
import subprocess
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
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

        -- Event-driven triggers
        CREATE TABLE IF NOT EXISTS task_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,  -- file_changed, threshold, webhook, cron
            source TEXT NOT NULL,      -- file path, metric name, URL
            task_id TEXT NOT NULL,     -- task to trigger
            config TEXT DEFAULT '{}',  -- threshold values, patterns, etc.
            enabled INTEGER DEFAULT 1,
            last_triggered TEXT,
            trigger_count INTEGER DEFAULT 0,
            cooldown_s INTEGER DEFAULT 300,  -- min seconds between triggers
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        );

        -- Escalation policies
        CREATE TABLE IF NOT EXISTS task_escalation (
            task_id TEXT PRIMARY KEY,
            consecutive_fails INTEGER DEFAULT 0,
            level_1_threshold INTEGER DEFAULT 3,   -- warn after 3 fails
            level_2_threshold INTEGER DEFAULT 5,   -- alert after 5 fails
            level_3_threshold INTEGER DEFAULT 10,  -- critical after 10 fails
            level_1_action TEXT DEFAULT 'log',     -- log, telegram, email
            level_2_action TEXT DEFAULT 'telegram',
            level_3_action TEXT DEFAULT 'telegram_critical',
            last_escalation TEXT,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        );

        -- System metrics (time-series)
        CREATE TABLE IF NOT EXISTS task_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_name TEXT NOT NULL,
            metric_value REAL NOT NULL,
            tags TEXT DEFAULT '{}',
            recorded_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_metrics_name ON task_metrics(metric_name);
        CREATE INDEX IF NOT EXISTS idx_metrics_time ON task_metrics(recorded_at);

        -- Task chain state (data passing between pipeline steps)
        CREATE TABLE IF NOT EXISTS task_chain_state (
            chain_id TEXT NOT NULL,
            step_index INTEGER NOT NULL,
            output_key TEXT NOT NULL,
            output_value TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (chain_id, step_index, output_key)
        );
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
    elif check_type in _EXTENDED_CONDITIONS:
        branch_key = check_branch_condition(condition)
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


# ── Escalation Engine ──────────────────────────────────────────────────────

def init_escalation(task_id: str, l1=3, l2=5, l3=10):
    """Initialize escalation policy for a task."""
    conn = get_db()
    conn.execute("""
        INSERT OR IGNORE INTO task_escalation (task_id, level_1_threshold, level_2_threshold, level_3_threshold)
        VALUES (?, ?, ?, ?)
    """, (task_id, l1, l2, l3))
    conn.commit()
    conn.close()


def process_escalation(task_id: str, status: str):
    """Update escalation state after task run. Trigger alerts if thresholds crossed."""
    conn = get_db()
    conn.execute("""
        INSERT OR IGNORE INTO task_escalation (task_id) VALUES (?)
    """, (task_id,))

    if status == "completed":
        conn.execute("UPDATE task_escalation SET consecutive_fails=0 WHERE task_id=?", (task_id,))
        conn.commit()
        conn.close()
        return

    # Increment fail counter
    conn.execute("UPDATE task_escalation SET consecutive_fails=consecutive_fails+1 WHERE task_id=?", (task_id,))
    row = conn.execute("SELECT consecutive_fails, level_1_threshold, level_2_threshold, level_3_threshold FROM task_escalation WHERE task_id=?", (task_id,)).fetchone()
    conn.commit()
    conn.close()

    if not row:
        return
    fails, l1, l2, l3 = row

    if fails >= l3:
        msg = f"CRITICAL: {task_id} failed {fails}x consecutively!"
        logger.error(msg)
        notify_telegram(f"🔴 {msg}")
    elif fails >= l2:
        msg = f"ALERT: {task_id} failed {fails}x consecutively"
        logger.warning(msg)
        notify_telegram(f"🟠 {msg}", silent=True)
    elif fails >= l1:
        logger.warning("WARN: %s failed %dx consecutively", task_id, fails)


# ── Parallel Executor ──────────────────────────────────────────────────────

def execute_parallel(tasks: list[TaskDef], max_workers: int = 4) -> list[TaskResult]:
    """Execute multiple independent tasks in parallel using ThreadPoolExecutor."""
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(execute_task, t): t for t in tasks}
        for future in as_completed(futures):
            task = futures[future]
            try:
                result = future.result(timeout=600)
                results.append(result)
            except Exception as e:
                results.append(TaskResult(task.id, "failed", error=f"Parallel exec error: {e}"))
    return results


def run_due_tasks_parallel():
    """Run due tasks with parallelism for independent tasks."""
    tasks = get_due_tasks()
    if not tasks:
        return 0

    # Sort by priority
    tasks.sort(key=lambda t: TASK_PRIORITY.get(t.priority, 2))

    # Split into groups: tasks with deps run sequentially, others in parallel
    sequential = [t for t in tasks if t.depends_on]
    parallel = [t for t in tasks if not t.depends_on]

    completed = 0

    # Run parallel batch first
    if parallel:
        logger.info("Running %d tasks in parallel", len(parallel))
        results = execute_parallel(parallel)
        for r in results:
            record_run(r)
            process_escalation(r.task_id, r.status)
            if r.status == "completed":
                completed += 1
            logger.info("[%s] %s (%dms)", r.status, r.task_id, r.duration_ms)

    # Then sequential with dependency checks
    for task in sequential:
        if check_dependencies(task):
            result = execute_task(task)
            record_run(result)
            process_escalation(result.task_id, result.status)
            if result.status == "completed":
                completed += 1
            logger.info("[%s] %s (%dms)", result.status, task.id, result.duration_ms)

    return completed


# ── Resource-Aware Scheduling ──────────────────────────────────────────────

def check_resource_availability(task: TaskDef) -> tuple[bool, str]:
    """Check if system resources are available for this task."""
    tags = task.tags or []

    # GPU tasks: check temperature
    if "gpu" in tags or task.task_type == "trading":
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=temperature.gpu,utilization.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0:
                for line in r.stdout.strip().splitlines():
                    parts = [x.strip() for x in line.split(",")]
                    if int(parts[0]) > 90:
                        return False, f"GPU too hot: {parts[0]}C"
                    if int(parts[1]) > 95:
                        return False, f"GPU too busy: {parts[1]}%"
        except Exception:
            pass

    # Heavy tasks: check RAM
    if "heavy" in tags or task.task_type in ("pipeline", "audit"):
        try:
            import psutil
            mem = psutil.virtual_memory()
            if mem.percent > 92:
                return False, f"RAM too high: {mem.percent}%"
        except ImportError:
            pass

    # Disk tasks: check free space
    if "backup" in tags:
        try:
            import shutil
            usage = shutil.disk_usage("F:/")
            if usage.free < 2 * 1024**3:
                return False, f"Disk F: too full: {usage.free / 1024**3:.1f}GB free"
        except Exception:
            pass

    return True, "OK"


# ── Event Engine ───────────────────────────────────────────────────────────

def register_event(event_type: str, source: str, task_id: str, config: dict = None, cooldown_s: int = 300):
    """Register an event trigger for a task."""
    conn = get_db()
    conn.execute("""
        INSERT OR REPLACE INTO task_events (event_type, source, task_id, config, cooldown_s)
        VALUES (?, ?, ?, ?, ?)
    """, (event_type, source, task_id, json.dumps(config or {}), cooldown_s))
    conn.commit()
    conn.close()


def check_file_events():
    """Check for file-change events. Returns list of task_ids to trigger."""
    conn = get_db()
    events = conn.execute("""
        SELECT id, source, task_id, config, last_triggered, cooldown_s
        FROM task_events WHERE event_type='file_changed' AND enabled=1
    """).fetchall()

    triggered = []
    now = datetime.now()
    for eid, source, task_id, config_json, last_triggered, cooldown_s in events:
        cfg = json.loads(config_json or "{}")
        path = Path(source)
        if not path.exists():
            continue

        # Check cooldown
        if last_triggered:
            lt = datetime.fromisoformat(last_triggered)
            if (now - lt).total_seconds() < cooldown_s:
                continue

        # Check if file changed since last trigger
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        last_mtime = cfg.get("last_mtime", "")
        if last_mtime and mtime.isoformat() <= last_mtime:
            continue

        # File changed! Trigger the task
        triggered.append(task_id)
        cfg["last_mtime"] = mtime.isoformat()
        conn.execute("""
            UPDATE task_events SET last_triggered=?, trigger_count=trigger_count+1, config=?
            WHERE id=?
        """, (now.isoformat(), json.dumps(cfg), eid))

    conn.commit()
    conn.close()
    return triggered


def check_threshold_events():
    """Check metric threshold events. Returns list of task_ids to trigger."""
    conn = get_db()
    events = conn.execute("""
        SELECT id, source, task_id, config, last_triggered, cooldown_s
        FROM task_events WHERE event_type='threshold' AND enabled=1
    """).fetchall()

    triggered = []
    now = datetime.now()
    for eid, metric_name, task_id, config_json, last_triggered, cooldown_s in events:
        cfg = json.loads(config_json or "{}")
        threshold = cfg.get("threshold", 0)
        direction = cfg.get("direction", "above")  # above or below

        # Check cooldown
        if last_triggered:
            lt = datetime.fromisoformat(last_triggered)
            if (now - lt).total_seconds() < cooldown_s:
                continue

        # Get latest metric value
        row = conn.execute("""
            SELECT metric_value FROM task_metrics
            WHERE metric_name=? ORDER BY id DESC LIMIT 1
        """, (metric_name,)).fetchone()
        if not row:
            continue

        value = row[0]
        if (direction == "above" and value > threshold) or \
           (direction == "below" and value < threshold):
            triggered.append(task_id)
            conn.execute("""
                UPDATE task_events SET last_triggered=?, trigger_count=trigger_count+1
                WHERE id=?
            """, (now.isoformat(), eid))

    conn.commit()
    conn.close()
    return triggered


def process_events():
    """Process all event triggers. Returns count of tasks triggered."""
    triggered_ids = set()
    triggered_ids.update(check_file_events())
    triggered_ids.update(check_threshold_events())

    if not triggered_ids:
        return 0

    logger.info("Events triggered %d tasks: %s", len(triggered_ids), ", ".join(triggered_ids))
    for task_id in triggered_ids:
        run_single_task(task_id)

    return len(triggered_ids)


# ── Metrics Collector ──────────────────────────────────────────────────────

def record_metric(name: str, value: float, tags: dict = None):
    """Record a system metric data point."""
    conn = get_db()
    conn.execute("""
        INSERT INTO task_metrics (metric_name, metric_value, tags)
        VALUES (?, ?, ?)
    """, (name, value, json.dumps(tags or {})))
    conn.commit()
    conn.close()


def collect_system_metrics():
    """Collect system-wide metrics and store them."""
    # GPU metrics
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu,memory.used,memory.total,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0:
            for i, line in enumerate(r.stdout.strip().splitlines()):
                parts = [x.strip() for x in line.split(",")]
                if len(parts) >= 4:
                    record_metric(f"gpu{i}_temp", float(parts[0]))
                    record_metric(f"gpu{i}_vram_used", float(parts[1]))
                    record_metric(f"gpu{i}_vram_total", float(parts[2]))
                    record_metric(f"gpu{i}_util", float(parts[3]))
    except Exception:
        pass

    # Disk metrics
    try:
        import shutil
        for drive in ["C:/", "F:/"]:
            usage = shutil.disk_usage(drive)
            label = drive[0].lower()
            record_metric(f"disk_{label}_free_gb", usage.free / 1024**3)
            record_metric(f"disk_{label}_used_pct", usage.used * 100 / usage.total)
    except Exception:
        pass

    # Orchestrator metrics
    try:
        conn = get_db()
        total = conn.execute("SELECT count(*) FROM task_runs").fetchone()[0]
        ok = conn.execute("SELECT count(*) FROM task_runs WHERE status='completed'").fetchone()[0]
        fail = conn.execute("SELECT count(*) FROM task_runs WHERE status='failed'").fetchone()[0]
        conn.close()
        record_metric("orch_total_runs", float(total))
        record_metric("orch_success_rate", ok * 100.0 / max(total, 1))
        record_metric("orch_fail_count", float(fail))
    except Exception:
        pass

    # Cluster health (count of online nodes)
    online = 0
    for name in ["M1", "OL1", "M2", "M3"]:
        if check_node_health(name):
            online += 1
    record_metric("cluster_nodes_online", float(online))


def get_metrics_summary(metric_name: str, hours: int = 24) -> dict:
    """Get summary stats for a metric over the last N hours."""
    conn = get_db()
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    rows = conn.execute("""
        SELECT metric_value FROM task_metrics
        WHERE metric_name=? AND recorded_at > ?
        ORDER BY recorded_at
    """, (metric_name, cutoff)).fetchall()
    conn.close()

    if not rows:
        return {"count": 0}
    values = [r[0] for r in rows]
    return {
        "count": len(values),
        "min": min(values),
        "max": max(values),
        "avg": sum(values) / len(values),
        "latest": values[-1],
    }


# ── Task Chain with Data Passing ───────────────────────────────────────────

def execute_pipeline_with_data(task: TaskDef) -> TaskResult:
    """Enhanced pipeline: output of each step is available to the next via {{step_N_output}}."""
    steps = task.payload.get("steps", [])
    results = []
    chain_data = {}
    t0 = time.monotonic()
    chain_id = f"{task.id}_{int(time.time())}"

    for i, step in enumerate(steps):
        # Template substitution: replace {{step_N_output}} placeholders
        step_payload = json.dumps(step.get("payload", {}))
        for k, v in chain_data.items():
            step_payload = step_payload.replace(f"{{{{{k}}}}}", str(v).replace('"', '\\"')[:500])
        try:
            resolved_payload = json.loads(step_payload)
        except json.JSONDecodeError:
            resolved_payload = step.get("payload", {})

        step_task = TaskDef(
            id=f"{task.id}_step{i}",
            name=f"{task.name} step {i}",
            task_type=step.get("type", "quick"),
            action=step.get("action", "script"),
            payload=resolved_payload,
            timeout_s=step.get("timeout", 120),
            retry_max=0,
        )

        # Resource check before heavy steps
        ok, reason = check_resource_availability(step_task)
        if not ok:
            logger.warning("Resource check failed for step %d: %s", i, reason)
            results.append({"step": i, "status": "skipped", "output": f"Resource: {reason}"})
            if step.get("required", True):
                dur = (time.monotonic() - t0) * 1000
                return TaskResult(task.id, "failed", output=json.dumps(results, indent=2),
                                  error=f"Step {i} skipped: {reason}", duration_ms=dur)
            continue

        result = execute_task(step_task)
        results.append({"step": i, "status": result.status, "output": result.output[:500]})

        # Store output for next steps
        chain_data[f"step_{i}_output"] = result.output.strip()[:1000]
        chain_data[f"step_{i}_status"] = result.status

        # Save chain state to DB for inspection
        conn = get_db()
        conn.execute("""
            INSERT OR REPLACE INTO task_chain_state (chain_id, step_index, output_key, output_value)
            VALUES (?, ?, 'output', ?)
        """, (chain_id, i, result.output[:2000]))
        conn.commit()
        conn.close()

        # Branch/stop logic
        if task.branch_on and result.status in task.branch_on:
            branch = task.branch_on[result.status]
            if branch == "stop":
                dur = (time.monotonic() - t0) * 1000
                final_status = "failed" if result.status == "failed" else "completed"
                return TaskResult(task.id, final_status, output=json.dumps(results, indent=2),
                                  error=f"Stopped at step {i}", duration_ms=dur)
            elif branch == "skip_rest":
                break
            elif isinstance(branch, str) and branch.startswith("goto:"):
                target = int(branch[5:])
                steps = steps[target:]
                continue

        if result.status == "failed" and step.get("required", True):
            dur = (time.monotonic() - t0) * 1000
            return TaskResult(task.id, "failed", output=json.dumps(results, indent=2),
                              error=f"Step {i} failed: {result.error[:200]}", duration_ms=dur)

    dur = (time.monotonic() - t0) * 1000
    return TaskResult(task.id, "completed", output=json.dumps(results, indent=2), duration_ms=dur)


# ── Additional Branch Conditions ───────────────────────────────────────────

def check_branch_condition(condition: dict) -> str:
    """Extended branch condition checker. Returns branch key string."""
    check_type = condition.get("type", "script")

    if check_type == "http_status":
        url = condition.get("url", "")
        expected = condition.get("expected", 200)
        try:
            r = subprocess.run(
                ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "5", url],
                capture_output=True, text=True, timeout=10,
            )
            code = int(r.stdout.strip())
            return "ok" if code == expected else "error"
        except Exception:
            return "error"

    elif check_type == "port_open":
        host = condition.get("host", "127.0.0.1")
        port = condition.get("port", 80)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3)
            result = s.connect_ex((host, port))
            s.close()
            return "open" if result == 0 else "closed"
        except Exception:
            return "error"

    elif check_type == "memory_usage":
        threshold_pct = condition.get("threshold_pct", 85)
        try:
            import psutil
            mem = psutil.virtual_memory()
            return "high" if mem.percent > threshold_pct else "ok"
        except ImportError:
            # Fallback without psutil
            try:
                r = subprocess.run(
                    ["wmic", "OS", "get", "FreePhysicalMemory", "/value"],
                    capture_output=True, text=True, timeout=5,
                )
                for line in r.stdout.splitlines():
                    if "FreePhysicalMemory" in line:
                        free_kb = int(line.split("=")[1].strip())
                        # If less than 2GB free, consider high
                        return "high" if free_kb < 2 * 1024 * 1024 else "ok"
            except Exception:
                pass
            return "ok"

    elif check_type == "service_status":
        service = condition.get("service", "")
        try:
            r = subprocess.run(
                ["sc", "query", service],
                capture_output=True, text=True, timeout=10,
            )
            if "RUNNING" in r.stdout:
                return "running"
            elif "STOPPED" in r.stdout:
                return "stopped"
            return "unknown"
        except Exception:
            return "error"

    elif check_type == "env_var":
        var_name = condition.get("var", "")
        expected = condition.get("expected", "")
        value = os.environ.get(var_name, "")
        if expected:
            return "match" if value == expected else "mismatch"
        return "set" if value else "unset"

    elif check_type == "recent_task_status":
        target_task = condition.get("task_id", "")
        try:
            conn = get_db()
            row = conn.execute("""
                SELECT status FROM task_runs WHERE task_id=?
                ORDER BY id DESC LIMIT 1
            """, (target_task,)).fetchone()
            conn.close()
            return row[0] if row else "never_run"
        except Exception:
            return "error"

    elif check_type == "cluster_quorum":
        min_nodes = condition.get("min_nodes", 2)
        online = sum(1 for n in ["M1", "OL1", "M2", "M3"] if check_node_health(n))
        return "quorum" if online >= min_nodes else "no_quorum"

    elif check_type == "error_rate":
        task_id = condition.get("task_id", "")
        window_min = condition.get("window_min", 60)
        threshold_pct = condition.get("threshold_pct", 50)
        try:
            conn = get_db()
            cutoff = (datetime.now() - timedelta(minutes=window_min)).isoformat()
            total = conn.execute("SELECT count(*) FROM task_runs WHERE task_id=? AND started_at>?", (task_id, cutoff)).fetchone()[0]
            fails = conn.execute("SELECT count(*) FROM task_runs WHERE task_id=? AND status='failed' AND started_at>?", (task_id, cutoff)).fetchone()[0]
            conn.close()
            if total == 0:
                return "no_data"
            rate = fails * 100 / total
            return "high" if rate > threshold_pct else "ok"
        except Exception:
            return "error"

    return "unknown"


# ── Enhanced execute_branch with new conditions ────────────────────────────

# Extend the existing execute_branch by injecting extended checks
_EXTENDED_CONDITIONS = {
    "http_status", "port_open", "memory_usage", "service_status",
    "env_var", "recent_task_status", "cluster_quorum", "error_rate",
}


# ── Dashboard Data Export ──────────────────────────────────────────────────

def export_dashboard_data() -> dict:
    """Export orchestrator state for Electron dashboard consumption."""
    conn = get_db()

    # Task summary
    tasks = conn.execute("SELECT id, name, task_type, priority, enabled FROM tasks").fetchall()
    schedules = {r[0]: {"last_run": r[1], "next_run": r[2], "run_count": r[3], "fail_count": r[4], "avg_ms": r[5]}
                 for r in conn.execute("SELECT task_id, last_run, next_run, run_count, fail_count, avg_duration_ms FROM task_schedule").fetchall()}

    # Recent runs
    recent = conn.execute("""
        SELECT task_id, status, duration_ms, node, started_at
        FROM task_runs ORDER BY id DESC LIMIT 50
    """).fetchall()

    # Escalation states
    escalations = conn.execute("""
        SELECT task_id, consecutive_fails, level_1_threshold, level_2_threshold
        FROM task_escalation WHERE consecutive_fails > 0
    """).fetchall()

    # Metric snapshots (latest of each)
    metrics = {}
    for row in conn.execute("""
        SELECT metric_name, metric_value, recorded_at FROM task_metrics
        WHERE id IN (SELECT MAX(id) FROM task_metrics GROUP BY metric_name)
    """).fetchall():
        metrics[row[0]] = {"value": row[1], "at": row[2]}

    conn.close()

    return {
        "generated_at": datetime.now().isoformat(),
        "task_count": len(tasks),
        "tasks": [{"id": t[0], "name": t[1], "type": t[2], "priority": t[3],
                    "schedule": schedules.get(t[0], {})} for t in tasks],
        "recent_runs": [{"task_id": r[0], "status": r[1], "ms": r[2], "node": r[3], "at": r[4]} for r in recent],
        "escalations": [{"task_id": e[0], "consecutive_fails": e[1]} for e in escalations],
        "metrics": metrics,
    }


# ── Task Templates (dynamic task spawning) ─────────────────────────────────

TASK_TEMPLATES = {
    "cluster_query_template": lambda prompt, route="quick", timeout=15: TaskDef(
        id=f"dynamic_query_{int(time.time())}",
        name=f"Dynamic Query: {prompt[:30]}",
        task_type=route,
        action="cluster_query",
        payload={"prompt": prompt, "route": route, "timeout": timeout},
        retry_max=1,
    ),
    "health_check_template": lambda node_name: TaskDef(
        id=f"dynamic_health_{node_name}_{int(time.time())}",
        name=f"Dynamic Health: {node_name}",
        task_type="health",
        action="branch",
        payload={
            "condition": {"type": "port_open", "host": NODES.get(node_name, {}).get("host", "127.0.0.1"),
                          "port": NODES.get(node_name, {}).get("port", 1234)},
            "branches": {
                "open": {"action": "python", "payload": {"code": f"print('{node_name} is UP')"}},
                "closed": {"action": "python", "payload": {"code": f"print('{node_name} is DOWN')"}},
            },
        },
    ),
    "backup_template": lambda db_path: TaskDef(
        id=f"dynamic_backup_{int(time.time())}",
        name=f"Dynamic Backup: {db_path}",
        task_type="backup",
        action="python",
        payload={"code": f"""
import shutil, sqlite3
from pathlib import Path
from datetime import datetime
src = Path('F:/BUREAU/turbo') / '{db_path}'
dst = Path('F:/BUREAU/turbo/backups') / f'{{src.stem}}_{{datetime.now():%Y%m%d_%H%M%S}}.db'
dst.parent.mkdir(exist_ok=True)
shutil.copy2(str(src), str(dst))
c = sqlite3.connect(str(dst))
print(f"OK: {{dst.name}} ({{c.execute('PRAGMA integrity_check').fetchone()[0]}})")
c.close()
"""},
    ),
}


def spawn_dynamic_task(template_name: str, *args, **kwargs) -> TaskResult:
    """Create and immediately execute a task from a template."""
    template = TASK_TEMPLATES.get(template_name)
    if not template:
        return TaskResult("dynamic", "failed", error=f"Unknown template: {template_name}")
    task = template(*args, **kwargs)
    result = execute_task(task)
    record_run(result)
    return result


# ── Self-Monitoring ────────────────────────────────────────────────────────

def orchestrator_self_check() -> dict:
    """Check orchestrator's own health."""
    issues = []
    conn = get_db()

    # DB size
    db_size = Path(DB_PATH).stat().st_size / 1024**2
    if db_size > 100:
        issues.append(f"DB too large: {db_size:.1f}MB")

    # Stuck tasks (next_run far in the past)
    cutoff = (datetime.now() - timedelta(hours=2)).isoformat()
    stuck = conn.execute("""
        SELECT t.id FROM tasks t JOIN task_schedule s ON t.id=s.task_id
        WHERE t.enabled=1 AND s.next_run < ? AND s.next_run != ''
    """, (cutoff,)).fetchall()
    if len(stuck) > 10:
        issues.append(f"{len(stuck)} tasks overdue by >2h")

    # High failure rate (last hour)
    hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
    total = conn.execute("SELECT count(*) FROM task_runs WHERE started_at>?", (hour_ago,)).fetchone()[0]
    fails = conn.execute("SELECT count(*) FROM task_runs WHERE status='failed' AND started_at>?", (hour_ago,)).fetchone()[0]
    if total > 0 and fails / total > 0.5:
        issues.append(f"High failure rate: {fails}/{total} in last hour")

    # Metrics table bloat
    metrics_count = conn.execute("SELECT count(*) FROM task_metrics").fetchone()[0]
    if metrics_count > 100000:
        issues.append(f"Metrics table bloat: {metrics_count} rows")

    conn.close()

    return {
        "status": "healthy" if not issues else "degraded",
        "db_size_mb": round(db_size, 1),
        "issues": issues,
    }


def cleanup_old_data(days: int = 30):
    """Clean up old metrics and run history."""
    conn = get_db()
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    # Keep last N runs per task
    conn.execute("""
        DELETE FROM task_runs WHERE id NOT IN (
            SELECT id FROM (
                SELECT id, ROW_NUMBER() OVER (PARTITION BY task_id ORDER BY id DESC) as rn
                FROM task_runs
            ) WHERE rn <= 100
        )
    """)
    # Trim metrics
    conn.execute("DELETE FROM task_metrics WHERE recorded_at < ?", (cutoff,))
    # Trim chain state
    conn.execute("DELETE FROM task_chain_state WHERE created_at < ?", (cutoff,))
    conn.commit()
    deleted = conn.total_changes
    conn.close()
    return deleted


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
            payload={"script": "scripts/jarvis_unified_boot.py", "args": ["--status"]},
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
                "condition": {"type": "port_open", "host": "127.0.0.1", "port": 18789},
                "branches": {
                    "open": {
                        "action": "python",
                        "payload": {"code": """
import subprocess
r = subprocess.run(["curl","-s","--max-time","3","http://127.0.0.1:18789/health"],
    capture_output=True, text=True, timeout=5)
print(f"OpenClaw: {'OK' if r.returncode==0 else 'ERROR'} {r.stdout[:80]}")
"""},
                    },
                    "closed": {
                        "action": "python",
                        "payload": {"code": """
import subprocess, os
print("OpenClaw not running - starting...")
openclaw_cmd = os.path.expandvars(r'%APPDATA%\\npm\\openclaw.cmd')
if os.path.exists(openclaw_cmd):
    subprocess.Popen([openclaw_cmd, 'serve'], creationflags=0x00000008,
                     cwd='F:/BUREAU/turbo', shell=True)
    print("OpenClaw start initiated")
else:
    print(f"OpenClaw binary not found: {openclaw_cmd}")
"""},
                    },
                    "error": {
                        "action": "python",
                        "payload": {"code": "print('OpenClaw port check error')"},
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

        # ══════════════════════════════════════════════════════════════════
        # PHASE 3 — Event-driven, Escalation, Metrics, Self-monitoring
        # ══════════════════════════════════════════════════════════════════

        # ── System Metrics Collector ──
        TaskDef(
            id="metrics_collector",
            name="System Metrics Collector",
            task_type="health",
            action="python",
            payload={"code": """
import sys, os, subprocess, json, sqlite3
sys.path.insert(0, 'F:/BUREAU/turbo')
from pathlib import Path
TURBO = Path('F:/BUREAU/turbo')
DB = str(TURBO / 'data/task_orchestrator.db')
conn = sqlite3.connect(DB)
def rec(name, val):
    conn.execute('INSERT INTO task_metrics (metric_name,metric_value) VALUES (?,?)',(name,val))
# GPU
try:
    r = subprocess.run(['nvidia-smi','--query-gpu=temperature.gpu,memory.used,utilization.gpu',
        '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=5)
    for i, line in enumerate(r.stdout.strip().splitlines()):
        p = [x.strip() for x in line.split(',')]
        rec(f'gpu{i}_temp', float(p[0]))
        rec(f'gpu{i}_vram_mb', float(p[1]))
        rec(f'gpu{i}_util', float(p[2]))
except: pass
# Disk
import shutil
for d in ['C:/','F:/']:
    u = shutil.disk_usage(d)
    rec(f'disk_{d[0].lower()}_free_gb', u.free/1024**3)
# Cluster nodes
for name, url in [('m1','127.0.0.1:1234/v1/models'),('ol1','127.0.0.1:11434/api/tags')]:
    try:
        r = subprocess.run(['curl','-s','--max-time','2',f'http://{url}'],
            capture_output=True, text=True, timeout=4)
        rec(f'cluster_{name}_online', 1.0 if r.returncode==0 and len(r.stdout)>10 else 0.0)
    except: rec(f'cluster_{name}_online', 0.0)
# Python processes
output = os.popen('tasklist /FI "IMAGENAME eq python.exe" /FO CSV 2>NUL').read()
rec('python_processes', float(len([l for l in output.strip().splitlines()[1:] if l.strip()])))
conn.commit()
conn.close()
print('Metrics collected')
"""},
            priority="low",
            schedule="every:5m",
            tags=["metrics", "monitoring"],
        ),

        # ── Orchestrator Self-Health ──
        TaskDef(
            id="orch_self_health",
            name="Orchestrator Self-Health",
            task_type="health",
            action="python",
            payload={"code": """
import sqlite3, json
from pathlib import Path
from datetime import datetime, timedelta
DB = str(Path('F:/BUREAU/turbo/data/task_orchestrator.db'))
conn = sqlite3.connect(DB)
issues = []
# DB size
db_mb = Path(DB).stat().st_size / 1024**2
if db_mb > 50: issues.append(f'DB large: {db_mb:.1f}MB')
# Overdue tasks
cutoff = (datetime.now() - timedelta(hours=2)).isoformat()
stuck = conn.execute("SELECT count(*) FROM tasks t JOIN task_schedule s ON t.id=s.task_id WHERE t.enabled=1 AND s.next_run<? AND s.next_run!=''", (cutoff,)).fetchone()[0]
if stuck > 10: issues.append(f'{stuck} tasks overdue >2h')
# Failure rate (last hour)
h = (datetime.now() - timedelta(hours=1)).isoformat()
total = conn.execute("SELECT count(*) FROM task_runs WHERE started_at>?", (h,)).fetchone()[0]
fails = conn.execute("SELECT count(*) FROM task_runs WHERE status='failed' AND started_at>?", (h,)).fetchone()[0]
if total > 5 and fails/total > 0.4: issues.append(f'High fail rate: {fails}/{total}')
# Metrics bloat
mc = conn.execute("SELECT count(*) FROM task_metrics").fetchone()[0]
if mc > 50000: issues.append(f'Metrics: {mc} rows (trim needed)')
conn.close()
if issues:
    print(f'DEGRADED: {"; ".join(issues)}')
    exit(1)
else:
    print(f'HEALTHY: DB={db_mb:.1f}MB, runs_1h={total}, metrics={mc}')
"""},
            priority="normal",
            schedule="every:30m",
            tags=["health", "self-monitoring"],
        ),

        # ── Metrics Cleanup (daily trim) ──
        TaskDef(
            id="metrics_cleanup",
            name="Metrics Data Cleanup",
            task_type="schedule",
            action="python",
            payload={"code": """
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
DB = str(Path('F:/BUREAU/turbo/data/task_orchestrator.db'))
conn = sqlite3.connect(DB)
cutoff = (datetime.now() - timedelta(days=7)).isoformat()
conn.execute('DELETE FROM task_metrics WHERE recorded_at < ?', (cutoff,))
conn.execute('DELETE FROM task_chain_state WHERE created_at < ?', (cutoff,))
# Keep last 200 runs per task
conn.execute('''DELETE FROM task_runs WHERE id NOT IN (
    SELECT id FROM (SELECT id, ROW_NUMBER() OVER (PARTITION BY task_id ORDER BY id DESC) as rn FROM task_runs) WHERE rn <= 200)''')
changes = conn.total_changes
conn.commit()
conn.close()
print(f'Cleaned {changes} old records')
"""},
            priority="low",
            schedule="daily:04:30",
            tags=["cleanup", "metrics"],
        ),

        # ── WS Server Health (port check) ──
        TaskDef(
            id="ws_server_health",
            name="WebSocket Server Health",
            task_type="health",
            action="branch",
            payload={
                "condition": {"type": "port_open", "host": "127.0.0.1", "port": 9742},
                "branches": {
                    "open": {"action": "python", "payload": {"code": """
import subprocess
r = subprocess.run(['curl','-s','--max-time','2','http://127.0.0.1:9742/health'],
    capture_output=True, text=True, timeout=5)
print(f"WS Server: {'OK' if r.returncode==0 else 'ERROR'} {r.stdout[:80]}")
"""}},
                    "closed": {"action": "python", "payload": {"code": """
import subprocess
print('WS Server DOWN - attempting restart...')
subprocess.Popen(['python','python_ws/server.py'], cwd='F:/BUREAU/turbo', creationflags=0x00000008)
print('WS restart initiated')
"""}},
                },
            },
            priority="high",
            schedule="every:5m",
            tags=["health", "ws", "auto-heal"],
        ),

        # ── Gemini Proxy Health ──
        TaskDef(
            id="gemini_proxy_health",
            name="Gemini Proxy Health",
            task_type="health",
            action="branch",
            payload={
                "condition": {"type": "process_running", "process": "node.exe"},
                "branches": {
                    "running": {"action": "python", "payload": {"code": """
import subprocess
# Test gemini proxy
r = subprocess.run(['node','F:/BUREAU/turbo/gemini-proxy.js','--ping'],
    capture_output=True, text=True, timeout=10)
if r.returncode == 0:
    print(f'Gemini proxy: OK')
else:
    print(f'Gemini proxy: ERROR {r.stderr[:60]}')
"""}},
                    "stopped": {"action": "python", "payload": {"code": "print('Node not running')"}},
                },
            },
            priority="low",
            schedule="every:30m",
            tags=["health", "gemini"],
        ),

        # ── M2/M3 Cluster Failover Monitor ──
        TaskDef(
            id="cluster_failover",
            name="Cluster Failover Monitor",
            task_type="health",
            action="branch",
            payload={
                "condition": {"type": "cluster_quorum", "min_nodes": 2},
                "branches": {
                    "quorum": {"action": "python", "payload": {"code": """
import subprocess, json
online = []
for name, url in [('M1','127.0.0.1:1234/v1/models'),('OL1','127.0.0.1:11434/api/tags'),
                   ('M2','192.168.1.26:1234/v1/models'),('M3','192.168.1.113:1234/v1/models')]:
    try:
        r = subprocess.run(['curl','-s','--max-time','3',f'http://{url}'],
            capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and len(r.stdout) > 10:
            online.append(name)
    except: pass
print(f'Quorum OK: {len(online)}/4 nodes online ({", ".join(online)})')
"""}},
                    "no_quorum": {"action": "python", "payload": {"code": """
import subprocess
print('WARNING: Cluster quorum lost (<2 nodes online)')
print('Attempting recovery...')
# Try restarting Ollama
try:
    r = subprocess.run(['curl','-s','--max-time','2','http://127.0.0.1:11434/api/tags'],
        capture_output=True, text=True, timeout=4)
    if r.returncode != 0:
        subprocess.Popen(['ollama','serve'], creationflags=0x00000008)
        print('Ollama restart attempted')
except: print('Ollama restart failed')
"""}},
                },
            },
            priority="high",
            schedule="every:10m",
            tags=["health", "cluster", "failover"],
        ),

        # ── Error Rate Monitor ──
        TaskDef(
            id="error_rate_monitor",
            name="Error Rate Monitor",
            task_type="health",
            action="python",
            payload={"code": """
import sqlite3, json
from pathlib import Path
from datetime import datetime, timedelta
DB = str(Path('F:/BUREAU/turbo/data/task_orchestrator.db'))
conn = sqlite3.connect(DB)
cutoff = (datetime.now() - timedelta(hours=1)).isoformat()
# Per-task error rates
rows = conn.execute('''
    SELECT task_id,
        SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as ok,
        SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as fail
    FROM task_runs WHERE started_at > ?
    GROUP BY task_id HAVING fail > 0
    ORDER BY fail DESC
''', (cutoff,)).fetchall()
conn.close()
if not rows:
    print('No failures in last hour')
else:
    print(f'{len(rows)} tasks with failures:')
    for tid, ok, fail in rows:
        rate = fail * 100 / (ok + fail) if (ok + fail) > 0 else 0
        alert = ' [CRITICAL]' if rate > 75 else ' [WARNING]' if rate > 50 else ''
        print(f'  {tid}: {fail} fails / {ok+fail} runs ({rate:.0f}%){alert}')
"""},
            priority="normal",
            schedule="every:30m",
            tags=["monitoring", "error-rate"],
        ),

        # ── Dashboard Data Export ──
        TaskDef(
            id="dashboard_export",
            name="Dashboard Data Export",
            task_type="schedule",
            action="python",
            payload={"code": """
import sqlite3, json
from pathlib import Path
from datetime import datetime, timedelta
TURBO = Path('F:/BUREAU/turbo')
DB = str(TURBO / 'data/task_orchestrator.db')
conn = sqlite3.connect(DB)
# Tasks
tasks = conn.execute('SELECT id,name,task_type,priority,enabled FROM tasks').fetchall()
# Schedules
scheds = {r[0]:{'last':r[1],'next':r[2],'runs':r[3],'fails':r[4],'avg_ms':r[5]}
    for r in conn.execute('SELECT task_id,last_run,next_run,run_count,fail_count,avg_duration_ms FROM task_schedule').fetchall()}
# Recent runs
recent = [{'id':r[0],'status':r[1],'ms':r[2],'node':r[3],'at':r[4]}
    for r in conn.execute('SELECT task_id,status,duration_ms,node,started_at FROM task_runs ORDER BY id DESC LIMIT 30').fetchall()]
# Metrics (latest)
metrics = {}
for r in conn.execute('SELECT metric_name,metric_value,recorded_at FROM task_metrics WHERE id IN (SELECT MAX(id) FROM task_metrics GROUP BY metric_name)').fetchall():
    metrics[r[0]] = {'v':r[1],'at':r[2]}
conn.close()
data = {
    'generated': datetime.now().isoformat(),
    'tasks': [{'id':t[0],'name':t[1],'type':t[2],'prio':t[3],'sched':scheds.get(t[0],{})} for t in tasks],
    'recent': recent, 'metrics': metrics, 'task_count': len(tasks)
}
out = TURBO / 'data' / 'dashboard_orchestrator.json'
out.write_text(json.dumps(data, indent=2, default=str), encoding='utf-8')
print(f'Dashboard export: {len(tasks)} tasks, {len(recent)} runs, {len(metrics)} metrics -> {out.name}')
"""},
            priority="low",
            schedule="every:10m",
            tags=["dashboard", "export"],
        ),

        # ── Watchdog: Telegram Bot Process ──
        TaskDef(
            id="telegram_bot_watchdog",
            name="Telegram Bot Watchdog",
            task_type="health",
            action="branch",
            payload={
                "condition": {"type": "process_running", "process": "node.exe"},
                "branches": {
                    "running": {"action": "python", "payload": {"code": """
from pathlib import Path
lock = Path('F:/BUREAU/turbo/.telegram-bot.lock')
if lock.exists():
    pid = lock.read_text().strip()
    print(f'Telegram bot lock: PID {pid}')
    import os
    output = os.popen(f'tasklist /FI "PID eq {pid}" /FO CSV 2>NUL').read()
    if pid in output:
        print('Telegram bot: RUNNING')
    else:
        print('Telegram bot: STALE LOCK (process dead)')
        lock.unlink()
else:
    print('Telegram bot: NO LOCK (probably not running)')
"""}},
                    "stopped": {"action": "python", "payload": {"code": "print('Node.exe not running')"}},
                },
            },
            priority="low",
            schedule="every:15m",
            tags=["health", "telegram", "watchdog"],
        ),

        # ── HuggingFace Cache Monitor ──
        TaskDef(
            id="hf_cache_monitor",
            name="HuggingFace Cache Monitor",
            task_type="health",
            action="python",
            payload={"code": """
from pathlib import Path
hf_cache = Path.home() / '.cache' / 'huggingface'
if hf_cache.exists():
    total = sum(f.stat().st_size for f in hf_cache.rglob('*') if f.is_file())
    gb = total / 1024**3
    print(f'HuggingFace cache: {gb:.1f}GB')
    if gb > 50:
        print(f'WARNING: Cache exceeds 50GB, consider cleanup')
    else:
        print('Cache size OK')
else:
    print('No HuggingFace cache found')
"""},
            priority="low",
            schedule="daily:05:00",
            tags=["monitoring", "disk", "huggingface"],
        ),

        # ── Git Uncommitted Alert ──
        TaskDef(
            id="git_uncommitted_alert",
            name="Git Uncommitted Changes Alert",
            task_type="sync",
            action="branch",
            payload={
                "condition": {"type": "script", "code": """
import subprocess
r = subprocess.run(['git','status','--porcelain','-u'],
    capture_output=True, text=True, cwd='F:/BUREAU/turbo')
changes = len([l for l in r.stdout.splitlines() if l.strip()])
exit(0 if changes > 30 else 1)
"""},
                "branches": {
                    "success": {"action": "python", "payload": {"code": """
import subprocess
r = subprocess.run(['git','status','--porcelain','-u'],
    capture_output=True, text=True, cwd='F:/BUREAU/turbo')
changes = len([l for l in r.stdout.splitlines() if l.strip()])
print(f'WARNING: {changes} uncommitted changes! Consider committing.')
r2 = subprocess.run(['git','diff','--stat','--cached'],
    capture_output=True, text=True, cwd='F:/BUREAU/turbo')
if r2.stdout.strip():
    print(f'Staged: {r2.stdout.strip().splitlines()[-1]}')
"""}},
                    "failure": {"action": "python", "payload": {"code": """
import subprocess
r = subprocess.run(['git','status','--porcelain','-u'],
    capture_output=True, text=True, cwd='F:/BUREAU/turbo')
changes = len([l for l in r.stdout.splitlines() if l.strip()])
print(f'Git OK: {changes} changes (under threshold)')
"""}},
                },
            },
            priority="low",
            schedule="every:2h",
            tags=["sync", "git", "alert"],
        ),

        # ── Python Environment Health ──
        TaskDef(
            id="python_env_health",
            name="Python Environment Health",
            task_type="health",
            action="python",
            payload={"code": """
import sys, importlib
print(f'Python: {sys.version.split()[0]}')
print(f'Path: {sys.executable}')
# Check critical imports
critical = ['pytest','requests','fastapi','websockets','sqlite3']
ok = missing = 0
for mod in critical:
    try:
        importlib.import_module(mod)
        ok += 1
    except ImportError:
        missing += 1
        print(f'  MISSING: {mod}')
print(f'Modules: {ok}/{len(critical)} OK')
# Check venv
venv = 'F:/BUREAU/turbo/.venv'
from pathlib import Path
if Path(venv).exists():
    print(f'venv: OK ({venv})')
else:
    print('venv: NOT FOUND')
"""},
            priority="low",
            schedule="daily:06:30",
            tags=["health", "python"],
        ),

        # ── Port Conflict Detector ──
        TaskDef(
            id="port_conflict_check",
            name="Port Conflict Detector",
            task_type="health",
            action="python",
            payload={"code": """
import socket
ports = {
    1234: 'LM Studio (M1)',
    9742: 'JARVIS WS Server',
    11434: 'Ollama',
    18789: 'OpenClaw Gateway',
    18800: 'Canvas Proxy',
}
conflicts = []
for port, name in ports.items():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        result = s.connect_ex(('127.0.0.1', port))
        s.close()
        status = 'OPEN' if result == 0 else 'CLOSED'
        print(f'  :{port} {name}: {status}')
    except Exception as e:
        print(f'  :{port} {name}: ERROR {e}')
"""},
            priority="low",
            schedule="every:30m",
            tags=["health", "network"],
        ),

        # ── Full Weekly Pipeline (comprehensive) ──
        TaskDef(
            id="weekly_full_pipeline",
            name="Weekly Full Pipeline",
            task_type="pipeline",
            action="pipeline",
            payload={"steps": [
                {"action": "python", "type": "health", "payload": {"code": """
import subprocess, json
nodes_ok = 0
for name, url in [('M1','127.0.0.1:1234/v1/models'),('OL1','127.0.0.1:11434/api/tags')]:
    try:
        r = subprocess.run(['curl','-s','--max-time','3',f'http://{url}'],
            capture_output=True, text=True, timeout=5)
        if r.returncode == 0: nodes_ok += 1
    except: pass
print(f'Cluster: {nodes_ok}/2 nodes online')
"""}, "required": True},
                {"action": "python", "type": "audit", "payload": {"code": """
import sys; sys.path.insert(0, 'F:/BUREAU/turbo')
from src.auto_fixer import AutoFixer
from src.auto_auditor import AutoAuditor
AutoFixer().run_fix_cycle(dry_run=False)
r = AutoAuditor().run_full_audit()
print(f'Audit: {r.summary["score"]}/100, {len(r.findings)} findings')
"""}, "required": False},
                {"action": "python", "type": "test", "payload": {"code": """
import subprocess
r = subprocess.run(['python','-m','pytest','tests/','-x','-q','--tb=no','-k','not integration'],
    capture_output=True, text=True, cwd='F:/BUREAU/turbo', timeout=300)
lines = r.stdout.strip().splitlines()
print(lines[-1] if lines else 'No output')
"""}, "timeout": 300, "required": False},
                {"action": "python", "type": "backup", "payload": {"code": """
import shutil, hashlib, sqlite3
from pathlib import Path
from datetime import datetime
TURBO = Path('F:/BUREAU/turbo')
ts = datetime.now().strftime('%Y%m%d_%H%M%S')
backups = TURBO / 'backups'
backups.mkdir(exist_ok=True)
for db in ['data/jarvis.db','etoile.db','data/sniper.db']:
    src = TURBO / db; dst = backups / f'{src.stem}_{ts}.db'
    shutil.copy2(str(src), str(dst))
    c = sqlite3.connect(str(dst))
    ok = c.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    c.close()
    print(f"{'OK' if ok else 'FAIL'}: {dst.name}")
"""}, "required": True},
                {"action": "python", "type": "sync", "payload": {"code": """
import subprocess
r = subprocess.run(['git','log','--oneline','-5'],
    capture_output=True, text=True, cwd='F:/BUREAU/turbo')
print('Last 5 commits:')
print(r.stdout.strip())
r2 = subprocess.run(['git','status','--porcelain','-u'],
    capture_output=True, text=True, cwd='F:/BUREAU/turbo')
changes = len([l for l in r2.stdout.splitlines() if l.strip()])
print(f'Uncommitted: {changes} files')
"""}, "required": False},
                {"action": "python", "type": "health", "payload": {"code": """
import sqlite3, json
from pathlib import Path
TURBO = Path('F:/BUREAU/turbo')
# Orchestrator stats
c = sqlite3.connect(str(TURBO/'data/task_orchestrator.db'))
total = c.execute('SELECT count(*) FROM task_runs').fetchone()[0]
ok = c.execute("SELECT count(*) FROM task_runs WHERE status='completed'").fetchone()[0]
fail = c.execute("SELECT count(*) FROM task_runs WHERE status='failed'").fetchone()[0]
tasks = c.execute('SELECT count(*) FROM tasks WHERE enabled=1').fetchone()[0]
c.close()
rate = ok*100/max(total,1)
print(f'Orchestrator: {tasks} tasks, {total} runs, {rate:.1f}% success, {fail} fails')
"""}, "required": False},
            ]},
            branch_on={"failed": "stop"},
            priority="normal",
            schedule="weekly:sun:03:00",
            timeout_s=900,
            tags=["pipeline", "weekly", "comprehensive"],
        ),

        # ── Consensus Code Quality ──
        TaskDef(
            id="consensus_code_quality",
            name="Consensus Code Quality Review",
            task_type="consensus",
            action="cluster_query",
            payload={
                "prompt": "Analyse ces metriques de code Python: 228 modules, 3665 fonctions de test, score audit 100/100. Quels sont les 3 domaines a ameliorer en priorite? Propose des actions concretes. Reponds en francais.",
                "route": "consensus",
                "nodes": ["M1", "OL1"],
                "timeout": 20,
            },
            priority="low",
            schedule="weekly:fri:14:00",
            tags=["review", "consensus", "quality"],
        ),

        # ── Escalation Test ──
        TaskDef(
            id="escalation_check",
            name="Escalation Status Check",
            task_type="health",
            action="python",
            payload={"code": """
import sqlite3
from pathlib import Path
DB = str(Path('F:/BUREAU/turbo/data/task_orchestrator.db'))
conn = sqlite3.connect(DB)
try:
    rows = conn.execute('SELECT task_id, consecutive_fails FROM task_escalation WHERE consecutive_fails > 0').fetchall()
except: rows = []
conn.close()
if rows:
    print(f'{len(rows)} tasks with consecutive failures:')
    for tid, fails in rows:
        level = 'CRITICAL' if fails >= 10 else 'ALERT' if fails >= 5 else 'WARN' if fails >= 3 else 'INFO'
        print(f'  [{level}] {tid}: {fails} consecutive fails')
else:
    print('No escalated tasks')
"""},
            priority="normal",
            schedule="every:1h",
            tags=["monitoring", "escalation"],
        ),

        # ── Event Triggers Summary ──
        TaskDef(
            id="event_triggers_report",
            name="Event Triggers Report",
            task_type="schedule",
            action="python",
            payload={"code": """
import sqlite3
from pathlib import Path
DB = str(Path('F:/BUREAU/turbo/data/task_orchestrator.db'))
conn = sqlite3.connect(DB)
try:
    rows = conn.execute('SELECT event_type, source, task_id, trigger_count, last_triggered FROM task_events WHERE enabled=1').fetchall()
except: rows = []
conn.close()
if rows:
    print(f'{len(rows)} active event triggers:')
    for etype, src, tid, cnt, last in rows:
        print(f'  [{etype}] {src[:40]} -> {tid} (triggered {cnt}x, last: {last or "never"})')
else:
    print('No event triggers configured')
"""},
            priority="low",
            schedule="daily:09:00",
            tags=["monitoring", "events"],
        ),

        # ── Memory Pressure Guard ──
        TaskDef(
            id="memory_guard",
            name="Memory Pressure Guard",
            task_type="health",
            action="branch",
            payload={
                "condition": {"type": "memory_usage", "threshold_pct": 90},
                "branches": {
                    "high": {"action": "python", "payload": {"code": """
import os
print('MEMORY PRESSURE - High RAM usage detected')
# List top memory consumers
output = os.popen('tasklist /FO CSV /NH 2>NUL').read()
procs = []
for line in output.strip().splitlines():
    parts = line.replace('"','').split(',')
    if len(parts) >= 5:
        try:
            mem_kb = int(parts[4].replace(' K','').replace(',','').strip())
            procs.append((parts[0], int(parts[1]), mem_kb))
        except: pass
procs.sort(key=lambda x: x[2], reverse=True)
print('Top memory consumers:')
for name, pid, mem in procs[:10]:
    print(f'  {name}: PID {pid}, {mem/1024:.0f}MB')
"""}},
                    "ok": {"action": "python", "payload": {"code": "print('Memory usage OK')"}},
                },
            },
            priority="high",
            schedule="every:15m",
            tags=["health", "memory"],
        ),

        # ── Cowork Scripts Monitor ──
        TaskDef(
            id="cowork_monitor",
            name="Cowork Scripts Monitor",
            task_type="health",
            action="python",
            payload={"code": """
from pathlib import Path
cowork = Path('F:/BUREAU/turbo/cowork/dev')
if cowork.exists():
    scripts = list(cowork.glob('*.py'))
    total_lines = sum(1 for s in scripts for _ in s.read_text(errors='replace').splitlines())
    print(f'Cowork scripts: {len(scripts)} files, {total_lines:,} lines')
    # Check for recent modifications
    from datetime import datetime, timedelta
    recent = [s for s in scripts if datetime.fromtimestamp(s.stat().st_mtime) > datetime.now() - timedelta(days=1)]
    if recent:
        print(f'Recently modified: {len(recent)} scripts')
        for s in recent[:5]:
            print(f'  {s.name}')
else:
    print('Cowork dir not found')
"""},
            priority="low",
            schedule="daily:10:00",
            tags=["monitoring", "cowork"],
        ),

        # ── Windows Scheduled Tasks Sync ──
        TaskDef(
            id="win_tasks_sync",
            name="Windows Tasks Sync Check",
            task_type="sync",
            action="python",
            payload={"code": """
import os
output = os.popen('schtasks /Query /FO CSV /NH 2>NUL').read()
jarvis_tasks = [l for l in output.splitlines() if 'JARVIS' in l]
print(f'Windows JARVIS scheduled tasks: {len(jarvis_tasks)}')
for t in jarvis_tasks:
    parts = t.replace('"','').split(',')
    if len(parts) >= 3:
        print(f'  {parts[0]}: {parts[2]}')
"""},
            priority="low",
            schedule="daily:07:00",
            tags=["sync", "windows"],
        ),

        # ── Backup Verification Pipeline ──
        TaskDef(
            id="backup_verify",
            name="Backup Integrity Verification",
            task_type="backup",
            action="python",
            payload={"code": """
import sqlite3, hashlib
from pathlib import Path
TURBO = Path('F:/BUREAU/turbo')
backups = TURBO / 'backups'
if not backups.exists():
    print('No backups directory')
    exit(0)
verified = failed = 0
for stem in ['jarvis','etoile','sniper']:
    files = sorted(backups.glob(f'{stem}_*.db'), key=lambda f: f.stat().st_mtime, reverse=True)
    if files:
        latest = files[0]
        try:
            c = sqlite3.connect(str(latest))
            r = c.execute('PRAGMA integrity_check').fetchone()[0]
            c.close()
            if r == 'ok':
                verified += 1
                print(f'  OK: {latest.name} ({latest.stat().st_size//1024}KB)')
            else:
                failed += 1
                print(f'  CORRUPT: {latest.name}')
        except Exception as e:
            failed += 1
            print(f'  ERROR: {latest.name}: {e}')
    else:
        print(f'  MISSING: no {stem} backups')
        failed += 1
print(f'Backup verification: {verified} OK, {failed} issues')
if failed: exit(1)
"""},
            priority="normal",
            schedule="every:4h",
            tags=["backup", "verification"],
        ),

        # ── Parallel Cluster Ping ──
        TaskDef(
            id="parallel_cluster_ping",
            name="Parallel Cluster Ping",
            task_type="health",
            action="python",
            payload={"code": """
import subprocess, time, json
from concurrent.futures import ThreadPoolExecutor
def ping_node(name, url):
    t0 = time.monotonic()
    try:
        r = subprocess.run(['curl','-s','--max-time','3',f'http://{url}'],
            capture_output=True, text=True, timeout=5)
        ms = (time.monotonic()-t0)*1000
        if r.returncode == 0 and len(r.stdout) > 10:
            return name, 'OK', ms
        return name, 'DOWN', ms
    except:
        return name, 'TIMEOUT', (time.monotonic()-t0)*1000
nodes = [
    ('M1','127.0.0.1:1234/v1/models'),('OL1','127.0.0.1:11434/api/tags'),
    ('M2','192.168.1.26:1234/v1/models'),('M3','192.168.1.113:1234/v1/models'),
]
with ThreadPoolExecutor(max_workers=4) as pool:
    results = list(pool.map(lambda n: ping_node(n[0],n[1]), nodes))
for name, status, ms in results:
    print(f'  {name}: {status} ({ms:.0f}ms)')
online = sum(1 for _,s,_ in results if s == 'OK')
print(f'Cluster: {online}/{len(nodes)} online')
"""},
            priority="normal",
            schedule="every:5m",
            tags=["health", "cluster", "parallel"],
        ),

        # ── Autonomy Engine Tasks ──
        TaskDef(
            id="autonomy_cycle",
            name="Autonomy Brain Cycle",
            task_type="health",
            action="python",
            payload={"code": """
import subprocess, sys
r = subprocess.run([sys.executable, 'scripts/cluster_autonomy.py', '--status'],
    capture_output=True, text=True, timeout=120, cwd='F:/BUREAU/turbo')
print(r.stdout[-2000:] if len(r.stdout) > 2000 else r.stdout)
if r.returncode != 0:
    print('STDERR:', r.stderr[-500:])
"""},
            priority="high",
            schedule="every:10m",
            tags=["autonomy", "brain", "self-improve"],
        ),

        TaskDef(
            id="autonomy_heal",
            name="Autonomy Self-Healer",
            task_type="health",
            action="python",
            payload={"code": """
import subprocess, sys
r = subprocess.run([sys.executable, 'scripts/cluster_autonomy.py', '--heal'],
    capture_output=True, text=True, timeout=60, cwd='F:/BUREAU/turbo')
print(r.stdout[-2000:] if len(r.stdout) > 2000 else r.stdout)
if r.returncode != 0:
    print('STDERR:', r.stderr[-500:])
"""},
            priority="high",
            schedule="every:5m",
            tags=["autonomy", "heal", "self-repair"],
        ),

        TaskDef(
            id="autonomy_trends",
            name="Autonomy Trend Analyzer",
            task_type="audit",
            action="python",
            payload={"code": """
import subprocess, sys
r = subprocess.run([sys.executable, 'scripts/cluster_autonomy.py', '--trends'],
    capture_output=True, text=True, timeout=60, cwd='F:/BUREAU/turbo')
print(r.stdout[-2000:] if len(r.stdout) > 2000 else r.stdout)
if r.returncode != 0:
    print('STDERR:', r.stderr[-500:])
"""},
            priority="normal",
            schedule="every:1h",
            tags=["autonomy", "trends", "analytics"],
        ),

        TaskDef(
            id="autonomy_optimize",
            name="Autonomy Routing Optimizer",
            task_type="audit",
            action="python",
            payload={"code": """
import subprocess, sys
r = subprocess.run([sys.executable, 'scripts/cluster_autonomy.py', '--optimize'],
    capture_output=True, text=True, timeout=60, cwd='F:/BUREAU/turbo')
print(r.stdout[-2000:] if len(r.stdout) > 2000 else r.stdout)
if r.returncode != 0:
    print('STDERR:', r.stderr[-500:])
"""},
            priority="normal",
            schedule="every:30m",
            tags=["autonomy", "routing", "optimize"],
        ),

        # ══════════════════════════════════════════════════════════════════
        # EVOLUTION ENGINE — Auto-debug, anticipation, learning, benchmark
        # ══════════════════════════════════════════════════════════════════

        # ── 1. Error Anticipation: analyse les patterns AVANT qu'ils deviennent critiques ──
        TaskDef(
            id="error_anticipator",
            name="Error Pattern Anticipator",
            task_type="audit",
            action="python",
            payload={"code": """
import sqlite3, json
from pathlib import Path
from datetime import datetime, timedelta

db = sqlite3.connect(str(Path('F:/BUREAU/turbo/data/task_orchestrator.db')))

# 1. Detect tasks with increasing failure rate (3 periods comparison)
cutoffs = [
    (datetime.now() - timedelta(hours=h)).isoformat() for h in [1, 4, 24]
]
print('=== ERROR ANTICIPATION ===')
rising = []
for task_id, in db.execute('SELECT DISTINCT task_id FROM task_runs').fetchall():
    rates = []
    for i, c in enumerate(cutoffs):
        rows = db.execute(
            'SELECT COUNT(*), SUM(CASE WHEN status=\"failed\" THEN 1 ELSE 0 END) '
            'FROM task_runs WHERE task_id=? AND started_at>?', (task_id, c)).fetchone()
        total, fails = rows[0] or 0, rows[1] or 0
        rates.append(fails / max(1, total))
    # Rising = each period worse than the last
    if rates[0] > rates[1] > rates[2] and rates[0] > 0.3:
        rising.append((task_id, rates))
        print(f'  RISING: {task_id} fail_rate 1h={rates[0]:.0%} 4h={rates[1]:.0%} 24h={rates[2]:.0%}')

# 2. Detect tasks that never ran (zombie definitions)
never_ran = db.execute('''
    SELECT t.id FROM tasks t LEFT JOIN task_runs r ON t.id = r.task_id
    WHERE r.id IS NULL AND t.enabled = 1
''').fetchall()
if never_ran:
    print(f'  ZOMBIE: {len(never_ran)} tasks never executed: {[r[0] for r in never_ran[:5]]}')

# 3. Detect slow tasks getting slower
slow = db.execute('''
    SELECT task_id, AVG(duration_ms) as avg_ms,
           MAX(duration_ms) as max_ms, COUNT(*) as runs
    FROM task_runs WHERE status='completed'
    GROUP BY task_id HAVING avg_ms > 10000 AND runs > 3
    ORDER BY avg_ms DESC LIMIT 5
''').fetchall()
for s in slow:
    print(f'  SLOW: {s[0]} avg={s[1]:.0f}ms max={s[2]:.0f}ms ({s[3]} runs)')

# 4. Disk prediction
import shutil
for drive in ['C:', 'F:']:
    usage = shutil.disk_usage(drive + '/')
    pct = usage.used / usage.total * 100
    free_gb = usage.free / 1e9
    if free_gb < 30:
        print(f'  DISK WARN: {drive} {free_gb:.1f}GB free ({pct:.0f}% used)')

if not rising and not never_ran and not slow:
    print('  No issues anticipated')
db.close()
"""},
            priority="normal",
            schedule="every:30m",
            tags=["evolution", "anticipation", "proactive"],
        ),

        # ── 2. Auto-Debug: diagnostique et corrige automatiquement les tâches qui échouent ──
        TaskDef(
            id="auto_debugger",
            name="Auto-Debugger",
            task_type="audit",
            action="python",
            payload={"code": """
import sqlite3, json, re, os, sys
from pathlib import Path

db = sqlite3.connect(str(Path('F:/BUREAU/turbo/data/task_orchestrator.db')))

# Find tasks that failed 3+ times in last 2 hours
rows = db.execute('''
    SELECT task_id, GROUP_CONCAT(error, '|||') as errors, COUNT(*) as cnt
    FROM task_runs WHERE status='failed'
    AND started_at > datetime('now', '-2 hours')
    GROUP BY task_id HAVING cnt >= 3
    ORDER BY cnt DESC LIMIT 10
''').fetchall()

print('=== AUTO-DEBUGGER ===')
fixes_applied = 0
for task_id, errors_str, cnt in rows:
    errors = (errors_str or '').split('|||')
    latest = errors[-1] if errors else ''
    print(f'  [{cnt}x] {task_id}: {latest[:80]}')

    # Pattern matching for known fixes
    if 'FileNotFoundError' in latest:
        # Extract path and check
        match = re.search(r"'([^']+)'", latest)
        if match:
            missing = match.group(1)
            print(f'    -> Missing file: {missing}')
            # Disable task if script doesn't exist
            if not os.path.exists(missing):
                db.execute('UPDATE tasks SET enabled=0 WHERE id=?', (task_id,))
                print(f'    -> DISABLED {task_id} (missing dependency)')
                fixes_applied += 1

    elif 'TimeoutExpired' in latest or 'Timeout' in latest:
        # Increase timeout
        row = db.execute('SELECT timeout_s FROM tasks WHERE id=?', (task_id,)).fetchone()
        if row and row[0] and row[0] < 300:
            new_timeout = min(row[0] * 2, 300)
            db.execute('UPDATE tasks SET timeout_s=? WHERE id=?', (new_timeout, task_id))
            print(f'    -> Timeout {row[0]}s -> {new_timeout}s')
            fixes_applied += 1

    elif 'ConnectionRefused' in latest or 'Connection refused' in latest:
        print(f'    -> Service down, will be healed by autonomy_heal')

    elif 'PermissionError' in latest:
        print(f'    -> Permission issue, requires manual fix')

db.commit()
db.close()
print(f'  Fixes applied: {fixes_applied}')
"""},
            priority="high",
            schedule="every:15m",
            tags=["evolution", "debug", "auto-fix"],
        ),

        # ── 3. Cluster Load Balancer: distribue le travail sur tous les nœuds ──
        TaskDef(
            id="cluster_load_balance",
            name="Cluster Load Balancer",
            task_type="health",
            action="python",
            payload={"code": """
import subprocess, time, json
from concurrent.futures import ThreadPoolExecutor

nodes = {
    'M1': '127.0.0.1:1234',
    'OL1': '127.0.0.1:11434',
    'M3': '192.168.1.113:1234',
}

def check_load(name, host):
    t0 = time.monotonic()
    try:
        if 'OL1' in name:
            url = f'http://{host}/api/tags'
        else:
            url = f'http://{host}/api/v1/models'
        r = subprocess.run(['curl','-s','--max-time','3',url],
            capture_output=True, text=True, timeout=5)
        ms = (time.monotonic()-t0)*1000
        if r.returncode == 0 and len(r.stdout) > 5:
            data = json.loads(r.stdout)
            if 'data' in data:
                loaded = sum(1 for m in data['data'] if m.get('loaded_instances'))
                return name, 'OK', ms, loaded
            elif 'models' in data:
                return name, 'OK', ms, len(data['models'])
        return name, 'DOWN', ms, 0
    except:
        return name, 'TIMEOUT', (time.monotonic()-t0)*1000, 0

print('=== CLUSTER LOAD BALANCE ===')
with ThreadPoolExecutor(max_workers=4) as pool:
    results = list(pool.map(lambda n: check_load(n[0], n[1]), nodes.items()))

total_capacity = 0
idle_nodes = []
busy_nodes = []
for name, status, ms, models in results:
    print(f'  {name}: {status} {ms:.0f}ms models={models}')
    if status == 'OK':
        total_capacity += 1
        if ms < 500:
            idle_nodes.append(name)
        else:
            busy_nodes.append(name)

if idle_nodes:
    print(f'  Idle nodes available: {idle_nodes}')
if len(idle_nodes) >= 2:
    print(f'  Cluster under-utilized — {len(idle_nodes)}/{len(nodes)} idle')
print(f'  Total capacity: {total_capacity}/{len(nodes)} online')
"""},
            priority="normal",
            schedule="every:10m",
            tags=["evolution", "cluster", "load-balance"],
        ),

        # ── 4. Code Evolution Scanner: détecte les améliorations possibles dans le codebase ──
        TaskDef(
            id="code_evolution_scan",
            name="Code Evolution Scanner",
            task_type="audit",
            action="python",
            payload={"code": """
import os, re
from pathlib import Path

turbo = Path('F:/BUREAU/turbo')
issues = []

# 1. Find Python files with no error handling in main()
for py in (turbo / 'scripts').glob('*.py'):
    try:
        code = py.read_text(encoding='utf-8', errors='replace')
        if 'def main(' in code and 'if __name__' in code:
            if 'try:' not in code.split('def main(')[1].split('\\ndef ')[0][:500]:
                issues.append(('no_try_main', py.name))
    except: pass

# 2. Find large functions (>100 lines)
for py in list((turbo / 'src').glob('*.py')) + list((turbo / 'scripts').glob('*.py')):
    try:
        lines = py.read_text(encoding='utf-8', errors='replace').splitlines()
        in_func = False
        func_start = 0
        func_name = ''
        for i, line in enumerate(lines):
            if re.match(r'^def |^    def |^class ', line):
                if in_func and (i - func_start) > 100:
                    issues.append(('long_func', f'{py.name}:{func_name} ({i-func_start}L)'))
                in_func = True
                func_start = i
                func_name = line.strip().split('(')[0].replace('def ', '')
    except: pass

# 3. Find TODO/FIXME/HACK/XXX
for d in ['src', 'scripts']:
    for py in (turbo / d).glob('*.py'):
        try:
            for i, line in enumerate(py.read_text(encoding='utf-8', errors='replace').splitlines()):
                for tag in ['TODO', 'FIXME', 'HACK', 'XXX']:
                    if tag in line and not line.strip().startswith('#!'):
                        issues.append(('todo', f'{py.name}:{i+1} {tag}: {line.strip()[:60]}'))
        except: pass

# 4. Find duplicate imports across files
import_counts = {}
for py in (turbo / 'src').glob('*.py'):
    try:
        for line in py.read_text(encoding='utf-8', errors='replace').splitlines()[:50]:
            if line.startswith('import ') or line.startswith('from '):
                mod = line.split()[1].split('.')[0]
                import_counts[mod] = import_counts.get(mod, 0) + 1
    except: pass

print('=== CODE EVOLUTION SCAN ===')
for cat, detail in issues[:20]:
    print(f'  [{cat}] {detail}')
print(f'  Total issues: {len(issues)}')

# Top unused-looking imports
heavy = [(m, c) for m, c in import_counts.items() if c > 20]
if heavy:
    print(f'  Most imported modules: {sorted(heavy, key=lambda x:-x[1])[:5]}')
"""},
            priority="low",
            schedule="every:2h",
            tags=["evolution", "code-quality", "scan"],
        ),

        # ── 5. Test Runner Evolution: lance les tests et track la progression ──
        TaskDef(
            id="test_evolution",
            name="Test Suite Evolution Tracker",
            task_type="test",
            action="python",
            payload={"code": """
import subprocess, sys, re, json, sqlite3
from pathlib import Path

print('=== TEST EVOLUTION ===')
r = subprocess.run(
    [sys.executable, '-m', 'pytest', 'tests/', '-v', '--tb=line', '-q', '--no-header'],
    capture_output=True, text=True, timeout=120, cwd='F:/BUREAU/turbo')

# Parse results
lines = r.stdout.strip().splitlines()
passed = failed = errors = 0
for line in lines:
    if ' passed' in line:
        m = re.search(r'(\\d+) passed', line)
        if m: passed = int(m.group(1))
    if ' failed' in line:
        m = re.search(r'(\\d+) failed', line)
        if m: failed = int(m.group(1))
    if ' error' in line:
        m = re.search(r'(\\d+) error', line)
        if m: errors = int(m.group(1))

total = passed + failed + errors
print(f'  Passed: {passed}/{total} ({passed/max(1,total):.0%})')
print(f'  Failed: {failed}  Errors: {errors}')

# Store metric
db = sqlite3.connect('F:/BUREAU/turbo/data/task_orchestrator.db')
from datetime import datetime
now = datetime.now().isoformat()
db.execute('INSERT INTO task_metrics (metric_name, metric_value, recorded_at) VALUES (?,?,?)',
    ('test_pass_rate', passed/max(1,total)*100, now))
db.execute('INSERT INTO task_metrics (metric_name, metric_value, recorded_at) VALUES (?,?,?)',
    ('test_total_count', total, now))
db.commit()
db.close()

# Show failures
if failed:
    print('  FAILURES:')
    for line in lines:
        if 'FAILED' in line:
            print(f'    {line.strip()[:100]}')
"""},
            priority="normal",
            schedule="every:1h",
            tags=["evolution", "test", "quality"],
        ),

        # ── 6. Cluster Benchmark: mesure les performances de chaque nœud ──
        TaskDef(
            id="cluster_benchmark",
            name="Cluster Performance Benchmark",
            task_type="audit",
            action="python",
            payload={"code": """
import subprocess, time, json, sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

def bench_node(name, url, prompt):
    t0 = time.monotonic()
    try:
        if '11434' in url:
            body = json.dumps({'model':'qwen3:1.7b','messages':[{'role':'user','content':prompt}],'stream':False})
            cmd = ['curl','-s','--max-time','15',f'http://{url}/api/chat','-d',body]
        else:
            body = json.dumps({'model':'qwen3-8b','input':f'/nothink\\n{prompt}','temperature':0.1,'max_output_tokens':100,'stream':False,'store':False})
            cmd = ['curl','-s','--max-time','15',f'http://{url}/api/v1/chat','-H','Content-Type: application/json','-d',body]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        ms = (time.monotonic()-t0)*1000
        if r.returncode == 0 and len(r.stdout) > 10:
            data = json.loads(r.stdout)
            # Count output tokens
            if 'message' in data:
                tokens = len(data['message'].get('content','').split())
            elif 'output' in data:
                msgs = [b for b in data['output'] if b.get('type')=='message']
                tokens = len(msgs[-1]['content'][0]['text'].split()) if msgs else 0
            else:
                tokens = 0
            tok_s = tokens / (ms/1000) if ms > 0 else 0
            return name, 'OK', ms, tokens, tok_s
        return name, 'FAIL', ms, 0, 0
    except Exception as e:
        return name, 'ERROR', (time.monotonic()-t0)*1000, 0, 0

nodes = [
    ('M1', '127.0.0.1:1234'),
    ('OL1', '127.0.0.1:11434'),
    ('M3', '192.168.1.113:1234'),
]
prompt = 'What is 2+2? Answer in one word.'

print('=== CLUSTER BENCHMARK ===')
with ThreadPoolExecutor(max_workers=3) as pool:
    results = list(pool.map(lambda n: bench_node(n[0], n[1], prompt), nodes))

db = sqlite3.connect('F:/BUREAU/turbo/data/task_orchestrator.db')
now = datetime.now().isoformat()
for name, status, ms, tokens, tok_s in results:
    print(f'  {name}: {status} {ms:.0f}ms tokens={tokens} {tok_s:.1f} tok/s')
    if status == 'OK':
        db.execute('INSERT INTO task_metrics (metric_name, metric_value, recorded_at) VALUES (?,?,?)',
            (f'bench_{name.lower()}_ms', ms, now))
        db.execute('INSERT INTO task_metrics (metric_name, metric_value, recorded_at) VALUES (?,?,?)',
            (f'bench_{name.lower()}_toks', tok_s, now))
db.commit()
db.close()
"""},
            priority="low",
            schedule="every:30m",
            tags=["evolution", "benchmark", "cluster"],
        ),

        # ── 7. Failure Learning: extrait les leçons des échecs pour améliorer le système ──
        TaskDef(
            id="failure_learner",
            name="Failure Pattern Learner",
            task_type="audit",
            action="python",
            payload={"code": """
import sqlite3, json, re
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter

db = sqlite3.connect('F:/BUREAU/turbo/data/task_orchestrator.db')

# Get all failures from last 24h
rows = db.execute('''
    SELECT task_id, error, duration_ms, started_at
    FROM task_runs WHERE status='failed'
    AND started_at > datetime('now', '-24 hours')
    ORDER BY started_at DESC
''').fetchall()

print(f'=== FAILURE LEARNING ({len(rows)} failures in 24h) ===')

# Categorize errors
categories = Counter()
for task_id, error, dur, at in rows:
    err = error or ''
    if 'Timeout' in err: categories['timeout'] += 1
    elif 'FileNotFound' in err: categories['missing_file'] += 1
    elif 'Connection' in err: categories['connection'] += 1
    elif 'Permission' in err: categories['permission'] += 1
    elif 'Import' in err: categories['import'] += 1
    elif 'Memory' in err: categories['memory'] += 1
    else: categories['other'] += 1

for cat, cnt in categories.most_common():
    print(f'  {cat}: {cnt}')

# Find time-of-day patterns
hour_fails = Counter()
for _, _, _, at in rows:
    try:
        h = datetime.fromisoformat(at).hour
        hour_fails[h] += 1
    except: pass
if hour_fails:
    worst_hour = hour_fails.most_common(1)[0]
    print(f'  Worst hour: {worst_hour[0]}:00 ({worst_hour[1]} failures)')

# Correlation: which tasks fail together?
from itertools import combinations
window_fails = {}
for task_id, _, _, at in rows:
    try:
        bucket = at[:16]  # minute bucket
        window_fails.setdefault(bucket, []).append(task_id)
    except: pass
pairs = Counter()
for bucket, tasks in window_fails.items():
    if len(tasks) >= 2:
        for a, b in combinations(set(tasks), 2):
            pairs[tuple(sorted([a,b]))] += 1
if pairs:
    top_pair = pairs.most_common(1)[0]
    print(f'  Correlated failures: {top_pair[0][0]} + {top_pair[0][1]} ({top_pair[1]}x)')

# Store learned patterns as metrics
db.execute('INSERT INTO task_metrics (metric_name, metric_value, recorded_at) VALUES (?,?,?)',
    ('failures_24h', len(rows), datetime.now().isoformat()))
db.commit()
db.close()
"""},
            priority="normal",
            schedule="every:2h",
            tags=["evolution", "learning", "patterns"],
        ),

        # ── 8. Proactive Node Exerciser: garde les nœuds chauds avec des tâches utiles ──
        TaskDef(
            id="node_exerciser",
            name="Proactive Node Exerciser",
            task_type="quick",
            action="python",
            payload={"code": """
import subprocess, json, time, random
from concurrent.futures import ThreadPoolExecutor

tasks = [
    'Analyze this Python best practice: always use context managers for file I/O. Explain in 2 sentences.',
    'What are the top 3 causes of memory leaks in Python long-running daemons?',
    'Give 3 tips for optimizing SQLite write performance in concurrent applications.',
    'What is the most efficient way to check if a TCP port is open in Python on Windows?',
    'Explain the difference between subprocess.Popen and subprocess.run in 2 sentences.',
]
task = random.choice(tasks)

def query_node(name, url, prompt):
    t0 = time.monotonic()
    try:
        if '11434' in url:
            body = json.dumps({'model':'qwen3:1.7b','messages':[{'role':'user','content':prompt}],'stream':False})
            r = subprocess.run(['curl','-s','--max-time','10',f'http://{url}/api/chat','-d',body],
                capture_output=True, text=True, timeout=15)
        else:
            body = json.dumps({'model':'qwen3-8b','input':f'/nothink\\n{prompt}','temperature':0.3,'max_output_tokens':200,'stream':False,'store':False})
            r = subprocess.run(['curl','-s','--max-time','10',f'http://{url}/api/v1/chat',
                '-H','Content-Type: application/json','-d',body],
                capture_output=True, text=True, timeout=15)
        ms = (time.monotonic()-t0)*1000
        if r.returncode == 0 and len(r.stdout) > 10:
            data = json.loads(r.stdout)
            if 'message' in data:
                content = data['message'].get('content','')[:200]
            elif 'output' in data:
                msgs = [b for b in data['output'] if b.get('type')=='message']
                content = msgs[-1]['content'][0]['text'][:200] if msgs else 'no output'
            else:
                content = 'unknown format'
            return name, ms, content
        return name, ms, 'FAIL'
    except:
        return name, (time.monotonic()-t0)*1000, 'TIMEOUT'

nodes = [('M1','127.0.0.1:1234'), ('OL1','127.0.0.1:11434'), ('M3','192.168.1.113:1234')]
print(f'=== NODE EXERCISER ===')
print(f'  Task: {task[:60]}...')

with ThreadPoolExecutor(max_workers=3) as pool:
    results = list(pool.map(lambda n: query_node(n[0], n[1], task), nodes))
for name, ms, content in results:
    status = 'OK' if content not in ('FAIL','TIMEOUT') else content
    print(f'  {name}: {status} ({ms:.0f}ms)')
    if status == 'OK':
        print(f'    {content[:100]}...')
"""},
            priority="low",
            schedule="every:20m",
            tags=["evolution", "cluster", "exercise", "warmup"],
        ),

        # ── 9. Dependency Health: vérifie que toutes les dépendances Python sont à jour ──
        TaskDef(
            id="dependency_health",
            name="Dependency Health Check",
            task_type="audit",
            action="python",
            payload={"code": """
import subprocess, sys, json, re
from pathlib import Path

print('=== DEPENDENCY HEALTH ===')

# 1. Check for import errors in key modules
key_modules = ['httpx', 'fastapi', 'uvicorn', 'websockets', 'pydantic',
               'anthropic', 'edge_tts', 'ccxt']
for mod in key_modules:
    try:
        __import__(mod)
        print(f'  [OK] {mod}')
    except ImportError:
        print(f'  [MISSING] {mod}')

# 2. Check pyproject.toml exists and is valid
pyp = Path('F:/BUREAU/turbo/pyproject.toml')
if pyp.exists():
    content = pyp.read_text(encoding='utf-8')
    deps = re.findall(r'"([a-zA-Z0-9_-]+)', content)
    print(f'  pyproject.toml: {len(deps)} dependencies declared')
else:
    print(f'  [WARN] pyproject.toml not found')

# 3. Check .venv health
venv = Path('F:/BUREAU/turbo/.venv')
if venv.exists():
    python_exe = venv / 'Scripts' / 'python.exe'
    if python_exe.exists():
        r = subprocess.run([str(python_exe), '--version'], capture_output=True, text=True, timeout=5)
        print(f'  .venv: {r.stdout.strip()}')
    else:
        print(f'  [WARN] .venv python.exe missing')
else:
    print(f'  [WARN] .venv not found')

# 4. Check uv availability
r = subprocess.run(['uv', '--version'], capture_output=True, text=True, timeout=5)
if r.returncode == 0:
    print(f'  uv: {r.stdout.strip()}')
else:
    print(f'  [WARN] uv not available')
"""},
            priority="low",
            schedule="daily:05:30",
            tags=["evolution", "dependencies", "health"],
        ),

        # ── 10. Log Anomaly Detector: détecte les anomalies dans les logs ──
        TaskDef(
            id="log_anomaly_detector",
            name="Log Anomaly Detector",
            task_type="audit",
            action="python",
            payload={"code": """
import os, re
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter

log_dir = Path('F:/BUREAU/turbo/logs')
print('=== LOG ANOMALY DETECTION ===')

anomalies = []
cutoff = datetime.now() - timedelta(hours=6)

for log_file in log_dir.glob('*.log'):
    try:
        content = log_file.read_text(encoding='utf-8', errors='replace')
        lines = content.splitlines()[-500:]  # Last 500 lines
        errors = [l for l in lines if any(x in l.lower() for x in ['error', 'critical', 'exception', 'traceback'])]
        if len(errors) > 10:
            anomalies.append((log_file.name, len(errors), errors[-1][:80]))
    except: pass

# Check orchestrator log specifically
orch_log = Path('F:/BUREAU/turbo/data/task_orchestrator.log')
if orch_log.exists():
    try:
        lines = orch_log.read_text(encoding='utf-8', errors='replace').splitlines()[-200:]
        fail_count = sum(1 for l in lines if '[failed]' in l.lower() or 'error' in l.lower())
        total = len(lines)
        if fail_count > total * 0.3:
            anomalies.append(('task_orchestrator.log', fail_count, f'{fail_count}/{total} error lines'))
    except: pass

# Check Windows event-like patterns
for a in anomalies:
    print(f'  [{a[0]}] {a[1]} anomalies: {a[2]}')

if not anomalies:
    print('  No anomalies detected in logs')
else:
    print(f'  Total: {len(anomalies)} files with anomalies')
"""},
            priority="low",
            schedule="every:1h",
            tags=["evolution", "logs", "anomaly"],
        ),

        # ── 11. Performance Regression Detector ──
        TaskDef(
            id="perf_regression",
            name="Performance Regression Detector",
            task_type="audit",
            action="python",
            payload={"code": """
import sqlite3
from datetime import datetime, timedelta

db = sqlite3.connect('F:/BUREAU/turbo/data/task_orchestrator.db')
print('=== PERFORMANCE REGRESSION ===')

# Compare avg duration now vs 24h ago for each task
rows = db.execute('''
    SELECT task_id,
        AVG(CASE WHEN started_at > datetime('now', '-2 hours') THEN duration_ms END) as recent_avg,
        AVG(CASE WHEN started_at BETWEEN datetime('now', '-24 hours') AND datetime('now', '-2 hours')
            THEN duration_ms END) as old_avg,
        COUNT(*) as total_runs
    FROM task_runs WHERE status='completed'
    GROUP BY task_id
    HAVING recent_avg IS NOT NULL AND old_avg IS NOT NULL AND total_runs > 5
''').fetchall()

regressions = []
improvements = []
for task_id, recent, old, runs in rows:
    if old > 0:
        change = (recent - old) / old * 100
        if change > 50:  # 50% slower
            regressions.append((task_id, old, recent, change))
        elif change < -30:  # 30% faster
            improvements.append((task_id, old, recent, change))

for t, old, new, pct in sorted(regressions, key=lambda x: -x[3])[:5]:
    print(f'  REGRESSION: {t} {old:.0f}ms -> {new:.0f}ms (+{pct:.0f}%)')
for t, old, new, pct in sorted(improvements, key=lambda x: x[3])[:3]:
    print(f'  IMPROVED: {t} {old:.0f}ms -> {new:.0f}ms ({pct:.0f}%)')

if not regressions and not improvements:
    print('  No significant changes detected')

db.close()
"""},
            priority="normal",
            schedule="every:1h",
            tags=["evolution", "performance", "regression"],
        ),

        # ── 12. Cluster Knowledge Sync: synchronise les connaissances entre nœuds ──
        TaskDef(
            id="cluster_knowledge_sync",
            name="Cluster Knowledge Sync",
            task_type="sync",
            action="python",
            payload={"code": """
import subprocess, json, time, sqlite3
from datetime import datetime

print('=== CLUSTER KNOWLEDGE SYNC ===')

db = sqlite3.connect('F:/BUREAU/turbo/data/task_orchestrator.db')

# 1. Get cluster state summary
metrics = db.execute('''
    SELECT metric_name, metric_value FROM task_metrics
    WHERE id IN (SELECT MAX(id) FROM task_metrics GROUP BY metric_name)
    ORDER BY metric_name
''').fetchall()

state = {m: v for m, v in metrics}

# 2. Get task health summary
health = db.execute('''
    SELECT task_id,
        SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as ok,
        SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as fail,
        AVG(duration_ms) as avg_ms
    FROM task_runs
    GROUP BY task_id
    HAVING ok + fail > 3
    ORDER BY fail DESC LIMIT 10
''').fetchall()

print(f'  Metrics tracked: {len(state)}')
print(f'  Tasks with history: {len(health)}')

# 3. Export condensed state to dashboard
dashboard = {
    'timestamp': datetime.now().isoformat(),
    'metrics_count': len(state),
    'task_health': [{
        'id': h[0], 'ok': h[1], 'fail': h[2],
        'avg_ms': round(h[3], 0), 'rate': round(h[1]/max(1,h[1]+h[2])*100, 1)
    } for h in health],
    'top_metrics': {k: round(v, 2) for k, v in list(state.items())[:20]},
}

out = 'F:/BUREAU/turbo/data/cluster_knowledge.json'
with open(out, 'w') as f:
    json.dump(dashboard, f, indent=2)
print(f'  Exported to {out}')

db.close()
"""},
            priority="low",
            schedule="every:30m",
            tags=["evolution", "sync", "knowledge"],
        ),

        # ── 13. Smart Task Scheduler: réorganise les priorités basé sur l'historique ──
        TaskDef(
            id="smart_scheduler",
            name="Smart Task Priority Optimizer",
            task_type="audit",
            action="python",
            payload={"code": """
import sqlite3
from datetime import datetime

db = sqlite3.connect('F:/BUREAU/turbo/data/task_orchestrator.db')
print('=== SMART SCHEDULER ===')

# Find tasks that always succeed and take <100ms — reduce frequency
fast_reliable = db.execute('''
    SELECT r.task_id, COUNT(*) as runs,
        AVG(r.duration_ms) as avg_ms,
        SUM(CASE WHEN r.status='failed' THEN 1 ELSE 0 END) as fails
    FROM task_runs r
    JOIN tasks t ON r.task_id = t.id
    WHERE t.enabled = 1
    GROUP BY r.task_id
    HAVING runs > 10 AND avg_ms < 100 AND fails = 0
''').fetchall()

if fast_reliable:
    print(f'  Ultra-reliable tasks (0 fails, <100ms): {len(fast_reliable)}')
    for t in fast_reliable[:5]:
        print(f'    {t[0]}: {t[1]} runs, {t[2]:.0f}ms avg')

# Find tasks that frequently fail — candidates for investigation
chronic = db.execute('''
    SELECT task_id, COUNT(*) as total,
        SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as fails
    FROM task_runs
    GROUP BY task_id
    HAVING total > 5 AND CAST(fails AS FLOAT)/total > 0.5
''').fetchall()

adjustments = 0
if chronic:
    print(f'  Chronic failures (>50% fail rate):')
    for t in chronic:
        rate = t[2] / t[1] * 100
        print(f'    {t[0]}: {rate:.0f}% fail ({t[2]}/{t[1]})')
        # Reduce priority of chronic failures
        if rate > 80:
            db.execute('UPDATE tasks SET priority=\"low\" WHERE id=? AND priority != \"low\"', (t[0],))
            adjustments += 1

db.commit()
db.close()
print(f'  Priority adjustments: {adjustments}')
"""},
            priority="low",
            schedule="every:2h",
            tags=["evolution", "scheduler", "optimize"],
        ),

        # ── 14. M1 Deep Code Review via Cluster ──
        TaskDef(
            id="cluster_code_review",
            name="Cluster Code Review (M1+OL1)",
            task_type="review",
            action="python",
            payload={"code": """
import subprocess, json, random, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# Pick a random recently modified Python file
turbo = Path('F:/BUREAU/turbo')
candidates = sorted(
    [f for f in list((turbo/'src').glob('*.py')) + list((turbo/'scripts').glob('*.py'))
     if f.stat().st_size > 500 and f.stat().st_size < 50000],
    key=lambda f: f.stat().st_mtime, reverse=True
)[:10]

if not candidates:
    print('No candidates for review')
    exit()

target = random.choice(candidates)
# Read first 100 lines
code = target.read_text(encoding='utf-8', errors='replace')
snippet = '\\n'.join(code.splitlines()[:80])
prompt = f'Review this Python code for bugs, security issues, and improvements. Be concise (3-5 points):\\n\\n```python\\n{snippet}\\n```'

def review_node(name, url):
    t0 = time.monotonic()
    try:
        if '11434' in url:
            body = json.dumps({'model':'qwen3:1.7b','messages':[{'role':'user','content':prompt}],'stream':False})
            r = subprocess.run(['curl','-s','--max-time','15',f'http://{url}/api/chat','-d',body],
                capture_output=True, text=True, timeout=20)
        else:
            body = json.dumps({'model':'qwen3-8b','input':f'/nothink\\n{prompt}','temperature':0.2,'max_output_tokens':500,'stream':False,'store':False})
            r = subprocess.run(['curl','-s','--max-time','15',f'http://{url}/api/v1/chat',
                '-H','Content-Type: application/json','-d',body],
                capture_output=True, text=True, timeout=20)
        ms = (time.monotonic()-t0)*1000
        if r.returncode == 0:
            data = json.loads(r.stdout)
            if 'message' in data:
                return name, ms, data['message'].get('content','')[:500]
            elif 'output' in data:
                msgs = [b for b in data['output'] if b.get('type')=='message']
                return name, ms, msgs[-1]['content'][0]['text'][:500] if msgs else 'no output'
        return name, ms, 'FAIL'
    except:
        return name, (time.monotonic()-t0)*1000, 'ERROR'

nodes = [('M1','127.0.0.1:1234'), ('OL1','127.0.0.1:11434')]
print(f'=== CLUSTER CODE REVIEW: {target.name} ===')

with ThreadPoolExecutor(max_workers=2) as pool:
    results = list(pool.map(lambda n: review_node(n[0], n[1]), nodes))

for name, ms, review in results:
    print(f'\\n  [{name}] ({ms:.0f}ms):')
    print(f'  {review[:300]}')
"""},
            priority="low",
            schedule="every:3h",
            tags=["evolution", "review", "cluster", "code"],
        ),

        # ── 15. Resource Prediction: prédit quand les resources seront saturées ──
        TaskDef(
            id="resource_predictor",
            name="Resource Saturation Predictor",
            task_type="audit",
            action="python",
            payload={"code": """
import sqlite3, shutil
from datetime import datetime

db = sqlite3.connect('F:/BUREAU/turbo/data/task_orchestrator.db')
print('=== RESOURCE PREDICTION ===')

# 1. Disk usage trend
for drive, label in [('C:/', 'C:'), ('F:/', 'F:')]:
    usage = shutil.disk_usage(drive)
    free_gb = usage.free / 1e9
    total_gb = usage.total / 1e9

    # Get historical disk metrics
    hist = db.execute('''
        SELECT metric_value FROM task_metrics
        WHERE metric_name = ? ORDER BY id DESC LIMIT 10
    ''', (f'disk_free_{label}',)).fetchall()

    if len(hist) >= 3:
        recent = [h[0] for h in hist]
        avg_decline = (recent[-1] - recent[0]) / len(recent) if len(recent) > 1 else 0
        if avg_decline < -0.1:  # losing more than 100MB per check
            days_left = free_gb / abs(avg_decline) if avg_decline != 0 else 999
            print(f'  {label} {free_gb:.1f}GB free — losing {abs(avg_decline):.2f}GB/check — ~{days_left:.0f} days until full')
        else:
            print(f'  {label} {free_gb:.1f}GB free — stable')
    else:
        print(f'  {label} {free_gb:.1f}GB free — not enough history')

    # Store current reading
    db.execute('INSERT INTO task_metrics (metric_name, metric_value, recorded_at) VALUES (?,?,?)',
        (f'disk_free_{label}', free_gb, datetime.now().isoformat()))

# 2. DB growth trend
import os
for db_name in ['task_orchestrator', 'etoile', 'jarvis']:
    db_path = f'F:/BUREAU/turbo/data/{db_name}.db'
    if os.path.exists(db_path):
        size_mb = os.path.getsize(db_path) / 1e6
        db.execute('INSERT INTO task_metrics (metric_name, metric_value, recorded_at) VALUES (?,?,?)',
            (f'db_size_{db_name}', size_mb, datetime.now().isoformat()))
        print(f'  {db_name}.db: {size_mb:.1f}MB')

db.commit()
db.close()
"""},
            priority="low",
            schedule="every:2h",
            tags=["evolution", "prediction", "resources"],
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
    """Run as a daemon with parallel execution, events, metrics, and escalation."""
    print("  JARVIS Task Orchestrator — Daemon mode (v3 — parallel + events + metrics)")
    print("  Checking for due tasks every 60 seconds...")
    cycle = 0
    while True:
        try:
            cycle += 1

            # 1. Collect metrics every 5 cycles (5 min)
            if cycle % 5 == 0:
                try:
                    collect_system_metrics()
                except Exception as e:
                    logger.debug("Metrics collection error: %s", e)

            # 2. Process event triggers
            try:
                events_triggered = process_events()
                if events_triggered:
                    logger.info("Events triggered %d tasks", events_triggered)
            except Exception as e:
                logger.debug("Event processing error: %s", e)

            # 3. Run due tasks (with parallel execution)
            tasks = get_due_tasks()
            if tasks:
                logger.info("Found %d due tasks (cycle %d)", len(tasks), cycle)

                # Split by priority: critical/high run sequentially, normal/low in parallel
                critical = [t for t in tasks if t.priority in ("critical", "high") and check_dependencies(t)]
                parallel = [t for t in tasks if t.priority in ("normal", "low") and check_dependencies(t) and not t.depends_on]
                sequential_deps = [t for t in tasks if t.depends_on and t.priority not in ("critical", "high") and check_dependencies(t)]

                # Run critical tasks first (sequentially)
                for task in critical:
                    ok, reason = check_resource_availability(task)
                    if not ok:
                        logger.warning("Resource unavailable for %s: %s", task.id, reason)
                        continue
                    result = execute_task(task)
                    record_run(result)
                    process_escalation(result.task_id, result.status)
                    logger.info("[%s] %s (%dms)", result.status, task.name, result.duration_ms)

                # Run parallel batch
                if parallel:
                    # Resource-check filter
                    runnable = []
                    for t in parallel:
                        ok, reason = check_resource_availability(t)
                        if ok:
                            runnable.append(t)
                        else:
                            logger.warning("Resource unavailable for %s: %s", t.id, reason)

                    if runnable:
                        results = execute_parallel(runnable, max_workers=min(4, len(runnable)))
                        for r in results:
                            record_run(r)
                            process_escalation(r.task_id, r.status)
                            logger.info("[%s] %s (%dms)", r.status, r.task_id, r.duration_ms)

                # Run sequential deps
                for task in sequential_deps:
                    result = execute_task(task)
                    record_run(result)
                    process_escalation(result.task_id, result.status)
                    logger.info("[%s] %s (%dms)", result.status, task.name, result.duration_ms)

            # 4. Self-check every 30 cycles (30 min)
            if cycle % 30 == 0:
                health = orchestrator_self_check()
                if health["status"] != "healthy":
                    logger.warning("Orchestrator degraded: %s", health["issues"])

        except Exception as e:
            logger.error("Daemon error (cycle %d): %s", cycle, e)

        time.sleep(60)


# ── Main ────────────────────────────────────────────────────────────────────

def show_metrics(metric_name: str = None, hours: int = 24):
    """Show metrics summary."""
    conn = get_db()
    if metric_name:
        summary = get_metrics_summary(metric_name, hours)
        print(f"\n  Metric: {metric_name} (last {hours}h)")
        if summary["count"] == 0:
            print("  No data")
        else:
            print(f"  Count: {summary['count']}")
            print(f"  Min: {summary['min']:.2f}  Max: {summary['max']:.2f}  Avg: {summary['avg']:.2f}")
            print(f"  Latest: {summary['latest']:.2f}")
    else:
        # Show all latest metrics
        rows = conn.execute("""
            SELECT metric_name, metric_value, recorded_at FROM task_metrics
            WHERE id IN (SELECT MAX(id) FROM task_metrics GROUP BY metric_name)
            ORDER BY metric_name
        """).fetchall()
        print(f"\n{'='*60}")
        print(f"  SYSTEM METRICS — {len(rows)} tracked")
        print(f"{'='*60}")
        for name, value, at in rows:
            print(f"  {name:30} {value:10.2f}  ({at})")
        print(f"{'='*60}")
    conn.close()


def show_events():
    """Show event triggers."""
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT event_type, source, task_id, enabled, trigger_count, last_triggered, cooldown_s
            FROM task_events ORDER BY event_type
        """).fetchall()
    except Exception:
        rows = []
    conn.close()

    print(f"\n{'='*70}")
    print(f"  EVENT TRIGGERS — {len(rows)} registered")
    print(f"{'='*70}")
    for etype, source, task_id, enabled, count, last, cooldown in rows:
        status = "ON" if enabled else "OFF"
        print(f"  [{status}] {etype:15} {source[:30]:30} -> {task_id:25} (x{count}, cd={cooldown}s)")
    print(f"{'='*70}")


def show_escalations():
    """Show escalation states."""
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT task_id, consecutive_fails, level_1_threshold, level_2_threshold, level_3_threshold
            FROM task_escalation ORDER BY consecutive_fails DESC
        """).fetchall()
    except Exception:
        rows = []
    conn.close()

    print(f"\n{'='*60}")
    print(f"  ESCALATION STATUS — {len(rows)} tasks tracked")
    print(f"{'='*60}")
    for tid, fails, l1, l2, l3 in rows:
        if fails > 0:
            level = "CRITICAL" if fails >= l3 else "ALERT" if fails >= l2 else "WARN" if fails >= l1 else "OK"
            print(f"  [{level:8}] {tid:25} fails={fails} (L1@{l1} L2@{l2} L3@{l3})")
    ok_count = sum(1 for _, f, *_ in rows if f == 0)
    if ok_count:
        print(f"  ... {ok_count} tasks with 0 consecutive fails")
    print(f"{'='*60}")


def show_dashboard():
    """Export and display dashboard data."""
    data = export_dashboard_data()
    print(json.dumps(data, indent=2, default=str))


def main():
    parser = argparse.ArgumentParser(description="JARVIS Task Orchestrator v3")
    parser.add_argument("--init", action="store_true", help="Initialize DB + default tasks")
    parser.add_argument("--status", action="store_true", help="Show task queue status")
    parser.add_argument("--schedule", action="store_true", help="Show scheduled tasks")
    parser.add_argument("--run", metavar="TASK_ID", help="Run specific task")
    parser.add_argument("--add", metavar="JSON", help="Add task from JSON")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon (v3: parallel + events)")
    parser.add_argument("--run-all", action="store_true", help="Run all due tasks now")
    parser.add_argument("--parallel", action="store_true", help="Run due tasks with parallel execution")
    parser.add_argument("--metrics", nargs="?", const="__all__", metavar="NAME", help="Show metrics (optionally filter by name)")
    parser.add_argument("--events", action="store_true", help="Show event triggers")
    parser.add_argument("--escalations", action="store_true", help="Show escalation states")
    parser.add_argument("--dashboard", action="store_true", help="Export dashboard JSON")
    parser.add_argument("--self-check", action="store_true", help="Orchestrator self-health check")
    parser.add_argument("--cleanup", type=int, nargs="?", const=30, metavar="DAYS", help="Clean old data (default: 30 days)")
    parser.add_argument("--enable", metavar="TASK_ID", help="Enable a task")
    parser.add_argument("--disable", metavar="TASK_ID", help="Disable a task")
    parser.add_argument("--run-tag", metavar="TAG", help="Run all tasks matching a tag")
    parser.add_argument("--collect-metrics", action="store_true", help="Collect system metrics now")
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
        # Singleton: kill existing instance before starting
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
            from src.process_singleton import singleton
            singleton.acquire("orchestrator", pid=os.getpid())
        except Exception:
            pass  # singleton not available, proceed anyway
        daemon_loop()
    elif args.parallel:
        completed = run_due_tasks_parallel()
        print(f"  Completed: {completed} tasks (parallel mode)")
    elif args.metrics:
        if args.metrics == "__all__":
            show_metrics()
        else:
            show_metrics(args.metrics)
    elif args.events:
        show_events()
    elif args.escalations:
        show_escalations()
    elif args.dashboard:
        show_dashboard()
    elif args.self_check:
        health = orchestrator_self_check()
        print(f"  Status: {health['status']}")
        print(f"  DB size: {health['db_size_mb']}MB")
        if health["issues"]:
            for issue in health["issues"]:
                print(f"  Issue: {issue}")
        else:
            print("  No issues")
    elif args.cleanup is not None:
        deleted = cleanup_old_data(args.cleanup)
        print(f"  Cleaned {deleted} old records (>{args.cleanup} days)")
    elif args.enable:
        conn = get_db()
        conn.execute("UPDATE tasks SET enabled=1 WHERE id=?", (args.enable,))
        conn.commit()
        conn.close()
        print(f"  Enabled: {args.enable}")
    elif args.disable:
        conn = get_db()
        conn.execute("UPDATE tasks SET enabled=0 WHERE id=?", (args.disable,))
        conn.commit()
        conn.close()
        print(f"  Disabled: {args.disable}")
    elif args.run_tag:
        tasks = load_tasks()
        matching = [t for t in tasks if args.run_tag in t.tags]
        print(f"  Running {len(matching)} tasks with tag '{args.run_tag}'")
        for task in matching:
            result = execute_task(task)
            record_run(result)
            process_escalation(result.task_id, result.status)
            print(f"  [{result.status}] {task.name} ({result.duration_ms:.0f}ms)")
    elif args.collect_metrics:
        collect_system_metrics()
        print("  Metrics collected")
    elif args.run_all:
        run_due_tasks()
    else:
        run_due_tasks()


if __name__ == "__main__":
    main()
