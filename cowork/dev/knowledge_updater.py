#!/usr/bin/env python3
"""
JARVIS Knowledge Base Updater
Standalone Python script for maintaining and updating a knowledge base.
Uses stdlib only, SQLite3, argparse, JSON output.
Windows compatible.
"""

import sqlite3
import json
import argparse
import sys
from datetime import datetime
from pathlib import Path
import os

# Constants
DB_PATH = Path("dev/data/knowledge.db")
KEYWORDS = {
    "system": ["windows", "gpu", "thermal", "process", "cpu", "ram", "disk", "registry", "service"],
    "code": ["python", "javascript", "typescript", "bash", "sql", "api", "function", "class", "module"],
    "trading": ["mexc", "futures", "btc", "eth", "signal", "strategy", "tp", "sl", "position"],
    "cluster": ["m1", "m2", "m3", "ol1", "gemini", "claude", "agent", "node", "orchestrator", "latency"],
    "windows": ["bash", "batch", "cmd", "registry", "user", "admin", "permission", "wsl"],
    "general": []
}


def init_db():
    """Initialize database with required tables."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Create entries table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_created TEXT NOT NULL,
            ts_updated TEXT NOT NULL,
            topic TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT,
            tags TEXT,
            source TEXT
        )
    """)

    # Create updates table for tracking changes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_id INTEGER NOT NULL,
            ts TEXT NOT NULL,
            old_content_preview TEXT,
            new_content_preview TEXT,
            FOREIGN KEY (entry_id) REFERENCES entries (id)
        )
    """)

    conn.commit()
    conn.close()


def auto_categorize(topic, content):
    """Auto-categorize based on keywords."""
    text = f"{topic} {content}".lower()

    for category, keywords in KEYWORDS.items():
        if category == "general":
            continue
        if any(keyword in text for keyword in keywords):
            return category

    return "general"


def extract_tags(content):
    """Extract hashtags from content."""
    tags = []
    words = content.split()
    for word in words:
        if word.startswith("#"):
            tags.append(word[1:])
    return ",".join(tags) if tags else None


def add_entry(topic, content, source=None):
    """Add a new knowledge entry."""
    init_db()
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    now = datetime.now().isoformat()
    category = auto_categorize(topic, content)
    tags = extract_tags(content)

    cursor.execute("""
        INSERT INTO entries (ts_created, ts_updated, topic, content, category, tags, source)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (now, now, topic, content, category, tags, source))

    entry_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {
        "status": "success",
        "message": f"Entry added with ID {entry_id}",
        "entry_id": entry_id,
        "timestamp": now,
        "category": category
    }


def search_entries(query):
    """Search knowledge base by keyword."""
    init_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query_lower = query.lower()
    cursor.execute("""
        SELECT * FROM entries
        WHERE topic LIKE ? OR content LIKE ? OR tags LIKE ?
        ORDER BY ts_updated DESC
    """, (f"%{query_lower}%", f"%{query_lower}%", f"%{query_lower}%"))

    results = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return {
        "status": "success",
        "query": query,
        "count": len(results),
        "results": results
    }


def update_entry(entry_id, new_content):
    """Update an entry and track the change."""
    init_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get old content
    cursor.execute("SELECT content FROM entries WHERE id = ?", (entry_id,))
    row = cursor.fetchone()

    if not row:
        return {"status": "error", "message": f"Entry ID {entry_id} not found"}

    old_content = row["content"]
    old_preview = old_content[:100] + "..." if len(old_content) > 100 else old_content
    new_preview = new_content[:100] + "..." if len(new_content) > 100 else new_content

    now = datetime.now().isoformat()

    # Update entry
    cursor.execute("""
        UPDATE entries
        SET content = ?, ts_updated = ?
        WHERE id = ?
    """, (new_content, now, entry_id))

    # Log update
    cursor.execute("""
        INSERT INTO updates (entry_id, ts, old_content_preview, new_content_preview)
        VALUES (?, ?, ?, ?)
    """, (entry_id, now, old_preview, new_preview))

    conn.commit()
    conn.close()

    return {
        "status": "success",
        "message": f"Entry {entry_id} updated",
        "entry_id": entry_id,
        "timestamp": now,
        "old_preview": old_preview,
        "new_preview": new_preview
    }


def list_entries():
    """List all entries."""
    init_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, topic, category, ts_created, ts_updated, tags
        FROM entries
        ORDER BY ts_updated DESC
    """)

    results = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return {
        "status": "success",
        "total": len(results),
        "entries": results
    }


def list_categories():
    """List all categories."""
    init_db()
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    cursor.execute("""
        SELECT category, COUNT(*) as count
        FROM entries
        GROUP BY category
        ORDER BY count DESC
    """)

    results = [{"category": row[0], "count": row[1]} for row in cursor.fetchall()]
    conn.close()

    return {
        "status": "success",
        "categories": results,
        "total_categories": len(results)
    }


def export_all():
    """Export all entries as JSON."""
    init_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM entries
        ORDER BY ts_updated DESC
    """)

    entries = [dict(row) for row in cursor.fetchall()]

    # Get update history
    cursor.execute("""
        SELECT * FROM updates
        ORDER BY ts DESC
    """)

    updates = [dict(row) for row in cursor.fetchall()]
    conn.close()

    export_data = {
        "exported": datetime.now().isoformat(),
        "total_entries": len(entries),
        "entries": entries,
        "update_history": updates
    }

    return {
        "status": "success",
        "data": export_data
    }


