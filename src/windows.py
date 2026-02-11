"""JARVIS Windows System Integration — Complete Windows automation toolkit.

All Windows interactions for JARVIS: apps, windows, files, clipboard,
keyboard, mouse, audio, network, services, registry, screen, browser.
"""

from __future__ import annotations

import json
import subprocess
from typing import Any


# ═══════════════════════════════════════════════════════════════════════════
# CORE — PowerShell execution
# ═══════════════════════════════════════════════════════════════════════════

def run_powershell(command: str, timeout: int = 60) -> dict[str, Any]:
    """Execute a PowerShell command and return structured output."""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True, text=True, timeout=timeout,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "stdout": "", "stderr": "Timeout", "exit_code": -1}
    except Exception as e:
        return {"success": False, "stdout": "", "stderr": str(e), "exit_code": -1}


def _ps(cmd: str, timeout: int = 15) -> str:
    """Quick PowerShell command, returns stdout or error string."""
    r = run_powershell(cmd, timeout)
    return r["stdout"] if r["success"] else f"ERREUR: {r['stderr']}"


def _ps_json(cmd: str, timeout: int = 15) -> Any:
    """PowerShell command that returns parsed JSON."""
    r = run_powershell(cmd + " | ConvertTo-Json -Depth 3 -Compress", timeout)
    if r["success"] and r["stdout"]:
        try:
            data = json.loads(r["stdout"])
            return data
        except json.JSONDecodeError:
            return r["stdout"]
    return None


# ═══════════════════════════════════════════════════════════════════════════
# SYSTEM INFO
# ═══════════════════════════════════════════════════════════════════════════

def get_system_info() -> dict[str, str]:
    """Get system info in pure Python — no PowerShell, no blocking."""
    import platform
    import os
    import ctypes

    info = {
        "hostname": platform.node(),
        "os_version": platform.platform(),
        "cpu": platform.processor(),
        "user": os.environ.get("USERNAME", "unknown"),
    }

    # RAM via ctypes (fast, no subprocess)
    try:
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]
        mem = MEMORYSTATUSEX()
        mem.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
        total_gb = round(mem.ullTotalPhys / (1024**3), 1)
        avail_gb = round(mem.ullAvailPhys / (1024**3), 1)
        info["ram_total_gb"] = str(total_gb)
        info["ram_available_gb"] = str(avail_gb)
        info["ram_usage_pct"] = str(mem.dwMemoryLoad)
    except Exception:
        info["ram"] = "unknown"

    # Disk free via ctypes (fast)
    try:
        disks = []
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for i, letter in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
            if bitmask & (1 << i):
                free = ctypes.c_ulonglong(0)
                total = ctypes.c_ulonglong(0)
                if ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                    f"{letter}:\\", None, ctypes.byref(total), ctypes.byref(free)
                ):
                    free_gb = round(free.value / (1024**3), 1)
                    total_gb = round(total.value / (1024**3), 1)
                    disks.append(f"{letter}: {free_gb}/{total_gb}GB free")
        info["disks"] = "; ".join(disks)
    except Exception:
        info["disks"] = "unknown"

    # GPU via quick PowerShell (single command, fast)
    info["gpu"] = _ps("(Get-CimInstance Win32_VideoController).Name -join ', '", timeout=5)

    return info


def get_gpu_info() -> str:
    """Get detailed GPU information."""
    return _ps(
        "Get-CimInstance Win32_VideoController | "
        "ForEach-Object { $_.Name + ' | VRAM: ' + [math]::Round($_.AdapterRAM/1GB,1).ToString() + 'GB | Driver: ' + $_.DriverVersion } | "
        "Out-String"
    )


def get_network_info() -> str:
    """Get network adapter info and IP addresses."""
    return _ps(
        "Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -ne '127.0.0.1' } | "
        "Select-Object InterfaceAlias, IPAddress | Format-Table -AutoSize | Out-String"
    )


# ═══════════════════════════════════════════════════════════════════════════
# APPLICATIONS — Open, close, manage
# ═══════════════════════════════════════════════════════════════════════════

def open_application(name: str, args: str = "") -> str:
    """Open an application by name or path."""
    if args:
        return _ps(f"Start-Process '{name}' -ArgumentList '{args}' -ErrorAction SilentlyContinue; 'OK'")
    return _ps(f"Start-Process '{name}' -ErrorAction SilentlyContinue; 'OK'")


