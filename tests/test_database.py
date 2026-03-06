"""Tests for src/database.py — JARVIS SQLite persistent storage.

Covers: connection, table creation, CRUD operations, migrations, integrity checks,
backup/restore, maintenance, cross-DB queries, statistics, and export.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

# Project root on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

import src.database as db


# ---------------------------------------------------------------------------
# Helpers — redirect all DB paths to tmp_path so tests are fully isolated
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolate_db(tmp_path, monkeypatch):
    """Redirect every module-level path constant into tmp_path."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    monkeypatch.setattr(db, "DATA_DIR", data_dir)
    monkeypatch.setattr(db, "DB_PATH", data_dir / "jarvis.db")
    monkeypatch.setattr(db, "ETOILE_DB_PATH", data_dir / "etoile.db")
    monkeypatch.setattr(db, "SNIPER_DB_PATH", data_dir / "sniper.db")
    monkeypatch.setattr(db, "BACKUP_DIR", data_dir / "backups")
    monkeypatch.setattr(db, "_MAINTENANCE_FILE", data_dir / "last_maintenance.json")
    monkeypatch.setattr(db, "MIGRATIONS_DIR", tmp_path / "migrations")


def _create_etoile(path: Path):
    """Create a minimal etoile.db with expected tables."""
    conn = sqlite3.connect(str(path))
    conn.execute("""CREATE TABLE pipeline_dictionary (
        pipeline_id INTEGER PRIMARY KEY, trigger_phrase TEXT, steps TEXT, category TEXT)""")
    conn.execute("""CREATE TABLE domino_chains (id INTEGER PRIMARY KEY, name TEXT)""")
    conn.execute("""CREATE TABLE scenario_weights (
        id INTEGER PRIMARY KEY, scenario TEXT, agent TEXT, weight REAL,
        priority INTEGER, chain_next TEXT, description TEXT)""")
    conn.execute("""CREATE TABLE agents (id INTEGER PRIMARY KEY, name TEXT)""")
    conn.execute("""CREATE TABLE map (id INTEGER PRIMARY KEY, key TEXT)""")
    conn.commit()
    conn.close()


def _create_sniper(path: Path):
    """Create a minimal sniper.db with expected tables."""
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE signals (id INTEGER PRIMARY KEY, timestamp REAL)")
    conn.execute("CREATE TABLE coins (id INTEGER PRIMARY KEY, symbol TEXT)")
    conn.execute("CREATE TABLE scans (id INTEGER PRIMARY KEY, result TEXT)")
    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# CONNECTION
# ═══════════════════════════════════════════════════════════════════════════

class TestConnection:
    def test_get_connection_creates_db(self):
        """get_connection should create the database file and set pragmas."""
        conn = db.get_connection()
        try:
            assert db.DB_PATH.exists()
            journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
            assert journal == "wal"
            fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
            assert fk == 1
        finally:
            conn.close()

    def test_get_connection_row_factory(self):
        """Rows should be accessible by column name via sqlite3.Row."""
        db.init_db()
        conn = db.get_connection()
        try:
            conn.execute(
                "INSERT INTO commands (name, category, description, triggers, action_type, action)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                ("test_cmd", "test", "desc", "[]", "python", "pass"),
            )
            conn.commit()
            row = conn.execute("SELECT name, category FROM commands WHERE name='test_cmd'").fetchone()
            assert row["name"] == "test_cmd"
            assert row["category"] == "test"
        finally:
            conn.close()

    def test_db_context_manager_closes(self):
        """_db() context manager should close the connection on exit."""
        with db._db() as conn:
            conn.execute("SELECT 1")
        # After exiting, the connection should be closed — further operations raise
        with pytest.raises(Exception):
            conn.execute("SELECT 1")

    def test_get_unified_connection_attaches(self):
        """get_unified_connection should ATTACH etoile and sniper when they exist."""
        _create_etoile(db.ETOILE_DB_PATH)
        _create_sniper(db.SNIPER_DB_PATH)
        conn = db.get_unified_connection()
        try:
            # Should be able to query attached databases
            count = conn.execute("SELECT COUNT(*) FROM etoile.pipeline_dictionary").fetchone()[0]
            assert count == 0
            count = conn.execute("SELECT COUNT(*) FROM sniper.signals").fetchone()[0]
            assert count == 0
        finally:
            conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# SCHEMA INIT
