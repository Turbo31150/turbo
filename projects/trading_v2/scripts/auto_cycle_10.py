#!/usr/bin/env python3
"""Pipeline Intensif V2 - 10 Cycles + Full Cluster IA (M1+M2+M3+Gemini)
   CQ Pipeline v3.2: SHORT x1.5, LONG x0.4, confidence >= 80%
"""
import urllib.request, json, sys, time, datetime, sqlite3, subprocess, re
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout.reconfigure(encoding='utf-8')
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

# === CONFIG ===
TOKEN = '8369376863:AAF-7YGDbun8mXWwqYJFj-eX6P78DeIu9Aw'
CHAT = '2010747443'
DB = 'F:/BUREAU/TRADING_V2_PRODUCTION/database/trading.db'

# LM Studio Cluster
LM_SERVERS = {
    'M1': {'url': 'http://192.168.1.85:1234', 'model': 'openai/gpt-oss-20b', 'role': 'Deep'},
    'M2': {'url': 'http://192.168.1.26:1234', 'model': 'openai/gpt-oss-20b', 'role': 'Fast'},
    'M3': {'url': 'http://192.168.1.113:1234', 'model': 'mistral-7b-instruct-v0.3', 'role': 'Validate'},
}
# Models that don't support system prompts
NO_SYSTEM_MODELS = ['mistral-7b', 'phi-3.1-mini']
GEMINI_CLI = r'/home/turbo\AppData\Roaming\npm\gemini.cmd'
LM_TIMEOUT = 60
GEMINI_TIMEOUT = 25

# V3.2 Patch
SHORT_BOOST = 1.5
LONG_PENALTY = 0.4
CONFIDENCE_MIN = 80


# === IA FUNCTIONS ===

def ask_lmstudio(server_key, prompt, timeout=LM_TIMEOUT):
    """Query a specific LM Studio server"""
    srv = LM_SERVERS[server_key]
    url = f"{srv['url']}/v1/chat/completions"

    has_no_system = any(ns in srv['model'] for ns in NO_SYSTEM_MODELS)

    if has_no_system:
        messages = [{"role": "user", "content": prompt}]
    else:
        messages = [
            {"role": "system", "content": "Tu es un analyste trading crypto. Reponds UNIQUEMENT en JSON: {\"direction\": \"LONG|SHORT|NEUTRAL\", \"confidence\": 0-100, \"reason\": \"...\"}. Sois objectif, pas de biais."},
            {"role": "user", "content": prompt}
        ]

    body = json.dumps({
        "model": srv['model'],
        "messages": messages,
        "temperature": 0.65,
        "max_tokens": 200
    }).encode('utf-8')

    req = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'})
    try:
        t0 = time.time()
        resp = urllib.request.urlopen(req, timeout=timeout)
        data = json.loads(resp.read())
        msg = data['choices'][0]['message']
        content = msg.get('content', '') or ''

        # GPT-OSS fallback: response in reasoning_content or reasoning if content empty
        if not content.strip():
            content = msg.get('reasoning_content', '') or msg.get('reasoning', '') or ''

        # Last resort: stringify the whole message
        if not content.strip():
            content = json.dumps(msg)

        elapsed = round(time.time() - t0, 1)
        return {'server': server_key, 'response': content, 'time': elapsed, 'ok': bool(content.strip())}
    except Exception as e:
        elapsed = round(time.time() - t0, 1) if 't0' in dir() else 0
        return {'server': server_key, 'response': f'ERROR:{e}', 'time': elapsed, 'ok': False}


def ask_gemini(prompt, timeout=GEMINI_TIMEOUT):
    """Query Gemini via CLI with stdin pipe (OAuth, no API key needed)"""
    try:
        t0 = time.time()
        proc = subprocess.run(
            [GEMINI_CLI],
            input=prompt, capture_output=True, text=True,
            timeout=timeout, encoding='utf-8'
        )
        elapsed = round(time.time() - t0, 1)
        output = proc.stdout.strip() if proc.stdout else proc.stderr.strip()
        return {'server': 'GEMINI', 'response': output, 'time': elapsed, 'ok': bool(output)}
    except subprocess.TimeoutExpired:
        return {'server': 'GEMINI', 'response': 'TIMEOUT', 'time': timeout, 'ok': False}
    except Exception as e:
        return {'server': 'GEMINI', 'response': str(e), 'time': 0, 'ok': False}


