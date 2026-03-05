#!/usr/bin/env python3
"""
TRIDENT STRATEGY - Execution automatique MEXC Futures
BERA (Reversal) + RESOLV (Breakout) + LSK (Agressif)
Pipeline Intensif - 10 cycles consensus
"""
import sys
import json
import time
import datetime
import urllib.request

sys.stdout.reconfigure(encoding='utf-8')

# ===================== CONFIGURATION =====================
DRY_RUN = True  # True = simulation, False = ORDRES REELS

MEXC_API_KEY = "MEXC_KEY_REDACTED"
MEXC_SECRET_KEY = "MEXC_SECRET_REDACTED"

TELEGRAM_TOKEN = "TELEGRAM_TOKEN_REDACTED"
TELEGRAM_CHAT = "2010747443"

# Taille par trade en USDT (avant levier)
SIZE_USDT = 10
LEVERAGE = 10

# ===================== TRIDENT ORDERS =====================
TRIDENT = [
    {
        "name": "BERA - REVERSAL LONG",
        "symbol": "BERA_USDT",
        "ccxt_symbol": "BERA/USDT:USDT",
        "side": "buy",
        "order_type": "limit",
        "entry": 0.4300,
        "tp": 0.4600,
        "sl": 0.4200,
        "confidence": "7/10 cycles",
        "reason": "RSI 29-38 oversold, Chaikin BUY, Funding -0.0023",
    },
    {
        "name": "RESOLV - BREAKOUT LONG",
        "symbol": "RESOLV_USDT",
        "ccxt_symbol": "RESOLV/USDT:USDT",
        "side": "buy",
        "order_type": "limit",
        "entry": 0.0890,
        "trigger": 0.0885,  # Stop-limit: entre seulement si casse 0.0885
        "tp": 0.0950,
        "sl": 0.0850,
        "confidence": "6/10 cycles",
        "reason": "RSI 55-68 sain, OB souvent BUY, breakout en cours",
    },
    {
        "name": "LSK - BREAKOUT AGRESSIF",
        "symbol": "LSK_USDT",
        "ccxt_symbol": "LSK/USDT:USDT",
        "side": "buy",
        "order_type": "limit",
        "entry": 0.1490,
        "tp": 0.1580,
        "sl": 0.1450,
        "confidence": "5/10 cycles",
        "reason": "Murs achats 1.5-4.8x BUY massif, RSI extreme",
    },
]


def send_telegram(msg):
    """Envoie message Telegram"""
    try:
        body = json.dumps({"chat_id": TELEGRAM_CHAT, "text": msg}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data=body, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=10)
        d = json.loads(resp.read())
        return d.get("result", {}).get("message_id", "?")
    except Exception as e:
        print(f"  TG ERROR: {e}")
        return "FAIL"


def get_current_price(symbol):
    """Recupere le prix actuel depuis MEXC"""
    try:
        url = f"https://contract.mexc.com/api/v1/contract/ticker?symbol={symbol}"
        req = urllib.request.urlopen(url, timeout=10)
        d = json.loads(req.read())
        return float(d["data"]["lastPrice"])
    except:
        return None


def calculate_quantity(entry_price):
    """Calcule la quantite basee sur SIZE_USDT et le prix"""
    notional = SIZE_USDT * LEVERAGE
    qty = notional / entry_price
    return round(qty, 2)


def place_order_ccxt(order):
    """Place un ordre via ccxt (mode LIVE uniquement)"""
    try:
        import ccxt
        mexc = ccxt.mexc({
            "apiKey": MEXC_API_KEY,
            "secret": MEXC_SECRET_KEY,
            "options": {"defaultType": "swap"},
        })
        mexc.load_markets()

        symbol = order["ccxt_symbol"]
        qty = calculate_quantity(order["entry"])

        # Set leverage
        try:
            mexc.set_leverage(LEVERAGE, symbol)
        except:
            pass

        # Place main order
        if order.get("trigger"):
            # Stop-limit order (RESOLV)
            params = {
                "stopPrice": order["trigger"],
                "type": "stop",
            }
            result = mexc.create_order(symbol, "limit", "buy", qty, order["entry"], params)
        else:
            # Regular limit order
            result = mexc.create_order(symbol, "limit", "buy", qty, order["entry"])

        order_id = result.get("id", "?")
        print(f"  ORDER PLACED: {symbol} | ID: {order_id} | Qty: {qty}")

        # Place TP
        try:
            mexc.create_order(symbol, "limit", "sell", qty, order["tp"],
                              {"reduceOnly": True})
            print(f"  TP SET: {order['tp']}")
        except Exception as e:
            print(f"  TP ERROR: {e}")

        # Place SL
        try:
            mexc.create_order(symbol, "stop_market", "sell", qty, None,
                              {"stopPrice": order["sl"], "reduceOnly": True})
            print(f"  SL SET: {order['sl']}")
        except Exception as e:
            print(f"  SL ERROR: {e}")

        return order_id
    except Exception as e:
        print(f"  CCXT ERROR: {e}")
        return None


