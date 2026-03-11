# Auto-Heal v2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Evolve the auto-heal daemon into a multi-pipeline interactive system with Telegram InlineKeyboard validation, parallel cluster consensus, log watching, and a risk-rated fix catalogue.

**Architecture:** 4 new modules in `src/` (heal_detectors, heal_fixes, heal_pipeline, heal_telegram) orchestrated by the existing `scripts/auto_heal_daemon.py`. All fixes require Telegram approval via InlineKeyboard buttons. Analysis is done in parallel across M1+OL1+M2 with weighted consensus voting.

**Tech Stack:** Python 3.13, sqlite3, urllib.request, threading, Telegram Bot API (getUpdates polling + InlineKeyboard), LM Studio/Ollama HTTP APIs.

**Design doc:** `docs/plans/2026-03-07-auto-heal-v2-design.md`

---

## Task 1: heal_detectors.py — Extract + Extend Detectors

**Files:**
- Create: `src/heal_detectors.py`
- Test: `tests/test_heal_detectors.py`
- Reference: `scripts/auto_heal_daemon.py:219-364` (existing detectors to extract)

**Context:** The existing `auto_heal_daemon.py` has 5 inline detector functions. We extract them into a dedicated module and add 2 new ones (log watcher, latency). The `Issue` and `CycleReport` dataclasses also move here as shared types.

**Step 1: Write the failing tests**

```python
# tests/test_heal_detectors.py
"""Tests for heal_detectors module."""
import json
import sqlite3
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
from dataclasses import dataclass

import pytest

# Will import after creation
# from src.heal_detectors import (
#     Issue, detect_nodes, detect_services, detect_logs,
#     detect_thermal, detect_doublons, detect_db, detect_latency,
#     LogWatcher,
# )


def test_issue_dataclass():
    from src.heal_detectors import Issue
    i = Issue("node", "critical", "M1", "M1 offline")
    assert i.category == "node"
    assert i.severity == "critical"
    assert i.component == "M1"
    assert i.resolved is False
    assert i.risk_level == "unknown"


def test_detect_nodes_all_up():
    from src.heal_detectors import detect_nodes
    with patch("src.heal_detectors.check_port", return_value=True):
        with patch("src.heal_detectors._check_m1_model", return_value=True):
            issues = detect_nodes()
    assert len(issues) == 0


def test_detect_nodes_m1_down():
    from src.heal_detectors import detect_nodes
    def fake_port(host, port, timeout=2.0):
        return not (host == "127.0.0.1" and port == 1234)
    with patch("src.heal_detectors.check_port", side_effect=fake_port):
        issues = detect_nodes()
    assert len(issues) == 1
    assert issues[0].severity == "critical"
    assert issues[0].component == "M1"


def test_detect_services_all_up():
    from src.heal_detectors import detect_services
    with patch("src.heal_detectors.check_port", return_value=True):
        issues = detect_services()
    assert len(issues) == 0


def test_detect_services_ws_down():
    from src.heal_detectors import detect_services
    def fake_port(host, port, timeout=2.0):
        return port != 9742
    with patch("src.heal_detectors.check_port", side_effect=fake_port):
        issues = detect_services()
    ws_issues = [i for i in issues if i.component == "jarvis_ws"]
    assert len(ws_issues) == 1
    assert ws_issues[0].severity == "critical"


def test_log_watcher_detects_traceback(tmp_path):
    from src.heal_detectors import LogWatcher
    log_file = tmp_path / "test.log"
    log_file.write_text(
        "2026-03-07 INFO: normal line\n"
        "Traceback (most recent call last):\n"
        "  File 'test.py', line 1\n"
        "ValueError: bad value\n"
        "2026-03-07 INFO: normal again\n",
        encoding="utf-8",
    )
    watcher = LogWatcher([log_file])
    issues = watcher.scan()
    assert len(issues) >= 1
    assert issues[0].category == "log"
    assert "Traceback" in issues[0].message or "ValueError" in issues[0].message


def test_log_watcher_dedup(tmp_path):
    from src.heal_detectors import LogWatcher
    log_file = tmp_path / "test.log"
    log_file.write_text("Traceback (most recent call last):\nValueError: x\n", encoding="utf-8")
    watcher = LogWatcher([log_file])
    issues1 = watcher.scan()
    issues2 = watcher.scan()  # same content, should dedup
    assert len(issues2) == 0


def test_detect_latency_normal():
    from src.heal_detectors import detect_latency
    with patch("src.heal_detectors.check_port", return_value=True):
        with patch("src.heal_detectors._ping_node", return_value=0.05):
            issues = detect_latency()
    assert len(issues) == 0


def test_detect_latency_slow():
    from src.heal_detectors import detect_latency
    with patch("src.heal_detectors.check_port", return_value=True):
        # Return very slow response
        with patch("src.heal_detectors._ping_node", return_value=5.0):
            issues = detect_latency()
    # Should flag at least one latency warning
    assert any(i.category == "latency" for i in issues)


def test_detect_thermal_cool():
    from src.heal_detectors import detect_thermal
    fake_output = "0, NVIDIA GeForce RTX 4090, 45\n1, NVIDIA GeForce RTX 4090, 50\n"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=fake_output, returncode=0)
        issues = detect_thermal()
    assert len(issues) == 0


def test_detect_thermal_hot():
    from src.heal_detectors import detect_thermal
    fake_output = "0, NVIDIA GeForce RTX 4090, 87\n"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=fake_output, returncode=0)
        issues = detect_thermal()
    assert len(issues) == 1
    assert issues[0].severity == "critical"


def test_detect_db_ok(tmp_path):
    from src.heal_detectors import detect_db
    db_path = tmp_path / "test.db"
    db = sqlite3.connect(str(db_path))
    db.execute("CREATE TABLE t (id INTEGER)")
    db.commit()
    db.close()
    with patch("src.heal_detectors.DB_PATHS", {"test": db_path}):
        issues = detect_db()
    assert len(issues) == 0
```

**Step 2: Run tests to verify they fail**

Run: `cd F:/BUREAU/turbo && python -m pytest tests/test_heal_detectors.py -v 2>&1 | head -30`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.heal_detectors'`

**Step 3: Implement heal_detectors.py**

Create `src/heal_detectors.py` with:

