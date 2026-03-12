#!/usr/bin/env python3
"""
Strategy Evolution Loop — Autonomous self-improving trading strategy engine.

Genetic algorithm approach:
1. Seed population: 1000+ strategies (base 336 + mutations + crossovers)
2. Scan coins → evaluate fitness (PnL, WR, Sharpe proxy)
3. Selection: keep top 30%, kill bottom 30%
4. Mutation: tweak parameters of survivors
5. Crossover: combine winning strategies
6. Repeat — each generation improves

Runs as a continuous background service. Self-launches, self-improves.

Usage:
    python cowork/dev/strategy_evolution_loop.py                  # Full evolution loop
    python cowork/dev/strategy_evolution_loop.py --generations 10  # N generations
    python cowork/dev/strategy_evolution_loop.py --pop 500         # Population size
    python cowork/dev/strategy_evolution_loop.py --once            # Single generation
    python cowork/dev/strategy_evolution_loop.py --status          # Show current state

Stdlib-only. No external dependencies.
"""

import argparse, json, math, os, random, sqlite3, sys, time, urllib.request, urllib.parse
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

SCRIPT_DIR = Path(__file__).resolve().parent
TURBO_ROOT = SCRIPT_DIR.parent.parent
DATA_DIR = TURBO_ROOT / "data"
DB_PATH = DATA_DIR / "strategy_lab.db"
EVOLUTION_DB = DATA_DIR / "strategy_evolution.db"
PID_FILE = DATA_DIR / "evolution_loop.pid"
LOG_FILE = DATA_DIR / "evolution_loop.log"

# Import engine from multi_strategy_scanner
sys.path.insert(0, str(TURBO_ROOT / "scripts"))
from multi_strategy_scanner import (
    precompute_indicators, run_single_strategy, fetch_klines,
    assess_coin_quality, fetch_top_coins, init_db as init_scanner_db,
    ema, sma, rsi, stochastic, atr, macd, bollinger, vwap_calc, adx_calc, obv_calc
)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# ═══════════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════

DEFAULT_POP_SIZE = 1000          # Population size
MAX_GENERATIONS = 999            # Unlimited by default
SCAN_INTERVAL_MIN = 30           # Minutes between full scans
COINS_PER_GEN = 25               # Coins to test per generation
CANDLES = 2000                   # 1min candles per coin
ELITE_PCT = 0.10                 # Top 10% survive unchanged
SURVIVOR_PCT = 0.30              # Top 30% reproduce
MUTATION_RATE = 0.3              # 30% chance to mutate each param
CROSSOVER_RATE = 0.4             # 40% of new pop from crossover
MIN_TRADES_VALID = 5             # Min trades for fitness eval
FITNESS_WR_WEIGHT = 0.4          # WR contribution to fitness
FITNESS_PNL_WEIGHT = 0.4         # PnL contribution
FITNESS_SHARPE_WEIGHT = 0.2      # Sharpe proxy contribution


# ═══════════════════════════════════════════════════════════════════════
#  DATABASE
# ═══════════════════════════════════════════════════════════════════════

def init_evolution_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(EVOLUTION_DB), timeout=15)
    db.execute("PRAGMA journal_mode=WAL")
    db.row_factory = sqlite3.Row

    db.execute("""CREATE TABLE IF NOT EXISTS generations (
        id INTEGER PRIMARY KEY, timestamp TEXT, generation INT,
        pop_size INT, coins_tested INT, avg_fitness REAL,
        best_fitness REAL, best_strategy TEXT, best_wr REAL, best_pnl REAL,
        mutations INT, crossovers INT, elapsed_sec REAL
    )""")

    db.execute("""CREATE TABLE IF NOT EXISTS strategies (
        id INTEGER PRIMARY KEY, gen_born INT, gen_last_seen INT,
        name TEXT, dna TEXT, fitness REAL, total_evals INT,
        avg_wr REAL, avg_pnl REAL, best_coin TEXT, best_pnl_coin REAL,
        alive INTEGER DEFAULT 1, lineage TEXT
    )""")

    db.execute("""CREATE TABLE IF NOT EXISTS eval_results (
        id INTEGER PRIMARY KEY, gen_id INT, strategy_id INT,
        symbol TEXT, trades INT, wins INT, wr REAL, pnl REAL,
        avg_bars REAL, long_wr REAL, short_wr REAL, fitness REAL
    )""")

    db.execute("""CREATE TABLE IF NOT EXISTS coin_performance (
        symbol TEXT PRIMARY KEY, total_evals INT, avg_best_pnl REAL,
        avg_volatility REAL, last_grade TEXT, last_scan TEXT
    )""")

    db.execute("""CREATE TABLE IF NOT EXISTS evolution_log (
        id INTEGER PRIMARY KEY, timestamp TEXT, event TEXT, detail TEXT
    )""")

    db.commit()
    return db


