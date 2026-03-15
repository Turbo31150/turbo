#!/usr/bin/env python3
"""linkedin_publisher.py — Multi-method LinkedIn post publisher.

Tries 5 different methods to publish a LinkedIn post:
  1. CLIPBOARD + BROWSER: Copy to clipboard, open LinkedIn, ready to paste
  2. CDP PILOT: Use browser_pilot.py to navigate and type
  3. PLAYWRIGHT: Headless browser automation
  4. TELEGRAM DRAFT: Send as draft to Telegram for manual posting
  5. FILE EXPORT: Save as ready-to-paste files (FR + EN)

CLI:
    --post "text"           : Post content to publish
    --post-file path        : Read post from file
    --method all|clipboard|cdp|playwright|telegram|file
    --once                  : Single attempt
    --dry-run               : Show what would happen without executing

Stdlib-only for core, optional playwright for method 3.
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
from _paths import TURBO_DIR, TELEGRAM_TOKEN, TELEGRAM_CHAT

RESULTS = []


def log(method, status, detail=""):
    RESULTS.append({"method": method, "status": status, "detail": detail})
    icon = "OK" if status == "success" else "SKIP" if status == "skip" else "FAIL"
    print(f"  [{icon}] {method}: {detail}")


# --- METHOD 1: Clipboard + Browser Open ---
def method_clipboard(post_text, dry_run=False):
    """Copy post to clipboard and open LinkedIn in browser."""
    print("\n[1/5] CLIPBOARD + BROWSER OPEN")
    try:
        if dry_run:
            log("clipboard", "skip", "dry-run mode")
            return

        # Copy to clipboard via PowerShell (pipe to avoid quoting issues)
        ps_script = '$input | Set-Clipboard'
        r = subprocess.run(
            ['bash', '-Command', ps_script],
            input=post_text.encode('utf-8'),
            capture_output=True, timeout=10)
        if r.returncode != 0:
            log("clipboard", "fail", f"PowerShell error: {r.stderr[:200]}")
            return

        # Verify clipboard
        verify = subprocess.run(
            'bash -Command "Get-Clipboard | Measure-Object -Character | Select-Object -ExpandProperty Characters"',
            shell=True, capture_output=True, text=True, timeout=10)
        chars = verify.stdout.strip()
        print(f"  Clipboard: {chars} chars copied")

        # Open LinkedIn new post page
        subprocess.Popen(
            ['bash', '-Command',
             'Start-Process "https://www.linkedin.com/feed/"'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        log("clipboard", "success",
            f"{chars} chars in clipboard + LinkedIn opened. CTRL+V to paste.")
    except Exception as e:
        log("clipboard", "fail", str(e))


# --- METHOD 2: CDP Browser Pilot ---
def method_cdp(post_text, dry_run=False):
    """Use browser_pilot.py to navigate to LinkedIn and type the post."""
    print("\n[2/5] CDP BROWSER PILOT")
    pilot = SCRIPT_DIR / "browser_pilot.py"
    if not pilot.exists():
        log("cdp", "skip", "browser_pilot.py not found")
        return

    if dry_run:
        log("cdp", "skip", "dry-run mode")
        return

    try:
        # Check if Chrome CDP is running
        try:
            urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=3)
        except Exception:
            log("cdp", "skip", "Chrome CDP not running (port 9222). Launch with --remote-debugging-port=9222")
            return

        # Navigate to LinkedIn
        r = subprocess.run(
            [sys.executable, str(pilot), "--navigate", "https://www.linkedin.com/feed/"],
            capture_output=True, text=True, timeout=15, cwd=str(SCRIPT_DIR))
        if r.returncode != 0:
            log("cdp", "fail", f"Navigate failed: {r.stderr[:200]}")
            return

        time.sleep(3)

        # Click on "Start a post" button
        r = subprocess.run(
            [sys.executable, str(pilot), "--eval",
             "document.querySelector('.share-box-feed-entry__trigger')?.click(); 'clicked'"],
            capture_output=True, text=True, timeout=10, cwd=str(SCRIPT_DIR))

        time.sleep(2)

        # Type the post content
        r = subprocess.run(
            [sys.executable, str(pilot), "--eval",
             f"const editor = document.querySelector('.ql-editor'); "
             f"if(editor) {{ editor.innerHTML = {json.dumps(post_text.replace(chr(10), '<br>'))}; 'typed' }} "
             f"else {{ 'no editor found' }}"],
            capture_output=True, text=True, timeout=10, cwd=str(SCRIPT_DIR))

        log("cdp", "success",
            f"Post typed in LinkedIn editor. Review and click 'Post' manually.")
    except Exception as e:
        log("cdp", "fail", str(e))


# --- METHOD 3: Playwright ---
def method_playwright(post_text, dry_run=False):
    """Use Playwright to open LinkedIn and prepare the post."""
    print("\n[3/5] PLAYWRIGHT BROWSER")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log("playwright", "skip", "playwright not installed")
        return

    if dry_run:
        log("playwright", "skip", "dry-run mode")
        return

    try:
        with sync_playwright() as p:
            # Use persistent context to reuse LinkedIn session
            user_data = Path.home() / ".jarvis" / "playwright_linkedin"
            user_data.mkdir(parents=True, exist_ok=True)

            browser = p.chromium.launch_persistent_context(
                str(user_data),
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
                viewport={"width": 1280, "height": 900},
            )

            page = browser.pages[0] if browser.pages else browser.new_page()
            page.goto("https://www.linkedin.com/feed/", timeout=30000)
            time.sleep(3)

            # Check if logged in
            if "login" in page.url.lower() or "signup" in page.url.lower():
                log("playwright", "skip",
                    f"LinkedIn login required. Browser opened at {page.url}. "
                    "Log in manually, then re-run.")
                # Don't close — let user log in
                input("  Press Enter after logging in...")
                page.goto("https://www.linkedin.com/feed/", timeout=30000)
                time.sleep(2)

            # Click "Start a post"
            try:
                trigger = page.locator(".share-box-feed-entry__trigger, "
                                       "[data-control-name='identity_welcome_message'],"
                                       "button:has-text('Start a post'),"
                                       "button:has-text('Commencer un post')")
                trigger.first.click(timeout=5000)
                time.sleep(2)
            except Exception:
                log("playwright", "fail", "Could not find 'Start a post' button")
                browser.close()
                return

            # Type in the editor
            try:
                editor = page.locator(".ql-editor, [role='textbox'],"
                                      "[contenteditable='true']")
                editor.first.click()
                # Type line by line for natural formatting
                for line in post_text.split("\n"):
                    editor.first.type(line, delay=5)
                    page.keyboard.press("Enter")
                time.sleep(1)
            except Exception:
                log("playwright", "fail", "Could not type in editor")
                browser.close()
                return

            log("playwright", "success",
                f"Post typed ({len(post_text)} chars). Review and click 'Post'.")
            # Keep browser open for user to review
            input("  Press Enter to close browser (or post manually first)...")
            browser.close()

    except Exception as e:
        log("playwright", "fail", str(e))


# --- METHOD 4: Telegram Draft ---
def method_telegram(post_text, dry_run=False):
    """Send as formatted draft to Telegram for easy copy-paste."""
    print("\n[4/5] TELEGRAM DRAFT")
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        log("telegram", "skip", "No Telegram credentials")
        return

    if dry_run:
        log("telegram", "skip", "dry-run mode")
        return

    try:
        # Send the post as a formatted message
        header = "LINKEDIN POST PRET A PUBLIER\n" + "=" * 30 + "\n\n"
        footer = "\n\n" + "=" * 30 + "\nCopiez le texte ci-dessus et collez-le sur LinkedIn"

        full_msg = header + post_text + footer

        data = urllib.parse.urlencode({
            "chat_id": TELEGRAM_CHAT,
            "text": full_msg[:4000],
            "parse_mode": "",
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data)
        resp = urllib.request.urlopen(req, timeout=15)
        result = json.loads(resp.read())

        if result.get("ok"):
            log("telegram", "success",
                f"Draft sent to Telegram ({len(post_text)} chars). Copy-paste to LinkedIn.")
        else:
            log("telegram", "fail", f"Telegram API error: {result}")
    except Exception as e:
        log("telegram", "fail", str(e))


# --- METHOD 5: File Export ---
def method_file_export(post_text, dry_run=False):
    """Save as ready-to-paste text files on desktop."""
    print("\n[5/5] FILE EXPORT")
    if dry_run:
        log("file", "skip", "dry-run mode")
        return

    try:
        desktop = Path.home() / "Desktop"
        if not desktop.exists():
            desktop = Path.home() / "Bureau"
        if not desktop.exists():
            desktop = Path.home()

        ts = datetime.now().strftime("%Y%m%d_%H%M")
        filepath = desktop / f"linkedin_post_{ts}.txt"
        filepath.write_text(post_text, encoding="utf-8")

        log("file", "success",
            f"Saved to {filepath} ({len(post_text)} chars). Open and copy-paste.")
    except Exception as e:
        log("file", "fail", str(e))


def run_all_methods(post_text, methods="all", dry_run=False):
    """Try all publication methods."""
    print("=" * 60)
    print("  LINKEDIN MULTI-PUBLISHER")
    print(f"  Post: {len(post_text)} chars")
    print(f"  Methods: {methods}")
    print("=" * 60)

    method_map = {
        "clipboard": method_clipboard,
        "cdp": method_cdp,
        "playwright": method_playwright,
        "telegram": method_telegram,
        "file": method_file_export,
    }

    if methods == "all":
        targets = ["clipboard", "telegram", "file", "cdp", "playwright"]
    else:
        targets = [m.strip() for m in methods.split(",")]

    for m in targets:
        if m in method_map:
            method_map[m](post_text, dry_run)
        else:
            print(f"\n  [?] Unknown method: {m}")

    # Summary
    print("\n" + "=" * 60)
    print("  RESULTS SUMMARY")
    print("=" * 60)
    for r in RESULTS:
        icon = {"success": "+", "fail": "X", "skip": "-"}[r["status"]]
        print(f"  [{icon}] {r['method']:12} {r['detail']}")

    ok = sum(1 for r in RESULTS if r["status"] == "success")
    print(f"\n  {ok}/{len(RESULTS)} methods succeeded")
    return RESULTS


def main():
    parser = argparse.ArgumentParser(description="LinkedIn Multi-Publisher")
    parser.add_argument("--post", type=str, help="Post text to publish")
    parser.add_argument("--post-file", type=str, help="Read post from file")
    parser.add_argument("--method", type=str, default="all",
                        help="Methods: all|clipboard|cdp|playwright|telegram|file")
    parser.add_argument("--once", action="store_true", help="Single attempt")
    parser.add_argument("--dry-run", action="store_true", help="Show without executing")
    args = parser.parse_args()

    if args.post:
        post_text = args.post
    elif args.post_file:
        post_text = Path(args.post_file).read_text(encoding="utf-8")
    else:
        print("Usage: --post 'text' or --post-file path")
        print("\nMethods disponibles:")
        print("  clipboard  : Copie dans presse-papier + ouvre LinkedIn")
        print("  cdp        : Chrome DevTools Protocol (browser_pilot)")
        print("  playwright : Automatisation Playwright (persistent session)")
        print("  telegram   : Envoie brouillon sur Telegram")
        print("  file       : Exporte en fichier .txt sur le Bureau")
        print("  all        : Essaye toutes les methodes")
        sys.exit(1)

    run_all_methods(post_text, args.method, args.dry_run)


if __name__ == "__main__":
    main()
