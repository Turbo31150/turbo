"""Tests for src/cowork_perplexity_executor.py — Perplexity code generation.

Covers: _build_prompt, _extract_code_from_response, _extract_file_path,
_validate_python_syntax, execute_task_with_perplexity.
Uses mocks for external calls.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from dataclasses import dataclass

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.cowork_perplexity_executor import (
    _build_prompt, _extract_code_from_response, _extract_file_path,
    _validate_python_syntax,
)


@dataclass
class FakeTask:
    id: str = "T001"
    title: str = "Test Task"
    description: str = "Build a logger module"
    category: str = "optimization"
    priority: int = 5
    estimated_duration_min: int = 10


# ===========================================================================
# _build_prompt
# ===========================================================================

class TestBuildPrompt:
    def test_contains_task_info(self):
        task = FakeTask()
        prompt = _build_prompt(task)
        assert "Test Task" in prompt
        assert "optimization" in prompt
        assert "Build a logger module" in prompt


# ===========================================================================
# _extract_code_from_response
# ===========================================================================

class TestExtractCode:
    def test_python_block(self):
        response = "Here is the code:\n```python\nimport os\nprint('hello')\n```\nDone."
        code = _extract_code_from_response(response)
        assert "import os" in code
        assert "print('hello')" in code

    def test_generic_block_with_python(self):
        response = "Code:\n```\nimport sys\ndef main(): pass\n```\n"
        code = _extract_code_from_response(response)
        assert "import sys" in code

    def test_no_code(self):
        response = "No code here, just text."
        code = _extract_code_from_response(response)
        assert code == ""

    def test_longest_block(self):
        response = (
            "```python\nshort\n```\n"
            "```python\nimport os\nimport sys\ndef main():\n    pass\n```\n"
        )
        code = _extract_code_from_response(response)
        assert "def main" in code


# ===========================================================================
# _extract_file_path
# ===========================================================================

class TestExtractFilePath:
    def test_found_in_response(self):
        task = FakeTask()
        response = "Save this to src/optimization/logger.py"
        path = _extract_file_path(task, response)
        assert path == "src/optimization/logger.py"

    def test_default_path(self):
        task = FakeTask(title="My Module", category="windows")
        response = "No file path mentioned."
        path = _extract_file_path(task, response)
        assert path.startswith("src/windows/")
        assert path.endswith(".py")


# ===========================================================================
# _validate_python_syntax
# ===========================================================================

class TestValidateSyntax:
    def test_valid(self):
        assert _validate_python_syntax("x = 1\nprint(x)") is True

    def test_invalid(self):
        assert _validate_python_syntax("def foo(:\n  pass") is False

    def test_empty(self):
        assert _validate_python_syntax("") is True


# ===========================================================================
# execute_task_with_perplexity (async, mocked)
# ===========================================================================

class TestExecuteTask:
    @pytest.mark.asyncio
    async def test_success(self, tmp_path):
        from src.cowork_perplexity_executor import execute_task_with_perplexity
        task = FakeTask()
        mock_response = "```python\nimport logging\nlogger = logging.getLogger('test')\n```\n"
        mock_tools = MagicMock()
        mock_tools.gemini_query = AsyncMock(return_value={"response": mock_response})
        with patch.dict("sys.modules", {"src.tools": mock_tools}), \
             patch("pathlib.Path.mkdir"), \
             patch("pathlib.Path.write_text"):
            result = await execute_task_with_perplexity(task)
        assert result["success"] is True
        assert result["lines_of_code"] >= 1

    @pytest.mark.asyncio
    async def test_no_code_in_response(self):
        from src.cowork_perplexity_executor import execute_task_with_perplexity
        task = FakeTask()
        mock_tools = MagicMock()
        mock_tools.gemini_query = AsyncMock(return_value={"response": "Just text, no code."})
        with patch.dict("sys.modules", {"src.tools": mock_tools}):
            result = await execute_task_with_perplexity(task)
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_import_error(self):
        from src.cowork_perplexity_executor import execute_task_with_perplexity
        task = FakeTask()
        with patch.dict("sys.modules", {"src.tools": None}):
            result = await execute_task_with_perplexity(task)
        assert result["success"] is False
