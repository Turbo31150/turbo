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


def test_linux_screen_imports():
    from src.linux_screen import capture_screen, capture_window
    assert callable(capture_screen)


def test_linux_services_imports():
    from src.linux_services import list_services, start_service, stop_service, service_status
    assert callable(list_services)


def test_platform_dispatch_resolves_screen():
    from src.platform_dispatch import get_platform_module
    mod = get_platform_module("screen")
    assert hasattr(mod, "capture_screen")


def test_platform_dispatch_resolves_services():
    from src.platform_dispatch import get_platform_module
    mod = get_platform_module("services")
    assert hasattr(mod, "list_services")


def test_linux_network_imports():
    from src.linux_network import get_interfaces, get_wifi_networks, ping_host, get_dns_servers
    assert callable(get_interfaces)
    assert callable(ping_host)

def test_linux_packages_imports():
    from src.linux_packages import list_installed, check_updates, search_package
    assert callable(list_installed)

def test_platform_dispatch_resolves_network():
    from src.platform_dispatch import get_platform_module
    mod = get_platform_module("network")
    assert hasattr(mod, "get_interfaces")

def test_platform_dispatch_resolves_packages():
    from src.platform_dispatch import get_platform_module
    mod = get_platform_module("packages")
    assert hasattr(mod, "list_installed")
