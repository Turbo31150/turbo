"""Tests for src/daily_report.py — fully mocked, no external dependencies."""

import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# 1. Import tests
# ---------------------------------------------------------------------------

class TestImports:
    """Verify that the module and its public API can be imported."""

    def test_import_module(self):
        import src.daily_report
        assert hasattr(src.daily_report, "generate_morning_report")
        assert hasattr(src.daily_report, "generate_evening_report")

    def test_import_public_functions(self):
        from src.daily_report import generate_morning_report, generate_evening_report
        assert callable(generate_morning_report)
        assert callable(generate_evening_report)

    def test_import_build_summary(self):
        from src.daily_report import _build_summary
        assert callable(_build_summary)


# ---------------------------------------------------------------------------
# 2. _build_summary tests (pure function, no mocking needed)
# ---------------------------------------------------------------------------

class TestBuildSummary:
    """Test the synchronous summary builder."""

    def test_empty_report(self):
        from src.daily_report import _build_summary
        result = _build_summary({"sections": {}})
        assert result == "Rapport genere"

    def test_cluster_section(self):
        from src.daily_report import _build_summary
        report = {"sections": {"cluster": {"score": 95}}}
        result = _build_summary(report)
        assert "95% sante" in result

    def test_cluster_with_error_skipped(self):
        from src.daily_report import _build_summary
        report = {"sections": {"cluster": {"error": "offline"}}}
        result = _build_summary(report)
        assert "sante" not in result

    def test_trading_section(self):
        from src.daily_report import _build_summary
        report = {"sections": {"trading": {"positions_monitored": 3, "alerts_today": 1}}}
        result = _build_summary(report)
        assert "3 positions" in result
        assert "1 alertes" in result

    def test_gpu_section(self):
        from src.daily_report import _build_summary
        report = {"sections": {"gpu": {"current": {"temperature": 55, "vram_percent": 60}}}}
        result = _build_summary(report)
        assert "55C" in result or "55" in result
        assert "60%" in result

    def test_alerts_critical(self):
        from src.daily_report import _build_summary
        report = {"sections": {"alerts": {"total": 10, "critical": 3}}}
        result = _build_summary(report)
        assert "3 critiques" in result

    def test_alerts_zero_critical_not_shown(self):
        from src.daily_report import _build_summary
        report = {"sections": {"alerts": {"total": 5, "critical": 0}}}
        result = _build_summary(report)
        assert "critiques" not in result

    def test_daily_alerts_fallback_key(self):
        """Evening reports use 'daily_alerts' instead of 'alerts'."""
        from src.daily_report import _build_summary
        report = {"sections": {"daily_alerts": {"total": 2, "critical": 2}}}
        result = _build_summary(report)
        assert "2 critiques" in result

    def test_multiple_sections_joined(self):
        from src.daily_report import _build_summary
        report = {
            "sections": {
                "cluster": {"score": 100},
                "trading": {"positions_monitored": 5, "alerts_today": 0},
            }
        }
        result = _build_summary(report)
        assert " | " in result
        assert "100% sante" in result
        assert "5 positions" in result


# ---------------------------------------------------------------------------
# 3. Internal data-gathering functions (each import is mocked)
# ---------------------------------------------------------------------------

class TestGetClusterHealth:
    @pytest.mark.asyncio
    async def test_success(self):
        from src.daily_report import _get_cluster_health

        mock_result_healthy = MagicMock()
        mock_result_healthy.status.value = "healthy"
        mock_result_healthy.name = "M1"

        mock_result_unhealthy = MagicMock()
        mock_result_unhealthy.status.value = "degraded"
        mock_result_unhealthy.name = "M3"

        mock_probe = MagicMock()
        mock_probe.run_all.return_value = [mock_result_healthy, mock_result_unhealthy]

        with patch.dict("sys.modules", {"src.health_probe": MagicMock(health_probe=mock_probe)}):
            result = await _get_cluster_health()

        assert result["healthy"] == 1
        assert result["total"] == 2
        assert result["score"] == 50
        assert "M3" in result["issues"]

    @pytest.mark.asyncio
    async def test_all_healthy(self):
        from src.daily_report import _get_cluster_health

        nodes = []
        for name in ["M1", "M2", "OL1"]:
            m = MagicMock()
            m.status.value = "healthy"
            m.name = name
            nodes.append(m)

        mock_probe = MagicMock()
        mock_probe.run_all.return_value = nodes

        with patch.dict("sys.modules", {"src.health_probe": MagicMock(health_probe=mock_probe)}):
            result = await _get_cluster_health()

        assert result["score"] == 100
        assert result["issues"] == []

    @pytest.mark.asyncio
    async def test_import_error(self):
        from src.daily_report import _get_cluster_health

        with patch.dict("sys.modules", {"src.health_probe": None}):
            result = await _get_cluster_health()

        assert "error" in result


