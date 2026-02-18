#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Déploiement automatique du modèle fine-tuné dans LM Studio
Automatise : recherche GGUF → copie → redémarrage LMS → test santé
"""

import os
import sys
import shutil
import subprocess
import time
import json
from pathlib import Path
from datetime import datetime
import requests
from typing import Optional, Tuple

# Configuration chemins
GGUF_SOURCE_DIR = r"F:\BUREAU\turbo\finetuning\gguf"
LMS_MODEL_DIR = r"F:\models lmsqtudio\jarvis-qwen3-30b-finetune"
LMS_CLI = r"C:\Users\franc\.lmstudio\bin\lms.exe"
LMS_SERVER_URL = "http://10.5.0.2:1234"  # IMPORTANT: IP directe PAS localhost (IPv6 latence)
MODEL_NAME = "jarvis-qwen3-30b-finetune"

# Logs et rapports
LOG_DIR = Path(r"F:\BUREAU\turbo\finetuning\logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
REPORT_FILE = LOG_DIR / f"deploy_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"


def log_message(msg: str, level: str = "INFO") -> None:
    """Affiche et enregistre un message de log"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prefix = f"[{timestamp}] [{level:8s}]"
    print(f"{prefix} {msg}")


def find_latest_gguf() -> Optional[Path]:
    """
    Cherche le dernier fichier GGUF dans le répertoire source
    Retourne: Path du dernier fichier GGUF ou None
    """
    log_message("Recherche du dernier fichier GGUF...", "INFO")

    gguf_dir = Path(GGUF_SOURCE_DIR)
    if not gguf_dir.exists():
        log_message(f"Répertoire GGUF introuvable: {GGUF_SOURCE_DIR}", "ERROR")
        return None

    gguf_files = list(gguf_dir.glob("*.gguf"))
    if not gguf_files:
        log_message(f"Aucun fichier GGUF trouvé dans {GGUF_SOURCE_DIR}", "WARNING")
        return None

    # Trier par date de modification (le plus récent en premier)
    latest_gguf = max(gguf_files, key=lambda p: p.stat().st_mtime)
    file_size_mb = latest_gguf.stat().st_size / (1024 * 1024)
    log_message(f"Fichier GGUF trouvé: {latest_gguf.name} ({file_size_mb:.2f} MB)", "SUCCESS")

    return latest_gguf


def copy_model_to_lms(gguf_file: Path) -> bool:
    """
    Copie le fichier GGUF vers le répertoire LM Studio
    Retourne: True si succès, False sinon
    """
    log_message(f"Copie du modèle vers LM Studio...", "INFO")

    try:
        lms_dir = Path(LMS_MODEL_DIR)
        lms_dir.mkdir(parents=True, exist_ok=True)

        dest_path = lms_dir / gguf_file.name
        log_message(f"Source: {gguf_file}", "DEBUG")
        log_message(f"Destination: {dest_path}", "DEBUG")

        # Copie avec barre de progression basique
        shutil.copy2(gguf_file, dest_path)
        dest_size_mb = dest_path.stat().st_size / (1024 * 1024)
        log_message(f"Modèle copié avec succès ({dest_size_mb:.2f} MB)", "SUCCESS")

        return True

    except Exception as e:
        log_message(f"Erreur lors de la copie: {str(e)}", "ERROR")
        return False


def check_lms_server() -> bool:
    """
    Vérifie si le serveur LM Studio est accessible
    Retourne: True si serveur accessible, False sinon
    """
    try:
        response = requests.get(f"{LMS_SERVER_URL}/api/v1/models", timeout=5)
        return response.status_code == 200
    except Exception:
        return False


