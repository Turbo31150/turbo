#!/usr/bin/env python3
"""JARVIS Unified Boot — UN SEUL script pour TOUT demarrer.

Remplace les 19+ .bat/.ps1/.py disperses par un demarrage orchestre
en 6 phases avec detection fiable et retry.

Phases:
  1. Infrastructure  — LM Studio server, Ollama, GPU check
  2. Modeles         — Load/verify models on M1, check M2/M3
  3. Services Node   — n8n, Gemini proxy, Canvas proxy
  4. Services Python — Dashboard, Telegram bot, MCP SSE
  5. Watchdogs       — OpenClaw watchdog, cluster monitor
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

# ============================================================================
# CONFIG
# ============================================================================
TURBO_DIR = Path("F:/BUREAU/turbo")
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

# Cluster nodes
NODES = {
    "M1": {"url": "http://127.0.0.1:1234", "ip": "127.0.0.1", "port": 1234,
            "auth": "sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7"},
    "M2": {"url": "http://192.168.1.26:1234", "ip": "192.168.1.26", "port": 1234,
            "auth": "sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4"},
    "M3": {"url": "http://192.168.1.113:1234", "ip": "192.168.1.113", "port": 1234,
            "auth": "sk-lm-Zxbn5FZ1:M2PkaqHzwA4TilZ9EFux"},
}
OLLAMA = {"url": "http://127.0.0.1:11434", "ip": "127.0.0.1", "port": 11434}

# Services avec ports
SERVICES = {
    "n8n":           {"port": 5678, "name": "n8n Workflow Automation"},
    "dashboard":     {"port": 8080, "name": "JARVIS Dashboard"},
    "gemini_proxy":  {"port": 18791, "name": "Gemini Proxy"},
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
N8N_CMD = r"C:\nvm4w\nodejs\n8n.cmd"

LMS_CLI = str(HOME / ".lmstudio" / "bin" / "lms.exe")

# SQLite databases to verify
DATABASES = {
    "etoile": TURBO_DIR / "data" / "etoile.db",
    "jarvis": TURBO_DIR / "data" / "jarvis.db",
    "sniper": TURBO_DIR / "data" / "sniper.db",
    "finetuning": TURBO_DIR / "data" / "finetuning.db",
}

# Processes launched (for cleanup)
_launched_procs: list[subprocess.Popen] = []


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
                  shell: bool = False, hidden: bool = True) -> subprocess.Popen | None:
    """Start a background process, track it for cleanup."""
    try:
        kwargs: dict[str, Any] = {
            "cwd": cwd,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = (
                subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
            )
        if shell:
            kwargs["shell"] = True

        proc = subprocess.Popen(cmd, **kwargs)
        _launched_procs.append(proc)
        log(f"  Started {name} (PID {proc.pid})", "DIM", indent=1)
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

    # -- LM Studio (M1) --
    m1_online = check_port(NODES["M1"]["ip"], NODES["M1"]["port"])
    if m1_online:
        log("M1 LM Studio: deja actif sur :1234", "OK", indent=1)
        report["m1"] = "already_running"
    else:
        if dry_run:
            log("M1 LM Studio: OFFLINE (dry-run, skip start)", "WARN", indent=1)
            report["m1"] = "dry_run"
        else:
            log("M1 LM Studio: demarrage serveur...", "INFO", indent=1)
            try:
                subprocess.run(
                    [LMS_CLI, "server", "start"],
                    capture_output=True, timeout=30, encoding="utf-8",
                )
                if wait_for_port("127.0.0.1", 1234, max_wait=20):
                    log("M1 LM Studio: demarre", "OK", indent=1)
                    report["m1"] = "started"
                else:
                    log("M1 LM Studio: pas de reponse apres 20s", "FAIL", indent=1)
                    report["m1"] = "start_failed"
            except (subprocess.SubprocessError, OSError) as e:
                log(f"M1 LM Studio: erreur CLI ({e})", "FAIL", indent=1)
                report["m1"] = "error"

    # -- Ollama --
    ol_online = check_port(OLLAMA["ip"], OLLAMA["port"])
    if ol_online:
        data = http_get(f"{OLLAMA['url']}/api/tags")
        count = len(data.get("models", [])) if data else 0
        log(f"Ollama: actif ({count} modeles)", "OK", indent=1)
        report["ollama"] = {"status": "online", "models": count}
    else:
        if dry_run:
            log("Ollama: OFFLINE (dry-run, skip start)", "WARN", indent=1)
            report["ollama"] = {"status": "dry_run"}
        else:
            log("Ollama: demarrage...", "INFO", indent=1)
            start_process(["ollama", "serve"], "Ollama")
            if wait_for_port("127.0.0.1", 11434, max_wait=15):
                log("Ollama: demarre", "OK", indent=1)
                report["ollama"] = {"status": "started"}
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
        output = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]|\[\\?25[hl]", "", output)
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
                    "model": M1_REQUIRED_MODEL,
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
    """Start n8n, Gemini proxy, Canvas proxy."""
    log("PHASE 3 — SERVICES NODE (n8n + proxies)", "PHASE")
    skip = skip or []
    report: dict[str, Any] = {}

    # -- n8n --
    if "n8n" not in skip:
        if check_port("127.0.0.1", 5678):
            log("n8n: deja actif sur :5678", "OK", indent=1)
            report["n8n"] = "already_running"
        elif dry_run:
            log("n8n: OFFLINE (dry-run)", "WARN", indent=1)
            report["n8n"] = "dry_run"
        else:
            log("n8n: demarrage...", "INFO", indent=1)
            env = os.environ.copy()
            env["N8N_SECURE_COOKIE"] = "false"
            env["EXECUTIONS_MODE"] = "regular"
            env["NODE_OPTIONS"] = "--max-old-space-size=4096"
            env["EXECUTIONS_DATA_PRUNE"] = "true"
            env["EXECUTIONS_DATA_MAX_AGE"] = "72"
            try:
                # Use .cmd wrapper on Windows for proper PATH resolution
                n8n_bin = N8N_CMD if os.path.exists(N8N_CMD) else "n8n"
                proc = subprocess.Popen(
                    [n8n_bin, "start"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    env=env, shell=True,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
                )
                _launched_procs.append(proc)
                if wait_for_port("127.0.0.1", 5678, max_wait=30):
                    log("n8n: demarre (PID {})".format(proc.pid), "OK", indent=1)
                    report["n8n"] = "started"
                else:
                    log("n8n: pas pret apres 30s", "FAIL", indent=1)
                    report["n8n"] = "timeout"
            except (OSError, FileNotFoundError):
                log("n8n: commande introuvable ({})".format(N8N_CMD), "FAIL", indent=1)
                report["n8n"] = "not_found"

    # -- Gemini Proxy --
    gemini_proxy_path = TURBO_DIR / "gemini-proxy.js"
    if "gemini" not in skip and gemini_proxy_path.exists():
        if check_port("127.0.0.1", 18791):
            log("Gemini proxy: deja actif sur :18791", "OK", indent=1)
            report["gemini_proxy"] = "already_running"
        elif dry_run:
            log("Gemini proxy: OFFLINE (dry-run)", "WARN", indent=1)
            report["gemini_proxy"] = "dry_run"
        else:
            log("Gemini proxy: demarrage...", "INFO", indent=1)
            # Gemini proxy needs shell=False and proper node path
            try:
                proc = subprocess.Popen(
                    ["node", str(gemini_proxy_path)],
                    cwd=str(TURBO_DIR),
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                )
                _launched_procs.append(proc)
                log(f"  Started Gemini Proxy (PID {proc.pid})", "DIM", indent=1)
            except Exception as e:
                log(f"  Gemini proxy start error: {e}", "FAIL", indent=1)
            if wait_for_port("127.0.0.1", 18791, max_wait=15):
                log("Gemini proxy: demarre sur :18791", "OK", indent=1)
                report["gemini_proxy"] = "started"
            else:
                log("Gemini proxy: port 18791 pas ouvert apres 15s", "WARN", indent=1)
                report["gemini_proxy"] = "failed"

    # -- Canvas Direct Proxy --
    canvas_proxy_path = TURBO_DIR / "canvas" / "direct-proxy.js"
    if "canvas" not in skip and canvas_proxy_path.exists():
        if check_port("127.0.0.1", 18800):
            log("Canvas proxy: deja actif sur :18800", "OK", indent=1)
            report["canvas_proxy"] = "already_running"
        elif dry_run:
            log("Canvas proxy: OFFLINE (dry-run)", "WARN", indent=1)
            report["canvas_proxy"] = "dry_run"
        else:
            log("Canvas proxy: demarrage...", "INFO", indent=1)
            start_process(
                ["node", str(canvas_proxy_path)],
                "Canvas Proxy", cwd=str(TURBO_DIR),
            )
            if wait_for_port("127.0.0.1", 18800, max_wait=10):
                log("Canvas proxy: demarre sur :18800", "OK", indent=1)
                report["canvas_proxy"] = "started"
            else:
                log("Canvas proxy: echec", "FAIL", indent=1)
                report["canvas_proxy"] = "failed"

    return report


# ============================================================================
# PHASE 4: PYTHON SERVICES
# ============================================================================
def phase_4_python_services(dry_run: bool = False, skip: list[str] | None = None) -> dict:
    """Start Dashboard, Telegram bot."""
    log("PHASE 4 — SERVICES PYTHON (Dashboard + Telegram)", "PHASE")
    skip = skip or []
    report: dict[str, Any] = {}
    uv = str(HOME / ".local" / "bin" / "uv.exe")

    # -- Dashboard --
    dashboard_script = TURBO_DIR / "dashboard" / "server.py"
    if "dashboard" not in skip and dashboard_script.exists():
        if check_port("127.0.0.1", 8080):
            log("Dashboard: deja actif sur :8080", "OK", indent=1)
            report["dashboard"] = "already_running"
        elif dry_run:
            log("Dashboard: OFFLINE (dry-run)", "WARN", indent=1)
            report["dashboard"] = "dry_run"
        else:
            log("Dashboard: demarrage...", "INFO", indent=1)
            start_process(
                [uv, "run", "python", str(dashboard_script)],
                "Dashboard", cwd=str(TURBO_DIR),
            )
            if wait_for_port("127.0.0.1", 8080, max_wait=10):
                log("Dashboard: demarre sur :8080", "OK", indent=1)
                report["dashboard"] = "started"
            else:
                log("Dashboard: echec", "FAIL", indent=1)
                report["dashboard"] = "failed"

    # -- Python WebSocket Server (Electron backend) --
    ws_script = TURBO_DIR / "python_ws" / "server.py"
    if "ws" not in skip and ws_script.exists():
        if check_port("127.0.0.1", 9742):
            log("Python WS: deja actif sur :9742", "OK", indent=1)
            report["jarvis_ws"] = "already_running"
        elif dry_run:
            log("Python WS: OFFLINE (dry-run)", "WARN", indent=1)
            report["jarvis_ws"] = "dry_run"
        else:
            log("Python WS: demarrage...", "INFO", indent=1)
            start_process(
                [uv, "run", "python", str(ws_script)],
                "Python WS", cwd=str(TURBO_DIR),
            )
            if wait_for_port("127.0.0.1", 9742, max_wait=15):
                log("Python WS: demarre sur :9742", "OK", indent=1)
                report["jarvis_ws"] = "started"
            else:
                log("Python WS: echec", "FAIL", indent=1)
                report["jarvis_ws"] = "failed"

    # -- Telegram Bot --
    telegram_bot = TURBO_DIR / "canvas" / "telegram-bot.js"
    if "telegram" not in skip and telegram_bot.exists():
        if dry_run:
            log("Telegram bot: (dry-run, skip)", "WARN", indent=1)
            report["telegram"] = "dry_run"
        else:
            # Needs canvas proxy first
            if check_port("127.0.0.1", 18800):
                log("Telegram bot: demarrage...", "INFO", indent=1)
                start_process(
                    ["node", str(telegram_bot)],
                    "Telegram Bot", cwd=str(TURBO_DIR),
                )
                time.sleep(3)
                log("Telegram bot: lance", "OK", indent=1)
                report["telegram"] = "started"
            else:
                log("Telegram bot: skip (canvas proxy pas pret)", "WARN", indent=1)
                report["telegram"] = "no_proxy"

    return report


# ============================================================================
# PHASE 5: WATCHDOGS
# ============================================================================
def phase_5_watchdogs(dry_run: bool = False, skip: list[str] | None = None) -> dict:
    """Start OpenClaw watchdog, cluster monitor."""
    log("PHASE 5 — WATCHDOGS", "PHASE")
    skip = skip or []
    report: dict[str, Any] = {}

    # -- OpenClaw watchdog --
    watchdog_script = OPENCLAW_DIR / "workspace" / "dev" / "openclaw_watchdog.py"
    python312 = r"C:\Users\franc\AppData\Local\Programs\Python\Python312\python.exe"

    if "watchdog" not in skip and watchdog_script.exists():
        # Only start if OpenClaw is actually reachable
        if check_port("127.0.0.1", 18789):
            if dry_run:
                log("OpenClaw watchdog: (dry-run, skip)", "WARN", indent=1)
                report["watchdog"] = "dry_run"
            else:
                log("OpenClaw watchdog: demarrage...", "INFO", indent=1)
                start_process(
                    [python312, str(watchdog_script), "--loop"],
                    "OpenClaw Watchdog",
                    cwd=str(OPENCLAW_DIR / "workspace"),
                )
                log("OpenClaw watchdog: lance", "OK", indent=1)
                report["watchdog"] = "started"
        else:
            log("OpenClaw watchdog: skip (OpenClaw non detecte sur :18789)", "DIM", indent=1)
            report["watchdog"] = "openclaw_offline"

    return report


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
    for drive in ("C:\\", "F:\\"):
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
}


def watch_loop(interval: int = 60):
    """Continuously monitor services and restart any that crash."""
    log(f"WATCHDOG actif — check toutes les {interval}s", "PHASE")
    log("Services surveilles: " + ", ".join(WATCH_SERVICES.keys()), "INFO")
    log("Ctrl+C pour arreter", "DIM")

    while True:
        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            log("Watchdog arrete par l'utilisateur", "WARN")
            break

        restarted_lmstudio = False
        for svc_id, svc in WATCH_SERVICES.items():
            if not check_port(svc["host"], svc["port"], timeout=3):
                ts = datetime.now().strftime("%H:%M:%S")
                log(f"[{ts}] {svc_id} (:{svc['port']}) DOWN — redemarrage...", "WARN")
                proc = start_process(svc["cmd"], svc_id, cwd=svc.get("cwd"))
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


# ============================================================================
# MAIN
# ============================================================================
def main():
    parser = argparse.ArgumentParser(description="JARVIS Unified Boot")
    parser.add_argument("--status", action="store_true", help="Status only, don't start anything")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--phase", type=str, default="1-6", help="Phases to run (e.g., 1-3, 2,4)")
    parser.add_argument("--skip", type=str, nargs="*", default=[],
                        help="Services to skip (n8n, gemini, canvas, dashboard, telegram, watchdog)")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    parser.add_argument("--watch", action="store_true",
                        help="After boot, stay alive and restart crashed services")
    parser.add_argument("--watch-interval", type=int, default=60,
                        help="Seconds between watchdog checks (default: 60)")
    args = parser.parse_args()

    # Enable ANSI on Windows
    if sys.platform == "win32":
        os.system("")  # Enables ANSI escape codes

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
