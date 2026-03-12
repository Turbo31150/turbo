#!/usr/bin/env python3
"""JARVIS Unified Boot — UN SEUL script pour TOUT demarrer.

Remplace les 19+ .bat/.ps1/.py disperses par un demarrage orchestre
en 6 phases avec detection fiable et retry.

Phases:
  1. Infrastructure  — LM Studio server, Ollama, GPU check
  2. Modeles         — Load/verify models on M1, check M2/M3
  3. Services Node   — n8n, Gemini proxy, Canvas proxy
  4. Services Python — Dashboard, Telegram bot, MCP SSE
  5. (Retired)       — Daemons now handled by Automation Hub (port 9742)
  6. Validation      — Health check complet, DB integrity, rapport final

Usage:
    python scripts/jarvis_unified_boot.py              # Boot complet
    python scripts/jarvis_unified_boot.py --status      # Status sans demarrer
    python scripts/jarvis_unified_boot.py --phase 1-3   # Phases specifiques
    python scripts/jarvis_unified_boot.py --skip n8n    # Skip un service
    python scripts/jarvis_unified_boot.py --dry-run     # Affiche ce qui serait fait
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# Ensure src/ importable
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from src.process_singleton import singleton as _singleton

# ============================================================================
# CONFIG
# ============================================================================
TURBO_DIR = Path("/home/turbo/jarvis-m1-ops")
HOME = Path(os.path.expanduser("~"))
OPENCLAW_DIR = HOME / ".openclaw"
LOG_DIR = TURBO_DIR / "logs"
LOG_FILE = LOG_DIR / "unified_boot.log"

# Couleurs ANSI (Windows Terminal supporte)
C_RESET = "\033[0m"
C_GREEN = "\033[92m"
C_RED = "\033[91m"
C_YELLOW = "\033[93m"
C_CYAN = "\033[96m"
C_MAGENTA = "\033[95m"
C_BOLD = "\033[1m"
C_DIM = "\033[2m"

# Load .env for credentials
_env_path = TURBO_DIR / ".env"
if _env_path.exists():
    for _line in _env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

# Cluster nodes (credentials from .env)
NODES = {
    "M1": {"url": os.environ.get("LM_STUDIO_1_URL", "http://127.0.0.1:1234"), "ip": "127.0.0.1", "port": 1234,
            "auth": os.environ.get("LM_STUDIO_1_API_KEY", "")},
    "M2": {"url": os.environ.get("LM_STUDIO_2_URL", "http://192.168.1.26:1234"), "ip": "192.168.1.26", "port": 1234,
            "auth": os.environ.get("LM_STUDIO_2_API_KEY", "")},
    "M3": {"url": os.environ.get("LM_STUDIO_3_URL", "http://192.168.1.113:1234"), "ip": "192.168.1.113", "port": 1234,
            "auth": os.environ.get("LM_STUDIO_3_API_KEY", "")},
}
OLLAMA = {"url": "http://127.0.0.1:11434", "ip": "127.0.0.1", "port": 11434}

# Services avec ports
SERVICES = {
    "n8n":           {"port": 5678, "name": "n8n Workflow Automation"},
    "dashboard":     {"port": 8080, "name": "JARVIS Dashboard"},
    "gemini_proxy":  {"port": 18791, "name": "Gemini Proxy"},
    "gemini_openai": {"port": 18793, "name": "Gemini OpenAI Proxy"},
    "canvas_proxy":  {"port": 18800, "name": "Canvas Direct Proxy"},
    "openclaw":      {"port": 18789, "name": "OpenClaw Gateway"},
    "jarvis_ws":     {"port": 9742, "name": "JARVIS WebSocket"},
    "mcp_sse":       {"port": 8901, "name": "MCP SSE Server"},
}

# Models to load on M1
# LM Studio API returns short key "qwen3-8b", lms CLI uses "qwen/qwen3-8b"
M1_REQUIRED_MODEL = "qwen/qwen3-8b"
M1_REQUIRED_MODEL_SHORT = "qwen3-8b"
M1_MODEL_OPTS = {"gpu": "max", "context": 28813, "parallel": 4}

# n8n binary (Windows .cmd wrapper)
N8N_CMD = r"/nvm4w\nodejs\n8n.cmd"

LMS_CLI = str(HOME / ".lmstudio" / "bin" / "lms.exe")

# OpenClaw gateway binary
OPENCLAW_CMD = str(HOME / "AppData" / "Roaming" / "npm" / "node_modules" / "openclaw" / "dist" / "index.js")

# Gemini proxy DAEMON (OpenClaw version, HTTP server on :18791)
GEMINI_PROXY_DAEMON = str(OPENCLAW_DIR / "gemini-proxy.js")

# Gemini OpenAI-compatible proxy (wraps gemini CLI, HTTP server on :18793)
GEMINI_OPENAI_PROXY = str(TURBO_DIR / "gemini-openai-proxy.js")

# SQLite databases to verify
DATABASES = {
    "etoile": TURBO_DIR / "data" / "etoile.db",
    "jarvis": TURBO_DIR / "data" / "jarvis.db",
    "scheduler": TURBO_DIR / "data" / "scheduler.db",
    "sniper": TURBO_DIR / "data" / "sniper.db",
    "task_queue": TURBO_DIR / "data" / "task_queue.db",
    "auto_heal": TURBO_DIR / "data" / "auto_heal.db",
}

# Processes launched (for cleanup)
_launched_procs: list[subprocess.Popen] = []

# Singleton lock for unified boot
BOOT_LOCK_FILE = TURBO_DIR / "data" / ".unified-boot.lock"


_boot_lock_fh = None  # Keep file handle open for Windows file lock

def check_boot_singleton():
    """Ensure only one unified_boot runs. Kills the old one if a new one starts.
    The lock is held for the process lifetime and auto-released on crash/kill.
    """
    global _boot_lock_fh
    import msvcrt
    BOOT_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        _boot_lock_fh = open(BOOT_LOCK_FILE, "w")
        msvcrt.locking(_boot_lock_fh.fileno(), msvcrt.LK_NBLCK, 1)
        _boot_lock_fh.write(str(os.getpid()))
        _boot_lock_fh.flush()
    except (OSError, IOError):
        # Lock held by another instance — KILL it and take over
        old_pid = None
        try:
            old_pid = int(BOOT_LOCK_FILE.read_text().strip())
        except (ValueError, OSError):
            pass
        if old_pid:
            print(f"{C_YELLOW}[!!] unified_boot existant (PID {old_pid}) — arret...{C_RESET}")
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(old_pid), "/F", "/T"],
                    capture_output=True, timeout=10,
                )
            except Exception:
                pass
        else:
            # Stale lock without valid PID — just remove it
            print(f"{C_YELLOW}[!!] Lock orphelin detecte — nettoyage...{C_RESET}")
        # Close stale handle if any, wait for port/lock release
        if _boot_lock_fh:
            try:
                _boot_lock_fh.close()
            except Exception:
                pass
        time.sleep(2)
        # Retry lock acquisition
        try:
            _boot_lock_fh = open(BOOT_LOCK_FILE, "w")
            msvcrt.locking(_boot_lock_fh.fileno(), msvcrt.LK_NBLCK, 1)
            _boot_lock_fh.write(str(os.getpid()))
            _boot_lock_fh.flush()
            print(f"{C_GREEN}[OK] Lock acquis (ancien PID {old_pid} tue){C_RESET}")
        except (OSError, IOError):
            # Last resort: force delete and retry
            try:
                _boot_lock_fh.close()
            except Exception:
                pass
            try:
                BOOT_LOCK_FILE.unlink(missing_ok=True)
            except OSError:
                pass
            time.sleep(1)
            try:
                _boot_lock_fh = open(BOOT_LOCK_FILE, "w")
                msvcrt.locking(_boot_lock_fh.fileno(), msvcrt.LK_NBLCK, 1)
                _boot_lock_fh.write(str(os.getpid()))
                _boot_lock_fh.flush()
            except (OSError, IOError):
                print(f"{C_RED}[XX] Lock impossible apres kill — abandon{C_RESET}")
                sys.exit(1)


# ============================================================================
# HELPERS
# ============================================================================
def log(msg: str, level: str = "INFO", indent: int = 0):
    """Print with color and log to file."""
    ts = datetime.now().strftime("%H:%M:%S")
    prefix = "  " * indent

    colors = {
        "OK": C_GREEN, "INFO": C_CYAN, "WARN": C_YELLOW,
        "FAIL": C_RED, "PHASE": C_MAGENTA, "DIM": C_DIM,
    }
    icons = {
        "OK": "[OK]", "INFO": "[..]", "WARN": "[!!]",
        "FAIL": "[XX]", "PHASE": "[>>]", "DIM": "[--]",
    }

    color = colors.get(level, C_RESET)
    icon = icons.get(level, "[..]")
    line = f"{prefix}{icon} {msg}"
    print(f"{color}{line}{C_RESET}")

    # Log to file
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [{level}] {msg}\n")
    except OSError:
        pass


def banner(title: str, char: str = "=", width: int = 60):
    """Print a banner."""
    line = char * width
    print(f"\n{C_BOLD}{C_CYAN}{line}")
    print(f"  {title}")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{line}{C_RESET}\n")


def check_port(host: str, port: int, timeout: float = 3.0) -> bool:
    """TCP port check — fiable et rapide."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except (socket.error, OSError):
        return False


