"""
J.A.R.V.I.S. COMMANDER v3.6 "LINGUISTE" - Full Auto-Learning Engine
Architecture: STT -> CORRECT(M2) -> NORMALIZE -> Intent (Learned/Fallback/M2) -> Action -> LOG -> LEARN
M2 = http://192.168.1.26:1234 (openai/gpt-oss-20b, ~8s)
60+ actions OS + 8 trading + Genesis auto-coding + full instrumentation
v3.5: learning_engine module, command_history tracking, stats report, auto-expansion
v3.6: speech_corrector (correction phonetique IA avant pipeline)
v3.6.1: TTSPipeline hybride (Chatterbox cloud + pyttsx3 local fallback)
"""
import sys
import os
import time
import json
import subprocess
import importlib.util
import re
import requests

# CONFIGURATION
ROOT = r"/home/turbo\TRADING_V2_PRODUCTION"
SCRIPTS = os.path.join(ROOT, "scripts")
PILOT_PATH = os.path.join(SCRIPTS, "os_pilot.py")
GENESIS_PATH = os.path.join(SCRIPTS, "self_coder.py")
DB_PATH = os.path.join(ROOT, "database", "trading.db")

# Python absolu (evite alias Windows Store)
PYTHON_EXE = sys.executable

# LM Studio M2 (Fast)
M2_URL = "http://192.168.1.26:1234/v1/chat/completions"
M2_MODEL = "openai/gpt-oss-20b"
M2_TIMEOUT = 15

# IMPORT DYNAMIQUE DES MODULES
spec = importlib.util.spec_from_file_location("os_pilot", PILOT_PATH)
os_pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(os_pilot)

try:
    spec_gen = importlib.util.spec_from_file_location("self_coder", GENESIS_PATH)
    self_coder = importlib.util.module_from_spec(spec_gen)
    spec_gen.loader.exec_module(self_coder)
    GENESIS_OK = True
except Exception as e:
    print(f"  Genesis module not loaded: {e}")
    GENESIS_OK = False

# WORKFLOW ENGINE
WORKFLOW_PATH = os.path.join(SCRIPTS, "workflow_engine.py")
try:
    spec_wf = importlib.util.spec_from_file_location("workflow_engine", WORKFLOW_PATH)
    workflow_engine = importlib.util.module_from_spec(spec_wf)
    spec_wf.loader.exec_module(workflow_engine)
    WORKFLOW_OK = True
except Exception as e:
    print(f"  Workflow engine not loaded: {e}")
    WORKFLOW_OK = False

# SPEECH CORRECTOR v1.0 (V3.6 LINGUISTE)
CORRECTOR_PATH = os.path.join(SCRIPTS, "speech_corrector.py")
try:
    spec_corr = importlib.util.spec_from_file_location("speech_corrector", CORRECTOR_PATH)
    speech_corrector = importlib.util.module_from_spec(spec_corr)
    spec_corr.loader.exec_module(speech_corrector)
    CORRECTOR_OK = True
    print(f"  Speech corrector loaded (glossary: {len(speech_corrector._glossary)} terms)")
except Exception as e:
    print(f"  Speech corrector not loaded: {e}")
    CORRECTOR_OK = False

# ================================================================
# LEARNING ENGINE v2.0 - Full instrumentation + auto-improvement
# ================================================================
import sqlite3

LEARNING_DB = DB_PATH

# Import learning_engine module
try:
    sys.path.insert(0, SCRIPTS)
    from learning_engine import (
        init_db as _le_init_db, log_command as _le_log_command,
        get_stats, report as learning_report,
        auto_expand_fallback, suggest_genesis_tools,
        get_learned_patterns as _le_get_learned_patterns,
        increment_pattern_use, add_learned_pattern,
    )
    _le_init_db()
    LEARNING_ENGINE_OK = True
    print("  LEARNING ENGINE v2.0: OK")
except Exception as e:
    print(f"  Learning Engine import error: {e}")
    LEARNING_ENGINE_OK = False

