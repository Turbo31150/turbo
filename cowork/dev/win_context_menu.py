#!/usr/bin/env python3
"""win_context_menu.py — Dynamic context menu manager (#245).

Reads registry HKCU\\Software\\Classes\\*\\shell entries,
lists/adds/removes custom context menu items.

Usage:
    python dev/win_context_menu.py --once
    python dev/win_context_menu.py --scan
    python dev/win_context_menu.py --add ACTION
    python dev/win_context_menu.py --remove ACTION
    python dev/win_context_menu.py --export
"""
import argparse
import json
import sqlite3
import time
import winreg
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "context_menu.db"

SHELL_KEY_PATH = r"Software\Classes\*\shell"
DIR_SHELL_KEY_PATH = r"Software\Classes\Directory\shell"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS menu_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        key_path TEXT NOT NULL,
        name TEXT NOT NULL,
        command TEXT,
        icon TEXT,
        scope TEXT DEFAULT 'file'
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS actions_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        action TEXT NOT NULL,
        target TEXT NOT NULL,
        success INTEGER,
        details TEXT
    )""")
    db.commit()
    return db


def read_shell_entries(key_path, scope="file"):
    """Read shell context menu entries from registry."""
    entries = []
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path)
        i = 0
        while True:
            try:
                subkey_name = winreg.EnumKey(key, i)
                entry = {"name": subkey_name, "scope": scope, "key_path": key_path}

                # Try to read command subkey
                try:
                    cmd_key = winreg.OpenKey(key, f"{subkey_name}\\command")
                    command, _ = winreg.QueryValueEx(cmd_key, "")
                    entry["command"] = command
                    winreg.CloseKey(cmd_key)
                except (FileNotFoundError, OSError):
                    entry["command"] = None

                # Try to read icon
                try:
                    sub_key = winreg.OpenKey(key, subkey_name)
                    icon, _ = winreg.QueryValueEx(sub_key, "Icon")
                    entry["icon"] = icon
                    winreg.CloseKey(sub_key)
                except (FileNotFoundError, OSError):
                    entry["icon"] = None

                entries.append(entry)
                i += 1
            except OSError:
                break
        winreg.CloseKey(key)
    except FileNotFoundError:
        pass
    except OSError as e:
        entries.append({"error": str(e)})
    return entries


def do_scan():
    """Scan all context menu entries."""
    db = init_db()
    file_entries = read_shell_entries(SHELL_KEY_PATH, "file")
    dir_entries = read_shell_entries(DIR_SHELL_KEY_PATH, "directory")
    all_entries = file_entries + dir_entries

    # Store in DB
    db.execute("DELETE FROM menu_items")
    for e in all_entries:
        if "error" not in e:
            db.execute(
                "INSERT INTO menu_items (ts, key_path, name, command, icon, scope) VALUES (?,?,?,?,?,?)",
                (datetime.now().isoformat(), e.get("key_path", ""), e["name"],
                 e.get("command"), e.get("icon"), e.get("scope", "file")),
            )
    db.commit()

    result = {
        "ts": datetime.now().isoformat(),
        "action": "scan",
        "file_menu_items": len(file_entries),
        "directory_menu_items": len(dir_entries),
        "total": len(all_entries),
        "items": all_entries,
    }
    db.close()
    return result


def do_add(action_name):
    """Add a context menu entry."""
    db = init_db()
    now = datetime.now().isoformat()
    success = False
    details = ""

    try:
        # Create shell key entry
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"{SHELL_KEY_PATH}\\{action_name}")
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, action_name)

        # Create command subkey - default to opening with notepad
        cmd_key = winreg.CreateKey(key, "command")
        winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, f'notepad.exe "%1"')
        winreg.CloseKey(cmd_key)
        winreg.CloseKey(key)

        success = True
        details = f"Added '{action_name}' to file context menu"
    except OSError as e:
        details = f"Failed: {e}"

    db.execute(
        "INSERT INTO actions_log (ts, action, target, success, details) VALUES (?,?,?,?,?)",
        (now, "add", action_name, int(success), details),
    )
    db.commit()

    result = {
        "ts": now,
        "action": "add",
        "target": action_name,
        "success": success,
        "details": details,
    }
    db.close()
    return result


def do_remove(action_name):
    """Remove a context menu entry."""
    db = init_db()
    now = datetime.now().isoformat()
    success = False
    details = ""

    try:
        # Try to delete command subkey first
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, f"{SHELL_KEY_PATH}\\{action_name}\\command")
        except FileNotFoundError:
            pass
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, f"{SHELL_KEY_PATH}\\{action_name}")
        success = True
        details = f"Removed '{action_name}' from file context menu"
    except FileNotFoundError:
        details = f"Entry '{action_name}' not found"
    except OSError as e:
        details = f"Failed: {e}"

    db.execute(
        "INSERT INTO actions_log (ts, action, target, success, details) VALUES (?,?,?,?,?)",
        (now, "remove", action_name, int(success), details),
    )
    db.commit()

    result = {
        "ts": now,
        "action": "remove",
        "target": action_name,
        "success": success,
        "details": details,
    }
    db.close()
    return result


def do_export():
    """Export all context menu items."""
    db = init_db()
    items = db.execute("SELECT name, command, icon, scope, key_path FROM menu_items").fetchall()

    result = {
        "ts": datetime.now().isoformat(),
        "action": "export",
        "total": len(items),
        "items": [
            {"name": r[0], "command": r[1], "icon": r[2], "scope": r[3], "key_path": r[4]}
            for r in items
        ],
    }
    db.close()
    return result


def do_status():
    """Overall context menu manager status."""
    db = init_db()
    total_items = db.execute("SELECT COUNT(*) FROM menu_items").fetchone()[0]
    total_actions = db.execute("SELECT COUNT(*) FROM actions_log").fetchone()[0]
    recent_actions = db.execute(
        "SELECT ts, action, target, success FROM actions_log ORDER BY id DESC LIMIT 5"
    ).fetchall()

    result = {
        "ts": datetime.now().isoformat(),
        "script": "win_context_menu.py",
        "script_id": 245,
        "db": str(DB_PATH),
        "total_menu_items": total_items,
        "total_actions_logged": total_actions,
        "recent_actions": [
            {"ts": r[0], "action": r[1], "target": r[2], "success": bool(r[3])}
            for r in recent_actions
        ],
        "status": "ok",
    }
    db.close()
    return result


def main():
    parser = argparse.ArgumentParser(description="win_context_menu.py — Dynamic context menu manager (#245)")
    parser.add_argument("--scan", action="store_true", help="Scan context menu entries")
    parser.add_argument("--add", type=str, metavar="ACTION", help="Add a context menu entry")
    parser.add_argument("--remove", type=str, metavar="ACTION", help="Remove a context menu entry")
    parser.add_argument("--export", action="store_true", help="Export all menu items")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    if args.scan:
        result = do_scan()
    elif args.add:
        result = do_add(args.add)
    elif args.remove:
        result = do_remove(args.remove)
    elif args.export:
        result = do_export()
    else:
        result = do_status()

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
