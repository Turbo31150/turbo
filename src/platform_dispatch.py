"""Dispatch automatique vers modules plateforme (linux_* ou win_*)."""
from __future__ import annotations

import importlib
import logging
import os

log = logging.getLogger(__name__)

IS_LINUX = os.name != "nt"
IS_WINDOWS = os.name == "nt"


class _NotImplementedStub:
    """Stub pour modules pas encore portés."""

    def __init__(self, domain: str, platform: str) -> None:
        self._domain = domain
        self._platform = platform
        self.__name__ = f"{platform}_{domain}_stub"

    def __getattr__(self, name: str):
        raise NotImplementedError(
            f"{self._platform}_{self._domain}.{name}() pas encore implémenté. "
            f"Créer src/{self._platform}_{self._domain}.py"
        )


def get_platform_module(domain: str):
    """Retourne le module plateforme approprié ou un stub."""
    prefix = "linux" if IS_LINUX else "win"
    module_name = f"src.{prefix}_{domain}"
    try:
        return importlib.import_module(module_name)
    except ImportError:
        log.warning("Module %s pas trouvé, stub retourné", module_name)
        return _NotImplementedStub(domain, prefix)
