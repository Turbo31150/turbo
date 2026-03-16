from __future__ import annotations

"""Tests Linux pour les modules systeme — remplace les 21 tests Windows casses.

Chaque module est teste avec des mocks subprocess.run pour eviter
d'executer de vraies commandes systeme.
"""

import json
import os
import subprocess
from unittest.mock import MagicMock, mock_open, patch

import pytest

# ════════════════════════════════════════════════════════════════════════
# 1. LinuxJournalReader
# ════════════════════════════════════════════════════════════════════════

from src.linux_journal_reader import LinuxJournalReader


class TestLinuxJournalReader:
    """Tests pour linux_journal_reader.py"""

    def setup_method(self) -> None:
        self.reader = LinuxJournalReader()

    # -- get_recent (succes) --

    def test_get_recent_syslog_success(self) -> None:
        """Lecture du journal syslog avec des entrees valides."""
        journal_lines = "\n".join([
            json.dumps({
                "PRIORITY": "6",
                "MESSAGE": "Started service",
                "_PID": "1234",
                "SYSLOG_IDENTIFIER": "systemd",
                "__REALTIME_TIMESTAMP": "1700000000000000",
            }),
            json.dumps({
                "PRIORITY": "3",
                "MESSAGE": "Disk error detected",
                "_PID": "5678",
                "SYSLOG_IDENTIFIER": "kernel",
                "__REALTIME_TIMESTAMP": "1700000001000000",
            }),
        ])
        mock_result = MagicMock(returncode=0, stdout=journal_lines, stderr="")
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            entries = self.reader.get_recent("syslog", max_events=10)
            assert len(entries) == 2
            assert entries[0]["level"] == "Informational"
            assert entries[0]["provider"] == "systemd"
            assert entries[1]["level"] == "Error"
            # Verifie que journalctl est appele sans filtre pour syslog
            cmd = mock_run.call_args[0][0]
            assert "journalctl" in cmd
            assert "-u" not in cmd
            assert "-k" not in cmd

    def test_get_recent_kernel_filter(self) -> None:
        """Le filtre kernel utilise -k."""
        mock_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("subprocess.run", return_value=mock_result):
            self.reader.get_recent("kernel", max_events=5)

    def test_get_recent_auth_filter(self) -> None:
        """Le filtre auth utilise -t sshd/sudo/login/systemd-logind."""
        mock_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            self.reader.get_recent("auth", max_events=5)
            cmd = mock_run.call_args[0][0]
            assert "-t" in cmd

    def test_get_recent_unit_filter(self) -> None:
        """Un nom custom est traite comme unite systemd."""
        mock_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            self.reader.get_recent("nginx", max_events=5)
            cmd = mock_run.call_args[0][0]
            assert "-u" in cmd
            assert "nginx" in cmd

    # -- get_recent (erreurs) --

    def test_get_recent_journalctl_not_found(self) -> None:
        """Gestion de FileNotFoundError quand journalctl est absent."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            entries = self.reader.get_recent("syslog")
            assert entries == []

    def test_get_recent_nonzero_returncode(self) -> None:
        """Returncode non nul retourne une liste vide."""
        mock_result = MagicMock(returncode=1, stdout="", stderr="error")
        with patch("subprocess.run", return_value=mock_result):
            entries = self.reader.get_recent("syslog")
            assert entries == []

    def test_get_recent_invalid_json_lines(self) -> None:
        """Les lignes JSON invalides sont ignorees silencieusement."""
        stdout = "not-json\n" + json.dumps({
            "PRIORITY": "4", "MESSAGE": "warn", "_PID": "1",
            "SYSLOG_IDENTIFIER": "test", "__REALTIME_TIMESTAMP": "1700000000000000",
        })
        mock_result = MagicMock(returncode=0, stdout=stdout, stderr="")
        with patch("subprocess.run", return_value=mock_result):
            entries = self.reader.get_recent("syslog")
            assert len(entries) == 1
            assert entries[0]["level"] == "Warning"

    # -- get_errors_since --

    def test_get_errors_since_success(self) -> None:
        """Recuperation des erreurs depuis une periode donnee."""
        entry = json.dumps({
            "PRIORITY": "3", "MESSAGE": "critical failure",
            "SYSLOG_IDENTIFIER": "kernel",
        })
        mock_result = MagicMock(returncode=0, stdout=entry, stderr="")
        with patch("subprocess.run", return_value=mock_result):
            errors = self.reader.get_errors_since("1h ago")
            assert len(errors) == 1
            assert errors[0]["level"] == "Error"

    def test_get_errors_since_exception(self) -> None:
        """Exception dans get_errors_since retourne liste vide."""
        with patch("subprocess.run", side_effect=Exception("timeout")):
            errors = self.reader.get_errors_since("1h ago")
            assert errors == []

    # -- count_by_level / list_logs / search_events --

    def test_count_by_level(self) -> None:
        """Comptage par niveau de priorite."""
        entries = [
            json.dumps({"PRIORITY": "3", "MESSAGE": "err1", "_PID": "1",
                         "SYSLOG_IDENTIFIER": "a", "__REALTIME_TIMESTAMP": "1700000000000000"}),
            json.dumps({"PRIORITY": "3", "MESSAGE": "err2", "_PID": "2",
                         "SYSLOG_IDENTIFIER": "b", "__REALTIME_TIMESTAMP": "1700000000000000"}),
            json.dumps({"PRIORITY": "6", "MESSAGE": "info", "_PID": "3",
                         "SYSLOG_IDENTIFIER": "c", "__REALTIME_TIMESTAMP": "1700000000000000"}),
        ]
        mock_result = MagicMock(returncode=0, stdout="\n".join(entries), stderr="")
        with patch("subprocess.run", return_value=mock_result):
            counts = self.reader.count_by_level("syslog", 10)
            assert counts.get("Error", 0) == 2
            assert counts.get("Informational", 0) == 1

    def test_list_logs(self) -> None:
        """list_logs retourne les categories communes."""
        logs = self.reader.list_logs()
        assert "syslog" in logs
        assert "kernel" in logs
        assert "auth" in logs

    def test_search_events(self) -> None:
        """Recherche par mot-cle dans les messages."""
        entry = json.dumps({
            "PRIORITY": "6", "MESSAGE": "nginx started ok",
            "_PID": "100", "SYSLOG_IDENTIFIER": "nginx",
            "__REALTIME_TIMESTAMP": "1700000000000000",
        })
        mock_result = MagicMock(returncode=0, stdout=entry, stderr="")
        with patch("subprocess.run", return_value=mock_result):
            results = self.reader.search_events("syslog", "nginx")
            assert len(results) == 1

    # -- get_events / get_stats --

    def test_get_stats_initial(self) -> None:
        """Stats initiales a zero."""
        assert self.reader.get_stats() == {"total_events": 0}


# ════════════════════════════════════════════════════════════════════════
# 2. LinuxPackageManager
# ════════════════════════════════════════════════════════════════════════

from src.linux_package_manager import LinuxPackageManager


class TestLinuxPackageManager:
    """Tests pour linux_package_manager.py"""

    def setup_method(self) -> None:
        self.mgr = LinuxPackageManager()

    # -- list_features (succes) --

    def test_list_features_apt_only(self) -> None:
        """Liste des paquets apt installes."""
        dpkg_output = "vim\tinstall ok installed\nnano\tdeinstall ok config-files\n"
        mock_dpkg = MagicMock(returncode=0, stdout=dpkg_output, stderr="")
        mock_empty = MagicMock(returncode=1, stdout="", stderr="")

        def side_effect(cmd, **kwargs):
            if cmd[0] == "dpkg-query":
                return mock_dpkg
            return mock_empty

        with patch("subprocess.run", side_effect=side_effect):
            features = self.mgr.list_features()
            # Au moins les 2 paquets apt
            apt_pkgs = [f for f in features if f["source"] == "apt"]
            assert len(apt_pkgs) == 2
            assert apt_pkgs[0]["name"] == "vim"
            assert apt_pkgs[0]["state"] == "Enabled"
            assert apt_pkgs[1]["state"] == "Disabled"

    def test_list_features_with_snap(self) -> None:
        """Liste incluant les paquets snap."""
        snap_output = "Name  Version  Rev   Tracking  Publisher  Notes\nfirefox  120.0  1234  latest    mozilla    -\n"
        mock_snap = MagicMock(returncode=0, stdout=snap_output, stderr="")
        mock_empty = MagicMock(returncode=1, stdout="", stderr="")

        def side_effect(cmd, **kwargs):
            if cmd[0] == "snap":
                return mock_snap
            return mock_empty

        with patch("subprocess.run", side_effect=side_effect):
            features = self.mgr.list_features()
            snap_pkgs = [f for f in features if f["source"] == "snap"]
            assert len(snap_pkgs) == 1
            assert snap_pkgs[0]["name"] == "firefox"

    def test_list_features_with_flatpak(self) -> None:
        """Liste incluant les paquets flatpak."""
        flatpak_output = "org.gimp.GIMP\norg.libreoffice.LibreOffice\n"
        mock_flatpak = MagicMock(returncode=0, stdout=flatpak_output, stderr="")
        mock_empty = MagicMock(returncode=1, stdout="", stderr="")

        def side_effect(cmd, **kwargs):
            if cmd[0] == "flatpak":
                return mock_flatpak
            return mock_empty

        with patch("subprocess.run", side_effect=side_effect):
            features = self.mgr.list_features()
            fp = [f for f in features if f["source"] == "flatpak"]
            assert len(fp) == 2

    # -- list_features (erreurs) --

    def test_list_features_all_backends_missing(self) -> None:
        """Tous les backends absents retournent une liste vide."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            features = self.mgr.list_features()
            assert features == []

    # -- search --

    def test_search_packages(self) -> None:
        """Recherche de paquets par nom."""
        dpkg_output = "python3\tinstall ok installed\npython3-pip\tinstall ok installed\nvim\tinstall ok installed\n"
        mock_dpkg = MagicMock(returncode=0, stdout=dpkg_output, stderr="")
        mock_empty = MagicMock(returncode=1, stdout="", stderr="")

        def side_effect(cmd, **kwargs):
            if cmd[0] == "dpkg-query":
                return mock_dpkg
            return mock_empty

        with patch("subprocess.run", side_effect=side_effect):
            results = self.mgr.search("python")
            assert len(results) == 2
            assert all("python" in r["name"] for r in results)

    # -- is_enabled --

    def test_is_enabled_true(self) -> None:
        """Paquet installe retourne True."""
        dpkg_output = "vim\tinstall ok installed\n"
        mock_dpkg = MagicMock(returncode=0, stdout=dpkg_output, stderr="")
        mock_empty = MagicMock(returncode=1, stdout="", stderr="")

        def side_effect(cmd, **kwargs):
            if cmd[0] == "dpkg-query":
                return mock_dpkg
            return mock_empty

        with patch("subprocess.run", side_effect=side_effect):
            assert self.mgr.is_enabled("vim") is True

    def test_is_enabled_false(self) -> None:
        """Paquet absent retourne False."""
        mock_empty = MagicMock(returncode=1, stdout="", stderr="")
        with patch("subprocess.run", return_value=mock_empty):
            assert self.mgr.is_enabled("nonexistent") is False

    # -- count_by_source --

    def test_count_by_source(self) -> None:
        """Comptage par source (apt/snap/flatpak)."""
        dpkg_out = "pkg1\tinstall ok installed\n"
        snap_out = "Name  Version\nsnap1  1.0\n"
        flatpak_out = "org.app.One\n"

        def side_effect(cmd, **kwargs):
            if cmd[0] == "dpkg-query":
                return MagicMock(returncode=0, stdout=dpkg_out, stderr="")
            if cmd[0] == "snap":
                return MagicMock(returncode=0, stdout=snap_out, stderr="")
            if cmd[0] == "flatpak":
                return MagicMock(returncode=0, stdout=flatpak_out, stderr="")
            return MagicMock(returncode=1, stdout="", stderr="")

        with patch("subprocess.run", side_effect=side_effect):
            counts = self.mgr.count_by_source()
            assert counts["apt"] == 1
            assert counts["snap"] == 1
            assert counts["flatpak"] == 1


