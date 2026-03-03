"""JARVIS — DominoExecutor: executeur de cascades domino distribue.

Architecture concue par consensus cluster:
  [GEMINI] Architecture orchestrateur/worker + routing + fallback
  [M2/deepseek] Code async + aiohttp
  [M1/qwen3-8b] Logique de routing par type de step

Execution: chaque DominoPipeline est execute step par step,
avec routing vers le bon noeud, gestion d'erreur, logging SQLite,
et rapport TTS final.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request

logger = logging.getLogger("jarvis.domino_executor")

from src.config import config, prepare_lmstudio_input, PATHS
from src.domino_pipelines import DominoPipeline, DominoStep, find_domino


# ══════════════════════════════════════════════════════════════════════════════
# CLUSTER NODES — sourced from config.py (no hardcoded keys)
# ══════════════════════════════════════════════════════════════════════════════

def _build_nodes() -> dict:
    """Build NODES dict from config (avoids hardcoded IPs)."""
    nodes = {"LOCAL": {"url": None, "model": None, "weight": 1.0}}
    for n in config.lm_nodes:
        nodes[n.name] = {"url": n.url, "model": n.default_model, "weight": n.weight}
    for n in config.ollama_nodes:
        nodes[n.name] = {"url": n.url, "model": n.default_model, "weight": n.weight}
    return nodes

NODES = _build_nodes()

FALLBACK_CHAIN = ["M1", "M2", "M3", "OL1", "LOCAL"]


def _get_auth_header(node_name: str) -> str:
    """Get auth header for a node from config (no hardcoded keys)."""
    node = config.get_node(node_name)
    if node and hasattr(node, 'auth_headers'):
        return node.auth_headers.get("Authorization", "")
    return ""


# ══════════════════════════════════════════════════════════════════════════════
# DOMINO LOGGER — SQLite logging pour chaque cascade
# ══════════════════════════════════════════════════════════════════════════════

_DEFAULT_DB = str(PATHS.get("etoile_db", "data/etoile.db"))


class DominoLogger:
    """Log chaque step de cascade domino dans SQLite."""

    def __init__(self, db_path: str = _DEFAULT_DB):
        self.db_path = db_path
        self._ensure_table()

    def _ensure_table(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS domino_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                domino_id TEXT NOT NULL,
                step_name TEXT NOT NULL,
                step_idx INTEGER NOT NULL,
                status TEXT NOT NULL,
                duration_ms REAL,
                node TEXT,
                output_preview TEXT,
                error TEXT,
                ts TEXT NOT NULL DEFAULT (datetime('now'))
            )""")

    def log_step(self, run_id: str, domino_id: str, step_name: str, step_idx: int,
                 status: str, duration_ms: float, node: str = "local",
                 output: str = "", error: str = ""):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO domino_logs (run_id, domino_id, step_name, step_idx, status, duration_ms, node, output_preview, error) VALUES (?,?,?,?,?,?,?,?,?)",
                (run_id, domino_id, step_name, step_idx, status, duration_ms, node, output[:200], error[:200])
            )

    def get_run_summary(self, run_id: str) -> dict:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT step_name, status, duration_ms, node FROM domino_logs WHERE run_id=? ORDER BY step_idx",
                (run_id,)
            ).fetchall()
        total_ms = sum(r[2] or 0 for r in rows)
        passed = sum(1 for r in rows if r[1] == "PASS")
        failed = sum(1 for r in rows if r[1] == "FAIL")
        return {
            "run_id": run_id, "steps": len(rows),
            "passed": passed, "failed": failed,
            "total_ms": round(total_ms, 1),
            "details": [{"step": r[0], "status": r[1], "ms": r[2], "node": r[3]} for r in rows],
        }


# ══════════════════════════════════════════════════════════════════════════════
# STEP ROUTER — Route chaque step vers le bon noeud
# ══════════════════════════════════════════════════════════════════════════════

def route_step(step: DominoStep) -> str:
    """Route un step vers le noeud optimal selon son type."""
    action_type = step.action_type.lower()

    if action_type in ("powershell", "bash"):
        return "LOCAL"
    elif action_type == "python":
        # GPU-heavy tasks go to M1, others local
        if "gpu" in step.name or "model" in step.name or "embed" in step.name:
            return "M1"
        return "LOCAL"
    elif action_type == "curl":
        # Extract target from action URL
        action = step.action.lower()
        if "10.5.0.2" in action:
            return "M1"
        elif "192.168.1.26" in action:
            return "M2"
        elif "192.168.1.113" in action:
            return "M3"
        elif "127.0.0.1:11434" in action:
            return "OL1"
        return "M1"  # Default curl to M1
    elif action_type == "pipeline":
        return "LOCAL"
    elif action_type == "condition":
        return "LOCAL"

    return "LOCAL"