```python
"""JARVIS Auto-Heal Detectors — 7 detection modules for cluster health.

Detectors:
  detect_nodes     — Cluster node health (M1/M2/M3/OL1 port + model check)
  detect_services  — Service port checks (7 services)
  detect_logs      — LogWatcher: tail log files for Traceback/Exception
  detect_thermal   — GPU temperature via nvidia-smi
  detect_doublons  — Duplicate Python processes
  detect_db        — SQLite integrity_check
  detect_latency   — HTTP ping timing, baseline comparison
"""
from __future__ import annotations

import json
import os
import re
import socket
import sqlite3
import subprocess
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

# ── Shared data classes ──────────────────────────────────────────────

@dataclass
class Issue:
    category: str       # "node", "service", "process", "db", "thermal", "log", "latency"
    severity: str       # "critical", "warning", "info"
    component: str      # "M1", "jarvis_ws", "etoile.db", etc.
    message: str
    suggestion: str = ""
    fix_cmd: str = ""
    fix_fn: str = ""
    risk_level: str = "unknown"  # "safe", "moderate", "dangerous", "unknown"
    retries: int = 0
    max_retries: int = 3
    resolved: bool = False
    context: str = ""   # Extra context (log lines, etc.)


@dataclass
class CycleReport:
    cycle: int
    ts: str
    issues_found: int = 0
    issues_fixed: int = 0
    issues_failed: int = 0
    issues: list[dict] = field(default_factory=list)
    duration_ms: int = 0


# ── Config ───────────────────────────────────────────────────────────

NODES = {
    "M1": {"url": "http://127.0.0.1:1234", "ip": "127.0.0.1", "port": 1234},
    "M2": {"url": "http://192.168.1.26:1234", "ip": "192.168.1.26", "port": 1234},
    "M3": {"url": "http://192.168.1.113:1234", "ip": "192.168.1.113", "port": 1234},
    "OL1": {"url": "http://127.0.0.1:11434", "ip": "127.0.0.1", "port": 11434},
}
SERVICES = {
    "n8n": {"port": 5678, "critical": False},
    "dashboard": {"port": 8080, "critical": False},
    "gemini_proxy": {"port": 18791, "critical": False},
    "canvas_proxy": {"port": 18800, "critical": False},
    "openclaw": {"port": 18789, "critical": False},
    "jarvis_ws": {"port": 9742, "critical": True},
    "mcp_sse": {"port": 8901, "critical": False},
}
LOG_PATHS = [
    ROOT / "logs" / "auto_heal.log",
    ROOT / "logs" / "unified_boot.log",
    ROOT / "logs" / "cluster_boot.log",
    ROOT / "logs" / "watchdog.log",
    ROOT / "logs" / "direct-proxy.log",
    ROOT / "logs" / "telegram-bot.log",
]
DB_PATHS = {
    "etoile": ROOT / "data" / "etoile.db",
    "jarvis": ROOT / "data" / "jarvis.db",
}

ERROR_PATTERNS = [
    re.compile(r"Traceback \(most recent call last\)", re.IGNORECASE),
    re.compile(r"^\w+Error:", re.MULTILINE),
    re.compile(r"^\w+Exception:", re.MULTILINE),
    re.compile(r"CRITICAL", re.IGNORECASE),
    re.compile(r"ConnectionRefused", re.IGNORECASE),
]

# ── Helpers ──────────────────────────────────────────────────────────

def check_port(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        r = s.connect_ex((host, port))
        s.close()
        return r == 0
    except (socket.error, OSError):
        return False


def http_get(url: str, timeout: float = 5.0) -> dict | None:
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def _check_m1_model() -> bool:
    try:
        lms = str(Path.home() / ".lmstudio" / "bin" / "lms.exe")
        r = subprocess.run(
            [lms, "ps"], capture_output=True, timeout=10,
            encoding="utf-8", errors="replace",
        )
        output = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]|\[\?25[hl]", "", r.stdout + r.stderr)
        return "qwen3-8b" in output
    except Exception:
        return True  # assume OK if lms not available


def _ping_node(url: str) -> float:
    t0 = time.time()
    try:
        req = urllib.request.Request(f"{url}/api/v1/models")
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
        return time.time() - t0
    except Exception:
        return 999.0


# ── Detectors ────────────────────────────────────────────────────────

def detect_nodes() -> list[Issue]:
    issues = []
    for name, cfg in NODES.items():
        if not check_port(cfg["ip"], cfg["port"]):
            sev = "critical" if name == "M1" else "warning"
            fix = ""
            if name == "M1": fix = "lms server start"
            elif name == "OL1": fix = "ollama serve"
            issues.append(Issue(
                "node", sev, name,
                f"{name} ({cfg['ip']}:{cfg['port']}) OFFLINE",
                f"Redemarrer {name}" + (f": {fix}" if fix else " (distant)"),
                fix_cmd=fix, risk_level="safe" if fix else "unknown",
            ))
        elif name == "M1" and not _check_m1_model():
            issues.append(Issue(
                "node", "critical", "M1",
                "M1 actif mais qwen3-8b PAS charge",
                "Charger le modele",
                fix_cmd="lms load qwen/qwen3-8b --gpu max -c 28813 --parallel 4 -y",
                risk_level="safe",
            ))
    return issues


def detect_services() -> list[Issue]:
    issues = []
    for name, cfg in SERVICES.items():
        if not check_port("127.0.0.1", cfg["port"]):
            sev = "critical" if cfg.get("critical") else "warning"
            issues.append(Issue(
                "service", sev, name,
                f"Service {name} OFFLINE (:{cfg['port']})",
                f"Relancer {name} via singleton",
                fix_fn=f"restart_service:{name}",
                risk_level="safe",
            ))
    return issues


def detect_thermal() -> list[Issue]:
    issues = []
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, timeout=10, encoding="utf-8", errors="replace",
        )
        for line in r.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 3 and parts[2].isdigit():
                temp = int(parts[2])
                if temp >= 85:
                    issues.append(Issue(
                        "thermal", "critical", f"GPU{parts[0]}",
                        f"GPU{parts[0]} {parts[1]} a {temp}C",
                        "Reduire charge, deporter vers M2/OL1",
                        risk_level="moderate",
                    ))
                elif temp >= 75:
                    issues.append(Issue(
                        "thermal", "warning", f"GPU{parts[0]}",
                        f"GPU{parts[0]} {parts[1]} a {temp}C",
                        "Surveiller, reduire contexte si necessaire",
                        risk_level="safe",
                    ))
    except Exception:
        pass
    return issues


def detect_db() -> list[Issue]:
    issues = []
    for name, path in DB_PATHS.items():
        if not path.exists():
            issues.append(Issue("db", "warning", name, f"Base {name} absente"))
            continue
        try:
            db = sqlite3.connect(str(path))
            result = db.execute("PRAGMA integrity_check").fetchone()
            db.close()
            if not result or result[0] != "ok":
                issues.append(Issue(
                    "db", "critical", name,
                    f"Base {name} corrompue: {result}",
                    "PRAGMA recover ou restaurer backup",
                    fix_fn="clear_db_lock", risk_level="moderate",
                ))
        except sqlite3.Error as e:
            issues.append(Issue("db", "warning", name, f"Erreur DB {name}: {e}"))
    return issues


def detect_doublons() -> list[Issue]:
    issues = []
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter 'name=\"python.exe\"' | "
             "Select-Object ProcessId,CommandLine | ConvertTo-Json"],
            capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace",
        )
        procs = json.loads(r.stdout) if r.stdout.strip() else []
        if isinstance(procs, dict):
            procs = [procs]
        scripts: dict[str, list[int]] = {}
        for p in procs:
            cmd = p.get("CommandLine", "") or ""
            pid = p.get("ProcessId", 0)
            if "server.py" in cmd and "python_ws" in cmd:
                scripts.setdefault("python_ws/server.py", []).append(pid)
        for script, pids in scripts.items():
            if len(pids) > 1:
                issues.append(Issue(
                    "process", "warning", script,
                    f"Doublon: {script} ({len(pids)} instances: {pids})",
                    "Tuer les doublons sauf le plus recent",
                    fix_fn="kill_doublon", risk_level="moderate",
                ))
    except Exception:
        pass
    return issues


def detect_latency() -> list[Issue]:
    issues = []
    _baselines: dict[str, float] = {"M1": 0.1, "OL1": 0.05, "M2": 0.5, "M3": 0.5}
    for name, cfg in NODES.items():
        if not check_port(cfg["ip"], cfg["port"]):
            continue
        latency = _ping_node(cfg["url"])
        baseline = _baselines.get(name, 0.2)
        if latency > baseline * 3:
            issues.append(Issue(
                "latency", "warning", name,
                f"{name} latence {latency:.2f}s (baseline {baseline:.2f}s, {latency/baseline:.1f}x)",
                f"Verifier charge {name}",
                risk_level="safe",
            ))
    return issues


# ── Log Watcher ──────────────────────────────────────────────────────

class LogWatcher:
    def __init__(self, paths: list[Path] | None = None, dedup_window: int = 300):
        self._paths = paths or LOG_PATHS
        self._offsets: dict[str, int] = {}  # path -> last read offset
        self._seen: dict[str, float] = {}   # error_hash -> timestamp
        self._dedup_window = dedup_window

    def scan(self) -> list[Issue]:
        issues = []
        now = time.time()
        # Clean old dedup entries
        self._seen = {k: v for k, v in self._seen.items() if now - v < self._dedup_window}

        for path in self._paths:
            if not path.exists():
                continue
            try:
                key = str(path)
                size = path.stat().st_size
                offset = self._offsets.get(key, 0)
                if size < offset:
                    offset = 0  # file truncated/rotated
                if size == offset:
                    continue  # no new data

                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    f.seek(offset)
                    new_lines = f.readlines()
                    self._offsets[key] = f.tell()

                # Scan for error patterns
                for i, line in enumerate(new_lines):
                    for pattern in ERROR_PATTERNS:
                        if pattern.search(line):
                            # Build context (5 lines around)
                            start = max(0, i - 2)
                            end = min(len(new_lines), i + 5)
                            ctx = "".join(new_lines[start:end]).strip()
                            # Dedup key
                            dedup_key = f"{path.name}:{line.strip()[:80]}"
                            if dedup_key in self._seen:
                                break
                            self._seen[dedup_key] = now
                            issues.append(Issue(
                                "log", "warning", path.name,
                                f"Erreur dans {path.name}: {line.strip()[:120]}",
                                "Verifier les logs pour details",
                                context=ctx[:500],
                            ))
                            break  # one issue per line
            except Exception:
                continue
        return issues


# ── Run all detectors ────────────────────────────────────────────────

_log_watcher = LogWatcher()

def run_all_detectors() -> list[Issue]:
    all_issues: list[Issue] = []
    all_issues.extend(detect_nodes())
    all_issues.extend(detect_services())
    all_issues.extend(_log_watcher.scan())
    all_issues.extend(detect_thermal())
    all_issues.extend(detect_doublons())
    all_issues.extend(detect_db())
    all_issues.extend(detect_latency())
    return all_issues
```