# ════════════════════════════════════════════════════════════════════════
# 3. LinuxUpdateManager
# ════════════════════════════════════════════════════════════════════════

from src.linux_update_manager import LinuxUpdateManager


class TestLinuxUpdateManager:
    """Tests pour linux_update_manager.py"""

    def setup_method(self) -> None:
        self.mgr = LinuxUpdateManager()

    # -- get_update_history (succes) --

    def test_get_update_history_success(self) -> None:
        """Lecture de l'historique dpkg.log."""
        log_content = (
            "2025-01-15 10:30:45 upgrade libssl3:amd64 3.0.2-0ubuntu1.12 3.0.2-0ubuntu1.13\n"
            "2025-01-14 08:00:00 install python3-dev:amd64 <none> 3.10.12-1\n"
            "2025-01-14 07:00:00 status installed python3:amd64 3.10.12-1\n"
        )
        m = mock_open(read_data=log_content)
        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", m):
            updates = self.mgr.get_update_history(limit=10)
            # Seules les lignes install/upgrade sont comptees (ordre inverse)
            assert len(updates) == 2
            assert "install" in updates[0]["title"]
            assert updates[0]["source"] == "apt"

    def test_get_update_history_no_log(self) -> None:
        """Pas de dpkg.log retourne liste vide."""
        with patch("os.path.exists", return_value=False):
            updates = self.mgr.get_update_history()
            assert updates == []

    # -- get_pending_updates --

    def test_get_pending_updates_apt(self) -> None:
        """Mises a jour apt en attente."""
        apt_output = (
            "Listing...\n"
            "libssl3/jammy-updates 3.0.2-0ubuntu1.14 amd64 [upgradable from: 3.0.2-0ubuntu1.13]\n"
            "curl/jammy-updates 7.81.0-1ubuntu1.16 amd64 [upgradable from: 7.81.0-1ubuntu1.15]\n"
        )

        def side_effect(cmd, **kwargs):
            if cmd[0] == "apt":
                return MagicMock(returncode=0, stdout=apt_output, stderr="")
            return MagicMock(returncode=1, stdout="", stderr="")

        with patch("subprocess.run", side_effect=side_effect):
            pending = self.mgr.get_pending_updates()
            apt_pending = [p for p in pending if p["source"] == "apt"]
            assert len(apt_pending) == 2
            assert apt_pending[0]["title"] == "libssl3"

    def test_get_pending_updates_snap(self) -> None:
        """Mises a jour snap en attente."""
        snap_output = "Name  Version  Rev  Size  Publisher  Notes\nfirefox  121.0  4321  200M  mozilla  -\n"

        def side_effect(cmd, **kwargs):
            if cmd[0] == "snap":
                return MagicMock(returncode=0, stdout=snap_output, stderr="")
            if cmd[0] == "apt":
                return MagicMock(returncode=0, stdout="Listing...\n", stderr="")
            return MagicMock(returncode=1, stdout="", stderr="")

        with patch("subprocess.run", side_effect=side_effect):
            pending = self.mgr.get_pending_updates()
            snap_pending = [p for p in pending if p["source"] == "snap"]
            assert len(snap_pending) == 1

    # -- get_pending_updates (erreurs) --

    def test_get_pending_updates_all_fail(self) -> None:
        """Tous les backends echouent retournent liste vide."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            pending = self.mgr.get_pending_updates()
            assert pending == []

    # -- get_unattended_status --

    def test_get_unattended_status_enabled(self) -> None:
        """unattended-upgrades installe et active."""
        def side_effect(cmd, **kwargs):
            if "dpkg-query" in cmd[0]:
                return MagicMock(returncode=0, stdout="install ok installed", stderr="")
            if "apt-config" in cmd[0]:
                return MagicMock(returncode=0, stdout='APT::Periodic::Unattended-Upgrade "1";\n', stderr="")
            return MagicMock(returncode=1, stdout="", stderr="")

        with patch("subprocess.run", side_effect=side_effect):
            status = self.mgr.get_unattended_status()
            assert status["installed"] is True
            assert status["enabled"] is True

    def test_get_unattended_status_not_installed(self) -> None:
        """unattended-upgrades non installe."""
        mock_result = MagicMock(returncode=1, stdout="", stderr="")
        with patch("subprocess.run", return_value=mock_result):
            status = self.mgr.get_unattended_status()
            assert status["installed"] is False

    # -- search_history --

    def test_search_history(self) -> None:
        """Recherche dans l'historique des mises a jour."""
        log_content = (
            "2025-01-15 10:00:00 upgrade libssl3:amd64 1.0 2.0\n"
            "2025-01-15 10:01:00 install curl:amd64 <none> 7.0\n"
        )
        m = mock_open(read_data=log_content)
        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", m):
            results = self.mgr.search_history("curl")
            assert len(results) == 1


