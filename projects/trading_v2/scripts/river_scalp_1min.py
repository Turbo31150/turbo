#!/usr/bin/env python3
"""RIVER_USDT - Scalping 1min Monitor avec alertes Telegram"""
import urllib.request, json, sys, time, datetime

sys.stdout.reconfigure(encoding='utf-8')
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

TOKEN = '8369376863:AAF-7YGDbun8mXWwqYJFj-eX6P78DeIu9Aw'
CHAT = '2010747443'
SYMBOL = 'RIVER_USDT'

# Position info (MAJ 2026-02-08 from MEXC API)
ENTRY = 12.484
QTY_CONTRACTS = 478
CONTRACT_SIZE = 0.1
QTY_TOKENS = QTY_CONTRACTS * CONTRACT_SIZE  # 47.8
LEVERAGE = 20
MARGIN = 29.90
LIQUIDATION = 11.987

# Alert thresholds
ALERT_TP1 = 12.484    # breakeven (= entry)
ALERT_TP2 = 12.61     # +1.0%
ALERT_TP3 = 12.80     # +2.5%
ALERT_SL = 12.10      # emergency
ALERT_LIQ_WARN = 12.05  # ~0.5% above liquidation

CYCLES = 50  # 30 cycles x 60s = 30 minutes
INTERVAL = 60

last_alert_price = 0
alerts_sent = set()


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


def get_data():
    """Fetch ticker + klines 1min + orderbook"""
    # Ticker
    t_req = urllib.request.urlopen(
        f'https://contract.mexc.com/api/v1/contract/ticker?symbol={SYMBOL}', timeout=8)
    ticker = json.loads(t_req.read())['data']
    price = float(ticker['lastPrice'])
    bid1 = float(ticker.get('bid1', 0))
    ask1 = float(ticker.get('ask1', 0))

    # Klines 1min
    k_req = urllib.request.urlopen(
        f'https://contract.mexc.com/api/v1/contract/kline/{SYMBOL}?interval=Min1&limit=30', timeout=8)
    kd = json.loads(k_req.read())
    closes = kd['data']['close']
    highs = kd['data']['high']
    lows = kd['data']['low']
    vols = kd['data']['vol']

    # RSI 7
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    ag = sum(max(0, x) for x in deltas[-7:]) / 7
    al = sum(max(0, -x) for x in deltas[-7:]) / 7
    rsi7 = 100 - (100 / (1 + ag / al)) if al > 0 else 100

    # RSI 14
    ag14 = sum(max(0, x) for x in deltas[-14:]) / 14
    al14 = sum(max(0, -x) for x in deltas[-14:]) / 14
    rsi14 = 100 - (100 / (1 + ag14 / al14)) if al14 > 0 else 100

    # EMA
    def ema(data, period):
        k = 2 / (period + 1)
        e = data[0]
        for d in data[1:]:
            e = d * k + e * (1 - k)
        return e

    ema9 = ema(closes[-15:], 9)
    ema21 = ema(closes[-25:], 21)

    # BB
    n = min(20, len(closes))
    sma = sum(closes[-n:]) / n
    std = (sum((x - sma) ** 2 for x in closes[-n:]) / n) ** 0.5
    bb_up = sma + 2 * std
    bb_low = sma - 2 * std
    bb_w = (bb_up - bb_low) / sma * 100

    # Momentum
    mom3 = (closes[-1] - closes[-4]) / closes[-4] * 100 if len(closes) >= 4 else 0

    # Chaikin
    mfv = 0
    for j in range(-min(5, n), 0):
        hl = highs[j] - lows[j]
        if hl > 0:
            mfv += ((closes[j] - lows[j]) - (highs[j] - closes[j])) / hl * vols[j]

    # Orderbook
    try:
        o_req = urllib.request.urlopen(
            f'https://contract.mexc.com/api/v1/contract/depth/{SYMBOL}?limit=10', timeout=5)
        od = json.loads(o_req.read())
        bv = sum(float(b[1]) for b in od['data']['bids'][:10])
        av = sum(float(a[1]) for a in od['data']['asks'][:10])
        ob_pressure = bv / av if av > 0 else 0
    except:
        ob_pressure = -1

    # Volume
    vol_avg = sum(vols[-20:]) / max(len(vols[-20:]), 1)
    vol_recent = sum(vols[-3:]) / 3
    vol_ratio = vol_recent / vol_avg if vol_avg > 0 else 1

    return {
        'price': price, 'bid1': bid1, 'ask1': ask1,
        'rsi7': rsi7, 'rsi14': rsi14,
        'ema9': ema9, 'ema21': ema21,
        'bb_up': bb_up, 'bb_low': bb_low, 'bb_w': bb_w,
        'mom3': mom3, 'mfv': mfv, 'ob': ob_pressure,
        'vol_ratio': vol_ratio,
        'last_close': closes[-1],
        'last_high': max(highs[-3:]),
        'last_low': min(lows[-3:]),
    }


