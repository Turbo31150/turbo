"""
AUDIT COGNITIF V3 - Crash Test du Systeme Vocal
Teste 20 commandes sur M2 GPT-OSS + verifie le fallback local
"""
import sys
import os
import time
import json
import requests

sys.path.insert(0, os.path.dirname(__file__))

# Import du commander pour tester le fallback local
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'voice_system'))

M2_URL = "http://192.168.1.26:1234/v1/chat/completions"
M2_MODEL = "openai/gpt-oss-20b"
M2_TIMEOUT = 10

# System prompt identique au commander_v2.py
SYSTEM_PROMPT = """Tu es l'interface neurale Windows. Convertis l'ordre en JSON strict.
Reponds UNIQUEMENT: {"action": "NOM", "params": "valeur"}

TRADING:
- RUN_SCAN: scan marche | RUN_PIPELINE: pipeline 10 cycles | RUN_TRIDENT: trident
- RUN_SNIPER: sniper | MONITOR_RIVER: monitor river | STATUS_REPORT: positions/status
- CHECK_SYSTEM: etat systeme cpu/ram | STOP_ALL: arret urgence | LIST_APPS: liste apps

APPLICATIONS:
- OPEN_APP: params=nom (ex: "chrome","notepad") | OPEN_URL: params=url
- OPEN_FOLDER: params=chemin (ex: "F:/BUREAU") | CLOSE_WINDOW: fermer | KILL_PROCESS: params=nom.exe

FENETRES:
- SNAP_LEFT/SNAP_RIGHT | MAXIMIZE/MINIMIZE/MINIMIZE_ALL | SWITCH_WINDOW | DESKTOP | TASK_MANAGER

NAVIGATEUR:
- NEW_TAB/CLOSE_TAB/NEXT_TAB/PREV_TAB | REFRESH | BACK/FORWARD
- GO_TO_URL: params=url (ouvre dans barre adresse) | ADDRESS_BAR

SAISIE:
- TYPE_TEXT: params=texte | PRESS_KEY: params=touche (enter/esc/tab/backspace/space/delete)
- SCROLL_UP/SCROLL_DOWN | PRESS_ENTER/PRESS_ESC/PRESS_TAB

SOURIS:
- CLICK/DOUBLE_CLICK/RIGHT_CLICK | CLICK_AT: params="x y" | MOVE_MOUSE: params="x y"

CLAVIER:
- COPY/PASTE/CUT/UNDO/REDO/SAVE/SELECT_ALL/FIND/NEW_WINDOW
- HOTKEY: params="ctrl+shift+n" | READ_CLIPBOARD

SYSTEME:
- VOLUME_UP/VOLUME_DOWN/VOLUME_MUTE | SCREENSHOT | LOCK_PC | RUN_CMD: params=commande

Exemples:
"Ouvre chrome" -> {"action":"OPEN_APP","params":"chrome"}
"Va sur tradingview.com" -> {"action":"GO_TO_URL","params":"https://tradingview.com"}
"Ouvre le dossier bureau" -> {"action":"OPEN_FOLDER","params":"F:/BUREAU"}
"Nouvel onglet" -> {"action":"NEW_TAB","params":""}
"Ecris bonjour" -> {"action":"TYPE_TEXT","params":"bonjour"}
"Tue chrome" -> {"action":"KILL_PROCESS","params":"chrome.exe"}"""

# 20 commandes de test couvrant toutes les categories
TEST_CASES = [
    # BASIQUE (doit marcher 100%)
    ("Ouvre le bloc-notes", "OPEN_APP", "notepad"),
    ("Ferme la fenetre", "CLOSE_WINDOW", ""),
    ("Monte le son", "VOLUME_UP", ""),
    ("Coupe le son", "VOLUME_MUTE", ""),
    # NAVIGATION WEB
    ("Va sur youtube.com", "GO_TO_URL", "youtube.com"),
    ("Ouvre google maps", "OPEN_URL", "google maps"),
    ("Nouvel onglet", "NEW_TAB", ""),
    ("Rafraichis la page", "REFRESH", ""),
    ("Retour en arriere", "BACK", ""),
    # FICHIERS & DOSSIERS
    ("Ouvre le disque F", "OPEN_FOLDER", "F:/"),
    ("Ouvre le dossier bureau", "OPEN_FOLDER", "F:/BUREAU"),
    ("Montre les telechargements", "OPEN_FOLDER", ""),
    # SOURIS & CLAVIER
    ("Clic droit", "RIGHT_CLICK", ""),
    ("Copie tout le texte", "SELECT_ALL+COPY", ""),
    ("Sauvegarde le fichier", "SAVE", ""),
    ("Ecris bonjour le monde", "TYPE_TEXT", "bonjour le monde"),
    # SYSTEME
    ("Etat du systeme", "CHECK_SYSTEM", ""),
    ("Fais un screenshot", "SCREENSHOT", ""),
    ("Lance un scan du marche", "RUN_SCAN", ""),
    ("Verrouille le PC", "LOCK_PC", ""),
]