# ════════════════════════════════════════════════════════════════════════
# 4. LinuxSecurityStatus
# ════════════════════════════════════════════════════════════════════════

from src.linux_security_status import LinuxSecurityStatus


class TestLinuxSecurityStatus:
    """Tests pour linux_security_status.py"""

    def setup_method(self) -> None:
        self.sec = LinuxSecurityStatus()

    # -- get_status (succes) --

    def test_get_status_ufw_active(self) -> None:
        """UFW actif est detecte."""
        def side_effect(cmd, **kwargs):
            if cmd[0] == "ufw":
                return MagicMock(returncode=0, stdout="Status: active\nDefault: deny (incoming)", stderr="")
            # Autres commandes retournent pas installe
            raise FileNotFoundError

        with patch("subprocess.run", side_effect=side_effect), \
             patch("os.path.exists", return_value=False):
            status = self.sec.get_status()
            assert status["firewall_active"] is True
            assert status["firewall_backend"] == "ufw"

    def test_get_status_iptables_fallback(self) -> None:
        """Fallback iptables quand ufw absent."""
        call_count = 0

        def side_effect(cmd, **kwargs):
            nonlocal call_count
            if cmd[0] == "ufw":
                raise FileNotFoundError
            if cmd[0] == "iptables":
                # Simuler beaucoup de regles (> 6 lignes)
                lines = "\n".join([f"rule{i}" for i in range(10)])
                return MagicMock(returncode=0, stdout=lines, stderr="")
            raise FileNotFoundError

        with patch("subprocess.run", side_effect=side_effect), \
             patch("os.path.exists", return_value=False):
            status = self.sec.get_status()
            assert status["firewall_active"] is True
            assert status["firewall_backend"] == "iptables"

    # -- get_status (erreurs) --

    def test_get_status_no_firewall(self) -> None:
        """Aucun firewall disponible."""
        with patch("subprocess.run", side_effect=FileNotFoundError), \
             patch("os.path.exists", return_value=False):
            status = self.sec.get_status()
            assert status["firewall_active"] is False

    # -- fail2ban --

    def test_fail2ban_active(self) -> None:
        """Fail2ban actif avec jails."""
        def side_effect(cmd, **kwargs):
            if cmd[0] == "fail2ban-client":
                return MagicMock(returncode=0, stdout="Status\n|- Number of jail:\t3\n", stderr="")
            raise FileNotFoundError

        with patch("subprocess.run", side_effect=side_effect), \
             patch("os.path.exists", return_value=False):
            status = self.sec._get_fail2ban_status()
            assert status["fail2ban_active"] is True
            assert status["fail2ban_jails"] == 3

    def test_fail2ban_not_installed(self) -> None:
        """Fail2ban absent."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            status = self.sec._get_fail2ban_status()
            assert status["fail2ban_active"] is False

    # -- clamav --

    def test_clamav_installed_daemon_running(self) -> None:
        """ClamAV installe avec daemon actif."""
        def side_effect(cmd, **kwargs):
            if cmd[0] == "clamscan":
                return MagicMock(returncode=0, stdout="ClamAV 1.0.0/27000", stderr="")
            if cmd[0] == "systemctl":
                return MagicMock(returncode=0, stdout="active", stderr="")
            raise FileNotFoundError

        with patch("subprocess.run", side_effect=side_effect):
            status = self.sec._get_clamav_status()
            assert status["clamav_installed"] is True
            assert status["clamav_daemon_running"] is True

    # -- is_protected --

    def test_is_protected_true(self) -> None:
        """Systeme protege avec firewall + fail2ban."""
        def side_effect(cmd, **kwargs):
            if cmd[0] == "ufw":
                return MagicMock(returncode=0, stdout="Status: active", stderr="")
            if cmd[0] == "fail2ban-client":
                return MagicMock(returncode=0, stdout="Status\n|- Number of jail:\t1", stderr="")
            raise FileNotFoundError

        with patch("subprocess.run", side_effect=side_effect), \
             patch("os.path.exists", return_value=False):
            assert self.sec.is_protected() is True

    def test_is_protected_false(self) -> None:
        """Systeme non protege."""
        with patch("subprocess.run", side_effect=FileNotFoundError), \
             patch("os.path.exists", return_value=False):
            assert self.sec.is_protected() is False

    # -- get_threat_history --

    def test_get_threat_history(self) -> None:
        """Lecture des menaces ClamAV."""
        log = "2025-01-15 /tmp/eicar: Eicar-Signature FOUND\nScan summary\n"
        m = mock_open(read_data=log)
        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", m):
            threats = self.sec.get_threat_history()
            assert len(threats) == 1
            assert "FOUND" in threats[0]["detail"]

    def test_get_threat_history_no_log(self) -> None:
        """Pas de fichier log ClamAV."""
        with patch("os.path.exists", return_value=False):
            threats = self.sec.get_threat_history()
            assert threats == []


# ════════════════════════════════════════════════════════════════════════
# 5. LinuxPowerManager
# ════════════════════════════════════════════════════════════════════════

from src.linux_power_manager import LinuxPowerManager


class TestLinuxPowerManager:
    """Tests pour linux_power_manager.py"""

    def setup_method(self) -> None:
        self.mgr = LinuxPowerManager()

    # -- list_plans (succes) --

    def test_list_plans_powerprofiles(self) -> None:
        """Liste via powerprofilesctl."""
        list_output = "  performance:\n* balanced:\n  power-saver:\n"
        get_output = "balanced"

        def side_effect(cmd, **kwargs):
            if cmd[1] == "list":
                return MagicMock(returncode=0, stdout=list_output, stderr="")
            if cmd[1] == "get":
                return MagicMock(returncode=0, stdout=get_output, stderr="")
            return MagicMock(returncode=1, stdout="", stderr="")

        with patch("subprocess.run", side_effect=side_effect):
            plans = self.mgr.list_plans()
            assert len(plans) == 3
            active = [p for p in plans if p["is_active"]]
            assert len(active) >= 1

    def test_list_plans_powerprofiles_not_found(self) -> None:
        """Fallback CPU governors quand powerprofilesctl absent."""
        gov_content = "performance schedutil powersave"
        current_content = "schedutil"

        with patch("subprocess.run", side_effect=FileNotFoundError), \
             patch("os.path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data=gov_content)) as m:
            # On doit gerer 2 fichiers differents
            handles = [
                mock_open(read_data=gov_content).return_value,
                mock_open(read_data=current_content).return_value,
            ]
            m.side_effect = handles
            plans = self.mgr._list_cpu_governors()
            assert len(plans) == 3

    # -- get_battery_status --

    def test_get_battery_no_battery(self) -> None:
        """Pas de batterie (desktop)."""
        with patch("glob.glob", return_value=[]):
            status = self.mgr.get_battery_status()
            assert status["has_battery"] is False
            assert status["charge_percent"] == 100

    def test_get_battery_with_battery(self) -> None:
        """Batterie presente."""
        with patch("glob.glob", return_value=["/sys/class/power_supply/BAT0"]), \
             patch.object(self.mgr, "_read_sysfs", side_effect=["85", "Charging", "Li-Ion"]):
            status = self.mgr.get_battery_status()
            assert status["has_battery"] is True
            assert status["charge_percent"] == 85
            assert status["status"] == "Charging"

    # -- get_cpu_frequency --

    def test_get_cpu_frequency_cpupower(self) -> None:
        """Frequence CPU via cpupower."""
        mock_result = MagicMock(returncode=0, stdout="current CPU frequency is 3.50 GHz", stderr="")
        with patch("subprocess.run", return_value=mock_result):
            info = self.mgr.get_cpu_frequency()
            assert "detail" in info

    def test_get_cpu_frequency_fallback_procinfo(self) -> None:
        """Fallback /proc/cpuinfo quand cpupower absent."""
        cpuinfo = "cpu MHz\t\t: 3500.123\ncpu MHz\t\t: 3600.456\n"
        with patch("subprocess.run", side_effect=FileNotFoundError), \
             patch("builtins.open", mock_open(read_data=cpuinfo)):
            info = self.mgr.get_cpu_frequency()
            assert info["cores"] == 2
            assert info["min_mhz"] == 3500.1

    # -- get_tlp_status --

    def test_get_tlp_not_installed(self) -> None:
        """TLP non installe."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            status = self.mgr.get_tlp_status()
            assert status["installed"] is False

    # -- suspend / hibernate --

    def test_suspend_success(self) -> None:
        """Mise en veille reussie."""
        mock_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("subprocess.run", return_value=mock_result):
            assert self.mgr.suspend() is True

    def test_suspend_failure(self) -> None:
        """Mise en veille echouee."""
        with patch("subprocess.run", side_effect=Exception("permission denied")):
            assert self.mgr.suspend() is False


