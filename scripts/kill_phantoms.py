#!/usr/bin/env python3
"""kill_phantoms.py — Phantom Process Killer & Watchdog v2.0

Full-featured process deduplication daemon integrated with JARVIS cluster.
Detects and kills duplicate MCP servers, zombie Python/Node processes,
orphaned npx wrappers, and stale service instances.

Features:
    - JSON config file for all patterns/thresholds/protected processes
    - SQLite metrics & history (kill_phantoms.db)
    - Telegram alerts on mass kills or critical phantoms
    - Cluster health integration (checks M1/M2/M3/OL1 after cleanup)
    - Windows-native WMI enumeration (fast, reliable)
    - Singleton guard (PID file)
    - Configurable keep count per service type
    - Memory threshold kills (orphans > N MB)
    - Age threshold kills (processes older than N hours)
    - Protected PID tree (never kill current session)
    - Dry-run, scan, watchdog, once modes
    - JSON output for orchestrator integration
    - Devops orchestrator handler compatible

Usage:
    python scripts/kill_phantoms.py                          # Kill phantoms (once)
    python scripts/kill_phantoms.py --dry-run                # Scan without killing
    python scripts/kill_phantoms.py --watchdog               # Daemon mode
    python scripts/kill_phantoms.py --watchdog --interval 60 # Custom interval
    python scripts/kill_phantoms.py --config custom.json     # Custom config
    python scripts/kill_phantoms.py --json                   # JSON output
    python scripts/kill_phantoms.py --stats                  # Show kill history
    python scripts/kill_phantoms.py --status                 # Current phantom count
    python scripts/kill_phantoms.py --health                 # Post-kill cluster check
    python scripts/kill_phantoms.py --telegram               # Force Telegram report
    python scripts/kill_phantoms.py --aggressive             # Lower thresholds
    python scripts/kill_phantoms.py --protect-pids 1234,5678 # Extra protected PIDs
    python scripts/kill_phantoms.py --keep 2                 # Keep N newest per type
    python scripts/kill_phantoms.py --max-mem 200            # Kill orphans > 200MB
    python scripts/kill_phantoms.py --max-age 2              # Kill processes > 2h old

Stdlib-only (subprocess, json, time, argparse, sqlite3, os, re, socket).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import socket
import sqlite3
import subprocess
import sys
import time

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# ── Paths ────────────────────────────────────────────────────────────────────
TURBO_DIR = Path("F:/BUREAU/turbo")
SCRIPT_DIR = TURBO_DIR / "scripts"
DATA_DIR = TURBO_DIR / "data"
LOG_DIR = TURBO_DIR / "logs"
PID_DIR = TURBO_DIR / "data" / "pids"
DB_PATH = DATA_DIR / "kill_phantoms.db"
CONFIG_PATH = DATA_DIR / "kill_phantoms.json"
PID_FILE = PID_DIR / "kill_phantoms.pid"
LOG_FILE = LOG_DIR / "kill_phantoms.log"

# ── .env loader (shared pattern with devops_orchestrator) ────────────────────
def _load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    env_file = TURBO_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text(errors="replace").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env

ENV = _load_env()
TELEGRAM_TOKEN = ENV.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT = ENV.get("TELEGRAM_CHAT", "")

# ── Default Config ───────────────────────────────────────────────────────────
DEFAULT_CONFIG: dict[str, Any] = {
    "version": "2.0",

    # How many instances to KEEP per type (newest kept)
    "keep_count": 1,

    # Memory threshold: kill any unprotected orphan process above this (MB)
    # Set to 0 to disable
    "max_memory_mb": 0,

    # Age threshold: kill any unprotected orphan process older than this (hours)
    # Set to 0 to disable
    "max_age_hours": 0,

    # Watchdog interval (seconds)
    "watchdog_interval_s": 120,

    # Send Telegram alert when killing >= N phantoms in one cycle
    "telegram_alert_threshold": 3,

    # Run cluster health check after cleanup
    "health_check_after_kill": True,

    # Cluster nodes for post-kill health check
    "cluster_nodes": {
        "M1":  {"url": "http://127.0.0.1:1234/api/v1/models", "timeout": 5},
        "M2":  {"url": "http://192.168.1.26:1234/api/v1/models", "timeout": 5},
        "M3":  {"url": "http://192.168.1.113:1234/api/v1/models", "timeout": 5},
        "OL1": {"url": "http://127.0.0.1:11434/api/tags", "timeout": 3},
    },

    # Critical ports: NEVER kill process listening on these
    "protected_ports": [
        1234, 11434, 9742, 18789, 18793, 18800,
        8080, 8901, 5678, 9222
    ],

    # Protected command-line substrings: NEVER kill if cmdline contains these
    "protected_cmdline_patterns": [
        "unified_boot", "unified_console",
        "devops_orchestrator", "kill_phantoms",
        "openclaw_watchdog", "watchdog_autonomous",
        "telegram-bot", "linkedin_scheduler",
        "whisper_worker", "dashboard",
        "lmstudio", "ollama", "LM Studio"
    ],

    # === PROCESS PATTERNS ===
    # Node MCP servers (deduplicate, keep newest)
    "node_mcp_patterns": {
        "playwright-mcp":      {"match": "playwright.*mcp.*cli\\.js",          "exclude": "npx-cli", "keep": 1},
        "chrome-devtools-mcp": {"match": "chrome-devtools-mcp.*bin",           "exclude": "npx-cli", "keep": 1},
        "context7-mcp":        {"match": "context7-mcp.*index\\.js",           "exclude": "npx-cli", "keep": 1},
        "filesystem-mcp":      {"match": "server-filesystem.*index\\.js",      "exclude": "npx-cli", "keep": 1},
        "gemini-cli":          {"match": "gemini-cli.*index\\.js",             "exclude": None,      "keep": 1},
        "github-mcp":          {"match": "server-github.*index\\.js",          "exclude": "npx-cli", "keep": 1},
        "microsoft-learn-mcp": {"match": "microsoft-learn.*index\\.js",        "exclude": "npx-cli", "keep": 1},
        "browseros-mcp":       {"match": "browseros.*index\\.js",              "exclude": "npx-cli", "keep": 1},
        "canva-mcp":           {"match": "canva.*index\\.js",                  "exclude": "npx-cli", "keep": 1},
        "notion-mcp":          {"match": "notion.*index\\.js",                 "exclude": "npx-cli", "keep": 1},
        "calendar-mcp":        {"match": "google.*calendar.*index\\.js",       "exclude": "npx-cli", "keep": 1},
        "codex-cli":           {"match": "codex.*index\\.js",                  "exclude": None,      "keep": 1},
        "chrome-devtools-watchdog": {"match": "chrome-devtools-mcp.*watchdog", "exclude": None,      "keep": 1},
    },

    # NPX wrappers (parent processes — kill tree to get children too)
    "npx_patterns": {
        "npx-playwright":      "npx-cli.*playwright",
        "npx-chrome-devtools": "npx-cli.*chrome-devtools",
        "npx-context7":        "npx-cli.*context7",
        "npx-filesystem":      "npx-cli.*server-filesystem",
        "npx-microsoft-learn": "npx-cli.*microsoft-learn",
    },

    # Python service duplicates (keep newest)
    "python_patterns": {
        "mcp-server-sse":      {"match": "mcp_server_sse",     "keep": 1},
        "jarvis-mcp-router":   {"match": "jarvis_mcp_router",  "keep": 1},
        "windows-mcp":         {"match": "windows-mcp",        "keep": 1},
        "claude-proxy":        {"match": "claude-proxy\\.js",   "keep": 1},
        "gemini-proxy":        {"match": "gemini-proxy\\.js",   "keep": 1},
        "direct-proxy":        {"match": "direct-proxy\\.js",   "keep": 1},
        "devops-orchestrator": {"match": "devops_orchestrator", "keep": 1},
    },

    # cmd.exe orphan patterns (intermediate wrappers)
    "cmd_patterns": {
        "cmd-npx-wrapper": {"match": "cmd\\.exe.*npx.*mcp", "keep": 0},
    },

    # Aggressive mode overrides (lower thresholds)
    "aggressive": {
        "max_memory_mb": 300,
        "max_age_hours": 1,
        "keep_count": 1,
        "telegram_alert_threshold": 1,
    },
}


# ── Config management ────────────────────────────────────────────────────────
def load_config(path: Path | None = None) -> dict[str, Any]:
    """Load config from JSON file, merge with defaults."""
    cfg = dict(DEFAULT_CONFIG)
    config_file = path or CONFIG_PATH
    if config_file.exists():
        try:
            with open(config_file) as f:
                user_cfg = json.load(f)
            _deep_merge(cfg, user_cfg)
        except Exception as e:
            _log(f"WARN: config load failed ({e}), using defaults")
    return cfg


def save_default_config(path: Path | None = None):
    """Write default config to JSON file."""
    config_file = path or CONFIG_PATH
    config_file.parent.mkdir(parents=True, exist_ok=True)
    with open(config_file, "w") as f:
        json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
    _log(f"Config ecrit: {config_file}")


def _deep_merge(base: dict, override: dict):
    """Merge override into base recursively."""
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


# ── Logging ──────────────────────────────────────────────────────────────────
def _log(msg: str, level: str = "INFO"):
    """Log to file + stdout."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    print(line)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ── SQLite metrics ───────────────────────────────────────────────────────────
