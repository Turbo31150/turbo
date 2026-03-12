"""JARVIS Windows Service — Run JARVIS as a Windows background service.

Uses NSSM (Non-Sucking Service Manager) for reliable service management.
Falls back to a simple scheduled task if NSSM is unavailable.

Usage:
    python scripts/jarvis_service.py install   — Install JARVIS as service
    python scripts/jarvis_service.py uninstall — Remove JARVIS service
    python scripts/jarvis_service.py start     — Start the service
    python scripts/jarvis_service.py stop      — Stop the service
    python scripts/jarvis_service.py status    — Check service status
    python scripts/jarvis_service.py restart   — Restart the service
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

TURBO_ROOT = Path(__file__).resolve().parent.parent
SERVICE_NAME = "JARVISDesktop"
DISPLAY_NAME = "JARVIS Desktop AI Assistant"
DESCRIPTION = "JARVIS AI Desktop — FastAPI WS server + autonomous loop + cluster management"

# Components to manage
COMPONENTS = {
    "ws_server": {
        "name": "JARVIS WS Server",
        "cmd": f'"{sys.executable}" -m uvicorn python_ws.server:app --host 127.0.0.1 --port 9742',
        "cwd": str(TURBO_ROOT),
    },
    "ollama": {
        "name": "Ollama Server",
        "check": "http://127.0.0.1:11434/api/tags",
    },
    "lm_studio": {
        "name": "LM Studio M1",
        "check": "http://127.0.0.1:1234/api/v1/models",
    },
}


def _run_ps(cmd: str, check: bool = False) -> subprocess.CompletedProcess:
    """Run a PowerShell command."""
    return subprocess.run(
        ["powershell", "-NoProfile", "-Command", cmd],
        capture_output=True, text=True, timeout=30,
    )


def _nssm_available() -> bool:
    """Check if NSSM is installed."""
    try:
        r = subprocess.run(["nssm", "version"], capture_output=True, text=True, timeout=5)
        return r.returncode == 0
    except FileNotFoundError:
        return False


def install():
    """Install JARVIS as a Windows service or scheduled task."""
    if _nssm_available():
        _install_nssm()
    else:
        _install_task_scheduler()


def _install_nssm():
    """Install via NSSM."""
    python = sys.executable
    script = str(TURBO_ROOT / "scripts" / "jarvis_launcher.py")

    cmds = [
        f'nssm install {SERVICE_NAME} "{python}" "{script}"',
        f'nssm set {SERVICE_NAME} AppDirectory "{TURBO_ROOT}"',
        f'nssm set {SERVICE_NAME} DisplayName "{DISPLAY_NAME}"',
        f'nssm set {SERVICE_NAME} Description "{DESCRIPTION}"',
        f'nssm set {SERVICE_NAME} Start SERVICE_AUTO_START',
        f'nssm set {SERVICE_NAME} AppStdout "{TURBO_ROOT / "logs" / "service_stdout.log"}"',
        f'nssm set {SERVICE_NAME} AppStderr "{TURBO_ROOT / "logs" / "service_stderr.log"}"',
        f'nssm set {SERVICE_NAME} AppRotateFiles 1',
        f'nssm set {SERVICE_NAME} AppRotateBytes 5242880',
        f'nssm set {SERVICE_NAME} AppRestartDelay 5000',
    ]

    # Create logs dir
    (TURBO_ROOT / "logs").mkdir(exist_ok=True)

    for cmd in cmds:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        if r.returncode != 0 and "already exists" not in r.stderr:
            print(f"WARN: {cmd} -> {r.stderr.strip()}")

    print(f"Service '{SERVICE_NAME}' installed via NSSM")
    print(f"Start: nssm start {SERVICE_NAME}")


def _install_task_scheduler():
    """Fallback: install via Windows Task Scheduler."""
    python = sys.executable
    script = str(TURBO_ROOT / "scripts" / "jarvis_launcher.py")
    task_name = "JARVIS_Desktop_AutoStart"

    cmd = (
        f'schtasks /Create /TN "{task_name}" /TR "/\"{python}/\" /\"{script}/\"" '
        f'/SC ONLOGON /RL HIGHEST /F /DELAY 0000:15'
    )
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
    if r.returncode == 0:
        print(f"Scheduled task '{task_name}' created (runs at logon)")
    else:
        print(f"Failed: {r.stderr.strip()}")


def uninstall():
    """Remove JARVIS service/task."""
    if _nssm_available():
        r = subprocess.run(f"nssm remove {SERVICE_NAME} confirm", shell=True,
                           capture_output=True, text=True, timeout=10)
        print(f"NSSM remove: {r.stdout.strip() or r.stderr.strip()}")
    else:
        r = subprocess.run(f'schtasks /Delete /TN "JARVIS_Desktop_AutoStart" /F',
                           shell=True, capture_output=True, text=True, timeout=10)
        print(f"Task remove: {r.stdout.strip() or r.stderr.strip()}")


def start():
    """Start the service."""
    if _nssm_available():
        r = subprocess.run(f"nssm start {SERVICE_NAME}", shell=True,
                           capture_output=True, text=True, timeout=10)
        print(r.stdout.strip() or r.stderr.strip())
    else:
        print("NSSM not available. Start manually or use scheduled task.")


def stop():
    """Stop the service."""
    if _nssm_available():
        r = subprocess.run(f"nssm stop {SERVICE_NAME}", shell=True,
                           capture_output=True, text=True, timeout=10)
        print(r.stdout.strip() or r.stderr.strip())
    else:
        # Kill by process name
        _run_ps('Get-Process -Name python | Where-Object {$_.CommandLine -like "*jarvis_launcher*"} | Stop-Process -Force')
        print("Processes stopped")


def status():
    """Check service status."""
    if _nssm_available():
        r = subprocess.run(f"nssm status {SERVICE_NAME}", shell=True,
                           capture_output=True, text=True, timeout=10)
        print(f"NSSM status: {r.stdout.strip()}")
    else:
        r = _run_ps(f'schtasks /Query /TN "JARVIS_Desktop_AutoStart" /FO LIST')
        print(r.stdout.strip() if r.returncode == 0 else "Not installed")

    # Check component health
    print("\n--- Component Health ---")
    import urllib.request
    for comp_id, comp in COMPONENTS.items():
        check_url = comp.get("check")
        if check_url:
            try:
                req = urllib.request.urlopen(check_url, timeout=3)
                print(f"  {comp['name']}: ONLINE ({req.status})")
            except Exception:
                print(f"  {comp['name']}: OFFLINE")
        else:
            print(f"  {comp['name']}: (no health check)")


def restart():
    """Restart the service."""
    stop()
    import time
    time.sleep(2)
    start()


# Also create the launcher script
def _create_launcher():
    """Create jarvis_launcher.py if missing."""
    launcher = TURBO_ROOT / "scripts" / "jarvis_launcher.py"
    if launcher.exists():
        return
    launcher.write_text('''"""JARVIS Launcher — Starts all components."""
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

async def main():
    """Start WS server (main component)."""
    import uvicorn
    config = uvicorn.Config(
        "python_ws.server:app",
        host="127.0.0.1",
        port=9742,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
''', encoding="utf-8")
    print(f"Created {launcher}")


if __name__ == "__main__":
    _create_launcher()

    if len(sys.argv) < 2:
        print("Usage: python jarvis_service.py [install|uninstall|start|stop|status|restart]")
        sys.exit(1)

    action = sys.argv[1].lower()
    actions = {
        "install": install,
        "uninstall": uninstall,
        "start": start,
        "stop": stop,
        "status": status,
        "restart": restart,
    }

    fn = actions.get(action)
    if fn:
        fn()
    else:
        print(f"Unknown action: {action}")
        print(f"Valid: {', '.join(actions.keys())}")
        sys.exit(1)
