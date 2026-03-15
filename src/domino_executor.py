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
import os
import re
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request


__all__ = [
    "DominoExecutor",
    "DominoLogger",
    "check_node_online",
    "execute_bash",
    "execute_curl",
    "execute_powershell",
    "execute_python",
    "execute_step",
    "execute_tool_step",
    "get_fallback_node",
    "register_python_action",
    "route_step",
]

logger = logging.getLogger("jarvis.domino_executor")

from src.config import config, prepare_lmstudio_input, PATHS
from src.domino_pipelines import DominoPipeline, DominoStep, find_domino
from src.learned_actions import LearnedActionsEngine

_learned_engine = LearnedActionsEngine()


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


def _get_orchestrator_fallback(task_type: str = "system", exclude: set | None = None) -> list[str]:
    """Get fallback chain from orchestrator_v2 (drift-aware)."""
    try:
        from src.orchestrator_v2 import orchestrator_v2
        return orchestrator_v2.fallback_chain(task_type, exclude=exclude or set())
    except Exception:
        return list(FALLBACK_CHAIN)


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
        if "127.0.0.1" in action and ":1234" in action:
            return "M1"
        elif "192.168.1.26" in action:
            return "M2"
        elif "192.168.1.113" in action:
            return "M3"
        elif "127.0.0.1:11434" in action:
            return "OL1"
        return "M1"  # Default curl to M1
    elif action_type == "tool":
        return "LOCAL"  # Tools go via WS HTTP (port 9742)
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
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout
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
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
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
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
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
    """Send Telegram notification via Bot API."""
    import json
    import urllib.request
    token = os.environ.get("TELEGRAM_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT", "")
    if not token or not chat_id:
        return "[TELEGRAM] TELEGRAM_TOKEN ou TELEGRAM_CHAT manquant dans .env"
    try:
        # Collect system status for the notification
        msg = f"\ud83e\udd16 JARVIS Domino Notification\n{time.strftime('%Y-%m-%d %H:%M:%S')}"
        body = json.dumps({"chat_id": chat_id, "text": msg}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=body, headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
        return "[TELEGRAM] Notification envoyée"
    except Exception as e:
        return f"[TELEGRAM] Erreur: {e}"


@register_python_action("throttle_gpu_if_critical")
def _throttle_gpu(threshold: str = "85") -> str:
    """Reduce GPU power if temperature exceeds threshold."""
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu,power.draw", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
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
    db_path = Path(os.getenv("TURBO_DIR", "/home/turbo/jarvis-m1-ops")) / "data" / db_name
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


@register_python_action("sqlite3_analyze")
def _sqlite3_analyze() -> str:
    """Run ANALYZE on all databases to update query planner statistics."""
    import sqlite3
    results = []
    for db_name in ("etoile.db", "jarvis.db", "sniper.db"):
        db_path = Path(os.getenv("TURBO_DIR", "/home/turbo/jarvis-m1-ops")) / "data" / db_name
        if not db_path.exists():
            continue
        try:
            conn = sqlite3.connect(str(db_path))
            conn.execute("ANALYZE")
            conn.close()
            results.append(f"{db_name}: ANALYZE OK")
        except sqlite3.Error as e:
            results.append(f"{db_name}: ERROR {e}")
    return " | ".join(results) if results else "No databases found"


@register_python_action("count_commands")
def _count_commands() -> str:
    """Count total registered voice commands."""
    try:
        from src.commands import COMMANDS
        return f"Total commands: {len(COMMANDS)}"
    except ImportError:
        return "ERROR: Cannot import commands"


@register_python_action("count_voice_corrections")
def _count_voice_corrections() -> str:
    """Count total voice corrections in dictionary."""
    try:
        from src.commands import VOICE_CORRECTIONS
        return f"Total corrections: {len(VOICE_CORRECTIONS)}"
    except ImportError:
        return "ERROR: Cannot import VOICE_CORRECTIONS"


@register_python_action("test_voice_match")
def _test_voice_match(text: str = "ouvre chrome") -> str:
    """Test voice matching pipeline on a given text."""
    try:
        from src.commands import match_command
        cmd, params, score = match_command(text)
        if cmd:
            return f"MATCH: {cmd.name} (score={score:.2f}, params={params})"
        return f"NO MATCH for '{text}' (best_score={score:.2f})"
    except ImportError:
        return "ERROR: Cannot import match_command"


@register_python_action("backup_db")
def _backup_db(db_name: str = "jarvis.db") -> str:
    """Backup a specific database file."""
    import shutil
    from datetime import datetime
    db_path = Path(os.getenv("TURBO_DIR", "/home/turbo/jarvis-m1-ops")) / "data" / db_name
    if not db_path.exists():
        return f"DB introuvable: {db_path}"
    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{db_name.replace('.db', '')}_{ts}.db"
    shutil.copy2(str(db_path), str(backup_path))
    size_kb = backup_path.stat().st_size / 1024
    return f"Backup OK: {backup_path.name} ({size_kb:.1f} KB)"


@register_python_action("get_session_stats")
def _get_session_stats() -> str:
    """Get current voice session statistics."""
    try:
        from src.voice_correction import _recent_match_cache, IMPLICIT_COMMANDS, PHONETIC_GROUPS, FILLER_WORDS
        from src.commands import COMMANDS, VOICE_CORRECTIONS
        return (
            f"Session stats — Commands: {len(COMMANDS)}, "
            f"Corrections: {len(VOICE_CORRECTIONS)}, "
            f"Implicits: {len(IMPLICIT_COMMANDS)}, "
            f"Phonetics: {len(PHONETIC_GROUPS)}, "
            f"Fillers: {len(FILLER_WORDS)}, "
            f"Cache: {len(_recent_match_cache)} entries"
        )
    except ImportError as e:
        return f"ERROR: {e}"


@register_python_action("list_dominos")
def _list_dominos() -> str:
    """List all domino pipelines with IDs and categories."""
    try:
        from src.domino_pipelines import DOMINO_PIPELINES
        categories = {}
        for dp in DOMINO_PIPELINES:
            categories.setdefault(dp.category, []).append(dp.id)
        lines = [f"Total: {len(DOMINO_PIPELINES)} dominos"]
        for cat, ids in sorted(categories.items()):
            lines.append(f"  {cat}: {', '.join(ids)}")
        return "\n".join(lines)
    except ImportError as e:
        return f"ERROR: {e}"


@register_python_action("get_uptime")
def _get_uptime() -> str:
    """Get system uptime."""
    import time
    try:
        if os.name == "nt":
            import ctypes
            lib = ctypes.windll.kernel32
            tick = lib.GetTickCount64()
            uptime_s = tick / 1000
        else:
            with open("/proc/uptime") as f:
                uptime_s = float(f.read().split()[0])
        hours = int(uptime_s // 3600)
        mins = int((uptime_s % 3600) // 60)
        return f"Uptime: {hours}h {mins}m"
    except (OSError, AttributeError):
        return "Uptime: unavailable"


@register_python_action("get_disk_usage")
def _get_disk_usage() -> str:
    """Get disk usage for main drives."""
    import shutil
    results = []
    for drive in ["/\", "F:/"]:
        try:
            usage = shutil.disk_usage(drive)
            free_gb = usage.free / (1024**3)
            total_gb = usage.total / (1024**3)
            pct = (usage.used / usage.total) * 100
            results.append(f"{drive} {free_gb:.1f}GB free / {total_gb:.0f}GB ({pct:.0f}% used)")
        except (OSError, FileNotFoundError):
            continue
    return " | ".join(results) if results else "No drives found"


@register_python_action("clear_all_caches")
def _clear_all_caches() -> str:
    """Clear Python LRU caches and internal caches."""
    cleared = []
    try:
        from src.voice_correction import phonetic_normalize, remove_accents, _recent_match_cache
        phonetic_normalize.cache_clear()
        cleared.append("phonetic_normalize")
        remove_accents.cache_clear()
        cleared.append("remove_accents")
        _recent_match_cache.clear()
        cleared.append("recent_match_cache")
    except (ImportError, AttributeError):
        pass
    return f"Caches cleared: {', '.join(cleared)}" if cleared else "No caches to clear"


@register_python_action("count_lines_of_code")
def _count_lines_of_code() -> str:
    """Count lines of code in all Python source files."""
    import glob
    total = 0
    files = 0
    for f in glob.glob("src/*.py", root_dir="/home/turbo/jarvis-m1-ops"):
        try:
            with open(f"/home/turbo/jarvis-m1-ops/src/{f.replace('src/', '')}" if "/" in f else f"/home/turbo/jarvis-m1-ops/{f}") as fh:
                lines = sum(1 for _ in fh)
                total += lines
                files += 1
        except OSError:
            continue
    return f"{files} files, {total} lines total"


@register_python_action("list_env_versions")
def _list_env_versions() -> str:
    """List versions of key tools."""
    import subprocess
    versions = []
    for cmd, name in [("python --version", "Python"), ("node --version", "Node"), ("git --version", "Git")]:
        try:
            r = subprocess.run(cmd.split(), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5)
            versions.append(f"{name}: {r.stdout.strip()}")
        except (subprocess.TimeoutExpired, OSError):
            versions.append(f"{name}: N/A")
    return " | ".join(versions)


@register_python_action("db_table_count")
def _db_table_count() -> str:
    """Count tables and rows in all SQLite databases."""
    import sqlite3
    results = []
    for db_name in ["etoile.db", "jarvis.db", "sniper.db", "finetuning.db"]:
        db_path = f"/home/turbo/jarvis-m1-ops/data/{db_name}"
        try:
            conn = sqlite3.connect(db_path)
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            total_rows = sum(conn.execute(f"SELECT COUNT(*) FROM [{t[0]}]").fetchone()[0] for t in tables)
            results.append(f"{db_name}: {len(tables)} tables, {total_rows} rows")
            conn.close()
        except (sqlite3.Error, OSError):
            continue
    return " | ".join(results) if results else "No databases found"


@register_python_action("validate_json_files")
def _validate_json_files() -> str:
    """Validate all JSON files in data directory."""
    import json
    import glob
    ok = 0
    errors = []
    for f in glob.glob("/home/turbo/jarvis-m1-ops/data/*.json"):
        try:
            with open(f) as fh:
                json.load(fh)
            ok += 1
        except (json.JSONDecodeError, OSError) as e:
            errors.append(f"{f}: {e}")
    result = f"{ok} JSON files valid"
    if errors:
        result += f", {len(errors)} errors: {'; '.join(errors[:3])}"
    return result


@register_python_action("project_summary")
def _project_summary() -> str:
    """Generate a quick project summary."""
    try:
        from src.commands import COMMANDS, VOICE_CORRECTIONS
        from src.voice_correction import IMPLICIT_COMMANDS, PHONETIC_GROUPS, FILLER_WORDS
        from src.domino_pipelines import get_domino_stats
        ds = get_domino_stats()
        return (
            f"JARVIS Turbo: {len(COMMANDS)} cmds | {len(VOICE_CORRECTIONS)} corrections | "
            f"{ds['total_dominos']} dominos | {ds['total_triggers']} triggers | "
            f"{len(IMPLICIT_COMMANDS)} implicits | {len(PHONETIC_GROUPS)} phonetics | "
            f"{len(FILLER_WORDS)} fillers | {len(_PYTHON_REGISTRY)} actions"
        )
    except ImportError as e:
        return f"Import error: {e}"


@register_python_action("import_benchmark")
def _import_benchmark() -> str:
    """Benchmark import speed of all voice modules."""
    import time
    start = time.time()
    from src.commands import COMMANDS, VOICE_CORRECTIONS
    from src.voice_correction import IMPLICIT_COMMANDS, PHONETIC_GROUPS, FILLER_WORDS
    from src.domino_pipelines import DOMINO_PIPELINES
    elapsed = time.time() - start
    return f"Import: {elapsed:.3f}s | {len(COMMANDS)} cmds | {len(VOICE_CORRECTIONS)} corr | {len(DOMINO_PIPELINES)} dominos"


@register_python_action("large_files_check")
def _large_files_check() -> str:
    """Find large Python files in the project."""
    import os
    large = []
    src_dir = "/home/turbo/jarvis-m1-ops/src"
    try:
        for f in os.listdir(src_dir):
            if f.endswith(".py"):
                size = os.path.getsize(os.path.join(src_dir, f))
                if size > 50000:
                    large.append(f"{f}: {size // 1024}KB")
    except OSError:
        return "Cannot access src directory"
    return f"{len(large)} large files: {', '.join(large)}" if large else "No large files (>50KB)"


@register_python_action("phonetic_groups_summary")
def _phonetic_groups_summary() -> str:
    """Summary of phonetic groups."""
    try:
        from src.voice_correction import PHONETIC_GROUPS
        total_entries = sum(len(g) for g in PHONETIC_GROUPS)
        avg = total_entries / len(PHONETIC_GROUPS) if PHONETIC_GROUPS else 0
        return f"{len(PHONETIC_GROUPS)} groups, {total_entries} total entries ({avg:.1f} avg per group)"
    except ImportError:
        return "Import error"


@register_python_action("implicit_commands_top")
def _implicit_commands_top() -> str:
    """Show top implicit command categories."""
    try:
        from src.voice_correction import IMPLICIT_COMMANDS
        # Count by first word
        categories: dict[str, int] = {}
        for v in IMPLICIT_COMMANDS.values():
            first_word = v.split()[0] if v else "?"
            categories[first_word] = categories.get(first_word, 0) + 1
        top = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:8]
        return f"{len(IMPLICIT_COMMANDS)} implicits | Top verbs: {', '.join(f'{k}:{v}' for k, v in top)}"
    except ImportError:
        return "Import error"


@register_python_action("filler_words_count")
def _filler_words_count() -> str:
    """Count filler words by category."""
    try:
        from src.voice_correction import FILLER_WORDS
        fr = sum(1 for w in FILLER_WORDS if any(c in w for c in "àéèêîôùç") or w in {"euh", "hum", "bah", "ben", "bon", "alors", "donc", "voila"})
        return f"{len(FILLER_WORDS)} fillers ({fr} French, {len(FILLER_WORDS) - fr} English/other)"
    except ImportError:
        return "Import error"


@register_python_action("list_ollama_models")
def _list_ollama_models() -> str:
    """List Ollama models available."""
    import subprocess
    try:
        r = subprocess.run(['curl', '-s', 'http://127.0.0.1:11434/api/tags'], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5)
        import json
        data = json.loads(r.stdout)
        models = [m["name"] for m in data.get("models", [])]
        return f"{len(models)} models: {', '.join(models[:8])}" if models else "No models"
    except Exception:
        return "Ollama offline"


@register_python_action("list_lm_studio_models")
def _list_lm_studio_models() -> str:
    """List LM Studio loaded models."""
    import subprocess
    try:
        r = subprocess.run(['curl', '-s', 'http://127.0.0.1:1234/api/v1/models'], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5)
        import json
        data = json.loads(r.stdout)
        models = [m.get("id", "?") for m in data.get("data", data.get("models", [])) if m.get("loaded_instances")]
        return f"{len(models)} loaded: {', '.join(models[:5])}" if models else "No models loaded"
    except Exception:
        return "LM Studio offline"


@register_python_action("cluster_node_count")
def _cluster_node_count() -> str:
    """Count active cluster nodes."""
    import subprocess
    active = 0
    nodes = []
    for name, url in [("M1", "http://127.0.0.1:1234/api/v1/models"), ("OL1", "http://127.0.0.1:11434/api/tags"), ("M2", "http://192.168.1.26:1234/api/v1/models"), ("M3", "http://192.168.1.113:1234/api/v1/models")]:
        try:
            r = subprocess.run(["curl", "-s", "--max-time", "3", url], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5)
            if r.returncode == 0 and r.stdout.strip():
                active += 1
                nodes.append(name)
        except Exception:
            pass
    return f"{active}/4 nodes active: {', '.join(nodes)}" if nodes else "All nodes offline"


@register_python_action("voice_corrections_by_category")
def _voice_corrections_by_category() -> str:
    """Count voice corrections by category/vague."""
    try:
        from src.commands import VOICE_CORRECTIONS
        total = len(VOICE_CORRECTIONS)
        multi_word = sum(1 for k in VOICE_CORRECTIONS if " " in k)
        single_word = total - multi_word
        return f"{total} corrections ({single_word} single-word, {multi_word} multi-word)"
    except ImportError:
        return "Import error"


@register_python_action("full_system_summary")
def _full_system_summary() -> str:
    """Complete system summary: project + cluster + memory."""
    parts = []
    try:
        parts.append(_project_summary())
    except Exception:
        parts.append("Project: N/A")
    try:
        parts.append(_cluster_node_count())
    except Exception:
        parts.append("Cluster: N/A")
    try:
        parts.append(_system_memory_usage())
    except Exception:
        parts.append("RAM: N/A")
    try:
        parts.append(_get_disk_usage())
    except Exception:
        parts.append("Disk: N/A")
    return " | ".join(parts)


@register_python_action("git_status_short")
def _git_status_short() -> str:
    """Get git status summary."""
    import subprocess
    try:
        r = subprocess.run(['git', 'status', '--short'], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5, cwd="/home/turbo/jarvis-m1-ops")
        lines = r.stdout.strip().split("\n") if r.stdout.strip() else []
        return f"{len(lines)} files modified" if lines else "Working tree clean"
    except (subprocess.TimeoutExpired, OSError):
        return "Git N/A"


@register_python_action("git_log_today")
def _git_log_today() -> str:
    """Get today's git commits."""
    import subprocess
    try:
        r = subprocess.run(["git", "log", "--oneline", "--since=1 day ago"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5, cwd="/home/turbo/jarvis-m1-ops")
        lines = r.stdout.strip().split("\n") if r.stdout.strip() else []
        return f"{len(lines)} commits today: {'; '.join(lines[:5])}" if lines else "No commits today"
    except (subprocess.TimeoutExpired, OSError):
        return "Git N/A"


@register_python_action("system_memory_usage")
def _system_memory_usage() -> str:
    """Get system memory usage."""
    try:
        import psutil
        mem = psutil.virtual_memory()
        return f"RAM: {mem.used // (1024**3)}GB / {mem.total // (1024**3)}GB ({mem.percent}%)"
    except ImportError:
        import subprocess
        r = subprocess.run('powershell -Command "(Get-CimInstance Win32_OperatingSystem | Select-Object FreePhysicalMemory,TotalVisibleMemorySize | ForEach-Object { /"$([math]::Round(($_.TotalVisibleMemorySize - $_.FreePhysicalMemory)/1MB,1))GB / $([math]::Round($_.TotalVisibleMemorySize/1MB,1))GB/" })"', shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10)
        return f"RAM: {r.stdout.strip()}" if r.stdout.strip() else "RAM info N/A"


@register_python_action("count_domino_categories")
def _count_domino_categories() -> str:
    """Count dominos per category."""
    try:
        from src.domino_pipelines import get_domino_stats
        ds = get_domino_stats()
        cats = sorted(ds["categories"].items(), key=lambda x: x[1], reverse=True)
        return " | ".join(f"{k}:{v}" for k, v in cats[:10])
    except ImportError:
        return "Import error"


@register_python_action("recent_commits")
def _recent_commits() -> str:
    """Get last 5 commit subjects."""
    import subprocess
    try:
        r = subprocess.run(['git', 'log', '--oneline', '-5'], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5, cwd="/home/turbo/jarvis-m1-ops")
        return r.stdout.strip() if r.stdout.strip() else "No commits"
    except (subprocess.TimeoutExpired, OSError):
        return "Git N/A"


@register_python_action("ci_pipeline_count")
def _ci_pipeline_count() -> str:
    """Count GitHub Actions workflows."""
    import subprocess
    try:
        cmd = ['ls', '.github/workflows/*.yml', '2>/dev/null', '|', 'wc', '-l']
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5, cwd="/home/turbo/jarvis-m1-ops")
        count = r.stdout.strip()
        return f"GitHub workflows: {count}"
    except (subprocess.TimeoutExpired, OSError):
        return "Workflows N/A"


@register_python_action("npm_packages_count")
def _npm_packages_count() -> str:
    """Count installed npm packages."""
    import subprocess
    try:
        cmd_list = ['npm', 'list', '--depth=0']
        cmd_count = ['wc', '-l']
        proc = subprocess.Popen(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        output, _ = proc.communicate()
        count = output.decode().strip()
        return f"npm packages: {count}"
    except (subprocess.TimeoutExpired, OSError):
        return "npm N/A"


@register_python_action("proxy_ports_check")
def _proxy_ports_check() -> str:
    """Check common proxy ports."""
    import socket
    ports = {"HTTP": 80, "HTTPS": 443, "Nginx alt": 8080, "LM Studio": 1234, "Ollama": 11434}
    results = []
    for name, port in ports.items():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            result = s.connect_ex(("127.0.0.1", port))
            results.append(f"{name}({port}): {'OPEN' if result == 0 else 'closed'}")
            s.close()
        except OSError:
            results.append(f"{name}({port}): error")
    return " | ".join(results)


@register_python_action("state_mgmt_check")
def _state_mgmt_check() -> str:
    """Check state management libraries in package.json."""
    import json
    try:
        with open("/home/turbo/jarvis-m1-ops/electron/package.json") as f:
            pkg = json.load(f)
        deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        libs = ["redux", "zustand", "mobx", "recoil", "jotai", "pinia", "vuex"]
        found = [l for l in libs if l in deps]
        return f"State mgmt: {', '.join(found) if found else 'none found'}"
    except (FileNotFoundError, json.JSONDecodeError):
        return "package.json N/A"


@register_python_action("voice_system_stats")
def _voice_system_stats() -> str:
    """Get voice system comprehensive stats."""
    try:
        from src.commands import COMMANDS, VOICE_CORRECTIONS
        from src.voice_correction import PHONETIC_GROUPS, FILLER_WORDS, IMPLICIT_COMMANDS
        from src.domino_pipelines import DOMINO_PIPELINES
        cmds = len(COMMANDS)
        corr = len(VOICE_CORRECTIONS)
        doms = len(DOMINO_PIPELINES)
        trigs = sum(len(c.triggers) for c in COMMANDS)
        phon = len(PHONETIC_GROUPS)
        fill = len(FILLER_WORDS)
        impl = len(IMPLICIT_COMMANDS)
        acts = len(_PYTHON_REGISTRY)
        return f"Cmds:{cmds} Corr:{corr} Dom:{doms} Trig:{trigs} Phon:{phon} Fill:{fill} Impl:{impl} Act:{acts} Total:{cmds+corr+doms+trigs+phon+fill+impl+acts}"
    except ImportError:
        return "Voice stats N/A"


@register_python_action("docker_container_count")
def _docker_container_count() -> str:
    """Count running Docker containers."""
    import subprocess
    try:
        r = subprocess.run("docker ps -q 2>/dev/null | wc -l", shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5)
        count = r.stdout.strip()
        return f"Docker containers running: {count}"
    except (subprocess.TimeoutExpired, OSError):
        return "Docker N/A"


@register_python_action("terraform_version")
def _terraform_version() -> str:
    """Get Terraform version."""
    import subprocess
    try:
        r = subprocess.run("terraform version 2>/dev/null | head -1", shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5)
        return r.stdout.strip() if r.stdout.strip() else "Terraform N/A"
    except (subprocess.TimeoutExpired, OSError):
        return "Terraform N/A"


@register_python_action("node_versions")
def _node_versions() -> str:
    """Get Node.js and npm versions."""
    import subprocess
    parts = []
    try:
        r = subprocess.run("node --version", shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5)
        parts.append(f"Node {r.stdout.strip()}")
    except (subprocess.TimeoutExpired, OSError):
        parts.append("Node N/A")
    try:
        r = subprocess.run("npm --version", shell=True, capture_output=True, text=True, timeout=5)
        parts.append(f"npm {r.stdout.strip()}")
    except (subprocess.TimeoutExpired, OSError):
        parts.append("npm N/A")
    return " | ".join(parts)


@register_python_action("queue_status")
def _queue_status() -> str:
    """Check message queue availability."""
    import subprocess
    parts = []
    try:
        r = subprocess.run("redis-cli ping 2>/dev/null", shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3)
        parts.append(f"Redis: {'OK' if 'PONG' in r.stdout else 'N/A'}")
    except (subprocess.TimeoutExpired, OSError):
        parts.append("Redis: N/A")
    try:
        r = subprocess.run("rabbitmqctl status 2>/dev/null | head -1", shell=True, capture_output=True, text=True, timeout=5)
        parts.append(f"RabbitMQ: {'OK' if r.returncode == 0 else 'N/A'}")
    except (subprocess.TimeoutExpired, OSError):
        parts.append("RabbitMQ: N/A")
    return " | ".join(parts)


@register_python_action("build_tools_summary")
def _build_tools_summary() -> str:
    """Summarize available build tools."""
    import subprocess
    tools = {"node": "node --version", "npm": "npm --version", "vite": "npx vite --version 2>/dev/null", "esbuild": "npx esbuild --version 2>/dev/null"}
    parts = []
    for name, cmd in tools.items():
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5)
            ver = r.stdout.strip().split('\n')[0] if r.stdout.strip() else "N/A"
            parts.append(f"{name}: {ver}")
        except (subprocess.TimeoutExpired, OSError):
            parts.append(f"{name}: N/A")
    return " | ".join(parts)


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
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout
    )
    return result.stdout.strip() or result.stderr.strip()


def execute_tool_step(action: str, timeout: int = 30) -> str:
    """Execute a JARVIS IA tool step via WS port 9742.

    Format: "tool:tool_name" or "tool:tool_name:arg1=val1,arg2=val2"
    Examples:
        "tool:jarvis_cluster_health"
        "tool:jarvis_run_task:task_name=zombie_gc"
        "tool:jarvis_boot_status"
    """
    parts = action.replace("tool:", "", 1).split(":", 1) if action.startswith("tool:") else action.split(":", 1)
    tool_name = parts[0].strip()
    args = {}
    if len(parts) > 1 and parts[1].strip():
        for kv in parts[1].split(","):
            if "=" in kv:
                k, v = kv.split("=", 1)
                args[k.strip()] = v.strip()

    try:
        data = json.dumps({"tool_name": tool_name, "arguments": args}).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:9742/api/tools/execute",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode())
        if result.get("ok"):
            out = result.get("result", {})
            return json.dumps(out, ensure_ascii=False, default=str)[:500]
        return f"ERROR: {result.get('error', 'unknown')}"
    except (urllib.error.URLError, OSError, json.JSONDecodeError, ValueError) as e:
        return f"ERROR: {e}"


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
        elif step.action_type == "tool":
            output = execute_tool_step(step.action, step.timeout_s)
            if output.startswith("ERROR:"):
                return "FAIL", output
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


def execute_with_learned_actions(text: str) -> dict | None:
    """Tente un replay learned action. Retourne None si pas de match."""
    match = _learned_engine.match(text)
    if not match:
        return None

    logger.info("Learned action match: %s", match["canonical_name"])
    start = time.time()
    results = []
    for i, step_dict in enumerate(match["pipeline_steps"]):
        command = step_dict["command"]
        if match.get("params"):
            for key, val in match["params"].items():
                command = command.replace(f"{{{key}}}", val)
        domino_step = DominoStep(
            name=step_dict.get("label", f"step_{i}"),
            action=command,
            action_type=step_dict["type"],
            timeout_s=step_dict.get("timeout", 30),
        )
        node = route_step(domino_step)
        status, output = execute_step(domino_step, node)
        results.append({"step": domino_step.name, "status": status, "output": output})
        if status == "FAIL" and step_dict.get("on_fail", "stop") == "stop":
            break

    duration = (time.time() - start) * 1000
    all_passed = all(r["status"] == "PASS" for r in results)
    _learned_engine.record_execution(
        action_id=match["id"],
        trigger_text=text,
        status="success" if all_passed else "failed",
        duration_ms=duration,
        output=str(results[-1]["output"]) if results else "",
    )
    return {"source": "learned_action", "name": match["canonical_name"], "results": results}


# ══════════════════════════════════════════════════════════════════════════════
# DOMINO EXECUTOR — Orchestrateur principal
# ══════════════════════════════════════════════════════════════════════════════

class DominoExecutor:
    """Execute une cascade domino v2 avec retry, context passing, circuit breaker."""

    def __init__(self, db_path: str = _DEFAULT_DB, max_retries: int = 2):
        self.logger = DominoLogger(db_path)
        self.results: list[dict] = []
        self.max_retries = max_retries
        self._context: dict = {}  # Context passed between steps

    def run(self, domino: DominoPipeline, run_id: str | None = None) -> dict:
        """Execute un domino pipeline complet avec retry et context passing."""
        run_id = run_id or f"{domino.id}_{int(time.time())}"
        total_start = time.time()
        passed = failed = skipped = 0
        self._context = {"run_id": run_id, "domino_id": domino.id}

        # Circuit breaker integration
        try:
            from src.circuit_breaker import cluster_breakers
            use_breakers = True
        except ImportError:
            use_breakers = False

        logger.info("DOMINO CASCADE v2: %s (%s) — %s — %d steps, priority=%s",
                    domino.id, domino.category, domino.description, len(domino.steps), domino.priority)

        for idx, step in enumerate(domino.steps):
            step_start = time.time()

            # Evaluate condition with context
            if step.condition and not self._eval_condition(step.condition):
                logger.debug("[%d] %s — CONDITION FALSE: %s", idx + 1, step.name, step.condition)
                skipped += 1
                self.logger.log_step(run_id, domino.id, step.name, idx, "SKIP", 0, "N/A", "condition=false")
                continue

            # Route with circuit breaker awareness
            primary_node = route_step(step)
            node = primary_node

            if use_breakers and not cluster_breakers.can_execute(node):
                fallback = get_fallback_node(node)
                logger.warning("[%d] %s — %s CIRCUIT OPEN, fallback -> %s", idx + 1, step.name, node, fallback)
                node = fallback
            elif not check_node_online(node, timeout=int(config.health_timeout)):
                fallback = get_fallback_node(node)
                logger.warning("[%d] %s — %s OFFLINE, fallback -> %s", idx + 1, step.name, node, fallback)
                node = fallback

            # Execute with retry
            status, output = self._execute_with_retry(step, node, idx)
            duration_ms = (time.time() - step_start) * 1000

            # Record in circuit breaker
            if use_breakers and node not in ("LOCAL",):
                if status == "PASS":
                    cluster_breakers.record_success(node)
                else:
                    cluster_breakers.record_failure(node)

            # Store output in context for next steps
            ctx_key = step.name.replace(" ", "_").lower()
            self._context[ctx_key] = output
            self._context[f"step_{idx}_output"] = output
            self._context[f"step_{idx}_status"] = status

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

            self.logger.log_step(run_id, domino.id, step.name, idx, status, duration_ms, node, output)

        total_ms = (time.time() - total_start) * 1000

        result = {
            "run_id": run_id,
            "domino_id": domino.id,
            "category": domino.category,
            "success": failed == 0,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "total_ms": round(total_ms, 1),
            "total_steps": len(domino.steps),
            "context_keys": list(self._context.keys()),
        }
        self.results.append(result)

        logger.info("RESULTAT: %d PASS / %d FAIL / %d SKIP en %.0fms", passed, failed, skipped, total_ms)
        return result

    def _execute_with_retry(self, step: 'DominoStep', node: str, idx: int) -> tuple[str, str]:
        """Execute a step with retry logic + exponential backoff + orchestrator_v2 routing."""
        last_output = ""
        for attempt in range(self.max_retries + 1):
            # v2: enforce per-step timeout
            t0 = time.time()
            status, output = execute_step(step, node)
            elapsed_s = time.time() - t0
            last_output = output

            # v2: record in orchestrator_v2
            try:
                from src.orchestrator_v2 import orchestrator_v2
                orchestrator_v2.record_call(
                    node, latency_ms=elapsed_s * 1000,
                    success=(status == "PASS"),
                )
            except Exception:
                pass

            if status == "PASS":
                return status, output

            if attempt < self.max_retries:
                # v2: use orchestrator_v2 fallback chain if available
                fallback = node
                try:
                    from src.orchestrator_v2 import orchestrator_v2
                    task_type = "system" if step.action_type == "powershell" else "code"
                    chain = orchestrator_v2.fallback_chain(task_type, exclude={node})
                    if chain:
                        fallback = chain[0]
                except Exception:
                    fallback = get_fallback_node(node)

                if fallback != node:
                    logger.info("[%d] Retry %d/%d — switching %s → %s",
                               idx + 1, attempt + 1, self.max_retries, node, fallback)
                    node = fallback
                else:
                    logger.info("[%d] Retry %d/%d on %s",
                               idx + 1, attempt + 1, self.max_retries, node)
                # v2: exponential backoff (0.5s, 1s, 2s, ...)
                backoff_s = 0.5 * (2 ** attempt)
                time.sleep(min(backoff_s, 8.0))
        return "FAIL", last_output

    def _eval_condition(self, condition: str) -> bool:
        """Evaluate a step condition against the current context.

        v2: supports ==, !=, >, <, >=, <=, exists, contains, and/or logic.
        """
        try:
            # Handle AND/OR logic
            if " and " in condition:
                return all(self._eval_condition(c.strip()) for c in condition.split(" and "))
            if " or " in condition:
                return any(self._eval_condition(c.strip()) for c in condition.split(" or "))

            # Comparison operators (order matters: >= before >, <= before <)
            for op in (">=", "<=", "!=", "==", ">", "<"):
                if op in condition:
                    key, val = condition.split(op, 1)
                    ctx_val = self._context.get(key.strip(), "")
                    val = val.strip()
                    # Try numeric comparison
                    try:
                        num_ctx = float(str(ctx_val))
                        num_val = float(val)
                        if op == "==": return num_ctx == num_val
                        if op == "!=": return num_ctx != num_val
                        if op == ">":  return num_ctx > num_val
                        if op == "<":  return num_ctx < num_val
                        if op == ">=": return num_ctx >= num_val
                        if op == "<=": return num_ctx <= num_val
                    except (ValueError, TypeError):
                        pass
                    # String comparison
                    if op == "==": return str(ctx_val).strip() == val
                    if op == "!=": return str(ctx_val).strip() != val
                    return False

            if "contains" in condition:
                parts = condition.split("contains", 1)
                key = parts[0].strip()
                needle = parts[1].strip().strip("'\"")
                return needle in str(self._context.get(key, ""))

            if "exists" in condition:
                key = condition.replace("exists", "").strip()
                return key in self._context

            return True
        except (ValueError, KeyError):
            return True

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
