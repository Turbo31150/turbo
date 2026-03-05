#!/usr/bin/env python3
"""win_media_organizer.py — Media file organizer with duplicate detection.
COWORK #238 — Batch 107: Windows Gaming & Media

Usage:
    python dev/win_media_organizer.py --scan "C:/Users/franc/Pictures"
    python dev/win_media_organizer.py --organize
    python dev/win_media_organizer.py --duplicates
    python dev/win_media_organizer.py --stats
    python dev/win_media_organizer.py --once
"""
import argparse, json, sqlite3, time, subprocess, os, hashlib
from datetime import datetime
from pathlib import Path

DEV = Path(__file__).parent
DB_PATH = DEV / "data" / "media_organizer.db"

MEDIA_TYPES = {
    "images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".ico", ".tiff", ".raw", ".heic"],
    "videos": [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".mpg", ".mpeg"],
    "audio": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a", ".opus"],
    "documents": [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".csv"],
}

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        directory TEXT NOT NULL,
        total_files INTEGER,
        total_size_mb REAL,
        images INTEGER DEFAULT 0,
        videos INTEGER DEFAULT 0,
        audio INTEGER DEFAULT 0,
        documents INTEGER DEFAULT 0,
        other INTEGER DEFAULT 0,
        duplicates_found INTEGER DEFAULT 0,
        duration_ms INTEGER
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scan_id INTEGER,
        path TEXT NOT NULL,
        filename TEXT NOT NULL,
        extension TEXT,
        media_type TEXT,
        size_bytes INTEGER,
        md5_hash TEXT,
        modified_date TEXT,
        year INTEGER,
        month INTEGER,
        is_duplicate INTEGER DEFAULT 0,
        FOREIGN KEY (scan_id) REFERENCES scans(id)
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS organize_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        source TEXT NOT NULL,
        destination TEXT NOT NULL,
        files_moved INTEGER DEFAULT 0,
        success INTEGER DEFAULT 1
    )""")
    db.commit()
    return db

def get_media_type(ext):
    ext_lower = ext.lower()
    for mtype, extensions in MEDIA_TYPES.items():
        if ext_lower in extensions:
            return mtype
    return "other"

def file_md5(filepath, chunk_size=8192):
    """Calculate MD5 hash of a file (first 1MB for speed)."""
    h = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            # Read first 1MB for fast hashing
            data = f.read(1024 * 1024)
            h.update(data)
        return h.hexdigest()
    except Exception:
        return None

def do_scan(directory):
    db = init_db()
    scan_dir = Path(directory)
    if not scan_dir.exists():
        db.close()
        return {"error": f"Directory not found: {directory}"}

    start = time.time()
    counts = {"images": 0, "videos": 0, "audio": 0, "documents": 0, "other": 0}
    total_size = 0
    file_list = []
    hashes = {}
    duplicates = 0

    try:
        for item in scan_dir.rglob("*"):
            if item.is_file():
                ext = item.suffix.lower()
                mtype = get_media_type(ext)
                counts[mtype] = counts.get(mtype, 0) + 1

                try:
                    stat = item.stat()
                    size = stat.st_size
                    mtime = datetime.fromtimestamp(stat.st_mtime)
                    total_size += size

                    # Hash for duplicate detection (only for media files > 1KB)
                    md5 = None
                    is_dup = 0
                    if mtype in ["images", "videos", "audio"] and size > 1024:
                        md5 = file_md5(str(item))
                        if md5:
                            if md5 in hashes:
                                is_dup = 1
                                duplicates += 1
                            else:
                                hashes[md5] = str(item)

                    file_list.append({
                        "path": str(item),
                        "filename": item.name,
                        "extension": ext,
                        "media_type": mtype,
                        "size_bytes": size,
                        "md5_hash": md5,
                        "modified": mtime.isoformat(),
                        "year": mtime.year,
                        "month": mtime.month,
                        "is_duplicate": is_dup
                    })
                except (PermissionError, OSError):
                    continue

            # Safety: limit to 10000 files
            if len(file_list) >= 10000:
                break

    except (PermissionError, OSError) as e:
        pass

    elapsed = int((time.time() - start) * 1000)

    cursor = db.execute("""INSERT INTO scans (ts, directory, total_files, total_size_mb, images, videos, audio, documents, other, duplicates_found, duration_ms)
                          VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                        (datetime.now().isoformat(), str(scan_dir), len(file_list), round(total_size / (1024*1024), 2),
                         counts["images"], counts["videos"], counts["audio"], counts["documents"], counts["other"],
                         duplicates, elapsed))
    scan_id = cursor.lastrowid

    # Store files (batch insert)
    for f in file_list[:5000]:  # Limit DB entries
        db.execute("""INSERT INTO files (scan_id, path, filename, extension, media_type, size_bytes, md5_hash, modified_date, year, month, is_duplicate)
                      VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                   (scan_id, f["path"], f["filename"], f["extension"], f["media_type"],
                    f["size_bytes"], f["md5_hash"], f["modified"], f["year"], f["month"], f["is_duplicate"]))
    db.commit()

    result = {
        "action": "scan",
        "directory": str(scan_dir),
        "total_files": len(file_list),
        "total_size_mb": round(total_size / (1024*1024), 2),
        "by_type": counts,
        "duplicates_found": duplicates,
        "duration_ms": elapsed,
        "top_10_largest": sorted(
            [{"file": f["filename"], "size_mb": round(f["size_bytes"] / (1024*1024), 2), "type": f["media_type"]}
             for f in file_list], key=lambda x: x["size_mb"], reverse=True
        )[:10],
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_organize():
    """Show organization plan (dry run — does not move files)."""
    db = init_db()
    scan = db.execute("SELECT id, directory FROM scans ORDER BY id DESC LIMIT 1").fetchone()
    if not scan:
        db.close()
        return {"error": "No scans found. Use --scan first."}

    files = db.execute("SELECT filename, media_type, year, month, size_bytes FROM files WHERE scan_id=? ORDER BY year, month",
                       (scan[0],)).fetchall()

    plan = {}
    for f in files:
        dest = f"{f[1]}/{f[2]}/{f[3]:02d}"
        if dest not in plan:
            plan[dest] = {"count": 0, "size_mb": 0}
        plan[dest]["count"] += 1
        plan[dest]["size_mb"] = round(plan[dest]["size_mb"] + (f[4] or 0) / (1024*1024), 2)

    result = {
        "action": "organize_plan",
        "source_directory": scan[1],
        "total_files": len(files),
        "destination_folders": plan,
        "total_folders": len(plan),
        "note": "Dry run — files not moved. Folders follow pattern: type/YYYY/MM",
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_duplicates():
    db = init_db()
    scan = db.execute("SELECT id FROM scans ORDER BY id DESC LIMIT 1").fetchone()
    if not scan:
        db.close()
        return {"error": "No scans found"}

    dups = db.execute("""SELECT f1.filename, f1.path, f1.size_bytes, f1.md5_hash
                        FROM files f1 WHERE f1.scan_id=? AND f1.is_duplicate=1 ORDER BY f1.size_bytes DESC LIMIT 50""",
                      (scan[0],)).fetchall()

    # Group by hash
    hash_groups = {}
    all_hashed = db.execute("SELECT md5_hash, path, size_bytes FROM files WHERE scan_id=? AND md5_hash IS NOT NULL",
                            (scan[0],)).fetchall()
    for h, p, s in all_hashed:
        if h not in hash_groups:
            hash_groups[h] = []
        hash_groups[h].append({"path": p, "size_bytes": s})

    duplicate_groups = {h: files for h, files in hash_groups.items() if len(files) > 1}
    wasted_mb = sum(
        sum(f["size_bytes"] for f in files[1:])
        for files in duplicate_groups.values()
    ) / (1024*1024)

    result = {
        "action": "duplicates",
        "duplicate_groups": len(duplicate_groups),
        "total_duplicate_files": sum(len(f) - 1 for f in duplicate_groups.values()),
        "wasted_space_mb": round(wasted_mb, 2),
        "top_duplicates": [
            {"hash": h, "count": len(files), "files": [f["path"] for f in files[:3]],
             "size_each_mb": round(files[0]["size_bytes"] / (1024*1024), 2)}
            for h, files in sorted(duplicate_groups.items(),
                                   key=lambda x: x[1][0]["size_bytes"], reverse=True)[:10]
        ],
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_stats():
    db = init_db()
    total_scans = db.execute("SELECT COUNT(*) FROM scans").fetchone()[0]
    total_files = db.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    total_size = db.execute("SELECT SUM(total_size_mb) FROM scans").fetchone()[0] or 0
    type_dist = db.execute("SELECT media_type, COUNT(*) FROM files GROUP BY media_type ORDER BY COUNT(*) DESC").fetchall()
    recent = db.execute("SELECT ts, directory, total_files, duplicates_found FROM scans ORDER BY id DESC LIMIT 5").fetchall()

    result = {
        "action": "stats",
        "total_scans": total_scans,
        "total_files_indexed": total_files,
        "total_size_scanned_mb": round(total_size, 2),
        "type_distribution": {r[0]: r[1] for r in type_dist},
        "recent_scans": [{"ts": r[0], "dir": r[1], "files": r[2], "dups": r[3]} for r in recent],
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def do_once():
    db = init_db()
    total_scans = db.execute("SELECT COUNT(*) FROM scans").fetchone()[0]
    total_files = db.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    result = {
        "status": "ok",
        "total_scans": total_scans,
        "total_files_indexed": total_files,
        "supported_types": {k: len(v) for k, v in MEDIA_TYPES.items()},
        "ts": datetime.now().isoformat()
    }
    db.close()
    return result

def main():
    parser = argparse.ArgumentParser(description="Media File Organizer — COWORK #238")
    parser.add_argument("--scan", type=str, metavar="DIR", help="Scan directory for media files")
    parser.add_argument("--organize", action="store_true", help="Show organization plan")
    parser.add_argument("--duplicates", action="store_true", help="Show duplicate files")
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    parser.add_argument("--once", action="store_true", help="One-shot status check")
    args = parser.parse_args()

    if args.scan:
        print(json.dumps(do_scan(args.scan), ensure_ascii=False, indent=2))
    elif args.organize:
        print(json.dumps(do_organize(), ensure_ascii=False, indent=2))
    elif args.duplicates:
        print(json.dumps(do_duplicates(), ensure_ascii=False, indent=2))
    elif args.stats:
        print(json.dumps(do_stats(), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(do_once(), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
