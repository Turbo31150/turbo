"""
AI Consensus — Orchestrateur multi-IA (6 modeles)
Trading AI System v2.3 | Adapte cluster JARVIS

Modeles:
  M3/mistral-7b  (w=1.0) — Fallback rapide
  GEMINI/proxy    (w=1.1) — Validation externe
  OL1/minimax     (w=1.3) — Recherche web temps reel
  M1/qwen3-8b    (w=1.5) — Rapide + raisonnement
  M2/gpt-oss-20b  (w=1.2) — Code/strategies
  OL1/qwen3-1.7b (w=0.8) — Ultra-rapide

Protocole: JSON strict {bias, confidence, reason}
Mode: parallele par machine (v2.3) — sequentiel intra-machine
"""

import json
import time
import logging
import subprocess
import requests
from typing import Optional
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger("ai_consensus")

# --- Config cluster JARVIS ---
MODELS = [
    {
        "id": "m3-mistral",
        "name": "M3/mistral-7b",
        "weight": 1.0,
        "type": "general",
        "endpoint": "http://192.168.1.113:1234/api/v1/chat",
        "auth": "Bearer sk-lm-Zxbn5FZ1:M2PkaqHzwA4TilZ9EFux",
        "model_id": "mistral-7b-instruct-v0.3",
        "timeout": 60,
        "method": "lmstudio",
    },
    {
        "id": "gemini",
        "name": "GEMINI/proxy",
        "weight": 1.1,
        "type": "validation",
        "proxy_path": "F:/BUREAU/turbo/gemini-proxy.js",
        "timeout": 120,
        "method": "gemini_proxy",
    },
    {
        "id": "ol1-minimax",
        "name": "OL1/minimax-cloud",
        "weight": 1.3,
        "type": "search",
        "endpoint": "http://127.0.0.1:11434/api/chat",
        "model_id": "minimax-m2.5:cloud",
        "timeout": 120,
        "method": "ollama",
    },
    {
        "id": "m1-qwen8b",
        "name": "M1/qwen3-8b",
        "weight": 1.5,
        "type": "reasoning",
        "endpoint": "http://10.5.0.2:1234/api/v1/chat",
        "auth": "Bearer sk-lm-LOkUylwu:1PMZR74wuxj7OpeyISV7",
        "model_id": "qwen/qwen3-8b",
        "timeout": 30,
        "method": "lmstudio",
    },
    {
        "id": "m2-gptoss",
        "name": "M2/gpt-oss-20b",
        "weight": 1.2,
        "type": "code",
        "endpoint": "http://192.168.1.26:1234/api/v1/chat",
        "auth": "Bearer sk-lm-keRZkUya:St9kRjCg3VXTX6Getdp4",
        "model_id": "openai/gpt-oss-20b",
        "timeout": 120,
        "method": "lmstudio",
    },
    {
        "id": "ol1-local",
        "name": "OL1/qwen3-1.7b",
        "weight": 0.8,
        "type": "fast",
        "endpoint": "http://127.0.0.1:11434/api/chat",
        "model_id": "qwen3:1.7b",
        "timeout": 30,
        "method": "ollama",
    },
]

CONSENSUS_THRESHOLD = 0.7
PERMISSION_THRESHOLD = 0.6
CONFIDENCE_MIN = 0.5
BUY_SELL_SPREAD_MIN = 0.2

# JSON strict attendu
SYSTEM_PROMPT = """Tu es un analyste trading crypto expert. Analyse le signal et reponds UNIQUEMENT en JSON strict:
{"bias": "LONG" ou "SHORT" ou "HOLD", "confidence": 0.0 a 1.0, "reason": "explication courte"}
RIEN d'autre que ce JSON. Pas de markdown, pas de texte avant/apres."""


class MarketRegime(Enum):
    TREND = "trend"
    RANGE = "range"
    TRANSITION = "transition"


