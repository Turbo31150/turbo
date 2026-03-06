#!/usr/bin/env python3
"""
Cluster Strategy Worker — Dispatche du travail aux modeles locaux en continu.

Taches:
1. M1 (qwen3-8b): Genere de nouvelles strategies a injecter dans l'evolution
2. M2 (qwen3-8b): Analyse les resultats et detecte l'overfitting
3. M3 (qwen3-8b): Propose des nouveaux indicateurs et features
4. OL1 (qwen3:1.7b): Analyse rapide des coins

Boucle toutes les 10 minutes. Injecte les resultats dans evolution_db.

Usage:
    python cowork/dev/cluster_strategy_worker.py          # Boucle continue
    python cowork/dev/cluster_strategy_worker.py --once    # Une seule passe
"""

import json, os, sqlite3, sys, time, urllib.request, urllib.parse
from datetime import datetime
from pathlib import Path

TURBO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = TURBO_ROOT / "data"
EVOLUTION_DB = DATA_DIR / "strategy_evolution.db"

NODES = {
    "M1": {"url": "http://127.0.0.1:1234/api/v1/chat", "model": "qwen3-8b",
            "prefix": "/nothink\n", "timeout": 30, "extract": "lmstudio"},
    "M2": {"url": "http://192.168.1.26:1234/api/v1/chat", "model": "deepseek/qwen/qwen3-8b",
            "prefix": "", "timeout": 120, "extract": "lmstudio"},
    "M3": {"url": "http://192.168.1.113:1234/api/v1/chat", "model": "deepseek/qwen/qwen3-8b",
            "prefix": "", "timeout": 120, "extract": "lmstudio"},
    "OL1": {"url": "http://127.0.0.1:11434/api/chat", "model": "qwen3:1.7b",
             "prefix": "/nothink\n", "timeout": 30, "extract": "ollama"},
}


