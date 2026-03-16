#!/usr/bin/env python3
"""SNIPER BREAKOUT 10 CYCLES - Focus ROSE + Top Breakouts"""
import urllib.request, json, sys, time, datetime

sys.stdout.reconfigure(encoding='utf-8')
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

import os
TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT = '2010747443'
FOCUS = 'ROSE_USDT'
CYCLES = 10
INTERVAL = 60


def tg(msg):
    try:
        body = json.dumps({'chat_id': CHAT, 'text': msg}).encode()
        req = urllib.request.Request(
            f'https://api.telegram.org/bot{TOKEN}/sendMessage',
            data=body, headers={'Content-Type': 'application/json'})
        resp = urllib.request.urlopen(req, timeout=10)
        return json.loads(resp.read()).get('result', {}).get('message_id', '?')
    except:
        return 'FAIL'


def ema(data, period):
    k = 2 / (period + 1)
    e = data[0]
    for d in data[1:]:
        e = d * k + e * (1 - k)
    return e


def deep_analyze(sym):
    """Full analysis: klines + orderbook + indicators"""
    try:
        kd = json.loads(urllib.request.urlopen(
            f'https://contract.mexc.com/api/v1/contract/kline/{sym}?interval=Min15&limit=30', timeout=8).read())
        closes = kd['data']['close']
        highs = kd['data']['high']
        lows = kd['data']['low']
        vols = kd['data']['vol']

        deltas = [closes[j] - closes[j - 1] for j in range(1, len(closes))]
        ag14 = sum(max(0, x) for x in deltas[-14:]) / 14
        al14 = sum(max(0, -x) for x in deltas[-14:]) / 14
        rsi14 = 100 - (100 / (1 + ag14 / al14)) if al14 > 0 else 100
        ag7 = sum(max(0, x) for x in deltas[-7:]) / 7
        al7 = sum(max(0, -x) for x in deltas[-7:]) / 7
        rsi7 = 100 - (100 / (1 + ag7 / al7)) if al7 > 0 else 100

        ema9 = ema(closes[-15:], 9)
        ema21 = ema(closes[-25:], 21)

        n = min(20, len(closes))
        sma_val = sum(closes[-n:]) / n
        std = (sum((x - sma_val) ** 2 for x in closes[-n:]) / n) ** 0.5
        bb_w = (4 * std) / sma_val * 100

        mfv = 0
        for j in range(-min(5, n), 0):
            hl = highs[j] - lows[j]
            if hl > 0:
                mfv += ((closes[j] - lows[j]) - (highs[j] - closes[j])) / hl * vols[j]

        vol_avg = sum(vols[-20:]) / max(len(vols[-20:]), 1)
        vol_recent = sum(vols[-3:]) / 3
        vol_ratio = vol_recent / vol_avg if vol_avg > 0 else 1

        # Orderbook
        try:
            od = json.loads(urllib.request.urlopen(
                f'https://contract.mexc.com/api/v1/contract/depth/{sym}?limit=20', timeout=5).read())
            bids = od['data']['bids'][:20]
            asks = od['data']['asks'][:20]
            bv = sum(float(b[1]) for b in bids)
            av = sum(float(a[1]) for a in asks)
            ob = bv / av if av > 0 else 0
            bid_max = max(bids, key=lambda x: float(x[1]))
            ask_max = max(asks, key=lambda x: float(x[1]))
            bid_wall = f'{float(bid_max[0]):.6g}({float(bid_max[1]):,.0f})'
            ask_wall = f'{float(ask_max[0]):.6g}({float(ask_max[1]):,.0f})'
        except:
            ob = -1
            bid_wall = '?'
            ask_wall = '?'

        return {
            'rsi7': round(rsi7, 1), 'rsi14': round(rsi14, 1),
            'ob': round(ob, 2), 'mfv': mfv, 'bb_w': round(bb_w, 2),
            'vol_ratio': round(vol_ratio, 2), 'ema_bull': ema9 > ema21,
            'bid_wall': bid_wall, 'ask_wall': ask_wall,
            'last_close': closes[-1]
        }
    except Exception as e:
        return {'error': str(e)}


