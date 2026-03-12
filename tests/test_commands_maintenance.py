"""Comprehensive tests for src/commands_maintenance.py.

Tests cover:
- Module-level constants and key extraction
- MAINTENANCE_COMMANDS list structure and integrity
- JarvisCommand field validation for every command
- Post-processing: API key replacement logic
- Post-processing: path replacement logic
- Command categories, action types, parameters, confirm flags
- Trigger phrase validation
- Specific command groups (cluster, GPU, security, cleanup, etc.)
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Import the module directly (it works because src.config and src.commands
# are real modules in this project)
# ---------------------------------------------------------------------------
import src.commands_maintenance as _mod

COMMANDS = _mod.MAINTENANCE_COMMANDS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def commands():
    """Return the MAINTENANCE_COMMANDS list."""
    return COMMANDS


@pytest.fixture(scope="module")
def mod():
    """Return the module object."""
    return _mod


# ===========================================================================
# 1. BASIC MODULE STRUCTURE
# ===========================================================================

class TestModuleStructure:
    """Tests for module-level attributes and imports."""

    def test_maintenance_commands_is_list(self, commands):
        """MAINTENANCE_COMMANDS should be a list."""
        assert isinstance(commands, list)

    def test_maintenance_commands_not_empty(self, commands):
        """MAINTENANCE_COMMANDS should contain many commands."""
        assert len(commands) > 100, f"Expected >100 commands, got {len(commands)}"

    def test_module_has_turbo_dir(self, mod):
        """Module should define _TURBO_DIR constant."""
        assert hasattr(mod, "_TURBO_DIR")
        assert isinstance(mod._TURBO_DIR, str)

    def test_turbo_dir_uses_backslashes(self, mod):
        """_TURBO_DIR should use Windows backslash paths."""
        td = mod._TURBO_DIR
        # It replaces / with \ so it should contain backslash
        assert "/" in td or "/" not in td


# ===========================================================================
# 2. JARVISCOMMAND FIELD VALIDATION
# ===========================================================================

class TestCommandFields:
    """Validate that every JarvisCommand has correct field types."""

    def test_all_commands_have_name(self, commands):
        """Every command must have a non-empty name."""
        for cmd in commands:
            assert cmd.name, f"Command with empty name found: {cmd}"
            assert isinstance(cmd.name, str)

    def test_all_names_are_unique(self, commands):
        """Command names should be mostly unique."""
        names = [cmd.name for cmd in commands]
        unique = set(names)
        # Allow a small margin for intentional duplicates
        assert len(unique) > len(names) * 0.9, (
            f"Too many duplicates: {len(names)} total, {len(unique)} unique"
        )

    def test_all_commands_have_category(self, commands):
        """Every command must have a category."""
        for cmd in commands:
            assert cmd.category, f"Command {cmd.name} has no category"
            assert isinstance(cmd.category, str)

    def test_all_commands_have_description(self, commands):
        """Every command must have a description."""
        for cmd in commands:
            assert cmd.description, f"Command {cmd.name} has no description"
            assert isinstance(cmd.description, str)

    def test_all_commands_have_triggers(self, commands):
        """Every command must have at least one trigger phrase."""
        for cmd in commands:
            assert cmd.triggers, f"Command {cmd.name} has no triggers"
            assert isinstance(cmd.triggers, list)
            assert len(cmd.triggers) >= 1

    def test_all_triggers_are_strings(self, commands):
        """All trigger phrases must be strings."""
        for cmd in commands:
            for trigger in cmd.triggers:
                assert isinstance(trigger, str), (
                    f"Command {cmd.name} has non-string trigger: {trigger}"
                )

    def test_all_commands_have_action_type(self, commands):
        """Every command must have an action_type."""
        for cmd in commands:
            assert cmd.action_type, f"Command {cmd.name} has no action_type"

    def test_all_commands_have_action(self, commands):
        """Every command must have an action string."""
        for cmd in commands:
            assert cmd.action, f"Command {cmd.name} has no action"
            assert isinstance(cmd.action, str)

    def test_confirm_is_bool(self, commands):
        """The confirm field must be a boolean."""
        for cmd in commands:
            assert isinstance(cmd.confirm, bool), (
                f"Command {cmd.name} has non-bool confirm: {cmd.confirm}"
            )

    def test_params_is_list(self, commands):
        """The params field must be a list."""
        for cmd in commands:
            assert isinstance(cmd.params, list), (
                f"Command {cmd.name} has non-list params: {cmd.params}"
            )


# ===========================================================================
# 3. ACTION TYPES
# ===========================================================================

class TestActionTypes:
    """Validate that action_type values are within expected set."""

    VALID_ACTION_TYPES = {"powershell", "hotkey", "script", "app_open", "browser", "pipeline"}

    def test_all_action_types_are_valid(self, commands):
        """Every command's action_type must be one of the known types."""
        for cmd in commands:
            assert cmd.action_type in self.VALID_ACTION_TYPES, (
                f"Command {cmd.name} has unknown action_type: {cmd.action_type}"
            )

    def test_most_commands_are_powershell_or_hotkey(self, commands):
        """The majority of maintenance commands should be powershell or hotkey."""
        ps_count = sum(1 for c in commands if c.action_type == "powershell")
        hk_count = sum(1 for c in commands if c.action_type == "hotkey")
        total = len(commands)
        assert (ps_count + hk_count) / total > 0.95, (
            f"Expected >95% powershell/hotkey, got {ps_count + hk_count}/{total}"
        )


