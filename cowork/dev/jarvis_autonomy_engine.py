#!/usr/bin/env python3
"""jarvis_autonomy_engine.py

Batch 28: Moteur d'autonomie JARVIS — genere et dispatch des taches
de developpement continu pour le systeme Windows JARVIS et les IA autonomes.

Architecture:
  1. Scanne le codebase JARVIS pour trouver des s, stubs, et opportunites
  2. Genere des taches de dev priorisees
  3. Dispatch au cluster via canvas proxy
  4. Notifie les resultats sur Telegram

Categories de taches:
  - Windows integration (services, registry, systray)
  - JARVIS modules (nouveaux outils MCP, agents, pipelines)
  - IA autonome (autolearn, self-improvement, proactive agents)
  - Infrastructure (tests, monitoring, resilience)

Usage :
    jarvis_autonomy_engine.py --scan       # scanne et genere des taches
    jarvis_autonomy_engine.py --dispatch   # dispatch les taches au cluster
    jarvis_autonomy_engine.py --loop       # boucle continue (scan + dispatch toutes les 30 min)
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

TURBO_ROOT = "F:/BUREAU/turbo"
PROXY_URL = "http://127.0.0.1:18800"
TELEGRAM_TOKEN = "8369376863:AAF-7YGDbun8mXWwqYJFj-eX6P78DeIu9Aw"
TELEGRAM_CHAT = "2010747443"
TASK_FILE = os.path.join(os.path.dirname(__file__), "AUTONOMY_TASKS.json")

# Categories de taches avec priorite
TASK_CATEGORIES = {
    "windows": {"priority": 1, "desc": "Integration Windows (services, systray, registry)"},
    "mcp_tools": {"priority": 2, "desc": "Nouveaux outils MCP JARVIS"},
    "agents": {"priority": 3, "desc": "Agents IA autonomes"},
    "infrastructure": {"priority": 4, "desc": "Tests, monitoring, resilience"},
    "optimization": {"priority": 5, "desc": "Performance, cache, routing"},
}


def scan_s():
    """Scanne le codebase pour trouver des /FIXME/STUB."""
    s = []
    for root, dirs, files in os.walk(TURBO_ROOT):
        # Skip node_modules, __pycache__, .git
        dirs[:] = [d for d in dirs if d not in ("node_modules", "__pycache__", ".git", "data", "models")]
        for f in files:
            if not f.endswith((".py", ".js", ".ts")):
                continue
            fpath = os.path.join(root, f)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as fh:
                    for i, line in enumerate(fh, 1):
                        for marker in ("", "FIXME", "STUB", "HACK", "XXX"):
                            if marker in line and not line.strip().startswith("#!"):
                                s.append({
                                    "file": fpath.replace("\\", "/"),
                                    "line": i,
                                    "marker": marker,
                                    "text": line.strip()[:120],
                                })
            except Exception:
                pass
    return s


def scan_stubs():
    """Trouve les fonctions stub (raise NotImplementedError, pass-only, etc.)."""
    stubs = []
    for root, dirs, files in os.walk(os.path.join(TURBO_ROOT, "src")):
        dirs[:] = [d for d in dirs if d not in ("__pycache__",)]
        for f in files:
            if not f.endswith(".py"):
                continue
            fpath = os.path.join(root, f)
            try:
                content = open(fpath, "r", encoding="utf-8", errors="ignore").read()
                # Find functions with just pass or NotImplementedError
                for m in re.finditer(r'def (\w+)\(.*?\).*?:\s*\n\s*(""".*?"""\s*\n\s*)?(pass|raise NotImplementedError)', content, re.DOTALL):
                    stubs.append({
                        "file": fpath.replace("\\", "/"),
                        "function": m.group(1),
                        "type": "stub",
                    })
            except Exception:
                pass
    return stubs


def generate_dev_tasks():
    """Genere des taches de developpement basees sur le scan."""
    tasks = []

    # Taches Windows
    tasks.append({
        "id": f"win_{int(time.time())}",
        "category": "windows",
        "title": "Ameliorer integration Windows systray notifications",
        "desc": "Ajouter des notifications toast Windows natives pour les alertes JARVIS critiques",
        "priority": 1,
        "status": "pending",
    })
    tasks.append({
        "id": f"win2_{int(time.time())}",
        "category": "windows",
        "title": "Service Windows JARVIS auto-start",
        "desc": "Creer un service Windows qui demarre automatiquement le cluster JARVIS au boot",
        "priority": 1,
        "status": "pending",
    })

    # Taches IA autonome
    tasks.append({
        "id": f"ia_{int(time.time())}",
        "category": "agents",
        "title": "Agent proactif de maintenance codebase",
        "desc": "Agent qui detecte les code smells, dead code, et propose des refactors automatiques",
        "priority": 2,
        "status": "pending",
    })
    tasks.append({
        "id": f"ia2_{int(time.time())}",
        "category": "agents",
        "title": "Agent de test automatique continu",
        "desc": "Agent qui ecrit et execute des tests pour les modules non couverts",
        "priority": 2,
        "status": "pending",
    })
    tasks.append({
        "id": f"ia3_{int(time.time())}",
        "category": "agents",
        "title": "Agent de documentation auto-generee",
        "desc": "Agent qui genere et met a jour la documentation technique des modules JARVIS",
        "priority": 3,
        "status": "pending",
    })

    # Taches MCP
    tasks.append({
        "id": f"mcp_{int(time.time())}",
        "category": "mcp_tools",
        "title": "MCP tool: clipboard_manager",
        "desc": "Outil MCP pour gerer le presse-papier Windows (historique, search, paste)",
        "priority": 3,
        "status": "pending",
    })

    # Taches infrastructure
    tasks.append({
        "id": f"infra_{int(time.time())}",
        "category": "infrastructure",
        "title": "Couverture tests 80%+ sur modules critiques",
        "desc": "Ecrire des tests unitaires pour les modules sans couverture (orchestrator, autolearn, trading)",
        "priority": 2,
        "status": "pending",
    })

    return tasks


def save_tasks(tasks):
    """Sauvegarde les taches dans un fichier JSON."""
    with open(TASK_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2, ensure_ascii=False)
    print(f"  {len(tasks)} taches sauvegardees dans {TASK_FILE}")


def load_tasks():
    """Charge les taches existantes."""
    if os.path.exists(TASK_FILE):
        with open(TASK_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def dispatch_task(task):
    """Dispatch une tache au cluster via canvas proxy."""
    prompt = f"[TASK:{task['category']}] {task['title']}\n\n{task['desc']}"
    try:
        body = json.dumps({"agent": "coding", "text": prompt}).encode()
        req = urllib.request.Request(
            f"{PROXY_URL}/chat",
            data=body, headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=120)
        data = json.loads(resp.read().decode())
        if data.get("ok"):
            result = data["data"]
            print(f"  [{result.get('model', '?')}] {task['title']}: OK ({result.get('turns', 0)} turns)")
            return result
        print(f"  {task['title']}: ERREUR - {data.get('error', '?')}")
        return None
    except Exception as e:
        print(f"  {task['title']}: ERREUR - {e}")
        return None


def notify_telegram(msg):
    """Envoie un resume sur Telegram."""
    try:
        body = json.dumps({"chat_id": TELEGRAM_CHAT, "text": msg}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data=body, headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def run_scan():
    """Scan + generation de taches."""
    print(f"\n[{time.strftime('%H:%M:%S')}] Autonomy Engine — Scan")
    print("-" * 50)

    s = scan_s()
    stubs = scan_stubs()
    print(f"  s trouves: {len(s)}")
    print(f"  Stubs trouves: {len(stubs)}")

    tasks = generate_dev_tasks()

    # Ajouter des taches basees sur les stubs
    for stub in stubs[:5]:  # max 5 stubs
        tasks.append({
            "id": f"stub_{hash(stub['function']) % 100000}",
            "category": "infrastructure",
            "title": f"Implementer stub: {stub['function']}",
            "desc": f"Implementer la fonction {stub['function']} dans {stub['file']}",
            "priority": 4,
            "status": "pending",
        })

    save_tasks(tasks)
    return tasks


def run_dispatch():
    """Dispatch les taches pending au cluster."""
    tasks = load_tasks()
    pending = [t for t in tasks if t.get("status") == "pending"]
    if not pending:
        print("  Aucune tache pending")
        return

    print(f"\n[{time.strftime('%H:%M:%S')}] Dispatch {len(pending)} taches")
    results = []
    for task in sorted(pending, key=lambda t: t.get("priority", 99))[:3]:  # max 3 a la fois
        result = dispatch_task(task)
        if result:
            task["status"] = "done"
            task["result_model"] = result.get("model", "?")
            results.append(task["title"])

    save_tasks(tasks)

    if results:
        msg = f"🤖 Autonomy Engine: {len(results)} taches completees\n" + "\n".join(f"  ✅ {r}" for r in results)
        notify_telegram(msg)


def main():
    parser = argparse.ArgumentParser(description="JARVIS Autonomy Engine")
    parser.add_argument("--scan", action="store_true", help="Scanne et genere des taches")
    parser.add_argument("--dispatch", action="store_true", help="Dispatch les taches au cluster")
    parser.add_argument("--loop", action="store_true", help="Boucle continue (30 min)")
    args = parser.parse_args()

    if args.loop:
        print("Mode boucle (Ctrl+C pour arreter)")
        while True:
            run_scan()
            run_dispatch()
            time.sleep(1800)  # 30 min
    elif args.dispatch:
        run_dispatch()
    else:
        run_scan()


if __name__ == "__main__":
    main()