# Legacy inline DB functions (kept for backward compat with "apprends" / "oublie" commands)
def _init_learning_db():
    """Cree les tables legacy si absentes"""
    try:
        conn = sqlite3.connect(LEARNING_DB)
        cur = conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS learning_failures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT DEFAULT (datetime('now','localtime')),
            raw_text TEXT,
            normalized TEXT,
            count INTEGER DEFAULT 1
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS learning_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT DEFAULT (datetime('now','localtime')),
            trigger_phrase TEXT UNIQUE,
            action TEXT,
            params TEXT DEFAULT '',
            source TEXT DEFAULT 'auto',
            uses INTEGER DEFAULT 0
        )""")
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"  LEARNING DB init error: {e}")
        return False

def _load_learned_patterns():
    """Charge les patterns appris depuis la DB (legacy + learned_patterns)"""
    patterns = {}
    try:
        conn = sqlite3.connect(LEARNING_DB)
        cur = conn.cursor()
        # Load from legacy table
        cur.execute("SELECT trigger_phrase, action, params FROM learning_patterns ORDER BY uses DESC")
        for row in cur.fetchall():
            patterns[row[0]] = {"action": row[1], "params": row[2] or ""}
        # Load from new learned_patterns table (learning_engine)
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='learned_patterns'")
        if cur.fetchone():
            cur.execute("SELECT pattern_text, action, params FROM learned_patterns ORDER BY usage_count DESC")
            for row in cur.fetchall():
                if row[0] not in patterns:
                    patterns[row[0]] = {"action": row[1], "params": row[2] or ""}
        conn.close()
    except:
        pass
    return patterns

def _log_failure(raw_text, normalized):
    """Logge une commande non comprise pour analyse future"""
    try:
        conn = sqlite3.connect(LEARNING_DB)
        cur = conn.cursor()
        cur.execute("SELECT id, count FROM learning_failures WHERE normalized = ?", (normalized,))
        row = cur.fetchone()
        if row:
            cur.execute("UPDATE learning_failures SET count = count + 1, timestamp = datetime('now','localtime') WHERE id = ?", (row[0],))
        else:
            cur.execute("INSERT INTO learning_failures (raw_text, normalized) VALUES (?, ?)", (raw_text, normalized))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"  LOG FAILURE error: {e}")

def _learn_pattern(trigger, action, params="", source="auto"):
    """Ajoute un pattern appris dans la DB (legacy + learning_engine)"""
    try:
        conn = sqlite3.connect(LEARNING_DB)
        cur = conn.cursor()
        cur.execute("""INSERT OR REPLACE INTO learning_patterns
                       (trigger_phrase, action, params, source, timestamp)
                       VALUES (?, ?, ?, ?, datetime('now','localtime'))""",
                    (trigger.lower().strip(), action, params, source))
        conn.commit()
        conn.close()
        # Also add to learning_engine
        if LEARNING_ENGINE_OK:
            add_learned_pattern(trigger, action, params, source)
        return True
    except Exception as e:
        print(f"  LEARN error: {e}")
        return False

def _increment_learned_use(trigger):
    """Incremente le compteur d'utilisation d'un pattern appris"""
    try:
        conn = sqlite3.connect(LEARNING_DB)
        cur = conn.cursor()
        cur.execute("UPDATE learning_patterns SET uses = uses + 1 WHERE trigger_phrase = ?", (trigger,))
        conn.commit()
        conn.close()
        if LEARNING_ENGINE_OK:
            increment_pattern_use(trigger)
    except:
        pass

def _get_top_failures(limit=5):
    """Retourne les echecs les plus frequents"""
    try:
        conn = sqlite3.connect(LEARNING_DB)
        cur = conn.cursor()
        cur.execute("SELECT normalized, count FROM learning_failures ORDER BY count DESC LIMIT ?", (limit,))
        rows = cur.fetchall()
        conn.close()
        return rows
    except:
        return []

# Init DB + charger patterns au boot
LEARNING_OK = _init_learning_db()
LEARNED_PATTERNS = _load_learned_patterns() if LEARNING_OK else {}
if LEARNED_PATTERNS:
    print(f"  LEARNING: {len(LEARNED_PATTERNS)} patterns appris charges")


# INIT TTS - TTSPipeline hybride (Chatterbox cloud + pyttsx3 local)
try:
    sys.path.insert(0, os.path.dirname(__file__))
    from tts_pipeline import TTSPipeline
    _tts_pipeline = TTSPipeline()
    TTS_OK = True
    print("  TTS Pipeline v1.0: OK (Cloud+Local)")
except Exception as e:
    print(f"  TTSPipeline import failed, fallback pyttsx3 direct: {e}")
    _tts_pipeline = None
    try:
        import pyttsx3
        _tts_engine = pyttsx3.init()
        _tts_engine.setProperty('rate', 190)
        _tts_engine.setProperty('volume', 1.0)
        voices = _tts_engine.getProperty('voices')
        for v in voices:
            if 'french' in v.name.lower() or 'fr' in v.id.lower():
                _tts_engine.setProperty('voice', v.id)
                break
        TTS_OK = True
    except Exception as e2:
        print(f"  TTS init failed: {e2} - mode silencieux")
        TTS_OK = False

def speak(text):
    """Feedback vocal - TTSPipeline (cloud+local) ou pyttsx3 direct"""
    print(f"  JARVIS: {text}")
    if not TTS_OK:
        return
    try:
        if _tts_pipeline:
            _tts_pipeline.say(text, use_cloning=True)
        elif _tts_engine:
            _tts_engine.say(text)
            _tts_engine.runAndWait()
    except Exception:
        pass


def _looks_garbled(text):
    """Detecte si le texte semble mal transcrit par Whisper (heuristique rapide).
    Retourne True si le texte est suspect -> on active M2 pour corriger."""
    words = text.lower().split()
    if len(words) < 2:
        return False
    # Mots connus (commandes JARVIS, articles, verbes courants)
    known = {
        "ouvre", "ferme", "lance", "arrete", "stop", "scan", "analyse", "verifie",
        "recherche", "copie", "colle", "tape", "ecris", "montre", "affiche",
        "le", "la", "les", "un", "une", "du", "de", "des", "ce", "cette",
        "sur", "dans", "avec", "pour", "et", "ou", "au", "aux", "mon", "ma",
        "bitcoin", "ethereum", "solana", "mexc", "chrome", "firefox",
        "sniper", "trident", "pipeline", "dashboard", "cluster", "jarvis",
        "rapport", "positions", "marge", "consensus", "volume", "bureau",
    }
    unknown = sum(1 for w in words if w not in known and len(w) > 2)
    # Si plus de la moitie des mots sont inconnus -> suspect
    return unknown > len(words) * 0.5


def _strip_articles(text):
    """Retire les articles francais du debut du texte"""
    for art in ["le ", "la ", "l'", "les ", "un ", "une ", "du ", "de la ", "de l'", "de ", "des ", "ce ", "cette ", "mon ", "ma ", "mes "]:
        if text.startswith(art):
            return text[len(art):]
    return text


# ================================================================
# NORMALISATION CONVERSATIONNELLE - STT -> commande propre
# Pipeline: corrections STT → fillers → politesse → patterns → clean
# ================================================================

# Corrections Whisper FR (erreurs courantes de transcription)
STT_CORRECTIONS = {
    "bit coin": "bitcoin",
    "bit coins": "bitcoin",
    "crome": "chrome",
    "cromme": "chrome",
    "google crome": "google chrome",
    "trading vue": "tradingview",
    "trading view": "tradingview",
    "power shell": "powershell",
    "power ciel": "powershell",
    "note pad": "notepad",
    "dis cord": "discord",
    "you tube": "youtube",
    "note pad plus plus": "notepad++",
    "vis code": "vscode",
    "v s code": "vscode",
    "fichier explorateur": "explorateur de fichiers",
    "explorateur fichier": "explorateur de fichiers",
    "controle c": "ctrl c",
    "controle v": "ctrl v",
    "controle z": "ctrl z",
    "controle s": "ctrl s",
    "controle f": "ctrl f",
    "alt f4": "alt f4",
    "f cinq": "f5",
    "f douze": "f12",
    "mexique": "mexc",
    "mex c": "mexc",
    "usdt": "usdt",
    "eu sd t": "usdt",
    "river usdt": "river usdt",
}

# Mots de remplissage a supprimer (Whisper capte souvent ces fillers)
FILLER_WORDS = [
    "euh", "euuh", "euhh", "hmm", "hm", "hein",
    "bon", "bah", "ben", "beh",
    "alors", "du coup", "en fait", "en gros", "genre",
    "voila", "quoi", "tu vois", "ok", "okay",
    "allez", "hop", "tiens", "donc",
]

# Patterns conversationnels -> forme imperative directe
# (regex_pattern, remplacement)
CONVERSATIONAL_PATTERNS = [
    # Questions polies -> imperatif
    (r"est[- ]ce que tu (?:peux|pourrais|veux bien) (.+)", r"\1"),
    (r"tu (?:peux|pourrais|veux bien) (.+?)(?:\s*\?)?$", r"\1"),
    (r"(?:je (?:veux|voudrais|souhaite|aimerais)) (.+)", r"\1"),
    (r"(?:j'(?:aimerais|aimerai)) (.+)", r"\1"),
    (r"(?:il (?:faut|faudrait)) (.+)", r"\1"),
    # Reformulations courantes
    (r"montre[- ]moi (.+)", r"ouvre \1"),
    (r"affiche[- ]moi (.+)", r"ouvre \1"),
    (r"emmene[- ]moi (?:sur|vers|a) (.+)", r"va sur \1"),
    (r"mets[- ]moi sur (.+)", r"va sur \1"),
    (r"fais[- ]moi voir (.+)", r"ouvre \1"),
    (r"dis[- ]moi l'heure", "quelle heure"),
    # Volume naturel
    (r"(?:mets|met) (?:le son |le volume )?plus fort", "monte le son"),
    (r"(?:mets|met) (?:le son |le volume )?moins fort", "baisse le son"),
    (r"(?:mets|met) (?:le son |le volume )?a fond", "monte le son"),
    (r"c'est trop fort", "baisse le son"),
    (r"c'est trop bas", "monte le son"),
    (r"on entend rien", "monte le son"),
    # Navigation naturelle
    (r"(?:remonte|reviens) en haut", "monte la page"),
    (r"(?:va|descends) en bas", "descends la page"),
    (r"plus bas", "descends la page"),
    (r"plus haut", "monte la page"),
    # Actions rapides conversationnelles
    (r"vas[- ]y", "valide"),
    (r"go$", "valide"),
    (r"confirme", "valide"),
    (r"c'est bon", "valide"),
    (r"annule ca", "annule"),
    (r"(?:defais|defait) ca", "annule"),
    (r"laisse tomber", "echap"),
    (r"(?:ferme|quitte) (?:ca|tout ca)", "ferme"),
]

# Suffixes de politesse a retirer en fin de phrase
POLITENESS_SUFFIXES = [
    " s'il te plait", " s'il te plaît", " stp",
    " s'il vous plait", " s'il vous plaît", " svp",
    " merci", " merci beaucoup",
    " jarvis", " hey jarvis", " dis jarvis",
    " steuplait", " please",
]


def normalize_speech(text):
    """Normalise le texte STT brut en commande propre.
    Pipeline: corrections STT -> fillers -> politesse -> patterns -> nettoyage"""
    if not text or not text.strip():
        return text

    result = text.lower().strip()

    # 1. Corrections STT (mots mal transcrits par Whisper)
    for wrong, right in STT_CORRECTIONS.items():
        result = result.replace(wrong, right)

    # 2. Retrait fillers (tries par longueur decroissante pour eviter partiel)
    for filler in sorted(FILLER_WORDS, key=len, reverse=True):
        # Retire au debut, a la fin, ou isole (entoure d'espaces/ponctuation)
        result = re.sub(r'(?:^|\s)' + re.escape(filler) + r'(?:\s|$|,)', ' ', result)

    # 3. Retrait suffixes de politesse
    for suffix in sorted(POLITENESS_SUFFIXES, key=len, reverse=True):
        if result.endswith(suffix):
            result = result[:-len(suffix)]

    # 4. Patterns conversationnels -> forme imperative
    for pattern, replacement in CONVERSATIONAL_PATTERNS:
        new_result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        if new_result != result:
            result = new_result
            break  # Un seul pattern applique (le premier qui matche)

    # 5. Nettoyage final
    result = re.sub(r'\s+', ' ', result).strip()  # espaces multiples
    result = result.strip('.,;:!? ')  # ponctuation residuelle

    if result != text.lower().strip():
        print(f"  NORMALIZE: '{text}' -> '{result}'")

    return result


def analyze_intent_with_m2(text):
    """M2 GPT-OSS analyse la phrase et retourne {action, params}"""
    system_prompt = """Tu es J.A.R.V.I.S., l'intelligence centrale. Convertis l'ordre en JSON strict.