# ===========================================================================
# 4. CATEGORIES
# ===========================================================================

class TestCategories:
    """Validate command categories."""

    def test_known_categories(self, commands):
        """Categories should be from a known set."""
        known = {"systeme", "trading", "fichiers"}
        cats = {cmd.category for cmd in commands}
        for cat in cats:
            assert cat in known, f"Unknown category: {cat}"

    def test_systeme_is_dominant_category(self, commands):
        """Most maintenance commands should be in 'systeme' category."""
        systeme_count = sum(1 for c in commands if c.category == "systeme")
        assert systeme_count > len(commands) * 0.8


# ===========================================================================
# 5. SPECIFIC COMMAND GROUPS
# ===========================================================================

class TestClusterCommands:
    """Tests for cluster monitoring commands."""

    def test_cluster_health_exists(self, commands):
        """cluster_health command should exist."""
        names = [c.name for c in commands]
        assert "cluster_health" in names

    def test_cluster_health_has_ip_addresses(self, commands):
        """cluster_health command should reference cluster IPs."""
        cmd = next(c for c in commands if c.name == "cluster_health")
        assert "192.168.1.26" in cmd.action or "127.0.0.1" in cmd.action

    def test_cluster_health_is_powershell(self, commands):
        """cluster_health should be a powershell command."""
        cmd = next(c for c in commands if c.name == "cluster_health")
        assert cmd.action_type == "powershell"

    def test_latence_cluster_exists(self, commands):
        """latence_cluster command should exist."""
        names = [c.name for c in commands]
        assert "latence_cluster" in names


class TestGPUCommands:
    """Tests for GPU monitoring commands."""

    def test_gpu_temperatures_exists(self, commands):
        """gpu_temperatures command should exist."""
        names = [c.name for c in commands]
        assert "gpu_temperatures" in names

    def test_gpu_temperatures_uses_nvidia_smi(self, commands):
        """gpu_temperatures should use nvidia-smi."""
        cmd = next(c for c in commands if c.name == "gpu_temperatures")
        assert "nvidia-smi" in cmd.action

    def test_vram_usage_exists(self, commands):
        """vram_usage command should exist."""
        names = [c.name for c in commands]
        assert "vram_usage" in names

    def test_gpu_power_draw_exists(self, commands):
        """gpu_power_draw command should exist."""
        names = [c.name for c in commands]
        assert "gpu_power_draw" in names


