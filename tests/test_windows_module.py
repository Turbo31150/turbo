"""Comprehensive tests for src/windows.py — Windows automation toolkit.

All external dependencies (subprocess, ctypes, platform, os) are mocked.
No real PowerShell commands or Windows APIs are called.
"""

from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, patch, call

import pytest

# ---------------------------------------------------------------------------
# We must mock ctypes.windll before importing windows.py because
# get_system_info() uses ctypes.windll at call time, not import time.
# The module itself only imports subprocess and json at the top level,
# so a plain import is safe.
# ---------------------------------------------------------------------------
import src.windows as win


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_subprocess_run():
    """Patch subprocess.run and return the mock for configuration."""
    with patch("src.windows.subprocess.run") as mock_run:
        yield mock_run


def _make_completed(stdout="", stderr="", returncode=0):
    """Helper: build a CompletedProcess-like mock."""
    cp = MagicMock(spec=subprocess.CompletedProcess)
    cp.stdout = stdout
    cp.stderr = stderr
    cp.returncode = returncode
    return cp


def _ok(stdout="OK"):
    return _make_completed(stdout=stdout, returncode=0)


def _err(stderr="Something failed"):
    return _make_completed(stdout="", stderr=stderr, returncode=1)


# ═══════════════════════════════════════════════════════════════════════════
# 1. Core — run_powershell
# ═══════════════════════════════════════════════════════════════════════════