def close_application(name: str) -> str:
    """Close an application by process name."""
    return _ps(f"Stop-Process -Name '{name}' -Force -ErrorAction SilentlyContinue; 'Ferme: {name}'")


def open_url(url: str, browser: str = "chrome") -> str:
    """Open a URL in the specified browser."""
    return _ps(f"Start-Process '{browser}' '{url}' -ErrorAction SilentlyContinue; 'OK'")


def list_installed_apps(filter_name: str = "") -> str:
    """List installed applications."""
    cmd = "Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* | Select-Object DisplayName, DisplayVersion | Where-Object { $_.DisplayName -ne $null }"
    if filter_name:
        cmd += f" | Where-Object {{ $_.DisplayName -match '{filter_name}' }}"
    cmd += " | Select-Object -First 30 | Format-Table -AutoSize | Out-String"
    return _ps(cmd, timeout=20)


# ═══════════════════════════════════════════════════════════════════════════
# PROCESSES
# ═══════════════════════════════════════════════════════════════════════════

def list_processes(filter_name: str | None = None) -> list[dict[str, Any]]:
    """List running processes, optionally filtered."""
    cmd = "Get-Process"
    if filter_name:
        cmd += f" -Name '*{filter_name}*' -ErrorAction SilentlyContinue"
    cmd += " | Select-Object -First 50 Name, Id, CPU, WorkingSet64"
    data = _ps_json(cmd)
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return data
    return []


def kill_process(name_or_pid: str) -> str:
    """Stop a process by name or PID."""
    if name_or_pid.isdigit():
        return _ps(f"Stop-Process -Id {name_or_pid} -Force -ErrorAction SilentlyContinue; 'Processus {name_or_pid} arrete'")
    return _ps(f"Stop-Process -Name '{name_or_pid}' -Force -ErrorAction SilentlyContinue; '{name_or_pid} arrete'")


# ═══════════════════════════════════════════════════════════════════════════
# WINDOWS — Manage windows (minimize, maximize, focus, list)
# ═══════════════════════════════════════════════════════════════════════════

def list_windows() -> str:
    """List all visible windows with their titles."""
    return _ps(
        "Get-Process | Where-Object { $_.MainWindowTitle -ne '' } | "
        "Select-Object Id, ProcessName, MainWindowTitle | Format-Table -AutoSize | Out-String"
    )


def focus_window(title_part: str) -> str:
    """Bring a window to front by partial title match."""
    return _ps(
        f"Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; "
        f"public class Win {{ [DllImport(\"user32.dll\")] public static extern bool SetForegroundWindow(IntPtr hWnd); }}'; "
        f"$p = Get-Process | Where-Object {{ $_.MainWindowTitle -match \"{title_part}\" }} | Select-Object -First 1; "
        f"if ($p) {{ [Win]::SetForegroundWindow($p.MainWindowHandle); 'Focus: ' + $p.MainWindowTitle }} else {{ 'Fenetre non trouvee' }}"
    )


def minimize_window(title_part: str) -> str:
    """Minimize a window by partial title match."""
    return _ps(
        f"Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; "
        f"public class Win {{ [DllImport(\"user32.dll\")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow); }}'; "
        f"$p = Get-Process | Where-Object {{ $_.MainWindowTitle -match \"{title_part}\" }} | Select-Object -First 1; "
        f"if ($p) {{ [Win]::ShowWindow($p.MainWindowHandle, 6); 'Minimise' }} else {{ 'Non trouve' }}"
    )


