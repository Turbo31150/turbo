"""
JARVIS Tache 21: Point d'entrée principal
Lance le system tray avec notifications et monitoring.
"""

import sys
import logging
from pathlib import Path

# Ajoute le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tache21_systray.systray_manager import TrayManager
from tache21_systray.notification_center import NotificationCenter


def setup_logging():
    """Configure le logging."""
    log_dir = Path("/home/turbo/jarvis-m1-ops/logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "jarvis_tray.log"),
            logging.StreamHandler(),
        ],
    )


def main():
    """Démarre JARVIS Tray Manager."""
    print("=" * 60)
    print("JARVIS SYSTEM TRAY MANAGER v1.0")
    print("Démarrage en cours...")
    print("=" * 60)

    setup_logging()
    logger = logging.getLogger(__name__)

    try:
        # Lance le Tray Manager
        logger.info("Initialisation du Tray Manager...")
        manager = TrayManager()

        logger.info("Démarrage du system tray...")
        manager.run()

    except KeyboardInterrupt:
        logger.info("Arrêt demandé par l'utilisateur")
        print("\nARRÊT GRACIEUX...")
    except Exception as e:
        logger.error(f"Erreur fatale: {e}", exc_info=True)
        print(f"\nERREUR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
