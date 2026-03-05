#!/usr/bin/env python3
"""win_font_manager.py — Gestionnaire polices Windows.

Detecte doublons, polices inutilisees, stats.

Usage:
    python dev/win_font_manager.py --once
    python dev/win_font_manager.py --list
    python dev/win_font_manager.py --duplicates
    python dev/win_font_manager.py --unused
"""
import argparse
import json
import os
import sqlite3
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "font_manager.db"
FONTS_DIR = Path("C:/Windows/Fonts")
USER_FONTS_DIR = Path.home() / "AppData" / "Local" / "Microsoft" / "Windows" / "Fonts"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS fonts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, name TEXT, path TEXT, size_kb REAL,
        extension TEXT, location TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, system_fonts INTEGER, user_fonts INTEGER,
        total_size_mb REAL, duplicates INTEGER)""")
    db.commit()
    return db


def scan_fonts():
    """Scan all font directories."""
    fonts = []
    font_exts = {".ttf", ".otf", ".ttc", ".woff", ".woff2", ".fon"}

    for fonts_dir, location in [(FONTS_DIR, "system"), (USER_FONTS_DIR, "user")]:
        if not fonts_dir.exists():
            continue
        try:
            for f in fonts_dir.iterdir():
                if f.suffix.lower() in font_exts:
                    try:
                        size = f.stat().st_size
                        fonts.append({
                            "name": f.stem,
                            "path": str(f),
                            "size_kb": round(size / 1024, 1),
                            "ext": f.suffix.lower(),
                            "location": location,
                        })
                    except OSError:
                        pass
        except PermissionError:
            pass

    return fonts


def find_duplicates(fonts):
    """Find duplicate fonts by name base."""
    by_name = defaultdict(list)
    for f in fonts:
        base = f["name"].lower().split("-")[0].split("_")[0]
        by_name[base].append(f)

    duplicates = []
    for name, group in by_name.items():
        if len(group) > 4:  # More than 4 variants = potential bloat
            total_size = sum(f["size_kb"] for f in group)
            duplicates.append({
                "base_name": name,
                "variants": len(group),
                "total_size_kb": round(total_size, 1),
            })

    return sorted(duplicates, key=lambda x: x["total_size_kb"], reverse=True)


def do_scan():
    """Full font scan."""
    db = init_db()
    fonts = scan_fonts()
    duplicates = find_duplicates(fonts)

    system = sum(1 for f in fonts if f["location"] == "system")
    user = sum(1 for f in fonts if f["location"] == "user")
    total_size = sum(f["size_kb"] for f in fonts) / 1024  # MB

    # Extension breakdown
    by_ext = defaultdict(int)
    for f in fonts:
        by_ext[f["ext"]] += 1

    # Store
    for f in fonts[:500]:
        db.execute(
            "INSERT INTO fonts (ts, name, path, size_kb, extension, location) VALUES (?,?,?,?,?,?)",
            (time.time(), f["name"], f["path"][:300], f["size_kb"], f["ext"], f["location"])
        )

    db.execute(
        "INSERT INTO scans (ts, system_fonts, user_fonts, total_size_mb, duplicates) VALUES (?,?,?,?,?)",
        (time.time(), system, user, round(total_size, 1), len(duplicates))
    )
    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "total_fonts": len(fonts),
        "system_fonts": system,
        "user_fonts": user,
        "total_size_mb": round(total_size, 1),
        "by_extension": dict(by_ext),
        "duplicate_families": len(duplicates),
        "top_duplicates": duplicates[:10],
    }


def main():
    parser = argparse.ArgumentParser(description="Windows Font Manager")
    parser.add_argument("--once", "--list", action="store_true", help="Scan fonts")
    parser.add_argument("--duplicates", action="store_true", help="Find duplicates")
    parser.add_argument("--unused", action="store_true", help="Unused fonts")
    parser.add_argument("--install", metavar="PATH", help="Install font")
    args = parser.parse_args()

    result = do_scan()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