def parse_ia_response(raw):
    """Extract direction + confidence from IA response - robust multi-strategy parser"""
    if not raw or not isinstance(raw, str):
        return 'NEUTRAL', 50

    # Clean thinking tags (qwen3 /think blocks)
    clean = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
    if not clean:
        clean = raw

    # Strategy 1: JSON extraction (try all JSON objects in response)
    json_matches = re.findall(r'\{[^{}]+\}', clean)
    for jm in json_matches:
        try:
            obj = json.loads(jm)
            d = str(obj.get('direction', obj.get('dir', obj.get('signal', '')))).upper()
            c = obj.get('confidence', obj.get('conf', obj.get('score', 50)))
            c = int(float(c))
            # Normalize
            d = d.replace('BUY', 'LONG').replace('SELL', 'SHORT').replace('HOLD', 'NEUTRAL')
            if d in ('LONG', 'SHORT', 'NEUTRAL'):
                return d, max(0, min(100, c))
        except:
            continue

    # Strategy 2: keyword detection in full text
    text = clean.upper()
    text = text.replace('BUY', 'LONG').replace('SELL', 'SHORT').replace('BEARISH', 'SHORT').replace('BULLISH', 'LONG')

    direction = 'NEUTRAL'
    # Count occurrences
    long_count = text.count('LONG')
    short_count = text.count('SHORT')
    if short_count > long_count:
        direction = 'SHORT'
    elif long_count > short_count:
        direction = 'LONG'

    # Extract confidence - multiple patterns
    confidence = 60 if direction != 'NEUTRAL' else 40
    patterns = [
        r'(?:confiance|confidence|conf)[:\s]*(\d+)',
        r'(\d{2,3})\s*[%％]',
        r'(?:score|rating)[:\s]*(\d+)',
        r'"confidence"\s*:\s*(\d+)',
    ]
    for pat in patterns:
        m = re.search(pat, clean, re.IGNORECASE)
        if m:
            val = int(m.group(1))
            if 0 <= val <= 100:
                confidence = val
                break

    return direction, max(0, min(100, confidence))


def consensus_cluster(symbol_data):
    """Full cluster consensus: M1+M2+M3+Gemini in parallel, V3.2 weights"""

    prompt = (
        f"Analyse trading crypto {symbol_data['sym']} (MEXC Futures):\n"
        f"- Prix: {symbol_data['price']} | Change 24h: {symbol_data['ch']}%\n"
        f"- Range position: {symbol_data['rp']} (0=low24, 1=high24)\n"
        f"- RSI14: {symbol_data.get('rsi', 'N/A')} | BB width: {symbol_data.get('bb_w', 'N/A')}%\n"
        f"- Orderbook ratio: {symbol_data.get('ob', 'N/A')}x (>1=acheteurs)\n"
        f"- Volume 24h: {symbol_data['vol']:.0f} | Funding: {symbol_data['fund']}\n"
        f"- Type signal: {symbol_data['type']} | Score brut: {symbol_data['score']}\n"
        f"- Chaikin MFV: {'POSITIF (danger)' if symbol_data.get('mfv', 0) > 0 else 'NEGATIF (bottom)'}\n\n"
        f"Direction LONG, SHORT ou NEUTRAL? Reponds en JSON: "
        f'{{\"direction\": \"LONG|SHORT|NEUTRAL\", \"confidence\": 0-100, \"reason\": \"...\"}}'
    )

    votes = []
    results = {}

    # Parallel queries: M1 + M2 + M3 + Gemini
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(ask_lmstudio, 'M1', prompt): 'M1',
            pool.submit(ask_lmstudio, 'M2', prompt): 'M2',
            pool.submit(ask_lmstudio, 'M3', prompt): 'M3',
            pool.submit(ask_gemini, prompt): 'GEMINI',
        }
        for fut in as_completed(futures):
            key = futures[fut]
            try:
                res = fut.result()
                results[key] = res
                if res['ok']:
                    direction, confidence = parse_ia_response(res['response'])
                    votes.append({
                        'server': key, 'direction': direction,
                        'confidence': confidence, 'time': res['time']
                    })
                else:
                    votes.append({
                        'server': key, 'direction': 'NEUTRAL',
                        'confidence': 0, 'time': res['time']
                    })
            except Exception as e:
                votes.append({
                    'server': key, 'direction': 'NEUTRAL',
                    'confidence': 0, 'time': 0
                })

    if not votes:
        return 'NEUTRAL', 0, [], {}

    # Count votes
    dir_counts = {'LONG': 0, 'SHORT': 0, 'NEUTRAL': 0}
    dir_conf = {'LONG': [], 'SHORT': [], 'NEUTRAL': []}
    for v in votes:
        d = v['direction']
        dir_counts[d] = dir_counts.get(d, 0) + 1
        dir_conf[d].append(v['confidence'])

    # Consensus direction = majority
    consensus_dir = max(dir_counts, key=dir_counts.get)

    # Average confidence for consensus direction
    confs = dir_conf.get(consensus_dir, [50])
    avg_conf = sum(confs) / len(confs) if confs else 50

    # V3.2 PATCH: Direction weighting
    if consensus_dir == 'SHORT':
        avg_conf = min(99, avg_conf * SHORT_BOOST)
    elif consensus_dir == 'LONG':
        avg_conf = avg_conf * LONG_PENALTY

    avg_conf = round(avg_conf, 1)

    return consensus_dir, avg_conf, votes, results


