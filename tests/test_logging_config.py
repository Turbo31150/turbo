"""Tests for src/logging_config.py — JARVIS Structured Logging.

Covers: imports, trace ID management, JSONFormatter, CompactFormatter,
log_node_call, log_tool_call, setup_logging, log levels, formatters, handlers.
All external I/O (filesystem, network) is mocked.
"""

import sys
import json
import logging
import logging.handlers
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.logging_config import (
    JSONFormatter,
    CompactFormatter,
    get_trace_id,
    set_trace_id,
    new_trace,
    log_node_call,
    log_tool_call,
    setup_logging,
    LOG_DIR,
    _trace_local,
)


# ── Helpers ─────────────────────────────────────────────────────────────


def _make_mock_file_handler():
    """Create a MagicMock that behaves like a logging.Handler.

    The real logging machinery checks ``record.levelno >= handler.level``
    so ``.level`` must be a real int, not a MagicMock.
    """
    handler = MagicMock()
    handler.level = logging.DEBUG
    handler.filters = []
    handler.lock = MagicMock()
    return handler


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clear_trace():
    """Reset trace ID before and after each test."""
    if hasattr(_trace_local, "trace_id"):
        del _trace_local.trace_id
    yield
    if hasattr(_trace_local, "trace_id"):
        del _trace_local.trace_id


@pytest.fixture()
def json_formatter():
    return JSONFormatter()


@pytest.fixture()
def compact_formatter():
    return CompactFormatter()


@pytest.fixture()
def mock_logger():
    """Return a fresh logger with no handlers for patching method calls."""
    logger = logging.getLogger(f"test.logging_config.{id(object())}")
    logger.handlers.clear()
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    return logger


@pytest.fixture()
def capturing_logger():
    """Return a logger + captured records list for inspecting emitted records."""
    logger = logging.getLogger(f"test.capture.{id(object())}")
    logger.handlers.clear()
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    records: list[logging.LogRecord] = []

    class _ListHandler(logging.Handler):
        def emit(self, record):
            records.append(record)

    handler = _ListHandler()
    handler.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    return logger, records


# ── 1. Module imports ───────────────────────────────────────────────────


class TestImports:
    """Verify that all public symbols are importable."""

    def test_classes_importable(self):
        assert JSONFormatter is not None
        assert CompactFormatter is not None

    def test_functions_importable(self):
        assert callable(get_trace_id)
        assert callable(set_trace_id)
        assert callable(new_trace)
        assert callable(log_node_call)
        assert callable(log_tool_call)
        assert callable(setup_logging)

    def test_log_dir_is_path(self):
        assert isinstance(LOG_DIR, Path)


# ── 2. Trace ID management ─────────────────────────────────────────────


class TestTraceId:
    """Trace ID set/get/new operations."""

    def test_get_trace_id_default_empty(self):
        assert get_trace_id() == ""

    def test_set_trace_id_explicit(self):
        result = set_trace_id("abc123")
        assert result == "abc123"
        assert get_trace_id() == "abc123"

    def test_set_trace_id_auto_generates(self):
        result = set_trace_id()
        assert isinstance(result, str)
        assert len(result) == 12  # uuid4 hex[:12]

    def test_new_trace_returns_string(self):
        tid = new_trace()
        assert isinstance(tid, str)
        assert len(tid) == 12
        assert get_trace_id() == tid

    def test_set_trace_id_overwrite(self):
        set_trace_id("first")
        set_trace_id("second")
        assert get_trace_id() == "second"

    def test_trace_id_thread_isolation(self):
        """Trace IDs must be thread-local."""
        set_trace_id("main_thread")
        child_ids = []

        def worker():
            child_ids.append(get_trace_id())  # should be "" in new thread

        t = threading.Thread(target=worker)
        t.start()
        t.join()

        assert get_trace_id() == "main_thread"
        assert child_ids == [""]


# ── 3. JSONFormatter ────────────────────────────────────────────────────