def execute_trident():
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    mode = "SIMULATION" if DRY_RUN else "LIVE"

    print("=" * 60)
    print(f"  TRIDENT STRATEGY - {mode}")
    print(f"  {now}")
    print(f"  Size: {SIZE_USDT} USDT x {LEVERAGE}x = {SIZE_USDT * LEVERAGE} USDT notional/trade")
    print("=" * 60)

    tg_lines = [
        f"TRIDENT {mode} - {now}",
        f"Size: {SIZE_USDT}$ x {LEVERAGE}x = {SIZE_USDT * LEVERAGE}$ notional",
        "",
    ]

    for i, order in enumerate(TRIDENT, 1):
        print(f"\n--- #{i} {order['name']} ---")

        # Get current price
        current = get_current_price(order["symbol"])
        qty = calculate_quantity(order["entry"])
        risk_usdt = qty * abs(order["entry"] - order["sl"])
        reward_usdt = qty * abs(order["tp"] - order["entry"])
        rr = reward_usdt / risk_usdt if risk_usdt > 0 else 0

        tp_pct = (order["tp"] - order["entry"]) / order["entry"] * 100
        sl_pct = (order["sl"] - order["entry"]) / order["entry"] * 100

        print(f"  Symbol:  {order['symbol']}")
        print(f"  Current: {current}")
        print(f"  Entry:   {order['entry']}")
        print(f"  TP:      {order['tp']} ({tp_pct:+.2f}%)")
        print(f"  SL:      {order['sl']} ({sl_pct:+.2f}%)")
        print(f"  Qty:     {qty} tokens ({SIZE_USDT}$ x {LEVERAGE}x)")
        print(f"  R/R:     1:{rr:.1f}")
        print(f"  Conf:    {order['confidence']}")

        trigger_str = f" | Trigger: {order['trigger']}" if order.get("trigger") else ""
        tg_lines.append(
            f"#{i} {order['symbol']} LONG"
            f"\n  Entry: {order['entry']}{trigger_str}"
            f"\n  TP: {order['tp']} ({tp_pct:+.1f}%) | SL: {order['sl']} ({sl_pct:+.1f}%)"
            f"\n  Qty: {qty} | R/R: 1:{rr:.1f} | {order['confidence']}"
        )

        if DRY_RUN:
            print(f"  >> SIMULATION - ordre non place")
            tg_lines.append(f"  >> SIMULATION\n")
        else:
            print(f"  >> PLACEMENT ORDRE REEL...")
            oid = place_order_ccxt(order)
            status = f"OK (#{oid})" if oid else "ECHEC"
            print(f"  >> {status}")
            tg_lines.append(f"  >> {status}\n")

    # Summary
    total_risk = sum(
        calculate_quantity(o["entry"]) * abs(o["entry"] - o["sl"])
        for o in TRIDENT
    )
    total_reward = sum(
        calculate_quantity(o["entry"]) * abs(o["tp"] - o["entry"])
        for o in TRIDENT
    )

    print(f"\n{'='*60}")
    print(f"  TOTAL: 3 ordres | Risque: {total_risk:.2f}$ | Reward: {total_reward:.2f}$")
    print(f"  R/R Global: 1:{total_reward/total_risk:.1f}" if total_risk > 0 else "")
    print(f"  Mode: {mode}")
    print(f"{'='*60}")

    tg_lines.append(f"Total: Risque {total_risk:.2f}$ | Reward {total_reward:.2f}$")
    if total_risk > 0:
        tg_lines.append(f"R/R Global: 1:{total_reward/total_risk:.1f}")

    # Send Telegram
    mid = send_telegram("\n".join(tg_lines))
    print(f"\nTelegram: #{mid}")

    if DRY_RUN:
        print("\n>>> Pour passer en LIVE, change DRY_RUN = False dans le script")
        print(">>> Puis relance: python execute_trident.py")


if __name__ == "__main__":
    # Override DRY_RUN via argument: python execute_trident.py --live
    if "--live" in sys.argv:
        DRY_RUN = False
        print("!!! MODE LIVE ACTIVE !!!")
        confirm = input("Confirmer execution REELLE ? (oui/non): ")
        if confirm.lower() != "oui":
            print("Annule.")
            sys.exit(0)

    execute_trident()
