#!/usr/bin/env python3
"""jarvis_usage_analytics.py — #207 Aggregate analytics from all dev/data/*.db files.
Usage:
    python dev/jarvis_usage_analytics.py --report
    python dev/jarvis_usage_analytics.py --daily
    python dev/jarvis_usage_analytics.py --weekly
    python dev/jarvis_usage_analytics.py --trends
    python dev/jarvis_usage_analytics.py --once
"""
import argparse, json, sqlite3, time, os, glob as globmod
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

DEV = Path(__file__).parent
DATA_DIR = DEV / "data"
DB_PATH = DATA_DIR / "usage_analytics.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        total_dbs INTEGER,
        total_rows INTEGER,
        total_size_bytes INTEGER,
        most_active_db TEXT,
        most_active_rows INTEGER,
        ts TEXT DEFAULT (datetime('now','localtime'))
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS db_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        snapshot_id INTEGER,
        db_name TEXT,
        table_count INTEGER,
        row_count INTEGER,
        size_bytes INTEGER,
        FOREIGN KEY(snapshot_id) REFERENCES snapshots(id)
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS hourly_activity (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        hour INTEGER,
        activity_count INTEGER,
        ts TEXT DEFAULT (datetime('now','localtime'))
    )""")
    db.commit()
    return db


def _scan_databases():
    """Scan all .db files in data/ and collect stats."""
    dbs = []
    for db_file in sorted(DATA_DIR.glob("*.db")):
        if db_file.name == "usage_analytics.db":
            continue
        try:
            conn = sqlite3.connect(str(db_file))
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            total_rows = 0
            table_details = []
            for (tname,) in tables:
                try:
                    cnt = conn.execute(f"SELECT COUNT(*) FROM [{tname}]").fetchone()[0]
                    total_rows += cnt
                    table_details.append({"table": tname, "rows": cnt})
                except Exception:
                    pass
            size = db_file.stat().st_size
            dbs.append({
                "name": db_file.name,
                "path": str(db_file),
                "tables": len(tables),
                "rows": total_rows,
                "size_bytes": size,
                "size_kb": round(size / 1024, 1),
                "table_details": table_details
            })
            conn.close()
        except Exception as e:
            dbs.append({"name": db_file.name, "error": str(e)})
    return dbs


def _try_count_by_date(conn, table, date_col="ts"):
    """Try to count rows by date in a table."""
    try:
        rows = conn.execute(
            f"SELECT DATE([{date_col}]) as d, COUNT(*) FROM [{table}] WHERE [{date_col}] IS NOT NULL GROUP BY d ORDER BY d DESC LIMIT 30"
        ).fetchall()
        return {r[0]: r[1] for r in rows if r[0]}
    except Exception:
        return {}


def take_snapshot(db):
    """Take a fresh analytics snapshot."""
    dbs = _scan_databases()
    total_rows = sum(d.get("rows", 0) for d in dbs)
    total_size = sum(d.get("size_bytes", 0) for d in dbs)
    most_active = max(dbs, key=lambda d: d.get("rows", 0)) if dbs else {"name": "none", "rows": 0}

    cur = db.execute(
        "INSERT INTO snapshots (date, total_dbs, total_rows, total_size_bytes, most_active_db, most_active_rows) VALUES (?,?,?,?,?,?)",
        (datetime.now().strftime("%Y-%m-%d"), len(dbs), total_rows, total_size,
         most_active.get("name", ""), most_active.get("rows", 0))
    )
    snap_id = cur.lastrowid

    for d in dbs:
        if "error" not in d:
            db.execute(
                "INSERT INTO db_stats (snapshot_id, db_name, table_count, row_count, size_bytes) VALUES (?,?,?,?,?)",
                (snap_id, d["name"], d.get("tables", 0), d.get("rows", 0), d.get("size_bytes", 0))
            )
    db.commit()
    return snap_id, dbs


def generate_report(db):
    """Full analytics report."""
    snap_id, dbs = take_snapshot(db)
    total_rows = sum(d.get("rows", 0) for d in dbs)
    total_size = sum(d.get("size_bytes", 0) for d in dbs)

    sorted_by_rows = sorted([d for d in dbs if "error" not in d], key=lambda x: x.get("rows", 0), reverse=True)
    sorted_by_size = sorted([d for d in dbs if "error" not in d], key=lambda x: x.get("size_bytes", 0), reverse=True)

    return {
        "total_databases": len(dbs),
        "total_rows": total_rows,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "top_by_rows": [{"db": d["name"], "rows": d["rows"]} for d in sorted_by_rows[:5]],
        "top_by_size": [{"db": d["name"], "kb": d["size_kb"]} for d in sorted_by_size[:5]],
        "all_databases": [{k: v for k, v in d.items() if k != "table_details"} for d in dbs],
        "snapshot_id": snap_id,
        "ts": datetime.now().isoformat()
    }


def daily_report(db):
    """Today's activity across DBs."""
    today = datetime.now().strftime("%Y-%m-%d")
    dbs = _scan_databases()
    daily_activity = []

    for d in dbs:
        if "error" in d:
            continue
        try:
            conn = sqlite3.connect(d["path"])
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            for (tname,) in tables:
                cols = [c[1] for c in conn.execute(f"PRAGMA table_info([{tname}])").fetchall()]
                for date_col in ["ts", "created_at", "date", "timestamp"]:
                    if date_col in cols:
                        try:
                            cnt = conn.execute(
                                f"SELECT COUNT(*) FROM [{tname}] WHERE DATE([{date_col}])=?", (today,)
                            ).fetchone()[0]
                            if cnt > 0:
                                daily_activity.append({"db": d["name"], "table": tname, "today_rows": cnt})
                        except Exception:
                            pass
                        break
            conn.close()
        except Exception:
            pass

    daily_activity.sort(key=lambda x: x["today_rows"], reverse=True)
    total_today = sum(a["today_rows"] for a in daily_activity)

    return {
        "date": today,
        "total_activity_today": total_today,
        "active_tables": daily_activity[:15],
        "active_db_count": len(set(a["db"] for a in daily_activity))
    }


