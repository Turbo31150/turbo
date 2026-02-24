"""
GPU Trading Pipeline — Detection & Analyse Multi-GPU MEXC Futures
Architecture:
  - RTX 3080 (GPU 4): Detection rapide, scoring neuronal
  - 3x GTX 1660S (GPU 1-3): Analyse fine distribuee par coin
  - RTX 2060 (GPU 0): Orchestration, watchlist, modeles charges

Pipeline: MEXC scrape → Score → Filtre → Analyse IA fine → Classification → Signal
Usage:
  cd F:/BUREAU/turbo && uv run python scripts/gpu_trading_pipeline.py [--cycles N] [--json] [--top N] [--interval S]
"""
import asyncio
import httpx
import json
import sys
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime

# === CONFIG ===
BASE = "https://contract.mexc.com/api/v1/contract"
OLLAMA_URL = "http://127.0.0.1:11434"

# Paires par market cap tier
TIER_LARGE_CAP = ["BTC_USDT", "ETH_USDT", "SOL_USDT", "XRP_USDT"]
TIER_MID_CAP = ["SUI_USDT", "AVAX_USDT", "LINK_USDT", "ADA_USDT"]
TIER_SMALL_CAP = ["PEPE_USDT", "DOGE_USDT"]
ALL_PAIRS = TIER_LARGE_CAP + TIER_MID_CAP + TIER_SMALL_CAP

# Trading params
TP_PCT = 0.004    # 0.4%
SL_PCT = 0.0025   # 0.25%
LEVERAGE = 10
SIZE_USDT = 10
MIN_SCORE = 20     # score min pour analyse fine (marche calme = baisser)
SIGNAL_SCORE = 70  # score min pour signal actionnable

# GPU allocation (nvidia-smi index)
GPU_ORCHESTRATOR = 0   # RTX 2060 — watchlist, modeles Ollama
GPU_DETECTOR = 4       # RTX 3080 — detection rapide
GPU_WORKERS = [1, 2, 3]  # 3x 1660S — analyse fine distribuee


@dataclass
class CoinAnalysis:
    symbol: str
    tier: str                   # large/mid/small
    direction: str              # LONG/SHORT
    score_technical: int        # 0-100 (scan sniper)
    score_ai: int               # 0-100 (analyse fine IA)
    score_final: int            # ponderation (tech*0.4 + ai*0.6)
    pump_probability: float     # 0-100%
    pump_eta_minutes: int       # estimation temps avant pump
    last_price: float
    entry: float
    tp: float
    sl: float
    reasons: list = field(default_factory=list)
    ai_analysis: str = ""
    watchlist_tier: str = ""    # "imminent" / "1h" / "2h+" / "surveillance"
    gpu_worker: int = -1        # quel GPU a fait l'analyse
    timestamp: str = ""


# === PHASE 1: Detection Rapide (RTX 3080) ===

async def fetch_json(client: httpx.AsyncClient, url: str) -> dict | None:
    try:
        r = await client.get(url, timeout=10)
        data = r.json()
        if data.get("success"):
            return data.get("data")
    except Exception:
        pass
    return None


