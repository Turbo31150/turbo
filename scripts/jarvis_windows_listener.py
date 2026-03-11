#!/usr/bin/env python3
"""JARVIS Windows Listener — persistent command bridge OS ↔ JARVIS.

3 modes de communication Windows → JARVIS → Windows:
  1. Hotkey Ctrl+Shift+J → popup InputBox → execute → toast reponse
  2. File watcher: ecrire dans data/jarvis_inbox.txt → execute → reponse dans data/jarvis_outbox.txt
  3. CLI direct: python jarvis_windows_listener.py "ma commande"

Le listener tourne en permanence et accepte des commandes Windows.
JARVIS execute a travers les 7 couches (L0→L6) et repond en toast.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

WS_URL = "http://127.0.0.1:9742"
TURBO_DIR = Path(__file__).resolve().parent.parent
INBOX = TURBO_DIR / "data" / "jarvis_inbox.txt"
OUTBOX = TURBO_DIR / "data" / "jarvis_outbox.txt"
PID_FILE = TURBO_DIR / "data" / "pids" / "windows_listener.pid"


def _acquire_singleton():
    """Kill any existing listener instance, write our PID."""
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text().strip())
            if old_pid != os.getpid():
                subprocess.run(
                    ["taskkill", "/F", "/PID", str(old_pid)],
                    capture_output=True, timeout=5,
                )
        except Exception:
            pass
    PID_FILE.write_text(str(os.getpid()))


def _release_singleton():
    try:
        if PID_FILE.exists() and PID_FILE.read_text().strip() == str(os.getpid()):
            PID_FILE.unlink()
    except Exception:
        pass


def http_post(path: str, data: dict, timeout: float = 30.0):
    try:
        req = urllib.request.Request(
            f"{WS_URL}{path}",
            data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"error": str(e)}


def send_command(text: str) -> dict:
    """Send command through JARVIS 7-layer pipeline."""
    resp = http_post("/api/windows/command", {"text": text})
    return resp


def send_toast(title: str, message: str) -> bool:
    """Send Windows toast notification via PowerShell."""
    msg_safe = message[:300].replace("'", "''").replace("\n", " ").replace("\r", "")
    title_safe = title[:80].replace("'", "''")
    ps = f"""
    Add-Type -AssemblyName System.Windows.Forms
    $n = New-Object System.Windows.Forms.NotifyIcon
    $n.Icon = [System.Drawing.SystemIcons]::Information
    $n.Visible = $true
    $n.BalloonTipTitle = '{title_safe}'
    $n.BalloonTipText = '{msg_safe}'
    $n.ShowBalloonTip(8000)
    Start-Sleep -Seconds 9
    $n.Dispose()
    """
    try:
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, timeout=15, creationflags=flags,
        )
        return r.returncode == 0
    except Exception:
        return False


def show_input_dialog(prompt: str = "Commande pour JARVIS:") -> str | None:
    """Show Windows InputBox dialog."""
    ps = f"""
    Add-Type -AssemblyName Microsoft.VisualBasic
    $result = [Microsoft.VisualBasic.Interaction]::InputBox(
        '{prompt.replace("'", "''")}',
        'JARVIS Commander',
        ''
    )
    if ($result) {{ Write-Output $result }}
    """
    try:
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=300, creationflags=flags,
        )
        text = r.stdout.strip()
        return text if text else None
    except Exception:
        return None


def execute_and_respond(text: str) -> str:
    """Execute command and return response string."""
    print(f"  > {text[:80]}")
    resp = send_command(text)

    if resp.get("error"):
        msg = f"Erreur: {resp['error'][:200]}"
    else:
        layer = resp.get("layer", "?")
        intent = resp.get("intent", "?")
        content = resp.get("response", "Pas de reponse")
        msg = f"[{layer}|{intent}] {content[:300]}"

    print(f"  < {msg[:100]}")
    return msg


# ── Mode 1: Hotkey listener (Ctrl+Shift+J) ──────────────────────────

def register_hotkey_loop():
    """Register global hotkey Ctrl+Shift+J and loop."""
    ps_script = r"""
    Add-Type @'
    using System;
    using System.Runtime.InteropServices;
    public class HotKey {
        [DllImport("user32.dll")] public static extern bool RegisterHotKey(IntPtr hWnd, int id, uint fsModifiers, uint vk);
        [DllImport("user32.dll")] public static extern bool UnregisterHotKey(IntPtr hWnd, int id);
        [DllImport("user32.dll")] public static extern bool GetMessage(out MSG lpMsg, IntPtr hWnd, uint wMsgFilterMin, uint wMsgFilterMax);
        [StructLayout(LayoutKind.Sequential)] public struct MSG { public IntPtr hwnd; public uint message; public IntPtr wParam; public IntPtr lParam; public uint time; public POINT pt; }
        [StructLayout(LayoutKind.Sequential)] public struct POINT { public int x; public int y; }
    }
