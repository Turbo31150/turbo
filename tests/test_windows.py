"""Tests for src/windows.py — Windows system integration toolkit.

Covers: run_powershell, _ps, _sq, _ps_json, get_system_info,
application/process management, file operations, clipboard, audio,
screen, services, system control, registry, accessibility.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.windows import (
    run_powershell, _ps, _sq, _ps_json,
    open_application, close_application, open_url, list_installed_apps,
    list_processes, kill_process,
    list_windows, focus_window, minimize_window, maximize_window,
    send_keys, type_text, press_hotkey,
    clipboard_get, clipboard_set,
    open_folder, list_folder, create_folder, copy_item, move_item,
    delete_item, read_file, write_file, search_files,
    volume_up, volume_down, volume_mute,
    screenshot, get_screen_resolution,
    check_service, list_services, start_service, stop_service,
    lock_screen, shutdown_pc, restart_pc, sleep_pc,
    notify_windows,
    get_wifi_networks, get_ip_address, ping_host,
    registry_get, registry_set,
    list_scheduled_tasks,
    check_accessibility, toggle_narrator,
    get_system_info, get_gpu_info, get_network_info,
)


# Helper to mock subprocess.run for PowerShell
def _mock_ps_success(stdout="OK"):
    mock = MagicMock()
    mock.returncode = 0
    mock.stdout = stdout
    mock.stderr = ""
    return mock


def _mock_ps_fail(stderr="Error"):
    mock = MagicMock()
    mock.returncode = 1
    mock.stdout = ""
    mock.stderr = stderr
    return mock


# ===========================================================================
# Core: _sq (pure function)
# ===========================================================================

class TestSq:
    def test_basic(self):
        assert _sq("hello") == "hello"

    def test_single_quote(self):
        assert _sq("it's") == "it''s"

    def test_multiple_quotes(self):
        assert _sq("a'b'c") == "a''b''c"

    def test_empty(self):
        assert _sq("") == ""


# ===========================================================================
# Core: run_powershell
# ===========================================================================

class TestRunPowershell:
    def test_success(self):
        with patch("src.windows.subprocess.run", return_value=_mock_ps_success("Hello")):
            result = run_powershell("echo Hello")
        assert result["success"] is True
        assert result["stdout"] == "Hello"

    def test_failure(self):
        with patch("src.windows.subprocess.run", return_value=_mock_ps_fail("Bad cmd")):
            result = run_powershell("bad_command")
        assert result["success"] is False
        assert "Bad cmd" in result["stderr"]

    def test_timeout(self):
        import subprocess
        with patch("src.windows.subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 60)):
            result = run_powershell("long_command", timeout=60)
        assert result["success"] is False
        assert "Timeout" in result["stderr"]

    def test_os_error(self):
        with patch("src.windows.subprocess.run", side_effect=OSError("No powershell")):
            result = run_powershell("echo test")
        assert result["success"] is False
        assert "powershell" in result["stderr"].lower()


# ===========================================================================
# Core: _ps
# ===========================================================================

class TestPs:
    def test_success(self):
        with patch("src.windows.subprocess.run", return_value=_mock_ps_success("result data")):
            assert _ps("Get-Date") == "result data"

    def test_error(self):
        with patch("src.windows.subprocess.run", return_value=_mock_ps_fail("fail reason")):
            result = _ps("bad cmd")
        assert "ERREUR" in result


# ===========================================================================
# Core: _ps_json
# ===========================================================================

class TestPsJson:
    def test_valid_json(self):
        data = {"Name": "test", "Status": "Running"}
        with patch("src.windows.subprocess.run", return_value=_mock_ps_success(json.dumps(data))):
            result = _ps_json("Get-Service test")
        assert result == data

    def test_invalid_json(self):
        with patch("src.windows.subprocess.run", return_value=_mock_ps_success("not json")):
            result = _ps_json("Get-Service test")
        assert result == "not json"

    def test_failure_returns_none(self):
        with patch("src.windows.subprocess.run", return_value=_mock_ps_fail()):
            result = _ps_json("bad cmd")
        assert result is None


# ===========================================================================
# Applications
# ===========================================================================

class TestApplications:
    def test_open_application(self):
        with patch("src.windows.subprocess.run", return_value=_mock_ps_success("OK")):
            result = open_application("notepad")
        assert result == "OK"

    def test_open_application_with_args(self):
        with patch("src.windows.subprocess.run", return_value=_mock_ps_success("OK")) as mock:
            open_application("chrome", "https://google.com")
        call_args = mock.call_args[0][0]
        assert "ArgumentList" in call_args[-1]

    def test_close_application(self):
        with patch("src.windows.subprocess.run", return_value=_mock_ps_success("Ferme: chrome")):
            result = close_application("chrome")
        assert "ferme" in result.lower()

    def test_open_url(self):
        with patch("src.windows.subprocess.run", return_value=_mock_ps_success("OK")):
            result = open_url("https://github.com")
        assert result == "OK"


# ===========================================================================
# Processes
# ===========================================================================

class TestProcesses:
    def test_list_processes_empty(self):
        with patch("src.windows.subprocess.run", return_value=_mock_ps_fail()):
            result = list_processes()
        assert result == []

    def test_list_processes_single(self):
        data = {"Name": "python", "Id": 1234}
        with patch("src.windows.subprocess.run", return_value=_mock_ps_success(json.dumps(data))):
            result = list_processes()
        assert len(result) == 1
        assert result[0]["Name"] == "python"

    def test_list_processes_multiple(self):
        data = [{"Name": "a"}, {"Name": "b"}]
        with patch("src.windows.subprocess.run", return_value=_mock_ps_success(json.dumps(data))):
            result = list_processes()
        assert len(result) == 2

    def test_kill_by_pid(self):
        with patch("src.windows.subprocess.run", return_value=_mock_ps_success("arrete")) as mock:
            kill_process("1234")
        assert "Id 1234" in mock.call_args[0][0][-1]

    def test_kill_by_name(self):
        with patch("src.windows.subprocess.run", return_value=_mock_ps_success("arrete")) as mock:
            kill_process("chrome")
        assert "Name" in mock.call_args[0][0][-1]


# ===========================================================================
# File operations
# ===========================================================================

class TestFileOps:
    def test_open_folder(self):
        with patch("src.windows.subprocess.run", return_value=_mock_ps_success("Dossier ouvert")):
            result = open_folder("C:\\Users")
        assert "dossier" in result.lower()

    def test_create_folder(self):
        with patch("src.windows.subprocess.run", return_value=_mock_ps_success("/\test")):
            result = create_folder("/\test")
        assert "test" in result

    def test_copy_item(self):
        with patch("src.windows.subprocess.run", return_value=_mock_ps_success("Copie OK")):
            result = copy_item("a.txt", "b.txt")
        assert "copie" in result.lower()

    def test_write_file(self):
        with patch("src.windows.subprocess.run", return_value=_mock_ps_success("Ecrit")):
            result = write_file("test.txt", "hello")
        assert "ecrit" in result.lower()

    def test_search_files(self):
        with patch("src.windows.subprocess.run", return_value=_mock_ps_success("file1.py\nfile2.py")):
            result = search_files("C:\\", "*.py")
        assert "py" in result


# ===========================================================================
# Registry
# ===========================================================================

class TestRegistry:
    def test_registry_get_value(self):
        with patch("src.windows.subprocess.run", return_value=_mock_ps_success("1")):
            result = registry_get("HKCU:/Software/Test", "Key")
        assert result == "1"

    def test_registry_set_valid_type(self):
        with patch("src.windows.subprocess.run", return_value=_mock_ps_success("OK")):
            result = registry_set("HKCU:/Test", "Key", "Value", "String")
        assert "mis a jour" in result.lower() or result == "OK"

    def test_registry_set_invalid_type(self):
        result = registry_set("HKCU:/Test", "Key", "Value", "EVIL_TYPE")
        assert "ERREUR" in result
        assert "invalide" in result.lower()


# ===========================================================================
# Services
# ===========================================================================

class TestServices:
    def test_check_service_found(self):
        data = {"Name": "wuauserv", "Status": "Running", "DisplayName": "Windows Update"}
        with patch("src.windows.subprocess.run", return_value=_mock_ps_success(json.dumps(data))):
            result = check_service("wuauserv")
        assert result["Name"] == "wuauserv"

    def test_check_service_not_found(self):
        with patch("src.windows.subprocess.run", return_value=_mock_ps_fail()):
            result = check_service("nonexistent")
        assert result["Status"] == "Unknown"


# ===========================================================================
# Notify
# ===========================================================================

class TestNotify:
    def test_notify_success(self):
        with patch("src.windows.run_powershell", return_value={"success": True, "stdout": "OK", "stderr": ""}):
            assert notify_windows("Title", "Message") is True

    def test_notify_failure(self):
        with patch("src.windows.run_powershell", return_value={"success": False, "stdout": "", "stderr": "err"}):
            assert notify_windows("Title", "Message") is False


# ===========================================================================
# Accessibility
# ===========================================================================

class TestAccessibility:
    def test_check_accessibility(self):
        with patch("src.windows.subprocess.run", return_value=_mock_ps_success("False")):
            result = check_accessibility()
        assert "narrator" in result
        assert "magnifier" in result

    def test_toggle_narrator_on(self):
        with patch("src.windows.subprocess.run", return_value=_mock_ps_success("Narrateur active")):
            result = toggle_narrator(enable=True)
        assert "active" in result.lower()

    def test_toggle_narrator_off(self):
        with patch("src.windows.subprocess.run", return_value=_mock_ps_success("Narrateur desactive")):
            result = toggle_narrator(enable=False)
        assert "desactive" in result.lower()


# ===========================================================================
# get_system_info (uses ctypes, needs partial mock)
# ===========================================================================

class TestGetSystemInfo:
    def test_returns_dict(self):
        with patch("src.windows.subprocess.run", return_value=_mock_ps_success("NVIDIA RTX 2060")):
            info = get_system_info()
        assert isinstance(info, dict)
        assert "hostname" in info
        assert "os_version" in info
        assert "cpu" in info
        assert "user" in info
