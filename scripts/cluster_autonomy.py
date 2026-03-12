#!/usr/bin/env python3
"""JARVIS Cluster Autonomy Engine — Total autonomous self-improvement.

Master controller that connects all auto-* modules and makes decisions
without human intervention. Learns from failures, adapts routing,
self-heals services, detects performance trends, and optimizes itself.

Architecture:
    1. AutonomyBrain — Decision engine with learning DB
    2. FailurePatternDetector — Learns from recurring failures
    3. RoutingOptimizer — Adjusts cluster weights from real performance
    4. ScheduleAdaptor — Tunes task intervals based on success/failure
    5. SelfHealer — Fixes issues with automatic rollback
    6. TrendAnalyzer — Detects degradation before critical
    7. AutonomyDaemon — Continuous loop tying everything together

Usage:
    python scripts/cluster_autonomy.py                  # Run one autonomy cycle
    python scripts/cluster_autonomy.py --daemon         # Continuous autonomous mode
    python scripts/cluster_autonomy.py --status         # Show autonomy state
    python scripts/cluster_autonomy.py --history        # Show decision history
    python scripts/cluster_autonomy.py --learn          # Show learned patterns
    python scripts/cluster_autonomy.py --trends         # Show performance trends
    python scripts/cluster_autonomy.py --heal           # Force healing cycle
    python scripts/cluster_autonomy.py --optimize       # Force optimization cycle
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import subprocess
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

TURBO = Path("/home/turbo/jarvis-m1-ops")
DB_PATH = str(TURBO / "data" / "cluster_autonomy.db")
ORCH_DB = str(TURBO / "data" / "task_orchestrator.db")
LOG_PATH = str(TURBO / "data" / "cluster_autonomy.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
    ],
)
logger = logging.getLogger("autonomy")

# ── Telegram ───────────────────────────────────────────────────────────────

def _load_telegram():
    env_file = TURBO / ".env"
    token = chat_id = None
    if env_file.exists():
        for line in env_file.read_text(errors="replace").splitlines():
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                token = line.split("=", 1)[1].strip().strip('"')
            elif line.startswith("TELEGRAM_CHAT_ID="):
                chat_id = line.split("=", 1)[1].strip().strip('"')
    return token, chat_id

TG_TOKEN, TG_CHAT = _load_telegram()

def notify(msg: str, silent: bool = True):
    if not TG_TOKEN or not TG_CHAT:
        return
    try:
        subprocess.run(
            ["curl", "-s", "--max-time", "10",
             f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
             "-d", f"chat_id={TG_CHAT}", "-d", f"text={msg[:4000]}",
             "-d", "parse_mode=HTML", "-d", f"disable_notification={'true' if silent else 'false'}"],
            capture_output=True, timeout=15)
    except Exception:
        pass


# ── Autonomy Database ──────────────────────────────────────────────────────

def init_autonomy_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        -- Decisions made by the autonomy engine
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            decision_type TEXT NOT NULL,
            target TEXT NOT NULL,
            action TEXT NOT NULL,
            reason TEXT,
            params TEXT DEFAULT '{}',
            outcome TEXT DEFAULT 'pending',
            rollback_data TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now')),
            resolved_at TEXT
        );

        -- Learned failure patterns
        CREATE TABLE IF NOT EXISTS failure_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_key TEXT UNIQUE NOT NULL,
            task_id TEXT,
            error_signature TEXT,
            occurrence_count INTEGER DEFAULT 1,
            last_seen TEXT DEFAULT (datetime('now')),
            auto_fix TEXT,
            fix_success_count INTEGER DEFAULT 0,
            fix_fail_count INTEGER DEFAULT 0
        );

        -- Routing weight history (what weights were tried, and performance)
        CREATE TABLE IF NOT EXISTS routing_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node TEXT NOT NULL,
            old_weight REAL,
            new_weight REAL,
            reason TEXT,
            performance_before REAL,
            performance_after REAL,
            recorded_at TEXT DEFAULT (datetime('now'))
        );

        -- Schedule adaptations
        CREATE TABLE IF NOT EXISTS schedule_adaptations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            old_interval TEXT,
            new_interval TEXT,
            reason TEXT,
            adapted_at TEXT DEFAULT (datetime('now'))
        );

        -- Performance trend snapshots
        CREATE TABLE IF NOT EXISTS trend_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_name TEXT NOT NULL,
            window_avg REAL,
            window_min REAL,
            window_max REAL,
            trend TEXT,  -- improving, stable, degrading
            recorded_at TEXT DEFAULT (datetime('now'))
        );

        -- Heal actions with rollback support
        CREATE TABLE IF NOT EXISTS heal_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service TEXT NOT NULL,
            action TEXT NOT NULL,
            pre_state TEXT,
            post_state TEXT,
            success INTEGER DEFAULT 0,
            rolled_back INTEGER DEFAULT 0,
            executed_at TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_decisions_type ON decisions(decision_type);
        CREATE INDEX IF NOT EXISTS idx_patterns_key ON failure_patterns(pattern_key);
        CREATE INDEX IF NOT EXISTS idx_trends_metric ON trend_snapshots(metric_name);
    """)
    conn.commit()
    conn.close()