**Step 4: Run tests to verify they pass**

Run: `cd F:/BUREAU/turbo && python -m pytest tests/test_heal_detectors.py -v`
Expected: All 11 tests PASS

**Step 5: Commit**

```bash
git add src/heal_detectors.py tests/test_heal_detectors.py
git commit -m "feat(heal): extract detectors into src/heal_detectors.py + add log watcher & latency"
```

---

## Task 2: heal_fixes.py — Fix Catalogue with Risk Levels

**Files:**
- Create: `src/heal_fixes.py`
- Test: `tests/test_heal_fixes.py`
- Reference: `scripts/auto_heal_daemon.py:370-448` (existing fix logic), `src/process_singleton.py` (singleton import)

**Context:** Extract fix logic from daemon, create a registry of named fixes with risk levels and verify() methods. Each fix is a callable that returns (success: bool, message: str).

**Step 1: Write the failing tests**

```python
# tests/test_heal_fixes.py
"""Tests for heal_fixes module."""
from unittest.mock import patch, MagicMock
import pytest


def test_fix_registry_has_entries():
    from src.heal_fixes import FIX_REGISTRY
    assert "restart_service" in FIX_REGISTRY
    assert "reload_model" in FIX_REGISTRY
    assert "kill_doublon" in FIX_REGISTRY


def test_fix_entry_structure():
    from src.heal_fixes import FIX_REGISTRY
    entry = FIX_REGISTRY["restart_service"]
    assert entry["risk"] in ("safe", "moderate", "dangerous")
    assert callable(entry["fn"])
    assert callable(entry["verify"])


def test_restart_service_calls_singleton():
    from src.heal_fixes import execute_fix
    from src.heal_detectors import Issue
    issue = Issue("service", "critical", "dashboard", "dashboard OFFLINE",
                  fix_fn="restart_service:dashboard", risk_level="safe")
    with patch("src.heal_fixes._do_restart_service", return_value=(True, "OK")):
        ok, msg = execute_fix(issue)
    assert ok is True


def test_execute_fix_unknown():
    from src.heal_fixes import execute_fix
    from src.heal_detectors import Issue
    issue = Issue("node", "critical", "M1", "M1 offline", fix_fn="nonexistent")
    ok, msg = execute_fix(issue)
    assert ok is False
    assert "inconnu" in msg.lower() or "unknown" in msg.lower()


def test_execute_fix_by_cmd():
    from src.heal_fixes import execute_fix
    from src.heal_detectors import Issue
    issue = Issue("node", "critical", "M1", "M1 offline",
                  fix_cmd="echo test", risk_level="safe")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        ok, msg = execute_fix(issue)
    assert ok is True


def test_get_risk_level():
    from src.heal_fixes import get_risk_level
    assert get_risk_level("restart_service:jarvis_ws") == "safe"
    assert get_risk_level("kill_doublon") == "moderate"
    assert get_risk_level("rollback_config") == "dangerous"
    assert get_risk_level("nonexistent") == "unknown"
```

**Step 2: Run tests to verify they fail**

Run: `cd F:/BUREAU/turbo && python -m pytest tests/test_heal_fixes.py -v 2>&1 | head -20`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.heal_fixes'`

**Step 3: Implement heal_fixes.py**