# ════════════════════════════════════════════════════════════════════════
# 6. LinuxConfigManager
# ════════════════════════════════════════════════════════════════════════

from src.linux_config_manager import LinuxConfigManager


class TestLinuxConfigManager:
    """Tests pour linux_config_manager.py"""

    def setup_method(self) -> None:
        self.mgr = LinuxConfigManager()

    # -- read_value gsettings (succes) --

    def test_read_gsetting_success(self) -> None:
        """Lecture d'une valeur gsettings."""
        mock_result = MagicMock(returncode=0, stdout="'Adwaita-dark'\n", stderr="")
        with patch("subprocess.run", return_value=mock_result):
            result = self.mgr.read_value("GSETTINGS", "org.gnome.desktop.interface", "gtk-theme")
            assert result["value"] == "Adwaita-dark"

    def test_read_gsetting_not_found(self) -> None:
        """Cle gsettings introuvable."""
        mock_result = MagicMock(returncode=1, stdout="", stderr="No such schema")
        with patch("subprocess.run", return_value=mock_result):
            result = self.mgr.read_value("GSETTINGS", "bad.schema", "key")
            assert "error" in result

    def test_read_gsettings_binary_missing(self) -> None:
        """gsettings non installe."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = self.mgr.read_value("GSETTINGS", "org.gnome.desktop.interface", "gtk-theme")
            assert "error" in result

    # -- read_value dconf --

    def test_read_dconf_success(self) -> None:
        """Lecture dconf."""
        mock_result = MagicMock(returncode=0, stdout="true\n", stderr="")
        with patch("subprocess.run", return_value=mock_result):
            result = self.mgr.read_value("DCONF", "/org/gnome/shell", "enabled")
            assert result["value"] == "true"

    def test_read_dconf_empty(self) -> None:
        """Cle dconf vide retourne erreur."""
        mock_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("subprocess.run", return_value=mock_result):
            result = self.mgr.read_value("DCONF", "/org/gnome/shell", "missing")
            assert "error" in result

    # -- read_value ETC (fichier) --

    def test_read_file_key_value(self) -> None:
        """Lecture d'une cle dans un fichier config."""
        content = "# comment\nHOSTNAME=jarvis-m1\nDOMAIN=local\n"
        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data=content)):
            result = self.mgr.read_value("ETC", "/etc/hostname.conf", "HOSTNAME")
            assert result["value"] == "jarvis-m1"

    def test_read_file_not_found(self) -> None:
        """Fichier config absent."""
        with patch("os.path.exists", return_value=False):
            result = self.mgr.read_value("ETC", "/etc/nonexistent", "key")
            assert "error" in result

    # -- read_value SYSTEMD --

    def test_read_systemd_property(self) -> None:
        """Lecture propriete systemd."""
        mock_result = MagicMock(returncode=0, stdout="ActiveState=active\n", stderr="")
        with patch("subprocess.run", return_value=mock_result):
            result = self.mgr.read_value("SYSTEMD", "ssh.service", "ActiveState")
            assert result["value"] == "active"

    # -- read_value backend inconnu --

    def test_read_unknown_backend(self) -> None:
        """Backend inconnu retourne erreur."""
        result = self.mgr.read_value("WINDOWS_REGISTRY", "HKLM", "key")
        assert "error" in result

    # -- write_value --

    def test_write_gsetting_success(self) -> None:
        """Ecriture gsettings reussie."""
        mock_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("subprocess.run", return_value=mock_result):
            assert self.mgr.write_value("GSETTINGS", "org.gnome.desktop.interface", "gtk-theme", "Yaru") is True

    def test_write_gsetting_failure(self) -> None:
        """Ecriture gsettings echouee."""
        mock_result = MagicMock(returncode=1, stdout="", stderr="schema not found")
        with patch("subprocess.run", return_value=mock_result):
            assert self.mgr.write_value("GSETTINGS", "bad.schema", "key", "val") is False

    # -- favorites --

    def test_add_and_list_favorites(self) -> None:
        """Ajout et listing de favoris."""
        self.mgr.add_favorite("theme", "GSETTINGS", "org.gnome.desktop.interface", "Theme config")
        favs = self.mgr.list_favorites()
        assert len(favs) == 1
        assert favs[0]["name"] == "theme"

    def test_remove_favorite(self) -> None:
        """Suppression de favori."""
        self.mgr.add_favorite("test", "ETC", "/etc/test")
        assert self.mgr.remove_favorite("test") is True
        assert self.mgr.remove_favorite("nonexistent") is False

    # -- get_stats --

    def test_get_stats(self) -> None:
        """Stats incluent les favoris et backends supportes."""
        stats = self.mgr.get_stats()
        assert "total_events" in stats
        assert "supported_hives" in stats