class TestGetGpuStatus:
    @pytest.mark.asyncio
    async def test_success(self):
        from src.daily_report import _get_gpu_status

        mock_guardian = MagicMock()
        mock_guardian.status.return_value = {
            "latest": {"temperature": 42, "vram_percent": 55},
            "stats": {"avg_temp": 40}
        }
        mock_guardian.trend.return_value = [40, 41, 42]

        with patch.dict("sys.modules", {"src.gpu_guardian": MagicMock(gpu_guardian=mock_guardian)}):
            result = await _get_gpu_status()

        assert result["current"]["temperature"] == 42
        assert result["trend_1h"] == [40, 41, 42]
        assert result["stats"]["avg_temp"] == 40

    @pytest.mark.asyncio
    async def test_import_error(self):
        from src.daily_report import _get_gpu_status

        with patch.dict("sys.modules", {"src.gpu_guardian": None}):
            result = await _get_gpu_status()

        assert "error" in result


class TestGetTradingStatus:
    @pytest.mark.asyncio
    async def test_success(self):
        from src.daily_report import _get_trading_status

        mock_sentinel = MagicMock()
        mock_sentinel.summary.return_value = {
            "stats": {"positions_monitored": 5, "alerts_sent": 2, "emergency_closes": 0},
            "recent_alerts": ["a1", "a2", "a3", "a4", "a5", "a6", "a7"]
        }

        with patch.dict("sys.modules", {"src.trading_sentinel": MagicMock(trading_sentinel=mock_sentinel)}):
            result = await _get_trading_status()

        assert result["positions_monitored"] == 5
        assert result["alerts_today"] == 2
        assert result["emergency_closes"] == 0
        # Only last 5 alerts kept
        assert len(result["recent_alerts"]) == 5

    @pytest.mark.asyncio
    async def test_import_error(self):
        from src.daily_report import _get_trading_status

        with patch.dict("sys.modules", {"src.trading_sentinel": None}):
            result = await _get_trading_status()

        assert "error" in result


class TestGetRecentAlerts:
    @pytest.mark.asyncio
    async def test_filters_by_hours(self):
        from src.daily_report import _get_recent_alerts

        now = time.time()
        recent_notif = MagicMock(ts=now - 3600, level="warning")  # 1h ago
        old_notif = MagicMock(ts=now - 100000, level="critical")  # ~28h ago
        critical_recent = MagicMock(ts=now - 1800, level="critical")  # 30min ago

        mock_hub = MagicMock()
        mock_hub._history = [recent_notif, old_notif, critical_recent]

        with patch.dict("sys.modules", {"src.notification_hub": MagicMock(notification_hub=mock_hub)}):
            result = await _get_recent_alerts(hours=12)

        assert result["total"] == 2  # recent_notif + critical_recent
        assert result["critical"] == 1  # only critical_recent
        assert result["hours"] == 12

    @pytest.mark.asyncio
    async def test_import_error(self):
        from src.daily_report import _get_recent_alerts

        with patch.dict("sys.modules", {"src.notification_hub": None}):
            result = await _get_recent_alerts(hours=24)

        assert "error" in result


