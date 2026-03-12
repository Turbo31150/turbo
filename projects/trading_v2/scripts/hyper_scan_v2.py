#!/usr/bin/env python3
"""
HYPER-SCAN V2 - Grid Computing sur 3 Nodes + Gemini
M1=Strategie, M2=Technique, M3=Contrarian, Gemini=Juge
"""
import json, urllib.request, subprocess, sqlite3, time, sys, os, math
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

ROOT = r"/home/turbo\TRADING_V2_PRODUCTION"
CONFIG_FILE = os.path.join(ROOT, "config", "cluster_map.json")
DB_PATH = os.path.join(ROOT, "database", "trading.db")
MAX_CYCLES = int(sys.argv[1]) if len(sys.argv) > 1 else 10
CYCLE_DELAY = 120  # 2min entre cycles (rapide, grid computing)
TOP_COINS = 5
MIN_SCORE = 35

with open(CONFIG_FILE, 'r') as f:
    CLUSTER = json.load(f)

TELEGRAM_TOKEN = CLUSTER['telegram']['token']
TELEGRAM_CHAT = CLUSTER['telegram']['chat_id']

# No system prompt for these models
NO_SYSTEM = ['mistral-7b-instruct-v0.3']

def log(msg, level='INFO'):
    tag = {'INFO': '  ', 'OK': 'OK', 'WARN': '!!', 'ERR': 'XX', 'CYCLE': '>>'}.get(level, '  ')
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [{tag}] {msg}", flush=True)

def fetch_json(url, timeout=10):
    try:
        return json.loads(urllib.request.urlopen(url, timeout=timeout).read())
    except:
        return None

def post_json(url, data, timeout=30):
    try:
        payload = json.dumps(data).encode()
        req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
        return json.loads(urllib.request.urlopen(req, timeout=timeout).read())
    except Exception as e:
        return {'error': str(e)}

def send_telegram(msg):
    try:
        post_json(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                  {'chat_id': TELEGRAM_CHAT, 'text': msg[:4000]}, timeout=5)
    except:
        pass

# ============================================================
# INDICATEURS TECHNIQUES
# ============================================================
def calc_rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i-1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    ag = sum(gains[-period:]) / period
    al = sum(losses[-period:]) / period
    return 100 - (100 / (1 + ag / al)) if al > 0 else 100

def calc_bb_width(closes, period=20):
    if len(closes) < period:
        return 999
    sma = sum(closes[-period:]) / period
    std = math.sqrt(sum((c - sma)**2 for c in closes[-period:]) / period)
    return (4 * std / sma * 100) if sma > 0 else 999

def calc_vol_ratio(volumes, lookback=10):
    if len(volumes) < lookback + 1:
        return 1
    avg = sum(volumes[-lookback-1:-1]) / lookback
    return volumes[-1] / avg if avg > 0 else 1

# ============================================================
# STAGE 1: SCAN MEXC + INDICATEURS
# ============================================================
def scan_mexc():
    log("STAGE 1: SCAN MEXC FUTURES", 'CYCLE')
    tickers = fetch_json('https://contract.mexc.com/api/v1/contract/ticker')
    if not tickers or 'data' not in tickers:
        log("MEXC API FAILED", 'ERR')
        return []

    candidates = []
    for t in tickers['data']:
        try:
            sym = t['symbol']
            price = float(t.get('lastPrice', 0))
            change = float(t.get('riseFallRate', 0)) * 100
            vol = float(t.get('volume24', 0))
            high24 = float(t.get('high24Price', 0))
            low24 = float(t.get('low24Price', 0))
            funding = float(t.get('fundingRate', 0))

            if price <= 0 or vol < 2_000_000 or abs(change) < 2.0:
                continue
            denom = high24 - low24
            range_pos = (price - low24) / denom if denom > 0 else 0.5

            candidates.append({
                'symbol': sym, 'price': price, 'change': change,
                'vol': vol, 'high24': high24, 'low24': low24,
                'range_pos': range_pos, 'funding': funding
            })
        except:
            continue

    candidates.sort(key=lambda x: abs(x['change']) * min(x['vol']/1e6, 10), reverse=True)
    candidates = candidates[:TOP_COINS]

    # Enrichir avec indicateurs 1H
    for c in candidates:
        kl = fetch_json(f"https://contract.mexc.com/api/v1/contract/kline/{c['symbol']}?interval=Min60&limit=50")
        if kl and kl.get('data') and len(kl['data'].get('close', [])) >= 20:
            closes = [float(x) for x in kl['data']['close']]
            volumes = [float(x) for x in kl['data']['vol']]
            c['rsi'] = calc_rsi(closes)
            c['bb_width'] = calc_bb_width(closes)
            c['vol_ratio'] = calc_vol_ratio(volumes)
        else:
            c['rsi'] = 50
            c['bb_width'] = 999
            c['vol_ratio'] = 1
        time.sleep(0.2)

        # Orderbook
        ob = fetch_json(f"https://contract.mexc.com/api/v1/contract/depth/{c['symbol']}?limit=20")
        if ob and ob.get('data'):
            bids = sum(float(b[1]) for b in ob['data'].get('bids', [])[:10])
            asks = sum(float(a[1]) for a in ob['data'].get('asks', [])[:10])
            c['buy_pct'] = bids / (bids + asks) * 100 if (bids + asks) > 0 else 50
            c['ob_ratio'] = bids / asks if asks > 0 else 1
        else:
            c['buy_pct'] = 50
            c['ob_ratio'] = 1

    log(f"  {len(candidates)} coins scannes | Top: {', '.join(c['symbol']+'('+str(round(c['change'],1))+'%)' for c in candidates[:3])}")
    return candidates