def _query_lmstudio(model_cfg: dict, prompt: str) -> Optional[dict]:
    """Query LM Studio (M1, M2, M3) — chat completions avec fallback responses API."""
    headers = {"Content-Type": "application/json"}
    if model_cfg.get("auth"):
        headers["Authorization"] = model_cfg["auth"]

    # Essai 1: /v1/chat/completions (messages format — meilleur suivi JSON)
    try:
        endpoint_cc = model_cfg["endpoint"].replace("/api/v1/chat", "/v1/chat/completions")
        payload_cc = {
            "model": model_cfg["model_id"],
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 512,
            "stream": False,
        }

        r = requests.post(endpoint_cc, json=payload_cc,
                          headers=headers, timeout=model_cfg["timeout"])
        r.raise_for_status()
        data = r.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        result = _parse_json_response(content, model_cfg["id"])
        if result:
            return result
    except requests.exceptions.HTTPError:
        pass  # Fallback ci-dessous
    except Exception as e:
        logger.debug(f"{model_cfg['name']}: chat completions failed: {e}")

    # Essai 2: /api/v1/chat (responses API — anciens LM Studio)
    try:
        full_input = f"{SYSTEM_PROMPT}\n\n{prompt}"
        payload_resp = {
            "model": model_cfg["model_id"],
            "input": full_input,
            "temperature": 0.3,
            "max_output_tokens": 512,
            "stream": False,
            "store": False,
        }

        r = requests.post(model_cfg["endpoint"], json=payload_resp,
                          headers=headers, timeout=model_cfg["timeout"])
        r.raise_for_status()
        data = r.json()
        content = data.get("output", [{}])[0].get("content", "")
        return _parse_json_response(content, model_cfg["id"])
    except Exception as e:
        logger.warning(f"{model_cfg['name']}: {e}")
        return None


def _query_ollama(model_cfg: dict, prompt: str) -> Optional[dict]:
    """Query Ollama (OL1)."""
    try:
        payload = {
            "model": model_cfg["model_id"],
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "think": False,  # OBLIGATOIRE pour cloud
        }

        r = requests.post(model_cfg["endpoint"], json=payload,
                          timeout=model_cfg["timeout"])
        r.raise_for_status()
        data = r.json()

        content = data.get("message", {}).get("content", "")
        return _parse_json_response(content, model_cfg["id"])
    except Exception as e:
        logger.warning(f"{model_cfg['name']}: {e}")
        return None


def _query_gemini(model_cfg: dict, prompt: str) -> Optional[dict]:
    """Query Gemini via proxy Node.js."""
    try:
        full_prompt = f"{SYSTEM_PROMPT}\n\n{prompt}"
        result = subprocess.run(
            ["node", model_cfg["proxy_path"], "--json", full_prompt],
            capture_output=True, text=True,
            timeout=model_cfg["timeout"],
            encoding="utf-8", errors="replace"
        )

        if result.returncode != 0:
            logger.warning(f"GEMINI proxy error: {result.stderr[:200]}")
            return None

        content = result.stdout.strip()
        return _parse_json_response(content, model_cfg["id"])
    except Exception as e:
        logger.warning(f"GEMINI: {e}")
        return None


def _parse_json_response(content: str, model_id: str) -> Optional[dict]:
    """Parse la reponse JSON stricte {bias, confidence, reason}."""
    if not content:
        return None

    # Nettoyer markdown
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(l for l in lines if not l.strip().startswith("```"))
        content = content.strip()

    # Chercher le JSON dans le texte
    start = content.find("{")
    end = content.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            obj = json.loads(content[start:end])
            bias = obj.get("bias", "HOLD").upper()
            if bias not in ("LONG", "SHORT", "HOLD"):
                bias = "HOLD"
            confidence = float(obj.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, confidence))
            reason = str(obj.get("reason", ""))

            return {"bias": bias, "confidence": confidence, "reason": reason}
        except (json.JSONDecodeError, ValueError):
            pass

    logger.warning(f"{model_id}: JSON invalide: {content[:100]}")
    return None