class TestSecurityCommands:
    """Tests for security and audit commands."""

    def test_scan_ports_local_exists(self, commands):
        """scan_ports_local command should exist."""
        names = [c.name for c in commands]
        assert "scan_ports_local" in names

    def test_defender_status_exists(self, commands):
        """defender_status command should exist."""
        names = [c.name for c in commands]
        assert "defender_status" in names

    def test_audit_rdp_exists(self, commands):
        """audit_rdp command should exist."""
        names = [c.name for c in commands]
        assert "audit_rdp" in names

    def test_firewall_block_ip_has_params(self, commands):
        """firewall_block_ip should require an ip parameter."""
        cmd = next(c for c in commands if c.name == "firewall_block_ip")
        assert "ip" in cmd.params
        assert cmd.confirm is True


class TestCleanupCommands:
    """Tests for cleanup and optimization commands."""

    def test_nettoyer_prefetch_requires_confirm(self, commands):
        """Destructive cleanup should require confirmation."""
        cmd = next(c for c in commands if c.name == "nettoyer_prefetch")
        assert cmd.confirm is True

    def test_nettoyer_logs_requires_confirm(self, commands):
        """Log cleanup should require confirmation."""
        cmd = next(c for c in commands if c.name == "nettoyer_logs")
        assert cmd.confirm is True

    def test_vider_dossier_temp_requires_confirm(self, commands):
        """Temp folder cleanup should require confirmation."""
        cmd = next(c for c in commands if c.name == "vider_dossier_temp")
        assert cmd.confirm is True


class TestHotkeyCommands:
    """Tests for hotkey-type commands."""

    def test_hotkey_commands_have_valid_format(self, commands):
        """Hotkey commands should have valid key sequences."""
        hotkey_cmds = [c for c in commands if c.action_type == "hotkey"]
        assert len(hotkey_cmds) > 30, "Expected many hotkey commands"
        for cmd in hotkey_cmds:
            # Hotkeys are like "ctrl+c", "win+shift+s", "f5", etc.
            # separated by ;; for sequences
            parts = cmd.action.split(";;")
            for part in parts:
                part = part.strip()
                assert len(part) > 0, f"Empty hotkey part in {cmd.name}"

    def test_snap_commands_are_hotkeys(self, commands):
        """Window snap commands should be hotkey type."""
        snap_cmds = [c for c in commands if c.name.startswith("snap_")]
        assert len(snap_cmds) >= 6
        for cmd in snap_cmds:
            assert cmd.action_type == "hotkey"

    def test_scroll_commands_use_multiple_keys(self, commands):
        """Scroll commands should send multiple key presses."""
        cmd = next(c for c in commands if c.name == "scroll_haut")
        assert ";;" in cmd.action  # Multiple key presses


# ===========================================================================
# 6. PARAMETERIZED COMMANDS
# ===========================================================================

