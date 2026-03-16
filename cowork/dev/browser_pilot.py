#!/usr/bin/env python3
"""browser_pilot.py — Controle le navigateur Chrome/Edge via DevTools Protocol.

Lance Chrome avec --remote-debugging-port et pilote via CDP HTTP.
Permet: navigation, clic, scroll, capture, extraction texte, onglets.

Usage:
    python dev/browser_pilot.py --start                     # Lancer Chrome avec CDP
    python dev/browser_pilot.py --navigate "https://google.com"  # Naviguer
    python dev/browser_pilot.py --click "selector"           # Cliquer
    python dev/browser_pilot.py --scroll down                # Scroller
    python dev/browser_pilot.py --tabs                       # Lister onglets
    python dev/browser_pilot.py --close-tab                  # Fermer onglet courant
    python dev/browser_pilot.py --new-tab "url"              # Nouvel onglet
    python dev/browser_pilot.py --back                       # Page precedente
    python dev/browser_pilot.py --forward                    # Page suivante
    python dev/browser_pilot.py --text                       # Extraire le texte
    python dev/browser_pilot.py --screenshot out.png         # Capture d'ecran
    python dev/browser_pilot.py --eval "document.title"      # Evaluer JS
    python dev/browser_pilot.py --type "texte a taper"       # Taper du texte
    python dev/browser_pilot.py --press Enter                # Appuyer touche
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
CDP_PORT = 9222
CDP_URL = f"http://127.0.0.1:{CDP_PORT}"
COMET_PATHS = [
    os.path.expandvars(r"%LOCALAPPDATA%\Perplexity\Comet\Application\comet.exe"),
    r"/home/turbo\AppData\Local\Perplexity\Comet\Application\comet.exe",
]
CHROME_PATHS = [
    r"/Program Files\Google\Chrome\Application\chrome.exe",
    r"/Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
]
EDGE_PATHS = [
    r"/Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"/Program Files\Microsoft\Edge\Application\msedge.exe",
]
# Priority: Comet > Chrome > Edge
ALL_BROWSERS = COMET_PATHS + CHROME_PATHS + EDGE_PATHS
USER_DATA = Path(os.path.expanduser("~")) / ".openclaw" / "workspace" / "dev" / "data" / "chrome_profile"

# ---------------------------------------------------------------------------
# CDP Helpers
# ---------------------------------------------------------------------------
def cdp_get(path: str):
    """GET request to CDP endpoint."""
    try:
        req = urllib.request.Request(f"{CDP_URL}{path}")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}

def cdp_post(ws_url: str, method: str, params: dict = None):
    """Send CDP command via HTTP endpoint (simplified, no WebSocket needed)."""
    # Use the /json/protocol endpoint approach via evaluate
    pass

def is_cdp_running():
    """Check if Chrome CDP is accessible."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(("127.0.0.1", CDP_PORT))
        sock.close()
        return result == 0
    except:
        return False

def find_browser(prefer: str = None):
    """Find Comet, Chrome, or Edge executable. Comet has priority."""
    if prefer:
        prefer = prefer.lower()
        search = {"comet": COMET_PATHS, "chrome": CHROME_PATHS, "edge": EDGE_PATHS}.get(prefer, ALL_BROWSERS)
        for path in search:
            if os.path.exists(path):
                return path
    for path in ALL_BROWSERS:
        if os.path.exists(path):
            return path
    return None

