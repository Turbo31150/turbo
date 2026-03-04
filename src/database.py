"""JARVIS SQL Database — Persistent SQLite storage for commands, skills, scenarios, validations."""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.database")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "jarvis.db"
ETOILE_DB_PATH = DATA_DIR / "etoile.db"
SNIPER_DB_PATH = DATA_DIR / "sniper.db"


def get_connection(attach: bool = False) -> sqlite3.Connection:
    """Get a connection to the JARVIS database.

    Args:
        attach: If True, ATTACH etoile.db and sniper.db for cross-DB queries.
                Access tables via: etoile.pipeline_dictionary, sniper.signals, etc.
                Main jarvis.db tables remain accessible without prefix.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    if attach:
        _attach_databases(conn)
    return conn


def get_unified_connection() -> sqlite3.Connection:
    """Get a connection with all 3 databases attached (jarvis + etoile + sniper).

    Usage:
        conn = get_unified_connection()
        # jarvis.db tables: commands, scenarios, skills, etc. (no prefix needed)
        # etoile.db tables: etoile.pipeline_dictionary, etoile.domino_chains, etc.
        # sniper.db tables: sniper.signals, sniper.coins, etc.
        conn.execute("SELECT * FROM etoile.pipeline_dictionary WHERE category = ?", ("trading_adv",))
        conn.execute("SELECT * FROM sniper.signals ORDER BY timestamp DESC LIMIT 10")
    """
    return get_connection(attach=True)


@contextmanager
def _db(attach: bool = False):
    """Context manager that guarantees conn.close() even on exceptions."""
    conn = get_connection(attach=attach)
    try:
        yield conn
    finally:
        conn.close()


def _attach_databases(conn: sqlite3.Connection):
    """Attach etoile.db and sniper.db to an existing connection."""
    if ETOILE_DB_PATH.exists():
        # Path from config (not user input) — str() to sanitize PurePath
        conn.execute("ATTACH DATABASE ? AS etoile", (str(ETOILE_DB_PATH),))
    if SNIPER_DB_PATH.exists():
        conn.execute("ATTACH DATABASE ? AS sniper", (str(SNIPER_DB_PATH),))


def init_db():
    """Initialize the database schema."""
    with _db() as conn:
        tables = [
            """CREATE TABLE IF NOT EXISTS commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                triggers TEXT NOT NULL,
                action_type TEXT NOT NULL,
                action TEXT NOT NULL,
                params TEXT DEFAULT '[]',
                confirm INTEGER DEFAULT 0,
                created_at REAL DEFAULT 0,
                usage_count INTEGER DEFAULT 0,
                last_used REAL DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                fail_count INTEGER DEFAULT 0
            )""",
            """CREATE TABLE IF NOT EXISTS skills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT NOT NULL,
                triggers TEXT NOT NULL,
                steps TEXT NOT NULL,
                category TEXT DEFAULT 'custom',
                created_at REAL DEFAULT 0,
                usage_count INTEGER DEFAULT 0,
                last_used REAL DEFAULT 0,
                success_rate REAL DEFAULT 1.0,
                confirm INTEGER DEFAULT 0
            )""",
            """CREATE TABLE IF NOT EXISTS voice_corrections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wrong TEXT NOT NULL,
                correct TEXT NOT NULL,
                category TEXT DEFAULT 'phonetic',
                hit_count INTEGER DEFAULT 0
            )""",
            """CREATE TABLE IF NOT EXISTS scenarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                voice_input TEXT NOT NULL,
                expected_commands TEXT NOT NULL,
                expected_result TEXT NOT NULL,
                difficulty TEXT DEFAULT 'normal',
                created_at REAL DEFAULT 0,
                validated INTEGER DEFAULT 0,
                validation_count INTEGER DEFAULT 0,
                last_validated REAL DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                fail_count INTEGER DEFAULT 0
            )""",
            """CREATE TABLE IF NOT EXISTS validation_cycles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cycle_number INTEGER NOT NULL,
                scenario_id INTEGER,
                scenario_name TEXT NOT NULL,
                voice_input TEXT NOT NULL,
                matched_command TEXT,
                match_score REAL DEFAULT 0,
                expected_command TEXT,
                result TEXT NOT NULL,
                details TEXT DEFAULT '',
                execution_time_ms REAL DEFAULT 0,
                timestamp REAL DEFAULT 0
            )""",
            """CREATE TABLE IF NOT EXISTS action_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                result TEXT DEFAULT '',
                success INTEGER DEFAULT 1,
                source TEXT DEFAULT 'voice',
                timestamp REAL DEFAULT 0
            )""",
        ]

        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_commands_category ON commands(category)",
            "CREATE INDEX IF NOT EXISTS idx_commands_name ON commands(name)",
            "CREATE INDEX IF NOT EXISTS idx_skills_category ON skills(category)",
            "CREATE INDEX IF NOT EXISTS idx_scenarios_category ON scenarios(category)",
            "CREATE INDEX IF NOT EXISTS idx_validation_cycle ON validation_cycles(cycle_number)",
            "CREATE INDEX IF NOT EXISTS idx_validation_result ON validation_cycles(result)",
            "CREATE INDEX IF NOT EXISTS idx_history_timestamp ON action_history(timestamp)",
        ]

        for sql in tables:
            conn.execute(sql)
        for sql in indexes:
            conn.execute(sql)
        conn.commit()


# ═══════════════════════════════════════════════════════════════════════════
# IMPORT FROM EXISTING CODE
# ═══════════════════════════════════════════════════════════════════════════

def import_commands_from_code():
    """Import all commands from commands.py into the database."""
    from src.commands import COMMANDS
    with _db() as conn:
        imported = 0
        for cmd in COMMANDS:
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO commands (name, category, description, triggers, action_type, action, params, confirm)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    cmd.name, cmd.category, cmd.description,
                    json.dumps(cmd.triggers, ensure_ascii=False),
                    cmd.action_type, cmd.action,
                    json.dumps(cmd.params, ensure_ascii=False),
                    1 if cmd.confirm else 0,
                ))
                imported += 1
            except (sqlite3.Error, ValueError) as e:
                logger.warning("Erreur import %s: %s", cmd.name, e)
        conn.commit()
        return imported


def import_skills_from_code():
    """Import all skills from skills.py into the database."""
    from src.skills import load_skills
    with _db() as conn:
        skills = load_skills()
        imported = 0
        for s in skills:
            try:
                steps_data = json.dumps([
                    {"tool": st.tool, "args": st.args, "description": st.description, "wait_for_result": st.wait_for_result}
                    for st in s.steps
                ], ensure_ascii=False)
                conn.execute("""
                    INSERT OR REPLACE INTO skills (name, description, triggers, steps, category, created_at, usage_count, success_rate, confirm)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    s.name, s.description,
                    json.dumps(s.triggers, ensure_ascii=False),
                    steps_data, s.category, s.created_at,
                    s.usage_count, s.success_rate,
                    1 if s.confirm else 0,
                ))
                imported += 1
            except (sqlite3.Error, ValueError) as e:
                logger.warning("Erreur import skill %s: %s", s.name, e)
        conn.commit()
        return imported