# ============================================================
# STAGE 2: DISPATCH PARALLELE (M1 + M2 + M3)
# ============================================================
SYSTEM_PROMPTS = {
    'M1_STRATEGY': (
        "Tu es un STRATEGE de marche. Analyse la structure de marche et le sentiment.\n"
        "Reponds UNIQUEMENT: DIRECTION(LONG/SHORT/WAIT) CONFIDENCE(0-100) RAISON(1 phrase)"
    ),
    'M2_TECHNICAL': (
        "Tu es un ANALYSTE TECHNIQUE. Evalue les indicateurs et le rapport risque/gain.\n"
        "Reponds UNIQUEMENT: DIRECTION(LONG/SHORT/WAIT) SCORE(0-100) RAISON(1 phrase)"
    ),
    'M3_RISK': (
        "Tu es un RISK MANAGER pessimiste. Cherche les raisons de NE PAS trader.\n"
        "Si RSI>70 ou coin deja pumpe >5%, le risque est ELEVE.\n"
        "Reponds UNIQUEMENT: RISQUE(LOW/MEDIUM/HIGH) SCORE(0-100) RAISON(1 phrase)"
    )
}

def _call_model(url, model, messages, timeout):
    """Appel bas-niveau a un modele LM Studio"""
    result = post_json(url, {
        'model': model,
        'messages': messages,
        'max_tokens': 200,
        'temperature': 0.65
    }, timeout=timeout)
    if 'error' in result and 'choices' not in result:
        return None, str(result['error'])[:80]
    try:
        content = result['choices'][0]['message'].get('content', '')
        if not content or not content.strip():
            content = result['choices'][0]['message'].get('reasoning', '')
        return content.strip() if content else None, None
    except:
        return None, 'parse_error'

def query_node(node_name, prompt):
    node = CLUSTER['nodes'][node_name]
    url = f"http://{node['ip']}:{node['port']}/v1/chat/completions"
    model = node['model_key']
    fallback = node.get('fallback_key')

    messages = [{"role": "user", "content": prompt}]
    if model not in NO_SYSTEM:
        messages.insert(0, {"role": "system", "content": SYSTEM_PROMPTS.get(node_name, "Analyse trading.")})

    t0 = time.time()
    content, err = _call_model(url, model, messages, node['timeout'])
    elapsed = time.time() - t0

    if content:
        return {'node': node_name, 'ok': True, 'content': content, 'time': elapsed, 'model': model}

    # Retry avec fallback si disponible
    if fallback and fallback != model:
        log(f"    {node_name}: {model} FAIL ({err}), retry {fallback}...", 'WARN')
        fb_msgs = [{"role": "user", "content": prompt}]
        if fallback not in NO_SYSTEM:
            fb_msgs.insert(0, {"role": "system", "content": SYSTEM_PROMPTS.get(node_name, "Analyse trading.")})
        t1 = time.time()
        content2, err2 = _call_model(url, fallback, fb_msgs, node['timeout'])
        elapsed2 = time.time() - t0
        if content2:
            return {'node': node_name, 'ok': True, 'content': content2, 'time': elapsed2, 'model': fallback}
        return {'node': node_name, 'ok': False, 'error': f"{err} + fallback:{err2}", 'time': elapsed2}

    return {'node': node_name, 'ok': False, 'error': err or 'empty', 'time': elapsed}

# Track M1 failures to auto-skip after N consecutive fails
M1_FAIL_COUNT = 0
M1_SKIP_AFTER = 2  # Skip M1 after 2 consecutive failures

