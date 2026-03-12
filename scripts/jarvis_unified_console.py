#!/usr/bin/env python3
"""JARVIS Unified Console — ALL services in ONE terminal.
Launches and manages every JARVIS service with tagged output.

Phase 0: Infrastructure (LM Studio + Ollama)
Phase 1: Application services (12 subprocess)
Phase 2: Supervisor loop (health checks every 60s)

Usage: python jarvis_unified_console.py
"""
import subprocess, threading, time, sys, os, signal, re, socket
from datetime import datetime
from pathlib import Path
import urllib.error
from urllib.request import urlopen

BASE = Path("/home/turbo/jarvis-m1-ops")
HOME = Path(os.path.expanduser("~"))
LOG_FILE = BASE / "data" / "jarvis_unified.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
VENV_PY = str(BASE / ".venv" / "Scripts" / "python.exe")
NODE = r'"/Program Files\nodejs\node.exe"'
N8N_CMD = r"/nvm4w\nodejs\n8n.cmd"
LMS_CLI = str(HOME / ".lmstudio" / "bin" / "lms.exe")

# ── ANSI colors for tags ────────────────────────────────────────────
COLORS = {
    "OPENCLAW":   "\033[96m",  # cyan
    "TELEGRAM":   "\033[92m",  # green
    "PROXY":      "\033[94m",  # blue
    "WS":         "\033[93m",  # yellow
    "DASHBOARD":  "\033[95m",  # magenta
    "MCP-SSE":    "\033[36m",  # dark cyan
    "WHISPER":    "\033[90m",  # gray
    "WINDOWS":    "\033[35m",  # dark magenta
    "LISTENER":   "\033[33m",  # dark yellow
    "GEMINI":     "\033[38;5;75m",   # light blue
    "N8N":        "\033[38;5;208m",  # orange
    "SUPERVISOR": "\033[97m",  # bright white
    "SYSTEM":     "\033[37m",  # white
    "ERROR":      "\033[91m",  # red
}
RESET = "\033[0m"
ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')

PID_FILE = BASE / "data" / "pids" / "unified_console.pid"

log_lock = threading.Lock()
log_fh = open(str(LOG_FILE), "w", encoding="utf-8", errors="replace")
processes = {}
running = True


def acquire_singleton():
    """Kill any existing console instance, write our PID."""
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text().strip())
            if old_pid != os.getpid():
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(old_pid)],
                    capture_output=True, timeout=5,
                )
        except Exception:
            pass
    PID_FILE.write_text(str(os.getpid()))


def release_singleton():
    """Remove PID file on exit."""
    try:
        if PID_FILE.exists() and PID_FILE.read_text().strip() == str(os.getpid()):
            PID_FILE.unlink()
    except Exception:
        pass


def emit(tag, line):
    """Print tagged line to console + write to clean log file."""
    ts = datetime.now().strftime("%H:%M:%S")
    color = COLORS.get(tag, "")
    formatted = f"{color}[{ts}] [{tag:10s}]{RESET} {line}"
    clean = ANSI_RE.sub('', f"[{ts}] [{tag:10s}] {line}")
    with log_lock:
        print(formatted, flush=True)
        log_fh.write(clean + "\n")
        log_fh.flush()


def stream_output(proc, tag):
    """Read stdout/stderr from a process and emit tagged lines."""
    for stream, is_err in [(proc.stdout, False), (proc.stderr, True)]:
        if stream is None:
            continue
        def _reader(s=stream, t=tag, e=is_err):
            try:
                for raw_line in s:
                    line = raw_line.rstrip("\n\r")
                    if not line:
                        continue
                    out_tag = "ERROR" if e and any(w in line.lower() for w in ["error", "exception", "traceback", "fail"]) else t
                    emit(out_tag, line)
            except Exception:
                pass
        threading.Thread(target=_reader, daemon=True).start()


def kill_port(port):
    """Kill any process listening on a port (safe, no shell injection)."""
    try:
        r = subprocess.run(
            ["cmd", "/c", f'netstat -ano | findstr ":{port} " | findstr LISTENING'],
            capture_output=True, text=True, timeout=5,
        )
        for line in r.stdout.strip().splitlines():
            pid = line.strip().split()[-1]
            if pid.isdigit() and int(pid) != os.getpid():
                subprocess.run(
                    ["taskkill", "/F", "/PID", pid],
                    capture_output=True, timeout=5,
                )
    except Exception:
        pass