def scan_cycle(cycle_num):
    t0 = time.time()
    now = datetime.datetime.now().strftime('%H:%M:%S')
    print(f'\n{"=" * 80}')
    print(f'  SNIPER CYCLE {cycle_num}/10 - {now}')
    print(f'{"=" * 80}')

    # 1. FETCH TICKERS
    try:
        req = urllib.request.urlopen('https://contract.mexc.com/api/v1/contract/ticker', timeout=15)
        tickers = json.loads(req.read())['data']
    except Exception as e:
        print(f'  TICKER ERROR: {e}')
        return []

    # 2. SCORE
    scored = []
    rose_data = None
    for t in tickers:
        sym = t['symbol']
        try:
            price = float(t['lastPrice'])
            ch = float(t['riseFallRate']) * 100
            vol = float(t['volume24'])
            high = float(t['high24Price'])
            low = float(t['lower24Price'])
            rng = high - low if high > low else 0.0001
            rp = (price - low) / rng if rng > 0 else 0.5
            fund = float(t.get('fundingRate', 0))
            hold = float(t.get('holdVol', 0))
        except:
            continue

        # Save ROSE data always
        if sym == FOCUS:
            rose_data = {
                'sym': sym, 'price': price, 'ch': round(ch, 2), 'vol': vol,
                'rp': round(rp, 4), 'fund': round(fund, 6), 'hold': hold,
                'type': 'FOCUS', 'score': 100
            }

        score = 0
        stype = ''
        if rp > 0.88 and ch > 5 and vol > 5e5:
            score = rp * 55 + ch * 3.5 + min(vol / 1e6, 25) + (8 if hold > 5e7 else 0)
            stype = 'BRK-A'
        elif rp > 0.82 and ch > 3 and vol > 3e5:
            score = rp * 48 + ch * 3 + min(vol / 1e6, 20) + (5 if hold > 1e7 else 0)
            stype = 'BRK-B'
        elif rp > 0.90 and ch > 1:
            score = rp * 45 + ch * 2.5 + min(vol / 1e6, 15)
            stype = 'BRK-C'
        elif rp < 0.08 and vol > 5e6:
            score = (1 - rp) * 50 + abs(ch) * 2 + min(vol / 1e6, 25) + (8 if fund < -0.001 else 0)
            stype = 'REV-A'
        elif rp < 0.18 and ch < -5 and vol > 1e6:
            score = (1 - rp) * 42 + abs(ch) * 1.8 + min(vol / 1e6, 20)
            stype = 'REV-B'
        elif rp < 0.12 and vol > 2e6:
            score = (1 - rp) * 40 + abs(ch) * 1.5 + min(vol / 1e6, 18)
            stype = 'REV-C'

        if score > 35:
            scored.append({
                'sym': sym, 'price': price, 'ch': round(ch, 2), 'vol': vol,
                'rp': round(rp, 4), 'score': round(score, 1), 'fund': round(fund, 6),
                'hold': hold, 'type': stype
            })

    scored.sort(key=lambda x: x['score'], reverse=True)

    # 3. ROSE FOCUS - always analyze
    print(f'\n  --- ROSE FOCUS ---')
    if rose_data:
        rd = deep_analyze(FOCUS)
        if 'error' not in rd:
            pump = 50  # base
            if rd['ob'] > 1.5: pump += 10
            if rd['mfv'] < 0: pump += 5
            if rd['vol_ratio'] > 2: pump += 7
            if rd['bb_w'] < 2: pump += 5
            if rd['ema_bull']: pump += 3
            if rose_data['fund'] < -0.001: pump += 5
            if rose_data['rp'] > 0.85: pump += 8

            ema_tag = 'BULL' if rd['ema_bull'] else 'BEAR'
            chk = 'BUY' if rd['mfv'] < 0 else 'SELL'
            verdict = 'ENTRY NOW' if pump > 70 and rd['ob'] > 1.3 else 'GO' if pump > 60 else 'WAIT'

            print(f'  ROSE {rose_data["price"]} | Ch:{rose_data["ch"]:+.1f}% RP:{rose_data["rp"]:.2f}')
            print(f'  RSI7:{rd["rsi7"]} RSI14:{rd["rsi14"]} | OB:{rd["ob"]}x | {ema_tag} {chk}')
            print(f'  BB:{rd["bb_w"]}% | Vol:{rd["vol_ratio"]}x | Fund:{rose_data["fund"]}')
            print(f'  Walls: B={rd["bid_wall"]} A={rd["ask_wall"]}')
            print(f'  PUMP SCORE: {pump} | VERDICT: {verdict}')

            rose_data.update(rd)
            rose_data['pump_score'] = pump
            rose_data['verdict'] = verdict
        else:
            print(f'  ROSE ERROR: {rd["error"]}')
    else:
        print(f'  ROSE_USDT non trouve dans tickers!')

    # 4. TOP 5 others
    print(f'\n  --- TOP 5 BREAKOUTS ---')
    top5 = [s for s in scored[:8] if s['sym'] != FOCUS][:5]
    go_list = []

    for i, s in enumerate(top5):
        sym = s['sym']
        rd = deep_analyze(sym)
        if 'error' in rd:
            print(f'  #{i+1} {sym:18} ERROR: {rd["error"]}')
            continue

        pump = s['score']
        if rd['ob'] > 1.5: pump += 10
        if rd['mfv'] < 0: pump += 5
        if rd['vol_ratio'] > 2: pump += 7
        if rd['bb_w'] < 2: pump += 5
        if rd['ema_bull']: pump += 3

        tag = 'GO' if pump > 55 else 'WAIT'
        ema_tag = 'BULL' if rd['ema_bull'] else 'BEAR'
        chk = 'BUY' if rd['mfv'] < 0 else 'SELL'

        print(f'  #{i+1} {sym:18} Sc:{pump:5.1f} | {s["type"]} Ch:{s["ch"]:+.1f}% | RSI7:{rd["rsi7"]:4.1f} OB:{rd["ob"]:.2f}x {ema_tag} {chk} | {tag}')

        s.update(rd)
        s['pump_score'] = round(pump, 1)
        if tag == 'GO':
            go_list.append(s)

    # 5. TELEGRAM
    tg_lines = [f'SNIPER C{cycle_num}/10 - {now}', '']
    if rose_data and 'verdict' in rose_data:
        tg_lines.append(
            f'ROSE: {rose_data["price"]} | {rose_data.get("verdict","?")} | Sc:{rose_data.get("pump_score",0)}'
            f'\n  OB:{rose_data.get("ob","?")}x RSI7:{rose_data.get("rsi7","?")} Ch:{rose_data["ch"]:+.1f}%'
        )
    if go_list:
        tg_lines.append('')
        for s in go_list[:3]:
            tg_lines.append(f'{s["sym"]} Sc:{s["pump_score"]} Ch:{s["ch"]:+.1f}% OB:{s.get("ob","?")}x')

    tg_lines.append(f'\n{len(scored)} signaux | {round(time.time()-t0,1)}s')
    tg('\n'.join(tg_lines))

    elapsed = round(time.time() - t0, 1)
    print(f'\n  >> {len(scored)} signaux | {len(go_list)} GO | {elapsed}s')

    result = []
    if rose_data and 'verdict' in rose_data:
        result.append(rose_data)
    result.extend(go_list[:3])
    return result