def analyze(d):
    """Generate scalping signal"""
    signals = []

    # RSI
    if d['rsi7'] < 20:
        signals.append('+++ RSI7 EXTREME OVERSOLD')
    elif d['rsi7'] < 30:
        signals.append('++ RSI7 oversold')
    elif d['rsi7'] > 80:
        signals.append('--- RSI7 OVERBOUGHT')
    elif d['rsi7'] > 70:
        signals.append('-- RSI7 high')

    # BB
    if d['price'] < d['bb_low']:
        signals.append('+++ BELOW BB lower')
    elif d['price'] > d['bb_up']:
        signals.append('--- ABOVE BB upper')
    if d['bb_w'] < 1.5:
        signals.append('!! BB SQUEEZE')

    # EMA
    if d['ema9'] > d['ema21']:
        signals.append('+ EMA BULL')
    else:
        signals.append('- EMA BEAR')

    # Momentum
    if d['mom3'] > 0.3:
        signals.append('+ Mom UP')
    elif d['mom3'] < -0.3:
        signals.append('- Mom DOWN')

    # Orderbook
    if d['ob'] > 1.5:
        signals.append('++ OB BUY STRONG')
    elif d['ob'] > 1.1:
        signals.append('+ OB BUY')
    elif d['ob'] < 0.7 and d['ob'] >= 0:
        signals.append('-- OB SELL')

    # Chaikin
    if d['mfv'] < 0:
        signals.append('+ Chaikin BUY')
    else:
        signals.append('- Chaikin SELL')

    # Volume
    if d['vol_ratio'] > 2:
        signals.append(f'!! VOL SPIKE {d["vol_ratio"]:.1f}x')

    bull = len([s for s in signals if s.startswith('+')])
    bear = len([s for s in signals if s.startswith('-')])

    return signals, bull, bear


