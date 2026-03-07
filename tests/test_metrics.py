"""Tests for src/metrics.py — Cluster performance tracking.

Covers: MetricsCollector (record_node_call, record_voice, record_trade,
record_agent, _buffer_write, flush, _flush, get_node_stats, get_voice_stats,
get_trading_stats), metrics singleton.
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.metrics import MetricsCollector, metrics


# ===========================================================================
# MetricsCollector — init
# ===========================================================================

class TestInit:
    def test_defaults(self):
        mc = MetricsCollector(db_path=Path(":memory:"))
        assert mc._buffer == []
        assert mc._initialized is False
        assert mc._buffer_limit == 50


# ===========================================================================
# MetricsCollector — record methods (buffer only)
# ===========================================================================

class TestRecordMethods:
    def test_record_node_call(self):
        mc = MetricsCollector(db_path=Path(":memory:"))
        mc._buffer_limit = 1000  # prevent auto-flush
        mc.record_node_call("M1", 500.0, success=True, model="qwen3-8b")
        assert len(mc._buffer) == 1
        assert mc._buffer[0]["table"] == "node_metrics"
        assert mc._buffer[0]["data"]["node"] == "M1"

    def test_record_voice(self):
        mc = MetricsCollector(db_path=Path(":memory:"))
        mc._buffer_limit = 1000
        mc.record_voice(transcription_ms=200, tts_ms=150, cache_hit=True)
        assert len(mc._buffer) == 1
        assert mc._buffer[0]["table"] == "voice_metrics"
        assert mc._buffer[0]["data"]["cache_hit"] == 1

    def test_record_trade(self):
        mc = MetricsCollector(db_path=Path(":memory:"))
        mc._buffer_limit = 1000
        mc.record_trade("MEXC", "BTCUSDT", "long", 50000.0, 51000.0, pnl=100.0)
        assert len(mc._buffer) == 1
        assert mc._buffer[0]["table"] == "trading_metrics"
        assert mc._buffer[0]["data"]["symbol"] == "BTCUSDT"

    def test_record_agent(self):
        mc = MetricsCollector(db_path=Path(":memory:"))
        mc._buffer_limit = 1000
        mc.record_agent("auto_develop", 5000.0, success=True, task_type="code")
        assert len(mc._buffer) == 1
        assert mc._buffer[0]["table"] == "agent_metrics"
        assert mc._buffer[0]["data"]["agent_name"] == "auto_develop"

    def test_buffer_accumulates(self):
        mc = MetricsCollector(db_path=Path(":memory:"))
        mc._buffer_limit = 1000
        mc.record_node_call("M1", 100)
        mc.record_node_call("OL1", 200)
        mc.record_voice(tts_ms=50)
        assert len(mc._buffer) == 3


# ===========================================================================
# MetricsCollector — auto-flush at limit
# ===========================================================================

class TestAutoFlush:
    def test_flushes_at_limit(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        mc = MetricsCollector(db_path=db_path)
        mc._buffer_limit = 3
        mc.record_node_call("M1", 100)
        mc.record_node_call("M1", 200)
        assert len(mc._buffer) == 2
        mc.record_node_call("M1", 300)  # triggers flush
        assert len(mc._buffer) == 0
        # Verify data in DB
        conn = sqlite3.connect(str(db_path))
        count = conn.execute("SELECT COUNT(*) FROM node_metrics").fetchone()[0]
        conn.close()
        assert count == 3
        db_path.unlink(missing_ok=True)


# ===========================================================================
# MetricsCollector — manual flush
# ===========================================================================

class TestFlush:
    def test_flush_empty(self):
        mc = MetricsCollector(db_path=Path(":memory:"))
        mc.flush()  # should not crash

    def test_flush_writes_to_db(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        mc = MetricsCollector(db_path=db_path)
        mc._buffer_limit = 1000
        mc.record_node_call("M1", 100)
        mc.record_voice(tts_ms=50)
        mc.flush()
        assert len(mc._buffer) == 0
        conn = sqlite3.connect(str(db_path))
        node_count = conn.execute("SELECT COUNT(*) FROM node_metrics").fetchone()[0]
        voice_count = conn.execute("SELECT COUNT(*) FROM voice_metrics").fetchone()[0]
        conn.close()
        assert node_count == 1
        assert voice_count == 1
        db_path.unlink(missing_ok=True)


# ===========================================================================
# MetricsCollector — _ensure_db
# ===========================================================================

class TestEnsureDb:
    def test_creates_tables(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        mc = MetricsCollector(db_path=db_path)
        mc._ensure_db()
        conn = sqlite3.connect(str(db_path))
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        conn.close()
        assert "node_metrics" in tables
        assert "voice_metrics" in tables
        assert "trading_metrics" in tables
        assert "agent_metrics" in tables
        db_path.unlink(missing_ok=True)

    def test_idempotent(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        mc = MetricsCollector(db_path=db_path)
        mc._ensure_db()
        mc._ensure_db()  # second call should be no-op
        assert mc._initialized is True
        db_path.unlink(missing_ok=True)


# ===========================================================================
# MetricsCollector — get_node_stats
# ===========================================================================

class TestGetNodeStats:
    def test_empty_db(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        mc = MetricsCollector(db_path=db_path)
        stats = mc.get_node_stats(hours=24)
        assert stats["period_hours"] == 24
        assert stats["nodes"] == {}
        db_path.unlink(missing_ok=True)

    def test_with_data(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        mc = MetricsCollector(db_path=db_path)
        mc._buffer_limit = 1000
        mc.record_node_call("M1", 500, success=True, tokens_per_sec=46.0)
        mc.record_node_call("M1", 600, success=True, tokens_per_sec=44.0)
        mc.record_node_call("OL1", 200, success=False)
        mc.flush()
        stats = mc.get_node_stats(hours=1)
        assert "M1" in stats["nodes"]
        assert stats["nodes"]["M1"]["calls"] == 2
        assert stats["nodes"]["M1"]["failures"] == 0
        assert "OL1" in stats["nodes"]
        assert stats["nodes"]["OL1"]["failures"] == 1
        db_path.unlink(missing_ok=True)


# ===========================================================================
# MetricsCollector — get_voice_stats
# ===========================================================================

class TestGetVoiceStats:
    def test_empty(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        mc = MetricsCollector(db_path=db_path)
        stats = mc.get_voice_stats()
        assert stats["total"] == 0
        db_path.unlink(missing_ok=True)

    def test_with_data(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        mc = MetricsCollector(db_path=db_path)
        mc._buffer_limit = 1000
        mc.record_voice(transcription_ms=200, tts_ms=100, cache_hit=True, confidence=0.95)
        mc.record_voice(transcription_ms=300, tts_ms=150, cache_hit=False, confidence=0.88)
        mc.flush()
        stats = mc.get_voice_stats()
        assert stats["total_calls"] == 2
        assert stats["avg_stt_ms"] == 250.0
        db_path.unlink(missing_ok=True)


# ===========================================================================
# MetricsCollector — get_trading_stats
# ===========================================================================

class TestGetTradingStats:
    def test_empty(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        mc = MetricsCollector(db_path=db_path)
        stats = mc.get_trading_stats()
        assert stats["total_trades"] == 0
        db_path.unlink(missing_ok=True)

    def test_with_data(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        mc = MetricsCollector(db_path=db_path)
        mc._buffer_limit = 1000
        mc.record_trade("MEXC", "BTCUSDT", "long", 50000, 51000, pnl=100, score=85)
        mc.record_trade("MEXC", "ETHUSDT", "short", 3000, 2900, pnl=50, score=72)
        mc.record_trade("MEXC", "SOLUSDT", "long", 100, 95, pnl=-25, score=60)
        mc.flush()
        stats = mc.get_trading_stats()
        assert stats["total_trades"] == 3
        assert stats["total_pnl"] == 125.0
        assert stats["wins"] == 2
        assert stats["losses"] == 1
        db_path.unlink(missing_ok=True)


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert metrics is not None
        assert isinstance(metrics, MetricsCollector)