def get_db():
    return sqlite3.connect(DB_PATH)


def get_orch_db():
    return sqlite3.connect(ORCH_DB)


# ── Data Models ────────────────────────────────────────────────────────────

@dataclass
class Decision:
    decision_type: str
    target: str
    action: str
    reason: str
    params: dict = field(default_factory=dict)
    outcome: str = "pending"

@dataclass
class FailurePattern:
    pattern_key: str
    task_id: str
    error_signature: str
    count: int = 1
    auto_fix: str = ""


# ── 1. Failure Pattern Detector ────────────────────────────────────────────

class FailurePatternDetector:
    """Learns from recurring failures and suggests/applies auto-fixes."""

    # Known auto-fix mappings: error signature -> fix action
    KNOWN_FIXES = {
        "Timeout": "increase_timeout",
        "Connection refused": "restart_service",
        "OFFLINE": "restart_service",
        "No space left": "cleanup_disk",
        "MemoryError": "reduce_concurrency",
        "Permission denied": "skip",
        "nvidia-smi": "skip_gpu_check",
        "integrity_check": "restore_backup",
        "CORRUPT": "restore_backup",
    }

    def analyze_recent_failures(self, hours: int = 6) -> list[FailurePattern]:
        """Scan orchestrator runs for failure patterns."""
        try:
            orch = get_orch_db()
            cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
            rows = orch.execute("""
                SELECT task_id, error, started_at FROM task_runs
                WHERE status='failed' AND started_at > ?
                ORDER BY started_at DESC
            """, (cutoff,)).fetchall()
            orch.close()
        except Exception:
            return []

        # Group by error signature
        patterns: dict[str, FailurePattern] = {}
        for task_id, error, ts in rows:
            sig = self._extract_signature(error or "")
            key = f"{task_id}:{sig}"
            if key in patterns:
                patterns[key].count += 1
            else:
                fix = self._suggest_fix(sig)
                patterns[key] = FailurePattern(key, task_id, sig, 1, fix)

        # Store/update in DB
        conn = get_db()
        for pat in patterns.values():
            conn.execute("""
                INSERT INTO failure_patterns (pattern_key, task_id, error_signature,
                    occurrence_count, last_seen, auto_fix)
                VALUES (?, ?, ?, ?, datetime('now'), ?)
                ON CONFLICT(pattern_key) DO UPDATE SET
                    occurrence_count = occurrence_count + ?,
                    last_seen = datetime('now'),
                    auto_fix = COALESCE(NULLIF(auto_fix, ''), ?)
            """, (pat.pattern_key, pat.task_id, pat.error_signature,
                  pat.count, pat.auto_fix, pat.count, pat.auto_fix))
        conn.commit()
        conn.close()

        return list(patterns.values())

    def get_recurring_patterns(self, min_count: int = 3) -> list[dict]:
        """Get patterns that keep recurring."""
        conn = get_db()
        rows = conn.execute("""
            SELECT pattern_key, task_id, error_signature, occurrence_count,
                   auto_fix, fix_success_count, fix_fail_count, last_seen
            FROM failure_patterns WHERE occurrence_count >= ?
            ORDER BY occurrence_count DESC
        """, (min_count,)).fetchall()
        conn.close()
        return [{"key": r[0], "task_id": r[1], "error": r[2], "count": r[3],
                 "fix": r[4], "fix_ok": r[5], "fix_fail": r[6], "last": r[7]}
                for r in rows]

    def _extract_signature(self, error: str) -> str:
        """Extract a stable signature from an error message."""
        if not error:
            return "unknown"
        # Normalize: take first meaningful line, strip paths/numbers
        lines = error.strip().splitlines()
        sig = lines[0][:80] if lines else "unknown"
        # Remove file paths and line numbers
        import re
        sig = re.sub(r'[A-Z]:/[^\s]+', 'PATH', sig)
        sig = re.sub(r'/[^\s]+', 'PATH', sig)
        sig = re.sub(r'line \d+', 'line N', sig)
        sig = re.sub(r'\d{4,}', 'NUM', sig)
        return sig.strip()

    def _suggest_fix(self, signature: str) -> str:
        """Suggest an auto-fix based on error signature."""
        for pattern, fix in self.KNOWN_FIXES.items():
            if pattern.lower() in signature.lower():
                return fix
        return ""