# === CORE FUNCTIONS ===

def send_tg(msg):
    try:
        body = json.dumps({'chat_id': CHAT, 'text': msg}).encode()
        req = urllib.request.Request(
            f'https://api.telegram.org/bot{TOKEN}/sendMessage',
            data=body, headers={'Content-Type': 'application/json'})
        resp = urllib.request.urlopen(req, timeout=10)
        d = json.loads(resp.read())
        return d.get('result', {}).get('message_id', '?')
    except Exception as e:
        print(f'  TG ERROR: {e}')
        return 'FAIL'


def save_db(signals):
    try:
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        for s in signals:
            c.execute(
                'INSERT INTO predictions (created_at,symbol,direction,confidence,entry_price,tp1,tp2,sl,score,models_used,model_votes) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                (now, s['sym'], s['dir'], s['conf'], s['entry'], s['tp1'], s['tp2'], s['sl'], s['score'],
                 s.get('models_used', 'auto-cycle'), json.dumps(s.get('votes', {}))))
            c.execute(
                'INSERT INTO signals (symbol,direction,price,score,reasons,tp1,tp2,sl,source) VALUES (?,?,?,?,?,?,?,?,?)',
                (s['sym'], s['dir'], s['entry'], s['score'], s['reason'], s['tp1'], s['tp2'], s['sl'],
                 'cluster-v3.2'))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f'  DB ERROR: {e}')
        return False


def save_consensus_db(symbol, votes, consensus_dir, confidence):
    """Save individual model responses to consensus_responses table"""
    try:
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        # Get next query_id
        c.execute('SELECT COALESCE(MAX(query_id), 0) + 1 FROM consensus_responses')
        qid = c.fetchone()[0]
        for v in votes:
            srv_name = v['server']
            model = LM_SERVERS.get(srv_name, {}).get('model', 'gemini-cli')
            c.execute(
                'INSERT INTO consensus_responses (query_id, server_name, server_id, model, response, latency_ms, success, detected_signal, confidence_score) VALUES (?,?,?,?,?,?,?,?,?)',
                (qid, srv_name, srv_name, model,
                 json.dumps({'direction': v['direction'], 'confidence': v['confidence']}),
                 int(v['time'] * 1000), 1 if v['confidence'] > 0 else 0,
                 v['direction'], v['confidence']))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f'  CONSENSUS DB ERROR: {e}')


