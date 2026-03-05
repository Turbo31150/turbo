#!/usr/bin/env python3
"""JARVIS Win Backup — Backup automatique fichiers importants."""
import json, sys, os, shutil, zipfile
from datetime import datetime

TELEGRAM_TOKEN = "TELEGRAM_TOKEN_REDACTED"
TELEGRAM_CHAT = "2010747443"
BACKUP_DIR = "F:/BACKUP_JARVIS"

TARGETS = {
    "configs": [
        "C:/Users/franc/.claude/CLAUDE.md",
        "C:/Users/franc/.openclaw/openclaw.json",
        "F:/BUREAU/turbo/pyproject.toml",
        "F:/BUREAU/turbo/.env",
    ],
    "databases": [
        "F:/BUREAU/etoile.db",
        "F:/BUREAU/turbo/data/jarvis.db",
        "F:/BUREAU/turbo/data/sniper.db",
        "F:/BUREAU/turbo/finetuning/finetuning.db",
    ],
    "scripts": [
        "C:/Users/franc/.openclaw/workspace/dev/",
        "F:/BUREAU/turbo/scripts/",
    ],
    "workspace": [
        "C:/Users/franc/.openclaw/workspace/TOOLS.md",
        "C:/Users/franc/.openclaw/workspace/COWORK_TASKS.md",
    ],
}

def send_telegram(msg):
    import urllib.request
    data = json.dumps({"chat_id": TELEGRAM_CHAT, "text": msg}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                                 data=data, headers={"Content-Type": "application/json"})
    try: urllib.request.urlopen(req, timeout=10)
    except: pass

def backup_files():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"jarvis_backup_{ts}"
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    os.makedirs(backup_path, exist_ok=True)

    stats = {"files": 0, "dirs": 0, "size": 0, "errors": []}

    for category, paths in TARGETS.items():
        cat_dir = os.path.join(backup_path, category)
        os.makedirs(cat_dir, exist_ok=True)
        for path in paths:
            path = path.replace("/", os.sep)
            try:
                if os.path.isdir(path):
                    dest = os.path.join(cat_dir, os.path.basename(path.rstrip("/\\")))
                    shutil.copytree(path, dest, dirs_exist_ok=True)
                    stats["dirs"] += 1
                elif os.path.isfile(path):
                    shutil.copy2(path, cat_dir)
                    stats["files"] += 1
                    stats["size"] += os.path.getsize(path)
                else:
                    stats["errors"].append(f"Not found: {path}")
            except Exception as e:
                stats["errors"].append(f"{path}: {str(e)[:80]}")

    # Zip
    zip_path = f"{backup_path}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(backup_path):
            for f in files:
                fp = os.path.join(root, f)
                arcname = os.path.relpath(fp, backup_path)
                zf.write(fp, arcname)

    zip_size_mb = round(os.path.getsize(zip_path) / 1048576, 1)

    # Cleanup unzipped
    shutil.rmtree(backup_path, ignore_errors=True)

    stats["zip"] = zip_path
    stats["zip_mb"] = zip_size_mb

    return stats

def cleanup_old_backups(keep=5):
    if not os.path.exists(BACKUP_DIR):
        return 0
    zips = sorted([f for f in os.listdir(BACKUP_DIR) if f.endswith(".zip")])
    removed = 0
    while len(zips) > keep:
        old = zips.pop(0)
        os.remove(os.path.join(BACKUP_DIR, old))
        removed += 1
    return removed

if __name__ == "__main__":
    os.makedirs(BACKUP_DIR, exist_ok=True)

    if "--once" in sys.argv:
        stats = backup_files()
        removed = cleanup_old_backups()
        summary = (f"[JARVIS BACKUP] {datetime.now().strftime('%H:%M')}\n"
                   f"Fichiers: {stats['files']} | Dossiers: {stats['dirs']}\n"
                   f"Archive: {stats['zip_mb']} MB\n"
                   f"Anciens supprimés: {removed}")
        if stats["errors"]:
            summary += f"\nErreurs: {len(stats['errors'])}"
        print(summary)
        if "--notify" in sys.argv:
            send_telegram(summary)
    elif "--loop" in sys.argv:
        import time
        interval = 86400  # 24h
        print(f"Backup every {interval}s... Ctrl+C to stop")
        while True:
            stats = backup_files()
            cleanup_old_backups()
            send_telegram(f"[JARVIS BACKUP] {stats['zip_mb']}MB | {stats['files']} files | {stats.get('zip','?')}")
            time.sleep(interval)
    else:
        print("Usage: win_backup.py --once [--notify] | --loop")
