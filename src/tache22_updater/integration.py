"""
Integration Module - Connexion Auto-Updater + Version Manager + JARVIS
Point d'entrée unique pour les opérations de mise à jour et versioning
"""

import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

from auto_updater import AutoUpdater
from version_manager import VersionManager

# Configuration
BASE_PATH = Path("F:\\BUREAU\\turbo")
CONFIG_PATH = BASE_PATH / "config"
LOGS_PATH = BASE_PATH / "logs"

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(LOGS_PATH / "integration.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("Integration")


class JARVISUpdateOrchestrator:
    """
    Orchestrateur unifié pour mises à jour et versioning JARVIS
    Combine AutoUpdater et VersionManager
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or CONFIG_PATH / "config.json"
        self.config = self._load_config()
        self.updater = AutoUpdater()
        self.vm = VersionManager()
        self.is_updating = False
        self.update_status = "idle"  # idle, checking, updating, done, error
        
        logger.info("JARVIS Update Orchestrator initialized")
    
    def _load_config(self) -> Dict:
        """Charge la configuration"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Erreur chargement config: {e}")
                return {}
        return {}
    
    async def initialize(self):
        """Initialise le système complet"""
        logger.info("Initialisation du système de mise à jour...")
        
        try:
            # Initialiser composants
            self.vm.initialize_components()
            self.vm.setup_compatibility_matrix()
            
            # Enregistrer feature flags
            self._register_default_flags()
            
            # Health check initial
            health = self.vm.perform_health_check()
            
            if health['status'] != 'healthy':
                logger.warning(f"Health check dégradé: {health['status']}")
            
            logger.info("Système initialisé avec succès")
            return True
            
        except Exception as e:
            logger.error(f"Erreur initialisation: {e}")
            return False
    
    def _register_default_flags(self):
        """Enregistre les feature flags par défaut"""
        default_flags = {
            'advanced_analytics': {
                'min_version': '10.6.0',
                'enabled': True,
                'description': 'Analyse avancée des données trading'
            },
            'gpu_acceleration': {
                'min_version': '10.5.0',
                'enabled': True,
                'description': 'Accélération GPU pour les modèles'
            },
            'new_ui': {
                'min_version': '10.7.0',
                'enabled': False,
                'description': 'Nouvelle interface utilisateur'
            },
            'distributed_training': {
                'min_version': '10.8.0',
                'enabled': False,
                'description': 'Entraînement distribué multi-GPU'
            }
        }
        
        for name, config in default_flags.items():
            self.vm.feature_flags.register_flag(
                name,
                config['min_version'],
                enabled=config['enabled'],
                description=config['description']
            )
            logger.info(f"Feature flag enregistré: {name}")
    
    async def check_updates(self, force: bool = False) -> Optional[Dict]:
        """Vérifie les mises à jour disponibles"""
        logger.info("Vérification des mises à jour...")
        self.update_status = "checking"
        
        try:
            release = await self.updater.check_for_updates(force=force)
            
            if release:
                tag = release.get('tag_name', '').lstrip('v')
                logger.info(f"Nouvelle version disponible: v{tag}")
                self.update_status = "available"
                
                return {
                    'available': True,
                    'version': tag,
                    'published_at': release.get('published_at'),
                    'download_url': release.get('html_url'),
                    'changelog_snippet': release.get('body', '')[:200]
                }
            else:
                logger.info("Pas de mises à jour disponibles")
                self.update_status = "idle"
                return {'available': False, 'version': None}
                
        except Exception as e:
            logger.error(f"Erreur vérification: {e}")
            self.update_status = "error"
            return None
    
    async def apply_update(self, release: Dict) -> Dict:
        """Applique une mise à jour avec tous les vérifications"""
        if self.is_updating:
            logger.warning("Mise à jour déjà en cours")
            return {'success': False, 'error': 'Update already in progress'}
        
        self.is_updating = True
        self.update_status = "updating"
        
        try:
            logger.info("Début du processus de mise à jour...")
            
            # Étape 1: Backup + Update
            success = await self.updater.perform_update(release)
            
            if not success:
                logger.error("Mise à jour échouée")
                self.update_status = "error"
                return {
                    'success': False,
                    'error': 'Update failed - rollback applied'
                }
            
            # Étape 2: Health check
            logger.info("Effectuation du health check post-update...")
            health = self.vm.perform_health_check()
            
            if health['status'] == 'unhealthy':
                logger.error("Health check échoué - état dégradé")
                self.update_status = "error"
                return {
                    'success': False,
                    'error': 'Health check failed',
                    'health': health
                }
            
            # Étape 3: Export rapport
            version_report = self.vm.export_version_json()
            
            logger.info("Mise à jour terminée avec succès")
            self.update_status = "done"
            
            return {
                'success': True,
                'message': 'Update applied successfully',
                'version_report': json.loads(version_report) if isinstance(version_report, str) else version_report,
                'health_status': health['status']
            }
            
        except Exception as e:
            logger.error(f"Erreur application: {e}")
            self.update_status = "error"
            return {'success': False, 'error': str(e)}
        
        finally:
            self.is_updating = False
    
    async def start_auto_updates(self, interval_hours: int = 6):
        """Démarre les mises à jour automatiques"""
        logger.info(f"Activation mises à jour automatiques ({interval_hours}h)")
        
        try:
            await self.updater.enable_auto_updates()
        except KeyboardInterrupt:
            logger.info("Arrêt des mises à jour automatiques")
            self.updater.disable_auto_updates()
    
    def get_system_status(self) -> Dict:
        """Récupère l'état complet du système"""
        components = self.vm.db.get_all_components()
        active_flags = self.vm.feature_flags.get_active_flags(
            self.vm.current_version
        )
        history = self.updater.get_history(limit=5)
        
        return {
            'timestamp': datetime.now().isoformat(),
            'update_status': self.update_status,
            'is_updating': self.is_updating,
            'current_version': self.vm.current_version,
            'components': components,
            'active_features': active_flags,
            'recent_updates': history,
            'components_count': len(components)
        }
    
    def get_compatibility_report(self) -> Dict:
        """Génère un rapport de compatibilité"""
        components = self.vm.db.get_all_components()
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'components': {},
            'incompatibilities': []
        }
        
        for comp in components:
            report['components'][comp['name']] = {
                'version': comp['current'],
                'status': comp['status'],
                'type': comp['type']
            }
        
        # Vérifier compatibilités croisées
        for i, comp1 in enumerate(components):
            for comp2 in components[i+1:]:
                is_compatible = self.vm.db.check_compatibility(
                    comp1['name'], comp1['current'],
                    comp2['name'], comp2['current']
                )
                
                if not is_compatible:
                    report['incompatibilities'].append({
                        'component_a': comp1['name'],
                        'version_a': comp1['current'],
                        'component_b': comp2['name'],
                        'version_b': comp2['current']
                    })
        
        return report
    
    def export_status_report(self, output_path: Optional[Path] = None) -> Path:
        """Exporte un rapport complet"""
        output_path = output_path or LOGS_PATH / f"status_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        report = {
            'system': self.get_system_status(),
            'compatibility': self.get_compatibility_report(),
            'generated_at': datetime.now().isoformat()
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Rapport exporté: {output_path}")
        return output_path
    
    def notify_update_available(self, release_info: Dict):
        """Notifie de la disponibilité d'une mise à jour"""
        logger.info(f"NOTIFICATION: Nouvelle version v{release_info['version']} disponible")
        
        # TODO: Intégration Telegram via MCP jarvis-turbo
        # Pour faire partie d'une tâche future
    
    async def full_update_cycle(self):
        """Cycle complet: vérifier + appliquer + health check"""
        logger.info("=== Cycle complet de mise à jour ===")
        
        # Vérifier
        update_info = await self.check_updates(force=True)
        
        if not update_info or not update_info.get('available'):
            logger.info("Pas de mise à jour disponible")
            return {'status': 'no_updates'}
        
        # Notifier
        self.notify_update_available(update_info)
        
        # Appliquer (simulation: en production, attendre approbation utilisateur)
        logger.info("Application de la mise à jour...")
        
        # Récupérer la release complète
        release = await self.updater.gh_mgr.get_latest_release()
        if release:
            result = await self.apply_update(release)
            return result
        
        return {'status': 'failed', 'error': 'Could not fetch release'}