# ═══════════════════════════════════════════════════════════════════════════

class TestInitDb:
    def test_init_creates_all_tables(self):
        """init_db should create all 6 core tables."""
        db.init_db()
        conn = db.get_connection()
        try:
            tables = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            expected = {
                "commands", "skills", "voice_corrections",
                "scenarios", "validation_cycles", "action_history",
            }
            assert expected.issubset(tables)
        finally:
            conn.close()

    def test_init_creates_indexes(self):
        """init_db should create the expected indexes."""
        db.init_db()
        conn = db.get_connection()
        try:
            indexes = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
                ).fetchall()
            }
            assert "idx_commands_category" in indexes
            assert "idx_commands_name" in indexes
            assert "idx_skills_category" in indexes
            assert "idx_scenarios_category" in indexes
            assert "idx_validation_cycle" in indexes
            assert "idx_validation_result" in indexes
            assert "idx_history_timestamp" in indexes
        finally:
            conn.close()

    def test_init_is_idempotent(self):
        """Calling init_db twice should not raise."""
        db.init_db()
        db.init_db()  # second call — no error


# ═══════════════════════════════════════════════════════════════════════════
# SCENARIOS CRUD
# ═══════════════════════════════════════════════════════════════════════════

class TestScenariosCrud:
    def test_add_and_get_scenario(self):
        """add_scenario should insert; get_scenario should retrieve by id."""
        db.init_db()
        sid = db.add_scenario(
            name="greet",
            description="Greeting test",
            category="voice",
            voice_input="bonjour jarvis",
            expected_commands=["cmd_greet"],
            expected_result="Bonjour!",
            difficulty="easy",
        )
        assert isinstance(sid, int)
        s = db.get_scenario(sid)
        assert s is not None
        assert s["name"] == "greet"
        assert s["category"] == "voice"
        assert s["difficulty"] == "easy"
        assert json.loads(s["expected_commands"]) == ["cmd_greet"]

    def test_get_all_scenarios(self):
        """get_all_scenarios should return all inserted scenarios."""
        db.init_db()
        db.add_scenario("s1", "d1", "cat_a", "input1", ["c1"], "r1")
        db.add_scenario("s2", "d2", "cat_b", "input2", ["c2"], "r2")
        all_s = db.get_all_scenarios()
        assert len(all_s) == 2
        names = {s["name"] for s in all_s}
        assert names == {"s1", "s2"}

    def test_get_scenario_not_found(self):
        """get_scenario with non-existent id should return None."""
        db.init_db()
        assert db.get_scenario(9999) is None

    def test_add_scenario_replace(self):
        """add_scenario with same name should replace (INSERT OR REPLACE)."""
        db.init_db()
        db.add_scenario("dup", "first", "cat", "v", ["c"], "r")
        db.add_scenario("dup", "second", "cat", "v", ["c"], "r")
        all_s = db.get_all_scenarios()
        descs = [s["description"] for s in all_s if s["name"] == "dup"]
        assert descs == ["second"]


# ═══════════════════════════════════════════════════════════════════════════
# VALIDATION RECORDING
# ═══════════════════════════════════════════════════════════════════════════

