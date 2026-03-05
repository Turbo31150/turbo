#!/usr/bin/env python3
"""desktop_organizer.py — Range le bureau Windows automatiquement.

Organise les fichiers du bureau par type dans des sous-dossiers.
Supporte aussi le nettoyage du dossier Telechargements.

Usage:
    python dev/desktop_organizer.py --scan          # Voir ce qui sera range
    python dev/desktop_organizer.py --organize      # Ranger le bureau
    python dev/desktop_organizer.py --downloads      # Ranger les telechargements
    python dev/desktop_organizer.py --undo           # Annuler le dernier rangement
    python dev/desktop_organizer.py --rules          # Afficher les regles de tri
"""
import argparse
import json
import os
import shutil
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DESKTOP = Path(os.path.expanduser("~/Desktop"))
DOWNLOADS = Path(os.path.expanduser("~/Downloads"))
DB_PATH = Path(__file__).parent / "data" / "organizer.db"

# Regles de tri : extension → dossier
RULES = {
    # Images
    ".jpg": "Images", ".jpeg": "Images", ".png": "Images", ".gif": "Images",
    ".bmp": "Images", ".svg": "Images", ".ico": "Images", ".webp": "Images",
    ".tiff": "Images", ".raw": "Images",
    # Documents
    ".pdf": "Documents", ".doc": "Documents", ".docx": "Documents",
    ".xls": "Documents", ".xlsx": "Documents", ".ppt": "Documents",
    ".pptx": "Documents", ".odt": "Documents", ".ods": "Documents",
    ".txt": "Documents", ".rtf": "Documents", ".csv": "Documents",
    # Videos
    ".mp4": "Videos", ".avi": "Videos", ".mkv": "Videos", ".mov": "Videos",
    ".wmv": "Videos", ".flv": "Videos", ".webm": "Videos", ".m4v": "Videos",
    # Audio
    ".mp3": "Audio", ".wav": "Audio", ".flac": "Audio", ".aac": "Audio",
    ".ogg": "Audio", ".wma": "Audio", ".m4a": "Audio",
    # Archives
    ".zip": "Archives", ".rar": "Archives", ".7z": "Archives",
    ".tar": "Archives", ".gz": "Archives", ".bz2": "Archives",
    # Code
    ".py": "Code", ".js": "Code", ".ts": "Code", ".html": "Code",
    ".css": "Code", ".json": "Code", ".xml": "Code", ".yaml": "Code",
    ".yml": "Code", ".md": "Code", ".sh": "Code", ".bat": "Code",
    ".ps1": "Code", ".sql": "Code",
    # Executables
    ".exe": "Programmes", ".msi": "Programmes", ".appx": "Programmes",
    # Polices
    ".ttf": "Polices", ".otf": "Polices", ".woff": "Polices",
    # Torrents
    ".torrent": "Torrents",
    # Autres data
    ".db": "Data", ".sqlite": "Data", ".sqlite3": "Data",
    ".log": "Logs",
}

# Fichiers/dossiers a ignorer
IGNORE = {
    "desktop.ini", "Thumbs.db", ".DS_Store",
    # Dossiers de tri (ne pas re-trier)
    "Images", "Documents", "Videos", "Audio", "Archives", "Code",
    "Programmes", "Polices", "Torrents", "Data", "Logs", "Divers",
}

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS moves (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, batch_id TEXT,
        source TEXT, destination TEXT,
        filename TEXT, category TEXT,
        undone INTEGER DEFAULT 0)""")
    db.execute("""CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL, batch_id TEXT,
        target TEXT, files_moved INTEGER,
        categories TEXT)""")
    db.commit()
    return db

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
def scan_folder(folder: Path) -> dict:
    """Scanne un dossier et categorise les fichiers."""
    result = {}
    if not folder.exists():
        return result
    for item in folder.iterdir():
        if item.name in IGNORE or item.is_dir():
            continue
        ext = item.suffix.lower()
        category = RULES.get(ext, "Divers")
        if category not in result:
            result[category] = []
        result[category].append({
            "name": item.name,
            "ext": ext,
            "size_mb": round(item.stat().st_size / 1024 / 1024, 2),
            "modified": datetime.fromtimestamp(item.stat().st_mtime).isoformat(),
        })
    return result

def organize_folder(folder: Path, dry_run: bool = False) -> dict:
    """Organise les fichiers d'un dossier par categorie."""
    db = init_db()
    batch_id = f"batch_{int(time.time())}"
    scan = scan_folder(folder)
    moved = 0
    categories_used = set()

    for category, files in scan.items():
        target_dir = folder / category
        if not dry_run:
            target_dir.mkdir(exist_ok=True)
        for f in files:
            src = folder / f["name"]
            dst = target_dir / f["name"]
            # Gerer les doublons
            if dst.exists() and not dry_run:
                stem = dst.stem
                suffix = dst.suffix
                counter = 1
                while dst.exists():
                    dst = target_dir / f"{stem}_{counter}{suffix}"
                    counter += 1
            if not dry_run:
                try:
                    shutil.move(str(src), str(dst))
                    db.execute(
                        "INSERT INTO moves (ts, batch_id, source, destination, filename, category) VALUES (?,?,?,?,?,?)",
                        (time.time(), batch_id, str(src), str(dst), f["name"], category)
                    )
                    moved += 1
                    categories_used.add(category)
                except Exception as e:
                    print(f"Erreur: {f['name']}: {e}", file=sys.stderr)
            else:
                moved += 1
                categories_used.add(category)

    if not dry_run:
        db.execute(
            "INSERT INTO runs (ts, batch_id, target, files_moved, categories) VALUES (?,?,?,?,?)",
            (time.time(), batch_id, str(folder), moved, json.dumps(list(categories_used)))
        )
        db.commit()
    db.close()

    return {
        "action": "dry_run" if dry_run else "organized",
        "folder": str(folder),
        "batch_id": batch_id,
        "files_moved": moved,
        "categories": {cat: len(files) for cat, files in scan.items()},
        "timestamp": datetime.now().isoformat(),
    }

