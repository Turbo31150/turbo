"""JARVIS Structured Logging — JSON format + Distributed tracing.

Provides:
- JSON-formatted log entries for machine parsing
- Trace IDs for distributed request tracking across nodes
- Log rotation with configurable limits
- Per-module log level control
- Performance metrics in log entries
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any

# ── Log directory ────────────────────────────────────────────────────────
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ── Trace ID context ────────────────────────────────────────────────────
_trace_local = threading.local()


def get_trace_id() -> str:
    """Get the current trace ID for distributed tracing."""
    return getattr(_trace_local, "trace_id", "")


def set_trace_id(trace_id: str | None = None) -> str:
    """Set a trace ID. Generates one if not provided."""
    tid = trace_id or uuid.uuid4().hex[:12]
    _trace_local.trace_id = tid
    return tid


def new_trace() -> str:
    """Start a new trace (for incoming requests)."""
    return set_trace_id()


# ── JSON Formatter ───────────────────────────────────────────────────────

class JSONFormatter(logging.Formatter):
    """Format log records as JSON lines for machine parsing."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": record.created,
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno,
        }

        # Add trace ID if available
        trace_id = get_trace_id()
        if trace_id:
            entry["trace_id"] = trace_id

        # Add extra fields
        if hasattr(record, "node"):
            entry["node"] = record.node
        if hasattr(record, "latency_ms"):
            entry["latency_ms"] = record.latency_ms
        if hasattr(record, "tool"):
            entry["tool"] = record.tool
        if hasattr(record, "agent"):
            entry["agent"] = record.agent

        # Add exception info
        if record.exc_info and record.exc_info[1]:
            entry["error"] = str(record.exc_info[1])
            entry["error_type"] = type(record.exc_info[1]).__name__

        return json.dumps(entry, default=str)


class CompactFormatter(logging.Formatter):
    """Compact human-readable format for console output."""

    LEVEL_COLORS = {
        "DEBUG": "\033[36m",    # Cyan
        "INFO": "\033[32m",     # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",    # Red
        "CRITICAL": "\033[41m", # Red BG
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.LEVEL_COLORS.get(record.levelname, "")
        trace = get_trace_id()
        trace_str = f" [{trace}]" if trace else ""

        ts = time.strftime("%H:%M:%S", time.localtime(record.created))
        ms = f".{int((record.created % 1) * 1000):03d}"

        return (
            f"{color}{ts}{ms} {record.levelname:7s}{self.RESET} "
            f"{record.name:25s}{trace_str} {record.getMessage()}"
        )


# ── Log helpers ──────────────────────────────────────────────────────────

def log_node_call(
    logger_: logging.Logger,
    node: str,
    latency_ms: float,
    success: bool = True,
    model: str = "",
    **extra,
):
    """Log a cluster node API call with structured metadata."""
    record_extra = {"node": node, "latency_ms": round(latency_ms, 1)}
    if model:
        record_extra["model"] = model

    if success:
        logger_.info(
            "%s call OK (%.0fms, model=%s)",
            node, latency_ms, model or "default",
            extra=record_extra,
        )
    else:
        logger_.warning(
            "%s call FAILED (%.0fms, model=%s)",
            node, latency_ms, model or "default",
            extra=record_extra,
        )


def log_tool_call(
    logger_: logging.Logger,
    tool_name: str,
    duration_ms: float,
    success: bool = True,
    **extra,
):
    """Log an MCP tool execution."""
    record_extra = {"tool": tool_name, "latency_ms": round(duration_ms, 1)}

    if success:
        logger_.debug(
            "Tool %s OK (%.0fms)",
            tool_name, duration_ms,
            extra=record_extra,
        )
    else:
        logger_.warning(
            "Tool %s FAILED (%.0fms)",
            tool_name, duration_ms,
            extra=record_extra,
        )


# ── Setup function ───────────────────────────────────────────────────────

def setup_logging(
    level: str = "INFO",
    json_file: bool = True,
    console: bool = True,
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
    module_levels: dict[str, str] | None = None,
) -> None:
    """Configure JARVIS structured logging.

    Args:
        level: Default log level
        json_file: Write JSON logs to file
        console: Write human-readable logs to console
        max_bytes: Max log file size before rotation
        backup_count: Number of rotated files to keep
        module_levels: Per-module log levels (e.g., {"jarvis.voice": "DEBUG"})
    """
    root = logging.getLogger("jarvis")
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers
    root.handlers.clear()

    if console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(CompactFormatter())
        console_handler.setLevel(logging.INFO)
        root.addHandler(console_handler)

    if json_file:
        json_path = LOG_DIR / "jarvis.jsonl"
        file_handler = logging.handlers.RotatingFileHandler(
            str(json_path),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(JSONFormatter())
        file_handler.setLevel(logging.DEBUG)
        root.addHandler(file_handler)

    # Set per-module levels
    if module_levels:
        for module, mod_level in module_levels.items():
            logging.getLogger(module).setLevel(getattr(logging, mod_level.upper()))

    root.info("JARVIS logging initialized (level=%s, json=%s, console=%s)", level, json_file, console)