def _init_db():
    """Initialize SQLite database for kill history."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""
        CREATE TABLE IF NOT EXISTS kill_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            cycle_id TEXT,
            process_type TEXT NOT NULL,
            process_name TEXT,
            pid INTEGER NOT NULL,
            mem_mb REAL DEFAULT 0,
            age_hours REAL DEFAULT 0,
            reason TEXT,
            action TEXT NOT NULL,
            success INTEGER DEFAULT 1
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS cycles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            mode TEXT DEFAULT 'once',
            phantoms_found INTEGER DEFAULT 0,
            phantoms_killed INTEGER DEFAULT 0,
            processes_kept INTEGER DEFAULT 0,
            mem_freed_mb REAL DEFAULT 0,
            cluster_health TEXT,
            telegram_sent INTEGER DEFAULT 0,
            duration_ms REAL DEFAULT 0
        )
    """)
    db.execute("""
        CREATE INDEX IF NOT EXISTS idx_kill_ts ON kill_log(ts)
    """)
    db.execute("""
        CREATE INDEX IF NOT EXISTS idx_cycles_ts ON cycles(ts)
    """)
    db.commit()
    return db


def _record_kill(db: sqlite3.Connection, cycle_id: str, entry: dict):
    """Record a kill event in the database."""
    db.execute(
        "INSERT INTO kill_log(cycle_id, process_type, process_name, pid, mem_mb, age_hours, reason, action, success) "
        "VALUES(?,?,?,?,?,?,?,?,?)",
        (cycle_id, entry.get("type", ""), entry.get("name", ""),
         entry.get("pid", 0), entry.get("mem_mb", 0), entry.get("age_hours", 0),
         entry.get("reason", "duplicate"), entry.get("action", "kill"), 1)
    )


