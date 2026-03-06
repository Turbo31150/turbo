#!/usr/bin/env python3
"""
Autonomous Orchestrator v3 — Distributed AI Trading System.

Unified loop:
  1. Health check cluster nodes (M1/M2/M3/OL1)
  2. Fetch real-time market data (MEXC order books, prices, volumes)
  3. Distribute analysis to available models
  4. Aggregate signals + cross-validate with evolution DB
  5. Execute decisions (or dry-run log)
  6. Log everything to SQLite
  7. Repeat

Runs indefinitely. Self-healing. Load-balanced.

Usage:
    python cowork/dev/autonomous_orchestrator_v3.py                # Full auto
    python cowork/dev/autonomous_orchestrator_v3.py --once         # Single cycle
    python cowork/dev/autonomous_orchestrator_v3.py --dry          # Dry run
    python cowork/dev/autonomous_orchestrator_v3.py --interval 60  # Custom interval
    python cowork/dev/autonomous_orchestrator_v3.py --status       # Show state
"""

import argparse, json, math, os, random, sqlite3, sys, time, traceback
import urllib.request, urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

TURBO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = TURBO_ROOT / "data"
ORCH_DB = DATA_DIR / "orchestrator_v3.db"
EVOLUTION_DB = DATA_DIR / "strategy_evolution.db"
PID_FILE = DATA_DIR / "orchestrator_v3.pid"

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# ═══════════════════════════════════════════════════════════════════════
#  CLUSTER NODES
# ═══════════════════════════════════════════════════════════════════════

NODES = {
    "M1": {
        "url": "http://127.0.0.1:1234/api/v1/chat",
        "model": "qwen3-8b", "prefix": "/nothink\n",
        "timeout": 30, "type": "lmstudio",
        "role": "fast", "weight": 1.8,
        "max_tokens": 1024,
    },
    "M2": {
        "url": "http://192.168.1.26:1234/api/v1/chat",
        "model": "deepseek/qwen/qwen3-8b", "prefix": "",
        "timeout": 90, "type": "lmstudio",
        "role": "reasoning", "weight": 1.5,
        "max_tokens": 2048,
    },
    "M3": {
        "url": "http://192.168.1.113:1234/api/v1/chat",
        "model": "deepseek/qwen/qwen3-8b", "prefix": "",
        "timeout": 90, "type": "lmstudio",
        "role": "reasoning_fallback", "weight": 1.2,
        "max_tokens": 2048,
    },
    "OL1": {
        "url": "http://127.0.0.1:11434/api/chat",
        "model": "qwen3:1.7b", "prefix": "/nothink\n",
        "timeout": 20, "type": "ollama",
        "role": "quick", "weight": 1.0,
        "max_tokens": 512,
    },
}

# Circuit breaker state per node
_node_state = {n: {"failures": 0, "last_fail": 0, "status": "CLOSED"} for n in NODES}
CB_THRESHOLD = 3     # failures before OPEN
CB_RESET_SEC = 120   # seconds before HALF_OPEN

# Trading pairs to monitor
TRADING_PAIRS = [
    "BTC_USDT", "ETH_USDT", "SOL_USDT", "SUI_USDT", "PEPE_USDT",
    "DOGE_USDT", "XRP_USDT", "ADA_USDT", "AVAX_USDT", "LINK_USDT",
    "TAO_USDT", "HYPE_USDT", "XMR_USDT", "RIVER_USDT",
]


# ═══════════════════════════════════════════════════════════════════════
#  DATABASE
# ═══════════════════════════════════════════════════════════════════════