async def phase1_detect(client: httpx.AsyncClient) -> list[dict]:
    """Phase 1: Scan rapide MEXC — ticker + klines + depth pour toutes les paires."""
    tickers_data = await fetch_json(client, f"{BASE}/ticker")
    if not tickers_data:
        return []

    tickers = [t for t in tickers_data if t["symbol"] in ALL_PAIRS]
    results = []

    # Analyse parallele de toutes les paires
    async def analyze_quick(ticker):
        symbol = ticker["symbol"]
        klines, depth = await asyncio.gather(
            fetch_json(client, f"{BASE}/kline/{symbol}?interval=Min15&limit=96"),
            fetch_json(client, f"{BASE}/depth/{symbol}?limit=20"),
        )

        score = 0
        reasons = []
        direction = "LONG"

        # Analyse klines
        if klines and "close" in klines:
            closes = klines["close"]
            highs = klines["high"]
            lows = klines["low"]
            volumes = klines["vol"]
            n = len(closes)

            if n >= 20:
                sma20 = sum(closes[-20:]) / 20
                last = closes[-1]
                avg_vol = sum(volumes[-20:]) / 20
                vol_surge = volumes[-1] > avg_vol * 1.5 if avg_vol > 0 else False

                # Breakout
                recent_high = max(highs[-20:])
                if last > recent_high * 0.998 and vol_surge:
                    score += 25
                    reasons.append("Breakout haussier + volume")

                # Volume surge
                if vol_surge:
                    ratio = volumes[-1] / avg_vol if avg_vol > 0 else 0
                    score += min(20, int(ratio * 5))
                    reasons.append(f"Volume x{ratio:.1f}")

                # RSI
                if n >= 15:
                    gains = [max(0, closes[i] - closes[i-1]) for i in range(-14, 0)]
                    losses = [max(0, closes[i-1] - closes[i]) for i in range(-14, 0)]
                    avg_g = sum(gains) / 14
                    avg_l = sum(losses) / 14
                    rsi = 100 - (100 / (1 + avg_g / avg_l)) if avg_l > 0 else 100
                    if rsi < 30:
                        score += 20
                        reasons.append(f"RSI survendu ({rsi:.0f})")
                    elif rsi > 70:
                        score += 15
                        reasons.append(f"RSI suracheté ({rsi:.0f})")

                # Compression (squeeze)
                if n >= 20:
                    r_recent = max(highs[-10:]) - min(lows[-10:])
                    r_older = max(highs[-20:-10]) - min(lows[-20:-10])
                    if r_older > 0 and r_recent < r_older * 0.5:
                        score += 15
                        reasons.append("Squeeze pre-breakout")

                # Momentum
                if n >= 5:
                    momentum = (closes[-1] - closes[-5]) / closes[-5] * 100
                    if abs(momentum) > 1.5:
                        score += 10
                        reasons.append(f"Momentum {'haussier' if momentum > 0 else 'baissier'} ({momentum:+.2f}%)")
                    direction = "LONG" if momentum > 0 else "SHORT"

                # Retournement
                if n >= 3:
                    wick_low = min(closes[-1], klines["open"][-1]) - lows[-1]
                    body_last = abs(closes[-1] - klines["open"][-1])
                    if body_last > 0 and wick_low > body_last * 2 and last < sma20:
                        score += 15
                        reasons.append("Hammer reversal")

        # Analyse depth
        if depth:
            bids = depth.get("bids", [])
            asks = depth.get("asks", [])
            bid_vol = sum(b[1] for b in bids[:20]) if bids else 0
            ask_vol = sum(a[1] for a in asks[:20]) if asks else 0
            total = bid_vol + ask_vol
            if total > 0:
                bid_pct = bid_vol / total
                if bid_pct > 0.6:
                    score += 10
                    reasons.append(f"Pression acheteuse {bid_pct:.0%}")
                elif bid_pct < 0.4:
                    score += 10
                    reasons.append(f"Pression vendeuse {1-bid_pct:.0%}")

        # Tier
        tier = "large" if symbol in TIER_LARGE_CAP else "mid" if symbol in TIER_MID_CAP else "small"

        return {
            "symbol": symbol,
            "tier": tier,
            "score": score,
            "direction": direction,
            "reasons": reasons,
            "last_price": ticker["lastPrice"],
            "change_24h": ticker["riseFallRate"] * 100,
            "volume_24h": ticker["amount24"],
            "funding_rate": ticker["fundingRate"],
        }

    tasks = [analyze_quick(t) for t in tickers]
    results = await asyncio.gather(*tasks)
    return [r for r in results if r["score"] >= MIN_SCORE]


# === PHASE 2: Analyse Fine IA (3x 1660 Super) ===

