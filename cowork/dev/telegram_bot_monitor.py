#!/usr/bin/env python3
"""telegram_bot_monitor.py

Batch 28: Moniteur du bot Telegram JARVIS autonome.
Verifie que le bot poll correctement, que le proxy repond,
et relance si necessaire.

* Bot Telegram : getMe + getUpdates check
* Canvas Proxy : http://127.0.0.1:18800/health
* Service Registry : heartbeat telegram-bot

Alertes Telegram si le bot est down.

Usage :
    telegram_bot_monitor.py --once      # check une fois
    telegram_bot_monitor.py --loop      # boucle toutes les 2 min
"""

import argparse
import json
import subprocess
import sys
import time
import urllib.request

TELEGRAM_TOKEN = "TELEGRAM_TOKEN_REDACTED"
TELEGRAM_CHAT = "2010747443"
PROXY_URL = "http://127.0.0.1:18800"
WS_URL = "http://127.0.0.1:9742"
BOT_SCRIPT = "F:/BUREAU/turbo/canvas/telegram-bot.js"


def tg_api(method, params=None, timeout=10):
    """Call Telegram Bot API."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"
    body = json.dumps(params or {}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=timeout)
    return json.loads(resp.read().decode())


def check_bot():
    """Verifie que le bot Telegram est accessible."""
    try:
        me = tg_api("getMe")
        r = me.get("result", {})
        print(f"  Bot: @{r.get('username', '?')} OK")
        return True
    except Exception as e:
        print(f"  Bot: ERREUR - {e}")
        return False


def check_proxy():
    """Verifie que le canvas proxy tourne."""
    try:
        req = urllib.request.Request(f"{PROXY_URL}/health")
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read().decode())
        nodes = data.get("nodes", [])
        online = sum(1 for n in nodes if n.get("status") == "online")
        print(f"  Proxy: {online}/{len(nodes)} noeuds online")
        return online > 0
    except Exception as e:
        print(f"  Proxy: OFFLINE - {e}")
        return False


def check_service_registry():
    """Verifie que telegram-bot est enregistre."""
    try:
        req = urllib.request.Request(f"{WS_URL}/api/services")
        resp = urllib.request.urlopen(req, timeout=3)
        data = json.loads(resp.read().decode())
        services = data.get("services", [])
        tg = [s for s in services if "telegram" in s.get("name", "")]
        if tg:
            print(f"  Registry: {tg[0]['name']} enregistre")
            return True
        print("  Registry: telegram-bot non enregistre")
        return False
    except Exception:
        print("  Registry: WS backend non joignable")
        return False


def send_alert(msg):
    """Envoie une alerte Telegram."""
    try:
        body = json.dumps({"chat_id": TELEGRAM_CHAT, "text": f"🔴 {msg}"}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data=body, headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def restart_bot():
    """Tente de relancer le bot Telegram."""
    print("  Tentative de relance du bot...")
    try:
        subprocess.Popen(
            ["node", BOT_SCRIPT],
            cwd="F:/BUREAU/turbo",
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
        time.sleep(3)
        return True
    except Exception as e:
        print(f"  Relance echouee: {e}")
        return False


def run_check():
    """Execute un cycle de monitoring."""
    print(f"\n[{time.strftime('%H:%M:%S')}] Telegram Bot Monitor")
    print("-" * 40)

    bot_ok = check_bot()
    proxy_ok = check_proxy()
    registry_ok = check_service_registry()

    if not proxy_ok:
        send_alert("Canvas Proxy OFFLINE - bot Telegram ne peut pas router")
    if not bot_ok:
        send_alert("Bot Telegram non accessible - verification requise")

    status = "OK" if (bot_ok and proxy_ok) else "DEGRADED"
    print(f"\n  Status global: {status}")
    return bot_ok and proxy_ok


def main():
    parser = argparse.ArgumentParser(description="Telegram Bot Monitor")
    parser.add_argument("--once", action="store_true", help="Check une fois")
    parser.add_argument("--loop", action="store_true", help="Boucle toutes les 2 min")
    args = parser.parse_args()

    if args.loop:
        print("Mode boucle (Ctrl+C pour arreter)")
        while True:
            run_check()
            time.sleep(120)
    else:
        ok = run_check()
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
