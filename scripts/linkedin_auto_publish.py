#!/usr/bin/env python3
"""LinkedIn Auto-Publisher — Pipeline Playwright automatisé.

Reproduit la séquence exacte utilisée pour publier via Claude Code + Playwright MCP:
1. Navigation vers linkedin.com/feed
2. Auth Google SSO (compte MiningExpert)
3. Clic "Commencer un post"
4. Remplissage éditeur rich-text
5. Clic "Publier"

Usage:
    python linkedin_auto_publish.py --content "Mon post..."
    python linkedin_auto_publish.py --file post.txt
    python linkedin_auto_publish.py --generate  # Génère via M1 cluster

Prérequis: playwright installé (pip install playwright && playwright install chromium)
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _paths import TURBO_DIR

# === PIPELINE PLAYWRIGHT (séquence exacte) ===
# Ces étapes correspondent aux actions Playwright MCP réelles utilisées:
#
# STEP 1: browser_navigate → https://www.linkedin.com/feed/
# STEP 2: browser_snapshot → chercher dialog Google SSO
# STEP 3: browser_click ref=f8e33 → "Continuer en tant que MiningExpert"
# STEP 4: browser_wait_for time=5 → attendre redirection feed
# STEP 5: browser_snapshot → chercher bouton "Commencer un post"
# STEP 6: browser_click ref=e190 → "Commencer un post"
# STEP 7: browser_snapshot → chercher textbox éditeur
# STEP 8: browser_type ref=e728 → coller le contenu du post
# STEP 9: browser_snapshot → vérifier contenu + chercher "Publier"
# STEP 10: browser_click ref=e787 → "Publier"
# STEP 11: browser_snapshot → vérifier notification "Le post a bien été publié"
#
# Note: Les ref= changent à chaque session. En production, utiliser des sélecteurs stables.

PLAYWRIGHT_STEPS = [
    {"action": "navigate", "url": "https://www.linkedin.com/feed/"},
    {"action": "wait", "seconds": 3},
    {"action": "snapshot", "find": "Commencer un post"},
    {"action": "click", "selector": "button:has-text('Commencer un post')"},
    {"action": "wait", "seconds": 2},
    {"action": "fill", "selector": "[role='textbox'][aria-label*='créer']", "value": "{content}"},
    {"action": "wait", "seconds": 1},
    {"action": "click", "selector": "button:has-text('Publier')"},
    {"action": "wait", "seconds": 3},
    {"action": "verify", "text": "Le post a bien été publié"},
]

# Sélecteurs LinkedIn stables (Mars 2026)
SELECTORS = {
    "start_post": "button:has-text('Commencer un post')",
    "editor": "[role='textbox'][aria-label*='créer du contenu']",
    "publish": "button.share-actions__primary-action:has-text('Publier')",
    "google_sso": "button:has-text('Continuer en tant que')",
    "dismiss_notif": "button[aria-label*='Ignorez la notification']",
    "post_success": "text='Le post a bien été publié'",
}


def generate_post_m1(theme: str = "IA distribuée") -> str:
    """Génère un post via M1/qwen3-8b du cluster local."""
    prompt = (
        f"/nothink\nEcris un post LinkedIn en francais (200 mots max). "
        f"Theme: {theme}. Texte brut, emojis, hook percutant, call-to-action."
    )
    try:
        data = json.dumps({
            "model": "qwen3-8b",
            "input": prompt,
            "temperature": 0.7,
            "max_output_tokens": 1024,
            "stream": False,
            "store": False,
        }).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:1234/api/v1/chat",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            d = json.loads(resp.read())
        for block in d.get("output", []):
            if isinstance(block, dict) and block.get("type") == "message":
                content = block.get("content", "")
                return content if isinstance(content, str) else str(content)
    except Exception as e:
        print(f"[M1] Erreur génération: {e}")
    return ""


def generate_post_ol1(theme: str = "IA distribuée") -> str:
    """Fallback: génère via OL1/qwen3:1.7b."""
    try:
        data = json.dumps({
            "model": "qwen3:1.7b",
            "messages": [{"role": "user", "content":
                f"/nothink\nEcris un post LinkedIn en francais (200 mots). Theme: {theme}. "
                f"Emojis, hook percutant, CTA."}],
            "stream": False,
        }).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:11434/api/chat",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            d = json.loads(resp.read())
        return d.get("message", {}).get("content", "")
    except Exception as e:
        print(f"[OL1] Erreur génération: {e}")
    return ""


def publish_via_playwright_cli(content: str) -> bool:
    """Publie via Playwright Python (non-MCP, standalone)."""
    script = f'''
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, channel="chrome")
        ctx = await browser.new_context(storage_state="linkedin_auth.json" if __import__("os").path.exists("linkedin_auth.json") else None)
        page = await ctx.new_page()
        await page.goto("https://www.linkedin.com/feed/")
        await page.wait_for_timeout(5000)

        # Vérifier si connecté
        if "/login" in page.url:
            print("Non connecté — authentification requise via navigateur")
            await browser.close()
            return False

        # Commencer un post
        await page.click("button:has-text('Commencer un post')")
        await page.wait_for_timeout(2000)

        # Remplir l'éditeur
        editor = page.locator("[role='textbox']").first
        await editor.fill("""{content.replace('"', '/"')}""")
        await page.wait_for_timeout(1000)

        # Publier
        await page.click("button:has-text('Publier')")
        await page.wait_for_timeout(3000)

        # Sauvegarder la session pour réutilisation
        await ctx.storage_state(path="linkedin_auth.json")
        await browser.close()
        return True

asyncio.run(main())
'''
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, timeout=60,
    )
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="LinkedIn Auto-Publisher")
    parser.add_argument("--content", help="Texte du post")
    parser.add_argument("--file", help="Fichier contenant le texte du post")
    parser.add_argument("--generate", action="store_true", help="Générer via cluster M1")
    parser.add_argument("--theme", default="IA distribuée sur cluster GPU local",
                        help="Thème pour la génération")
    parser.add_argument("--dry-run", action="store_true", help="Afficher sans publier")
    parser.add_argument("--method", choices=["playwright-mcp", "playwright-cli"],
                        default="playwright-mcp",
                        help="Méthode de publication")
    args = parser.parse_args()

    # Obtenir le contenu
    content = ""
    if args.content:
        content = args.content
    elif args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            content = f.read().strip()
    elif args.generate:
        print("[*] Génération via M1...")
        content = generate_post_m1(args.theme)
        if not content:
            print("[*] M1 offline, fallback OL1...")
            content = generate_post_ol1(args.theme)

    if not content:
        print("Erreur: aucun contenu. Utiliser --content, --file ou --generate")
        sys.exit(1)

    print(f"\n{'='*50}")
    print("POST LINKEDIN:")
    print(f"{'='*50}")
    print(content)
    print(f"{'='*50}")
    print(f"Longueur: {len(content)} caractères")

    if args.dry_run:
        print("\n[DRY RUN] Post non publié.")
        sys.exit(0)

    if args.method == "playwright-mcp":
        print("\n[*] Méthode: Playwright MCP (via Claude Code)")
        print("[*] Utiliser les commandes suivantes dans Claude Code:")
        print(f"    1. browser_navigate → https://www.linkedin.com/feed/")
        print(f"    2. browser_click → 'Commencer un post'")
        print(f"    3. browser_type → [contenu du post]")
        print(f"    4. browser_click → 'Publier'")
    elif args.method == "playwright-cli":
        print("\n[*] Publication via Playwright CLI...")
        ok = publish_via_playwright_cli(content)
        print("OK" if ok else "ECHEC")
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
