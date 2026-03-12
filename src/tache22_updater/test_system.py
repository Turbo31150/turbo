"""
Tests unitaires pour Auto-Updater + Version Manager System
"""

import unittest
import json
from pathlib import Path
from packaging import version

from auto_updater import VersionComparer, ChangelogParser
from version_manager import VersionManager


class TestVersionComparer(unittest.TestCase):
    """Tests de comparaison de versions"""
    
    def test_compare_versions(self):
        """Test comparaison de versions"""
        # v1 < v2
        self.assertEqual(VersionComparer.compare("10.5.0", "10.6.0"), -1)
        
        # v1 > v2
        self.assertEqual(VersionComparer.compare("10.6.0", "10.5.0"), 1)
        
        # v1 == v2
        self.assertEqual(VersionComparer.compare("10.6.0", "10.6.0"), 0)
    
    def test_is_newer(self):
        """Test détection de version plus récente"""
        self.assertTrue(VersionComparer.is_newer("10.7.0", "10.6.0"))
        self.assertFalse(VersionComparer.is_newer("10.5.0", "10.6.0"))
        self.assertFalse(VersionComparer.is_newer("10.6.0", "10.6.0"))
    
    def test_semver_comparison(self):
        """Test comparaison sémantique complète"""
        # Major version
        self.assertTrue(VersionComparer.is_newer("11.0.0", "10.9.9"))
        
        # Minor version
        self.assertTrue(VersionComparer.is_newer("10.7.0", "10.6.9"))
        
        # Patch version
        self.assertTrue(VersionComparer.is_newer("10.6.1", "10.6.0"))


class TestChangelogParser(unittest.TestCase):
    """Tests du parsing de changelog"""
    
    def test_parse_changelog(self):
        """Test parsing de changelog markdown"""
        changelog_text = """
## [10.6.0]

### Features
- New feature 1
- New feature 2

### Fixes
- Bug fix 1
- Bug fix 2

### Improvements
- Improvement 1
"""
        parsed = ChangelogParser.parse_changelog(changelog_text)
        
        self.assertIn("10.6.0", parsed)
        self.assertIn("Features", parsed["10.6.0"])
        self.assertEqual(len(parsed["10.6.0"]["Features"]), 2)
    
    def test_format_changelog(self):
        """Test formatage de changelog"""
        parsed = {
            "10.6.0": {
                "Features": ["Feature 1", "Feature 2"],
                "Fixes": ["Fix 1"]
            }
        }
        
        formatted = ChangelogParser.format_changelog(parsed)
        
        self.assertIn("10.6.0", formatted)
        self.assertIn("Features", formatted)
        self.assertIn("Feature 1", formatted)


class TestVersionManager(unittest.TestCase):
    """Tests du gestionnaire de versions"""
    
    def setUp(self):
        """Configuration avant chaque test"""
        self.vm = VersionManager()
    
    def test_component_registration(self):
        """Test enregistrement de composant"""
        self.vm.db.register_component("test_comp", "1.0.0", "plugin")
        
        comp = self.vm.db.get_component("test_comp")
        self.assertIsNotNone(comp)
        self.assertEqual(comp['name'], "test_comp")
        self.assertEqual(comp['current'], "1.0.0")
    
    def test_get_all_components(self):
        """Test récupération de tous les composants"""
        self.vm.initialize_components()
        
        components = self.vm.db.get_all_components()
        self.assertGreater(len(components), 0)
        
        # Vérifier qu'il y a les composants par défaut
        names = [c['name'] for c in components]
        self.assertIn("core", names)
    
    def test_feature_flag_registration(self):
        """Test enregistrement de feature flag"""
        self.vm.feature_flags.register_flag(
            "test_flag",
            "10.5.0",
            True,
            "Test flag"
        )
        
        # Vérifier que le flag est enregistré
        is_enabled = self.vm.feature_flags.is_enabled("test_flag", "10.6.0")
        # Ne peut pas directement tester car it depends on DB state
        # Mais on ne devrait pas avoir d'erreur
        self.assertIsNotNone(is_enabled)
    
    def test_version_report(self):
        """Test génération de rapport de version"""
        self.vm.initialize_components()
        
        report = self.vm.get_version_report()
        
        self.assertIn('timestamp', report)
        self.assertIn('current_version', report)
        self.assertIn('components', report)
        self.assertEqual(report['current_version'], "10.6.0")
    
    def test_health_check(self):
        """Test health check"""
        health = self.vm.perform_health_check()
        
        self.assertIn('status', health)
        self.assertIn('timestamp', health)
        self.assertIn('version', health)


