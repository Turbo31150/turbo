"""Predictive Log Analyzer — learns from historical log patterns to anticipate failures.

Scans .log files in ROOT/logs, extracts ERROR/CRITICAL/WARNING entries,
detects recurring patterns, and predicts likely upcoming failures based
on frequency + recency heuristics.

DB: ROOT/data/log_analysis.db
"""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


class LogAnalyzer:
    """Predictive log analyzer that learns from historical log patterns."""

    # Regex for structured log entries:
    #   2026-03-10 14:23:01 ... [ERROR] some message
    _LOG_RE = re.compile(
        r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*\[(ERROR|CRITICAL|WARNING)\]\s*(.*)"
    )

    # Used to normalize messages: strip numbers, hex IDs, UUIDs, PIDs, ports
    _NORMALIZE_RE = re.compile(
        r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"  # UUIDs
        r"|\b\d{4,}\b"       # long numbers (PIDs, ports, counts)
        r"|\b0x[0-9a-fA-F]+\b"  # hex addresses
        r"|\b\d+\.\d+\.\d+\.\d+\b"  # IP addresses
    )

    def __init__(self) -> None:
        self.ROOT = Path(__file__).resolve().parent.parent
        self.LOG_DIR = self.ROOT / "logs"
        self.DB_PATH = self.ROOT / "data" / "log_analysis.db"
        self._init_db()

    # ── Database ──────────────────────────────────────────────────────

    def _init_db(self) -> None:
        """Create tables if they don't exist."""
        self.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(self.DB_PATH))
        try:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS error_patterns (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern   TEXT UNIQUE,
                    count     INTEGER,
                    last_seen TEXT,
                    category  TEXT
                );
                CREATE TABLE IF NOT EXISTS predictions (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts              TEXT,
                    pattern         TEXT,
                    predicted_issue TEXT,
                    confidence      REAL,
                    resolved        INTEGER DEFAULT 0
                );
                """
            )
            con.commit()
        finally:
            con.close()

    def _db(self) -> sqlite3.Connection:
        """Return a fresh connection (short-lived, thread-safe)."""
        con = sqlite3.connect(str(self.DB_PATH))
        con.row_factory = sqlite3.Row
        return con

    # ── Pattern persistence ───────────────────────────────────────────

    def _save_pattern(self, pattern: str, category: str) -> None:
        """Upsert into error_patterns table."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        con = self._db()
        try:
            con.execute(
                """
                INSERT INTO error_patterns (pattern, count, last_seen, category)
                VALUES (?, 1, ?, ?)
                ON CONFLICT(pattern) DO UPDATE SET
                    count     = count + 1,
                    last_seen = excluded.last_seen,
                    category  = excluded.category
                """,
                (pattern, now, category),
            )
            con.commit()
        finally:
            con.close()

    def _save_prediction(self, pattern: str, predicted_issue: str, confidence: float) -> None:
        """Insert into predictions table."""
        now = datetime.utcnow().isoformat(timespec="seconds")
        con = self._db()
        try:
            con.execute(
                "INSERT INTO predictions (ts, pattern, predicted_issue, confidence) VALUES (?, ?, ?, ?)",
                (now, pattern, predicted_issue, confidence),
            )
            con.commit()
        finally:
            con.close()

    # ── Log scanning ──────────────────────────────────────────────────

    def _scan_logs(self, hours: int) -> list[dict[str, Any]]:
        """Parse all .log files and return entries within the last *hours*."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        entries: list[dict[str, Any]] = []

        if not self.LOG_DIR.exists():
            return entries

        for log_file in self.LOG_DIR.glob("*.log"):
            try:
                text = log_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            for line in text.splitlines():
                m = self._LOG_RE.search(line)
                if not m:
                    continue
                try:
                    ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    continue
                if ts < cutoff:
                    continue
                entries.append(
                    {
                        "ts": ts,
                        "level": m.group(2),
                        "message": m.group(3).strip(),
                        "file": log_file.name,
                    }
                )

        return entries

    def _normalize(self, msg: str) -> str:
        """Strip variable parts (IDs, numbers, IPs) to group similar messages."""
        return self._NORMALIZE_RE.sub("<N>", msg).strip()

    # ── Public API ────────────────────────────────────────────────────

    def analyze_recent(self, hours: int = 1) -> dict[str, Any]:
        """Scan log files for the last *hours* and return a summary."""
        entries = self._scan_logs(hours)

        errors = [e for e in entries if e["level"] == "ERROR"]
        warnings = [e for e in entries if e["level"] == "WARNING"]
        criticals = [e for e in entries if e["level"] == "CRITICAL"]

        # Top patterns
        pattern_counts: dict[str, int] = {}
        for e in entries:
            norm = self._normalize(e["message"])
            pattern_counts[norm] = pattern_counts.get(norm, 0) + 1

        top_patterns = sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        top_patterns_list = [{"pattern": p, "count": c} for p, c in top_patterns]

        # Trend: compare first half vs second half of the window
        trend = self._compute_trend_from_entries(entries, hours)

        return {
            "total_entries": len(entries),
            "errors": len(errors),
            "warnings": len(warnings),
            "criticals": len(criticals),
            "top_patterns": top_patterns_list,
            "trend": trend,
        }

    def detect_patterns(self) -> list[dict[str, Any]]:
        """Group similar error messages and return top 10 recurring patterns."""
        # Scan last 24 h for a meaningful window
        entries = self._scan_logs(hours=24)

        groups: dict[str, dict[str, Any]] = {}
        for e in entries:
            norm = self._normalize(e["message"])
            if norm not in groups:
                groups[norm] = {"pattern": norm, "count": 0, "last_seen": e["ts"], "category": e["level"]}
            groups[norm]["count"] += 1
            if e["ts"] > groups[norm]["last_seen"]:
                groups[norm]["last_seen"] = e["ts"]

        # Persist discovered patterns
        for g in groups.values():
            self._save_pattern(g["pattern"], g["category"])

        ranked = sorted(groups.values(), key=lambda x: x["count"], reverse=True)[:10]

        # Serialize datetimes
        for item in ranked:
            item["last_seen"] = item["last_seen"].isoformat(timespec="seconds")

        return ranked

    def predict_failures(self) -> list[dict[str, Any]]:
        """Predict likely upcoming failures based on pattern frequency + recency.

        Heuristic: if a pattern appeared 3+ times in the last hour **and** more
        occurrences fell in the last 15 min than in the previous 45 min, flag it
        as a predicted failure.
        """
        now = datetime.utcnow()
        entries_1h = self._scan_logs(hours=1)

        # Group by normalized pattern
        pattern_entries: dict[str, list[datetime]] = {}
        for e in entries_1h:
            norm = self._normalize(e["message"])
            pattern_entries.setdefault(norm, []).append(e["ts"])

        cutoff_15 = now - timedelta(minutes=15)
        predictions: list[dict[str, Any]] = []

        for pattern, timestamps in pattern_entries.items():
            if len(timestamps) < 3:
                continue

            recent_15 = sum(1 for t in timestamps if t >= cutoff_15)
            older_45 = len(timestamps) - recent_15

            # Accelerating?
            if recent_15 > older_45:
                confidence = min(0.95, 0.5 + 0.05 * len(timestamps))
                predicted_issue = f"Pattern accelerating ({recent_15} in last 15min vs {older_45} in previous 45min)"
                recommended_action = self._recommend_action(pattern)

                predictions.append(
                    {
                        "pattern": pattern,
                        "predicted_issue": predicted_issue,
                        "confidence": round(confidence, 2),
                        "recommended_action": recommended_action,
                    }
                )

                self._save_prediction(pattern, predicted_issue, confidence)

        # Sort by confidence descending
        predictions.sort(key=lambda x: x["confidence"], reverse=True)
        return predictions

    def get_trend(self, hours: int = 24) -> dict[str, Any]:
        """Compare error counts between recent period and an older period of the
        same duration.  Return trend information."""
        now = datetime.utcnow()
        recent_cutoff = now - timedelta(hours=hours)
        previous_cutoff = recent_cutoff - timedelta(hours=hours)

        recent_entries = self._scan_logs(hours=hours)
        recent_count = len(recent_entries)

        # For the previous period we need to scan 2*hours and subtract recent
        all_entries = self._scan_logs(hours=hours * 2)
        previous_count = len([
            e for e in all_entries
            if e["ts"] < recent_cutoff and e["ts"] >= previous_cutoff
        ])

        if previous_count == 0:
            change_pct = 0.0
            trend = "stable"
        else:
            change_pct = round(((recent_count - previous_count) / previous_count) * 100, 1)
            if change_pct <= -10:
                trend = "improving"
            elif change_pct >= 10:
                trend = "degrading"
            else:
                trend = "stable"

        return {
            "period_hours": hours,
            "recent_count": recent_count,
            "previous_count": previous_count,
            "trend": trend,
            "change_pct": change_pct,
        }

    # ── Helpers ────────────────────────────────────────────────────────

    def _compute_trend_from_entries(
        self, entries: list[dict[str, Any]], hours: int
    ) -> str:
        """Determine trend from a single batch of entries (first half vs second half)."""
        if not entries:
            return "stable"

        now = datetime.utcnow()
        midpoint = now - timedelta(hours=hours / 2)
        first_half = sum(1 for e in entries if e["ts"] < midpoint)
        second_half = len(entries) - first_half

        if first_half == 0:
            return "stable" if second_half == 0 else "degrading"

        change = ((second_half - first_half) / first_half) * 100
        if change <= -10:
            return "improving"
        elif change >= 10:
            return "degrading"
        return "stable"

    @staticmethod
    def _recommend_action(pattern: str) -> str:
        """Return a recommended action string based on pattern keywords."""
        p = pattern.lower()
        if "offline" in p or "connection" in p or "timeout" in p:
            return "Check node connectivity and restart if needed"
        if "doublon" in p or "duplicate" in p:
            return "Kill duplicate processes via singleton manager"
        if "memory" in p or "oom" in p:
            return "Investigate memory usage; consider restarting the service"
        if "disk" in p or "space" in p:
            return "Check disk space and run cleanup"
        if "gpu" in p or "cuda" in p or "vram" in p:
            return "Monitor GPU temperature and VRAM; unload unused models"
        if "permission" in p or "denied" in p:
            return "Check file/process permissions"
        return "Investigate and consider restarting the affected service"


# ── Singleton ─────────────────────────────────────────────────────────
log_analyzer = LogAnalyzer()
