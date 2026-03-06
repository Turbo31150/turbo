#!/usr/bin/env python3
"""JARVIS Feature Builder — Scan /FIXME/STUB in codebase, generate feature specs.

Continuously scans F:\\BUREAU\\turbo\\src\\ for incomplete features,
generates implementation specs, and dispatches to cluster for coding.
"""
import argparse
import json
import os
import re
import sqlite3
import time
from pathlib import Path

from _paths import TURBO_DIR as TURBO
SRC = TURBO / "src"
DB_PATH = Path(__file__).parent / "features.db"
REPORT_DIR = Path(__file__).parent / "reports"

PATTERNS = [
    (r"#\s*[:\s]+(.*)", ""),
    (r"#\s*FIXME[:\s]+(.*)", "FIXME"),
    (r"#\s*STUB[:\s]+(.*)", "STUB"),
    (r"#\s*HACK[:\s]+(.*)", "HACK"),
    (r"pass\s*#\s*(.*)", "EMPTY_IMPL"),
    (r"raise\s+NotImplementedError\((.*?)\)", "NOT_IMPL"),
]

def init_db():
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS features (
        id INTEGER PRIMARY KEY, file TEXT, line INTEGER, pattern TEXT,
        text TEXT, priority TEXT DEFAULT 'medium', status TEXT DEFAULT 'open',
        found_at REAL, resolved_at REAL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY, ts REAL, files_scanned INTEGER,
        new_found INTEGER, total_open INTEGER)""")
    db.commit()
    return db

def scan_codebase(db):
    """Scan all .py files for /FIXME/STUB patterns."""
    new_found = 0
    files_scanned = 0
    existing = set()
    for row in db.execute("SELECT file, line, pattern FROM features WHERE status='open'"):
        existing.add((row[0], row[1], row[2]))

    for py_file in SRC.rglob("*.py"):
        files_scanned += 1
        try:
            lines = py_file.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        rel = str(py_file.relative_to(TURBO))
        for i, line in enumerate(lines, 1):
            for regex, ptype in PATTERNS:
                m = re.search(regex, line)
                if m:
                    key = (rel, i, ptype)
                    if key not in existing:
                        text = m.group(1).strip()[:200]
                        priority = "high" if ptype in ("FIXME", "NOT_IMPL") else "medium"
                        db.execute(
                            "INSERT INTO features (file, line, pattern, text, priority, found_at) VALUES (?,?,?,?,?,?)",
                            (rel, i, ptype, text, priority, time.time()))
                        new_found += 1
                        existing.add(key)
    db.commit()
    total_open = db.execute("SELECT COUNT(*) FROM features WHERE status='open'").fetchone()[0]
    db.execute("INSERT INTO runs (ts, files_scanned, new_found, total_open) VALUES (?,?,?,?)",
               (time.time(), files_scanned, new_found, total_open))
    db.commit()
    return files_scanned, new_found, total_open

def generate_report(db):
    """Generate feature report."""
    rows = db.execute(
        "SELECT file, line, pattern, text, priority FROM features WHERE status='open' ORDER BY priority DESC, found_at DESC LIMIT 30"
    ).fetchall()
    report = ["# JARVIS Feature Backlog", f"Generated: {time.strftime('%Y-%m-%d %H:%M')}", ""]
    by_priority = {"high": [], "medium": [], "low": []}
    for r in rows:
        by_priority.get(r[4], by_priority["medium"]).append(r)
    for prio in ("high", "medium", "low"):
        if by_priority[prio]:
            report.append(f"## {prio.upper()} ({len(by_priority[prio])})")
            for f, l, p, t, _ in by_priority[prio]:
                report.append(f"- `{f}:{l}` [{p}] {t}")
            report.append("")
    REPORT_DIR.mkdir(exist_ok=True)
    rpath = REPORT_DIR / f"features_{time.strftime('%Y%m%d_%H%M')}.md"
    rpath.write_text("\n".join(report), encoding="utf-8")
    return "\n".join(report[:20]), str(rpath)

def dispatch_to_cluster(db):
    """Send high-priority features to cluster for implementation."""
    import urllib.request
    high = db.execute(
        "SELECT id, file, line, text FROM features WHERE status='open' AND priority='high' ORDER BY found_at LIMIT 3"
    ).fetchall()
    if not high:
        return "Aucune feature high-priority en attente"
    results = []
    for fid, fpath, line, text in high:
        prompt = f"/nothink\nDans le fichier {fpath} ligne {line}, implemente: {text}. Donne le code Python complet."
        try:
            body = json.dumps({
                "model": "qwen3-8b", "input": prompt,
                "temperature": 0.2, "max_output_tokens": 2048, "stream": False, "store": False
            }).encode()
            req = urllib.request.Request(
                "http://127.0.0.1:1234/api/v1/chat",
                data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
                output = ""
                for item in reversed(data.get("output", [])):
                    if item.get("type") == "message":
                        output = item.get("content", [{}])[0].get("text", "")[:300]
                        break
                results.append(f"[{fpath}:{line}] {text[:60]} → M1: {output[:100]}")
        except Exception as e:
            results.append(f"[{fpath}:{line}] ERREUR: {e}")
    return "\n".join(results)

def main():
    parser = argparse.ArgumentParser(description="JARVIS Feature Builder")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dispatch", action="store_true", help="Dispatch high-prio to cluster")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=3600)
    args = parser.parse_args()

    db = init_db()
    if args.once or not args.loop:
        files, new, total = scan_codebase(db)
        print(f"Scanned {files} files | New: {new} | Total open: {total}")
        summary, rpath = generate_report(db)
        print(summary)
        if args.dispatch:
            print("\n--- Cluster Dispatch ---")
            print(dispatch_to_cluster(db))
    if args.loop:
        while True:
            try:
                files, new, total = scan_codebase(db)
                print(f"[{time.strftime('%H:%M')}] Scanned {files} | +{new} | Open: {total}")
                if new > 0:
                    generate_report(db)
                time.sleep(args.interval)
            except KeyboardInterrupt:
                break

if __name__ == "__main__":
    main()