Reponds UNIQUEMENT: {"action": "NOM", "params": "valeur"}

GENESIS (auto-coding):
- CREATE_TOOL: generer un script -> params=description
- RUN_SCRIPT: executer un script genere -> params=nom_fichier.py
- LIST_TOOLS: lister les outils generes

TRADING:
- RUN_SCAN: scan marche | RUN_PIPELINE: pipeline cycles | RUN_TRIDENT: trident
- RUN_SNIPER: sniper | MONITOR_RIVER: monitor river | STATUS_REPORT: positions/status
- CHECK_SYSTEM: etat systeme cpu/ram | STOP_ALL: arret urgence | LIST_APPS: liste apps

APPLICATIONS:
- OPEN_APP: params=nom (chrome, notepad, powershell, discord, explorateur, excel, calculatrice)
- OPEN_URL: params=url | OPEN_FOLDER: params=nom ou chemin (bureau, documents, disque f)
- CLOSE_WINDOW: fermer | KILL_PROCESS: params=nom.exe

FENETRES:
- SNAP_LEFT/SNAP_RIGHT | MAXIMIZE/MINIMIZE/MINIMIZE_ALL | SWITCH_WINDOW | DESKTOP | TASK_MANAGER

NAVIGATEUR:
- NEW_TAB: nouvel onglet | CLOSE_TAB: fermer onglet | NEXT_TAB/PREV_TAB: changer onglet
- REFRESH: actualiser/f5 | BACK: retour | FORWARD: avancer
- GO_TO_URL: params=url (barre adresse) | ADDRESS_BAR

SAISIE:
- TYPE_TEXT: params=texte | PRESS_KEY: params=touche (enter/esc/tab/backspace/space/delete/f1-f12)
- PRESS_ENTER | PRESS_ESC | PRESS_TAB | PRESS_BACKSPACE
- SCROLL_UP/SCROLL_DOWN | SELECT_ALL: tout selectionner

SOURIS:
- CLICK/DOUBLE_CLICK/RIGHT_CLICK | CLICK_AT: params="x y" | MOVE_MOUSE: params="x y"

CLAVIER:
- COPY/PASTE/CUT/UNDO/REDO/SAVE/SELECT_ALL/FIND/NEW_WINDOW
- HOTKEY: params="ctrl+shift+n" | READ_CLIPBOARD

SYSTEME:
- VOLUME_UP/VOLUME_DOWN/VOLUME_MUTE | SCREENSHOT | LOCK_PC
- SETTINGS: parametres Win+I | NOTIFICATIONS: Win+N | SEARCH_WEB: params=query google
- SEARCH_FILES: Win+S | VIRTUAL_DESKTOPS: Win+Tab | NEW_DESKTOP | RUN_CMD: params=commande

FICHIERS:
- NEW_FOLDER: nouveau dossier | RENAME_FILE: F2 | DELETE_FILE | FILE_PROPERTIES: Alt+Enter

