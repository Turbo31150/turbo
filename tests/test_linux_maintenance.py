from __future__ import annotations


def test_module_has_commands():
    from src.linux_maintenance import LINUX_MAINTENANCE_COMMANDS
    assert len(LINUX_MAINTENANCE_COMMANDS) >= 10


def test_commands_are_bash():
    from src.linux_maintenance import LINUX_MAINTENANCE_COMMANDS
    for name, cmd in LINUX_MAINTENANCE_COMMANDS.items():
        assert "Get-" not in cmd["command"], f"{name} contient du PowerShell!"
        assert "Set-" not in cmd["command"], f"{name} contient du PowerShell!"
        assert "powershell" not in cmd["command"].lower(), f"{name} utilise powershell!"


def test_all_have_required_fields():
    from src.linux_maintenance import LINUX_MAINTENANCE_COMMANDS
    for name, cmd in LINUX_MAINTENANCE_COMMANDS.items():
        assert "command" in cmd, f"{name} manque command"
        assert "description" in cmd, f"{name} manque description"
        assert "category" in cmd, f"{name} manque category"
