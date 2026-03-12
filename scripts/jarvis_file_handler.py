#!/usr/bin/env python3
"""JARVIS File Handler — Called from Windows Explorer context menu.
Receives a file/folder path and sends it to JARVIS WS for processing.

Usage: python jarvis_file_handler.py "/path\to\file.txt"
"""
import json, sys, os, urllib.request

WS = "http://127.0.0.1:9742"
CHAT_ID = "2010747443"

def send_to_ws(filepath):
    """Send file info to WS API for processing."""
    data = json.dumps({"file": filepath, "action": "analyze"}).encode()
    try:
        req = urllib.request.Request(f"{WS}/api/windows/command",
            data=data, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None

def notify(title, msg):
    """Show Windows toast notification."""
    import subprocess
    ps = f'''
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
    $textNodes = $template.GetElementsByTagName("text")
    $textNodes.Item(0).AppendChild($template.CreateTextNode("{title}")) | Out-Null
    $textNodes.Item(1).AppendChild($template.CreateTextNode("{msg}")) | Out-Null
    $toast = [Windows.UI.Notifications.ToastNotification]::new($template)
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("JARVIS").Show($toast)
    '''
    subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                   capture_output=True, timeout=5)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: jarvis_file_handler.py <path>")
        sys.exit(1)

    filepath = sys.argv[1]
    is_dir = os.path.isdir(filepath)
    name = os.path.basename(filepath)

    result = send_to_ws(filepath)
    if result:
        notify("JARVIS", f"Processing: {name}")
    else:
        # Fallback: just show notification
        if is_dir:
            size = sum(os.path.getsize(os.path.join(dp, f))
                      for dp, _, fns in os.walk(filepath) for f in fns) // 1024
            notify("JARVIS", f"Folder: {name} ({size} KB)")
        else:
            size = os.path.getsize(filepath) // 1024 if os.path.exists(filepath) else 0
            notify("JARVIS", f"File: {name} ({size} KB)")
