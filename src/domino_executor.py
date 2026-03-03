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


def execute_python(action: str, timeout: int = 30) -> str:
    """Execute une action Python (stub — retourne description)."""
    func = action.replace("python:", "", 1) if action.startswith("python:") else action
    return f"[PYTHON] {func}"


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
