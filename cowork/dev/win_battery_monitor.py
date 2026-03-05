#!/usr/bin/env python3
"""win_battery_monitor.py — #214 Monitor battery/PSU health on Windows.
Usage:
    python dev/win_battery_monitor.py --status
    python dev/win_battery_monitor.py --health
    python dev/win_battery_monitor.py --history
    python dev/win_battery_monitor.py --alert
    python dev/win_battery_monitor.py --once
"""
import argparse, json, sqlite3, time, subprocess, os, re
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "battery_monitor.db"
ALERT_THRESHOLD = 20  # percent


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS readings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        is_laptop INTEGER DEFAULT 0,
        battery_present INTEGER DEFAULT 0,
        charge_pct REAL,
        status TEXT,
        estimated_runtime_min REAL,
        voltage_mv REAL,
        design_capacity_mwh REAL,
        full_charge_mwh REAL,
        health_pct REAL,
        power_source TEXT DEFAULT 'AC',
        ts TEXT DEFAULT (datetime('now','localtime'))
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        alert_type TEXT,
        message TEXT,
        charge_pct REAL,
        ts TEXT DEFAULT (datetime('now','localtime'))
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS power_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT,
        details TEXT,
        ts TEXT DEFAULT (datetime('now','localtime'))
    )""")
    db.commit()
    return db


def _get_battery_info():
    """Get battery info via PowerShell Get-CimInstance."""
    info = {
        "is_laptop": False,
        "battery_present": False,
        "charge_pct": None,
        "status": "unknown",
        "estimated_runtime_min": None,
        "voltage_mv": None,
        "design_capacity_mwh": None,
        "full_charge_mwh": None,
        "health_pct": None,
        "power_source": "AC"
    }

    try:
        # Try Win32_Battery
        cmd = [
            "powershell", "-NoProfile", "-Command",
            "Get-CimInstance -ClassName Win32_Battery | Select-Object -Property * | ConvertTo-Json"
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            if isinstance(data, list):
                data = data[0] if data else {}
            if data:
                info["is_laptop"] = True
                info["battery_present"] = True
                info["charge_pct"] = data.get("EstimatedChargeRemaining")
                info["estimated_runtime_min"] = data.get("EstimatedRunTime")
                info["voltage_mv"] = data.get("DesignVoltage")

                # Battery status codes
                status_map = {1: "Discharging", 2: "AC Power", 3: "Fully Charged",
                              4: "Low", 5: "Critical", 6: "Charging", 7: "Charging+High",
                              8: "Charging+Low", 9: "Charging+Critical"}
                info["status"] = status_map.get(data.get("BatteryStatus"), "Unknown")
                info["power_source"] = "Battery" if data.get("BatteryStatus") == 1 else "AC"
        else:
            info["is_laptop"] = False
            info["power_source"] = "AC (Desktop)"

    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        pass

    # Try to get battery health via powercfg
    if info["is_laptop"]:
        try:
            cmd = [
                "powershell", "-NoProfile", "-Command",
                "Get-CimInstance -ClassName BatteryFullChargedCapacity -Namespace root\\wmi 2>$null | Select-Object FullChargedCapacity | ConvertTo-Json"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            if result.returncode == 0 and result.stdout.strip():
                fcc = json.loads(result.stdout)
                if isinstance(fcc, list):
                    fcc = fcc[0] if fcc else {}
                info["full_charge_mwh"] = fcc.get("FullChargedCapacity")
        except Exception:
            pass

        try:
            cmd = [
                "powershell", "-NoProfile", "-Command",
                "Get-CimInstance -ClassName BatteryStaticData -Namespace root\\wmi 2>$null | Select-Object DesignedCapacity | ConvertTo-Json"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            if result.returncode == 0 and result.stdout.strip():
                dc = json.loads(result.stdout)
                if isinstance(dc, list):
                    dc = dc[0] if dc else {}
                info["design_capacity_mwh"] = dc.get("DesignedCapacity")
        except Exception:
            pass

        if info["design_capacity_mwh"] and info["full_charge_mwh"] and info["design_capacity_mwh"] > 0:
            info["health_pct"] = round(info["full_charge_mwh"] / info["design_capacity_mwh"] * 100, 1)

    return info


def _get_ups_status():
    """Check UPS status for desktop systems."""
    try:
        cmd = [
            "powershell", "-NoProfile", "-Command",
            "Get-CimInstance -ClassName Win32_Battery | Where-Object {$_.Chemistry -eq 'UPS'} | ConvertTo-Json"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            return {"ups_detected": True, "data": data}
    except Exception:
        pass
    return {"ups_detected": False}


def get_status(db):
    """Get current battery/power status."""
    info = _get_battery_info()

    # Record reading
    db.execute(
        "INSERT INTO readings (is_laptop, battery_present, charge_pct, status, estimated_runtime_min, voltage_mv, design_capacity_mwh, full_charge_mwh, health_pct, power_source) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (int(info["is_laptop"]), int(info["battery_present"]), info["charge_pct"],
         info["status"], info["estimated_runtime_min"], info["voltage_mv"],
         info["design_capacity_mwh"], info["full_charge_mwh"], info["health_pct"],
         info["power_source"])
    )
    db.commit()

    if not info["is_laptop"]:
        ups = _get_ups_status()
        info["ups"] = ups
        info["note"] = "Desktop system detected — no battery. Monitoring PSU/UPS status."

    return info


def get_health(db):
    """Battery health analysis."""
    info = _get_battery_info()
    history = db.execute(
        "SELECT health_pct, ts FROM readings WHERE health_pct IS NOT NULL ORDER BY id DESC LIMIT 30"
    ).fetchall()

    result = {
        "current_health_pct": info.get("health_pct"),
        "design_capacity_mwh": info.get("design_capacity_mwh"),
        "full_charge_mwh": info.get("full_charge_mwh"),
        "is_laptop": info["is_laptop"]
    }

    if history:
        health_values = [h[0] for h in history if h[0] is not None]
        if health_values:
            result["avg_health"] = round(sum(health_values) / len(health_values), 1)
            result["min_health"] = min(health_values)
            result["max_health"] = max(health_values)
            if health_values[-1] and health_values[0]:
                result["trend"] = "declining" if health_values[-1] < health_values[0] else "stable"

    if not info["is_laptop"]:
        result["note"] = "Desktop — battery health N/A. Run powercfg /batteryreport on laptops."

    result["recommendations"] = []
    if info.get("health_pct") and info["health_pct"] < 50:
        result["recommendations"].append("Battery health below 50% — consider replacement")
    elif info.get("health_pct") and info["health_pct"] < 80:
        result["recommendations"].append("Battery health declining — avoid full discharges")

    return result


def get_history(db, limit=50):
    """Reading history."""
    rows = db.execute(
        "SELECT charge_pct, status, power_source, health_pct, ts FROM readings ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    return {
        "history": [
            {"charge_pct": r[0], "status": r[1], "source": r[2], "health": r[3], "ts": r[4]}
            for r in rows
        ],
        "total_readings": db.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
    }


def check_alerts(db):
    """Check for low battery alerts."""
    info = _get_battery_info()
    alerts = []

    if info["battery_present"] and info["charge_pct"] is not None:
        if info["charge_pct"] <= ALERT_THRESHOLD:
            alert_msg = f"Low battery: {info['charge_pct']}% (threshold: {ALERT_THRESHOLD}%)"
            alerts.append({"type": "low_battery", "message": alert_msg, "charge": info["charge_pct"]})
            db.execute(
                "INSERT INTO alerts (alert_type, message, charge_pct) VALUES (?,?,?)",
                ("low_battery", alert_msg, info["charge_pct"])
            )

        if info.get("health_pct") and info["health_pct"] < 50:
            alert_msg = f"Battery health critical: {info['health_pct']}%"
            alerts.append({"type": "health_critical", "message": alert_msg})
            db.execute(
                "INSERT INTO alerts (alert_type, message, charge_pct) VALUES (?,?,?)",
                ("health_critical", alert_msg, info["health_pct"])
            )

    db.commit()

    past_alerts = db.execute(
        "SELECT alert_type, message, charge_pct, ts FROM alerts ORDER BY id DESC LIMIT 10"
    ).fetchall()

    return {
        "current_alerts": alerts,
        "past_alerts": [{"type": a[0], "message": a[1], "charge": a[2], "ts": a[3]} for a in past_alerts],
        "alert_threshold": ALERT_THRESHOLD
    }


def do_status(db):
    info = _get_battery_info()
    total = db.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
    return {
        "script": "win_battery_monitor.py",
        "id": 214,
        "db": str(DB_PATH),
        "is_laptop": info["is_laptop"],
        "battery_present": info["battery_present"],
        "charge_pct": info["charge_pct"],
        "power_source": info["power_source"],
        "health_pct": info.get("health_pct"),
        "total_readings": total,
        "alert_threshold": ALERT_THRESHOLD,
        "ts": datetime.now().isoformat()
    }


def main():
    parser = argparse.ArgumentParser(description="Windows Battery/PSU Monitor — health and alerts")
    parser.add_argument("--status", action="store_true", help="Current battery/power status")
    parser.add_argument("--health", action="store_true", help="Battery health analysis")
    parser.add_argument("--history", action="store_true", help="Reading history")
    parser.add_argument("--alert", action="store_true", help="Check for alerts")
    parser.add_argument("--once", action="store_true", help="Quick status")
    args = parser.parse_args()

    db = init_db()

    if args.status:
        result = get_status(db)
    elif args.health:
        result = get_health(db)
    elif args.history:
        result = get_history(db)
    elif args.alert:
        result = check_alerts(db)
    else:
        result = do_status(db)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    db.close()


if __name__ == "__main__":
    main()