class TestGetBrainActivity:
    @pytest.mark.asyncio
    async def test_success(self):
        from src.daily_report import _get_brain_activity

        mock_brain = MagicMock()
        mock_brain.status.return_value = {
            "skills_count": 89,
            "patterns_detected": 26,
            "actions_logged": 500
        }

        with patch.dict("sys.modules", {"src.brain": MagicMock(brain=mock_brain)}):
            result = await _get_brain_activity()

        assert result["skills_count"] == 89
        assert result["patterns_detected"] == 26
        assert result["actions_logged"] == 500

    @pytest.mark.asyncio
    async def test_brain_without_status(self):
        from src.daily_report import _get_brain_activity

        mock_brain = MagicMock(spec=[])  # no 'status' attribute

        with patch.dict("sys.modules", {"src.brain": MagicMock(brain=mock_brain)}):
            result = await _get_brain_activity()

        assert result["skills_count"] == 0
        assert result["patterns_detected"] == 0

    @pytest.mark.asyncio
    async def test_import_error(self):
        from src.daily_report import _get_brain_activity

        with patch.dict("sys.modules", {"src.brain": None}):
            result = await _get_brain_activity()

        assert "error" in result


class TestGetSystemResources:
    @pytest.mark.asyncio
    async def test_success(self):
        from src.daily_report import _get_system_resources

        mock_psutil = MagicMock()
        mock_psutil.cpu_percent.return_value = 35.0
        mock_mem = MagicMock()
        mock_mem.used = 16 * (1024 ** 3)
        mock_mem.total = 32 * (1024 ** 3)
        mock_mem.percent = 50.0
        mock_psutil.virtual_memory.return_value = mock_mem

        mock_shutil = MagicMock()
        mock_disk = MagicMock()
        mock_disk.free = 100 * (1024 ** 3)
        mock_disk.used = 346 * (1024 ** 3)
        mock_disk.total = 446 * (1024 ** 3)
        mock_shutil.disk_usage.return_value = mock_disk

        with patch.dict("sys.modules", {"psutil": mock_psutil, "shutil": mock_shutil}):
            # Need to reimport to pick up mocked shutil at module level
            # Instead, patch inside the function scope
            pass

        # Better approach: patch at the point of use inside the function
        with patch("shutil.disk_usage", return_value=mock_disk), \
             patch("psutil.cpu_percent", return_value=35.0), \
             patch("psutil.virtual_memory", return_value=mock_mem):
            result = await _get_system_resources()

        assert result["cpu_percent"] == 35.0
        assert result["ram_used_gb"] == 16.0
        assert result["ram_total_gb"] == 32.0
        assert result["ram_percent"] == 50.0
        assert result["disk_free_gb"] == 100.0
        assert 77.0 < result["disk_percent_used"] < 78.0


class TestGetPerformanceStats:
    @pytest.mark.asyncio
    async def test_success(self):
        from src.daily_report import _get_performance_stats

        mock_stats = MagicMock()
        mock_stats.to_dict.return_value = {"success_rate": 97, "total_calls": 200}

        with patch.dict("sys.modules", {"src.smart_retry": MagicMock(retry_stats=mock_stats)}):
            result = await _get_performance_stats()

        assert result["success_rate"] == 97
        assert result["total_calls"] == 200

    @pytest.mark.asyncio
    async def test_import_error(self):
        from src.daily_report import _get_performance_stats

        with patch.dict("sys.modules", {"src.smart_retry": None}):
            result = await _get_performance_stats()

        assert "error" in result


# ---------------------------------------------------------------------------
# 4. Recommendations
# ---------------------------------------------------------------------------

