"""JARVIS Metrics & Analytics — Cluster performance tracking.

Collects and stores metrics for:
- Node latency, throughput, error rates
- Voice pipeline performance
- Trading signal accuracy
- Cache hit rates
- Agent usage patterns
"""

from __future__ import annotations

import logging
import sqlite3
import time
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.metrics")

_METRICS_DB = Path(__file__).parent.parent / "data" / "metrics.db"


class MetricsCollector:
    """Collects and stores performance metrics in SQLite.

    Thread-safe. Batches writes for performance.
    """

    def __init__(self, db_path: Path = _METRICS_DB):
        self.db_path = db_path
        self._buffer: list[dict] = []
        self._lock = threading.Lock()
        self._initialized = False
        self._buffer_limit = 50  # Flush every 50 entries

    def _ensure_db(self):
        if self._initialized:
            return
        conn = sqlite3.connect(str(self.db_path))

        conn.executescript("""
            CREATE TABLE IF NOT EXISTS node_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                node TEXT NOT NULL,
                model TEXT,
                latency_ms REAL,
                tokens_per_sec REAL,
                success INTEGER DEFAULT 1,
                category TEXT,
                prompt_tokens INTEGER,
                output_tokens INTEGER
            );

            CREATE TABLE IF NOT EXISTS voice_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                transcription_ms REAL,
                correction_ms REAL,
                tts_ms REAL,
                cache_hit INTEGER DEFAULT 0,
                method TEXT,
                confidence REAL
            );

            CREATE TABLE IF NOT EXISTS trading_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                exchange TEXT,
                symbol TEXT,
                direction TEXT,
                entry_price REAL,
                exit_price REAL,
                pnl REAL,
                score REAL,
                duration_min REAL
            );

            CREATE TABLE IF NOT EXISTS agent_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                agent_name TEXT NOT NULL,
                task_type TEXT,
                duration_ms REAL,
                success INTEGER DEFAULT 1,
                tools_used INTEGER,
                confidence REAL
            );

            CREATE INDEX IF NOT EXISTS idx_node_metrics_ts ON node_metrics(timestamp);
            CREATE INDEX IF NOT EXISTS idx_node_metrics_node ON node_metrics(node);
            CREATE INDEX IF NOT EXISTS idx_voice_metrics_ts ON voice_metrics(timestamp);
            CREATE INDEX IF NOT EXISTS idx_trading_metrics_ts ON trading_metrics(timestamp);
            CREATE INDEX IF NOT EXISTS idx_agent_metrics_ts ON agent_metrics(timestamp);
        """)

        conn.commit()
        conn.close()
        self._initialized = True

    def record_node_call(
        self,
        node: str,
        latency_ms: float,
        success: bool = True,
        model: str = "",
        category: str = "",
        tokens_per_sec: float = 0,
        prompt_tokens: int = 0,
        output_tokens: int = 0,
    ):
        """Record a cluster node API call."""
        self._buffer_write("node_metrics", {
            "timestamp": time.time(),
            "node": node,
            "model": model,
            "latency_ms": latency_ms,
            "tokens_per_sec": tokens_per_sec,
            "success": 1 if success else 0,
            "category": category,
            "prompt_tokens": prompt_tokens,
            "output_tokens": output_tokens,
        })

    def record_voice(
        self,
        transcription_ms: float = 0,
        correction_ms: float = 0,
        tts_ms: float = 0,
        cache_hit: bool = False,
        method: str = "",
        confidence: float = 0,
    ):
        """Record a voice pipeline execution."""
        self._buffer_write("voice_metrics", {
            "timestamp": time.time(),
            "transcription_ms": transcription_ms,
            "correction_ms": correction_ms,
            "tts_ms": tts_ms,
            "cache_hit": 1 if cache_hit else 0,
            "method": method,
            "confidence": confidence,
        })

    def record_trade(
        self,
        exchange: str,
        symbol: str,
        direction: str,
        entry_price: float,
        exit_price: float = 0,
        pnl: float = 0,
        score: float = 0,
        duration_min: float = 0,
    ):
        """Record a trading operation."""
        self._buffer_write("trading_metrics", {
            "timestamp": time.time(),
            "exchange": exchange,
            "symbol": symbol,
            "direction": direction,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "pnl": pnl,
            "score": score,
            "duration_min": duration_min,
        })

    def record_agent(
        self,
        agent_name: str,
        duration_ms: float,
        success: bool = True,
        task_type: str = "",
        tools_used: int = 0,
        confidence: float = 0,
    ):
        """Record an agent execution."""
        self._buffer_write("agent_metrics", {
            "timestamp": time.time(),
            "agent_name": agent_name,
            "task_type": task_type,
            "duration_ms": duration_ms,
            "success": 1 if success else 0,
            "tools_used": tools_used,
            "confidence": confidence,
        })

    def _buffer_write(self, table: str, data: dict):
        """Buffer a write and flush when limit reached."""
        with self._lock:
            self._buffer.append({"table": table, "data": data})
            if len(self._buffer) >= self._buffer_limit:
                self._flush()

    def _flush(self):
        """Write buffered entries to database."""
        if not self._buffer:
            return
        self._ensure_db()
        entries = self._buffer.copy()
        self._buffer.clear()

        try:
            conn = sqlite3.connect(str(self.db_path))
            for entry in entries:
                table = entry["table"]
                data = entry["data"]
                cols = ", ".join(data.keys())
                placeholders = ", ".join(["?"] * len(data))
                conn.execute(
                    f"INSERT INTO {table} ({cols}) VALUES ({placeholders})",
                    list(data.values()),
                )
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.error("Metrics flush failed: %s", exc)

    def flush(self):
        """Force flush buffer to disk."""
        with self._lock:
            self._flush()

    def get_node_stats(self, hours: int = 24) -> dict:
        """Get aggregated node performance stats."""
        self._ensure_db()
        cutoff = time.time() - hours * 3600
        conn = sqlite3.connect(str(self.db_path))

        stats = {}
        rows = conn.execute("""
            SELECT node,
                   COUNT(*) as calls,
                   AVG(latency_ms) as avg_latency,
                   MAX(latency_ms) as max_latency,
                   AVG(tokens_per_sec) as avg_tps,
                   SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successes,
                   SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failures
            FROM node_metrics
            WHERE timestamp > ?
            GROUP BY node
            ORDER BY calls DESC
        """, (cutoff,)).fetchall()

        for row in rows:
            node = row[0]
            stats[node] = {
                "calls": row[1],
                "avg_latency_ms": round(row[2], 1),
                "max_latency_ms": round(row[3], 1),
                "avg_tokens_per_sec": round(row[4] or 0, 1),
                "success_rate": f"{row[5] / max(1, row[1]) * 100:.1f}%",
                "failures": row[6],
            }

        conn.close()
        return {"period_hours": hours, "nodes": stats}

    def get_voice_stats(self) -> dict:
        """Get voice pipeline performance stats."""
        self._ensure_db()
        conn = sqlite3.connect(str(self.db_path))

        row = conn.execute("""
            SELECT COUNT(*) as total,
                   AVG(transcription_ms) as avg_stt,
                   AVG(correction_ms) as avg_corr,
                   AVG(tts_ms) as avg_tts,
                   SUM(cache_hit) as cache_hits,
                   AVG(confidence) as avg_confidence
            FROM voice_metrics
        """).fetchone()

        conn.close()

        if not row or row[0] == 0:
            return {"total": 0}

        return {
            "total_calls": row[0],
            "avg_stt_ms": round(row[1] or 0, 1),
            "avg_correction_ms": round(row[2] or 0, 1),
            "avg_tts_ms": round(row[3] or 0, 1),
            "cache_hit_rate": f"{row[4] / max(1, row[0]) * 100:.1f}%",
            "avg_confidence": round(row[5] or 0, 3),
        }

    def get_trading_stats(self) -> dict:
        """Get trading performance stats."""
        self._ensure_db()
        conn = sqlite3.connect(str(self.db_path))

        row = conn.execute("""
            SELECT COUNT(*) as total,
                   SUM(pnl) as total_pnl,
                   AVG(pnl) as avg_pnl,
                   SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
                   SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END) as losses,
                   AVG(score) as avg_score
            FROM trading_metrics
            WHERE exit_price > 0
        """).fetchone()

        conn.close()

        if not row or row[0] == 0:
            return {"total_trades": 0}

        return {
            "total_trades": row[0],
            "total_pnl": round(row[1] or 0, 2),
            "avg_pnl": round(row[2] or 0, 4),
            "win_rate": f"{row[3] / max(1, row[0]) * 100:.1f}%",
            "wins": row[3],
            "losses": row[4],
            "avg_signal_score": round(row[5] or 0, 1),
        }


# Global metrics collector
metrics = MetricsCollector()
