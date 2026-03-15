from __future__ import annotations
import pytest
from unittest.mock import patch


def test_get_platform_module_linux():
    from src.platform_dispatch import get_platform_module
    mod = get_platform_module("sys")
    assert hasattr(mod, "__name__")
    assert "linux" in mod.__name__


def test_get_platform_module_missing_returns_stub():
    from src.platform_dispatch import get_platform_module
    stub = get_platform_module("zzznonexistent")
    with pytest.raises(NotImplementedError, match="pas encore implémenté"):
        stub.some_function()


def test_stub_message_includes_module_name():
    from src.platform_dispatch import get_platform_module
    stub = get_platform_module("display")
    with pytest.raises(NotImplementedError, match="linux_display"):
        stub.get_resolution()