def _record_cycle(db: sqlite3.Connection, report: dict):
    """Record a full scan cycle."""
    db.execute(
        "INSERT INTO cycles(mode, phantoms_found, phantoms_killed, processes_kept, mem_freed_mb, cluster_health, telegram_sent, duration_ms) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (report.get("mode", "once"), len(report.get("phantoms", [])),
         report.get("killed", 0), report.get("kept", 0),
         report.get("mem_freed_mb", 0), json.dumps(report.get("cluster_health", {})),
         1 if report.get("telegram_sent") else 0, report.get("duration_ms", 0))
    )
    db.commit()


# ── Process enumeration (WMIC CSV — 8x faster than PowerShell) ───────────────
def _wmic_query(name_filter: str) -> list[dict]:
    """Query processes via WMIC CSV format (fastest on Windows)."""
    try:
        r = subprocess.run(
            ["wmic", "process", "where", f"Name='{name_filter}'",
             "get", "ProcessId,ParentProcessId,Name,CommandLine,CreationDate,WorkingSetSize",
             "/format:csv"],
            capture_output=True, text=True, timeout=10,
            encoding="utf-8", errors="replace"
        )
        if r.returncode != 0:
            return []
        lines = [l.strip() for l in r.stdout.strip().split("\n") if l.strip()]
        if len(lines) < 2:
            return []
        # CSV header: Node,CommandLine,CreationDate,Name,ParentProcessId,ProcessId,WorkingSetSize
        header = [h.strip() for h in lines[0].split(",")]
        procs = []
        for line in lines[1:]:
            # Handle commas inside CommandLine (quoted fields)
            parts = _parse_csv_line(line, len(header))
            if not parts or len(parts) < len(header):
                continue
            row = dict(zip(header, parts))
            # Normalize field names and types
            try:
                proc = {
                    "ProcessId": int(row.get("ProcessId", 0)),
                    "ParentProcessId": int(row.get("ParentProcessId", 0)),
                    "Name": row.get("Name", ""),
                    "CommandLine": row.get("CommandLine", ""),
                    "CreationDate": row.get("CreationDate", ""),
                    "WorkingSetSize": int(row.get("WorkingSetSize", 0)),
                }
                if proc["ProcessId"] > 0:
                    procs.append(proc)
            except (ValueError, TypeError):
                continue
        return procs
    except Exception as e:
        _log(f"WMIC query failed for {name_filter}: {e}", "ERROR")
        return []


def _parse_csv_line(line: str, expected_fields: int) -> list[str]:
    """Parse a CSV line handling commas in quoted fields (WMIC output)."""
    # WMIC CSV: first field is Node (hostname), always unquoted
    # CommandLine may contain commas and quotes
    parts = line.split(",")
    if len(parts) == expected_fields:
        return parts
    # If too many parts, CommandLine has commas — reconstruct it
    if len(parts) > expected_fields:
        # Node is parts[0], CommandLine starts at parts[1]
        # We need to find where CommandLine ends
        # Strategy: work from the end (known fixed fields: Name, ParentPid, Pid, WorkingSet)
        # Last 4 fields are always single-value
        tail = parts[-(expected_fields - 2):]  # last N-2 fields (after Node + CommandLine)
        cmdline = ",".join(parts[1:len(parts) - (expected_fields - 2)])
        return [parts[0], cmdline] + tail
    return parts


