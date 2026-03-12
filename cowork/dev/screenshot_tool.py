#!/usr/bin/env python3
"""JARVIS Screenshot Tool — Capture d'ecran Windows avec PowerShell."""
import json, sys, os, subprocess
from datetime import datetime

SCREENSHOT_DIR = "C:/Users/franc/.openclaw/workspace/dev/screenshots"

def ensure_dir():
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

def take_screenshot(filename=None):
    ensure_dir()
    if not filename:
        filename = f"screen_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    filepath = os.path.join(SCREENSHOT_DIR, filename)
    ps = f"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$screens = [System.Windows.Forms.Screen]::AllScreens
$bounds = [System.Drawing.Rectangle]::Empty
foreach ($s in $screens) {{ $bounds = [System.Drawing.Rectangle]::Union($bounds, $s.Bounds) }}
$bmp = New-Object System.Drawing.Bitmap($bounds.Width, $bounds.Height)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
$bmp.Save('{filepath.replace(chr(92), "/")}')
$g.Dispose()
$bmp.Dispose()
Write-Output "Saved: {filepath.replace(chr(92), "/")}"
"""
    try:
        r = subprocess.run(["powershell", "-Command", ps],
                          capture_output=True, text=True, timeout=15)
        if r.returncode == 0 and os.path.exists(filepath):
            size_kb = round(os.path.getsize(filepath) / 1024, 1)
            print(f"Screenshot saved: {filepath} ({size_kb} KB)")
            return filepath
        print(f"Screenshot failed: {r.stderr[:200]}")
        return None
    except Exception as e:
        print(f"Screenshot error: {e}")
        return None

def take_window_screenshot(filename=None):
    ensure_dir()
    if not filename:
        filename = f"window_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    filepath = os.path.join(SCREENSHOT_DIR, filename)
    ps = f"""
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.SendKeys]::SendWait('%{{PRTSC}}')
Start-Sleep -Milliseconds 500
$img = [System.Windows.Forms.Clipboard]::GetImage()
if ($img) {{
    $img.Save('{filepath.replace(chr(92), "/")}')
    Write-Output "Window screenshot saved"
}} else {{
    Write-Output "No image in clipboard"
}}
"""
    try:
        r = subprocess.run(["powershell", "-Command", ps],
                          capture_output=True, text=True, timeout=15)
        if os.path.exists(filepath):
            size_kb = round(os.path.getsize(filepath) / 1024, 1)
            print(f"Window screenshot: {filepath} ({size_kb} KB)")
            return filepath
        print(f"Window screenshot failed: {r.stdout} {r.stderr[:200]}")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def list_screenshots():
    ensure_dir()
    files = sorted([f for f in os.listdir(SCREENSHOT_DIR) if f.endswith(".png")], reverse=True)
    total_kb = 0
    print(f"[SCREENSHOTS] {len(files)} files in {SCREENSHOT_DIR}:")
    for f in files[:20]:
        fpath = os.path.join(SCREENSHOT_DIR, f)
        size_kb = round(os.path.getsize(fpath) / 1024, 1)
        total_kb += size_kb
        print(f"  {f} ({size_kb} KB)")
    print(f"  Total: {round(total_kb / 1024, 1)} MB")

def cleanup(keep=10):
    ensure_dir()
    files = sorted([f for f in os.listdir(SCREENSHOT_DIR) if f.endswith(".png")])
    removed = 0
    while len(files) > keep:
        oldest = files.pop(0)
        os.remove(os.path.join(SCREENSHOT_DIR, oldest))
        removed += 1
    print(f"Cleanup: removed {removed} screenshots, kept {len(files)}")

if __name__ == "__main__":
    if "--capture" in sys.argv or "--once" in sys.argv:
        take_screenshot()
    elif "--window" in sys.argv:
        take_window_screenshot()
    elif "--list" in sys.argv:
        list_screenshots()
    elif "--cleanup" in sys.argv:
        keep = 10
        if "--keep" in sys.argv:
            idx = sys.argv.index("--keep")
            keep = int(sys.argv[idx + 1]) if len(sys.argv) > idx + 1 else 10
        cleanup(keep)
    else:
        print("Usage: screenshot_tool.py --capture | --window | --list | --cleanup [--keep N]")