```python
# src/heal_fixes.py
"""JARVIS Auto-Heal Fix Catalogue — risk-rated fixes with verify().

Each fix is registered with:
  - risk: safe / moderate / dangerous
  - fn: callable(issue) -> (success, message)
  - verify: callable(issue) -> bool (confirms the fix worked)
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


def _check_port(host: str, port: int, timeout: float = 2.0) -> bool:
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        r = s.connect_ex((host, port))
        s.close()
        return r == 0
    except (socket.error, OSError):
        return False


# ── Fix implementations ──────────────────────────────────────────────

SERVICES_CFG = {
    "n8n": {"port": 5678},
    "dashboard": {"port": 8080},
    "gemini_proxy": {"port": 18791},
    "canvas_proxy": {"port": 18800},
    "openclaw": {"port": 18789},
    "jarvis_ws": {"port": 9742},
    "mcp_sse": {"port": 8901},
}

def _do_restart_service(issue) -> tuple[bool, str]:
    svc = issue.fix_fn.split(":")[-1] if ":" in issue.fix_fn else issue.component
    cfg = SERVICES_CFG.get(svc)
    if not cfg:
        return False, f"Service inconnu: {svc}"
    port = cfg["port"]
    try:
        from src.process_singleton import singleton
        singleton.acquire(svc, pid=0, port=port)
        time.sleep(1)
    except Exception:
        pass

    uv = str(Path.home() / ".local" / "bin" / "uv.exe")
    cmds = {
        "dashboard": [uv, "run", "python", str(ROOT / "dashboard" / "server.py")],
        "jarvis_ws": [uv, "run", "python", str(ROOT / "python_ws" / "server.py")],
        "canvas_proxy": ["node", str(ROOT / "canvas" / "direct-proxy.js")],
        "gemini_proxy": ["node", str(ROOT / "gemini-proxy.js")],
        "mcp_sse": [uv, "run", "python", "-m", "src.mcp_server_sse", "--port", "8901"],
    }
    cmd = cmds.get(svc)
    if not cmd:
        return False, f"Pas de commande pour {svc}"

    kwargs: dict[str, Any] = {"cwd": str(ROOT), "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if sys.platform == "win32":
        kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
        )
    proc = subprocess.Popen(cmd, **kwargs)
    try:
        from src.process_singleton import singleton
        singleton.register(svc, proc.pid)
    except Exception:
        pass

    for _ in range(15):
        if _check_port("127.0.0.1", port):
            return True, f"{svc} relance (PID {proc.pid})"
        time.sleep(1)
    return False, f"{svc}: port {port} pas ouvert apres 15s"


def _verify_service(issue) -> bool:
    svc = issue.fix_fn.split(":")[-1] if ":" in issue.fix_fn else issue.component
    port = SERVICES_CFG.get(svc, {}).get("port", 0)
    return _check_port("127.0.0.1", port) if port else False


def _do_reload_model(issue) -> tuple[bool, str]:
    if not issue.fix_cmd:
        return False, "Pas de commande fix_cmd"
    lms = str(Path.home() / ".lmstudio" / "bin" / "lms.exe")
    cmd = issue.fix_cmd.replace("lms ", f"{lms} ", 1) if issue.fix_cmd.startswith("lms ") else issue.fix_cmd
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, timeout=180,
                           encoding="utf-8", errors="replace")
        return r.returncode == 0, r.stdout[:200] if r.returncode == 0 else r.stderr[:200]
    except Exception as e:
        return False, str(e)


def _verify_model(issue) -> bool:
    from src.heal_detectors import _check_m1_model
    return _check_m1_model()


def _do_kill_doublon(issue) -> tuple[bool, str]:
    # Extract PIDs from issue message: "... (2 instances: [1234, 5678])"
    import re
    m = re.search(r"\[([0-9, ]+)\]", issue.message)
    if not m:
        return False, "Pas de PIDs trouves dans le message"
    pids = [int(p.strip()) for p in m.group(1).split(",")]
    if len(pids) < 2:
        return False, "Moins de 2 PIDs"
    # Kill all except the newest (highest PID)
    keep = max(pids)
    killed = []
    for pid in pids:
        if pid == keep:
            continue
        try:
            r = subprocess.run(["taskkill", "/PID", str(pid), "/F", "/T"],
                               capture_output=True, timeout=10, encoding="utf-8", errors="replace")
            if r.returncode == 0:
                killed.append(pid)
        except Exception:
            pass
    return len(killed) > 0, f"Killed PIDs: {killed}, kept: {keep}"


def _verify_no_doublon(issue) -> bool:
    from src.heal_detectors import detect_doublons
    return len(detect_doublons()) == 0


def _do_shell_cmd(issue) -> tuple[bool, str]:
    if not issue.fix_cmd:
        return False, "Pas de commande"
    lms = str(Path.home() / ".lmstudio" / "bin" / "lms.exe")
    cmd = issue.fix_cmd
    if cmd.startswith("lms "):
        cmd = cmd.replace("lms ", f"{lms} ", 1)
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, timeout=180,
                           encoding="utf-8", errors="replace")
        return r.returncode == 0, (r.stdout or r.stderr)[:200]
    except Exception as e:
        return False, str(e)


def _do_clear_db_lock(issue) -> tuple[bool, str]:
    import sqlite3
    db_name = issue.component
    db_paths = {"etoile": ROOT / "data" / "etoile.db", "jarvis": ROOT / "data" / "jarvis.db"}
    path = db_paths.get(db_name)
    if not path or not path.exists():
        return False, f"DB {db_name} introuvable"
    try:
        db = sqlite3.connect(str(path))
        db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        db.commit()
        db.close()
        return True, f"WAL checkpoint OK pour {db_name}"
    except Exception as e:
        return False, str(e)


def _verify_db(issue) -> bool:
    import sqlite3
    db_paths = {"etoile": ROOT / "data" / "etoile.db", "jarvis": ROOT / "data" / "jarvis.db"}
    path = db_paths.get(issue.component)
    if not path or not path.exists():
        return False
    try:
        db = sqlite3.connect(str(path))
        r = db.execute("PRAGMA integrity_check").fetchone()
        db.close()
        return r and r[0] == "ok"
    except Exception:
        return False


def _do_restart_node(issue) -> tuple[bool, str]:
    return _do_shell_cmd(issue)


def _verify_node(issue) -> bool:
    from src.heal_detectors import check_port, NODES
    cfg = NODES.get(issue.component)
    return check_port(cfg["ip"], cfg["port"]) if cfg else False


# ── Fix Registry ─────────────────────────────────────────────────────

FIX_REGISTRY: dict[str, dict] = {
    "restart_service": {"risk": "safe", "fn": _do_restart_service, "verify": _verify_service},
    "reload_model":    {"risk": "safe", "fn": _do_reload_model, "verify": _verify_model},
    "kill_doublon":    {"risk": "moderate", "fn": _do_kill_doublon, "verify": _verify_no_doublon},
    "clear_db_lock":   {"risk": "moderate", "fn": _do_clear_db_lock, "verify": _verify_db},
    "restart_node":    {"risk": "dangerous", "fn": _do_restart_node, "verify": _verify_node},
    "rollback_config": {"risk": "dangerous", "fn": _do_shell_cmd, "verify": lambda i: True},
    "swap_node":       {"risk": "moderate", "fn": _do_shell_cmd, "verify": lambda i: True},
}


def get_risk_level(fix_fn: str) -> str:
    key = fix_fn.split(":")[0] if ":" in fix_fn else fix_fn
    entry = FIX_REGISTRY.get(key)
    return entry["risk"] if entry else "unknown"


def execute_fix(issue) -> tuple[bool, str]:
    # Try fix_fn first (named fix from registry)
    if issue.fix_fn:
        key = issue.fix_fn.split(":")[0] if ":" in issue.fix_fn else issue.fix_fn
        entry = FIX_REGISTRY.get(key)
        if entry:
            return entry["fn"](issue)
        return False, f"Fix inconnu: {issue.fix_fn}"

    # Fallback to fix_cmd (shell command)
    if issue.fix_cmd:
        return _do_shell_cmd(issue)

    return False, "Aucun fix disponible"


def verify_fix(issue) -> bool:
    if issue.fix_fn:
        key = issue.fix_fn.split(":")[0] if ":" in issue.fix_fn else issue.fix_fn
        entry = FIX_REGISTRY.get(key)
        if entry:
            return entry["verify"](issue)
    return False
```

**Step 4: Run tests**

Run: `cd F:/BUREAU/turbo && python -m pytest tests/test_heal_fixes.py -v`
Expected: All 6 tests PASS

**Step 5: Commit**