def wait_for_port(host: str, port: int, max_wait: int = 30, interval: int = 2) -> bool:
    """Wait for a port to become available."""
    waited = 0
    while waited < max_wait:
        if check_port(host, port, timeout=2):
            return True
        time.sleep(interval)
        waited += interval
    return False


def http_get(url: str, timeout: float = 5.0, headers: dict | None = None) -> dict | None:
    """Simple HTTP GET returning JSON or None."""
    import urllib.request
    try:
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def start_process(cmd: list[str] | str, name: str, cwd: str | None = None,
                  shell: bool = False, hidden: bool = True,
                  singleton_port: int | None = None) -> subprocess.Popen | None:
    """Start a background process as singleton — kills existing instance first.

    Args:
        singleton_port: If given, also kill whatever occupies this TCP port.
            The service name for the singleton is derived from ``name``
            (lowercased, spaces replaced by underscores).
    """
    svc_name = name.lower().replace(" ", "_").replace("-", "_")
    try:
        # ── Singleton: kill existing instance before starting ──
        _singleton.acquire(svc_name, pid=0, port=singleton_port)
        # pid=0 is a placeholder — we'll overwrite with real PID below

        kwargs: dict[str, Any] = {
            "cwd": cwd,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = (
                subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
                | subprocess.CREATE_NO_WINDOW
            )
        if shell:
            kwargs["shell"] = True

        proc = subprocess.Popen(cmd, **kwargs)
        _launched_procs.append(proc)

        # ── Register real PID in singleton ──
        _singleton.register(svc_name, proc.pid)

        log(f"  Started {name} (PID {proc.pid}) [singleton]", "DIM", indent=1)
        return proc
    except Exception as e:
        log(f"  Failed to start {name}: {e}", "FAIL", indent=1)
        return None


def get_gpu_info() -> list[dict]:
    """Get GPU stats via nvidia-smi."""
    try:
        r = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=index,name,memory.used,memory.total,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, timeout=10, encoding="utf-8", errors="replace",
        )
        gpus = []
        for line in r.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 5:
                idx = int(parts[0]) if parts[0].isdigit() else 0
                used = int(parts[2]) if parts[2].isdigit() else 0
                total = int(parts[3]) if parts[3].isdigit() else 0
                temp = int(parts[4]) if parts[4].isdigit() else -1
                gpus.append({
                    "index": idx, "name": parts[1],
                    "vram_used": used, "vram_total": total, "temp": temp,
                })
        return gpus
    except (subprocess.SubprocessError, OSError):
        return []


def check_db_integrity(path: Path) -> dict:
    """Check SQLite DB integrity and return stats."""
    if not path.exists():
        return {"ok": False, "error": "file not found"}
    try:
        db = sqlite3.connect(str(path))
        # Integrity check
        result = db.execute("PRAGMA integrity_check").fetchone()
        ok = result and result[0] == "ok"
        # Count tables and rows
        tables = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        total_rows = 0
        for (tname,) in tables:
            try:
                count = db.execute(f"SELECT COUNT(*) FROM [{tname}]").fetchone()[0]
                total_rows += count
            except sqlite3.Error:
                pass
        db.close()
        return {
            "ok": ok, "tables": len(tables), "rows": total_rows,
            "size_mb": round(path.stat().st_size / 1024 / 1024, 1),
        }
    except sqlite3.Error as e:
        return {"ok": False, "error": str(e)}


