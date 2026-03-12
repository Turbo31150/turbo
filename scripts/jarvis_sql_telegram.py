#!/usr/bin/env python3
"""JARVIS SQL — Execute SQL queries via WS API for Telegram.
Usage: python /home/turbo/jarvis-m1-ops/scripts/jarvis_sql_telegram.py [query|stats|databases]
"""
import json, sys, urllib.request

WS = "http://127.0.0.1:9742"

def ws_get(path, timeout=8):
    try:
        with urllib.request.urlopen(f"{WS}{path}", timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}

def ws_post(path, data, timeout=10):
    body = json.dumps(data).encode()
    try:
        req = urllib.request.Request(f"{WS}{path}", data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}

def cmd_stats():
    d = ws_get("/api/sql/stats")
    if "error" in d:
        return f"SQL STATS\n  Erreur: {d['error']}"
    lines = ["SQL STATS"]
    for db, info in d.items():
        if db.startswith("_"):
            continue
        lines.append(f"  {db}: {info.get('tables',0)} tables, {info.get('rows',0)} rows, {info.get('size_kb',0):.0f} KB")
    total = d.get("_total", {})
    lines.append(f"  TOTAL: {total.get('databases',0)} DBs, {total.get('tables',0)} tables, {total.get('rows',0)} rows")
    return "\n".join(lines)

def cmd_databases():
    d = ws_get("/api/sql/databases")
    if "error" in d:
        return f"DATABASES\n  Erreur: {d['error']}"
    lines = ["DATABASES"]
    for db, info in d.items():
        lines.append(f"\n  {db} ({info.get('tables',0)} tables, {info.get('total_rows',0)} rows)")
        for t in info.get("table_list", [])[:10]:
            lines.append(f"    {t['name']}: {t['rows']} rows")
        remaining = len(info.get("table_list", [])) - 10
        if remaining > 0:
            lines.append(f"    ... +{remaining} tables")
    return "\n".join(lines)

def cmd_query(query):
    if not query.strip():
        return "Usage: sql [db:]<query>\nExemples:\n  sql SELECT * FROM signals LIMIT 5\n  sql jarvis:SELECT COUNT(*) FROM dispatch_log\n  sql etoile:PRAGMA table_info(signals)\nDBs: etoile (defaut), jarvis, scheduler"
    # Parse optional db prefix: "jarvis:SELECT ..."
    db = "etoile"
    if ":" in query and query.split(":")[0].lower() in ("etoile", "jarvis", "scheduler"):
        db, query = query.split(":", 1)
        db = db.strip().lower()
    d = ws_post("/api/sql/query", {"db": db, "sql": query.strip(), "limit": 50})
    if not d or "error" in d:
        err = d.get("error", "unknown") if d else "WS unavailable"
        return f"SQL ERROR\n  {err}"
    rows = d.get("rows", [])
    cols = d.get("columns", [])
    if not rows:
        return f"SQL OK ({db}) — 0 rows"
    lines = [f"SQL RESULTS ({db}, {len(rows)} rows)"]
    if cols:
        lines.append("  " + " | ".join(str(c) for c in cols))
        lines.append("  " + "-" * min(60, len(cols) * 15))
    for row in rows[:20]:
        if isinstance(row, dict):
            vals = [str(v)[:20] for v in row.values()]
            lines.append("  " + " | ".join(vals))
        else:
            lines.append(f"  {row}")
    if len(rows) > 20:
        lines.append(f"  ... +{len(rows) - 20} rows")
    return "\n".join(lines)

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    args = " ".join(sys.argv[1:]).strip()
    if not args or args == "stats":
        print(cmd_stats())
    elif args == "databases" or args == "db":
        print(cmd_databases())
    else:
        print(cmd_query(args))