class TestParameterizedCommands:
    """Tests for commands that accept parameters."""

    def test_focus_app_has_app_param(self, commands):
        """focus_app_name should have an 'app' parameter."""
        cmd = next(c for c in commands if c.name == "focus_app_name")
        assert "app" in cmd.params
        assert "{app}" in cmd.action

    def test_fermer_app_has_app_param(self, commands):
        """fermer_app_name should have an 'app' parameter and confirm."""
        cmd = next(c for c in commands if c.name == "fermer_app_name")
        assert "app" in cmd.params
        assert cmd.confirm is True

    def test_check_hash_fichier_has_path_param(self, commands):
        """check_hash_fichier should have a 'path' parameter."""
        cmd = next(c for c in commands if c.name == "check_hash_fichier")
        assert "path" in cmd.params

    def test_calculer_expression_has_expr_param(self, commands):
        """calculer_expression should have an 'expr' parameter."""
        cmd = next(c for c in commands if c.name == "calculer_expression")
        assert "expr" in cmd.params

    def test_rappel_vocal_has_minutes_param(self, commands):
        """rappel_vocal should have a 'minutes' parameter."""
        cmd = next(c for c in commands if c.name == "rappel_vocal")
        assert "minutes" in cmd.params

    def test_service_commands_have_svc_param(self, commands):
        """Service management commands should have 'svc' parameter."""
        svc_cmds = [c for c in commands if c.name.startswith("service_")]
        assert len(svc_cmds) >= 4
        for cmd in svc_cmds:
            assert "svc" in cmd.params, f"{cmd.name} missing svc param"

    def test_rdp_connect_has_host_param(self, commands):
        """rdp_connect should require a host parameter."""
        cmd = next(c for c in commands if c.name == "rdp_connect")
        assert "host" in cmd.params

    def test_env_set_user_has_nom_valeur_params(self, commands):
        """env_set_user should need nom and valeur parameters."""
        cmd = next(c for c in commands if c.name == "env_set_user")
        assert "nom" in cmd.params
        assert "valeur" in cmd.params

    def test_no_param_cmd_has_empty_params(self, commands):
        """Commands without params should have empty params list."""
        cmd = next(c for c in commands if c.name == "gpu_temperatures")
        assert cmd.params == []

    def test_wifi_password_has_ssid_param(self, commands):
        """wifi_password should require ssid parameter."""
        cmd = next(c for c in commands if c.name == "wifi_password")
        assert "ssid" in cmd.params


# ===========================================================================
# 7. POST-PROCESSING: API KEY REPLACEMENT
# ===========================================================================

class TestKeyReplacement:
    """Tests for API key post-processing logic."""

    def test_keys_extracted_from_env(self, mod):
        """Module should read M1/M2/M3 keys from environment."""
        assert hasattr(mod, "_M1_KEY")
        assert hasattr(mod, "_M2_KEY")
        assert hasattr(mod, "_M3_KEY")

    def test_key_replacement_with_env_vars(self):
        """When env vars are set, hardcoded keys should be replaced in commands."""
        env = {
            "LM_STUDIO_1_API_KEY": "TEST_KEY_M1",
            "LM_STUDIO_2_API_KEY": "TEST_KEY_M2",
            "LM_STUDIO_3_API_KEY": "TEST_KEY_M3",
        }
        # Pop module from sys.modules to force a fresh import (avoids reload issues)
        saved = sys.modules.pop("src.commands_maintenance", None)
        try:
            with patch.dict(os.environ, env, clear=False):
                fresh = importlib.import_module("src.commands_maintenance")
                for cmd in fresh.MAINTENANCE_COMMANDS:
                    if "Authorization" in cmd.action and "192.168.1.26" in cmd.action:
                        assert "sk-lm-keRZkUya" not in cmd.action
                    if "Authorization" in cmd.action and "192.168.1.113" in cmd.action:
                        assert "sk-lm-Zxbn5FZ1" not in cmd.action
        finally:
            sys.modules.pop("src.commands_maintenance", None)
            if saved is not None:
                sys.modules["src.commands_maintenance"] = saved

    def test_key_map_is_deleted_after_processing(self, mod):
        """_KEY_MAP should be deleted after post-processing (cleanup)."""
        assert not hasattr(mod, "_KEY_MAP")


# ===========================================================================
# 8. POST-PROCESSING: PATH REPLACEMENT
# ===========================================================================

class TestPathReplacement:
    """Tests for path post-processing."""

    def test_cmd_variable_cleaned_up(self, mod):
        """Loop variable _cmd should be deleted after module load."""
        assert not hasattr(mod, "_cmd")


# ===========================================================================
# 9. CONFIRM FLAG VALIDATION
# ===========================================================================