# ============================================================================
# PHASE 1: INFRASTRUCTURE
# ============================================================================
def phase_1_infrastructure(dry_run: bool = False) -> dict:
    """Check/start LM Studio, Ollama, GPU status."""
    log("PHASE 1 — INFRASTRUCTURE (LM Studio + Ollama + GPU)", "PHASE")
    report: dict[str, Any] = {}

    # -- GPU Status --
    gpus = get_gpu_info()
    report["gpus"] = gpus
    if gpus:
        for g in gpus:
            temp_str = f" {g['temp']}C" if g['temp'] >= 0 else ""
            bar_pct = int(g['vram_used'] / max(g['vram_total'], 1) * 100)
            bar = "#" * (bar_pct // 5) + "." * (20 - bar_pct // 5)
            log(f"GPU{g['index']} {g['name'][:22]:22s} [{bar}] "
                f"{g['vram_used']}MB/{g['vram_total']}MB{temp_str}", "INFO", indent=1)
        max_temp = max(g['temp'] for g in gpus if g['temp'] >= 0)
        if max_temp >= 85:
            log(f"THERMAL CRITIQUE: {max_temp}C!", "FAIL", indent=1)
        elif max_temp >= 75:
            log(f"Thermal warning: {max_temp}C", "WARN", indent=1)
        else:
            log(f"Thermal: {max_temp}C (normal)", "OK", indent=1)
    else:
        log("nvidia-smi non disponible", "WARN", indent=1)

    # -- LM Studio (M1) — kill existant + restart --
    if dry_run:
        log("M1 LM Studio: (dry-run, skip)", "WARN", indent=1)
        report["m1"] = "dry_run"
    else:
        was_running = check_port(NODES["M1"]["ip"], NODES["M1"]["port"])
        if was_running:
            log("M1 LM Studio: existant detecte, arret...", "INFO", indent=1)
            try:
                subprocess.run(
                    [LMS_CLI, "server", "stop"],
                    capture_output=True, timeout=15, encoding="utf-8",
                )
                time.sleep(2)
            except (subprocess.SubprocessError, OSError):
                _singleton.kill_on_port(1234)
                time.sleep(1)
        log("M1 LM Studio: demarrage serveur...", "INFO", indent=1)
        try:
            subprocess.run(
                [LMS_CLI, "server", "start"],
                capture_output=True, timeout=30, encoding="utf-8",
            )
            if wait_for_port("127.0.0.1", 1234, max_wait=20):
                log(f"M1 LM Studio: demarre (restart={'oui' if was_running else 'non'})", "OK", indent=1)
                report["m1"] = "restarted" if was_running else "started"
            else:
                log("M1 LM Studio: pas de reponse apres 20s", "FAIL", indent=1)
                report["m1"] = "start_failed"
        except (subprocess.SubprocessError, OSError) as e:
            log(f"M1 LM Studio: erreur CLI ({e})", "FAIL", indent=1)
            report["m1"] = "error"

    # -- Ollama — kill existant + restart --
    if dry_run:
        log("Ollama: (dry-run, skip)", "WARN", indent=1)
        report["ollama"] = {"status": "dry_run"}
    else:
        was_running = check_port(OLLAMA["ip"], OLLAMA["port"])
        if was_running:
            log("Ollama: existant detecte, arret via singleton...", "INFO", indent=1)
        log("Ollama: demarrage...", "INFO", indent=1)
        start_process(["ollama", "serve"], "Ollama", singleton_port=11434)
        if wait_for_port("127.0.0.1", 11434, max_wait=15):
            log(f"Ollama: demarre (restart={'oui' if was_running else 'non'})", "OK", indent=1)
            data = http_get(f"{OLLAMA['url']}/api/tags")
            count = len(data.get("models", [])) if data else 0
            report["ollama"] = {"status": "restarted" if was_running else "started", "models": count}
        else:
            log("Ollama: echec demarrage", "FAIL", indent=1)
            report["ollama"] = {"status": "failed"}

    # -- M2 / M3 (check only — remote, can't start) --
    for node_name in ("M2", "M3"):
        n = NODES[node_name]
        online = check_port(n["ip"], n["port"], timeout=3)
        if online:
            headers = {"Authorization": f"Bearer {n['auth']}"}
            data = http_get(f"{n['url']}/api/v1/models", headers=headers)
            loaded = 0
            if data:
                models = data.get("data", data.get("models", []))
                loaded = sum(1 for m in models if m.get("loaded_instances"))
            log(f"{node_name}: ONLINE ({loaded} modeles charges)", "OK", indent=1)
            report[node_name.lower()] = {"status": "online", "loaded": loaded}
        else:
            log(f"{node_name}: OFFLINE ({n['ip']})", "DIM", indent=1)
            report[node_name.lower()] = {"status": "offline"}

    return report


# ============================================================================
# PHASE 2: MODELS
# ============================================================================
def phase_2_models(dry_run: bool = False) -> dict:
    """Load/verify models on M1."""
    log("PHASE 2 — MODELES (load + warmup)", "PHASE")
    report: dict[str, Any] = {}

    if not check_port("127.0.0.1", 1234):
        log("M1 OFFLINE — skip model loading", "WARN", indent=1)
        return {"status": "m1_offline"}

    # Check what's loaded
    try:
        r = subprocess.run(
            [LMS_CLI, "ps"], capture_output=True, timeout=10,
            encoding="utf-8", errors="replace",
        )
        output = r.stdout + r.stderr
        # Strip ANSI
        import re
        output = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]|\[/?25[hl]", "", output)
        report["lms_ps"] = output.strip()
        log(f"Models charges: {output.strip()[:200]}", "DIM", indent=1)
    except (subprocess.SubprocessError, OSError):
        report["lms_ps"] = "error"

    # Check if required model is loaded via API
    headers = {"Authorization": f"Bearer {NODES['M1']['auth']}"}
    data = http_get(f"{NODES['M1']['url']}/api/v1/models", headers=headers)
    if data:
        models = data.get("data", data.get("models", []))
        loaded_ids = [m.get("id", m.get("key", "")) for m in models if m.get("loaded_instances")]
        loaded_keys = [m.get("key", "") for m in models if m.get("loaded_instances")]
        has_required = any(
            M1_REQUIRED_MODEL in str(m) or M1_REQUIRED_MODEL_SHORT in str(m)
            for m in loaded_ids + loaded_keys
        )

        if has_required:
            log(f"{M1_REQUIRED_MODEL}: deja charge", "OK", indent=1)
            report["model_load"] = "already_loaded"
        elif dry_run:
            log(f"{M1_REQUIRED_MODEL}: pas charge (dry-run)", "WARN", indent=1)
            report["model_load"] = "dry_run"
        else:
            log(f"Chargement {M1_REQUIRED_MODEL}...", "INFO", indent=1)
            opts = M1_MODEL_OPTS
            try:
                subprocess.run(
                    [LMS_CLI, "load", M1_REQUIRED_MODEL,
                     "--gpu", opts["gpu"], "-c", str(opts["context"]),
                     "--parallel", str(opts["parallel"]), "-y"],
                    capture_output=True, timeout=180, encoding="utf-8",
                )
                time.sleep(3)
                # Verify
                data2 = http_get(f"{NODES['M1']['url']}/api/v1/models", headers=headers)
                if data2:
                    loaded2 = [m.get("key", m.get("id", "")) for m in data2.get("data", data2.get("models", []))
                               if m.get("loaded_instances")]
                    if any(M1_REQUIRED_MODEL_SHORT in str(m) for m in loaded2):
                        log(f"{M1_REQUIRED_MODEL}: charge avec succes", "OK", indent=1)
                        report["model_load"] = "loaded"
                    else:
                        log(f"{M1_REQUIRED_MODEL}: echec verification", "FAIL", indent=1)
                        report["model_load"] = "verify_failed"
            except subprocess.TimeoutExpired:
                log(f"Timeout chargement {M1_REQUIRED_MODEL}", "FAIL", indent=1)
                report["model_load"] = "timeout"

        # Warmup
        if not dry_run and report.get("model_load") in ("already_loaded", "loaded"):
            log("Warmup M1...", "INFO", indent=1)
            try:
                import urllib.request
                warmup_body = json.dumps({
                    "model": M1_REQUIRED_MODEL_SHORT,
                    "input": "/nothink\nReponds OK.",
                    "temperature": 0.1,
                    "max_output_tokens": 5,
                    "stream": False, "store": False,
                }).encode()
                req = urllib.request.Request(
                    f"{NODES['M1']['url']}/api/v1/chat",
                    data=warmup_body,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {NODES['M1']['auth']}",
                    },
                )
                t0 = time.time()
                with urllib.request.urlopen(req, timeout=15) as resp:
                    resp.read()
                latency = int((time.time() - t0) * 1000)
                log(f"Warmup OK — {latency}ms", "OK", indent=1)
                report["warmup_ms"] = latency
            except Exception as e:
                log(f"Warmup echec: {e}", "WARN", indent=1)
                report["warmup_ms"] = -1

    return report