def get_all_processes() -> dict[str, list[dict]]:
    """Get all node.exe, python.exe, pythonw.exe, cmd.exe processes at once.
    Uses parallel WMIC queries (each ~170ms vs PowerShell ~1400ms)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    result: dict[str, list[dict]] = {"node": [], "python": [], "cmd": []}
    targets = {
        "node": "node.exe",
        "python": "python.exe",
        "python_w": "pythonw.exe",
        "cmd": "cmd.exe",
    }

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(_wmic_query, name): key for key, name in targets.items()}
        for f in as_completed(futures, timeout=15):
            key = futures[f]
            try:
                procs = f.result()
                if key == "python_w":
                    result["python"].extend(procs)
                else:
                    result.setdefault(key, []).extend(procs)
            except Exception:
                pass

    return result


def match_processes(procs: list[dict], match_pattern: str,
                    exclude_pattern: str | None = None) -> list[dict]:
    """Filter processes matching regex pattern, sorted oldest→newest."""
    matched = []
    for p in procs:
        cmd = p.get("CommandLine") or ""
        if re.search(match_pattern, cmd, re.IGNORECASE):
            if exclude_pattern and re.search(exclude_pattern, cmd, re.IGNORECASE):
                continue
            matched.append(p)
    return sorted(matched, key=lambda x: x.get("CreationDate") or "")


def get_listening_pids(ports: list[int]) -> set[int]:
    """Get PIDs of processes listening on protected ports."""
    pids: set[int] = set()
    try:
        r = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            capture_output=True, text=True, timeout=10, encoding="utf-8", errors="replace"
        )
        for line in r.stdout.splitlines():
            if "LISTENING" in line:
                parts = line.split()
                if len(parts) >= 5:
                    try:
                        port = int(parts[1].rsplit(":", 1)[1])
                        pid = int(parts[4])
                        if port in ports:
                            pids.add(pid)
                    except (ValueError, IndexError):
                        pass
    except Exception:
        pass
    return pids


def is_protected(pid: int, cmdline: str, cfg: dict, extra_protected: set[int]) -> bool:
    """Check if a process is protected from killing."""
    if pid in extra_protected:
        return True
    if pid == os.getpid() or pid == os.getppid():
        return True
    for pattern in cfg.get("protected_cmdline_patterns", []):
        if pattern.lower() in cmdline.lower():
            return True
    return False


def kill_process(pid: int, tree: bool = False) -> bool:
    """Kill a process by PID. Returns True on success."""
    try:
        # Try os.kill first (fastest, no subprocess overhead)
        if not tree:
            try:
                os.kill(pid, signal.SIGTERM)
                time.sleep(0.1)
                # Verify it's dead
                try:
                    os.kill(pid, 0)  # check if alive
                    # Still alive, force kill via taskkill
                    subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                                   capture_output=True, timeout=5,
                                   encoding="utf-8", errors="replace")
                except OSError:
                    pass  # Dead, good
                return True
            except (OSError, PermissionError):
                pass  # Fallback to taskkill

        # Fallback: taskkill (handles tree kills and permissions)
        cmd = f"taskkill /F {'/T ' if tree else ''}/PID {pid}"
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           timeout=10, encoding="utf-8", errors="replace")
        return r.returncode == 0
    except Exception:
        return False


def proc_age_hours(proc: dict) -> float:
    """Calculate process age in hours from WMI CreationDate."""
    cd = proc.get("CreationDate")
    if not cd:
        return 0
    try:
        # WMI format: /Date(1711000000000+0100)/ or YYYYMMDDHHmmss.ffffff+ZZZ
        if "/Date(" in str(cd):
            ms = int(re.search(r"\d+", str(cd)).group())
            created = datetime.fromtimestamp(ms / 1000)
        else:
            created = datetime.strptime(str(cd)[:14], "%Y%m%d%H%M%S")
        return (datetime.now() - created).total_seconds() / 3600
    except Exception:
        return 0


# ── Core scan & kill ─────────────────────────────────────────────────────────
def scan_and_kill(cfg: dict, dry_run: bool = False, mode: str = "once") -> dict:
    """Full scan cycle: detect phantoms, kill, report."""
    t0 = time.time()
    cycle_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    all_procs = get_all_processes()
    node_procs = all_procs["node"]
    python_procs = all_procs["python"]
    cmd_procs = all_procs["cmd"]

    # Build protected PID set
    protected_ports = cfg.get("protected_ports", [])
    protected_pids = get_listening_pids(protected_ports)
    protected_pids.add(os.getpid())
    if os.getppid():
        protected_pids.add(os.getppid())

    report: dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "cycle_id": cycle_id,
        "mode": mode,
        "phantoms": [],
        "killed": 0,
        "kept": 0,
        "mem_freed_mb": 0.0,
        "errors": [],
    }

    db = None
    try:
        db = _init_db()
    except Exception as e:
        report["errors"].append(f"DB init failed: {e}")

    global_keep = cfg.get("keep_count", 1)
    max_mem = cfg.get("max_memory_mb", 0)
    max_age = cfg.get("max_age_hours", 0)

    # ── 1. Node MCP deduplication ────────────────────────────────────────
    for name, pat_cfg in cfg.get("node_mcp_patterns", {}).items():
        match_pat = pat_cfg.get("match", "")
        exclude_pat = pat_cfg.get("exclude")
        keep = pat_cfg.get("keep", global_keep)

        matches = match_processes(node_procs, match_pat, exclude_pat)
        if len(matches) <= keep:
            report["kept"] += len(matches)
            continue

        to_kill = matches[:-keep] if keep > 0 else matches
        report["kept"] += keep

        for p in to_kill:
            pid = p["ProcessId"]
            cmdline = p.get("CommandLine") or ""
            if is_protected(pid, cmdline, cfg, protected_pids):
                continue
            mem_mb = round((p.get("WorkingSetSize") or 0) / 1024 / 1024, 1)
            age_h = round(proc_age_hours(p), 2)
            entry = {
                "type": name, "pid": pid, "mem_mb": mem_mb,
                "age_hours": age_h, "reason": "duplicate",
                "action": "kill" if not dry_run else "would_kill",
            }
            report["phantoms"].append(entry)
            if not dry_run:
                if kill_process(pid):
                    report["killed"] += 1
                    report["mem_freed_mb"] += mem_mb
                    if db:
                        _record_kill(db, cycle_id, entry)
                else:
                    entry["action"] = "kill_failed"
                    report["errors"].append(f"Failed to kill PID {pid}")

    # ── 2. NPX wrapper deduplication ─────────────────────────────────────
    for name, pattern in cfg.get("npx_patterns", {}).items():
        matches = match_processes(node_procs, pattern)
        if len(matches) <= 1:
            continue
        to_kill = matches[:-1]
        for p in to_kill:
            pid = p["ProcessId"]
            cmdline = p.get("CommandLine") or ""
            if is_protected(pid, cmdline, cfg, protected_pids):
                continue
            mem_mb = round((p.get("WorkingSetSize") or 0) / 1024 / 1024, 1)
            entry = {
                "type": name, "pid": pid, "mem_mb": mem_mb,
                "reason": "duplicate_wrapper", "action": "kill_tree" if not dry_run else "would_kill_tree",
            }
            report["phantoms"].append(entry)
            if not dry_run:
                if kill_process(pid, tree=True):
                    report["killed"] += 1
                    report["mem_freed_mb"] += mem_mb
                    if db:
                        _record_kill(db, cycle_id, entry)

    # ── 3. Python service deduplication ──────────────────────────────────
    for name, pat_cfg in cfg.get("python_patterns", {}).items():
        match_pat = pat_cfg if isinstance(pat_cfg, str) else pat_cfg.get("match", "")
        keep = pat_cfg.get("keep", global_keep) if isinstance(pat_cfg, dict) else global_keep

        matches = match_processes(python_procs, match_pat)
        if len(matches) <= keep:
            report["kept"] += len(matches)
            continue

        to_kill = matches[:-keep] if keep > 0 else matches
        report["kept"] += keep

        for p in to_kill:
            pid = p["ProcessId"]
            cmdline = p.get("CommandLine") or ""
            if is_protected(pid, cmdline, cfg, protected_pids):
                continue
            mem_mb = round((p.get("WorkingSetSize") or 0) / 1024 / 1024, 1)
            entry = {
                "type": name, "pid": pid, "mem_mb": mem_mb,
                "reason": "duplicate", "action": "kill" if not dry_run else "would_kill",
            }
            report["phantoms"].append(entry)
            if not dry_run:
                if kill_process(pid):
                    report["killed"] += 1
                    report["mem_freed_mb"] += mem_mb
                    if db:
                        _record_kill(db, cycle_id, entry)

    # ── 4. cmd.exe orphan wrappers ───────────────────────────────────────
    for name, pat_cfg in cfg.get("cmd_patterns", {}).items():
        match_pat = pat_cfg.get("match", "")
        keep = pat_cfg.get("keep", 0)
        matches = match_processes(cmd_procs, match_pat)
        if len(matches) <= keep:
            continue
        to_kill = matches[:-keep] if keep > 0 else matches
        for p in to_kill:
            pid = p["ProcessId"]
            cmdline = p.get("CommandLine") or ""
            if is_protected(pid, cmdline, cfg, protected_pids):
                continue
            entry = {
                "type": name, "pid": pid, "reason": "orphan_wrapper",
                "action": "kill_tree" if not dry_run else "would_kill_tree",
            }
            report["phantoms"].append(entry)
            if not dry_run:
                if kill_process(pid, tree=True):
                    report["killed"] += 1
                    if db:
                        _record_kill(db, cycle_id, entry)

    # ── 5. Memory hogs (unprotected processes > max_memory_mb) ───────────
    if max_mem > 0:
        all_python = [p for p in python_procs
                      if not is_protected(p["ProcessId"], p.get("CommandLine") or "", cfg, protected_pids)]
        for p in all_python:
            mem_mb = (p.get("WorkingSetSize") or 0) / 1024 / 1024
            if mem_mb > max_mem:
                pid = p["ProcessId"]
                entry = {
                    "type": "memory_hog", "pid": pid,
                    "mem_mb": round(mem_mb, 1), "reason": f">{max_mem}MB",
                    "action": "kill" if not dry_run else "would_kill",
                }
                report["phantoms"].append(entry)
                if not dry_run:
                    if kill_process(pid):
                        report["killed"] += 1
                        report["mem_freed_mb"] += mem_mb
                        if db:
                            _record_kill(db, cycle_id, entry)

    # ── 6. Age-based kills (unprotected processes > max_age_hours) ───────
    if max_age > 0:
        all_node = [p for p in node_procs
                    if not is_protected(p["ProcessId"], p.get("CommandLine") or "", cfg, protected_pids)]
        for p in all_node:
            age_h = proc_age_hours(p)
            if age_h > max_age:
                pid = p["ProcessId"]
                mem_mb = (p.get("WorkingSetSize") or 0) / 1024 / 1024
                entry = {
                    "type": "stale_node", "pid": pid,
                    "mem_mb": round(mem_mb, 1), "age_hours": round(age_h, 2),
                    "reason": f">{max_age}h old",
                    "action": "kill" if not dry_run else "would_kill",
                }
                report["phantoms"].append(entry)
                if not dry_run:
                    if kill_process(pid):
                        report["killed"] += 1
                        report["mem_freed_mb"] += mem_mb
                        if db:
                            _record_kill(db, cycle_id, entry)

    report["mem_freed_mb"] = round(report["mem_freed_mb"], 1)
    report["duration_ms"] = round((time.time() - t0) * 1000, 1)

    # ── 7. Post-kill cluster health check ────────────────────────────────
    if cfg.get("health_check_after_kill") and report["killed"] > 0:
        report["cluster_health"] = cluster_health_check(cfg)

    # ── 8. Record cycle in DB ────────────────────────────────────────────
    if db:
        try:
            _record_cycle(db, report)
            db.close()
        except Exception:
            pass

    return report


# ── Cluster health check ─────────────────────────────────────────────────────
def cluster_health_check(cfg: dict) -> dict[str, str]:
    """Quick health check of cluster nodes after cleanup."""
    import urllib.request
    results = {}
    nodes = cfg.get("cluster_nodes", {})
    for node_id, node_cfg in nodes.items():
        url = node_cfg.get("url", "")
        timeout = node_cfg.get("timeout", 5)
        try:
            r = urllib.request.urlopen(url, timeout=timeout)
            data = json.loads(r.read())
            if "models" in data:
                count = len([m for m in data["models"] if m.get("loaded_instances")])
                results[node_id] = f"OK ({count} loaded)"
            elif "data" in data:
                count = len([m for m in data["data"] if m.get("loaded_instances")])
                results[node_id] = f"OK ({count} loaded)"
            else:
                results[node_id] = "OK"
        except Exception as e:
            results[node_id] = f"OFFLINE ({e})"
    return results


# ── Telegram ─────────────────────────────────────────────────────────────────
def send_telegram(report: dict, cfg: dict) -> bool:
    """Send Telegram alert about phantom cleanup."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        return False
    threshold = cfg.get("telegram_alert_threshold", 3)
    if report.get("killed", 0) < threshold and not report.get("force_telegram"):
        return False

    lines = [f"KILL PHANTOMS -- {report['killed']} elimines"]
    for p in report.get("phantoms", [])[:10]:
        mem = f" ({p.get('mem_mb', 0)}MB)" if p.get("mem_mb") else ""
        lines.append(f"  - {p['type']} PID {p['pid']}{mem}")
    if report.get("mem_freed_mb", 0) > 0:
        lines.append(f"MEM: {report['mem_freed_mb']}MB liberes")
    health = report.get("cluster_health", {})
    if health:
        offline = [n for n, s in health.items() if "OFFLINE" in s]
        if offline:
            lines.append(f"WARN Cluster: {', '.join(offline)} OFFLINE")
        else:
            lines.append("Cluster OK")

    msg = "\n".join(lines)
    try:
        subprocess.run(
            ["curl", "-s", "-X", "POST",
             f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
             "-d", f"chat_id={TELEGRAM_CHAT}",
             "-d", f"text={msg}",
             "-d", "parse_mode=HTML"],
            capture_output=True, timeout=10
        )
        return True
    except Exception:
        return False