```bash
git add src/heal_fixes.py tests/test_heal_fixes.py
git commit -m "feat(heal): add fix catalogue with risk levels and verify()"
```

---

## Task 3: heal_pipeline.py — Parallel Multi-Agent Consensus

**Files:**
- Create: `src/heal_pipeline.py`
- Test: `tests/test_heal_pipeline.py`
- Reference: `scripts/auto_heal_daemon.py:173-213` (existing ask_m1/ask_ol1)

**Context:** Dispatch each issue to M1+OL1+M2 in parallel threads. Each agent returns structured analysis. Weighted consensus vote determines the fix recommendation. Uses threading (not asyncio) since the daemon is synchronous.

**Step 1: Write the failing tests**

```python
# tests/test_heal_pipeline.py
"""Tests for heal_pipeline — parallel multi-agent consensus."""
from unittest.mock import patch, MagicMock
import pytest


def test_agent_response_parse():
    from src.heal_pipeline import parse_agent_response
    raw = "Cause: M1 surcharge\nFix: restart service\nRisque: safe\nConfiance: 85"
    r = parse_agent_response(raw)
    assert r["cause"] != ""
    assert r["confidence"] >= 0


def test_consensus_single_agent():
    from src.heal_pipeline import compute_consensus
    responses = [{"agent": "M1", "cause": "surcharge", "fix": "restart",
                  "risk": "safe", "confidence": 90}]
    weights = {"M1": 1.9}
    result = compute_consensus(responses, weights)
    assert result["recommended_fix"] == "restart"
    assert result["confidence"] > 0


def test_consensus_majority():
    from src.heal_pipeline import compute_consensus
    responses = [
        {"agent": "M1", "cause": "surcharge", "fix": "restart", "risk": "safe", "confidence": 90},
        {"agent": "OL1", "cause": "surcharge", "fix": "restart", "risk": "safe", "confidence": 80},
        {"agent": "M2", "cause": "bug", "fix": "rollback", "risk": "dangerous", "confidence": 70},
    ]
    weights = {"M1": 1.9, "OL1": 1.4, "M2": 1.5}
    result = compute_consensus(responses, weights)
    # M1(1.9) + OL1(1.4) = 3.3 for restart vs M2(1.5) for rollback
    assert result["recommended_fix"] == "restart"


def test_consensus_empty():
    from src.heal_pipeline import compute_consensus
    result = compute_consensus([], {})
    assert result["recommended_fix"] == ""
    assert result["confidence"] == 0


def test_analyze_issue_parallel():
    from src.heal_pipeline import analyze_issue
    from src.heal_detectors import Issue
    issue = Issue("service", "critical", "jarvis_ws", "jarvis_ws OFFLINE")
    fake_response = '{"cause":"port bloque","fix":"restart","risk":"safe","confidence":85}'
    with patch("src.heal_pipeline._ask_agent", return_value=fake_response):
        with patch("src.heal_pipeline._get_alive_agents", return_value=["M1"]):
            result = analyze_issue(issue)
    assert "recommended_fix" in result
```

**Step 2: Run to verify fail**

Run: `cd F:/BUREAU/turbo && python -m pytest tests/test_heal_pipeline.py -v 2>&1 | head -20`

**Step 3: Implement heal_pipeline.py**

```python
# src/heal_pipeline.py
"""JARVIS Auto-Heal Pipeline — Parallel multi-agent consensus analysis.

Dispatches issues to M1+OL1+M2 in parallel threads.
Each agent returns structured analysis (cause, fix, risk, confidence).
Weighted consensus determines the recommended fix.
"""
from __future__ import annotations

import json
import re
import socket
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

AGENT_CONFIG = {
    "M1": {
        "url": "http://127.0.0.1:1234/api/v1/chat",
        "ip": "127.0.0.1", "port": 1234,
        "model": "qwen3-8b", "weight": 1.9,
        "format": "lmstudio",
        "timeout": 30,
    },
    "OL1": {
        "url": "http://127.0.0.1:11434/api/chat",
        "ip": "127.0.0.1", "port": 11434,
        "model": "qwen3:1.7b", "weight": 1.4,
        "format": "ollama",
        "timeout": 15,
    },
    "M2": {
        "url": "http://192.168.1.26:1234/api/v1/chat",
        "ip": "192.168.1.26", "port": 1234,
        "model": "deepseek-r1-0528-qwen3-8b", "weight": 1.5,
        "format": "lmstudio",
        "timeout": 60,
    },
}

ANALYSIS_PROMPT = """Tu es JARVIS, systeme de diagnostic cluster. Analyse cette erreur et reponds en JSON strict:
{{"cause": "cause probable en 1 phrase", "fix": "commande ou action recommandee", "risk": "safe|moderate|dangerous", "confidence": 0-100}}

Erreur: [{category}] {component}: {message}
Contexte: {context}

Reponds UNIQUEMENT avec le JSON, rien d'autre."""


def _check_port(host: str, port: int) -> bool:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        r = s.connect_ex((host, port))
        s.close()
        return r == 0
    except (socket.error, OSError):
        return False


def _get_alive_agents() -> list[str]:
    return [name for name, cfg in AGENT_CONFIG.items()
            if _check_port(cfg["ip"], cfg["port"])]


def _ask_agent(agent_name: str, prompt: str) -> str:
    cfg = AGENT_CONFIG[agent_name]
    try:
        if cfg["format"] == "lmstudio":
            body = json.dumps({
                "model": cfg["model"],
                "input": f"/nothink\n{prompt}",
                "temperature": 0.2, "max_output_tokens": 512,
                "stream": False, "store": False,
            }).encode()
            req = urllib.request.Request(cfg["url"], body, {"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=cfg["timeout"]) as resp:
                d = json.loads(resp.read().decode())
                for o in reversed(d.get("output", [])):
                    if o.get("type") == "message":
                        content = o.get("content", "")
                        if isinstance(content, list):
                            return content[0].get("text", "") if content else ""
                        return str(content)
            return ""
        else:  # ollama
            body = json.dumps({
                "model": cfg["model"],
                "messages": [{"role": "user", "content": f"/nothink\n{prompt}"}],
                "stream": False,
            }).encode()
            req = urllib.request.Request(cfg["url"], body, {"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=cfg["timeout"]) as resp:
                d = json.loads(resp.read().decode())
                return d.get("message", {}).get("content", "")
    except Exception:
        return ""


def parse_agent_response(raw: str) -> dict[str, Any]:
    # Try JSON parse first
    try:
        # Extract JSON from potential wrapper text
        m = re.search(r'\{[^}]+\}', raw, re.DOTALL)
        if m:
            d = json.loads(m.group())
            return {
                "cause": str(d.get("cause", "")),
                "fix": str(d.get("fix", "")),
                "risk": str(d.get("risk", "unknown")),
                "confidence": int(d.get("confidence", 50)),
            }
    except (json.JSONDecodeError, ValueError):
        pass
    # Fallback: extract from free text
    return {
        "cause": raw[:100] if raw else "",
        "fix": "",
        "risk": "unknown",
        "confidence": 30,
    }


def compute_consensus(responses: list[dict], weights: dict[str, float]) -> dict[str, Any]:
    if not responses:
        return {"recommended_fix": "", "risk": "unknown", "confidence": 0,
                "cause": "", "agents": [], "quorum": False}

    # Group by fix recommendation
    fix_votes: dict[str, float] = {}
    fix_details: dict[str, list[dict]] = {}
    total_weight = 0

    for r in responses:
        agent = r.get("agent", "?")
        fix = r.get("fix", "")
        w = weights.get(agent, 1.0)
        conf = r.get("confidence", 50) / 100
        score = w * conf
        fix_votes[fix] = fix_votes.get(fix, 0) + score
        fix_details.setdefault(fix, []).append(r)
        total_weight += w

    # Pick highest voted fix
    best_fix = max(fix_votes, key=fix_votes.get)
    best_score = fix_votes[best_fix]
    quorum = (best_score / total_weight) >= 0.65 if total_weight > 0 else False

    # Aggregate risk (take worst case from majority)
    risks = [r.get("risk", "unknown") for r in fix_details.get(best_fix, [])]
    risk_order = {"safe": 0, "moderate": 1, "dangerous": 2, "unknown": 1}
    worst_risk = max(risks, key=lambda x: risk_order.get(x, 1)) if risks else "unknown"

    # Average confidence
    confs = [r.get("confidence", 50) for r in fix_details.get(best_fix, [])]
    avg_conf = sum(confs) // len(confs) if confs else 0

    # Cause from highest-weight agent
    causes = fix_details.get(best_fix, [])
    cause = causes[0].get("cause", "") if causes else ""

    return {
        "recommended_fix": best_fix,
        "risk": worst_risk,
        "confidence": avg_conf,
        "cause": cause,
        "agents": [r.get("agent", "?") for r in responses],
        "quorum": quorum,
        "votes": fix_votes,
    }


def analyze_issue(issue) -> dict[str, Any]:
    prompt = ANALYSIS_PROMPT.format(
        category=issue.category, component=issue.component,
        message=issue.message, context=getattr(issue, "context", ""),
    )
    alive = _get_alive_agents()
    if not alive:
        return {"recommended_fix": "", "risk": "unknown", "confidence": 0,
                "cause": "Aucun agent disponible", "agents": [], "quorum": False}

    responses = []
    with ThreadPoolExecutor(max_workers=len(alive)) as pool:
        futures = {pool.submit(_ask_agent, name, prompt): name for name in alive}
        for future in as_completed(futures, timeout=65):
            name = futures[future]
            try:
                raw = future.result()
                if raw:
                    parsed = parse_agent_response(raw)
                    parsed["agent"] = name
                    responses.append(parsed)
            except Exception:
                pass

    weights = {name: AGENT_CONFIG[name]["weight"] for name in AGENT_CONFIG}
    return compute_consensus(responses, weights)
```

