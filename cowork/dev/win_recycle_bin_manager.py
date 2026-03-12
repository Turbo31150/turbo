#!/usr/bin/env python3
"""win_recycle_bin_manager.py — Recycle Bin stats, cleanup, and scheduling.
COWORK #230 — Batch 104: Windows Maintenance Pro

Usage:
    python dev/win_recycle_bin_manager.py --stats
    python dev/win_recycle_bin_manager.py --clean
    python dev/win_recycle_bin_manager.py --recover
    python dev/win_recycle_bin_manager.py --schedule
    python dev/win_recycle_bin_manager.py --once
"""
import argparse, json, sqlite3, time, subprocess, os
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "recycle_bin.db"

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS bin_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        total_items INTEGER,
        total_size_mb REAL,
        oldest_item_days INTEGER,
        top_extensions TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS bin_actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        action TEXT NOT NULL,
        items_affected INTEGER DEFAULT 0,
        size_freed_mb REAL DEFAULT 0,
        details TEXT,
        success INTEGER DEFAULT 1
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS bin_schedule (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        max_age_days INTEGER DEFAULT 30,
        max_size_mb INTEGER DEFAULT 5000,
        auto_clean INTEGER DEFAULT 0,
        check_interval_hours INTEGER DEFAULT 24,
        last_clean TEXT
    )""")
    if db.execute("SELECT COUNT(*) FROM bin_schedule").fetchone()[0] == 0:
        db.execute("INSERT INTO bin_schedule (max_age_days, max_size_mb, auto_clean, check_interval_hours) VALUES (30, 5000, 0, 24)")
    db.commit()
    return db

def get_bin_size():
    """Get total recycle bin size."""
    try:
        cmd = '''powershell -NoProfile -Command "
$bin = (New-Object -ComObject Shell.Application).Namespace(0xA)
$items = @($bin.Items())
$totalSize = 0
foreach ($item in $items) { try { $totalSize += $item.Size } catch {} }
@{ count = $items.Count; size = $totalSize } | ConvertTo-Json
"'''
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30, shell=True)
        if r.stdout.strip():
            data = json.loads(r.stdout)
            size_bytes = data.get("size", 0) or 0
            return {
                "count": data.get("count", 0) or 0,
                "size_bytes": size_bytes,
                "size_mb": round(size_bytes / (1024*1024), 2)
            }
        return {"count": 0, "size_bytes": 0, "size_mb": 0}
    except Exception as e:
        return {"count": 0, "size_bytes": 0, "size_mb": 0, "error": str(e)}

def empty_recycle_bin():
    """Empty the recycle bin."""
    try:
        cmd = 'powershell -NoProfile -Command "Clear-RecycleBin -Force -ErrorAction SilentlyContinue; Write-Output OK"'
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30, shell=True)
        return "OK" in r.stdout
    except Exception:
        return False

def do_stats():
    db = init_db()
    size_info = get_bin_size()
    db.execute("INSERT INTO bin_snapshots (ts, total_items, total_size_mb) VALUES (?,?,?)",
               (datetime.now().isoformat(), size_info["count"], size_info["size_mb"]))
    db.commit()

    prev = db.execute("SELECT total_items, total_size_mb FROM bin_snapshots ORDER BY id DESC LIMIT 1 OFFSET 1").fetchone()
    trend = "stable"
    if prev:
        if size_info["count"] > (prev[0] or 0):
            trend = "growing"
        elif size_info["count"] < (prev[0] or 0):
            trend = "shrinking"

    result = {
        "action": "stats",
        "items": size_info["count"],
        "size_mb": size_info["size_mb"],
        "size_bytes": size_info["size_bytes"],
        "trend": trend,
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_clean():
    db = init_db()
    before = get_bin_size()
    success = empty_recycle_bin()
    after = get_bin_size()

    freed_mb = max(0, (before["size_mb"] or 0) - (after["size_mb"] or 0))
    items_cleaned = max(0, (before["count"] or 0) - (after["count"] or 0))

    db.execute("INSERT INTO bin_actions (ts, action, items_affected, size_freed_mb, details, success) VALUES (?,?,?,?,?,?)",
               (datetime.now().isoformat(), "clean", items_cleaned, freed_mb,
                f"Before: {before['count']} items ({before['size_mb']} MB)", int(success)))
    db.commit()

    result = {
        "action": "clean",
        "success": success,
        "items_cleaned": items_cleaned,
        "size_freed_mb": freed_mb,
        "before": {"items": before["count"], "size_mb": before["size_mb"]},
        "after": {"items": after["count"], "size_mb": after["size_mb"]},
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_recover():
    """Show top 10 recoverable items."""
    db = init_db()
    try:
        cmd = '''powershell -NoProfile -Command "
$bin = (New-Object -ComObject Shell.Application).Namespace(0xA)
$items = @($bin.Items())
$result = @()
$count = [Math]::Min(10, $items.Count)
for ($i = 0; $i -lt $count; $i++) {
    $item = $items[$i]
    $result += @{
        Name = $item.Name
        Type = $item.Type
        OriginalPath = $bin.GetDetailsOf($item, 1)
        DeleteDate = $bin.GetDetailsOf($item, 2)
        Size = $bin.GetDetailsOf($item, 3)
    }
}
$result | ConvertTo-Json
"'''
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=20, shell=True)
        items = []
        if r.stdout.strip():
            data = json.loads(r.stdout)
            if isinstance(data, dict):
                data = [data]
            items = data
    except Exception as e:
        items = [{"error": str(e)}]

    result = {
        "action": "recover",
        "recoverable_items": items[:10],
        "total_shown": len(items),
        "note": "To recover: right-click item in Recycle Bin > Restore",
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_schedule():
    db = init_db()
    row = db.execute("SELECT max_age_days, max_size_mb, auto_clean, check_interval_hours, last_clean FROM bin_schedule LIMIT 1").fetchone()
    result = {
        "action": "schedule",
        "config": {
            "max_age_days": row[0],
            "max_size_mb": row[1],
            "auto_clean": bool(row[2]),
            "check_interval_hours": row[3],
            "last_clean": row[4]
        },
        "note": "Enable auto_clean to automatically empty bin items older than max_age_days",
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_once():
    db = init_db()
    size_info = get_bin_size()
    total_actions = db.execute("SELECT COUNT(*) FROM bin_actions").fetchone()[0]
    total_freed = db.execute("SELECT SUM(size_freed_mb) FROM bin_actions WHERE action='clean'").fetchone()[0] or 0
    result = {
        "status": "ok",
        "current_items": size_info["count"],
        "current_size_mb": size_info["size_mb"],
        "total_clean_actions": total_actions,
        "total_freed_mb": round(total_freed, 2),
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def main():
    parser = argparse.ArgumentParser(description="Recycle Bin Manager — COWORK #230")
    parser.add_argument("--stats", action="store_true", help="Show recycle bin statistics")
    parser.add_argument("--clean", action="store_true", help="Empty recycle bin")
    parser.add_argument("--recover", action="store_true", help="List recoverable items")
    parser.add_argument("--schedule", action="store_true", help="Show auto-clean schedule")
    parser.add_argument("--once", action="store_true", help="One-shot status check")
    args = parser.parse_args()

    if args.stats:
        print(json.dumps(do_stats(), ensure_ascii=False, indent=2))
    elif args.clean:
        print(json.dumps(do_clean(), ensure_ascii=False, indent=2))
    elif args.recover:
        print(json.dumps(do_recover(), ensure_ascii=False, indent=2))
    elif args.schedule:
        print(json.dumps(do_schedule(), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(do_once(), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