def log_event(db, event, detail=""):
    db.execute("INSERT INTO evolution_log (timestamp, event, detail) VALUES (?,?,?)",
               (datetime.now().isoformat(), event, detail[:500]))
    db.commit()


# ═══════════════════════════════════════════════════════════════════════
#  TELEGRAM
# ═══════════════════════════════════════════════════════════════════════

def _alerts_enabled():
    return not (TURBO_ROOT / "data" / ".trading_alerts_off").exists()

def send_telegram(text):
    if not _alerts_enabled():
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
        try:
            data2 = urllib.parse.urlencode({"chat_id": TELEGRAM_CHAT_ID, "text": text}).encode()
            req2 = urllib.request.Request(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data2
            )
            urllib.request.urlopen(req2, timeout=10)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════
#  GENETIC DNA — Strategy Genome
# ═══════════════════════════════════════════════════════════════════════

# Parameter ranges for mutation
PARAM_RANGES = {
    "ema_s":     (2, 20, "int"),
    "ema_l":     (8, 60, "int"),
    "rsi_len":   (5, 21, "int"),
    "rsi_ob":    (55, 85, "int"),
    "rsi_os":    (15, 45, "int"),
    "tp":        (0.3, 4.0, "float"),
    "sl":        (0.3, 3.0, "float"),
    "stoch_len": (5, 30, "int"),
    "stoch_hi":  (60, 95, "int"),
    "stoch_lo":  (5, 40, "int"),
    "adx_min":   (10, 40, "int"),
    "vol_mult":  (1.0, 4.0, "float"),
    "bb_period": (10, 30, "int"),
    "bb_std":    (1.0, 3.5, "float"),
    "macd_fast": (3, 15, "int"),
    "macd_slow": (15, 35, "int"),
    "macd_sig":  (3, 12, "int"),
    "trail_atr": (0.3, 2.5, "float"),
}

# Feature flags (toggleable genes)
FEATURE_FLAGS = [
    "use_stoch", "use_macd", "use_bb", "use_vol_filter",
    "use_adx", "use_vwap", "use_obv", "long_only", "short_only", "trailing"
]


def random_dna():
    """Generate a random strategy DNA."""
    dna = {}
    for param, (lo, hi, typ) in PARAM_RANGES.items():
        if typ == "int":
            dna[param] = random.randint(lo, hi)
        else:
            dna[param] = round(random.uniform(lo, hi), 2)

    # Ensure ema_s < ema_l
    if dna["ema_s"] >= dna["ema_l"]:
        dna["ema_s"], dna["ema_l"] = min(dna["ema_s"], dna["ema_l"]), max(dna["ema_s"], dna["ema_l"]) + 2

    # Ensure rsi_os < rsi_ob
    if dna["rsi_os"] >= dna["rsi_ob"]:
        dna["rsi_os"] = dna["rsi_ob"] - 10

    # Ensure macd_fast < macd_slow
    if dna["macd_fast"] >= dna["macd_slow"]:
        dna["macd_fast"] = dna["macd_slow"] - 5

    # Random feature flags (2-4 active)
    active_flags = random.sample(FEATURE_FLAGS, random.randint(1, 4))
    for f in FEATURE_FLAGS:
        dna[f] = f in active_flags

    # Enforce: long_only and short_only are mutually exclusive
    if dna.get("long_only") and dna.get("short_only"):
        dna["short_only"] = False

    return dna


VALID_EMA_PERIODS = [3,5,8,10,12,13,15,20,21,26,30,34,40,50]
VALID_RSI_PERIODS = [7, 10, 14]
VALID_STOCH_PERIODS = [9, 14, 21]
VALID_MACD_CONFIGS = [(8,17,9),(12,26,9),(5,13,5)]

def _nearest(val, valid):
    return min(valid, key=lambda x: abs(x - val))