def weekly_report(db):
    """7-day trend."""
    snapshots = db.execute(
        "SELECT date, total_dbs, total_rows, total_size_bytes FROM snapshots ORDER BY id DESC LIMIT 7"
    ).fetchall()
    return {
        "weekly_snapshots": [
            {"date": s[0], "dbs": s[1], "rows": s[2], "size_mb": round(s[3]/(1024*1024), 2)}
            for s in snapshots
        ]
    }


def trends_report(db):
    """ASCII trend graph of row counts."""
    snapshots = db.execute(
        "SELECT date, total_rows FROM snapshots ORDER BY id DESC LIMIT 14"
    ).fetchall()
    snapshots.reverse()

    if not snapshots:
        return {"trends": "No data yet. Run --report first."}

    max_rows = max(s[1] for s in snapshots) if snapshots else 1
    graph_width = 40
    lines = []
    for date, rows in snapshots:
        bar_len = int((rows / max_rows) * graph_width) if max_rows else 0
        bar = "#" * bar_len
        lines.append(f"{date} |{bar} {rows}")

    return {
        "trend_graph": "\n".join(lines),
        "data_points": len(snapshots),
        "latest_rows": snapshots[-1][1] if snapshots else 0,
        "growth": snapshots[-1][1] - snapshots[0][1] if len(snapshots) > 1 else 0
    }


def do_status(db):
    dbs = _scan_databases()
    total_rows = sum(d.get("rows", 0) for d in dbs)
    total_size = sum(d.get("size_bytes", 0) for d in dbs)
    return {
        "script": "jarvis_usage_analytics.py",
        "id": 207,
        "db": str(DB_PATH),
        "total_databases": len(dbs),
        "total_rows": total_rows,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "top_3": [{"db": d["name"], "rows": d.get("rows", 0)}
                  for d in sorted([x for x in dbs if "error" not in x],
                                  key=lambda x: x.get("rows", 0), reverse=True)[:3]],
        "ts": datetime.now().isoformat()
    }


def main():
    parser = argparse.ArgumentParser(description="JARVIS Usage Analytics — aggregate all DB stats")
    parser.add_argument("--report", action="store_true", help="Full analytics report")
    parser.add_argument("--daily", action="store_true", help="Today's activity")
    parser.add_argument("--weekly", action="store_true", help="7-day snapshots")
    parser.add_argument("--trends", action="store_true", help="ASCII trend graph")
    parser.add_argument("--once", action="store_true", help="Quick status")
    args = parser.parse_args()

    db = init_db()

    if args.report:
        result = generate_report(db)
    elif args.daily:
        result = daily_report(db)
    elif args.weekly:
        result = weekly_report(db)
    elif args.trends:
        result = trends_report(db)
    else:
        result = do_status(db)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    db.close()


if __name__ == "__main__":
    main()
