#!/usr/bin/env python3
"""
CHECK PREDICTIONS v1.0 - Verification automatique WIN/LOSS
Recupere les prix actuels MEXC, compare aux TP/SL de chaque prediction PENDING.
Marque WIN (tp1 touche), LOSS (sl touche), ou garde PENDING (ni l'un ni l'autre).

Usage:
  python check_predictions.py              # Verifier toutes les PENDING
  python check_predictions.py --force      # Re-verifier aussi les WIN/LOSS
  python check_predictions.py --dry-run    # Simuler sans modifier la DB
  python check_predictions.py --symbol BTC # Filtrer par symbol
"""
import sys
import os
import json
import sqlite3
import time
import urllib.request
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding='utf-8')

ROOT = r"F:\BUREAU\TRADING_V2_PRODUCTION"
DB_PATH = os.path.join(ROOT, "database", "trading.db")
MEXC_TICKER_URL = "https://contract.mexc.com/api/v1/contract/ticker"
MEXC_KLINE_URL = "https://contract.mexc.com/api/v1/contract/kline"

# ============================================================
# HELPERS
# ============================================================

def fetch_all_tickers():
    """Recupere tous les tickers MEXC futures en une seule requete"""
    try:
        req = urllib.request.Request(MEXC_TICKER_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        if data.get("success") and data.get("data"):
            return {t["symbol"]: float(t["lastPrice"]) for t in data["data"]}
    except Exception as e:
        print(f"  ERREUR tickers MEXC: {e}")
    return {}


def fetch_kline_high_low(symbol, interval="Min15", limit=20):
    """Recupere high/low depuis les klines pour verifier si TP/SL ont ete touches"""
    try:
        url = f"{MEXC_KLINE_URL}/{symbol}?interval={interval}&limit={limit}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        if data.get("success") and data.get("data"):
            d = data["data"]
            highs = d.get("high", [])
            lows = d.get("low", [])
            if highs and lows:
                return max(float(h) for h in highs), min(float(l) for l in lows)
    except Exception:
        pass
    return None, None


def check_single_prediction(pred, current_price, kline_high, kline_low):
    """
    Verifie une prediction contre le prix actuel ET les klines high/low.
    Retourne (result, hit_tp1, hit_tp2, hit_sl, pnl_pct, price_check)
    """
    direction = pred["direction"]
    entry = pred["entry_price"]
    tp1 = pred["tp1"]
    tp2 = pred["tp2"]
    sl = pred["sl"]

    if not entry or not tp1 or not sl:
        return None, False, False, False, None, current_price

    # Prix extreme atteint (klines ou current)
    if direction == "LONG":
        highest = max(current_price, kline_high or current_price)
        lowest = min(current_price, kline_low or current_price)
        hit_tp1 = highest >= tp1
        hit_tp2 = highest >= tp2 if tp2 else False
        hit_sl = lowest <= sl
        pnl_pct = ((current_price - entry) / entry) * 100
    elif direction == "SHORT":
        highest = max(current_price, kline_high or current_price)
        lowest = min(current_price, kline_low or current_price)
        hit_tp1 = lowest <= tp1
        hit_tp2 = lowest <= tp2 if tp2 else False
        hit_sl = highest >= sl
        pnl_pct = ((entry - current_price) / entry) * 100
    else:
        return None, False, False, False, None, current_price

    # Determination du resultat
    if hit_sl and not hit_tp1:
        result = "LOSS"
    elif hit_tp1:
        result = "WIN"
    elif hit_sl and hit_tp1:
        # TP1 touche avant SL (on considere WIN partiel)
        result = "WIN"
    else:
        # Ni TP ni SL touche
        # Verifier si la prediction est vieille (>4h) et le prix a bouge
        result = None  # Reste PENDING

    return result, hit_tp1, hit_tp2, hit_sl, round(pnl_pct, 2), current_price


# ============================================================
# MAIN
# ============================================================

def main():
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    force = "--force" in args
    symbol_filter = None
    if "--symbol" in args:
        idx = args.index("--symbol")
        if idx + 1 < len(args):
            symbol_filter = args[idx + 1].upper()
            if not symbol_filter.endswith("_USDT"):
                symbol_filter += "_USDT"

    print("=" * 60)
    print("  CHECK PREDICTIONS v1.0")
    print(f"  Mode: {'DRY-RUN' if dry_run else 'LIVE'} | Force: {force}")
    if symbol_filter:
        print(f"  Filtre: {symbol_filter}")
    print("=" * 60)

    # 1. Charger les predictions
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if force:
        query = "SELECT * FROM predictions ORDER BY id"
    else:
        query = "SELECT * FROM predictions WHERE result = 'PENDING' ORDER BY id"

    if symbol_filter:
        query = query.replace("ORDER BY", f"AND symbol = '{symbol_filter}' ORDER BY")

    predictions = [dict(r) for r in cur.execute(query).fetchall()]
    print(f"\n  Predictions a verifier: {len(predictions)}")

    if not predictions:
        print("  Rien a verifier.")
        conn.close()
        return

    # 2. Recuperer les prix actuels MEXC
    print("  Recuperation des prix MEXC...")
    tickers = fetch_all_tickers()
    print(f"  {len(tickers)} tickers recuperes")

    if not tickers:
        print("  ERREUR: Impossible de recuperer les prix. Abandon.")
        conn.close()
        return

    # 3. Collecter les symbols uniques pour les klines
    unique_symbols = set(p["symbol"] for p in predictions)
    print(f"  Symbols uniques: {len(unique_symbols)}")

    # 4. Recuperer les klines high/low par symbol (pour detecter si TP/SL touche entre les bougies)
    kline_cache = {}
    for i, sym in enumerate(unique_symbols):
        high, low = fetch_kline_high_low(sym, "Min15", 20)
        if high and low:
            kline_cache[sym] = (high, low)
        if (i + 1) % 10 == 0:
            print(f"    Klines: {i+1}/{len(unique_symbols)}...")
            time.sleep(0.2)

    print(f"  Klines recuperes: {len(kline_cache)}/{len(unique_symbols)}")

    # 5. Verifier chaque prediction
    stats = {"checked": 0, "win": 0, "loss": 0, "pending": 0, "skipped": 0, "errors": 0}

    print(f"\n{'='*60}")
    print(f"  {'#':>4} {'SYMBOL':15s} {'DIR':5s} {'CONF':>4} {'ENTRY':>10} {'NOW':>10} {'PNL%':>7} {'RESULT':8}")
    print(f"{'='*60}")

    for pred in predictions:
        sym = pred["symbol"]
        current_price = tickers.get(sym)

        if not current_price:
            stats["skipped"] += 1
            continue

        kh, kl = kline_cache.get(sym, (None, None))
        result, hit_tp1, hit_tp2, hit_sl, pnl_pct, price_check = check_single_prediction(
            pred, current_price, kh, kl
        )

        stats["checked"] += 1

        if result == "WIN":
            stats["win"] += 1
            tag = "WIN"
        elif result == "LOSS":
            stats["loss"] += 1
            tag = "LOSS"
        else:
            stats["pending"] += 1
            tag = "..."

        # Afficher seulement les WIN/LOSS (pas les pending)
        if result:
            pnl_str = f"{pnl_pct:+.2f}%" if pnl_pct is not None else "N/A"
            print(f"  {pred['id']:>4} {sym:15s} {pred['direction']:5s} {pred['confidence']:>3.0f}% "
                  f"{pred['entry_price']:>10.6f} {current_price:>10.6f} {pnl_str:>7} {tag:8}")

            # Mettre a jour la DB
            if not dry_run:
                now = datetime.now().isoformat()
                cur.execute("""
                    UPDATE predictions SET
                        result = ?,
                        hit_tp1 = ?,
                        hit_tp2 = ?,
                        hit_sl = ?,
                        pnl_pct = ?,
                        checked_at = ?
                    WHERE id = ?
                """, (result, int(hit_tp1), int(hit_tp2), int(hit_sl), pnl_pct, now, pred["id"]))

        # Update price columns meme pour PENDING
        if not dry_run and current_price:
            age_minutes = 0
            try:
                created = datetime.fromisoformat(pred["created_at"])
                age_minutes = (datetime.now() - created).total_seconds() / 60
            except Exception:
                pass

            # price_15m: si prediction a >= 15min
            updates = {}
            if age_minutes >= 15 and not pred.get("price_15m"):
                updates["price_15m"] = current_price
            if age_minutes >= 60 and not pred.get("price_1h"):
                updates["price_1h"] = current_price
            if age_minutes >= 240 and not pred.get("price_4h"):
                updates["price_4h"] = current_price

            if updates:
                set_clause = ", ".join(f"{k} = ?" for k in updates)
                cur.execute(f"UPDATE predictions SET {set_clause} WHERE id = ?",
                            list(updates.values()) + [pred["id"]])

    if not dry_run:
        conn.commit()

    conn.close()

    # 6. Resume
    total_resolved = stats["win"] + stats["loss"]
    wr = (stats["win"] / total_resolved * 100) if total_resolved > 0 else 0

    print(f"\n{'='*60}")
    print(f"  RESULTATS CHECK PREDICTIONS")
    print(f"{'='*60}")
    print(f"  Verifiees:    {stats['checked']}")
    print(f"  WIN:          {stats['win']}")
    print(f"  LOSS:         {stats['loss']}")
    print(f"  Toujours PENDING: {stats['pending']}")
    print(f"  Skipped (no price): {stats['skipped']}")
    print(f"  ---")
    print(f"  Win Rate (resolus): {wr:.1f}% ({stats['win']}/{total_resolved})")

    if not dry_run:
        print(f"\n  DB mise a jour.")
    else:
        print(f"\n  DRY-RUN: aucune modification DB.")

    # 7. Stats globales (toute la DB)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN result='LOSS' THEN 1 ELSE 0 END) as losses,
            SUM(CASE WHEN result='PENDING' THEN 1 ELSE 0 END) as pending
        FROM predictions
    """)
    r = cur.fetchone()
    total, wins, losses, pending = r
    resolved = wins + losses
    global_wr = (wins / resolved * 100) if resolved > 0 else 0

    print(f"\n{'='*60}")
    print(f"  STATS GLOBALES DB")
    print(f"{'='*60}")
    print(f"  Total predictions: {total}")
    print(f"  WIN: {wins} | LOSS: {losses} | PENDING: {pending}")
    print(f"  Win Rate Global: {global_wr:.1f}% ({wins}/{resolved})")

    # Breakdown par direction
    cur.execute("""
        SELECT direction,
            COUNT(*) as total,
            SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN result='LOSS' THEN 1 ELSE 0 END) as losses
        FROM predictions WHERE result != 'PENDING'
        GROUP BY direction
    """)
    print(f"\n  Par direction:")
    for row in cur.fetchall():
        d, t, w, l = row
        dr = (w / t * 100) if t > 0 else 0
        print(f"    {d:6s}: {w}W / {l}L = {dr:.1f}% WR ({t} resolus)")

    # Breakdown par tranche de confidence
    cur.execute("""
        SELECT
            CASE
                WHEN confidence >= 80 THEN '80-100%'
                WHEN confidence >= 70 THEN '70-79%'
                WHEN confidence >= 60 THEN '60-69%'
                ELSE '<60%'
            END as conf_range,
            COUNT(*) as total,
            SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN result='LOSS' THEN 1 ELSE 0 END) as losses
        FROM predictions WHERE result != 'PENDING'
        GROUP BY conf_range ORDER BY conf_range DESC
    """)
    print(f"\n  Par confidence:")
    for row in cur.fetchall():
        cr, t, w, l = row
        dr = (w / t * 100) if t > 0 else 0
        print(f"    {cr:8s}: {w}W / {l}L = {dr:.1f}% WR ({t} resolus)")

    conn.close()
    print(f"\n{'='*60}")
    print(f"  CHECK TERMINE")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
