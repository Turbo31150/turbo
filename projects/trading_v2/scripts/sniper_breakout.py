#!/usr/bin/env python3
"""
SNIPER BREAKOUT v2.0 - Full cluster: M1+MCP, M2, M3, OL1 web search
Agents: SCANNER(M2) | WEB_INTEL(OL1) | MCP_ANALYST(M1+HF) | VOTERS(M1,M2,M3)
"""
import sys, json, urllib.request, time, sqlite3, re
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

# CONFIG
DB_PATH = 'F:/BUREAU/TRADING_V2_PRODUCTION/database/trading.db'
PRIORITY_COINS = ['BERA_USDT']
MIN_VOL = 1_000_000
MIN_RANGE_POS = 0.80
MIN_SCORE = 35
CYCLE_DELAY = 60
MAX_CYCLES = int(sys.argv[1]) if len(sys.argv) > 1 else 10

# ── AGENTS / NODES ───────────────────────────────────────────────────────
IA_NODES = [
    {'name': 'M1-Qwen', 'url': 'http://10.5.0.2:1234', 'model': 'qwen/qwen3-30b-a3b-2507',
     'key': 'LMSTUDIO_KEY_M1_REDACTED', 'role': 'analyst'},
    {'name': 'M2-DeepSeek', 'url': 'http://192.168.1.26:1234', 'model': 'deepseek-coder-v2-lite-instruct',
     'key': 'LMSTUDIO_KEY_M2_REDACTED', 'role': 'coder'},
    {'name': 'M3-Mistral', 'url': 'http://192.168.1.113:1234', 'model': 'mistral-7b-instruct-v0.3',
     'key': '', 'role': 'fast'},
]

# OL1 — Ollama local (fallback qwen3:1.7b si cloud indisponible)
OL1_URL = 'http://127.0.0.1:11434'
OL1_WEB_MODEL = 'qwen3:1.7b'

# M1 MCP — HuggingFace integration (LM Studio 0.4.0+)
MCP_INTEGRATIONS = [{
    "type": "ephemeral_mcp",
    "server_label": "huggingface",
    "server_url": "https://huggingface.co/mcp",
}]

NO_SYSTEM = ['mistral-7b-instruct-v0.3', 'phi-3.1-mini-128k-instruct']
TELEGRAM_TOKEN = 'TELEGRAM_TOKEN_REDACTED'
TELEGRAM_CHAT = '2010747443'

def log(msg, level='  ', end='\n'):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f"[{ts}] [{level}] {msg}", end=end, flush=True)

def fetch_json(url, timeout=10):
    try:
        return json.loads(urllib.request.urlopen(url, timeout=timeout).read())
    except:
        return None

def get_klines(sym, interval='Min15', limit=50):
    url = f'https://contract.mexc.com/api/v1/contract/kline/{sym}?interval={interval}&limit={limit}'
    data = fetch_json(url)
    if not data or 'data' not in data:
        return None
    d = data['data']
    return {
        'close': [float(x) for x in d.get('close', [])],
        'high': [float(x) for x in d.get('high', [])],
        'low': [float(x) for x in d.get('low', [])],
        'vol': [float(x) for x in d.get('vol', [])],
    }

def rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i-1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    ag = sum(gains[-period:]) / period
    al = sum(losses[-period:]) / period
    if al == 0:
        return 100
    return 100 - 100 / (1 + ag / al)

def bb_width(closes, period=20):
    if len(closes) < period:
        return 100
    sma = sum(closes[-period:]) / period
    std = (sum((c - sma) ** 2 for c in closes[-period:]) / period) ** 0.5
    return (std / sma) * 100 if sma > 0 else 100

def macd(closes):
    if len(closes) < 26:
        return 0, 0
    ema12 = closes[-1]
    ema26 = closes[-1]
    for c in closes[-26:]:
        ema12 = c * (2/13) + ema12 * (11/13)
        ema26 = c * (2/27) + ema26 * (25/27)
    return ema12 - ema26, 0