# ════════════════════════════════════════════════════════════════════════
# 7. LinuxSwapManager
# ════════════════════════════════════════════════════════════════════════

from src.linux_swap_manager import LinuxSwapManager


class TestLinuxSwapManager:
    """Tests pour linux_swap_manager.py"""

    def setup_method(self) -> None:
        self.mgr = LinuxSwapManager()

    # -- get_usage (succes) --

    def test_get_usage_success(self) -> None:
        """Lecture de /proc/swaps."""
        proc_swaps = (
            "Filename\t\t\t\tType\t\tSize\t\tUsed\t\tPriority\n"
            "/dev/zram0                              partition\t6291456\t\t1048576\t\t100\n"
        )
        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data=proc_swaps)):
            usage = self.mgr.get_usage()
            assert len(usage) == 1
            assert usage[0]["name"] == "/dev/zram0"
            assert usage[0]["allocated_mb"] == round(6291456 / 1024)
            assert usage[0]["current_usage_mb"] == round(1048576 / 1024)

    def test_get_usage_no_swap(self) -> None:
        """Pas de swap configure."""
        proc_swaps = "Filename\t\t\t\tType\t\tSize\t\tUsed\t\tPriority\n"
        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data=proc_swaps)):
            usage = self.mgr.get_usage()
            assert usage == []

    # -- get_usage (erreur) --

    def test_get_usage_no_proc_swaps(self) -> None:
        """Fichier /proc/swaps absent."""
        with patch("os.path.exists", return_value=False):
            usage = self.mgr.get_usage()
            assert usage == []

    # -- get_virtual_memory (succes) --

    def test_get_virtual_memory_success(self) -> None:
        """Lecture /proc/meminfo."""
        meminfo = (
            "MemTotal:       32000000 kB\n"
            "MemFree:        16000000 kB\n"
            "SwapTotal:       6000000 kB\n"
            "SwapFree:        5000000 kB\n"
            "Cached:          8000000 kB\n"
            "Buffers:         1000000 kB\n"
        )
        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data=meminfo)):
            vm = self.mgr.get_virtual_memory()
            assert vm["total_physical_kb"] == 32000000
            assert vm["swap_total_kb"] == 6000000
            assert vm["total_virtual_kb"] == 38000000

    def test_get_virtual_memory_no_meminfo(self) -> None:
        """Pas de /proc/meminfo."""
        with patch("os.path.exists", return_value=False):
            vm = self.mgr.get_virtual_memory()
            assert vm == {}

    # -- get_settings --

    def test_get_settings_fstab(self) -> None:
        """Lecture des entrees swap dans fstab."""
        fstab = (
            "# /etc/fstab\n"
            "UUID=xxx / ext4 defaults 0 1\n"
            "/swapfile none swap sw 0 0\n"
        )
        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data=fstab)), \
             patch("subprocess.run", side_effect=FileNotFoundError):
            settings = self.mgr.get_settings()
            swap_entries = [s for s in settings if s["source"] == "fstab"]
            assert len(swap_entries) == 1
            assert swap_entries[0]["name"] == "/swapfile"

    # -- get_swappiness --

    def test_get_swappiness(self) -> None:
        """Lecture de vm.swappiness."""
        with patch("builtins.open", mock_open(read_data="60\n")):
            assert self.mgr.get_swappiness() == 60

    def test_get_swappiness_error(self) -> None:
        """Erreur lecture swappiness retourne -1."""
        with patch("builtins.open", side_effect=FileNotFoundError):
            assert self.mgr.get_swappiness() == -1

    # -- zram --

    def test_get_zram_info(self) -> None:
        """Detection des devices ZRAM."""
        zram_output = "/dev/zram0 lzo-rle 6G 128M 256M  4 [SWAP]\n"
        mock_result = MagicMock(returncode=0, stdout=zram_output, stderr="")
        with patch("subprocess.run", return_value=mock_result):
            zram = self.mgr._get_zram_info()
            assert len(zram) == 1
            assert zram[0]["source"] == "zram"