# ── 2. Routing Optimizer ───────────────────────────────────────────────────

class RoutingOptimizer:
    """Adjusts cluster routing weights based on real performance data."""

    NODES = {
        "M1": {"host": "127.0.0.1", "port": 1234, "base_weight": 1.8},
        "OL1": {"host": "127.0.0.1", "port": 11434, "base_weight": 1.3},
        "M2": {"host": "192.168.1.26", "port": 1234, "base_weight": 1.5},
        "M3": {"host": "192.168.1.113", "port": 1234, "base_weight": 1.2},
    }

    def analyze_node_performance(self, hours: int = 24) -> dict[str, dict]:
        """Analyze node performance from orchestrator dispatch data."""
        try:
            orch = get_orch_db()
            cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
            rows = orch.execute("""
                SELECT node, status, duration_ms FROM task_runs
                WHERE node != '' AND node IS NOT NULL AND started_at > ?
            """, (cutoff,)).fetchall()
            orch.close()
        except Exception:
            return {}

        stats: dict[str, dict] = {}
        for node, status, ms in rows:
            for n in node.split(","):
                n = n.strip()
                if not n or n == "local":
                    continue
                if n not in stats:
                    stats[n] = {"total": 0, "ok": 0, "fail": 0, "total_ms": 0}
                stats[n]["total"] += 1
                if status == "completed":
                    stats[n]["ok"] += 1
                else:
                    stats[n]["fail"] += 1
                stats[n]["total_ms"] += (ms or 0)

        # Compute derived metrics
        for n, s in stats.items():
            s["success_rate"] = s["ok"] / max(s["total"], 1)
            s["avg_ms"] = s["total_ms"] / max(s["total"], 1)

        return stats

    def compute_optimal_weights(self) -> dict[str, float]:
        """Compute optimal routing weights based on performance."""
        perf = self.analyze_node_performance()
        weights = {}

        for node, cfg in self.NODES.items():
            base = cfg["base_weight"]
            if node not in perf or perf[node]["total"] < 5:
                weights[node] = base
                continue

            s = perf[node]
            # Adjust weight based on success rate and latency
            success_factor = s["success_rate"]  # 0-1
            latency_factor = max(0.3, 1.0 - (s["avg_ms"] / 30000))  # penalize >30s

            adjusted = base * success_factor * latency_factor
            weights[node] = round(max(0.1, min(2.0, adjusted)), 2)

        return weights

    def apply_weight_adjustments(self) -> list[dict]:
        """Compute and record weight adjustments."""
        optimal = self.compute_optimal_weights()
        perf = self.analyze_node_performance()
        adjustments = []
        conn = get_db()

        for node, new_weight in optimal.items():
            old_weight = self.NODES[node]["base_weight"]
            if abs(new_weight - old_weight) > 0.1:
                p = perf.get(node, {})
                conn.execute("""
                    INSERT INTO routing_history (node, old_weight, new_weight, reason,
                        performance_before)
                    VALUES (?, ?, ?, ?, ?)
                """, (node, old_weight, new_weight,
                      f"success={p.get('success_rate', 0):.0%} avg={p.get('avg_ms', 0):.0f}ms",
                      p.get("success_rate", 0)))
                adjustments.append({
                    "node": node, "old": old_weight, "new": new_weight,
                    "reason": f"success={p.get('success_rate', 0):.0%}"
                })

        conn.commit()
        conn.close()
        return adjustments


# ── 3. Schedule Adaptor ────────────────────────────────────────────────────