def dispatch_agents(coin):
    """Envoie M2/M3 (+ M1 si actif) en parallele pour un coin"""
    global M1_FAIL_COUNT
    sym = coin['symbol']
    ctx = (
        f"{sym} a {coin['price']} USDT. Change 24h: {coin['change']:+.1f}%, "
        f"RSI 1H: {coin['rsi']:.0f}, BB Width: {coin['bb_width']:.1f}%, "
        f"Volume: {coin['vol']/1e6:.1f}M (ratio x{coin['vol_ratio']:.1f}), "
        f"Orderbook buy: {coin['buy_pct']:.0f}% (ratio {coin['ob_ratio']:.1f}x), "
        f"Range pos: {coin['range_pos']:.2f}, Funding: {coin['funding']:.4f}"
    )

    prompts = {
        'M2_TECHNICAL': f"Analyse TECHNIQUE pour {ctx}. RSI, BB, volume, divergences. Score 0-100.",
        'M3_RISK': f"Analyse RISQUE pour {ctx}. Trouve les raisons de NE PAS trader. Risque LOW/MEDIUM/HIGH."
    }
    # Include M1 only if it hasn't failed too many times
    if M1_FAIL_COUNT < M1_SKIP_AFTER:
        prompts['M1_STRATEGY'] = f"Analyse STRATEGIE pour {ctx}. Market structure, sentiment, momentum. LONG, SHORT ou WAIT?"
    else:
        log(f"    M1_STRATEGY: SKIP (>{M1_SKIP_AFTER} echecs consecutifs)", 'WARN')

    results = {}
    workers = len(prompts)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(query_node, node, prompts[node]): node for node in prompts}
        try:
            for future in as_completed(futures, timeout=100):
                node = futures[future]
                try:
                    data = future.result()
                    results[node] = data
                    if data['ok']:
                        model_used = data.get('model', '?')
                        log(f"    {node}: {data['time']:.1f}s ({model_used})", 'OK')
                        if node == 'M1_STRATEGY':
                            M1_FAIL_COUNT = 0  # Reset on success
                    else:
                        log(f"    {node}: FAIL ({data.get('error','')})", 'ERR')
                        if node == 'M1_STRATEGY':
                            M1_FAIL_COUNT += 1
                except Exception:
                    results[node] = {'node': node, 'ok': False, 'error': 'future_error'}
                    if node == 'M1_STRATEGY':
                        M1_FAIL_COUNT += 1
        except TimeoutError:
            for f, node in futures.items():
                if node not in results:
                    results[node] = {'node': node, 'ok': False, 'error': 'global_timeout'}
                    log(f"    {node}: GLOBAL TIMEOUT", 'ERR')
                    if node == 'M1_STRATEGY':
                        M1_FAIL_COUNT += 1

    return results

# ============================================================
# STAGE 3: SYNTHESE GEMINI (Le Juge)
# ============================================================
def gemini_judge(coin, agent_results):
    """Gemini recoit les 3 rapports et tranche GO/NO-GO"""
    m1 = agent_results.get('M1_STRATEGY', {}).get('content', 'N/A')
    m2 = agent_results.get('M2_TECHNICAL', {}).get('content', 'N/A')
    m3 = agent_results.get('M3_RISK', {}).get('content', 'N/A')

    prompt = (
        f"DECIDE GO/NO-GO pour {coin['symbol']} a {coin['price']} (change {coin['change']:+.1f}%).\n\n"
        f"RAPPORT STRATEGE (M1): {m1}\n"
        f"RAPPORT TECHNIQUE (M2): {m2}\n"
        f"RAPPORT RISQUE (M3): {m3}\n\n"
        f"Reponds UNIQUEMENT sur une ligne: DECISION(LONG/SHORT/WAIT) CONFIDENCE(0-100) RAISON"
    )

    gemini_cmd = CLUSTER['cloud']['path']
    try:
        t0 = time.time()
        proc = subprocess.run(
            [gemini_cmd],
            input=prompt,
            capture_output=True, text=True, timeout=30,
            encoding='utf-8'
        )
        elapsed = time.time() - t0
        output = proc.stdout.strip() if proc.stdout else proc.stderr.strip()
        log(f"    GEMINI: {elapsed:.1f}s", 'OK')
        return output, elapsed
    except Exception as e:
        log(f"    GEMINI: FAIL ({e})", 'ERR')
        return None, 0

def parse_decision(text):
    """Parse DIRECTION CONFIDENCE from any response"""
    if not text:
        return 'WAIT', 0
    text = text.upper()
    direction = 'WAIT'
    confidence = 50
    if 'LONG' in text:
        direction = 'LONG'
    elif 'SHORT' in text:
        direction = 'SHORT'
    import re
    m = re.search(r'(\d{1,3})', text)
    if m:
        n = int(m.group(1))
        if 0 <= n <= 100:
            confidence = n
    return direction, confidence

