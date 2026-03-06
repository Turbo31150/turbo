#!/usr/bin/env python3
"""
TRADING AI ULTIMATE v4.0 - Enhanced Scanner
Pipeline: Scan -> Deep Analysis -> 3-IA Consensus -> Telegram
"""

import asyncio
import aiohttp
import json
from datetime import datetime

# Configuration
CONFIG = {
    "mexc_api": "https://contract.mexc.com/api/v1/contract/ticker",
    "gemini_key": "AIzaSyBT1vDFHmMA8Fc4880rFM8Ylk-IYzeH2vA",
    "lm_studio_1": "http://192.168.1.85:1234",
    "lm_studio_2": "http://192.168.1.26:1234",
    "telegram_token": "8369376863:AAF-7YGDbun8mXWwqYJFj-eX6P78DeIu9Aw",
    "telegram_chat": "2010747443",
    "min_score": 70,
    "max_rsi": 75,
    "max_sell_pressure": 30,
    "consensus_required": 2
}

async def scan_mexc():
    """Step 1: Scan MEXC Futures"""
    async with aiohttp.ClientSession() as session:
        async with session.get(CONFIG["mexc_api"]) as resp:
            data = await resp.json()

    signals = []
    for t in data.get("data", []):
        if not t["symbol"].endswith("_USDT"):
            continue

        price = float(t.get("lastPrice", 0))
        high24 = float(t.get("high24Price", price))
        low24 = float(t.get("low24Price", price))
        volume = float(t.get("volume24", 0))
        change = float(t.get("riseFallRate", 0))
        volume_usd = volume * price

        # Calculate score
        score = 50
        if volume_usd > 10000000: score += 15
        elif volume_usd > 5000000: score += 10
        elif volume_usd > 1000000: score += 5

        range_val = high24 - low24
        if range_val > 0:
            position = (price - low24) / range_val
            if position > 0.85: score += 20
            elif position < 0.15: score += 15

        abs_change = abs(change)
        if abs_change > 10: score += 20
        elif abs_change > 5: score += 10
        elif abs_change > 2: score += 5

        if score >= CONFIG["min_score"]:
            signals.append({
                "symbol": t["symbol"].replace("_USDT", "/USDT"),
                "price": price,
                "score": score,
                "change_24h": change,
                "volume_usd": volume_usd,
                "direction": "LONG" if change > 0 else "SHORT",
                "position": position if range_val > 0 else 0.5
            })

    signals.sort(key=lambda x: x["score"], reverse=True)
    return signals[:5]

async def deep_analyze(session, symbol):
    """Step 2: Deep Analysis via MCP webhook"""
    try:
        url = f"http://localhost:5678/webhook/analyze-coin?symbol={symbol.replace('/', '')}"
        async with session.get(url, timeout=10) as resp:
            if resp.status == 200:
                return await resp.json()
    except:
        pass

    # Fallback: basic analysis
    return {
        "rsi": 50,
        "orderbook_pressure": "NEUTRAL",
        "sell_pressure_pct": 0,
        "whale_activity": "NEUTRAL"
    }

async def ask_gemini(session, prompt):
    """Query Gemini API"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={CONFIG['gemini_key']}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    try:
        async with session.post(url, json=payload, timeout=15) as resp:
            data = await resp.json()
            return data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "NO_RESPONSE")
    except Exception as e:
        return f"ERROR: {e}"

async def ask_lmstudio(session, endpoint, prompt):
    """Query LM Studio"""
    url = f"{endpoint}/v1/chat/completions"
    payload = {
        "model": "local",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 100
    }
    try:
        async with session.post(url, json=payload, timeout=60) as resp:
            data = await resp.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content", "NO_RESPONSE")
    except Exception as e:
        return f"ERROR: {e}"

async def get_consensus(session, signal, analysis):
    """Step 3: Multi-IA Consensus"""
    prompt = f"""Trading signal: {signal['symbol']} at {signal['price']:.6f}.
