#!/usr/bin/env python3
"""JARVIS DB Optimizer — Optimisation des bases de donnees."""
import json, sys, os, sqlite3
from _paths import TURBO_DIR, ETOILE_DB, JARVIS_DB, SNIPER_DB
from datetime import datetime

DATABASES = {
    "etoile.db": str(ETOILE_DB),
    "jarvis.db": str(JARVIS_DB),
    "sniper.db": str(SNIPER_DB),
    "finetuning.db": str(TURBO_DIR / "finetuning" / "finetuning.db"),
}
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

def send_telegram(msg):
    import urllib.request
    data = json.dumps({"chat_id": TELEGRAM_CHAT, "text": msg}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                                 data=data, headers={"Content-Type": "application/json"})
    try: urllib.request.urlopen(req, timeout=10)
    except: pass

def get_db_stats(path):
    if not os.path.exists(path):
        return {"error": "not found"}
    size_mb = round(os.path.getsize(path) / 1048576, 2)
    conn = sqlite3.connect(path)
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in c.fetchall()]
    total_rows = 0
    table_stats = {}
    for t in tables:
        try:
            c.execute(f"SELECT COUNT(*) FROM [{t}]")
            count = c.fetchone()[0]
            total_rows += count
            table_stats[t] = count
        except: table_stats[t] = -1
    conn.close()
    return {"size_mb": size_mb, "tables": len(tables), "rows": total_rows, "detail": table_stats}

def check_integrity(path):
    conn = sqlite3.connect(path)
    c = conn.cursor()
    c.execute("PRAGMA integrity_check")
    result = c.fetchone()[0]
    conn.close()
    return result == "ok", result

def optimize_db(path):
    conn = sqlite3.connect(path)
    c = conn.cursor()
    # Get size before
    size_before = os.path.getsize(path)
    # ANALYZE
    c.execute("ANALYZE")
    # VACUUM
    c.execute("VACUUM")
    conn.commit()
    conn.close()
    size_after = os.path.getsize(path)
    saved = size_before - size_after
    return {"saved_bytes": saved, "saved_mb": round(saved / 1048576, 3)}

def run_full_optimization(notify=False):
    results = {}
    total_saved = 0
    total_rows = 0
    total_tables = 0
    all_ok = True

    for name, path in DATABASES.items():
        stats = get_db_stats(path)
        if "error" in stats:
            results[name] = {"status": "NOT FOUND"}
            continue

        ok, integrity = check_integrity(path)
        if not ok:
            all_ok = False

        opt = optimize_db(path)
        total_saved += opt["saved_bytes"]
        total_rows += stats["rows"]
        total_tables += stats["tables"]

        results[name] = {
            "size_mb": stats["size_mb"],
            "tables": stats["tables"],
            "rows": stats["rows"],
            "integrity": "OK" if ok else integrity,
            "saved_mb": opt["saved_mb"],
        }

    lines = [f"[DB OPTIMIZER] {datetime.now().strftime('%H:%M')}"]
    for name, r in results.items():
        if r.get("status") == "NOT FOUND":
            lines.append(f"  {name}: NOT FOUND")
        else:
            lines.append(f"  {name}: {r['size_mb']}MB | {r['tables']}t | {r['rows']}r | {r['integrity']} | saved {r['saved_mb']}MB")

    lines.append(f"\n  Total: {total_tables} tables, {total_rows} rows, saved {round(total_saved/1048576, 3)}MB")
    lines.append(f"  Integrity: {'ALL OK' if all_ok else 'ERRORS DETECTED'}")

    text = "\n".join(lines)
    if notify:
        send_telegram(text)
    return text, results

if __name__ == "__main__":
    if "--once" in sys.argv:
        text, _ = run_full_optimization(notify="--notify" in sys.argv)
        print(text)

    elif "--stats" in sys.argv:
        for name, path in DATABASES.items():
            stats = get_db_stats(path)
            if "error" in stats:
                print(f"  {name}: NOT FOUND")
            else:
                print(f"  {name}: {stats['size_mb']}MB | {stats['tables']} tables | {stats['rows']} rows")
                if "--detail" in sys.argv:
                    for t, count in sorted(stats["detail"].items(), key=lambda x: -x[1]):
                        print(f"    {t}: {count}")

    elif "--integrity" in sys.argv:
        for name, path in DATABASES.items():
            if os.path.exists(path):
                ok, result = check_integrity(path)
                print(f"  {name}: {'OK' if ok else result}")

    else:
        print("Usage: db_optimizer.py --once [--notify] | --stats [--detail] | --integrity")