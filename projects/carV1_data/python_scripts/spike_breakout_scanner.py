#!/usr/bin/env python3
"""
SPIKE BREAKOUT SCANNER - Entree/Sortie Immediate sur GROS PIKES
Trading AI Ultimate v9.0
"""

import ccxt
import time
import json
import requests
from datetime import datetime

# Configuration
TELEGRAM_TOKEN = "TELEGRAM_TOKEN_REDACTED"
TELEGRAM_CHAT = "2010747443"
MIN_SPIKE_PERCENT = 1.5  # Minimum spike % pour alerte
MIN_VOLUME_MULTIPLIER = 3.0  # Volume 3x normal
SCAN_INTERVAL = 10  # Scan toutes les 10 secondes

# MEXC Setup
exchange = ccxt.mexc({
    'apiKey': 'MEXC_KEY_REDACTED',
    'secret': 'MEXC_SECRET_REDACTED',
    'enableRateLimit': True,
    'options': {'defaultType': 'swap'}
})

def send_telegram(message):
    """Envoyer alerte Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT, "text": message, "parse_mode": "HTML"}
        requests.post(url, data=data, timeout=5)
    except:
        pass

def get_all_tickers():
    """Recuperer tous les tickers MEXC Futures"""
    try:
        tickers = exchange.fetch_tickers()
        return {k: v for k, v in tickers.items() if '/USDT:USDT' in k}
    except Exception as e:
        print(f"[ERROR] Fetch tickers: {e}")
        return {}

def detect_spike(ticker, prev_price, prev_volume):
    """Detecter un spike de prix ou volume"""
    symbol = ticker['symbol']
    price = ticker.get('last', 0)
    volume = ticker.get('quoteVolume', 0) or 0
    change = ticker.get('percentage', 0) or 0
    high = ticker.get('high', 0) or price
    low = ticker.get('low', 0) or price

    if not price or not prev_price.get(symbol):
        prev_price[symbol] = price
        prev_volume[symbol] = volume
        return None

    # Calcul variation depuis dernier scan
    price_change = ((price - prev_price[symbol]) / prev_price[symbol]) * 100 if prev_price[symbol] else 0
    volume_ratio = volume / prev_volume[symbol] if prev_volume[symbol] else 1

    # Range position (0 = low, 100 = high)
    range_pos = ((price - low) / (high - low) * 100) if (high - low) > 0 else 50

    # Update previous values
    prev_price[symbol] = price
    prev_volume[symbol] = volume

    # Detection SPIKE
    is_spike = False
    spike_type = None

    # SPIKE HAUSSIER
    if price_change >= MIN_SPIKE_PERCENT:
        is_spike = True
        spike_type = "PUMP"
    # SPIKE BAISSIER
    elif price_change <= -MIN_SPIKE_PERCENT:
        is_spike = True
        spike_type = "DUMP"
    # VOLUME EXPLOSION
    elif volume_ratio >= MIN_VOLUME_MULTIPLIER and abs(price_change) >= 0.5:
        is_spike = True
        spike_type = "VOLUME_EXPLOSION"
    # BREAKOUT IMMINENT (proche du high avec volume)
    elif range_pos >= 95 and change > 3 and volume_ratio >= 2:
        is_spike = True
        spike_type = "BREAKOUT_IMMINENT"
    # REVERSAL IMMINENT (proche du low avec volume)
    elif range_pos <= 5 and change < -3 and volume_ratio >= 2:
        is_spike = True
        spike_type = "REVERSAL_IMMINENT"

    if is_spike:
        return {
            'symbol': symbol.replace(':USDT', ''),
            'type': spike_type,
            'price': price,
            'price_change': price_change,
            'change_24h': change,
            'volume_ratio': volume_ratio,
            'range_pos': range_pos,
            'high': high,
            'low': low,
            'timestamp': datetime.now().isoformat()
        }

    return None

def format_alert(spike):
    """Formater alerte pour Telegram"""
    emoji = {
        'PUMP': '🚀🟢',
        'DUMP': '🔻🔴',
        'VOLUME_EXPLOSION': '💥📊',
        'BREAKOUT_IMMINENT': '⚡🔥',
        'REVERSAL_IMMINENT': '🔄💎'
    }

    direction = "LONG" if spike['type'] in ['PUMP', 'BREAKOUT_IMMINENT', 'REVERSAL_IMMINENT'] else "SHORT"

    msg = f"""
{emoji.get(spike['type'], '⚠️')} <b>SPIKE DETECTE - {spike['type']}</b>

<b>{spike['symbol']}</b> - {direction}

💰 Prix: ${spike['price']:.4f}
📈 Variation: {spike['price_change']:+.2f}% (10s)
📊 24h: {spike['change_24h']:+.2f}%
🔊 Volume: {spike['volume_ratio']:.1f}x normal
📍 Range: {spike['range_pos']:.0f}%

🎯 TP: ${spike['price'] * (1.02 if direction == 'LONG' else 0.98):.4f} (+2%)
🛑 SL: ${spike['price'] * (0.99 if direction == 'LONG' else 1.01):.4f} (-1%)

<i>⏱️ ENTREE IMMEDIATE RECOMMANDEE</i>
"""
    return msg

def main():
    print("""
========================================================================
     SPIKE BREAKOUT SCANNER - GROS PIKES IMMEDIATS
     Scan: 10s | Min Spike: 1.5% | Volume: 3x
========================================================================
""")

    prev_price = {}
    prev_volume = {}
    scan_count = 0
    spikes_found = 0

    send_telegram("🔥 <b>SPIKE SCANNER ACTIVE</b>\n\nRecherche de GROS PIKES en cours...\nScan: 10s | Seuil: 1.5%")

    while True:
        try:
            scan_count += 1
            print(f"\n[SCAN #{scan_count}] {datetime.now().strftime('%H:%M:%S')}")

            tickers = get_all_tickers()
            print(f"  Analyse de {len(tickers)} paires...")

            for symbol, ticker in tickers.items():
                spike = detect_spike(ticker, prev_price, prev_volume)

                if spike:
                    spikes_found += 1
                    print(f"\n  >>> SPIKE #{spikes_found}: {spike['symbol']} - {spike['type']}")
                    print(f"     Prix: ${spike['price']:.4f} | Variation: {spike['price_change']:+.2f}%")
                    print(f"     Volume: {spike['volume_ratio']:.1f}x | Range: {spike['range_pos']:.0f}%")

                    # Envoyer alerte Telegram
                    alert = format_alert(spike)
                    send_telegram(alert)

                    # Log to file
                    with open('spikes_log.json', 'a') as f:
                        f.write(json.dumps(spike) + '\n')

            print(f"  Total spikes detectes: {spikes_found}")
            time.sleep(SCAN_INTERVAL)

        except KeyboardInterrupt:
            print("\n[STOP] Scanner arrete")
            break
        except Exception as e:
            print(f"[ERROR] {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