def scan_cycle(cycle_num):
    t0 = time.time()
    now = datetime.datetime.now().strftime('%H:%M:%S')
    print(f'\n{"="*80}')
    print(f'  CYCLE {cycle_num}/10 - {now} | CLUSTER: M1+M2+M3+GEMINI | V3.2')
    print(f'{"="*80}')

    # 1. FETCH TICKERS
    try:
        req = urllib.request.urlopen('https://contract.mexc.com/api/v1/contract/ticker', timeout=15)
        tickers = json.loads(req.read())['data']
    except Exception as e:
        print(f'  TICKER ERROR: {e}')
        return []

    # 2. SCORE
    scored = []
    for t in tickers:
        sym = t['symbol']
        price = float(t['lastPrice'])
        ch = float(t['riseFallRate']) * 100
        vol = float(t['volume24'])
        high = float(t['high24Price'])
        low = float(t['lower24Price'])
        rng = high - low if high > low else 0.0001
        rp = (price - low) / rng if rng > 0 else 0.5
        fund = float(t.get('fundingRate', 0))
        hold = float(t.get('holdVol', 0))

        score = 0
        stype = ''
        if rp > 0.85 and ch > 5 and vol > 5e5:
            score = rp * 55 + ch * 3.5 + min(vol / 1e6, 25) + (8 if hold > 5e7 else 0)
            stype = 'BRK-A'
        elif rp > 0.80 and ch > 2 and vol > 2e5:
            score = rp * 48 + ch * 3 + min(vol / 1e6, 20) + (5 if hold > 1e7 else 0)
            stype = 'BRK-B'
        elif rp > 0.90 and ch > 1:
            score = rp * 45 + ch * 2.5 + min(vol / 1e6, 15)
            stype = 'BRK-C'
        elif rp < 0.10 and vol > 5e6:
            score = (1 - rp) * 50 + abs(ch) * 2 + min(vol / 1e6, 25) + (8 if fund < -0.001 else 0)
            stype = 'REV-A'
        elif rp < 0.20 and ch < -5 and vol > 1e6:
            score = (1 - rp) * 42 + abs(ch) * 1.8 + min(vol / 1e6, 20)
            stype = 'REV-B'
        elif rp < 0.15 and vol > 2e6:
            score = (1 - rp) * 40 + abs(ch) * 1.5 + min(vol / 1e6, 18)
            stype = 'REV-C'

        if score > 30:
            scored.append({
                'sym': sym, 'price': price, 'ch': round(ch, 2), 'vol': vol,
                'rp': round(rp, 4), 'score': round(score, 1), 'fund': round(fund, 6),
                'hold': hold, 'type': stype
            })

    scored.sort(key=lambda x: x['score'], reverse=True)
    top8 = scored[:8]
    print(f'  {len(scored)} signaux bruts / {len(tickers)} pairs | Top 8 → klines+OB')

    # 3. KLINES + ORDERBOOK for top 8
    finals = []
    for s in top8:
        sym = s['sym']
        try:
            kurl = f'https://contract.mexc.com/api/v1/contract/kline/{sym}?interval=Min15&limit=20'
            kd = json.loads(urllib.request.urlopen(kurl, timeout=8).read())
            closes = kd['data']['close']
            highs = kd['data']['high']
            lows = kd['data']['low']
            vols = kd['data']['vol']

            deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
            ag = sum(max(0, x) for x in deltas[-14:]) / 14
            al = sum(max(0, -x) for x in deltas[-14:]) / 14
            rsi = 100 - (100 / (1 + ag / al)) if al > 0 else 100

            n = min(15, len(closes))
            sma = sum(closes[-n:]) / n
            std = (sum((x - sma) ** 2 for x in closes[-n:]) / n) ** 0.5
            bb_w = round((4 * std) / sma * 100, 2)

            mfv = 0
            for j in range(-min(5, n), 0):
                hl = highs[j] - lows[j]
                if hl > 0:
                    mfv += ((closes[j] - lows[j]) - (highs[j] - closes[j])) / hl * vols[j]

            # Orderbook
            try:
                od = json.loads(urllib.request.urlopen(
                    f'https://contract.mexc.com/api/v1/contract/depth/{sym}?limit=20', timeout=5).read())
                bv = sum(float(b[1]) for b in od['data']['bids'][:10])
                av = sum(float(a[1]) for a in od['data']['asks'][:10])
                ob = round(bv / av, 2) if av > 0 else 0
            except:
                ob = -1

            s['rsi'] = round(rsi, 1)
            s['ob'] = ob
            s['bb_w'] = bb_w
            s['mfv'] = mfv

            tag = 'SCAN'
            warns = []
            if rsi > 72:
                warns.append('OB')
            if ob > 1.3 and ob >= 0:
                warns.append(f'BUY({ob:.1f}x)')
            if ob < 0.7 and ob >= 0:
                warns.append(f'SELL({ob:.1f}x)')
            if mfv < 0:
                warns.append('CHK-BUY')
            if rsi < 35 and s['type'].startswith('REV'):
                warns.append('OVERSOLD')
            s['warns'] = warns

            print(f'  {sym:18} Sc:{s["score"]:5.1f} RSI:{rsi:5.1f} OB:{ob:4.2f}x BB:{bb_w:4.1f}% {" ".join(warns):20} {tag}')
            finals.append(s)
        except Exception as e:
            print(f'  {sym:18} ERROR: {e}')

    if not finals:
        print('  >> Aucun candidat ce cycle')
        return []

    # 4. CLUSTER IA CONSENSUS for top 5
    top5 = finals[:5]
    print(f'\n  --- CLUSTER IA CONSENSUS (M1+M2+M3+GEMINI) ---')
    ia_signals = []

    for s in top5:
        sym = s['sym']
        print(f'  {sym:18} querying 4 IAs...', end='', flush=True)
        consensus_dir, confidence, votes, raw_results = consensus_cluster(s)

        # V3.2 tag
        v32_tag = ''
        if consensus_dir == 'SHORT':
            v32_tag = f'[SHORTx{SHORT_BOOST}]'
        elif consensus_dir == 'LONG':
            v32_tag = f'[LONGx{LONG_PENALTY}]'

        # Vote summary
        vote_str = ' '.join(f'{v["server"]}={v["direction"][0]}({v["confidence"]}%)' for v in votes)
        times_str = '/'.join(f'{v["time"]:.0f}s' for v in votes)

        verdict = 'GO' if confidence >= CONFIDENCE_MIN and consensus_dir != 'NEUTRAL' else 'SKIP'
        print(f' {consensus_dir} {confidence:.0f}% {v32_tag} | {vote_str} | {times_str} | {verdict}')

        # Save consensus to DB
        save_consensus_db(sym, votes, consensus_dir, confidence)

        if verdict == 'GO':
            s['ia_dir'] = consensus_dir
            s['ia_conf'] = confidence
            s['ia_votes'] = votes
            ia_signals.append(s)

    if not ia_signals:
        print('  >> Aucun signal GO apres consensus IA (threshold >= 80%)')
        return []

    # 5. Build signals for DB + Telegram
    db_signals = []
    for s in ia_signals:
        d = s['ia_dir']
        if d == 'LONG':
            if s['type'].startswith('BRK'):
                tp1 = round(s['price'] * 1.03, 8)
                tp2 = round(s['price'] * 1.055, 8)
                sl = round(s['price'] * 0.988, 8)
            else:
                tp1 = round(s['price'] * 1.025, 8)
                tp2 = round(s['price'] * 1.05, 8)
                sl = round(s['price'] * 0.975, 8)
        else:  # SHORT
            if s['type'].startswith('BRK'):
                tp1 = round(s['price'] * 0.97, 8)
                tp2 = round(s['price'] * 0.945, 8)
                sl = round(s['price'] * 1.012, 8)
            else:
                tp1 = round(s['price'] * 0.975, 8)
                tp2 = round(s['price'] * 0.95, 8)
                sl = round(s['price'] * 1.025, 8)

        models_str = ','.join(v['server'] for v in s['ia_votes'] if v['confidence'] > 0)
        vote_json = {v['server']: {'dir': v['direction'], 'conf': v['confidence'], 'time': v['time']} for v in s['ia_votes']}

        reason = (f"CQ={s['ia_conf']:.0f}% {d} | Sc={s['score']} RSI={s['rsi']} OB={s['ob']}x "
                  f"BB={s.get('bb_w', '?')}% {s['type']} | {models_str}")
        db_signals.append({
            'sym': s['sym'], 'dir': d, 'conf': s['ia_conf'],
            'entry': s['price'], 'tp1': tp1, 'tp2': tp2, 'sl': sl,
            'score': s['score'], 'reason': reason,
            'models_used': f'cluster-v3.2:{models_str}',
            'votes': vote_json
        })

    # 6. Telegram
    tg_lines = [f'CYCLE {cycle_num}/10 - {now} [CLUSTER V3.2]', '']
    for i, sig in enumerate(db_signals):
        tg_lines.append(
            f'#{i+1} {sig["sym"]} {sig["dir"]} {sig["conf"]:.0f}%')
        tg_lines.append(
            f'   Entry:{sig["entry"]} TP1:{sig["tp1"]} SL:{sig["sl"]} Sc:{sig["score"]}')
    tg_lines.append(f'\nGO: {len(db_signals)} | Scan: {len(scored)} | {round(time.time()-t0,1)}s')
    mid = send_tg('\n'.join(tg_lines))

    # 7. DB
    save_db(db_signals)

    elapsed = round(time.time() - t0, 1)
    print(f'\n  >> {len(db_signals)} signaux GO | TG#{mid} | DB saved | {elapsed}s')
    print(f'  TOP: {" / ".join(f"{s["sym"]} {s["dir"]} {s["conf"]:.0f}%" for s in db_signals)}')
    return db_signals


