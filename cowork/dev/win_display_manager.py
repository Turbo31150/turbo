#!/usr/bin/env python3
"""win_display_manager.py — Windows Display Manager with multi-monitor support.
COWORK #219 — Batch 101: Windows Advanced Control

Usage:
    python dev/win_display_manager.py --info
    python dev/win_display_manager.py --resolution 1920x1080
    python dev/win_display_manager.py --brightness 80
    python dev/win_display_manager.py --rotate
    python dev/win_display_manager.py --once
"""
import argparse, json, sqlite3, time, subprocess, os, ctypes, struct
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "display_manager.db"

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS display_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        action TEXT NOT NULL,
        monitor TEXT,
        details TEXT,
        success INTEGER DEFAULT 1
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS display_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        monitors_json TEXT NOT NULL,
        brightness INTEGER,
        total_monitors INTEGER
    )""")
    db.commit()
    return db

def log_event(db, action, monitor=None, details=None, success=1):
    db.execute("INSERT INTO display_events (ts, action, monitor, details, success) VALUES (?,?,?,?,?)",
               (datetime.now().isoformat(), action, monitor, details, success))
    db.commit()

def get_display_info():
    """Get display info using ctypes user32 and powershell."""
    monitors = []
    try:
        user32 = ctypes.windll.user32
        # Get primary monitor resolution
        w = user32.GetSystemMetrics(0)  # SM_CXSCREEN
        h = user32.GetSystemMetrics(1)  # SM_CYSCREEN
        # Virtual screen (all monitors)
        vw = user32.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
        vh = user32.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN
        vx = user32.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
        vy = user32.GetSystemMetrics(77)  # SM_YVIRTUALSCREEN
        num_monitors = user32.GetSystemMetrics(80)  # SM_CMONITORS

        monitors.append({
            "name": "Primary",
            "resolution": f"{w}x{h}",
            "width": w,
            "height": h,
            "primary": True
        })

        # Try EnumDisplayDevices for more detail
        try:
            class DISPLAY_DEVICE(ctypes.Structure):
                _fields_ = [
                    ("cb", ctypes.c_ulong),
                    ("DeviceName", ctypes.c_wchar * 32),
                    ("DeviceString", ctypes.c_wchar * 128),
                    ("StateFlags", ctypes.c_ulong),
                    ("DeviceID", ctypes.c_wchar * 128),
                    ("DeviceKey", ctypes.c_wchar * 128),
                ]

            device = DISPLAY_DEVICE()
            device.cb = ctypes.sizeof(device)
            i = 0
            detected = []
            while user32.EnumDisplayDevicesW(None, i, ctypes.byref(device), 0):
                if device.StateFlags & 0x1:  # DISPLAY_DEVICE_ATTACHED_TO_DESKTOP
                    detected.append({
                        "device_name": device.DeviceName.strip('\x00'),
                        "device_string": device.DeviceString.strip('\x00'),
                        "active": bool(device.StateFlags & 0x1),
                        "primary": bool(device.StateFlags & 0x4),
                    })
                i += 1
            if detected:
                monitors = []
                for idx, dev in enumerate(detected):
                    mon = {
                        "name": dev["device_name"],
                        "adapter": dev["device_string"],
                        "primary": dev["primary"],
                        "index": idx
                    }
                    if idx == 0:
                        mon["resolution"] = f"{w}x{h}"
                        mon["width"] = w
                        mon["height"] = h
                    monitors.append(mon)
        except Exception:
            pass

        result = {
            "monitors": monitors,
            "total_monitors": num_monitors,
            "virtual_screen": {
                "width": vw,
                "height": vh,
                "offset_x": vx,
                "offset_y": vy
            },
            "dpi": get_dpi(),
            "ts": datetime.now().isoformat()
        }
        return result

    except Exception as e:
        return {"error": str(e), "monitors": [], "ts": datetime.now().isoformat()}

def get_dpi():
    """Get system DPI."""
    try:
        user32 = ctypes.windll.user32
        user32.SetProcessDPIAware()
        dc = ctypes.windll.user32.GetDC(0)
        dpi = ctypes.windll.gdi32.GetDeviceCaps(dc, 88)  # LOGPIXELSX
        ctypes.windll.user32.ReleaseDC(0, dc)
        return dpi
    except Exception:
        return 96

def get_brightness():
    """Get brightness via powershell WMI."""
    try:
        cmd = 'powershell -NoProfile -Command "try { (Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness).CurrentBrightness } catch { Write-Output -1 }"'
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10, shell=True)
        val = r.stdout.strip()
        if val and val != "-1":
            return int(val)
        return None
    except Exception:
        return None

def set_brightness(level):
    """Set brightness via powershell WMI."""
    level = max(0, min(100, level))
    try:
        cmd = f'powershell -NoProfile -Command "try {{ (Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods).WmiSetBrightness(1, {level}) ; Write-Output OK }} catch {{ Write-Output FAIL }}"'
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10, shell=True)
        success = "OK" in r.stdout
        return {"action": "set_brightness", "level": level, "success": success, "ts": datetime.now().isoformat()}
    except Exception as e:
        return {"action": "set_brightness", "level": level, "success": False, "error": str(e)}

def set_resolution(res_str):
    """Set resolution via powershell (requires restart or display settings)."""
    try:
        parts = res_str.lower().split("x")
        w, h = int(parts[0]), int(parts[1])
        # Use powershell Set-DisplayResolution or QRes approach
        cmd = f'powershell -NoProfile -Command "Set-DisplayResolution -Width {w} -Height {h} -Force 2>$null; if($?) {{ Write-Output OK }} else {{ Write-Output NOTAVAIL }}"'
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15, shell=True)
        ok = "OK" in r.stdout
        return {
            "action": "set_resolution",
            "requested": res_str,
            "width": w,
            "height": h,
            "success": ok,
            "note": "May require Server edition for Set-DisplayResolution" if not ok else None,
            "ts": datetime.now().isoformat()
        }
    except Exception as e:
        return {"action": "set_resolution", "requested": res_str, "success": False, "error": str(e)}

def rotate_display():
    """Display rotation info (actual rotation requires display settings or registry)."""
    try:
        cmd = 'powershell -NoProfile -Command "Get-CimInstance -ClassName Win32_VideoController | Select-Object Name, VideoModeDescription, CurrentRefreshRate | ConvertTo-Json"'
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10, shell=True)
        info = json.loads(r.stdout) if r.stdout.strip() else {}
        return {
            "action": "rotate_info",
            "video_controllers": info if isinstance(info, list) else [info],
            "note": "Use Settings > Display > Orientation to rotate",
            "ts": datetime.now().isoformat()
        }
    except Exception as e:
        return {"action": "rotate_info", "error": str(e)}

def do_info():
    db = init_db()
    info = get_display_info()
    info["brightness"] = get_brightness()
    log_event(db, "info")
    db.execute("INSERT INTO display_snapshots (ts, monitors_json, brightness, total_monitors) VALUES (?,?,?,?)",
               (datetime.now().isoformat(), json.dumps(info["monitors"]), info.get("brightness"), info.get("total_monitors", 0)))
    db.commit()
    db.close()
    return info

def do_once():
    db = init_db()
    info = get_display_info()
    info["brightness"] = get_brightness()
    # History
    rows = db.execute("SELECT ts, action, monitor, details FROM display_events ORDER BY id DESC LIMIT 10").fetchall()
    info["recent_events"] = [{"ts": r[0], "action": r[1], "monitor": r[2], "details": r[3]} for r in rows]
    total = db.execute("SELECT COUNT(*) FROM display_events").fetchone()[0]
    info["total_events"] = total
    info["status"] = "ok"
    log_event(db, "once_check")
    db.commit()
    db.close()
    return info

def main():
    parser = argparse.ArgumentParser(description="Windows Display Manager — COWORK #219")
    parser.add_argument("--info", action="store_true", help="Show display information")
    parser.add_argument("--resolution", type=str, help="Set resolution WxH (e.g. 1920x1080)")
    parser.add_argument("--brightness", type=int, help="Set brightness 0-100")
    parser.add_argument("--rotate", action="store_true", help="Show rotation info")
    parser.add_argument("--once", action="store_true", help="One-shot status check")
    args = parser.parse_args()

    if args.resolution:
        db = init_db()
        result = set_resolution(args.resolution)
        log_event(db, "set_resolution", details=args.resolution, success=int(result.get("success", False)))
        db.commit(); db.close()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.brightness is not None:
        db = init_db()
        result = set_brightness(args.brightness)
        log_event(db, "set_brightness", details=str(args.brightness), success=int(result.get("success", False)))
        db.commit(); db.close()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.rotate:
        db = init_db()
        result = rotate_display()
        log_event(db, "rotate")
        db.commit(); db.close()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.info:
        print(json.dumps(do_info(), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(do_once(), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
