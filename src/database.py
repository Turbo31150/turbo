"""JARVIS SQL Database — Persistent SQLite storage for commands, skills, scenarios, validations."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

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


def _attach_databases(conn: sqlite3.Connection):
    """Attach etoile.db and sniper.db to an existing connection."""
    if ETOILE_DB_PATH.exists():
        conn.execute(f"ATTACH DATABASE '{ETOILE_DB_PATH}' AS etoile")
    if SNIPER_DB_PATH.exists():
        conn.execute(f"ATTACH DATABASE '{SNIPER_DB_PATH}' AS sniper")


def init_db():
    """Initialize the database schema."""
    conn = get_connection()

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
    conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# IMPORT FROM EXISTING CODE
# ═══════════════════════════════════════════════════════════════════════════

def import_commands_from_code():
    """Import all commands from commands.py into the database."""
    from src.commands import COMMANDS
    conn = get_connection()
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
        except Exception as e:
            print(f"  Erreur import {cmd.name}: {e}")
    conn.commit()
    conn.close()
    return imported


def import_skills_from_code():
    """Import all skills from skills.py into the database."""
    from src.skills import load_skills
    from dataclasses import asdict
    conn = get_connection()
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
        except Exception as e:
            print(f"  Erreur import skill {s.name}: {e}")
    conn.commit()
    conn.close()
    return imported


def import_corrections_from_code():
    """Import voice corrections from commands.py into the database."""
    from src.commands import VOICE_CORRECTIONS
    conn = get_connection()
    imported = 0
    for wrong, correct in VOICE_CORRECTIONS.items():
        try:
            conn.execute("""
                INSERT OR IGNORE INTO voice_corrections (wrong, correct, category)
                VALUES (?, ?, 'phonetic')
            """, (wrong, correct))
            imported += 1
        except Exception:
            pass
    conn.commit()
    conn.close()
    return imported


# ═══════════════════════════════════════════════════════════════════════════
# SCENARIOS CRUD
# ═══════════════════════════════════════════════════════════════════════════

def add_scenario(name: str, description: str, category: str, voice_input: str,
                 expected_commands: list[str], expected_result: str,
                 difficulty: str = "normal") -> int:
    """Add a test scenario."""
    conn = get_connection()
    cur = conn.execute("""
        INSERT OR REPLACE INTO scenarios (name, description, category, voice_input, expected_commands, expected_result, difficulty)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (name, description, category, voice_input,
          json.dumps(expected_commands, ensure_ascii=False),
          expected_result, difficulty))
    conn.commit()
    sid = cur.lastrowid
    conn.close()
    return sid


