"""
SPEECH CORRECTOR v1.0 - Correcteur Phonetique Contextuel (V3.6 LINGUISTE)
Utilise M2 GPT-OSS pour corriger les erreurs STT de Whisper avant traitement.
Ex: "ouvre cro me" -> "Ouvre Chrome", "lance le traille dente" -> "Lance le Trident"

Cache local + glossaire JSON pour corrections rapides sans IA.
Fallback: retourne le texte brut si M2 est offline.
"""
import os
import sys
import json
import time
import re

# Config
ROOT = r"/home/turbo\TRADING_V2_PRODUCTION"
CONFIG_DIR = os.path.join(ROOT, "config")
GLOSSARY_PATH = os.path.join(CONFIG_DIR, "stt_corrections.json")
M2_URL = "http://192.168.1.26:1234/v1/chat/completions"
M2_MODEL = "openai/gpt-oss-20b"
M2_TIMEOUT = 4  # Rapide: on veut pas bloquer la boucle vocale

# Cache memoire pour eviter de re-appeler M2 pour la meme phrase
_correction_cache = {}

# Glossaire statique (charge au demarrage)
_glossary = {}


def load_glossary():
    """Charge le glossaire de corrections statiques depuis le JSON"""
    global _glossary
    if os.path.exists(GLOSSARY_PATH):
        try:
            with open(GLOSSARY_PATH, "r", encoding="utf-8") as f:
                _glossary = json.load(f)
        except Exception:
            _glossary = {}
    else:
        # Glossaire par defaut - erreurs phonetiques courantes Whisper FR
        _glossary = {
            # Crypto
            "bit coin": "Bitcoin",
            "bitcoin": "Bitcoin",
            "etherium": "Ethereum",
            "ethereum": "Ethereum",
            "eth": "ETH",
            "btc": "BTC",
            "usdt": "USDT",
            "mexc": "MEXC",
            "binance": "Binance",
            "bybit": "Bybit",
            "river": "RIVER",
            "rieuver": "RIVER",
            "rivert": "RIVER",
            "trump": "TRUMP",
            # Apps / OS
            "cro me": "Chrome",
            "crome": "Chrome",
            "chrome": "Chrome",
            "edge": "Edge",
            "firefox": "Firefox",
            "explorateur": "Explorateur",
            "notepad": "Notepad",
            "terminal": "Terminal",
            "power shell": "PowerShell",
            "powershell": "PowerShell",
            # Commandes trading
            "traille dente": "Trident",
            "trident": "Trident",
            "tridant": "Trident",
            "sniper": "Sniper",
            "snaiper": "Sniper",
            "pipe line": "Pipeline",
            "pipeline": "Pipeline",
            "scan": "scan",
            "hyper scan": "hyper scan",
            "hyper scanne": "hyper scan",
            # Indicateurs
            "rsi": "RSI",
            "ema": "EMA",
            "macd": "MACD",
            "bollinger": "Bollinger",
            "chaikin": "Chaikin",
            "volume": "volume",
            "funding rate": "funding rate",
            "pnl": "PnL",
            "roi": "ROI",
            "fvg": "Fair Value Gap",
            "order block": "Order Block",
            # Commandes JARVIS
            "ouvre": "ouvre",
            "ferme": "ferme",
            "capture": "capture",
            "screenshot": "screenshot",
            "ecris": "ecris",
            "tape": "tape",
            "recherche": "recherche",
            "volume": "volume",
            "mute": "mute",
            "bureau": "bureau",
            # Corrections phonetiques
            "la fenetre": "la fenetre",
            "s il te plait": "s'il te plait",
        }
        # Sauvegarder le glossaire par defaut
        save_glossary()


def save_glossary():
    """Sauvegarde le glossaire sur disque"""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(GLOSSARY_PATH, "w", encoding="utf-8") as f:
        json.dump(_glossary, f, indent=2, ensure_ascii=False)


def add_correction(wrong, correct):
    """Ajoute une correction au glossaire et sauvegarde"""
    _glossary[wrong.lower()] = correct
    save_glossary()