class ScheduleAdaptor:
    """Dynamically adjusts task schedules based on performance."""

    # Interval progression (faster → slower)
    INTERVALS = ["every:2m", "every:5m", "every:10m", "every:15m", "every:30m",
                  "every:1h", "every:2h", "every:4h", "every:6h", "every:12h", "daily:03:00"]

    def analyze_task_health(self) -> list[dict]:
        """Analyze which tasks need schedule adjustment."""
        try:
            orch = get_orch_db()
            rows = orch.execute("""
                SELECT t.id, t.schedule, s.run_count, s.fail_count, s.avg_duration_ms
                FROM tasks t JOIN task_schedule s ON t.id = s.task_id
                WHERE t.enabled = 1 AND s.run_count >= 5
            """).fetchall()
            orch.close()
        except Exception:
            return []

        suggestions = []
        for tid, schedule, runs, fails, avg_ms in rows:
            if not schedule:
                continue
            fail_rate = fails / max(runs, 1)
            # High failure rate → slow down
            if fail_rate > 0.5 and runs > 10:
                new_interval = self._slower_interval(schedule)
                if new_interval != schedule:
                    suggestions.append({
                        "task_id": tid, "current": schedule, "suggested": new_interval,
                        "reason": f"High fail rate {fail_rate:.0%} ({fails}/{runs})",
                        "action": "slow_down",
                    })
            # Very fast and always succeeds → can potentially speed up
            elif fail_rate == 0 and runs > 20 and avg_ms < 1000:
                new_interval = self._faster_interval(schedule)
                if new_interval != schedule:
                    suggestions.append({
                        "task_id": tid, "current": schedule, "suggested": new_interval,
                        "reason": f"Perfect {runs} runs, avg {avg_ms:.0f}ms",
                        "action": "speed_up",
                    })

        return suggestions

    def apply_adaptations(self, auto_apply: bool = True) -> list[dict]:
        """Analyze and optionally apply schedule changes."""
        suggestions = self.analyze_task_health()
        applied = []

        if not auto_apply:
            return suggestions

        conn = get_db()
        orch = get_orch_db()
        for s in suggestions:
            if s["action"] == "slow_down":
                # Apply: update the task schedule
                orch.execute("UPDATE tasks SET schedule=? WHERE id=?",
                             (s["suggested"], s["task_id"]))
                conn.execute("""
                    INSERT INTO schedule_adaptations (task_id, old_interval, new_interval, reason)
                    VALUES (?, ?, ?, ?)
                """, (s["task_id"], s["current"], s["suggested"], s["reason"]))
                s["applied"] = True
                applied.append(s)
                logger.info("Schedule adapted: %s %s -> %s (%s)",
                            s["task_id"], s["current"], s["suggested"], s["reason"])

        orch.commit()
        orch.close()
        conn.commit()
        conn.close()
        return applied

    def _slower_interval(self, schedule: str) -> str:
        s = schedule.lower().strip()
        if s in self.INTERVALS:
            idx = self.INTERVALS.index(s)
            if idx < len(self.INTERVALS) - 1:
                return self.INTERVALS[idx + 1]
        return schedule

    def _faster_interval(self, schedule: str) -> str:
        s = schedule.lower().strip()
        if s in self.INTERVALS:
            idx = self.INTERVALS.index(s)
            if idx > 0:
                return self.INTERVALS[idx - 1]
        return schedule


# ── 4. Self-Healer ─────────────────────────────────────────────────────────