def build_analysis_prompt(symbol: str, direction: str, confidence: float,
                          price: float, atr: float, strategies: list[str],
                          regime: str) -> str:
    """Construit le prompt d'analyse pour les IA."""
    strats_str = ", ".join(strategies[:10])
    return f"""Analyse trading crypto:

Symbole: {symbol}
Signal technique: {direction} (confiance: {confidence:.2f})
Prix actuel: {price:.6f} USDT
ATR(14): {atr:.6f}
Regime marche: {regime}
Strategies declenchees: {strats_str}

Donne ton avis en JSON: {{"bias": "LONG/SHORT/HOLD", "confidence": 0.0-1.0, "reason": "..."}}"""


def query_model(model_cfg: dict, prompt: str) -> Optional[dict]:
    """Route vers le bon backend selon la methode."""
    method = model_cfg.get("method")
    if method == "lmstudio":
        return _query_lmstudio(model_cfg, prompt)
    elif method == "ollama":
        return _query_ollama(model_cfg, prompt)
    elif method == "gemini_proxy":
        return _query_gemini(model_cfg, prompt)
    return None


# Groupes machines — modeles sur meme machine = sequentiels entre eux
MACHINE_GROUPS = {
    "M3":     ["m3-mistral"],
    "GEMINI": ["gemini"],
    "OL1":    ["ol1-minimax", "ol1-local"],   # Meme Ollama = sequentiel
    "M1":     ["m1-qwen8b"],
    "M2":     ["m2-gptoss"],
}


def _query_machine_group(models_in_group: list[dict], prompt: str) -> list[dict]:
    """Query sequentiellement les modeles d'un meme groupe machine."""
    results = []
    for model in models_in_group:
        t0 = time.time()
        result = query_model(model, prompt)
        elapsed = int((time.time() - t0) * 1000)

        if result:
            results.append({
                "model": model["name"],
                "weight": model["weight"],
                "bias": result["bias"],
                "confidence": result["confidence"],
                "reason": result["reason"],
                "time_ms": elapsed,
                "status": "OK",
            })
            logger.info(f"  {model['name']}: {result['bias']} ({result['confidence']:.2f}) [{elapsed}ms]")
        else:
            results.append({
                "model": model["name"],
                "weight": model["weight"],
                "bias": "HOLD",
                "confidence": 0.0,
                "reason": "timeout/error",
                "time_ms": elapsed,
                "status": "FAIL",
            })
            logger.warning(f"  {model['name']}: FAIL [{elapsed}ms]")
    return results


def run_consensus(symbol: str, direction: str, confidence: float,
                  price: float, atr: float, strategies: list[str],
                  regime: str, models: Optional[list] = None,
                  parallel: bool = True
                  ) -> dict:
    """
    Execute le consensus sur 6 modeles.
    Mode parallele (v2.3): machines differentes en parallele,
    modeles sur meme machine en sequentiel.

    Retourne:
      - consensus_bias: LONG/SHORT/HOLD
      - consensus_confidence: 0.0-1.0
      - consensus_pct: % accord
      - permission_to_trade: bool
      - market_regime: str
      - market_tag: str
      - responses: list des reponses par modele
      - timing_ms: temps total
      - mode: "parallel" ou "sequential"
    """
    if models is None:
        models = MODELS

    prompt = build_analysis_prompt(symbol, direction, confidence,
                                   price, atr, strategies, regime)

    t_start = time.time()

    if parallel and len(models) > 2:
        responses = _run_parallel(models, prompt)
    else:
        responses = _run_sequential(models, prompt)

    total_ms = int((time.time() - t_start) * 1000)

    result = _compute_weighted_consensus(responses, regime, total_ms)
    result["mode"] = "parallel" if (parallel and len(models) > 2) else "sequential"
    return result


