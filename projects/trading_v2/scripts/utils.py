#!/usr/bin/env python3
"""
UTILS v1.0 - Fonctions communes pour TRADING_V2_PRODUCTION
Elimine les doublons entre scripts (send_telegram, fetch_json, ema, log, etc.)
"""
import json
import urllib.request
from datetime import datetime

# === DEFAULTS (overridable par chaque script) ===
DEFAULT_TELEGRAM_TOKEN = '8369376863:AAF-7YGDbun8mXWwqYJFj-eX6P78DeIu9Aw'
DEFAULT_TELEGRAM_CHAT = '2010747443'


# === LOGGING ===

def log(msg, level='INFO'):
    """Log avec timestamp. Levels: INFO, OK, WARN, ERR, CYCLE"""
    tags = {'INFO': '  ', 'OK': 'OK', 'WARN': '!!', 'ERR': 'XX', 'CYCLE': '>>'}
    tag = tags.get(level, '  ')
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [{tag}] {msg}", flush=True)


# === HTTP ===

def fetch_json(url, timeout=10):
    """GET JSON depuis une URL. Retourne None si erreur."""
    try:
        return json.loads(urllib.request.urlopen(url, timeout=timeout).read())
    except Exception:
        return None


def post_json(url, data, timeout=30):
    """POST JSON vers une URL. Retourne dict ou {'error': ...}."""
    try:
        payload = json.dumps(data).encode()
        req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
        return json.loads(urllib.request.urlopen(req, timeout=timeout).read())
    except Exception as e:
        return {'error': str(e)}


# === TELEGRAM ===

def send_telegram(msg, token=None, chat_id=None, parse_mode=None):
    """Envoie un message Telegram. Retourne message_id ou 'FAIL'.

    Compatible avec toutes les variantes precedentes:
    - hyper_scan_v2: send_telegram(msg)  (pas de parse_mode)
    - sniper_breakout: send_telegram(msg) avec parse_mode='HTML'
    - execute_trident: send_telegram(msg) retourne message_id
    - river_scalp/sniper_10: tg(msg) retourne message_id
    """
    token = token or DEFAULT_TELEGRAM_TOKEN
    chat_id = chat_id or DEFAULT_TELEGRAM_CHAT
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {'chat_id': chat_id, 'text': str(msg)[:4000]}
        if parse_mode:
            payload['parse_mode'] = parse_mode
        body = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'})
        resp = urllib.request.urlopen(req, timeout=10)
        return json.loads(resp.read()).get('result', {}).get('message_id', '?')
    except Exception:
        return 'FAIL'


# Alias court (remplace tg() dans river_scalp et sniper_10cycles)
tg = send_telegram


# === INDICATEURS TECHNIQUES ===

def ema(data, period):
    """Exponential Moving Average."""
    k = 2 / (period + 1)
    e = data[0]
    for d in data[1:]:
        e = d * k + e * (1 - k)
    return e


def calc_rsi(closes, period=14):
    """Relative Strength Index."""
    if len(closes) < period + 1:
        return 50
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    ag = sum(gains[-period:]) / period
    al = sum(losses[-period:]) / period
    return 100 - (100 / (1 + ag / al)) if al > 0 else 100
