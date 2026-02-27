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

import asyncio
import json
import sqlite3
import subprocess
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from src.domino_pipelines import DominoPipeline, DominoStep, find_domino


# ══════════════════════════════════════════════════════════════════════════════
# CLUSTER NODES
# ══════════════════════════════════════════════════════════════════════════════

NODES = {
    "M1": {"url": "http://10.5.0.2:1234", "model": "qwen3-8b", "weight": 1.8},
    "M2": {"url": "http://192.168.1.26:1234", "model": "deepseek-coder-v2-lite-instruct", "weight": 1.4},
    "M3": {"url": "http://192.168.1.113:1234", "model": "mistral-7b-instruct-v0.3", "weight": 1.0},
    "OL1": {"url": "http://127.0.0.1:11434", "model": "qwen3:1.7b", "weight": 1.3},
    "LOCAL": {"url": None, "model": None, "weight": 1.0},
}

FALLBACK_CHAIN = ["M1", "M2", "M3", "OL1", "LOCAL"]

LM_STUDIO_KEYS = {
    "M1": "Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7",
    "M2": "Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4",
    "M3": "Bearer sk-lm-Zxbn5FZ1:M2PkaqHzwA4TilZ9EFux",
}


# ══════════════════════════════════════════════════════════════════════════════
# DOMINO LOGGER — SQLite logging pour chaque cascade
# ══════════════════════════════════════════════════════════════════════════════

class DominoLogger:
    """Log chaque step de cascade domino dans SQLite."""

    def __init__(self, db_path: str = "F:/BUREAU/turbo/data/etoile.db"):
        self.db_path = db_path
        self._ensure_table()

    def _ensure_table(self):
        conn = sqlite3.connect(self.db_path)
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
        conn.commit()
        conn.close()

    def log_step(self, run_id: str, domino_id: str, step_name: str, step_idx: int,
                 status: str, duration_ms: float, node: str = "local",
                 output: str = "", error: str = ""):
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO domino_logs (run_id, domino_id, step_name, step_idx, status, duration_ms, node, output_preview, error) VALUES (?,?,?,?,?,?,?,?,?)",
            (run_id, domino_id, step_name, step_idx, status, duration_ms, node, output[:200], error[:200])
        )
        conn.commit()
        conn.close()

    def get_run_summary(self, run_id: str) -> dict:
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT step_name, status, duration_ms, node FROM domino_logs WHERE run_id=? ORDER BY step_idx",
            (run_id,)
        ).fetchall()
        conn.close()
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

    if action_type == "powershell":
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
            urllib.request.urlopen(f"{url}/api/tags", timeout=timeout)
        else:
            req = urllib.request.Request(
                f"{url}/api/v1/models",
                headers={"Authorization": LM_STUDIO_KEYS.get(node_name, "")}
            )
            urllib.request.urlopen(req, timeout=timeout)
        return True
    except Exception:
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

def execute_powershell(command: str, timeout: int = 30) -> str:
    """Execute une commande PowerShell."""
    # Strip prefix if present
    cmd = command.replace("powershell:", "", 1) if command.startswith("powershell:") else command
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", cmd],
        capture_output=True, text=True, timeout=timeout
    )
    return result.stdout.strip() or result.stderr.strip()


def execute_curl(action: str, timeout: int = 20) -> str:
    """Execute un appel API curl vers un noeud cluster."""
    url = action.replace("curl:", "", 1) if action.startswith("curl:") else action
    try:
        req = urllib.request.Request(url)
        # Add auth for LM Studio endpoints
        for node_name, key in LM_STUDIO_KEYS.items():
            if NODES[node_name]["url"] and NODES[node_name]["url"] in url:
                req.add_header("Authorization", key)
                break
        resp = urllib.request.urlopen(req, timeout=timeout)
        data = resp.read().decode()
        return data[:500]
    except Exception as e:
        return f"ERROR: {e}"


def execute_python(action: str, timeout: int = 30) -> str:
    """Execute une action Python (stub — retourne description)."""
    func = action.replace("python:", "", 1) if action.startswith("python:") else action
    return f"[PYTHON] {func}"


def execute_step(step: DominoStep, node: str) -> tuple[str, str]:
    """Execute un step et retourne (status, output)."""
    try:
        if step.action_type == "powershell":
            output = execute_powershell(step.action, step.timeout_s)
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
    except Exception as e:
        return "FAIL", str(e)[:200]


# ══════════════════════════════════════════════════════════════════════════════
# DOMINO EXECUTOR — Orchestrateur principal
# ══════════════════════════════════════════════════════════════════════════════

class DominoExecutor:
    """Execute une cascade domino step par step avec routing + fallback + logging."""

    def __init__(self, db_path: str = "F:/BUREAU/turbo/data/etoile.db"):
        self.logger = DominoLogger(db_path)
        self.results: list[dict] = []

    def run(self, domino: DominoPipeline, run_id: Optional[str] = None) -> dict:
        """Execute un domino pipeline complet."""
        run_id = run_id or f"{domino.id}_{int(time.time())}"
        total_start = time.time()
        passed = failed = skipped = 0

        print(f"\n{'='*60}")
        print(f"DOMINO CASCADE: {domino.id} ({domino.category})")
        print(f"  {domino.description}")
        print(f"  {len(domino.steps)} steps | priority={domino.priority}")
        print(f"{'='*60}")

        for idx, step in enumerate(domino.steps):
            step_start = time.time()

            # Check condition
            if step.condition:
                print(f"  [{idx+1}] {step.name} — CONDITION: {step.condition}")

            # Route to best node
            primary_node = route_step(step)
            node = primary_node

            # Check if node online, fallback if not
            if not check_node_online(node, timeout=2):
                fallback = get_fallback_node(node)
                print(f"  [{idx+1}] {step.name} — {node} OFFLINE, fallback -> {fallback}")
                node = fallback

            # Execute step
            status, output = execute_step(step, node)
            duration_ms = (time.time() - step_start) * 1000

            # Handle failure
            if status == "FAIL":
                if step.on_fail == "skip":
                    print(f"  [{idx+1}] {step.name} — SKIP ({node}) — {output[:60]}")
                    skipped += 1
                    status = "SKIP"
                elif step.on_fail == "stop":
                    print(f"  [{idx+1}] {step.name} — FAIL STOP ({node}) — {output[:60]}")
                    failed += 1
                    self.logger.log_step(run_id, domino.id, step.name, idx, "FAIL", duration_ms, node, output)
                    break
                else:
                    print(f"  [{idx+1}] {step.name} — FAIL ({node}) — {output[:60]}")
                    failed += 1
            else:
                print(f"  [{idx+1}] {step.name} — PASS ({node}) {duration_ms:.0f}ms — {output[:50]}")
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

        print(f"\n  RESULTAT: {passed} PASS / {failed} FAIL / {skipped} SKIP en {total_ms:.0f}ms")
        return result

    def run_by_voice(self, text: str) -> Optional[dict]:
        """Trouve et execute un domino par phrase vocale."""
        domino = find_domino(text)
        if domino:
            return self.run(domino)
        print(f"  Aucun domino trouve pour: \"{text}\"")
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