def restart_lms_server() -> bool:
    """
    Redémarre le serveur LM Studio via CLI
    Retourne: True si succès, False sinon
    """
    log_message("Arrêt du serveur LM Studio...", "INFO")

    try:
        # Arrêt du serveur
        subprocess.run(
            [LMS_CLI, "server", "stop"],
            capture_output=True,
            timeout=30
        )
        time.sleep(2)  # Attendre l'arrêt complet

        # Démarrage du serveur
        log_message("Démarrage du serveur LM Studio...", "INFO")
        subprocess.Popen(
            [LMS_CLI, "server", "start"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        # Attendre que le serveur soit prêt
        log_message("Attente de disponibilité du serveur (max 60s)...", "INFO")
        for attempt in range(120):  # 120 * 0.5s = 60s max
            if check_lms_server():
                log_message("Serveur LM Studio prêt", "SUCCESS")
                return True
            time.sleep(0.5)

        log_message("Timeout: serveur LM Studio ne répond pas", "ERROR")
        return False

    except Exception as e:
        log_message(f"Erreur lors du redémarrage: {str(e)}", "ERROR")
        return False


def load_model_in_lms(model_filename: str) -> bool:
    """
    Charge le modèle fine-tuné dans LM Studio via CLI
    Retourne: True si succès, False sinon
    """
    log_message(f"Chargement du modèle {model_filename}...", "INFO")

    try:
        # Commande pour charger le modèle
        result = subprocess.run(
            [LMS_CLI, "load", model_filename],
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode == 0:
            log_message(f"Modèle {model_filename} chargé avec succès", "SUCCESS")
            return True
        else:
            log_message(f"Erreur chargement: {result.stderr}", "ERROR")
            return False

    except Exception as e:
        log_message(f"Erreur lors du chargement: {str(e)}", "ERROR")
        return False


def health_check() -> Tuple[bool, dict]:
    """
    Lance un test de santé rapide
    Envoie une requête simple à 10.5.0.2:1234
    Retourne: (succès, détails)
    """
    log_message("Test de santé du serveur...", "INFO")

    health_data = {
        "timestamp": datetime.now().isoformat(),
        "server_url": LMS_SERVER_URL,
        "test_prompt": "Bonjour, comment tu fonctionnes?",
        "success": False,
        "response_time": 0.0,
        "error": None
    }

    try:
        start_time = time.time()
        response = requests.post(
            f"{LMS_SERVER_URL}/api/v1/chat",
            json={
                "model": MODEL_NAME,
                "input": "Bonjour, comment tu fonctionnes?",
                "max_output_tokens": 50,
                "temperature": 0.1,
                "stream": False,
                "store": False,
            },
            timeout=30
        )
        response_time = time.time() - start_time
        health_data["response_time"] = response_time

        if response.status_code == 200:
            response_json = response.json()
            if "output" in response_json and len(response_json["output"]) > 0:
                reply = response_json["output"][0]["content"]
                health_data["success"] = True
                health_data["response"] = reply
                log_message(
                    f"Test réussi en {response_time:.2f}s\n"
                    f"  Réponse: {reply[:100]}...",
                    "SUCCESS"
                )
                return True, health_data

        health_data["error"] = f"Status {response.status_code}"
        log_message(f"Erreur: réponse serveur {response.status_code}", "ERROR")
        return False, health_data

    except requests.Timeout:
        health_data["error"] = "Timeout (30s)"
        log_message("Erreur: timeout du serveur (30s)", "ERROR")
        return False, health_data

    except Exception as e:
        health_data["error"] = str(e)
        log_message(f"Erreur: {str(e)}", "ERROR")
        return False, health_data


def generate_deployment_report(
    gguf_file: Optional[Path],
    copy_success: bool,
    restart_success: bool,
    load_success: bool,
    health_success: bool,
    health_data: dict
) -> dict:
    """
    Génère un rapport de déploiement JSON
    """
    report = {
        "timestamp": datetime.now().isoformat(),
        "deployment_summary": {
            "gguf_file_found": gguf_file is not None,
            "gguf_filename": gguf_file.name if gguf_file else None,
            "gguf_size_mb": (gguf_file.stat().st_size / (1024 * 1024)) if gguf_file else None,
            "model_copied": copy_success,
            "server_restarted": restart_success,
            "model_loaded": load_success,
            "health_check_passed": health_success,
            "overall_status": "SUCCESS" if all([
                gguf_file,
                copy_success,
                restart_success,
                load_success,
                health_success
            ]) else "FAILED"
        },
        "health_check": health_data,
        "paths": {
            "gguf_source": GGUF_SOURCE_DIR,
            "lms_destination": LMS_MODEL_DIR,
            "lms_cli": LMS_CLI,
            "lms_server_url": LMS_SERVER_URL
        }
    }

    # Sauvegarde le rapport
    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    log_message(f"Rapport sauvegardé: {REPORT_FILE}", "INFO")
    return report


def display_final_report(report: dict) -> None:
    """
    Affiche un résumé visuel du rapport de déploiement
    """
    summary = report["deployment_summary"]

    print("\n" + "="*70)
    print("RAPPORT DE DÉPLOIEMENT - JARVIS FINE-TUNED".center(70))
    print("="*70)

    print(f"\nModèle GGUF:")
    print(f"  Trouvé: {'✓' if summary['gguf_file_found'] else '✗'}")
    if summary['gguf_filename']:
        print(f"  Nom: {summary['gguf_filename']}")
        print(f"  Taille: {summary['gguf_size_mb']:.2f} MB")

    print(f"\nÉtapes de déploiement:")
    print(f"  Copie modèle: {'✓ SUCCÈS' if summary['model_copied'] else '✗ ÉCHOUE'}")
    print(f"  Redémarrage serveur: {'✓ SUCCÈS' if summary['server_restarted'] else '✗ ÉCHOUE'}")
    print(f"  Chargement modèle: {'✓ SUCCÈS' if summary['model_loaded'] else '✗ ÉCHOUE'}")

    print(f"\nTest de santé:")
    if summary['health_check_passed']:
        print(f"  ✓ SUCCÈS")
        health = report["health_check"]
        print(f"  Temps réponse: {health['response_time']:.2f}s")
        if 'response' in health:
            print(f"  Réponse: {health['response'][:80]}...")
    else:
        print(f"  ✗ ÉCHOUE")
        if report["health_check"].get("error"):
            print(f"  Erreur: {report['health_check']['error']}")

    print(f"\n📊 STATUT GLOBAL: {summary['overall_status']}")
    print(f"📁 Rapport: {REPORT_FILE}")
    print("="*70 + "\n")


def main() -> int:
    """Fonction principale du déploiement"""

    log_message("Démarrage du déploiement JARVIS Fine-Tuned", "INFO")
    log_message(f"Configuration: {LMS_MODEL_DIR}", "DEBUG")

    # Étape 1: Trouver le fichier GGUF
    gguf_file = find_latest_gguf()
    if not gguf_file:
        log_message("Déploiement annulé: aucun fichier GGUF trouvé", "FATAL")
        report = generate_deployment_report(None, False, False, False, False, {
            "error": "Aucun fichier GGUF trouvé",
            "timestamp": datetime.now().isoformat()
        })
        display_final_report(report)
        return 1

    # Étape 2: Copier le modèle
    copy_success = copy_model_to_lms(gguf_file)
    if not copy_success:
        log_message("Déploiement annulé: erreur copie", "FATAL")
        report = generate_deployment_report(gguf_file, False, False, False, False, {
            "error": "Erreur lors de la copie du modèle",
            "timestamp": datetime.now().isoformat()
        })
        display_final_report(report)
        return 1

    # Étape 3: Redémarrer le serveur LMS
    restart_success = restart_lms_server()
    if not restart_success:
        log_message("Avertissement: serveur LMS ne répond pas", "WARNING")

    # Étape 4: Charger le modèle
    load_success = load_model_in_lms(gguf_file.name)

    # Étape 5: Test de santé
    time.sleep(3)  # Attendre un peu avant le test
    health_success, health_data = health_check()

    # Génération du rapport
    report = generate_deployment_report(
        gguf_file,
        copy_success,
        restart_success,
        load_success,
        health_success,
        health_data
    )

    display_final_report(report)

    # Code de retour
    return 0 if report["deployment_summary"]["overall_status"] == "SUCCESS" else 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        log_message("Déploiement interrompu par l'utilisateur", "WARNING")
        sys.exit(130)
    except Exception as e:
        log_message(f"Erreur non gérée: {str(e)}", "FATAL")
        sys.exit(1)
