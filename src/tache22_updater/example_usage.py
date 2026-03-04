"""
Exemples d'utilisation du système Auto-Updater + Versioning JARVIS
"""

import asyncio
from pathlib import Path
from auto_updater import AutoUpdater, VersionComparer
from version_manager import VersionManager


async def example_manual_update():
    """Exemple: Vérifier et appliquer une mise à jour manuelle"""
    print("\n=== EXEMPLE 1: Mise à jour manuelle ===\n")
    
    updater = AutoUpdater()
    
    # Vérifier les mises à jour disponibles
    print("Vérification des mises à jour...")
    release = await updater.check_for_updates(force=True)
    
    if release:
        tag = release.get('tag_name', '').lstrip('v')
        print(f"✓ Nouvelle version trouvée: v{tag}")
        print(f"  Publiée le: {release.get('published_at', 'N/A')}")
        print(f"  Changelog: {release.get('body', 'N/A')[:100]}...")
        
        # Effectuer la mise à jour
        success = await updater.perform_update(release)
        if success:
            print("✓ Mise à jour réussie!")
        else:
            print("✗ Échec de la mise à jour (rollback effectué)")
    else:
        print("✓ Déjà à jour")


async def example_auto_updates():
    """Exemple: Activer les mises à jour automatiques"""
    print("\n=== EXEMPLE 2: Mises à jour automatiques ===\n")
    
    updater = AutoUpdater()
    
    print("Activation des mises à jour automatiques...")
    print("(Vérification toutes les 6 heures)")
    
    # Démarrer en arrière-plan (exemple: 10 secondes pour démo)
    # await updater.enable_auto_updates()


async def example_update_history():
    """Exemple: Consulter l'historique des mises à jour"""
    print("\n=== EXEMPLE 3: Historique des mises à jour ===\n")
    
    updater = AutoUpdater()
    history = updater.get_history()
    
    if history:
        print(f"Historique ({len(history)} entrées):\n")
        for entry in history:
            print(f"  Version: v{entry['version']}")
            print(f"  Date: {entry['date']}")
            print(f"  Status: {entry['status']}")
            if entry['backup']:
                print(f"  Backup: {entry['backup']}")
            print()
    else:
        print("Aucun historique disponible")


def example_version_comparison():
    """Exemple: Comparaison de versions"""
    print("\n=== EXEMPLE 4: Comparaison de versions ===\n")
    
    versions = [
        ("10.5.0", "10.6.0"),
        ("10.6.0", "10.6.0"),
        ("10.6.1", "10.6.0"),
        ("11.0.0", "10.6.0"),
    ]
    
    for v1, v2 in versions:
        is_newer = VersionComparer.is_newer(v1, v2)
        comparison = VersionComparer.compare(v2, v1)
        
        symbols = {-1: "<", 0: "=", 1: ">"}
        print(f"  v{v2} {symbols[comparison]} v{v1}")
        print(f"  v{v1} est plus récente: {is_newer}\n")


def example_version_manager():
    """Exemple: Gestion centralisée des versions"""
    print("\n=== EXEMPLE 5: Version Manager ===\n")
    
    vm = VersionManager()
    
    # Initialiser les composants
    vm.initialize_components()
    vm.setup_compatibility_matrix()
    
    # Enregistrer un feature flag
    vm.feature_flags.register_flag(
        'advanced_analytics',
        '10.6.0',
        '11.0.0',
        True,
        'Analyse avancée des données trading'
    )
    
    # Vérifier si un flag est actif
    is_enabled = vm.feature_flags.is_enabled('advanced_analytics', '10.6.0')
    print(f"Feature 'advanced_analytics' activée: {is_enabled}")
    
    # Récupérer les flags actifs
    active_flags = vm.feature_flags.get_active_flags('10.6.0')
    print(f"\nFeature flags actifs:")
    for flag in active_flags:
        print(f"  ✓ {flag}")
    
    # Health check
    health = vm.perform_health_check()
    print(f"\nHealth check post-update: {health['status']}")
    
    # Rapport de version
    print("\nRapport de version JSON:")
    report_json = vm.export_version_json()
    print(report_json[:200] + "...\n")


def example_component_monitoring():
    """Exemple: Monitoring des composants"""
    print("\n=== EXEMPLE 6: Monitoring des composants ===\n")
    
    vm = VersionManager()
    vm.initialize_components()
    
    components = vm.db.get_all_components()
    
    print("État des composants:\n")
    for comp in components:
        status_symbol = "✓" if comp['status'] == 'installed' else "⚠"
        print(f"{status_symbol} {comp['name']}")
        print(f"  Version actuelle: v{comp['current']}")
        if comp['latest']:
            print(f"  Version disponible: v{comp['latest']}")
        print(f"  Type: {comp['type']}")
        print(f"  Status: {comp['status']}\n")


def example_changelog_generation():
    """Exemple: Génération de changelog"""
    print("\n=== EXEMPLE 7: Génération de Changelog ===\n")
    
    from version_manager import ChangelogGenerator
    
    # Exemple avec git (si le repo local existe)
    repo_path = Path("F:\\BUREAU\\turbo")
    
    if repo_path.exists():
        changelog = ChangelogGenerator.generate_from_git(
            repo_path,
            "v10.5.0",
            "v10.6.0"
        )
        
        if changelog:
            print("Changelog généré:\n")
            print(changelog)
        else:
            print("Impossible de générer le changelog")
    else:
        print(f"Repo non trouvé: {repo_path}")


async def example_complete_workflow():
    """Exemple: Workflow complet de mise à jour"""
    print("\n=== EXEMPLE 8: Workflow complet ===\n")
    
    updater = AutoUpdater()
    vm = VersionManager()
    
    print("1. Vérification des mises à jour...")
    release = await updater.check_for_updates(force=True)
    
    if release:
        print("2. Préparation des sauvegardes...")
        # La sauvegarde est faite automatiquement dans perform_update
        
        print("3. Application de la mise à jour...")
        success = await updater.perform_update(release)
        
        if success:
            print("4. Vérification de santé post-update...")
            health = vm.perform_health_check()
            
            print(f"\n✓ Workflow complété avec succès")
            print(f"  Status: {health['status']}")
            print(f"  Database accessible: {health['database_accessible']}")
            print(f"  Config valid: {health['config_valid']}")
        else:
            print("\n✗ Mise à jour échouée - rollback effectué automatiquement")
    else:
        print("Pas de mises à jour disponibles")


async def main():
    """Fonction principale exécutant tous les exemples"""
    
    print("=" * 70)
    print("SYSTÈME AUTO-UPDATER + VERSIONING JARVIS v10.6.0")
    print("=" * 70)
    
    # Exemples synchrones
    example_version_comparison()
    example_version_manager()
    example_component_monitoring()
    example_changelog_generation()
    
    # Exemples asynchrones
    await example_manual_update()
    await example_update_history()
    await example_complete_workflow()
    
    print("\n" + "=" * 70)
    print("Exemples terminés")
    print("=" * 70)


if __name__ == "__main__":
    # Exécuter les exemples
    asyncio.run(main())
    
    # Pour démarrer les mises à jour automatiques:
    # asyncio.run(example_auto_updates())
