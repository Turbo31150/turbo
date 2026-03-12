"""Tests for src/agent_feedback_loop.py — Quality feedback and trend analysis.

Covers: feedback recording, trend detection, adjustment suggestions,
quality reports, A/B results, persistence.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agent_feedback_loop import FeedbackLoop, FeedbackEntry, PatternTrend, Adjustment


@pytest.fixture
def fb(tmp_path):
    """FeedbackLoop with isolated temp database."""
    return FeedbackLoop(db_path=str(tmp_path / "test_fb.db"))


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestDataclasses:
    def test_feedback_entry_defaults(self):
        e = FeedbackEntry("code", "M1", "single", 0.8)
        assert e.user_rating == 0
        assert e.success is True

    def test_pattern_trend(self):
        t = PatternTrend("code", "improving", 0.9, 0.7, 28.5, 20, "M1", "single")
        assert t.direction == "improving"

    def test_adjustment(self):
        a = Adjustment("code", "switch_node", "M3", "M1", "degrading", 0.8, "+20%")
        assert a.action == "switch_node"


# ===========================================================================
# Recording feedback
# ===========================================================================

class TestRecordFeedback:
    def test_record_basic(self, fb):
        fb.record_feedback("code", "M1", quality=0.9, success=True)
        assert len(fb._feedback_cache) == 1
        assert fb._feedback_cache[0].pattern == "code"

    def test_record_multiple(self, fb):
        fb.record_feedback("code", "M1", quality=0.9)
        fb.record_feedback("question", "OL1", quality=0.7)
        fb.record_feedback("math", "M1", quality=0.5)
        assert len(fb._feedback_cache) == 3

    def test_newest_first(self, fb):
        fb.record_feedback("code", "M1", quality=0.9)
        fb.record_feedback("question", "OL1", quality=0.7)
        assert fb._feedback_cache[0].pattern == "question"

    def test_cache_limit(self, fb):
        for i in range(2100):
            fb.record_feedback("code", "M1", quality=0.5)
        assert len(fb._feedback_cache) == 2000

    def test_user_rating(self, fb):
        fb.record_feedback("code", "M1", quality=0.8, user_rating=5)
        assert fb._feedback_cache[0].user_rating == 5

    def test_prompt_preview_truncated(self, fb):
        fb.record_feedback("code", "M1", prompt_preview="x" * 200)
        assert len(fb._feedback_cache[0].prompt_preview) == 100

    def test_persisted_to_db(self, fb, tmp_path):
        import sqlite3
        fb.record_feedback("code", "M1", quality=0.85)
        db = sqlite3.connect(str(tmp_path / "test_fb.db"))
        count = db.execute("SELECT COUNT(*) FROM agent_feedback").fetchone()[0]
        assert count == 1
        db.close()


# ===========================================================================
# Trends
# ===========================================================================

class TestTrends:
    def test_improving_trend(self, fb):
        # Older entries: low quality
        for _ in range(10):
            fb.record_feedback("code", "M1", quality=0.3)
        # Recent entries: high quality (inserted at front)
        for _ in range(10):
            fb.record_feedback("code", "M1", quality=0.9)
        trends = fb.get_trends()
        code_trend = next((t for t in trends if t.pattern == "code"), None)
        assert code_trend is not None
        assert code_trend.direction == "improving"
        assert code_trend.change_pct > 0

    def test_degrading_trend(self, fb):
        # Older entries: high quality
        for _ in range(10):
            fb.record_feedback("code", "M1", quality=0.9)
        # Recent entries: low quality
        for _ in range(10):
            fb.record_feedback("code", "M1", quality=0.3)
        trends = fb.get_trends()
        code_trend = next((t for t in trends if t.pattern == "code"), None)
        assert code_trend is not None
        assert code_trend.direction == "degrading"

    def test_stable_trend(self, fb):
        for _ in range(20):
            fb.record_feedback("code", "M1", quality=0.7)
        trends = fb.get_trends()
        code_trend = next((t for t in trends if t.pattern == "code"), None)
        assert code_trend is not None
        assert code_trend.direction == "stable"

    def test_not_enough_data(self, fb):
        fb.record_feedback("code", "M1", quality=0.5)
        fb.record_feedback("code", "M1", quality=0.6)
        trends = fb.get_trends()
        assert len([t for t in trends if t.pattern == "code"]) == 0

    def test_best_node_in_trend(self, fb):
        for _ in range(10):
            fb.record_feedback("code", "M1", quality=0.9, success=True)
        for _ in range(10):
            fb.record_feedback("code", "OL1", quality=0.5, success=True)
        trends = fb.get_trends()
        code_trend = next((t for t in trends if t.pattern == "code"), None)
        assert code_trend is not None
        assert code_trend.best_node == "M1"


# ===========================================================================
# Adjustments
# ===========================================================================

class TestAdjustments:
    def test_suggest_on_degrading(self, fb):
        for _ in range(15):
            fb.record_feedback("code", "M1", quality=0.9, success=True)
        for _ in range(15):
            fb.record_feedback("code", "M1", quality=0.2, success=True)
        adjustments = fb.suggest_adjustments()
        code_adj = [a for a in adjustments if a.pattern == "code"]
        assert len(code_adj) >= 1

    def test_suggest_on_low_quality(self, fb):
        for _ in range(10):
            fb.record_feedback("code", "M1", quality=0.2, success=True)
        adjustments = fb.suggest_adjustments()
        timeout_adj = [a for a in adjustments if a.action == "increase_timeout"]
        assert len(timeout_adj) >= 1

    def test_ab_switch_suggestion(self, fb):
        for _ in range(5):
            fb.record_feedback("code", "M1", quality=0.9, success=True)
        for _ in range(5):
            fb.record_feedback("code", "M3", quality=0.3, success=True)
        adjustments = fb.suggest_adjustments()
        switch = [a for a in adjustments if a.action == "switch_node" and "A/B" in a.reason]
        assert len(switch) >= 1

    def test_no_adjustments_when_ok(self, fb):
        for _ in range(20):
            fb.record_feedback("code", "M1", quality=0.8, success=True)
        adjustments = fb.suggest_adjustments()
        # Stable, high quality, single node — no adjustments needed
        degrading = [a for a in adjustments if a.pattern == "code" and "degrading" in a.reason.lower()]
        assert len(degrading) == 0


# ===========================================================================
# Quality report
# ===========================================================================

class TestQualityReport:
    def test_empty_report(self, fb):
        report = fb.get_quality_report()
        assert report["total"] == 0 or report["total_feedback"] == 0

    def test_report_with_data(self, fb):
        fb.record_feedback("code", "M1", quality=0.9, success=True)
        fb.record_feedback("code", "M1", quality=0.7, success=True)
        fb.record_feedback("question", "OL1", quality=0.5, success=False)
        report = fb.get_quality_report()
        assert report["total_feedback"] == 3
        assert report["success_rate"] == pytest.approx(2/3, abs=0.01)
        assert "code" in report["patterns"]

    def test_report_user_ratings(self, fb):
        fb.record_feedback("code", "M1", quality=0.8, user_rating=4)
        fb.record_feedback("code", "M1", quality=0.6, user_rating=3)
        fb.record_feedback("code", "M1", quality=0.5)  # No rating
        report = fb.get_quality_report()
        assert report["user_rated"] == 2
        assert report["avg_user_rating"] == 3.5


# ===========================================================================
# A/B results
# ===========================================================================

class TestABResults:
    def test_ab_results_multiple_nodes(self, fb):
        for _ in range(5):
            fb.record_feedback("code", "M1", quality=0.9, success=True)
        for _ in range(5):
            fb.record_feedback("code", "OL1", quality=0.6, success=True)
        results = fb.get_ab_results()
        assert "code" in results
        assert "M1" in results["code"]
        assert "OL1" in results["code"]
        assert results["code"]["M1"]["avg_quality"] > results["code"]["OL1"]["avg_quality"]

    def test_ab_results_single_node(self, fb):
        for _ in range(5):
            fb.record_feedback("code", "M1", quality=0.8)
        results = fb.get_ab_results()
        # Only 1 node, so no A/B comparison
        assert "code" not in results

    def test_ab_results_empty(self, fb):
        assert fb.get_ab_results() == {}


# ===========================================================================
# Persistence / reload
# ===========================================================================

class TestPersistence:
    def test_reload_from_db(self, tmp_path):
        db_path = str(tmp_path / "test_persist.db")
        fb1 = FeedbackLoop(db_path=db_path)
        fb1.record_feedback("code", "M1", quality=0.9)
        fb1.record_feedback("question", "OL1", quality=0.7)

        fb2 = FeedbackLoop(db_path=db_path)
        assert len(fb2._feedback_cache) == 2
        assert fb2._feedback_cache[0].pattern in ("code", "question")