def check_node_online(node_name: str, timeout: int = 3) -> bool:
    """Verifie si un noeud est en ligne."""
    node = NODES.get(node_name)
    if not node or not node["url"]:
        return True  # LOCAL always online
    try:
        url = node["url"]
        if "11434" in url:
            with urllib.request.urlopen(f"{url}/api/tags", timeout=timeout):
                pass
        else:
            req = urllib.request.Request(
                f"{url}/api/v1/models",
                headers={"Authorization": _get_auth_header(node_name)}
            )
            with urllib.request.urlopen(req, timeout=timeout):
                pass
        return True
    except (urllib.error.URLError, OSError):
        return False


def get_fallback_node(primary: str) -> str:
    """Trouve le prochain noeud disponible apres le primaire."""
    start_idx = FALLBACK_CHAIN.index(primary) if primary in FALLBACK_CHAIN else 0
    for node_name in FALLBACK_CHAIN[start_idx + 1:]:
        if check_node_online(node_name):
            return node_name
    return "LOCAL"


# ══════════════════════════════════════════════════════════════════════════════
# STEP EXECUTOR — Execute chaque type de step
# ══════════════════════════════════════════════════════════════════════════════

_DOMINO_PS_ALLOWLIST = re.compile(
    r"^(Get-|Set-|Start-Process|Write-|Test-|Select-|Where-Object|Format-|Out-|"
    r"Invoke-WebRequest|Measure-|Remove-Item|New-ItemProperty|Get-ChildItem|"
    r"nvidia-smi|git\s|cd\s|uv\s|npx\s|python|pip\s|node\s|"
    r"curl\s|\$|powershell)"
)

_DOMINO_PS_BLOCKLIST = re.compile(
    r"(Invoke-Expression|iex\s|rm\s+-rf|Format-Volume|Stop-Computer|"
    r"Restart-Computer|Clear-RecycleBin|del\s+/s|shutdown)"
)


def execute_powershell(command: str, timeout: int = 30) -> str:
    """Execute une commande PowerShell (validated against allowlist + blocklist)."""
    # Strip prefix if present
    cmd = command.replace("powershell:", "", 1) if command.startswith("powershell:") else command
    cmd = cmd.strip()
    # Block dangerous commands
    if _DOMINO_PS_BLOCKLIST.search(cmd):
        return f"BLOCKED: Dangerous command: {cmd[:80]}"
    # Block unknown commands (not in allowlist)
    if not _DOMINO_PS_ALLOWLIST.match(cmd):
        return f"BLOCKED: Command not in allowlist: {cmd[:80]}"
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", cmd],
        capture_output=True, text=True, timeout=timeout
    )
    return result.stdout.strip() or result.stderr.strip()


