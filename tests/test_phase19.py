"""Phase 19 Tests — Process Manager, Data Validator, File Watcher, MCP Handlers."""

import asyncio
import json
import os
import tempfile
import time
import pytest


# ═══════════════════════════════════════════════════════════════════════════
# PROCESS MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class TestProcessManager:
    @staticmethod
    def _make():
        from src.process_manager import ProcessManager
        return ProcessManager()

    def test_singleton_exists(self):
        from src.process_manager import process_manager
        assert process_manager is not None

    def test_register(self):
        pm = self._make()
        p = pm.register("test_proc", "echo", args=["hello"])
        assert p.name == "test_proc"
        assert p.command == "echo"

    def test_unregister(self):
        pm = self._make()
        pm.register("temp", "echo")
        assert pm.unregister("temp")
        assert not pm.unregister("temp")

    def test_list_processes(self):
        pm = self._make()
        pm.register("a", "echo", group="g1")
        pm.register("b", "echo", group="g2")
        all_procs = pm.list_processes()
        assert len(all_procs) == 2
        g1_procs = pm.list_processes(group="g1")
        assert len(g1_procs) == 1

    def test_list_groups(self):
        pm = self._make()
        pm.register("a", "echo", group="alpha")
        pm.register("b", "echo", group="beta")
        groups = pm.list_groups()
        assert "alpha" in groups
        assert "beta" in groups

    def test_get(self):
        pm = self._make()
        pm.register("x", "echo")
        assert pm.get("x") is not None
        assert pm.get("nope") is None

    def test_start_unknown(self):
        pm = self._make()
        assert not pm.start("nonexistent")

    def test_start_and_stop(self):
        pm = self._make()
        pm.register("sleeper", "python", args=["-c", "import time; time.sleep(30)"])
        assert pm.start("sleeper")
        assert pm.is_running("sleeper")
        assert pm.stop("sleeper")
        assert not pm.is_running("sleeper")

    def test_kill(self):
        pm = self._make()
        pm.register("sleeper2", "python", args=["-c", "import time; time.sleep(30)"])
        pm.start("sleeper2")
        assert pm.kill("sleeper2")
        assert not pm.is_running("sleeper2")

    def test_restart(self):
        pm = self._make()
        pm.register("restartable", "python", args=["-c", "import time; time.sleep(30)"])
        pm.start("restartable")
        assert pm.restart("restartable")
        profile = pm.get("restartable")
        assert profile.restart_count == 1
        pm.stop("restartable")

    def test_events(self):
        pm = self._make()
        pm.register("evproc", "echo", args=["hi"])
        pm.start("evproc")
        time.sleep(0.3)  # let echo finish
        events = pm.get_events(name="evproc")
        assert len(events) >= 1

    def test_health_check(self):
        pm = self._make()
        pm.register("hproc", "echo", health_check=lambda: True)
        result = pm.check_health("hproc")
        assert result["name"] == "hproc"

    def test_stats(self):
        pm = self._make()
        pm.register("s1", "echo", group="g")
        pm.register("s2", "echo", group="g")
        stats = pm.get_stats()
        assert stats["total_processes"] == 2
        assert stats["groups"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# DATA VALIDATOR
# ═══════════════════════════════════════════════════════════════════════════

class TestDataValidator:
    @staticmethod
    def _make():
        from src.data_validator import DataValidator
        return DataValidator()

    def test_singleton_exists(self):
        from src.data_validator import data_validator
        assert data_validator is not None

    def test_register_schema(self):
        from src.data_validator import FieldSchema
        dv = self._make()
        dv.register_schema("user", [FieldSchema(name="name", field_type="str", required=True)])
        schemas = dv.list_schemas()
        assert len(schemas) == 1
        assert schemas[0]["name"] == "user"

    def test_unregister_schema(self):
        from src.data_validator import FieldSchema
        dv = self._make()
        dv.register_schema("temp", [FieldSchema(name="x")])
        assert dv.unregister_schema("temp")
        assert not dv.unregister_schema("temp")

    def test_validate_required(self):
        from src.data_validator import FieldSchema
        dv = self._make()
        dv.register_schema("s", [FieldSchema(name="email", required=True)])
        r = dv.validate({}, "s")
        assert not r.valid
        assert r.error_count >= 1

    def test_validate_type(self):
        from src.data_validator import FieldSchema
        dv = self._make()
        dv.register_schema("s", [FieldSchema(name="age", field_type="int")])
        r = dv.validate({"age": "notint"}, "s")
        assert not r.valid

    def test_validate_range(self):
        from src.data_validator import FieldSchema
        dv = self._make()
        dv.register_schema("s", [FieldSchema(name="score", field_type="int", min_value=0, max_value=100)])
        assert dv.validate({"score": 50}, "s").valid
        assert not dv.validate({"score": 150}, "s").valid
        assert not dv.validate({"score": -5}, "s").valid

    def test_validate_length(self):
        from src.data_validator import FieldSchema
        dv = self._make()
        dv.register_schema("s", [FieldSchema(name="name", field_type="str", min_length=2, max_length=10)])
        assert dv.validate({"name": "abc"}, "s").valid
        assert not dv.validate({"name": "x"}, "s").valid

    def test_validate_pattern(self):
        from src.data_validator import FieldSchema
        dv = self._make()
        dv.register_schema("s", [FieldSchema(name="email", pattern=r"^[\w.]+@[\w.]+$")])
        assert dv.validate({"email": "a@b.com"}, "s").valid
        assert not dv.validate({"email": "invalid"}, "s").valid

    def test_validate_choices(self):
        from src.data_validator import FieldSchema
        dv = self._make()
        dv.register_schema("s", [FieldSchema(name="role", choices=["admin", "user"])])
        assert dv.validate({"role": "admin"}, "s").valid
        assert not dv.validate({"role": "guest"}, "s").valid

    def test_custom_validator(self):
        from src.data_validator import FieldSchema
        dv = self._make()
        dv.register_schema("s", [FieldSchema(name="val", custom_validator=lambda v: v > 0)])
        assert dv.validate({"val": 5}, "s").valid
        assert not dv.validate({"val": -1}, "s").valid

    def test_custom_validator_message(self):
        from src.data_validator import FieldSchema
        dv = self._make()
        dv.register_schema("s", [FieldSchema(name="val", custom_validator=lambda v: "too big" if v > 100 else True)])
        r = dv.validate({"val": 200}, "s")
        assert not r.valid
        assert "too big" in r.errors[0].message

    def test_nested_schema(self):
        from src.data_validator import FieldSchema
        dv = self._make()
        dv.register_schema("address", [FieldSchema(name="city", field_type="str", required=True)])
        dv.register_schema("user", [FieldSchema(name="addr", field_type="dict", nested_schema="address")])
        assert dv.validate({"addr": {"city": "Paris"}}, "user").valid
        assert not dv.validate({"addr": {}}, "user").valid

    def test_schema_not_found(self):
        dv = self._make()
        r = dv.validate({}, "nope")
        assert not r.valid

    def test_validate_pass(self):
        from src.data_validator import FieldSchema
        dv = self._make()
        dv.register_schema("s", [
            FieldSchema(name="name", field_type="str", required=True),
            FieldSchema(name="age", field_type="int", min_value=0),
        ])
        r = dv.validate({"name": "Alice", "age": 30}, "s")
        assert r.valid
        assert r.error_count == 0

    def test_history(self):
        from src.data_validator import FieldSchema
        dv = self._make()
        dv.register_schema("s", [FieldSchema(name="x")])
        dv.validate({"x": 1}, "s")
        h = dv.get_history()
        assert len(h) >= 1

    def test_stats(self):
        from src.data_validator import FieldSchema
        dv = self._make()
        dv.register_schema("s", [FieldSchema(name="x", required=True)])
        dv.validate({"x": 1}, "s")
        dv.validate({}, "s")
        stats = dv.get_stats()
        assert stats["total_validations"] == 2
        assert stats["passed"] == 1
        assert stats["failed"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# FILE WATCHER
# ═══════════════════════════════════════════════════════════════════════════

class TestFileWatcher:
    @staticmethod
    def _make():
        from src.file_watcher import FileWatcher
        return FileWatcher()

    def test_singleton_exists(self):
        from src.file_watcher import file_watcher
        assert file_watcher is not None

    def test_add_watch(self):
        fw = self._make()
        tmpdir = tempfile.mkdtemp()
        w = fw.add_watch("test", tmpdir)
        assert w.name == "test"
        assert w.directory == tmpdir

    def test_remove_watch(self):
        fw = self._make()
        tmpdir = tempfile.mkdtemp()
        fw.add_watch("temp", tmpdir)
        assert fw.remove_watch("temp")
        assert not fw.remove_watch("temp")

    def test_list_watches(self):
        fw = self._make()
        t1, t2 = tempfile.mkdtemp(), tempfile.mkdtemp()
        fw.add_watch("a", t1, group="g1")
        fw.add_watch("b", t2, group="g2")
        assert len(fw.list_watches()) == 2
        assert len(fw.list_watches(group="g1")) == 1

    def test_list_groups(self):
        fw = self._make()
        t1, t2 = tempfile.mkdtemp(), tempfile.mkdtemp()
        fw.add_watch("a", t1, group="alpha")
        fw.add_watch("b", t2, group="beta")
        groups = fw.list_groups()
        assert "alpha" in groups
        assert "beta" in groups

    def test_detect_created(self):
        fw = self._make()
        tmpdir = tempfile.mkdtemp()
        fw.add_watch("w", tmpdir, patterns=["*.txt"])
        # Create a new file
        with open(os.path.join(tmpdir, "test.txt"), "w") as f:
            f.write("hello")
        events = fw.poll("w")
        created = [e for e in events if e.change_type.value == "created"]
        assert len(created) == 1
        assert "test.txt" in created[0].path

    def test_detect_modified(self):
        fw = self._make()
        tmpdir = tempfile.mkdtemp()
        fpath = os.path.join(tmpdir, "data.txt")
        with open(fpath, "w") as f:
            f.write("v1")
        fw.add_watch("w", tmpdir)
        time.sleep(0.05)  # ensure different mtime
        with open(fpath, "w") as f:
            f.write("v2")
        events = fw.poll("w")
        modified = [e for e in events if e.change_type.value == "modified"]
        assert len(modified) >= 1

    def test_detect_deleted(self):
        fw = self._make()
        tmpdir = tempfile.mkdtemp()
        fpath = os.path.join(tmpdir, "todelete.txt")
        with open(fpath, "w") as f:
            f.write("bye")
        fw.add_watch("w", tmpdir)
        os.remove(fpath)
        events = fw.poll("w")
        deleted = [e for e in events if e.change_type.value == "deleted"]
        assert len(deleted) == 1

    def test_pattern_filtering(self):
        fw = self._make()
        tmpdir = tempfile.mkdtemp()
        fw.add_watch("w", tmpdir, patterns=["*.py"])
        with open(os.path.join(tmpdir, "test.txt"), "w") as f:
            f.write("ignored")
        with open(os.path.join(tmpdir, "test.py"), "w") as f:
            f.write("tracked")
        events = fw.poll("w")
        assert len(events) == 1
        assert events[0].path.endswith(".py")

    def test_callback(self):
        fw = self._make()
        tmpdir = tempfile.mkdtemp()
        received = []
        fw.add_watch("w", tmpdir, callback=lambda e: received.append(e.path))
        with open(os.path.join(tmpdir, "cb.txt"), "w") as f:
            f.write("x")
        fw.poll("w")
        assert len(received) == 1

    def test_enable_disable(self):
        fw = self._make()
        tmpdir = tempfile.mkdtemp()
        fw.add_watch("w", tmpdir)
        fw.disable_watch("w")
        with open(os.path.join(tmpdir, "skip.txt"), "w") as f:
            f.write("x")
        events = fw.poll("w")
        assert len(events) == 0
        fw.enable_watch("w")

    def test_get_events_history(self):
        fw = self._make()
        tmpdir = tempfile.mkdtemp()
        fw.add_watch("w", tmpdir)
        with open(os.path.join(tmpdir, "a.txt"), "w") as f:
            f.write("x")
        fw.poll()
        history = fw.get_events(watch_name="w")
        assert len(history) >= 1

    def test_stats(self):
        fw = self._make()
        tmpdir = tempfile.mkdtemp()
        with open(os.path.join(tmpdir, "f.txt"), "w") as f:
            f.write("x")
        fw.add_watch("w", tmpdir)
        stats = fw.get_stats()
        assert stats["total_watches"] == 1
        assert stats["total_files_tracked"] >= 1


# ═══════════════════════════════════════════════════════════════════════════
# MCP HANDLERS — Phase 19
# ═══════════════════════════════════════════════════════════════════════════

class TestMCPHandlersPhase19:
    def test_procmgr_list(self):
        from src.mcp_server import handle_procmgr_list
        result = asyncio.run(handle_procmgr_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_procmgr_events(self):
        from src.mcp_server import handle_procmgr_events
        result = asyncio.run(handle_procmgr_events({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_procmgr_stats(self):
        from src.mcp_server import handle_procmgr_stats
        result = asyncio.run(handle_procmgr_stats({}))
        data = json.loads(result[0].text)
        assert "total_processes" in data

    def test_dataval_schemas(self):
        from src.mcp_server import handle_dataval_schemas
        result = asyncio.run(handle_dataval_schemas({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_dataval_history(self):
        from src.mcp_server import handle_dataval_history
        result = asyncio.run(handle_dataval_history({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_dataval_stats(self):
        from src.mcp_server import handle_dataval_stats
        result = asyncio.run(handle_dataval_stats({}))
        data = json.loads(result[0].text)
        assert "total_schemas" in data

    def test_fwatch_list(self):
        from src.mcp_server import handle_fwatch_list
        result = asyncio.run(handle_fwatch_list({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_fwatch_events(self):
        from src.mcp_server import handle_fwatch_events
        result = asyncio.run(handle_fwatch_events({}))
        data = json.loads(result[0].text)
        assert isinstance(data, list)

    def test_fwatch_stats(self):
        from src.mcp_server import handle_fwatch_stats
        result = asyncio.run(handle_fwatch_stats({}))
        data = json.loads(result[0].text)
        assert "total_watches" in data


# ═══════════════════════════════════════════════════════════════════════════
# TOOL COUNT PHASE 19
# ═══════════════════════════════════════════════════════════════════════════

class TestToolCountPhase19:
    def test_tool_count_at_least_256(self):
        """247 + 3 procmgr + 3 dataval + 3 fwatch = 256."""
        from src.mcp_server import TOOL_DEFINITIONS
        assert len(TOOL_DEFINITIONS) >= 256, f"Expected >= 256 tools, got {len(TOOL_DEFINITIONS)}"

    def test_no_duplicate_tool_names(self):
        from src.mcp_server import TOOL_DEFINITIONS
        names = [t[0] for t in TOOL_DEFINITIONS]
        dupes = [n for n in names if names.count(n) > 1]
        assert len(names) == len(set(names)), f"Duplicate tools: {set(dupes)}"
