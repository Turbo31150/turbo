#!/usr/bin/env python3
"""JARVIS Auto-Heal Daemon — Boucle persistante de detection/reparation/notification.

Circuit:
  1. Detecte erreurs (health, ports, processes, logs, DB)
  2. Classifie et genere suggestions via M1/OL1
  3. Envoie notification Telegram avec commandes proposees
  4. Execute auto-fix si possible
  5. Verifie le fix
  6. Si OK  → Telegram confirme + commit/branch
  7. Si KO  → Telegram boucle + retry avec strategie differente

Usage:
    python scripts/auto_heal_daemon.py                    # 10000 cycles (defaut)
    python scripts/auto_heal_daemon.py --cycles 0         # Infini
    python scripts/auto_heal_daemon.py --interval 30      # 30s entre cycles
    python scripts/auto_heal_daemon.py --dry-run           # Detecte sans reparer
    python scripts/auto_heal_daemon.py --status             # Etat actuel
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
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Setup paths
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "cowork" / "dev"))

# Load .env
_env = ROOT / ".env"
if _env.exists():
    for _l in _env.read_text(encoding="utf-8", errors="ignore").splitlines():
        _l = _l.strip()
        if _l and not _l.startswith("#") and "=" in _l:
            _k, _, _v = _l.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT", "")

# Cluster config
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

LOG_FILE = ROOT / "logs" / "auto_heal.log"
STATE_FILE = ROOT / "data" / "auto_heal_state.json"
HEAL_DB = ROOT / "data" / "auto_heal.db"

# ANSI
C = {"R": "\033[0m", "G": "\033[92m", "Y": "\033[93m", "r": "\033[91m", "C": "\033[96m", "B": "\033[1m"}

_running = True


def _signal_handler(sig, frame):
    global _running
    _running = False
    print(f"\n{C['Y']}[!!] Arret demande...{C['R']}")


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


# ═══════════════════════════════════════════════════════════════════════════
# Data classes
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class Issue:
    category: str       # "node", "service", "process", "db", "thermal"
    severity: str       # "critical", "warning", "info"
    component: str      # "M1", "jarvis_ws", "etoile.db", etc.
    message: str
    suggestion: str = ""
    fix_cmd: str = ""   # Command to auto-fix
    fix_fn: str = ""    # Python function name for auto-fix
    retries: int = 0
    max_retries: int = 3
    resolved: bool = False


@dataclass
class CycleReport:
    cycle: int
    ts: str
    issues_found: int = 0
    issues_fixed: int = 0
    issues_failed: int = 0
    issues: list[dict] = field(default_factory=list)
    duration_ms: int = 0


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def log(msg: str, level: str = "INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    icon = {"OK": f"{C['G']}[OK]", "INFO": f"{C['C']}[..]", "WARN": f"{C['Y']}[!!]",
            "FAIL": f"{C['r']}[XX]", "HEAL": f"{C['G']}[+]"}.get(level, f"{C['C']}[..]")
    print(f"{icon} {msg}{C['R']}")
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [{level}] {msg}\n")
    except OSError:
        pass


def check_port(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        r = s.connect_ex((host, port))
        s.close()
        return r == 0
    except (socket.error, OSError):
        return False


def http_get(url: str, timeout: float = 5.0, headers: dict | None = None) -> dict | None:
    try:
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def send_telegram(text: str, parse_mode: str = "Markdown") -> bool:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    chunks = [text[i:i + 4000] for i in range(0, len(text), 4000)]
    for chunk in chunks:
        try:
            data = json.dumps({"chat_id": TELEGRAM_CHAT, "text": chunk,
                               "parse_mode": parse_mode}).encode()
            req = urllib.request.Request(url, data, {"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=10)
        except Exception:
            return False
    return True


def ask_m1(prompt: str, max_tokens: int = 512) -> str:
    """Ask M1/qwen3-8b for analysis/suggestions."""
    try:
        body = json.dumps({
            "model": "qwen3-8b", "input": f"/nothink\n{prompt}",
            "temperature": 0.2, "max_output_tokens": max_tokens,
            "stream": False, "store": False,
        }).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:1234/api/v1/chat", body,
            {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            d = json.loads(resp.read().decode())
            for o in reversed(d.get("output", [])):
                if o.get("type") == "message":
                    content = o.get("content", "")
                    if isinstance(content, list):
                        return content[0].get("text", "") if content else ""
                    return str(content)
        return ""
    except Exception:
        return ""


def ask_ol1(prompt: str) -> str:
    """Ask OL1/qwen3:1.7b for quick analysis."""
    try:
        body = json.dumps({
            "model": "qwen3:1.7b",
            "messages": [{"role": "user", "content": f"/nothink\n{prompt}"}],
            "stream": False,
        }).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:11434/api/chat", body,
            {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            d = json.loads(resp.read().decode())
            return d.get("message", {}).get("content", "")
    except Exception:
        return ""


def ask_m2(prompt: str, max_tokens: int = 1024) -> str:
    """Ask M2/deepseek-r1 for deep reasoning analysis (25s, remote)."""
    if not check_port("192.168.1.26", 1234, timeout=3):
        return ""
    try:
        body = json.dumps({
            "model": "deepseek-r1-0528-qwen3-8b", "input": prompt,
            "temperature": 0.3, "max_output_tokens": max_tokens,
            "stream": False, "store": False,
        }).encode()
        req = urllib.request.Request(
            "http://192.168.1.26:1234/api/v1/chat", body,
            {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            d = json.loads(resp.read().decode())
            for o in reversed(d.get("output", [])):
                if o.get("type") == "message":
                    content = o.get("content", "")
                    if isinstance(content, list):
                        return content[0].get("text", "") if content else ""
                    return str(content)
        return ""
    except Exception:
        return ""


def multi_pipeline_dispatch(issues: list[Issue]) -> dict[str, Any]:
    """Multi-pipeline agent dispatch: M1 rapide + OL1 parallele, M2 escalade.

    Pipeline:
      1. OL1 (0.5s) — triage rapide: classifie severity + suggestion courte
      2. M1 (1s) — analyse + commandes fix concretes
      3. M2 (25s) — SEULEMENT si issue persistante (retries >= 2) ou critique sans fix
      4. Consensus — si M1 et OL1 divergent, M2 tranche

    Returns dict with per-issue results and agent attributions.
    """
    results: dict[str, Any] = {"pipeline": [], "agents_used": set()}

    if not issues:
        return results

    # ── Pipeline 1: OL1 triage rapide ──
    ol1_available = check_port("127.0.0.1", 11434)
    m1_available = check_port("127.0.0.1", 1234)

    for issue in issues:
        entry: dict[str, Any] = {
            "component": issue.component,
            "severity": issue.severity,
            "agents": [],
        }

        # OL1: triage rapide
        if ol1_available:
            ol1_prompt = (
                f"Erreur JARVIS: [{issue.category}] {issue.component}: {issue.message}\n"
                f"Donne en 2 lignes max: 1) cause probable 2) commande fix Windows"
            )
            ol1_resp = ask_ol1(ol1_prompt)
            if ol1_resp:
                entry["agents"].append({"agent": "OL1", "response": ol1_resp[:300]})
                results["agents_used"].add("OL1")
                if not issue.suggestion:
                    issue.suggestion = f"[OL1] {ol1_resp[:200]}"

        # M1: analyse + fix concret
        if m1_available:
            m1_prompt = (
                f"Tu es JARVIS sys-admin. Erreur: [{issue.category}] {issue.component}: {issue.message}\n"
                f"Retries: {issue.retries}/{issue.max_retries}\n"
                f"Donne: 1) Diagnostic 2) Commande fix exacte (Windows/bash) 3) Verification"
            )
            m1_resp = ask_m1(m1_prompt, max_tokens=400)
            if m1_resp:
                entry["agents"].append({"agent": "M1", "response": m1_resp[:400]})
                results["agents_used"].add("M1")
                # M1 overrides OL1 suggestion (higher quality)
                issue.suggestion = f"[M1] {m1_resp[:200]}"
                # Extract fix command if present
                for line in m1_resp.split("\n"):
                    stripped = line.strip().strip("`")
                    if stripped and any(stripped.startswith(c) for c in [
                        "taskkill", "ollama", "lms", "curl", "python", "node",
                        "npm", "uv ", "net ", "sc ", "start ",
                    ]):
                        if not issue.fix_cmd:
                            issue.fix_cmd = stripped
                            break

        # M2: escalade pour issues persistantes ou critiques sans fix
        if issue.retries >= 2 or (issue.severity == "critical" and not issue.fix_cmd):
            m2_resp = ask_m2(
                f"Analyse APPROFONDIE erreur persistante JARVIS (echec {issue.retries}x):\n"
                f"[{issue.category}] {issue.component}: {issue.message}\n"
                f"Suggestions precedentes: {issue.suggestion}\n"
                f"Propose une strategie ALTERNATIVE de reparation avec commandes exactes."
            )
            if m2_resp:
                entry["agents"].append({"agent": "M2", "response": m2_resp[:500]})
                results["agents_used"].add("M2")
                issue.suggestion = f"[M2 reasoning] {m2_resp[:250]}"
                for line in m2_resp.split("\n"):
                    stripped = line.strip().strip("`")
                    if stripped and any(stripped.startswith(c) for c in [
                        "taskkill", "ollama", "lms", "curl", "python", "node",
                    ]):
                        issue.fix_cmd = stripped
                        break

        entry["final_suggestion"] = issue.suggestion
        entry["fix_cmd"] = issue.fix_cmd
        results["pipeline"].append(entry)

    results["agents_used"] = list(results["agents_used"])
    return results


# ═══════════════════════════════════════════════════════════════════════════
# Detection pipeline
# ═══════════════════════════════════════════════════════════════════════════

def detect_node_issues() -> list[Issue]:
    """Check all cluster nodes."""
    issues = []
    for name, cfg in NODES.items():
        if not check_port(cfg["ip"], cfg["port"]):
            # Remote nodes (M2, M3): info only (not actionable locally)
            if name in ("M2", "M3"):
                sev = "info"
            elif name == "M1":
                sev = "critical"
            else:
                sev = "warning"
            fix = ""
            if name == "M1":
                fix = "lms server start"
            elif name == "OL1":
                fix = "ollama serve"
            issues.append(Issue(
                "node", sev, name,
                f"{name} ({cfg['ip']}:{cfg['port']}) OFFLINE",
                f"Redemarrer {name}" + (f": {fix}" if fix else " (distant, verifier manuellement)"),
                fix_cmd=fix,
            ))
        elif name == "M1":
            # Check if qwen3-8b is loaded
            data = http_get(f"{cfg['url']}/api/v1/models")
            if data:
                # lms ps is more reliable than API for loaded check
                try:
                    r = subprocess.run(
                        [str(Path.home() / ".lmstudio" / "bin" / "lms.exe"), "ps"],
                        capture_output=True, timeout=10, encoding="utf-8", errors="replace",
                    )
                    import re
                    output = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]|\[\?25[hl]", "", r.stdout + r.stderr)
                    if "qwen3-8b" not in output:
                        issues.append(Issue(
                            "node", "critical", "M1",
                            "M1 actif mais qwen3-8b PAS charge",
                            "Charger le modele: lms load qwen/qwen3-8b --gpu max -c 28813 --parallel 4 -y",
                            fix_cmd="lms load qwen/qwen3-8b --gpu max -c 28813 --parallel 4 -y",
                        ))
                except Exception:
                    pass
    return issues


def detect_service_issues() -> list[Issue]:
    """Check all services by port."""
    issues = []
    uv = str(Path.home() / ".local" / "bin" / "uv.exe")
    for name, cfg in SERVICES.items():
        if not check_port("127.0.0.1", cfg["port"]):
            sev = "critical" if cfg.get("critical") else "warning"
            issues.append(Issue(
                "service", sev, name,
                f"Service {name} OFFLINE (:{cfg['port']})",
                f"Relancer {name} via singleton",
                fix_fn=f"fix_service_{name}",
            ))
    return issues


def detect_thermal_issues() -> list[Issue]:
    """Check GPU temperatures."""
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
                        f"GPU{parts[0]} {parts[1]} a {temp}C — CRITIQUE",
                        "Reduire charge M1, deporter vers M2/OL1",
                    ))
                elif temp >= 75:
                    issues.append(Issue(
                        "thermal", "warning", f"GPU{parts[0]}",
                        f"GPU{parts[0]} {parts[1]} a {temp}C — warning",
                        "Surveiller, reduire contexte modele si necessaire",
                    ))
    except Exception:
        pass
    return issues


def detect_db_issues() -> list[Issue]:
    """Check SQLite database integrity."""
    issues = []
    dbs = {
        "etoile": ROOT / "data" / "etoile.db",
        "jarvis": ROOT / "data" / "jarvis.db",
    }
    for name, path in dbs.items():
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
                    "PRAGMA recover ou restaurer depuis backup",
                ))
        except sqlite3.Error as e:
            issues.append(Issue("db", "warning", name, f"Erreur DB {name}: {e}"))
    return issues


def detect_process_doublons() -> list[Issue]:
    """Detect duplicate processes."""
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

        # Group by script name — only count real python.exe processes
        scripts: dict[str, list[int]] = {}
        for p in procs:
            cmd = p.get("CommandLine", "") or ""
            pid = p.get("ProcessId", 0)
            # Only match processes whose CommandLine starts with python/uv
            # Skip bash shells, wmic, grep, etc. that match on substring
            cmd_lower = cmd.lower().strip().strip('"')
            is_python = (cmd_lower.startswith("python") or
                         cmd_lower.startswith("c:\\") and "python" in cmd_lower.split("\\")[-1].lower())
            if not is_python:
                continue
            if "server.py" in cmd and "python_ws" in cmd:
                scripts.setdefault("python_ws/server.py", []).append(pid)

        for script, pids in scripts.items():
            if len(pids) > 1:
                issues.append(Issue(
                    "process", "warning", script,
                    f"Doublon detecte: {script} ({len(pids)} instances: {pids})",
                    f"Tuer les doublons sauf le plus recent",
                    fix_fn="fix_doublon",
                ))
    except Exception:
        pass
    return issues


# ═══════════════════════════════════════════════════════════════════════════
# Fix pipeline
# ═══════════════════════════════════════════════════════════════════════════

def attempt_fix(issue: Issue, dry_run: bool = False) -> bool:
    """Try to auto-fix an issue. Returns True if fixed."""
    if dry_run:
        log(f"  [DRY-RUN] Fix: {issue.suggestion}", "INFO")
        return False

    # Fix via shell command
    if issue.fix_cmd:
        log(f"  Executing: {issue.fix_cmd}", "HEAL")
        try:
            lms = str(Path.home() / ".lmstudio" / "bin" / "lms.exe")
            cmd = issue.fix_cmd
            if cmd.startswith("lms "):
                cmd = cmd.replace("lms ", f"{lms} ", 1)
            r = subprocess.run(
                cmd, shell=True, capture_output=True, timeout=180,
                encoding="utf-8", errors="replace",
            )
            return r.returncode == 0
        except Exception as e:
            log(f"  Fix failed: {e}", "FAIL")
            return False

    # Fix via service restart (singleton)
    if issue.fix_fn and issue.fix_fn.startswith("fix_service_"):
        svc = issue.fix_fn.replace("fix_service_", "")
        return restart_service(svc)

    # Fix doublons: kill older PIDs, keep newest
    if issue.fix_fn == "fix_doublon":
        try:
            # Extract PIDs from message like "3 instances: [1234, 5678, 9012]"
            import re
            m = re.search(r'\[([0-9, ]+)\]', issue.message)
            if m:
                pids = sorted(int(p.strip()) for p in m.group(1).split(","))
                # Keep the newest (highest PID), kill the rest
                for old_pid in pids[:-1]:
                    subprocess.run(["taskkill", "/PID", str(old_pid), "/F"],
                                   capture_output=True, timeout=10)
                    log(f"  Killed doublon PID {old_pid}", "HEAL")
                return True
        except Exception as e:
            log(f"  Fix doublon failed: {e}", "FAIL")
        return False

    return False


def restart_service(name: str) -> bool:
    """Restart a service using singleton anti-doublon."""
    try:
        from src.process_singleton import singleton
        port = SERVICES.get(name, {}).get("port")
        if port:
            singleton.acquire(name, pid=0, port=port)
            time.sleep(1)

        uv = str(Path.home() / ".local" / "bin" / "uv.exe")
        cmds = {
            "dashboard": [uv, "run", "python", str(ROOT / "dashboard" / "server.py")],
            "jarvis_ws": [uv, "run", "python", str(ROOT / "python_ws" / "server.py")],
            "canvas_proxy": ["node", str(ROOT / "canvas" / "direct-proxy.js")],
            "gemini_proxy": ["node", str(ROOT / "gemini-proxy.js")],
            "mcp_sse": [uv, "run", "python", "-m", "src.mcp_server_sse", "--port", "8901"],
        }
        cmd = cmds.get(name)
        if not cmd:
            return False

        log(f"  Relance {name}...", "HEAL")
        kwargs: dict[str, Any] = {
            "cwd": str(ROOT),
            "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL,
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = (
                subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
                | subprocess.CREATE_NO_WINDOW
            )
        proc = subprocess.Popen(cmd, **kwargs)
        if port:
            singleton.register(name, proc.pid)

        # Wait for port
        for _ in range(15):
            if check_port("127.0.0.1", port):
                log(f"  {name}: relance OK (PID {proc.pid})", "OK")
                return True
            time.sleep(1)

        log(f"  {name}: port {port} pas ouvert apres 15s", "FAIL")
        return False
    except Exception as e:
        log(f"  {name}: erreur relance: {e}", "FAIL")
        return False


# ═══════════════════════════════════════════════════════════════════════════
# Telegram notification
# ═══════════════════════════════════════════════════════════════════════════

def notify_issues(issues: list[Issue], cycle: int) -> None:
    """Send issues to Telegram with suggestions."""
    if not issues:
        return

    critical = [i for i in issues if i.severity == "critical"]
    warnings = [i for i in issues if i.severity == "warning"]

    lines = [f"*JARVIS Auto-Heal — Cycle {cycle}*"]
    lines.append(f"Detecte: {len(critical)} critiques, {len(warnings)} warnings")
    lines.append("")

    for i in issues:
        icon = "🔴" if i.severity == "critical" else "🟡"
        lines.append(f"{icon} *{i.component}*: {i.message}")
        if i.suggestion:
            # Show agent attribution
            lines.append(f"   💡 {i.suggestion[:200]}")
        if i.fix_cmd:
            lines.append(f"   🔧 `{i.fix_cmd}`")
        if i.retries >= 2:
            lines.append(f"   ⚠️ Persistant ({i.retries}x) — escalade M2")
        lines.append("")

    send_telegram("\n".join(lines))


def notify_fixes(fixed: list[Issue], failed: list[Issue], cycle: int) -> None:
    """Report fix results to Telegram."""
    lines = [f"*JARVIS Auto-Heal — Resultats Cycle {cycle}*"]

    if fixed:
        lines.append(f"\n✅ *{len(fixed)} repares:*")
        for i in fixed:
            lines.append(f"  • {i.component}: {i.message}")

    if failed:
        lines.append(f"\n❌ *{len(failed)} echecs (retry {failed[0].retries}/{failed[0].max_retries}):*")
        for i in failed:
            lines.append(f"  • {i.component}: {i.message}")
            if i.suggestion:
                lines.append(f"    >{i.suggestion}")

    if not fixed and not failed:
        lines.append("\n✅ Aucun probleme detecte — cluster sain")

    send_telegram("\n".join(lines))


# ═══════════════════════════════════════════════════════════════════════════
# AI-enhanced analysis
# ═══════════════════════════════════════════════════════════════════════════

def ai_analyze_issues(issues: list[Issue]) -> None:
    """Multi-pipeline AI analysis: OL1 triage + M1 fix + M2 escalade."""
    if not issues:
        return

    # Filter issues worth analyzing
    analyzable = [i for i in issues if i.severity in ("critical", "warning") and not i.suggestion]
    if not analyzable:
        return

    result = multi_pipeline_dispatch(analyzable)
    agents = ", ".join(result.get("agents_used", [])) or "none"
    log(f"  Multi-pipeline: {len(analyzable)} issues -> agents [{agents}]", "INFO")


# ═══════════════════════════════════════════════════════════════════════════
# State persistence
# ═══════════════════════════════════════════════════════════════════════════

def init_db():
    """Initialize auto_heal SQLite database."""
    HEAL_DB.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(HEAL_DB))
    db.execute("""CREATE TABLE IF NOT EXISTS heal_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT, cycle INTEGER,
        issues_found INTEGER, issues_fixed INTEGER, issues_failed INTEGER,
        duration_ms INTEGER, details TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS persistent_issues (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        component TEXT UNIQUE, category TEXT, severity TEXT,
        message TEXT, retries INTEGER DEFAULT 0,
        first_seen TEXT, last_seen TEXT
    )""")
    db.commit()
    db.close()


def save_cycle(report: CycleReport):
    """Log cycle results to DB."""
    try:
        db = sqlite3.connect(str(HEAL_DB))
        db.execute(
            "INSERT INTO heal_log (ts, cycle, issues_found, issues_fixed, issues_failed, duration_ms, details) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (report.ts, report.cycle, report.issues_found, report.issues_fixed,
             report.issues_failed, report.duration_ms, json.dumps(report.issues, default=str)),
        )
        db.commit()
        db.close()
    except Exception:
        pass


def track_persistent(issue: Issue):
    """Track issues that persist across cycles."""
    try:
        db = sqlite3.connect(str(HEAL_DB))
        now = datetime.now().isoformat()
        db.execute("""INSERT INTO persistent_issues (component, category, severity, message, retries, first_seen, last_seen)
            VALUES (?, ?, ?, ?, 1, ?, ?)
            ON CONFLICT(component) DO UPDATE SET
                retries = retries + 1, last_seen = ?, message = ?, severity = ?""",
            (issue.component, issue.category, issue.severity, issue.message, now, now,
             now, issue.message, issue.severity))
        db.commit()
        db.close()
    except Exception:
        pass


def clear_resolved(component: str):
    """Remove a resolved issue from persistent tracking."""
    try:
        db = sqlite3.connect(str(HEAL_DB))
        db.execute("DELETE FROM persistent_issues WHERE component = ?", (component,))
        db.commit()
        db.close()
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════
# Main cycle
# ═══════════════════════════════════════════════════════════════════════════

def run_cycle(cycle: int, dry_run: bool = False, notify: bool = True) -> CycleReport:
    """Execute one detection-fix-verify cycle."""
    t0 = time.time()
    report = CycleReport(cycle=cycle, ts=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    # ── Step 1: Detect ──
    all_issues: list[Issue] = []
    all_issues.extend(detect_node_issues())
    all_issues.extend(detect_service_issues())
    all_issues.extend(detect_thermal_issues())
    all_issues.extend(detect_db_issues())
    all_issues.extend(detect_process_doublons())

    report.issues_found = len(all_issues)

    if not all_issues:
        report.duration_ms = int((time.time() - t0) * 1000)
        if cycle % 100 == 0:
            log(f"Cycle {cycle}: cluster sain ({report.duration_ms}ms)", "OK")
        if cycle % 500 == 0 and notify:
            notify_fixes([], [], cycle)
        save_cycle(report)
        return report

    # ── Step 2: AI analysis for critical issues ──
    ai_analyze_issues(all_issues)

    # ── Step 3: Notify Telegram ──
    if notify:
        notify_issues(all_issues, cycle)

    # ── Step 4: Attempt fixes ──
    fixed: list[Issue] = []
    failed: list[Issue] = []

    for issue in all_issues:
        if issue.severity == "info":
            continue

        log(f"Cycle {cycle}: [{issue.severity}] {issue.component} — {issue.message}", "WARN")

        if issue.fix_cmd or issue.fix_fn:
            ok = attempt_fix(issue, dry_run)
            if ok:
                issue.resolved = True
                fixed.append(issue)
                clear_resolved(issue.component)
                log(f"  -> REPARE: {issue.component}", "OK")
            else:
                issue.retries += 1
                failed.append(issue)
                track_persistent(issue)
                log(f"  -> ECHEC ({issue.retries}/{issue.max_retries}): {issue.component}", "FAIL")
        else:
            # No auto-fix available, just track
            track_persistent(issue)
            failed.append(issue)

    # ── Step 5: Notify results ──
    if notify and (fixed or failed):
        notify_fixes(fixed, failed, cycle)

    report.issues_fixed = len(fixed)
    report.issues_failed = len(failed)
    report.issues = [{"component": i.component, "severity": i.severity,
                       "message": i.message, "resolved": i.resolved} for i in all_issues]
    report.duration_ms = int((time.time() - t0) * 1000)

    save_cycle(report)
    return report


# ═══════════════════════════════════════════════════════════════════════════
# Status
# ═══════════════════════════════════════════════════════════════════════════

def show_status():
    """Show current auto-heal status."""
    print(f"\n{C['B']}{C['C']}{'='*55}")
    print("  JARVIS Auto-Heal — Status")
    print(f"{'='*55}{C['R']}\n")

    # Persistent issues
    try:
        db = sqlite3.connect(str(HEAL_DB))
        rows = db.execute("SELECT component, severity, message, retries, first_seen, last_seen "
                          "FROM persistent_issues ORDER BY severity, retries DESC").fetchall()
        db.close()
        if rows:
            print(f"  {C['Y']}Problemes persistants: {len(rows)}{C['R']}")
            for comp, sev, msg, retries, first, last in rows:
                icon = "[!!]" if sev == "critical" else "[??]"
                print(f"    {icon} {comp}: {msg} (retries={retries})")
        else:
            print(f"  {C['G']}Aucun probleme persistant{C['R']}")
    except Exception:
        print("  [pas de DB auto_heal]")

    # Recent cycles
    try:
        db = sqlite3.connect(str(HEAL_DB))
        rows = db.execute("SELECT cycle, ts, issues_found, issues_fixed, issues_failed, duration_ms "
                          "FROM heal_log ORDER BY id DESC LIMIT 10").fetchall()
        db.close()
        if rows:
            print(f"\n  Derniers cycles:")
            for cycle, ts, found, fixed, fail, ms in rows:
                icon = "[OK]" if fail == 0 else "[XX]"
                print(f"    {icon} Cycle {cycle} ({ts}): {found} detectes, {fixed} repares, {fail} echecs ({ms}ms)")
    except Exception:
        pass

    print()


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="JARVIS Auto-Heal Daemon")
    parser.add_argument("--cycles", type=int, default=10000, help="Nombre de cycles (0=infini)")
    parser.add_argument("--interval", type=int, default=30, help="Secondes entre cycles")
    parser.add_argument("--dry-run", action="store_true", help="Detecte sans reparer")
    parser.add_argument("--status", action="store_true", help="Affiche le statut actuel")
    parser.add_argument("--no-telegram", action="store_true", help="Desactive Telegram")
    parser.add_argument("--quiet", action="store_true", help="Log minimal (seulement les erreurs)")
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    # Singleton: kill existing heal daemon before starting
    try:
        from src.process_singleton import singleton
        singleton.acquire("auto_heal_daemon", pid=0)
        singleton.register("auto_heal_daemon", os.getpid())
    except Exception:
        pass

    # Init
    init_db()

    max_cycles = args.cycles if args.cycles > 0 else float("inf")
    notify = not args.no_telegram

    print(f"\n{C['B']}{C['C']}{'='*55}")
    print(f"  JARVIS Auto-Heal Daemon")
    print(f"  Cycles: {args.cycles if args.cycles > 0 else 'INFINI'} | Interval: {args.interval}s")
    print(f"  Telegram: {'ON' if notify and TELEGRAM_TOKEN else 'OFF'}")
    print(f"  Mode: {'DRY-RUN' if args.dry_run else 'ACTIF'}")
    print(f"{'='*55}{C['R']}\n")

    if notify and TELEGRAM_TOKEN:
        send_telegram(
            f"*JARVIS Auto-Heal ACTIVE*\n"
            f"Cycles: {args.cycles if args.cycles > 0 else 'INFINI'}\n"
            f"Interval: {args.interval}s\n"
            f"Mode: {'DRY-RUN' if args.dry_run else 'ACTIF'}"
        )

    cycle = 0
    consecutive_clean = 0

    while _running and cycle < max_cycles:
        cycle += 1

        report = run_cycle(cycle, args.dry_run, notify)

        if report.issues_found == 0:
            consecutive_clean += 1
        else:
            consecutive_clean = 0

        # Adaptive interval: slow down when cluster is healthy
        if consecutive_clean >= 10:
            interval = min(args.interval * 2, 120)
        elif consecutive_clean >= 50:
            interval = min(args.interval * 3, 300)
        else:
            interval = args.interval

        # Sleep with interrupt check
        for _ in range(interval):
            if not _running:
                break
            time.sleep(1)

    # Shutdown
    log(f"Auto-Heal arrete apres {cycle} cycles", "INFO")
    if notify and TELEGRAM_TOKEN:
        send_telegram(f"*JARVIS Auto-Heal ARRETE* apres {cycle} cycles")


if __name__ == "__main__":
    main()
