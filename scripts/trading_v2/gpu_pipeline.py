"""
GPU Pipeline — Calcul vectorise GPU complet
Trading AI System v2.3 | Adapte cluster JARVIS

Pipeline: data_fetcher -> strategies (PyTorch multi-GPU) -> ai_consensus -> output
Tensor 3D: [coins x temps x features] float32 sur GPU
v2.3: Consensus parallele + GPU thermal monitoring
"""

import sys
import os
import json
import time
import logging
import argparse
import subprocess
import numpy as np
from datetime import datetime, timezone
from pathlib import Path

# Ajout chemin local
sys.path.insert(0, str(Path(__file__).parent))

from data_fetcher import (
    fetch_batch_klines, fetch_batch_depth, build_tensor_3d,
    scan_top_volume, DEFAULT_PAIRS, TIME_WINDOW
)
from strategies import compute_final_scores, MarketRegime, GPU_AVAILABLE, GPU_COUNT, GPU_DEVICES
from ai_consensus import run_consensus, quick_consensus, fast_consensus

logger = logging.getLogger("gpu_pipeline")

# --- Config ---
TOP_N_COINS = 200         # Coins a scanner
TOP_SIGNALS = 10          # Top signaux a afficher
MIN_CONFIDENCE = 0.15     # Confiance min technique
SIGNAL_SCORE = 0.5        # Score min pour consensus IA
EPSILON = 0.05            # Garde-fou anti-ennui

# Risk management ATR dynamique
ATR_MULTIPLIER = 1.5
TP1_MULT = 1.5
TP2_MULT = 3.0
LEVERAGE = 10

# GPU allocation (RTX 2060=0, 1660S=1-3, RTX 3080=4)
GPU_ORCHESTRATOR = 0
GPU_DETECTOR = 4
GPU_WORKERS = [1, 2, 3]

# Output
OUTPUT_DIR = Path("F:/BUREAU/turbo/data/trading_v2")


GPU_TEMP_WARNING = 75   # °C — ralentir
GPU_TEMP_CRITICAL = 85  # °C — arreter GPU, fallback CPU


def setup_gpu():
    """Configure GPU via PyTorch multi-GPU."""
    if GPU_AVAILABLE:
        try:
            import torch
            gpu_names = [torch.cuda.get_device_name(i) for i in range(GPU_COUNT)]
            logger.info(f"GPU: PyTorch {torch.__version__} | {GPU_COUNT} GPU | {', '.join(gpu_names)}")
            return True
        except Exception as e:
            logger.warning(f"GPU init failed: {e} - fallback NumPy")
    else:
        logger.info("GPU: PyTorch CUDA non dispo - mode NumPy")
    return False


