#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DISK CLEANER - Script de Nettoyage et Organisation Intelligente
================================================================

Analyse, nettoie, organise et dédoublonne un disque dur avec système de scoring.

Architecture:
- FileScanner: Scan récursif et détection doublons (SHA-256)
- ScoreEngine: Attribution de scores de pertinence (0-100)
- ActionManager: Organisation et nettoyage des fichiers
- Database: Persistance SQLite pour mémorisation

Auteur: Claude Code
Version: 1.0.0
Date: 2026-02-03
"""

import os
import sys
import hashlib
import sqlite3
import shutil
import mimetypes
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from tqdm import tqdm
import json


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class Config:
    """Configuration globale du scanner."""

    # Chemins
    source_dir: str = "."
    output_dir: str = "./Dossier_Trie"
    quarantine_dir: str = "./Dossier_Trie/_QUARANTINE"
    trash_dir: str = "./Dossier_Trie/_TRASH"
    db_path: str = "./disk_cleaner.db"

    # Seuils de scoring
    score_threshold_keep: int = 60  # >= 60: À garder
    score_threshold_trash: int = 30  # < 30: Poubelle

    # Comportement
    dry_run: bool = True  # Mode simulation par défaut
    verbose: bool = True
    organize_by_year: bool = True
    organize_by_type: bool = True

    # Performance
    chunk_size: int = 8192  # Pour lecture fichiers
    max_file_size: int = 100 * 1024 * 1024  # 100 MB max pour analyse


# ============================================================================
# MODÈLES DE DONNÉES
# ============================================================================

@dataclass
class FileInfo:
    """Informations sur un fichier."""

    path: str
    name: str
    size: int
    extension: str
    mime_type: str
    hash_sha256: str
    created_at: datetime
    modified_at: datetime
    accessed_at: datetime
    score: int = 0
    score_reasons: List[str] = None
    is_duplicate: bool = False
    duplicate_of: Optional[str] = None

    def __post_init__(self):
        if self.score_reasons is None:
            self.score_reasons = []


# ============================================================================
# DATABASE MANAGER
# ============================================================================

class DatabaseManager:
    """Gestion de la base de données SQLite."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = None
        self.init_database()

    def init_database(self):
        """Initialise la base de données."""
        self.conn = sqlite3.connect(self.db_path)
        cursor = self.conn.cursor()

        # Table des fichiers analysés
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                size INTEGER NOT NULL,
                extension TEXT,
                mime_type TEXT,
                hash_sha256 TEXT NOT NULL,
                score INTEGER DEFAULT 0,
                score_reasons TEXT,
                is_duplicate BOOLEAN DEFAULT 0,
                duplicate_of TEXT,
                action TEXT DEFAULT 'pending',
                created_at TIMESTAMP,
                modified_at TIMESTAMP,
                scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Table des décisions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER,
                action TEXT NOT NULL,
                reason TEXT,
                executed BOOLEAN DEFAULT 0,
                executed_at TIMESTAMP,
                FOREIGN KEY (file_id) REFERENCES files(id)
            )
        """)

        # Index pour performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_hash ON files(hash_sha256)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_score ON files(score)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_duplicate ON files(is_duplicate)")

        self.conn.commit()

    def file_exists(self, file_path: str) -> Optional[Dict]:
        """Vérifie si un fichier est déjà en base."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM files WHERE path = ?
        """, (file_path,))
        result = cursor.fetchone()

        if result:
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, result))
        return None

    def get_by_hash(self, hash_sha256: str) -> Optional[Dict]:
        """Récupère un fichier par son hash."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM files WHERE hash_sha256 = ? LIMIT 1
        """, (hash_sha256,))
        result = cursor.fetchone()

        if result:
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, result))
        return None

    def save_file(self, file_info: FileInfo):
        """Sauvegarde les informations d'un fichier."""
        cursor = self.conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO files
            (path, name, size, extension, mime_type, hash_sha256, score,
             score_reasons, is_duplicate, duplicate_of, created_at, modified_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            file_info.path,
            file_info.name,
            file_info.size,
            file_info.extension,
            file_info.mime_type,
            file_info.hash_sha256,
            file_info.score,
            json.dumps(file_info.score_reasons),
            file_info.is_duplicate,
            file_info.duplicate_of,
            file_info.created_at,
            file_info.modified_at
        ))

        self.conn.commit()

    def save_decision(self, file_path: str, action: str, reason: str):
        """Sauvegarde une décision."""
        cursor = self.conn.cursor()

        # Récupérer l'ID du fichier
        cursor.execute("SELECT id FROM files WHERE path = ?", (file_path,))
        result = cursor.fetchone()

        if result:
            file_id = result[0]
            cursor.execute("""
                INSERT INTO decisions (file_id, action, reason)
                VALUES (?, ?, ?)
            """, (file_id, action, reason))
            self.conn.commit()

    def get_statistics(self) -> Dict:
        """Récupère les statistiques globales."""
        cursor = self.conn.cursor()

        stats = {}

        # Total fichiers
        cursor.execute("SELECT COUNT(*) FROM files")
        stats['total_files'] = cursor.fetchone()[0]

        # Total duplicates
        cursor.execute("SELECT COUNT(*) FROM files WHERE is_duplicate = 1")
        stats['total_duplicates'] = cursor.fetchone()[0]

        # Distribution des scores
        cursor.execute("""
            SELECT
                COUNT(CASE WHEN score >= 60 THEN 1 END) as high_score,
                COUNT(CASE WHEN score >= 30 AND score < 60 THEN 1 END) as medium_score,
                COUNT(CASE WHEN score < 30 THEN 1 END) as low_score
            FROM files
        """)
        result = cursor.fetchone()
        stats['high_score'] = result[0]
        stats['medium_score'] = result[1]
        stats['low_score'] = result[2]

        # Espace total
        cursor.execute("SELECT SUM(size) FROM files")
        stats['total_size'] = cursor.fetchone()[0] or 0

        return stats

    def close(self):
        """Ferme la connexion."""
        if self.conn:
            self.conn.close()