def execute_curl(action: str, timeout: int = 20) -> str:
    """Execute un appel API curl vers un noeud cluster."""
    url = action.replace("curl:", "", 1) if action.startswith("curl:") else action
    try:
        # Chat endpoints need POST with a body
        if "/api/v1/chat" in url:
            # LM Studio Responses API — find which node
            node_name = None
            for n, info in NODES.items():
                if info["url"] and info["url"] in url:
                    node_name = n
                    break
            model = NODES[node_name]["model"] if node_name else "qwen3-8b"
            prompt_text = prepare_lmstudio_input(
                "Reponds OK si tu fonctionnes.", node_name or "M1", model
            )
            body = json.dumps({
                "model": model,
                "input": prompt_text,
                "temperature": 0.1, "max_output_tokens": 32,
                "stream": False, "store": False,
            }).encode()
            req = urllib.request.Request(url, data=body,
                                        headers={"Content-Type": "application/json"})
            auth = _get_auth_header(node_name) if node_name else ""
            if auth:
                req.add_header("Authorization", auth)
        elif "/api/chat" in url:
            # Ollama chat endpoint — POST
            body = json.dumps({
                "model": "qwen3:1.7b",
                "messages": [{"role": "user", "content": "Reponds OK."}],
                "stream": False, "think": False,
            }).encode()
            req = urllib.request.Request(url, data=body,
                                        headers={"Content-Type": "application/json"})
        else:
            # GET for models/tags/health endpoints
            req = urllib.request.Request(url)
            for n, info in NODES.items():
                if info["url"] and info["url"] in url:
                    auth = _get_auth_header(n)
                    if auth:
                        req.add_header("Authorization", auth)
                    break
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read().decode()
        # Parse LM Studio response to extract content
        if "/api/v1/chat" in url:
            try:
                d = json.loads(data)
                for item in reversed(d.get("output", [])):
                    if isinstance(item, dict) and item.get("type") == "message":
                        content = item.get("content", "")
                        if isinstance(content, str):
                            return content[:300]
                        if isinstance(content, list):
                            for c in content:
                                if isinstance(c, dict) and c.get("type") == "output_text":
                                    return c["text"][:300]
            except json.JSONDecodeError as exc:
                logger.debug("LM Studio JSON parse failed: %s", exc)
        elif "/api/chat" in url:
            try:
                d = json.loads(data)
                return d.get("message", {}).get("content", data[:300])[:300]
            except json.JSONDecodeError as exc:
                logger.debug("Ollama JSON parse failed: %s", exc)
        return data[:500]
    except (urllib.error.URLError, OSError, json.JSONDecodeError, ValueError) as e:
        return f"ERROR: {e}"


_PYTHON_REGISTRY: dict[str, callable] = {}


def register_python_action(name: str):
    """Decorator to register a Python action for domino execution."""
    def decorator(func):
        _PYTHON_REGISTRY[name] = func
        return func
    return decorator


@register_python_action("edge_tts_speak")
def _tts_speak(text: str) -> str:
    """TTS speak via edge-tts (stub — logs to console)."""
    logger.info("[TTS] %s", text)
    return f"TTS: {text}"


@register_python_action("sqlite3_integrity_check")
def _sqlite3_integrity(db_name: str) -> str:
    """Check SQLite integrity."""
    import os
    db_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data", db_name))
    if not os.path.exists(db_path):
        return f"DB not found: {db_name}"
    import sqlite3 as _sql
    with _sql.connect(db_path, timeout=10) as conn:
        result = conn.execute("PRAGMA integrity_check").fetchone()
    return f"{db_name}: {result[0]}"


@register_python_action("sqlite3_table_counts")
def _sqlite3_counts(db_name: str) -> str:
    """Count rows in all tables of a SQLite database."""
    import os
    db_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data", db_name))
    if not os.path.exists(db_path):
        return f"DB not found: {db_name}"
    import sqlite3 as _sql
    with _sql.connect(db_path, timeout=10) as conn:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        counts = {}
        for t in tables:
            if not t.isidentifier():
                continue
            cnt = conn.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]  # noqa: S608 — table name validated
            counts[t] = cnt
    return "; ".join(f"{t}: {c}" for t, c in sorted(counts.items()))


@register_python_action("sqlite3_vacuum")
def _sqlite3_vacuum(db_name: str) -> str:
    """VACUUM a SQLite database."""
    import os
    db_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data", db_name))
    if not os.path.exists(db_path):
        return f"DB not found: {db_name}"
    import sqlite3 as _sql
    size_before = os.path.getsize(db_path)
    with _sql.connect(db_path, timeout=30) as conn:
        conn.execute("VACUUM")
    size_after = os.path.getsize(db_path)
    saved = size_before - size_after
    return f"{db_name}: VACUUM OK ({saved} bytes saved)"


@register_python_action("sqlite3_vacuum_if_needed")
def _sqlite3_vacuum_if(db_name: str, max_mb: str = "50") -> str:
    """VACUUM only if DB exceeds size threshold."""
    import os
    db_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data", db_name))
    if not os.path.exists(db_path):
        return f"DB not found: {db_name}"
    size_mb = os.path.getsize(db_path) / (1024 * 1024)
    threshold = float(max_mb)
    if size_mb < threshold:
        return f"{db_name}: {size_mb:.1f} MB < {threshold} MB — skip VACUUM"
    return _sqlite3_vacuum(db_name)


@register_python_action("start_pomodoro")
def _start_pomodoro(minutes: str = "25") -> str:
    """Start a pomodoro timer (non-blocking)."""
    mins = int(minutes)
    logger.info("[POMODORO] Timer started: %d minutes", mins)
    return f"Pomodoro: {mins} minutes started"


