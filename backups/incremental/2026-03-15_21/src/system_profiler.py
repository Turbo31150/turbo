"""System Profiler — Windows system profiling and benchmarking.

Capture system profiles (CPU, RAM, disk, network), run benchmarks,
compare profiles, track hardware changes over time.
Designed for JARVIS system monitoring and diagnostics.
"""

from __future__ import annotations

import logging
import os
import platform
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any


__all__ = [
    "BenchmarkResult",
    "SystemProfile",
    "SystemProfiler",
]

logger = logging.getLogger("jarvis.system_profiler")


@dataclass
class SystemProfile:
    """A captured system profile."""
    profile_id: str
    name: str
    timestamp: float = field(default_factory=time.time)
    cpu: dict[str, Any] = field(default_factory=dict)
    memory: dict[str, Any] = field(default_factory=dict)
    disk: dict[str, Any] = field(default_factory=dict)
    network: dict[str, Any] = field(default_factory=dict)
    os_info: dict[str, Any] = field(default_factory=dict)
    gpu: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)


@dataclass
class BenchmarkResult:
    """Result of a system benchmark."""
    bench_id: str
    name: str
    score: float
    duration_ms: float
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class SystemProfiler:
    """System profiling with benchmarks and comparison."""

    def __init__(self) -> None:
        self._profiles: dict[str, SystemProfile] = {}
        self._benchmarks: list[BenchmarkResult] = []
        self._counter = 0
        self._bench_counter = 0
        self._lock = threading.Lock()

    # ── Profiling ───────────────────────────────────────────────────

    def capture(self, name: str = "auto", tags: list[str] | None = None) -> SystemProfile:
        """Capture current system profile."""
        with self._lock:
            self._counter += 1
            pid = f"prof_{self._counter}"

        profile = SystemProfile(
            profile_id=pid, name=name, tags=tags or [],
            cpu=self._get_cpu_info(),
            memory=self._get_memory_info(),
            disk=self._get_disk_info(),
            os_info=self._get_os_info(),
            gpu=self._get_gpu_info(),
        )

        with self._lock:
            self._profiles[pid] = profile
        return profile

    def _get_cpu_info(self) -> dict[str, Any]:
        try:
            count = os.cpu_count() or 0
            return {"cores": count, "processor": platform.processor()}
        except Exception:
            return {"cores": 0}

    def _get_memory_info(self) -> dict[str, Any]:
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            mem_status = ctypes.c_ulonglong()
            kernel32.GetPhysicallyInstalledSystemMemory(ctypes.byref(mem_status))
            total_kb = mem_status.value
            return {"total_bytes": total_kb * 1024, "total_gb": round(total_kb / (1024**2), 1)}
        except Exception:
            return {}

    def _get_disk_info(self) -> dict[str, Any]:
        import shutil
        drives = {}
        for letter in "CDEF":
            path = f"{letter}:/"
            try:
                t, u, f = shutil.disk_usage(path)
                drives[letter] = {"total_gb": round(t / (1024**3), 1), "free_gb": round(f / (1024**3), 1)}
            except Exception:
                pass
        return drives

    def _get_os_info(self) -> dict[str, Any]:
        return {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "hostname": platform.node(),
        }

    def _get_gpu_info(self) -> dict[str, Any]:
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,temperature.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode == 0:
                gpus = []
                for line in result.stdout.strip().split("\n"):
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 3:
                        gpus.append({"name": parts[0], "vram_mb": int(parts[1]), "temp_c": int(parts[2])})
                return {"gpus": gpus, "count": len(gpus)}
        except Exception:
            pass
        return {"gpus": [], "count": 0}

    # ── Benchmarks ──────────────────────────────────────────────────

    def run_benchmark(self, name: str = "cpu_basic") -> BenchmarkResult:
        """Run a simple benchmark."""
        with self._lock:
            self._bench_counter += 1
            bid = f"bench_{self._bench_counter}"

        start = time.time()
        score = 0.0
        details: dict[str, Any] = {}

        if name == "cpu_basic":
            # Simple CPU benchmark: prime counting
            count = 0
            for n in range(2, 10000):
                if all(n % i != 0 for i in range(2, int(n**0.5) + 1)):
                    count += 1
            score = round(count / (time.time() - start), 1)
            details = {"primes_found": count, "type": "primes_per_second"}
        elif name == "memory_basic":
            # Memory allocation benchmark
            data = [bytearray(1024) for _ in range(10000)]
            score = round(10000 / (time.time() - start), 1)
            details = {"allocations": 10000, "type": "allocs_per_second"}
            del data
        elif name == "io_basic":
            # Simple I/O benchmark
            import tempfile
            tmpf = os.path.join(tempfile.gettempdir(), "jarvis_bench.tmp")
            data = b"x" * 1024 * 1024  # 1MB
            for _ in range(10):
                with open(tmpf, "wb") as f:
                    f.write(data)
            score = round(10 / (time.time() - start), 1)
            details = {"writes_mb": 10, "type": "mb_per_second"}
            try:
                os.remove(tmpf)
            except OSError:
                pass

        duration = round((time.time() - start) * 1000, 1)
        result = BenchmarkResult(bench_id=bid, name=name, score=score, duration_ms=duration, details=details)
        with self._lock:
            self._benchmarks.append(result)
        return result

    # ── Comparison ──────────────────────────────────────────────────

    def compare(self, id_a: str, id_b: str) -> dict[str, Any]:
        """Compare two profiles."""
        with self._lock:
            a = self._profiles.get(id_a)
            b = self._profiles.get(id_b)
            if not a or not b:
                return {"error": "Profile not found"}
        return {
            "profile_a": a.name,
            "profile_b": b.name,
            "cpu_same": a.cpu == b.cpu,
            "memory_same": a.memory == b.memory,
            "gpu_same": a.gpu == b.gpu,
            "os_same": a.os_info == b.os_info,
        }

    # ── Query ───────────────────────────────────────────────────────

    def get(self, profile_id: str) -> SystemProfile | None:
        with self._lock:
            return self._profiles.get(profile_id)

    def list_profiles(self, tag: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            result = []
            for p in self._profiles.values():
                if tag and tag not in p.tags:
                    continue
                result.append({
                    "id": p.profile_id, "name": p.name, "timestamp": p.timestamp,
                    "tags": p.tags, "cpu_cores": p.cpu.get("cores", 0),
                    "gpu_count": p.gpu.get("count", 0),
                })
            return result

    def list_benchmarks(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"id": b.bench_id, "name": b.name, "score": b.score,
                 "duration_ms": b.duration_ms, "timestamp": b.timestamp, "details": b.details}
                for b in self._benchmarks[-limit:]
            ]

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "total_profiles": len(self._profiles),
                "total_benchmarks": len(self._benchmarks),
                "benchmark_types": list(set(b.name for b in self._benchmarks)),
            }


# ── Singleton ───────────────────────────────────────────────────────
system_profiler = SystemProfiler()