class TestJSONFormatter:
    """JSON log formatting with structured fields."""

    def _make_record(self, msg="hello", level=logging.INFO, extras=None):
        record = logging.LogRecord(
            name="jarvis.test",
            level=level,
            pathname="test.py",
            lineno=42,
            msg=msg,
            args=(),
            exc_info=None,
        )
        for k, v in (extras or {}).items():
            setattr(record, k, v)
        return record

    def test_basic_json_output(self, json_formatter):
        record = self._make_record("test message")
        output = json_formatter.format(record)
        data = json.loads(output)

        assert data["msg"] == "test message"
        assert data["level"] == "INFO"
        assert data["logger"] == "jarvis.test"
        assert data["line"] == 42
        assert "ts" in data

    def test_trace_id_included_when_set(self, json_formatter):
        set_trace_id("trace_abc")
        record = self._make_record()
        data = json.loads(json_formatter.format(record))
        assert data["trace_id"] == "trace_abc"

    def test_trace_id_absent_when_unset(self, json_formatter):
        record = self._make_record()
        data = json.loads(json_formatter.format(record))
        assert "trace_id" not in data

    def test_extra_node_field(self, json_formatter):
        record = self._make_record(extras={"node": "M1"})
        data = json.loads(json_formatter.format(record))
        assert data["node"] == "M1"

    def test_extra_latency_field(self, json_formatter):
        record = self._make_record(extras={"latency_ms": 123.4})
        data = json.loads(json_formatter.format(record))
        assert data["latency_ms"] == 123.4

    def test_extra_tool_field(self, json_formatter):
        record = self._make_record(extras={"tool": "grep"})
        data = json.loads(json_formatter.format(record))
        assert data["tool"] == "grep"

    def test_extra_agent_field(self, json_formatter):
        record = self._make_record(extras={"agent": "ia-fast"})
        data = json.loads(json_formatter.format(record))
        assert data["agent"] == "ia-fast"

    def test_exception_info(self, json_formatter):
        try:
            raise ValueError("boom")
        except ValueError:
            import sys as _sys
            exc_info = _sys.exc_info()

        record = self._make_record()
        record.exc_info = exc_info
        data = json.loads(json_formatter.format(record))

        assert data["error"] == "boom"
        assert data["error_type"] == "ValueError"

    def test_no_exception_keys_when_clean(self, json_formatter):
        record = self._make_record()
        data = json.loads(json_formatter.format(record))
        assert "error" not in data
        assert "error_type" not in data

    def test_output_is_valid_json_single_line(self, json_formatter):
        record = self._make_record("multiword message here")
        output = json_formatter.format(record)
        assert "\n" not in output
        json.loads(output)  # must not raise


# ── 4. CompactFormatter ─────────────────────────────────────────────────


class TestCompactFormatter:
    """Human-readable console format with ANSI colors."""

    def _make_record(self, level=logging.INFO, msg="hello"):
        return logging.LogRecord(
            name="jarvis.test",
            level=level,
            pathname="test.py",
            lineno=1,
            msg=msg,
            args=(),
            exc_info=None,
        )

    def test_contains_message(self, compact_formatter):
        record = self._make_record(msg="visible text")
        output = compact_formatter.format(record)
        assert "visible text" in output

    def test_contains_level(self, compact_formatter):
        record = self._make_record(level=logging.WARNING)
        output = compact_formatter.format(record)
        assert "WARNING" in output

    def test_contains_logger_name(self, compact_formatter):
        record = self._make_record()
        output = compact_formatter.format(record)
        assert "jarvis.test" in output

    def test_trace_id_in_compact_output(self, compact_formatter):
        set_trace_id("tr99")
        record = self._make_record()
        output = compact_formatter.format(record)
        assert "[tr99]" in output

    def test_no_trace_bracket_when_unset(self, compact_formatter):
        record = self._make_record()
        output = compact_formatter.format(record)
        # No [xxx] trace bracket should appear
        assert "[tr" not in output

    def test_color_codes_present_for_error(self, compact_formatter):
        record = self._make_record(level=logging.ERROR)
        output = compact_formatter.format(record)
        assert "\033[31m" in output  # Red
        assert "\033[0m" in output   # Reset

    def test_level_colors_dict_complete(self):
        expected = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        assert set(CompactFormatter.LEVEL_COLORS.keys()) == expected