Exemples:
"Ouvre chrome" -> {"action":"OPEN_APP","params":"chrome"}
"Va sur tradingview.com" -> {"action":"GO_TO_URL","params":"https://tradingview.com"}
"Ouvre le dossier bureau" -> {"action":"OPEN_FOLDER","params":"bureau"}
"Va dans le disque F" -> {"action":"OPEN_FOLDER","params":"disque f"}
"Nouvel onglet" -> {"action":"NEW_TAB","params":""}
"Actualise la page" -> {"action":"REFRESH","params":""}
"Descends la page" -> {"action":"SCROLL_DOWN","params":""}
"Ecris bonjour" -> {"action":"TYPE_TEXT","params":"bonjour"}
"Appuie sur echap" -> {"action":"PRESS_ESC","params":""}
"Tout selectionner" -> {"action":"SELECT_ALL","params":""}
"Cherche bitcoin sur google" -> {"action":"SEARCH_WEB","params":"bitcoin"}
"Ouvre les parametres" -> {"action":"SETTINGS","params":""}
"Cree un outil pour nettoyer" -> {"action":"CREATE_TOOL","params":"nettoyer le bureau"}
"Lance le dernier script" -> {"action":"RUN_SCRIPT","params":"latest"}"""

    try:
        payload = {
            "model": M2_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            "temperature": 0.1,
            "max_tokens": 80
        }
        t0 = time.time()
        resp = requests.post(M2_URL, json=payload, timeout=M2_TIMEOUT)
        latency = time.time() - t0

        if resp.status_code == 200:
            msg = resp.json()['choices'][0]['message']
            content = msg.get('content', '') or ''
            if not content.strip():
                content = msg.get('reasoning_content', '') or msg.get('reasoning', '') or ''

            print(f"  M2 ({latency:.1f}s): {content[:100]}")

            if "{" in content and "}" in content:
                json_str = content[content.find("{"):content.rfind("}") + 1]
                return json.loads(json_str)
        else:
            print(f"  M2 HTTP {resp.status_code}")

    except requests.exceptions.Timeout:
        print(f"  M2 timeout ({M2_TIMEOUT}s)")
    except json.JSONDecodeError as e:
        print(f"  M2 JSON parse error: {e}")
    except Exception as e:
        print(f"  M2 error: {e}")

    return {"action": "UNKNOWN", "params": ""}


# ================================================================
# PRIORITY PATTERNS - phrases completes (verifees AVANT tout le reste)
# Empeche "ouvre un nouvel onglet" d'etre capte par "ouvre " -> OPEN_APP
# ================================================================
PRIORITY_PATTERNS = [
    # Navigation web
    ("nouvel onglet", {"action": "NEW_TAB", "params": ""}),
    ("nouveau onglet", {"action": "NEW_TAB", "params": ""}),
    ("fermer l'onglet", {"action": "CLOSE_TAB", "params": ""}),
    ("ferme l'onglet", {"action": "CLOSE_TAB", "params": ""}),
    ("ferme onglet", {"action": "CLOSE_TAB", "params": ""}),
    ("onglet suivant", {"action": "NEXT_TAB", "params": ""}),
    ("onglet precedent", {"action": "PREV_TAB", "params": ""}),
    ("actualise la page", {"action": "REFRESH", "params": ""}),
    ("rafraichis la page", {"action": "REFRESH", "params": ""}),
    ("retour en arriere", {"action": "BACK", "params": ""}),
    ("page precedente", {"action": "BACK", "params": ""}),
    ("page suivante", {"action": "FORWARD", "params": ""}),
    # Scroll
    ("descends la page", {"action": "SCROLL_DOWN", "params": ""}),
    ("monte la page", {"action": "SCROLL_UP", "params": ""}),
    ("scroll down", {"action": "SCROLL_DOWN", "params": ""}),
    ("scroll up", {"action": "SCROLL_UP", "params": ""}),
    ("descends", {"action": "SCROLL_DOWN", "params": ""}),
    # Selection / Edition
    ("tout selectionner", {"action": "SELECT_ALL", "params": ""}),
    ("selectionne tout", {"action": "SELECT_ALL", "params": ""}),
    ("efface tout", {"action": "HOTKEY", "params": "ctrl+a"}),
    ("retour arriere", {"action": "PRESS_BACKSPACE", "params": ""}),
    # Touches
    ("appuie sur echap", {"action": "PRESS_ESC", "params": ""}),
    ("appuie sur escape", {"action": "PRESS_ESC", "params": ""}),
    ("appuie sur espace", {"action": "PRESS_KEY", "params": "space"}),
    ("appuie sur entree", {"action": "PRESS_ENTER", "params": ""}),
    ("appuie sur tab", {"action": "PRESS_TAB", "params": ""}),
    ("appuie sur supprimer", {"action": "PRESS_KEY", "params": "delete"}),
    ("touche espace", {"action": "PRESS_KEY", "params": "space"}),
    ("touche echap", {"action": "PRESS_ESC", "params": ""}),
    # Systeme
    ("verrouille l'ecran", {"action": "LOCK_PC", "params": ""}),
    ("verrouille le pc", {"action": "LOCK_PC", "params": ""}),
    ("panneau de notifications", {"action": "NOTIFICATIONS", "params": ""}),
    ("ouvre les notifications", {"action": "NOTIFICATIONS", "params": ""}),
    ("ouvre les parametres", {"action": "SETTINGS", "params": ""}),
    ("parametres windows", {"action": "SETTINGS", "params": ""}),
    ("bureaux virtuels", {"action": "VIRTUAL_DESKTOPS", "params": ""}),
    ("affiche les bureaux", {"action": "VIRTUAL_DESKTOPS", "params": ""}),
    ("nouveau bureau", {"action": "NEW_DESKTOP", "params": ""}),
    # Fichiers
    ("nouveau dossier", {"action": "NEW_FOLDER", "params": ""}),
    ("cree un dossier", {"action": "NEW_FOLDER", "params": ""}),
    ("renomme ce fichier", {"action": "RENAME_FILE", "params": ""}),
    ("renomme le fichier", {"action": "RENAME_FILE", "params": ""}),
    ("supprime ce fichier", {"action": "DELETE_FILE", "params": ""}),
    ("supprime le fichier", {"action": "DELETE_FILE", "params": ""}),
    ("proprietes du fichier", {"action": "FILE_PROPERTIES", "params": ""}),
    # Fenetres
    ("change de fenetre", {"action": "SWITCH_WINDOW", "params": ""}),
    ("fenetre suivante", {"action": "SWITCH_WINDOW", "params": ""}),
    ("gestionnaire de taches", {"action": "TASK_MANAGER", "params": ""}),
    ("gestionnaire des taches", {"action": "TASK_MANAGER", "params": ""}),
    # Heure
    ("quelle heure", {"action": "RUN_CMD", "params": "echo %TIME%"}),
    # Genesis
    ("liste les outils", {"action": "LIST_TOOLS", "params": ""}),
    ("outils generes", {"action": "LIST_TOOLS", "params": ""}),
    # JARVIS Self-Report & Learning
    ("rapport jarvis", {"action": "JARVIS_REPORT", "params": ""}),
    ("statistiques jarvis", {"action": "JARVIS_REPORT", "params": ""}),
    ("statistiques", {"action": "JARVIS_REPORT", "params": ""}),
    ("comment tu vas", {"action": "JARVIS_REPORT", "params": ""}),
    ("ton rapport", {"action": "JARVIS_REPORT", "params": ""}),
    ("auto-amelioration", {"action": "JARVIS_LEARN", "params": ""}),
    ("ameliore-toi", {"action": "JARVIS_LEARN", "params": ""}),
    ("optimise-toi", {"action": "JARVIS_LEARN", "params": ""}),
    # Predictions + Vocabulaire (V3.6)
    ("verifie les predictions", {"action": "RUN_CHECK_PRED", "params": ""}),
    ("check predictions", {"action": "RUN_CHECK_PRED", "params": ""}),
    ("checkpred", {"action": "RUN_CHECK_PRED", "params": ""}),
    ("resultats predictions", {"action": "RUN_CHECK_PRED", "params": ""}),
    ("enrichis le vocabulaire", {"action": "RUN_KNOWLEDGE_HUNTER", "params": ""}),
    ("enrichir vocabulaire", {"action": "RUN_KNOWLEDGE_HUNTER", "params": ""}),
    ("knowledge hunter", {"action": "RUN_KNOWLEDGE_HUNTER", "params": ""}),
    ("mets a jour le glossaire", {"action": "RUN_KNOWLEDGE_HUNTER", "params": ""}),
    # Trading (evite que "lance " prefix capture -> OPEN_APP)
    ("lance un scan", {"action": "RUN_SCAN", "params": ""}),
    ("lance le scan", {"action": "RUN_SCAN", "params": ""}),
    ("lance le pipeline", {"action": "RUN_PIPELINE", "params": ""}),
    ("lance le sniper 10", {"action": "RUN_SNIPER_10", "params": ""}),
    ("lance le sniper", {"action": "RUN_SNIPER", "params": ""}),
    ("lance le trident", {"action": "RUN_TRIDENT", "params": ""}),
    ("lance river", {"action": "MONITOR_RIVER", "params": ""}),
    ("monitor river", {"action": "MONITOR_RIVER", "params": ""}),
    # Dashboard / GUI / Cluster
    ("lance le dashboard", {"action": "RUN_DASHBOARD", "params": ""}),
    ("ouvre le dashboard", {"action": "RUN_DASHBOARD", "params": ""}),
    ("lance le cockpit", {"action": "RUN_GUI", "params": ""}),
    ("ouvre le cockpit", {"action": "RUN_GUI", "params": ""}),
    ("lance le gui", {"action": "RUN_GUI", "params": ""}),
    ("sniper 10 cycles", {"action": "RUN_SNIPER_10", "params": ""}),
    ("test cluster", {"action": "CHECK_CLUSTER", "params": ""}),
    ("health check", {"action": "CHECK_CLUSTER", "params": ""}),
    ("verifie le cluster", {"action": "CHECK_CLUSTER", "params": ""}),
    # Workflows complexes -> COMPLEX_TASK (route vers workflow_engine)
    ("ecris un mail", {"action": "COMPLEX_TASK", "params": "ecris un mail"}),
    ("envoie un mail", {"action": "COMPLEX_TASK", "params": "envoie un mail"}),
    ("mail a", {"action": "COMPLEX_TASK", "params": ""}),
    ("ecris une note", {"action": "COMPLEX_TASK", "params": "ecris une note"}),
    ("prends en note", {"action": "COMPLEX_TASK", "params": "prends en note"}),
    ("note rapide", {"action": "COMPLEX_TASK", "params": "note rapide"}),
    ("envoie un message telegram", {"action": "COMPLEX_TASK", "params": "envoie un message telegram"}),
    ("fais une recherche", {"action": "COMPLEX_TASK", "params": "fais une recherche"}),
    ("liste les workflows", {"action": "LIST_WORKFLOWS", "params": ""}),
    ("workflows memorises", {"action": "LIST_WORKFLOWS", "params": ""}),
]


# ================================================================
# LOCAL_KEYWORDS - mots-cles simples sans params
# ================================================================
LOCAL_KEYWORDS = {
    # Trading
    "pipeline": "RUN_PIPELINE",
    "trident": "RUN_TRIDENT",
    "sniper": "RUN_SNIPER",
    "river": "MONITOR_RIVER",
    "scan": "RUN_SCAN",
    "position": "STATUS_REPORT",
    "status": "STATUS_REPORT",
    "stop": "STOP_ALL",
    "urgence": "STOP_ALL",
    "hyper scan": "RUN_SCAN",
    "scan v2": "RUN_SCAN",
    "dashboard": "RUN_DASHBOARD",
    "cockpit": "RUN_GUI",
    "sniper 10": "RUN_SNIPER_10",
    "health check": "CHECK_CLUSTER",
    # Fenetres
    "gauche": "SNAP_LEFT",
    "droite": "SNAP_RIGHT",
    "maximise": "MAXIMIZE",
    "plein ecran": "MAXIMIZE",
    "minimise": "MINIMIZE",
    "reduit": "MINIMIZE",
    "minimise tout": "MINIMIZE_ALL",
    "ferme": "CLOSE_WINDOW",
    "bureau": "DESKTOP",
    "alt tab": "SWITCH_WINDOW",
    "gestionnaire": "TASK_MANAGER",
    # Navigateur
    "rafraichis": "REFRESH",
    "actualise": "REFRESH",
    "f5": "REFRESH",
    "barre adresse": "ADDRESS_BAR",
    # Volume
    "monte le son": "VOLUME_UP",
    "monte le volume": "VOLUME_UP",
    "baisse le son": "VOLUME_DOWN",
    "baisse le volume": "VOLUME_DOWN",
    "volume plus": "VOLUME_UP",
    "volume moins": "VOLUME_DOWN",
    "mute": "VOLUME_MUTE",
    "coupe le son": "VOLUME_MUTE",
    # Capture
    "screenshot": "SCREENSHOT",
    "capture ecran": "SCREENSHOT",
    "capture": "SCREENSHOT",
    # Souris
    "clic droit": "RIGHT_CLICK",
    "double clic": "DOUBLE_CLICK",
    "double-clique": "DOUBLE_CLICK",
    "clique": "CLICK",
    "clic": "CLICK",
    # Clavier / Clipboard
    "copie": "COPY",
    "colle": "PASTE",
    "coupe": "CUT",
    "couper": "CUT",
    "annule": "UNDO",
    "refaire": "REDO",
    "sauvegarde": "SAVE",
    "enregistre": "SAVE",
    "ctrl s": "SAVE",
    "selectionne tout": "SELECT_ALL",
    "recherche": "FIND",
    "ctrl f": "FIND",
    "valide": "PRESS_ENTER",
    "entree": "PRESS_ENTER",
    "echap": "PRESS_ESC",
    "echappe": "PRESS_ESC",
    "tabulation": "PRESS_TAB",
    "backspace": "PRESS_BACKSPACE",
    # Systeme
    "cpu": "CHECK_SYSTEM",
    "ram": "CHECK_SYSTEM",
    "etat systeme": "CHECK_SYSTEM",
    "etat du systeme": "CHECK_SYSTEM",
    "liste apps": "LIST_APPS",
    "applications": "LIST_APPS",
    "verrouille": "LOCK_PC",
    "mets en veille": "SLEEP_PC",
    "veille": "SLEEP_PC",
    "nouvelle fenetre": "NEW_WINDOW",
    "presse-papier": "READ_CLIPBOARD",
    "notifications": "NOTIFICATIONS",
    "parametres": "SETTINGS",
    "renomme": "RENAME_FILE",
    "proprietes": "FILE_PROPERTIES",
    # Genesis
    "liste outils": "LIST_TOOLS",
    "liste scripts": "LIST_TOOLS",
}


# ================================================================
# PARAM_KEYWORDS - prefixes avec extraction de parametres
# Tries par longueur decroissante (plus long = plus specifique)
# ================================================================
PARAM_KEYWORDS = {
    # Genesis
    "cree un outil ": "CREATE_TOOL",
    "genere un script ": "CREATE_TOOL",
    "code un ": "CREATE_TOOL",
    "lance le script ": "RUN_SCRIPT",
    "execute le script ": "RUN_SCRIPT",
    "execute ": "RUN_SCRIPT",
    # Dossiers (avant "ouvre " pour priorite)
    "ouvre le dossier ": "OPEN_FOLDER",
    "ouvre dossier ": "OPEN_FOLDER",
    "va dans le dossier ": "OPEN_FOLDER",
    "va dans ": "OPEN_FOLDER",
    # Recherche
    "cherche ": "SEARCH_WEB",
    "recherche sur google ": "SEARCH_WEB",
    # Apps / Navigation
    "ouvre ": "OPEN_APP",
    "lance ": "OPEN_APP",
    "demarre ": "OPEN_APP",
    "va sur ": "GO_TO_URL",
    # Saisie
    "ecris ": "TYPE_TEXT",
    "tape ": "TYPE_TEXT",
    # Processus
    "tue ": "KILL_PROCESS",
    "kill ": "KILL_PROCESS",
    # Clavier generique
    "appuie sur ": "PRESS_KEY",
}


# ================================================================
# FOLDER_ALIASES - noms connus vers paths Windows
# ================================================================
FOLDER_ALIASES = {
    "bureau": os.path.join(os.environ.get("USERPROFILE", "/\Users/franc"), "Desktop"),
    "documents": os.path.join(os.environ.get("USERPROFILE", "/\Users/franc"), "Documents"),
    "downloads": os.path.join(os.environ.get("USERPROFILE", "/\Users/franc"), "Downloads"),
    "telechargements": os.path.join(os.environ.get("USERPROFILE", "/\Users/franc"), "Downloads"),
    "images": os.path.join(os.environ.get("USERPROFILE", "/\Users/franc"), "Pictures"),
    "musique": os.path.join(os.environ.get("USERPROFILE", "/\Users/franc"), "Music"),
    "videos": os.path.join(os.environ.get("USERPROFILE", "/\Users/franc"), "Videos"),
    "disque c": "/\",
    "disque d": "D:/",
    "disque f": "F:/",
    "f bureau": r"/home/turbo",
    "production": r"/home/turbo\TRADING_V2_PRODUCTION",
    "trading v2": r"/home/turbo\TRADING_V2_PRODUCTION",
    "scripts": r"/home/turbo\TRADING_V2_PRODUCTION\scripts",
    "logs": r"/home/turbo\TRADING_V2_PRODUCTION\logs",
    "config": r"/home/turbo\TRADING_V2_PRODUCTION\config",
    "database": r"/home/turbo\TRADING_V2_PRODUCTION\database",
    "voice": r"/home/turbo\TRADING_V2_PRODUCTION\voice_system",
}

# APP ALIASES - noms courants vers noms Windows
APP_ALIASES = {
    "chrome": "chrome",
    "bloc-notes": "notepad",
    "bloc notes": "notepad",
    "notepad": "notepad",
    "explorateur": "explorer",
    "explorateur de fichiers": "explorer",
    "terminal": "cmd",
    "invite de commandes": "cmd",
    "powershell": "powershell",
    "discord": "discord",
    "tradingview": "tradingview",
    "firefox": "firefox",
    "edge": "msedge",
    "excel": "excel",
    "word": "word",
    "calculatrice": "calc",
    "paint": "mspaint",
}


# ================================================================
# PILOT_ACTIONS - toutes les actions supportees par os_pilot
# ================================================================
PILOT_ACTIONS = {
    "OPEN_APP", "OPEN_URL", "OPEN_FOLDER", "CLOSE_WINDOW", "KILL_PROCESS",
    "SNAP_LEFT", "SNAP_RIGHT", "MAXIMIZE", "MINIMIZE", "MINIMIZE_ALL",
    "SWITCH_WINDOW", "TASK_MANAGER", "DESKTOP",
    "NEW_TAB", "CLOSE_TAB", "NEXT_TAB", "PREV_TAB",
    "REFRESH", "BACK", "FORWARD", "ADDRESS_BAR", "GO_TO_URL",
    "SCROLL_UP", "SCROLL_DOWN", "TYPE_TEXT",
    "PRESS_KEY", "PRESS_ENTER", "PRESS_ESC", "PRESS_TAB", "PRESS_BACKSPACE",
    "CLICK", "DOUBLE_CLICK", "RIGHT_CLICK", "CLICK_AT", "MOVE_MOUSE",
    "HOTKEY", "COPY", "PASTE", "CUT", "UNDO", "REDO",
    "SAVE", "SELECT_ALL", "FIND", "NEW_WINDOW", "READ_CLIPBOARD",
    "VOLUME_UP", "VOLUME_DOWN", "VOLUME_MUTE",
    "SCREENSHOT", "RUN_CMD", "LOCK_PC", "SLEEP_PC",
    "SETTINGS", "NOTIFICATIONS", "VIRTUAL_DESKTOPS", "NEW_DESKTOP",
    "SEARCH_WEB", "SEARCH_FILES",
    "NEW_FOLDER", "RENAME_FILE", "DELETE_FILE", "FILE_PROPERTIES",
}


def local_fallback(text):
    """Fallback rapide sans IA - 4 niveaux: LEARNED -> PRIORITY -> PARAM -> KEYWORD"""
    text_lower = text.lower().strip()

    # -1. LEARNED PATTERNS (auto-appris, plus haute priorite car confirmes par l'utilisateur)
    if text_lower in LEARNED_PATTERNS:
        _increment_learned_use(text_lower)
        return LEARNED_PATTERNS[text_lower].copy()

    # 0. PRIORITY PATTERNS (phrases completes)
    for pattern, result in PRIORITY_PATTERNS:
        if pattern in text_lower:
            return result.copy()

    # 1. PARAM_KEYWORDS (prefixes avec extraction, tries par longueur)
    for prefix, action in sorted(PARAM_KEYWORDS.items(), key=lambda x: -len(x[0])):
        if text_lower.startswith(prefix):
            params = text_lower[len(prefix):].strip()
            params = _strip_articles(params)

            if action == "GO_TO_URL" and not params.startswith("http"):
                params = "https://" + params
            if action == "OPEN_FOLDER":
                params = FOLDER_ALIASES.get(params, params)
            if action == "KILL_PROCESS" and not params.endswith(".exe"):
                params += ".exe"
            if action == "OPEN_APP":
                params = APP_ALIASES.get(params, params)
            if action == "RUN_SCRIPT" and not params.endswith(".py"):
                params += ".py"
            return {"action": action, "params": params}

    # 2. LOCAL_KEYWORDS (mots-cles simples sans params)
    # Tri par longueur decroissante: "sniper 10" matche avant "sniper"
    for kw, action in sorted(LOCAL_KEYWORDS.items(), key=lambda x: len(x[0]), reverse=True):
        if kw in text_lower:
            return {"action": action, "params": ""}

    return None


def execute_command(intent_data):
    """Execute l'action detectee"""
    action = intent_data.get("action", "UNKNOWN")
    params = intent_data.get("params", "")

    print(f"  EXEC: {action} ({params})")

    # --- COMMANDES TRADING ---
    if action == "RUN_SCAN":
        speak("Lancement du scan hyper-cluster.")
        scan_script = os.path.join(SCRIPTS, "hyper_scan_v2.py")
        if not os.path.exists(scan_script):
            scan_script = os.path.join(SCRIPTS, "auto_cycle_10.py")
        subprocess.Popen(f'start cmd /k "{PYTHON_EXE}" -u "{scan_script}"', shell=True)

    elif action == "RUN_PIPELINE":
        speak("Pipeline 10 cycles en route.")
        subprocess.Popen(f'start cmd /k "{PYTHON_EXE}" -u "{os.path.join(SCRIPTS, "auto_cycle_10.py")}"', shell=True)

    elif action == "RUN_TRIDENT":
        speak("Protocole Trident engage.")
        subprocess.Popen(f'start cmd /k "{PYTHON_EXE}" -u "{os.path.join(SCRIPTS, "execute_trident.py")}" --dry-run', shell=True)

    elif action == "RUN_SNIPER":
        speak("Sniper breakout active.")
        subprocess.Popen(f'start cmd /k "{PYTHON_EXE}" -u "{os.path.join(SCRIPTS, "sniper_breakout.py")}"', shell=True)

    elif action == "MONITOR_RIVER":
        speak("Monitoring RIVER active.")
        subprocess.Popen(f'start cmd /k "{PYTHON_EXE}" -u "{os.path.join(SCRIPTS, "river_scalp_1min.py")}"', shell=True)

    elif action == "STATUS_REPORT":
        speak("Lecture des positions.")
        try:
            import sqlite3
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT symbol, direction, score FROM signals ORDER BY id DESC LIMIT 3")
            rows = cur.fetchall()
            conn.close()
            if rows:
                for r in rows:
                    speak(f"{r[0]}: {r[1]}, score {r[2]}")
            else:
                speak("Aucun signal recent en base.")
        except Exception as e:
            speak(f"Erreur base de donnees: {e}")

    elif action == "STOP_ALL":
        speak("Arret d'urgence de tous les systemes.")
        os.system('taskkill /f /im python.exe /fi "PID ne %d"' % os.getpid())

    elif action == "RUN_DASHBOARD":
        speak("Lancement du dashboard.")
        dash = r"/home/turbo\MCP_MCPLMSTUDIO1\dashboard\app.py"
        if os.path.exists(dash):
            subprocess.Popen(f'start cmd /k "{PYTHON_EXE}" -u "{dash}"', shell=True)
        else:
            speak("Dashboard introuvable.")

    elif action == "RUN_GUI":
        speak("Ouverture du cockpit.")
        gui = os.path.join(SCRIPTS, "jarvis_gui.py")
        subprocess.Popen(f'start cmd /k "{PYTHON_EXE}" -u "{gui}"', shell=True)

    elif action == "RUN_SNIPER_10":
        speak("Sniper 10 cycles active.")
        subprocess.Popen(f'start cmd /k "{PYTHON_EXE}" -u "{os.path.join(SCRIPTS, "sniper_10cycles.py")}"', shell=True)

    elif action == "CHECK_CLUSTER":
        speak("Test du cluster en cours.")
        subprocess.Popen(f'start cmd /k "{PYTHON_EXE}" -u "{os.path.join(SCRIPTS, "test_cluster.py")}"', shell=True)

    elif action == "CHECK_SYSTEM":
        speak("Verification du systeme.")
        info = os_pilot.run_command("CHECK_SYSTEM")
        if info and isinstance(info, dict) and 'error' not in info:
            disks = info.get('disks', {})
            disk_msg = ". ".join(f"Disque {d}: {v['free_gb']} giga libres" for d, v in disks.items())
            speak(f"CPU a {info['cpu_pct']} pourcent. "
                  f"RAM {info['ram_used_gb']} sur {info['ram_total_gb']} giga. "
                  f"{disk_msg}.")
        else:
            speak("psutil non disponible.")

    elif action == "LIST_APPS":
        speak("Liste des applications.")
        apps = os_pilot.run_command("LIST_APPS")
        if apps and isinstance(apps, list):
            for a in apps[:5]:
                speak(f"{a['name']}, {int(a['mem_mb'])} mega.")
        else:
            speak("Impossible de lister les applications.")

    # --- GENESIS (AUTO-CODING) ---
    elif action == "CREATE_TOOL":
        if not GENESIS_OK:
            speak("Module Genesis non disponible.")
        elif not params:
            speak("Decris ce que tu veux creer.")
        else:
            speak("Genesis: creation de l'outil en cours.")
            filepath, err = self_coder.generate_tool(params)
            if filepath:
                speak(f"Outil cree: {os.path.basename(filepath)}")
            else:
                speak(f"Echec Genesis: {err}")

    elif action == "RUN_SCRIPT":
        if not GENESIS_OK:
            speak("Module Genesis non disponible.")
        else:
            generated_dir = os.path.join(SCRIPTS, "generated")
            if params == "latest" or not params:
                files = self_coder.list_generated()
                if files:
                    script = os.path.join(generated_dir, files[0])
                    speak(f"Execution de {files[0]}")
                    subprocess.Popen(f'start cmd /k "{PYTHON_EXE}" -u "{script}"', shell=True)
                else:
                    speak("Aucun script genere disponible.")
            else:
                script = os.path.join(generated_dir, params)
                if not script.endswith('.py'):
                    script += '.py'
                if os.path.exists(script):
                    speak(f"Execution de {params}")
                    subprocess.Popen(f'start cmd /k "{PYTHON_EXE}" -u "{script}"', shell=True)
                else:
                    speak(f"Script {params} introuvable.")

    elif action == "LIST_TOOLS":
        if not GENESIS_OK:
            speak("Module Genesis non disponible.")
        else:
            files = self_coder.list_generated()
            if files:
                speak(f"{len(files)} outils disponibles.")
                for f in files[:5]:
                    speak(f)
            else:
                speak("Aucun outil genere pour le moment.")

    # --- JARVIS SELF-REPORT & LEARNING ---
    elif action == "JARVIS_REPORT":
        if LEARNING_ENGINE_OK:
            speak(learning_report())
        else:
            speak("Module d'apprentissage non disponible.")

    elif action == "JARVIS_LEARN":
        if LEARNING_ENGINE_OK:
            n_expanded = auto_expand_fallback()
            n_genesis = suggest_genesis_tools()
            # Reload patterns in memory
            LEARNED_PATTERNS.update(_load_learned_patterns())
            speak(f"Apprentissage termine. {n_expanded} patterns ajoutes, {n_genesis} outils proposes.")
        else:
            speak("Module d'apprentissage non disponible.")

    # --- CHECK PREDICTIONS (V3.6) ---
    elif action == "RUN_CHECK_PRED":
        speak("Verification des predictions en cours.")
        check_script = os.path.join(SCRIPTS, "check_predictions.py")
        if os.path.exists(check_script):
            subprocess.Popen(f'start cmd /k "{PYTHON_EXE}" -u "{check_script}"', shell=True)
        else:
            speak("Script check predictions introuvable.")

    # --- KNOWLEDGE HUNTER (V3.6) ---
    elif action == "RUN_KNOWLEDGE_HUNTER":
        speak("Enrichissement du vocabulaire en cours.")
        kh_script = os.path.join(SCRIPTS, "knowledge_hunter.py")
        if os.path.exists(kh_script):
            subprocess.Popen(f'start cmd /k "{PYTHON_EXE}" -u "{kh_script}"', shell=True)
            # Recharger le glossaire apres enrichissement
            if CORRECTOR_OK:
                time.sleep(2)
                speech_corrector.load_glossary()
                speak("Glossaire recharge.")
        else:
            speak("Knowledge hunter introuvable.")

    # --- WORKFLOW ENGINE (taches complexes multi-etapes) ---
    elif action == "COMPLEX_TASK":
        if not WORKFLOW_OK:
            speak("Module workflow non disponible.")
        else:
            # Utiliser params si defini, sinon le texte original
            task_text = params if params else "tache complexe"
            workflow_engine.run_complex_task(task_text)

    elif action == "LIST_WORKFLOWS":
        if not WORKFLOW_OK:
            speak("Module workflow non disponible.")
        else:
            wfs = workflow_engine.list_workflows()
            if wfs:
                speak(f"{len(wfs)} workflows memorises.")
                for trigger, count, last in wfs[:5]:
                    speak(f"  '{trigger}' utilise {count} fois")
            else:
                speak("Aucun workflow memorise.")

    # --- TOUTES LES ACTIONS PILOT ---
    elif action in PILOT_ACTIONS:
        feedback = {
            "OPEN_APP": f"Ouverture de {params}",
            "OPEN_FOLDER": f"Dossier {params}",
            "GO_TO_URL": f"Navigation vers {params}",
            "KILL_PROCESS": f"Arret de {params}",
            "SCREENSHOT": "Capture d'ecran",
            "SAVE": "Sauvegarde",
            "COPY": "Copie",
            "PASTE": "Colle",
            "CUT": "Coupe",
            "LOCK_PC": "Verrouillage",
            "NEW_TAB": "Nouvel onglet",
            "CLOSE_TAB": "Fermeture onglet",
            "REFRESH": "Actualisation",
            "BACK": "Retour",
            "SETTINGS": "Parametres",
            "NOTIFICATIONS": "Notifications",
            "SEARCH_WEB": f"Recherche: {params}",
            "SCROLL_DOWN": "Descente",
            "SCROLL_UP": "Montee",
            "SELECT_ALL": "Tout selectionne",
            "NEW_FOLDER": "Nouveau dossier",
            "TYPE_TEXT": f"Saisie: {params[:30]}",
            "VIRTUAL_DESKTOPS": "Bureaux virtuels",
            "NEW_DESKTOP": "Nouveau bureau",
        }
        msg = feedback.get(action)
        if msg:
            speak(msg)
        result = os_pilot.run_command(action, params)
        if action == "READ_CLIPBOARD" and result:
            speak(f"Contenu: {str(result)[:100]}")

    else:
        speak("Commande non comprise. Repete s'il te plait.")


