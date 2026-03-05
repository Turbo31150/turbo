"""Migration commands.py -> SQLite (jarvis.db)

Extrait les 889 JarvisCommand vers la table voice_commands.
Phase 1: extraction seule (--extract)
Phase 2: remplacement commands.py (--replace) apres verification

Usage:
    python scripts/migrate_commands_to_sql.py --extract   # Phase 1: SQL only
    python scripts/migrate_commands_to_sql.py --verify    # Check extraction
    python scripts/migrate_commands_to_sql.py --replace   # Phase 2: rewrite commands.py
    python scripts/migrate_commands_to_sql.py --rollback <backup>
"""

from __future__ import annotations

import argparse
import ast
import json
import logging
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")

REPO_ROOT = Path(__file__).resolve().parent.parent
COMMANDS_PY = REPO_ROOT / "src" / "commands.py"
JARVIS_DB = REPO_ROOT / "data" / "jarvis.db"
BACKUP_DIR = REPO_ROOT / "backups"


class JarvisCommandExtractor:
    """Extrait les JarvisCommand de commands.py via AST parsing."""

    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.commands: list[dict[str, Any]] = []

    def extract(self) -> list[dict[str, Any]]:
        logger.info(f"Parsing {self.filepath.name} ({self.filepath.stat().st_size // 1024} KB)...")

        with open(self.filepath, encoding="utf-8") as f:
            content = f.read()

        tree = ast.parse(content)

        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and self._is_jarvis_command(node):
                cmd = self._parse_jarvis_command(node)
                if cmd:
                    self.commands.append(cmd)

        logger.info(f"Extracted {len(self.commands)} JarvisCommand instances")
        return self.commands

    def _is_jarvis_command(self, node: ast.Call) -> bool:
        return isinstance(node.func, ast.Name) and node.func.id == "JarvisCommand"

    def _parse_jarvis_command(self, node: ast.Call) -> dict[str, Any] | None:
        try:
            args = node.args
            if len(args) < 6:
                return None

            name = self._eval(args[0])
            category = self._eval(args[1])
            description = self._eval(args[2])
            triggers = self._eval(args[3])
            action_type = self._eval(args[4])
            action = self._eval(args[5])
            params = self._eval(args[6]) if len(args) > 6 else {}

            return {
                "name": name,
                "category": category,
                "description": description or "",
                "triggers": triggers if isinstance(triggers, list) else [str(triggers)],
                "action_type": action_type,
                "action": str(action) if action is not None else "",
                "params": params if isinstance(params, (dict, list)) else {},
            }
        except Exception as e:
            logger.warning(f"Failed to parse JarvisCommand at line {getattr(node, 'lineno', '?')}: {e}")
            return None

    def _eval(self, node):
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.List):
            return [self._eval(el) for el in node.elts]
        elif isinstance(node, ast.Dict):
            return {self._eval(k): self._eval(v) for k, v in zip(node.keys, node.values)}
        elif isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Tuple):
            return tuple(self._eval(el) for el in node.elts)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -self._eval(node.operand)
        elif isinstance(node, ast.JoinedStr):
            return "<f-string>"
        else:
            return None


def create_table(conn: sqlite3.Connection):
    logger.info("Creating voice_commands table...")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS voice_commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL,
            description TEXT,
            triggers TEXT NOT NULL,
            action_type TEXT NOT NULL,
            action TEXT NOT NULL,
            params TEXT,
            enabled INTEGER DEFAULT 1,
            usage_count INTEGER DEFAULT 0,
            last_used REAL,
            created_at REAL,
            updated_at REAL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_vc_category ON voice_commands(category)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_vc_enabled ON voice_commands(enabled)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_vc_usage ON voice_commands(usage_count DESC)")
    conn.commit()
    logger.info("Table voice_commands ready")