def import_from_file(file_path):
    """Import entries from JSON file."""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except Exception as e:
        return {"status": "error", "message": f"Failed to read file: {e}"}

    if not isinstance(data, dict) or "entries" not in data:
        return {"status": "error", "message": "Invalid JSON format. Expected 'entries' key."}

    init_db()
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    imported_count = 0
    now = datetime.now().isoformat()

    for entry in data.get("entries", []):
        try:
            topic = entry.get("topic", "Unknown")
            content = entry.get("content", "")
            category = entry.get("category", auto_categorize(topic, content))
            tags = entry.get("tags")
            source = entry.get("source")

            cursor.execute("""
                INSERT INTO entries (ts_created, ts_updated, topic, content, category, tags, source)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (now, now, topic, content, category, tags, source))

            imported_count += 1
        except Exception as e:
            print(f"Warning: Failed to import entry: {e}", file=sys.stderr)

    conn.commit()
    conn.close()

    return {
        "status": "success",
        "message": f"Imported {imported_count} entries from {file_path}",
        "imported_count": imported_count
    }


def get_stats():
    """Get knowledge base statistics."""
    init_db()
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM entries")
    total_entries = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM updates")
    total_updates = cursor.fetchone()[0]

    cursor.execute("""
        SELECT category, COUNT(*) as count
        FROM entries
        GROUP BY category
    """)
    categories = {row[0]: row[1] for row in cursor.fetchall()}

    cursor.execute("""
        SELECT AVG(LENGTH(content)) as avg_size,
               MIN(LENGTH(content)) as min_size,
               MAX(LENGTH(content)) as max_size
        FROM entries
    """)
    size_row = cursor.fetchone()

    cursor.execute("""
        SELECT COUNT(DISTINCT tags) FROM entries WHERE tags IS NOT NULL
    """)
    unique_tags = cursor.fetchone()[0]

    # Get database file size
    try:
        db_size = os.path.getsize(str(DB_PATH))
    except:
        db_size = 0

    conn.close()

    return {
        "status": "success",
        "statistics": {
            "total_entries": total_entries,
            "total_updates": total_updates,
            "categories": categories,
            "average_content_size": round(size_row[0]) if size_row[0] else 0,
            "min_content_size": size_row[1],
            "max_content_size": size_row[2],
            "unique_tags": unique_tags,
            "database_size_bytes": db_size,
            "database_path": str(DB_PATH)
        }
    }


def get_recent(limit=20):
    """Get recent entries."""
    init_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM entries
        ORDER BY ts_updated DESC
        LIMIT ?
    """, (limit,))

    results = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return {
        "status": "success",
        "limit": limit,
        "count": len(results),
        "recent": results
    }


def main():
    """Main CLI handler."""
    parser = argparse.ArgumentParser(
        description="JARVIS Knowledge Base Updater",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python knowledge_updater.py --add "GPU Tuning" "M1 thermal threshold is 75C warning, 85C critical"
  python knowledge_updater.py --search "gpu thermal"
  python knowledge_updater.py --update 5 "New content here"
  python knowledge_updater.py --list
  python knowledge_updater.py --categories
  python knowledge_updater.py --stats
  python knowledge_updater.py --recent
  python knowledge_updater.py --export > knowledge.json
  python knowledge_updater.py --import knowledge.json
        """
    )

    parser.add_argument("--add", nargs=2, metavar=("TOPIC", "CONTENT"),
                        help="Add a new knowledge entry")
    parser.add_argument("--search", metavar="QUERY",
                        help="Search knowledge base by keyword")
    parser.add_argument("--update", nargs=2, metavar=("ID", "CONTENT"),
                        help="Update an entry by ID")
    parser.add_argument("--list", action="store_true",
                        help="List all entries")
    parser.add_argument("--categories", action="store_true",
                        help="List all categories with counts")
    parser.add_argument("--export", action="store_true",
                        help="Export all entries as JSON")
    parser.add_argument("--import", metavar="FILE", dest="import_file",
                        help="Import entries from JSON file")
    parser.add_argument("--stats", action="store_true",
                        help="Show knowledge base statistics")
    parser.add_argument("--recent", type=int, nargs="?", const=20, metavar="LIMIT",
                        help="Show recent entries (default: 20)")

    args = parser.parse_args()

    # Dispatch to appropriate function
    result = None

    if args.add:
        result = add_entry(args.add[0], args.add[1])
    elif args.search:
        result = search_entries(args.search)
    elif args.update:
        try:
            entry_id = int(args.update[0])
            result = update_entry(entry_id, args.update[1])
        except ValueError:
            result = {"status": "error", "message": f"Invalid entry ID: {args.update[0]}"}
    elif args.list:
        result = list_entries()
    elif args.categories:
        result = list_categories()
    elif args.export:
        result = export_all()
    elif args.import_file:
        result = import_from_file(args.import_file)
    elif args.stats:
        result = get_stats()
    elif args.recent is not None:
        result = get_recent(args.recent)
    else:
        parser.print_help()
        sys.exit(0)

    # Output as JSON
    if result:
        print(json.dumps(result, indent=2))

    sys.exit(0)


if __name__ == "__main__":
    main()