class TestRunPowershell:
    def test_success(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("hello")
        result = win.run_powershell("echo hello")
        assert result == {
            "success": True,
            "stdout": "hello",
            "stderr": "",
            "exit_code": 0,
        }
        mock_subprocess_run.assert_called_once()
        args = mock_subprocess_run.call_args
        assert args[0][0] == [
            "powershell", "-NoProfile", "-NonInteractive", "-Command", "echo hello"
        ]

    def test_failure_nonzero_exit(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _err("bad command")
        result = win.run_powershell("bad")
        assert result["success"] is False
        assert result["stderr"] == "bad command"
        assert result["exit_code"] == 1

    def test_timeout(self, mock_subprocess_run):
        mock_subprocess_run.side_effect = subprocess.TimeoutExpired("cmd", 60)
        result = win.run_powershell("slow", timeout=60)
        assert result == {
            "success": False,
            "stdout": "",
            "stderr": "Timeout",
            "exit_code": -1,
        }

    def test_os_error(self, mock_subprocess_run):
        mock_subprocess_run.side_effect = OSError("powershell not found")
        result = win.run_powershell("x")
        assert result["success"] is False
        assert "powershell not found" in result["stderr"]
        assert result["exit_code"] == -1

    def test_custom_timeout_passed_through(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok()
        win.run_powershell("cmd", timeout=120)
        _, kwargs = mock_subprocess_run.call_args
        assert kwargs["timeout"] == 120


# ═══════════════════════════════════════════════════════════════════════════
# 2. Core — _ps helper
# ═══════════════════════════════════════════════════════════════════════════

class TestPsHelper:
    def test_ps_success(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("data here")
        assert win._ps("Get-Date") == "data here"

    def test_ps_error_returns_erreur(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _err("oops")
        result = win._ps("bad")
        assert result.startswith("ERREUR:")
        assert "oops" in result


# ═══════════════════════════════════════════════════════════════════════════
# 3. Core — _sq (escape single quotes)
# ═══════════════════════════════════════════════════════════════════════════

class TestSqEscape:
    def test_no_quotes(self):
        assert win._sq("hello") == "hello"

    def test_single_quote(self):
        assert win._sq("it's") == "it''s"

    def test_multiple_quotes(self):
        assert win._sq("a'b'c") == "a''b''c"

    def test_empty_string(self):
        assert win._sq("") == ""


# ═══════════════════════════════════════════════════════════════════════════
# 4. Core — _ps_json
# ═══════════════════════════════════════════════════════════════════════════

class TestPsJson:
    def test_returns_parsed_dict(self, mock_subprocess_run):
        payload = {"Name": "svc", "Status": "Running"}
        mock_subprocess_run.return_value = _ok(json.dumps(payload))
        result = win._ps_json("Get-Service")
        assert result == payload

    def test_returns_parsed_list(self, mock_subprocess_run):
        payload = [{"a": 1}, {"a": 2}]
        mock_subprocess_run.return_value = _ok(json.dumps(payload))
        result = win._ps_json("Get-Process")
        assert result == payload

    def test_returns_raw_string_on_bad_json(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("not json {{{")
        result = win._ps_json("cmd")
        assert result == "not json {{{"

    def test_returns_none_on_failure(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _err("error")
        result = win._ps_json("cmd")
        assert result is None

    def test_returns_none_on_empty_stdout(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("")
        result = win._ps_json("cmd")
        assert result is None

    def test_appends_convertto_json(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("{}")
        win._ps_json("Get-Stuff")
        cmd_sent = mock_subprocess_run.call_args[0][0][4]  # -Command arg
        assert "ConvertTo-Json -Depth 3 -Compress" in cmd_sent


# ═══════════════════════════════════════════════════════════════════════════
# 5. System Info — get_system_info
# ═══════════════════════════════════════════════════════════════════════════

class TestGetSystemInfo:
    @patch("src.windows._ps", return_value="NVIDIA RTX 2060")
    def test_get_system_info_basic(self, mock_ps):
        """Test that get_system_info assembles info from platform/os/ctypes.

        platform, os, ctypes are imported locally inside get_system_info().
        We only mock ctypes.windll (the Windows-specific part) and leave
        ctypes.Structure / c_ulong / c_ulonglong real so the local class
        MEMORYSTATUSEX can be defined correctly.
        """
        with patch("platform.node", return_value="MY-PC"), \
             patch("platform.platform", return_value="Windows-11"), \
             patch("platform.processor", return_value="AMD Ryzen"), \
             patch.dict("os.environ", {"USERNAME": "Turbo"}), \
             patch("ctypes.windll") as mock_windll:

            # RAM: GlobalMemoryStatusEx succeeds (fills struct in-place)
            mock_windll.kernel32.GlobalMemoryStatusEx.return_value = True
            # Disk: no drives (bitmask 0) for simplicity
            mock_windll.kernel32.GetLogicalDrives.return_value = 0

            info = win.get_system_info()
            assert info["hostname"] == "MY-PC"
            assert info["os_version"] == "Windows-11"
            assert info["cpu"] == "AMD Ryzen"
            assert info["user"] == "Turbo"
            assert info["gpu"] == "NVIDIA RTX 2060"
            # RAM keys exist (values are 0 since the struct is zeroed)
            assert "ram_total_gb" in info
            assert "ram_usage_pct" in info

    @patch("src.windows._ps", return_value="GPU info")
    def test_get_system_info_ram_error_fallback(self, mock_ps):
        """When ctypes RAM query raises OSError, info['ram'] should be 'unknown'."""
        with patch("platform.node", return_value="PC"), \
             patch("platform.platform", return_value="Win"), \
             patch("platform.processor", return_value="CPU"), \
             patch.dict("os.environ", {"USERNAME": "user"}), \
             patch("ctypes.windll") as mock_windll:

            # Make GlobalMemoryStatusEx raise OSError to trigger the fallback
            mock_windll.kernel32.GlobalMemoryStatusEx.side_effect = OSError("fail")
            # Disk: also fail to hit the except branch
            mock_windll.kernel32.GetLogicalDrives.side_effect = OSError("no drives")

            info = win.get_system_info()
            # RAM fallback
            assert info.get("ram") == "unknown"
            # Disk fallback
            assert info.get("disks") == "unknown"
            # Other fields still populated
            assert info["hostname"] == "PC"


# ═══════════════════════════════════════════════════════════════════════════
# 6. GPU / Network info
# ═══════════════════════════════════════════════════════════════════════════

class TestGpuAndNetwork:
    def test_get_gpu_info(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("RTX 3090 | VRAM: 24GB")
        result = win.get_gpu_info()
        assert "RTX 3090" in result

    def test_get_network_info(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("Ethernet: 192.168.1.100")
        result = win.get_network_info()
        assert "192.168.1.100" in result


# ═══════════════════════════════════════════════════════════════════════════
# 7. Applications
# ═══════════════════════════════════════════════════════════════════════════

class TestApplications:
    def test_open_application_no_args(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("OK")
        result = win.open_application("notepad")
        assert result == "OK"
        cmd = mock_subprocess_run.call_args[0][0][4]
        assert "Start-Process 'notepad'" in cmd
        assert "-ArgumentList" not in cmd

    def test_open_application_with_args(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("OK")
        result = win.open_application("code", "--new-window")
        assert result == "OK"
        cmd = mock_subprocess_run.call_args[0][0][4]
        assert "-ArgumentList" in cmd

    def test_close_application(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("Ferme: chrome")
        result = win.close_application("chrome")
        assert "chrome" in result

    def test_open_url(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("OK")
        result = win.open_url("https://example.com", "firefox")
        assert result == "OK"
        cmd = mock_subprocess_run.call_args[0][0][4]
        assert "firefox" in cmd
        assert "example.com" in cmd

    def test_list_installed_apps_no_filter(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("AppList")
        result = win.list_installed_apps()
        assert result == "AppList"
        cmd = mock_subprocess_run.call_args[0][0][4]
        assert "-match" not in cmd

    def test_list_installed_apps_with_filter(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("Python 3.13")
        result = win.list_installed_apps("Python")
        assert "Python" in result
        cmd = mock_subprocess_run.call_args[0][0][4]
        assert "-match 'Python'" in cmd


# ═══════════════════════════════════════════════════════════════════════════
# 8. Processes
# ═══════════════════════════════════════════════════════════════════════════

class TestProcesses:
    def test_list_processes_no_filter(self, mock_subprocess_run):
        payload = [{"Name": "chrome", "Id": 1234}]
        mock_subprocess_run.return_value = _ok(json.dumps(payload))
        result = win.list_processes()
        assert isinstance(result, list)
        assert result[0]["Name"] == "chrome"

    def test_list_processes_with_filter(self, mock_subprocess_run):
        payload = {"Name": "python", "Id": 5678}
        mock_subprocess_run.return_value = _ok(json.dumps(payload))
        result = win.list_processes("python")
        assert isinstance(result, list)
        assert result[0]["Name"] == "python"
        cmd = mock_subprocess_run.call_args[0][0][4]
        assert "*python*" in cmd

    def test_list_processes_returns_empty_on_none(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _err("error")
        result = win.list_processes()
        assert result == []

    def test_kill_process_by_pid(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("Processus 1234 arrete")
        result = win.kill_process("1234")
        assert "1234" in result
        cmd = mock_subprocess_run.call_args[0][0][4]
        assert "-Id 1234" in cmd

    def test_kill_process_by_name(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("chrome arrete")
        result = win.kill_process("chrome")
        assert "chrome" in result
        cmd = mock_subprocess_run.call_args[0][0][4]
        assert "-Name 'chrome'" in cmd


# ═══════════════════════════════════════════════════════════════════════════
# 9. Windows Management
# ═══════════════════════════════════════════════════════════════════════════

class TestWindowsManagement:
    def test_list_windows(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("1234 chrome Google")
        result = win.list_windows()
        assert "chrome" in result

    def test_focus_window(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("Focus: Visual Studio Code")
        result = win.focus_window("Visual Studio")
        assert "Focus" in result
        cmd = mock_subprocess_run.call_args[0][0][4]
        assert "Visual Studio" in cmd
        assert "SetForegroundWindow" in cmd

    def test_minimize_window(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("Minimise")
        result = win.minimize_window("Code")
        assert "Minimise" in result
        cmd = mock_subprocess_run.call_args[0][0][4]
        assert "ShowWindow" in cmd
        assert ", 6)" in cmd  # SW_MINIMIZE = 6

    def test_maximize_window(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("Maximise")
        result = win.maximize_window("Code")
        assert "Maximise" in result
        cmd = mock_subprocess_run.call_args[0][0][4]
        assert "ShowWindow" in cmd
        assert ", 3)" in cmd  # SW_MAXIMIZE = 3


# ═══════════════════════════════════════════════════════════════════════════
# 10. Keyboard & Mouse
# ═══════════════════════════════════════════════════════════════════════════

class TestKeyboardMouse:
    def test_send_keys(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("Touches envoyees")
        result = win.send_keys("{ENTER}")
        assert "Touches" in result

    def test_type_text_escapes_special(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("Texte tape")
        result = win.type_text("hello+world")
        assert "Texte" in result
        cmd = mock_subprocess_run.call_args[0][0][4]
        # + should be escaped to {+}
        assert "{+}" in cmd

    def test_press_hotkey_ctrl_c(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("Raccourci: ctrl+c")
        result = win.press_hotkey("ctrl+c")
        assert "ctrl+c" in result
        cmd = mock_subprocess_run.call_args[0][0][4]
        # ctrl maps to ^, c stays c → "^c"
        assert "^c" in cmd

    def test_press_hotkey_alt_tab(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("Raccourci: alt+tab")
        win.press_hotkey("alt+tab")
        cmd = mock_subprocess_run.call_args[0][0][4]
        assert "%{TAB}" in cmd

    def test_mouse_click(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("Click (100,200)")
        result = win.mouse_click(100, 200)
        assert "Click" in result
        cmd = mock_subprocess_run.call_args[0][0][4]
        assert "SetCursorPos(100, 200)" in cmd


# ═══════════════════════════════════════════════════════════════════════════
# 11. Clipboard
# ═══════════════════════════════════════════════════════════════════════════

class TestClipboard:
    def test_clipboard_get(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("copied text")
        assert win.clipboard_get() == "copied text"

    def test_clipboard_set(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("Clipboard mis a jour")
        result = win.clipboard_set("new content")
        assert "Clipboard" in result
        cmd = mock_subprocess_run.call_args[0][0][4]
        assert "new content" in cmd


# ═══════════════════════════════════════════════════════════════════════════
# 12. Files & Folders
# ═══════════════════════════════════════════════════════════════════════════

class TestFilesAndFolders:
    def test_open_folder(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("Dossier ouvert: /\Users")
        result = win.open_folder("/\Users")
        assert "Dossier ouvert" in result

    def test_list_folder(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("file1.txt  file2.txt")
        result = win.list_folder("/\temp", "*.txt")
        assert "file1" in result
        cmd = mock_subprocess_run.call_args[0][0][4]
        assert "*.txt" in cmd

    def test_create_folder(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("/\new_folder")
        result = win.create_folder("/\new_folder")
        assert "new_folder" in result

    def test_copy_item(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("Copie OK: a -> b")
        result = win.copy_item("a", "b")
        assert "Copie OK" in result

    def test_move_item(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("Deplacement OK: a -> b")
        result = win.move_item("a", "b")
        assert "Deplacement OK" in result

    def test_delete_item(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("Supprime (corbeille): file.txt")
        result = win.delete_item("file.txt")
        assert "corbeille" in result

    def test_read_file(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("line1\nline2")
        result = win.read_file("/\test.txt", lines=10)
        assert "line1" in result
        cmd = mock_subprocess_run.call_args[0][0][4]
        assert "-TotalCount 10" in cmd

    def test_write_file(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("Ecrit: test.txt")
        result = win.write_file("test.txt", "hello world")
        assert "Ecrit" in result

    def test_search_files(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("/\dir/found.py")
        result = win.search_files("/\dir", "*.py")
        assert "found.py" in result


# ═══════════════════════════════════════════════════════════════════════════
# 13. Audio
# ═══════════════════════════════════════════════════════════════════════════

class TestAudio:
    def test_volume_up(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("Volume augmente")
        assert "augmente" in win.volume_up()

    def test_volume_down(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("Volume baisse")
        assert "baisse" in win.volume_down()

    def test_volume_mute(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("Mute bascule")
        assert "Mute" in win.volume_mute()


# ═══════════════════════════════════════════════════════════════════════════
# 14. Screen
# ═══════════════════════════════════════════════════════════════════════════

class TestScreen:
    def test_screenshot_default_filename(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("/\Desktop/capture.png")
        result = win.screenshot()
        assert "capture" in result

    def test_screenshot_custom_filename(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("/\Desktop/my_shot.png")
        result = win.screenshot("my_shot.png")
        assert "my_shot" in result
        cmd = mock_subprocess_run.call_args[0][0][4]
        assert "my_shot.png" in cmd

    def test_get_screen_resolution(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("Resolution: 1920x1080")
        result = win.get_screen_resolution()
        assert "1920x1080" in result


# ═══════════════════════════════════════════════════════════════════════════
# 15. Services
# ═══════════════════════════════════════════════════════════════════════════

class TestServices:
    def test_check_service_found(self, mock_subprocess_run):
        payload = {"Name": "wuauserv", "Status": "Running", "DisplayName": "Windows Update"}
        mock_subprocess_run.return_value = _ok(json.dumps(payload))
        result = win.check_service("wuauserv")
        assert result["Name"] == "wuauserv"
        assert result["Status"] == "Running"

    def test_check_service_not_found(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _err("not found")
        result = win.check_service("fakesvc")
        assert result["Name"] == "fakesvc"
        assert result["Status"] == "Unknown"

    def test_list_services_no_filter(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("Running  wuauserv")
        result = win.list_services()
        assert "wuauserv" in result

    def test_list_services_with_filter(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("Running  ssh")
        result = win.list_services("ssh")
        cmd = mock_subprocess_run.call_args[0][0][4]
        assert "*ssh*" in cmd

    def test_start_service(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("Service wuauserv demarre")
        result = win.start_service("wuauserv")
        assert "demarre" in result

    def test_stop_service(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("Service wuauserv arrete")
        result = win.stop_service("wuauserv")
        assert "arrete" in result


# ═══════════════════════════════════════════════════════════════════════════
# 16. System Control
# ═══════════════════════════════════════════════════════════════════════════

class TestSystemControl:
    def test_lock_screen(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("Ecran verrouille")
        result = win.lock_screen()
        assert "verrouille" in result

    def test_shutdown_pc(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("Extinction en cours")
        result = win.shutdown_pc()
        assert "Extinction" in result

    def test_restart_pc(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("Redemarrage en cours")
        result = win.restart_pc()
        assert "Redemarrage" in result

    def test_sleep_pc(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("Mise en veille")
        result = win.sleep_pc()
        assert "veille" in result


# ═══════════════════════════════════════════════════════════════════════════
# 17. Notifications
# ═══════════════════════════════════════════════════════════════════════════

class TestNotifications:
    def test_notify_success(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("OK")
        result = win.notify_windows("Title", "Body")
        assert result is True

    def test_notify_failure(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _err("no runtime")
        result = win.notify_windows("Title", "Body")
        assert result is False

    def test_notify_escapes_quotes(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("OK")
        win.notify_windows("It's a test", "Don't panic")
        cmd = mock_subprocess_run.call_args[0][0][4]
        # Single quotes should be doubled for PS safety
        assert "It''s a test" in cmd
        assert "Don''t panic" in cmd


# ═══════════════════════════════════════════════════════════════════════════
# 18. WiFi & Network
# ═══════════════════════════════════════════════════════════════════════════

class TestWifiNetwork:
    def test_get_wifi_networks(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("SSID: MyWiFi\nSignal: 80%")
        result = win.get_wifi_networks()
        assert "MyWiFi" in result

    def test_get_ip_address(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("Ethernet: 192.168.1.10")
        result = win.get_ip_address()
        assert "192.168.1.10" in result

    def test_ping_host(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("Address: 8.8.8.8  ResponseTime: 15")
        result = win.ping_host("8.8.8.8")
        assert "8.8.8.8" in result


# ═══════════════════════════════════════════════════════════════════════════
# 19. Registry
# ═══════════════════════════════════════════════════════════════════════════

class TestRegistry:
    def test_registry_get_with_name(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("1")
        result = win.registry_get("HKLM:/Software/Test", "Value")
        assert result == "1"
        cmd = mock_subprocess_run.call_args[0][0][4]
        assert "Get-ItemPropertyValue" in cmd
        assert "-Name 'Value'" in cmd

    def test_registry_get_no_name(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("Value1=1")
        result = win.registry_get("HKLM:/Software/Test")
        assert "Value1" in result
        cmd = mock_subprocess_run.call_args[0][0][4]
        assert "Get-ItemProperty" in cmd

    def test_registry_set_valid_type(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("Registry mis a jour")
        result = win.registry_set("HKLM:/Test", "Key", "Value", "DWord")
        assert "mis a jour" in result
        cmd = mock_subprocess_run.call_args[0][0][4]
        assert "-Type DWord" in cmd

    def test_registry_set_invalid_type(self, mock_subprocess_run):
        result = win.registry_set("HKLM:/Test", "Key", "Value", "EvilType")
        assert "ERREUR" in result
        assert "invalide" in result
        # subprocess.run should NOT have been called
        mock_subprocess_run.assert_not_called()

    def test_registry_set_all_valid_types(self, mock_subprocess_run):
        """Verify all allowed registry types are accepted."""
        mock_subprocess_run.return_value = _ok("OK")
        for reg_type in ("String", "DWord", "QWord", "Binary", "ExpandString", "MultiString"):
            win.registry_set("HKLM:/Test", "K", "V", reg_type)
        assert mock_subprocess_run.call_count == 6


# ═══════════════════════════════════════════════════════════════════════════
# 20. Scheduled Tasks
# ═══════════════════════════════════════════════════════════════════════════

class TestScheduledTasks:
    def test_list_scheduled_tasks_no_filter(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("Ready  MyTask")
        result = win.list_scheduled_tasks()
        assert "MyTask" in result
        cmd = mock_subprocess_run.call_args[0][0][4]
        assert "-match" not in cmd

    def test_list_scheduled_tasks_with_filter(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("Ready  BackupTask")
        result = win.list_scheduled_tasks("Backup")
        assert "BackupTask" in result
        cmd = mock_subprocess_run.call_args[0][0][4]
        assert "-match 'Backup'" in cmd


# ═══════════════════════════════════════════════════════════════════════════
# 21. Accessibility
# ═══════════════════════════════════════════════════════════════════════════

class TestAccessibility:
    def test_check_accessibility(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("True")
        result = win.check_accessibility()
        assert "narrator" in result
        assert "magnifier" in result
        assert "speech_recognition" in result
        # Should have been called 3 times (once per check)
        assert mock_subprocess_run.call_count == 3

    def test_toggle_narrator_enable(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("Narrateur active")
        result = win.toggle_narrator(enable=True)
        assert "active" in result
        cmd = mock_subprocess_run.call_args[0][0][4]
        assert "Start-Process narrator" in cmd

    def test_toggle_narrator_disable(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("Narrateur desactive")
        result = win.toggle_narrator(enable=False)
        assert "desactive" in result
        cmd = mock_subprocess_run.call_args[0][0][4]
        assert "Stop-Process -Name Narrator" in cmd


# ═══════════════════════════════════════════════════════════════════════════
# 22. _SENDKEYS_SPECIAL translation table
# ═══════════════════════════════════════════════════════════════════════════

class TestSendKeysSpecial:
    """Verify the translation table used by type_text."""

    @pytest.mark.parametrize("char,expected", [
        ("+", "{+}"),
        ("^", "{^}"),
        ("%", "{%}"),
        ("~", "{~}"),
        ("(", "{(}"),
        (")", "{)}"),
        ("[", "{[}"),
        ("]", "{]}"),
        ("{", "{{}"),
        ("}", "{}}"),
    ])
    def test_special_char_escaped(self, char, expected):
        result = char.translate(win._SENDKEYS_SPECIAL)
        assert result == expected

    def test_normal_chars_unchanged(self):
        assert "hello".translate(win._SENDKEYS_SPECIAL) == "hello"


# ═══════════════════════════════════════════════════════════════════════════
# 23. Edge cases & integration-style
# ═══════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_ps_timeout_default_15s(self, mock_subprocess_run):
        """_ps uses 15s default timeout."""
        mock_subprocess_run.return_value = _ok("ok")
        win._ps("cmd")
        _, kwargs = mock_subprocess_run.call_args
        assert kwargs["timeout"] == 15

    def test_ps_custom_timeout(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("ok")
        win._ps("cmd", timeout=30)
        _, kwargs = mock_subprocess_run.call_args
        assert kwargs["timeout"] == 30

    def test_open_application_with_quotes_in_name(self, mock_subprocess_run):
        """App name with single quotes should be escaped."""
        mock_subprocess_run.return_value = _ok("OK")
        win.open_application("it's app")
        cmd = mock_subprocess_run.call_args[0][0][4]
        assert "it''s app" in cmd

    def test_kill_process_distinguishes_pid_vs_name(self, mock_subprocess_run):
        """Numeric strings → -Id, otherwise → -Name."""
        mock_subprocess_run.return_value = _ok("done")

        win.kill_process("999")
        cmd1 = mock_subprocess_run.call_args[0][0][4]
        assert "-Id 999" in cmd1

        win.kill_process("my_proc")
        cmd2 = mock_subprocess_run.call_args[0][0][4]
        assert "-Name 'my_proc'" in cmd2

    def test_list_processes_dict_wrapped_in_list(self, mock_subprocess_run):
        """When PS returns a single object (dict), it should be wrapped in a list."""
        single = {"Name": "solo", "Id": 1}
        mock_subprocess_run.return_value = _ok(json.dumps(single))
        result = win.list_processes()
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["Name"] == "solo"

    def test_read_file_lines_cast_to_int(self, mock_subprocess_run):
        """lines parameter is cast to int to prevent injection."""
        mock_subprocess_run.return_value = _ok("content")
        win.read_file("f.txt", lines=25)
        cmd = mock_subprocess_run.call_args[0][0][4]
        assert "-TotalCount 25" in cmd

    def test_screenshot_generates_timestamp_pattern_when_no_filename(self, mock_subprocess_run):
        mock_subprocess_run.return_value = _ok("path")
        win.screenshot()
        cmd = mock_subprocess_run.call_args[0][0][4]
        assert "capture_$(Get-Date" in cmd
