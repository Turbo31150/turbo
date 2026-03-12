#!/usr/bin/env python3
"""JARVIS Win Notify — Notifications toast Windows pour alertes."""
import json, sys, subprocess
from datetime import datetime

def show_toast(title, message, duration=5):
    """Affiche une notification toast Windows via PowerShell."""
    ps_script = f'''
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom, ContentType=WindowsRuntime] | Out-Null

$template = @"
<toast>
    <visual>
        <binding template="ToastGeneric">
            <text>$("{title}")</text>
            <text>$("{message}")</text>
        </binding>
    </visual>
</toast>
"@

$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml($template)
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("JARVIS").Show($toast)
'''
    try:
        result = subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except Exception as e:
        # Fallback: BurntToast module
        return show_toast_fallback(title, message)

def show_toast_fallback(title, message):
    """Fallback via BurntToast PowerShell module."""
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             f'New-BurntToastNotification -Text "{title}","{message}"'],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except:
        # Ultimate fallback: msg command
        try:
            subprocess.run(["msg", "*", f"{title}: {message}"], timeout=5)
            return True
        except:
            return False

def notify_alert(level, source, message):
    """Notification avec niveau (info/warning/critical)."""
    icons = {"info": "INFO", "warning": "ATTENTION", "critical": "ALERTE CRITIQUE"}
    title = f"JARVIS [{icons.get(level, level.upper())}]"
    full_msg = f"[{source}] {message}"
    return show_toast(title, full_msg)

def listen_stdin():
    """Ecoute stdin pour notifications en temps reel (pipe mode)."""
    print("JARVIS Notify — listening on stdin (JSON lines)...")
    print('Format: {"level":"info|warning|critical","source":"module","message":"text"}')
    for line in sys.stdin:
        line = line.strip()
        if not line: continue
        try:
            data = json.loads(line)
            level = data.get("level", "info")
            source = data.get("source", "JARVIS")
            message = data.get("message", line)
            ok = notify_alert(level, source, message)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {'OK' if ok else 'FAIL'}: {source} — {message[:60]}")
        except json.JSONDecodeError:
            show_toast("JARVIS", line)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Raw: {line[:60]}")

if __name__ == "__main__":
    if "--test" in sys.argv:
        ok = show_toast("JARVIS Test", f"Notification OK — {datetime.now().strftime('%H:%M:%S')}")
        print(f"Toast: {'OK' if ok else 'FAIL'}")
    elif "--alert" in sys.argv:
        level = sys.argv[sys.argv.index("--alert") + 1] if len(sys.argv) > sys.argv.index("--alert") + 1 else "info"
        msg = " ".join(sys.argv[sys.argv.index("--alert") + 2:]) or "Test alert"
        ok = notify_alert(level, "CLI", msg)
        print(f"Alert [{level}]: {'OK' if ok else 'FAIL'}")
    elif "--listen" in sys.argv:
        listen_stdin()
    else:
        print("Usage: win_notify.py --test | --alert <level> <message> | --listen")
