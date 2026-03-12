"""JARVIS Test Configuration — Shared fixtures and mocks."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Cleanup mock pollution from test modules that inject into sys.modules
# ---------------------------------------------------------------------------
# Some test files (test_brain, test_orchestrator) use sys.modules.setdefault()
# to inject MagicMock modules before importing src code. This pollutes later
# test modules that import the same src modules and get the mock instead.

# Modules that test files may inject mocks for
_MOCK_TARGETS = {"src.config", "src.skills", "src.tools", "src.event_bus",
                 "src.cluster_startup", "claude_agent_sdk"}


@pytest.fixture(autouse=True, scope="module")
def _cleanup_mock_modules():
    """Remove MagicMock injections from sys.modules after each test module."""
    # Snapshot real modules before test module runs
    real_modules = {}
    for name in _MOCK_TARGETS:
        if name in sys.modules and not isinstance(sys.modules[name], MagicMock):
            real_modules[name] = sys.modules[name]
    yield
    # After test module: restore real modules or remove mocks
    for name in _MOCK_TARGETS:
        if name in sys.modules and isinstance(sys.modules[name], MagicMock):
            if name in real_modules:
                sys.modules[name] = real_modules[name]
            else:
                del sys.modules[name]


@pytest.fixture
def mock_httpx():
    """Mock httpx.AsyncClient for cluster calls."""
    with patch("httpx.AsyncClient") as mock_client:
        client = AsyncMock()
        mock_client.return_value.__aenter__ = AsyncMock(return_value=client)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        yield client


@pytest.fixture
def mock_config():
    """Provide a test configuration."""
    from src.config import JarvisConfig
    config = JarvisConfig()
    # Override for testing
    config.dry_run = True
    config.voice_cache_size = 10
    return config


@pytest.fixture
def sample_audio():
    """Generate sample audio data for voice tests."""
    import numpy as np
    # 1 second of 440Hz sine wave at 16kHz
    sr = 16000
    t = np.linspace(0, 1.0, sr, endpoint=False)
    audio = (np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)
    return audio


@pytest.fixture
def sample_silence():
    """Generate 1 second of silence."""
    import numpy as np
    return np.zeros(16000, dtype=np.int16)