'@
    # Ctrl+Shift+J = MOD_CONTROL(2) | MOD_SHIFT(4) = 6, J=0x4A
    [HotKey]::RegisterHotKey([IntPtr]::Zero, 1, 6, 0x4A)
    Write-Host "HOTKEY_REGISTERED"
    while ($true) {
        $msg = New-Object HotKey+MSG
        if ([HotKey]::GetMessage([ref]$msg, [IntPtr]::Zero, 0, 0)) {
            if ($msg.message -eq 0x0312) {
                Write-Host "HOTKEY_PRESSED"
            }
        }
    }
    """
    print("[JARVIS] Registering hotkey Ctrl+Shift+J...")
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

    proc = subprocess.Popen(
        ["powershell", "-NoProfile", "-Command", ps_script],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, creationflags=flags,
    )

    for line in iter(proc.stdout.readline, ""):
        line = line.strip()
        if line == "HOTKEY_REGISTERED":
            print("[JARVIS] Hotkey Ctrl+Shift+J active!")
            send_toast("JARVIS", "Hotkey Ctrl+Shift+J actif. Appuie pour envoyer une commande.")
        elif line == "HOTKEY_PRESSED":
            # Show input dialog
            text = show_input_dialog()
            if text:
                msg = execute_and_respond(text)
                send_toast("JARVIS Reponse", msg)


# ── Mode 2: File watcher (inbox/outbox) ──────────────────────────────

def file_watcher_loop(interval: float = 1.0):
    """Watch jarvis_inbox.txt for commands, write responses to jarvis_outbox.txt."""
    print(f"[JARVIS] File watcher mode")
    print(f"  Inbox:  {INBOX}")
    print(f"  Outbox: {OUTBOX}")
    send_toast("JARVIS", f"File watcher actif. Ecris dans {INBOX.name}")

    last_mtime = 0.0
    while True:
        try:
            if INBOX.exists():
                mtime = INBOX.stat().st_mtime
                if mtime > last_mtime:
                    last_mtime = mtime
                    text = INBOX.read_text(encoding="utf-8", errors="replace").strip()
                    if text:
                        msg = execute_and_respond(text)
                        # Write response to outbox
                        OUTBOX.write_text(msg, encoding="utf-8")
                        # Send toast
                        send_toast("JARVIS Reponse", msg[:200])
                        # Clear inbox
                        INBOX.write_text("", encoding="utf-8")
        except Exception as e:
            print(f"  Watcher error: {e}")
        time.sleep(interval)


# ── Mode 3: Interactive dialog loop ──────────────────────────────────

def dialog_loop():
    """Repeating dialog: InputBox → execute → toast."""
    print("[JARVIS] Dialog loop mode")
    send_toast("JARVIS", "Commander mode actif")

    while True:
        text = show_input_dialog()
        if not text:
            print("  Dialog fermee")
            break
        msg = execute_and_respond(text)
        send_toast("JARVIS Reponse", msg[:300])


# ── Mode 4: Daemon (hotkey + file watcher combined) ──────────────────

def daemon_mode():
    """Run both hotkey listener and file watcher."""
    print("[JARVIS] Daemon mode: hotkey + file watcher")

    # File watcher in background thread
    watcher = threading.Thread(target=file_watcher_loop, daemon=True)
    watcher.start()

    # Hotkey in main thread
    register_hotkey_loop()


def main():
    _acquire_singleton()
    parser = argparse.ArgumentParser(description="JARVIS Windows Listener")
    parser.add_argument("command", nargs="?", help="Direct command to execute")
    parser.add_argument("--hotkey", action="store_true", help="Hotkey mode (Ctrl+Shift+J)")
    parser.add_argument("--watch", action="store_true", help="File watcher mode (inbox/outbox)")
    parser.add_argument("--loop", action="store_true", help="Interactive dialog loop")
    parser.add_argument("--daemon", action="store_true", help="Daemon: hotkey + file watcher")
    parser.add_argument("--once", action="store_true", help="Single dialog then exit")
    args = parser.parse_args()

    if args.command:
        msg = execute_and_respond(args.command)
        send_toast("JARVIS", msg[:300])
    elif args.daemon:
        daemon_mode()
    elif args.hotkey:
        register_hotkey_loop()
    elif args.watch:
        file_watcher_loop()
    elif args.loop:
        dialog_loop()
    elif args.once:
        text = show_input_dialog()
        if text:
            msg = execute_and_respond(text)
            send_toast("JARVIS", msg[:300])
    else:
        # Default: daemon mode
        daemon_mode()


if __name__ == "__main__":
    main()