def import_corrections_from_code():
    """Import voice corrections from commands.py into the database."""
    from src.commands import VOICE_CORRECTIONS
    with _db() as conn:
        imported = 0
        for wrong, correct in VOICE_CORRECTIONS.items():
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO voice_corrections (wrong, correct, category)
                    VALUES (?, ?, 'phonetic')
                """, (wrong, correct))
                imported += 1
            except sqlite3.Error as exc:
                logger.debug("voice_corrections import skip: %s", exc)
        conn.commit()
        return imported


# ═══════════════════════════════════════════════════════════════════════════
# SCENARIOS CRUD
# ═══════════════════════════════════════════════════════════════════════════

def add_scenario(name: str, description: str, category: str, voice_input: str,
                 expected_commands: list[str], expected_result: str,
                 difficulty: str = "normal") -> int:
    """Add a test scenario."""
    with _db() as conn:
        cur = conn.execute("""
            INSERT OR REPLACE INTO scenarios (name, description, category, voice_input, expected_commands, expected_result, difficulty)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (name, description, category, voice_input,
              json.dumps(expected_commands, ensure_ascii=False),
              expected_result, difficulty))
        conn.commit()
        return cur.lastrowid


def get_all_scenarios() -> list[dict]:
    """Get all scenarios."""
    with _db() as conn:
        rows = conn.execute("SELECT * FROM scenarios ORDER BY category, id").fetchall()
        return [dict(r) for r in rows]


def get_scenario(scenario_id: int) -> dict | None:
    """Get a scenario by ID."""
    with _db() as conn:
        row = conn.execute("SELECT * FROM scenarios WHERE id = ?", (scenario_id,)).fetchone()
        return dict(row) if row else None