**Step 4: Run tests**

Run: `cd F:/BUREAU/turbo && python -m pytest tests/test_heal_pipeline.py -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add src/heal_pipeline.py tests/test_heal_pipeline.py
git commit -m "feat(heal): parallel multi-agent consensus pipeline with weighted voting"
```

---

## Task 4: heal_telegram.py — Interactive Bot with InlineKeyboard

**Files:**
- Create: `src/heal_telegram.py`
- Test: `tests/test_heal_telegram.py`
- Reference: `scripts/auto_heal_daemon.py:157-170` (existing send_telegram)

**Context:** Telegram bot with InlineKeyboard buttons under each alert. Runs a polling thread that calls getUpdates every 2s. Maintains a queue of pending fixes awaiting user approval. Timeout 5min per issue.

**Step 1: Write the failing tests**

```python
# tests/test_heal_telegram.py
"""Tests for heal_telegram — interactive Telegram bot with InlineKeyboard."""
from unittest.mock import patch, MagicMock
import json
import pytest


def test_build_keyboard():
    from src.heal_telegram import build_inline_keyboard
    kb = build_inline_keyboard("M1", "reload_model", 42)
    assert len(kb) == 1  # 1 row
    assert len(kb[0]) == 4  # 4 buttons
    labels = [b["text"] for b in kb[0]]
    assert "Approuver" in labels[0]
    assert "Rejeter" in labels[1]


def test_format_issue_message():
    from src.heal_telegram import format_issue_message
    from src.heal_detectors import Issue
    issue = Issue("node", "critical", "M1", "M1 OFFLINE", suggestion="Redemarrer")
    consensus = {"recommended_fix": "restart", "risk": "safe", "confidence": 85,
                 "cause": "port bloque", "agents": ["M1", "OL1"]}
    msg = format_issue_message(issue, consensus, 42)
    assert "M1" in msg
    assert "Cycle 42" in msg


def test_parse_callback():
    from src.heal_telegram import parse_callback_data
    action, component, fix_type, cycle = parse_callback_data("approve:M1:reload_model:42")
    assert action == "approve"
    assert component == "M1"
    assert fix_type == "reload_model"
    assert cycle == 42


def test_parse_callback_invalid():
    from src.heal_telegram import parse_callback_data
    result = parse_callback_data("bad_data")
    assert result is None


def test_pending_fix_queue():
    from src.heal_telegram import HealTelegramBot
    bot = HealTelegramBot(token="fake", chat_id="123")
    from src.heal_detectors import Issue
    issue = Issue("node", "critical", "M1", "offline")
    bot.add_pending("M1:reload_model:1", issue, {"fix": "reload"})
    assert bot.has_pending("M1:reload_model:1")
    bot.resolve_pending("M1:reload_model:1", "approved")
    assert not bot.has_pending("M1:reload_model:1")


def test_pending_timeout():
    from src.heal_telegram import HealTelegramBot
    import time
    bot = HealTelegramBot(token="fake", chat_id="123", timeout=0.1)
    from src.heal_detectors import Issue
    issue = Issue("node", "critical", "M1", "offline")
    bot.add_pending("M1:x:1", issue, {})
    time.sleep(0.2)
    expired = bot.get_expired()
    assert len(expired) == 1
```

**Step 2: Run to verify fail**

Run: `cd F:/BUREAU/turbo && python -m pytest tests/test_heal_telegram.py -v 2>&1 | head -20`

**Step 3: Implement heal_telegram.py**