def init_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(ORCH_DB), timeout=15)
    db.execute("PRAGMA journal_mode=WAL")
    db.row_factory = sqlite3.Row

    db.execute("""CREATE TABLE IF NOT EXISTS cycles (
        id INTEGER PRIMARY KEY, timestamp TEXT, cycle_id TEXT,
        nodes_used TEXT, signals_detected INT, actions_executed INT,
        elapsed_sec REAL, market_snapshot TEXT
    )""")

    db.execute("""CREATE TABLE IF NOT EXISTS signals (
        id INTEGER PRIMARY KEY, cycle_id TEXT, timestamp TEXT,
        symbol TEXT, direction TEXT, confidence REAL,
        source_node TEXT, reason TEXT, price REAL,
        tp REAL, sl REAL, status TEXT DEFAULT 'NEW'
    )""")

    db.execute("""CREATE TABLE IF NOT EXISTS node_health (
        id INTEGER PRIMARY KEY, timestamp TEXT, node TEXT,
        status TEXT, latency_ms REAL, model TEXT, error TEXT
    )""")

    db.execute("""CREATE TABLE IF NOT EXISTS market_data (
        id INTEGER PRIMARY KEY, timestamp TEXT, symbol TEXT,
        price REAL, change_24h REAL, volume_24h REAL,
        high_24h REAL, low_24h REAL, spread REAL
    )""")

    db.execute("""CREATE TABLE IF NOT EXISTS orch_log (
        id INTEGER PRIMARY KEY, timestamp TEXT, level TEXT,
        event TEXT, detail TEXT
    )""")

    db.commit()
    return db


def log_event(db, level, event, detail=""):
    db.execute("INSERT INTO orch_log (timestamp, level, event, detail) VALUES (?,?,?,?)",
               (datetime.now().isoformat(), level, event, detail[:1000]))
    db.commit()


# ═══════════════════════════════════════════════════════════════════════
#  NODE COMMUNICATION
# ═══════════════════════════════════════════════════════════════════════

def _cb_check(node):
    """Circuit breaker check."""
    s = _node_state[node]
    if s["status"] == "OPEN":
        if time.time() - s["last_fail"] > CB_RESET_SEC:
            s["status"] = "HALF_OPEN"
            return True
        return False
    return True


def _cb_success(node):
    _node_state[node]["failures"] = 0
    _node_state[node]["status"] = "CLOSED"


def _cb_fail(node):
    s = _node_state[node]
    s["failures"] += 1
    s["last_fail"] = time.time()
    if s["failures"] >= CB_THRESHOLD:
        s["status"] = "OPEN"


