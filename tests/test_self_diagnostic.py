"""Tests for JARVIS Self-Diagnostic and Log Analyzer."""

import pytest


class TestSelfDiagnostic:
    def test_import(self):
        from src.self_diagnostic import self_diagnostic
        assert self_diagnostic is not None

    @pytest.mark.asyncio
    async def test_diagnose(self):
        from src.self_diagnostic import self_diagnostic
        result = await self_diagnostic.diagnose()
        assert "health_score" in result
        assert "issues" in result
        assert "recommendations" in result
        assert "timestamp" in result
        assert 0 <= result["health_score"] <= 100

    @pytest.mark.asyncio
    async def test_check_response_times(self):
        from src.self_diagnostic import self_diagnostic
        issues = self_diagnostic._check_response_times()
        assert isinstance(issues, list)

    @pytest.mark.asyncio
    async def test_check_error_rates(self):
        from src.self_diagnostic import self_diagnostic
        issues = self_diagnostic._check_error_rates()
        assert isinstance(issues, list)

    @pytest.mark.asyncio
    async def test_check_circuit_breakers(self):
        from src.self_diagnostic import self_diagnostic
        issues = self_diagnostic._check_circuit_breakers()
        assert isinstance(issues, list)

    @pytest.mark.asyncio
    async def test_check_scheduler_health(self):
        from src.self_diagnostic import self_diagnostic
        issues = self_diagnostic._check_scheduler_health()
        assert isinstance(issues, list)

    @pytest.mark.asyncio
    async def test_check_queue_backlog(self):
        from src.self_diagnostic import self_diagnostic
        issues = self_diagnostic._check_queue_backlog()
        assert isinstance(issues, list)

    def test_generate_recommendations(self):
        from src.self_diagnostic import self_diagnostic
        recs = self_diagnostic._generate_recommendations([
            {"severity": "critical", "description": "M1 OFFLINE"},
            {"severity": "warning", "description": "VRAM >95%"},
        ])
        assert isinstance(recs, list)


class TestLogAnalyzer:
    def test_import(self):
        from src.log_analyzer import log_analyzer
        assert log_analyzer is not None

    def test_analyze_recent(self):
        from src.log_analyzer import log_analyzer
        result = log_analyzer.analyze_recent()
        assert isinstance(result, dict)
        assert "total_entries" in result
        assert "trend" in result

    def test_detect_patterns(self):
        from src.log_analyzer import log_analyzer
        patterns = log_analyzer.detect_patterns()
        assert isinstance(patterns, list)

    def test_predict_failures(self):
        from src.log_analyzer import log_analyzer
        predictions = log_analyzer.predict_failures()
        assert isinstance(predictions, list)

    def test_get_trend(self):
        from src.log_analyzer import log_analyzer
        trend = log_analyzer.get_trend()
        assert isinstance(trend, dict)
        assert "trend" in trend
        assert trend["trend"] in ("improving", "stable", "degrading", "no_data")