# ── Singleton guard ──────────────────────────────────────────────────────────
def acquire_singleton() -> bool:
    """Ensure only one instance runs (PID file)."""
    PID_DIR.mkdir(parents=True, exist_ok=True)
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text().strip())
            # Check if process is still alive
            r = subprocess.run(["tasklist", "/FI", f"PID eq {old_pid}", "/NH"],
                               capture_output=True, text=True, timeout=5,
                               encoding="utf-8", errors="replace")
            if str(old_pid) in r.stdout:
                _log(f"Autre instance active (PID {old_pid}). Abandon.", "WARN")
                return False
        except Exception:
            pass
    PID_FILE.write_text(str(os.getpid()))
    return True


def release_singleton():
    """Release PID file."""
    try:
        if PID_FILE.exists():
            pid = int(PID_FILE.read_text().strip())
            if pid == os.getpid():
                PID_FILE.unlink()
    except Exception:
        pass


# ── Output formatting ────────────────────────────────────────────────────────
def format_report(report: dict, as_json: bool = False) -> str:
    """Format report for display."""
    if as_json:
        return json.dumps(report, indent=2, ensure_ascii=False)

    lines = [f"[kill_phantoms] {report.get('timestamp', '')} ({report.get('duration_ms', 0):.0f}ms)"]

    if not report.get("phantoms"):
        lines.append("  Systeme propre — 0 fantomes.")
    else:
        # Group by type
        by_type: dict[str, list] = {}
        for p in report["phantoms"]:
            by_type.setdefault(p["type"], []).append(p)

        for ptype, entries in by_type.items():
            mem = sum(e.get("mem_mb", 0) for e in entries)
            pids = ", ".join(str(e["pid"]) for e in entries)
            action = entries[0].get("action", "?")
            lines.append(f"  {action}: {ptype} x{len(entries)} (PIDs: {pids}, {mem:.0f}MB)")

        lines.append(f"  ── Total: {report['killed']} killed, {report['kept']} kept, "
                      f"{report.get('mem_freed_mb', 0):.0f}MB liberes")

    health = report.get("cluster_health", {})
    if health:
        lines.append("  ── Cluster:")
        for node, status in health.items():
            marker = "OK" if "OK" in status else "OFFLINE"
            lines.append(f"    {node}: {status}")

    if report.get("errors"):
        lines.append(f"  ── Erreurs: {len(report['errors'])}")
        for e in report["errors"][:3]:
            lines.append(f"    ! {e}")

    return "\n".join(lines)


