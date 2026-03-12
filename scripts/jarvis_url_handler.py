#!/usr/bin/env python3
"""JARVIS URL Protocol Handler — Handles jarvis:// URLs.
Called when user clicks a jarvis:// link.

Examples:
    jarvis://status       → Show system status
    jarvis://gpu          → Show GPU info
    jarvis://sql/stats    → SQL stats
    jarvis://ask/question → Ask the cluster

Usage: python jarvis_url_handler.py "jarvis://command/args"
"""
import json, sys, subprocess, urllib.request, urllib.parse

WS = "http://127.0.0.1:9742"
SCRIPTS = "F:/BUREAU/turbo/scripts"

def run_script(script, args=""):
    try:
        cmd = f'python "{SCRIPTS}/{script}"'
        if args:
            cmd += f' {args}'
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                          timeout=30, encoding='utf-8', errors='replace')
        return r.stdout.strip()
    except Exception as e:
        return f"Error: {e}"

def notify(title, msg):
    ps = f'Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show("{msg}", "{title}")'
    subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                   capture_output=True, timeout=10)

COMMANDS = {
    "status":    lambda a: run_script("jarvis_fullstatus_telegram.py"),
    "boot":      lambda a: run_script("jarvis_boot_telegram.py"),
    "gpu":       lambda a: run_script("jarvis_models_telegram.py"),
    "models":    lambda a: run_script("jarvis_models_telegram.py"),
    "sql":       lambda a: run_script("jarvis_sql_telegram.py", a or "stats"),
    "weights":   lambda a: run_script("jarvis_weights_telegram.py"),
    "autofix":   lambda a: run_script("jarvis_autofix_telegram.py"),
    "supervisor":lambda a: run_script("jarvis_supervisor.py"),
}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        notify("JARVIS", "Usage: jarvis://command[/args]")
        sys.exit(1)

    url = sys.argv[1]
    # Parse jarvis://command/args
    parsed = urllib.parse.urlparse(url)
    cmd = parsed.netloc or parsed.path.strip("/").split("/")[0]
    args = "/".join(parsed.path.strip("/").split("/")[1:]) if "/" in parsed.path.strip("/") else ""

    if cmd in COMMANDS:
        result = COMMANDS[cmd](args)
        notify(f"JARVIS — {cmd}", result[:500] if result else "Done")
    else:
        available = ", ".join(COMMANDS.keys())
        notify("JARVIS", f"Unknown: {cmd}\nAvailable: {available}")