# ============================================================================
# FILE SCANNER
# ============================================================================

class FileScanner:
    """Scanner de fichiers avec détection de doublons par hash."""

    def __init__(self, config: Config, db: DatabaseManager):
        self.config = config
        self.db = db
        self.hashes_seen = {}  # cache des hash déjà vus

    def calculate_hash(self, file_path: str) -> str:
        """Calcule le hash SHA-256 d'un fichier."""
        sha256 = hashlib.sha256()

        try:
            with open(file_path, 'rb') as f:
                while chunk := f.read(self.config.chunk_size):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception as e:
            print(f"Erreur calcul hash {file_path}: {e}")
            return ""

    def scan_file(self, file_path: str) -> Optional[FileInfo]:
        """Analyse un fichier et retourne ses informations."""
        try:
            path_obj = Path(file_path)

            # Vérifier si le fichier existe
            if not path_obj.exists():
                return None

            # Récupérer les informations de base
            stat = path_obj.stat()

            # Vérifier la taille
            if stat.st_size > self.config.max_file_size:
                if self.config.verbose:
                    print(f"Fichier trop gros ignoré: {file_path}")
                return None

            # Calculer le hash
            file_hash = self.calculate_hash(file_path)
            if not file_hash:
                return None

            # Détecter le type MIME
            mime_type, _ = mimetypes.guess_type(file_path)

            # Créer l'objet FileInfo
            file_info = FileInfo(
                path=str(path_obj.absolute()),
                name=path_obj.name,
                size=stat.st_size,
                extension=path_obj.suffix.lower(),
                mime_type=mime_type or "unknown",
                hash_sha256=file_hash,
                created_at=datetime.fromtimestamp(stat.st_ctime),
                modified_at=datetime.fromtimestamp(stat.st_mtime),
                accessed_at=datetime.fromtimestamp(stat.st_atime)
            )

            # Vérifier si c'est un doublon
            if file_hash in self.hashes_seen:
                file_info.is_duplicate = True
                file_info.duplicate_of = self.hashes_seen[file_hash]
            else:
                # Vérifier en base
                existing = self.db.get_by_hash(file_hash)
                if existing:
                    file_info.is_duplicate = True
                    file_info.duplicate_of = existing['path']
                else:
                    self.hashes_seen[file_hash] = file_info.path

            return file_info

        except Exception as e:
            if self.config.verbose:
                print(f"Erreur scan fichier {file_path}: {e}")
            return None

    def scan_directory(self, directory: str) -> List[FileInfo]:
        """Scan récursif d'un répertoire."""
        files = []
        directory_path = Path(directory)

        # Compter le nombre total de fichiers
        total_files = sum(1 for _ in directory_path.rglob('*') if _.is_file())

        print(f"\n[SCAN] Scan du répertoire: {directory}")
        print(f"[FOLDER] Nombre de fichiers détectés: {total_files}")

        # Scanner avec barre de progression
        with tqdm(total=total_files, desc="Scan en cours", unit="fichier") as pbar:
            for file_path in directory_path.rglob('*'):
                if file_path.is_file():
                    file_info = self.scan_file(str(file_path))
                    if file_info:
                        files.append(file_info)
                    pbar.update(1)

        print(f"[OK] Scan terminé: {len(files)} fichiers analysés")
        return files