# ═══════════════════════════════════════════════════════════════════════════
# VALIDATION RECORDING
# ═══════════════════════════════════════════════════════════════════════════

def record_validation(cycle_number: int, scenario_name: str, voice_input: str,
                      matched_command: str | None, match_score: float,
                      expected_command: str, result: str, details: str = "",
                      execution_time_ms: float = 0, scenario_id: int | None = None):
    """Record a validation cycle result."""
    with _db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS validation_cycles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cycle_number INTEGER NOT NULL,
            scenario_id INTEGER,
            scenario_name TEXT NOT NULL,
            voice_input TEXT NOT NULL,
            matched_command TEXT,
            match_score REAL DEFAULT 0,
            expected_command TEXT,
            result TEXT NOT NULL,
            details TEXT DEFAULT '',
            execution_time_ms REAL DEFAULT 0,
            timestamp REAL DEFAULT 0
        )""")
        conn.execute("""
            INSERT INTO validation_cycles (cycle_number, scenario_id, scenario_name, voice_input,
                                           matched_command, match_score, expected_command, result, details, execution_time_ms, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (cycle_number, scenario_id, scenario_name, voice_input,
              matched_command, match_score, expected_command, result, details, execution_time_ms, time.time()))

        if scenario_id:
            if result == "pass":
                conn.execute("UPDATE scenarios SET validated=1, validation_count=validation_count+1, success_count=success_count+1, last_validated=? WHERE id=?",
                             (time.time(), scenario_id))
            else:
                conn.execute("UPDATE scenarios SET validation_count=validation_count+1, fail_count=fail_count+1, last_validated=? WHERE id=?",
                             (time.time(), scenario_id))
        conn.commit()


# ═══════════════════════════════════════════════════════════════════════════
# STATISTICS
# ═══════════════════════════════════════════════════════════════════════════

def get_stats() -> dict:
    """Get comprehensive database statistics."""
    with _db() as conn:
        stats = {}

        _c = lambda q: (conn.execute(q).fetchone() or (0,))[0]
        stats["commands"] = _c("SELECT COUNT(*) FROM commands")
        stats["skills"] = _c("SELECT COUNT(*) FROM skills")
        stats["corrections"] = _c("SELECT COUNT(*) FROM voice_corrections")
        stats["scenarios"] = _c("SELECT COUNT(*) FROM scenarios")
        stats["scenarios_validated"] = _c("SELECT COUNT(*) FROM scenarios WHERE validated=1")
        stats["history_entries"] = _c("SELECT COUNT(*) FROM action_history")
        stats["validation_cycles"] = _c("SELECT COUNT(*) FROM validation_cycles")

        cats_cmd = conn.execute("SELECT DISTINCT category FROM commands ORDER BY category").fetchall()
        stats["categories_commands"] = [r[0] for r in cats_cmd]
        cats_skill = conn.execute("SELECT DISTINCT category FROM skills ORDER BY category").fetchall()
        stats["categories_skills"] = [r[0] for r in cats_skill]

        total_val = _c("SELECT COUNT(*) FROM validation_cycles")
        pass_val = _c("SELECT COUNT(*) FROM validation_cycles WHERE result='pass'")
        stats["validation_pass_rate"] = round(pass_val / total_val * 100, 1) if total_val > 0 else 0

        last = _c("SELECT MAX(cycle_number) FROM validation_cycles")
        stats["last_cycle"] = last or 0

        return stats