def execute_command_tracked(intent_data):
    """Wrapper: execute la commande et retourne (success, error)"""
    try:
        execute_command(intent_data)
        return True, None
    except Exception as e:
        return False, str(e)


def _check_learned_engine(text):
    """Verifie si le texte match un pattern appris via learning_engine"""
    if not LEARNING_ENGINE_OK:
        return None
    patterns = _le_get_learned_patterns()
    text_lower = text.lower().strip()
    for p in patterns:
        if p['pattern_text'] in text_lower:
            increment_pattern_use(p['pattern_text'])
            return {"action": p['action'], "params": p['params']}
    return None


def process_input(text):
    """Pipeline complet: CORRECT -> normalize -> intent (learned/fallback/M2) -> LOG -> learn -> action"""
    if not text.strip():
        return

    # -1. Correction phonetique IA (V3.6 LINGUISTE)
    # Passe 1: glossaire (instant). Passe 2: M2 IA si texte encore suspect (4s max)
    if CORRECTOR_OK:
        original = text
        text = speech_corrector.correct_text(text, use_m2=False)
        # Si le glossaire n'a rien change et que le texte contient des mots inconnus -> M2
        if text == original and _looks_garbled(text):
            text = speech_corrector.correct_text(text, use_m2=True)

    # 0. Normalisation conversationnelle (STT corrections + fillers + patterns)
    clean = normalize_speech(text)

    # === COMMANDES META (apprentissage) ===
    clean_lower = clean.lower().strip()

    # "apprends X = ACTION PARAMS" - apprentissage manuel
    learn_match = re.match(r'apprends?\s+(.+?)\s*=\s*(\w+)(?:\s+(.+))?', clean_lower)
    if learn_match:
        trigger = learn_match.group(1).strip()
        action = learn_match.group(2).upper().strip()
        params = (learn_match.group(3) or "").strip()
        if _learn_pattern(trigger, action, params, source="manual"):
            LEARNED_PATTERNS[trigger] = {"action": action, "params": params}
            speak(f"Compris. '{trigger}' est maintenant associe a {action}.")
        else:
            speak("Erreur lors de l'apprentissage.")
        return

    # "oublie X" - supprime un pattern appris
    forget_match = re.match(r'oublie\s+(.+)', clean_lower)
    if forget_match:
        trigger = forget_match.group(1).strip()
        if trigger in LEARNED_PATTERNS:
            del LEARNED_PATTERNS[trigger]
            try:
                conn = sqlite3.connect(LEARNING_DB)
                conn.execute("DELETE FROM learning_patterns WHERE trigger_phrase = ?", (trigger,))
                conn.commit()
                conn.close()
            except:
                pass
            speak(f"Pattern '{trigger}' oublie.")
        else:
            speak(f"Je ne connais pas '{trigger}'.")
        return

    # "qu'est-ce que tu as appris" / "patterns appris"
    if clean_lower in ("patterns appris", "qu'est-ce que tu as appris", "liste apprentissage", "ce que tu as appris"):
        if LEARNED_PATTERNS:
            speak(f"{len(LEARNED_PATTERNS)} patterns appris.")
            for trig, act in list(LEARNED_PATTERNS.items())[:8]:
                speak(f"  '{trig}' -> {act['action']}")
        else:
            speak("Aucun pattern appris pour le moment.")
        return

    # "echecs" / "commandes ratees" - affiche les top echecs
    if clean_lower in ("echecs", "commandes ratees", "erreurs frequentes", "top echecs"):
        fails = _get_top_failures(5)
        if fails:
            speak(f"{len(fails)} commandes non reconnues frequentes.")
            for f_text, f_count in fails:
                speak(f"  '{f_text}' - {f_count} fois")
        else:
            speak("Aucun echec enregistre.")
        return

    # === PIPELINE NORMAL (avec tracking complet) ===
    t0 = time.time()
    intent = None
    intent_source = "UNKNOWN"
    m2_latency_ms = 0

    # 1. Essayer fallback local d'abord (instantane, pas de latence reseau)
    local = local_fallback(clean)
    if local:
        intent = local
        if clean_lower in LEARNED_PATTERNS:
            intent_source = "FALLBACK_LEARNED"
        else:
            intent_source = "FALLBACK_LOCAL"
        print(f"  {intent_source}: {intent}")
    else:
        # 1b. Check learned_engine patterns (broader match)
        learned = _check_learned_engine(clean)
        if learned:
            intent = learned
            intent_source = "LEARNED_ENGINE"
            print(f"  LEARNED_ENGINE: {intent}")

    # 2. M2 si le fallback n'a rien trouve
    if not intent:
        t_m2 = time.time()
        intent = analyze_intent_with_m2(clean)
        m2_latency_ms = int((time.time() - t_m2) * 1000)
        intent_source = "M2"

    # 3. Si M2 a trouve, auto-apprendre pour la prochaine fois
    if intent_source == "M2" and intent.get("action") != "UNKNOWN":
        action = intent["action"]
        params = intent.get("params", "")
        if clean_lower not in LEARNED_PATTERNS and len(clean_lower.split()) <= 5:
            _learn_pattern(clean_lower, action, params, source="auto-m2")
            LEARNED_PATTERNS[clean_lower] = {"action": action, "params": params}
            print(f"  AUTO-LEARN: '{clean_lower}' -> {action} (from M2)")

    # 4. Execute with tracking
    t_exec = time.time()
    success, error = execute_command_tracked(intent)
    exec_latency_ms = int((time.time() - t_exec) * 1000)

    # 5. If UNKNOWN, log failure (legacy)
    if intent.get("action") == "UNKNOWN":
        _log_failure(text, clean_lower)
        intent_source = "UNKNOWN"

    # 6. Log to command_history (learning_engine)
    if LEARNING_ENGINE_OK:
        _le_log_command(
            raw_text=text,
            intent_source=intent_source,
            action=intent.get("action"),
            params=intent.get("params", ""),
            m2_latency_ms=m2_latency_ms,
            exec_success=success,
            exec_error=error,
            exec_latency_ms=exec_latency_ms,
        )