def start_service(key, cmd, cwd, tag, env_extra=None, kill_ports=None):
    """Start a service as subprocess with merged output."""
    # Kill existing instances on specified ports
    if kill_ports:
        for p in kill_ports:
            kill_port(p)
        time.sleep(1)

    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    try:
        proc = subprocess.Popen(
            cmd, shell=True, cwd=cwd,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            encoding="utf-8", errors="replace",
            env=env,
        )
        processes[key] = proc
        emit("SYSTEM", f"Started {tag} (PID {proc.pid})")
        stream_output(proc, tag)
        return proc
    except Exception as e:
        emit("ERROR", f"Failed to start {tag}: {e}")
        return None


def supervisor_loop():
    """Built-in supervisor — scan every 60s and emit status."""
    time.sleep(30)  # Wait for all services to fully initialize
    while running:
        try:
            checks = {
                "M1":    "http://127.0.0.1:1234/api/v1/models",
                "OL1":   "http://127.0.0.1:11434/api/tags",
                "N8N":   "http://127.0.0.1:5678/healthz",
                "WS":    "http://127.0.0.1:9742/health",
                "Proxy": "http://127.0.0.1:18800/health",
                "OC":    "http://127.0.0.1:18789/",
                "Dash":  "http://127.0.0.1:8080/",
                "MCP":   "http://127.0.0.1:8901/mcp",
                "Gem":   "http://127.0.0.1:18791/",
            }
            results = []
            up_count = 0
            for name, url in checks.items():
                try:
                    with urlopen(url, timeout=5) as r:
                        ok = r.status < 500
                except urllib.error.HTTPError as e:
                    # Any HTTP error (4xx) still means server is alive
                    ok = e.code < 500
                except Exception:
                    ok = False
                if ok:
                    up_count += 1
                results.append(f"{name}={'UP' if ok else 'DOWN'}")

            # Process checks
            for key in ["n8n", "telegram", "openclaw", "proxy", "ws", "dashboard"]:
                if key in processes and processes[key].poll() is not None:
                    emit("ERROR", f"{key} CRASHED (exit={processes[key].returncode})")

            total = len(checks)
            score = up_count * 100 // total
            if score >= 95:   grade = "A+"
            elif score >= 85: grade = "A"
            elif score >= 70: grade = "B"
            elif score >= 50: grade = "C"
            else:             grade = "D"

            emit("SUPERVISOR", f"Grade {grade} ({score}%) — {' | '.join(results)}")

        except Exception as e:
            emit("ERROR", f"Supervisor: {e}")

        for _ in range(60):
            if not running:
                break
            time.sleep(1)


def shutdown(sig=None, frame=None):
    """Graceful shutdown of all processes."""
    global running
    running = False
    emit("SYSTEM", "Shutting down all services...")
    for key, proc in processes.items():
        try:
            proc.terminate()
            proc.wait(timeout=5)
            emit("SYSTEM", f"  {key} stopped")
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    release_singleton()
    log_fh.close()
    sys.exit(0)