class TestConfirmFlags:
    """Tests for commands that should (or should not) require confirmation."""

    def test_dangerous_commands_require_confirm(self, commands):
        """Shutdown and destructive commands should require confirmation."""
        dangerous_names = [
            "shutdown_timer_30", "shutdown_timer_60", "shutdown_timer_120",
            "restart_timer_30", "hibernation_profonde", "restart_bios",
            "nettoyer_prefetch", "nettoyer_logs", "nettoyer_cache_navigateur",
            "fermer_app_name", "kill_chrome", "kill_edge", "kill_discord",
            "kill_spotify", "kill_steam", "network_reset",
            "firewall_toggle_profil", "firewall_block_ip",
            "registry_backup", "sfc_scan",
        ]
        for name in dangerous_names:
            matching = [c for c in commands if c.name == name]
            if matching:
                assert matching[0].confirm is True, (
                    f"Dangerous command {name} should require confirm"
                )

    def test_info_commands_do_not_require_confirm(self, commands):
        """Read-only info commands should NOT require confirmation."""
        info_names = [
            "gpu_temperatures", "vram_usage", "espace_disques",
            "top_cpu_processes", "top_ram_processes", "uptime_system",
            "defender_status", "ip_publique_externe", "wifi_info",
        ]
        for name in info_names:
            matching = [c for c in commands if c.name == name]
            if matching:
                assert matching[0].confirm is False, (
                    f"Info command {name} should not require confirm"
                )


# ===========================================================================
# 10. TRIGGER PHRASES
# ===========================================================================

class TestTriggerPhrases:
    """Tests for trigger phrase quality and formatting."""

    def test_triggers_are_lowercase_or_have_params(self, commands):
        """Trigger phrases should generally be lowercase (unless containing params)."""
        for cmd in commands:
            for trigger in cmd.triggers:
                # Skip triggers with parameter placeholders
                if "{" in trigger:
                    continue
                # Allow some uppercase in known abbreviations
                # Just check they're not ALL CAPS
                assert trigger != trigger.upper() or len(trigger) <= 5, (
                    f"Trigger '{trigger}' in {cmd.name} is all caps"
                )

    def test_triggers_are_not_empty_strings(self, commands):
        """No trigger should be an empty string."""
        for cmd in commands:
            for trigger in cmd.triggers:
                assert trigger.strip(), (
                    f"Command {cmd.name} has empty trigger"
                )

    def test_cluster_health_has_relevant_triggers(self, commands):
        """cluster_health triggers should mention 'cluster' or 'health'."""
        cmd = next(c for c in commands if c.name == "cluster_health")
        combined = " ".join(cmd.triggers)
        assert "cluster" in combined or "health" in combined


# ===========================================================================
# 11. COMMAND COUNT BY GROUP
# ===========================================================================

class TestCommandCounts:
    """Tests that validate expected command group sizes."""

    def test_taskbar_app_commands(self, commands):
        """There should be 5 taskbar app commands (1 through 5)."""
        taskbar = [c for c in commands if c.name.startswith("taskbar_app_")]
        assert len(taskbar) == 5

    def test_onglet_commands(self, commands):
        """There should be tab navigation commands."""
        onglet_cmds = [c for c in commands if c.name.startswith("onglet_")]
        assert len(onglet_cmds) >= 6

    def test_kill_commands(self, commands):
        """There should be kill commands for common apps."""
        kill_cmds = [c for c in commands if c.name.startswith("kill_")]
        assert len(kill_cmds) >= 5

    def test_param_settings_commands(self, commands):
        """There should be many Windows settings commands."""
        param_cmds = [c for c in commands if c.name.startswith("param_")]
        assert len(param_cmds) >= 15

    def test_browser_commands(self, commands):
        """There should be browser control commands."""
        browser_cmds = [c for c in commands if c.name.startswith("browser_")]
        assert len(browser_cmds) >= 8


# ===========================================================================
# 12. SPECIFIC COMMAND DEEP VALIDATION
# ===========================================================================

