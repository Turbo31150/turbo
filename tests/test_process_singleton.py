"""Tests for src/process_singleton.py — Process Singleton Manager."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def tmp_singleton(tmp_path):
    """Create a ProcessSingleton with a temp PID directory."""
    from src.process_singleton import ProcessSingleton
    return ProcessSingleton(pid_dir=tmp_path)


# ===========================================================================
# PID file basics
# ===========================================================================

class TestPidFileBasics:
    def test_register_creates_pid_file(self, tmp_singleton, tmp_path):
        tmp_singleton.register("test_svc", 12345)
        pid_file = tmp_path / "test_svc.pid"
        assert pid_file.exists()
        assert pid_file.read_text() == "12345"

    def test_is_running_no_file(self, tmp_singleton):
        alive, pid = tmp_singleton.is_running("nonexistent")
        assert alive is False
        assert pid is None

    def test_is_running_dead_process(self, tmp_singleton, tmp_path):
        # Write a PID file with a PID that doesn't exist
        (tmp_path / "dead_svc.pid").write_text("999999999")
        alive, pid = tmp_singleton.is_running("dead_svc")
        assert alive is False
        assert pid is None
        # PID file should be cleaned up
        assert not (tmp_path / "dead_svc.pid").exists()

    def test_is_running_current_process(self, tmp_singleton):
        tmp_singleton.register("self_test", os.getpid())
        alive, pid = tmp_singleton.is_running("self_test")
        assert alive is True
        assert pid == os.getpid()

    def test_is_running_invalid_content(self, tmp_singleton, tmp_path):
        (tmp_path / "bad.pid").write_text("not_a_number")
        alive, pid = tmp_singleton.is_running("bad")
        assert alive is False
        assert pid is None


# ===========================================================================
# Acquire / Release
# ===========================================================================

class TestAcquireRelease:
    def test_acquire_registers_current_pid(self, tmp_singleton, tmp_path):
        result_pid = tmp_singleton.acquire("my_service")
        assert result_pid == os.getpid()
        assert (tmp_path / "my_service.pid").exists()
        content = (tmp_path / "my_service.pid").read_text()
        assert content == str(os.getpid())

    def test_acquire_with_explicit_pid(self, tmp_singleton, tmp_path):
        result_pid = tmp_singleton.acquire("my_service", pid=42)
        assert result_pid == 42
        assert (tmp_path / "my_service.pid").read_text() == "42"

    def test_acquire_kills_existing_dead(self, tmp_singleton, tmp_path):
        # Pre-register a dead PID
        (tmp_path / "svc.pid").write_text("999999999")
        result_pid = tmp_singleton.acquire("svc")
        assert result_pid == os.getpid()

    def test_acquire_with_port(self, tmp_singleton):
        with patch.object(tmp_singleton, "kill_on_port", return_value=False) as mock_kill:
            tmp_singleton.acquire("ws", port=9742)
        mock_kill.assert_called_once_with(9742)

    def test_release_removes_pid_file(self, tmp_singleton, tmp_path):
        tmp_singleton.register("svc", 123)
        assert (tmp_path / "svc.pid").exists()
        tmp_singleton.release("svc")
        assert not (tmp_path / "svc.pid").exists()

    def test_release_nonexistent_is_noop(self, tmp_singleton):
        # Should not raise
        tmp_singleton.release("does_not_exist")


# ===========================================================================
# Kill existing
# ===========================================================================

class TestKillExisting:
    def test_kill_existing_dead_returns_false(self, tmp_singleton, tmp_path):
        (tmp_path / "dead.pid").write_text("999999999")
        result = tmp_singleton.kill_existing("dead")
        assert result is False

    def test_kill_existing_no_pid_file(self, tmp_singleton):
        result = tmp_singleton.kill_existing("nope")
        assert result is False

    @patch("subprocess.run")
    def test_kill_existing_alive_on_windows(self, mock_run, tmp_singleton, tmp_path):
        # Register current PID (alive)
        tmp_singleton.register("alive_svc", os.getpid())
        mock_run.return_value = MagicMock(
            returncode=0, stdout="SUCCESS: The process has been terminated."
        )
        with patch("os.name", "nt"):
            with patch.object(tmp_singleton, "is_running", return_value=(True, os.getpid())):
                result = tmp_singleton.kill_existing("alive_svc")
        assert result is True
        mock_run.assert_called_once()


# ===========================================================================
# Kill on port
# ===========================================================================

class TestKillOnPort:
    @patch("subprocess.run")
    def test_kill_on_port_windows(self, mock_run, tmp_singleton):
        # Simulate netstat output with a matching LISTENING line
        netstat_output = (
            "  TCP    127.0.0.1:9742     0.0.0.0:0          LISTENING       5678\n"
            "  TCP    127.0.0.1:80       0.0.0.0:0          LISTENING       1234\n"
        )
        mock_run.side_effect = [
            MagicMock(stdout=netstat_output, returncode=0),  # netstat call
            MagicMock(returncode=0),  # taskkill call
        ]
        with patch("os.name", "nt"):
            result = tmp_singleton.kill_on_port(9742)
        assert result is True
        assert mock_run.call_count == 2

    @patch("subprocess.run")
    def test_kill_on_port_no_match(self, mock_run, tmp_singleton):
        mock_run.return_value = MagicMock(
            stdout="  TCP    127.0.0.1:80     0.0.0.0:0   LISTENING  1234\n",
            returncode=0,
        )
        with patch("os.name", "nt"):
            result = tmp_singleton.kill_on_port(9999)
        assert result is False


# ===========================================================================
# List all & cleanup
# ===========================================================================

class TestListAndCleanup:
    def test_list_all_empty(self, tmp_singleton):
        result = tmp_singleton.list_all()
        assert result == {}

    def test_list_all_with_services(self, tmp_singleton, tmp_path):
        tmp_singleton.register("svc_a", os.getpid())
        tmp_singleton.register("svc_b", 999999999)  # dead
        result = tmp_singleton.list_all()
        assert "svc_a" in result
        assert result["svc_a"]["alive"] is True
        assert "svc_b" in result
        assert result["svc_b"]["alive"] is False

    def test_cleanup_dead_removes_dead_only(self, tmp_singleton, tmp_path):
        tmp_singleton.register("alive", os.getpid())
        tmp_singleton.register("dead1", 999999999)
        tmp_singleton.register("dead2", 999999998)
        cleaned = tmp_singleton.cleanup_dead()
        assert "dead1" in cleaned
        assert "dead2" in cleaned
        assert "alive" not in cleaned
        # Dead PID files removed
        assert not (tmp_path / "dead1.pid").exists()
        assert not (tmp_path / "dead2.pid").exists()
        # Alive PID file kept
        assert (tmp_path / "alive.pid").exists()

    def test_cleanup_empty_dir(self, tmp_singleton):
        cleaned = tmp_singleton.cleanup_dead()
        assert cleaned == []


# ===========================================================================
# Kill all
# ===========================================================================

class TestKillAll:
    def test_kill_all_no_services(self, tmp_singleton):
        killed = tmp_singleton.kill_all()
        assert killed == []

    @patch("subprocess.run")
    def test_kill_all_with_alive(self, mock_run, tmp_singleton, tmp_path):
        # Register current PID (alive) — kill_all should try to kill it
        tmp_singleton.register("svc_x", os.getpid())
        mock_run.return_value = MagicMock(
            returncode=0, stdout="SUCCESS: The process has been terminated."
        )
        with patch("os.name", "nt"):
            killed = tmp_singleton.kill_all()
        assert "svc_x" in killed


# ===========================================================================
# Singleton module instance
# ===========================================================================

class TestModuleSingleton:
    def test_singleton_exists(self):
        from src.process_singleton import singleton
        assert singleton is not None
        from src.process_singleton import ProcessSingleton
        assert isinstance(singleton, ProcessSingleton)
