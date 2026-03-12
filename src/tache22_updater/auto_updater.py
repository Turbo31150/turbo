"""
Auto-Updater JARVIS v10.6.0
Gestion automatique des mises à jour avec rollback et vérification d'intégrité
"""

import asyncio
import hashlib
import json
import logging
import os
import shutil
import sqlite3
import subprocess
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from packaging import version
import httpx
import aiofiles

# Configuration
BASE_PATH = Path("F:/BUREAU/turbo")
SRC_PATH = BASE_PATH / "src"
BACKUP_PATH = BASE_PATH / "backups"
DB_PATH = BASE_PATH / "jarvis.db"
GITHUB_REPO = "turbONE/jarvis"
GITHUB_API = "https://api.github.com"
CURRENT_VERSION = "10.6.0"
CHECK_INTERVAL = 6  # heures

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(BASE_PATH / "logs" / "auto_updater.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("AutoUpdater")


class VersionComparer:
    """Comparaison de versions sémantiques"""
    
    @staticmethod
    def compare(v1: str, v2: str) -> int:
        """Compare deux versions. Retourne: -1 (v1<v2), 0 (égal), 1 (v1>v2)"""
        try:
            ver1 = version.parse(v1)
            ver2 = version.parse(v2)
            if ver1 < ver2:
                return -1
            elif ver1 > ver2:
                return 1
            return 0
        except Exception as e:
            logger.error(f"Erreur comparaison versions: {e}")
            return 0
    
    @staticmethod
    def is_newer(new_ver: str, current_ver: str) -> bool:
        """Vérifie si new_ver > current_ver"""
        return VersionComparer.compare(current_ver, new_ver) < 0


class ChangelogParser:
    """Parsing du changelog markdown"""
    
    @staticmethod
    def parse_changelog(content: str) -> Dict:
        """Extrait les informations du changelog"""
        lines = content.split('\n')
        changelog = {}
        current_version = None
        current_section = None
        current_items = []
        
        for line in lines:
            if line.startswith('## '):
                if current_version and current_items:
                    changelog[current_version] = {
                        current_section: current_items.copy()
                    }
                current_version = line.replace('## [', '').replace(']', '').split(' ')[0]
                current_section = None
                current_items = []
            elif line.startswith('### '):
                if current_section and current_items:
                    if current_version not in changelog:
                        changelog[current_version] = {}
                    changelog[current_version][current_section] = current_items.copy()
                current_section = line.replace('### ', '').strip()
                current_items = []
            elif line.startswith('- ') and current_section:
                current_items.append(line.replace('- ', '').strip())
        
        return changelog
    
    @staticmethod
    def format_changelog(parsed: Dict) -> str:
        """Formate changelog parsé en texte lisible"""
        result = []
        for ver, sections in parsed.items():
            result.append(f"\nVersion {ver}:")
            for section, items in sections.items():
                result.append(f"  {section}:")
                for item in items:
                    result.append(f"    - {item}")
        return '\n'.join(result)


class IntegrityChecker:
    """Vérification d'intégrité SHA256"""
    
    @staticmethod
    async def calculate_sha256(filepath: Path) -> str:
        """Calcule le hash SHA256 d'un fichier"""
        sha256_hash = hashlib.sha256()
        async with aiofiles.open(filepath, 'rb') as f:
            async for chunk in f.iter_chunked(8192):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    
    @staticmethod
    async def verify_file(filepath: Path, expected_hash: str) -> bool:
        """Vérifie l'intégrité d'un fichier"""
        calculated = await IntegrityChecker.calculate_sha256(filepath)
        is_valid = calculated == expected_hash
        logger.info(f"Vérification {filepath.name}: {'OK' if is_valid else 'ÉCHOUÉ'}")
        return is_valid


class BackupManager:
    """Gestion des sauvegardes"""
    
    def __init__(self, backup_base: Path):
        self.backup_base = backup_base
        self.backup_base.mkdir(parents=True, exist_ok=True)
    
    def create_backup(self, version_str: str) -> Path:
        """Crée une sauvegarde de la version actuelle"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = self.backup_base / f"v{version_str}_{timestamp}"
        
        try:
            shutil.copytree(SRC_PATH, backup_dir)
            logger.info(f"Sauvegarde créée: {backup_dir}")
            return backup_dir
        except Exception as e:
            logger.error(f"Erreur sauvegarde: {e}")
            raise
    
    def restore_backup(self, backup_path: Path) -> bool:
        """Restaure une sauvegarde"""
        try:
            if SRC_PATH.exists():
                shutil.rmtree(SRC_PATH)
            shutil.copytree(backup_path, SRC_PATH)
            logger.info(f"Restauration depuis: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Erreur restauration: {e}")
            return False
    
    def cleanup_old_backups(self, keep_count: int = 5):
        """Nettoie les anciennes sauvegardes"""
        try:
            backups = sorted(self.backup_base.iterdir(), 
                           key=lambda p: p.stat().st_mtime, 
                           reverse=True)
            for backup in backups[keep_count:]:
                shutil.rmtree(backup)
                logger.info(f"Sauvegarde supprimée: {backup.name}")
        except Exception as e:
            logger.error(f"Erreur nettoyage sauvegardes: {e}")


class UpdateDatabase:
    """Gestion SQLite des logs de mise à jour"""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Initialise la base de données"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS updates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version TEXT NOT NULL,
                update_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL,
                rollback BOOLEAN DEFAULT FALSE,
                backup_path TEXT,
                changelog TEXT,
                notes TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS version_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version TEXT NOT NULL,
                installed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                checksum TEXT,
                components_count INTEGER
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def log_update(self, version_str: str, status: str, backup: Optional[Path] = None,
                   changelog: str = "", rollback: bool = False, notes: str = ""):
        """Enregistre une mise à jour"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO updates 
            (version, status, backup_path, changelog, rollback, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (version_str, status, str(backup) if backup else None, changelog, rollback, notes))
        
        conn.commit()
        conn.close()
        logger.info(f"Mise à jour enregistrée: v{version_str} [{status}]")
    
    def get_update_history(self, limit: int = 20) -> List[Dict]:
        """Récupère l'historique des mises à jour"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT version, update_date, status, rollback, backup_path, changelog
            FROM updates
            ORDER BY update_date DESC
            LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                'version': row[0],
                'date': row[1],
                'status': row[2],
                'rollback': bool(row[3]),
                'backup': row[4],
                'changelog': row[5]
            }
            for row in rows
        ]


class GitHubReleaseManager:
    """Gestion des releases GitHub"""
    
    def __init__(self, repo: str):
        self.repo = repo
        self.client = None
    
    async def get_latest_release(self) -> Optional[Dict]:
        """Récupère la dernière release"""
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                url = f"{GITHUB_API}/repos/{self.repo}/releases/latest"
                response = await client.get(url)
                if response.status_code == 200:
                    return response.json()
            except Exception as e:
                logger.error(f"Erreur récupération release: {e}")
        return None
    
    async def download_release(self, download_url: str, dest_path: Path) -> bool:
        """Télécharge une release"""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(download_url, follow_redirects=True)
                if response.status_code == 200:
                    async with aiofiles.open(dest_path, 'wb') as f:
                        await f.write(response.content)
                    logger.info(f"Release téléchargée: {dest_path.name}")
                    return True
        except Exception as e:
            logger.error(f"Erreur téléchargement: {e}")
        return False
    
    @staticmethod
    def extract_release(zip_path: Path, extract_to: Path):
        """Extrait une release ZIP"""
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_to)
            logger.info(f"Release extraite dans: {extract_to}")
        except Exception as e:
            logger.error(f"Erreur extraction: {e}")
            raise


class AutoUpdater:
    """Orchestrateur principal de mises à jour"""
    
    def __init__(self):
        self.backup_mgr = BackupManager(BACKUP_PATH)
        self.db = UpdateDatabase(DB_PATH)
        self.gh_mgr = GitHubReleaseManager(GITHUB_REPO)
        self.last_check = None
        self.auto_mode = False
    
    async def check_for_updates(self, force: bool = False) -> Optional[Dict]:
        """Vérifie les mises à jour disponibles"""
        now = datetime.now()
        
        if not force and self.last_check:
            if (now - self.last_check).total_seconds() < CHECK_INTERVAL * 3600:
                logger.debug("Check déjà effectué récemment")
                return None
        
        logger.info("Vérification des mises à jour...")
        release = await self.gh_mgr.get_latest_release()
        
        if not release:
            logger.warning("Impossible de vérifier les mises à jour")
            return None
        
        self.last_check = now
        tag = release.get('tag_name', '').lstrip('v')
        
        if VersionComparer.is_newer(tag, CURRENT_VERSION):
            logger.info(f"Nouvelle version disponible: v{tag}")
            return release
        
        logger.info(f"Vous avez la dernière version (v{CURRENT_VERSION})")
        return None
    
    async def perform_update(self, release: Dict) -> bool:
        """Effectue la mise à jour"""
        try:
            tag = release.get('tag_name', '').lstrip('v')
            logger.info(f"Début mise à jour vers v{tag}")
            
            # Sauvegarde
            backup_path = self.backup_mgr.create_backup(CURRENT_VERSION)
            
            # Téléchargement
            download_url = None
            for asset in release.get('assets', []):
                if asset['name'].endswith('.zip'):
                    download_url = asset['browser_download_url']
                    break
            
            if not download_url:
                raise ValueError("Aucun asset ZIP trouvé")
            
            temp_zip = BASE_PATH / "temp_release.zip"
            if not await self.gh_mgr.download_release(download_url, temp_zip):
                raise Exception("Téléchargement échoué")
            
            # Vérification intégrité
            if not await self._verify_download(release, temp_zip):
                temp_zip.unlink()
                raise Exception("Vérification intégrité échouée")
            
            # Extraction
            extract_path = BASE_PATH / "temp_extract"
            extract_path.mkdir(exist_ok=True)
            self.gh_mgr.extract_release(temp_zip, extract_path)
            
            # Remplacement
            self._replace_code(extract_path)
            
            # Test démarrage
            if not await self._test_startup():
                logger.error("Erreur au démarrage, rollback...")
                self.backup_mgr.restore_backup(backup_path)
                self.db.log_update(tag, "FAILED_STARTUP", backup_path, rollback=True)
                return False
            
            # Nettoyage
            temp_zip.unlink()
            shutil.rmtree(extract_path)
            
            # Enregistrement
            changelog = release.get('body', '')
            self.db.log_update(tag, "SUCCESS", backup_path, changelog)
            self.backup_mgr.cleanup_old_backups()
            
            logger.info(f"Mise à jour v{tag} réussie")
            return True
            
        except Exception as e:
            logger.error(f"Erreur mise à jour: {e}")
            self.db.log_update(tag, "ERROR", notes=str(e))
            return False
    
    async def _verify_download(self, release: Dict, file_path: Path) -> bool:
        """Vérifie l'intégrité du téléchargement"""
        # Cherche le SHA256 dans le changelog
        body = release.get('body', '')
        if 'sha256:' in body.lower():
            hash_line = [l for l in body.split('\n') if 'sha256:' in l.lower()][0]
            expected_hash = hash_line.split(':')[1].strip().split()[0]
            return await IntegrityChecker.verify_file(file_path, expected_hash)
        return True
    
    def _replace_code(self, source_path: Path):
        """Remplace les fichiers source"""
        for item in source_path.iterdir():
            dest = SRC_PATH / item.name
            if dest.exists():
                shutil.rmtree(dest)
            shutil.move(str(item), str(dest))
    
    async def _test_startup(self) -> bool:
        """Teste le démarrage après mise à jour"""
        try:
            # Vérification basique des fichiers critiques
            critical_files = ['jarvis.py', 'config.json', 'requirements.txt']
            for filename in critical_files:
                if not (SRC_PATH / filename).exists():
                    return False
            return True
        except Exception as e:
            logger.error(f"Erreur test démarrage: {e}")
            return False
    
    async def enable_auto_updates(self):
        """Active les mises à jour automatiques"""
        self.auto_mode = True
        logger.info("Mises à jour automatiques activées")
        
        while self.auto_mode:
            await asyncio.sleep(CHECK_INTERVAL * 3600)
            release = await self.check_for_updates()
            if release:
                await self.perform_update(release)
    
    def disable_auto_updates(self):
        """Désactive les mises à jour automatiques"""
        self.auto_mode = False
        logger.info("Mises à jour automatiques désactivées")
    
    def get_history(self) -> List[Dict]:
        """Récupère l'historique des mises à jour"""
        return self.db.get_update_history()
    
    def get_current_version(self) -> str:
        """Retourne la version actuelle"""
        return CURRENT_VERSION


# Exemple d'utilisation
async def main():
    updater = AutoUpdater()
    
    # Mode manuel
    release = await updater.check_for_updates(force=True)
    if release:
        success = await updater.perform_update(release)
        print(f"Mise à jour: {'OK' if success else 'ÉCHOUÉE'}")
    
    # Afficher historique
    history = updater.get_history()
    print(f"\nHistorique ({len(history)} entrées):")
    for entry in history[:5]:
        print(f"  v{entry['version']} - {entry['date']} [{entry['status']}]")


if __name__ == "__main__":
    asyncio.run(main())