def _run_sequential(models: list[dict], prompt: str) -> list[dict]:
    """Mode sequentiel classique (fallback ou petit nombre de modeles)."""
    responses = []
    for model in models:
        t0 = time.time()
        result = query_model(model, prompt)
        elapsed = int((time.time() - t0) * 1000)

        if result:
            responses.append({
                "model": model["name"],
                "weight": model["weight"],
                "bias": result["bias"],
                "confidence": result["confidence"],
                "reason": result["reason"],
                "time_ms": elapsed,
                "status": "OK",
            })
            logger.info(f"  {model['name']}: {result['bias']} ({result['confidence']:.2f}) [{elapsed}ms]")
        else:
            responses.append({
                "model": model["name"],
                "weight": model["weight"],
                "bias": "HOLD",
                "confidence": 0.0,
                "reason": "timeout/error",
                "time_ms": elapsed,
                "status": "FAIL",
            })
            logger.warning(f"  {model['name']}: FAIL [{elapsed}ms]")
    return responses


def _run_parallel(models: list[dict], prompt: str) -> list[dict]:
    """
    Mode parallele v2.3: groupe par machine, execute les groupes en parallele.
    Intra-groupe = sequentiel (meme machine).
    """
    # Construire groupes a partir des modeles demandes
    groups = {}
    ungrouped = []

    for model in models:
        placed = False
        for machine, ids in MACHINE_GROUPS.items():
            if model["id"] in ids:
                groups.setdefault(machine, []).append(model)
                placed = True
                break
        if not placed:
            ungrouped.append(model)

    # Chaque modele non-groupe = son propre groupe
    for m in ungrouped:
        groups[m["id"]] = [m]

    logger.info(f"  Parallel consensus: {len(groups)} groupes machines "
                f"({', '.join(f'{k}({len(v)})' for k, v in groups.items())})")

    all_responses = []

    with ThreadPoolExecutor(max_workers=len(groups)) as executor:
        futures = {
            executor.submit(_query_machine_group, group_models, prompt): machine
            for machine, group_models in groups.items()
        }

        for future in as_completed(futures):
            machine = futures[future]
            try:
                group_results = future.result(timeout=180)
                all_responses.extend(group_results)
            except Exception as e:
                logger.error(f"  Groupe {machine} erreur: {e}")
                # Marquer tous les modeles du groupe comme FAIL
                for m in groups[machine]:
                    all_responses.append({
                        "model": m["name"],
                        "weight": m["weight"],
                        "bias": "HOLD",
                        "confidence": 0.0,
                        "reason": f"group_error: {e}",
                        "time_ms": 0,
                        "status": "FAIL",
                    })

    return all_responses


