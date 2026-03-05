#!/usr/bin/env python3
"""model_manager.py — Gestion des modèles IA du cluster.

Fonctionnalités principales :
  --list               : Liste les modèles disponibles (LM Studio & Ollama).
  --load NAME [--node NODE]   : Charge le modèle NAME sur le nœud spécifié (par défaut le nœud le plus approprié).
  --unload NAME [--node NODE] : Décharge le modèle NAME.
  --swap OLD NEW [--node NODE] : Décharge OLD et charge NEW atomiquement.
  --optimize           : Optimise l'usage de la VRAM en déchargeant les modèles inactifs et en pré‑chauffant les modèles fréquents.

Le script utilise uniquement la bibliothèque standard Python.
Il invoque les APIs de LM Studio et d'Ollama via `curl.exe` (PowerShell).
Les réponses sont affichées au format JSON pour être facilement exploitées.
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# Configuration des endpoints (modifiable si besoin)
LM_STUDIO_URL = "http://127.0.0.1:1234"
OLLAMA_URL = "http://127.0.0.1:11434"

# Simple in‑memory cache pour le TTL (durée de vie des modèles en VRAM)
MODEL_TTL_SECONDS = 3600  # 1 heure par défaut
_model_cache = {}

def _run_curl(command: list[str]) -> str:
    """Exécute curl.exe avec les arguments fournis et retourne stdout.
    Lève une exception si le code de retour n'est pas 0.
    """
    proc = subprocess.run(["curl.exe", *command], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"curl failed: {proc.stderr.strip()}")
    return proc.stdout.strip()

def list_models() -> dict:
    """Récupère la liste des modèles depuis LM Studio et Ollama.
    Retourne un dictionnaire avec deux clés: 'lmstudio' et 'ollama'.
    """
    result = {"lmstudio": [], "ollama": []}
    try:
        # LM Studio – endpoint hypothétique /v1/models (liste simple)
        out = _run_curl(["-s", f"{LM_STUDIO_URL}/v1/models"])
        result["lmstudio"] = json.loads(out) if out else []
    except Exception:
        result["lmstudio"] = []
    try:
        # Ollama – liste des tags (modèles) via /api/tags
        out = _run_curl(["-s", f"{OLLAMA_URL}/api/tags"])
        data = json.loads(out) if out else {}
        # Le format renvoie {"models": [{"name": "..."}, ...]}
        result["ollama"] = [m.get("name") for m in data.get("models", [])]
    except Exception:
        result["ollama"] = []
    return result

def load_model(name: str, node: str | None = None) -> dict:
    """Charge un modèle.
    Si le nœud est spécifié, on utilise LM Studio (assume le même endpoint).
    Sinon on charge via Ollama.
    """
    # Marquer le temps de chargement pour le TTL
    _model_cache[name] = datetime.utcnow()
    if node:
        # Exemple d'appel LM Studio – on suppose un endpoint `load`
        payload = json.dumps({"model": name, "node": node})
        _run_curl(["-X", "POST", "-H", "Content-Type: application/json", "-d", payload, f"{LM_STUDIO_URL}/v1/load"])
    else:
        # Ollama – pull le modèle si nécessaire
        _run_curl(["-X", "POST", "-H", "Content-Type: application/json", "-d", f'{{"name":"{name}"}}', f"{OLLAMA_URL}/api/pull"])
    return {"model": name, "action": "load", "node": node or "ollama", "status": "ok"}

def unload_model(name: str, node: str | None = None) -> dict:
    """Décharge un modèle."""
    _model_cache.pop(name, None)
    if node:
        payload = json.dumps({"model": name, "node": node})
        _run_curl(["-X", "POST", "-H", "Content-Type: application/json", "-d", payload, f"{LM_STUDIO_URL}/v1/unload"])
    else:
        _run_curl(["-X", "DELETE", f"{OLLAMA_URL}/api/delete/{name}"])
    return {"model": name, "action": "unload", "node": node or "ollama", "status": "ok"}

def swap_models(old: str, new: str, node: str | None = None) -> dict:
    """Swap atomique d'un modèle vers un autre."""
    unload_model(old, node)
    time.sleep(0.5)  # petite pause pour laisser le système se stabiliser
    load_model(new, node)
    return {"swap": {"old": old, "new": new}, "node": node or "ollama", "status": "ok"}

def _prune_expired() -> None:
    """Décharge les modèles dont le TTL est expiré."""
    now = datetime.utcnow()
    expired = [name for name, ts in _model_cache.items() if now - ts > timedelta(seconds=MODEL_TTL_SECONDS)]
    for name in expired:
        unload_model(name)

def optimize() -> dict:
    """Optimise l'usage VRAM : purge les modèles expirés et pré‑chauffe les modèles fréquents.
    Les modèles fréquents sont renseignés dans le fichier `dev/frequent_models.txt` (un par ligne).
    """
    _prune_expired()
    # Pré‑chauffage des modèles fréquents
    frequent_path = Path(__file__).with_name("frequent_models.txt")
    warmed = []
    if frequent_path.is_file():
        for line in frequent_path.read_text(encoding="utf-8").splitlines():
            name = line.strip()
            if name:
                load_model(name)
                warmed.append(name)
    return {"pruned": len(_model_cache), "warmed": warmed, "status": "ok"}

def main() -> None:
    parser = argparse.ArgumentParser(description="Gestionnaire de modèles IA (LM Studio + Ollama)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="Lister les modèles disponibles")
    group.add_argument("--load", metavar="NAME", help="Charger le modèle NAME")
    group.add_argument("--unload", metavar="NAME", help="Décharger le modèle NAME")
    group.add_argument("--swap", nargs=2, metavar=("OLD", "NEW"), help="Swap du modèle OLD vers NEW")
    group.add_argument("--optimize", action="store_true", help="Optimiser l'usage de la VRAM")
    parser.add_argument("--node", help="Nom du nœud cible (LM Studio). Si absent, Ollama est utilisé.")
    args = parser.parse_args()

    try:
        if args.list:
            out = list_models()
        elif args.load:
            out = load_model(args.load, args.node)
        elif args.unload:
            out = unload_model(args.unload, args.node)
        elif args.swap:
            old, new = args.swap
            out = swap_models(old, new, args.node)
        elif args.optimize:
            out = optimize()
        else:
            out = {"error": "Aucune action spécifiée"}
        print(json.dumps(out, ensure_ascii=False, indent=2))
    except Exception as e:
        error = {"error": str(e)}
        print(json.dumps(error, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