def query_lmstudio(node, prompt):
    cfg = NODES[node]
    body = json.dumps({
        "model": cfg["model"],
        "input": cfg["prefix"] + prompt,
        "temperature": 0.3,
        "max_output_tokens": 1024,
        "stream": False,
        "store": False
    }).encode()
    try:
        req = urllib.request.Request(cfg["url"], body, {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=cfg["timeout"]) as resp:
            d = json.loads(resp.read())
        for o in d.get("output", []):
            if o.get("type") == "message" and o.get("content"):
                return o["content"]
        return None
    except Exception as e:
        return f"[ERR] {e}"


def query_ollama(node, prompt):
    cfg = NODES[node]
    body = json.dumps({
        "model": cfg["model"],
        "messages": [{"role": "user", "content": cfg["prefix"] + prompt}],
        "stream": False
    }).encode()
    try:
        req = urllib.request.Request(cfg["url"], body, {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=cfg["timeout"]) as resp:
            d = json.loads(resp.read())
        return d.get("message", {}).get("content")
    except Exception as e:
        return f"[ERR] {e}"


def query(node, prompt):
    cfg = NODES[node]
    if cfg["extract"] == "ollama":
        return query_ollama(node, prompt)
    return query_lmstudio(node, prompt)


def get_evolution_summary():
    if not EVOLUTION_DB.exists():
        return "Pas de donnees evolution"
    db = sqlite3.connect(str(EVOLUTION_DB), timeout=10)
    db.row_factory = sqlite3.Row
    last = db.execute("SELECT * FROM generations ORDER BY id DESC LIMIT 1").fetchone()
    top5 = db.execute("SELECT * FROM strategies ORDER BY fitness DESC LIMIT 5").fetchall()
    db.close()
    if not last:
        return "Aucune generation"
    lines = [f"Gen {last['generation']}: pop={last['pop_size']} coins={last['coins_tested']} "
             f"avg_fit={last['avg_fitness']:.4f} best_fit={last['best_fitness']:.4f}"]
    for s in top5:
        dna = json.loads(s["dna"])
        lines.append(f"  {s['name']}: Fit={s['fitness']:.4f} WR={s['avg_wr']:.1f}% "
                     f"PnL={s['avg_pnl']:+.3f}% EMA {dna.get('ema_s')}/{dna.get('ema_l')} "
                     f"TP={dna.get('tp')} SL={dna.get('sl')}")
    return "\n".join(lines)


def inject_strategies(strategies_json):
    """Parse JSON strategies from M1 and inject into evolution DB."""
    try:
        data = json.loads(strategies_json) if isinstance(strategies_json, str) else strategies_json
        strats = data if isinstance(data, list) else data.get("strategies", [])
        if not strats:
            return 0
        db = sqlite3.connect(str(EVOLUTION_DB), timeout=10)
        last_gen = db.execute("SELECT MAX(generation) FROM generations").fetchone()[0] or 0
        count = 0
        for s in strats[:20]:  # Max 20 injections
            dna = {
                "ema_s": s.get("ema_s", 5), "ema_l": s.get("ema_l", 13),
                "rsi_len": s.get("rsi_len", 7), "rsi_ob": s.get("rsi_ob", 70),
                "rsi_os": s.get("rsi_os", 30), "tp": s.get("tp", 1.0),
                "sl": s.get("sl", 1.0), "stoch_len": s.get("stoch_len", 14),
                "stoch_hi": 80, "stoch_lo": 20,
                "use_stoch": "stoch" in str(s.get("features", [])).lower(),
                "use_macd": "macd" in str(s.get("features", [])).lower(),
                "use_bb": "bb" in str(s.get("features", [])).lower() or "bollinger" in str(s.get("features", [])).lower(),
                "use_vol_filter": "vol" in str(s.get("features", [])).lower(),
                "use_adx": "adx" in str(s.get("features", [])).lower(),
                "use_vwap": "vwap" in str(s.get("features", [])).lower(),
                "use_obv": "obv" in str(s.get("features", [])).lower(),
                "long_only": "long" in str(s.get("features", [])).lower(),
                "short_only": "short" in str(s.get("features", [])).lower(),
                "trailing": False,
            }
            db.execute("""INSERT INTO strategies
                (gen_born, gen_last_seen, name, dna, fitness, total_evals,
                 avg_wr, avg_pnl, best_coin, best_pnl_coin, alive, lineage)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (last_gen, last_gen, s.get("name", f"INJECTED_{count}"),
                 json.dumps(dna), 0, 0, 0, 0, "", 0, 1, "CLUSTER_INJECT"))
            count += 1
        db.commit()
        db.close()
        return count
    except Exception as e:
        print(f"  [ERR] inject: {e}")
        return 0


def log_cluster_event(event, detail):
    try:
        db = sqlite3.connect(str(EVOLUTION_DB), timeout=10)
        db.execute("INSERT INTO evolution_log (timestamp, event, detail) VALUES (?,?,?)",
                   (datetime.now().isoformat(), event, detail[:500]))
        db.commit()
        db.close()
    except Exception:
        pass


def run_cycle(cycle_num):
    ts = datetime.now().strftime("%H:%M:%S")
    summary = get_evolution_summary()
    print(f"\n[{ts}] === CLUSTER CYCLE #{cycle_num} ===")
    print(f"  Evolution: {summary.split(chr(10))[0]}")

    # TASK 1: M1 — Generate new strategies
    print(f"  [M1] Generating strategies...", end=" ", flush=True)
    prompt = (f"Tu es un generateur de strategies trading. Voici l'etat actuel:\n{summary}\n\n"
              f"Genere 5 nouvelles strategies DIFFERENTES du top actuel. "
              f"Reponds UNIQUEMENT en JSON: [{{\"name\":\"...\",\"ema_s\":N,\"ema_l\":N,"
              f"\"rsi_len\":N,\"rsi_ob\":N,\"rsi_os\":N,\"tp\":F,\"sl\":F,"
              f"\"features\":[\"macd\",\"bb\"]}}]. Pas de texte.")
    r1 = query("M1", prompt)
    if r1 and not r1.startswith("[ERR]"):
        # Try to extract JSON
        try:
            start = r1.find("[")
            end = r1.rfind("]") + 1
            if start >= 0 and end > start:
                injected = inject_strategies(r1[start:end])
                print(f"OK — {injected} strategies injected")
            else:
                print(f"no JSON found")
        except Exception as e:
            print(f"parse error: {e}")
    else:
        print(f"FAIL: {str(r1)[:60]}")

    # TASK 2: M2 — Analyze overfitting risk
    print(f"  [M2] Analyzing overfitting...", end=" ", flush=True)
    prompt2 = (f"Analyse rapide de ces resultats de trading algo:\n{summary}\n\n"
               f"En 3 lignes: 1) Y a-t-il overfitting? 2) Les parametres sont-ils robustes? "
               f"3) Que changer?")
    r2 = query("M2", prompt2)
    if r2 and not r2.startswith("[ERR]"):
        print(f"OK")
        for line in r2.strip().split("\n")[:5]:
            print(f"    {line.strip()[:100]}")
        log_cluster_event("M2_ANALYSIS", r2[:300])
    else:
        print(f"FAIL: {str(r2)[:60]}")

    # TASK 3: OL1 — Quick coin recommendation
    print(f"  [OL1] Coin analysis...", end=" ", flush=True)
    r4 = query("OL1", f"Parmi BTC ETH SOL SUI PEPE DOGE XRP AVAX LINK TAO HYPE XMR, "
               f"quels 5 sont les meilleurs pour du scalping 1min maintenant? "
               f"Juste la liste avec 1 mot de raison chacun.")
    if r4 and not r4.startswith("[ERR]"):
        print(f"OK")
        for line in r4.strip().split("\n")[:6]:
            print(f"    {line.strip()[:80]}")
    else:
        print(f"FAIL: {str(r4)[:60]}")

    print(f"  Cycle #{cycle_num} done")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Cluster Strategy Worker")
    parser.add_argument("--once", action="store_true", help="Single cycle")
    parser.add_argument("--interval", type=int, default=10, help="Minutes between cycles")
    args = parser.parse_args()

    print("=" * 60)
    print("  CLUSTER STRATEGY WORKER — JARVIS")
    print("=" * 60)
    print(f"  Mode: {'single' if args.once else 'continuous'}")
    print(f"  Interval: {args.interval}min")
    print(f"  Nodes: M1, M2, M3, OL1")

    cycle = 0
    while True:
        cycle += 1
        try:
            run_cycle(cycle)
        except Exception as e:
            print(f"  [ERR] Cycle failed: {e}")

        if args.once:
            break
        print(f"\n  Next cycle in {args.interval}min...")
        time.sleep(args.interval * 60)


if __name__ == "__main__":
    main()
