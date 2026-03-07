"""Tests for src/system_profiler.py — Windows system profiling and benchmarking.

Covers: SystemProfile, BenchmarkResult, SystemProfiler (capture, run_benchmark,
compare, get, list_profiles, list_benchmarks, get_stats), system_profiler singleton.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.system_profiler import (
    SystemProfile, BenchmarkResult, SystemProfiler, system_profiler,
)


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestSystemProfile:
    def test_defaults(self):
        p = SystemProfile(profile_id="p1", name="test")
        assert p.cpu == {}
        assert p.memory == {}
        assert p.disk == {}
        assert p.gpu == {}
        assert p.tags == []
        assert p.timestamp > 0


class TestBenchmarkResult:
    def test_defaults(self):
        b = BenchmarkResult(bench_id="b1", name="cpu", score=1000, duration_ms=500)
        assert b.details == {}
        assert b.timestamp > 0


# ===========================================================================
# SystemProfiler — capture
# ===========================================================================

class TestCapture:
    def test_capture(self):
        sp = SystemProfiler()
        with patch.object(sp, "_get_gpu_info", return_value={"gpus": [], "count": 0}):
            profile = sp.capture("test", tags=["debug"])
        assert profile.profile_id == "prof_1"
        assert profile.name == "test"
        assert profile.tags == ["debug"]
        assert "cores" in profile.cpu
        assert "system" in profile.os_info

    def test_capture_increments_counter(self):
        sp = SystemProfiler()
        with patch.object(sp, "_get_gpu_info", return_value={"gpus": [], "count": 0}):
            p1 = sp.capture("a")
            p2 = sp.capture("b")
        assert p1.profile_id == "prof_1"
        assert p2.profile_id == "prof_2"


# ===========================================================================
# SystemProfiler — internal info getters
# ===========================================================================

class TestInfoGetters:
    def test_cpu_info(self):
        sp = SystemProfiler()
        info = sp._get_cpu_info()
        assert "cores" in info
        assert info["cores"] > 0

    def test_os_info(self):
        sp = SystemProfiler()
        info = sp._get_os_info()
        assert info["system"] in ("Windows", "Linux", "Darwin")
        assert "hostname" in info

    def test_gpu_info_no_nvidia(self):
        sp = SystemProfiler()
        with patch("subprocess.run", side_effect=FileNotFoundError):
            info = sp._get_gpu_info()
        assert info == {"gpus": [], "count": 0}


# ===========================================================================
# SystemProfiler — run_benchmark
# ===========================================================================

class TestRunBenchmark:
    def test_cpu_basic(self):
        sp = SystemProfiler()
        result = sp.run_benchmark("cpu_basic")
        assert result.bench_id == "bench_1"
        assert result.name == "cpu_basic"
        assert result.score > 0
        assert result.duration_ms > 0
        assert result.details["type"] == "primes_per_second"

    def test_memory_basic(self):
        sp = SystemProfiler()
        result = sp.run_benchmark("memory_basic")
        assert result.score > 0
        assert result.details["type"] == "allocs_per_second"

    def test_unknown_benchmark(self):
        sp = SystemProfiler()
        result = sp.run_benchmark("unknown_type")
        assert result.score == 0.0


# ===========================================================================
# SystemProfiler — compare
# ===========================================================================

class TestCompare:
    def test_compare(self):
        sp = SystemProfiler()
        with patch.object(sp, "_get_gpu_info", return_value={"gpus": [], "count": 0}):
            p1 = sp.capture("a")
            p2 = sp.capture("b")
        result = sp.compare(p1.profile_id, p2.profile_id)
        assert result["cpu_same"] is True
        assert result["os_same"] is True

    def test_compare_not_found(self):
        sp = SystemProfiler()
        result = sp.compare("nope_a", "nope_b")
        assert "error" in result


# ===========================================================================
# SystemProfiler — query methods
# ===========================================================================

class TestQueryMethods:
    def test_get(self):
        sp = SystemProfiler()
        with patch.object(sp, "_get_gpu_info", return_value={"gpus": [], "count": 0}):
            p = sp.capture("test")
        assert sp.get(p.profile_id) is not None
        assert sp.get("nope") is None

    def test_list_profiles(self):
        sp = SystemProfiler()
        with patch.object(sp, "_get_gpu_info", return_value={"gpus": [], "count": 0}):
            sp.capture("a", tags=["web"])
            sp.capture("b", tags=["db"])
        result = sp.list_profiles()
        assert len(result) == 2

    def test_list_profiles_filter_tag(self):
        sp = SystemProfiler()
        with patch.object(sp, "_get_gpu_info", return_value={"gpus": [], "count": 0}):
            sp.capture("a", tags=["web"])
            sp.capture("b", tags=["db"])
        result = sp.list_profiles(tag="web")
        assert len(result) == 1

    def test_list_benchmarks(self):
        sp = SystemProfiler()
        sp.run_benchmark("cpu_basic")
        result = sp.list_benchmarks()
        assert len(result) == 1
        assert result[0]["name"] == "cpu_basic"

    def test_get_stats_empty(self):
        sp = SystemProfiler()
        stats = sp.get_stats()
        assert stats["total_profiles"] == 0
        assert stats["total_benchmarks"] == 0

    def test_get_stats_with_data(self):
        sp = SystemProfiler()
        with patch.object(sp, "_get_gpu_info", return_value={"gpus": [], "count": 0}):
            sp.capture("test")
        sp.run_benchmark("cpu_basic")
        stats = sp.get_stats()
        assert stats["total_profiles"] == 1
        assert stats["total_benchmarks"] == 1
        assert "cpu_basic" in stats["benchmark_types"]


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert system_profiler is not None
        assert isinstance(system_profiler, SystemProfiler)