def insert_commands(conn: sqlite3.Connection, commands: list[dict]) -> tuple[int, int]:
    now = time.time()
    inserted = skipped = 0

    for cmd in commands:
        try:
            conn.execute("""
                INSERT INTO voice_commands
                (name, category, description, triggers, action_type, action, params, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                cmd["name"],
                cmd["category"],
                cmd["description"],
                json.dumps(cmd["triggers"], ensure_ascii=False),
                cmd["action_type"],
                cmd["action"],
                json.dumps(cmd["params"], ensure_ascii=False) if cmd["params"] else "{}",
                now, now,
            ))
            inserted += 1
        except sqlite3.IntegrityError:
            skipped += 1
        except Exception as e:
            logger.warning(f"Insert failed for {cmd.get('name', '?')}: {e}")
            skipped += 1

    conn.commit()
    logger.info(f"Inserted {inserted} commands ({skipped} skipped/duplicates)")
    return inserted, skipped


def verify(conn: sqlite3.Connection):
    logger.info("\n=== Verification ===")

    count = conn.execute("SELECT COUNT(*) FROM voice_commands").fetchone()[0]
    logger.info(f"Total commands in DB: {count}")

    cats = conn.execute("""
        SELECT category, COUNT(*) as cnt
        FROM voice_commands
        GROUP BY category
        ORDER BY cnt DESC
    """).fetchall()

    logger.info(f"Categories ({len(cats)}):")
    for cat, cnt in cats:
        logger.info(f"  {cat}: {cnt}")

    # Test trigger match
    test = conn.execute("""
        SELECT name, triggers FROM voice_commands
        WHERE triggers LIKE '%ouvre chrome%' LIMIT 1
    """).fetchone()
    if test:
        logger.info(f"\nTrigger test: 'ouvre chrome' -> {test[0]}")
    else:
        logger.info("\nTrigger test: 'ouvre chrome' -> no match")

    # Sample random commands
    samples = conn.execute("SELECT name, category, action_type FROM voice_commands ORDER BY RANDOM() LIMIT 5").fetchall()
    logger.info("\nRandom samples:")
    for s in samples:
        logger.info(f"  {s[0]} [{s[1]}] type={s[2]}")


def backup_commands_py() -> Path:
    BACKUP_DIR.mkdir(exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    backup = BACKUP_DIR / f"commands.py.{ts}.bak"
    shutil.copy2(COMMANDS_PY, backup)
    logger.info(f"Backup: {backup} ({backup.stat().st_size // 1024} KB)")
    return backup


def main():
    parser = argparse.ArgumentParser(description="Migrate commands.py to SQLite")
    parser.add_argument("--extract", action="store_true", help="Phase 1: extract to SQL only")
    parser.add_argument("--verify", action="store_true", help="Verify extraction")
    parser.add_argument("--replace", action="store_true", help="Phase 2: rewrite commands.py")
    parser.add_argument("--rollback", type=str, help="Restore from backup")
    args = parser.parse_args()

    if args.rollback:
        src = Path(args.rollback)
        if not src.exists():
            logger.error(f"Backup not found: {src}")
            return
        shutil.copy2(src, COMMANDS_PY)
        logger.info(f"Rolled back from {src}")
        return

    if args.verify:
        conn = sqlite3.Connection(str(JARVIS_DB))
        verify(conn)
        conn.close()
        return

    if args.replace:
        logger.warning("Phase 2 (replace) not yet implemented — waiting for Phase 1 validation.")
        logger.warning("Run --extract first, then --verify, then we implement --replace.")
        return

    if args.extract or (not args.verify and not args.replace):
        logger.info("=" * 60)
        logger.info("PHASE 1: Extract commands.py -> jarvis.db")
        logger.info("=" * 60)

        backup_path = backup_commands_py()

        extractor = JarvisCommandExtractor(COMMANDS_PY)
        commands = extractor.extract()

        if not commands:
            logger.error("No commands extracted! Aborting.")
            return

        conn = sqlite3.connect(str(JARVIS_DB))

        # Drop existing if re-running
        conn.execute("DROP TABLE IF EXISTS voice_commands")
        create_table(conn)
        inserted, skipped = insert_commands(conn, commands)

        verify(conn)
        conn.close()

        logger.info("\n" + "=" * 60)
        logger.info("PHASE 1 COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Backup: {backup_path}")
        logger.info(f"Commands in DB: {inserted}")
        logger.info(f"Next: python scripts/migrate_commands_to_sql.py --verify")
        logger.info(f"Rollback: python scripts/migrate_commands_to_sql.py --rollback {backup_path}")


if __name__ == "__main__":
    main()
