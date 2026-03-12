#!/usr/bin/env python3
"""win_peripheral_manager.py — #215 Manage peripherals, detect driver issues, track USB.
Usage:
    python dev/win_peripheral_manager.py --scan
    python dev/win_peripheral_manager.py --status
    python dev/win_peripheral_manager.py --drivers
    python dev/win_peripheral_manager.py --problematic
    python dev/win_peripheral_manager.py --once
"""
import argparse, json, sqlite3, time, subprocess, os, re
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "peripheral_manager.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS devices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id TEXT,
        name TEXT NOT NULL,
        category TEXT,
        status TEXT DEFAULT 'OK',
        manufacturer TEXT,
        driver_version TEXT,
        pnp_class TEXT,
        is_usb INTEGER DEFAULT 0,
        first_seen TEXT DEFAULT (datetime('now','localtime')),
        last_seen TEXT DEFAULT (datetime('now','localtime')),
        UNIQUE(device_id)
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS device_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id TEXT,
        event_type TEXT,
        details TEXT,
        ts TEXT DEFAULT (datetime('now','localtime'))
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS problem_devices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id TEXT,
        name TEXT,
        status TEXT,
        error_code TEXT,
        recommendation TEXT,
        first_detected TEXT DEFAULT (datetime('now','localtime')),
        resolved INTEGER DEFAULT 0
    )""")
    db.commit()
    return db


def _run_wmic(query, timeout=15):
    """Run a WMIC query and return parsed results."""
    try:
        cmd = f"wmic {query}"
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return ""


def _run_powershell(command, timeout=20):
    """Run PowerShell command and return JSON."""
    try:
        cmd = ["powershell", "-NoProfile", "-Command", command]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass
    return None


def scan_devices(db):
    """Scan all PnP devices."""
    devices = []

    # Get all PnP entities
    data = _run_powershell(
        "Get-CimInstance -ClassName Win32_PnPEntity | Select-Object DeviceID, Name, Status, Manufacturer, PNPClass | ConvertTo-Json -Compress"
    )

    if data:
        if isinstance(data, dict):
            data = [data]
        for d in data:
            dev_id = d.get("DeviceID", "")
            name = d.get("Name", "Unknown")
            status = d.get("Status", "Unknown")
            manufacturer = d.get("Manufacturer", "")
            pnp_class = d.get("PNPClass", "")
            is_usb = 1 if "USB" in dev_id.upper() else 0

            # Upsert device
            existing = db.execute("SELECT id FROM devices WHERE device_id=?", (dev_id,)).fetchone()
            if existing:
                db.execute(
                    "UPDATE devices SET name=?, status=?, manufacturer=?, pnp_class=?, is_usb=?, last_seen=datetime('now','localtime') WHERE device_id=?",
                    (name, status, manufacturer, pnp_class, is_usb, dev_id)
                )
            else:
                db.execute(
                    "INSERT INTO devices (device_id, name, status, manufacturer, pnp_class, is_usb) VALUES (?,?,?,?,?,?)",
                    (dev_id, name, status, manufacturer, pnp_class, is_usb)
                )
                db.execute(
                    "INSERT INTO device_events (device_id, event_type, details) VALUES (?,?,?)",
                    (dev_id, "first_detected", f"New device: {name}")
                )

            devices.append({
                "name": name, "status": status, "class": pnp_class,
                "usb": bool(is_usb), "manufacturer": manufacturer
            })

    db.commit()

    usb_count = sum(1 for d in devices if d["usb"])
    problem_count = sum(1 for d in devices if d["status"] != "OK")

    return {
        "scanned": True,
        "total_devices": len(devices),
        "usb_devices": usb_count,
        "problem_devices": problem_count,
        "by_class": _count_by_key(devices, "class")
    }


def _count_by_key(items, key):
    """Count items by a key."""
    counts = {}
    for item in items:
        val = item.get(key, "unknown") or "unknown"
        counts[val] = counts.get(val, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True)[:10])


def get_device_status(db):
    """Current device status summary."""
    total = db.execute("SELECT COUNT(*) FROM devices").fetchone()[0]
    usb = db.execute("SELECT COUNT(*) FROM devices WHERE is_usb=1").fetchone()[0]
    ok = db.execute("SELECT COUNT(*) FROM devices WHERE status='OK'").fetchone()[0]
    problem = db.execute("SELECT COUNT(*) FROM devices WHERE status!='OK'").fetchone()[0]

    by_class = db.execute(
        "SELECT pnp_class, COUNT(*) FROM devices GROUP BY pnp_class ORDER BY COUNT(*) DESC LIMIT 10"
    ).fetchall()

    recent_usb = db.execute(
        "SELECT name, manufacturer, last_seen FROM devices WHERE is_usb=1 ORDER BY last_seen DESC LIMIT 5"
    ).fetchall()

    return {
        "total_devices": total,
        "usb_devices": usb,
        "ok_devices": ok,
        "problem_devices": problem,
        "by_class": {c[0] or "unknown": c[1] for c in by_class},
        "recent_usb": [{"name": r[0], "manufacturer": r[1], "last_seen": r[2]} for r in recent_usb]
    }


def check_drivers(db):
    """Check for driver issues."""
    # Get devices with driver info
    data = _run_powershell(
        "Get-CimInstance -ClassName Win32_PnPSignedDriver | Where-Object {$_.DeviceName -ne $null} | Select-Object DeviceName, DriverVersion, DriverDate, IsSigned, Manufacturer | Sort-Object DriverDate | Select-Object -First 20 | ConvertTo-Json -Compress"
    )

    drivers = []
    unsigned = []
    outdated = []

    if data:
        if isinstance(data, dict):
            data = [data]
        for d in data:
            name = d.get("DeviceName", "Unknown")
            version = d.get("DriverVersion", "")
            date_raw = d.get("DriverDate", "")
            signed = d.get("IsSigned", True)
            mfr = d.get("Manufacturer", "")

            entry = {
                "name": name,
                "version": version,
                "date": str(date_raw)[:10] if date_raw else "",
                "signed": signed,
                "manufacturer": mfr
            }
            drivers.append(entry)

            if not signed:
                unsigned.append(entry)

    return {
        "total_drivers_checked": len(drivers),
        "unsigned_drivers": unsigned,
        "unsigned_count": len(unsigned),
        "oldest_drivers": drivers[:10],
        "recommendation": "Update unsigned drivers and those older than 2 years" if unsigned else "All checked drivers are signed"
    }


def get_problematic(db):
    """Get devices with problems."""
    # Query problematic PnP entities
    data = _run_powershell(
        "Get-CimInstance -ClassName Win32_PnPEntity | Where-Object {$_.Status -ne 'OK'} | Select-Object DeviceID, Name, Status, ConfigManagerErrorCode | ConvertTo-Json -Compress"
    )

    problems = []
    error_codes = {
        1: "Not configured correctly",
        3: "Driver corrupted",
        10: "Device cannot start",
        12: "Not enough free resources",
        14: "Restart required",
        18: "Reinstall drivers",
        22: "Device disabled",
        24: "Device not present",
        28: "Drivers not installed",
        31: "Device not working properly",
        43: "Device stopped (reported problem)",
    }

    if data:
        if isinstance(data, dict):
            data = [data]
        for d in data:
            dev_id = d.get("DeviceID", "")
            name = d.get("Name", "Unknown")
            status = d.get("Status", "Error")
            err_code = d.get("ConfigManagerErrorCode", 0)
            recommendation = error_codes.get(err_code, f"Error code {err_code} — check Device Manager")

            problems.append({
                "device_id": dev_id,
                "name": name,
                "status": status,
                "error_code": err_code,
                "recommendation": recommendation
            })

            # Record problem
            existing = db.execute(
                "SELECT id FROM problem_devices WHERE device_id=? AND resolved=0", (dev_id,)
            ).fetchone()
            if not existing:
                db.execute(
                    "INSERT INTO problem_devices (device_id, name, status, error_code, recommendation) VALUES (?,?,?,?,?)",
                    (dev_id, name, status, str(err_code), recommendation)
                )

    db.commit()

    return {
        "problematic_devices": problems,
        "count": len(problems),
        "status": "ISSUES FOUND" if problems else "ALL OK"
    }


def do_status(db):
    total = db.execute("SELECT COUNT(*) FROM devices").fetchone()[0]
    problems = db.execute("SELECT COUNT(*) FROM problem_devices WHERE resolved=0").fetchone()[0]
    usb = db.execute("SELECT COUNT(*) FROM devices WHERE is_usb=1").fetchone()[0]
    return {
        "script": "win_peripheral_manager.py",
        "id": 215,
        "db": str(DB_PATH),
        "total_devices": total,
        "usb_devices": usb,
        "unresolved_problems": problems,
        "ts": datetime.now().isoformat()
    }


def main():
    parser = argparse.ArgumentParser(description="Windows Peripheral Manager — device/driver/USB tracking")
    parser.add_argument("--scan", action="store_true", help="Scan all devices")
    parser.add_argument("--status", action="store_true", help="Device status summary")
    parser.add_argument("--drivers", action="store_true", help="Check drivers")
    parser.add_argument("--problematic", action="store_true", help="List problem devices")
    parser.add_argument("--once", action="store_true", help="Quick status")
    args = parser.parse_args()

    db = init_db()

    if args.scan:
        result = scan_devices(db)
    elif args.status:
        result = get_device_status(db)
    elif args.drivers:
        result = check_drivers(db)
    elif args.problematic:
        result = get_problematic(db)
    else:
        result = do_status(db)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    db.close()


if __name__ == "__main__":
    main()