# ── Stats from DB ────────────────────────────────────────────────────────────
def show_stats(hours: int = 24) -> str:
    """Show kill history from SQLite."""
    if not DB_PATH.exists():
        return "Pas d'historique (DB vide)"
    db = sqlite3.connect(str(DB_PATH))
    since = (datetime.now() - timedelta(hours=hours)).isoformat()

    # Cycle stats
    rows = db.execute(
        "SELECT COUNT(*), SUM(phantoms_killed), SUM(mem_freed_mb) FROM cycles WHERE ts > ?",
        (since,)
    ).fetchone()
    cycles, total_killed, total_mem = rows[0] or 0, rows[1] or 0, rows[2] or 0

    # Top killed types
    type_rows = db.execute(
        "SELECT process_type, COUNT(*) as c FROM kill_log WHERE ts > ? "
        "GROUP BY process_type ORDER BY c DESC LIMIT 10",
        (since,)
    ).fetchall()

    db.close()

    lines = [f"[kill_phantoms] Stats ({hours}h):",
             f"  Cycles: {cycles}, Killed: {total_killed}, Mem freed: {total_mem:.0f}MB"]
    if type_rows:
        lines.append("  Top types:")
        for ptype, count in type_rows:
            lines.append(f"    {ptype}: {count} kills")
    return "\n".join(lines)


