"""Process Singleton Manager — garantit 1 seul exemplaire par service.

Chaque service JARVIS est identifie par un nom unique. Avant de lancer
un service, on tue l'instance existante (PID file + kill-on-port).

Usage:
    from src.process_singleton import singleton

    # Before starting a service:
    singleton.acquire("jarvis_ws", port=9742)  # kills existing, registers PID

    # When starting a subprocess:
    proc = subprocess.Popen(...)
    singleton.register("dashboard", proc.pid)

    # On clean shutdown:
    singleton.release("jarvis_ws")

    # List all:
    singleton.list_all()  -> {"jarvis_ws": {"pid": 1234, "alive": True}, ...}
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.singleton")

PID_DIR = Path("/home/turbo/jarvis-m1-ops/data/pids")


class ProcessSingleton:
    """Ensures only one instance of a named service runs at a time."""

    def __init__(self, pid_dir: Path | str = PID_DIR) -> None:
        self._pid_dir = Path(pid_dir)

    # ── PID file helpers ──────────────────────────────────────────────

    def _pid_file(self, service: str) -> Path:
        return self._pid_dir / f"{service}.pid"

    def is_running(self, service: str) -> tuple[bool, int | None]:
        """Check if service is already running. Returns (alive, pid)."""
        pf = self._pid_file(service)
        if not pf.exists():
            return False, None
        try:
            pid = int(pf.read_text().strip())
            if self._is_pid_alive(pid):
                return True, pid
            pf.unlink(missing_ok=True)
            return False, None
        except (ValueError, OSError):
            pf.unlink(missing_ok=True)
            return False, None

    @staticmethod
    def _is_pid_alive(pid: int) -> bool:
        """Check if a PID is alive — Windows-compatible (no signal 0)."""
        if os.name == "nt":
            try:
                output = os.popen(f'tasklist /FI "PID eq {pid}" /FO CSV /NH 2>NUL').read()
                return f'"{pid}"' in output
            except Exception:
                return False
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except (PermissionError, OSError):
            return True  # alive but no permissions

    # ── Kill existing ─────────────────────────────────────────────────

    def kill_existing(self, service: str) -> bool:
        """Kill existing instance by PID file. Returns True if killed."""
        alive, pid = self.is_running(service)
        if not alive or pid is None:
            return False
        # Never kill our own process or parent (uvicorn spawn pattern:
        # boot registers parent PID, child startup calls acquire → would self-kill)
        if pid == os.getpid() or pid == os.getppid():
            logger.info("Skipping kill of %s (PID %d) — it's us or our parent", service, pid)
            return False
        return self._kill_pid(pid, service)

    def _kill_pid(self, pid: int, label: str = "") -> bool:
        """Kill a single PID. Uses taskkill /T on Windows for process tree."""
        try:
            if os.name == "nt":
                r = subprocess.run(
                    ["taskkill", "/PID", str(pid), "/F", "/T"],
                    capture_output=True, timeout=10,
                    encoding="utf-8", errors="replace",
                )
                success = r.returncode == 0 or "has been terminated" in r.stdout.lower()
            else:
                import signal
                os.kill(pid, signal.SIGTERM)
                success = True
            if success:
                logger.info("Killed %s (PID %d)", label or "process", pid)
            return success
        except Exception as e:
            logger.warning("Failed to kill %s (PID %d): %s", label or "process", pid, e)
            return False

    # ── Kill on port ──────────────────────────────────────────────────

    def kill_on_port(self, port: int, host: str = "127.0.0.1") -> bool:
        """Find and kill whatever process listens on a TCP port.

        Filet de securite pour les process orphelins sans PID file.
        """
        if os.name != "nt":
            try:
                r = subprocess.run(
                    ["fuser", "-k", f"{port}/tcp"],
                    capture_output=True, timeout=10,
                )
                return r.returncode == 0
            except Exception:
                return False

        try:
            r = subprocess.run(
                ["netstat", "-ano", "-p", "TCP"],
                capture_output=True, text=True, timeout=10,
                encoding="utf-8", errors="replace",
            )
            killed = False
            for line in r.stdout.splitlines():
                # Match "  TCP    127.0.0.1:9742    0.0.0.0:0    LISTENING    12345"
                # Also match 0.0.0.0:port (bind all interfaces)
                if "LISTENING" not in line:
                    continue
                if f"{host}:{port} " not in line and f"0.0.0.0:{port} " not in line:
                    continue
                parts = line.split()
                pid = int(parts[-1])
                if pid > 0:
                    self._kill_pid(pid, f"port:{port}")
                    killed = True
            return killed
        except Exception as e:
            logger.warning("kill_on_port(%d) failed: %s", port, e)
            return False

    # ── Register / Acquire / Release ──────────────────────────────────

    def register(self, service: str, pid: int) -> None:
        """Write PID file for a service."""
        self._pid_dir.mkdir(parents=True, exist_ok=True)
        self._pid_file(service).write_text(str(pid))

    def acquire(self, service: str, pid: int | None = None,
                port: int | None = None) -> int:
        """Kill any existing instance, then register new PID.

        Args:
            service: Unique service name (e.g. "jarvis_ws", "dashboard")
            pid: PID to register. Defaults to current process.
            port: If given, also kill whatever is on this TCP port.

        Returns:
            The registered PID.
        """
        # 1. Kill by PID file
        self.kill_existing(service)

        # 2. Kill by port (filet de securite — process orphelin sans PID file)
        if port is not None:
            self.kill_on_port(port)
            # Small delay to let the port free up
            time.sleep(0.5)

        # 3. Register
        actual_pid = pid or os.getpid()
        self.register(service, actual_pid)
        logger.info("Acquired singleton: %s (PID %d%s)",
                     service, actual_pid, f", port {port}" if port else "")
        return actual_pid

    def release(self, service: str) -> None:
        """Unregister a service (on clean shutdown)."""
        pf = self._pid_file(service)
        pf.unlink(missing_ok=True)
        logger.info("Released singleton: %s", service)

    # ── Listing & cleanup ─────────────────────────────────────────────

    def list_all(self) -> dict[str, dict[str, Any]]:
        """List all registered services and their status."""
        if not self._pid_dir.exists():
            return {}
        result: dict[str, dict[str, Any]] = {}
        for pf in sorted(self._pid_dir.glob("*.pid")):
            name = pf.stem
            alive, pid = self.is_running(name)
            result[name] = {"pid": pid, "alive": alive}
        return result

    def cleanup_dead(self) -> list[str]:
        """Remove PID files for dead processes. Returns cleaned names."""
        cleaned: list[str] = []
        if not self._pid_dir.exists():
            return cleaned
        for pf in self._pid_dir.glob("*.pid"):
            name = pf.stem
            alive, _ = self.is_running(name)
            if not alive:
                pf.unlink(missing_ok=True)
                cleaned.append(name)
        return cleaned

    def kill_all(self) -> list[str]:
        """Kill ALL registered services. Returns killed names."""
        killed: list[str] = []
        for name, info in self.list_all().items():
            if info["alive"] and info["pid"]:
                if self._kill_pid(info["pid"], name):
                    killed.append(name)
                self._pid_file(name).unlink(missing_ok=True)
        return killed


# ── Singleton instance ────────────────────────────────────────────────
singleton = ProcessSingleton()