def _compute_weighted_consensus(responses: list, regime: str,
                                 total_ms: int) -> dict:
    """Calcule le consensus pondere a partir des reponses."""
    total_weight = 0.0
    weighted_signal = 0.0
    weighted_confidence = 0.0
    long_count = 0
    short_count = 0
    hold_count = 0

    for r in responses:
        w = r["weight"]
        total_weight += w

        direction_sign = 0
        if r["bias"] == "LONG":
            direction_sign = 1
            long_count += 1
        elif r["bias"] == "SHORT":
            direction_sign = -1
            short_count += 1
        else:
            hold_count += 1

        signal_i = r["confidence"] * direction_sign
        weighted_signal += w * signal_i
        weighted_confidence += w * r["confidence"]

    if total_weight == 0:
        total_weight = 1.0

    C = weighted_signal / total_weight
    avg_confidence = weighted_confidence / total_weight

    # Consensus bias
    if C > 0.1:
        consensus_bias = "LONG"
    elif C < -0.1:
        consensus_bias = "SHORT"
    else:
        consensus_bias = "HOLD"

    # Consensus %
    total_votes = long_count + short_count + hold_count
    if total_votes > 0:
        if consensus_bias == "LONG":
            consensus_pct = long_count / total_votes
        elif consensus_bias == "SHORT":
            consensus_pct = short_count / total_votes
        else:
            consensus_pct = hold_count / total_votes
    else:
        consensus_pct = 0.0

    # Buy/sell spread
    if total_votes > 0:
        buy_sell_spread = abs(long_count - short_count) / total_votes
    else:
        buy_sell_spread = 0.0

    # Permission to trade (v2.2)
    permission_to_trade = (
        consensus_pct >= PERMISSION_THRESHOLD and
        avg_confidence >= CONFIDENCE_MIN and
        consensus_bias != "HOLD" and
        buy_sell_spread > BUY_SELL_SPREAD_MIN
    )

    # Market regime detection
    if consensus_pct > 0.8:
        detected_regime = MarketRegime.TREND
    elif consensus_pct > 0.6:
        detected_regime = MarketRegime.RANGE
    else:
        detected_regime = MarketRegime.TRANSITION

    # Market tag
    if detected_regime == MarketRegime.TREND:
        tag = f"trend_{consensus_bias.lower()}"
    elif detected_regime == MarketRegime.RANGE:
        tag = "range_bound"
    else:
        tag = "transition_uncertain"

    # Signal format (v2.2)
    if not permission_to_trade:
        signal_type = f"BLOCKED_{consensus_bias}"
        action_type = "blocked"
    elif consensus_pct > 0.8:
        signal_type = f"STRONG_{consensus_bias}"
        action_type = "authorized"
    elif consensus_pct > 0.6:
        signal_type = f"WEAK_{consensus_bias}"
        action_type = "weak"
    else:
        signal_type = "HOLD"
        action_type = "weak"

    return {
        "consensus_bias": consensus_bias,
        "consensus_confidence": abs(C),
        "consensus_pct": consensus_pct,
        "avg_confidence": avg_confidence,
        "permission_to_trade": permission_to_trade,
        "signal_type": signal_type,
        "action_type": action_type,
        "market_regime": detected_regime.value,
        "market_tag": tag,
        "buy_sell_spread": buy_sell_spread,
        "votes": f"{long_count}L/{short_count}S/{hold_count}H",
        "responses": responses,
        "timing_ms": total_ms,
    }


def quick_consensus(symbol: str, direction: str, confidence: float,
                    price: float, atr: float, strategies: list[str],
                    regime: str = "unknown") -> dict:
    """Wrapper rapide: n'utilise que M3 + OL1 (les 2 plus rapides)."""
    fast_models = [m for m in MODELS if m["id"] in ("m3-mistral", "ol1-minimax")]
    return run_consensus(symbol, direction, confidence, price, atr,
                         strategies, regime, models=fast_models)


def fast_consensus(symbol: str, direction: str, confidence: float,
                   price: float, atr: float, strategies: list[str],
                   regime: str = "unknown") -> dict:
    """Consensus 5 IA sans GEMINI (evite le bottleneck 60-90s)."""
    no_gemini = [m for m in MODELS if m["id"] != "gemini"]
    return run_consensus(symbol, direction, confidence, price, atr,
                         strategies, regime, models=no_gemini)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    print("=== AI Consensus Test ===")

    result = run_consensus(
        symbol="BTC_USDT",
        direction="LONG",
        confidence=0.75,
        price=97500.0,
        atr=450.0,
        strategies=["breakout_ema21_res20", "momentum_ema_stack", "hybrid_full_confluence"],
        regime="trend",
    )

    print(f"\nConsensus: {result['consensus_bias']} ({result['consensus_confidence']:.2f})")
    print(f"Signal: {result['signal_type']} | Action: {result['action_type']}")
    print(f"Permission: {result['permission_to_trade']}")
    print(f"Regime: {result['market_regime']} | Tag: {result['market_tag']}")
    print(f"Votes: {result['votes']} | Temps: {result['timing_ms']}ms")
    for r in result["responses"]:
        print(f"  {r['model']}: {r['bias']} ({r['confidence']:.2f}) [{r['time_ms']}ms] - {r['reason'][:60]}")