def start_browser(url: str = None, prefer: str = None):
    """Lance Comet/Chrome/Edge avec CDP active."""
    if is_cdp_running():
        return {"status": "already_running", "port": CDP_PORT}

    browser = find_browser(prefer)
    if not browser:
        return {"error": "Ni Comet, ni Chrome, ni Edge trouve sur le systeme"}

    USER_DATA.mkdir(parents=True, exist_ok=True)
    cmd = [
        browser,
        f"--remote-debugging-port={CDP_PORT}",
        f"--user-data-dir={USER_DATA}",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    if url:
        cmd.append(url)

    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Wait for CDP to be ready
    for _ in range(30):
        if is_cdp_running():
            time.sleep(0.5)
            return {"status": "started", "browser": os.path.basename(browser), "port": CDP_PORT}
        time.sleep(0.3)

    return {"error": "Chrome n'a pas demarre dans les 10s"}

def get_tabs():
    """Liste les onglets ouverts."""
    result = cdp_get("/json")
    if isinstance(result, list):
        return [{"id": t.get("id"), "title": t.get("title", ""), "url": t.get("url", ""),
                 "type": t.get("type", "")}
                for t in result if t.get("type") == "page"]
    return result

def get_active_tab():
    """Retourne le premier onglet 'page'."""
    tabs = get_tabs()
    if isinstance(tabs, list) and tabs:
        return tabs[0]
    return None

def activate_tab(tab_id: str):
    """Active un onglet."""
    return cdp_get(f"/json/activate/{tab_id}")

def close_tab(tab_id: str = None):
    """Ferme un onglet."""
    if not tab_id:
        tab = get_active_tab()
        if tab:
            tab_id = tab["id"]
    if tab_id:
        return cdp_get(f"/json/close/{tab_id}")
    return {"error": "Pas d'onglet a fermer"}

def new_tab(url: str = "about:blank"):
    """Ouvre un nouvel onglet."""
    encoded = urllib.parse.quote(url, safe='/:?=&')
    return cdp_get(f"/json/new?{encoded}")

def evaluate_js(expression: str, tab_id: str = None):
    """Evalue du JavaScript dans l'onglet via CDP HTTP POST."""
    if not tab_id:
        tab = get_active_tab()
        if not tab:
            return {"error": "Pas d'onglet actif"}
        tab_id = tab["id"]

    # Use the /json/protocol to send commands
    # CDP requires WebSocket for Runtime.evaluate, but we can use a workaround
    # via the Chrome DevTools frontend protocol
    try:
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", CDP_PORT, timeout=10)

        # CDP command via WebSocket is needed for evaluate
        # Fallback: use PowerShell to send WebSocket message
        ws_url = None
        tabs = cdp_get("/json")
        if isinstance(tabs, list):
            for t in tabs:
                if t.get("id") == tab_id:
                    ws_url = t.get("webSocketDebuggerUrl")
                    break

        if not ws_url:
            return {"error": "WebSocket URL non trouvee"}

        # Use Python's built-in websocket-like approach via subprocess
        # Since stdlib doesn't have WebSocket, use PowerShell
        ps_script = f'''
$ws = New-Object System.Net.WebSockets.ClientWebSocket
$uri = [System.Uri]::new("{ws_url}")
$ct = [System.Threading.CancellationToken]::None
$ws.ConnectAsync($uri, $ct).Wait()

$cmd = '{{"id":1,"method":"Runtime.evaluate","params":{{"expression":"{expression.replace(chr(34), chr(92)+chr(34)).replace(chr(10), chr(92)+'n')}","returnByValue":true}}}}'
$bytes = [System.Text.Encoding]::UTF8.GetBytes($cmd)
$seg = New-Object System.ArraySegment[byte] -ArgumentList @(,$bytes)
$ws.SendAsync($seg, [System.Net.WebSockets.WebSocketMessageType]::Text, $true, $ct).Wait()

$buf = New-Object byte[] 65536
$seg = New-Object System.ArraySegment[byte] -ArgumentList @(,$buf)
$result = $ws.ReceiveAsync($seg, $ct).Result
$response = [System.Text.Encoding]::UTF8.GetString($buf, 0, $result.Count)
Write-Output $response

$ws.CloseAsync([System.Net.WebSockets.WebSocketCloseStatus]::NormalClosure, "", $ct).Wait()
'''
        result = subprocess.run(
            ["bash", "-NoProfile", "-Command", ps_script],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0 and result.stdout.strip():
            try:
                data = json.loads(result.stdout.strip())
                if "result" in data and "result" in data["result"]:
                    return data["result"]["result"].get("value", data["result"]["result"])
                return data
            except:
                return {"raw": result.stdout.strip()}
        return {"error": result.stderr.strip() if result.stderr else "Pas de reponse"}
    except Exception as e:
        return {"error": str(e)}

def navigate(url: str):
    """Navigue vers une URL."""
    return evaluate_js(f"window.location.href = '{url}'; 'navigating to {url}'")

def go_back():
    return evaluate_js("history.back(); 'back'")

def go_forward():
    return evaluate_js("history.forward(); 'forward'")

def scroll(direction: str, amount: int = 500):
    directions = {
        "down": f"window.scrollBy(0, {amount})",
        "up": f"window.scrollBy(0, -{amount})",
        "top": "window.scrollTo(0, 0)",
        "bottom": "window.scrollTo(0, document.body.scrollHeight)",
    }
    js = directions.get(direction, directions["down"])
    return evaluate_js(f"{js}; 'scrolled {direction}'")

def click_element(selector: str):
    """Clique sur un element CSS."""
    js = f"var el = document.querySelector('{selector}'); if(el){{el.click(); 'clicked'}}else{{'not found'}}"
    return evaluate_js(js)

def click_text(text: str):
    """Clique sur un element contenant le texte."""
    js = f"""
    var els = document.querySelectorAll('a, button, input[type=submit], [role=button], [onclick]');
    var found = false;
    els.forEach(function(el) {{
        if (!found && el.textContent.toLowerCase().includes('{text.lower()}')) {{
            el.click();
            found = true;
        }}
    }});
    found ? 'clicked' : 'not found: {text}'
    """
    return evaluate_js(js)

def type_text(text: str):
    """Tape du texte dans l'element actif."""
    # Escape for JS
    escaped = text.replace("/", "//").replace("'", "/'").replace("\n", "/n")
    js = f"""
    var el = document.activeElement;
    if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.contentEditable === 'true')) {{
        el.value = (el.value || '') + '{escaped}';
        el.dispatchEvent(new Event('input', {{bubbles: true}}));
        'typed'
    }} else {{
        'no active input'
    }}
    """
    return evaluate_js(js)

def press_key(key: str):
    """Simule une touche clavier."""
    key_map = {
        "enter": "Enter", "tab": "Tab", "escape": "Escape",
        "backspace": "Backspace", "delete": "Delete",
        "up": "ArrowUp", "down": "ArrowDown", "left": "ArrowLeft", "right": "ArrowRight",
        "space": " ", "f5": "F5",
    }
    mapped = key_map.get(key.lower(), key)
    js = f"""
    var el = document.activeElement || document.body;
    el.dispatchEvent(new KeyboardEvent('keydown', {{key: '{mapped}', bubbles: true}}));
    el.dispatchEvent(new KeyboardEvent('keyup', {{key: '{mapped}', bubbles: true}}));
    'pressed {mapped}'
    """
    return evaluate_js(js)

def get_page_text():
    """Extrait le texte visible de la page."""
    return evaluate_js("document.body.innerText.substring(0, 5000)")

def get_page_title():
    return evaluate_js("document.title")

def get_page_url():
    return evaluate_js("window.location.href")

def screenshot(output_path: str):
    """Capture la page via CDP screenshot."""
    tab = get_active_tab()
    if not tab:
        return {"error": "Pas d'onglet actif"}
    # Screenshot via CDP requires WebSocket
    result = evaluate_js("""
    (function() {
        var c = document.createElement('canvas');
        c.width = window.innerWidth;
        c.height = window.innerHeight;
        return 'screenshot requires CDP WebSocket - use --eval for page info instead';
    })()
    """)
    return {"note": "Screenshot via CDP necesssite WebSocket avance. Utilisez screenshot_tool.py pour captures.", "page_title": get_page_title()}

import urllib.parse

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="JARVIS Browser Pilot — Controle navigateur via CDP")
    parser.add_argument("--start", nargs="?", const="", help="Lancer le navigateur avec CDP (optionnel: URL)")
    parser.add_argument("--browser", type=str, choices=["comet", "chrome", "edge"], default=None, help="Navigateur prefere")
    parser.add_argument("--comet", action="store_true", help="Raccourci: --start --browser comet")
    parser.add_argument("--navigate", type=str, help="Naviguer vers URL")
    parser.add_argument("--tabs", action="store_true", help="Lister les onglets")
    parser.add_argument("--new-tab", type=str, help="Nouvel onglet (URL)")
    parser.add_argument("--close-tab", action="store_true", help="Fermer l'onglet actif")
    parser.add_argument("--activate", type=str, help="Activer un onglet (ID)")
    parser.add_argument("--back", action="store_true", help="Page precedente")
    parser.add_argument("--forward", action="store_true", help="Page suivante")
    parser.add_argument("--scroll", type=str, help="Scroller: up/down/top/bottom")
    parser.add_argument("--click", type=str, help="Cliquer (selecteur CSS)")
    parser.add_argument("--click-text", type=str, help="Cliquer sur texte visible")
    parser.add_argument("--type", type=str, help="Taper du texte")
    parser.add_argument("--press", type=str, help="Appuyer touche (enter/tab/escape...)")
    parser.add_argument("--text", action="store_true", help="Extraire texte de la page")
    parser.add_argument("--title", action="store_true", help="Titre de la page")
    parser.add_argument("--url", action="store_true", help="URL de la page")
    parser.add_argument("--eval", type=str, help="Evaluer JavaScript")
    parser.add_argument("--screenshot", type=str, help="Capture d'ecran (chemin)")
    parser.add_argument("--status", action="store_true", help="Statut CDP")
    args = parser.parse_args()

    # Status
    if args.status:
        running = is_cdp_running()
        tabs = get_tabs() if running else []
        print(json.dumps({
            "cdp_running": running, "port": CDP_PORT,
            "tabs": len(tabs) if isinstance(tabs, list) else 0,
        }, indent=2))
        return

    # Comet shortcut
    if args.comet:
        args.start = args.start if (args.start is not None and args.start) else ""
        args.browser = "comet"

    # Start
    if args.start is not None:
        url = args.start if args.start else None
        result = start_browser(url, prefer=args.browser)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    # Check CDP
    if not is_cdp_running():
        print(json.dumps({"error": "Chrome CDP non actif. Lancez: --start"}, ensure_ascii=False))
        sys.exit(1)

    # Tab operations
    if args.tabs:
        print(json.dumps(get_tabs(), indent=2, ensure_ascii=False))
    elif args.new_tab:
        result = new_tab(args.new_tab)
        print(json.dumps({"action": "new_tab", "url": args.new_tab, "result": str(result)[:200]}, indent=2, ensure_ascii=False))
    elif args.close_tab:
        result = close_tab()
        print(json.dumps({"action": "close_tab", "result": str(result)}, indent=2, ensure_ascii=False))
    elif args.activate:
        result = activate_tab(args.activate)
        print(json.dumps({"action": "activate", "result": str(result)}, indent=2, ensure_ascii=False))
    # Navigation
    elif args.navigate:
        result = navigate(args.navigate)
        print(json.dumps({"action": "navigate", "url": args.navigate, "result": result}, indent=2, ensure_ascii=False))
    elif args.back:
        result = go_back()
        print(json.dumps({"action": "back", "result": result}, indent=2, ensure_ascii=False))
    elif args.forward:
        result = go_forward()
        print(json.dumps({"action": "forward", "result": result}, indent=2, ensure_ascii=False))
    # Interaction
    elif args.scroll:
        result = scroll(args.scroll)
        print(json.dumps({"action": "scroll", "direction": args.scroll, "result": result}, indent=2, ensure_ascii=False))
    elif args.click:
        result = click_element(args.click)
        print(json.dumps({"action": "click", "selector": args.click, "result": result}, indent=2, ensure_ascii=False))
    elif args.click_text:
        result = click_text(args.click_text)
        print(json.dumps({"action": "click_text", "text": args.click_text, "result": result}, indent=2, ensure_ascii=False))
    elif args.type:
        result = type_text(args.type)
        print(json.dumps({"action": "type", "result": result}, indent=2, ensure_ascii=False))
    elif args.press:
        result = press_key(args.press)
        print(json.dumps({"action": "press", "key": args.press, "result": result}, indent=2, ensure_ascii=False))
    # Info
    elif args.text:
        result = get_page_text()
        print(json.dumps({"text": result[:3000] if isinstance(result, str) else result}, indent=2, ensure_ascii=False))
    elif args.title:
        result = get_page_title()
        print(json.dumps({"title": result}, indent=2, ensure_ascii=False))
    elif args.url:
        result = get_page_url()
        print(json.dumps({"url": result}, indent=2, ensure_ascii=False))
    elif args.eval:
        result = evaluate_js(args.eval)
        print(json.dumps({"eval": args.eval, "result": result}, indent=2, ensure_ascii=False))
    elif args.screenshot:
        result = screenshot(args.screenshot)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