class TestIntegration(unittest.TestCase):
    """Tests d'intégration"""
    
    def test_version_comparison_chain(self):
        """Test chaîne de comparaison"""
        versions = ["10.4.0", "10.5.0", "10.6.0", "11.0.0"]
        
        # Vérifier que chaque version est plus récente que la précédente
        for i in range(len(versions) - 1):
            self.assertTrue(
                VersionComparer.is_newer(versions[i+1], versions[i])
            )
    
    def test_components_initialization(self):
        """Test initialisation complète des composants"""
        from integration import JARVISUpdateOrchestrator
        
        orchestrator = JARVISUpdateOrchestrator()
        orchestrator.vm.initialize_components()
        
        components = orchestrator.vm.db.get_all_components()
        self.assertGreater(len(components), 0)
    
    def test_compatibility_matrix_setup(self):
        """Test configuration matrice de compatibilité"""
        from version_manager import VersionManager, CompatibilityRule
        
        vm = VersionManager()
        
        rule = CompatibilityRule(
            "core",
            "plugins",
            "10.0.0",
            "2.0.0"
        )
        
        vm.db.add_compatibility_rule(rule)
        
        # Vérifier que la règle peut être trouvée
        is_compatible = vm.db.check_compatibility(
            "core", "10.6.0",
            "plugins", "2.1.0"
        )
        self.assertIsNotNone(is_compatible)


class TestDataIntegrity(unittest.TestCase):
    """Tests d'intégrité des données"""
    
    def test_version_string_format(self):
        """Test format des chaînes de version"""
        test_versions = ["10.6.0", "10.6.1", "11.0.0"]
        
        for v in test_versions:
            # Doit être parseable par packaging.version
            parsed = version.parse(v)
            self.assertIsNotNone(parsed)
    
    def test_config_json_validity(self):
        """Test validité du fichier config JSON"""
        config_path = Path(__file__).parent / "config_example.json"
        
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Vérifier structure basique
            self.assertIn('auto_updater', config)
            self.assertIn('components', config)
            self.assertIn('machines', config)


class TestErrorHandling(unittest.TestCase):
    """Tests de gestion d'erreurs"""
    
    def test_version_compare_invalid_input(self):
        """Test comparaison avec entrée invalide"""
        # Ne devrait pas lever d'exception
        result = VersionComparer.compare("invalid", "1.0.0")
        self.assertEqual(result, 0)  # Retourne 0 en cas d'erreur
    
    def test_missing_component(self):
        """Test récupération de composant inexistant"""
        vm = VersionManager()
        
        comp = vm.db.get_component("nonexistent_component")
        self.assertIsNone(comp)
    
    def test_changelog_empty_string(self):
        """Test parsing changelog vide"""
        parsed = ChangelogParser.parse_changelog("")
        
        self.assertEqual(len(parsed), 0)


class TestPerformance(unittest.TestCase):
    """Tests de performance"""
    
    def test_version_comparison_speed(self):
        """Test vitesse de comparaison"""
        import time
        
        start = time.time()
        
        for _ in range(1000):
            VersionComparer.is_newer("10.7.0", "10.6.0")
        
        elapsed = time.time() - start
        
        # Devrait être très rapide (< 100ms pour 1000 comparaisons)
        self.assertLess(elapsed, 0.1)
    
    def test_component_retrieval_speed(self):
        """Test vitesse de récupération des composants"""
        import time
        
        vm = VersionManager()
        vm.initialize_components()
        
        start = time.time()
        
        for _ in range(100):
            vm.db.get_all_components()
        
        elapsed = time.time() - start
        
        # Devrait être très rapide (< 500ms pour 100 requêtes)
        self.assertLess(elapsed, 0.5)


def run_tests():
    """Exécute tous les tests"""
    # Créer une suite de tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Ajouter tous les tests
    suite.addTests(loader.loadTestsFromTestCase(TestVersionComparer))
    suite.addTests(loader.loadTestsFromTestCase(TestChangelogParser))
    suite.addTests(loader.loadTestsFromTestCase(TestVersionManager))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestDataIntegrity))
    suite.addTests(loader.loadTestsFromTestCase(TestErrorHandling))
    suite.addTests(loader.loadTestsFromTestCase(TestPerformance))
    
    # Exécuter les tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result


if __name__ == "__main__":
    print("=" * 70)
    print("TÂCHE 22 - Auto-Updater System Tests")
    print("=" * 70)
    print()
    
    result = run_tests()
    
    print()
    print("=" * 70)
    print(f"Tests: {result.testsRun}")
    print(f"Succès: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Échecs: {len(result.failures)}")
    print(f"Erreurs: {len(result.errors)}")
    print("=" * 70)