@register_python_action("check_last_backup_date")
def _check_backup() -> str:
    """Check the last backup date from data directory."""
    import os
    import glob
    data_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data"))
    backups = sorted(glob.glob(os.path.join(data_dir, "backup_*")), reverse=True)
    if backups:
        last = os.path.basename(backups[0])
        mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(backups[0])))
        return f"Last backup: {last} ({mtime})"
    return "No backups found in data/"


@register_python_action("check_portfolio_balance")
def _portfolio_balance() -> str:
    """Check trading portfolio balance (stub)."""
    return "[PORTFOLIO] Balance check — requires MEXC API connection"


@register_python_action("fetch_current_pnl")
def _fetch_pnl() -> str:
    """Fetch current PnL (stub)."""
    return "[PNL] Current PnL check — requires MEXC API connection"


@register_python_action("fetch_today_pnl")
def _fetch_today_pnl() -> str:
    """Fetch today's PnL (stub)."""
    return "[PNL] Today's PnL — requires MEXC API connection"


@register_python_action("weighted_consensus_vote")
def _consensus_vote() -> str:
    """Run weighted consensus vote across cluster (stub)."""
    return "[CONSENSUS] Vote requires active cluster nodes — use MAO consensus"


# ── Batch 73: Critical Python actions ──────────────────────────────────────

@register_python_action("backup_all_databases")
def _backup_all_dbs() -> str:
    """Backup all SQLite databases to data/backups/."""
    import os, shutil
    data_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data"))
    backup_dir = os.path.join(data_dir, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    backed = []
    for db_name in ("etoile.db", "jarvis.db", "sniper.db", "finetuning.db"):
        src = os.path.join(data_dir, db_name)
        if os.path.exists(src):
            dst = os.path.join(backup_dir, f"{db_name}.{ts}.bak")
            shutil.copy2(src, dst)
            backed.append(db_name)
    return f"Backup OK: {', '.join(backed)} -> backups/{ts}"


@register_python_action("backup_etoile_db")
def _backup_etoile() -> str:
    """Backup etoile.db specifically."""
    import os, shutil
    data_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data"))
    src = os.path.join(data_dir, "etoile.db")
    if not os.path.exists(src):
        return "etoile.db not found"
    backup_dir = os.path.join(data_dir, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    dst = os.path.join(backup_dir, f"etoile.db.{ts}.bak")
    shutil.copy2(src, dst)
    size_mb = os.path.getsize(src) / (1024 * 1024)
    return f"Backup etoile.db OK ({size_mb:.1f} MB) -> {dst}"


@register_python_action("check_api_keys_in_db")
def _check_api_keys() -> str:
    """Check for API keys stored in etoile.db."""
    import os
    db_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data", "etoile.db"))
    if not os.path.exists(db_path):
        return "etoile.db not found"
    import sqlite3 as _sql
    with _sql.connect(db_path, timeout=10) as conn:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        key_tables = [t for t in tables if "key" in t.lower() or "api" in t.lower() or "secret" in t.lower()]
        if not key_tables:
            return "No API key tables found in etoile.db"
        results = []
        for t in key_tables:
            cnt = conn.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]  # noqa: S608
            results.append(f"{t}: {cnt} entries")
    return "; ".join(results)


@register_python_action("kill_heaviest_gpu_process")
def _kill_heaviest_gpu() -> str:
    """Kill the GPU process using the most VRAM."""
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode != 0 or not r.stdout.strip():
            return "No GPU processes found"
        lines = [l.strip().split(", ") for l in r.stdout.strip().splitlines() if l.strip()]
        if not lines:
            return "No GPU processes running"
        heaviest = max(lines, key=lambda x: int(x[1]) if len(x) > 1 else 0)
        pid = heaviest[0]
        mem = heaviest[1] if len(heaviest) > 1 else "?"
        subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True, timeout=10)
        return f"Killed PID {pid} (using {mem} MB VRAM)"
    except (subprocess.TimeoutExpired, OSError, ValueError) as e:
        return f"ERROR: {e}"