# ============================================================================
# SCORE ENGINE
# ============================================================================

class ScoreEngine:
    """Moteur d'attribution de scores de pertinence."""

    def __init__(self, config: Config):
        self.config = config

    def score_file(self, file_info: FileInfo) -> int:
        """Calcule le score d'un fichier (0-100)."""
        score = 50  # Score de base
        reasons = []

        # 1. Taille du fichier
        if file_info.size == 0:
            score = 0
            reasons.append("Fichier vide")
            file_info.score = score
            file_info.score_reasons = reasons
            return score
        elif file_info.size < 1024:  # < 1 KB
            score -= 20
            reasons.append("Très petit fichier")
        elif file_info.size > 10 * 1024 * 1024:  # > 10 MB
            score += 10
            reasons.append("Fichier volumineux")

        # 2. Type de fichier
        score += self._score_by_type(file_info, reasons)

        # 3. Ancienneté
        score += self._score_by_age(file_info, reasons)

        # 4. Extension
        score += self._score_by_extension(file_info, reasons)

        # 5. Doublons
        if file_info.is_duplicate:
            score -= 30
            reasons.append("Fichier dupliqué")

        # 6. Nom du fichier
        score += self._score_by_name(file_info, reasons)

        # Limiter entre 0 et 100
        score = max(0, min(100, score))

        file_info.score = score
        file_info.score_reasons = reasons

        return score

    def _score_by_type(self, file_info: FileInfo, reasons: List[str]) -> int:
        """Score basé sur le type MIME."""
        mime = file_info.mime_type

        # Images
        if mime and mime.startswith('image/'):
            # Images haute résolution
            if file_info.size > 1 * 1024 * 1024:  # > 1 MB
                reasons.append("Image haute résolution")
                return 15
            reasons.append("Image")
            return 10

        # Documents
        if mime and any(doc in mime for doc in ['pdf', 'document', 'word', 'excel', 'powerpoint']):
            reasons.append("Document important")
            return 15

        # Code source
        if mime and any(code in mime for code in ['python', 'javascript', 'text/x-']):
            reasons.append("Code source")
            return 20

        # Archives
        if mime and any(arc in mime for arc in ['zip', 'tar', 'rar', '7z']):
            reasons.append("Archive")
            return 10

        # Vidéos
        if mime and mime.startswith('video/'):
            reasons.append("Vidéo")
            return 10

        # Audio
        if mime and mime.startswith('audio/'):
            reasons.append("Audio")
            return 5

        return 0

    def _score_by_age(self, file_info: FileInfo, reasons: List[str]) -> int:
        """Score basé sur l'ancienneté."""
        days_old = (datetime.now() - file_info.modified_at).days

        # Fichiers récents (< 30 jours)
        if days_old < 30:
            reasons.append("Fichier récent")
            return 15

        # Fichiers moyens (30-365 jours)
        if days_old < 365:
            reasons.append("Fichier de l'année")
            return 5

        # Fichiers anciens (> 1 an)
        if days_old > 365:
            reasons.append("Fichier ancien")
            return -10

        return 0

    def _score_by_extension(self, file_info: FileInfo, reasons: List[str]) -> int:
        """Score basé sur l'extension."""
        ext = file_info.extension

        # Extensions temporaires
        temp_extensions = ['.tmp', '.temp', '.cache', '.bak', '.old', '.swp', '~']
        if ext in temp_extensions:
            reasons.append("Fichier temporaire")
            return -30

        # Logs anciens
        if ext == '.log' and (datetime.now() - file_info.modified_at).days > 7:
            reasons.append("Log ancien")
            return -20

        # Code source de qualité
        code_extensions = ['.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.go', '.rs']
        if ext in code_extensions:
            reasons.append("Code source")
            return 15

        # Documents professionnels
        doc_extensions = ['.pdf', '.docx', '.xlsx', '.pptx']
        if ext in doc_extensions:
            reasons.append("Document professionnel")
            return 15

        return 0

    def _score_by_name(self, file_info: FileInfo, reasons: List[str]) -> int:
        """Score basé sur le nom du fichier."""
        name = file_info.name.lower()

        # Noms suspects
        suspects = ['temp', 'tmp', 'cache', 'backup', 'old', 'copy', 'copie', 'nouveau', 'untitled']
        if any(suspect in name for suspect in suspects):
            reasons.append("Nom suspect")
            return -10

        # Numéros de version (copie (1), copie (2), etc.)
        if '(' in name and ')' in name:
            reasons.append("Copie numérotée possible")
            return -5

        return 0


