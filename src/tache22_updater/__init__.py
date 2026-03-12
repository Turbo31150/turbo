"""
Tâche 22: Auto-Updater + Versioning System JARVIS
Package d'intégration pour mises à jour et gestion des versions
"""

from .auto_updater import (
    AutoUpdater,
    VersionComparer,
    ChangelogParser,
    IntegrityChecker,
    BackupManager,
    UpdateDatabase,
    GitHubReleaseManager
)

from .version_manager import (
    VersionManager,
    VersionDatabase,
    ChangelogGenerator,
    MigrationRunner,
    FeatureFlagManager,
    ComponentVersion,
    CompatibilityRule
)

__version__ = "1.0.0"
__author__ = "JARVIS Team"

__all__ = [
    # Auto-updater
    'AutoUpdater',
    'VersionComparer',
    'ChangelogParser',
    'IntegrityChecker',
    'BackupManager',
    'UpdateDatabase',
    'GitHubReleaseManager',
    
    # Version manager
    'VersionManager',
    'VersionDatabase',
    'ChangelogGenerator',
    'MigrationRunner',
    'FeatureFlagManager',
    'ComponentVersion',
    'CompatibilityRule'
]


def get_updater():
    """Factory pour créer une instance AutoUpdater"""
    return AutoUpdater()


def get_version_manager():
    """Factory pour créer une instance VersionManager"""
    return VersionManager()