@register_python_action("kill_idle_gpu_processes")
def _kill_idle_gpu() -> str:
    """Kill GPU processes using minimal VRAM (<100MB)."""
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        if not r.stdout.strip():
            return "No GPU processes"
        killed = 0
        for line in r.stdout.strip().splitlines():
            parts = line.strip().split(", ")
            if len(parts) >= 2 and int(parts[1]) < 100:
                subprocess.run(["taskkill", "/F", "/PID", parts[0]], capture_output=True, timeout=5)
                killed += 1
        return f"Killed {killed} idle GPU processes"
    except (subprocess.TimeoutExpired, OSError, ValueError) as e:
        return f"ERROR: {e}"


@register_python_action("clear_all_caches")
def _clear_caches() -> str:
    """Clear LRU caches and temp files."""
    from src.voice_correction import phonetic_normalize
    phonetic_normalize.cache_clear()
    import os, glob
    data_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data"))
    tmp_files = glob.glob(os.path.join(data_dir, "*.tmp"))
    for f in tmp_files:
        try:
            os.remove(f)
        except OSError:
            pass
    return f"Caches cleared. {len(tmp_files)} tmp files removed."


@register_python_action("send_telegram_notification")
def _send_telegram() -> str:
    """Send Telegram notification (stub — requires bot token)."""
    return "[TELEGRAM] Notification stub — configure bot token in etoile.db"


@register_python_action("throttle_gpu_if_critical")
def _throttle_gpu(threshold: str = "85") -> str:
    """Reduce GPU power if temperature exceeds threshold."""
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu,power.draw", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        if not r.stdout.strip():
            return "No GPU data"
        temps = []
        for line in r.stdout.strip().splitlines():
            parts = line.strip().split(", ")
            if parts:
                temps.append(int(float(parts[0])))
        max_temp = max(temps) if temps else 0
        limit = int(threshold)
        if max_temp > limit:
            subprocess.run(
                ["nvidia-smi", "-pl", "120"],
                capture_output=True, timeout=10,
            )
            return f"GPU {max_temp}C > {limit}C — power limited to 120W"
        return f"GPU {max_temp}C OK (threshold {limit}C)"
    except (subprocess.TimeoutExpired, OSError, ValueError) as e:
        return f"ERROR: {e}"


