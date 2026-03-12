#!/usr/bin/env python3
"""jarvis_meta_dashboard.py — Meta dashboard generator.
Generates a standalone HTML dashboard from all dev/data/*.db stats.
Usage: python dev/jarvis_meta_dashboard.py --generate --once
"""
import argparse
import json
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "meta_dashboard.db"
DATA_DIR = DEV / "data"
HTML_PATH = DEV / "data" / "meta_dashboard.html"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS checks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        action TEXT,
        report TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS generations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        total_dbs INTEGER,
        total_tables INTEGER,
        total_rows INTEGER,
        total_size_bytes INTEGER,
        html_size_bytes INTEGER,
        output_path TEXT
    )""")
    db.commit()
    return db


def _scan_databases():
    """Scan all .db files and collect stats."""
    dbs = []
    for db_file in sorted(DATA_DIR.glob("*.db")):
        info = {
            "name": db_file.name,
            "size_bytes": db_file.stat().st_size,
            "size_mb": round(db_file.stat().st_size / (1024 * 1024), 3),
            "modified": datetime.fromtimestamp(db_file.stat().st_mtime).isoformat(),
            "tables": [],
            "total_rows": 0
        }
        try:
            conn = sqlite3.connect(str(db_file))
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
            for (tname,) in tables:
                try:
                    count = conn.execute(f"SELECT COUNT(*) FROM [{tname}]").fetchone()[0]
                    info["tables"].append({"name": tname, "rows": count})
                    info["total_rows"] += count
                except Exception:
                    info["tables"].append({"name": tname, "rows": -1})
            conn.close()
        except Exception as e:
            info["error"] = str(e)
        dbs.append(info)
    return dbs


def _generate_html(db_stats):
    """Generate a standalone HTML dashboard."""
    total_dbs = len(db_stats)
    total_tables = sum(len(d["tables"]) for d in db_stats)
    total_rows = sum(d["total_rows"] for d in db_stats)
    total_size = sum(d["size_bytes"] for d in db_stats)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Build table rows
    table_rows = ""
    for d in sorted(db_stats, key=lambda x: x["total_rows"], reverse=True):
        status_color = "#4CAF50" if d["total_rows"] > 0 else "#ff9800"
        table_rows += f"""
        <tr>
            <td style="font-weight:bold">{d['name']}</td>
            <td>{len(d['tables'])}</td>
            <td>{d['total_rows']:,}</td>
            <td>{d['size_mb']:.3f} MB</td>
            <td>{d['modified'][:16]}</td>
            <td><span style="color:{status_color}">{'OK' if d['total_rows'] > 0 else 'EMPTY'}</span></td>
        </tr>"""

    # Build detail sections
    details = ""
    for d in sorted(db_stats, key=lambda x: x["name"]):
        if d["tables"]:
            subtable = "".join(
                f"<tr><td>{t['name']}</td><td>{t['rows']:,}</td></tr>" for t in d["tables"]
            )
            details += f"""
            <div style="margin:10px 0;padding:10px;background:#2a2a2a;border-radius:6px">
                <h4 style="margin:0 0 8px 0;color:#64b5f6">{d['name']}</h4>
                <table style="width:100%;font-size:12px"><tr><th>Table</th><th>Rows</th></tr>{subtable}</table>
            </div>"""

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>JARVIS Meta Dashboard</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #1a1a2e; color: #e0e0e0; padding: 20px; }}
        h1 {{ color: #64b5f6; text-align: center; margin-bottom: 5px; font-size: 28px; }}
        h2 {{ color: #90caf9; margin: 20px 0 10px; font-size: 20px; }}
        .subtitle {{ text-align: center; color: #888; margin-bottom: 20px; }}
        .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }}
        .card {{ background: #16213e; border-radius: 10px; padding: 20px; text-align: center; border: 1px solid #333; }}
        .card .value {{ font-size: 36px; font-weight: bold; color: #4fc3f7; }}
        .card .label {{ font-size: 14px; color: #aaa; margin-top: 5px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
        th {{ background: #16213e; color: #64b5f6; padding: 10px; text-align: left; font-size: 13px; }}
        td {{ padding: 8px 10px; border-bottom: 1px solid #333; font-size: 13px; }}
        tr:hover {{ background: #1a2744; }}
        .footer {{ text-align: center; color: #666; margin-top: 30px; font-size: 12px; }}
    </style>
</head>
<body>
    <h1>JARVIS Meta Dashboard</h1>
    <p class="subtitle">Generated: {now} | dev/data/ overview</p>

    <div class="cards">
        <div class="card">
            <div class="value">{total_dbs}</div>
            <div class="label">Databases</div>
        </div>
        <div class="card">
            <div class="value">{total_tables}</div>
            <div class="label">Tables</div>
        </div>
        <div class="card">
            <div class="value">{total_rows:,}</div>
            <div class="label">Total Rows</div>
        </div>
        <div class="card">
            <div class="value">{round(total_size / (1024*1024), 1)}</div>
            <div class="label">Total Size (MB)</div>
        </div>
    </div>

    <h2>Database Overview</h2>
    <table>
        <tr>
            <th>Database</th><th>Tables</th><th>Rows</th><th>Size</th><th>Last Modified</th><th>Status</th>
        </tr>
        {table_rows}
    </table>

    <h2>Table Details</h2>
    {details}

    <p class="footer">JARVIS Turbo v10.6 | Meta Dashboard | {total_dbs} databases scanned</p>
</body>
</html>"""
    return html, total_dbs, total_tables, total_rows, total_size


