#!/usr/bin/env python3
"""win_printer_manager.py — Windows printer manager with queue control.
COWORK #229 — Batch 104: Windows Maintenance Pro

Usage:
    python dev/win_printer_manager.py --list
    python dev/win_printer_manager.py --status
    python dev/win_printer_manager.py --default "HP LaserJet"
    python dev/win_printer_manager.py --queue
    python dev/win_printer_manager.py --once
"""
import argparse, json, sqlite3, time, subprocess, os
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "printer_manager.db"

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS printer_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        action TEXT NOT NULL,
        printer TEXT,
        details TEXT,
        success INTEGER DEFAULT 1
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS printer_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        printers_json TEXT NOT NULL,
        total_printers INTEGER,
        default_printer TEXT
    )""")
    db.commit()
    return db

def log_event(db, action, printer=None, details=None, success=1):
    db.execute("INSERT INTO printer_events (ts, action, printer, details, success) VALUES (?,?,?,?,?)",
               (datetime.now().isoformat(), action, printer, details, success))
    db.commit()

def get_printers():
    """Get printer list via powershell."""
    try:
        cmd = 'powershell -NoProfile -Command "Get-Printer | Select-Object Name, PrinterStatus, Type, DriverName, PortName, Shared, Published | ConvertTo-Json"'
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15, shell=True)
        if r.stdout.strip():
            data = json.loads(r.stdout)
            if isinstance(data, dict):
                data = [data]
            printers = []
            for p in data:
                status_code = p.get("PrinterStatus", 0)
                status_map = {0: "Normal", 1: "Paused", 2: "Error", 3: "Deleting",
                              4: "PaperJam", 5: "PaperOut", 6: "ManualFeed", 7: "Offline"}
                printers.append({
                    "name": p.get("Name", ""),
                    "status": status_map.get(status_code, f"Unknown({status_code})"),
                    "status_code": status_code,
                    "type": str(p.get("Type", "")),
                    "driver": p.get("DriverName", ""),
                    "port": p.get("PortName", ""),
                    "shared": p.get("Shared", False),
                })
            return printers
        return []
    except Exception as e:
        return [{"error": str(e)}]

def get_default_printer():
    """Get default printer."""
    try:
        cmd = 'powershell -NoProfile -Command "(Get-CimInstance -ClassName Win32_Printer | Where-Object {$_.Default -eq $true}).Name"'
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10, shell=True)
        return r.stdout.strip() or None
    except Exception:
        return None

def get_print_queue():
    """Get print queue for all printers."""
    try:
        cmd = 'powershell -NoProfile -Command "Get-PrintJob -PrinterName * -ErrorAction SilentlyContinue | Select-Object Id, PrinterName, DocumentName, UserName, SubmittedTime, JobStatus, Size | ConvertTo-Json"'
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15, shell=True)
        if r.stdout.strip():
            data = json.loads(r.stdout)
            if isinstance(data, dict):
                data = [data]
            return data
        return []
    except Exception as e:
        return [{"error": str(e)}]

def set_default_printer(name):
    """Set default printer."""
    try:
        # Escape quotes in printer name
        safe_name = name.replace('"', '`"')
        cmd = f'powershell -NoProfile -Command "Set-DefaultPrinter -Name \\"{safe_name}\\" -ErrorAction SilentlyContinue; if($?) {{ Write-Output OK }} else {{ (New-Object -ComObject WScript.Network).SetDefaultPrinter(\\"{safe_name}\\"); Write-Output OK2 }}"'
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10, shell=True)
        ok = "OK" in r.stdout
        if not ok:
            # Fallback via rundll32
            cmd2 = f'rundll32 printui.dll,PrintUIEntry /y /n "{name}"'
            r2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=10, shell=True)
            ok = r2.returncode == 0
        return {"action": "set_default", "printer": name, "success": ok, "ts": datetime.now().isoformat()}
    except Exception as e:
        return {"action": "set_default", "printer": name, "success": False, "error": str(e)}

def do_list():
    db = init_db()
    printers = get_printers()
    default = get_default_printer()
    for p in printers:
        p["is_default"] = p.get("name", "") == default

    db.execute("INSERT INTO printer_snapshots (ts, printers_json, total_printers, default_printer) VALUES (?,?,?,?)",
               (datetime.now().isoformat(), json.dumps(printers), len(printers), default))
    log_event(db, "list", details=f"{len(printers)} printers")
    db.close()

    return {
        "action": "list",
        "printers": printers,
        "total": len(printers),
        "default": default,
        "ts": datetime.now().isoformat()
    }

def do_status():
    db = init_db()
    printers = get_printers()
    default = get_default_printer()
    issues = [p for p in printers if p.get("status_code", 0) not in [0]]
    log_event(db, "status_check", details=f"{len(issues)} issues")
    db.close()

    return {
        "action": "status",
        "total_printers": len(printers),
        "default_printer": default,
        "healthy": len(printers) - len(issues),
        "issues": issues,
        "all_printers": [{
            "name": p.get("name"),
            "status": p.get("status"),
            "type": p.get("type")
        } for p in printers],
        "ts": datetime.now().isoformat()
    }

def do_queue():
    db = init_db()
    queue = get_print_queue()
    log_event(db, "queue_check", details=f"{len(queue)} jobs")
    db.close()

    return {
        "action": "queue",
        "jobs": queue,
        "total_jobs": len(queue),
        "note": "Use 'Cancel-PrintJob' in PowerShell to clear stuck jobs",
        "ts": datetime.now().isoformat()
    }

def do_once():
    db = init_db()
    printers = get_printers()
    default = get_default_printer()
    total_events = db.execute("SELECT COUNT(*) FROM printer_events").fetchone()[0]
    issues = [p for p in printers if p.get("status_code", 0) not in [0]]
    log_event(db, "once_check")
    db.close()

    return {
        "status": "ok",
        "total_printers": len(printers),
        "default_printer": default,
        "printers_with_issues": len(issues),
        "total_events": total_events,
        "printer_names": [p.get("name", "") for p in printers],
        "ts": datetime.now().isoformat()
    }

def main():
    parser = argparse.ArgumentParser(description="Windows Printer Manager — COWORK #229")
    parser.add_argument("--list", action="store_true", help="List all printers")
    parser.add_argument("--status", action="store_true", help="Check printer status")
    parser.add_argument("--default", type=str, metavar="NAME", help="Set default printer")
    parser.add_argument("--queue", action="store_true", help="Show print queue")
    parser.add_argument("--once", action="store_true", help="One-shot status check")
    args = parser.parse_args()

    if args.list:
        print(json.dumps(do_list(), ensure_ascii=False, indent=2))
    elif args.default:
        db = init_db()
        result = set_default_printer(args.default)
        log_event(db, "set_default", printer=args.default, success=int(result.get("success", False)))
        db.close()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.status:
        print(json.dumps(do_status(), ensure_ascii=False, indent=2))
    elif args.queue:
        print(json.dumps(do_queue(), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(do_once(), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