async def phase2_ai_analysis(client: httpx.AsyncClient, coins: list[dict]) -> list[CoinAnalysis]:
    """Phase 2: Distribue l'analyse fine sur les 3 GPU workers (1660S)."""
    if not coins:
        return []

    async def analyze_with_ai(coin: dict, gpu_idx: int) -> CoinAnalysis:
        """Analyse fine d'un coin via Ollama sur un GPU specifique."""
        symbol = coin["symbol"].replace("_USDT", "")
        prompt = (
            f"Analyse trading rapide de {symbol}/USDT:\n"
            f"- Prix: {coin['last_price']} USDT\n"
            f"- Variation 24h: {coin['change_24h']:+.2f}%\n"
            f"- Volume 24h: {coin['volume_24h']:,.0f} USDT\n"
            f"- Funding rate: {coin['funding_rate']:.6f}\n"
            f"- Direction detectee: {coin['direction']}\n"
            f"- Score technique: {coin['score']}/100\n"
            f"- Signaux: {', '.join(coin['reasons'])}\n\n"
            f"Reponds en 3 lignes max:\n"
            f"1. Probabilite pump (0-100%) et temps estime\n"
            f"2. Niveau entree optimal, TP et SL en USDT\n"
            f"3. Risque principal"
        )

        ai_score = 0
        ai_text = ""
        pump_prob = 0.0
        pump_eta = 999

        try:
            r = await client.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": "qwen3:1.7b",
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"num_gpu": 99},
                },
                timeout=30,
            )
            data = r.json()
            ai_text = data.get("message", {}).get("content", "")

            # Extraire la probabilite pump du texte IA
            import re
            prob_match = re.search(r'(\d{1,3})\s*%', ai_text)
            if prob_match:
                pump_prob = min(100, int(prob_match.group(1)))

            # Estimer le temps
            time_match = re.search(r'(\d+)\s*(min|h|heure)', ai_text, re.IGNORECASE)
            if time_match:
                val = int(time_match.group(1))
                unit = time_match.group(2).lower()
                pump_eta = val if 'min' in unit else val * 60

            # Score IA base sur la probabilite
            ai_score = int(pump_prob * 0.8)
            if pump_eta < 30:
                ai_score += 20
            elif pump_eta < 60:
                ai_score += 10
            ai_score = min(100, ai_score)

        except Exception as e:
            ai_text = f"Erreur IA: {e}"
            ai_score = coin["score"]  # fallback au score technique
            pump_prob = coin["score"]
            pump_eta = 120

        # Score final pondéré
        score_final = int(coin["score"] * 0.4 + ai_score * 0.6)

        # Prix entree/TP/SL
        lp = coin["last_price"]
        decimals = _price_decimals(lp)
        if coin["direction"] == "LONG":
            entry = round(lp * 0.999, decimals)
            tp = round(entry * (1 + TP_PCT), decimals)
            sl = round(entry * (1 - SL_PCT), decimals)
        else:
            entry = round(lp * 1.001, decimals)
            tp = round(entry * (1 - TP_PCT), decimals)
            sl = round(entry * (1 + SL_PCT), decimals)

        # Classification watchlist
        if pump_prob >= 80 and pump_eta <= 15:
            wl_tier = "IMMINENT"
        elif pump_prob >= 60 and pump_eta <= 60:
            wl_tier = "1h"
        elif pump_prob >= 40:
            wl_tier = "2h+"
        else:
            wl_tier = "surveillance"

        return CoinAnalysis(
            symbol=coin["symbol"],
            tier=coin["tier"],
            direction=coin["direction"],
            score_technical=coin["score"],
            score_ai=ai_score,
            score_final=score_final,
            pump_probability=pump_prob,
            pump_eta_minutes=pump_eta,
            last_price=lp,
            entry=entry,
            tp=tp,
            sl=sl,
            reasons=coin["reasons"],
            ai_analysis=ai_text[:500],
            watchlist_tier=wl_tier,
            gpu_worker=GPU_WORKERS[gpu_idx % len(GPU_WORKERS)],
            timestamp=datetime.now().isoformat(),
        )

    # Distribuer sur les 3 GPU workers (round-robin)
    tasks = [analyze_with_ai(coin, i) for i, coin in enumerate(coins)]
    return await asyncio.gather(*tasks)


def _price_decimals(price: float) -> int:
    if price > 1000: return 1
    elif price > 10: return 2
    elif price > 1: return 3
    elif price > 0.01: return 5
    else: return 8


# === PHASE 3: Classification & Output ===