def test_m2_intent(text):
    """Envoie la commande a M2 et recupere l'intent"""
    try:
        t0 = time.time()
        payload = {
            "model": M2_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ],
            "temperature": 0.1,
            "max_tokens": 80
        }
        r = requests.post(M2_URL, json=payload, timeout=M2_TIMEOUT)
        latency = round(time.time() - t0, 2)

        if r.status_code != 200:
            return {"action": "HTTP_ERROR", "params": str(r.status_code)}, latency

        msg = r.json()['choices'][0]['message']
        content = msg.get('content', '') or ''
        if not content.strip():
            content = msg.get('reasoning_content', '') or msg.get('reasoning', '') or ''

        if "{" in content and "}" in content:
            json_str = content[content.find("{"):content.rfind("}") + 1]
            return json.loads(json_str), latency

        return {"action": "PARSE_FAIL", "params": content[:80]}, latency

    except requests.exceptions.Timeout:
        return {"action": "TIMEOUT", "params": ""}, M2_TIMEOUT
    except Exception as e:
        return {"action": "ERROR", "params": str(e)[:60]}, 0


def test_local_fallback(text):
    """Teste le fallback local (sans IA)"""
    # Reproduire la logique du commander
    LOCAL_KEYWORDS = {
        "pipeline": "RUN_PIPELINE", "trident": "RUN_TRIDENT", "sniper": "RUN_SNIPER",
        "river": "MONITOR_RIVER", "scan": "RUN_SCAN", "position": "STATUS_REPORT",
        "status": "STATUS_REPORT", "stop": "STOP_ALL", "urgence": "STOP_ALL",
        "gauche": "SNAP_LEFT", "droite": "SNAP_RIGHT", "maximise": "MAXIMIZE",
        "minimise": "MINIMIZE", "ferme": "CLOSE_WINDOW", "bureau": "DESKTOP",
        "gestionnaire": "TASK_MANAGER",
        "nouvel onglet": "NEW_TAB", "ferme onglet": "CLOSE_TAB",
        "rafraichis": "REFRESH", "actualise": "REFRESH", "retour": "BACK",
        "monte le son": "VOLUME_UP", "baisse le son": "VOLUME_DOWN",
        "mute": "VOLUME_MUTE", "coupe le son": "VOLUME_MUTE",
        "screenshot": "SCREENSHOT", "capture": "SCREENSHOT",
        "clic droit": "RIGHT_CLICK", "double clic": "DOUBLE_CLICK", "clic": "CLICK",
        "copie": "COPY", "colle": "PASTE", "coupe": "CUT",
        "annule": "UNDO", "sauvegarde": "SAVE", "enregistre": "SAVE",
        "selectionne tout": "SELECT_ALL", "recherche": "FIND",
        "valide": "PRESS_ENTER", "echappe": "PRESS_ESC",
        "cpu": "CHECK_SYSTEM", "ram": "CHECK_SYSTEM", "etat systeme": "CHECK_SYSTEM",
        "liste apps": "LIST_APPS", "verrouille": "LOCK_PC",
    }
    PARAM_KEYWORDS = {
        "ouvre ": "OPEN_APP", "lance ": "OPEN_APP",
        "va sur ": "GO_TO_URL", "ecris ": "TYPE_TEXT", "tape ": "TYPE_TEXT",
        "tue ": "KILL_PROCESS", "ouvre dossier ": "OPEN_FOLDER",
    }

    text_lower = text.lower().strip()
    for prefix, action in sorted(PARAM_KEYWORDS.items(), key=lambda x: -len(x[0])):
        if text_lower.startswith(prefix):
            return {"action": action, "params": text_lower[len(prefix):].strip()}
    for kw, action in LOCAL_KEYWORDS.items():
        if kw in text_lower:
            return {"action": action, "params": ""}
    return None


print("=" * 80)
print("  AUDIT COGNITIF V3 - CRASH TEST SYSTEME VOCAL")
print("  20 commandes | M2 GPT-OSS + Fallback Local")
print("=" * 80)
print()

results = []
m2_ok = 0
m2_fail = 0
fallback_ok = 0
total_latency = 0

for text, expected_action, expected_params in TEST_CASES:
    # Test M2
    intent, latency = test_m2_intent(text)
    total_latency += latency
    got_action = intent.get("action", "?")
    got_params = intent.get("params", "")

    # Test fallback
    fb = test_local_fallback(text)
    fb_action = fb["action"] if fb else "NONE"

    # Evaluation
    m2_match = expected_action.split("+")[0] in got_action or got_action == expected_action
    fb_match = expected_action.split("+")[0] in fb_action or fb_action == expected_action if fb else False

    if m2_match:
        m2_ok += 1
    else:
        m2_fail += 1
    if fb_match:
        fallback_ok += 1

    status = "OK" if m2_match else ("FB" if fb_match else "FAIL")
    icon = {"OK": "[OK]", "FB": "[FB]", "FAIL": "[XX]"}[status]

    print(f"  {icon} {text:<35} | {latency:>5}s | M2={got_action:<15} | Local={fb_action:<15} | Expected={expected_action}")
    results.append({
        "text": text, "latency": latency, "m2_action": got_action,
        "fb_action": fb_action, "expected": expected_action, "status": status
    })

print()
print("=" * 80)
print(f"  RESULTATS: M2={m2_ok}/{len(TEST_CASES)} ({100*m2_ok//len(TEST_CASES)}%) | "
      f"Fallback={fallback_ok}/{len(TEST_CASES)} ({100*fallback_ok//len(TEST_CASES)}%) | "
      f"Latence moy={total_latency/len(TEST_CASES):.1f}s")
print()

# Identifier les trous
fails = [r for r in results if r["status"] == "FAIL"]
if fails:
    print("  ACTIONS MANQUANTES (ni M2 ni Fallback):")
    for f in fails:
        print(f"    - \"{f['text']}\" -> attendu {f['expected']}, M2={f['m2_action']}, Local={f['fb_action']}")
print("=" * 80)