def get_validation_report(cycle_number: int | None = None) -> dict:
    """Get a detailed validation report for a cycle or all cycles."""
    with _db() as conn:
        if cycle_number:
            rows = conn.execute(
                "SELECT * FROM validation_cycles WHERE cycle_number=? ORDER BY id", (cycle_number,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM validation_cycles ORDER BY cycle_number, id").fetchall()

        results = [dict(r) for r in rows]
        total = len(results)
        passed = sum(1 for r in results if r["result"] == "pass")
        failed = sum(1 for r in results if r["result"] == "fail")
        partial = sum(1 for r in results if r["result"] == "partial")
        errors = sum(1 for r in results if r["result"] == "error")

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "partial": partial,
            "errors": errors,
            "pass_rate": round(passed / total * 100, 1) if total > 0 else 0,
            "results": results,
        }


def export_full_db() -> dict:
    """Export the entire database as a dictionary for GitHub/documentation."""
    with _db() as conn:
        commands = [dict(r) for r in conn.execute("SELECT * FROM commands ORDER BY category, id").fetchall()]
        skills = [dict(r) for r in conn.execute("SELECT * FROM skills ORDER BY category, id").fetchall()]
        corrections = [dict(r) for r in conn.execute("SELECT * FROM voice_corrections ORDER BY id").fetchall()]
        scenarios = [dict(r) for r in conn.execute("SELECT * FROM scenarios ORDER BY category, id").fetchall()]

    # get_stats() opens its own connection via _db() — safe to call outside the with block
    stats = get_stats()
    return {
        "version": "10.1",
        "exported_at": time.time(),
        "stats": stats,
        "commands": commands,
        "skills": skills,
        "voice_corrections": corrections,
        "scenarios": scenarios,
    }


# ═══════════════════════════════════════════════════════════════════════════
# CROSS-DB QUERIES (unified access via ATTACH)
# ═══════════════════════════════════════════════════════════════════════════

def get_unified_stats() -> dict:
    """Get comprehensive stats across all 3 databases."""
    with _db(attach=True) as conn:
        stats = {}

        stats["commands"] = conn.execute("SELECT COUNT(*) FROM commands").fetchone()[0]
        stats["skills"] = conn.execute("SELECT COUNT(*) FROM skills").fetchone()[0]
        stats["scenarios"] = conn.execute("SELECT COUNT(*) FROM scenarios").fetchone()[0]
        stats["corrections"] = conn.execute("SELECT COUNT(*) FROM voice_corrections").fetchone()[0]

        try:
            stats["pipelines"] = conn.execute("SELECT COUNT(*) FROM etoile.pipeline_dictionary").fetchone()[0]
            stats["domino_chains"] = conn.execute("SELECT COUNT(*) FROM etoile.domino_chains").fetchone()[0]
            stats["scenario_weights"] = conn.execute("SELECT COUNT(*) FROM etoile.scenario_weights").fetchone()[0]
            stats["cluster_agents"] = conn.execute("SELECT COUNT(*) FROM etoile.agents").fetchone()[0]
            stats["map_entries"] = conn.execute("SELECT COUNT(*) FROM etoile.map").fetchone()[0]
        except sqlite3.OperationalError as exc:
            logger.debug("etoile.db stats unavailable: %s", exc)

        try:
            stats["trading_signals"] = conn.execute("SELECT COUNT(*) FROM sniper.signals").fetchone()[0]
            stats["trading_coins"] = conn.execute("SELECT COUNT(*) FROM sniper.coins").fetchone()[0]
            stats["trading_scans"] = conn.execute("SELECT COUNT(*) FROM sniper.scans").fetchone()[0]
        except sqlite3.OperationalError as exc:
            logger.debug("sniper.db stats unavailable: %s", exc)

        return stats


def find_pipeline_for_voice(voice_input: str) -> dict | None:
    """Find a matching pipeline for a voice command, searching across both DBs."""
    with _db(attach=True) as conn:
        row = conn.execute(
            "SELECT name, action_type, action, category FROM commands WHERE triggers LIKE ?",
            (f"%{voice_input}%",)
        ).fetchone()
        if row:
            return {"source": "jarvis.commands", **dict(row)}

        try:
            row = conn.execute(
                "SELECT pipeline_id, trigger_phrase, steps, category FROM etoile.pipeline_dictionary WHERE trigger_phrase LIKE ?",
                (f"%{voice_input}%",)
            ).fetchone()
            if row:
                return {"source": "etoile.pipeline_dictionary", **dict(row)}
        except sqlite3.OperationalError as exc:
            logger.debug("etoile.db search unavailable: %s", exc)

        return None


def get_routing_weights(scenario: str) -> list[dict]:
    """Get agent routing weights for a scenario from etoile.db."""
    with _db(attach=True) as conn:
        try:
            rows = conn.execute(
                "SELECT agent, weight, priority, chain_next, description FROM etoile.scenario_weights WHERE scenario = ? ORDER BY priority",
                (scenario,)
            ).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.OperationalError:
            return []


# ═══════════════════════════════════════════════════════════════════════════
# SCHEMA MIGRATIONS v2 — Version-tracked schema evolution
# ═══════════════════════════════════════════════════════════════════════════

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"

_BUILT_IN_MIGRATIONS: dict[str, list[str]] = {
    "002_chat_history": [
        """CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            agent TEXT,
            model TEXT,
            latency_ms REAL,
            tokens INTEGER,
            timestamp REAL DEFAULT 0
        )""",
        "CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_history(session_id)",
        "CREATE INDEX IF NOT EXISTS idx_chat_timestamp ON chat_history(timestamp)",
    ],
    "003_command_analytics": [
        """CREATE TABLE IF NOT EXISTS command_analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            command_name TEXT NOT NULL,
            duration_ms REAL DEFAULT 0,
            success INTEGER DEFAULT 1,
            source TEXT DEFAULT 'voice',
            params TEXT,
            timestamp REAL DEFAULT 0
        )""",
        "CREATE INDEX IF NOT EXISTS idx_cmd_analytics_name ON command_analytics(command_name)",
    ],
    "004_maintenance_log": [
        """CREATE TABLE IF NOT EXISTS maintenance_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operation TEXT NOT NULL,
            db_name TEXT NOT NULL,
            duration_ms REAL DEFAULT 0,
            details TEXT,
            timestamp REAL DEFAULT 0
        )""",
    ],
}


def _ensure_migrations_table(conn: sqlite3.Connection):
    conn.execute("""CREATE TABLE IF NOT EXISTS schema_migrations (
        version TEXT PRIMARY KEY,
        applied_at REAL NOT NULL,
        description TEXT
    )""")
    conn.commit()


def get_applied_migrations(conn: sqlite3.Connection | None = None) -> set[str]:
    """Get set of already-applied migration versions."""
    close = False
    if conn is None:
        conn = get_connection()
        close = True
    try:
        _ensure_migrations_table(conn)
        rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
        return {r[0] for r in rows}
    finally:
        if close:
            conn.close()


def apply_migrations(db_path: Path | None = None) -> list[str]:
    """Apply pending migrations (built-in + SQL files from migrations/ dir).

    Returns list of applied migration version strings.
    """
    target = str(db_path) if db_path else str(DB_PATH)
    conn = sqlite3.connect(target)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _ensure_migrations_table(conn)

    applied = get_applied_migrations(conn)
    newly_applied = []

    # Built-in migrations
    for version in sorted(_BUILT_IN_MIGRATIONS.keys()):
        if version not in applied:
            try:
                for sql in _BUILT_IN_MIGRATIONS[version]:
                    conn.execute(sql)
                conn.execute(
                    "INSERT INTO schema_migrations (version, applied_at, description) VALUES (?, ?, ?)",
                    (version, time.time(), f"built-in: {version}"),
                )
                conn.commit()
                newly_applied.append(version)
                logger.info("Migration %s applied", version)
            except sqlite3.Error as e:
                logger.error("Migration %s failed: %s", version, e)
                conn.rollback()

    # SQL file migrations from migrations/ directory
    if MIGRATIONS_DIR.exists():
        for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
            version = sql_file.stem
            if version not in applied:
                try:
                    sql = sql_file.read_text(encoding="utf-8")
                    conn.executescript(sql)
                    conn.execute(
                        "INSERT INTO schema_migrations (version, applied_at, description) VALUES (?, ?, ?)",
                        (version, time.time(), f"file: {sql_file.name}"),
                    )
                    conn.commit()
                    newly_applied.append(version)
                    logger.info("Migration %s applied from %s", version, sql_file.name)
                except sqlite3.Error as e:
                    logger.error("Migration %s failed: %s", version, e)

    conn.close()
    return newly_applied


# ═══════════════════════════════════════════════════════════════════════════
# AUTO-MAINTENANCE — VACUUM, ANALYZE, integrity checks
# ═══════════════════════════════════════════════════════════════════════════

_MAINTENANCE_INTERVAL = 86400  # 24 hours
_MAINTENANCE_FILE = DATA_DIR / "last_maintenance.json"


def _load_maintenance_state() -> dict:
    try:
        return json.loads(_MAINTENANCE_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return {}


def _save_maintenance_state(state: dict):
    _MAINTENANCE_FILE.write_text(json.dumps(state, indent=2))


def auto_maintenance(force: bool = False) -> dict:
    """Run VACUUM + ANALYZE on all databases if interval elapsed.

    Returns dict with operations performed and durations.
    """
    state = _load_maintenance_state()
    last = state.get("last_run", 0)
    now = time.time()

    if not force and (now - last) < _MAINTENANCE_INTERVAL:
        return {"skipped": True, "next_in_hours": round((_MAINTENANCE_INTERVAL - (now - last)) / 3600, 1)}

    results = {}
    for db_name, db_path in [("jarvis", DB_PATH), ("etoile", ETOILE_DB_PATH), ("sniper", SNIPER_DB_PATH)]:
        if not db_path.exists():
            continue
        t0 = time.time()
        try:
            conn = sqlite3.connect(str(db_path))
            # Integrity check
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            # VACUUM (requires no active transactions)
            conn.execute("VACUUM")
            conn.execute("ANALYZE")
            duration = round((time.time() - t0) * 1000, 1)
            results[db_name] = {"status": "ok", "integrity": integrity, "duration_ms": duration}
            conn.close()
        except sqlite3.Error as e:
            results[db_name] = {"status": "error", "error": str(e)}

    state["last_run"] = now
    state["last_results"] = results
    _save_maintenance_state(state)

    # Log to maintenance_log table
    try:
        with _db() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS maintenance_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation TEXT NOT NULL, db_name TEXT NOT NULL,
                duration_ms REAL DEFAULT 0, details TEXT, timestamp REAL DEFAULT 0
            )""")
            for db_name, info in results.items():
                conn.execute(
                    "INSERT INTO maintenance_log (operation, db_name, duration_ms, details, timestamp) VALUES (?, ?, ?, ?, ?)",
                    ("auto_maintenance", db_name, info.get("duration_ms", 0), json.dumps(info), now),
                )
            conn.commit()
    except sqlite3.Error:
        pass

    return {"performed": True, "results": results}


# ═══════════════════════════════════════════════════════════════════════════
# BACKUP / RESTORE
# ═══════════════════════════════════════════════════════════════════════════

BACKUP_DIR = DATA_DIR / "backups"


def backup_database(db_path: Path | None = None, label: str = "") -> Path:
    """Create a timestamped backup of a database using SQLite backup API.

    Returns path to backup file.
    """
    source = db_path or DB_PATH
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    name = source.stem
    suffix = f"_{label}" if label else ""
    backup_path = BACKUP_DIR / f"{name}_{timestamp}{suffix}.db"

    src_conn = sqlite3.connect(str(source))
    dst_conn = sqlite3.connect(str(backup_path))
    src_conn.backup(dst_conn)
    src_conn.close()
    dst_conn.close()

    logger.info("Backup created: %s", backup_path)
    return backup_path


def list_backups() -> list[dict]:
    """List available database backups."""
    if not BACKUP_DIR.exists():
        return []
    backups = []
    for f in sorted(BACKUP_DIR.glob("*.db"), reverse=True):
        backups.append({
            "file": f.name,
            "path": str(f),
            "size_kb": round(f.stat().st_size / 1024, 1),
            "created": f.stat().st_mtime,
        })
    return backups


def restore_database(backup_path: Path, target_path: Path | None = None) -> bool:
    """Restore a database from backup."""
    target = target_path or DB_PATH
    if not backup_path.exists():
        logger.error("Backup not found: %s", backup_path)
        return False

    # Safety: backup current before restore
    backup_database(target, label="pre_restore")

    src = sqlite3.connect(str(backup_path))
    dst = sqlite3.connect(str(target))
    src.backup(dst)
    src.close()
    dst.close()

    logger.info("Restored %s from %s", target, backup_path)
    return True


def get_db_health() -> dict:
    """Get health status of all databases."""
    health = {}
    for db_name, db_path in [("jarvis", DB_PATH), ("etoile", ETOILE_DB_PATH), ("sniper", SNIPER_DB_PATH)]:
        if not db_path.exists():
            health[db_name] = {"status": "missing"}
            continue
        try:
            conn = sqlite3.connect(str(db_path))
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            tables = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
            size_kb = round(db_path.stat().st_size / 1024, 1)
            journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
            conn.close()
            health[db_name] = {
                "status": "ok" if integrity == "ok" else "corrupted",
                "integrity": integrity,
                "tables": tables,
                "size_kb": size_kb,
                "journal_mode": journal,
            }
        except sqlite3.Error as e:
            health[db_name] = {"status": "error", "error": str(e)}

    maintenance = _load_maintenance_state()
    health["last_maintenance"] = maintenance.get("last_run", 0)
    health["backups"] = len(list_backups())
    return health
