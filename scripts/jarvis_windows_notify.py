#!/usr/bin/env python3
"""JARVIS Windows Notification Bridge — toast notifications + response loop."""
from __future__ import annotations
import argparse, json, os, subprocess, sys, time, urllib.request, urllib.error, threading
from pathlib import Path

WS_URL = "http://127.0.0.1:9742"

def send_toast(title: str, message: str, app_id: str = "JARVIS") -> bool:
    """Send a Windows toast notification via PowerShell."""
    # Escape single quotes for PowerShell
    title_safe = title.replace("'", "''")
    msg_safe = message.replace("'", "''")
    ps_script = f"""
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom, ContentType = WindowsRuntime] | Out-Null
    $xml = @'
    <toast>
        <visual>
            <binding template="ToastGeneric">
                <text>{title_safe}</text>
                <text>{msg_safe}</text>
            </binding>
        </visual>
        <audio silent="true"/>
    </toast>
'@
    $XmlDocument = [Windows.Data.Xml.Dom.XmlDocument]::new()
    $XmlDocument.LoadXml($xml)
    $AppId = '{app_id}'
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($AppId).Show(
        [Windows.UI.Notifications.ToastNotification]::new($XmlDocument)
    )
    """
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        return r.returncode == 0
    except Exception as e:
        print(f"Toast error: {e}")
        return False

def send_toast_simple(title: str, message: str) -> bool:
    """Fallback: simple PowerShell balloon notification."""
    ps = f"""
    Add-Type -AssemblyName System.Windows.Forms
    $n = New-Object System.Windows.Forms.NotifyIcon
    $n.Icon = [System.Drawing.SystemIcons]::Information
    $n.Visible = $true
    $n.BalloonTipTitle = '{title.replace("'", "''")}'
    $n.BalloonTipText = '{message.replace("'", "''")}'
    $n.ShowBalloonTip(5000)
    Start-Sleep -Seconds 6
    $n.Dispose()
    """
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        return r.returncode == 0
    except Exception:
        return False

def notify(title: str, message: str) -> bool:
    """Send notification, trying toast first, then balloon fallback."""
    return send_toast(title, message) or send_toast_simple(title, message)

def http_get(path: str, timeout: float = 5.0):
    try:
        with urllib.request.urlopen(f"{WS_URL}{path}", timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None

def http_post(path: str, data: dict, timeout: float = 5.0):
    try:
        req = urllib.request.Request(
            f"{WS_URL}{path}",
            data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None

def poll_notifications():
    """Poll WS API for pending notifications and display them."""
    data = http_get("/api/notifications/pending")
    if not data:
        return 0
    notifications = data.get("notifications", [])
    for n in notifications:
        title = n.get("title", "JARVIS")
        message = n.get("message", "")
        nid = n.get("id", "")
        if notify(f"JARVIS - {title}", message):
            http_post("/api/notifications/ack", {"id": nid})
    return len(notifications)

PID_FILE = Path("/home/turbo/jarvis-m1-ops/data/pids/windows_notify.pid")

def _acquire_singleton():
    """Ensure only one notification daemon runs. Kill existing if found."""
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text().strip())
            if old_pid != os.getpid():
                subprocess.run(f"taskkill /F /PID {old_pid}", shell=True,
                               capture_output=True, timeout=5)
                print(f"  Killed previous daemon PID {old_pid}")
        except Exception:
            pass
    PID_FILE.write_text(str(os.getpid()))

def _release_singleton():
    try:
        if PID_FILE.exists() and PID_FILE.read_text().strip() == str(os.getpid()):
            PID_FILE.unlink()
    except Exception:
        pass

def daemon_loop(interval: int = 5):
    """Continuous polling loop."""
    _acquire_singleton()
    print(f"[JARVIS] Notification daemon started (poll every {interval}s, PID {os.getpid()})")
    notify("JARVIS", "Notification bridge active")
    while True:
        try:
            count = poll_notifications()
            if count > 0:
                print(f"  Displayed {count} notification(s)")
        except KeyboardInterrupt:
            _release_singleton()
            break
        except Exception as e:
            print(f"  Poll error: {e}")
        time.sleep(interval)

def main():
    parser = argparse.ArgumentParser(description="JARVIS Windows notification bridge")
    parser.add_argument("--message", "-m", help="Send a single notification")
    parser.add_argument("--title", "-t", default="JARVIS", help="Notification title")
    parser.add_argument("--daemon", action="store_true", help="Run as polling daemon")
    parser.add_argument("--interval", type=int, default=5, help="Poll interval in seconds")
    parser.add_argument("--once", action="store_true", help="Poll once and exit")
    args = parser.parse_args()

    if args.message:
        ok = notify(args.title, args.message)
        print(f"Notification {'sent' if ok else 'failed'}: {args.message[:60]}")
    elif args.daemon:
        daemon_loop(args.interval)
    elif args.once:
        count = poll_notifications()
        print(f"Processed {count} notification(s)")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