# ════════════════════════════════════════════════════════════════════════
# 8. LinuxTrashManager
# ════════════════════════════════════════════════════════════════════════

from src.linux_trash_manager import LinuxTrashManager


class TestLinuxTrashManager:
    """Tests pour linux_trash_manager.py"""

    def setup_method(self) -> None:
        self.mgr = LinuxTrashManager()

    # -- get_info (succes) --

    def test_get_info_via_gio(self) -> None:
        """Info corbeille via gio."""
        gio_output = "file:///home/user/.local/share/Trash/files/test.txt\n"
        mock_result = MagicMock(returncode=0, stdout=gio_output, stderr="")
        with patch("subprocess.run", return_value=mock_result), \
             patch.object(self.mgr, "_calc_trash_size", return_value=1.5):
            info = self.mgr.get_info()
            assert info["item_count"] == 1
            assert info["size_mb"] == 1.5

    def test_get_info_gio_empty(self) -> None:
        """Corbeille vide via gio."""
        mock_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("subprocess.run", return_value=mock_result), \
             patch.object(self.mgr, "_calc_trash_size", return_value=0.0):
            info = self.mgr.get_info()
            assert info["item_count"] == 0

    def test_get_info_fallback_direct(self) -> None:
        """Fallback lecture directe du repertoire."""
        with patch("subprocess.run", side_effect=FileNotFoundError), \
             patch("os.path.isdir", return_value=True), \
             patch("os.listdir", return_value=["file1.txt", "file2.txt"]), \
             patch.object(self.mgr, "_calc_trash_size", return_value=3.0):
            info = self.mgr.get_info()
            assert info["item_count"] == 2

    # -- get_info (erreur) --

    def test_get_info_no_trash_dir(self) -> None:
        """Pas de repertoire Trash."""
        with patch("subprocess.run", side_effect=FileNotFoundError), \
             patch("os.path.isdir", return_value=False):
            info = self.mgr.get_info()
            assert info["item_count"] == 0
            assert info["size_mb"] == 0.0

    # -- list_items --

    def test_list_items_success(self) -> None:
        """Listing des elements de la corbeille."""
        trashinfo = "[Trash Info]\nPath=/home/user/Documents/old.txt\nDeletionDate=2025-01-15T10:00:00\n"
        with patch("os.path.isdir", return_value=True), \
             patch("os.listdir", return_value=["old.txt.trashinfo"]), \
             patch("builtins.open", mock_open(read_data=trashinfo)):
            items = self.mgr.list_items()
            assert len(items) == 1
            assert items[0]["name"] == "old.txt"
            assert "2025" in items[0]["deletion_date"]

    def test_list_items_empty(self) -> None:
        """Corbeille vide."""
        with patch("os.path.isdir", return_value=False):
            items = self.mgr.list_items()
            assert items == []

    # -- is_empty --

    def test_is_empty_true(self) -> None:
        """Corbeille vide."""
        with patch.object(self.mgr, "get_info", return_value={"item_count": 0, "size_mb": 0}):
            assert self.mgr.is_empty() is True

    def test_is_empty_false(self) -> None:
        """Corbeille non vide."""
        with patch.object(self.mgr, "get_info", return_value={"item_count": 5, "size_mb": 10}):
            assert self.mgr.is_empty() is False

    # -- empty_trash --

    def test_empty_trash_gio_success(self) -> None:
        """Vidage via gio."""
        mock_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("subprocess.run", return_value=mock_result):
            assert self.mgr.empty_trash() is True

    def test_empty_trash_all_fail(self) -> None:
        """Aucun outil disponible pour vider."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert self.mgr.empty_trash() is False


# ════════════════════════════════════════════════════════════════════════
# 9. LinuxSnapshotManager
# ════════════════════════════════════════════════════════════════════════

from src.linux_snapshot_manager import LinuxSnapshotManager


class TestLinuxSnapshotManager:
    """Tests pour linux_snapshot_manager.py"""

    def setup_method(self) -> None:
        self.mgr = LinuxSnapshotManager()

    # -- list_shadow_copies (succes) --

    def test_list_lvm_snapshots(self) -> None:
        """Detection de snapshots LVM."""
        lvs_output = "  snap1|vg0|1.00g|swi-a-s--|50.00\n  root|vg0|20.00g|owi-a-s--|"
        mock_lvs = MagicMock(returncode=0, stdout=lvs_output, stderr="")

        def side_effect(cmd, **kwargs):
            if cmd[0] == "lvs":
                return mock_lvs
            raise FileNotFoundError

        with patch("subprocess.run", side_effect=side_effect):
            snaps = self.mgr._list_lvm_snapshots()
            assert len(snaps) == 1
            assert snaps[0]["name"] == "snap1"
            assert snaps[0]["type"] == "lvm"

    def test_list_btrfs_snapshots(self) -> None:
        """Detection de snapshots btrfs."""
        btrfs_output = "ID 256 gen 100 cgen 50 top level 5 otime 2025-01-15 path .snapshots/daily\n"

        def side_effect(cmd, **kwargs):
            if cmd[0] == "btrfs":
                return MagicMock(returncode=0, stdout=btrfs_output, stderr="")
            raise FileNotFoundError

        with patch("subprocess.run", side_effect=side_effect):
            snaps = self.mgr._list_btrfs_snapshots()
            assert len(snaps) == 1
            assert snaps[0]["type"] == "btrfs"

    def test_list_timeshift_snapshots(self) -> None:
        """Detection de snapshots Timeshift."""
        timeshift_output = (
            "Device : /dev/sda1\n"
            "Num   Name                 Tags  Description\n"
            "---\n"
            "0     2025-01-15_10-00-00  O     Scheduled\n"
            "1     2025-01-14_10-00-00  O     Scheduled\n"
        )

        def side_effect(cmd, **kwargs):
            if cmd[0] == "timeshift":
                return MagicMock(returncode=0, stdout=timeshift_output, stderr="")
            raise FileNotFoundError

        with patch("subprocess.run", side_effect=side_effect):
            snaps = self.mgr._list_timeshift_snapshots()
            assert len(snaps) == 2
            assert snaps[0]["type"] == "timeshift"

    # -- list_shadow_copies combine --

    def test_list_shadow_copies_all_empty(self) -> None:
        """Aucun snapshot disponible."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            snaps = self.mgr.list_shadow_copies()
            assert snaps == []

    # -- create_shadow_copy --

    def test_create_shadow_copy_timeshift(self) -> None:
        """Creation via Timeshift."""
        mock_result = MagicMock(returncode=0, stdout="Snapshot created", stderr="")
        with patch("subprocess.run", return_value=mock_result):
            assert self.mgr.create_shadow_copy() is True

    def test_create_shadow_copy_no_backend(self) -> None:
        """Aucun backend disponible."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert self.mgr.create_shadow_copy() is False


# ════════════════════════════════════════════════════════════════════════
# 10. LinuxWorkspaceManager
# ════════════════════════════════════════════════════════════════════════

from src.linux_workspace_manager import LinuxWorkspaceManager


class TestLinuxWorkspaceManager:
    """Tests pour linux_workspace_manager.py"""

    def setup_method(self) -> None:
        self.mgr = LinuxWorkspaceManager()

    # -- list_desktops / get_desktop_count (succes) --

    def test_list_desktops_wmctrl(self) -> None:
        """Listing des workspaces via wmctrl."""
        wmctrl_output = (
            "0  * DG: 1920x1080  VP: 0,0  WA: 0,28 1920x1052  Workspace 1\n"
            "1  - DG: 1920x1080  VP: N/A  WA: 0,28 1920x1052  Workspace 2\n"
        )
        mock_result = MagicMock(returncode=0, stdout=wmctrl_output, stderr="")
        with patch("subprocess.run", return_value=mock_result):
            desktops = self.mgr.list_desktops()
            assert len(desktops) == 2
            assert desktops[0]["is_current"] is True
            assert desktops[1]["is_current"] is False

    def test_get_desktop_count_wmctrl(self) -> None:
        """Nombre de workspaces via wmctrl."""
        wmctrl_output = "0  * DG: 1920x1080\n1  - DG: 1920x1080\n2  - DG: 1920x1080\n"
        mock_result = MagicMock(returncode=0, stdout=wmctrl_output, stderr="")
        with patch("subprocess.run", return_value=mock_result):
            count = self.mgr.get_desktop_count()
            assert count == 3

    def test_get_desktop_count_gsettings_fallback(self) -> None:
        """Fallback gsettings quand wmctrl absent."""
        call_idx = 0

        def side_effect(cmd, **kwargs):
            nonlocal call_idx
            call_idx += 1
            if cmd[0] == "wmctrl":
                raise FileNotFoundError
            if cmd[0] == "gsettings":
                return MagicMock(returncode=0, stdout="4\n", stderr="")
            return MagicMock(returncode=1, stdout="", stderr="")

        with patch("subprocess.run", side_effect=side_effect):
            count = self.mgr.get_desktop_count()
            assert count == 4

    # -- get_current_desktop --

    def test_get_current_desktop(self) -> None:
        """Workspace actif."""
        wmctrl_output = "0  - DG: 1920x1080  VP: N/A  WA: 0,28 1920x1052  Workspace 1\n1  * DG: 1920x1080  VP: 0,0  WA: 0,28 1920x1052  Workspace 2\n"
        mock_result = MagicMock(returncode=0, stdout=wmctrl_output, stderr="")
        with patch("subprocess.run", return_value=mock_result):
            current = self.mgr.get_current_desktop()
            assert current["index"] == 1
            assert current["is_current"] is True

    # -- list_desktops (erreur) --

    def test_list_desktops_no_tools(self) -> None:
        """Aucun outil disponible retourne un workspace par defaut."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            desktops = self.mgr.list_desktops()
            assert len(desktops) == 1
            assert desktops[0]["is_current"] is True

    # -- switch_desktop --

    def test_switch_desktop_wmctrl(self) -> None:
        """Changement de workspace via wmctrl."""
        mock_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("subprocess.run", return_value=mock_result):
            assert self.mgr.switch_desktop(2) is True

    def test_switch_desktop_no_tools(self) -> None:
        """Aucun outil pour changer de workspace."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert self.mgr.switch_desktop(1) is False

    # -- get_screen_info --

    def test_get_screen_info_xrandr(self) -> None:
        """Info ecran via xrandr."""
        xrandr_output = (
            "Screen 0: minimum 8 x 8, current 3840 x 1080\n"
            "DP-0 connected primary 1920x1080+0+0\n"
            "   1920x1080     60.00*+  59.94\n"
            "DP-2 connected 1920x1080+1920+0\n"
            "   1920x1080     60.00*+\n"
        )
        mock_result = MagicMock(returncode=0, stdout=xrandr_output, stderr="")
        with patch("subprocess.run", return_value=mock_result):
            info = self.mgr.get_screen_info()
            assert info["monitors"] == 2
            assert info["width"] == 1920
            assert info["height"] == 1080

    def test_get_screen_info_no_tools(self) -> None:
        """Aucun outil pour les infos ecran."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            info = self.mgr.get_screen_info()
            assert info["width"] == 0