def orderbook(sym):
    url = f'https://contract.mexc.com/api/v1/contract/depth/{sym}?limit=20'
    data = fetch_json(url)
    if not data or 'data' not in data:
        return 50, 0
    d = data['data']
    bids = sum(float(b[1]) for b in d.get('bids', []))
    asks = sum(float(a[1]) for a in d.get('asks', []))
    total = bids + asks
    buy_pct = bids / total * 100 if total > 0 else 50
    spread = 0
    if d.get('bids') and d.get('asks'):
        spread = (float(d['asks'][0][0]) - float(d['bids'][0][0])) / float(d['asks'][0][0]) * 100
    return buy_pct, spread

def ol1_web_search(query, timeout=45):
    """Agent WEB_INTEL: analyse sentiment via OL1 (local qwen3 ou cloud minimax)."""
    body = json.dumps({
        "model": OL1_WEB_MODEL,
        "messages": [
            {"role": "system", "content":
                "Tu es un analyste crypto. Analyse le coin demande. "
                "Reponds en 2-3 lignes: SENTIMENT(bullish/bearish/neutre), "
                "raisons techniques, risques. Sois concis."},
            {"role": "user", "content": query},
        ],
        "stream": False, "think": False,
        "options": {"temperature": 0.3, "num_predict": 200},
    })
    req = urllib.request.Request(
        f"{OL1_URL}/api/chat", data=body.encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
        return resp.get('message', {}).get('content', '')
    except Exception as e:
        log(f"  OL1-WEB ERREUR: {e}")
        return None


def ask_m1_mcp(prompt, timeout=60):
    """Agent MCP_ANALYST: M1 + HuggingFace MCP pour analyse enrichie."""
    m1 = IA_NODES[0]  # M1-Qwen
    body = json.dumps({
        "model": m1['model'],
        "input": prompt + " /no_think",
        "integrations": MCP_INTEGRATIONS,
        "context_length": 8000,
        "temperature": 0.3,
        "max_output_tokens": 300,
        "stream": False,
        "store": False,
    })
    headers = {"Content-Type": "application/json",
               "Authorization": f"Bearer {m1['key']}"}
    req = urllib.request.Request(f"{m1['url']}/api/v1/chat", data=body.encode(), headers=headers)
    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
        parts = []
        for item in resp.get('output', []):
            t = item.get('type', 'message')
            if t == 'message' and item.get('content'):
                parts.append(item['content'])
            elif t == 'tool_call':
                parts.append(f"[MCP:{item.get('tool','?')}] {item.get('output','')[:200]}")
        return '\n'.join(parts) if parts else None
    except Exception as e:
        log(f"  M1-MCP ERREUR: {e}")
        return None


def ask_node(node, prompt, timeout=30):
    system_msg = (
        "Tu es un analyste trading NEUTRE et OBJECTIF. Considere TOUJOURS les deux scenarios:\n"
        "- LONG: momentum, breakout confirme, volume croissant\n"
        "- SHORT: coin deja pumpe (retrace probable), RSI surachete, faux breakout\n"
        "Si le coin a pumpe >5% en 24h, un SHORT/retrace est STATISTIQUEMENT plus probable.\n"
        "Reponds UNIQUEMENT: DIRECTION(LONG/SHORT) CONFIDENCE(0-100%)"
    )
    if node['model'] in NO_SYSTEM:
        full_prompt = system_msg + "\n\n" + prompt
    else:
        full_prompt = f"[SYSTEM] {system_msg}\n\n[USER] {prompt}"
    body = json.dumps({
        "model": node['model'],
        "input": full_prompt,
        "temperature": 0.65,
        "max_output_tokens": 150,
        "stream": False,
        "store": False,
    })
    headers = {"Content-Type": "application/json"}
    if node.get('key'):
        headers["Authorization"] = f"Bearer {node['key']}"
    req = urllib.request.Request(
        f"{node['url']}/api/v1/chat",
        data=body.encode(),
        headers=headers,
    )
    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
        output = resp.get('output', [])
        if not output:
            return None
        for item in output:
            c = item.get('content', '')
            if c:
                return c
        return None
    except Exception as e:
        log(f"  {node['name']} ERREUR: {e}")
        return None

def parse_vote(text):
    if not text:
        return None, 0
    text = text.upper()
    direction = None
    confidence = 50
    if 'LONG' in text:
        direction = 'LONG'
    elif 'SHORT' in text:
        direction = 'SHORT'
    m = re.search(r'(\d{1,3})%', text)
    if m:
        confidence = int(m.group(1))
    return direction, confidence

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = json.dumps({"chat_id": TELEGRAM_CHAT, "text": msg, "parse_mode": "HTML"}).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
        return True
    except:
        return False

def save_prediction(sym, direction, entry, tp1, tp2, tp3, sl, score, confidence, reasons):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""INSERT INTO predictions
            (created_at, symbol, direction, entry_price, tp1, tp2, tp3, sl, score, confidence, result, models_used)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?)""",
            (datetime.now().isoformat(), sym, direction, entry, tp1, tp2, tp3, sl, score, confidence,
             'sniper_v2_M1mcp+M2+M3+OL1'))
        conn.commit()
        conn.close()
        return True
    except:
        return False

# ============================================================
# MAIN SNIPER LOOP
# ============================================================
def run_sniper():
    log("=" * 60)
    log("  SNIPER BREAKOUT v2.0 - FULL CLUSTER")
    log(f"  Agents: M1+MCP | M2 | M3 | OL1-web")
    log(f"  Priority: {', '.join(PRIORITY_COINS)}")
    log(f"  Cycle: {CYCLE_DELAY}s | Max: {MAX_CYCLES} cycles")
    log("=" * 60)

    total_signals = 0
    start_time = time.time()

    for cycle in range(1, MAX_CYCLES + 1):
        cycle_start = time.time()
        log("")
        log("=" * 60, '>>')
        log(f"  SNIPER CYCLE #{cycle} - {datetime.now().strftime('%H:%M:%S')}", '>>')
        log("=" * 60)

        # STAGE 1: Scan tickers
        log("SCAN MEXC FUTURES", '>>')
        tickers_data = fetch_json('https://contract.mexc.com/api/v1/contract/ticker')
        if not tickers_data or 'data' not in tickers_data:
            log("ERREUR: impossible de scanner MEXC", '!!')
            time.sleep(CYCLE_DELAY)
            continue

        tickers = tickers_data['data']
        candidates = []

        for t in tickers:
            sym = t.get('symbol', '')
            change = float(t.get('riseFallRate', 0)) * 100
            vol = float(t.get('volume24', 0))
            last = float(t.get('lastPrice', 0))
            high = float(t.get('high24Price', 0))
            low = float(t.get('low24Price', 0))

            if last == 0 or high == low:
                continue

            is_priority = sym in PRIORITY_COINS
            range_pos = (last - low) / (high - low)

            # Priority coins: always include
            if is_priority:
                candidates.append({
                    'sym': sym, 'price': last, 'change': change, 'vol': vol,
                    'high': high, 'low': low, 'range_pos': range_pos, 'priority': True
                })
            # Others: filter by breakout criteria
            elif vol >= MIN_VOL and range_pos >= MIN_RANGE_POS and change > 2:
                candidates.append({
                    'sym': sym, 'price': last, 'change': change, 'vol': vol,
                    'high': high, 'low': low, 'range_pos': range_pos, 'priority': False
                })

        # Sort: priority first, then by range_pos * volume
        candidates.sort(key=lambda x: (x['priority'], x['range_pos'] * min(x['vol']/1e6, 10)), reverse=True)
        candidates = candidates[:8]  # max 8 to analyze

        log(f"  {len(tickers)} futures | {len(candidates)} candidats (priority: {sum(1 for c in candidates if c['priority'])})")

        # STAGE 2: Multi-TF Analysis
        log("MULTI-TF ANALYSIS", '>>')
        scored = []

        for c in candidates:
            sym = c['sym']
            score = 0
            reasons = []

            for tf_name, tf_code, weight in [('15m', 'Min15', 0.3), ('1H', 'Min60', 0.5), ('4H', 'Hour4', 0.2)]:
                kl = get_klines(sym, tf_code, 50)
                if not kl or len(kl['close']) < 20:
                    continue

                r = rsi(kl['close'])
                bb = bb_width(kl['close'])
                mc, _ = macd(kl['close'])
                vol_avg = sum(kl['vol'][-20:]) / 20 if len(kl['vol']) >= 20 else 1
                vol_ratio = kl['vol'][-1] / max(vol_avg, 0.001)

                tf_score = 0

                # RSI momentum
                if r > 60:
                    tf_score += 10
                    reasons.append(f"{tf_name}:RSI({r:.0f})")
                elif r < 30:
                    tf_score += 8
                    reasons.append(f"{tf_name}:OVERSOLD({r:.0f})")

                # BB squeeze (pre-breakout)
                if bb < 5:
                    tf_score += 15
                    reasons.append(f"{tf_name}:BB_SQUEEZE({bb:.1f}%)")
                elif bb < 10:
                    tf_score += 8
                    reasons.append(f"{tf_name}:BB_TIGHT({bb:.1f}%)")

                # Volume spike
                if vol_ratio > 3:
                    tf_score += 15
                    reasons.append(f"{tf_name}:VOL_SPIKE(x{vol_ratio:.1f})")
                elif vol_ratio > 2:
                    tf_score += 10
                    reasons.append(f"{tf_name}:VOL_SURGE(x{vol_ratio:.1f})")

                # MACD bullish
                if mc > 0:
                    tf_score += 5
                    reasons.append(f"{tf_name}:MACD_BULL")

                # Breakout position
                if c['range_pos'] > 0.90:
                    tf_score += 10
                    reasons.append(f"{tf_name}:BREAKOUT({c['range_pos']:.2f})")

                score += tf_score * weight
                time.sleep(0.3)

            # RSI Overbought penalty (1H)
            kl_rsi = get_klines(sym, 'Min60', 50)
            rsi_1h = rsi(kl_rsi['close']) if kl_rsi and len(kl_rsi['close']) >= 15 else 50
            c['rsi_1h'] = rsi_1h
            if rsi_1h > 80:
                score -= 10
                reasons.append(f"RSI_OVERBOUGHT({rsi_1h:.0f})")
            elif rsi_1h > 70:
                score -= 5
                reasons.append(f"RSI_HIGH({rsi_1h:.0f})")

            # Priority bonus
            if c['priority']:
                score += 15
                reasons.append("PRIORITY")

            # Volume bonus
            if c['vol'] > 10e6:
                score += 10
            elif c['vol'] > 5e6:
                score += 5

            c['score'] = int(score)
            c['reasons'] = reasons

            r_display = rsi(get_klines(sym, 'Min60', 50)['close']) if get_klines(sym, 'Min60', 50) else 0
            log(f"  {sym}: score={c['score']} range={c['range_pos']:.2f} chg={c['change']:+.1f}% vol={c['vol']/1e6:.1f}M {'*PRIORITY*' if c['priority'] else ''}")

            if c['score'] >= MIN_SCORE:
                scored.append(c)

        scored.sort(key=lambda x: x['score'], reverse=True)
        scored = scored[:3]  # Top 3

        if not scored:
            log(f"  Aucun signal qualifie (score>={MIN_SCORE})")
            elapsed = time.time() - cycle_start
            wait = max(CYCLE_DELAY - elapsed, 10)
            log(f"Cycle #{cycle} termine en {elapsed:.0f}s | Prochain dans {wait:.0f}s")
            time.sleep(wait)
            continue

        log(f"  {len(scored)} coins qualifies | Top: {', '.join(s['sym'] + '(' + str(s['score']) + ')' for s in scored)}")

        # STAGE 3: Orderbook
        log("ORDERBOOK ANALYSIS", '>>')
        for s in scored:
            bp, sp = orderbook(s['sym'])
            s['buy_pct'] = bp
            s['spread'] = sp
            wall = 'BUY WALL' if bp > 65 else 'SELL WALL' if bp < 35 else ''
            log(f"  {s['sym']}: buy={bp:.0f}% spread={sp:.3f}% {wall}")

        # STAGE 4: WEB INTEL (OL1/minimax cloud search)
        log("WEB INTEL (OL1/minimax)", '>>')
        for s in scored:
            coin_name = s['sym'].replace('_USDT', '')
            query = f"{coin_name} crypto news sentiment today trading signal"
            web_result = ol1_web_search(query, timeout=45)
            if web_result:
                s['web_intel'] = web_result[:300]
                log(f"  {s['sym']}: {web_result[:80]}...")
            else:
                s['web_intel'] = ''
                log(f"  {s['sym']}: pas de donnees web")

        # STAGE 5: MCP ANALYST (M1+HuggingFace)
        log("MCP ANALYST (M1+HuggingFace)", '>>')
        for s in scored:
            coin_name = s['sym'].replace('_USDT', '')
            mcp_prompt = (
                f"Search for the latest sentiment and trending analysis about {coin_name} crypto. "
                f"Is it bullish or bearish? Any major news?"
            )
            mcp_result = ask_m1_mcp(mcp_prompt, timeout=90)
            if mcp_result:
                s['mcp_intel'] = mcp_result[:300]
                log(f"  {s['sym']}: {mcp_result[:80]}...")
            else:
                s['mcp_intel'] = ''
                log(f"  {s['sym']}: pas de donnees MCP")

        # STAGE 6: IA CONSENSUS (M1 + M2 + M3, enrichi web+MCP)
        log("CONSENSUS IA (full cluster)", '>>')
        signals = []

        for s in scored:
            sym = s['sym']
            kl_1h = get_klines(sym, 'Min60', 50)
            rsi_val = rsi(kl_1h['close']) if kl_1h and len(kl_1h['close']) >= 15 else 50
            rsi_status = "SURACHETE (>70)" if rsi_val > 70 else "SURVENDU (<30)" if rsi_val < 30 else "neutre"
            pump_warning = f" ATTENTION: deja pumpe {s['change']:+.1f}% (risque retrace)." if s['change'] > 5 else ""

            # Enrichir le prompt avec web intel + MCP
            web_section = f"\nWEB INTEL: {s['web_intel']}" if s.get('web_intel') else ""
            mcp_section = f"\nMCP DATA: {s['mcp_intel']}" if s.get('mcp_intel') else ""

            prompt = (
                f"Analyse {sym} MEXC Futures. Prix: {s['price']}, Change 24h: {s['change']:+.1f}%, "
                f"Range: {s['range_pos']:.2f}, RSI 1H: {rsi_val:.0f} ({rsi_status}), "
                f"Volume: {s['vol']/1e6:.1f}M, Orderbook buy: {s['buy_pct']:.0f}%.{pump_warning}\n"
                f"Indicateurs: {', '.join(s['reasons'][:5])}."
                f"{web_section}{mcp_section}\n"
                f"Analyse les DEUX scenarios (LONG et SHORT) puis choisis. LONG ou SHORT? Confidence?"
            )

            votes = []
            for node in IA_NODES:  # 3 nodes pour consensus
                resp = ask_node(node, prompt, timeout=25)
                d, c = parse_vote(resp)
                if d and c >= 65:  # Filtre confidence minimale
                    votes.append((d, c, node['name']))
                    log(f"  {node['name']}={d}/{c}%", end=' ')
                elif d:
                    log(f"  {node['name']}={d}/{c}% (FILTRE<65%)", end=' ')

            print()  # newline after votes

            if not votes:
                log(f"  {sym}: NO VALID VOTES (all failed or <65% conf), SKIP")
                continue

            # Majority vote (tie-breaking neutre)
            longs = [(c, n) for d, c, n in votes if d == 'LONG']
            shorts = [(c, n) for d, c, n in votes if d == 'SHORT']

            if len(longs) > len(shorts):
                direction = 'LONG'
                conf = sum(c for c, _ in longs) / len(longs)
            elif len(shorts) > len(longs):
                direction = 'SHORT'
                conf = sum(c for c, _ in shorts) / len(shorts)
            elif longs and shorts:
                # Egalite: prendre la direction avec la confidence moyenne la plus haute
                avg_long_conf = sum(c for c, _ in longs) / len(longs)
                avg_short_conf = sum(c for c, _ in shorts) / len(shorts)
                direction = 'LONG' if avg_long_conf > avg_short_conf else 'SHORT'
                conf = max(avg_long_conf, avg_short_conf)
            else:
                log(f"  {sym}: NO DIRECTIONAL VOTES, SKIP")
                continue

            log(f"  -> {sym}: {direction} {conf:.0f}% ({len(longs)}L/{len(shorts)}S)")

            # Generate signal
            entry = s['price']
            if direction == 'LONG':
                tp1 = entry * 1.02  # +2% sniper
                tp2 = entry * 1.04  # +4%
                tp3 = entry * 1.07  # +7%
                sl = entry * 0.985  # -1.5%
            else:
                tp1 = entry * 0.98
                tp2 = entry * 0.96
                tp3 = entry * 0.93
                sl = entry * 1.015

            prob = min(int(conf * s['score'] / 100), 99)

            signals.append({
                'sym': sym, 'direction': direction, 'entry': entry,
                'tp1': tp1, 'tp2': tp2, 'tp3': tp3, 'sl': sl,
                'score': s['score'], 'confidence': conf, 'prob': prob,
                'reasons': s['reasons'], 'buy_pct': s['buy_pct'],
                'change': s['change'], 'range_pos': s['range_pos'],
                'priority': s.get('priority', False),
                'web_intel': s.get('web_intel', ''), 'mcp_intel': s.get('mcp_intel', '')
            })

        if not signals:
            log("Aucun signal valide apres consensus")
            elapsed = time.time() - cycle_start
            wait = max(CYCLE_DELAY - elapsed, 10)
            log(f"Cycle #{cycle} termine en {elapsed:.0f}s | Prochain dans {wait:.0f}s")
            time.sleep(wait)
            continue

        # STAGE 5: Output
        signals.sort(key=lambda x: (x['priority'], x['score']), reverse=True)

        print()
        print("=" * 60)
        print(f"  SNIPER BREAKOUT v2.0 - CYCLE #{cycle}")
        print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | LIVE MEXC")
        print("=" * 60)

        tg_msg = f"<b>SNIPER #{cycle}</b>\n"

        for i, sig in enumerate(signals):
            star = " *PRIORITY*" if sig['priority'] else ""
            print(f"\n  #{i+1} {sig['sym']} ({sig['direction']}){star}")
            print(f"  {'─' * 50}")
            print(f"  Entry:      {sig['entry']} USDT")
            print(f"  TP1 (50%):  {sig['tp1']:.6f}  (+{abs(sig['tp1']/sig['entry']-1)*100:.1f}%)")
            print(f"  TP2 (30%):  {sig['tp2']:.6f}  (+{abs(sig['tp2']/sig['entry']-1)*100:.1f}%)")
            print(f"  TP3 (20%):  {sig['tp3']:.6f}  (+{abs(sig['tp3']/sig['entry']-1)*100:.1f}%)")
            print(f"  SL:         {sig['sl']:.6f}  ({abs(sig['sl']/sig['entry']-1)*100:.1f}%)")
            print(f"  Score:      {sig['score']}/100 | Conf: {sig['confidence']:.0f}% | Prob: {sig['prob']}%")
            print(f"  Orderbook:  buy={sig['buy_pct']:.0f}%")
            print(f"  Raisons:    {', '.join(sig['reasons'][:6])}")
            if sig.get('web_intel'):
                print(f"  Web Intel:  {sig['web_intel'][:80]}...")
            if sig.get('mcp_intel'):
                print(f"  MCP Data:   {sig['mcp_intel'][:80]}...")

            tg_msg += f"\n{'*' if sig['priority'] else ''}{sig['sym']} {sig['direction']}\n"
            tg_msg += f"Entry: {sig['entry']} | TP1: {sig['tp1']:.6f} (+{abs(sig['tp1']/sig['entry']-1)*100:.1f}%)\n"
            tg_msg += f"Score: {sig['score']} | Conf: {sig['confidence']:.0f}%\n"

            save_prediction(sig['sym'], sig['direction'], sig['entry'],
                          sig['tp1'], sig['tp2'], sig['tp3'], sig['sl'],
                          sig['score'], sig['confidence'], ', '.join(sig['reasons']))
            total_signals += 1

        send_telegram(tg_msg)
        log(f"  Telegram + SQL OK | Total signals: {total_signals}")

        elapsed = time.time() - cycle_start
        wait = max(CYCLE_DELAY - elapsed, 10)
        log(f"Cycle #{cycle} termine en {elapsed:.0f}s | Prochain dans {wait:.0f}s")

        if cycle < MAX_CYCLES:
            time.sleep(wait)

    runtime = (time.time() - start_time) / 60
    print(f"\nSNIPER TERMINE\nCycles: {MAX_CYCLES} | Runtime: {runtime:.1f}min\nSignals: {total_signals}")

if __name__ == '__main__':
    run_sniper()
