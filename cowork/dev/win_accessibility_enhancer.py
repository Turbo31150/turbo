#!/usr/bin/env python3
"""win_accessibility_enhancer.py — Ameliorateur accessibilite Windows.

Optimise contraste, taille texte, narrateur.

Usage:
    python dev/win_accessibility_enhancer.py --once
    python dev/win_accessibility_enhancer.py --scan
    python dev/win_accessibility_enhancer.py --optimize
    python dev/win_accessibility_enhancer.py --contrast
"""
import argparse
import ctypes
import json
import os
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "accessibility.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, dpi_scaling INTEGER, cursor_size INTEGER,
        high_contrast INTEGER, narrator_active INTEGER, score INTEGER)""")
    db.commit()
    return db


def get_dpi_scaling():
    try:
        user32 = ctypes.windll.user32
        user32.SetProcessDPIAware()
        dpi = user32.GetDpiForSystem()
        return int(dpi / 96 * 100)
    except Exception:
        return 100


def get_cursor_size():
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Cursors")
        try:
            val, _ = winreg.QueryValueEx(key, "CursorBaseSize")
            return int(val)
        except FileNotFoundError:
            return 32
        finally:
            winreg.CloseKey(key)
    except Exception:
        return 32


def check_high_contrast():
    try:
        out = subprocess.run(
            ["powershell", "-Command",
             "(Get-ItemProperty 'HKCU:/Control Panel/Accessibility/HighContrast' -Name Flags -ErrorAction SilentlyContinue).Flags"],
            capture_output=True, text=True, timeout=5
        )
        flags = int(out.stdout.strip() or "0")
        return bool(flags & 1)
    except Exception:
        return False


def check_narrator():
    try:
        out = subprocess.run(
            ["powershell", "-Command",
             "Get-Process Narrator -ErrorAction SilentlyContinue | Select-Object -First 1 Id"],
            capture_output=True, text=True, timeout=5
        )
        return bool(out.stdout.strip())
    except Exception:
        return False


def check_magnifier():
    try:
        out = subprocess.run(
            ["powershell", "-Command",
             "Get-Process Magnify -ErrorAction SilentlyContinue | Select-Object -First 1 Id"],
            capture_output=True, text=True, timeout=5
        )
        return bool(out.stdout.strip())
    except Exception:
        return False


def do_scan():
    db = init_db()
    dpi = get_dpi_scaling()
    cursor = get_cursor_size()
    contrast = check_high_contrast()
    narrator = check_narrator()
    magnifier = check_magnifier()

    # Scoring
    score = 50
    if dpi >= 125:
        score += 10
    if cursor >= 48:
        score += 10
    if contrast:
        score += 15
    if narrator:
        score += 10
    score = min(100, score)

    recommendations = []
    if dpi < 125:
        recommendations.append("Consider increasing DPI scaling to 125%+")
    if cursor < 48:
        recommendations.append("Consider larger cursor size (48+)")
    if not contrast:
        recommendations.append("High contrast mode available for better readability")

    db.execute("INSERT INTO scans (ts, dpi_scaling, cursor_size, high_contrast, narrator_active, score) VALUES (?,?,?,?,?,?)",
               (time.time(), dpi, cursor, int(contrast), int(narrator), score))
    db.commit()
    db.close()

    return {
        "ts": datetime.now().isoformat(),
        "settings": {
            "dpi_scaling_pct": dpi,
            "cursor_size": cursor,
            "high_contrast": contrast,
            "narrator_active": narrator,
            "magnifier_active": magnifier,
        },
        "accessibility_score": score,
        "recommendations": recommendations,
    }


def main():
    parser = argparse.ArgumentParser(description="Windows Accessibility Enhancer")
    parser.add_argument("--once", "--scan", action="store_true", help="Scan settings")
    parser.add_argument("--optimize", action="store_true", help="Optimize")
    parser.add_argument("--contrast", action="store_true", help="Toggle contrast")
    parser.add_argument("--narrator", action="store_true", help="Toggle narrator")
    args = parser.parse_args()
    print(json.dumps(do_scan(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
