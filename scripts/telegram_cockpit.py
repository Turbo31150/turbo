#!/usr/bin/env python3
"""telegram_cockpit.py — JARVIS Telegram Cockpit for Cluster Operations.

Central module for pushing cluster intelligence to Telegram and
receiving commands back. Used by orchestrator tasks and standalone.

Features:
- Send formatted reports (cluster health, entropy, evolution, alerts)
- Dispatch questions to cluster via Telegram
- Voice note support (Edge TTS → send audio)
- Rate-limited (max 20 msgs/min)

Usage:
    python scripts/telegram_cockpit.py --report cluster
    python scripts/telegram_cockpit.py --report evolution
    python scripts/telegram_cockpit.py --report full
    python scripts/telegram_cockpit.py --send "Custom message"
    python scripts/telegram_cockpit.py --ask "Question for cluster"
    python scripts/telegram_cockpit.py --voice "Text to speak"
    python scripts/telegram_cockpit.py --alerts
"""

import argparse
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────
TURBO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TURBO_DIR / "cowork" / "dev"))

# Load .env
env_file = TURBO_DIR / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT", "")
ORCH_DB = str(TURBO_DIR / "data" / "task_orchestrator.db")
MAX_MSG = 4096
RATE_LIMIT = 20  # msgs/min
_send_times: list[float] = []


# ── Telegram API ────────────────────────────────────────────────────────

def _rate_ok() -> bool:
    now = time.time()
    _send_times[:] = [t for t in _send_times if now - t < 60]
    return len(_send_times) < RATE_LIMIT


def send(text: str, parse_mode: str = "Markdown") -> bool:
    """Send a message to Telegram. Returns True on success."""
    if not TOKEN or not CHAT_ID:
        print(f"[COCKPIT] No token/chat: {text[:80]}")
        return False
    if not _rate_ok():
        print("[COCKPIT] Rate limited")
        return False

    # Split long messages
    chunks = []
    while text:
        if len(text) <= MAX_MSG:
            chunks.append(text)
            break
        cut = text.rfind("\n", 0, MAX_MSG)
        if cut < MAX_MSG * 0.3:
            cut = MAX_MSG
        chunks.append(text[:cut])
        text = text[cut:].lstrip()

    ok = True
    for chunk in chunks:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = json.dumps({"chat_id": CHAT_ID, "text": chunk, "parse_mode": parse_mode}).encode()
        try:
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=10)
            _send_times.append(time.time())
        except Exception:
            # Retry without parse_mode
            try:
                payload = json.dumps({"chat_id": CHAT_ID, "text": chunk}).encode()
                req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
                urllib.request.urlopen(req, timeout=10)
                _send_times.append(time.time())
            except Exception as e:
                print(f"[COCKPIT] Send failed: {e}")
                ok = False
    return ok


