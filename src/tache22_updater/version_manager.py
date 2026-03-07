"""
Version Manager JARVIS v10.6.0
Gestion centralisée des versions, compatibilité, migration et feature flags
"""

import json
import logging
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import hashlib

# Configuration
BASE_PATH = Path("F:\\BUREAU\\turbo")
SRC_PATH = BASE_PATH / "src"
DB_PATH = BASE_PATH / "jarvis.db"
CONFIG_PATH = BASE_PATH / "config"
MIGRATIONS_PATH = BASE_PATH / "migrations"

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("VersionManager")


@dataclass
class ComponentVersion:
    """Représente la version d'un composant"""
    name: str
    current: str
    latest: str
    status: str  # installed, update_available, incompatible
    dependencies: List[str]
    installation_date: str
    checksum: str


@dataclass
class CompatibilityRule:
    """Règle de compatibilité entre composants"""
    component_a: str
    component_b: str
    min_version_a: str
    min_version_b: str
    max_version_a: Optional[str] = None
    max_version_b: Optional[str] = None


class VersionDatabase:
    """Gestion de la base de données des versions"""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Initialise les tables de versioning"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Table composants
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS components (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                current_version TEXT NOT NULL,
                latest_version TEXT,
                type TEXT,
                installation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_check TIMESTAMP,
                checksum TEXT,
                status TEXT DEFAULT 'installed'
            )
        ''')
        
        # Table compatibilité
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS compatibility_matrix (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                component_a TEXT NOT NULL,
                component_b TEXT NOT NULL,
                min_version_a TEXT NOT NULL,
                min_version_b TEXT NOT NULL,
                max_version_a TEXT,
                max_version_b TEXT,
                compatible BOOLEAN DEFAULT TRUE
            )
        ''')
        
        # Table feature flags
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feature_flags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                enabled BOOLEAN DEFAULT FALSE,
                min_version TEXT,
                max_version TEXT,
                description TEXT,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Table migrations
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS migrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                migration_name TEXT UNIQUE NOT NULL,
                version_from TEXT NOT NULL,
                version_to TEXT NOT NULL,
                executed BOOLEAN DEFAULT FALSE,
                execution_date TIMESTAMP,
                rollback_date TIMESTAMP,
                status TEXT DEFAULT 'pending'
            )
        ''')
        
        # Table santé post-update
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS health_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                check_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                version TEXT NOT NULL,
                cpu_usage REAL,
                memory_usage REAL,
                disk_usage REAL,
                services_running INTEGER,
                errors_count INTEGER,
                status TEXT DEFAULT 'healthy'
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def register_component(self, name: str, version: str, comp_type: str = "plugin"):
        """Enregistre un composant"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO components 
            (name, current_version, type, status)
            VALUES (?, ?, ?, 'installed')
        ''', (name, version, comp_type))
        
        conn.commit()
        conn.close()
        logger.info(f"Composant enregistré: {name} v{version}")
    
    def get_component(self, name: str) -> Optional[Dict]:
        """Récupère un composant"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT name, current_version, latest_version, type, status
            FROM components WHERE name = ?
        ''', (name,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'name': row[0],
                'current': row[1],
                'latest': row[2],
                'type': row[3],
                'status': row[4]
            }
        return None
    
    def get_all_components(self) -> List[Dict]:
        """Récupère tous les composants"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT name, current_version, latest_version, type, status
            FROM components ORDER BY name
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                'name': row[0],
                'current': row[1],
                'latest': row[2],
                'type': row[3],
                'status': row[4]
            }
            for row in rows
        ]
    
    def add_compatibility_rule(self, rule: CompatibilityRule):
        """Ajoute une règle de compatibilité"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO compatibility_matrix
            (component_a, component_b, min_version_a, min_version_b, 
             max_version_a, max_version_b)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (rule.component_a, rule.component_b, rule.min_version_a,
              rule.min_version_b, rule.max_version_a, rule.max_version_b))
        
        conn.commit()
        conn.close()
    
    def check_compatibility(self, comp_a: str, ver_a: str, 
                          comp_b: str, ver_b: str) -> bool:
        """Vérifie la compatibilité entre deux composants"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT compatible FROM compatibility_matrix
            WHERE component_a = ? AND component_b = ?
        ''', (comp_a, comp_b))
        
        result = cursor.fetchone()
        conn.close()
        
        return bool(result and result[0])
    
    def log_health_check(self, version: str, status: str = "healthy",
                        cpu: float = 0, memory: float = 0, disk: float = 0,
                        services: int = 0, errors: int = 0):
        """Enregistre un health check"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO health_checks
            (version, cpu_usage, memory_usage, disk_usage, 
             services_running, errors_count, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (version, cpu, memory, disk, services, errors, status))
        
        conn.commit()
        conn.close()


class ChangelogGenerator:
    """Génère les changelogs à partir du git log"""
    
    @staticmethod
    def generate_from_git(repo_path: Path, from_tag: str, to_tag: str) -> str:
        """Génère un changelog entre deux tags"""
        try:
            cmd = f'git log {from_tag}..{to_tag} --oneline'
            result = subprocess.run(
                cmd, cwd=repo_path, capture_output=True, text=True, encoding="utf-8", errors="replace"
            )
            
            if result.returncode != 0:
                logger.error(f"Erreur git log: {result.stderr}")
                return ""
            
            lines = result.stdout.strip().split('\n')
            
            # Catégorise les commits
            features = []
            fixes = []
            improvements = []
            
            for line in lines:
                if 'feat:' in line or 'feature:' in line:
                    features.append(line)
                elif 'fix:' in line or 'bugfix:' in line:
                    fixes.append(line)
                elif 'improve:' in line or 'refactor:' in line:
                    improvements.append(line)
            
            changelog = f"## [{to_tag}]\n\n"
            
            if features:
                changelog += "### Features\n"
                for line in features:
                    changelog += f"- {line}\n"
                changelog += "\n"
            
            if fixes:
                changelog += "### Fixes\n"
                for line in fixes:
                    changelog += f"- {line}\n"
                changelog += "\n"
            
            if improvements:
                changelog += "### Improvements\n"
                for line in improvements:
                    changelog += f"- {line}\n"
            
            return changelog
            
        except Exception as e:
            logger.error(f"Erreur génération changelog: {e}")
            return ""
    
    @staticmethod
    def parse_conventional_commits(log_content: str) -> Dict:
        """Parse les conventional commits"""
        parsed = {
            'features': [],
            'fixes': [],
            'breaking': [],
            'other': []
        }
        
        for line in log_content.split('\n'):
            if not line.strip():
                continue
            
            if line.startswith('feat'):
                parsed['features'].append(line)
            elif line.startswith('fix'):
                parsed['fixes'].append(line)
            elif 'BREAKING' in line:
                parsed['breaking'].append(line)
            else:
                parsed['other'].append(line)
        
        return parsed


class MigrationRunner:
    """Exécute les scripts de migration"""
    
    def __init__(self, migrations_path: Path, db: VersionDatabase):
        self.migrations_path = migrations_path
        self.db = db
        self.migrations_path.mkdir(parents=True, exist_ok=True)
    
    def run_migrations(self, from_version: str, to_version: str) -> bool:
        """Exécute les migrations UP"""
        try:
            migration_name = f"{from_version}_to_{to_version}"
            migration_file = self.migrations_path / f"{migration_name}.py"
            
            if not migration_file.exists():
                logger.warning(f"Pas de migration: {migration_name}")
                return True
            
            logger.info(f"Exécution migration: {migration_name}")
            
            # Exécute le script de migration
            spec = __import__('importlib.util').util.spec_from_file_location(
                migration_name, migration_file
            )
            module = __import__('importlib.util').util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            if hasattr(module, 'migrate_up'):
                result = module.migrate_up()
                if result:
                    self.db.log_migration(migration_name, from_version, 
                                         to_version, "success")
                    logger.info(f"Migration réussie: {migration_name}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Erreur migration: {e}")
            return False
    
    def rollback_migration(self, migration_name: str) -> bool:
        """Effectue un rollback"""
        try:
            migration_file = self.migrations_path / f"{migration_name}.py"
            
            spec = __import__('importlib.util').util.spec_from_file_location(
                migration_name, migration_file
            )
            module = __import__('importlib.util').util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            if hasattr(module, 'migrate_down'):
                module.migrate_down()
                logger.info(f"Rollback réussi: {migration_name}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Erreur rollback: {e}")
            return False


class FeatureFlagManager:
    """Gestion des feature flags par version"""
    
    def __init__(self, db: VersionDatabase):
        self.db = db
    
    def register_flag(self, name: str, min_version: str, 
                     max_version: Optional[str] = None, 
                     enabled: bool = False, description: str = ""):
        """Enregistre un feature flag"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO feature_flags
            (name, enabled, min_version, max_version, description)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, enabled, min_version, max_version, description))
        
        conn.commit()
        conn.close()
        logger.info(f"Feature flag enregistré: {name}")
    
    def is_enabled(self, flag_name: str, current_version: str) -> bool:
        """Vérifie si un flag est activé pour la version"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT enabled FROM feature_flags
            WHERE name = ? AND min_version <= ? 
            AND (max_version IS NULL OR max_version >= ?)
        ''', (flag_name, current_version, current_version))
        
        result = cursor.fetchone()
        conn.close()
        
        return bool(result and result[0])
    
    def get_active_flags(self, current_version: str) -> List[str]:
        """Récupère tous les flags actifs"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT name FROM feature_flags
            WHERE enabled = TRUE AND min_version <= ?
            AND (max_version IS NULL OR max_version >= ?)
        ''', (current_version, current_version))
        
        flags = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return flags


class VersionManager:
    """Orchestrateur principal de gestion des versions"""
    
    def __init__(self):
        self.db = VersionDatabase(DB_PATH)
        self.changelog_gen = ChangelogGenerator()
        self.migration_runner = MigrationRunner(MIGRATIONS_PATH, self.db)
        self.feature_flags = FeatureFlagManager(self.db)
        self.current_version = "10.6.0"
    
    def initialize_components(self):
        """Initialise les composants principaux"""
        components = {
            'core': '10.6.0',
            'plugins': '2.1.0',
            'models': '1.5.0',
            'configs': '3.2.1'
        }
        
        for name, version in components.items():
            self.db.register_component(name, version)
        
        logger.info("Composants initialisés")
    
    def setup_compatibility_matrix(self):
        """Configure la matrice de compatibilité"""
        rules = [
            CompatibilityRule('core', 'plugins', '10.0.0', '2.0.0'),
            CompatibilityRule('core', 'models', '10.0.0', '1.0.0'),
            CompatibilityRule('plugins', 'models', '2.0.0', '1.0.0'),
        ]
        
        for rule in rules:
            self.db.add_compatibility_rule(rule)
        
        logger.info("Matrice de compatibilité configurée")
    
    def get_version_report(self) -> Dict:
        """Génère un rapport complet des versions"""
        components = self.db.get_all_components()
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'current_version': self.current_version,
            'components': components,
            'active_features': self.feature_flags.get_active_flags(
                self.current_version
            ),
            'status': 'healthy'
        }
        
        return report
    
    def export_version_json(self, output_path: Optional[Path] = None) -> str:
        """Exporte le rapport de version en JSON"""
        report = self.get_version_report()
        
        output_path = output_path or CONFIG_PATH / "versions.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Rapport JSON exporté: {output_path}")
        return json.dumps(report, indent=2, ensure_ascii=False)
    
    def perform_health_check(self) -> Dict:
        """Effectue un health check post-update"""
        try:
            # Vérifications basiques
            critical_files = ['jarvis.py', 'config.json']
            all_ok = all((SRC_PATH / f).exists() for f in critical_files)
            
            health = {
                'timestamp': datetime.now().isoformat(),
                'version': self.current_version,
                'critical_files': all_ok,
                'database_accessible': self._check_database(),
                'config_valid': self._check_config(),
                'status': 'healthy' if all_ok else 'degraded'
            }
            
            self.db.log_health_check(
                self.current_version,
                health['status']
            )
            
            logger.info(f"Health check: {health['status']}")
            return health
            
        except Exception as e:
            logger.error(f"Erreur health check: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e)
            }
    
    def _check_database(self) -> bool:
        """Vérifie l'accessibilité de la base de données"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute('SELECT 1')
            conn.close()
            return True
        except:
            return False
    
    def _check_config(self) -> bool:
        """Vérifie la validité de la config"""
        config_file = CONFIG_PATH / "config.json"
        if not config_file.exists():
            return False
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                json.load(f)
            return True
        except (json.JSONDecodeError, OSError):
            return False


# Exemple d'utilisation
if __name__ == "__main__":
    vm = VersionManager()
    
    # Initialisation
    vm.initialize_components()
    vm.setup_compatibility_matrix()
    
    # Enregistrer des feature flags
    vm.feature_flags.register_flag(
        'new_ui',
        '10.5.0',
        '11.0.0',
        True,
        'Interface utilisateur redessinée'
    )
    
    # Rapport
    report = vm.export_version_json()
    print("Rapport de version:")
    print(report)
    
    # Health check
    health = vm.perform_health_check()
    print(f"\nHealth check: {health['status']}")
    
    # Composants
    components = vm.db.get_all_components()
    print(f"\nComposants ({len(components)}):")
    for comp in components:
        print(f"  {comp['name']}: v{comp['current']}")