def dna_to_strategy(dna, sid, name, group="GEN"):
    """Convert DNA dict to strategy dict for the engine. Clamps to pre-computed values."""
    ema_s = _nearest(dna["ema_s"], VALID_EMA_PERIODS)
    ema_l = _nearest(dna["ema_l"], [p for p in VALID_EMA_PERIODS if p > ema_s])
    if ema_l <= ema_s:
        ema_l = VALID_EMA_PERIODS[VALID_EMA_PERIODS.index(ema_s) + 1] if ema_s in VALID_EMA_PERIODS and VALID_EMA_PERIODS.index(ema_s) + 1 < len(VALID_EMA_PERIODS) else ema_s + 5

    params = {
        "ema_s": ema_s, "ema_l": ema_l,
        "rsi_len": _nearest(dna["rsi_len"], VALID_RSI_PERIODS),
        "tp": dna["tp"], "sl": dna["sl"],
        "rsi_ob": dna["rsi_ob"], "rsi_os": dna["rsi_os"],
        "stoch_len": _nearest(dna.get("stoch_len", 14), VALID_STOCH_PERIODS),
        "use_stoch": dna.get("use_stoch", True),
        "stoch_hi": dna.get("stoch_hi", 80),
        "stoch_lo": dna.get("stoch_lo", 20),
    }
    if dna.get("use_macd"):
        # Snap to nearest valid MACD config
        target = (dna.get("macd_fast", 12), dna.get("macd_slow", 26), dna.get("macd_sig", 9))
        best_cfg = min(VALID_MACD_CONFIGS, key=lambda c: abs(c[0]-target[0])+abs(c[1]-target[1]))
        params["use_macd"] = True
        params["macd_fast"] = best_cfg[0]
        params["macd_slow"] = best_cfg[1]
        params["macd_sig"] = best_cfg[2]
    if dna.get("use_bb"):
        params["use_bb"] = True
        params["bb_period"] = _nearest(dna.get("bb_period", 20), [15, 20])
        bb_std_val = dna.get("bb_std", 2.0)
        params["bb_std"] = _nearest(bb_std_val, [1.5, 2.0, 2.5])
    if dna.get("use_vol_filter"):
        params["use_vol_filter"] = True
        params["vol_mult"] = dna.get("vol_mult", 1.5)
    if dna.get("use_adx"):
        params["use_adx"] = True
        params["adx_min"] = dna.get("adx_min", 20)
    if dna.get("use_vwap"):
        params["use_vwap"] = True
    if dna.get("use_obv"):
        params["use_obv"] = True
    if dna.get("long_only"):
        params["long_only"] = True
    if dna.get("short_only"):
        params["short_only"] = True
    if dna.get("trailing"):
        params["trailing"] = True
        params["trail_atr"] = dna.get("trail_atr", 1.0)

    return {"id": sid, "name": name, "group": group, "params": params}


def mutate(dna, rate=MUTATION_RATE):
    """Mutate a DNA with small random changes."""
    child = dict(dna)
    for param, (lo, hi, typ) in PARAM_RANGES.items():
        if random.random() < rate:
            if typ == "int":
                delta = random.randint(-3, 3)
                child[param] = max(lo, min(hi, dna.get(param, lo) + delta))
            else:
                delta = random.uniform(-0.3, 0.3)
                child[param] = max(lo, min(hi, round(dna.get(param, lo) + delta, 2)))

    # Mutate feature flags (10% chance each)
    for f in FEATURE_FLAGS:
        if random.random() < 0.1:
            child[f] = not child.get(f, False)

    # Enforce constraints
    if child["ema_s"] >= child["ema_l"]:
        child["ema_l"] = child["ema_s"] + 3
    if child["rsi_os"] >= child["rsi_ob"]:
        child["rsi_os"] = child["rsi_ob"] - 10
    if child.get("macd_fast", 8) >= child.get("macd_slow", 26):
        child["macd_fast"] = child["macd_slow"] - 5
    if child.get("long_only") and child.get("short_only"):
        child["short_only"] = False

    return child


def crossover(dna_a, dna_b):
    """Cross two DNAs — uniform crossover."""
    child = {}
    for key in set(list(dna_a.keys()) + list(dna_b.keys())):
        if random.random() < 0.5:
            child[key] = dna_a.get(key, dna_b.get(key))
        else:
            child[key] = dna_b.get(key, dna_a.get(key))

    # Enforce constraints
    if child.get("ema_s", 5) >= child.get("ema_l", 13):
        child["ema_l"] = child["ema_s"] + 3
    if child.get("rsi_os", 30) >= child.get("rsi_ob", 70):
        child["rsi_os"] = child["rsi_ob"] - 10
    if child.get("macd_fast", 8) >= child.get("macd_slow", 26):
        child["macd_fast"] = child["macd_slow"] - 5
    if child.get("long_only") and child.get("short_only"):
        child["short_only"] = False

    return child


# ═══════════════════════════════════════════════════════════════════════
#  SEED POPULATION — From existing R1+R2 strategies + random mutations
# ═══════════════════════════════════════════════════════════════════════

def seed_from_existing():
    """Import winning strategies from strategy_lab.db as seed DNA."""
    seeds = []

    # Import from multi_strategy_scanner base strategies
    from multi_strategy_scanner import build_strategies
    for s in build_strategies():
        dna = dict(s["params"])
        for f in FEATURE_FLAGS:
            if f not in dna:
                dna[f] = False
        for param in PARAM_RANGES:
            if param not in dna:
                dna[param] = PARAM_RANGES[param][0]
        seeds.append({"dna": dna, "origin": f"R1:{s['name']}", "group": s["group"]})

    # Import from strategy_optimizer R2 strategies
    try:
        from strategy_optimizer import build_round2_strategies
        for s in build_round2_strategies():
            dna = dict(s["params"])
            for f in FEATURE_FLAGS:
                if f not in dna:
                    dna[f] = False
            for param in PARAM_RANGES:
                if param not in dna:
                    dna[param] = PARAM_RANGES[param][0]
            seeds.append({"dna": dna, "origin": f"R2:{s['name']}", "group": s["group"]})
    except Exception:
        pass

    return seeds