class TestGetRecommendations:
    @pytest.mark.asyncio
    async def test_nominal_no_issues(self):
        from src.daily_report import _get_recommendations

        with patch("src.daily_report._get_gpu_status", new_callable=AsyncMock) as mock_gpu, \
             patch("src.daily_report._get_system_resources", new_callable=AsyncMock) as mock_res, \
             patch.dict("sys.modules", {"src.smart_retry": None}):

            mock_gpu.return_value = {"current": {"temperature": 50, "vram_percent": 40}}
            mock_res.return_value = {"disk_free_gb": 100, "ram_percent": 50}

            recs = await _get_recommendations()

        assert len(recs) == 1
        assert "nominal" in recs[0].lower()

    @pytest.mark.asyncio
    async def test_high_gpu_temp(self):
        from src.daily_report import _get_recommendations

        with patch("src.daily_report._get_gpu_status", new_callable=AsyncMock) as mock_gpu, \
             patch("src.daily_report._get_system_resources", new_callable=AsyncMock) as mock_res, \
             patch.dict("sys.modules", {"src.smart_retry": None}):

            mock_gpu.return_value = {"current": {"temperature": 80, "vram_percent": 40}}
            mock_res.return_value = {"disk_free_gb": 100, "ram_percent": 50}

            recs = await _get_recommendations()

        assert any("temperature" in r.lower() for r in recs)

    @pytest.mark.asyncio
    async def test_high_vram(self):
        from src.daily_report import _get_recommendations

        with patch("src.daily_report._get_gpu_status", new_callable=AsyncMock) as mock_gpu, \
             patch("src.daily_report._get_system_resources", new_callable=AsyncMock) as mock_res, \
             patch.dict("sys.modules", {"src.smart_retry": None}):

            mock_gpu.return_value = {"current": {"temperature": 50, "vram_percent": 90}}
            mock_res.return_value = {"disk_free_gb": 100, "ram_percent": 50}

            recs = await _get_recommendations()

        assert any("vram" in r.lower() for r in recs)

    @pytest.mark.asyncio
    async def test_low_disk(self):
        from src.daily_report import _get_recommendations

        with patch("src.daily_report._get_gpu_status", new_callable=AsyncMock) as mock_gpu, \
             patch("src.daily_report._get_system_resources", new_callable=AsyncMock) as mock_res, \
             patch.dict("sys.modules", {"src.smart_retry": None}):

            mock_gpu.return_value = {"current": {"temperature": 50, "vram_percent": 40}}
            mock_res.return_value = {"disk_free_gb": 10, "ram_percent": 50}

            recs = await _get_recommendations()

        assert any("disk" in r.lower() for r in recs)

    @pytest.mark.asyncio
    async def test_high_ram(self):
        from src.daily_report import _get_recommendations

        with patch("src.daily_report._get_gpu_status", new_callable=AsyncMock) as mock_gpu, \
             patch("src.daily_report._get_system_resources", new_callable=AsyncMock) as mock_res, \
             patch.dict("sys.modules", {"src.smart_retry": None}):

            mock_gpu.return_value = {"current": {"temperature": 50, "vram_percent": 40}}
            mock_res.return_value = {"disk_free_gb": 100, "ram_percent": 90}

            recs = await _get_recommendations()

        assert any("ram" in r.lower() for r in recs)

    @pytest.mark.asyncio
    async def test_low_success_rate(self):
        from src.daily_report import _get_recommendations

        mock_stats = MagicMock()
        mock_stats.to_dict.return_value = {"success_rate": 75}

        with patch("src.daily_report._get_gpu_status", new_callable=AsyncMock) as mock_gpu, \
             patch("src.daily_report._get_system_resources", new_callable=AsyncMock) as mock_res, \
             patch.dict("sys.modules", {"src.smart_retry": MagicMock(retry_stats=mock_stats)}):

            mock_gpu.return_value = {"current": {"temperature": 50, "vram_percent": 40}}
            mock_res.return_value = {"disk_free_gb": 100, "ram_percent": 50}

            recs = await _get_recommendations()

        assert any("success rate" in r.lower() for r in recs)


# ---------------------------------------------------------------------------
# 5. Full report generation (end-to-end with all sub-functions mocked)
# ---------------------------------------------------------------------------