def send_voice(text: str) -> bool:
    """Generate TTS audio and send as voice note to Telegram."""
    if not TOKEN or not CHAT_ID:
        return False
    try:
        # Generate audio via Edge TTS
        audio_path = TURBO_DIR / "data" / "tmp" / "cockpit_voice.mp3"
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([
            sys.executable, "-m", "edge_tts",
            "--voice", "fr-FR-DeniseNeural",
            "--text", text[:500],
            "--write-media", str(audio_path)
        ], capture_output=True, timeout=15)

        if not audio_path.exists():
            return False

        # Send via Telegram sendVoice
        url = f"https://api.telegram.org/bot{TOKEN}/sendVoice"
        import io
        boundary = "----JARVISVoiceBoundary"
        body = b""
        body += f"--{boundary}\r\n".encode()
        body += f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{CHAT_ID}\r\n'.encode()
        body += f"--{boundary}\r\n".encode()
        body += f'Content-Disposition: form-data; name="voice"; filename="voice.mp3"\r\n'.encode()
        body += b'Content-Type: audio/mpeg\r\n\r\n'
        body += audio_path.read_bytes()
        body += f"\r\n--{boundary}--\r\n".encode()

        req = urllib.request.Request(url, data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        urllib.request.urlopen(req, timeout=15)
        audio_path.unlink(missing_ok=True)
        return True
    except Exception as e:
        print(f"[COCKPIT] Voice send failed: {e}")
        return False


# ── Cluster Helpers ─────────────────────────────────────────────────────

def check_port(host: str, port: int, timeout: float = 2) -> bool:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        result = s.connect_ex((host, port)) == 0
        s.close()
        return result
    except Exception:
        return False


def ask_m1(prompt: str, max_tokens: int = 300) -> str:
    """Ask M1 a question and return the answer."""
    try:
        data = json.dumps({
            "model": "qwen3-8b",
            "input": f"/nothink\n{prompt}",
            "temperature": 0.3,
            "max_output_tokens": max_tokens,
            "stream": False, "store": False,
        }).encode()
        req = urllib.request.Request("http://127.0.0.1:1234/api/v1/chat",
            data=data, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=15)
        body = json.loads(resp.read())
        for b in body.get("output", []):
            if b.get("type") == "message":
                c = b.get("content", "")
                return c.strip() if isinstance(c, str) else ""
        return ""
    except Exception as e:
        return f"[M1 error: {e}]"


def ask_ol1(prompt: str) -> str:
    """Ask OL1 a question."""
    try:
        data = json.dumps({
            "model": "qwen3:1.7b",
            "messages": [{"role": "user", "content": f"/nothink\n{prompt}"}],
            "stream": False,
        }).encode()
        req = urllib.request.Request("http://127.0.0.1:11434/api/chat",
            data=data, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=10)
        body = json.loads(resp.read())
        return body.get("message", {}).get("content", "").strip()
    except Exception as e:
        return f"[OL1 error: {e}]"


# ── Report Generators ───────────────────────────────────────────────────

def report_cluster() -> str:
    """Generate cluster health report."""
    lines = ["*JARVIS Cluster Status*", f"_{datetime.now().strftime('%d/%m %H:%M')}_\n"]

    nodes = [
        ("M1", "127.0.0.1", 1234, "qwen3-8b"),
        ("OL1", "127.0.0.1", 11434, "qwen3:1.7b"),
        ("M3", "192.168.1.113", 1234, "deepseek-r1"),
        ("WS", "127.0.0.1", 9742, "FastAPI"),
        ("OpenClaw", "127.0.0.1", 18789, "Gateway"),
        ("Proxy", "127.0.0.1", 18800, "Canvas"),
    ]

    online = 0
    for name, host, port, model in nodes:
        alive = check_port(host, port)
        icon = "+" if alive else "x"
        if alive:
            online += 1
        lines.append(f"  [{icon}] {name}: {model}")

    lines.append(f"\n*Mesh*: {online}/{len(nodes)} services")

    # Disk
    for drive in ["C:", "F:"]:
        try:
            u = shutil.disk_usage(drive + "/")
            free = u.free / 1e9
            lines.append(f"  {drive} {free:.0f}GB free")
        except Exception:
            pass

    return "\n".join(lines)


def report_evolution() -> str:
    """Generate evolution/orchestrator report."""
    lines = ["*JARVIS Evolution Report*", f"_{datetime.now().strftime('%d/%m %H:%M')}_\n"]

    try:
        db = sqlite3.connect(ORCH_DB)
        active = db.execute("SELECT COUNT(*) FROM tasks WHERE enabled=1").fetchone()[0]
        total_runs = db.execute("SELECT COUNT(*) FROM task_runs").fetchone()[0]

        # Success rate
        r = db.execute("""
            SELECT COUNT(*), SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END)
            FROM task_runs WHERE started_at > datetime('now', '-1 hour')
        """).fetchone()
        runs_1h, ok_1h = r[0] or 0, r[1] or 0
        rate = (ok_1h / runs_1h * 100) if runs_1h > 0 else 0

        # Entropy
        entropy = db.execute(
            "SELECT metric_value FROM task_metrics WHERE metric_name='system_entropy_score' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        entropy_val = entropy[0] if entropy else -1

        # Top failures
        top_fail = db.execute("""
            SELECT task_id, COUNT(*) as c FROM task_runs
            WHERE status='failed' AND started_at > datetime('now', '-1 hour')
            GROUP BY task_id ORDER BY c DESC LIMIT 5
        """).fetchall()

        lines.append(f"*Tasks*: {active} active")
        lines.append(f"*Runs*: {total_runs} total, {runs_1h}/h")
        lines.append(f"*Success*: {rate:.0f}%")
        lines.append(f"*Entropy*: {entropy_val:.0f}/100")

        if top_fail:
            lines.append("\n*Top failures (1h):*")
            for tid, count in top_fail:
                lines.append(f"  - {tid}: {count}x")

        db.close()
    except Exception as e:
        lines.append(f"DB error: {e}")

    return "\n".join(lines)


def report_alerts() -> str:
    """Generate active alerts report."""
    lines = ["*JARVIS Alerts*", f"_{datetime.now().strftime('%d/%m %H:%M')}_\n"]
    alerts = []

    # Check services
    critical_services = [("M1", "127.0.0.1", 1234), ("OL1", "127.0.0.1", 11434),
                         ("WS", "127.0.0.1", 9742)]
    for name, host, port in critical_services:
        if not check_port(host, port):
            alerts.append(f"[x] {name} DOWN (port {port})")

    # Check entropy
    try:
        db = sqlite3.connect(ORCH_DB)
        e = db.execute("SELECT metric_value FROM task_metrics WHERE metric_name='system_entropy_score' ORDER BY id DESC LIMIT 1").fetchone()
        if e and e[0] < 60:
            alerts.append(f"[!] Entropy LOW: {e[0]:.0f}/100")

        # Circuit breakers
        tripped = db.execute("SELECT task_id FROM task_escalation WHERE consecutive_fails >= 5").fetchall()
        if tripped:
            alerts.append(f"[!] {len(tripped)} circuit breakers tripped")

        # Disk
        for drive in ["C:", "F:"]:
            free = shutil.disk_usage(drive + "/").free / 1e9
            if free < 20:
                alerts.append(f"[!] {drive} LOW: {free:.0f}GB")

        db.close()
    except Exception:
        pass

    if alerts:
        for a in alerts:
            lines.append(a)
    else:
        lines.append("No active alerts - system healthy")

    return "\n".join(lines)


def report_full() -> str:
    """Full cockpit report combining all."""
    parts = [report_cluster(), "", report_evolution(), "", report_alerts()]
    return "\n".join(parts)


def report_genome() -> str:
    """Quick system genome."""
    genome_path = TURBO_DIR / "data" / "system_genome.json"
    if not genome_path.exists():
        return "System genome not yet generated. Run system_genome task first."

    g = json.loads(genome_path.read_text())
    lines = ["*JARVIS System Genome*", f"_{g.get('timestamp', '')[:16]}_\n"]
    lines.append(f"Platform: {g.get('platform', {}).get('os', '?')}")
    t = g.get("tasks", {})
    lines.append(f"Tasks: {t.get('active', 0)} active, {t.get('total_runs', 0)} runs")
    c = g.get("codebase", {})
    lines.append(f"Code: {c.get('src_modules', 0)} modules, {c.get('tests', 0)} tests")
    lines.append(f"Git: {g.get('git_commits', 0)} commits")
    lines.append(f"Services: {g.get('services_online', 0)}/5 online")
    lines.append(f"Head: {g.get('git_head', '?')}")
    return "\n".join(lines)


def report_tasks_top() -> str:
    """Top/bottom tasks by value."""
    lines = ["*Task Performance*", f"_{datetime.now().strftime('%d/%m %H:%M')}_\n"]
    try:
        db = sqlite3.connect(ORCH_DB)
        # Slowest
        slow = db.execute("""
            SELECT task_id, AVG(duration_ms) as avg FROM task_runs
            WHERE status='completed' AND duration_ms > 0
            GROUP BY task_id HAVING COUNT(*) >= 3
            ORDER BY avg DESC LIMIT 5
        """).fetchall()
        if slow:
            lines.append("*Slowest:*")
            for tid, avg in slow:
                lines.append(f"  {tid}: {avg:.0f}ms")

        # Most failing
        fail = db.execute("""
            SELECT task_id, COUNT(*) as c FROM task_runs
            WHERE status='failed' AND started_at > datetime('now', '-6 hours')
            GROUP BY task_id ORDER BY c DESC LIMIT 5
        """).fetchall()
        if fail:
            lines.append("\n*Most failing (6h):*")
            for tid, c in fail:
                lines.append(f"  {tid}: {c}x")

        db.close()
    except Exception as e:
        lines.append(f"Error: {e}")
    return "\n".join(lines)


def dispatch_question(question: str) -> str:
    """Dispatch a question to the cluster and return formatted answer."""
    lines = [f"*Question*: {question}\n"]

    # Ask M1 and OL1 in parallel-ish (sequential for simplicity)
    m1 = ask_m1(question)
    if m1 and "[M1 error" not in m1:
        lines.append(f"*[M1/qwen3-8b]*:\n{m1[:800]}")
    else:
        lines.append(f"*M1*: unavailable")

    ol1 = ask_ol1(question)
    if ol1 and "[OL1 error" not in ol1:
        lines.append(f"\n*[OL1/qwen3]*:\n{ol1[:500]}")

    return "\n".join(lines)


# ── Error Watcher & Auto-Fix ────────────────────────────────────────────

ERROR_DB = str(TURBO_DIR / "data" / "error_tracker.db")

def _init_error_db():
    """Initialize error tracking database."""
    db = sqlite3.connect(ERROR_DB)
    db.execute("""CREATE TABLE IF NOT EXISTS errors (
        id INTEGER PRIMARY KEY,
        timestamp TEXT DEFAULT (datetime('now')),
        source TEXT,
        error_type TEXT,
        message TEXT,
        task_id TEXT,
        fix_status TEXT DEFAULT 'pending',
        fix_command TEXT,
        fix_result TEXT,
        dispatched_to TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS error_patterns (
        id INTEGER PRIMARY KEY,
        pattern TEXT UNIQUE,
        fix_template TEXT,
        success_count INTEGER DEFAULT 0,
        fail_count INTEGER DEFAULT 0
    )""")
    db.commit()
    return db


def scan_task_errors(hours: int = 1) -> list[dict]:
    """Scan orchestrator DB for recent task failures with error details."""
    errors = []
    try:
        db = sqlite3.connect(ORCH_DB)
        rows = db.execute("""
            SELECT task_id, started_at, error, duration_ms
            FROM task_runs
            WHERE status='failed' AND started_at > datetime('now', ? || ' hours')
            ORDER BY started_at DESC LIMIT 20
        """, (f"-{hours}",)).fetchall()
        for tid, ts, err, dur in rows:
            errors.append({
                "task_id": tid, "timestamp": ts,
                "error": (err or "unknown")[:500],
                "duration_ms": dur or 0,
                "source": "orchestrator",
            })
        db.close()
    except Exception as e:
        errors.append({"task_id": "db_error", "error": str(e), "source": "scan"})
    return errors


def scan_service_errors() -> list[dict]:
    """Scan services for errors (OpenClaw, WS, logs)."""
    errors = []
    # OpenClaw gateway logs
    oc_log = TURBO_DIR / "data" / "openclaw.log"
    if oc_log.exists():
        try:
            lines = oc_log.read_text(errors="replace").splitlines()
            recent = lines[-100:]  # last 100 lines
            for line in recent:
                low = line.lower()
                if any(k in low for k in ["error", "traceback", "exception", "failed", "crash"]):
                    errors.append({
                        "task_id": "openclaw",
                        "error": line.strip()[:300],
                        "source": "openclaw_log",
                    })
        except Exception:
            pass

    # WS server health
    if check_port("127.0.0.1", 9742):
        try:
            req = urllib.request.Request("http://127.0.0.1:9742/health")
            resp = urllib.request.urlopen(req, timeout=5)
            data = json.loads(resp.read())
            if data.get("errors"):
                for e in data["errors"][:5]:
                    errors.append({"task_id": "ws_server", "error": str(e)[:300], "source": "ws_health"})
        except Exception:
            pass

    # Python stderr logs
    log_dir = TURBO_DIR / "data" / "logs"
    if log_dir.exists():
        for logfile in sorted(log_dir.glob("*.log"), key=lambda f: f.stat().st_mtime, reverse=True)[:5]:
            try:
                content = logfile.read_text(errors="replace")
                lines = content.splitlines()[-50:]
                for line in lines:
                    low = line.lower()
                    if any(k in low for k in ["traceback", "error:", "exception:", "fatal"]):
                        errors.append({
                            "task_id": logfile.stem,
                            "error": line.strip()[:300],
                            "source": f"log:{logfile.name}",
                        })
            except Exception:
                pass

    return errors


def scan_openclaw_errors() -> list[dict]:
    """Scan OpenClaw crons for errors and generate fix commands."""
    errors = []
    try:
        oc_cmd = os.path.expandvars(r"%APPDATA%\npm\openclaw.cmd")
        if not Path(oc_cmd).exists():
            oc_cmd = "openclaw"
        r = subprocess.run(
            [oc_cmd, "cron", "list", "--json"],
            capture_output=True, timeout=15,
            encoding="utf-8", errors="replace",
            shell=(oc_cmd.endswith(".cmd")),
        )
        if r.returncode != 0:
            return errors
        data = json.loads(r.stdout)
        for job in data.get("jobs", []):
            state = job.get("state", {})
            if state.get("lastStatus") == "error":
                name = job.get("name", "unknown")
                jid = job.get("id", "")[:8]
                consec = state.get("consecutiveErrors", 0)
                desc = job.get("description", "")
                payload_msg = job.get("payload", {}).get("message", "")[:200]

                # Build fix commands
                fix_cmds = [
                    f"openclaw cron run {jid}",
                    f"openclaw cron logs {jid}",
                    f"openclaw cron disable {jid}",
                ]

                # If the payload references a Python script, add direct execution
                if "python " in payload_msg.lower():
                    import re
                    scripts = re.findall(r'python\s+([\S]+\.py)', payload_msg)
                    for s in scripts[:1]:
                        fix_cmds.insert(0, f"python {s} 2>&1 | tail -20")

                errors.append({
                    "task_id": f"oc:{name}",
                    "error": f"OpenClaw cron '{name}' failed ({consec} consecutive errors). Payload: {payload_msg}",
                    "source": "openclaw_cron",
                    "fix_commands": fix_cmds,
                    "openclaw_id": jid,
                })
    except Exception as e:
        if "not found" not in str(e).lower():
            errors.append({"task_id": "openclaw_scan", "error": str(e)[:300], "source": "openclaw"})
    return errors


def generate_debug_commands(error: dict) -> list[str]:
    """Generate actionable debug commands for an error."""
    # If error already has fix_commands (e.g. from OpenClaw scanner), use those
    if error.get("fix_commands"):
        return error["fix_commands"]

    tid = error.get("task_id", "")
    err = error.get("error", "").lower()
    source = error.get("source", "")
    commands = []

    # Service down
    if "connection refused" in err or "down" in err:
        if "m1" in tid or "1234" in err:
            commands.append("curl -s http://127.0.0.1:1234/api/v1/models | python -m json.tool")
            commands.append('tasklist /FI "IMAGENAME eq lms.exe" /FO CSV /NH')
        elif "ol1" in tid or "11434" in err:
            commands.append("curl -s http://127.0.0.1:11434/api/tags")
            commands.append('tasklist /FI "IMAGENAME eq ollama.exe" /FO CSV /NH')
        elif "openclaw" in tid or "18789" in err:
            commands.append("curl -s http://127.0.0.1:18789/health")
            commands.append("openclaw status 2>&1")
        elif "ws" in tid or "9742" in err:
            commands.append("curl -s http://127.0.0.1:9742/health")
            commands.append("netstat -ano | findstr 9742")

    # Module import errors
    if "import" in err or "modulenotfound" in err:
        commands.append(f"python -c \"import {tid}\" 2>&1")
        commands.append("pip list | findstr -i " + tid.split("_")[0])

    # Permission/file errors
    if "permission" in err or "access denied" in err:
        commands.append(f"icacls /home/turbo/jarvis-m1-ops/data/ 2>&1 | head -5")

    # Timeout errors
    if "timeout" in err or "timed out" in err:
        commands.append("netstat -ano -p TCP | findstr LISTENING | head -10")
        commands.append("tasklist /FI \"STATUS eq RUNNING\" /FO CSV /NH | wc -l")

    # GPU/nvidia errors
    if "nvidia" in err or "cuda" in err or "gpu" in err:
        commands.append("nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,memory.used --format=csv 2>&1")

    # Database errors
    if "database" in err or "sqlite" in err or "locked" in err:
        commands.append(f"python -c \"import sqlite3; c=sqlite3.connect('{ORCH_DB}'); print('DB OK:', c.execute('SELECT COUNT(*) FROM tasks').fetchone())\"")

    # Generic task debug
    if not commands:
        commands.append(f"python /home/turbo/jarvis-m1-ops/scripts/task_orchestrator.py --run-once {tid} 2>&1 | tail -20")
        commands.append(f"python -c \"import sqlite3; db=sqlite3.connect('{ORCH_DB}'); r=db.execute('SELECT * FROM task_runs WHERE task_id=? ORDER BY id DESC LIMIT 1', ('{tid}',)).fetchone(); print(r)\"")

    return commands


def dispatch_error_to_cluster(error: dict) -> str:
    """Send error to cluster (M1/OL1) asking for diagnosis and fix."""
    err_msg = error.get("error", "")[:400]
    tid = error.get("task_id", "unknown")
    source = error.get("source", "unknown")

    prompt = (
        f"JARVIS error detected. Task: {tid}, Source: {source}.\n"
        f"Error: {err_msg}\n\n"
        f"Give a 2-line diagnosis and a 1-line fix command (Windows/Python). "
        f"Be concise, actionable."
    )

    # Try M1 first (faster, more capable)
    result = ask_m1(prompt, max_tokens=200)
    agent = "M1/qwen3-8b"
    if not result or "[M1 error" in result:
        result = ask_ol1(prompt)
        agent = "OL1/qwen3"

    return f"[{agent}]: {result}" if result else "[Cluster] No response"


def error_watcher(hours: int = 1, auto_fix: bool = False) -> str:
    """Full error detection pipeline: scan → diagnose → report → optionally fix."""
    _init_error_db()
    edb = sqlite3.connect(ERROR_DB)

    # Collect errors from all sources
    task_errors = scan_task_errors(hours)
    service_errors = scan_service_errors()
    openclaw_errors = scan_openclaw_errors()
    all_errors = task_errors + service_errors + openclaw_errors

    if not all_errors:
        return "*JARVIS Error Watch*\nNo errors detected - system clean"

    # Deduplicate by task_id (keep most recent)
    seen = {}
    for e in all_errors:
        key = e["task_id"]
        if key not in seen:
            seen[key] = e
    unique_errors = list(seen.values())[:10]  # max 10

    lines = [
        f"*JARVIS Error Watch*",
        f"_{datetime.now().strftime('%d/%m %H:%M')}_ | {len(all_errors)} errors ({len(unique_errors)} unique)\n",
    ]

    for i, error in enumerate(unique_errors[:8], 1):
        tid = error["task_id"]
        err_short = error["error"][:150].replace("*", "").replace("_", "")
        source = error["source"]
        debug_cmds = generate_debug_commands(error)

        lines.append(f"*{i}. [{source}] {tid}*")
        lines.append(f"  {err_short}")

        if debug_cmds:
            lines.append(f"  Debug:")
            for cmd in debug_cmds[:2]:
                lines.append(f"  `{cmd[:120]}`")

        # Dispatch to cluster for diagnosis
        if auto_fix or len(unique_errors) <= 5:
            diagnosis = dispatch_error_to_cluster(error)
            if diagnosis and "[Cluster] No response" not in diagnosis:
                lines.append(f"  AI: {diagnosis[:200]}")
                # Log to error DB
                edb.execute(
                    "INSERT INTO errors (source, error_type, message, task_id, fix_command, dispatched_to) VALUES (?,?,?,?,?,?)",
                    (source, "auto_detected", error["error"][:500], tid, diagnosis[:500], "cluster")
                )

        lines.append("")

    edb.commit()
    edb.close()

    # Summary
    task_fails = len(task_errors)
    svc_fails = len(service_errors)
    lines.append(f"*Summary*: {task_fails} task failures, {svc_fails} service errors")
    if auto_fix:
        lines.append("Auto-fix: dispatched to cluster for correction")

    return "\n".join(lines)


def fix_task(task_id: str) -> str:
    """Attempt to auto-fix a specific failed task by dispatching to cluster."""
    # Get latest error for this task
    errors = scan_task_errors(hours=6)
    target = None
    for e in errors:
        if e["task_id"] == task_id:
            target = e
            break

    if not target:
        return f"No recent errors for task '{task_id}'"

    lines = [f"*Auto-Fix: {task_id}*\n"]
    lines.append(f"Error: {target['error'][:200]}\n")

    # Get debug commands
    debug_cmds = generate_debug_commands(target)
    lines.append("*Debug commands:*")
    for cmd in debug_cmds:
        lines.append(f"  `{cmd}`")

    # Ask cluster for fix
    diagnosis = dispatch_error_to_cluster(target)
    lines.append(f"\n*Cluster diagnosis:*\n{diagnosis}")

    # Execute debug commands and capture output
    lines.append("\n*Debug output:*")
    for cmd in debug_cmds[:2]:
        try:
            r = subprocess.run(
                cmd, shell=True, capture_output=True, timeout=10,
                encoding="utf-8", errors="replace",
                cwd=str(TURBO_DIR),
            )
            output = (r.stdout or r.stderr or "no output").strip()[:300]
            lines.append(f"`{cmd[:80]}`")
            lines.append(f"  → {output}")
        except Exception as ex:
            lines.append(f"`{cmd[:80]}` → timeout/error: {ex}")

    return "\n".join(lines)


def report_openclaw() -> str:
    """Report OpenClaw cron errors with actionable fix commands."""
    lines = ["*OpenClaw Error Report*", f"_{datetime.now().strftime('%d/%m %H:%M')}_\n"]

    oc_errors = scan_openclaw_errors()
    if not oc_errors:
        lines.append("OpenClaw: tous les crons OK")
        # Also show status summary
        try:
            oc_cmd = os.path.expandvars(r"%APPDATA%\npm\openclaw.cmd")
            if not Path(oc_cmd).exists():
                oc_cmd = "openclaw"
            r = subprocess.run(
                [oc_cmd, "cron", "list", "--json"],
                capture_output=True, timeout=15,
                encoding="utf-8", errors="replace",
                shell=(oc_cmd.endswith(".cmd")),
            )
            if r.returncode == 0:
                data = json.loads(r.stdout)
                jobs = data.get("jobs", [])
                ok = sum(1 for j in jobs if j.get("state", {}).get("lastStatus") == "ok")
                lines.append(f"  {ok}/{len(jobs)} crons OK")
        except Exception:
            pass
        return "\n".join(lines)

    for i, err in enumerate(oc_errors, 1):
        lines.append(f"*{i}. {err['task_id']}*")
        lines.append(f"  {err['error'][:200]}")
        fix_cmds = err.get("fix_commands", [])
        if fix_cmds:
            lines.append("  *Commandes de correction:*")
            for cmd in fix_cmds:
                lines.append(f"  `{cmd}`")

        # Dispatch to cluster for diagnosis
        diagnosis = dispatch_error_to_cluster(err)
        if diagnosis and "[Cluster] No response" not in diagnosis:
            lines.append(f"  *AI*: {diagnosis[:200]}")
        lines.append("")

    return "\n".join(lines)


def report_error_patterns() -> str:
    """Report recurring error patterns with fix success rates."""
    lines = ["*Error Patterns*", f"_{datetime.now().strftime('%d/%m %H:%M')}_\n"]
    try:
        db = sqlite3.connect(ORCH_DB)
        # Group failures by task and error substring
        patterns = db.execute("""
            SELECT task_id, SUBSTR(error, 1, 80) as pattern, COUNT(*) as c
            FROM task_runs
            WHERE status='failed' AND started_at > datetime('now', '-24 hours')
            GROUP BY task_id, pattern
            ORDER BY c DESC LIMIT 10
        """).fetchall()
        if patterns:
            for tid, pat, count in patterns:
                lines.append(f"  *{tid}* ({count}x): {pat}")
        else:
            lines.append("No recurring patterns in last 24h")
        db.close()
    except Exception as e:
        lines.append(f"Error: {e}")
    return "\n".join(lines)


# ── CLI ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="JARVIS Telegram Cockpit")
    parser.add_argument("--report", choices=["cluster", "evolution", "alerts", "full", "genome", "tasks", "errors", "patterns", "openclaw"],
                        help="Send a report to Telegram")
    parser.add_argument("--send", help="Send custom message")
    parser.add_argument("--ask", help="Ask the cluster a question via Telegram")
    parser.add_argument("--voice", help="Send voice message")
    parser.add_argument("--alerts", action="store_true", help="Send alerts report")
    parser.add_argument("--quiet", action="store_true", help="Only send if there are alerts")
    parser.add_argument("--watch-errors", action="store_true", help="Scan errors, diagnose, report to Telegram")
    parser.add_argument("--auto-fix", action="store_true", help="Auto-dispatch errors to cluster for fix")
    parser.add_argument("--fix", metavar="TASK_ID", help="Auto-fix a specific failed task")
    args = parser.parse_args()

    if args.report:
        reports = {
            "cluster": report_cluster,
            "evolution": report_evolution,
            "alerts": report_alerts,
            "full": report_full,
            "genome": report_genome,
            "tasks": report_tasks_top,
            "errors": lambda: error_watcher(hours=1),
            "patterns": report_error_patterns,
            "openclaw": report_openclaw,
        }
        text = reports[args.report]()
        if args.quiet and ("No active alerts" in text or "No errors" in text or "system clean" in text):
            print("[COCKPIT] Quiet mode: nothing to report")
            return
        print(text)
        send(text)

    elif args.watch_errors:
        text = error_watcher(hours=1, auto_fix=args.auto_fix)
        print(text)
        send(text)

    elif args.fix:
        text = fix_task(args.fix)
        print(text)
        send(text)

    elif args.send:
        send(args.send)
        print(f"[COCKPIT] Sent: {args.send[:80]}")

    elif args.ask:
        answer = dispatch_question(args.ask)
        print(answer)
        send(answer)

    elif args.voice:
        ok = send_voice(args.voice)
        print(f"[COCKPIT] Voice: {'OK' if ok else 'FAILED'}")

    elif args.alerts:
        text = report_alerts()
        print(text)
        send(text)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