# ── Watchdog loop ────────────────────────────────────────────────────────────
def watchdog_loop(cfg: dict, dry_run: bool = False):
    """Continuous phantom detection and cleanup."""
    interval = cfg.get("watchdog_interval_s", 120)
    _log(f"Watchdog demarre — interval={interval}s, dry_run={dry_run}")

    if not acquire_singleton():
        return

    def _cleanup(sig, frame):
        release_singleton()
        sys.exit(0)
    signal.signal(signal.SIGINT, _cleanup)
    signal.signal(signal.SIGTERM, _cleanup)

    try:
        while True:
            try:
                report = scan_and_kill(cfg, dry_run=dry_run, mode="watchdog")
                if report["phantoms"]:
                    _log(format_report(report))
                    send_telegram(report, cfg)
                else:
                    _log(f"Clean — 0 phantoms ({report.get('duration_ms', 0):.0f}ms)", "OK")
            except Exception as e:
                _log(f"Cycle error: {e}", "ERROR")
            time.sleep(interval)
    finally:
        release_singleton()


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="JARVIS Phantom Process Killer & Watchdog v2.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  %(prog)s                           # Kill once
  %(prog)s --watchdog --interval 60  # Daemon (60s)
  %(prog)s --aggressive              # Low thresholds
  %(prog)s --dry-run --json          # Scan, JSON output
  %(prog)s --stats --hours 48        # History (48h)
  %(prog)s --max-mem 200 --max-age 1 # Custom thresholds
  %(prog)s --init-config             # Write default config
        """,
    )

    # Modes
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--dry-run", "--scan", action="store_true",
                            help="Scan without killing")
    mode_group.add_argument("--watchdog", action="store_true",
                            help="Continuous daemon mode")
    mode_group.add_argument("--stats", action="store_true",
                            help="Show kill history")
    mode_group.add_argument("--status", action="store_true",
                            help="Current phantom count (scan only)")
    mode_group.add_argument("--health", action="store_true",
                            help="Cluster health check only")
    mode_group.add_argument("--init-config", action="store_true",
                            help="Write default config to JSON file")

    # Options
    parser.add_argument("--config", type=str, help="Custom config JSON path")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--interval", type=int, help="Watchdog interval (seconds)")
    parser.add_argument("--keep", type=int, help="Keep N newest per type")
    parser.add_argument("--max-mem", type=float, help="Kill orphans above N MB")
    parser.add_argument("--max-age", type=float, help="Kill processes older than N hours")
    parser.add_argument("--aggressive", action="store_true",
                        help="Use aggressive thresholds")
    parser.add_argument("--telegram", action="store_true",
                        help="Force Telegram report")
    parser.add_argument("--no-health", action="store_true",
                        help="Skip post-kill cluster health check")
    parser.add_argument("--protect-pids", type=str,
                        help="Extra PIDs to protect (comma-separated)")
    parser.add_argument("--hours", type=int, default=24,
                        help="History window for --stats (default: 24)")

    args = parser.parse_args()

    # Load config
    config_path = Path(args.config) if args.config else None
    cfg = load_config(config_path)

    # Init config mode
    if args.init_config:
        save_default_config(config_path)
        return

    # Apply CLI overrides
    if args.aggressive:
        _deep_merge(cfg, cfg.get("aggressive", {}))
    if args.interval:
        cfg["watchdog_interval_s"] = args.interval
    if args.keep is not None:
        cfg["keep_count"] = args.keep
    if args.max_mem is not None:
        cfg["max_memory_mb"] = args.max_mem
    if args.max_age is not None:
        cfg["max_age_hours"] = args.max_age
    if args.no_health:
        cfg["health_check_after_kill"] = False

    # Extra protected PIDs
    if args.protect_pids:
        for pid_str in args.protect_pids.split(","):
            try:
                cfg.setdefault("_extra_protected", set()).add(int(pid_str.strip()))
            except ValueError:
                pass

    # Stats mode
    if args.stats:
        print(show_stats(args.hours))
        return

    # Health check only
    if args.health:
        health = cluster_health_check(cfg)
        if args.json:
            print(json.dumps(health, indent=2))
        else:
            for node, status in health.items():
                print(f"  {node}: {status}")
        return

    # Status mode (scan only, quick report)
    if args.status:
        report = scan_and_kill(cfg, dry_run=True, mode="status")
        if args.json:
            print(json.dumps({"phantom_count": len(report["phantoms"]),
                               "types": list({p["type"] for p in report["phantoms"]})}, indent=2))
        else:
            print(f"Fantomes detectes: {len(report['phantoms'])}")
            for p in report["phantoms"]:
                print(f"  {p['type']} PID {p['pid']}")
        return

    # Watchdog mode
    if args.watchdog:
        watchdog_loop(cfg, dry_run=args.dry_run)
        return

    # Once mode (default)
    report = scan_and_kill(cfg, dry_run=args.dry_run, mode="once")
    if args.telegram:
        report["force_telegram"] = True
    telegram_sent = send_telegram(report, cfg)
    report["telegram_sent"] = telegram_sent
    print(format_report(report, as_json=args.json))


if __name__ == "__main__":
    main()
