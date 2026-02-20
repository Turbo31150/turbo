"""Benchmark REEL — Prompts de difficulte croissante sur tous les noeuds.

Teste M1, M2, M3, OL1, GEMINI en parallele avec 10 niveaux de difficulte.
Mesure: latence, longueur, qualite, limites de chaque noeud.

Usage: python benchmark_real_test.py
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = r"F:\BUREAU\turbo"
os.chdir(PROJECT_ROOT)
sys.path.insert(0, PROJECT_ROOT)

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import httpx
from src.config import config
from src.tools import extract_lms_output, _strip_thinking_tags

# ══════════════════════════════════════════════════════════════════════════
# 10 NIVEAUX DE DIFFICULTE
# ══════════════════════════════════════════════════════════════════════════

PROMPTS = [
    {
        "level": 1, "category": "code_simple",
        "name": "Fonction basique",
        "prompt": "Ecris une fonction Python qui inverse une string. Juste le code, pas d'explication.",
        "expected_keywords": ["def", "return", "[::-1]"],
        "max_tokens": 256,
    },
    {
        "level": 2, "category": "code_algo",
        "name": "Fibonacci iteratif",
        "prompt": "Ecris une fonction Python iterative fibonacci(n) qui retourne le n-ieme nombre de Fibonacci. Optimise pour la performance. Juste le code.",
        "expected_keywords": ["def", "fibonacci", "for", "return"],
        "max_tokens": 512,
    },
    {
        "level": 3, "category": "debug",
        "name": "Trouver le bug",
        "prompt": "Trouve le bug dans ce code Python et corrige-le:\n\ndef merge_sort(arr):\n    if len(arr) <= 1:\n        return arr\n    mid = len(arr) / 2\n    left = merge_sort(arr[:mid])\n    right = merge_sort(arr[mid:])\n    return merge(left, right)\n\ndef merge(left, right):\n    result = []\n    i = j = 0\n    while i < len(left) and j < len(right):\n        if left[i] <= right[j]:\n            result.append(left[i])\n            i += 1\n        else:\n            result.append(right[j])\n            j += 1\n    return result\n\nIndique le bug, la correction, et pourquoi.",
        "expected_keywords": ["//", "int", "mid", "extend", "remaining"],
        "max_tokens": 1024,
    },
    {
        "level": 4, "category": "architecture",
        "name": "Design pattern",
        "prompt": "Explique la difference entre Strategy, State et Command patterns en Python. Donne un exemple concret pour chacun avec du code. Quand utiliser lequel?",
        "expected_keywords": ["class", "Strategy", "State", "Command"],
        "max_tokens": 2048,
    },
    {
        "level": 5, "category": "code_complex",
        "name": "LRU Cache from scratch",
        "prompt": "Implemente un LRU Cache en Python avec get(key) et put(key, value) en O(1) pour les deux operations. Utilise une doubly-linked list + hashmap. Pas de functools. Code complet et fonctionnel.",
        "expected_keywords": ["class", "Node", "get", "put", "head", "tail", "dict"],
        "max_tokens": 2048,
    },
    {
        "level": 6, "category": "analyse",
        "name": "Complexite algorithmique",
        "prompt": "Analyse la complexite temporelle et spatiale de cet algorithme. Donne le Big-O exact et justifie:\n\ndef mystery(n):\n    if n <= 1:\n        return 1\n    result = 0\n    for i in range(n):\n        result += mystery(n // 2)\n    return result\n\nCombien d'appels recursifs au total pour mystery(16)? Montre l'arbre d'execution.",
        "expected_keywords": ["O(", "recursif", "log", "appels", "arbre"],
        "max_tokens": 2048,
    },
    {
        "level": 7, "category": "code_system",
        "name": "Async producer-consumer",
        "prompt": "Ecris un systeme producer-consumer en Python asyncio avec: 1 queue bornee (max 10), 3 producers qui generent des items a vitesse variable, 2 consumers qui traitent avec latence aleatoire, graceful shutdown via signal, metriques (throughput, queue depth, latence). Code complet et fonctionnel.",
        "expected_keywords": ["asyncio", "Queue", "producer", "consumer", "signal", "gather"],
        "max_tokens": 4096,
    },
    {
        "level": 8, "category": "raisonnement",
        "name": "Probleme logique multi-etapes",
        "prompt": "Resous le probleme d'Einstein des 5 maisons: 5 maisons de couleurs differentes. Chaque proprietaire a une nationalite, boisson, cigarette, animal differents. 1.L'Anglais vit dans la maison rouge 2.Le Suedois a un chien 3.Le Danois boit du the 4.La maison verte est a gauche de la blanche 5.Le proprietaire de la maison verte boit du cafe 6.Le fumeur de Pall Mall a un oiseau 7.Le proprietaire de la maison jaune fume des Dunhill 8.L'homme de la maison du milieu boit du lait 9.Le Norvegien vit dans la premiere maison 10.Le fumeur de Blend vit a cote de celui qui a un chat 11.L'homme qui a un cheval vit a cote du fumeur de Dunhill 12.Le fumeur de Blue Master boit de la biere 13.L'Allemand fume des Prince 14.Le Norvegien vit a cote de la maison bleue 15.Le fumeur de Blend a un voisin qui boit de l'eau. Qui a le poisson? Montre ton raisonnement etape par etape.",
        "expected_keywords": ["Allemand", "poisson", "maison", "Norvegien"],
        "max_tokens": 4096,
    },
    {
        "level": 9, "category": "code_expert",
        "name": "Mini interpreteur",
        "prompt": "Ecris un interpreteur pour un mini-langage avec: Variables (let x = 5), Arithmetique (+,-,*,/ avec precedence), Conditions (if x > 3 then ... else ... end), Boucles (while x > 0 do ... end), Fonctions (fn add(a,b) = a + b end), Print (print(expr)). Implemente le lexer, parser recursive descent, et evaluateur. Code Python complet et fonctionnel avec au moins 1 test.",
        "expected_keywords": ["class", "Token", "parse", "eval", "def", "while", "if"],
        "max_tokens": 8192,
    },
    {
        "level": 10, "category": "meta_analyse",
        "name": "Auto-analyse architecture distribuee",
        "prompt": "Tu fais partie d'un cluster IA distribue avec 5 noeuds: M1 (qwen3-30b, 46GB, analyse profonde), M2 (deepseek-coder, 24GB, code rapide), M3 (mistral-7b, 8GB, taches legeres), OL1 (qwen3:1.7b, recherche web), GEMINI (gemini-3-pro, architecture). Analyse cette architecture et propose: 1.Algorithme de routage optimal base sur type de tache, charge GPU, latence historique 2.Protocole de consensus pondere avec detection desaccords et re-query automatique 3.Strategie de failover avec degradation gracieuse 4.Systeme de cache distribue 5.Metriques de sante avec alertes predictives. Donne du pseudo-code ou Python pour chaque point. Sois precis et technique.",
        "expected_keywords": ["routing", "consensus", "failover", "cache", "health", "class"],
        "max_tokens": 8192,
    },
]


# ══════════════════════════════════════════════════════════════════════════
# NODE QUERY FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════

async def query_lm_node(client, node, prompt, max_tokens):
    t0 = time.monotonic()
    try:
        r = await client.post(f"{node.url}/api/v1/chat", json={
            "model": node.default_model, "input": prompt,
            "temperature": 0.3, "max_output_tokens": max_tokens,
            "stream": False, "store": False,
        }, headers=node.auth_headers, timeout=180)
        r.raise_for_status()
        latency = int((time.monotonic() - t0) * 1000)
        content = extract_lms_output(r.json())
        return {"node": node.name, "model": node.default_model, "status": "OK",
                "latency_ms": latency, "output": content, "output_len": len(content)}
    except Exception as e:
        return {"node": node.name, "model": node.default_model, "status": "ERREUR",
                "latency_ms": int((time.monotonic() - t0) * 1000),
                "output": "", "output_len": 0, "error": str(e)[:200]}


async def query_ollama(client, node, prompt, max_tokens):
    t0 = time.monotonic()
    try:
        r = await client.post(f"{node.url}/api/chat", json={
            "model": node.default_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False, "think": False,
            "options": {"temperature": 0.3, "num_predict": max_tokens},
        }, timeout=180)
        r.raise_for_status()
        latency = int((time.monotonic() - t0) * 1000)
        content = _strip_thinking_tags(r.json()["message"]["content"])
        return {"node": node.name, "model": node.default_model, "status": "OK",
                "latency_ms": latency, "output": content, "output_len": len(content)}
    except Exception as e:
        return {"node": node.name, "model": node.default_model, "status": "ERREUR",
                "latency_ms": int((time.monotonic() - t0) * 1000),
                "output": "", "output_len": 0, "error": str(e)[:200]}


async def query_gemini(prompt, max_tokens):
    t0 = time.monotonic()
    try:
        proc = await asyncio.create_subprocess_exec(
            "node", config.gemini_node.proxy_path, prompt,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=180)
        latency = int((time.monotonic() - t0) * 1000)
        content = _strip_thinking_tags(stdout.decode(errors="replace").strip())
        if proc.returncode != 0 and not content:
            return {"node": "GEMINI", "model": config.gemini_node.default_model,
                    "status": "ERREUR", "latency_ms": latency,
                    "output": "", "output_len": 0, "error": stderr.decode(errors="replace")[:200]}
        return {"node": "GEMINI", "model": config.gemini_node.default_model,
                "status": "OK", "latency_ms": latency,
                "output": content, "output_len": len(content)}
    except asyncio.TimeoutError:
        return {"node": "GEMINI", "model": config.gemini_node.default_model,
                "status": "TIMEOUT", "latency_ms": 180000, "output": "", "output_len": 0}
    except Exception as e:
        return {"node": "GEMINI", "model": config.gemini_node.default_model,
                "status": "ERREUR", "latency_ms": int((time.monotonic() - t0) * 1000),
                "output": "", "output_len": 0, "error": str(e)[:200]}


# ══════════════════════════════════════════════════════════════════════════
# QUALITY SCORING
# ══════════════════════════════════════════════════════════════════════════

def score_response(result, test):
    if result["status"] != "OK" or not result["output"]:
        return {"score": 0, "keyword_hits": "0/0", "quality": "ECHEC"}
    output = result["output"].lower()
    keywords = test.get("expected_keywords", [])
    hits = sum(1 for k in keywords if k.lower() in output)
    keyword_pct = hits / max(len(keywords), 1)
    min_len = test["level"] * 50
    length_ok = result["output_len"] >= min_len
    has_code = "def " in output or "class " in output or "```" in output
    is_structured = output.count("\n") >= 3
    quality_score = keyword_pct * 40 + (20 if length_ok else 5)
    quality_score += 15 if has_code and test["category"].startswith("code") else 10
    quality_score += 15 if is_structured else 5
    quality_score += 10 if result["output_len"] > min_len * 2 else 0
    quality = "EXCELLENT" if quality_score >= 80 else "BON" if quality_score >= 60 else "MOYEN" if quality_score >= 40 else "FAIBLE"
    return {"score": round(min(quality_score, 100)), "keyword_hits": f"{hits}/{len(keywords)}", "quality": quality}


# ══════════════════════════════════════════════════════════════════════════
# MAIN BENCHMARK
# ══════════════════════════════════════════════════════════════════════════

def _print(msg):
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("ascii", errors="replace").decode(), flush=True)


async def run_benchmark():
    _print("=" * 70)
    _print("  JARVIS REAL BENCHMARK — 10 niveaux x 5 noeuds")
    _print("=" * 70)
    t_global = time.monotonic()

    lm_nodes = config.lm_nodes
    ol_nodes = config.ollama_nodes
    node_names = [n.name for n in lm_nodes] + [n.name for n in ol_nodes] + ["GEMINI"]
    results_all = {}
    node_scores = {name: [] for name in node_names}
    node_latencies = {name: [] for name in node_names}
    node_failures = {name: 0 for name in node_names}

    async with httpx.AsyncClient(timeout=180) as client:
        for test in PROMPTS:
            level = test["level"]
            _print(f"\n{'~'*60}")
            _print(f"  NIVEAU {level}/10 — {test['name']} [{test['category']}]")
            _print(f"{'~'*60}")

            tasks = []
            for n in lm_nodes:
                tasks.append(query_lm_node(client, n, test["prompt"], test["max_tokens"]))
            for n in ol_nodes:
                tasks.append(query_ollama(client, n, test["prompt"], test["max_tokens"]))
            tasks.append(query_gemini(test["prompt"], test["max_tokens"]))

            raw_results = await asyncio.gather(*tasks, return_exceptions=True)

            level_results = {}
            for r in raw_results:
                if isinstance(r, Exception):
                    continue
                node_name = r["node"]
                scoring = score_response(r, test)
                r["scoring"] = scoring
                level_results[node_name] = r
                node_scores[node_name].append(scoring["score"])
                if r["status"] == "OK":
                    node_latencies[node_name].append(r["latency_ms"])
                else:
                    node_failures[node_name] += 1

                status_icon = "OK" if r["status"] == "OK" else "--"
                score_str = f"{scoring['score']}/100" if scoring['score'] > 0 else "ECHEC"
                preview = r["output"][:80].replace("\n", " ") if r["output"] else "(vide)"
                _print(f"  [{status_icon}] {node_name:6} | {r['latency_ms']:>7}ms | {score_str:>7} {scoring['quality']:>9} | kw:{scoring['keyword_hits']} | {r['output_len']:>5}ch")
                if r["output"]:
                    _print(f"         > {preview}...")

            results_all[f"level_{level}"] = level_results

    total_ms = int((time.monotonic() - t_global) * 1000)

    _print(f"\n{'='*70}")
    _print(f"  RAPPORT FINAL — {total_ms/1000:.1f}s")
    _print(f"{'='*70}")
    _print(f"\n  {'NOEUD':8} | {'MODELE':30} | {'SCORE':>6} | {'LATENCE':>8} | {'FAIL':>4} | PROFIL")
    _print(f"  {'~'*68}")

    node_profiles = {}
    for name in node_names:
        scores = node_scores[name]
        lats = node_latencies[name]
        fails = node_failures[name]
        avg_score = sum(scores) / max(len(scores), 1)
        avg_lat = int(sum(lats) / max(len(lats), 1)) if lats else 0
        model = "?"
        for n in lm_nodes:
            if n.name == name: model = n.default_model
        for n in ol_nodes:
            if n.name == name: model = n.default_model
        if name == "GEMINI": model = config.gemini_node.default_model

        if avg_score >= 70 and avg_lat < 20000: profile = "POLYVALENT"
        elif avg_score >= 70: profile = "PUISSANT LENT"
        elif avg_lat < 3000 and avg_score >= 40: profile = "RAPIDE"
        elif avg_lat < 3000: profile = "RAPIDE LIMITE"
        elif avg_score < 30: profile = "LIMITE"
        else: profile = "MOYEN"

        node_profiles[name] = {"model": model, "avg_score": round(avg_score, 1),
                               "avg_latency_ms": avg_lat, "failures": fails,
                               "profile": profile, "scores_by_level": scores}
        _print(f"  {name:8} | {model:30} | {avg_score:5.1f}% | {avg_lat:>6}ms | {fails:>4} | {profile}")

    _print(f"\n  LIMITES (dernier niveau score >= 50)")
    _print(f"  {'~'*50}")
    for name in node_names:
        scores = node_scores[name]
        last_good = 0
        for i, s in enumerate(scores):
            if s >= 50: last_good = i + 1
        _print(f"  {name:8} | Limite: niv.{last_good:>2}/10 | {scores}")

    _print(f"\n  MEILLEUR NOEUD PAR CATEGORIE")
    _print(f"  {'~'*50}")
    categories = {}
    for test in PROMPTS:
        cat = test["category"]
        level = test["level"]
        key = f"level_{level}"
        if key in results_all:
            for nname in node_names:
                if nname in results_all[key]:
                    categories.setdefault(cat, {}).setdefault(nname, []).append(
                        results_all[key][nname]["scoring"]["score"])
    for cat, ndata in categories.items():
        best_name = max(ndata.keys(), key=lambda n: sum(ndata[n]) / len(ndata[n]))
        best_avg = sum(ndata[best_name]) / len(ndata[best_name])
        _print(f"  {cat:25} -> {best_name:8} ({best_avg:.0f}%)")

    _print(f"\n  CLASSEMENT GLOBAL")
    _print(f"  {'~'*50}")
    for rank, (name, p) in enumerate(sorted(node_profiles.items(),
                                            key=lambda x: x[1]["avg_score"], reverse=True), 1):
        _print(f"  #{rank} {name:8} — {p['profile']:15} — {p['avg_score']:.0f}% — {p['avg_latency_ms']}ms")

    report = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "duration_ms": total_ms,
              "nodes": node_profiles,
              "results_by_level": {
                  k: {n: {kk: vv for kk, vv in v.items() if kk != "output"}
                      for n, v in lv.items()} for k, lv in results_all.items()}}
    rpath = Path("data/benchmark_real_report.json")
    rpath.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    _print(f"\n{'='*70}")
    _print(f"  TERMINE — {total_ms/1000:.1f}s — Rapport: {rpath.absolute()}")
    _print(f"{'='*70}")


if __name__ == "__main__":
    asyncio.run(run_benchmark())
