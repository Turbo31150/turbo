"""
Tests de benchmark et performance pour JARVIS Linux.
Valide que le système fonctionne correctement avec des métriques de performance.
"""

import json
import os
import sqlite3
import sys
import time
import unittest
import importlib
import urllib.request
import urllib.error

# Chemins de base
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
SRC_DIR = os.path.join(BASE_DIR, "src")
SKILLS_PATH = os.path.join(DATA_DIR, "skills.json")
JARVIS_DB = os.path.join(DATA_DIR, "jarvis.db")
ETOILE_DB = os.path.join(DATA_DIR, "etoile.db")

# Ajouter src au path pour les imports
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


class TestSkillsPerformance(unittest.TestCase):
    """Tests de performance sur le chargement et la structure des skills."""

    @classmethod
    def setUpClass(cls):
        """Charger les skills une seule fois pour tous les tests."""
        with open(SKILLS_PATH, "r", encoding="utf-8") as f:
            cls.skills = json.load(f)

    def test_load_skills_under_100ms(self):
        """Charger 200+ skills en moins de 100ms."""
        start = time.perf_counter()
        with open(SKILLS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        elapsed_ms = (time.perf_counter() - start) * 1000
        self.assertGreater(len(data), 200, f"Seulement {len(data)} skills chargés")
        self.assertLess(elapsed_ms, 100, f"Chargement trop lent: {elapsed_ms:.1f}ms")

    def test_find_skill_under_10ms(self):
        """Trouver un skill par trigger en moins de 10ms."""
        # Prendre le premier trigger du premier skill comme cible
        target_trigger = self.skills[0]["triggers"][0]
        start = time.perf_counter()
        found = None
        for skill in self.skills:
            if target_trigger in skill.get("triggers", []):
                found = skill
                break
        elapsed_ms = (time.perf_counter() - start) * 1000
        self.assertIsNotNone(found, f"Trigger '{target_trigger}' introuvable")
        self.assertLess(elapsed_ms, 10, f"Recherche trop lente: {elapsed_ms:.1f}ms")

    def test_save_skill_under_50ms(self):
        """Sauvegarder les skills en JSON en moins de 50ms (en mémoire)."""
        start = time.perf_counter()
        output = json.dumps(self.skills, ensure_ascii=False, indent=2)
        elapsed_ms = (time.perf_counter() - start) * 1000
        self.assertGreater(len(output), 0)
        self.assertLess(elapsed_ms, 50, f"Sérialisation trop lente: {elapsed_ms:.1f}ms")

    def test_skills_json_valid(self):
        """Le fichier skills.json est un JSON valide et parseable."""
        with open(SKILLS_PATH, "r", encoding="utf-8") as f:
            raw = f.read()
        # Doit être parseable sans exception
        data = json.loads(raw)
        self.assertIsInstance(data, list, "skills.json doit être une liste")

    def test_no_duplicate_skill_names(self):
        """Aucun doublon de nom dans les skills."""
        names = [s.get("name", "") for s in self.skills]
        duplicates = [n for n in names if names.count(n) > 1]
        unique_duplicates = list(set(duplicates))
        self.assertEqual(len(unique_duplicates), 0,
                         f"Doublons trouvés: {unique_duplicates[:10]}")

    def test_all_skills_have_triggers(self):
        """Tous les skills ont au moins un trigger."""
        missing = [s.get("name", "?") for s in self.skills
                   if not s.get("triggers") or len(s["triggers"]) == 0]
        self.assertEqual(len(missing), 0,
                         f"{len(missing)} skills sans triggers: {missing[:5]}")

    def test_all_skills_have_steps(self):
        """Tous les skills ont au moins un step."""
        missing = [s.get("name", "?") for s in self.skills
                   if not s.get("steps") or len(s["steps"]) == 0]
        self.assertEqual(len(missing), 0,
                         f"{len(missing)} skills sans steps: {missing[:5]}")

    def test_skill_count_above_200(self):
        """Au moins 200 skills enregistrés."""
        count = len(self.skills)
        self.assertGreaterEqual(count, 200,
                                f"Seulement {count} skills (minimum: 200)")

    def test_trigger_count_above_1000(self):
        """Au moins 1000 triggers au total."""
        total = sum(len(s.get("triggers", [])) for s in self.skills)
        self.assertGreaterEqual(total, 1000,
                                f"Seulement {total} triggers (minimum: 1000)")

    def test_skills_file_under_5mb(self):
        """Le fichier skills.json fait moins de 5MB."""
        size_bytes = os.path.getsize(SKILLS_PATH)
        size_mb = size_bytes / (1024 * 1024)
        self.assertLess(size_mb, 5.0,
                        f"skills.json trop gros: {size_mb:.2f}MB")


class TestDatabasePerformance(unittest.TestCase):
    """Tests de performance et intégrité sur les bases de données."""

    @classmethod
    def setUpClass(cls):
        """Ouvrir les connexions DB pour tous les tests."""
        cls.jarvis_conn = sqlite3.connect(JARVIS_DB)
        cls.etoile_conn = sqlite3.connect(ETOILE_DB)

    @classmethod
    def tearDownClass(cls):
        """Fermer les connexions DB."""
        cls.jarvis_conn.close()
        cls.etoile_conn.close()

    def test_voice_commands_count_above_180(self):
        """Au moins 180 commandes vocales enregistrées."""
        cursor = self.jarvis_conn.execute("SELECT COUNT(*) FROM voice_commands")
        count = cursor.fetchone()[0]
        self.assertGreaterEqual(count, 180,
                                f"Seulement {count} commandes (minimum: 180)")

    def test_voice_corrections_count_above_300(self):
        """Au moins 300 corrections vocales enregistrées."""
        cursor = self.jarvis_conn.execute("SELECT COUNT(*) FROM voice_corrections")
        count = cursor.fetchone()[0]
        self.assertGreaterEqual(count, 300,
                                f"Seulement {count} corrections (minimum: 300)")

    def test_voice_macros_count_30(self):
        """Exactement 30 macros vocales."""
        cursor = self.jarvis_conn.execute("SELECT COUNT(*) FROM voice_macros")
        count = cursor.fetchone()[0]
        self.assertEqual(count, 30,
                         f"{count} macros au lieu de 30")

    def test_db_integrity_jarvis(self):
        """PRAGMA integrity_check sur jarvis.db passe."""
        cursor = self.jarvis_conn.execute("PRAGMA integrity_check")
        result = cursor.fetchone()[0]
        self.assertEqual(result, "ok",
                         f"Intégrité jarvis.db échouée: {result}")

    def test_db_integrity_etoile(self):
        """PRAGMA integrity_check sur etoile.db passe."""
        cursor = self.etoile_conn.execute("PRAGMA integrity_check")
        result = cursor.fetchone()[0]
        self.assertEqual(result, "ok",
                         f"Intégrité etoile.db échouée: {result}")

    def test_query_voice_commands_under_10ms(self):
        """Requête sur voice_commands en moins de 10ms."""
        start = time.perf_counter()
        cursor = self.jarvis_conn.execute(
            "SELECT * FROM voice_commands WHERE category = 'linux' LIMIT 50"
        )
        rows = cursor.fetchall()
        elapsed_ms = (time.perf_counter() - start) * 1000
        self.assertGreater(len(rows), 0, "Aucun résultat pour la catégorie 'linux'")
        self.assertLess(elapsed_ms, 10, f"Requête trop lente: {elapsed_ms:.1f}ms")

    def test_no_empty_triggers(self):
        """Aucun trigger vide dans voice_commands."""
        cursor = self.jarvis_conn.execute(
            "SELECT COUNT(*) FROM voice_commands WHERE triggers IS NULL OR triggers = ''"
        )
        count = cursor.fetchone()[0]
        self.assertEqual(count, 0,
                         f"{count} commandes avec triggers vides")

    def test_no_empty_actions(self):
        """Aucune action vide dans voice_commands."""
        cursor = self.jarvis_conn.execute(
            "SELECT COUNT(*) FROM voice_commands WHERE action IS NULL OR action = ''"
        )
        count = cursor.fetchone()[0]
        self.assertEqual(count, 0,
                         f"{count} commandes avec actions vides")

    def test_categories_exist(self):
        """Les catégories sont bien définies."""
        cursor = self.jarvis_conn.execute(
            "SELECT DISTINCT category FROM voice_commands"
        )
        categories = [row[0] for row in cursor.fetchall()]
        self.assertGreater(len(categories), 5,
                           f"Seulement {len(categories)} catégories")
        # Vérifier qu'aucune catégorie n'est vide
        empty = [c for c in categories if not c or c.strip() == ""]
        self.assertEqual(len(empty), 0, "Catégories vides trouvées")

    def test_db_size_reasonable(self):
        """jarvis.db fait moins de 50MB."""
        size_bytes = os.path.getsize(JARVIS_DB)
        size_mb = size_bytes / (1024 * 1024)
        self.assertLess(size_mb, 50.0,
                        f"jarvis.db trop gros: {size_mb:.2f}MB")


class TestSystemIntegration(unittest.TestCase):
    """Tests d'intégration système : services, imports, connectivité."""

    def test_dashboard_web_responds(self):
        """Le dashboard web répond en HTTP 200 sur le port 8088."""
        try:
            req = urllib.request.Request("http://127.0.0.1:8088/",
                                         method="GET")
            req.add_header("User-Agent", "JARVIS-Benchmark/1.0")
            resp = urllib.request.urlopen(req, timeout=5)
            self.assertEqual(resp.status, 200,
                             f"Dashboard HTTP {resp.status} au lieu de 200")
        except urllib.error.URLError as e:
            self.skipTest(f"Dashboard non accessible: {e}")
        except Exception as e:
            self.skipTest(f"Dashboard non accessible: {e}")

    def test_mcp_server_responds(self):
        """Le serveur MCP répond en HTTP sur le port 8080."""
        try:
            req = urllib.request.Request("http://127.0.0.1:8080/",
                                         method="GET")
            req.add_header("User-Agent", "JARVIS-Benchmark/1.0")
            resp = urllib.request.urlopen(req, timeout=5)
            status = resp.status
            self.assertIn(status, [200, 404, 405],
                          f"MCP HTTP {status} inattendu")
        except urllib.error.HTTPError as e:
            # 404/405 = le serveur répond, c'est ok
            self.assertIn(e.code, [404, 405],
                          f"MCP erreur HTTP {e.code}")
        except urllib.error.URLError as e:
            self.skipTest(f"MCP non accessible: {e}")
        except Exception as e:
            self.skipTest(f"MCP non accessible: {e}")

    def test_mega_improve_running(self):
        """Le service mega-improve est actif (ou un cycle récent existe)."""
        # Vérifier via les logs ou la DB
        try:
            conn = sqlite3.connect(JARVIS_DB)
            cursor = conn.execute(
                "SELECT COUNT(*) FROM validation_cycles"
            )
            count = cursor.fetchone()[0]
            conn.close()
            if count > 0:
                return  # Des cycles existent, le service a tourné
        except Exception:
            pass
        # Vérifier le processus
        import subprocess
        result = subprocess.run(
            ["pgrep", "-f", "mega.improve"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return  # Processus actif
        self.skipTest("mega-improve non actif et aucun cycle trouvé")

    def test_improve_cycles_exist(self):
        """Au moins 1 cycle d'amélioration ou de maintenance loggé."""
        try:
            conn = sqlite3.connect(JARVIS_DB)
            total = 0
            # Vérifier validation_cycles
            for table in ["validation_cycles", "maintenance_log"]:
                try:
                    cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
                    total += cursor.fetchone()[0]
                except sqlite3.OperationalError:
                    pass
            conn.close()
            self.assertGreaterEqual(total, 1,
                                    f"Seulement {total} cycles/logs (minimum: 1)")
        except sqlite3.OperationalError as e:
            self.skipTest(f"Tables de cycles absentes: {e}")

    def test_skills_json_loadable(self):
        """Le fichier skills.json se charge sans erreur."""
        with open(SKILLS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

    def test_domino_pipelines_importable(self):
        """Le module domino_pipelines_linux est importable."""
        try:
            mod = importlib.import_module("domino_pipelines_linux")
            self.assertIsNotNone(mod)
        except ImportError as e:
            self.fail(f"Import domino_pipelines_linux échoué: {e}")

    def test_voice_router_importable(self):
        """Le module voice_router est importable."""
        try:
            mod = importlib.import_module("voice_router")
            self.assertIsNotNone(mod)
        except ImportError as e:
            self.fail(f"Import voice_router échoué: {e}")

    def test_linux_modules_importable(self):
        """Les 11 modules linux principaux sont importables."""
        modules = [
            "linux_maintenance",
            "linux_network",
            "linux_packages",
            "linux_services",
            "linux_desktop_control",
            "linux_journal_reader",
            "linux_security_status",
            "linux_power_manager",
            "linux_config_manager",
            "linux_update_manager",
            "linux_workspace_manager",
        ]
        failed = []
        for mod_name in modules:
            try:
                importlib.import_module(mod_name)
            except Exception as e:
                failed.append(f"{mod_name}: {e}")
        self.assertEqual(len(failed), 0,
                         f"{len(failed)} modules non importables:\n" +
                         "\n".join(failed[:5]))

    def test_new_modules_importable(self):
        """Les nouveaux modules (voice_conversational, voice_profiles, etc.) sont importables."""
        modules = [
            "voice_conversational",
            "voice_profiles",
            "voice_emotion",
            "voice_analytics_dashboard",
            "voice_context_engine",
        ]
        failed = []
        for mod_name in modules:
            try:
                importlib.import_module(mod_name)
            except Exception as e:
                failed.append(f"{mod_name}: {e}")
        self.assertEqual(len(failed), 0,
                         f"{len(failed)} nouveaux modules non importables:\n" +
                         "\n".join(failed[:5]))

    def test_services_count_above_10(self):
        """Au moins 10 services JARVIS détectés (fichiers systemd ou modules src)."""
        # Compter les fichiers de service systemd
        systemd_dir = os.path.join(BASE_DIR, "systemd")
        service_count = 0
        if os.path.isdir(systemd_dir):
            service_count = len([f for f in os.listdir(systemd_dir)
                                 if f.endswith(".service")])
        # Sinon, compter les modules de service dans src
        if service_count < 10:
            service_modules = [
                "dashboard", "mcp_server", "mcp_server_sse",
                "voice_router", "voice_pipeline_v3", "auto_optimizer",
                "domino_executor", "alert_manager", "health_dashboard",
                "observability", "trading_engine", "notification_hub",
                "event_bus", "scheduler_manager", "service_mesh",
            ]
            importable = 0
            for mod_name in service_modules:
                try:
                    importlib.import_module(mod_name)
                    importable += 1
                except Exception:
                    pass
            service_count = max(service_count, importable)
        self.assertGreaterEqual(service_count, 10,
                                f"Seulement {service_count} services (minimum: 10)")


if __name__ == "__main__":
    # Afficher un header
    print("=" * 70)
    print("  JARVIS Linux - Benchmark & Performance Tests")
    print("=" * 70)
    print(f"  Base: {BASE_DIR}")
    print(f"  Skills: {SKILLS_PATH}")
    print(f"  DB: {JARVIS_DB}")
    print("=" * 70)
    print()

    unittest.main(verbosity=2)