# ========== MAIN ==========
if __name__ == '__main__':
    print('PIPELINE INTENSIF V2 - FULL CLUSTER (M1+M2+M3+GEMINI)')
    print(f'Pipeline CQ v3.2 | SHORT x{SHORT_BOOST} | LONG x{LONG_PENALTY} | Conf >= {CONFIDENCE_MIN}%')
    print(f'Debut: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'Servers: {" | ".join(f"{k}={v["url"]}" for k,v in LM_SERVERS.items())} | GEMINI=CLI')
    send_tg(f'PIPELINE V2 CLUSTER DEMARRE - M1+M2+M3+GEMINI - {datetime.datetime.now().strftime("%H:%M:%S")}')

    all_signals = {}
    for cycle in range(1, 11):
        try:
            top = scan_cycle(cycle)
            for s in top:
                sym = s['sym']
                if sym not in all_signals:
                    all_signals[sym] = {'count': 0, 'dirs': []}
                all_signals[sym]['count'] += 1
                all_signals[sym]['dirs'].append(s['dir'])
        except Exception as e:
            print(f'  CYCLE {cycle} ERROR: {e}')

        if cycle < 10:
            wait = 90  # 90s entre cycles (temps pour cluster IA)
            print(f'  Attente {wait}s avant cycle {cycle+1}...')
            time.sleep(wait)

    # FINAL SUMMARY
    print(f'\n{"="*80}')
    print('  RESUME 10 CYCLES - CLUSTER V3.2')
    print(f'{"="*80}')
    ranking = sorted(all_signals.items(), key=lambda x: x[1]['count'], reverse=True)
    summary_lines = ['RESUME 10 CYCLES - CLUSTER V3.2', '']
    for sym, data in ranking:
        dirs = '/'.join(data['dirs'])
        bar = '#' * data['count']
        line = f'{sym:18} {bar} ({data["count"]}/10) [{dirs}]'
        print(f'  {line}')
        summary_lines.append(line)
    summary_lines.append(f'\nFin: {datetime.datetime.now().strftime("%H:%M:%S")}')
    send_tg('\n'.join(summary_lines))

    # Save summary
    try:
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        summary_data = {sym: {'count': d['count'], 'dirs': d['dirs']} for sym, d in ranking}
        c.execute(
            'INSERT INTO predictions (created_at,symbol,direction,confidence,entry_price,score,models_used,model_votes) VALUES (?,?,?,?,?,?,?,?)',
            (now, 'SUMMARY_10CYCLES', 'INFO', 0, 0, 0, 'cluster-v3.2', json.dumps(summary_data)))
        conn.commit()
        conn.close()
    except:
        pass

    print(f'\nPIPELINE V2 CLUSTER TERMINE - {datetime.datetime.now().strftime("%H:%M:%S")}')