class TestGenerateMorningReport:
    @pytest.mark.asyncio
    async def test_structure(self):
        from src.daily_report import generate_morning_report

        with patch("src.daily_report._get_cluster_health", new_callable=AsyncMock) as m_cluster, \
             patch("src.daily_report._get_gpu_status", new_callable=AsyncMock) as m_gpu, \
             patch("src.daily_report._get_trading_status", new_callable=AsyncMock) as m_trading, \
             patch("src.daily_report._get_recent_alerts", new_callable=AsyncMock) as m_alerts, \
             patch("src.daily_report._get_brain_activity", new_callable=AsyncMock) as m_brain, \
             patch("src.daily_report._get_system_resources", new_callable=AsyncMock) as m_res:

            m_cluster.return_value = {"healthy": 4, "total": 4, "score": 100, "issues": []}
            m_gpu.return_value = {"current": {"temperature": 45, "vram_percent": 50}, "trend_1h": [], "stats": {}}
            m_trading.return_value = {"positions_monitored": 2, "alerts_today": 0, "emergency_closes": 0, "recent_alerts": []}
            m_alerts.return_value = {"total": 0, "critical": 0, "hours": 12}
            m_brain.return_value = {"skills_count": 89, "patterns_detected": 26, "actions_logged": 100}
            m_res.return_value = {"cpu_percent": 20, "ram_used_gb": 10, "ram_total_gb": 32, "ram_percent": 31, "disk_free_gb": 100, "disk_percent_used": 77}

            report = await generate_morning_report()

        assert report["type"] == "morning_briefing"
        assert "ts" in report
        assert "date" in report
        assert "summary" in report
        expected_sections = {"cluster", "gpu", "trading", "alerts", "brain", "resources"}
        assert expected_sections == set(report["sections"].keys())

    @pytest.mark.asyncio
    async def test_alerts_called_with_12_hours(self):
        from src.daily_report import generate_morning_report

        with patch("src.daily_report._get_cluster_health", new_callable=AsyncMock, return_value={}), \
             patch("src.daily_report._get_gpu_status", new_callable=AsyncMock, return_value={}), \
             patch("src.daily_report._get_trading_status", new_callable=AsyncMock, return_value={}), \
             patch("src.daily_report._get_recent_alerts", new_callable=AsyncMock, return_value={}) as m_alerts, \
             patch("src.daily_report._get_brain_activity", new_callable=AsyncMock, return_value={}), \
             patch("src.daily_report._get_system_resources", new_callable=AsyncMock, return_value={}):

            await generate_morning_report()
            m_alerts.assert_called_once_with(hours=12)


class TestGenerateEveningReport:
    @pytest.mark.asyncio
    async def test_structure(self):
        from src.daily_report import generate_evening_report

        with patch("src.daily_report._get_cluster_health", new_callable=AsyncMock, return_value={"score": 80}), \
             patch("src.daily_report._get_trading_status", new_callable=AsyncMock, return_value={"positions_monitored": 1, "alerts_today": 0}), \
             patch("src.daily_report._get_recent_alerts", new_callable=AsyncMock, return_value={"total": 3, "critical": 0, "hours": 24}), \
             patch("src.daily_report._get_performance_stats", new_callable=AsyncMock, return_value={"success_rate": 95}), \
             patch("src.daily_report._get_brain_activity", new_callable=AsyncMock, return_value={"skills_count": 89}), \
             patch("src.daily_report._get_recommendations", new_callable=AsyncMock, return_value=["All systems nominal"]):

            report = await generate_evening_report()

        assert report["type"] == "evening_report"
        expected_sections = {"cluster", "trading", "daily_alerts", "performance", "brain", "recommendations"}
        assert expected_sections == set(report["sections"].keys())

    @pytest.mark.asyncio
    async def test_alerts_called_with_24_hours(self):
        from src.daily_report import generate_evening_report

        with patch("src.daily_report._get_cluster_health", new_callable=AsyncMock, return_value={}), \
             patch("src.daily_report._get_trading_status", new_callable=AsyncMock, return_value={}), \
             patch("src.daily_report._get_recent_alerts", new_callable=AsyncMock, return_value={}) as m_alerts, \
             patch("src.daily_report._get_performance_stats", new_callable=AsyncMock, return_value={}), \
             patch("src.daily_report._get_brain_activity", new_callable=AsyncMock, return_value={}), \
             patch("src.daily_report._get_recommendations", new_callable=AsyncMock, return_value=[]):

            await generate_evening_report()
            m_alerts.assert_called_once_with(hours=24)

    @pytest.mark.asyncio
    async def test_summary_is_string(self):
        from src.daily_report import generate_evening_report

        with patch("src.daily_report._get_cluster_health", new_callable=AsyncMock, return_value={}), \
             patch("src.daily_report._get_trading_status", new_callable=AsyncMock, return_value={}), \
             patch("src.daily_report._get_recent_alerts", new_callable=AsyncMock, return_value={}), \
             patch("src.daily_report._get_performance_stats", new_callable=AsyncMock, return_value={}), \
             patch("src.daily_report._get_brain_activity", new_callable=AsyncMock, return_value={}), \
             patch("src.daily_report._get_recommendations", new_callable=AsyncMock, return_value=[]):

            report = await generate_evening_report()

        assert isinstance(report["summary"], str)