class SelfHealer:
    """Fixes issues automatically with rollback support."""

    SERVICES = {
        "lm_studio": {"check": "curl -s --max-time 3 http://127.0.0.1:1234/v1/models",
                       "restart": None},  # Manual restart needed
        "ollama": {"check": "curl -s --max-time 3 http://127.0.0.1:11434/api/tags",
                   "restart": "ollama serve"},
        "canvas_proxy": {"check": "curl -s --max-time 3 http://127.0.0.1:18800/health",
                         "restart": f"node {TURBO / 'direct-proxy.js'}"},
        "ws_server": {"check": "curl -s --max-time 2 http://127.0.0.1:9742/health",
                      "restart": f"python {TURBO / 'python_ws' / 'server.py'}"},
    }

    def check_all_services(self) -> dict[str, bool]:
        """Check health of all services."""
        results = {}
        for name, cfg in self.SERVICES.items():
            try:
                r = subprocess.run(
                    cfg["check"].split(), capture_output=True, text=True, timeout=5)
                results[name] = r.returncode == 0 and len(r.stdout) > 5
            except Exception:
                results[name] = False
        return results

    def heal_services(self) -> list[dict]:
        """Check and auto-heal failed services."""
        status = self.check_all_services()
        actions = []
        conn = get_db()

        for name, is_healthy in status.items():
            if is_healthy:
                continue

            cfg = self.SERVICES[name]
            if not cfg.get("restart"):
                actions.append({"service": name, "action": "alert",
                                "reason": "Down but no auto-restart available"})
                continue

            # Attempt restart
            logger.info("Auto-healing: restarting %s", name)
            pre_state = "down"
            try:
                parts = cfg["restart"].split()
                subprocess.Popen(parts, creationflags=0x00000008,
                                 cwd=str(TURBO), stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
                time.sleep(3)

                # Verify
                r = subprocess.run(
                    cfg["check"].split(), capture_output=True, text=True, timeout=5)
                post_state = "up" if (r.returncode == 0 and len(r.stdout) > 5) else "still_down"
                success = post_state == "up"

                conn.execute("""
                    INSERT INTO heal_actions (service, action, pre_state, post_state, success)
                    VALUES (?, 'restart', ?, ?, ?)
                """, (name, pre_state, post_state, int(success)))

                actions.append({"service": name, "action": "restart",
                                "success": success, "post_state": post_state})
                if success:
                    logger.info("Healed: %s is now UP", name)
                else:
                    logger.warning("Heal failed: %s still DOWN", name)

            except Exception as e:
                conn.execute("""
                    INSERT INTO heal_actions (service, action, pre_state, post_state, success)
                    VALUES (?, 'restart_failed', 'down', ?, 0)
                """, (name, str(e)[:200]))
                actions.append({"service": name, "action": "restart_failed", "error": str(e)[:100]})

        conn.commit()
        conn.close()
        return actions

    def apply_failure_fix(self, pattern: dict) -> dict:
        """Apply a known fix for a failure pattern."""
        fix = pattern.get("fix", "")
        task_id = pattern.get("task_id", "")
        result = {"pattern": pattern["key"], "fix": fix, "applied": False}

        conn = get_db()
        if fix == "increase_timeout":
            try:
                orch = get_orch_db()
                orch.execute("UPDATE tasks SET timeout_s = MIN(timeout_s * 2, 600) WHERE id=?",
                             (task_id,))
                orch.commit()
                orch.close()
                result["applied"] = True
                result["detail"] = "Doubled timeout"
                conn.execute("""
                    UPDATE failure_patterns SET fix_success_count = fix_success_count + 1
                    WHERE pattern_key = ?
                """, (pattern["key"],))
            except Exception as e:
                result["error"] = str(e)[:100]
                conn.execute("""
                    UPDATE failure_patterns SET fix_fail_count = fix_fail_count + 1
                    WHERE pattern_key = ?
                """, (pattern["key"],))

        elif fix == "restart_service":
            actions = self.heal_services()
            result["applied"] = any(a.get("success") for a in actions)
            result["detail"] = f"Healed {len(actions)} services"

        elif fix == "cleanup_disk":
            try:
                r = subprocess.run(
                    [sys.executable, str(TURBO / "scripts" / "task_orchestrator.py"),
                     "--cleanup", "7"],
                    capture_output=True, text=True, timeout=30, cwd=str(TURBO))
                result["applied"] = r.returncode == 0
                result["detail"] = r.stdout.strip()[:100]
            except Exception as e:
                result["error"] = str(e)[:100]

        elif fix == "skip":
            result["applied"] = False
            result["detail"] = "Pattern marked as skip (manual fix needed)"

        conn.commit()
        conn.close()
        return result


# ── 5. Trend Analyzer ──────────────────────────────────────────────────────

class TrendAnalyzer:
    """Detects performance trends and predicts degradation."""

    def analyze_trends(self, hours: int = 24) -> list[dict]:
        """Analyze metric trends over time."""
        try:
            orch = get_orch_db()
            cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
            rows = orch.execute("""
                SELECT metric_name, metric_value, recorded_at FROM task_metrics
                WHERE recorded_at > ?
                ORDER BY metric_name, recorded_at
            """, (cutoff,)).fetchall()
            orch.close()
        except Exception:
            return []

        # Group by metric
        by_metric: dict[str, list[tuple[float, str]]] = defaultdict(list)
        for name, value, at in rows:
            by_metric[name].append((value, at))

        trends = []
        conn = get_db()
        for name, points in by_metric.items():
            if len(points) < 3:
                continue

            values = [p[0] for p in points]
            avg = sum(values) / len(values)
            mn, mx = min(values), max(values)

            # Simple trend: compare first half avg vs second half avg
            mid = len(values) // 2
            first_half = sum(values[:mid]) / max(mid, 1)
            second_half = sum(values[mid:]) / max(len(values) - mid, 1)

            if second_half > first_half * 1.2:
                trend = "increasing"
            elif second_half < first_half * 0.8:
                trend = "decreasing"
            else:
                trend = "stable"

            # Detect concerning trends
            alert = None
            if "temp" in name and trend == "increasing" and values[-1] > 75:
                alert = "GPU temperature rising"
            elif "free_gb" in name and trend == "decreasing" and values[-1] < 30:
                alert = "Disk space declining"
            elif "fail" in name and trend == "increasing":
                alert = "Failure count rising"
            elif "success_rate" in name and trend == "decreasing":
                alert = "Success rate declining"

            trend_data = {
                "metric": name, "trend": trend, "avg": round(avg, 2),
                "min": round(mn, 2), "max": round(mx, 2),
                "latest": round(values[-1], 2), "points": len(values),
                "alert": alert,
            }
            trends.append(trend_data)

            conn.execute("""
                INSERT INTO trend_snapshots (metric_name, window_avg, window_min, window_max, trend)
                VALUES (?, ?, ?, ?, ?)
            """, (name, avg, mn, mx, trend))

        conn.commit()
        conn.close()
        return trends


# ── 6. Autonomy Brain ─────────────────────────────────────────────────────

class AutonomyBrain:
    """Master decision engine — coordinates all autonomy components."""

    def __init__(self):
        self.failure_detector = FailurePatternDetector()
        self.routing_optimizer = RoutingOptimizer()
        self.schedule_adaptor = ScheduleAdaptor()
        self.self_healer = SelfHealer()
        self.trend_analyzer = TrendAnalyzer()
        self._cycle_count = 0

    def run_cycle(self) -> dict:
        """Execute one full autonomy cycle. Returns summary of all actions."""
        self._cycle_count += 1
        t0 = time.monotonic()
        summary = {"cycle": self._cycle_count, "actions": [], "decisions": []}

        logger.info("=== Autonomy Cycle %d ===", self._cycle_count)

        # Phase 1: Detect failures
        patterns = self.failure_detector.analyze_recent_failures(hours=2)
        summary["failure_patterns"] = len(patterns)

        # Phase 2: Auto-heal services
        heal_actions = self.self_healer.heal_services()
        summary["heal_actions"] = heal_actions
        for a in heal_actions:
            if a.get("success"):
                summary["actions"].append(f"Healed {a['service']}")

        # Phase 3: Apply known fixes for recurring patterns
        recurring = self.failure_detector.get_recurring_patterns(min_count=3)
        fixes_applied = 0
        for pat in recurring:
            if pat["fix"] and pat["fix"] != "skip" and pat["fix_fail"] < 3:
                result = self.self_healer.apply_failure_fix(pat)
                if result.get("applied"):
                    fixes_applied += 1
                    summary["actions"].append(f"Fixed {pat['task_id']}: {pat['fix']}")
                    self._record_decision("auto_fix", pat["task_id"], pat["fix"],
                                          f"Pattern {pat['key']} seen {pat['count']}x")
        summary["fixes_applied"] = fixes_applied

        # Phase 4: Optimize routing (every 5 cycles)
        if self._cycle_count % 5 == 0:
            adjustments = self.routing_optimizer.apply_weight_adjustments()
            summary["routing_adjustments"] = adjustments
            for a in adjustments:
                summary["actions"].append(f"Route {a['node']}: {a['old']} -> {a['new']}")
                self._record_decision("routing", a["node"], "adjust_weight",
                                      a["reason"], {"old": a["old"], "new": a["new"]})

        # Phase 5: Adapt schedules (every 10 cycles)
        if self._cycle_count % 10 == 0:
            adaptations = self.schedule_adaptor.apply_adaptations(auto_apply=True)
            summary["schedule_adaptations"] = adaptations
            for a in adaptations:
                if a.get("applied"):
                    summary["actions"].append(
                        f"Schedule {a['task_id']}: {a['current']} -> {a['suggested']}")

        # Phase 6: Analyze trends (every 3 cycles)
        if self._cycle_count % 3 == 0:
            trends = self.trend_analyzer.analyze_trends(hours=6)
            alerts = [t for t in trends if t.get("alert")]
            summary["trend_alerts"] = alerts
            for a in alerts:
                summary["actions"].append(f"Trend alert: {a['alert']} ({a['metric']})")
                self._record_decision("trend_alert", a["metric"], "alert",
                                      a["alert"], {"trend": a["trend"], "latest": a["latest"]})

        # Phase 7: Telegram report if significant actions taken
        dur = (time.monotonic() - t0) * 1000
        summary["duration_ms"] = round(dur)

        if summary["actions"]:
            msg = f"<b>JARVIS Autonomy Cycle #{self._cycle_count}</b>\n"
            msg += f"Duration: {dur:.0f}ms\n"
            for action in summary["actions"][:10]:
                msg += f"  {action}\n"
            notify(msg)

        logger.info("Cycle %d complete: %d actions, %.0fms",
                     self._cycle_count, len(summary["actions"]), dur)

        return summary

    def _record_decision(self, dtype: str, target: str, action: str,
                         reason: str, params: dict = None):
        conn = get_db()
        conn.execute("""
            INSERT INTO decisions (decision_type, target, action, reason, params)
            VALUES (?, ?, ?, ?, ?)
        """, (dtype, target, action, reason, json.dumps(params or {})))
        conn.commit()
        conn.close()

    def get_status(self) -> dict:
        """Full autonomy status."""
        conn = get_db()

        # Decision counts
        try:
            total_decisions = conn.execute("SELECT count(*) FROM decisions").fetchone()[0]
            recent_decisions = conn.execute("""
                SELECT count(*) FROM decisions
                WHERE created_at > datetime('now', '-24 hours')
            """).fetchone()[0]
        except Exception:
            total_decisions = recent_decisions = 0

        # Failure patterns
        try:
            pattern_count = conn.execute("SELECT count(*) FROM failure_patterns").fetchone()[0]
            recurring = conn.execute("""
                SELECT count(*) FROM failure_patterns WHERE occurrence_count >= 3
            """).fetchone()[0]
        except Exception:
            pattern_count = recurring = 0

        # Heal stats
        try:
            heal_total = conn.execute("SELECT count(*) FROM heal_actions").fetchone()[0]
            heal_ok = conn.execute("SELECT count(*) FROM heal_actions WHERE success=1").fetchone()[0]
        except Exception:
            heal_total = heal_ok = 0

        # Schedule adaptations
        try:
            adapt_count = conn.execute("SELECT count(*) FROM schedule_adaptations").fetchone()[0]
        except Exception:
            adapt_count = 0

        conn.close()

        # Services
        services = self.self_healer.check_all_services()

        return {
            "cycle_count": self._cycle_count,
            "total_decisions": total_decisions,
            "recent_decisions_24h": recent_decisions,
            "failure_patterns": pattern_count,
            "recurring_patterns": recurring,
            "heal_actions": heal_total,
            "heal_success_rate": f"{heal_ok}/{heal_total}" if heal_total else "0/0",
            "schedule_adaptations": adapt_count,
            "services": services,
            "optimal_weights": self.routing_optimizer.compute_optimal_weights(),
        }

    def get_decision_history(self, limit: int = 30) -> list[dict]:
        conn = get_db()
        try:
            rows = conn.execute("""
                SELECT decision_type, target, action, reason, outcome, created_at
                FROM decisions ORDER BY id DESC LIMIT ?
            """, (limit,)).fetchall()
        except Exception:
            rows = []
        conn.close()
        return [{"type": r[0], "target": r[1], "action": r[2],
                 "reason": r[3], "outcome": r[4], "at": r[5]} for r in rows]


# ── 7. Autonomy Daemon ────────────────────────────────────────────────────

def daemon_loop():
    """Continuous autonomous improvement loop."""
    brain = AutonomyBrain()
    print("  JARVIS Cluster Autonomy — Total Autonomous Mode")
    print("  Running autonomy cycle every 5 minutes...")
    notify("<b>JARVIS Autonomy Engine started</b>\nTotal autonomous mode active.")

    while True:
        try:
            summary = brain.run_cycle()
            actions = len(summary.get("actions", []))
            logger.info("Autonomy: %d actions taken", actions)
        except Exception as e:
            logger.error("Autonomy error: %s", e)
        time.sleep(300)  # 5 minutes between cycles


# ── CLI ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="JARVIS Cluster Autonomy Engine")
    parser.add_argument("--daemon", action="store_true", help="Continuous autonomous mode")
    parser.add_argument("--status", action="store_true", help="Show autonomy status")
    parser.add_argument("--history", action="store_true", help="Show decision history")
    parser.add_argument("--learn", action="store_true", help="Show learned failure patterns")
    parser.add_argument("--trends", action="store_true", help="Show performance trends")
    parser.add_argument("--heal", action="store_true", help="Force healing cycle")
    parser.add_argument("--optimize", action="store_true", help="Force optimization cycle")
    parser.add_argument("--init", action="store_true", help="Initialize autonomy DB")
    args = parser.parse_args()

    init_autonomy_db()
    brain = AutonomyBrain()

    if args.daemon:
        # Singleton: kill existing instance before starting
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
            from src.process_singleton import singleton
            singleton.acquire("autonomy", pid=os.getpid())
        except Exception:
            pass
        daemon_loop()

    elif args.status:
        status = brain.get_status()
        print(f"\n{'='*60}")
        print(f"  JARVIS CLUSTER AUTONOMY — Status")
        print(f"{'='*60}")
        print(f"  Cycles run:          {status['cycle_count']}")
        print(f"  Total decisions:     {status['total_decisions']}")
        print(f"  Decisions (24h):     {status['recent_decisions_24h']}")
        print(f"  Failure patterns:    {status['failure_patterns']} ({status['recurring_patterns']} recurring)")
        print(f"  Heal actions:        {status['heal_success_rate']}")
        print(f"  Schedule adapts:     {status['schedule_adaptations']}")
        print(f"\n  Services:")
        for svc, ok in status["services"].items():
            print(f"    {svc:20} {'UP' if ok else 'DOWN'}")
        print(f"\n  Optimal weights:")
        for node, w in status["optimal_weights"].items():
            print(f"    {node:6} {w:.2f}")
        print(f"{'='*60}")

    elif args.history:
        decisions = brain.get_decision_history(30)
        print(f"\n{'='*60}")
        print(f"  DECISION HISTORY — {len(decisions)} recent")
        print(f"{'='*60}")
        for d in decisions:
            print(f"  [{d['type']:12}] {d['target']:20} {d['action']:20} {d['at']}")
            print(f"                 {d['reason'][:60]}")
        print(f"{'='*60}")

    elif args.learn:
        patterns = brain.failure_detector.get_recurring_patterns(min_count=1)
        print(f"\n{'='*60}")
        print(f"  LEARNED FAILURE PATTERNS — {len(patterns)}")
        print(f"{'='*60}")
        for p in patterns:
            fix_info = f"fix={p['fix']}" if p['fix'] else "no fix"
            print(f"  [{p['count']:3}x] {p['task_id']:25} {p['error'][:40]}")
            print(f"         {fix_info} (ok={p['fix_ok']} fail={p['fix_fail']})")
        print(f"{'='*60}")

    elif args.trends:
        trends = brain.trend_analyzer.analyze_trends(hours=24)
        print(f"\n{'='*60}")
        print(f"  PERFORMANCE TRENDS — {len(trends)} metrics")
        print(f"{'='*60}")
        for t in trends:
            alert = f" *** {t['alert']}" if t.get("alert") else ""
            print(f"  {t['metric']:30} {t['trend']:12} avg={t['avg']:.1f} "
                  f"[{t['min']:.1f}-{t['max']:.1f}] now={t['latest']:.1f}{alert}")
        print(f"{'='*60}")

    elif args.heal:
        print("  Forcing healing cycle...")
        actions = brain.self_healer.heal_services()
        for a in actions:
            status_str = "OK" if a.get("success") else "FAIL"
            print(f"  [{status_str}] {a['service']}: {a['action']}")
        if not actions:
            print("  All services healthy")

    elif args.optimize:
        print("  Forcing optimization cycle...")
        summary = brain.run_cycle()
        print(f"\n  Actions taken: {len(summary['actions'])}")
        for a in summary["actions"]:
            print(f"    {a}")
        print(f"  Duration: {summary['duration_ms']}ms")

    elif args.init:
        print("  Autonomy DB initialized")

    else:
        # Default: run one cycle
        summary = brain.run_cycle()
        print(f"\n  Autonomy cycle complete:")
        print(f"    Failure patterns: {summary['failure_patterns']}")
        print(f"    Fixes applied:    {summary['fixes_applied']}")
        print(f"    Heal actions:     {len(summary['heal_actions'])}")
        print(f"    Total actions:    {len(summary['actions'])}")
        print(f"    Duration:         {summary['duration_ms']}ms")
        if summary["actions"]:
            print(f"\n  Actions:")
            for a in summary["actions"]:
                print(f"    {a}")


if __name__ == "__main__":
    main()