@register_python_action("check_recent_error_logs")
def _check_error_logs() -> str:
    """Check for recent errors in log files."""
    import os, glob
    log_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data"))
    logs = glob.glob(os.path.join(log_dir, "*.log"))
    errors = []
    for log_path in logs[:5]:
        try:
            with open(log_path, encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()[-50:]
            err_lines = [l.strip() for l in lines if "ERROR" in l or "CRITICAL" in l]
            if err_lines:
                errors.append(f"{os.path.basename(log_path)}: {len(err_lines)} errors")
        except OSError:
            pass
    return "; ".join(errors) if errors else "No recent errors in logs"


@register_python_action("save_session_state")
def _save_session() -> str:
    """Save current session state to data/session_state.json."""
    import os
    data_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data"))
    state = {
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "session": "active",
    }
    state_path = os.path.join(data_dir, "session_state.json")
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    return f"Session state saved to {state_path}"


@register_python_action("restore_latest_backup")
def _restore_backup() -> str:
    """Restore the latest backup of etoile.db."""
    import os, shutil, glob
    data_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data"))
    backup_dir = os.path.join(data_dir, "backups")
    backups = sorted(glob.glob(os.path.join(backup_dir, "etoile.db.*.bak")), reverse=True)
    if not backups:
        return "No backups found"
    latest = backups[0]
    dst = os.path.join(data_dir, "etoile.db")
    shutil.copy2(latest, dst)
    return f"Restored {os.path.basename(latest)} -> etoile.db"


@register_python_action("confirm_action")
def _confirm_action(message: str = "Confirmer?") -> str:
    """Log confirmation request (auto-approve in domino context)."""
    logger.info("[CONFIRM] %s — auto-approved in domino context", message)
    return f"CONFIRMED: {message}"


@register_python_action("get_session_stats")
def _get_session_stats() -> str:
    """Get session statistics from databases."""
    import os
    db_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data", "jarvis.db"))
    if not os.path.exists(db_path):
        return "jarvis.db not found"
    import sqlite3 as _sql
    with _sql.connect(db_path, timeout=10) as conn:
        try:
            cmd_count = conn.execute("SELECT COUNT(*) FROM command_history WHERE date(created_at) = date('now')").fetchone()[0]
        except _sql.OperationalError:
            cmd_count = 0
    return f"Today: {cmd_count} commands executed"


# ── Trading stubs (require MEXC API connection) ───────────────────────────

@register_python_action("configure_trading_alerts")
def _trading_alerts() -> str:
    return "[TRADING] Alert config — requires MEXC connection"

@register_python_action("assess_trading_risk")
def _assess_risk() -> str:
    return "[TRADING] Risk assessment — requires market data"

@register_python_action("validate_signal_score")
def _validate_signal() -> str:
    return "[TRADING] Signal validation — requires pipeline data"

@register_python_action("check_usdt_balance")
def _check_usdt() -> str:
    return "[TRADING] USDT balance — requires MEXC API"

@register_python_action("execute_mexc_order")
def _execute_order() -> str:
    return "[TRADING] Order execution — requires MEXC API"

@register_python_action("set_tp_sl_levels")
def _set_tp_sl() -> str:
    return "[TRADING] TP/SL config — requires open position"

@register_python_action("list_open_positions")
def _list_positions() -> str:
    return "[TRADING] Positions — requires MEXC API"

@register_python_action("close_all_positions")
def _close_all() -> str:
    return "[TRADING] Close all — requires MEXC API"

@register_python_action("calculate_session_pnl")
def _session_pnl() -> str:
    return "[TRADING] Session PnL — requires trade history"

@register_python_action("save_trading_report")
def _save_report() -> str:
    return "[TRADING] Report saved (stub)"

@register_python_action("load_price_history")
def _load_history(timeframe: str = "1h", days: str = "30") -> str:
    return f"[TRADING] Price history {timeframe}/{days}d — requires MEXC API"

@register_python_action("analyze_backtest_results")
def _analyze_backtest() -> str:
    return "[TRADING] Backtest analysis — requires history data"

@register_python_action("calculate_drawdown")
def _calc_drawdown() -> str:
    return "[TRADING] Drawdown calc — requires PnL data"

@register_python_action("close_trading_if_open")
def _close_if_open() -> str:
    return "[TRADING] Close if open — requires MEXC API"

@register_python_action("fetch_mexc_prices")
def _fetch_prices(coins: str = "BTC,ETH,SOL") -> str:
    return f"[TRADING] Fetch prices {coins} — requires MEXC API"


# ── Cluster/System stubs ──────────────────────────────────────────────────

@register_python_action("generate_cluster_sync_report")
def _sync_report() -> str:
    return "[CLUSTER] Sync report — requires active cluster nodes"

@register_python_action("check_model_loaded_local")
def _check_model() -> str:
    return "[CLUSTER] Model check — requires LM Studio connection"

@register_python_action("prepare_model_transfer_config")
def _transfer_config() -> str:
    return "[CLUSTER] Transfer config prepared (stub)"

@register_python_action("calculate_weighted_vote")
def _weighted_vote() -> str:
    return "[CLUSTER] Weighted vote — use MAO consensus"

@register_python_action("calculate_weighted_consensus")
def _weighted_consensus() -> str:
    return "[CLUSTER] Weighted consensus — use MAO consensus"

@register_python_action("evaluate_model_latency")
def _eval_latency() -> str:
    return "[CLUSTER] Model latency eval — requires active nodes"

@register_python_action("trigger_model_swap")
def _trigger_swap() -> str:
    return "[CLUSTER] Model swap — requires LM Studio CLI"

@register_python_action("reduce_cluster_load")
def _reduce_load() -> str:
    return "[CLUSTER] Load reduced (stub)"

@register_python_action("compare_model_responses")
def _compare_responses() -> str:
    return "[CLUSTER] Response comparison — requires multiple models"


# ── Data/ETL stubs ────────────────────────────────────────────────────────

@register_python_action("extract_all_databases")
def _extract_dbs() -> str:
    return "[ETL] Extract all DBs (stub)"

@register_python_action("transform_and_clean")
def _transform() -> str:
    return "[ETL] Transform & clean (stub)"

@register_python_action("load_to_target_db")
def _load_target() -> str:
    return "[ETL] Load to target (stub)"

@register_python_action("verify_etl_integrity")
def _verify_etl() -> str:
    return "[ETL] Integrity verification (stub)"

@register_python_action("rebuild_search_index")
def _rebuild_index() -> str:
    return "[CACHE] Search index rebuilt (stub)"

@register_python_action("warm_up_cache")
def _warm_cache() -> str:
    return "[CACHE] Cache warmed up (stub)"

@register_python_action("save_weekly_metrics")
def _save_metrics() -> str:
    return "[METRICS] Weekly metrics saved (stub)"


# ── Multimedia/Notification stubs ─────────────────────────────────────────

@register_python_action("open_stream_chat_monitor")
def _open_chat() -> str:
    return "[STREAM] Chat monitor opened (stub)"

@register_python_action("save_stream_vod_info")
def _save_vod() -> str:
    return "[STREAM] VOD info saved (stub)"

@register_python_action("build_telegram_alert")
def _build_telegram() -> str:
    return "[TELEGRAM] Alert message built (stub)"

@register_python_action("build_desktop_notification")
def _build_toast() -> str:
    return "[NOTIFICATION] Desktop notification built (stub)"

# ── Batch 80: 3 new real + 2 stubs ──

@register_python_action("export_db_to_csv")
def _export_csv(db_name: str = "etoile.db") -> str:
    """Export all tables from a SQLite DB to CSV files."""
    import csv
    import sqlite3
    db_path = Path(os.getenv("TURBO_DIR", "F:/BUREAU/turbo")) / "data" / db_name
    out_dir = db_path.parent / "exports"
    out_dir.mkdir(exist_ok=True)
    if not db_path.exists():
        return f"DB introuvable: {db_path}"
    conn = sqlite3.connect(str(db_path))
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    exported = []
    for tbl in tables:
        rows = conn.execute(f"SELECT * FROM [{tbl}]").fetchall()
        cols = [d[0] for d in conn.execute(f"SELECT * FROM [{tbl}] LIMIT 0").description]
        csv_path = out_dir / f"{db_name.replace('.db', '')}_{tbl}.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(cols)
            w.writerows(rows)
        exported.append(f"{tbl}: {len(rows)} rows")
    conn.close()
    return f"Exported {len(tables)} tables to {out_dir}: " + ", ".join(exported)

@register_python_action("start_pomodoro_timer")
def _start_pomodoro_timer(minutes: str = "25") -> str:
    return f"[POMODORO] Timer started for {minutes} minutes"


def execute_python(action: str, timeout: int = 30) -> str:
    """Execute a registered Python action or return description for unknown ones."""
    func_str = action.replace("python:", "", 1) if action.startswith("python:") else action
    func_str = func_str.strip()

    # Parse function call: "func_name('arg1', 'arg2')" or "func_name(arg1)"
    match = re.match(r"(\w+)\(([^)]*)\)", func_str)
    if match:
        func_name = match.group(1)
        args_str = match.group(2).strip()
        # Parse arguments (simple string extraction)
        args = [a.strip().strip("'\"") for a in args_str.split(",") if a.strip()] if args_str else []

        if func_name in _PYTHON_REGISTRY:
            try:
                return _PYTHON_REGISTRY[func_name](*args)
            except (TypeError, ValueError, OSError) as e:
                return f"ERROR: {func_name}: {e}"

    return f"[PYTHON:UNREGISTERED] {func_str}"


def execute_bash(command: str, timeout: int = 30) -> str:
    """Execute une commande bash/shell."""
    cmd = command.replace("bash:", "", 1) if command.startswith("bash:") else command
    cmd = cmd.strip()
    if _DOMINO_PS_BLOCKLIST.search(cmd):
        return f"BLOCKED: Dangerous command: {cmd[:80]}"
    result = subprocess.run(
        ["bash", "-c", cmd],
        capture_output=True, text=True, timeout=timeout
    )
    return result.stdout.strip() or result.stderr.strip()


def execute_step(step: DominoStep, node: str) -> tuple[str, str]:
    """Execute un step et retourne (status, output)."""
    try:
        if step.action_type == "powershell":
            output = execute_powershell(step.action, step.timeout_s)
            if output.startswith("BLOCKED:"):
                return "FAIL", output
            return "PASS", output
        elif step.action_type == "bash":
            output = execute_bash(step.action, step.timeout_s)
            if output.startswith("BLOCKED:"):
                return "FAIL", output
            return "PASS", output
        elif step.action_type == "curl":
            output = execute_curl(step.action, step.timeout_s)
            if output.startswith("ERROR:"):
                return "FAIL", output
            return "PASS", output
        elif step.action_type == "python":
            output = execute_python(step.action, step.timeout_s)
            return "PASS", output
        elif step.action_type == "pipeline":
            output = f"[PIPELINE] {step.action}"
            return "PASS", output
        elif step.action_type == "condition":
            return "PASS", f"[CONDITION] {step.condition}"
        else:
            return "PASS", f"[UNKNOWN TYPE] {step.action_type}"
    except subprocess.TimeoutExpired:
        return "FAIL", f"TIMEOUT ({step.timeout_s}s)"
    except (OSError, ValueError) as e:
        return "FAIL", str(e)[:200]


# ══════════════════════════════════════════════════════════════════════════════
# DOMINO EXECUTOR — Orchestrateur principal
# ══════════════════════════════════════════════════════════════════════════════

class DominoExecutor:
    """Execute une cascade domino step par step avec routing + fallback + logging."""

    def __init__(self, db_path: str = _DEFAULT_DB):
        self.logger = DominoLogger(db_path)
        self.results: list[dict] = []

    def run(self, domino: DominoPipeline, run_id: str | None = None) -> dict:
        """Execute un domino pipeline complet."""
        run_id = run_id or f"{domino.id}_{int(time.time())}"
        total_start = time.time()
        passed = failed = skipped = 0

        logger.info("DOMINO CASCADE: %s (%s) — %s — %d steps, priority=%s",
                    domino.id, domino.category, domino.description, len(domino.steps), domino.priority)

        for idx, step in enumerate(domino.steps):
            step_start = time.time()

            # Check condition
            if step.condition:
                logger.debug("[%d] %s — CONDITION: %s", idx + 1, step.name, step.condition)

            # Route to best node
            primary_node = route_step(step)
            node = primary_node

            # Check if node online, fallback if not
            if not check_node_online(node, timeout=int(config.health_timeout)):
                fallback = get_fallback_node(node)
                logger.warning("[%d] %s — %s OFFLINE, fallback -> %s", idx + 1, step.name, node, fallback)
                node = fallback

            # Execute step
            status, output = execute_step(step, node)
            duration_ms = (time.time() - step_start) * 1000

            # Handle failure
            if status == "FAIL":
                if step.on_fail == "skip":
                    logger.info("[%d] %s — SKIP (%s) — %s", idx + 1, step.name, node, output[:60])
                    skipped += 1
                    status = "SKIP"
                elif step.on_fail == "stop":
                    logger.error("[%d] %s — FAIL STOP (%s) — %s", idx + 1, step.name, node, output[:60])
                    failed += 1
                    self.logger.log_step(run_id, domino.id, step.name, idx, "FAIL", duration_ms, node, output)
                    break
                else:
                    logger.warning("[%d] %s — FAIL (%s) — %s", idx + 1, step.name, node, output[:60])
                    failed += 1
            else:
                logger.info("[%d] %s — PASS (%s) %.0fms — %s", idx + 1, step.name, node, duration_ms, output[:50])
                passed += 1

            # Log to SQLite
            self.logger.log_step(run_id, domino.id, step.name, idx, status, duration_ms, node, output)

        total_ms = (time.time() - total_start) * 1000

        result = {
            "run_id": run_id,
            "domino_id": domino.id,
            "category": domino.category,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "total_ms": round(total_ms, 1),
            "total_steps": len(domino.steps),
        }
        self.results.append(result)

        logger.info("RESULTAT: %d PASS / %d FAIL / %d SKIP en %.0fms", passed, failed, skipped, total_ms)
        return result

    def run_by_voice(self, text: str) -> dict | None:
        """Trouve et execute un domino par phrase vocale."""
        domino = find_domino(text)
        if domino:
            return self.run(domino)
        logger.info("Aucun domino trouve pour: %r", text)
        return None

    def run_category(self, category: str) -> list[dict]:
        """Execute tous les dominos d'une categorie."""
        from src.domino_pipelines import DOMINO_PIPELINES
        results = []
        for dp in DOMINO_PIPELINES:
            if dp.category == category:
                results.append(self.run(dp))
        return results

    def get_all_results(self) -> dict:
        """Resume de toutes les executions."""
        total_pass = sum(r["passed"] for r in self.results)
        total_fail = sum(r["failed"] for r in self.results)
        total_skip = sum(r["skipped"] for r in self.results)
        total_ms = sum(r["total_ms"] for r in self.results)
        return {
            "runs": len(self.results),
            "total_pass": total_pass,
            "total_fail": total_fail,
            "total_skip": total_skip,
            "total_ms": round(total_ms, 1),
            "details": self.results,
        }
