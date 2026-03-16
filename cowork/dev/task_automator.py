#!/usr/bin/env python3
"""task_automator.py

Automatiseur de tâches Windows via des *workflows* définis en JSON.

Un workflow est un objet JSON stocké dans ``automator.json`` :

```json
{
  "my_workflow": {
    "description": "Exemple simple",
    "steps": [
      {
        "command": "echo Hello",
        "condition": "(Get-Process -Name notepad -ErrorAction SilentlyContinue) -eq $null",
        "retry": 2
      },
      {"command": "bash -Command \"Get-Date\""}
    ]
  }
}
```

Chaque *step* peut contenir :
* ``command`` – chaîne exécutée (PowerShell ou CMD, selon l'utilisateur).
* ``condition`` (optionnel) – commande PowerShell qui doit renvoyer le code de sortie 0
  pour que l'étape soit exécutée.
* ``retry`` (optionnel, entier) – nombre de tentatives supplémentaires en cas d’échec
  (code de sortie différent de 0).

CLI :
* ``--list`` – liste les workflows disponibles.
* ``--create NAME`` – crée un nouveau workflow vide avec le nom indiqué.
* ``--edit NAME`` – ouvre ``automator.json`` dans l’éditeur par défaut (``notepad``).
* ``--run WORKFLOW`` – exécute le workflow nommé.
* ``--show NAME`` – affiche le JSON complet du workflow.

Le script ne dépend que de la bibliothèque standard : ``json``, ``subprocess``,
``argparse``, ``pathlib`` et ``time``.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Chemins et chargement
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
WORKFLOWS_FILE = BASE_DIR / "automator.json"

def load_workflows() -> dict:
    if not WORKFLOWS_FILE.is_file():
        return {}
    try:
        with WORKFLOWS_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[task_automator] Erreur de lecture du fichier workflows : {e}", file=sys.stderr)
        return {}

def save_workflows(data: dict):
    try:
        with WORKFLOWS_FILE.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[task_automator] Erreur d'écriture du fichier workflows : {e}", file=sys.stderr)

# ---------------------------------------------------------------------------
# Gestion des workflows
# ---------------------------------------------------------------------------

def list_workflows():
    data = load_workflows()
    if not data:
        print("[task_automator] Aucun workflow déclaré.")
        return
    print("Workflows disponibles :")
    for name, details in data.items():
        desc = details.get("description", "(no description)")
        print(f"  - {name}: {desc}")

def create_workflow(name: str):
    data = load_workflows()
    if name in data:
        print(f"[task_automator] Un workflow nommé '{name}' existe déjà.")
        return
    data[name] = {"description": "", "steps": []}
    save_workflows(data)
    print(f"[task_automator] Workflow '{name}' créé (vide). Vous pouvez l'éditer via --edit {name}.")

def edit_workflow(name: str):
    # Simple implémentation : ouvrir le fichier complet avec notepad.
    # L'utilisateur pourra modifier la section du workflow.
    if not WORKFLOWS_FILE.is_file():
        print("[task_automator] Aucun fichier de workflows trouvé – création d'un nouveau fichier.")
        save_workflows({})
    # Try to open with the default editor – use notepad on Windows.
    try:
        subprocess.Popen(["notepad.exe", str(WORKFLOWS_FILE)])
        print(f"[task_automator] Ouverture de {WORKFLOWS_FILE} avec notepad. Modifiez le workflow '{name}'.")
    except Exception as e:
        print(f"[task_automator] Impossible d'ouvrir l'éditeur : {e}", file=sys.stderr)

def show_workflow(name: str):
    data = load_workflows()
    wf = data.get(name)
    if not wf:
        print(f"[task_automator] Workflow '{name}' introuvable.")
        return
    print(json.dumps({name: wf}, ensure_ascii=False, indent=2))

# ---------------------------------------------------------------------------
# Exécution d'une étape
# ---------------------------------------------------------------------------

def evaluate_condition(condition: str) -> bool:
    """Execute the PowerShell condition, return True if exit code 0."""
    try:
        subprocess.check_output([
            "bash", "-NoProfile", "-Command", condition
        ], stderr=subprocess.STDOUT, timeout=15)
        return True
    except subprocess.CalledProcessError:
        return False
    except Exception as e:
        print(f"[task_automator] Condition error: {e}", file=sys.stderr)
        return False

def run_command(command: str) -> int:
    """Run the command via the system shell (PowerShell by default) and return exit code."""
    try:
        # Use PowerShell to keep consistency with condition syntax
        subprocess.check_call([
            "bash", "-NoProfile", "-Command", command
        ], timeout=120)
        return 0
    except subprocess.CalledProcessError as e:
        return e.returncode
    except Exception as e:
        print(f"[task_automator] Command execution error: {e}", file=sys.stderr)
        return -1

# ---------------------------------------------------------------------------
# Exécution d'un workflow
# ---------------------------------------------------------------------------

def run_workflow(name: str):
    data = load_workflows()
    wf = data.get(name)
    if not wf:
        print(f"[task_automator] Workflow '{name}' introuvable.")
        return
    steps = wf.get("steps", [])
    if not steps:
        print(f"[task_automator] Workflow '{name}' ne contient aucune étape.")
        return
    print(f"[task_automator] Exécution du workflow '{name}' ({len(steps)} étapes)…")
    for idx, step in enumerate(steps, start=1):
        cmd = step.get("command")
        if not cmd:
            print(f"  Étape {idx}: aucune commande, ignorée.")
            continue
        condition = step.get("condition")
        retry = int(step.get("retry", 0))
        # Condition check
        if condition:
            ok = evaluate_condition(condition)
            if not ok:
                print(f"  Étape {idx}: condition échouée, étape sautée.")
                continue
        # Execute avec retries
        attempt = 0
        while True:
            attempt += 1
            print(f"  Étape {idx} (tentative {attempt}) – exécution: {cmd}")
            ret = run_command(cmd)
            if ret == 0:
                print(f"    → Succès (code 0)")
                break
            else:
                print(f"    → Échec (code {ret})")
                if attempt > retry:
                    print(f"    → Nombre maximal de retries atteint, passage à l'étape suivante.")
                    break
                else:
                    print(f"    → Nouvelle tentative dans 2 s …")
                    time.sleep(2)
    print(f"[task_automator] Workflow '{name}' terminé.")

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Automatiseur de tâches Windows via workflows JSON.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="Lister les workflows existants")
    group.add_argument("--create", metavar="NAME", help="Créer un nouveau workflow vide")
    group.add_argument("--edit", metavar="NAME", help="Éditer le workflow (ouvre automator.json)")
    group.add_argument("--run", metavar="NAME", help="Exécuter le workflow indiqué")
    group.add_argument("--show", metavar="NAME", help="Afficher le JSON complet du workflow")
    args = parser.parse_args()

    if args.list:
        list_workflows()
    elif args.create:
        create_workflow(args.create)
    elif args.edit:
        edit_workflow(args.edit)
    elif args.run:
        run_workflow(args.run)
    elif args.show:
        show_workflow(args.show)

if __name__ == "__main__":
    main()
