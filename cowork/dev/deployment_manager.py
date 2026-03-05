#!/usr/bin/env python3
"""deployment_manager.py

Gestionnaire de déploiement pour le workspace JARVIS.
Git commit, push, vérification et rollback.

CLI :
    --deploy [MSG]   : Commit + push vers le remote
    --status         : État du repo git (branch, ahead/behind, dirty)
    --rollback [N]   : Revenir de N commits (défaut: 1)
    --history        : Derniers 10 commits
"""

import argparse
import subprocess
import sys
from datetime import datetime
from typing import List, Optional

TELEGRAM_TOKEN = "TELEGRAM_TOKEN_REDACTED"
TELEGRAM_CHAT_ID = "2010747443"

def telegram_send(msg: str):
    import urllib.parse, urllib.request
    try:
        data = urllib.parse.urlencode({"chat_id": TELEGRAM_CHAT_ID, "text": msg}).encode()
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=10)
    except Exception:
        pass

def run_cmd(cmd: List[str], timeout: int = 30) -> str:
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT, timeout=timeout).strip()
    except subprocess.CalledProcessError as e:
        return f"ERROR: {e.output.strip() if e.output else str(e)}"
    except Exception as e:
        return f"ERROR: {e}"

def git(*args) -> str:
    return run_cmd(["git"] + list(args))

# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------
def show_status():
    branch = git("branch", "--show-current")
    status = git("status", "--porcelain")
    remote = git("remote", "-v")

    dirty_files = [l for l in status.splitlines() if l.strip()]
    ahead_behind = git("rev-list", "--left-right", "--count", f"origin/{branch}...HEAD") if branch else ""

    print(f"=== Déploiement JARVIS ===")
    print(f"Branche : {branch or 'N/A'}")

    if ahead_behind and not ahead_behind.startswith("ERROR"):
        parts = ahead_behind.split()
        if len(parts) == 2:
            behind, ahead = parts
            print(f"Commits : {ahead} en avance, {behind} en retard")

    if dirty_files:
        print(f"Fichiers modifiés : {len(dirty_files)}")
        for f in dirty_files[:10]:
            print(f"  {f}")
    else:
        print("Working tree : propre")

    if remote:
        print(f"\nRemote :")
        for line in remote.splitlines()[:2]:
            print(f"  {line}")

# ---------------------------------------------------------------------------
# Deploy
# ---------------------------------------------------------------------------
def deploy(message: Optional[str] = None):
    # Check if git repo
    check = git("status")
    if check.startswith("ERROR"):
        print("[deployment_manager] Pas un repo git ou git non disponible.")
        return

    branch = git("branch", "--show-current")
    status = git("status", "--porcelain")
    dirty = [l for l in status.splitlines() if l.strip()]

    if not dirty:
        print("[deployment_manager] Rien à déployer (working tree propre).")
        return

    # Stage all
    print(f"[deployment_manager] {len(dirty)} fichier(s) à committer...")
    git("add", "-A")

    # Commit
    msg = message or f"JARVIS auto-deploy {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    result = git("commit", "-m", msg)
    if result.startswith("ERROR"):
        print(f"[deployment_manager] Erreur commit : {result}")
        return
    print(f"[deployment_manager] Commit : {msg}")

    # Push
    push_result = git("push", "origin", branch)
    if "ERROR" in push_result and "rejected" in push_result.lower():
        print(f"[deployment_manager] Push rejeté. Tentative pull --rebase...")
        git("pull", "--rebase", "origin", branch)
        push_result = git("push", "origin", branch)

    if push_result.startswith("ERROR"):
        print(f"[deployment_manager] Erreur push : {push_result}")
    else:
        print(f"[deployment_manager] Push OK → origin/{branch}")
        telegram_send(f"🚀 Deploy JARVIS — {len(dirty)} fichier(s) → {branch}\n{msg}")

# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------
def show_history():
    log = git("log", "--oneline", "-10", "--format=%h %s (%cr)")
    if log.startswith("ERROR"):
        print("[deployment_manager] Pas de repo git.")
        return
    print("Derniers commits :")
    for line in log.splitlines():
        print(f"  {line}")

# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------
def rollback(n: int = 1):
    branch = git("branch", "--show-current")
    print(f"[deployment_manager] Rollback de {n} commit(s) sur {branch}...")
    result = git("revert", "--no-edit", f"HEAD~{n}..HEAD")
    if result.startswith("ERROR"):
        print(f"[deployment_manager] Erreur rollback : {result}")
    else:
        print(f"[deployment_manager] Rollback OK ({n} commits)")
        telegram_send(f"⏪ Rollback JARVIS — {n} commit(s) annulé(s)")

def main():
    parser = argparse.ArgumentParser(description="Gestionnaire de déploiement JARVIS.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--deploy", nargs="?", const=None, metavar="MSG", help="Commit + push")
    group.add_argument("--status", action="store_true", help="État du repo")
    group.add_argument("--rollback", nargs="?", const=1, type=int, metavar="N", help="Rollback N commits")
    group.add_argument("--history", action="store_true", help="Derniers commits")
    args = parser.parse_args()

    if args.deploy is not None or (hasattr(args, 'deploy') and args.deploy is None and not args.status and not args.rollback and not args.history):
        deploy(args.deploy)
    elif args.status:
        show_status()
    elif args.rollback is not None:
        rollback(args.rollback)
    elif args.history:
        show_history()

if __name__ == "__main__":
    main()