def correct_with_glossary(text):
    """Correction rapide par glossaire statique (sans appel IA)"""
    if not text or not _glossary:
        return text

    corrected = text
    lower = text.lower()

    # Remplacement des termes du glossaire (plus longs d'abord pour eviter les collisions)
    sorted_keys = sorted(_glossary.keys(), key=len, reverse=True)
    for wrong in sorted_keys:
        correct = _glossary[wrong]
        if wrong in lower:
            # Remplacement case-insensitive
            pattern = re.compile(re.escape(wrong), re.IGNORECASE)
            corrected = pattern.sub(correct, corrected)
            lower = corrected.lower()

    return corrected


def correct_with_m2(text):
    """Correction contextuelle via M2 GPT-OSS (appel reseau)"""
    try:
        import requests
    except ImportError:
        import urllib.request
        return _correct_with_m2_urllib(text)

    try:
        payload = {
            "model": M2_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Tu es un correcteur pour un systeme de trading vocal. "
                        "Corrige les erreurs phonetiques, noms propres crypto et grammaire. "
                        "REPONDS UNIQUEMENT par la phrase corrigee. Rien d'autre."
                    )
                },
                {"role": "user", "content": text}
            ],
            "temperature": 0.1,
            "max_tokens": 100,
        }
        r = requests.post(M2_URL, json=payload, timeout=M2_TIMEOUT)
        if r.status_code == 200:
            content = r.json()["choices"][0]["message"].get("content", "")
            if not content:
                content = r.json()["choices"][0]["message"].get("reasoning", "")
            # Nettoyage
            content = content.strip().strip('"').strip("'")
            content = re.sub(r"^(Corrected|Correction|Voici):\s*", "", content, flags=re.IGNORECASE).strip()
            if content and len(content) < len(text) * 3:
                return content
        return text
    except Exception:
        return text


def _correct_with_m2_urllib(text):
    """Fallback urllib si requests pas disponible"""
    import urllib.request
    try:
        payload = json.dumps({
            "model": M2_MODEL,
            "messages": [
                {"role": "system", "content": "Corrige les erreurs phonetiques. REPONDS UNIQUEMENT par la phrase corrigee."},
                {"role": "user", "content": text}
            ],
            "temperature": 0.1,
            "max_tokens": 100,
        }).encode("utf-8")
        req = urllib.request.Request(
            M2_URL, data=payload,
            headers={"Content-Type": "application/json"}
        )
        resp = urllib.request.urlopen(req, timeout=M2_TIMEOUT)
        data = json.loads(resp.read())
        content = data["choices"][0]["message"].get("content", "")
        if not content:
            content = data["choices"][0]["message"].get("reasoning", "")
        return content.strip().strip('"') if content else text
    except Exception:
        return text


def correct_text(raw_text, use_m2=True):
    """
    Pipeline de correction complet:
    1. Cache memoire (instant)
    2. Glossaire statique (instant)
    3. M2 IA contextuelle (2-4s, optionnel)
    """
    if not raw_text or len(raw_text.strip()) < 3:
        return raw_text

    text = raw_text.strip()

    # 1. Cache memoire
    cache_key = text.lower()
    if cache_key in _correction_cache:
        return _correction_cache[cache_key]

    # 2. Glossaire statique
    corrected = correct_with_glossary(text)

    # 3. M2 IA (si active et si le texte semble incorrect)
    if use_m2 and corrected == text:
        # Seulement si le glossaire n'a rien change (evite double correction)
        corrected = correct_with_m2(text)

    # Log si modification
    if corrected.lower() != text.lower():
        print(f"  CORRECTOR: '{text}' -> '{corrected}'")

    # Mettre en cache
    _correction_cache[cache_key] = corrected
    return corrected


# Charger le glossaire au demarrage
load_glossary()


if __name__ == "__main__":
    print("=== SPEECH CORRECTOR v1.0 - TEST ===\n")

    tests = [
        "ouvre cro me",
        "lance le traille dente sur le bit coin",
        "analyse le rieuver",
        "ferme la fenetre",
        "scan le mexc",
        "hyper scanne maintenant",
        "capture d ecran",
    ]

    for t in tests:
        result = correct_text(t, use_m2=False)  # Glossaire seulement pour le test
        changed = " [CORRIGE]" if result != t else ""
        print(f"  '{t}' -> '{result}'{changed}")

    print(f"\n  Glossaire: {len(_glossary)} entrees")
    print(f"  Cache: {len(_correction_cache)} entrees")
    print(f"  Fichier: {GLOSSARY_PATH}")