# Fonctions de convenience
async def quick_check_updates():
    """Vérifie rapidement les mises à jour"""
    orchestrator = JARVISUpdateOrchestrator()
    await orchestrator.initialize()
    result = await orchestrator.check_updates(force=True)
    
    if result['available']:
        print(f"✓ Nouvelle version: v{result['version']}")
    else:
        print("✓ Vous avez la dernière version")
    
    return result


async def quick_apply_update():
    """Applique une mise à jour en une commande"""
    orchestrator = JARVISUpdateOrchestrator()
    await orchestrator.initialize()
    
    update_info = await orchestrator.check_updates(force=True)
    
    if update_info['available']:
        release = await orchestrator.updater.gh_mgr.get_latest_release()
        result = await orchestrator.apply_update(release)
        return result
    
    return {'status': 'no_updates'}


def quick_status():
    """Affiche le statut du système"""
    orchestrator = JARVISUpdateOrchestrator()
    status = orchestrator.get_system_status()
    
    print("\n=== JARVIS Update System Status ===\n")
    print(f"Version: v{status['current_version']}")
    print(f"Update Status: {status['update_status']}")
    print(f"Components: {status['components_count']}")
    print(f"Active Features: {len(status['active_features'])}")
    
    if status['recent_updates']:
        print(f"\nLast update: {status['recent_updates'][0]['date']}")
    
    return status


if __name__ == "__main__":
    # Exemples d'utilisation
    print("JARVIS Update Orchestrator - Integration Module\n")
    
    # Status simple
    # quick_status()
    
    # Vérifier les mises à jour
    # asyncio.run(quick_check_updates())
    
    # Cycle complet (avec initialisation)
    # asyncio.run(quick_apply_update())