# ============================================================================
# PHASE 3: NODE SERVICES
# ============================================================================
def phase_3_node_services(dry_run: bool = False, skip: list[str] | None = None) -> dict:
    """Start n8n, Gemini proxy, Canvas proxy. Kills existing before restart (anti-doublon)."""
    log("PHASE 3 — SERVICES NODE (n8n + proxies)", "PHASE")
    skip = skip or []
    report: dict[str, Any] = {}

    # -- n8n — kill existant + restart --
    if "n8n" not in skip:
        if dry_run:
            log("n8n: (dry-run, skip)", "WARN", indent=1)
            report["n8n"] = "dry_run"
        else:
            was_running = check_port("127.0.0.1", 5678)
            if was_running:
                log("n8n: existant detecte, arret via singleton...", "INFO", indent=1)
            _singleton.acquire("n8n", pid=0, port=5678)
            log("n8n: demarrage...", "INFO", indent=1)
            env = os.environ.copy()
            env["N8N_SECURE_COOKIE"] = "false"
            env["EXECUTIONS_MODE"] = "regular"
            env["NODE_OPTIONS"] = "--max-old-space-size=4096"
            env["EXECUTIONS_DATA_PRUNE"] = "true"
            env["EXECUTIONS_DATA_MAX_AGE"] = "72"
            try:
                n8n_bin = N8N_CMD if os.path.exists(N8N_CMD) else "n8n"
                proc = subprocess.Popen(
                    [n8n_bin, "start"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    env=env, shell=True,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
                )
                _launched_procs.append(proc)
                _singleton.register("n8n", proc.pid)
                if wait_for_port("127.0.0.1", 5678, max_wait=30):
                    log(f"n8n: demarre PID {proc.pid} (restart={'oui' if was_running else 'non'})", "OK", indent=1)
                    report["n8n"] = "restarted" if was_running else "started"
                else:
                    log("n8n: pas pret apres 30s", "FAIL", indent=1)
                    report["n8n"] = "timeout"
            except (OSError, FileNotFoundError):
                log("n8n: commande introuvable ({})".format(N8N_CMD), "FAIL", indent=1)
                report["n8n"] = "not_found"

    # -- Gemini Proxy DAEMON — kill existant + restart --
    gemini_daemon = Path(GEMINI_PROXY_DAEMON)
    if "gemini" not in skip and gemini_daemon.exists():
        if dry_run:
            log("Gemini proxy daemon: (dry-run, skip)", "WARN", indent=1)
            report["gemini_proxy"] = "dry_run"
        else:
            was_running = check_port("127.0.0.1", 18791)
            if was_running:
                log("Gemini proxy: existant detecte, arret via singleton...", "INFO", indent=1)
            log("Gemini proxy daemon: demarrage...", "INFO", indent=1)
            start_process(
                ["node", str(gemini_daemon)],
                "Gemini Proxy", cwd=str(gemini_daemon.parent),
                singleton_port=18791,
            )
            if wait_for_port("127.0.0.1", 18791, max_wait=10):
                log(f"Gemini proxy: demarre :18791 (restart={'oui' if was_running else 'non'})", "OK", indent=1)
                report["gemini_proxy"] = "restarted" if was_running else "started"
            else:
                log("Gemini proxy: port 18791 pas ouvert apres 10s", "WARN", indent=1)
                report["gemini_proxy"] = "failed"

    # -- Gemini OpenAI Proxy — wraps gemini CLI as OpenAI-compatible HTTP --
    gemini_openai = Path(GEMINI_OPENAI_PROXY)
    if "gemini" not in skip and gemini_openai.exists():
        if dry_run:
            log("Gemini OpenAI proxy: (dry-run, skip)", "WARN", indent=1)
            report["gemini_openai"] = "dry_run"
        else:
            was_running = check_port("127.0.0.1", 18793)
            if was_running:
                log("Gemini OpenAI proxy: existant detecte, arret via singleton...", "INFO", indent=1)
            log("Gemini OpenAI proxy: demarrage...", "INFO", indent=1)
            start_process(
                ["node", str(gemini_openai)],
                "Gemini OpenAI Proxy", cwd=str(TURBO_DIR),
                singleton_port=18793,
            )
            if wait_for_port("127.0.0.1", 18793, max_wait=10):
                log(f"Gemini OpenAI proxy: demarre :18793 (restart={'oui' if was_running else 'non'})", "OK", indent=1)
                report["gemini_openai"] = "restarted" if was_running else "started"
            else:
                log("Gemini OpenAI proxy: port 18793 pas ouvert apres 10s", "WARN", indent=1)
                report["gemini_openai"] = "failed"

    # -- Canvas Direct Proxy — singleton anti-doublon --
    canvas_proxy_path = TURBO_DIR / "canvas" / "direct-proxy.js"
    if "canvas" not in skip and canvas_proxy_path.exists():
        if dry_run:
            log("Canvas proxy: (dry-run, skip)", "WARN", indent=1)
            report["canvas_proxy"] = "dry_run"
        else:
            was_running = check_port("127.0.0.1", 18800)
            if was_running:
                log("Canvas proxy: existant detecte, arret via singleton...", "INFO", indent=1)
            log("Canvas proxy: demarrage...", "INFO", indent=1)
            start_process(
                ["node", str(canvas_proxy_path)],
                "Canvas Proxy", cwd=str(TURBO_DIR),
                singleton_port=18800,
            )
            if wait_for_port("127.0.0.1", 18800, max_wait=10):
                log(f"Canvas proxy: demarre :18800 (restart={'oui' if was_running else 'non'})", "OK", indent=1)
                report["canvas_proxy"] = "restarted" if was_running else "started"
            else:
                log("Canvas proxy: echec", "FAIL", indent=1)
                report["canvas_proxy"] = "failed"

    # -- OpenClaw Gateway — SKIP si telegram-bot.js actif (conflit 409) --
    openclaw_bin = Path(OPENCLAW_CMD)
    try:
        _tg_check = subprocess.run(["tasklist", "/FI", "IMAGENAME eq node.exe", "/FO", "CSV"], capture_output=True, text=True, timeout=5)
        tg_bot_running = "telegram-bot" in subprocess.run(["wmic", "process", "where", "name='node.exe'", "get", "commandline"], capture_output=True, text=True, timeout=5).stdout
    except Exception:
        tg_bot_running = False
    if tg_bot_running:
        log("OpenClaw: SKIP — telegram-bot.js actif (evite conflit 409 Telegram)", "WARN", indent=1)
        report["openclaw"] = "skipped_tg_conflict"
    elif "openclaw" not in skip and openclaw_bin.exists():
        if dry_run:
            log("OpenClaw Gateway: (dry-run, skip)", "WARN", indent=1)
            report["openclaw"] = "dry_run"
        else:
            was_running = check_port("127.0.0.1", 18789)
            if was_running:
                log("OpenClaw: existant detecte, arret via singleton...", "INFO", indent=1)
            log("OpenClaw Gateway: demarrage...", "INFO", indent=1)
            start_process(
                ["node", str(openclaw_bin), "gateway", "--port", "18789"],
                "OpenClaw Gateway",
                singleton_port=18789,
            )
            if wait_for_port("127.0.0.1", 18789, max_wait=10):
                log(f"OpenClaw: demarre :18789 (restart={'oui' if was_running else 'non'})", "OK", indent=1)
                report["openclaw"] = "restarted" if was_running else "started"
            else:
                log("OpenClaw: port 18789 pas ouvert apres 10s", "FAIL", indent=1)
                report["openclaw"] = "failed"

    return report


# ============================================================================
# PHASE 4: PYTHON SERVICES
# ============================================================================
def phase_4_python_services(dry_run: bool = False, skip: list[str] | None = None) -> dict:
    """Start Dashboard, WS backend, Telegram bot. Kills existing before restart (anti-doublon)."""
    log("PHASE 4 — SERVICES PYTHON (Dashboard + WS + Telegram)", "PHASE")
    skip = skip or []
    report: dict[str, Any] = {}
    uv = str(HOME / ".local" / "bin" / "uv.exe")

    # -- Dashboard — singleton anti-doublon --
    dashboard_script = TURBO_DIR / "dashboard" / "server.py"
    if "dashboard" not in skip and dashboard_script.exists():
        if dry_run:
            log("Dashboard: (dry-run, skip)", "WARN", indent=1)
            report["dashboard"] = "dry_run"
        else:
            was_running = check_port("127.0.0.1", 8080)
            if was_running:
                log("Dashboard: existant detecte, arret via singleton...", "INFO", indent=1)
            log("Dashboard: demarrage...", "INFO", indent=1)
            start_process(
                [uv, "run", "python", str(dashboard_script)],
                "Dashboard", cwd=str(TURBO_DIR),
                singleton_port=8080,
            )
            if wait_for_port("127.0.0.1", 8080, max_wait=10):
                log(f"Dashboard: demarre :8080 (restart={'oui' if was_running else 'non'})", "OK", indent=1)
                report["dashboard"] = "restarted" if was_running else "started"
            else:
                log("Dashboard: echec", "FAIL", indent=1)
                report["dashboard"] = "failed"

    # -- Python WebSocket Server — singleton anti-doublon --
    ws_script = TURBO_DIR / "python_ws" / "server.py"
    if "ws" not in skip and ws_script.exists():
        if dry_run:
            log("Python WS: (dry-run, skip)", "WARN", indent=1)
            report["jarvis_ws"] = "dry_run"
        else:
            was_running = check_port("127.0.0.1", 9742)
            if was_running:
                log("Python WS: existant detecte, arret via singleton...", "INFO", indent=1)
            log("Python WS: demarrage...", "INFO", indent=1)
            start_process(
                [uv, "run", "python", str(ws_script)],
                "JARVIS WS", cwd=str(TURBO_DIR),
                singleton_port=9742,
            )
            if wait_for_port("127.0.0.1", 9742, max_wait=25):
                log(f"Python WS: demarre :9742 (restart={'oui' if was_running else 'non'})", "OK", indent=1)
                report["jarvis_ws"] = "restarted" if was_running else "started"
            else:
                log("Python WS: echec", "FAIL", indent=1)
                report["jarvis_ws"] = "failed"

    # -- Telegram Bot --
    # Skip legacy bot if OpenClaw Telegram channel is active (same token = conflict)
    telegram_bot = TURBO_DIR / "canvas" / "telegram-bot.js"
    if "telegram" not in skip and telegram_bot.exists():
        openclaw_tg = check_port("127.0.0.1", 18789)
        if openclaw_tg:
            log("Telegram bot: skip (OpenClaw Telegram actif)", "INFO", indent=1)
            report["telegram"] = "openclaw"
        elif dry_run:
            log("Telegram bot: (dry-run, skip)", "WARN", indent=1)
            report["telegram"] = "dry_run"
        else:
            # Needs canvas proxy first
            if check_port("127.0.0.1", 18800):
                log("Telegram bot: demarrage...", "INFO", indent=1)
                start_process(
                    ["node", str(telegram_bot)],
                    "Telegram Bot", cwd=str(TURBO_DIR),
                )  # singleton kills existing via PID
                time.sleep(3)
                log("Telegram bot: lance", "OK", indent=1)
                report["telegram"] = "started"
            else:
                log("Telegram bot: skip (canvas proxy pas pret)", "WARN", indent=1)
                report["telegram"] = "no_proxy"

    # -- WhisperFlow (Voice Overlay) --
    whisperflow_dir = TURBO_DIR / "whisperflow"
    if "whisperflow" not in skip and whisperflow_dir.exists():
        if dry_run:
            log("WhisperFlow: (dry-run, skip)", "WARN", indent=1)
            report["whisperflow"] = "dry_run"
        else:
            # Needs WS backend (port 9742) first
            if check_port("127.0.0.1", 9742):
                log("WhisperFlow: demarrage overlay...", "INFO", indent=1)
                # Try npx electron (local install), then global, then browser fallback
                wf_node_modules = whisperflow_dir / "node_modules" / ".bin" / "electron.cmd"
                if wf_node_modules.exists():
                    proc = start_process(
                        [str(wf_node_modules), "."],
                        "WhisperFlow", cwd=str(whisperflow_dir),
                    )
                elif subprocess.run(["where", "electron"], capture_output=True).returncode == 0:
                    proc = start_process(
                        ["electron", "."],
                        "WhisperFlow", cwd=str(whisperflow_dir),
                    )
                else:
                    proc = None
                if proc:
                    log("WhisperFlow: lance (Electron)", "OK", indent=1)
                    report["whisperflow"] = "started_electron"
                else:
                    # Fallback: open in browser via WS backend
                    log("WhisperFlow: Electron absent, ouverture navigateur...", "INFO", indent=1)
                    import webbrowser
                    webbrowser.open("http://127.0.0.1:9742/whisperflow/")
                    report["whisperflow"] = "started_browser"
                    log("WhisperFlow: lance (navigateur)", "OK", indent=1)
            else:
                log("WhisperFlow: skip (WS backend pas pret sur :9742)", "WARN", indent=1)
                report["whisperflow"] = "no_ws_backend"

    # -- MCP SSE Server — singleton anti-doublon --
    if "mcp_sse" not in skip:
        if dry_run:
            log("MCP SSE: (dry-run, skip)", "WARN", indent=1)
            report["mcp_sse"] = "dry_run"
        else:
            was_running = check_port("127.0.0.1", 8901)
            if was_running:
                log("MCP SSE: existant detecte, arret via singleton...", "INFO", indent=1)
            log("MCP SSE: demarrage :8901...", "INFO", indent=1)
            start_process(
                [uv, "run", "python", "-m", "src.mcp_server_sse", "--port", "8901"],
                "MCP SSE", cwd=str(TURBO_DIR),
                singleton_port=8901,
            )
            if wait_for_port("127.0.0.1", 8901, max_wait=10):
                log(f"MCP SSE: demarre :8901 (restart={'oui' if was_running else 'non'})", "OK", indent=1)
                report["mcp_sse"] = "restarted" if was_running else "started"
            else:
                log("MCP SSE: port 8901 pas ouvert apres 10s", "FAIL", indent=1)
                report["mcp_sse"] = "failed"

    return report


# ============================================================================
# PHASE 5: WATCHDOGS
# ============================================================================
def phase_5_watchdogs(dry_run: bool = False, skip: list[str] | None = None) -> dict:
    """Phase 5 — retired. All daemons now handled by Automation Hub (python_ws on :9742).

    Previously launched standalone daemons that are now redundant:
    - auto_heal_daemon.py   → Automation Hub health_check + self_heal handlers
    - process_gc.py         → Automation Hub zombie_gc handler
    - vram_guard.py         → Automation Hub gpu_monitor handler
    - cluster_autonomy.py   → Automation Hub cluster monitoring
    - task_orchestrator.py   → Automation Hub task scheduler
    - openclaw_watchdog.py  → OpenClaw's own Scheduled Task service
    """
    log("PHASE 5 — SKIPPED (daemons handled by Automation Hub :9742)", "PHASE")
    return {"status": "retired_to_automation_hub"}


# ============================================================================
# PHASE 6: VALIDATION
# ============================================================================
def phase_6_validation() -> dict:
    """Final health check — cluster, services, databases."""
    log("PHASE 6 — VALIDATION FINALE", "PHASE")
    report: dict[str, Any] = {"nodes": {}, "services": {}, "databases": {}}

    # -- Cluster nodes --
    for name, node in NODES.items():
        online = check_port(node["ip"], node["port"], timeout=3)
        status = "OK" if online else "OFFLINE"
        loaded = 0
        if online:
            headers = {"Authorization": f"Bearer {node['auth']}"}
            data = http_get(f"{node['url']}/api/v1/models", headers=headers)
            if data:
                models = data.get("data", data.get("models", []))
                loaded = sum(1 for m in models if m.get("loaded_instances"))
        report["nodes"][name] = {"status": status, "loaded": loaded}
        lvl = "OK" if online else "DIM"
        extra = f" ({loaded} modeles)" if online else ""
        log(f"{name} ({node['ip']}:{node['port']}): {status}{extra}", lvl, indent=1)

    # Ollama
    ol_online = check_port(OLLAMA["ip"], OLLAMA["port"])
    if ol_online:
        data = http_get(f"{OLLAMA['url']}/api/tags")
        count = len(data.get("models", [])) if data else 0
        report["nodes"]["OL1"] = {"status": "OK", "models": count}
        log(f"OL1 Ollama: OK ({count} modeles)", "OK", indent=1)
    else:
        report["nodes"]["OL1"] = {"status": "OFFLINE"}
        log("OL1 Ollama: OFFLINE", "DIM", indent=1)

    # -- Services --
    for svc_id, svc in SERVICES.items():
        online = check_port("127.0.0.1", svc["port"])
        report["services"][svc_id] = "OK" if online else "OFFLINE"
        lvl = "OK" if online else "DIM"
        log(f"{svc['name']} (:{svc['port']}): {'OK' if online else 'OFFLINE'}", lvl, indent=1)

    # -- Databases --
    log("Bases SQLite:", "INFO", indent=1)
    total_tables = 0
    total_rows = 0
    for db_name, db_path in DATABASES.items():
        info = check_db_integrity(db_path)
        report["databases"][db_name] = info
        if info["ok"]:
            total_tables += info["tables"]
            total_rows += info["rows"]
            log(f"  {db_name}: OK ({info['tables']} tables, {info['rows']} rows, "
                f"{info['size_mb']}MB)", "OK", indent=1)
        else:
            log(f"  {db_name}: ERREUR ({info.get('error', '?')})", "FAIL", indent=1)
    log(f"  Total: {total_tables} tables, {total_rows} rows", "INFO", indent=1)

    # -- Disques --
    log("Disques:", "INFO", indent=1)
    for drive in ("/\", "F:/"):
        try:
            import shutil
            total, used, free = shutil.disk_usage(drive)
            free_gb = round(free / (1024**3), 1)
            total_gb = round(total / (1024**3), 1)
            pct = round(used / total * 100)
            lvl = "OK" if free_gb > 10 else "WARN"
            log(f"  {drive} {free_gb}GB libre / {total_gb}GB ({pct}% utilise)", lvl, indent=1)
        except OSError:
            log(f"  {drive} non accessible", "WARN", indent=1)

    return report


# ============================================================================
# FINAL REPORT
# ============================================================================
def print_final_report(reports: dict, duration_s: float):
    """Print the unified final report."""
    print()
    banner("JARVIS UNIFIED BOOT — RAPPORT FINAL", "=")

    # Count statuses
    nodes = reports.get("validation", {}).get("nodes", {})
    services = reports.get("validation", {}).get("services", {})

    nodes_ok = sum(1 for v in nodes.values() if v.get("status") == "OK")
    nodes_total = len(nodes)
    svcs_ok = sum(1 for v in services.values() if v == "OK")
    svcs_total = len(services)

    grade = "A" if (nodes_ok >= 3 and svcs_ok >= 4) else \
            "B" if (nodes_ok >= 2 and svcs_ok >= 3) else \
            "C" if (nodes_ok >= 1 and svcs_ok >= 2) else "D"

    print(f"  {C_BOLD}Grade: {C_GREEN if grade in 'AB' else C_YELLOW}{grade}{C_RESET}")
    print(f"  {C_BOLD}Cluster:{C_RESET} {nodes_ok}/{nodes_total} noeuds")
    print(f"  {C_BOLD}Services:{C_RESET} {svcs_ok}/{svcs_total} actifs")
    print(f"  {C_BOLD}Duree:{C_RESET} {duration_s:.1f}s")
    print()

    # Nodes table
    print(f"  {C_CYAN}{'Noeud':<8} {'Status':<10} {'Detail'}{C_RESET}")
    print(f"  {'-'*40}")
    for name, info in nodes.items():
        status = info.get("status", "?")
        color = C_GREEN if status == "OK" else C_RED
        detail = ""
        if info.get("loaded"):
            detail = f"{info['loaded']} modeles"
        elif info.get("models"):
            detail = f"{info['models']} modeles"
        print(f"  {name:<8} {color}{status:<10}{C_RESET} {detail}")

    print()

    # Services table
    print(f"  {C_CYAN}{'Service':<20} {'Port':<8} {'Status'}{C_RESET}")
    print(f"  {'-'*45}")
    for svc_id, status in services.items():
        svc = SERVICES.get(svc_id, {})
        port = svc.get("port", "?")
        name = svc.get("name", svc_id)
        color = C_GREEN if status == "OK" else C_RED
        print(f"  {name:<20} :{port:<7} {color}{status}{C_RESET}")

    print(f"\n  {'='*50}")
    print(f"  {C_BOLD}Startup complete.{C_RESET}")
    print()


# ============================================================================
# STATUS MODE (no start)
# ============================================================================
def status_only():
    """Print current status without starting anything."""
    banner("JARVIS CLUSTER STATUS")
    report = phase_6_validation()
    return report


# ============================================================================
# WATCH MODE — Continuous service watchdog with auto-restart
# ============================================================================
WATCH_SERVICES = {
    "lmstudio_m1": {
        "port": 1234, "host": "127.0.0.1",
        "cmd": [LMS_CLI, "server", "start"],
        "cwd": str(TURBO_DIR),
        "post_start_wait": 15,
    },
    "ollama": {
        "port": 11434, "host": "127.0.0.1",
        "cmd": ["ollama", "serve"],
        "cwd": str(TURBO_DIR),
        "post_start_wait": 5,
    },
    "dashboard": {
        "port": 8080, "host": "127.0.0.1",
        "cmd": [str(HOME / ".local" / "bin" / "uv.exe"), "run", "python",
                str(TURBO_DIR / "dashboard" / "server.py")],
        "cwd": str(TURBO_DIR),
    },
    "canvas_proxy": {
        "port": 18800, "host": "127.0.0.1",
        "cmd": ["node", str(TURBO_DIR / "canvas" / "direct-proxy.js")],
        "cwd": str(TURBO_DIR),
    },
    "jarvis_ws": {
        "port": 9742, "host": "127.0.0.1",
        "cmd": [str(HOME / ".local" / "bin" / "uv.exe"), "run", "python",
                str(TURBO_DIR / "python_ws" / "server.py")],
        "cwd": str(TURBO_DIR),
    },
    # gemini_proxy: CLI tool (exit immediat), pas un daemon — retire du watchdog
    # Utiliser via: node gemini-proxy.js "prompt"
    "gemini_openai": {
        "port": 18793, "host": "127.0.0.1",
        "cmd": ["node", str(TURBO_DIR / "gemini-openai-proxy.js")],
        "cwd": str(TURBO_DIR),
    },
    "openclaw": {
        "port": 18789, "host": "127.0.0.1",
        "cmd": ["node", str(OPENCLAW_CMD), "gateway", "--port", "18789"],
        "cwd": str(OPENCLAW_DIR),
        "post_start_wait": 10,
    },
}


def check_process_alive(process_name: str) -> bool:
    """Check if a process is running by name using tasklist."""
    try:
        r = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {process_name}", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=5, encoding="utf-8", errors="replace",
        )
        return process_name.lower() in r.stdout.lower()
    except (subprocess.TimeoutExpired, OSError):
        return False


# Process-based services (no port to check)
_wf_electron = str(TURBO_DIR / "whisperflow" / "node_modules" / ".bin" / "electron.cmd")
WATCH_PROCESSES = {
    "whisperflow": {
        "process_name": "electron.exe",
        "cmd": [_wf_electron, "."] if Path(_wf_electron).exists() else ["electron", "."],
        "cwd": str(TURBO_DIR / "whisperflow"),
        "depends_on_port": 9742,
        "post_start_wait": 5,
    },
}


def watch_loop(interval: int = 60):
    """Continuously monitor essential services and restart any that crash.

    NOTE: process_gc and vram_guard are no longer launched here — they are
    handled by Automation Hub (health_check, gpu_monitor, zombie_gc handlers).
    """
    log(f"WATCH MODE actif — check services toutes les {interval}s", "PHASE")
    log("Services surveilles: " + ", ".join(WATCH_SERVICES.keys()), "INFO")
    log("Ctrl+C pour arreter", "DIM")

    while True:
        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            log("Watchdog arrete par l'utilisateur", "WARN")
            break

        # ── Cleanup dead PID files every cycle ──
        _singleton.cleanup_dead()

        restarted_lmstudio = False
        for svc_id, svc in WATCH_SERVICES.items():
            if not check_port(svc["host"], svc["port"], timeout=3):
                ts = datetime.now().strftime("%H:%M:%S")
                log(f"[{ts}] {svc_id} (:{svc['port']}) DOWN — redemarrage...", "WARN")
                proc = start_process(
                    svc["cmd"], svc_id, cwd=svc.get("cwd"),
                    singleton_port=svc["port"],  # kill orphan on port
                )
                if proc:
                    wait = svc.get("post_start_wait", 5)
                    time.sleep(wait)
                    if check_port(svc["host"], svc["port"], timeout=5):
                        log(f"  {svc_id}: relance OK (PID {proc.pid})", "OK")
                        if svc_id == "lmstudio_m1":
                            restarted_lmstudio = True
                    else:
                        log(f"  {svc_id}: relance echouee", "FAIL")

        # Check M1 LM Studio model (always after restart, or on every cycle)
        if check_port("127.0.0.1", 1234):
            headers = {"Authorization": f"Bearer {NODES['M1']['auth']}"}
            data = http_get(f"{NODES['M1']['url']}/api/v1/models", headers=headers)
            if data:
                models = data.get("data", data.get("models", []))
                loaded = [m.get("key", "") for m in models if m.get("loaded_instances")]
                if not any(M1_REQUIRED_MODEL_SHORT in str(m) for m in loaded):
                    reason = "restart serveur" if restarted_lmstudio else "modele decharge"
                    log(f"M1: qwen3-8b absent ({reason}) — rechargement...", "WARN")
                    try:
                        subprocess.run(
                            [LMS_CLI, "load", M1_REQUIRED_MODEL,
                             "--gpu", M1_MODEL_OPTS["gpu"],
                             "-c", str(M1_MODEL_OPTS["context"]),
                             "--parallel", str(M1_MODEL_OPTS["parallel"]), "-y"],
                            capture_output=True, timeout=180,
                        )
                        log("M1: qwen3-8b recharge", "OK")
                    except Exception as e:
                        log(f"M1: echec rechargement ({e})", "FAIL")

        # Check Telegram bot (PID file based — no port to check)
        # Only skip if OpenClaw Telegram CHANNEL is enabled (not just gateway running)
        openclaw_tg_channel_enabled = False
        try:
            import json as _json
            _oc_cfg = Path.home() / ".openclaw" / "openclaw.json"
            if _oc_cfg.exists():
                _oc = _json.loads(_oc_cfg.read_text(encoding="utf-8"))
                openclaw_tg_channel_enabled = _oc.get("channels", {}).get("telegram", {}).get("enabled", False)
        except Exception:
            pass
        if openclaw_tg_channel_enabled:
            # OpenClaw Telegram CHANNEL actif — JAMAIS relancer telegram-bot.js (meme token = conflit getUpdates)
            telegram_lock = TURBO_DIR / "canvas" / ".telegram-bot.lock"
            if telegram_lock.exists():
                try:
                    pid = int(telegram_lock.read_text().strip())
                    os.kill(pid, 0)
                    # Kill orphan telegram-bot to avoid conflict
                    os.kill(pid, 9)
                    log("  telegram_bot orphelin tue (OpenClaw Telegram actif)", "WARN")
                    telegram_lock.unlink(missing_ok=True)
                except (ValueError, OSError):
                    telegram_lock.unlink(missing_ok=True)
        else:
            telegram_lock = TURBO_DIR / "canvas" / ".telegram-bot.lock"
            telegram_alive = False
            if telegram_lock.exists():
                try:
                    pid = int(telegram_lock.read_text().strip())
                    os.kill(pid, 0)  # Check if process alive (signal 0)
                    telegram_alive = True
                except (ValueError, OSError):
                    telegram_alive = False
            if not telegram_alive and check_port("127.0.0.1", 18800):
                ts = datetime.now().strftime("%H:%M:%S")
                log(f"[{ts}] telegram_bot DOWN — redemarrage...", "WARN")
                start_process(
                    ["node", str(TURBO_DIR / "canvas" / "telegram-bot.js")],
                    "Telegram Bot", cwd=str(TURBO_DIR),
                )  # singleton kills existing
                time.sleep(3)
                log("  telegram_bot: relance [singleton]", "OK")

        # Check LinkedIn Scheduler (PID file based — no port)
        # Also check if ANY linkedin_scheduler python process exists to avoid zombies
        linkedin_lock = TURBO_DIR / "data" / ".linkedin-scheduler.lock"
        linkedin_alive = False
        if linkedin_lock.exists():
            try:
                pid = int(linkedin_lock.read_text().strip())
                os.kill(pid, 0)
                linkedin_alive = True
            except (ValueError, OSError):
                linkedin_alive = False
        if not linkedin_alive:
            # Double-check: is there already a process running without lock file?
            try:
                r = subprocess.run(
                    ['wmic', 'process', 'where',
                     "name='python.exe' and commandline like '%linkedin_scheduler%'",
                     'get', 'ProcessId'],
                    capture_output=True, text=True, timeout=5, encoding="utf-8", errors="replace",
                )
                existing = [l.strip() for l in r.stdout.splitlines() if l.strip().isdigit()]
                if existing:
                    linkedin_alive = True  # Orphan process exists, don't spawn another
                    log("  linkedin_scheduler: orphan process detected, skipping restart", "WARN")
            except Exception:
                pass
        if not linkedin_alive:
            ts = datetime.now().strftime("%H:%M:%S")
            log(f"[{ts}] linkedin_scheduler DOWN — redemarrage...", "WARN")
            proc = start_process(
                [sys.executable, str(TURBO_DIR / "scripts" / "linkedin_scheduler.py")],
                "LinkedIn Scheduler", cwd=str(TURBO_DIR),
            )  # singleton kills existing
            if proc:
                time.sleep(3)
                log("  linkedin_scheduler: relance [singleton]", "OK")

        # ── Lightweight Telegram pipeline scheduler ──────────────
        # Runs scripts directly (no OpenClaw agent overhead)
        _tg_cmd = HOME / ".openclaw" / "workspace" / "dev" / "telegram_commander.py"
        if _tg_cmd.exists():
            if not hasattr(watch_loop, "_tg_counters"):
                watch_loop._tg_counters = {"trading": 0, "status": 0, "health": 0}
            c = watch_loop._tg_counters
            c["trading"] += 1
            c["status"] += 1
            c["health"] += 1
            tg_schedules = {"trading": 30, "status": 60, "health": 60}  # minutes
            for cmd, interval_min in tg_schedules.items():
                cycles_needed = max(1, interval_min * 60 // interval)
                if c[cmd] >= cycles_needed:
                    c[cmd] = 0
                    try:
                        subprocess.run(
                            [sys.executable, str(_tg_cmd), "--cmd", cmd],
                            capture_output=True, timeout=30,
                            cwd=str(_tg_cmd.parent),
                        )
                        log(f"  telegram_{cmd}: envoye", "OK")
                    except Exception as e:
                        log(f"  telegram_{cmd}: erreur ({e})", "WARN")

        # ── Zombie killer, process GC, VRAM guard, audit cycle ──
        # All removed — handled by Automation Hub (zombie_gc, gpu_monitor,
        # health_check, self_heal handlers on :9742)

        # Check process-based services (WhisperFlow, etc.)
        for svc_id, svc in WATCH_PROCESSES.items():
            dep_port = svc.get("depends_on_port")
            if dep_port and not check_port("127.0.0.1", dep_port, timeout=3):
                continue  # Skip restart if dependency is down

            if not check_process_alive(svc["process_name"]):
                ts = datetime.now().strftime("%H:%M:%S")
                log(f"[{ts}] {svc_id} ({svc['process_name']}) DOWN — redemarrage...", "WARN")
                proc = start_process(svc["cmd"], svc_id, cwd=svc.get("cwd"))
                if proc:
                    wait = svc.get("post_start_wait", 5)
                    time.sleep(wait)
                    if check_process_alive(svc["process_name"]):
                        log(f"  {svc_id}: relance OK (PID {proc.pid})", "OK")
                    else:
                        log(f"  {svc_id}: relance echouee", "FAIL")


# ============================================================================
# MAIN
# ============================================================================
def main():
    parser = argparse.ArgumentParser(description="JARVIS Unified Boot")
    parser.add_argument("--status", action="store_true", help="Status only, don't start anything")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--phase", type=str, default="1-6", help="Phases to run (e.g., 1-3, 2,4)")
    parser.add_argument("--skip", type=str, nargs="*", default=[],
                        help="Services to skip (n8n, gemini, canvas, dashboard, telegram)")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    parser.add_argument("--watch", action="store_true",
                        help="After boot, stay alive and restart crashed services")
    parser.add_argument("--fresh", action="store_true",
                        help="Kill existing services before restarting (anti-doublon)")
    parser.add_argument("--watch-interval", type=int, default=60,
                        help="Seconds between watchdog checks (default: 60)")
    args = parser.parse_args()

    # Enable ANSI on Windows
    if sys.platform == "win32":
        os.system("")  # Enables ANSI escape codes

    # Singleton check (skip for --status which is read-only)
    if not args.status:
        check_boot_singleton()

    if args.status:
        report = status_only()
        if args.json:
            print(json.dumps(report, indent=2, default=str))
        return

    # Parse phases
    phases_to_run = set()
    for part in args.phase.replace(" ", "").split(","):
        if "-" in part:
            start, end = part.split("-", 1)
            phases_to_run.update(range(int(start), int(end) + 1))
        else:
            phases_to_run.add(int(part))

    t0 = time.time()
    banner("JARVIS UNIFIED BOOT v10.6")
    reports: dict[str, Any] = {}

    # Anti-doublon: chaque service est tue+relance via singleton (kill_existing + kill_on_port)
    log("Mode anti-doublon actif: kill existant avant relance", "INFO")

    try:
        if 1 in phases_to_run:
            reports["infra"] = phase_1_infrastructure(args.dry_run)
        if 2 in phases_to_run:
            reports["models"] = phase_2_models(args.dry_run)
        if 3 in phases_to_run:
            reports["node_services"] = phase_3_node_services(args.dry_run, args.skip)
        if 4 in phases_to_run:
            reports["python_services"] = phase_4_python_services(args.dry_run, args.skip)
        if 5 in phases_to_run:
            reports["watchdogs"] = phase_5_watchdogs(args.dry_run, args.skip)
        if 6 in phases_to_run:
            reports["validation"] = phase_6_validation()
    except KeyboardInterrupt:
        print(f"\n{C_YELLOW}Interrupted.{C_RESET}")

    duration = time.time() - t0

    if args.json:
        reports["duration_s"] = round(duration, 1)
        print(json.dumps(reports, indent=2, default=str))
    elif 6 in phases_to_run:
        print_final_report(reports, duration)
    else:
        log(f"Boot termine en {duration:.1f}s", "OK")

    # Save boot log to SQLite
    try:
        db_path = TURBO_DIR / "data" / "etoile.db"
        if db_path.exists():
            db = sqlite3.connect(str(db_path))
            db.execute("""CREATE TABLE IF NOT EXISTS boot_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT, duration_s REAL, phases TEXT, report TEXT)""")
            db.execute(
                "INSERT INTO boot_log (ts, duration_s, phases, report) VALUES (?, ?, ?, ?)",
                (datetime.now().isoformat(), round(duration, 1),
                 str(sorted(phases_to_run)), json.dumps(reports, default=str)),
            )
            db.commit()
            db.close()
    except Exception:
        pass

    # Enter watchdog mode if requested
    if args.watch:
        watch_loop(args.watch_interval)


if __name__ == "__main__":
    main()