def manual_input_loop():
    """Mode test clavier"""
    print("=" * 60)
    print("  J.A.R.V.I.S. V3.6 LINGUISTE - MODE COMMANDE")
    print("  Tape tes ordres (quit pour sortir)")
    print("  Meta: apprends/oublie/patterns appris/echecs/rapport jarvis/auto-amelioration")
    print("=" * 60)
    while True:
        try:
            user_text = input("\n  JARVIS >> ")
            if user_text.lower() in ('quit', 'exit', 'q'):
                speak("Systeme en veille. A bientot.")
                break
            process_input(user_text)
        except KeyboardInterrupt:
            speak("Interruption. Au revoir.")
            break
        except EOFError:
            break


if __name__ == "__main__":
    print("=" * 60)
    print("  J.A.R.V.I.S. COMMANDER v3.6 LINGUISTE - Auto-Learning + Speech Correction")
    print(f"  Genesis: {'OK' if GENESIS_OK else 'OFF'} | TTS: {'OK' if TTS_OK else 'OFF'}")
    print(f"  Learning: {'OK' if LEARNING_OK else 'OFF'} | Engine: {'OK' if LEARNING_ENGINE_OK else 'OFF'}")
    corrector_info = f"OK ({len(speech_corrector._glossary)} termes)" if CORRECTOR_OK else "OFF"
    print(f"  Corrector: {corrector_info}")
    print(f"  Pilot: {PILOT_PATH}")
    print(f"  M2: {M2_URL}")
    print(f"  Normalizer: {len(STT_CORRECTIONS)} STT + {len(FILLER_WORDS)} fillers + {len(CONVERSATIONAL_PATTERNS)} conv")
    print(f"  Fallback: {len(PRIORITY_PATTERNS)} priority + {len(LOCAL_KEYWORDS)} kw + {len(PARAM_KEYWORDS)} prefix")
    print(f"  Learned: {len(LEARNED_PATTERNS)} patterns auto-appris")
    print(f"  Meta: apprends/oublie/patterns/echecs/rapport/checkpred/vocabulaire")
    print("=" * 60)
    speak("Jarvis version 3.6 Linguiste en ligne. Correction phonetique et auto-apprentissage actifs.")
    manual_input_loop()