def undo_last(folder: Path = None) -> dict:
    """Annule le dernier batch de rangement."""
    db = init_db()
    # Trouver le dernier batch non annule
    query = "SELECT batch_id FROM runs WHERE 1=1"
    params = []
    if folder:
        query += " AND target = ?"
        params.append(str(folder))
    query += " ORDER BY ts DESC LIMIT 1"
    row = db.execute(query, params).fetchone()
    if not row:
        return {"error": "Aucun rangement a annuler"}
    batch_id = row[0]

    moves = db.execute(
        "SELECT id, source, destination FROM moves WHERE batch_id=? AND undone=0",
        (batch_id,)
    ).fetchall()

    restored = 0
    for mid, src, dst in moves:
        dst_path = Path(dst)
        src_path = Path(src)
        if dst_path.exists():
            try:
                shutil.move(str(dst_path), str(src_path))
                db.execute("UPDATE moves SET undone=1 WHERE id=?", (mid,))
                restored += 1
            except Exception as e:
                print(f"Erreur undo: {dst_path.name}: {e}", file=sys.stderr)

    db.commit()
    db.close()

    # Nettoyer les dossiers vides
    if folder:
        for d in folder.iterdir():
            if d.is_dir() and d.name in RULES.values() and not any(d.iterdir()):
                d.rmdir()

    return {
        "action": "undo",
        "batch_id": batch_id,
        "files_restored": restored,
        "timestamp": datetime.now().isoformat(),
    }

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="JARVIS Desktop Organizer — Range le bureau automatiquement")
    parser.add_argument("--scan", action="store_true", help="Scanner le bureau sans rien bouger")
    parser.add_argument("--organize", action="store_true", help="Ranger le bureau")
    parser.add_argument("--downloads", action="store_true", help="Ranger les telechargements")
    parser.add_argument("--undo", action="store_true", help="Annuler le dernier rangement")
    parser.add_argument("--rules", action="store_true", help="Afficher les regles de tri")
    parser.add_argument("--folder", type=str, help="Dossier custom a organiser")
    args = parser.parse_args()

    if args.rules:
        # Inverser: dossier → extensions
        by_cat = {}
        for ext, cat in sorted(RULES.items()):
            by_cat.setdefault(cat, []).append(ext)
        print(json.dumps(by_cat, indent=2, ensure_ascii=False))
        return

    target = Path(args.folder) if args.folder else (DOWNLOADS if args.downloads else DESKTOP)

    if args.scan:
        result = scan_folder(target)
        total = sum(len(v) for v in result.values())
        output = {
            "folder": str(target),
            "total_files": total,
            "categories": {cat: len(files) for cat, files in result.items()},
            "details": result,
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
    elif args.organize or args.downloads:
        result = organize_folder(target)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.undo:
        result = undo_last(target)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        # Par defaut: scan
        result = scan_folder(target)
        total = sum(len(v) for v in result.values())
        print(json.dumps({"folder": str(target), "total_files": total,
                          "categories": {c: len(f) for c, f in result.items()}},
                         indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