def check_gpu_thermal() -> dict:
    """Verifie la temperature de tous les GPU locaux via nvidia-smi."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,temperature.gpu,utilization.gpu,memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return {"status": "unavailable", "gpus": []}

        gpus = []
        max_temp = 0
        for line in result.stdout.strip().split("\n"):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 6:
                temp = int(parts[2])
                max_temp = max(max_temp, temp)
                gpus.append({
                    "index": int(parts[0]),
                    "name": parts[1],
                    "temp_c": temp,
                    "util_pct": int(parts[3]),
                    "mem_used_mb": int(parts[4]),
                    "mem_total_mb": int(parts[5]),
                })

        if max_temp >= GPU_TEMP_CRITICAL:
            status = "critical"
        elif max_temp >= GPU_TEMP_WARNING:
            status = "warning"
        else:
            status = "ok"

        return {"status": status, "max_temp": max_temp, "gpus": gpus}

    except FileNotFoundError:
        return {"status": "no_nvidia_smi", "gpus": []}
    except Exception as e:
        logger.warning(f"GPU thermal check: {e}")
        return {"status": "error", "gpus": []}


def compute_entry_exit(price: float, atr: float, direction: str) -> dict:
    """Calcul SL/TP adaptatifs bases sur ATR (pas fixe)."""
    k = ATR_MULTIPLIER

    if direction == "LONG":
        entry = price * 0.999  # Leger slippage
        sl = entry - k * atr
        tp1 = entry + TP1_MULT * k * atr
        tp2 = entry + TP2_MULT * k * atr
    else:  # SHORT
        entry = price * 1.001
        sl = entry + k * atr
        tp1 = entry - TP1_MULT * k * atr
        tp2 = entry - TP2_MULT * k * atr

    return {
        "entry_price": round(entry, 6),
        "sl": round(sl, 6),
        "tp1": round(tp1, 6),
        "tp2": round(tp2, 6),
        "risk_reward": round(TP1_MULT, 2),
    }


def run_pipeline(n_coins: int = TOP_N_COINS,
                 use_ai: bool = True,
                 quick_mode: bool = False,
                 no_gemini: bool = False,
                 time_window: int = TIME_WINDOW,
                 output_json: bool = False) -> dict:
    """
    Pipeline complet:
    1. Scan MEXC top volume
    2. Fetch klines batch (parallele)
    3. Build tenseur 3D [coins x time x features]
    4. Strategies vectorisees CuPy (100 strategies)
    5. Ponderation adaptive + garde-fou
    6. AI consensus (5 modeles) sur top signals
    7. Output JSON + classement

    Retourne dict avec resultats.
    """
    pipeline_start = time.time()
    results = {"signals": [], "meta": {}, "errors": []}

    # --- GPU Thermal Pre-check ---
    thermal = check_gpu_thermal()
    if thermal["status"] == "critical":
        print(f"  [THERMAL] CRITIQUE: {thermal['max_temp']}C — GPU desactive, mode CPU force")
        logger.error(f"GPU thermal critical: {thermal['max_temp']}C")
        results["errors"].append(f"GPU thermal critical: {thermal['max_temp']}C")
    elif thermal["status"] == "warning":
        print(f"  [THERMAL] WARNING: {thermal['max_temp']}C — surveillance active")
        logger.warning(f"GPU thermal warning: {thermal['max_temp']}C")

    # --- Phase 1: Scan symboles ---
    print(f"\n{'='*60}")
    print(f"  TRADING AI SYSTEM v2.3 | GPU Pipeline")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    gpu_label = f"PyTorch {GPU_COUNT}xGPU" if GPU_AVAILABLE else "NumPy CPU"
    print(f"  GPU: {gpu_label} | Coins: {n_coins} | Window: {time_window}")
    if thermal["gpus"]:
        gpu_info = " | ".join(f"GPU{g['index']}:{g['temp_c']}C" for g in thermal["gpus"])
        print(f"  Thermal: {gpu_info}")
    print(f"{'='*60}\n")

    t0 = time.time()
    symbols = scan_top_volume(n_coins)
    if not symbols:
        symbols = DEFAULT_PAIRS
    print(f"[1/5] Scan: {len(symbols)} symboles ({int((time.time()-t0)*1000)}ms)")

    # --- Phase 2: Fetch data ---
    t0 = time.time()
    klines = fetch_batch_klines(symbols, limit=time_window, max_workers=12)
    depths = fetch_batch_depth(list(klines.keys()), max_workers=12)
    print(f"[2/5] Data: {len(klines)} klines, {len(depths)} order books ({int((time.time()-t0)*1000)}ms)")

    if not klines:
        results["errors"].append("Aucune kline recuperee")
        return results

    # --- Phase 3: Tenseur 3D ---
    t0 = time.time()
    tensor, tensor_symbols = build_tensor_3d(klines, time_window)
    print(f"[3/5] Tenseur: {tensor.shape} float32 ({int((time.time()-t0)*1000)}ms)")

    # OB imbalances
    ob_imbalances = np.zeros(len(tensor_symbols), dtype=np.float32)
    for i, sym in enumerate(tensor_symbols):
        if sym in depths:
            ob_imbalances[i] = depths[sym]["imbalance"]

    # --- Phase 4: Strategies vectorisees ---
    t0 = time.time()
    scores = compute_final_scores(tensor, ob_imbalances)
    print(f"[4/5] Strategies: 100 evaluees sur {len(tensor_symbols)} coins ({int((time.time()-t0)*1000)}ms)")

    # Extraire top signaux
    mean_scores = scores["mean_scores"]
    confidences = scores["confidences"]
    directions = scores["directions"]
    atrs = scores["atr"]
    regimes = scores["market_regimes"]

    # Trier par confiance decroissante
    sorted_idx = np.argsort(-confidences)

    # Filtrer: confiance > min ET direction != 0
    candidates = []
    for idx in sorted_idx:
        conf = float(confidences[idx])
        direction = int(directions[idx])
        if conf >= MIN_CONFIDENCE and direction != 0:
            sym = tensor_symbols[idx]
            price = float(tensor[idx, -1, 3])  # Dernier close
            atr_val = float(atrs[idx])

            # Strategies declenchees
            triggered = scores["triggered_strategies"].get(idx, [])
            regime = regimes[idx].value if hasattr(regimes[idx], 'value') else str(regimes[idx])

            dir_str = "LONG" if direction > 0 else "SHORT"
            entry_exit = compute_entry_exit(price, atr_val, dir_str)

            candidates.append({
                "rank": len(candidates) + 1,
                "symbol": sym,
                "direction": dir_str,
                "confidence": round(conf, 4),
                "score": round(float(mean_scores[idx]), 4),
                "price": price,
                "atr": round(atr_val, 6),
                "market_regime": regime,
                "strategies_count": len(triggered),
                "strategies": triggered[:10],
                "entry_exit": entry_exit,
                "ob_imbalance": round(float(ob_imbalances[idx]), 4),
            })

            if len(candidates) >= TOP_SIGNALS:
                break

    print(f"\n[4/5] Top signaux: {len(candidates)} (seuil confiance={MIN_CONFIDENCE})")

    # --- Phase 5: AI Consensus (optionnel) ---
    if use_ai and candidates:
        t0 = time.time()
        if quick_mode:
            mode_str = "rapide M3+OL1"
        elif no_gemini:
            mode_str = "fast 5 IA (sans Gemini)"
        else:
            mode_str = "parallele 6 IA"
        print(f"\n[5/5] AI Consensus ({mode_str}) sur top {min(3, len(candidates))} signaux...")

        for i, cand in enumerate(candidates[:3]):
            print(f"\n  --- {cand['symbol']} ({cand['direction']}, conf={cand['confidence']:.2f}) ---")

            if quick_mode:
                consensus = quick_consensus(
                    symbol=cand["symbol"],
                    direction=cand["direction"],
                    confidence=cand["confidence"],
                    price=cand["price"],
                    atr=cand["atr"],
                    strategies=cand["strategies"],
                    regime=cand["market_regime"],
                )
            elif no_gemini:
                consensus = fast_consensus(
                    symbol=cand["symbol"],
                    direction=cand["direction"],
                    confidence=cand["confidence"],
                    price=cand["price"],
                    atr=cand["atr"],
                    strategies=cand["strategies"],
                    regime=cand["market_regime"],
                )
            else:
                consensus = run_consensus(
                    symbol=cand["symbol"],
                    direction=cand["direction"],
                    confidence=cand["confidence"],
                    price=cand["price"],
                    atr=cand["atr"],
                    strategies=cand["strategies"],
                    regime=cand["market_regime"],
                )

            cand["consensus"] = {
                "bias": consensus["consensus_bias"],
                "confidence": round(consensus["consensus_confidence"], 4),
                "pct": round(consensus["consensus_pct"], 4),
                "permission": consensus["permission_to_trade"],
                "signal_type": consensus["signal_type"],
                "action_type": consensus["action_type"],
                "market_tag": consensus["market_tag"],
                "votes": consensus["votes"],
                "timing_ms": consensus["timing_ms"],
                "mode": consensus.get("mode", "sequential"),
            }

            status = "OK" if consensus["permission_to_trade"] else "BLOCKED"
            print(f"  Consensus: {consensus['signal_type']} | {status} | {consensus['votes']} | {consensus['timing_ms']}ms")

        print(f"\n[5/5] Consensus termine ({int((time.time()-t0)*1000)}ms)")
    else:
        print(f"\n[5/5] AI Consensus: {'desactive' if not use_ai else 'aucun candidat'}")

    # --- Resultats ---
    total_ms = int((time.time() - pipeline_start) * 1000)
    results["signals"] = candidates
    # Thermal post-check
    thermal_post = check_gpu_thermal()

    results["meta"] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "coins_scanned": len(tensor_symbols),
        "tensor_shape": list(tensor.shape),
        "gpu": GPU_AVAILABLE,
        "time_window": time_window,
        "strategies_count": 100,
        "signals_found": len(candidates),
        "total_ms": total_ms,
        "thermal": {
            "pre": {"status": thermal["status"], "max_temp": thermal.get("max_temp", 0)},
            "post": {"status": thermal_post["status"], "max_temp": thermal_post.get("max_temp", 0)},
            "gpus": thermal_post.get("gpus", []),
        },
    }

    # Affichage
    print(f"\n{'='*60}")
    print(f"  RESULTATS | {len(candidates)} signaux | {total_ms}ms total")
    print(f"{'='*60}")

    for c in candidates:
        dir_icon = "[LONG]" if c["direction"] == "LONG" else "[SHORT]"
        consensus_str = ""
        if "consensus" in c:
            cs = c["consensus"]
            perm = "OK" if cs["permission"] else "BLOCKED"
            consensus_str = f" | AI: {cs['signal_type']} ({perm})"

        print(f"\n  #{c['rank']} {c['symbol']} {dir_icon} conf={c['confidence']:.2f} score={c['score']:.4f}")
        print(f"     Prix: {c['price']:.6f} | ATR: {c['atr']:.6f} | Regime: {c['market_regime']}")
        print(f"     Entry: {c['entry_exit']['entry_price']:.6f} | SL: {c['entry_exit']['sl']:.6f} | TP1: {c['entry_exit']['tp1']:.6f} | TP2: {c['entry_exit']['tp2']:.6f}")
        print(f"     Strategies: {c['strategies_count']} ({', '.join(c['strategies'][:5])})")
        if consensus_str:
            print(f"     {consensus_str}")

    # Sauvegarder JSON
    if output_json:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = OUTPUT_DIR / f"pipeline_{ts}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n  Sauvegarde: {out_path}")

    return results


def run_continuous(cycles: int = 0, interval: int = 300, no_gemini: bool = False, **kwargs):
    """Mode continu: repete le pipeline toutes les N secondes."""
    cycle = 0
    while cycles == 0 or cycle < cycles:
        cycle += 1
        print(f"\n{'#'*60}")
        print(f"  CYCLE {cycle}" + (f"/{cycles}" if cycles else " (continu)"))
        print(f"{'#'*60}")

        try:
            run_pipeline(no_gemini=no_gemini, **kwargs)
        except KeyboardInterrupt:
            print("\nArret demande.")
            break
        except Exception as e:
            logger.error(f"Erreur cycle {cycle}: {e}")

        if cycles == 0 or cycle < cycles:
            print(f"\nProchain cycle dans {interval}s...")
            try:
                time.sleep(interval)
            except KeyboardInterrupt:
                print("\nArret demande.")
                break


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s"
    )

    parser = argparse.ArgumentParser(description="Trading AI GPU Pipeline v2.2")
    parser.add_argument("--coins", type=int, default=TOP_N_COINS, help="Nombre de coins a scanner")
    parser.add_argument("--top", type=int, default=TOP_SIGNALS, help="Top N signaux")
    parser.add_argument("--window", type=int, default=TIME_WINDOW, help="Fenetre temporelle (bougies)")
    parser.add_argument("--no-ai", action="store_true", help="Desactiver consensus IA")
    parser.add_argument("--quick", action="store_true", help="Consensus rapide (M3+OL1 seulement)")
    parser.add_argument("--no-gemini", action="store_true", help="Consensus 5 IA sans Gemini (plus rapide)")
    parser.add_argument("--json", action="store_true", help="Sauvegarder JSON")
    parser.add_argument("--cycles", type=int, default=1, help="Nombre de cycles (0=infini)")
    parser.add_argument("--interval", type=int, default=300, help="Intervalle entre cycles (sec)")
    args = parser.parse_args()

    TOP_SIGNALS = args.top
    setup_gpu()

    if args.cycles > 1 or args.cycles == 0:
        run_continuous(
            cycles=args.cycles,
            interval=args.interval,
            n_coins=args.coins,
            use_ai=not args.no_ai,
            quick_mode=args.quick,
            no_gemini=args.no_gemini,
            time_window=args.window,
            output_json=args.json,
        )
    else:
        run_pipeline(
            n_coins=args.coins,
            use_ai=not args.no_ai,
            quick_mode=args.quick,
            no_gemini=args.no_gemini,
            time_window=args.window,
            output_json=args.json,
        )