Score: {signal['score']}, Change 24h: {signal['change_24h']:.2f}%
RSI: {analysis.get('rsi', 'N/A')}, Orderbook: {analysis.get('orderbook_pressure', 'N/A')}
Whale activity: {analysis.get('whale_activity', 'N/A')}
Direction proposed: {signal['direction']}

Quick answer: BUY, WAIT, or AVOID? One word."""

    # Query 3 IAs in parallel
    results = await asyncio.gather(
        ask_gemini(session, prompt),
        ask_lmstudio(session, CONFIG["lm_studio_1"], prompt),
        ask_lmstudio(session, CONFIG["lm_studio_2"], prompt),
        return_exceptions=True
    )

    responses = {
        "gemini": str(results[0])[:100] if results[0] else "ERROR",
        "lm_studio_1": str(results[1])[:100] if results[1] else "ERROR",
        "lm_studio_2": str(results[2])[:100] if results[2] else "ERROR"
    }

    # Count BUY votes
    buy_votes = sum(1 for r in responses.values() if "BUY" in r.upper())

    return {
        "responses": responses,
        "buy_votes": buy_votes,
        "consensus": buy_votes >= CONFIG["consensus_required"]
    }

async def send_telegram(message):
    """Step 4: Send Telegram Alert"""
    url = f"https://api.telegram.org/bot{CONFIG['telegram_token']}/sendMessage"
    payload = {
        "chat_id": CONFIG["telegram_chat"],
        "text": message,
        "parse_mode": "HTML"
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            return await resp.json()

async def run_pipeline():
    """Main pipeline"""
    print(f"[{datetime.now()}] Starting Enhanced Scanner v4.0...")

    # Step 1: Scan
    signals = await scan_mexc()
    print(f"[SCAN] Found {len(signals)} signals with score >= {CONFIG['min_score']}")

    if not signals:
        return {"status": "no_signals"}

    async with aiohttp.ClientSession() as session:
        for signal in signals[:3]:  # Process top 3
            print(f"\n[ANALYZE] {signal['symbol']} - Score {signal['score']}")

            # Step 2: Deep Analysis
            analysis = await deep_analyze(session, signal['symbol'])

            # Anti-FOMO filter
            rsi = analysis.get('rsi', 50)
            sell_pressure = analysis.get('sell_pressure_pct', 0)

            if rsi > CONFIG["max_rsi"]:
                print(f"  [SKIP] RSI {rsi} > {CONFIG['max_rsi']} (FOMO risk)")
                continue

            if sell_pressure > CONFIG["max_sell_pressure"]:
                print(f"  [SKIP] Sell pressure {sell_pressure}% > {CONFIG['max_sell_pressure']}%")
                continue

            # Step 3: Consensus
            consensus = await get_consensus(session, signal, analysis)
            print(f"  [CONSENSUS] {consensus['buy_votes']}/3 IAs say BUY")

            if consensus["consensus"]:
                # Step 4: Send Alert
                msg = f"""<b>SIGNAL VALIDATED - v4.0</b>

<b>{signal['symbol']}</b>
Direction: {signal['direction']}
Score: {signal['score']}/100

Price: {signal['price']:.6f}
RSI: {rsi}
Orderbook: {analysis.get('orderbook_pressure', 'N/A')}
Whales: {analysis.get('whale_activity', 'N/A')}

<b>CONSENSUS: {consensus['buy_votes']}/3 BUY</b>
Gemini: {consensus['responses']['gemini'][:50]}
LM1: {consensus['responses']['lm_studio_1'][:50]}
LM2: {consensus['responses']['lm_studio_2'][:50]}

{datetime.now().strftime('%H:%M:%S')}"""

                await send_telegram(msg)
                print(f"  [TELEGRAM] Alert sent!")
            else:
                print(f"  [SKIP] No consensus ({consensus['buy_votes']}/3)")

    return {"status": "complete", "signals_processed": len(signals)}

if __name__ == "__main__":
    asyncio.run(run_pipeline())