# ============================================================
# STAGE 4: SAVE DB + TELEGRAM
# ============================================================
def save_signal(coin, decision, confidence, m1_resp, m2_resp, m3_resp, gemini_resp):
    try:
        db = sqlite3.connect(DB_PATH)
        db.execute("""INSERT INTO predictions
            (created_at, symbol, direction, confidence, entry_price, score,
             models_used, model_votes, result)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')""",
            (datetime.now().isoformat(), coin['symbol'], decision, confidence,
             coin['price'], int(confidence * 0.6 + coin.get('rsi', 50) * 0.4),
             'M1+M2+M3+Gemini',
             json.dumps({
                 'M1_STRATEGY': m1_resp[:200] if m1_resp else 'N/A',
                 'M2_TECHNICAL': m2_resp[:200] if m2_resp else 'N/A',
                 'M3_RISK': m3_resp[:200] if m3_resp else 'N/A',
                 'GEMINI': gemini_resp[:200] if gemini_resp else 'N/A'
             })))
        db.commit()
        db.close()
        return True
    except Exception as e:
        log(f"  DB ERROR: {e}", 'ERR')
        return False

# ============================================================
# MAIN HYPER-CYCLE
# ============================================================
def run_hyper_cycle(cycle_num):
    log(f"{'='*65}")
    log(f"  HYPER-SCAN V2 - CYCLE #{cycle_num} - GRID COMPUTING", 'CYCLE')
    log(f"  M1(Stratege) + M2(Technicien) + M3(Contrarian) + Gemini(Juge)")
    log(f"{'='*65}")

    # STAGE 1: Scan MEXC
    coins = scan_mexc()
    if not coins:
        log("Aucun candidat", 'WARN')
        return 0

    signals = []

    for i, coin in enumerate(coins):
        sym = coin['symbol']
        log(f"\n  [{i+1}/{len(coins)}] {sym} @ {coin['price']} ({coin['change']:+.1f}%)", 'CYCLE')
        log(f"    RSI={coin['rsi']:.0f} BB={coin['bb_width']:.1f}% OB_buy={coin['buy_pct']:.0f}%")

        # STAGE 2: Dispatch 3 agents en parallele
        agent_results = dispatch_agents(coin)
        active = sum(1 for r in agent_results.values() if r.get('ok'))

        if active < 2:
            log(f"    SKIP: seulement {active} noeuds actifs", 'WARN')
            continue

        # STAGE 3: Gemini juge
        gemini_resp, g_time = gemini_judge(coin, agent_results)
        decision, confidence = parse_decision(gemini_resp)

        # Filtre: WAIT ou confidence < 65% = skip
        if decision == 'WAIT' or confidence < 65:
            log(f"    -> {decision} {confidence}% (SKIP)", 'WARN')
            continue

        log(f"    -> VERDICT: {decision} {confidence}%", 'OK')

        # STAGE 4: Save
        m1_c = agent_results.get('M1_STRATEGY', {}).get('content', '')
        m2_c = agent_results.get('M2_TECHNICAL', {}).get('content', '')
        m3_c = agent_results.get('M3_RISK', {}).get('content', '')
        save_signal(coin, decision, confidence, m1_c, m2_c, m3_c, gemini_resp)

        signals.append({
            'symbol': sym, 'direction': decision, 'confidence': confidence,
            'price': coin['price'], 'change': coin['change'], 'rsi': coin['rsi']
        })

    # Telegram
    if signals:
        lines = [f"HYPER-SCAN V2 - Cycle #{cycle_num}\n"]
        for s in signals:
            lines.append(f"{s['symbol']} {s['direction']} {s['confidence']}%")
            lines.append(f"  Price: {s['price']} | Chg: {s['change']:+.1f}% | RSI: {s['rsi']:.0f}")
        lines.append(f"\n{len(signals)} signaux | {active} nodes actifs")
        send_telegram('\n'.join(lines))

    log(f"\n  Cycle #{cycle_num}: {len(signals)} signaux emis")
    return len(signals)

# ============================================================
# MAIN
# ============================================================
if __name__ == '__main__':
    log(f"HYPER-SCAN V2 DEMARRE - {MAX_CYCLES} cycles, {CYCLE_DELAY}s interval")
    send_telegram(f"HYPER-SCAN V2 DEMARRE\nCycles: {MAX_CYCLES}\nNodes: M1+M2+M3+Gemini")

    total_signals = 0
    start = time.time()

    for cycle in range(1, MAX_CYCLES + 1):
        t0 = time.time()
        n = run_hyper_cycle(cycle)
        total_signals += n
        elapsed = time.time() - t0

        log(f"  Runtime: {(time.time()-start)/60:.0f}min | Total signals: {total_signals}")

        if cycle < MAX_CYCLES:
            wait = max(10, CYCLE_DELAY - elapsed)
            log(f"  Prochain cycle dans {wait:.0f}s...")
            time.sleep(wait)

    runtime = (time.time() - start) / 60
    report = f"HYPER-SCAN V2 TERMINE\nCycles: {MAX_CYCLES} | Runtime: {runtime:.1f}min\nSignals: {total_signals}"
    log(report)
    send_telegram(report)