def check_alerts(d, cycle):
    """Check price alerts and send Telegram"""
    global alerts_sent
    price = d['price']
    pnl = QTY_TOKENS * (price - ENTRY)
    pnl_pct = pnl / MARGIN * 100
    dist_liq = (price - LIQUIDATION) / price * 100

    msgs = []

    # Liquidation warning
    if price <= ALERT_LIQ_WARN and 'LIQ_WARN' not in alerts_sent:
        msgs.append(f'RIVER LIQUIDATION WARNING\nPrix: {price} | Liq: {LIQUIDATION}\nDist: {dist_liq:.1f}%')
        alerts_sent.add('LIQ_WARN')

    # Emergency SL
    if price <= ALERT_SL and 'SL' not in alerts_sent:
        msgs.append(f'RIVER SL TOUCHE\nPrix: {price} | PnL: {pnl:+.2f}$ ({pnl_pct:+.1f}%)')
        alerts_sent.add('SL')

    # Breakeven
    if price >= ALERT_TP1 and 'BE' not in alerts_sent:
        msgs.append(f'RIVER BREAKEVEN ATTEINT\nPrix: {price} | Entry: {ENTRY}')
        alerts_sent.add('BE')

    # TP2
    if price >= ALERT_TP2 and 'TP2' not in alerts_sent:
        msgs.append(f'RIVER TP2 TOUCHE\nPrix: {price} | PnL: {pnl:+.2f}$ ({pnl_pct:+.1f}%)')
        alerts_sent.add('TP2')

    # TP3
    if price >= ALERT_TP3 and 'TP3' not in alerts_sent:
        msgs.append(f'RIVER TP3 TOUCHE - TAKE PROFIT\nPrix: {price} | PnL: {pnl:+.2f}$ ({pnl_pct:+.1f}%)')
        alerts_sent.add('TP3')

    # RSI extreme alerts
    if d['rsi7'] < 15 and 'RSI_EXTREME' not in alerts_sent:
        msgs.append(f'RIVER RSI7 EXTREME LOW: {d["rsi7"]:.1f}\nRebond imminent probable')
        alerts_sent.add('RSI_EXTREME')

    # Send all alerts
    for m in msgs:
        tg(m)

    # Reset alerts if price moves away
    if price > ALERT_LIQ_WARN + 0.1:
        alerts_sent.discard('LIQ_WARN')
    if d['rsi7'] > 30:
        alerts_sent.discard('RSI_EXTREME')

    return pnl, pnl_pct, dist_liq


# ========== MAIN ==========
print(f'RIVER SCALP MONITOR - {CYCLES} cycles x {INTERVAL}s')
print(f'Position: LONG {QTY_TOKENS} RIVER @ {ENTRY} (20x, margin {MARGIN}$)')
print(f'Liquidation: {LIQUIDATION}')
tg(f'RIVER SCALP MONITOR START\nLONG {QTY_TOKENS} @ {ENTRY}\nLiq: {LIQUIDATION}\n{CYCLES} cycles')

for cycle in range(1, CYCLES + 1):
    try:
        now = datetime.datetime.now().strftime('%H:%M:%S')
        d = get_data()
        signals, bull, bear = analyze(d)
        pnl, pnl_pct, dist_liq = check_alerts(d, cycle)

        direction = 'LONG' if bull > bear else 'SHORT' if bear > bull else 'FLAT'
        ema_tag = 'B' if d['ema9'] > d['ema21'] else 'S'
        ob_tag = f'{d["ob"]:.1f}x' if d['ob'] > 0 else '?'
        chk = 'B' if d['mfv'] < 0 else 'S'

        line = (
            f'C{cycle:02d} {now} | {d["price"]:8.3f} | '
            f'PnL:{pnl:+6.2f}$({pnl_pct:+5.1f}%) | '
            f'RSI7:{d["rsi7"]:4.1f} RSI14:{d["rsi14"]:4.1f} | '
            f'EMA:{ema_tag} OB:{ob_tag} CHK:{chk} | '
            f'BB:{d["bb_w"]:4.1f}% Mom:{d["mom3"]:+.2f}% | '
            f'Liq:{dist_liq:.1f}% | {direction}'
        )
        print(line)

        # Every 5 cycles, send Telegram status
        if cycle % 5 == 0:
            status_lines = [
                f'RIVER C{cycle}/{CYCLES} - {now}',
                f'Prix: {d["price"]} | PnL: {pnl:+.2f}$ ({pnl_pct:+.1f}%)',
                f'RSI7: {d["rsi7"]:.1f} | OB: {ob_tag} | {direction}',
                f'Dist Liq: {dist_liq:.1f}%',
            ]
            if signals:
                status_lines.append('Signals: ' + ' | '.join(signals[:4]))
            tg('\n'.join(status_lines))

    except Exception as e:
        print(f'C{cycle:02d} ERROR: {e}')

    if cycle < CYCLES:
        time.sleep(INTERVAL)

# Final summary
print(f'\nMONITOR TERMINE - {CYCLES} cycles')
tg(f'RIVER MONITOR TERMINE - {CYCLES} cycles')
