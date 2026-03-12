"""Tests for src/printer_manager.py — Windows printer management.

Covers: PrinterInfo, PrintEvent, PrinterManager (list_printers, _get_default_name,
get_default, get_queue, search, get_events, get_stats), printer_manager singleton.
All subprocess calls are mocked.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.printer_manager import (
    PrinterInfo, PrintEvent, PrinterManager, printer_manager,
)


# ===========================================================================
# Dataclasses
# ===========================================================================

class TestPrinterInfo:
    def test_defaults(self):
        p = PrinterInfo(name="HP LaserJet")
        assert p.port == ""
        assert p.driver == ""
        assert p.is_default is False
        assert p.is_network is False


class TestPrintEvent:
    def test_defaults(self):
        e = PrintEvent(action="list")
        assert e.printer == ""
        assert e.success is True
        assert e.timestamp > 0


# ===========================================================================
# PrinterManager — list_printers (mocked)
# ===========================================================================

PRINTERS_JSON = json.dumps([
    {"Name": "HP LaserJet", "PortName": "USB001", "DriverName": "HP Driver",
     "PrinterStatus": "Normal", "Type": "Local"},
    {"Name": "PDF Printer", "PortName": "PORTPROMPT:", "DriverName": "Microsoft Print to PDF",
     "PrinterStatus": "Normal", "Type": "Local"},
])


class TestListPrinters:
    def test_parses_printers(self):
        pm = PrinterManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = PRINTERS_JSON
        mock_default = MagicMock()
        mock_default.returncode = 0
        mock_default.stdout = "HP LaserJet"
        with patch("subprocess.run", side_effect=[mock_result, mock_default]):
            printers = pm.list_printers()
        assert len(printers) == 2
        assert printers[0]["name"] == "HP LaserJet"
        assert printers[0]["is_default"] is True
        assert printers[1]["is_default"] is False

    def test_single_printer_dict(self):
        pm = PrinterManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            {"Name": "Printer1", "PortName": "P1", "DriverName": "D1",
             "PrinterStatus": "Normal", "Type": "Local"})
        mock_default = MagicMock()
        mock_default.returncode = 0
        mock_default.stdout = ""
        with patch("subprocess.run", side_effect=[mock_result, mock_default]):
            printers = pm.list_printers()
        assert len(printers) == 1

    def test_exception_falls_back_to_wmic(self):
        pm = PrinterManager()
        mock_wmic = MagicMock()
        mock_wmic.stdout = "TRUE,HP Driver,HP LaserJet,USB001\n"
        with patch("subprocess.run", side_effect=[Exception("fail"), mock_wmic]):
            printers = pm.list_printers()
        # May parse wmic output
        assert isinstance(printers, list)

    def test_records_event(self):
        pm = PrinterManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = PRINTERS_JSON
        mock_default = MagicMock()
        mock_default.returncode = 0
        mock_default.stdout = ""
        with patch("subprocess.run", side_effect=[mock_result, mock_default]):
            pm.list_printers()
        events = pm.get_events()
        assert len(events) >= 1
        assert events[0]["action"] == "list_printers"


# ===========================================================================
# PrinterManager — get_default
# ===========================================================================

class TestGetDefault:
    def test_get_default(self):
        pm = PrinterManager()
        with patch.object(pm, "list_printers", return_value=[
            {"name": "P1", "is_default": False},
            {"name": "P2", "is_default": True},
        ]):
            default = pm.get_default()
        assert default["name"] == "P2"

    def test_get_default_none(self):
        pm = PrinterManager()
        with patch.object(pm, "list_printers", return_value=[]):
            default = pm.get_default()
        assert default["name"] == "none"


# ===========================================================================
# PrinterManager — get_queue (mocked)
# ===========================================================================

QUEUE_JSON = json.dumps([
    {"Id": 1, "DocumentName": "Report.pdf", "UserName": "franc",
     "SubmittedTime": None, "JobStatus": "Printing", "Size": 1024},
])


class TestGetQueue:
    def test_parses_queue(self):
        pm = PrinterManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = QUEUE_JSON
        with patch("subprocess.run", return_value=mock_result):
            queue = pm.get_queue("HP LaserJet")
        assert len(queue) == 1
        assert queue[0]["document"] == "Report.pdf"
        assert queue[0]["id"] == 1

    def test_empty_queue(self):
        pm = PrinterManager()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        with patch("subprocess.run", return_value=mock_result):
            queue = pm.get_queue()
        assert queue == []

    def test_queue_exception(self):
        pm = PrinterManager()
        with patch("subprocess.run", side_effect=Exception("fail")):
            queue = pm.get_queue("P1")
        assert queue == []


# ===========================================================================
# PrinterManager — search
# ===========================================================================

class TestSearch:
    def test_search(self):
        pm = PrinterManager()
        with patch.object(pm, "list_printers", return_value=[
            {"name": "HP LaserJet", "port": "USB"},
            {"name": "PDF Printer", "port": "PORT"},
        ]):
            results = pm.search("hp")
        assert len(results) == 1
        assert results[0]["name"] == "HP LaserJet"

    def test_search_no_match(self):
        pm = PrinterManager()
        with patch.object(pm, "list_printers", return_value=[
            {"name": "Printer1"},
        ]):
            results = pm.search("epson")
        assert results == []


# ===========================================================================
# PrinterManager — events / stats
# ===========================================================================

class TestEventsAndStats:
    def test_events_empty(self):
        pm = PrinterManager()
        assert pm.get_events() == []

    def test_events_recorded(self):
        pm = PrinterManager()
        pm._record("test", "P1", True, "detail")
        events = pm.get_events()
        assert len(events) == 1
        assert events[0]["action"] == "test"
        assert events[0]["printer"] == "P1"

    def test_stats(self):
        pm = PrinterManager()
        with patch.object(pm, "list_printers", return_value=[
            {"name": "P1", "is_default": True},
        ]):
            stats = pm.get_stats()
        assert stats["total_printers"] == 1
        assert stats["default_printer"] == "P1"


# ===========================================================================
# Singleton
# ===========================================================================

class TestSingleton:
    def test_exists(self):
        assert printer_manager is not None
        assert isinstance(printer_manager, PrinterManager)