class TestValidation:
    def test_record_validation_pass(self):
        """record_validation with result='pass' should increment success_count."""
        db.init_db()
        sid = db.add_scenario("val_test", "d", "cat", "input", ["c"], "r")
        db.record_validation(
            cycle_number=1, scenario_name="val_test", voice_input="input",
            matched_command="c", match_score=0.95, expected_command="c",
            result="pass", details="ok", execution_time_ms=42.0, scenario_id=sid,
        )
        s = db.get_scenario(sid)
        assert s["validated"] == 1
        assert s["success_count"] == 1
        assert s["fail_count"] == 0
        assert s["validation_count"] == 1

    def test_record_validation_fail(self):
        """record_validation with result='fail' should increment fail_count."""
        db.init_db()
        sid = db.add_scenario("val_fail", "d", "cat", "input", ["c"], "r")
        db.record_validation(
            cycle_number=1, scenario_name="val_fail", voice_input="input",
            matched_command=None, match_score=0.0, expected_command="c",
            result="fail", scenario_id=sid,
        )
        s = db.get_scenario(sid)
        assert s["validated"] == 0  # fail does not set validated=1
        assert s["fail_count"] == 1
        assert s["success_count"] == 0

    def test_record_validation_without_scenario_id(self):
        """record_validation with scenario_id=None should still insert a cycle row."""
        db.init_db()
        db.record_validation(
            cycle_number=5, scenario_name="orphan", voice_input="test",
            matched_command="x", match_score=0.5, expected_command="x",
            result="partial",
        )
        report = db.get_validation_report(cycle_number=5)
        assert report["total"] == 1
        assert report["partial"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# STATISTICS
# ═══════════════════════════════════════════════════════════════════════════

class TestStats:
    def test_get_stats_empty(self):
        """get_stats on a fresh DB should return all zeroes."""
        db.init_db()
        stats = db.get_stats()
        assert stats["commands"] == 0
        assert stats["skills"] == 0
        assert stats["corrections"] == 0
        assert stats["scenarios"] == 0
        assert stats["validation_pass_rate"] == 0
        assert stats["last_cycle"] == 0
        assert isinstance(stats["categories_commands"], list)

    def test_get_stats_with_data(self):
        """get_stats should reflect inserted data."""
        db.init_db()
        db.add_scenario("s1", "d", "cat", "v", ["c"], "r")
        db.record_validation(1, "s1", "v", "c", 1.0, "c", "pass")
        db.record_validation(1, "s2", "v", None, 0.0, "c", "fail")
        stats = db.get_stats()
        assert stats["scenarios"] == 1
        assert stats["validation_cycles"] == 2
        assert stats["validation_pass_rate"] == 50.0
        assert stats["last_cycle"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# VALIDATION REPORT
# ═══════════════════════════════════════════════════════════════════════════

class TestValidationReport:
    def test_report_all_cycles(self):
        """get_validation_report() without cycle_number returns all."""
        db.init_db()
        db.record_validation(1, "a", "v", "c", 1.0, "c", "pass")
        db.record_validation(2, "b", "v", "c", 0.5, "c", "fail")
        report = db.get_validation_report()
        assert report["total"] == 2
        assert report["passed"] == 1
        assert report["failed"] == 1
        assert report["pass_rate"] == 50.0

    def test_report_single_cycle(self):
        """get_validation_report(cycle_number) filters to that cycle."""
        db.init_db()
        db.record_validation(1, "a", "v", "c", 1.0, "c", "pass")
        db.record_validation(2, "b", "v", "c", 0.5, "c", "fail")
        report = db.get_validation_report(cycle_number=1)
        assert report["total"] == 1
        assert report["passed"] == 1
        assert report["failed"] == 0

    def test_report_empty(self):
        """Empty DB should return zero totals and 0 pass_rate."""
        db.init_db()
        report = db.get_validation_report()
        assert report["total"] == 0
        assert report["pass_rate"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# EXPORT
# ═══════════════════════════════════════════════════════════════════════════

class TestExport:
    def test_export_full_db(self):
        """export_full_db should return a dict with all expected keys."""
        db.init_db()
        db.add_scenario("export_s", "d", "cat", "v", ["c"], "r")
        export = db.export_full_db()
        assert "version" in export
        assert "exported_at" in export
        assert "stats" in export
        assert isinstance(export["commands"], list)
        assert isinstance(export["skills"], list)
        assert isinstance(export["voice_corrections"], list)
        assert isinstance(export["scenarios"], list)
        assert len(export["scenarios"]) == 1


# ═══════════════════════════════════════════════════════════════════════════
# MIGRATIONS
# ═══════════════════════════════════════════════════════════════════════════

class TestMigrations:
    def test_apply_built_in_migrations(self):
        """apply_migrations should apply all built-in migrations."""
        db.init_db()
        applied = db.apply_migrations(db_path=db.DB_PATH)
        assert "002_chat_history" in applied
        assert "003_command_analytics" in applied
        assert "004_maintenance_log" in applied

        # Tables should now exist
        conn = db.get_connection()
        try:
            tables = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            assert "chat_history" in tables
            assert "command_analytics" in tables
            assert "maintenance_log" in tables
        finally:
            conn.close()

    def test_migrations_are_idempotent(self):
        """Running apply_migrations twice should not duplicate."""
        db.init_db()
        first = db.apply_migrations(db_path=db.DB_PATH)
        second = db.apply_migrations(db_path=db.DB_PATH)
        assert len(first) == 3
        assert len(second) == 0  # already applied

    def test_get_applied_migrations(self):
        """get_applied_migrations should return set of applied versions."""
        db.init_db()
        db.apply_migrations(db_path=db.DB_PATH)
        versions = db.get_applied_migrations()
        assert "002_chat_history" in versions
        assert "003_command_analytics" in versions

    def test_sql_file_migrations(self, tmp_path):
        """Migrations from .sql files in the migrations/ directory should be applied."""
        db.init_db()
        mig_dir = tmp_path / "migrations"
        mig_dir.mkdir(exist_ok=True)
        sql_file = mig_dir / "099_test_table.sql"
        sql_file.write_text(
            "CREATE TABLE IF NOT EXISTS test_mig (id INTEGER PRIMARY KEY, val TEXT);",
            encoding="utf-8",
        )
        applied = db.apply_migrations(db_path=db.DB_PATH)
        assert "099_test_table" in applied

        # Verify the table exists
        conn = sqlite3.connect(str(db.DB_PATH))
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        conn.close()
        assert "test_mig" in tables


# ═══════════════════════════════════════════════════════════════════════════
# CROSS-DB QUERIES
# ═══════════════════════════════════════════════════════════════════════════

class TestCrossDb:
    def test_get_unified_stats(self):
        """get_unified_stats should count rows across all 3 DBs."""
        db.init_db()
        _create_etoile(db.ETOILE_DB_PATH)
        _create_sniper(db.SNIPER_DB_PATH)

        # Insert some data into etoile
        conn = sqlite3.connect(str(db.ETOILE_DB_PATH))
        conn.execute("INSERT INTO pipeline_dictionary (trigger_phrase, steps, category) VALUES ('hello', '[]', 'test')")
        conn.execute("INSERT INTO agents (name) VALUES ('M1')")
        conn.commit()
        conn.close()

        stats = db.get_unified_stats()
        assert stats["commands"] == 0
        assert stats["pipelines"] == 1
        assert stats["cluster_agents"] == 1

    def test_get_unified_stats_missing_dbs(self):
        """get_unified_stats should still work when etoile/sniper don't exist."""
        db.init_db()
        stats = db.get_unified_stats()
        assert stats["commands"] == 0
        # etoile/sniper keys should be absent (caught by try/except)
        assert "pipelines" not in stats

    def test_find_pipeline_for_voice_in_commands(self):
        """find_pipeline_for_voice should search jarvis commands first."""
        db.init_db()
        conn = db.get_connection()
        conn.execute(
            "INSERT INTO commands (name, category, description, triggers, action_type, action)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            ("hello_cmd", "greet", "Say hello", '["bonjour", "hello"]', "python", "greet()"),
        )
        conn.commit()
        conn.close()

        result = db.find_pipeline_for_voice("bonjour")
        assert result is not None
        assert result["source"] == "jarvis.commands"
        assert result["name"] == "hello_cmd"

    def test_find_pipeline_for_voice_in_etoile(self):
        """find_pipeline_for_voice should fall back to etoile.pipeline_dictionary."""
        db.init_db()
        _create_etoile(db.ETOILE_DB_PATH)

        conn = sqlite3.connect(str(db.ETOILE_DB_PATH))
        conn.execute(
            "INSERT INTO pipeline_dictionary (trigger_phrase, steps, category) VALUES (?, ?, ?)",
            ("lance le trading", '["step1"]', "trading"),
        )
        conn.commit()
        conn.close()

        result = db.find_pipeline_for_voice("lance le trading")
        assert result is not None
        assert result["source"] == "etoile.pipeline_dictionary"

    def test_find_pipeline_for_voice_not_found(self):
        """find_pipeline_for_voice should return None when nothing matches."""
        db.init_db()
        result = db.find_pipeline_for_voice("nonexistent phrase")
        assert result is None

    def test_get_routing_weights(self):
        """get_routing_weights should return weights for a given scenario."""
        db.init_db()
        _create_etoile(db.ETOILE_DB_PATH)

        conn = sqlite3.connect(str(db.ETOILE_DB_PATH))
        conn.execute(
            "INSERT INTO scenario_weights (scenario, agent, weight, priority, chain_next, description)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            ("code", "M1", 1.8, 1, "M2", "Champion local"),
        )
        conn.commit()
        conn.close()

        weights = db.get_routing_weights("code")
        assert len(weights) == 1
        assert weights[0]["agent"] == "M1"
        assert weights[0]["weight"] == 1.8

    def test_get_routing_weights_missing_etoile(self):
        """get_routing_weights should return empty list when etoile.db is missing."""
        db.init_db()
        weights = db.get_routing_weights("code")
        assert weights == []


# ═══════════════════════════════════════════════════════════════════════════
# BACKUP / RESTORE
# ═══════════════════════════════════════════════════════════════════════════

class TestBackupRestore:
    def test_backup_database(self):
        """backup_database should create a copy in the backups directory."""
        db.init_db()
        db.add_scenario("bkp_test", "d", "cat", "v", ["c"], "r")
        backup_path = db.backup_database()
        assert backup_path.exists()
        assert backup_path.parent == db.BACKUP_DIR
        assert "jarvis_" in backup_path.name

        # Verify backup content
        conn = sqlite3.connect(str(backup_path))
        count = conn.execute("SELECT COUNT(*) FROM scenarios").fetchone()[0]
        conn.close()
        assert count == 1

    def test_backup_with_label(self):
        """backup_database with a label should include it in the filename."""
        db.init_db()
        backup_path = db.backup_database(label="manual")
        assert "_manual" in backup_path.name

    def test_list_backups(self):
        """list_backups should return metadata for each backup file."""
        db.init_db()
        db.backup_database(label="one")
        db.backup_database(label="two")
        backups = db.list_backups()
        assert len(backups) == 2
        assert "file" in backups[0]
        assert "size_kb" in backups[0]

    def test_list_backups_empty(self):
        """list_backups should return empty list when no backups exist."""
        assert db.list_backups() == []

    def test_restore_database(self):
        """restore_database should overwrite the target with backup content."""
        db.init_db()
        db.add_scenario("before_restore", "d", "cat", "v", ["c"], "r")
        backup_path = db.backup_database()

        # Modify the live DB
        conn = db.get_connection()
        conn.execute("DELETE FROM scenarios")
        conn.commit()
        conn.close()
        assert len(db.get_all_scenarios()) == 0

        # Restore
        result = db.restore_database(backup_path)
        assert result is True
        scenarios = db.get_all_scenarios()
        assert len(scenarios) == 1
        assert scenarios[0]["name"] == "before_restore"

    def test_restore_nonexistent_backup(self, tmp_path):
        """restore_database should return False for a missing backup file."""
        db.init_db()
        fake = tmp_path / "no_such_backup.db"
        assert db.restore_database(fake) is False


# ═══════════════════════════════════════════════════════════════════════════
# MAINTENANCE
# ═══════════════════════════════════════════════════════════════════════════

class TestMaintenance:
    def test_auto_maintenance_force(self):
        """auto_maintenance(force=True) should always run."""
        db.init_db()
        result = db.auto_maintenance(force=True)
        assert result["performed"] is True
        assert "jarvis" in result["results"]
        assert result["results"]["jarvis"]["integrity"] == "ok"

    def test_auto_maintenance_skipped(self):
        """auto_maintenance should skip if interval has not elapsed."""
        db.init_db()
        # Run once to set timestamp
        db.auto_maintenance(force=True)
        # Second run should be skipped
        result = db.auto_maintenance(force=False)
        assert result.get("skipped") is True
        assert "next_in_hours" in result

    def test_maintenance_state_persistence(self):
        """Maintenance state should persist across calls via JSON file."""
        db.init_db()
        db.auto_maintenance(force=True)
        state = db._load_maintenance_state()
        assert "last_run" in state
        assert state["last_run"] > 0

    def test_maintenance_on_multiple_dbs(self):
        """auto_maintenance should process etoile and sniper when they exist."""
        db.init_db()
        _create_etoile(db.ETOILE_DB_PATH)
        _create_sniper(db.SNIPER_DB_PATH)
        result = db.auto_maintenance(force=True)
        assert "etoile" in result["results"]
        assert "sniper" in result["results"]
        assert result["results"]["etoile"]["integrity"] == "ok"


# ═══════════════════════════════════════════════════════════════════════════
# DB HEALTH
# ═══════════════════════════════════════════════════════════════════════════

class TestDbHealth:
    def test_get_db_health_jarvis_only(self):
        """get_db_health should report jarvis as ok, others as missing."""
        db.init_db()
        health = db.get_db_health()
        assert health["jarvis"]["status"] == "ok"
        assert health["jarvis"]["integrity"] == "ok"
        assert health["jarvis"]["tables"] > 0
        assert health["etoile"]["status"] == "missing"
        assert health["sniper"]["status"] == "missing"
        assert "last_maintenance" in health

    def test_get_db_health_all_present(self):
        """get_db_health should report all 3 DBs when they exist."""
        db.init_db()
        _create_etoile(db.ETOILE_DB_PATH)
        _create_sniper(db.SNIPER_DB_PATH)
        health = db.get_db_health()
        assert health["jarvis"]["status"] == "ok"
        assert health["etoile"]["status"] == "ok"
        assert health["sniper"]["status"] == "ok"


# ═══════════════════════════════════════════════════════════════════════════
# IMPORT FROM CODE (mocked)
# ═══════════════════════════════════════════════════════════════════════════

class TestImports:
    def test_import_commands_from_code(self):
        """import_commands_from_code should insert command objects into DB."""
        db.init_db()

        # Build a minimal mock command object
        class FakeCmd:
            def __init__(self, name):
                self.name = name
                self.category = "test"
                self.description = f"Test {name}"
                self.triggers = ["trigger1"]
                self.action_type = "python"
                self.action = "pass"
                self.params = []
                self.confirm = False

        fake_commands = [FakeCmd("cmd_a"), FakeCmd("cmd_b")]
        with patch("src.commands.COMMANDS", fake_commands):
            count = db.import_commands_from_code()
        assert count == 2

        conn = db.get_connection()
        try:
            rows = conn.execute("SELECT name FROM commands ORDER BY name").fetchall()
            names = [r["name"] for r in rows]
            assert names == ["cmd_a", "cmd_b"]
        finally:
            conn.close()

    def test_import_corrections_from_code(self):
        """import_corrections_from_code should insert voice corrections."""
        db.init_db()
        fake_corrections = {"jarvi": "jarvis", "trasaction": "transaction"}
        with patch("src.commands.VOICE_CORRECTIONS", fake_corrections):
            count = db.import_corrections_from_code()
        assert count == 2

        conn = db.get_connection()
        try:
            rows = conn.execute("SELECT wrong, correct FROM voice_corrections ORDER BY wrong").fetchall()
            assert dict(rows[0])["wrong"] == "jarvi"
            assert dict(rows[1])["correct"] == "transaction"
        finally:
            conn.close()