# ========== MAIN ==========
print('SNIPER BREAKOUT 10 CYCLES - FOCUS ROSE')
print(f'Debut: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
tg(f'SNIPER 10 CYCLES START - FOCUS ROSE\n{datetime.datetime.now().strftime("%H:%M:%S")}')

all_signals = {}
rose_history = []

for cycle in range(1, CYCLES + 1):
    try:
        results = scan_cycle(cycle)
        for s in results:
            sym = s['sym']
            if sym not in all_signals:
                all_signals[sym] = 0
            all_signals[sym] += 1
            if sym == FOCUS:
                rose_history.append({
                    'cycle': cycle,
                    'price': s['price'],
                    'ob': s.get('ob', '?'),
                    'rsi7': s.get('rsi7', '?'),
                    'verdict': s.get('verdict', '?'),
                    'pump_score': s.get('pump_score', 0)
                })
    except Exception as e:
        print(f'  CYCLE {cycle} ERROR: {e}')

    if cycle < CYCLES:
        print(f'  Attente {INTERVAL}s...')
        time.sleep(INTERVAL)

# FINAL
print(f'\n{"=" * 80}')
print(f'  RESUME 10 CYCLES SNIPER')
print(f'{"=" * 80}')

ranking = sorted(all_signals.items(), key=lambda x: x[1], reverse=True)
summary = ['SNIPER 10 CYCLES - RESUME', '']

print(f'\n  FREQUENCE APPARITION:')
for sym, count in ranking:
    bar = '#' * count
    line = f'{sym:18} {bar} ({count}/10)'
    print(f'  {line}')
    summary.append(line)

print(f'\n  ROSE EVOLUTION:')
summary.append('')
summary.append('ROSE EVOLUTION:')
for rh in rose_history:
    line = f'  C{rh["cycle"]:02d} | {rh["price"]} | OB:{rh["ob"]}x | RSI7:{rh["rsi7"]} | Sc:{rh["pump_score"]} | {rh["verdict"]}'
    print(line)
    summary.append(line)

# Best entry timing
if rose_history:
    best = min(rose_history, key=lambda x: x['price'])
    worst = max(rose_history, key=lambda x: x['price'])
    summary.append(f'\nBest entry: C{best["cycle"]} @ {best["price"]}')
    summary.append(f'Peak: C{worst["cycle"]} @ {worst["price"]}')
    print(f'\n  Best entry: C{best["cycle"]} @ {best["price"]}')
    print(f'  Peak: C{worst["cycle"]} @ {worst["price"]}')

summary.append(f'\nFin: {datetime.datetime.now().strftime("%H:%M:%S")}')
tg('\n'.join(summary))

print(f'\nSNIPER 10 CYCLES TERMINE - {datetime.datetime.now().strftime("%H:%M:%S")}')
