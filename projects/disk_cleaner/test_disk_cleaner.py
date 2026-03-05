#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test du Disk Cleaner
====================

Crée un environnement de test avec différents types de fichiers
et teste le fonctionnement du Disk Cleaner.
"""

import os
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
import random


class TestEnvironment:
    """Crée un environnement de test pour le Disk Cleaner."""

    def __init__(self):
        self.test_dir = tempfile.mkdtemp(prefix="disk_cleaner_test_")
        print(f"[DIR] Environnement de test créé : {self.test_dir}")

    def create_test_files(self):
        """Crée différents types de fichiers de test."""
        print("\n[BUILD] Création des fichiers de test...")

        # 1. Fichiers vides (score bas)
        self._create_empty_files()

        # 2. Fichiers temporaires (score bas)
        self._create_temp_files()

        # 3. Images (score élevé si grandes)
        self._create_images()

        # 4. Documents (score élevé)
        self._create_documents()

        # 5. Code source (score élevé)
        self._create_code_files()

        # 6. Doublons (score bas)
        self._create_duplicates()

        # 7. Fichiers anciens (score bas)
        self._create_old_files()

        print(f"[OK] Environnement de test prêt : {self.test_dir}")
        print(f"   Utilisez : python disk_cleaner.py \"{self.test_dir}\"")

    def _create_empty_files(self):
        """Crée des fichiers vides (score = 0)."""
        empty_dir = Path(self.test_dir) / "empty_files"
        empty_dir.mkdir(exist_ok=True)

        for i in range(5):
            (empty_dir / f"empty_{i}.txt").touch()

        print("   [OK] 5 fichiers vides créés")

    def _create_temp_files(self):
        """Crée des fichiers temporaires (score bas)."""
        temp_dir = Path(self.test_dir) / "temp_files"
        temp_dir.mkdir(exist_ok=True)

        extensions = ['.tmp', '.temp', '.cache', '.bak', '.old']
        for i, ext in enumerate(extensions):
            file_path = temp_dir / f"temp_file_{i}{ext}"
            file_path.write_text(f"Temporary data {i}" * 100)

        # Logs anciens
        log_file = temp_dir / "old.log"
        log_file.write_text("Old log data\n" * 1000)
        # Modifier la date (ancien)
        old_time = (datetime.now() - timedelta(days=30)).timestamp()
        os.utime(log_file, (old_time, old_time))

        print("   [OK] 6 fichiers temporaires créés")

    def _create_images(self):
        """Crée des fausses images (score élevé si grandes)."""
        img_dir = Path(self.test_dir) / "images"
        img_dir.mkdir(exist_ok=True)

        # Petite image (score moyen)
        (img_dir / "small.jpg").write_bytes(b"FAKE_IMAGE_DATA" * 10)

        # Grande image (score élevé)
        (img_dir / "high_res.jpg").write_bytes(b"FAKE_HD_IMAGE_DATA" * 100000)

        # Image PNG
        (img_dir / "photo.png").write_bytes(b"PNG_DATA" * 50000)

        print("   [OK] 3 images créées")

    def _create_documents(self):
        """Crée des documents (score élevé)."""
        doc_dir = Path(self.test_dir) / "documents"
        doc_dir.mkdir(exist_ok=True)

        # Document récent
        (doc_dir / "rapport_2026.pdf").write_text("Important PDF content" * 1000)

        # Excel
        (doc_dir / "data.xlsx").write_text("Excel data" * 500)

        # Word
        (doc_dir / "memo.docx").write_text("Word document" * 300)

        print("   [OK] 3 documents créés")

    def _create_code_files(self):
        """Crée des fichiers de code source (score élevé)."""
        code_dir = Path(self.test_dir) / "code"
        code_dir.mkdir(exist_ok=True)

        # Python
        python_code = '''
def hello_world():
    """Function example."""
    print("Hello, World!")
    return True

if __name__ == "__main__":
    hello_world()
'''
        (code_dir / "script.py").write_text(python_code * 10)

        # JavaScript
        js_code = '''
function calculate(a, b) {
    return a + b;
}
console.log(calculate(2, 3));
'''
        (code_dir / "app.js").write_text(js_code * 10)

        # TypeScript
        (code_dir / "types.ts").write_text("interface User { name: string; }" * 20)

        print("   [OK] 3 fichiers de code créés")

    def _create_duplicates(self):
        """Crée des fichiers en double (score bas)."""
        dup_dir = Path(self.test_dir) / "duplicates"
        dup_dir.mkdir(exist_ok=True)

        # Contenu identique
        content = "This is duplicate content\n" * 1000

        # Créer 3 copies du même fichier
        for i in range(3):
            (dup_dir / f"document_copy_{i}.txt").write_text(content)

        print("   [OK] 3 doublons créés")

    def _create_old_files(self):
        """Crée des fichiers anciens (score bas)."""
        old_dir = Path(self.test_dir) / "old_files"
        old_dir.mkdir(exist_ok=True)

        # Fichier de 2023
        old_file = old_dir / "archive_2023.txt"
        old_file.write_text("Old data from 2023" * 100)

        # Modifier la date (2 ans)
        old_time = (datetime.now() - timedelta(days=730)).timestamp()
        os.utime(old_file, (old_time, old_time))

        # Backup ancien
        backup_file = old_dir / "backup_old.bak"
        backup_file.write_text("Old backup" * 100)
        os.utime(backup_file, (old_time, old_time))

        print("   [OK] 2 fichiers anciens créés")

    def cleanup(self):
        """Supprime l'environnement de test."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
            print(f"\n[TRASH]  Environnement de test supprimé : {self.test_dir}")

    def get_statistics(self):
        """Affiche les statistiques de l'environnement de test."""
        total_files = sum(1 for _ in Path(self.test_dir).rglob('*') if _.is_file())
        total_size = sum(f.stat().st_size for f in Path(self.test_dir).rglob('*') if f.is_file())

        print(f"\n[STATS] Statistiques de l'environnement de test:")
        print(f"   [DIR] Répertoire : {self.test_dir}")
        print(f"   [FILES] Fichiers créés : {total_files}")
        print(f"   [SIZE] Taille totale : {self._format_size(total_size)}")

    def _format_size(self, size: int) -> str:
        """Formate une taille en octets."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"


def run_test():
    """Exécute un test complet."""
    print("=" * 70)
    print("TEST DU DISK CLEANER")
    print("=" * 70)

    # Créer l'environnement de test
    env = TestEnvironment()

    try:
        # Créer les fichiers
        env.create_test_files()

        # Afficher les statistiques
        env.get_statistics()

        # Instructions
        print("\n" + "=" * 70)
        print("[INFO] ÉTAPES SUIVANTES")
        print("=" * 70)

        print(f"\n1.  Mode Simulation (Dry-Run) :")
        print(f'   python disk_cleaner.py "{env.test_dir}"')

        print(f"\n2.  Mode Exécution (Modifications réelles) :")
        print(f'   python disk_cleaner.py "{env.test_dir}" --execute')

        print(f"\n3.  Nettoyage de l'environnement de test :")
        print(f"   python test_disk_cleaner.py --cleanup")

        print("\n" + "=" * 70)
        print("[WARN]  L'environnement de test est prêt. Testez le Disk Cleaner !")
        print("=" * 70)

    except Exception as e:
        print(f"\n[ERROR] Erreur lors de la création de l'environnement : {e}")
        import traceback
        traceback.print_exc()
        env.cleanup()


def main():
    """Point d'entrée principal."""
    import argparse

    parser = argparse.ArgumentParser(description="Test du Disk Cleaner")
    parser.add_argument('--cleanup', action='store_true', help="Nettoyer tous les environnements de test")

    args = parser.parse_args()

    if args.cleanup:
        # Supprimer tous les dossiers de test
        temp_dir = Path(tempfile.gettempdir())
        count = 0

        for test_dir in temp_dir.glob("disk_cleaner_test_*"):
            if test_dir.is_dir():
                shutil.rmtree(test_dir)
                count += 1
                print(f"[TRASH]  Supprimé : {test_dir}")

        if count > 0:
            print(f"\n[OK] {count} environnement(s) de test supprimé(s)")
        else:
            print("[INFO]  Aucun environnement de test à supprimer")
    else:
        run_test()


if __name__ == "__main__":
    main()