# ── PHASE 0: INFRASTRUCTURE ────────────────────────────────────────
def check_port(host, port, timeout=2):
    """Check if a port is open."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False


def start_infrastructure():
    """Start LM Studio + Ollama if not already running."""
    emit("SYSTEM", "Phase 0 — Infrastructure (LM Studio + Ollama)")

    # -- LM Studio (M1) --
    if check_port("127.0.0.1", 1234):
        emit("SYSTEM", "  M1 LM Studio: already running on :1234")
    else:
        emit("SYSTEM", "  M1 LM Studio: starting...")
        try:
            subprocess.run(
                [LMS_CLI, "server", "start"],
                capture_output=True, timeout=30, encoding="utf-8",
            )
            for _ in range(20):
                if check_port("127.0.0.1", 1234):
                    emit("SYSTEM", "  M1 LM Studio: OK")
                    break
                time.sleep(1)
            else:
                emit("ERROR", "  M1 LM Studio: no response after 20s")
        except (subprocess.SubprocessError, OSError, FileNotFoundError) as e:
            emit("ERROR", f"  M1 LM Studio: {e}")

    # -- Ollama --
    if check_port("127.0.0.1", 11434):
        emit("SYSTEM", "  Ollama: already running on :11434")
    else:
        emit("SYSTEM", "  Ollama: starting...")
        try:
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            for _ in range(15):
                if check_port("127.0.0.1", 11434):
                    emit("SYSTEM", "  Ollama: OK")
                    break
                time.sleep(1)
            else:
                emit("ERROR", "  Ollama: no response after 15s")
        except (OSError, FileNotFoundError) as e:
            emit("ERROR", f"  Ollama: {e}")

    emit("SYSTEM", "Phase 0 complete")


# ── SERVICE DEFINITIONS ─────────────────────────────────────────────
SERVICES = [
    # (key, cmd, cwd, tag, env_extra, kill_ports, delay_after)
    ("n8n", f'"{N8N_CMD}" start', str(BASE),
     "N8N", {"N8N_SECURE_COOKIE": "false", "EXECUTIONS_MODE": "regular",
             "NODE_OPTIONS": "--max-old-space-size=4096",
             "EXECUTIONS_DATA_PRUNE": "true", "EXECUTIONS_DATA_MAX_AGE": "72"}, [5678], 5),

    ("proxy", f'{NODE} direct-proxy.js', str(BASE / "canvas"),
     "PROXY", None, [18800], 2),

    ("ws", f'"{VENV_PY}" -m uvicorn python_ws.server:app --host 0.0.0.0 --port 9742 --log-level warning', str(BASE),
     "WS", None, [9742], 3),

    ("dashboard", f'"{VENV_PY}" {BASE / "dashboard" / "server.py"}', str(BASE),
     "DASHBOARD", None, [8080], 1),

    ("mcp_sse", f'"{VENV_PY}" -m src.mcp_server_sse --port 8901', str(BASE),
     "MCP-SSE", None, [8901], 1),

    ("whisper", f'"{VENV_PY}" -m src.whisper_worker', str(BASE),
     "WHISPER", None, None, 1),

    ("openclaw", f'{NODE} /\Users/franc/AppData/Roaming/npm/node_modules/openclaw/dist/index.js gateway --port 18789',
     "/\Users/franc/.openclaw",
     "OPENCLAW", {"OPENCLAW_GATEWAY_PORT": "18789", "OPENCLAW_GATEWAY_TOKEN": "ae1cd158a0975c30e7712b274859e202896e7f67203de9d2"}, [18789], 2),

    ("telegram", f'{NODE} telegram-bot.js', str(BASE / "canvas"),
     "TELEGRAM", None, None, 2),

    ("gemini", f'{NODE} /\Users/franc/.openclaw/gemini-proxy.js',
     str(HOME / ".openclaw"),
     "GEMINI", None, [18791], 1),

    ("windows", f'"{VENV_PY}" "{BASE / "scripts" / "jarvis_windows_notify.py"}" --daemon', str(BASE),
     "WINDOWS", None, None, 0),

    ("listener", f'"{VENV_PY}" "{BASE / "scripts" / "jarvis_windows_listener.py"}" --daemon', str(BASE),
     "LISTENER", None, None, 0),
]

# Auto-restart critical services
CRITICAL_SERVICES = {"proxy", "ws", "openclaw", "n8n", "telegram"}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    os.system("")  # Enable ANSI on Windows

    acquire_singleton()
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    svc_count = len(SERVICES)
    print()
    print(f"\033[97m{'=' * 62}{RESET}")
    print(f"\033[97m  JARVIS UNIFIED CONSOLE — {svc_count} services, one terminal{RESET}")
    print(f"\033[97m  Log: {LOG_FILE}{RESET}")
    print(f"\033[97m  Ctrl+C to stop all{RESET}")
    print(f"\033[97m{'=' * 62}{RESET}")
    print()

    # Phase 0: Infrastructure (LM Studio + Ollama)
    start_infrastructure()
    print()

    emit("SYSTEM", f"Phase 1 — Launching {svc_count} services...")

    for key, cmd, cwd, tag, env_extra, kill_ports, delay in SERVICES:
        start_service(key, cmd, cwd, tag, env_extra, kill_ports)
        if delay:
            time.sleep(delay)

    # Start supervisor thread
    sup_thread = threading.Thread(target=supervisor_loop, daemon=True)
    sup_thread.start()
    emit("SYSTEM", "Supervisor thread started (scan every 60s)")
    emit("SYSTEM", f"All {svc_count} services launched — Ctrl+C to stop")

    # Main loop — watch for crashes, auto-restart critical services
    try:
        while running:
            time.sleep(2)
            for key, cmd, cwd, tag, env_extra, kill_ports, delay in SERVICES:
                if key in CRITICAL_SERVICES and key in processes:
                    if processes[key].poll() is not None:
                        emit("ERROR", f"{tag} died — restarting in 3s...")
                        time.sleep(3)
                        start_service(key, cmd, cwd, tag, env_extra)
    except KeyboardInterrupt:
        shutdown()