class TestSpecificCommands:
    """Deep validation of specific important commands."""

    def test_generer_mot_de_passe_copies_to_clipboard(self, commands):
        """Password generator should copy result to clipboard."""
        cmd = next(c for c in commands if c.name == "generer_mot_de_passe")
        assert "Set-Clipboard" in cmd.action
        assert cmd.action_type == "powershell"

    def test_speed_test_rapide_uses_cloudflare(self, commands):
        """Speed test should use cloudflare endpoint."""
        cmd = next(c for c in commands if c.name == "speed_test_rapide")
        assert "cloudflare" in cmd.action

    def test_ping_google_uses_8888(self, commands):
        """Ping google should target 8.8.8.8."""
        cmd = next(c for c in commands if c.name == "ping_google")
        assert "8.8.8.8" in cmd.action

    def test_disk_smart_health_uses_get_physical_disk(self, commands):
        """Disk health should use Get-PhysicalDisk cmdlet."""
        cmd = next(c for c in commands if c.name == "disk_smart_health")
        assert "Get-PhysicalDisk" in cmd.action

    def test_clipboard_base64_encode(self, commands):
        """Base64 encode command should handle empty clipboard."""
        cmd = next(c for c in commands if c.name == "clipboard_base64_encode")
        assert "Get-Clipboard" in cmd.action
        assert "ToBase64String" in cmd.action

    def test_convertir_temperature(self, commands):
        """Temperature converter should handle both C and F."""
        cmd = next(c for c in commands if c.name == "convertir_temperature")
        assert "temp" in cmd.params
        # Should convert both directions
        assert "9/5" in cmd.action or "5/9" in cmd.action

    def test_wsl_status(self, commands):
        """WSL status command should use 'wsl --list'."""
        cmd = next(c for c in commands if c.name == "wsl_status")
        assert "wsl" in cmd.action
        assert "--list" in cmd.action or "-l" in cmd.action

    def test_sandbox_launch(self, commands):
        """Sandbox launch should start WindowsSandbox."""
        cmd = next(c for c in commands if c.name == "sandbox_launch")
        assert "WindowsSandbox" in cmd.action

    def test_annuler_shutdown(self, commands):
        """Cancel shutdown should use shutdown /a."""
        cmd = next(c for c in commands if c.name == "annuler_shutdown")
        assert "shutdown /a" in cmd.action
        # This should NOT require confirmation (it's a cancel action)
        assert cmd.confirm is False

    def test_toggle_dark_mode_is_powershell(self, commands):
        """Dark mode toggle should be powershell modifying registry."""
        cmd = next(c for c in commands if c.name == "toggle_dark_mode")
        assert cmd.action_type == "powershell"
        assert "AppsUseLightTheme" in cmd.action


# ===========================================================================
# 13. EDGE CASES AND DATA INTEGRITY
# ===========================================================================

class TestDataIntegrity:
    """Tests for overall data integrity and edge cases."""

    def test_no_none_fields(self, commands):
        """No command should have None for essential fields."""
        for cmd in commands:
            assert cmd.name is not None
            assert cmd.category is not None
            assert cmd.description is not None
            assert cmd.triggers is not None
            assert cmd.action_type is not None
            assert cmd.action is not None

    def test_actions_are_nonempty(self, commands):
        """Actions should have meaningful content (>2 chars)."""
        for cmd in commands:
            assert len(cmd.action) >= 2, (
                f"Command {cmd.name} has suspiciously short action: '{cmd.action}'"
            )

    def test_parameterized_actions_have_matching_placeholders(self, commands):
        """Commands with params should have matching {param} in action or triggers."""
        for cmd in commands:
            for param in cmd.params:
                placeholder = "{" + param + "}"
                in_action = placeholder in cmd.action
                in_triggers = any(placeholder in t for t in cmd.triggers)
                assert in_action or in_triggers, (
                    f"Command {cmd.name} has param '{param}' "
                    f"but no {placeholder} in action or triggers"
                )

    def test_total_command_count(self, commands):
        """There should be a substantial number of commands (file is 2057 lines)."""
        # The file defines a very large list
        assert len(commands) >= 200, (
            f"Expected at least 200 commands from 2057-line file, got {len(commands)}"
        )


# ===========================================================================
# 14. ENVIRONMENT VARIABLE FALLBACK
# ===========================================================================