def get_all_scenarios() -> list[dict]:
    """Get all scenarios."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM scenarios ORDER BY category, id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_scenario(scenario_id: int) -> dict | None:
    """Get a scenario by ID."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM scenarios WHERE id = ?", (scenario_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ═══════════════════════════════════════════════════════════════════════════
# VALIDATION RECORDING
# ═══════════════════════════════════════════════════════════════════════════

def record_validation(cycle_number: int, scenario_name: str, voice_input: str,
                      matched_command: str | None, match_score: float,
                      expected_command: str, result: str, details: str = "",
                      execution_time_ms: float = 0, scenario_id: int | None = None):
    """Record a validation cycle result."""
    conn = get_connection()
    # Ensure table exists inline
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

    # Update scenario stats
    if scenario_id:
        if result == "pass":
            conn.execute("UPDATE scenarios SET validated=1, validation_count=validation_count+1, success_count=success_count+1, last_validated=? WHERE id=?",
                         (time.time(), scenario_id))
        else:
            conn.execute("UPDATE scenarios SET validation_count=validation_count+1, fail_count=fail_count+1, last_validated=? WHERE id=?",
                         (time.time(), scenario_id))
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# STATISTICS
# ═══════════════════════════════════════════════════════════════════════════

def get_stats() -> dict:
    """Get comprehensive database statistics."""
    conn = get_connection()
    stats = {}

    stats["commands"] = conn.execute("SELECT COUNT(*) FROM commands").fetchone()[0]
    stats["skills"] = conn.execute("SELECT COUNT(*) FROM skills").fetchone()[0]
    stats["corrections"] = conn.execute("SELECT COUNT(*) FROM voice_corrections").fetchone()[0]
    stats["scenarios"] = conn.execute("SELECT COUNT(*) FROM scenarios").fetchone()[0]
    stats["scenarios_validated"] = conn.execute("SELECT COUNT(*) FROM scenarios WHERE validated=1").fetchone()[0]
    stats["history_entries"] = conn.execute("SELECT COUNT(*) FROM action_history").fetchone()[0]
    stats["validation_cycles"] = conn.execute("SELECT COUNT(*) FROM validation_cycles").fetchone()[0]

    # Categories
    cats_cmd = conn.execute("SELECT DISTINCT category FROM commands ORDER BY category").fetchall()
    stats["categories_commands"] = [r[0] for r in cats_cmd]
    cats_skill = conn.execute("SELECT DISTINCT category FROM skills ORDER BY category").fetchall()
    stats["categories_skills"] = [r[0] for r in cats_skill]

    # Validation pass rate
    total_val = conn.execute("SELECT COUNT(*) FROM validation_cycles").fetchone()[0]
    pass_val = conn.execute("SELECT COUNT(*) FROM validation_cycles WHERE result='pass'").fetchone()[0]
    stats["validation_pass_rate"] = round(pass_val / total_val * 100, 1) if total_val > 0 else 0

    # Last cycle
    last = conn.execute("SELECT MAX(cycle_number) FROM validation_cycles").fetchone()[0]
    stats["last_cycle"] = last or 0

    conn.close()
    return stats


def get_validation_report(cycle_number: int | None = None) -> dict:
    """Get a detailed validation report for a cycle or all cycles."""
    conn = get_connection()

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

    conn.close()
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
    conn = get_connection()

    commands = [dict(r) for r in conn.execute("SELECT * FROM commands ORDER BY category, id").fetchall()]
    skills = [dict(r) for r in conn.execute("SELECT * FROM skills ORDER BY category, id").fetchall()]
    corrections = [dict(r) for r in conn.execute("SELECT * FROM voice_corrections ORDER BY id").fetchall()]
    scenarios = [dict(r) for r in conn.execute("SELECT * FROM scenarios ORDER BY category, id").fetchall()]
    stats = get_stats()

    conn.close()
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
    conn = get_unified_connection()
    stats = {}

    # jarvis.db (main)
    stats["commands"] = conn.execute("SELECT COUNT(*) FROM commands").fetchone()[0]
    stats["skills"] = conn.execute("SELECT COUNT(*) FROM skills").fetchone()[0]
    stats["scenarios"] = conn.execute("SELECT COUNT(*) FROM scenarios").fetchone()[0]
    stats["corrections"] = conn.execute("SELECT COUNT(*) FROM voice_corrections").fetchone()[0]

    # etoile.db
    try:
        stats["pipelines"] = conn.execute("SELECT COUNT(*) FROM etoile.pipeline_dictionary").fetchone()[0]
        stats["domino_chains"] = conn.execute("SELECT COUNT(*) FROM etoile.domino_chains").fetchone()[0]
        stats["scenario_weights"] = conn.execute("SELECT COUNT(*) FROM etoile.scenario_weights").fetchone()[0]
        stats["cluster_agents"] = conn.execute("SELECT COUNT(*) FROM etoile.agents").fetchone()[0]
        stats["map_entries"] = conn.execute("SELECT COUNT(*) FROM etoile.map").fetchone()[0]
    except sqlite3.OperationalError:
        pass

    # sniper.db
    try:
        stats["trading_signals"] = conn.execute("SELECT COUNT(*) FROM sniper.signals").fetchone()[0]
        stats["trading_coins"] = conn.execute("SELECT COUNT(*) FROM sniper.coins").fetchone()[0]
        stats["trading_scans"] = conn.execute("SELECT COUNT(*) FROM sniper.scans").fetchone()[0]
    except sqlite3.OperationalError:
        pass

    conn.close()
    return stats


def find_pipeline_for_voice(voice_input: str) -> dict | None:
    """Find a matching pipeline for a voice command, searching across both DBs."""
    conn = get_unified_connection()

    # Search in jarvis.db commands first
    row = conn.execute(
        "SELECT name, action_type, action, category FROM commands WHERE triggers LIKE ?",
        (f"%{voice_input}%",)
    ).fetchone()
    if row:
        conn.close()
        return {"source": "jarvis.commands", **dict(row)}

    # Search in etoile.db pipeline_dictionary
    try:
        row = conn.execute(
            "SELECT pipeline_id, trigger_phrase, steps, category FROM etoile.pipeline_dictionary WHERE trigger_phrase LIKE ?",
            (f"%{voice_input}%",)
        ).fetchone()
        if row:
            conn.close()
            return {"source": "etoile.pipeline_dictionary", **dict(row)}
    except sqlite3.OperationalError:
        pass

    conn.close()
    return None


def get_routing_weights(scenario: str) -> list[dict]:
    """Get agent routing weights for a scenario from etoile.db."""
    conn = get_unified_connection()
    try:
        rows = conn.execute(
            "SELECT agent, weight, priority, chain_next, description FROM etoile.scenario_weights WHERE scenario = ? ORDER BY priority",
            (scenario,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        conn.close()
        return []
