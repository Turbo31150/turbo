"""Shadow Copy Manager — Linux neutral placeholder.
Originally for Windows VSS (Volume Shadow Copy).
"""
from __future__ import annotations
import logging
from typing import Any

__all__ = ["ShadowCopyManager"]

logger = logging.getLogger("jarvis.shadow_copy_manager")

class ShadowCopyManager:
    """Linux placeholder for Windows VSS."""

    def list_shadow_copies(self) -> list[dict[str, Any]]:
        """No VSS on Linux. Returns empty list."""
        return []

    def create_shadow_copy(self, volume: str = "C:/") -> bool:
        """Not supported on Linux."""
        logger.warning("Shadow Copy (VSS) is not supported on Linux.")
        return False

shadow_copy_manager = ShadowCopyManager()
