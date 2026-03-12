#!/usr/bin/env python3
"""model_rotator.py

Batch 4.3 – Rotation automatique des modèles pour LM Studio.

Fonctionnalités :
* **--status**   – Affiche la VRAM totale/utilisée (tous les GPU) et les modèles actuellement chargés.
* **--load <model>**   – Charge le modèle indiqué via l'API LM Studio.
* **--unload <model>** – Décharge le modèle indiqué via l'API LM Studio.
* **--auto**   – Rotation intelligente : selon la VRAM libre, charge le modèle « deep » (qwen3‑30b) ou le modèle par défaut « light » (qwen3‑8b) et décharge l’autre.

Utilise uniquement la bibliothèque standard : `subprocess`, `json`, `urllib.request`, `argparse`.
Assume que LM Studio écoute sur http://127.0.0.1:1234.
"""

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from typing import List, Dict, Tuple

API_BASE = "http://127.0.0.1:1234/api/v1/models"
DEFAULT_MODEL = "qwen3-8b"
DEEP_MODEL = "qwen3-30b"

def _run_nvidia_smi() -> str:
    """Execute `nvidia-smi --query-gpu=memory.total,memory.used --format=csv,noheader,nounits`.
    Retourne le texte brut de la sortie.
    """
    try:
        result = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.total,memory.used", "--format=csv,noheader,nounits"],
            text=True,
        )
        return result.strip()
    except Exception as e:
        print(f"[model_rotator] Erreur nvidia‑smi : {e}", file=sys.stderr)
        return ""

def parse_vram(smi_output: str) -> Tuple[int, int]:
    """Parse la sortie de nvidia‑smi.
    Retourne (total_mb, used_mb) en additionnant tous les GPU.
    """
    total = 0
    used = 0
    if not smi_output:
        return (0, 0)
    for line in smi_output.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != 2:
            continue
        try:
            t = int(parts[0])
            u = int(parts[1])
            total += t
            used += u
        except ValueError:
            continue
    return (total, used)

def vram_status() -> Tuple[int, int, int]:
    """Retourne (total_gb, used_gb, free_gb)."""
    total_mb, used_mb = parse_vram(_run_nvidia_smi())
    total_gb = total_mb // 1024
    used_gb = used_mb // 1024
    free_gb = max(total_gb - used_gb, 0)
    return (total_gb, used_gb, free_gb)

def get_loaded_models() -> List[str]:
    """Interroge LM Studio pour récupérer la liste des modèles chargés.
    Retourne une liste de noms.
    """
    try:
        req = urllib.request.Request(API_BASE, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.load(resp)
        # On suppose que la réponse contient une clé "models" avec des dicts possédant "name" et "loaded"
        models = data.get("models", [])
        loaded = [m.get("name") for m in models if m.get("loaded")]
        return [name for name in loaded if name]
    except Exception as e:
        print(f"[model_rotator] Erreur lors de la lecture des modèles : {e}", file=sys.stderr)
        return []

def post_action(action: str, model: str) -> bool:
    """Envoie une requête POST à LM Studio.
    `action` doit être "load" ou "unload".
    Retourne True si le code HTTP est 200‑299.
    """
    payload = json.dumps({"model": model}).encode("utf-8")
    url = f"{API_BASE}/{action}"
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if 200 <= resp.getcode() < 300:
                return True
    except urllib.error.HTTPError as he:
        print(f"[model_rotator] HTTP error {he.code} pour {action} {model}: {he.read().decode()}", file=sys.stderr)
    except Exception as e:
        print(f"[model_rotator] Erreur POST {action} {model}: {e}", file=sys.stderr)
    return False

def load_model(model: str) -> bool:
    return post_action("load", model)

def unload_model(model: str) -> bool:
    return post_action("unload", model)

def show_status():
    total_gb, used_gb, free_gb = vram_status()
    loaded = get_loaded_models()
    print("[model_rotator] VRAM - Total: {} GB, Used: {} GB, Free: {} GB".format(total_gb, used_gb, free_gb))
    print("[model_rotator] Modèles chargés : {}".format(", ".join(loaded) if loaded else "(aucun)"))

def auto_rotate():
    total_gb, used_gb, free_gb = vram_status()
    loaded = set(get_loaded_models())
    # Décision basée sur la VRAM libre : si >=30 GB, charger le modèle deep, sinon le léger.
    if free_gb >= 30:
        target, other = DEEP_MODEL, DEFAULT_MODEL
    else:
        target, other = DEFAULT_MODEL, DEEP_MODEL
    actions = []
    if target not in loaded:
        actions.append(("load", target))
    if other in loaded:
        actions.append(("unload", other))
    if not actions:
        print(f"[model_rotator] Aucun changement nécessaire (cible = {target}).")
        return
    print(f"[model_rotator] Rotation automatique - VRAM libre {free_gb} GB, cible = {target}")
    for act, mdl in actions:
        ok = load_model(mdl) if act == "load" else unload_model(mdl)
        print(f"[model_rotator] {act.upper()} {mdl} -> {'OK' if ok else 'ÉCHEC'}")

def main():
    parser = argparse.ArgumentParser(description="Rotation automatique des modèles LM Studio.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--status", action="store_true", help="Affiche VRAM + modèles chargés")
    group.add_argument("--load", metavar="MODEL", help="Charge le modèle indiqué")
    group.add_argument("--unload", metavar="MODEL", help="Décharge le modèle indiqué")
    group.add_argument("--auto", action="store_true", help="Rotation intelligente selon la VRAM disponible")
    args = parser.parse_args()

    if args.status:
        show_status()
    elif args.load:
        ok = load_model(args.load)
        print(f"[model_rotator] LOAD {args.load} → {'OK' if ok else 'ÉCHEC'}")
    elif args.unload:
        ok = unload_model(args.unload)
        print(f"[model_rotator] UNLOAD {args.unload} → {'OK' if ok else 'ÉCHEC'}")
    elif args.auto:
        auto_rotate()

if __name__ == "__main__":
    main()