# ════════════════════════════════════════════════════════════════════════
# 11. LinuxShareManager
# ════════════════════════════════════════════════════════════════════════

from src.linux_share_manager import LinuxShareManager


class TestLinuxShareManager:
    """Tests pour linux_share_manager.py"""

    def setup_method(self) -> None:
        self.mgr = LinuxShareManager()

    # -- list_shares (succes) --

    def test_list_samba_usershares(self) -> None:
        """Detection des partages Samba user."""
        net_list = "Documents\nPublic\n"
        net_info_docs = "path=/home/user/Documents\ncomment=My Documents\n"
        net_info_pub = "path=/home/user/Public\ncomment=Public folder\n"

        def side_effect(cmd, **kwargs):
            if cmd[:3] == ["net", "usershare", "list"]:
                return MagicMock(returncode=0, stdout=net_list, stderr="")
            if cmd[:3] == ["net", "usershare", "info"]:
                if cmd[3] == "Documents":
                    return MagicMock(returncode=0, stdout=net_info_docs, stderr="")
                return MagicMock(returncode=0, stdout=net_info_pub, stderr="")
            raise FileNotFoundError

        with patch("subprocess.run", side_effect=side_effect), \
             patch("os.path.exists", return_value=False):
            shares = self.mgr.list_shares()
            samba = [s for s in shares if s["type"] == "samba"]
            assert len(samba) == 2
            assert samba[0]["name"] == "Documents"
            assert samba[0]["path"] == "/home/user/Documents"

    def test_list_nfs_exports(self) -> None:
        """Detection des exports NFS."""
        exports = "/srv/nfs/data 192.168.1.0/24(rw,sync,no_subtree_check)\n"
        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data=exports)):
            nfs = self.mgr._list_nfs_exports()
            assert len(nfs) == 1
            assert nfs[0]["type"] == "nfs"
            assert nfs[0]["path"] == "/srv/nfs/data"

    def test_list_samba_smb_conf_fallback(self) -> None:
        """Fallback lecture smb.conf."""
        smb_conf = (
            "[global]\n"
            "workgroup = WORKGROUP\n"
            "[shared]\n"
            "path = /srv/samba/shared\n"
            "comment = Shared folder\n"
        )
        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data=smb_conf)):
            shares = self.mgr._parse_smb_conf()
            assert len(shares) == 1
            assert shares[0]["name"] == "shared"
            assert shares[0]["path"] == "/srv/samba/shared"

    # -- list_shares (erreur) --

    def test_list_shares_nothing_available(self) -> None:
        """Aucun partage disponible."""
        with patch("subprocess.run", side_effect=FileNotFoundError), \
             patch("os.path.exists", return_value=False):
            shares = self.mgr.list_shares()
            assert shares == []

    # -- list_mapped_drives --

    def test_list_mapped_drives_success(self) -> None:
        """Detection des montages reseau."""
        proc_mounts = (
            "sysfs /sys sysfs rw 0 0\n"
            "//server/share /mnt/nas cifs rw 0 0\n"
            "server:/data /mnt/nfs nfs4 rw 0 0\n"
            "user@host:/home /mnt/ssh fuse.sshfs rw 0 0\n"
        )
        with patch("builtins.open", mock_open(read_data=proc_mounts)):
            drives = self.mgr.list_mapped_drives()
            assert len(drives) == 3
            types = {d["type"] for d in drives}
            assert "cifs" in types
            assert "nfs4" in types
            assert "fuse.sshfs" in types

    def test_list_mapped_drives_no_network(self) -> None:
        """Pas de montages reseau."""
        proc_mounts = "sysfs /sys sysfs rw 0 0\n/dev/sda1 / ext4 rw 0 0\n"
        with patch("builtins.open", mock_open(read_data=proc_mounts)):
            drives = self.mgr.list_mapped_drives()
            assert drives == []

    # -- search_shares --

    def test_search_shares(self) -> None:
        """Recherche de partages par nom."""
        with patch.object(self.mgr, "list_shares", return_value=[
            {"name": "Documents", "path": "/docs", "type": "samba"},
            {"name": "Public", "path": "/pub", "type": "samba"},
        ]):
            results = self.mgr.search_shares("doc")
            assert len(results) == 1
            assert results[0]["name"] == "Documents"

    # -- get_stats --

    def test_get_stats(self) -> None:
        """Stats initiales."""
        stats = self.mgr.get_stats()
        assert stats["total_events"] == 0