def build_initial_population(target_size):
    """Build initial population of target_size strategies."""
    pop = []

    # 1. Seed from existing winners
    seeds = seed_from_existing()
    for s in seeds:
        pop.append({"dna": s["dna"], "lineage": s["origin"], "fitness": 0,
                     "evals": 0, "avg_wr": 0, "avg_pnl": 0})

    print(f"  Seeds imported: {len(pop)} (R1+R2)")

    # 2. Mutations of seeds to reach target
    while len(pop) < target_size:
        parent = random.choice(seeds)
        child_dna = mutate(parent["dna"], rate=0.4)
        pop.append({"dna": child_dna, "lineage": f"MUT:{parent['origin'][:20]}",
                     "fitness": 0, "evals": 0, "avg_wr": 0, "avg_pnl": 0})

    # 3. Some pure random explorers (10%)
    n_random = max(10, target_size // 10)
    for _ in range(n_random):
        pop.append({"dna": random_dna(), "lineage": "RANDOM",
                     "fitness": 0, "evals": 0, "avg_wr": 0, "avg_pnl": 0})

    return pop[:target_size]


# ═══════════════════════════════════════════════════════════════════════
#  FITNESS EVALUATION
# ═══════════════════════════════════════════════════════════════════════

def compute_fitness(trades):
    """Compute fitness score from trade results."""
    closed = [t for t in trades if t["result"] != "OPEN"]
    if len(closed) < MIN_TRADES_VALID:
        return {"fitness": -1, "wr": 0, "pnl": 0, "trades": len(closed),
                "wins": 0, "avg_bars": 0, "long_wr": 0, "short_wr": 0}

    wins = [t for t in closed if t["result"] == "TP"]
    total_pnl = sum(t["pnl"] for t in closed)
    wr = len(wins) / len(closed) * 100
    avg_pnl = total_pnl / len(closed)
    avg_bars = sum(t["bars"] for t in closed) / len(closed)

    # Sharpe proxy: avg_pnl / std_pnl
    pnls = [t["pnl"] for t in closed]
    mean_pnl = sum(pnls) / len(pnls)
    std_pnl = math.sqrt(sum((p - mean_pnl)**2 for p in pnls) / len(pnls)) if len(pnls) > 1 else 1
    sharpe = mean_pnl / std_pnl if std_pnl > 0 else 0

    # Direction stats
    longs = [t for t in closed if t["dir"] == "LONG"]
    shorts = [t for t in closed if t["dir"] == "SHORT"]
    long_wr = len([t for t in longs if t["result"] == "TP"]) / len(longs) * 100 if longs else 0
    short_wr = len([t for t in shorts if t["result"] == "TP"]) / len(shorts) * 100 if shorts else 0

    # Composite fitness
    wr_norm = min(wr / 100, 1.0)
    pnl_norm = max(min(total_pnl / 10.0, 1.0), -1.0)  # Normalize to [-1, 1]
    sharpe_norm = max(min(sharpe, 1.0), -1.0)

    fitness = (FITNESS_WR_WEIGHT * wr_norm +
               FITNESS_PNL_WEIGHT * pnl_norm +
               FITNESS_SHARPE_WEIGHT * sharpe_norm)

    # Bonus for high trade count (more data = more reliable)
    if len(closed) > 20:
        fitness *= 1.1
    if len(closed) > 50:
        fitness *= 1.1

    # Anti-overfitting: penalize 100% WR on small samples (likely noise)
    if wr >= 99.9 and len(closed) < 15:
        fitness *= 0.6  # Heavy penalty — too few trades to trust
    elif wr >= 99.9 and len(closed) < 30:
        fitness *= 0.8  # Moderate penalty
    # Penalize too few trades overall
    if len(closed) < 10:
        fitness *= 0.7

    return {"fitness": round(fitness, 4), "wr": round(wr, 1), "pnl": round(total_pnl, 3),
            "trades": len(closed), "wins": len(wins), "avg_bars": round(avg_bars, 1),
            "long_wr": round(long_wr, 1), "short_wr": round(short_wr, 1)}


def evaluate_population(population, coins_data, gen_num):
    """Evaluate all strategies against a set of coins."""
    results = []

    for idx, strat_entry in enumerate(population):
        dna = strat_entry["dna"]
        strat = dna_to_strategy(dna, idx, f"GEN{gen_num}_S{idx}", "EVOLUTION")

        coin_fitnesses = []
        best_coin = ""
        best_coin_pnl = -999

        for sym, cache in coins_data.items():
            trades = run_single_strategy(cache, strat)
            fit = compute_fitness(trades)

            if fit["fitness"] >= 0:
                coin_fitnesses.append(fit)
                if fit["pnl"] > best_coin_pnl:
                    best_coin_pnl = fit["pnl"]
                    best_coin = sym

        if coin_fitnesses:
            avg_fitness = sum(f["fitness"] for f in coin_fitnesses) / len(coin_fitnesses)
            avg_wr = sum(f["wr"] for f in coin_fitnesses) / len(coin_fitnesses)
            avg_pnl = sum(f["pnl"] for f in coin_fitnesses) / len(coin_fitnesses)
            total_trades = sum(f["trades"] for f in coin_fitnesses)
        else:
            avg_fitness = -1
            avg_wr = 0
            avg_pnl = 0
            total_trades = 0

        strat_entry["fitness"] = avg_fitness
        strat_entry["avg_wr"] = avg_wr
        strat_entry["avg_pnl"] = avg_pnl
        strat_entry["evals"] += 1
        strat_entry["best_coin"] = best_coin
        strat_entry["best_coin_pnl"] = best_coin_pnl
        strat_entry["total_trades"] = total_trades
        strat_entry["coin_results"] = coin_fitnesses

        results.append(strat_entry)

    return results


# ═══════════════════════════════════════════════════════════════════════
#  SELECTION & REPRODUCTION
# ═══════════════════════════════════════════════════════════════════════

def evolve_population(population, gen_num):
    """Apply selection, mutation, crossover to produce next generation."""
    # Sort by fitness
    ranked = sorted(population, key=lambda x: x["fitness"], reverse=True)
    pop_size = len(ranked)

    n_elite = max(2, int(pop_size * ELITE_PCT))
    n_survivors = max(5, int(pop_size * SURVIVOR_PCT))
    n_crossover = int(pop_size * CROSSOVER_RATE)
    n_mutants = pop_size - n_elite - n_crossover

    next_gen = []
    mutations = 0
    crossovers = 0

    # 1. Elites pass unchanged
    for s in ranked[:n_elite]:
        child = dict(s)
        child["lineage"] = f"ELITE:G{gen_num}"
        next_gen.append(child)

    # 2. Crossover from top survivors
    survivors = ranked[:n_survivors]
    for _ in range(n_crossover):
        a, b = random.sample(survivors, 2)
        child_dna = crossover(a["dna"], b["dna"])
        next_gen.append({
            "dna": child_dna, "lineage": f"CROSS:G{gen_num}",
            "fitness": 0, "evals": 0, "avg_wr": 0, "avg_pnl": 0
        })
        crossovers += 1

    # 3. Mutants from survivors
    while len(next_gen) < pop_size:
        parent = random.choice(survivors)
        child_dna = mutate(parent["dna"])
        next_gen.append({
            "dna": child_dna, "lineage": f"MUT:G{gen_num}",
            "fitness": 0, "evals": 0, "avg_wr": 0, "avg_pnl": 0
        })
        mutations += 1

    # 4. Inject some pure random explorers (5%)
    n_random = max(2, pop_size // 20)
    for i in range(n_random):
        if i < len(next_gen):
            # Replace worst slots
            next_gen[-(i+1)] = {
                "dna": random_dna(), "lineage": f"RANDOM:G{gen_num}",
                "fitness": 0, "evals": 0, "avg_wr": 0, "avg_pnl": 0
            }

    return next_gen[:pop_size], mutations, crossovers


# ═══════════════════════════════════════════════════════════════════════
#  COIN SELECTION — Smart rotation
# ═══════════════════════════════════════════════════════════════════════

def select_coins_for_gen(gen_num, max_coins=COINS_PER_GEN):
    """Select coins to test this generation — mix of pool + exploration."""
    coins = []

    # 1. From existing pool (60%)
    try:
        db = sqlite3.connect(str(DB_PATH), timeout=10)
        db.row_factory = sqlite3.Row
        pool = db.execute("""
            SELECT symbol, grade, best_pnl FROM coin_pool
            ORDER BY best_pnl DESC LIMIT ?
        """, (int(max_coins * 0.6),)).fetchall()
        coins.extend([r["symbol"] for r in pool])
        db.close()
    except Exception:
        pass

    # 2. Fresh from MEXC (40% — exploration)
    try:
        fresh = fetch_top_coins(min_vol_24h=500000, max_coins=50)
        # Shuffle to explore different coins each gen
        random.shuffle(fresh)
        remaining = max_coins - len(coins)
        for c in fresh:
            if c["symbol"] not in coins and remaining > 0:
                coins.append(c["symbol"])
                remaining -= 1
    except Exception:
        pass

    return coins[:max_coins]


def fetch_and_cache_coins(symbols):
    """Fetch klines and pre-compute indicators for all coins."""
    coins_data = {}
    for sym in symbols:
        candles = fetch_klines(sym, limit=CANDLES)
        if not candles or len(candles) < 100:
            continue
        quality, status = assess_coin_quality(candles)
        if status != "OK":
            continue
        cache = precompute_indicators(candles)
        coins_data[sym] = cache
        time.sleep(0.05)
    return coins_data


# ═══════════════════════════════════════════════════════════════════════
#  PERSISTENCE — Save/Load population
# ═══════════════════════════════════════════════════════════════════════

def save_generation(db, gen_num, population, elapsed, mutations, crossovers, coins_tested):
    """Save generation results to DB."""
    ranked = sorted(population, key=lambda x: x["fitness"], reverse=True)
    best = ranked[0] if ranked else None
    avg_fit = sum(s["fitness"] for s in population) / len(population) if population else 0

    db.execute("""INSERT INTO generations
        (timestamp, generation, pop_size, coins_tested, avg_fitness, best_fitness,
         best_strategy, best_wr, best_pnl, mutations, crossovers, elapsed_sec)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (datetime.now().isoformat(), gen_num, len(population), coins_tested,
         round(avg_fit, 4), best["fitness"] if best else 0,
         json.dumps(best["dna"])[:200] if best else "",
         best.get("avg_wr", 0) if best else 0,
         best.get("avg_pnl", 0) if best else 0,
         mutations, crossovers, round(elapsed, 1)))

    # Save top strategies
    for idx, s in enumerate(ranked[:100]):
        db.execute("""INSERT OR REPLACE INTO strategies
            (gen_born, gen_last_seen, name, dna, fitness, total_evals,
             avg_wr, avg_pnl, best_coin, best_pnl_coin, alive, lineage)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (gen_num, gen_num, f"G{gen_num}_R{idx}",
             json.dumps(s["dna"]), s["fitness"], s.get("evals", 1),
             s.get("avg_wr", 0), s.get("avg_pnl", 0),
             s.get("best_coin", ""), s.get("best_coin_pnl", 0),
             1 if idx < len(ranked) * SURVIVOR_PCT else 0,
             s.get("lineage", "")))

    db.commit()


def load_last_population(db, target_size):
    """Load best strategies from DB to resume evolution."""
    rows = db.execute("""
        SELECT dna, fitness, avg_wr, avg_pnl, lineage, total_evals
        FROM strategies WHERE alive=1
        ORDER BY fitness DESC LIMIT ?
    """, (target_size,)).fetchall()

    pop = []
    for r in rows:
        try:
            dna = json.loads(r["dna"])
            pop.append({
                "dna": dna, "fitness": r["fitness"],
                "avg_wr": r["avg_wr"], "avg_pnl": r["avg_pnl"],
                "lineage": r["lineage"], "evals": r["total_evals"]
            })
        except Exception:
            continue

    return pop


# ═══════════════════════════════════════════════════════════════════════
#  MAIN LOOP
# ═══════════════════════════════════════════════════════════════════════

def print_gen_summary(gen_num, population, coins_tested, elapsed):
    """Print generation summary."""
    ranked = sorted(population, key=lambda x: x["fitness"], reverse=True)
    avg_fit = sum(s["fitness"] for s in population) / len(population) if population else 0
    avg_wr = sum(s.get("avg_wr", 0) for s in population) / len(population) if population else 0
    avg_pnl = sum(s.get("avg_pnl", 0) for s in population) / len(population) if population else 0
    positive = sum(1 for s in population if s.get("avg_pnl", 0) > 0)

    top5 = ranked[:5]
    ts = datetime.now().strftime("%H:%M:%S")

    print(f"\n{'='*75}")
    print(f"  GEN #{gen_num} — {ts} — {elapsed:.0f}s — {coins_tested} coins")
    print(f"{'='*75}")
    print(f"  Pop: {len(population)} | Avg Fitness: {avg_fit:.4f} | Avg WR: {avg_wr:.1f}% | Avg PnL: {avg_pnl:+.3f}%")
    print(f"  Profitable: {positive}/{len(population)} ({positive/len(population)*100:.0f}%)")
    print()
    print(f"  TOP 5:")
    for i, s in enumerate(top5):
        features = [f for f in FEATURE_FLAGS if s["dna"].get(f)]
        feat_str = "+".join(f.replace("use_","") for f in features[:3]) or "base"
        print(f"    #{i+1} Fit:{s['fitness']:.4f} WR:{s.get('avg_wr',0):.1f}% "
              f"PnL:{s.get('avg_pnl',0):+.3f}% | "
              f"EMA {s['dna']['ema_s']}/{s['dna']['ema_l']} RSI {s['dna']['rsi_len']} "
              f"TP:{s['dna']['tp']} SL:{s['dna']['sl']} | {feat_str}")
    print(f"{'='*75}")


def run_evolution(pop_size=DEFAULT_POP_SIZE, max_gens=MAX_GENERATIONS,
                  single=False, verbose=True):
    """Main evolution loop."""
    db = init_evolution_db()

    # Check for resume
    last_gen = db.execute("SELECT MAX(generation) FROM generations").fetchone()[0] or 0
    start_gen = last_gen + 1

    # Build or resume population
    if start_gen > 1:
        print(f"[RESUME] Loading population from generation {last_gen}...")
        population = load_last_population(db, pop_size)
        if len(population) < pop_size:
            # Fill remaining with mutations of best
            while len(population) < pop_size:
                parent = random.choice(population[:max(1, len(population)//3)])
                population.append({
                    "dna": mutate(parent["dna"]),
                    "lineage": f"FILL:G{start_gen}",
                    "fitness": 0, "evals": 0, "avg_wr": 0, "avg_pnl": 0
                })
        print(f"  Resumed with {len(population)} strategies")
    else:
        print(f"[INIT] Building initial population of {pop_size} strategies...")
        population = build_initial_population(pop_size)
        print(f"  Population ready: {len(population)} strategies")

    log_event(db, "EVOLUTION_START",
              f"pop={pop_size}, start_gen={start_gen}, max_gens={max_gens}")

    # Notify
    send_telegram(f"<b>EVOLUTION START</b>\n"
                  f"Pop: {pop_size} strategies\n"
                  f"Gen: {start_gen} -> {start_gen + max_gens - 1}\n"
                  f"Mode: {'single' if single else 'continuous'}")

    end_gen = start_gen + (1 if single else max_gens)

    for gen in range(start_gen, end_gen):
        t0 = time.time()
        print(f"\n[GEN {gen}] Selecting coins...")

        # 1. Select coins
        symbols = select_coins_for_gen(gen)
        print(f"  Coins: {len(symbols)} — {', '.join(symbols[:5])}{'...' if len(symbols)>5 else ''}")

        # 2. Fetch data
        print(f"  Fetching {len(symbols)} coins...")
        coins_data = fetch_and_cache_coins(symbols)
        print(f"  Cached: {len(coins_data)} coins ready")

        if not coins_data:
            print("  [WARN] No coin data, skipping generation")
            time.sleep(60)
            continue

        # 3. Evaluate
        print(f"  Evaluating {len(population)} strategies on {len(coins_data)} coins...")
        population = evaluate_population(population, coins_data, gen)

        elapsed = time.time() - t0

        # 4. Summary
        print_gen_summary(gen, population, len(coins_data), elapsed)

        # 5. Save
        ranked = sorted(population, key=lambda x: x["fitness"], reverse=True)
        mutations_count = 0
        crossovers_count = 0

        save_generation(db, gen, population, elapsed, 0, 0, len(coins_data))

        # 6. Evolve for next gen
        if gen < end_gen - 1:
            population, mutations_count, crossovers_count = evolve_population(population, gen)
            print(f"  Evolution: {mutations_count} mutations, {crossovers_count} crossovers")

        # 7. Telegram summary every 5 gens
        if gen % 5 == 0 or single:
            best = ranked[0] if ranked else None
            avg_fit = sum(s["fitness"] for s in population) / len(population)
            msg = (f"<b>EVOLUTION GEN #{gen}</b>\n"
                   f"Pop: {len(population)} | Coins: {len(coins_data)}\n"
                   f"Avg Fitness: {avg_fit:.4f}\n")
            if best:
                msg += (f"Best: WR {best.get('avg_wr',0):.1f}% PnL {best.get('avg_pnl',0):+.3f}%\n"
                        f"EMA {best['dna']['ema_s']}/{best['dna']['ema_l']} "
                        f"TP:{best['dna']['tp']} SL:{best['dna']['sl']}")
            send_telegram(msg)

        gen_avg_fit = sum(s["fitness"] for s in population) / len(population) if population else 0
        log_event(db, f"GEN_{gen}_DONE",
                  f"fit={gen_avg_fit:.4f} best_wr={ranked[0].get('avg_wr',0):.1f}% "
                  f"elapsed={elapsed:.0f}s")

        # Wait between generations (if continuous)
        if not single and gen < end_gen - 1:
            wait = SCAN_INTERVAL_MIN * 60
            print(f"\n  Waiting {SCAN_INTERVAL_MIN}min before next generation...")
            time.sleep(wait)

    # Final summary
    db_final = init_evolution_db()
    best_ever = db_final.execute("""
        SELECT * FROM strategies ORDER BY fitness DESC LIMIT 10
    """).fetchall()

    print("\n" + "=" * 75)
    print("  EVOLUTION COMPLETE — TOP 10 ALL-TIME")
    print("=" * 75)
    for r in best_ever:
        dna = json.loads(r["dna"])
        print(f"  {r['name']:<20} Fit:{r['fitness']:.4f} WR:{r['avg_wr']:.1f}% "
              f"PnL:{r['avg_pnl']:+.3f}% | EMA {dna['ema_s']}/{dna['ema_l']} "
              f"TP:{dna['tp']} SL:{dna['sl']} | {r['lineage']}")

    send_telegram(f"<b>EVOLUTION COMPLETE</b>\n"
                  f"Best: WR {best_ever[0]['avg_wr']:.1f}% PnL {best_ever[0]['avg_pnl']:+.3f}%"
                  if best_ever else "No results")

    db_final.close()


def show_status():
    """Show current evolution status."""
    if not EVOLUTION_DB.exists():
        print("  No evolution data yet. Run the loop first.")
        return

    db = sqlite3.connect(str(EVOLUTION_DB), timeout=10)
    db.row_factory = sqlite3.Row

    last_gen = db.execute("SELECT * FROM generations ORDER BY id DESC LIMIT 1").fetchone()
    total_gens = db.execute("SELECT COUNT(*) FROM generations").fetchone()[0]
    total_strats = db.execute("SELECT COUNT(*) FROM strategies WHERE alive=1").fetchone()[0]
    best = db.execute("SELECT * FROM strategies ORDER BY fitness DESC LIMIT 5").fetchall()

    print("=" * 75)
    print("  EVOLUTION STATUS")
    print("=" * 75)

    if last_gen:
        print(f"  Generations: {total_gens}")
        print(f"  Last gen: #{last_gen['generation']} ({last_gen['timestamp'][:19]})")
        print(f"  Pop size: {last_gen['pop_size']} | Coins: {last_gen['coins_tested']}")
        print(f"  Avg fitness: {last_gen['avg_fitness']:.4f}")
        print(f"  Best fitness: {last_gen['best_fitness']:.4f}")
        print(f"  Active strategies: {total_strats}")

    if best:
        print(f"\n  TOP 5 STRATEGIES:")
        for r in best:
            dna = json.loads(r["dna"])
            features = [f for f in FEATURE_FLAGS if dna.get(f)]
            feat_str = "+".join(f.replace("use_","") for f in features[:3]) or "base"
            print(f"    {r['name']:<20} Fit:{r['fitness']:.4f} WR:{r['avg_wr']:.1f}% "
                  f"PnL:{r['avg_pnl']:+.3f}% | "
                  f"EMA {dna['ema_s']}/{dna['ema_l']} TP:{dna['tp']} SL:{dna['sl']} | {feat_str}")

    # Recent events
    events = db.execute("SELECT * FROM evolution_log ORDER BY id DESC LIMIT 5").fetchall()
    if events:
        print(f"\n  RECENT EVENTS:")
        for e in events:
            print(f"    [{e['timestamp'][:19]}] {e['event']}: {e['detail'][:60]}")

    print("=" * 75)
    db.close()


def main():
    global COINS_PER_GEN, SCAN_INTERVAL_MIN

    parser = argparse.ArgumentParser(description="Strategy Evolution Loop — Autonomous")
    parser.add_argument("--pop", type=int, default=DEFAULT_POP_SIZE,
                        help=f"Population size (default {DEFAULT_POP_SIZE})")
    parser.add_argument("--generations", type=int, default=MAX_GENERATIONS,
                        help=f"Max generations (default {MAX_GENERATIONS})")
    parser.add_argument("--coins", type=int, default=COINS_PER_GEN,
                        help=f"Coins per generation (default {COINS_PER_GEN})")
    parser.add_argument("--interval", type=int, default=SCAN_INTERVAL_MIN,
                        help=f"Minutes between gens (default {SCAN_INTERVAL_MIN})")
    parser.add_argument("--once", action="store_true", help="Run single generation")
    parser.add_argument("--status", action="store_true", help="Show current status")
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    COINS_PER_GEN = args.coins
    SCAN_INTERVAL_MIN = args.interval

    # Write PID for monitoring
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))

    print("=" * 75)
    print("  STRATEGY EVOLUTION LOOP — JARVIS AUTONOMOUS")
    print("=" * 75)
    print(f"  Population:    {args.pop}")
    print(f"  Generations:   {'1 (single)' if args.once else args.generations}")
    print(f"  Coins/gen:     {COINS_PER_GEN}")
    print(f"  Interval:      {SCAN_INTERVAL_MIN}min")
    print(f"  DB:            {EVOLUTION_DB}")
    print(f"  PID:           {os.getpid()}")
    print()

    try:
        run_evolution(
            pop_size=args.pop,
            max_gens=args.generations,
            single=args.once
        )
    except KeyboardInterrupt:
        print("\n  [STOP] Evolution interrupted by user")
        send_telegram("Evolution loop stopped (user interrupt)")
    finally:
        if PID_FILE.exists():
            PID_FILE.unlink()


if __name__ == "__main__":
    main()
