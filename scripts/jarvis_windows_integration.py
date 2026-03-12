#!/usr/bin/env python3
"""JARVIS Windows Deep Integration — Scheduled tasks, context menu, startup.
Usage:
    python jarvis_windows_integration.py --install     # Install all Windows integrations
    python jarvis_windows_integration.py --uninstall   # Remove all
    python jarvis_windows_integration.py --status      # Show current state
"""
import subprocess, sys, os

PYTHON = sys.executable
BASE = "F:/BUREAU/turbo"

def run(cmd, timeout=15):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           timeout=timeout, encoding='utf-8', errors='replace')
        return r.returncode == 0, r.stdout.strip(), r.stderr.strip()
    except Exception as e:
        return False, "", str(e)

# ── SCHEDULED TASKS ─────────────────────────────────────────────────
TASKS = [
    {
        "name": "JARVIS_Supervisor",
        "desc": "JARVIS Supervisor — monitor all services every 5 min",
        "cmd": f'"{PYTHON}" "{BASE}/scripts/jarvis_supervisor.py"',
        "schedule": "/SC MINUTE /MO 5",
    },
    {
        "name": "JARVIS_SelfImprove",
        "desc": "JARVIS Self-Improve — auto optimize weights every 15 min",
        "cmd": f'"{PYTHON}" "{BASE}/scripts/jarvis_auto_improve_telegram.py"',
        "schedule": "/SC MINUTE /MO 15",
    },
    {
        "name": "JARVIS_Boot",
        "desc": "JARVIS Boot — full system startup on logon",
        "cmd": f'"{PYTHON}" "{BASE}/scripts/jarvis_unified_boot.py"',
        "schedule": "/SC ONLOGON",
    },
    {
        "name": "JARVIS_Notifications",
        "desc": "JARVIS Notifications — Windows toast daemon on logon",
        "cmd": f'"{PYTHON}" "{BASE}/scripts/jarvis_windows_notify.py" --daemon',
        "schedule": "/SC ONLOGON",
    },
]

def install_tasks():
    lines = ["JARVIS Windows Scheduled Tasks", ""]
    for task in TASKS:
        # Delete existing first (silently)
        run(f'schtasks /Delete /TN "{task["name"]}" /F')
        # Create new
        cmd = (
            f'schtasks /Create /TN "{task["name"]}" '
            f'{task["schedule"]} '
            f'/TR "{task["cmd"]}" '
            f'/F /RL LIMITED'
        )
        ok, out, err = run(cmd)
        status = "OK" if ok else f"FAIL: {err[:80]}"
        lines.append(f"  {task['name']}: {status}")
    return "\n".join(lines)

def uninstall_tasks():
    lines = ["Removing JARVIS Scheduled Tasks", ""]
    for task in TASKS:
        ok, _, err = run(f'schtasks /Delete /TN "{task["name"]}" /F')
        status = "REMOVED" if ok else f"NOT FOUND: {err[:50]}"
        lines.append(f"  {task['name']}: {status}")
    return "\n".join(lines)

def status_tasks():
    lines = ["JARVIS Scheduled Tasks Status", ""]
    for task in TASKS:
        ok, out, _ = run(f'schtasks /Query /TN "{task["name"]}" /FO CSV /NH')
        if ok and out:
            parts = out.split(",")
            state = parts[3].strip('"') if len(parts) > 3 else "?"
            lines.append(f"  {task['name']}: {state}")
        else:
            lines.append(f"  {task['name']}: NOT INSTALLED")
    return "\n".join(lines)

# ── CONTEXT MENU (Explorer right-click) ─────────────────────────────
CONTEXT_MENU_REG = f"""Windows Registry Editor Version 5.00

[HKEY_CURRENT_USER/Software/Classes/*/shell/JarvisAnalyze]
@="Send to JARVIS"
"Icon"="{PYTHON.replace(chr(92), chr(92)*2)}"

[HKEY_CURRENT_USER/Software/Classes/*/shell/JarvisAnalyze/command]
@="/"{PYTHON.replace(chr(92), chr(92)*2)}/" /"{BASE.replace(chr(92), chr(92)*2)}//scripts//jarvis_file_handler.py/" /"%1/""

[HKEY_CURRENT_USER/Software/Classes/Directory/shell/JarvisOpen]
@="Open in JARVIS"
"Icon"="{PYTHON.replace(chr(92), chr(92)*2)}"

[HKEY_CURRENT_USER/Software/Classes/Directory/shell/JarvisOpen/command]
@="/"{PYTHON.replace(chr(92), chr(92)*2)}/" /"{BASE.replace(chr(92), chr(92)*2)}//scripts//jarvis_file_handler.py/" /"%1/""
"""

def install_context_menu():
    reg_file = os.path.join(BASE, "data", "jarvis_context_menu.reg")
    with open(reg_file, "w", encoding="utf-8") as f:
        f.write(CONTEXT_MENU_REG)
    ok, out, err = run(f'reg import "{reg_file}"')
    if ok:
        return f"Context menu installed (reg file: {reg_file})"
    return f"Context menu FAILED: {err[:100]}"

def uninstall_context_menu():
    run('reg delete "HKCU/Software/Classes/*/shell/JarvisAnalyze" /f')
    run('reg delete "HKCU/Software/Classes/Directory/shell/JarvisOpen" /f')
    return "Context menu removed"

# ── URL PROTOCOL HANDLER (jarvis://) ────────────────────────────────
def install_protocol():
    cmds = [
        'reg add "HKCU/Software/Classes/jarvis" /ve /d "URL:JARVIS Protocol" /f',
        'reg add "HKCU/Software/Classes/jarvis" /v "URL Protocol" /d "" /f',
        f'reg add "HKCU/Software/Classes/jarvis/shell/open/command" /ve /d "/"{PYTHON}/" /"{BASE}/scripts/jarvis_url_handler.py/" /"%1/"" /f',
    ]
    for cmd in cmds:
        run(cmd)
    return "Protocol handler jarvis:// installed"

# ── MAIN ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    args = sys.argv[1:]

    if "--install" in args:
        print(install_tasks())
        print()
        print(install_context_menu())
        print()
        print(install_protocol())
    elif "--uninstall" in args:
        print(uninstall_tasks())
        print()
        print(uninstall_context_menu())
    elif "--status" in args:
        print(status_tasks())
    else:
        print("Usage:")
        print("  --install    Install scheduled tasks + context menu + protocol handler")
        print("  --uninstall  Remove all Windows integrations")
        print("  --status     Show current state")