```python
# src/heal_telegram.py
"""JARVIS Auto-Heal Telegram Bot — InlineKeyboard interactive approval flow.

Features:
  - Send alerts with InlineKeyboard buttons [Approuver][Rejeter][Retry][Details]
  - Poll getUpdates for callback_query responses
  - Maintain pending fix queue with 5min timeout
  - Thread-safe for use with daemon main loop
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

# Load .env for tokens
_env = ROOT / ".env"
if _env.exists():
    for _l in _env.read_text(encoding="utf-8", errors="ignore").splitlines():
        _l = _l.strip()
        if _l and not _l.startswith("#") and "=" in _l:
            _k, _, _v = _l.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())


@dataclass
class PendingFix:
    key: str
    issue: Any
    consensus: dict
    message_id: int = 0
    created_at: float = field(default_factory=time.time)
    status: str = "pending"  # pending, approved, rejected, expired, retried


def build_inline_keyboard(component: str, fix_type: str, cycle: int) -> list[list[dict]]:
    base = f"{component}:{fix_type}:{cycle}"
    return [[
        {"text": "Approuver", "callback_data": f"approve:{base}"},
        {"text": "Rejeter", "callback_data": f"reject:{base}"},
        {"text": "Retry", "callback_data": f"retry:{base}"},
        {"text": "Details", "callback_data": f"details:{base}"},
    ]]


def format_issue_message(issue, consensus: dict, cycle: int) -> str:
    icon = "\U0001f534" if issue.severity == "critical" else "\U0001f7e1"
    agents = ", ".join(consensus.get("agents", []))
    conf = consensus.get("confidence", 0)
    risk = consensus.get("risk", "unknown")
    cause = consensus.get("cause", "")
    fix = consensus.get("recommended_fix", "")

    lines = [
        f"*JARVIS Auto-Heal -- Cycle {cycle}*",
        f"",
        f"{icon} *{issue.component}*: {issue.message}",
    ]
    if cause:
        lines.append(f"Cause: {cause}")
    if fix:
        lines.append(f"Fix: `{fix}`")
    lines.append(f"Risque: {risk} | Confiance: {conf}%")
    if agents:
        lines.append(f"Consensus: {agents}")
    return "\n".join(lines)


def parse_callback_data(data: str) -> tuple[str, str, str, int] | None:
    parts = data.split(":")
    if len(parts) != 4:
        return None
    try:
        return parts[0], parts[1], parts[2], int(parts[3])
    except (ValueError, IndexError):
        return None


class HealTelegramBot:
    def __init__(self, token: str = "", chat_id: str = "", timeout: float = 300.0):
        self._token = token or os.environ.get("TELEGRAM_TOKEN", "")
        self._chat_id = chat_id or os.environ.get("TELEGRAM_CHAT", "")
        self._timeout = timeout
        self._pending: dict[str, PendingFix] = {}
        self._lock = threading.Lock()
        self._offset = 0
        self._polling = False
        self._poll_thread: threading.Thread | None = None
        self._callbacks: list[tuple[str, str, str, int]] = []  # parsed callbacks queue

    @property
    def active(self) -> bool:
        return bool(self._token and self._chat_id)

    # ── Pending queue ────────────────────────────────────────────────

    def add_pending(self, key: str, issue, consensus: dict) -> None:
        with self._lock:
            self._pending[key] = PendingFix(key=key, issue=issue, consensus=consensus)

    def has_pending(self, key: str) -> bool:
        with self._lock:
            p = self._pending.get(key)
            return p is not None and p.status == "pending"

    def resolve_pending(self, key: str, status: str) -> PendingFix | None:
        with self._lock:
            p = self._pending.get(key)
            if p:
                p.status = status
            return p

    def get_expired(self) -> list[PendingFix]:
        now = time.time()
        with self._lock:
            expired = [p for p in self._pending.values()
                       if p.status == "pending" and now - p.created_at > self._timeout]
            for p in expired:
                p.status = "expired"
            return expired

    def get_approved(self) -> list[PendingFix]:
        with self._lock:
            return [p for p in self._pending.values() if p.status == "approved"]

    def clear_resolved(self) -> None:
        with self._lock:
            self._pending = {k: v for k, v in self._pending.items() if v.status == "pending"}

    # ── Telegram API ─────────────────────────────────────────────────

    def _api(self, method: str, data: dict) -> dict | None:
        if not self.active:
            return None
        url = f"https://api.telegram.org/bot{self._token}/{method}"
        try:
            body = json.dumps(data).encode()
            req = urllib.request.Request(url, body, {"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode())
        except Exception:
            return None

    def send_message(self, text: str, reply_markup: dict | None = None) -> int:
        data: dict[str, Any] = {
            "chat_id": self._chat_id, "text": text, "parse_mode": "Markdown",
        }
        if reply_markup:
            data["reply_markup"] = reply_markup
        result = self._api("sendMessage", data)
        if result and result.get("ok"):
            return result["result"]["message_id"]
        return 0

    def send_issue(self, issue, consensus: dict, cycle: int) -> str:
        fix_type = consensus.get("recommended_fix", "unknown")
        key = f"{issue.component}:{fix_type}:{cycle}"
        msg = format_issue_message(issue, consensus, cycle)
        kb = build_inline_keyboard(issue.component, fix_type, cycle)
        msg_id = self.send_message(msg, {"inline_keyboard": kb})

        pf = PendingFix(key=key, issue=issue, consensus=consensus, message_id=msg_id)
        with self._lock:
            self._pending[key] = pf
        return key

    def send_fix_result(self, issue, success: bool, message: str, cycle: int) -> None:
        icon = "\u2705" if success else "\u274c"
        text = f"*JARVIS Auto-Heal -- Cycle {cycle}*\n{icon} *{issue.component}*: {message}"
        self.send_message(text)

    def send_status(self, text: str) -> None:
        self.send_message(text)

    def answer_callback(self, callback_id: str, text: str = "") -> None:
        self._api("answerCallbackQuery", {"callback_query_id": callback_id, "text": text})

    # ── Polling ──────────────────────────────────────────────────────

    def poll_once(self) -> list[tuple[str, str, str, int]]:
        result = self._api("getUpdates", {"offset": self._offset, "timeout": 2})
        if not result or not result.get("ok"):
            return []
        callbacks = []
        for update in result.get("result", []):
            self._offset = update["update_id"] + 1
            cq = update.get("callback_query")
            if not cq:
                continue
            data = cq.get("data", "")
            parsed = parse_callback_data(data)
            if parsed:
                action, comp, fix_type, cycle = parsed
                key = f"{comp}:{fix_type}:{cycle}"
                if action == "approve":
                    self.resolve_pending(key, "approved")
                    self.answer_callback(cq["id"], "Fix approuve!")
                elif action == "reject":
                    self.resolve_pending(key, "rejected")
                    self.answer_callback(cq["id"], "Fix rejete.")
                elif action == "retry":
                    self.resolve_pending(key, "retried")
                    self.answer_callback(cq["id"], "Retry programme.")
                elif action == "details":
                    p = self._pending.get(key)
                    detail = ""
                    if p and hasattr(p.issue, "context"):
                        detail = p.issue.context[:500] or p.issue.message
                    self.answer_callback(cq["id"], detail[:200] or "Pas de details")
                callbacks.append(parsed)
        return callbacks

    def start_polling(self) -> None:
        if self._polling or not self.active:
            return
        self._polling = True
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

    def stop_polling(self) -> None:
        self._polling = False

    def _poll_loop(self) -> None:
        while self._polling:
            try:
                self.poll_once()
            except Exception:
                pass
            time.sleep(2)
```

**Step 4: Run tests**

Run: `cd F:/BUREAU/turbo && python -m pytest tests/test_heal_telegram.py -v`
Expected: All 7 tests PASS

**Step 5: Commit**

```bash
git add src/heal_telegram.py tests/test_heal_telegram.py
git commit -m "feat(heal): interactive Telegram bot with InlineKeyboard approval flow"
```

---

## Task 5: Refactor auto_heal_daemon.py — Wire Modules

**Files:**
- Modify: `scripts/auto_heal_daemon.py` (full rewrite to use new modules)
- Test: manual run `python scripts/auto_heal_daemon.py --cycles 2 --interval 5`

**Context:** Replace inline detection/fix/telegram code with imports from the 4 new modules. The daemon becomes a thin orchestrator: detect -> pipeline analyze -> telegram notify+wait -> fix (on approval) -> verify -> report.

**Step 1: Rewrite auto_heal_daemon.py**

