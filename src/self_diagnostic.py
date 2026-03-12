"""JARVIS Self-Diagnostic Engine — Analyzes own health and performance.

Checks response times, error rates, circuit breakers, scheduler health,
and queue backlog. Produces a scored report with actionable recommendations.

Usage:
    from src.self_diagnostic import self_diagnostic
    report = await self_diagnostic.diagnose()
"""

from __future__ import annotations

import logging
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("jarvis.self_diagnostic")

ROOT = Path(__file__).resolve().parent.parent
ETOILE_DB = ROOT / "data" / "etoile.db"
SCHEDULER_DB = ROOT / "data" / "scheduler.db"
TASK_QUEUE_DB = ROOT / "data" / "task_queue.db"


class SelfDiagnostic:
    """Self-diagnostic engine for JARVIS cluster health analysis."""

    # ── Main entry point ──────────────────────────────────────────────

    async def diagnose(self) -> dict:
        """Run full diagnostic. Returns report with health_score, issues, recommendations."""
        issues: list[dict] = []

        issues.extend(self._check_response_times())
        issues.extend(self._check_error_rates())
        issues.extend(self._check_circuit_breakers())
        issues.extend(self._check_scheduler_health())
        issues.extend(self._check_queue_backlog())

        recommendations = self._generate_recommendations(issues)

        # Compute health score: start at 100, deduct per issue severity
        score = 100
        for issue in issues:
            severity = issue.get("severity", "info")
            if severity == "critical":
                score -= 15
            elif severity == "warning":
                score -= 5
            elif severity == "info":
                score -= 1
        score = max(0, min(100, score))

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "health_score": score,
            "issues": issues,
            "recommendations": recommendations,
            "checks_run": 5,
        }

    # ── Check: Response Times ─────────────────────────────────────────

    def _check_response_times(self) -> list[dict]:
        """Query last 50 dispatches, flag nodes with high avg response time."""
        issues: list[dict] = []
        try:
            if not ETOILE_DB.exists():
                return []
            db = sqlite3.connect(str(ETOILE_DB))
            db.row_factory = sqlite3.Row

            rows = db.execute("""
                SELECT node, AVG(latency_ms) as avg_latency, COUNT(*) as cnt
                FROM dispatch_pipeline_log
                WHERE id > (SELECT COALESCE(MAX(id), 0) - 50 FROM dispatch_pipeline_log)
                  AND node IS NOT NULL AND node != ''
                GROUP BY node
            """).fetchall()
            db.close()

            for row in rows:
                node = row["node"]
                avg_ms = row["avg_latency"] or 0
                avg_s = avg_ms / 1000.0
                cnt = row["cnt"]

                if avg_s > 15:
                    issues.append({
                        "check": "response_time",
                        "node": node,
                        "severity": "critical",
                        "message": f"{node}: avg response {avg_s:.1f}s (>{15}s threshold) over {cnt} dispatches",
                        "value": round(avg_s, 2),
                    })
                elif avg_s > 5:
                    issues.append({
                        "check": "response_time",
                        "node": node,
                        "severity": "warning",
                        "message": f"{node}: avg response {avg_s:.1f}s (>{5}s threshold) over {cnt} dispatches",
                        "value": round(avg_s, 2),
                    })

        except sqlite3.Error as e:
            logger.warning("Response time check failed: %s", e)
        except Exception as e:
            logger.warning("Response time check unexpected error: %s", e)

        return issues

    # ── Check: Error Rates ────────────────────────────────────────────

    def _check_error_rates(self) -> list[dict]:
        """Query dispatches with quality < 0.3 in last hour. Flag high error rates."""
        issues: list[dict] = []
        try:
            if not ETOILE_DB.exists():
                return []
            db = sqlite3.connect(str(ETOILE_DB))
            db.row_factory = sqlite3.Row

            # Get total and low-quality dispatches in last hour
            row = db.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN quality < 0.3 THEN 1 ELSE 0 END) as low_quality
                FROM dispatch_pipeline_log
                WHERE timestamp > datetime('now', '-1 hour')
            """).fetchone()
            db.close()

            total = row["total"] or 0
            low_quality = row["low_quality"] or 0

            if total == 0:
                return []

            error_rate = low_quality / total
            pct = round(error_rate * 100, 1)

            if error_rate > 0.5:
                issues.append({
                    "check": "error_rate",
                    "severity": "critical",
                    "message": f"Error rate {pct}% ({low_quality}/{total} dispatches with quality<0.3 in last hour)",
                    "value": pct,
                })
            elif error_rate > 0.2:
                issues.append({
                    "check": "error_rate",
                    "severity": "warning",
                    "message": f"Error rate {pct}% ({low_quality}/{total} dispatches with quality<0.3 in last hour)",
                    "value": pct,
                })

        except sqlite3.Error as e:
            logger.warning("Error rate check failed: %s", e)
        except Exception as e:
            logger.warning("Error rate check unexpected error: %s", e)

        return issues

    # ── Check: Circuit Breakers ───────────────────────────────────────

    def _check_circuit_breakers(self) -> list[dict]:
        """Check which nodes have open circuit breakers via adaptive_router."""
        issues: list[dict] = []
        try:
            from src.adaptive_router import get_router

            router = get_router()
            for name, cb in router.circuits.items():
                if cb.state.value != "closed":
                    severity = "critical" if cb.state.value == "open" else "warning"
                    issues.append({
                        "check": "circuit_breaker",
                        "node": name,
                        "severity": severity,
                        "message": f"{name}: circuit breaker {cb.state.value} (failures={cb.failure_count})",
                        "value": cb.state.value,
                    })

        except ImportError:
            logger.warning("adaptive_router not available, skipping circuit breaker check")
        except Exception as e:
            logger.warning("Circuit breaker check failed: %s", e)

        return issues

    # ── Check: Scheduler Health ───────────────────────────────────────

    def _check_scheduler_health(self) -> list[dict]:
        """Query scheduler.db for jobs that haven't run in 2x their interval."""
        issues: list[dict] = []
        try:
            if not SCHEDULER_DB.exists():
                return []
            db = sqlite3.connect(str(SCHEDULER_DB))
            db.row_factory = sqlite3.Row

            rows = db.execute("""
                SELECT job_id, name, interval_s, last_run, enabled
                FROM jobs
                WHERE enabled = 1
            """).fetchall()
            db.close()

            now = time.time()
            for row in rows:
                job_id = row["job_id"]
                name = row["name"]
                interval_s = row["interval_s"] or 0
                last_run = row["last_run"] or 0

                if interval_s <= 0:
                    continue

                # If never run, flag if created long ago (use 2x interval as threshold)
                if last_run == 0:
                    issues.append({
                        "check": "scheduler_health",
                        "severity": "warning",
                        "message": f"Job '{name}' ({job_id}): never executed (interval={interval_s}s)",
                        "value": job_id,
                    })
                    continue

                elapsed = now - last_run
                threshold = interval_s * 2

                if elapsed > threshold:
                    overdue_s = round(elapsed - interval_s, 0)
                    issues.append({
                        "check": "scheduler_health",
                        "severity": "warning",
                        "message": f"Job '{name}' ({job_id}): stale, last ran {round(elapsed)}s ago (interval={interval_s}s, overdue by {overdue_s}s)",
                        "value": job_id,
                    })

        except sqlite3.Error as e:
            logger.warning("Scheduler health check failed: %s", e)
        except Exception as e:
            logger.warning("Scheduler health check unexpected error: %s", e)

        return issues

    # ── Check: Queue Backlog ──────────────────────────────────────────

    def _check_queue_backlog(self) -> list[dict]:
        """Query task_queue.db for pending tasks. Flag if backlog is large."""
        issues: list[dict] = []
        try:
            if not TASK_QUEUE_DB.exists():
                return []
            db = sqlite3.connect(str(TASK_QUEUE_DB))
            db.row_factory = sqlite3.Row

            row = db.execute("""
                SELECT COUNT(*) as pending
                FROM tasks
                WHERE status = 'pending'
            """).fetchone()
            db.close()

            pending = row["pending"] or 0

            if pending > 50:
                issues.append({
                    "check": "queue_backlog",
                    "severity": "critical",
                    "message": f"Task queue backlog: {pending} pending tasks (>50 threshold)",
                    "value": pending,
                })
            elif pending > 20:
                issues.append({
                    "check": "queue_backlog",
                    "severity": "warning",
                    "message": f"Task queue backlog: {pending} pending tasks (>20 threshold)",
                    "value": pending,
                })

        except sqlite3.Error as e:
            logger.warning("Queue backlog check failed: %s", e)
        except Exception as e:
            logger.warning("Queue backlog check unexpected error: %s", e)

        return issues

    # ── Recommendations ───────────────────────────────────────────────

    def _generate_recommendations(self, issues: list[dict]) -> list[str]:
        """Generate actionable recommendations based on detected issues."""
        recommendations: list[str] = []
        seen: set[str] = set()

        for issue in issues:
            check = issue.get("check", "")
            node = issue.get("node", "")
            severity = issue.get("severity", "info")
            key = f"{check}:{node}:{severity}"

            if key in seen:
                continue
            seen.add(key)

            if check == "response_time":
                if severity == "critical":
                    recommendations.append(
                        f"Restart node {node} — avg response >15s indicates severe degradation. "
                        f"Check GPU memory and model loading status."
                    )
                else:
                    recommendations.append(
                        f"Monitor node {node} — avg response >5s. "
                        f"Consider reducing concurrent requests or checking network latency."
                    )

            elif check == "error_rate":
                if severity == "critical":
                    recommendations.append(
                        "Critical error rate >50%. Run 'MAO check' to identify failing nodes. "
                        "Consider pausing dispatches until root cause is found."
                    )
                else:
                    recommendations.append(
                        "Elevated error rate >20%. Review recent dispatch logs for recurring patterns. "
                        "Check model availability on all nodes."
                    )

            elif check == "circuit_breaker":
                if severity == "critical":
                    recommendations.append(
                        f"Reset circuit breaker for {node} — currently OPEN. "
                        f"Verify node is responsive with health check, then restart if needed."
                    )
                else:
                    recommendations.append(
                        f"Circuit breaker for {node} is HALF_OPEN — node is recovering. "
                        f"Monitor for stability before increasing load."
                    )

            elif check == "scheduler_health":
                recommendations.append(
                    f"Stale scheduler job detected. Restart the scheduler or check "
                    f"automation_hub health. Jobs may need re-registration."
                )

            elif check == "queue_backlog":
                if severity == "critical":
                    recommendations.append(
                        "Task queue critically backed up (>50 pending). "
                        "Clear stale tasks with /api/queue/cancel or increase worker throughput."
                    )
                else:
                    recommendations.append(
                        "Task queue growing (>20 pending). "
                        "Check if queue processor is running. Consider draining old tasks."
                    )

        if not issues:
            recommendations.append("All checks passed. System is healthy.")

        return recommendations


# Singleton
self_diagnostic = SelfDiagnostic()