def maximize_window(title_part: str) -> str:
    """Maximize a window by partial title match."""
    return _ps(
        f"Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; "
        f"public class Win {{ [DllImport(\"user32.dll\")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow); }}'; "
        f"$p = Get-Process | Where-Object {{ $_.MainWindowTitle -match \"{title_part}\" }} | Select-Object -First 1; "
        f"if ($p) {{ [Win]::ShowWindow($p.MainWindowHandle, 3); 'Maximise' }} else {{ 'Non trouve' }}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# KEYBOARD & MOUSE — Simulate input
# ═══════════════════════════════════════════════════════════════════════════

def send_keys(keys: str) -> str:
    """Send keyboard input to the active window. Uses SendKeys syntax."""
    return _ps(
        f"Add-Type -AssemblyName System.Windows.Forms; "
        f"[System.Windows.Forms.SendKeys]::SendWait('{keys}'); 'Touches envoyees'"
    )


def type_text(text: str) -> str:
    """Type text into the active window character by character."""
    safe = text.replace("'", "''")
    return _ps(
        f"Add-Type -AssemblyName System.Windows.Forms; "
        f"[System.Windows.Forms.SendKeys]::SendWait('{safe}'); 'Texte tape'"
    )


def press_hotkey(keys: str) -> str:
    """Press a keyboard shortcut (e.g. 'ctrl+c', 'alt+tab', 'win+d')."""
    # Map key names to SendKeys syntax
    key_map = {
        "ctrl": "^", "alt": "%", "shift": "+", "win": "^{ESC}",
        "enter": "{ENTER}", "tab": "{TAB}", "esc": "{ESC}",
        "space": " ", "backspace": "{BACKSPACE}", "delete": "{DELETE}",
        "up": "{UP}", "down": "{DOWN}", "left": "{LEFT}", "right": "{RIGHT}",
        "home": "{HOME}", "end": "{END}", "pageup": "{PGUP}", "pagedown": "{PGDN}",
        "f1": "{F1}", "f2": "{F2}", "f3": "{F3}", "f4": "{F4}", "f5": "{F5}",
        "f6": "{F6}", "f7": "{F7}", "f8": "{F8}", "f9": "{F9}", "f10": "{F10}",
        "f11": "{F11}", "f12": "{F12}",
    }
    parts = keys.lower().split("+")
    sendkeys_str = ""
    for part in parts:
        part = part.strip()
        sendkeys_str += key_map.get(part, part)
    return _ps(
        f"Add-Type -AssemblyName System.Windows.Forms; "
        f"[System.Windows.Forms.SendKeys]::SendWait('{sendkeys_str}'); 'Raccourci: {keys}'"
    )


def mouse_click(x: int, y: int, button: str = "left") -> str:
    """Click at screen coordinates."""
    return _ps(
        f"Add-Type -TypeDefinition '"
        f"using System; using System.Runtime.InteropServices; "
        f"public class Mouse {{ "
        f"[DllImport(\"user32.dll\")] public static extern bool SetCursorPos(int X, int Y); "
        f"[DllImport(\"user32.dll\")] public static extern void mouse_event(uint dwFlags, int dx, int dy, uint dwData, int dwExtraInfo); "
        f"}}'; "
        f"[Mouse]::SetCursorPos({x}, {y}); Start-Sleep -Milliseconds 100; "
        f"[Mouse]::mouse_event(0x0002, 0, 0, 0, 0); [Mouse]::mouse_event(0x0004, 0, 0, 0, 0); "
        f"'Click ({x},{y})'"
    )


# ═══════════════════════════════════════════════════════════════════════════
# CLIPBOARD
# ═══════════════════════════════════════════════════════════════════════════

def clipboard_get() -> str:
    """Get clipboard text content."""
    return _ps("Get-Clipboard")


def clipboard_set(text: str) -> str:
    """Set clipboard text content."""
    safe = text.replace("'", "''")
    return _ps(f"Set-Clipboard -Value '{safe}'; 'Clipboard mis a jour'")


# ═══════════════════════════════════════════════════════════════════════════
# FILES & FOLDERS
# ═══════════════════════════════════════════════════════════════════════════

def open_folder(path: str) -> str:
    """Open a folder in Explorer."""
    return _ps(f"Start-Process explorer.exe -ArgumentList '{path}'; 'Dossier ouvert: {path}'")


def list_folder(path: str, pattern: str = "*") -> str:
    """List contents of a folder."""
    return _ps(
        f"Get-ChildItem '{path}' -Filter '{pattern}' | "
        f"Select-Object Mode, LastWriteTime, Length, Name | Format-Table -AutoSize | Out-String",
        timeout=10
    )


def create_folder(path: str) -> str:
    """Create a new folder."""
    return _ps(f"New-Item -ItemType Directory -Force -Path '{path}' | Select-Object FullName | Out-String")


def copy_item(source: str, dest: str) -> str:
    """Copy a file or folder."""
    return _ps(f"Copy-Item '{source}' '{dest}' -Recurse -Force; 'Copie OK: {source} -> {dest}'")


def move_item(source: str, dest: str) -> str:
    """Move a file or folder."""
    return _ps(f"Move-Item '{source}' '{dest}' -Force; 'Deplacement OK: {source} -> {dest}'")


def delete_item(path: str) -> str:
    """Delete a file or folder (to recycle bin)."""
    return _ps(
        f"Add-Type -AssemblyName Microsoft.VisualBasic; "
        f"[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile('{path}', "
        f"'UIOption.OnlyErrorDialogs', 'RecycleOption.SendToRecycleBin'); "
        f"'Supprime (corbeille): {path}'"
    )


def read_file(path: str, lines: int = 50) -> str:
    """Read text file content."""
    return _ps(f"Get-Content '{path}' -TotalCount {lines} -ErrorAction SilentlyContinue | Out-String")


def write_file(path: str, content: str) -> str:
    """Write text content to a file."""
    safe = content.replace("'", "''")
    return _ps(f"Set-Content '{path}' -Value '{safe}'; 'Ecrit: {path}'")


def search_files(path: str, pattern: str) -> str:
    """Search for files recursively."""
    return _ps(
        f"Get-ChildItem '{path}' -Recurse -Filter '{pattern}' -ErrorAction SilentlyContinue | "
        f"Select-Object -First 20 FullName | Out-String",
        timeout=30
    )


# ═══════════════════════════════════════════════════════════════════════════
# AUDIO
# ═══════════════════════════════════════════════════════════════════════════

def volume_up() -> str:
    """Increase system volume."""
    return _ps("(New-Object -ComObject WScript.Shell).SendKeys([char]175); 'Volume augmente'")


def volume_down() -> str:
    """Decrease system volume."""
    return _ps("(New-Object -ComObject WScript.Shell).SendKeys([char]174); 'Volume baisse'")


def volume_mute() -> str:
    """Toggle mute."""
    return _ps("(New-Object -ComObject WScript.Shell).SendKeys([char]173); 'Mute bascule'")


# ═══════════════════════════════════════════════════════════════════════════
# SCREEN
# ═══════════════════════════════════════════════════════════════════════════

def screenshot(filename: str = "") -> str:
    """Take a screenshot and save to Desktop."""
    if not filename:
        filename = "capture_$(Get-Date -Format 'yyyyMMdd_HHmmss').png"
    return _ps(
        f"Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing; "
        f"$screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; "
        f"$bmp = New-Object System.Drawing.Bitmap($screen.Width, $screen.Height); "
        f"$g = [System.Drawing.Graphics]::FromImage($bmp); "
        f"$g.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size); "
        f"$path = [Environment]::GetFolderPath('Desktop') + '\\{filename}'; "
        f"$bmp.Save($path); $path"
    )


def get_screen_resolution() -> str:
    """Get current screen resolution."""
    return _ps(
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$s = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; "
        "'Resolution: ' + $s.Width.ToString() + 'x' + $s.Height.ToString()"
    )


# ═══════════════════════════════════════════════════════════════════════════
# SERVICES
# ═══════════════════════════════════════════════════════════════════════════

def check_service(name: str) -> dict[str, str]:
    """Check a Windows service status."""
    data = _ps_json(f"Get-Service -Name '{name}' -ErrorAction SilentlyContinue | Select-Object Name, Status, DisplayName")
    if isinstance(data, dict):
        return data
    return {"Name": name, "Status": "Unknown"}


def list_services(filter_name: str = "") -> str:
    """List Windows services."""
    cmd = "Get-Service"
    if filter_name:
        cmd += f" -Name '*{filter_name}*' -ErrorAction SilentlyContinue"
    cmd += " | Select-Object -First 30 Status, Name, DisplayName | Format-Table -AutoSize | Out-String"
    return _ps(cmd)


def start_service(name: str) -> str:
    """Start a Windows service."""
    return _ps(f"Start-Service '{name}' -ErrorAction SilentlyContinue; 'Service {name} demarre'")


def stop_service(name: str) -> str:
    """Stop a Windows service."""
    return _ps(f"Stop-Service '{name}' -Force -ErrorAction SilentlyContinue; 'Service {name} arrete'")


# ═══════════════════════════════════════════════════════════════════════════
# SYSTEM CONTROL
# ═══════════════════════════════════════════════════════════════════════════

def lock_screen() -> str:
    """Lock the workstation."""
    return _ps("rundll32.exe user32.dll,LockWorkStation; 'Ecran verrouille'")


def shutdown_pc() -> str:
    """Shutdown the computer."""
    return _ps("Stop-Computer -Force; 'Extinction en cours'")


def restart_pc() -> str:
    """Restart the computer."""
    return _ps("Restart-Computer -Force; 'Redemarrage en cours'")


def sleep_pc() -> str:
    """Put the computer to sleep."""
    return _ps(
        "Add-Type -AssemblyName System.Windows.Forms; "
        "[System.Windows.Forms.Application]::SetSuspendState('Suspend', $false, $false); 'Mise en veille'"
    )


# ═══════════════════════════════════════════════════════════════════════════
# NOTIFICATIONS
# ═══════════════════════════════════════════════════════════════════════════

def notify_windows(title: str, message: str) -> bool:
    """Show a Windows toast notification."""
    safe_title = title.replace("'", "''")
    safe_msg = message.replace("'", "''")
    r = run_powershell(
        f"[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
        f"ContentType = WindowsRuntime] > $null; "
        f"$t = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent("
        f"[Windows.UI.Notifications.ToastTemplateType]::ToastText02); "
        f"$t.GetElementsByTagName('text')[0].AppendChild($t.CreateTextNode('{safe_title}')) > $null; "
        f"$t.GetElementsByTagName('text')[1].AppendChild($t.CreateTextNode('{safe_msg}')) > $null; "
        f"$n = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('JARVIS'); "
        f"$n.Show([Windows.UI.Notifications.ToastNotification]::new($t)); 'OK'",
        timeout=10
    )
    return r["success"]


# ═══════════════════════════════════════════════════════════════════════════
# WIFI & NETWORK
# ═══════════════════════════════════════════════════════════════════════════

def get_wifi_networks() -> str:
    """List available WiFi networks."""
    return _ps("netsh wlan show networks mode=bssid | Out-String", timeout=10)


def get_ip_address() -> str:
    """Get current IP addresses."""
    return _ps(
        "Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -ne '127.0.0.1' } | "
        "ForEach-Object { $_.InterfaceAlias + ': ' + $_.IPAddress } | Out-String"
    )


def ping_host(host: str) -> str:
    """Ping a host."""
    return _ps(f"Test-Connection '{host}' -Count 2 -ErrorAction SilentlyContinue | Select-Object Address, ResponseTime | Format-Table | Out-String", timeout=15)


# ═══════════════════════════════════════════════════════════════════════════
# REGISTRY
# ═══════════════════════════════════════════════════════════════════════════

def registry_get(path: str, name: str = "") -> str:
    """Read a registry value."""
    if name:
        return _ps(f"Get-ItemPropertyValue '{path}' -Name '{name}' -ErrorAction SilentlyContinue")
    return _ps(f"Get-ItemProperty '{path}' -ErrorAction SilentlyContinue | Out-String")


def registry_set(path: str, name: str, value: str, reg_type: str = "String") -> str:
    """Set a registry value."""
    return _ps(
        f"Set-ItemProperty '{path}' -Name '{name}' -Value '{value}' -Type {reg_type} "
        f"-ErrorAction SilentlyContinue; 'Registry mis a jour: {path}\\{name}'"
    )


# ═══════════════════════════════════════════════════════════════════════════
# SCHEDULED TASKS
# ═══════════════════════════════════════════════════════════════════════════

def list_scheduled_tasks(filter_name: str = "") -> str:
    """List scheduled tasks."""
    cmd = "Get-ScheduledTask"
    if filter_name:
        cmd += f" | Where-Object {{ $_.TaskName -match '{filter_name}' }}"
    cmd += " | Select-Object -First 20 State, TaskName | Format-Table -AutoSize | Out-String"
    return _ps(cmd, timeout=15)


# ═══════════════════════════════════════════════════════════════════════════
# ACCESSIBILITY
# ═══════════════════════════════════════════════════════════════════════════

def check_accessibility() -> dict[str, Any]:
    """Check Windows accessibility features status."""
    checks = {}
    items = {
        "narrator": "(Get-Process Narrator -ErrorAction SilentlyContinue) -ne $null",
        "magnifier": "(Get-Process Magnify -ErrorAction SilentlyContinue) -ne $null",
        "speech_recognition": "(Get-Process SpeechRuntime -ErrorAction SilentlyContinue) -ne $null",
    }
    for key, cmd in items.items():
        checks[key] = _ps(cmd, timeout=5)
    return checks


def toggle_narrator(enable: bool = True) -> str:
    """Enable/disable Windows Narrator."""
    if enable:
        return _ps("Start-Process narrator; 'Narrateur active'")
    return _ps("Stop-Process -Name Narrator -Force -ErrorAction SilentlyContinue; 'Narrateur desactive'")