# ── 5. log_node_call ────────────────────────────────────────────────────


class TestLogNodeCall:
    """Structured logging helper for cluster node calls."""

    def test_success_logs_info(self, capturing_logger):
        logger, records = capturing_logger
        log_node_call(logger, node="M1", latency_ms=42.7, success=True, model="qwen3-8b")

        assert len(records) == 1
        rec = records[0]
        assert rec.levelno == logging.INFO
        msg = rec.getMessage()
        assert "M1" in msg
        assert "OK" in msg
        assert rec.node == "M1"
        assert rec.latency_ms == 42.7

    def test_failure_logs_warning(self, capturing_logger):
        logger, records = capturing_logger
        log_node_call(logger, node="M2", latency_ms=500.0, success=False)

        assert len(records) == 1
        rec = records[0]
        assert rec.levelno == logging.WARNING
        assert "FAILED" in rec.getMessage()
        assert rec.node == "M2"

    def test_model_default_label(self, capturing_logger):
        logger, records = capturing_logger
        log_node_call(logger, node="OL1", latency_ms=10.0)

        assert len(records) == 1
        assert "default" in records[0].getMessage()


# ── 6. log_tool_call ───────────────────────────────────────────────────


class TestLogToolCall:
    """Structured logging helper for MCP tool calls."""

    def test_success_logs_debug(self, capturing_logger):
        logger, records = capturing_logger
        log_tool_call(logger, tool_name="grep", duration_ms=5.3, success=True)

        assert len(records) == 1
        rec = records[0]
        assert rec.levelno == logging.DEBUG
        assert "grep" in rec.getMessage()
        assert "OK" in rec.getMessage()
        assert rec.tool == "grep"
        assert rec.latency_ms == 5.3

    def test_failure_logs_warning(self, capturing_logger):
        logger, records = capturing_logger
        log_tool_call(logger, tool_name="bash", duration_ms=999.9, success=False)

        assert len(records) == 1
        rec = records[0]
        assert rec.levelno == logging.WARNING
        assert "FAILED" in rec.getMessage()
        assert rec.tool == "bash"


# ── 7. setup_logging ───────────────────────────────────────────────────