# ============================================================================
# ACTION MANAGER
# ============================================================================

class ActionManager:
    """Gestionnaire des actions (déplacement, suppression, organisation)."""

    def __init__(self, config: Config, db: DatabaseManager):
        self.config = config
        self.db = db
        self.stats = {
            'moved': 0,
            'quarantined': 0,
            'trashed': 0,
            'errors': 0
        }

    def organize_file(self, file_info: FileInfo):
        """Organise un fichier selon son score."""
        try:
            # Mode dry-run
            if self.config.dry_run:
                self._dry_run_action(file_info)
                return

            # Décider de l'action
            if file_info.score >= self.config.score_threshold_keep:
                self._move_to_organized(file_info)
            elif file_info.score < self.config.score_threshold_trash:
                self._move_to_trash(file_info)
            else:
                self._move_to_quarantine(file_info)

        except Exception as e:
            self.stats['errors'] += 1
            print(f"[ERROR] Erreur organisation {file_info.name}: {e}")

    def _dry_run_action(self, file_info: FileInfo):
        """Simulation (mode dry-run)."""
        if file_info.score >= self.config.score_threshold_keep:
            action = f"[FOLDER] GARDER (score: {file_info.score})"
            dest = self._get_organized_path(file_info)
        elif file_info.score < self.config.score_threshold_trash:
            action = f"[TRASH]  TRASH (score: {file_info.score})"
            dest = self.config.trash_dir
        else:
            action = f"[WARN]  QUARANTINE (score: {file_info.score})"
            dest = self.config.quarantine_dir

        if self.config.verbose:
            print(f"{action} - {file_info.name} -> {dest}")

        self.db.save_decision(file_info.path, action, f"Score: {file_info.score}")

    def _move_to_organized(self, file_info: FileInfo):
        """Déplace vers la structure organisée."""
        dest_path = self._get_organized_path(file_info)
        self._safe_move(file_info.path, dest_path)
        self.stats['moved'] += 1
        self.db.save_decision(file_info.path, "MOVED", f"Score: {file_info.score}")

    def _move_to_quarantine(self, file_info: FileInfo):
        """Déplace vers la quarantaine."""
        dest_path = os.path.join(self.config.quarantine_dir, file_info.name)
        self._safe_move(file_info.path, dest_path)
        self.stats['quarantined'] += 1
        self.db.save_decision(file_info.path, "QUARANTINE", f"Score: {file_info.score}")

    def _move_to_trash(self, file_info: FileInfo):
        """Déplace vers la poubelle."""
        dest_path = os.path.join(self.config.trash_dir, file_info.name)
        self._safe_move(file_info.path, dest_path)
        self.stats['trashed'] += 1
        self.db.save_decision(file_info.path, "TRASH", f"Score: {file_info.score}")

    def _get_organized_path(self, file_info: FileInfo) -> str:
        """Génère le chemin organisé pour un fichier."""
        parts = [self.config.output_dir]

        # Organisation par type
        if self.config.organize_by_type:
            file_type = self._get_file_type(file_info)
            parts.append(file_type)

        # Organisation par année
        if self.config.organize_by_year:
            year = file_info.modified_at.year
            parts.append(str(year))

        # Nom du fichier
        parts.append(file_info.name)

        return os.path.join(*parts)

    def _get_file_type(self, file_info: FileInfo) -> str:
        """Détermine le type de fichier pour l'organisation."""
        mime = file_info.mime_type

        if mime and mime.startswith('image/'):
            return 'Images'
        elif mime and mime.startswith('video/'):
            return 'Videos'
        elif mime and mime.startswith('audio/'):
            return 'Audio'
        elif mime and any(doc in mime for doc in ['pdf', 'document', 'word', 'excel', 'powerpoint']):
            return 'Documents'
        elif mime and any(code in mime for code in ['python', 'javascript', 'text/x-']):
            return 'Code'
        elif mime and any(arc in mime for arc in ['zip', 'tar', 'rar']):
            return 'Archives'
        else:
            return 'Autres'

    def _safe_move(self, source: str, destination: str):
        """Déplacement sécurisé d'un fichier."""
        try:
            # Créer les dossiers parents si nécessaire
            os.makedirs(os.path.dirname(destination), exist_ok=True)

            # Gérer les conflits de noms
            if os.path.exists(destination):
                base, ext = os.path.splitext(destination)
                counter = 1
                while os.path.exists(f"{base}_{counter}{ext}"):
                    counter += 1
                destination = f"{base}_{counter}{ext}"

            # Déplacer le fichier
            shutil.move(source, destination)

            if self.config.verbose:
                print(f"[OK] Déplacé: {os.path.basename(source)} -> {destination}")

        except Exception as e:
            self.stats['errors'] += 1
            print(f"[ERROR] Erreur déplacement {source}: {e}")


