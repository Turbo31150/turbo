#!/usr/bin/env python3
"""Audit complet des signaux trading JARVIS — prix donnes vs prix actuels."""
import sqlite3, json, urllib.request
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "sniper_scan.db"

def fetch_prices():
    prices = {}
    try:
        req = urllib.request.Request("https://contract.mexc.com/api/v1/contract/ticker")
        with urllib.request.urlopen(req, timeout=15) as resp:
            for t in json.loads(resp.read()).get("data", []):
                prices[t["symbol"]] = float(t.get("lastPrice", 0))
    except Exception:
        pass
    try:
        req2 = urllib.request.Request("https://api.mexc.com/api/v3/ticker/price")
        with urllib.request.urlopen(req2, timeout=15) as resp2:
            for t in json.loads(resp2.read()):
                sym = t["symbol"].replace("USDT", "_USDT")
                if sym not in prices:
                    prices[sym] = float(t.get("price", 0))
    except Exception:
        pass
    return prices

def main():
    db = sqlite3.connect(str(DB))
    db.row_factory = sqlite3.Row
    prices = fetch_prices()
    print(f"Prix charges: {len(prices)} tickers MEXC")

    # ── GLOBAL STATS ──
    total = db.execute("SELECT COUNT(*) FROM signal_tracker").fetchone()[0]
    closed = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE status != 'OPEN'").fetchone()[0]
    tp1 = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE tp1_hit=1").fetchone()[0]
    tp2 = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE tp2_hit=1").fetchone()[0]
    tp3 = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE tp3_hit=1").fetchone()[0]
    sl = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE sl_hit=1").fetchone()[0]
    avg_pnl = db.execute("SELECT AVG(pnl_pct) FROM signal_tracker WHERE status != 'OPEN'").fetchone()[0] or 0
    avg_pnl_tp = db.execute("SELECT AVG(pnl_pct) FROM signal_tracker WHERE tp1_hit=1 OR tp2_hit=1 OR tp3_hit=1").fetchone()[0] or 0
    avg_pnl_sl = db.execute("SELECT AVG(pnl_pct) FROM signal_tracker WHERE sl_hit=1").fetchone()[0] or 0
    avg_score = db.execute("SELECT AVG(score) FROM signal_tracker").fetchone()[0] or 0
    avg_valid = db.execute("SELECT AVG(validations) FROM signal_tracker").fetchone()[0] or 0
    wins = tp1 + tp2 + tp3
    winrate = (wins / closed * 100) if closed > 0 else 0

    print("=" * 65)
    print("  AUDIT SIGNAUX TRADING — JARVIS SNIPER SCANNER")
    print("=" * 65)
    print(f"  Total signaux emis:     {total}")
    print(f"  Signaux clotures:       {closed}")
    print(f"  Signaux ouverts:        {total - closed}")
    print(f"  Score moyen:            {avg_score:.1f}/100")
    print(f"  Validations moyennes:   {avg_valid:.1f}")
    print()
    print(f"  TP1 touches:   {tp1:>4} ({tp1/total*100:.1f}%)")
    print(f"  TP2 touches:   {tp2:>4} ({tp2/total*100:.1f}%)")
    print(f"  TP3 touches:   {tp3:>4} ({tp3/total*100:.1f}%)")
    print(f"  SL touches:    {sl:>4} ({sl/total*100:.1f}%)")
    print()
    print(f"  WIN RATE:      {winrate:.1f}% ({wins} wins / {closed} closed)")
    print(f"  PnL moyen (clotures):   {avg_pnl:+.3f}%")
    print(f"  PnL moyen (gagnants):   {avg_pnl_tp:+.3f}%")
    print(f"  PnL moyen (perdants):   {avg_pnl_sl:+.3f}%")

    # ── BY DIRECTION ──
    print()
    print("-" * 65)
    print("  PAR DIRECTION")
    print("-" * 65)
    for d in ["LONG", "SHORT"]:
        t = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE direction=?", (d,)).fetchone()[0]
        w = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE direction=? AND (tp1_hit=1 OR tp2_hit=1 OR tp3_hit=1)", (d,)).fetchone()[0]
        l = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE direction=? AND sl_hit=1", (d,)).fetchone()[0]
        ap = db.execute("SELECT AVG(pnl_pct) FROM signal_tracker WHERE direction=? AND status != 'OPEN'", (d,)).fetchone()[0] or 0
        cl = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE direction=? AND status != 'OPEN'", (d,)).fetchone()[0]
        wr = (w / cl * 100) if cl > 0 else 0
        print(f"  {d:>5}: {t} signaux | WR: {wr:.1f}% ({w}W/{l}L) | PnL: {ap:+.3f}%")

    # ── BY SCORE BRACKET ──
    print()
    print("-" * 65)
    print("  PAR TRANCHE DE SCORE")
    print("-" * 65)
    for lo, hi in [(70, 79), (80, 89), (90, 99), (100, 100)]:
        t = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE score>=? AND score<=?", (lo, hi)).fetchone()[0]
        w = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE score>=? AND score<=? AND (tp1_hit=1 OR tp2_hit=1 OR tp3_hit=1)", (lo, hi)).fetchone()[0]
        l = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE score>=? AND score<=? AND sl_hit=1", (lo, hi)).fetchone()[0]
        cl = db.execute("SELECT COUNT(*) FROM signal_tracker WHERE score>=? AND score<=? AND status != 'OPEN'", (lo, hi)).fetchone()[0]
        ap = db.execute("SELECT AVG(pnl_pct) FROM signal_tracker WHERE score>=? AND score<=? AND status != 'OPEN'", (lo, hi)).fetchone()[0] or 0
        wr = (w / cl * 100) if cl > 0 else 0
        print(f"  Score {lo}-{hi}: {t:>3} signaux | WR: {wr:.1f}% ({w}W/{l}L/{cl}cl) | PnL: {ap:+.3f}%")

    # ── OPEN SIGNALS vs CURRENT PRICE ──
    print()
    print("-" * 65)
    print("  SIGNAUX OUVERTS vs PRIX ACTUEL")
    print("-" * 65)
    opens = db.execute(
        "SELECT id, symbol, direction, entry_price, tp1, tp2, sl, score, validations, emitted_at, pnl_pct "
        "FROM signal_tracker WHERE status='OPEN' ORDER BY id DESC"
    ).fetchall()

    total_open_pnl = 0
    matched = 0
    winning_open = 0
    losing_open = 0
    for sig in opens:
        sym = sig["symbol"]
        current = prices.get(sym, 0)
        if current == 0:
            alt = sym.replace("STOCK_USDT", "USDT").replace("_USDT", "USDT")
            current = prices.get(alt, 0)

        entry = sig["entry_price"]
        direction = sig["direction"]

        if current > 0 and entry > 0:
            if direction == "LONG":
                live_pnl = (current - entry) / entry * 100
            else:
                live_pnl = (entry - current) / entry * 100
            total_open_pnl += live_pnl
            matched += 1
            if live_pnl >= 0:
                winning_open += 1
            else:
                losing_open += 1

            tp1_ok = (current >= sig["tp1"]) if direction == "LONG" else (current <= sig["tp1"])
            sl_ok = (current <= sig["sl"]) if direction == "LONG" else (current >= sig["sl"])
            status_icon = "TP" if tp1_ok else ("SL" if sl_ok else "..")
            sign = "+" if live_pnl >= 0 else ""

            print(f"  [{status_icon}] {sym:<22} {direction:>5} | Entry: {entry:<12} Now: {current:<12} | {sign}{live_pnl:.2f}% | Sc:{sig['score']:.0f} V:{sig['validations']}")

    if matched > 0:
        print(f"\n  OPEN RESUME: {matched} positions | {winning_open} vertes / {losing_open} rouges")
        print(f"  OPEN PnL TOTAL: {total_open_pnl:+.2f}%")
        print(f"  OPEN PnL MOYEN: {total_open_pnl / matched:+.3f}%")

    # ── TOP WINNERS ──
    print()
    print("-" * 65)
    print("  TOP 5 GAGNANTS")
    print("-" * 65)
    winners = db.execute(
        "SELECT symbol, direction, entry_price, pnl_pct, score, validations, status, emitted_at "
        "FROM signal_tracker WHERE pnl_pct > 0 ORDER BY pnl_pct DESC LIMIT 5"
    ).fetchall()
    for w in winners:
        print(f"  {w['symbol']:<22} {w['direction']:>5} | Entry: {w['entry_price']} | PnL: +{w['pnl_pct']:.2f}% | {w['status']} | Sc:{w['score']:.0f}")

    # ── TOP LOSERS ──
    print()
    print("-" * 65)
    print("  TOP 5 PERDANTS")
    print("-" * 65)
    losers = db.execute(
        "SELECT symbol, direction, entry_price, pnl_pct, score, validations, status, emitted_at "
        "FROM signal_tracker WHERE pnl_pct < 0 ORDER BY pnl_pct ASC LIMIT 5"
    ).fetchall()
    for l in losers:
        print(f"  {l['symbol']:<22} {l['direction']:>5} | Entry: {l['entry_price']} | PnL: {l['pnl_pct']:.2f}% | {l['status']} | Sc:{l['score']:.0f}")

    # ── DUREE MOYENNE ──
    print()
    print("-" * 65)
    print("  DUREE MOYENNE DES SIGNAUX")
    print("-" * 65)
    durations = db.execute(
        "SELECT status, "
        "AVG(CAST((julianday(checked_at) - julianday(emitted_at)) * 24 * 60 AS REAL)) as avg_min "
        "FROM signal_tracker WHERE status != 'OPEN' GROUP BY status"
    ).fetchall()
    for d in durations:
        print(f"  {d['status']:<10}: {d['avg_min']:.1f} minutes en moyenne")

    # ── TOP SYMBOLS ──
    print()
    print("-" * 65)
    print("  TOP 10 SYMBOLES (par nombre de signaux)")
    print("-" * 65)
    syms = db.execute(
        "SELECT symbol, COUNT(*) as cnt, "
        "SUM(CASE WHEN tp1_hit=1 OR tp2_hit=1 OR tp3_hit=1 THEN 1 ELSE 0 END) as wins, "
        "SUM(CASE WHEN sl_hit=1 THEN 1 ELSE 0 END) as losses, "
        "AVG(CASE WHEN status != 'OPEN' THEN pnl_pct END) as avg_pnl "
        "FROM signal_tracker GROUP BY symbol ORDER BY cnt DESC LIMIT 10"
    ).fetchall()
    for s in syms:
        ap = s["avg_pnl"] or 0
        print(f"  {s['symbol']:<22} {s['cnt']:>3} signaux | {s['wins']}W / {s['losses']}L | PnL: {ap:+.2f}%")

    # ── VERDICT ──
    print()
    print("=" * 65)
    print("  VERDICT")
    print("=" * 65)
    if winrate >= 50:
        print(f"  Strategie PROFITABLE — WR {winrate:.1f}% > 50%")
    elif winrate >= 30:
        print(f"  Strategie MARGINALE — WR {winrate:.1f}% (entre 30-50%)")
    else:
        print(f"  Strategie PERDANTE — WR {winrate:.1f}% < 30%")

    if avg_pnl > 0:
        print(f"  PnL moyen POSITIF: {avg_pnl:+.3f}%")
    else:
        print(f"  PnL moyen NEGATIF: {avg_pnl:+.3f}% — les pertes depassent les gains")

    ratio = abs(avg_pnl_tp / avg_pnl_sl) if avg_pnl_sl != 0 else 0
    print(f"  Ratio gain/perte: {ratio:.2f}x (gains moyens vs pertes moyennes)")
    if ratio < 1:
        print("  ATTENTION: Les pertes sont plus grandes que les gains en moyenne")
    print("=" * 65)

    db.close()

if __name__ == "__main__":
    main()
