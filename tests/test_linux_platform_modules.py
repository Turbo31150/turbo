from __future__ import annotations


def test_linux_startup_imports():
    from src.linux_startup import list_startup_items, add_startup_item, remove_startup_item, is_enabled
    assert callable(list_startup_items)
    assert callable(add_startup_item)


def test_linux_display_imports():
    from src.linux_display import get_displays, get_brightness, set_brightness, get_resolution
    assert callable(get_displays)
    assert callable(get_resolution)


def test_platform_dispatch_resolves_startup():
    """platform_dispatch doit maintenant résoudre linux_startup au lieu d'un stub."""
    from src.platform_dispatch import get_platform_module
    mod = get_platform_module("startup")
    assert hasattr(mod, "list_startup_items")
    assert "stub" not in mod.__name__


def test_platform_dispatch_resolves_display():
    from src.platform_dispatch import get_platform_module
    mod = get_platform_module("display")
    assert hasattr(mod, "get_displays")
    assert "stub" not in mod.__name__