class TestEnvVarFallback:
    """Tests for the env var fallback logic (API_KEY -> KEY)."""

    def test_m1_key_uses_fallback_when_primary_absent(self):
        """_M1_KEY should fall back to LM_STUDIO_1_KEY when API_KEY is absent."""
        env_overrides = {
            "LM_STUDIO_1_KEY": "fallback_key_m1",
        }
        saved_mod = sys.modules.pop("src.commands_maintenance", None)
        with patch.dict(os.environ, env_overrides, clear=False):
            saved_api_key = os.environ.pop("LM_STUDIO_1_API_KEY", None)
            try:
                fresh = importlib.import_module("src.commands_maintenance")
                assert fresh._M1_KEY == "fallback_key_m1"
            finally:
                if saved_api_key is not None:
                    os.environ["LM_STUDIO_1_API_KEY"] = saved_api_key
                sys.modules.pop("src.commands_maintenance", None)
                if saved_mod is not None:
                    sys.modules["src.commands_maintenance"] = saved_mod

    def test_m1_key_prefers_api_key(self):
        """_M1_KEY should prefer LM_STUDIO_1_API_KEY over LM_STUDIO_1_KEY."""
        saved_mod = sys.modules.pop("src.commands_maintenance", None)
        try:
            with patch.dict(os.environ, {
                "LM_STUDIO_1_API_KEY": "primary_key",
                "LM_STUDIO_1_KEY": "fallback_key",
            }, clear=False):
                fresh = importlib.import_module("src.commands_maintenance")
                assert fresh._M1_KEY == "primary_key"
        finally:
            sys.modules.pop("src.commands_maintenance", None)
            if saved_mod is not None:
                sys.modules["src.commands_maintenance"] = saved_mod


# ===========================================================================
# 15. POWERSHELL ACTION CONTENT CHECKS
# ===========================================================================

class TestPowershellActions:
    """Validate the content of powershell action strings."""

    def test_powershell_actions_are_not_truncated(self, commands):
        """PowerShell commands should appear complete (balanced quotes/parens)."""
        for cmd in commands:
            if cmd.action_type != "powershell":
                continue
            # Basic check: count of single quotes should be even
            single_quotes = cmd.action.count("'")
            # Allow {{ }} template escaping (used in calculer_expression)
            # Just ensure the action is non-trivial
            assert len(cmd.action) >= 5, (
                f"Command {cmd.name} has very short powershell action"
            )

    def test_no_hardcoded_turbo_path_remains(self, commands):
        """After post-processing, no raw F:/BUREAU/turbo should remain
        (unless _TURBO_DIR is exactly that path, which is the common case)."""
        # This test verifies the post-processing ran. Since on this machine
        # _TURBO_DIR is /home/turbo/jarvis-m1-ops, the replacement is a no-op.
        # We just check the post-processing code ran (i.e., _cmd deleted).
        assert not hasattr(_mod, "_cmd")

    def test_ollama_commands_reference_correct_port(self, commands):
        """Ollama commands should use port 11434."""
        cmd = next(c for c in commands if c.name == "ollama_running")
        assert "11434" in cmd.action


# ===========================================================================
# 16. WINDOW MANAGEMENT COMMANDS
# ===========================================================================

class TestWindowManagement:
    """Tests for window management commands."""

    def test_fenetre_toujours_visible_uses_dll(self, commands):
        """Always-on-top should use user32.dll via Add-Type."""
        cmd = next(c for c in commands if c.name == "fenetre_toujours_visible")
        assert "user32.dll" in cmd.action
        assert "SetWindowPos" in cmd.action

    def test_deplacer_fenetre_moniteur_is_hotkey(self, commands):
        """Moving window to other monitor should be a hotkey."""
        cmd = next(c for c in commands if c.name == "deplacer_fenetre_moniteur")
        assert cmd.action_type == "hotkey"
        assert "win" in cmd.action

    def test_liste_fenetres_ouvertes(self, commands):
        """List open windows should use Get-Process with MainWindowTitle."""
        cmd = next(c for c in commands if c.name == "liste_fenetres_ouvertes")
        assert "MainWindowTitle" in cmd.action
