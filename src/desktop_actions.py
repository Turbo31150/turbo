"""JARVIS Desktop Actions — Autonomous desktop management functions.

Provides clean_desktop (sort files by extension), move_window_to_next_monitor,
and other desktop automation for voice/autonomous control.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
import shutil
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.desktop_actions")

# Extension → folder mapping for desktop cleanup
EXTENSION_MAP: dict[str, str] = {
    # Images
    ".png": "Images", ".jpg": "Images", ".jpeg": "Images", ".gif": "Images",
    ".bmp": "Images", ".svg": "Images", ".ico": "Images", ".webp": "Images",
    # Documents
    ".pdf": "Documents", ".doc": "Documents", ".docx": "Documents",
    ".xls": "Documents", ".xlsx": "Documents", ".ppt": "Documents",
    ".pptx": "Documents", ".odt": "Documents", ".txt": "Documents",
    ".csv": "Documents", ".rtf": "Documents",
    # Code
    ".py": "Code", ".js": "Code", ".ts": "Code", ".html": "Code",
    ".css": "Code", ".json": "Code", ".yaml": "Code", ".yml": "Code",
    ".md": "Code", ".sh": "Code", ".bat": "Code", ".ps1": "Code",
    # Archives
    ".zip": "Archives", ".rar": "Archives", ".7z": "Archives",
    ".tar": "Archives", ".gz": "Archives",
    # Installers
    ".exe": "Installers", ".msi": "Installers", ".appx": "Installers",
    # Videos
    ".mp4": "Videos", ".mkv": "Videos", ".avi": "Videos", ".mov": "Videos",
    # Audio
    ".mp3": "Audio", ".wav": "Audio", ".ogg": "Audio", ".flac": "Audio",
    # Shortcuts (don't move)
    ".lnk": "_SKIP", ".url": "_SKIP",
}


async def clean_desktop() -> dict[str, Any]:
    """Sort desktop files into subfolders by extension.

    Returns summary of moved files.
    """
    desktop = Path.home() / "Desktop"
    if not desktop.exists():
        # Try OneDrive Desktop
        desktop = Path.home() / "OneDrive" / "Bureau"
        if not desktop.exists():
            desktop = Path.home() / "OneDrive" / "Desktop"
    if not desktop.exists():
        return {"error": "Desktop folder not found"}

    moved: dict[str, int] = {}
    errors: list[str] = []

    for f in desktop.iterdir():
        if f.is_dir():
            continue
        ext = f.suffix.lower()
        folder_name = EXTENSION_MAP.get(ext, "Divers")
        if folder_name == "_SKIP":
            continue

        target_dir = desktop / folder_name
        target_dir.mkdir(exist_ok=True)
        target = target_dir / f.name

        # Avoid overwrite
        if target.exists():
            stem = f.stem
            i = 1
            while target.exists():
                target = target_dir / f"{stem}_{i}{ext}"
                i += 1

        try:
            shutil.move(str(f), str(target))
            moved[folder_name] = moved.get(folder_name, 0) + 1
        except Exception as e:
            errors.append(f"{f.name}: {e}")

    total = sum(moved.values())
    logger.info("Desktop cleanup: %d files moved into %d folders", total, len(moved))
    return {"moved": moved, "total": total, "errors": errors[:5]}


async def move_window_to_next_monitor() -> dict[str, Any]:
    """Move the foreground window to the next monitor using Win32 API."""
    user32 = ctypes.windll.user32

    # Get foreground window
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return {"error": "No foreground window"}

    # Get window title
    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    title = buf.value

    # Get current window rect
    rect = ctypes.wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    win_x, win_y = rect.left, rect.top
    win_w = rect.right - rect.left
    win_h = rect.bottom - rect.top

    # Enumerate monitors
    monitors: list[tuple[int, int, int, int]] = []

    MONITOR_ENUM_PROC = ctypes.WINFUNCTYPE(
        ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong,
        ctypes.POINTER(ctypes.wintypes.RECT), ctypes.c_double
    )

    def enum_callback(hmon, hdc, lprect, lparam):
        r = lprect.contents
        monitors.append((r.left, r.top, r.right - r.left, r.bottom - r.top))
        return 1

    callback = MONITOR_ENUM_PROC(enum_callback)
    user32.EnumDisplayMonitors(None, None, callback, 0)

    if len(monitors) < 2:
        return {"error": "Only one monitor detected", "monitors": len(monitors)}

    # Find which monitor the window is on
    win_cx = win_x + win_w // 2
    win_cy = win_y + win_h // 2
    current_idx = 0
    for i, (mx, my, mw, mh) in enumerate(monitors):
        if mx <= win_cx < mx + mw and my <= win_cy < my + mh:
            current_idx = i
            break

    # Move to next monitor
    next_idx = (current_idx + 1) % len(monitors)
    nx, ny, nw, nh = monitors[next_idx]

    # Calculate relative position on new monitor
    cx, cy, cw, ch = monitors[current_idx]
    rel_x = (win_x - cx) / max(cw, 1)
    rel_y = (win_y - cy) / max(ch, 1)
    new_x = int(nx + rel_x * nw)
    new_y = int(ny + rel_y * nh)

    # Move window
    user32.MoveWindow(hwnd, new_x, new_y, win_w, win_h, True)

    logger.info("Moved '%s' from monitor %d to %d", title[:30], current_idx, next_idx)
    return {
        "window": title[:50],
        "from_monitor": current_idx,
        "to_monitor": next_idx,
        "position": {"x": new_x, "y": new_y},
    }


async def snap_window(direction: str = "left") -> dict[str, Any]:
    """Snap foreground window left/right using keyboard simulation."""
    import subprocess
    if direction == "left":
        key = "{LEFT}"
    elif direction == "right":
        key = "{RIGHT}"
    else:
        return {"error": f"Unknown direction: {direction}"}

    # Use PowerShell to send Win+Arrow
    cmd = f"""
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.SendKeys]::SendWait("^{{ESC}}")
    Start-Sleep -Milliseconds 50
    $wsh = New-Object -ComObject WScript.Shell
    $wsh.SendKeys("^{{ESC}}")
    """
    # Simpler approach: direct keybd_event
    user32 = ctypes.windll.user32
    VK_LWIN = 0x5B
    VK_LEFT = 0x25
    VK_RIGHT = 0x27

    vk = VK_LEFT if direction == "left" else VK_RIGHT

    user32.keybd_event(VK_LWIN, 0, 0, 0)  # Win down
    user32.keybd_event(vk, 0, 0, 0)        # Arrow down
    user32.keybd_event(vk, 0, 2, 0)        # Arrow up
    user32.keybd_event(VK_LWIN, 0, 2, 0)  # Win up

    return {"snapped": direction}
