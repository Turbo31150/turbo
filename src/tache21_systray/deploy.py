"""
Script de déploiement pour JARVIS Tache 21
Automatise installation, configuration et tests.
"""

import subprocess
import sys
import os
import shutil
from pathlib import Path


class Deployer:
    """Gère le déploiement complet."""

    def __init__(self):
        self.project_dir = Path(__file__).parent
        self.logs_dir = Path("F:/BUREAU/turbo/logs")
        self.venv_dir = self.project_dir / "venv"

    def log(self, message: str, level: str = "INFO"):
        """Affiche un log."""
        prefix = f"[{level}]"
        print(f"{prefix:10} {message}")

    def run_command(self, cmd: list, description: str) -> bool:
        """Exécute une commande."""
        self.log(f"Exécution: {description}", "RUN")
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_dir,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                self.log(f"Erreur: {result.stderr}", "ERROR")
                return False
            self.log(f"✓ {description}", "OK")
            return True
        except Exception as e:
            self.log(f"Exception: {e}", "ERROR")
            return False

    def create_directories(self) -> bool:
        """Crée les répertoires nécessaires."""
        self.log("Création des répertoires...", "INFO")
        try:
            self.logs_dir.mkdir(parents=True, exist_ok=True)
            (Path("F:/BUREAU/turbo/db") / "jarvis").mkdir(parents=True, exist_ok=True)
            self.log("✓ Répertoires créés", "OK")
            return True
        except Exception as e:
            self.log(f"Erreur création répertoires: {e}", "ERROR")
            return False

    def setup_venv(self) -> bool:
        """Configure l'environnement virtuel."""
        self.log("Configuration de l'environnement virtuel...", "INFO")

        if self.venv_dir.exists():
            self.log("venv existe déjà, passage", "SKIP")
            return True

        return self.run_command(
            [sys.executable, "-m", "venv", str(self.venv_dir)],
            "Création venv",
        )

    def install_dependencies(self) -> bool:
        """Installe les dépendances."""
        self.log("Installation des dépendances...", "INFO")

        pip_exe = self.venv_dir / "Scripts" / "pip.exe"
        if not pip_exe.exists():
            pip_exe = "pip"

        return self.run_command(
            [str(pip_exe), "install", "-r", "requirements.txt"],
            "Installation pip",
        )

    def setup_config(self) -> bool:
        """Configure les fichiers de config."""
        self.log("Setup configuration...", "INFO")

        config_example = self.project_dir / "config.example.py"
        config_py = self.project_dir / "config.py"

        if config_py.exists():
            self.log("config.py existe déjà, passage", "SKIP")
            return True

        try:
            shutil.copy(config_example, config_py)
            self.log("✓ config.py créé depuis config.example.py", "OK")
            return True
        except Exception as e:
            self.log(f"Erreur setup config: {e}", "ERROR")
            return False

    def run_tests(self) -> bool:
        """Lance les tests unitaires."""
        self.log("Lancement des tests...", "INFO")

        python_exe = self.venv_dir / "Scripts" / "python.exe"
        if not python_exe.exists():
            python_exe = sys.executable

        return self.run_command(
            [str(python_exe), "tests.py"],
            "Tests unitaires",
        )

    def deploy(self):
        """Lance le déploiement complet."""
        print("\n" + "=" * 60)
        print("JARVIS TACHE 21 - DÉPLOIEMENT")
        print("=" * 60 + "\n")

        steps = [
            ("Création répertoires", self.create_directories),
            ("Setup venv", self.setup_venv),
            ("Installation dépendances", self.install_dependencies),
            ("Setup configuration", self.setup_config),
            ("Exécution tests", self.run_tests),
        ]

        results = []
        for step_name, step_func in steps:
            success = step_func()
            results.append((step_name, success))
            if not success:
                self.log(f"Arrêt au step: {step_name}", "WARN")
                break

        print("\n" + "=" * 60)
        print("RÉSUMÉ DU DÉPLOIEMENT")
        print("=" * 60)

        for step_name, success in results:
            status = "✓ SUCCÈS" if success else "✗ ÉCHEC"
            print(f"{step_name:30} {status}")

        all_success = all(success for _, success in results)

        if all_success:
            print("\n✓ Déploiement complet avec succès!")
            print("\nPour démarrer JARVIS Tray:")
            python_exe = self.venv_dir / "Scripts" / "python.exe"
            if python_exe.exists():
                print(f'  {python_exe} main.py')
            else:
                print("  python main.py")
        else:
            print("\n✗ Déploiement échoué!")
            sys.exit(1)


def main():
    deployer = Deployer()
    deployer.deploy()


if __name__ == "__main__":
    main()
