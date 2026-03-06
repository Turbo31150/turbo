#!/usr/bin/env python3
"""auto_dispatcher.py

Standalone dispatcher for COWORK_BATCH33 tasks.
Features:
- CLI: --start, --stop, --status, --config <path>
- SQLite DB at dev/data/dispatcher.db (tables: tasks, runs, nodes)
- Simple routing based on intent, load, thermal (mocked).
- Priority order: M1 (qwen3-8b), M2 (deepseek-r1), OL1, M3.
- Config JSON defines node endpoints and thermal limits.
- Uses only Python stdlib (argparse, json, sqlite3, threading, time, logging, pathlib)
"""

import argparse
import json
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Dict, Any, List

DB_PATH = Path(__file__).parent.parent / "data" / "dispatcher.db"
DEFAULT_CONFIG = {
    "nodes": {
        "M1": {"endpoint": "http://10.5.0.2:1234/v1/chat/completions", "thermal_limit": 85},
        "M2": {"endpoint": "http://192.168.1.26:1234/v1/chat/completions", "thermal_limit": 80},
        "OL1": {"endpoint": "http://127.0.0.1:11434/api/chat", "thermal_limit": 90},
        "M3": {"endpoint": "http://192.168.1.113:1234/v1/chat/completions", "thermal_limit": 80},
    },
    "priority": ["M1", "M2", "OL1", "M3"]
}

log = logging.getLogger("auto_dispatcher")
log.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(message)s"))
log.addHandler(handler)


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            intent TEXT NOT NULL,
            payload TEXT,
            status TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            node TEXT,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            finished_at TIMESTAMP,
            success INTEGER,
            log TEXT,
            FOREIGN KEY(task_id) REFERENCES tasks(id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS node_status (
            node TEXT PRIMARY KEY,
            load REAL,
            temperature REAL,
            last_seen TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


def load_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        log.warning("Config file %s not found, using default", path)
        return DEFAULT_CONFIG
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    # merge with defaults for missing keys
    merged = DEFAULT_CONFIG.copy()
    merged.update(cfg)
    return merged


def select_node(intent: str, cfg: Dict[str, Any]) -> str:
    # Simple heuristic: pick highest priority node that is under thermal limit
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT node, temperature FROM node_status")
    status = {row[0]: row[1] for row in cur.fetchall()}
    conn.close()
    for node in cfg["priority"]:
        node_cfg = cfg["nodes"].get(node, {})
        temp_limit = node_cfg.get("thermal_limit", 100)
        temp = status.get(node, 0)
        if temp < temp_limit:
            return node
    # fallback to first priority
    return cfg["priority"][0]


def enqueue_task(intent: str, payload: str = "") -> int:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO tasks (intent, payload, status) VALUES (?,?,?)",
        (intent, payload, "queued"),
    )
    task_id = cur.lastrowid
    conn.commit()
    conn.close()
    log.info("Enqueued task %s with intent %s", task_id, intent)
    return task_id


def process_queue(stop_event: threading.Event, cfg: Dict[str, Any]) -> None:
    while not stop_event.is_set():
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT id, intent, payload FROM tasks WHERE status='queued' ORDER BY created_at LIMIT 1")
        row = cur.fetchone()
        if not row:
            conn.close()
            time.sleep(2)
            continue
        task_id, intent, payload = row
        node = select_node(intent, cfg)
        # mark running
        cur.execute("UPDATE tasks SET status='running' WHERE id=?", (task_id,))
        conn.commit()
        conn.close()
        log.info("Dispatching task %s to node %s", task_id, node)
        # simulate run (real implementation would exec curl etc.)
        run_id = None
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO runs (task_id, node, success, log) VALUES (?,?,?,?)",
                (task_id, node, 0, ""),
            )
            run_id = cur.lastrowid
            conn.commit()
            conn.close()
            # mock processing time
            time.sleep(1)
            # mark success
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute(
                "UPDATE runs SET finished_at=CURRENT_TIMESTAMP, success=1 WHERE id=?",
                (run_id,),
            )
            cur.execute("UPDATE tasks SET status='done' WHERE id=?", (task_id,))
            conn.commit()
            conn.close()
            log.info("Task %s completed on %s", task_id, node)
        except Exception as e:
            log.exception("Error processing task %s", task_id)
            if run_id:
                conn = sqlite3.connect(DB_PATH)
                cur = conn.cursor()
                cur.execute(
                    "UPDATE runs SET finished_at=CURRENT_TIMESTAMP, success=0, log=? WHERE id=?",
                    (str(e), run_id),
                )
                conn.commit()
                conn.close()
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("UPDATE tasks SET status='error' WHERE id=?", (task_id,))
            conn.commit()
            conn.close()
        time.sleep(0.5)


def start_service(cfg_path: Path) -> None:
    cfg = load_config(cfg_path)
    init_db()
    stop_event = threading.Event()
    worker = threading.Thread(target=process_queue, args=(stop_event, cfg), daemon=True)
    worker.start()
    log.info("Dispatcher started. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Shutdown signal received.")
        stop_event.set()
        worker.join()
        log.info("Dispatcher stopped.")


def stop_service() -> None:
    # Placeholder: in real system we would signal the running thread via pid file.
    log.info("Stop command received. Implement external signalling as needed.")


def status_service() -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM tasks WHERE status='queued'")
    queued = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM tasks WHERE status='running'")
    running = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM tasks WHERE status='done'")
    done = cur.fetchone()[0]
    conn.close()
    log.info("Dispatcher status: %s queued, %s running, %s completed.", queued, running, done)


def main() -> None:
    parser = argparse.ArgumentParser(description="Auto Dispatcher for COWORK batch tasks")
    parser.add_argument("--start", action="store_true", help="Start the dispatcher service")
    parser.add_argument("--stop", action="store_true", help="Stop the dispatcher service")
    parser.add_argument("--status", action="store_true", help="Show current dispatcher status")
    parser.add_argument("--config", type=str, default=str(Path(__file__).parent / "dispatcher_config.json"), help="Path to config JSON")
    args = parser.parse_args()
    cfg_path = Path(args.config)
    if args.start:
        start_service(cfg_path)
    elif args.stop:
        stop_service()
    elif args.status:
        status_service()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