def do_generate():
    """Generate the HTML dashboard."""
    db = init_db()
    db_stats = _scan_databases()
    html, total_dbs, total_tables, total_rows, total_size = _generate_html(db_stats)

    HTML_PATH.write_text(html, encoding="utf-8")
    html_size = HTML_PATH.stat().st_size

    db.execute(
        "INSERT INTO generations (ts, total_dbs, total_tables, total_rows, total_size_bytes, html_size_bytes, output_path) VALUES (?,?,?,?,?,?,?)",
        (time.time(), total_dbs, total_tables, total_rows, total_size, html_size, str(HTML_PATH))
    )
    db.commit()

    result = {
        "ts": datetime.now().isoformat(),
        "action": "generate",
        "output_path": str(HTML_PATH),
        "html_size_kb": round(html_size / 1024, 1),
        "total_databases": total_dbs,
        "total_tables": total_tables,
        "total_rows": total_rows,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "status": "generated"
    }
    db.execute("INSERT INTO checks (ts, action, report) VALUES (?,?,?)",
               (time.time(), "generate", json.dumps(result)))
    db.commit()
    db.close()
    return result


def do_serve(port=8888):
    """Serve the dashboard on a local port (non-blocking info)."""
    db = init_db()
    if not HTML_PATH.exists():
        do_generate()

    result = {
        "ts": datetime.now().isoformat(),
        "action": "serve",
        "url": f"http://127.0.0.1:{port}/meta_dashboard.html",
        "file": str(HTML_PATH),
        "note": f"Run: python -m http.server {port} --directory \"{DATA_DIR}\" to serve",
        "status": "info"
    }
    db.execute("INSERT INTO checks (ts, action, report) VALUES (?,?,?)",
               (time.time(), "serve", json.dumps(result)))
    db.commit()
    db.close()
    return result


def do_update():
    """Update the dashboard with fresh data."""
    return do_generate()


def do_export():
    """Export dashboard data as JSON."""
    db = init_db()
    db_stats = _scan_databases()
    export_path = DATA_DIR / f"meta_dashboard_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    export_data = {
        "generated": datetime.now().isoformat(),
        "databases": db_stats,
        "summary": {
            "total_dbs": len(db_stats),
            "total_tables": sum(len(d["tables"]) for d in db_stats),
            "total_rows": sum(d["total_rows"] for d in db_stats),
            "total_size_mb": round(sum(d["size_bytes"] for d in db_stats) / (1024 * 1024), 2)
        }
    }
    export_path.write_text(json.dumps(export_data, ensure_ascii=False, indent=2), encoding="utf-8")

    result = {
        "ts": datetime.now().isoformat(),
        "action": "export",
        "export_path": str(export_path),
        "size_bytes": export_path.stat().st_size,
        "databases_exported": len(db_stats)
    }
    db.execute("INSERT INTO checks (ts, action, report) VALUES (?,?,?)",
               (time.time(), "export", json.dumps(result)))
    db.commit()
    db.close()
    return result


def main():
    parser = argparse.ArgumentParser(description="Meta dashboard generator for all dev/data/*.db")
    parser.add_argument("--generate", action="store_true", help="Generate HTML dashboard")
    parser.add_argument("--serve", action="store_true", help="Show serve instructions")
    parser.add_argument("--update", action="store_true", help="Update dashboard with fresh data")
    parser.add_argument("--export", action="store_true", help="Export data as JSON")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    if args.generate:
        print(json.dumps(do_generate(), ensure_ascii=False, indent=2))
    elif args.serve:
        print(json.dumps(do_serve(), ensure_ascii=False, indent=2))
    elif args.update:
        print(json.dumps(do_update(), ensure_ascii=False, indent=2))
    elif args.export:
        print(json.dumps(do_export(), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(do_generate(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