The daemon keeps: CLI args, main loop, adaptive interval, signal handling, DB persistence.
It delegates to: `heal_detectors.run_all_detectors()`, `heal_pipeline.analyze_issue()`, `heal_telegram.HealTelegramBot`, `heal_fixes.execute_fix()`.

Key changes:
- Remove inline `detect_*`, `ask_m1`, `ask_ol1`, `send_telegram`, `attempt_fix`, `restart_service` functions
- Import from `src.heal_detectors`, `src.heal_fixes`, `src.heal_pipeline`, `src.heal_telegram`
- Main cycle becomes:
  1. `issues = run_all_detectors()`
  2. For each issue: `consensus = analyze_issue(issue)`
  3. `bot.send_issue(issue, consensus, cycle)` — sends with InlineKeyboard
  4. Wait for approvals (poll loop up to 5min)
  5. For approved: `execute_fix(issue)` then `verify_fix(issue)`
  6. Report results via `bot.send_fix_result()`

```python
# Key section of refactored run_cycle():
def run_cycle(cycle: int, bot: HealTelegramBot, dry_run: bool = False) -> CycleReport:
    t0 = time.time()
    report = CycleReport(cycle=cycle, ts=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    # 1. Detect
    all_issues = run_all_detectors()
    report.issues_found = len(all_issues)
    if not all_issues:
        report.duration_ms = int((time.time() - t0) * 1000)
        if cycle % 100 == 0:
            log(f"Cycle {cycle}: cluster sain ({report.duration_ms}ms)", "OK")
        save_cycle(report)
        return report

    # 2. Analyze each issue via parallel pipeline
    for issue in all_issues:
        if issue.severity == "info":
            continue
        log(f"Cycle {cycle}: [{issue.severity}] {issue.component} -- {issue.message}", "WARN")
        consensus = analyze_issue(issue)
        issue.suggestion = consensus.get("cause", "")
        if consensus.get("recommended_fix"):
            issue.fix_cmd = consensus["recommended_fix"]
        issue.risk_level = consensus.get("risk", "unknown")

        # 3. Send to Telegram with buttons
        if bot.active and not dry_run:
            bot.send_issue(issue, consensus, cycle)
        else:
            log(f"  Consensus: {consensus.get('recommended_fix', 'N/A')} "
                f"(risk={consensus.get('risk')}, conf={consensus.get('confidence')}%)", "INFO")

    # 4. Wait for approvals (5min max)
    if bot.active and not dry_run:
        deadline = time.time() + 300
        while time.time() < deadline and _running:
            approved = bot.get_approved()
            expired = bot.get_expired()
            if approved or expired or not any(bot.has_pending(f"{i.component}:{i.fix_cmd}:{cycle}")
                                               for i in all_issues if i.fix_cmd):
                break
            time.sleep(5)

        # 5. Execute approved fixes
        for pf in bot.get_approved():
            ok, msg = execute_fix(pf.issue)
            if ok:
                verified = verify_fix(pf.issue)
                if verified:
                    pf.issue.resolved = True
                    report.issues_fixed += 1
                    clear_resolved(pf.issue.component)
                    log(f"  REPARE+VERIFIE: {pf.issue.component}", "OK")
                    bot.send_fix_result(pf.issue, True, msg, cycle)
                else:
                    report.issues_failed += 1
                    track_persistent(pf.issue)
                    log(f"  Fix OK mais verification KO: {pf.issue.component}", "FAIL")
                    bot.send_fix_result(pf.issue, False, "Fix applique mais verification echouee", cycle)
            else:
                report.issues_failed += 1
                track_persistent(pf.issue)
                log(f"  ECHEC fix: {pf.issue.component}: {msg}", "FAIL")
                bot.send_fix_result(pf.issue, False, msg, cycle)

        bot.clear_resolved()

    report.duration_ms = int((time.time() - t0) * 1000)
    save_cycle(report)
    return report
```

**Step 2: Run smoke test**

Run: `cd F:/BUREAU/turbo && python scripts/auto_heal_daemon.py --cycles 2 --interval 5 --no-telegram`
Expected: 2 cycles complete, detects current issues, no crashes

**Step 3: Commit**

```bash
git add scripts/auto_heal_daemon.py
git commit -m "refactor(heal): wire daemon to modular heal_detectors/fixes/pipeline/telegram"
```

---

## Task 6: Integration Tests

**Files:**
- Create: `tests/test_heal_integration.py`

**Step 1: Write integration tests**

```python
# tests/test_heal_integration.py
"""Integration tests for the complete auto-heal v2 pipeline."""
from unittest.mock import patch, MagicMock
import pytest


def test_full_cycle_no_issues():
    from src.heal_detectors import run_all_detectors
    with patch("src.heal_detectors.check_port", return_value=True):
        with patch("src.heal_detectors._check_m1_model", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout="0, GPU, 45\n", returncode=0)
                issues = run_all_detectors()
    # May have some issues depending on log files, but core checks pass
    node_issues = [i for i in issues if i.category == "node"]
    svc_issues = [i for i in issues if i.category == "service"]
    assert len(node_issues) == 0
    assert len(svc_issues) == 0


def test_pipeline_to_telegram_flow():
    from src.heal_detectors import Issue
    from src.heal_pipeline import compute_consensus
    from src.heal_telegram import format_issue_message, build_inline_keyboard

    issue = Issue("service", "critical", "jarvis_ws", "jarvis_ws OFFLINE")
    responses = [
        {"agent": "M1", "cause": "port bloque", "fix": "restart", "risk": "safe", "confidence": 90},
        {"agent": "OL1", "cause": "crash", "fix": "restart", "risk": "safe", "confidence": 80},
    ]
    weights = {"M1": 1.9, "OL1": 1.4}
    consensus = compute_consensus(responses, weights)

    msg = format_issue_message(issue, consensus, 1)
    kb = build_inline_keyboard("jarvis_ws", "restart", 1)

    assert "jarvis_ws" in msg
    assert consensus["recommended_fix"] == "restart"
    assert len(kb[0]) == 4


def test_fix_catalogue_covers_all_detectors():
    from src.heal_fixes import FIX_REGISTRY, get_risk_level
    # All fix_fn values used by detectors should exist in registry
    expected = ["restart_service", "reload_model", "kill_doublon", "clear_db_lock"]
    for name in expected:
        assert get_risk_level(name) != "unknown", f"Fix {name} not in registry"
```

**Step 2: Run all tests**

Run: `cd F:/BUREAU/turbo && python -m pytest tests/test_heal_detectors.py tests/test_heal_fixes.py tests/test_heal_pipeline.py tests/test_heal_telegram.py tests/test_heal_integration.py -v`
Expected: All tests PASS

**Step 3: Commit**

```bash
git add tests/test_heal_integration.py
git commit -m "test(heal): add integration tests for auto-heal v2 pipeline"
```

---

## Summary

| Task | Module | Files | Tests |
|------|--------|-------|-------|
| 1 | heal_detectors.py | src/ + tests/ | 11 |
| 2 | heal_fixes.py | src/ + tests/ | 6 |
| 3 | heal_pipeline.py | src/ + tests/ | 5 |
| 4 | heal_telegram.py | src/ + tests/ | 7 |
| 5 | Refactor daemon | scripts/ | smoke |
| 6 | Integration | tests/ | 3 |

**Total: 6 tasks, 4 new modules, ~32 tests, 6 commits**