def classify_and_display(analyses: list[CoinAnalysis], output_json: bool = False):
    """Phase 3: Trie, classifie et affiche les resultats."""
    analyses.sort(key=lambda a: a.score_final, reverse=True)

    if output_json:
        print(json.dumps([asdict(a) for a in analyses], indent=2, ensure_ascii=False))
        return

    now = datetime.now().strftime("%H:%M:%S")
    print(f"\n{'='*60}")
    print(f"  GPU TRADING PIPELINE — {now}")
    print(f"  GPU: 3080(detect) + 3x1660S(analyse) + 2060(orchestre)")
    print(f"{'='*60}")

    # Grouper par watchlist tier
    imminent = [a for a in analyses if a.watchlist_tier == "IMMINENT"]
    short_term = [a for a in analyses if a.watchlist_tier == "1h"]
    medium_term = [a for a in analyses if a.watchlist_tier == "2h+"]
    watch = [a for a in analyses if a.watchlist_tier == "surveillance"]

    if imminent:
        print(f"\n  [!!!] PUMP IMMINENT (<15 min)")
        print(f"  {'-'*50}")
        for a in imminent:
            _print_signal(a)

    if short_term:
        print(f"\n  [!!] COURT TERME (<1h)")
        print(f"  {'-'*50}")
        for a in short_term:
            _print_signal(a)

    if medium_term:
        print(f"\n  [!] MOYEN TERME (2h+)")
        print(f"  {'-'*50}")
        for a in medium_term:
            _print_signal(a)

    if watch:
        print(f"\n  [...] SURVEILLANCE")
        print(f"  {'-'*50}")
        for a in watch:
            coin = a.symbol.replace("_USDT", "")
            print(f"    {coin:8} | Score {a.score_final:3}/100 | {a.direction} | {a.tier}")

    actionable = [a for a in analyses if a.score_final >= SIGNAL_SCORE]
    print(f"\n  {'-'*50}")
    print(f"  Total: {len(analyses)} coins analyses | {len(actionable)} signaux actionnables (>={SIGNAL_SCORE})")
    print(f"  Config: Levier {LEVERAGE}x | TP {TP_PCT*100:.1f}% | SL {SL_PCT*100:.2f}% | Taille {SIZE_USDT} USDT")
    print(f"{'='*60}\n")


def _print_signal(a: CoinAnalysis):
    coin = a.symbol.replace("_USDT", "")
    pump_str = f"{a.pump_probability:.0f}%" if a.pump_probability > 0 else "?"
    eta_str = f"{a.pump_eta_minutes}min" if a.pump_eta_minutes < 999 else "?"
    print(f"    {coin:8} | {a.direction:5} | Score {a.score_final:3}/100 | "
          f"Pump {pump_str} ~{eta_str} | {a.tier}")
    print(f"             Entree: {a.entry} | TP: {a.tp} | SL: {a.sl}")
    if a.reasons:
        print(f"             Signaux: {', '.join(a.reasons[:3])}")
    if a.ai_analysis:
        # Premiere ligne de l'analyse IA
        first_line = a.ai_analysis.split('\n')[0][:80]
        print(f"             IA: {first_line}")
    print()


# === MAIN ===

async def run_pipeline(cycles: int = 1, interval: int = 60, top_n: int = 10,
                       output_json: bool = False):
    """Execute le pipeline complet sur N cycles."""
    for cycle in range(1, cycles + 1):
        t0 = time.time()

        if not output_json:
            print(f"\n  Cycle {cycle}/{cycles} — Scan en cours...")

        async with httpx.AsyncClient() as client:
            # Phase 1: Detection rapide
            detected = await phase1_detect(client)

            if not output_json:
                print(f"  Phase 1: {len(detected)} coins detectes (score >= {MIN_SCORE})")

            # Trier par score et limiter
            detected.sort(key=lambda d: d["score"], reverse=True)
            detected = detected[:top_n]

            # Phase 2: Analyse fine IA
            analyses = await phase2_ai_analysis(client, detected)

            if not output_json:
                elapsed = time.time() - t0
                print(f"  Phase 2: {len(analyses)} analyses IA completees ({elapsed:.1f}s)")

        # Phase 3: Classification et affichage
        classify_and_display(analyses, output_json)

        # Sauvegarder en JSON
        if analyses:
            save_path = f"F:/BUREAU/turbo/data/pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            try:
                with open(save_path, "w", encoding="utf-8") as f:
                    json.dump([asdict(a) for a in analyses], f, indent=2, ensure_ascii=False)
                if not output_json:
                    print(f"  Sauvegarde: {save_path}")
            except Exception:
                pass

        # Pause entre cycles
        if cycle < cycles and interval > 0:
            if not output_json:
                print(f"  Prochain cycle dans {interval}s...")
            await asyncio.sleep(interval)


def main():
    args = sys.argv[1:]
    output_json = "--json" in args
    cycles = 1
    interval = 60
    top_n = 10

    for i, a in enumerate(args):
        if a == "--cycles" and i + 1 < len(args):
            cycles = int(args[i + 1])
        elif a == "--interval" and i + 1 < len(args):
            interval = int(args[i + 1])
        elif a == "--top" and i + 1 < len(args):
            top_n = int(args[i + 1])

    asyncio.run(run_pipeline(cycles=cycles, interval=interval, top_n=top_n,
                             output_json=output_json))


if __name__ == "__main__":
    main()