# ============================================================================
# MAIN APPLICATION
# ============================================================================

class DiskCleaner:
    """Application principale de nettoyage de disque."""

    def __init__(self, config: Config):
        self.config = config
        self.db = DatabaseManager(config.db_path)
        self.scanner = FileScanner(config, self.db)
        self.score_engine = ScoreEngine(config)
        self.action_manager = ActionManager(config, self.db)

    def run(self, source_dir: str):
        """Exécute le nettoyage complet."""
        print("=" * 70)
        print("[CLEAN] DISK CLEANER - Nettoyage et Organisation Intelligente")
        print("=" * 70)

        print(f"\n[DIR] Répertoire source: {source_dir}")
        print(f"[TARGET] Mode: {'DRY-RUN (Simulation)' if self.config.dry_run else 'EXECUTION'}")
        print(f"[STATS] Seuils: Garder >={self.config.score_threshold_keep}, Trash <{self.config.score_threshold_trash}")

        # Étape 1: Scan
        print("\n" + "=" * 70)
        print("ÉTAPE 1/3 : SCAN ET DÉTECTION DE DOUBLONS")
        print("=" * 70)
        files = self.scanner.scan_directory(source_dir)

        if not files:
            print("[ERROR] Aucun fichier trouvé.")
            return

        # Étape 2: Scoring
        print("\n" + "=" * 70)
        print("ÉTAPE 2/3 : ATTRIBUTION DES SCORES")
        print("=" * 70)

        with tqdm(total=len(files), desc="Calcul des scores", unit="fichier") as pbar:
            for file_info in files:
                self.score_engine.score_file(file_info)
                self.db.save_file(file_info)
                pbar.update(1)

        # Étape 3: Organisation
        print("\n" + "=" * 70)
        print("ÉTAPE 3/3 : ORGANISATION DES FICHIERS")
        print("=" * 70)

        with tqdm(total=len(files), desc="Organisation", unit="fichier") as pbar:
            for file_info in files:
                self.action_manager.organize_file(file_info)
                pbar.update(1)

        # Statistiques finales
        self._print_statistics(files)

    def _print_statistics(self, files: List[FileInfo]):
        """Affiche les statistiques finales."""
        print("\n" + "=" * 70)
        print("[STATS] STATISTIQUES FINALES")
        print("=" * 70)

        stats = self.db.get_statistics()

        print(f"\n[FOLDER] Fichiers analysés: {stats['total_files']}")
        print(f"[SYNC] Doublons détectés: {stats['total_duplicates']}")
        print(f"[SIZE] Espace total: {self._format_size(stats['total_size'])}")

        print(f"\n[CHART] Distribution des scores:")
        print(f"   [OK] Score élevé (>=60): {stats['high_score']} fichiers")
        print(f"   [WARN]  Score moyen (30-59): {stats['medium_score']} fichiers")
        print(f"   [TRASH]  Score faible (<30): {stats['low_score']} fichiers")

        print(f"\n[TARGET] Actions effectuées:")
        print(f"   [FOLDER] Déplacés: {self.action_manager.stats['moved']}")
        print(f"   [WARN]  Quarantaine: {self.action_manager.stats['quarantined']}")
        print(f"   [TRASH]  Poubelle: {self.action_manager.stats['trashed']}")
        print(f"   [ERROR] Erreurs: {self.action_manager.stats['errors']}")

        if self.config.dry_run:
            print("\n[WARN]  MODE DRY-RUN: Aucune modification réelle effectuée.")
            print("   Pour exécuter réellement, relancez avec --execute")

        print("\n" + "=" * 70)

    def _format_size(self, size: int) -> str:
        """Formate une taille en octets."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"

    def close(self):
        """Ferme les ressources."""
        self.db.close()


# ============================================================================
# CLI
# ============================================================================

def main():
    """Point d'entrée principal."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Disk Cleaner - Nettoyage et Organisation Intelligente",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  # Mode simulation (par défaut)
  python disk_cleaner.py /path/to/folder

  # Exécution réelle
  python disk_cleaner.py /path/to/folder --execute

  # Personnaliser les seuils
  python disk_cleaner.py /path/to/folder --keep 70 --trash 20

  # Mode silencieux
  python disk_cleaner.py /path/to/folder --quiet
        """
    )

    parser.add_argument('source', help="Répertoire source à nettoyer")
    parser.add_argument('--execute', action='store_true', help="Exécuter réellement (désactive dry-run)")
    parser.add_argument('--keep', type=int, default=60, help="Seuil score pour garder (défaut: 60)")
    parser.add_argument('--trash', type=int, default=30, help="Seuil score pour poubelle (défaut: 30)")
    parser.add_argument('--output', default="./Dossier_Trie", help="Dossier de sortie")
    parser.add_argument('--db', default="./disk_cleaner.db", help="Chemin base de données")
    parser.add_argument('--quiet', action='store_true', help="Mode silencieux")

    args = parser.parse_args()

    # Configuration
    config = Config(
        source_dir=args.source,
        output_dir=args.output,
        db_path=args.db,
        score_threshold_keep=args.keep,
        score_threshold_trash=args.trash,
        dry_run=not args.execute,
        verbose=not args.quiet
    )

    # Vérifier que le répertoire source existe
    if not os.path.exists(config.source_dir):
        print(f"[ERROR] Erreur: Le répertoire '{config.source_dir}' n'existe pas.")
        sys.exit(1)

    # Lancer le nettoyage
    cleaner = DiskCleaner(config)

    try:
        cleaner.run(config.source_dir)
    except KeyboardInterrupt:
        print("\n\n[WARN]  Interruption utilisateur. Arrêt du nettoyage...")
    except Exception as e:
        print(f"\n[ERROR] Erreur fatale: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cleaner.close()
        print("\n[OK] Nettoyage terminé.")


if __name__ == "__main__":
    main()