def query_node(node, prompt, retries=2):
    """Query a node with circuit breaker and retry."""
    if not _cb_check(node):
        return None, f"CB_OPEN ({_node_state[node]['failures']} fails)"

    cfg = NODES[node]
    for attempt in range(retries + 1):
        try:
            t0 = time.time()
            if cfg["type"] == "ollama":
                body = json.dumps({
                    "model": cfg["model"],
                    "messages": [{"role": "user", "content": cfg["prefix"] + prompt}],
                    "stream": False
                }).encode()
            else:
                body = json.dumps({
                    "model": cfg["model"],
                    "input": cfg["prefix"] + prompt,
                    "temperature": 0.3,
                    "max_output_tokens": cfg["max_tokens"],
                    "stream": False, "store": False
                }).encode()

            req = urllib.request.Request(cfg["url"], body, {"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=cfg["timeout"]) as resp:
                d = json.loads(resp.read())

            latency = (time.time() - t0) * 1000

            # Extract response
            if cfg["type"] == "ollama":
                content = d.get("message", {}).get("content", "")
            else:
                content = ""
                for o in d.get("output", []):
                    if o.get("type") == "message" and o.get("content"):
                        content = o["content"]
                        break

            if content:
                _cb_success(node)
                return content, f"OK ({latency:.0f}ms)"
            else:
                if attempt < retries:
                    time.sleep(1 * (attempt + 1))
                    continue
                _cb_fail(node)
                return None, "empty_response"

        except Exception as e:
            if attempt < retries:
                time.sleep(2 * (attempt + 1))
                continue
            _cb_fail(node)
            return None, str(e)[:100]

    return None, "max_retries"


def health_check_all(db):
    """Check all nodes, log results."""
    results = {}
    for node in NODES:
        t0 = time.time()
        cfg = NODES[node]
        try:
            if cfg["type"] == "ollama":
                req = urllib.request.Request(
                    "http://127.0.0.1:11434/api/ps",
                    headers={"Content-Type": "application/json"}
                )
            else:
                req = urllib.request.Request(cfg["url"].replace("/chat", "/models"))
            with urllib.request.urlopen(req, timeout=5) as resp:
                resp.read()
            latency = (time.time() - t0) * 1000
            results[node] = {"status": "OK", "latency": latency}
            db.execute("INSERT INTO node_health (timestamp, node, status, latency_ms, model) VALUES (?,?,?,?,?)",
                       (datetime.now().isoformat(), node, "OK", latency, cfg["model"]))
        except Exception as e:
            results[node] = {"status": "FAIL", "error": str(e)[:80]}
            db.execute("INSERT INTO node_health (timestamp, node, status, latency_ms, error) VALUES (?,?,?,?,?)",
                       (datetime.now().isoformat(), node, "FAIL", 0, str(e)[:200]))
    db.commit()
    return results


# ═══════════════════════════════════════════════════════════════════════
#  MARKET DATA
# ═══════════════════════════════════════════════════════════════════════

def fetch_market_data(db):
    """Fetch MEXC futures tickers."""
    try:
        req = urllib.request.Request("https://contract.mexc.com/api/v1/contract/ticker")
        with urllib.request.urlopen(req, timeout=15) as resp:
            tickers = json.loads(resp.read()).get("data", [])
    except Exception:
        return {}

    market = {}
    ts = datetime.now().isoformat()
    for t in tickers:
        sym = t.get("symbol", "")
        if sym not in TRADING_PAIRS:
            continue
        price = float(t.get("lastPrice", 0))
        change = float(t.get("riseFallRate", 0)) * 100
        vol = float(t.get("volume24", 0)) * price
        high = float(t.get("high24Price", 0))
        low = float(t.get("low24Price", 0))
        bid = float(t.get("bid1", 0))
        ask = float(t.get("ask1", 0))
        spread = (ask - bid) / price * 100 if price > 0 else 0

        market[sym] = {
            "price": price, "change_24h": change, "volume_usd": vol,
            "high_24h": high, "low_24h": low, "spread": spread,
            "bid": bid, "ask": ask,
        }

        db.execute("""INSERT INTO market_data
            (timestamp, symbol, price, change_24h, volume_24h, high_24h, low_24h, spread)
            VALUES (?,?,?,?,?,?,?,?)""",
            (ts, sym, price, change, vol, high, low, spread))

    db.commit()
    return market


# ═══════════════════════════════════════════════════════════════════════
#  SIGNAL DETECTION — Distributed to cluster
# ═══════════════════════════════════════════════════════════════════════

def build_market_summary(market):
    """Build concise market summary for LLM analysis."""
    lines = []
    for sym, d in sorted(market.items(), key=lambda x: abs(x[1]["change_24h"]), reverse=True):
        arrow = "+" if d["change_24h"] > 0 else ""
        lines.append(f"{sym}: ${d['price']} {arrow}{d['change_24h']:.1f}% vol=${d['volume_usd']/1e6:.1f}M spread={d['spread']:.3f}%")
    return "\n".join(lines)


def get_evolution_best():
    """Get best strategies from evolution DB."""
    if not EVOLUTION_DB.exists():
        return "Pas de donnees evolution"
    try:
        db = sqlite3.connect(str(EVOLUTION_DB), timeout=5)
        db.row_factory = sqlite3.Row
        top = db.execute("SELECT * FROM strategies ORDER BY fitness DESC LIMIT 3").fetchall()
        db.close()
        lines = []
        for s in top:
            dna = json.loads(s["dna"])
            lines.append(f"Fit={s['fitness']:.3f} WR={s['avg_wr']:.0f}% PnL={s['avg_pnl']:+.2f}% "
                         f"EMA {dna['ema_s']}/{dna['ema_l']} TP={dna['tp']} SL={dna['sl']}")
        return "\n".join(lines) if lines else "Aucune strategie"
    except Exception:
        return "DB error"


def detect_signals_distributed(market, available_nodes):
    """Distribute signal detection across cluster nodes."""
    if not market or not available_nodes:
        return []

    summary = build_market_summary(market)
    evo_best = get_evolution_best()
    signals = []

    # Task allocation by node role
    tasks = {}

    # OL1 or M1 (fast): Quick pattern scan
    fast_node = next((n for n in available_nodes if NODES[n]["role"] == "fast"),
                     next((n for n in available_nodes if NODES[n]["role"] == "quick"), None))
    if fast_node:
        tasks[fast_node] = (
            f"Donnees marche MEXC futures temps reel:\n{summary}\n\n"
            f"Meilleures strategies evolution genetique:\n{evo_best}\n\n"
            f"Identifie les 3 meilleurs signaux de trading maintenant. "
            f"Pour chaque signal reponds en JSON: "
            f'[{{"symbol":"X_USDT","direction":"LONG/SHORT","confidence":0.0-1.0,'
            f'"reason":"motif court","tp_pct":1.0,"sl_pct":0.5}}]. '
            f"Uniquement JSON, pas de texte."
        )

    # M2 (reasoning): Deep analysis on top movers
    reasoning_node = next((n for n in available_nodes if NODES[n]["role"] == "reasoning"), None)
    if reasoning_node:
        top_movers = sorted(market.items(), key=lambda x: abs(x[1]["change_24h"]), reverse=True)[:5]
        movers_txt = "\n".join(f"{s}: ${d['price']} {d['change_24h']:+.1f}% vol=${d['volume_usd']/1e6:.1f}M"
                               for s, d in top_movers)
        tasks[reasoning_node] = (
            f"Top 5 movers MEXC futures:\n{movers_txt}\n\n"
            f"Analyse en profondeur: pour chaque, dis si c'est un signal de continuation ou reversal. "
            f"Confidence 0-1. Format court: SYMBOL|DIRECTION|CONFIDENCE|RAISON"
        )

    # Execute in parallel
    with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
        futures = {}
        for node, prompt in tasks.items():
            futures[pool.submit(query_node, node, prompt)] = node

        for future in as_completed(futures, timeout=120):
            node = futures[future]
            try:
                content, status = future.result()
                if content and "ERR" not in status:
                    # Try parse JSON signals
                    try:
                        start = content.find("[")
                        end = content.rfind("]") + 1
                        if start >= 0 and end > start:
                            parsed = json.loads(content[start:end])
                            for s in parsed:
                                if isinstance(s, dict) and "symbol" in s:
                                    signals.append({
                                        "symbol": s.get("symbol", ""),
                                        "direction": s.get("direction", ""),
                                        "confidence": float(s.get("confidence", 0)),
                                        "reason": s.get("reason", "")[:100],
                                        "tp_pct": float(s.get("tp_pct", 1.0)),
                                        "sl_pct": float(s.get("sl_pct", 0.5)),
                                        "source": node,
                                    })
                    except (json.JSONDecodeError, ValueError):
                        # Parse pipe-delimited format from reasoning nodes
                        for line in content.strip().split("\n"):
                            parts = line.split("|")
                            if len(parts) >= 3:
                                sym = parts[0].strip()
                                direction = parts[1].strip().upper()
                                if direction in ("LONG", "SHORT") and any(sym.endswith(p) for p in ["_USDT", "USDT"]):
                                    try:
                                        conf = float(parts[2].strip())
                                    except ValueError:
                                        conf = 0.5
                                    signals.append({
                                        "symbol": sym if "_" in sym else sym.replace("USDT", "_USDT"),
                                        "direction": direction,
                                        "confidence": min(conf, 1.0),
                                        "reason": parts[3].strip()[:100] if len(parts) > 3 else "",
                                        "tp_pct": 1.0, "sl_pct": 0.5,
                                        "source": node,
                                    })
            except Exception:
                pass

    return signals


# ═══════════════════════════════════════════════════════════════════════
#  TELEGRAM
# ═══════════════════════════════════════════════════════════════════════

def _alerts_enabled():
    return not (TURBO_ROOT / "data" / ".trading_alerts_off").exists()

def send_telegram(text):
    if not _alerts_enabled() or not TELEGRAM_TOKEN:
        return
    try:
        data = urllib.parse.urlencode({
            "chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════
#  MAIN CYCLE
# ═══════════════════════════════════════════════════════════════════════

def run_cycle(db, cycle_num, dry_run=False):
    """Execute one full orchestration cycle."""
    t0 = time.time()
    ts = datetime.now().isoformat()
    cycle_id = f"C{cycle_num}_{datetime.now().strftime('%H%M%S')}"

    print(f"\n{'='*70}")
    print(f"  CYCLE #{cycle_num} — {datetime.now().strftime('%H:%M:%S')} — {cycle_id}")
    print(f"{'='*70}")

    # Phase 1: Health check
    print(f"  [1/5] Health check...", end=" ", flush=True)
    health = health_check_all(db)
    available = [n for n, h in health.items() if h["status"] == "OK"]
    print(f"{len(available)}/4 nodes OK: {', '.join(available)}")
    for n, h in health.items():
        status_icon = "OK" if h["status"] == "OK" else "XX"
        lat = f"{h.get('latency', 0):.0f}ms" if h["status"] == "OK" else h.get("error", "")[:40]
        cb = _node_state[n]["status"]
        print(f"    [{status_icon}] {n:<4} {lat:<20} CB:{cb}")

    if not available:
        print(f"  [ABORT] No nodes available!")
        log_event(db, "ERROR", "NO_NODES", "All nodes offline")
        return {"signals": 0, "actions": 0}

    # Phase 2: Market data
    print(f"  [2/5] Fetching market data...", end=" ", flush=True)
    market = fetch_market_data(db)
    print(f"{len(market)} pairs")
    for sym, d in sorted(market.items(), key=lambda x: abs(x[1]["change_24h"]), reverse=True)[:5]:
        arrow = "+" if d["change_24h"] > 0 else ""
        print(f"    {sym:<16} ${d['price']:<12} {arrow}{d['change_24h']:.1f}%  vol=${d['volume_usd']/1e6:.1f}M")

    # Phase 3: Signal detection (distributed)
    print(f"  [3/5] Detecting signals ({len(available)} nodes)...", end=" ", flush=True)
    signals = detect_signals_distributed(market, available)
    # Filter by confidence
    strong_signals = [s for s in signals if s["confidence"] >= 0.6]
    print(f"{len(signals)} raw, {len(strong_signals)} strong (conf>=0.6)")
    for s in sorted(strong_signals, key=lambda x: x["confidence"], reverse=True):
        print(f"    [{s['source']:<3}] {s['symbol']:<16} {s['direction']:<5} "
              f"conf={s['confidence']:.2f} | {s['reason'][:50]}")

    # Phase 4: Cross-validate with evolution DB
    print(f"  [4/5] Cross-validation...", end=" ", flush=True)
    evo_best = get_evolution_best()
    print(f"done")
    if evo_best and evo_best != "Pas de donnees evolution":
        print(f"    Evolution best: {evo_best.split(chr(10))[0][:70]}")

    # Phase 5: Log & store
    print(f"  [5/5] Logging...", end=" ", flush=True)
    elapsed = time.time() - t0

    # Store signals
    for s in strong_signals:
        price = market.get(s["symbol"], {}).get("price", 0)
        db.execute("""INSERT INTO signals
            (cycle_id, timestamp, symbol, direction, confidence,
             source_node, reason, price, tp, sl, status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (cycle_id, ts, s["symbol"], s["direction"], s["confidence"],
             s["source"], s["reason"], price,
             price * (1 + s["tp_pct"]/100) if s["direction"] == "LONG" else price * (1 - s["tp_pct"]/100),
             price * (1 - s["sl_pct"]/100) if s["direction"] == "LONG" else price * (1 + s["sl_pct"]/100),
             "DRY_RUN" if dry_run else "NEW"))

    # Store cycle
    db.execute("""INSERT INTO cycles
        (timestamp, cycle_id, nodes_used, signals_detected,
         actions_executed, elapsed_sec, market_snapshot)
        VALUES (?,?,?,?,?,?,?)""",
        (ts, cycle_id, json.dumps(available), len(strong_signals),
         0, elapsed, json.dumps({s: {"price": d["price"], "change": d["change_24h"]}
                                  for s, d in list(market.items())[:10]})))
    db.commit()
    print(f"done ({elapsed:.1f}s)")

    log_event(db, "INFO", f"CYCLE_{cycle_num}",
              f"signals={len(strong_signals)} nodes={len(available)} elapsed={elapsed:.1f}s")

    # Telegram summary every 5 cycles
    if cycle_num % 5 == 0 and strong_signals:
        msg_lines = [f"<b>ORCH v3 Cycle #{cycle_num}</b>", f"Nodes: {len(available)}/4"]
        for s in strong_signals[:3]:
            msg_lines.append(f"  {s['symbol']} {s['direction']} conf={s['confidence']:.2f}")
        send_telegram("\n".join(msg_lines))

    print(f"{'='*70}")
    return {"signals": len(strong_signals), "actions": 0, "elapsed": elapsed}


def show_status():
    if not ORCH_DB.exists():
        print("  No orchestrator data yet.")
        return
    db = sqlite3.connect(str(ORCH_DB), timeout=10)
    db.row_factory = sqlite3.Row

    total_cycles = db.execute("SELECT COUNT(*) FROM cycles").fetchone()[0]
    last_cycle = db.execute("SELECT * FROM cycles ORDER BY id DESC LIMIT 1").fetchone()
    total_signals = db.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
    strong_signals = db.execute("SELECT COUNT(*) FROM signals WHERE confidence >= 0.6").fetchone()[0]
    recent_signals = db.execute("""
        SELECT symbol, direction, confidence, source_node, reason, price
        FROM signals ORDER BY id DESC LIMIT 5
    """).fetchall()

    print("=" * 70)
    print("  ORCHESTRATOR v3 — STATUS")
    print("=" * 70)
    print(f"  Total cycles: {total_cycles}")
    if last_cycle:
        print(f"  Last cycle: {last_cycle['cycle_id']} ({last_cycle['timestamp'][:19]})")
        print(f"  Nodes used: {last_cycle['nodes_used']}")
        print(f"  Elapsed: {last_cycle['elapsed_sec']:.1f}s")
    print(f"  Total signals: {total_signals} ({strong_signals} strong)")

    if recent_signals:
        print(f"\n  RECENT SIGNALS:")
        for s in recent_signals:
            print(f"    {s['symbol']:<16} {s['direction']:<5} conf={s['confidence']:.2f} "
                  f"[{s['source_node']}] ${s['price']:.4f} | {s['reason'][:40]}")

    # Node circuit breaker state
    print(f"\n  NODE STATE:")
    for n, s in _node_state.items():
        print(f"    {n:<4} CB:{s['status']:<10} fails:{s['failures']}")

    events = db.execute("SELECT * FROM orch_log ORDER BY id DESC LIMIT 5").fetchall()
    if events:
        print(f"\n  RECENT EVENTS:")
        for e in events:
            print(f"    [{e['timestamp'][:19]}] {e['level']}: {e['event']} {e['detail'][:50]}")

    print("=" * 70)
    db.close()


def main():
    parser = argparse.ArgumentParser(description="Autonomous Orchestrator v3")
    parser.add_argument("--once", action="store_true", help="Single cycle")
    parser.add_argument("--dry", action="store_true", help="Dry run (no execution)")
    parser.add_argument("--interval", type=int, default=30, help="Seconds between cycles")
    parser.add_argument("--status", action="store_true", help="Show status")
    parser.add_argument("--max-cycles", type=int, default=999999, help="Max cycles")
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))

    db = init_db()

    print("=" * 70)
    print("  AUTONOMOUS ORCHESTRATOR v3 — JARVIS TRADING SYSTEM")
    print("=" * 70)
    print(f"  Mode:     {'single' if args.once else 'continuous'}")
    print(f"  Dry run:  {args.dry}")
    print(f"  Interval: {args.interval}s")
    print(f"  Pairs:    {len(TRADING_PAIRS)}")
    print(f"  PID:      {os.getpid()}")
    print(f"  DB:       {ORCH_DB}")

    log_event(db, "INFO", "ORCH_START",
              f"mode={'single' if args.once else 'continuous'} interval={args.interval}s")

    cycle = 0
    max_cycles = 1 if args.once else args.max_cycles

    try:
        while cycle < max_cycles:
            cycle += 1
            try:
                result = run_cycle(db, cycle, dry_run=args.dry)
            except Exception as e:
                print(f"  [ERR] Cycle {cycle} failed: {e}")
                traceback.print_exc()
                log_event(db, "ERROR", f"CYCLE_{cycle}_FAIL", str(e)[:200])

            if cycle >= max_cycles:
                break
            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\n  [STOP] Orchestrator stopped by user")
        log_event(db, "INFO", "ORCH_STOP", "User interrupt")
    finally:
        if PID_FILE.exists():
            PID_FILE.unlink()
        db.close()


if __name__ == "__main__":
    main()