class TestSetupLogging:
    """Full logging configuration via setup_logging()."""

    @pytest.fixture(autouse=True)
    def _clean_jarvis_logger(self):
        """Remove handlers from 'jarvis' logger before/after each test."""
        logger = logging.getLogger("jarvis")
        logger.handlers.clear()
        yield
        logger.handlers.clear()

    @patch("src.logging_config.logging.handlers.RotatingFileHandler")
    def test_default_adds_console_and_file(self, mock_rfh_cls):
        mock_rfh_cls.return_value = _make_mock_file_handler()
        setup_logging(level="DEBUG", json_file=True, console=True)

        root = logging.getLogger("jarvis")
        assert len(root.handlers) == 2
        has_stream = any(
            isinstance(h, logging.StreamHandler) and not isinstance(h, MagicMock)
            for h in root.handlers
        )
        assert has_stream

    @patch("src.logging_config.logging.handlers.RotatingFileHandler")
    def test_no_console_flag(self, mock_rfh_cls):
        mock_rfh_cls.return_value = _make_mock_file_handler()
        setup_logging(console=False, json_file=True)

        root = logging.getLogger("jarvis")
        real_stream_handlers = [
            h for h in root.handlers
            if isinstance(h, logging.StreamHandler) and not isinstance(h, MagicMock)
        ]
        assert len(real_stream_handlers) == 0

    @patch("src.logging_config.logging.handlers.RotatingFileHandler")
    def test_no_json_file_flag(self, mock_rfh_cls):
        setup_logging(console=True, json_file=False)
        mock_rfh_cls.assert_not_called()

    @patch("src.logging_config.logging.handlers.RotatingFileHandler")
    def test_level_setting(self, mock_rfh_cls):
        mock_rfh_cls.return_value = _make_mock_file_handler()
        setup_logging(level="WARNING")
        root = logging.getLogger("jarvis")
        assert root.level == logging.WARNING

    @patch("src.logging_config.logging.handlers.RotatingFileHandler")
    def test_module_levels(self, mock_rfh_cls):
        mock_rfh_cls.return_value = _make_mock_file_handler()
        setup_logging(module_levels={"jarvis.voice": "DEBUG", "jarvis.trading": "ERROR"})

        assert logging.getLogger("jarvis.voice").level == logging.DEBUG
        assert logging.getLogger("jarvis.trading").level == logging.ERROR

    @patch("src.logging_config.logging.handlers.RotatingFileHandler")
    def test_rotation_params_forwarded(self, mock_rfh_cls):
        mock_rfh_cls.return_value = _make_mock_file_handler()
        setup_logging(max_bytes=5_000_000, backup_count=3)

        mock_rfh_cls.assert_called_once()
        _, kwargs = mock_rfh_cls.call_args
        assert kwargs["maxBytes"] == 5_000_000
        assert kwargs["backupCount"] == 3

    @patch("src.logging_config.logging.handlers.RotatingFileHandler")
    def test_handlers_cleared_on_reconfig(self, mock_rfh_cls):
        mock_rfh_cls.return_value = _make_mock_file_handler()

        # First config
        setup_logging()
        root = logging.getLogger("jarvis")
        count_first = len(root.handlers)

        # Second config — fresh mock handler to avoid object identity issues
        mock_rfh_cls.return_value = _make_mock_file_handler()
        setup_logging()
        count_second = len(root.handlers)

        assert count_first == count_second  # no handler accumulation

    @patch("src.logging_config.logging.handlers.RotatingFileHandler")
    def test_console_handler_uses_compact_formatter(self, mock_rfh_cls):
        mock_rfh_cls.return_value = _make_mock_file_handler()
        setup_logging(console=True, json_file=False)
        root = logging.getLogger("jarvis")

        console_handlers = [
            h for h in root.handlers
            if isinstance(h, logging.StreamHandler) and not isinstance(h, MagicMock)
        ]
        assert len(console_handlers) == 1
        assert isinstance(console_handlers[0].formatter, CompactFormatter)

    @patch("src.logging_config.logging.handlers.RotatingFileHandler")
    def test_file_handler_uses_json_formatter(self, mock_rfh_cls):
        mock_handler = _make_mock_file_handler()
        mock_rfh_cls.return_value = mock_handler
        setup_logging(console=False, json_file=True)

        mock_handler.setFormatter.assert_called_once()
        formatter_arg = mock_handler.setFormatter.call_args[0][0]
        assert isinstance(formatter_arg, JSONFormatter)

    @patch("src.logging_config.logging.handlers.RotatingFileHandler")
    def test_invalid_level_defaults_to_info(self, mock_rfh_cls):
        mock_rfh_cls.return_value = _make_mock_file_handler()
        setup_logging(level="NONEXISTENT")
        root = logging.getLogger("jarvis")
        # getattr(logging, "NONEXISTENT", logging.INFO) -> logging.INFO
        assert root.level == logging.INFO

    @patch("src.logging_config.logging.handlers.RotatingFileHandler")
    def test_json_file_path_ends_with_jsonl(self, mock_rfh_cls):
        mock_rfh_cls.return_value = _make_mock_file_handler()
        setup_logging(console=False, json_file=True)

        mock_rfh_cls.assert_called_once()
        args, _ = mock_rfh_cls.call_args
        assert args[0].endswith("jarvis.jsonl")

    @patch("src.logging_config.logging.handlers.RotatingFileHandler")
    def test_file_handler_encoding_utf8(self, mock_rfh_cls):
        mock_rfh_cls.return_value = _make_mock_file_handler()
        setup_logging(console=False, json_file=True)

        _, kwargs = mock_rfh_cls.call_args
        assert kwargs["encoding"] == "utf-8"
