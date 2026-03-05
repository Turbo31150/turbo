#!/usr/bin/env python3
"""prompt_optimizer.py

Batch 6.2 – Optimisation automatique des prompts via A/B‑testing.

Fonctionnalités :
* Génère 3 variantes d'un même prompt (original, version concise, version détaillée).
* Envoie chaque variante au modèle M1 (qwen3‑8b) via l'API LM Studio :
    http://127.0.0.1:1234/v1/chat/completions
* Chronomètre le temps de réponse, mesure la longueur de la réponse (nombre de caractères).
* Stocke les résultats dans une base SQLite `prompts.db`.
* CLI :
  --test "prompt"      → teste les variantes, affiche les métriques et enregistre.
  --stats              → affiche les meilleures variantes (latence + longueur).
  --optimize "prompt" → exécute le test puis retourne la variante jugée optimale.

Le script utilise uniquement la bibliothèque standard (`urllib`, `json`, `sqlite3`, `time`, …).
"""

import argparse
import json
import sqlite3
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
API_URL = "http://127.0.0.1:1234/v1/chat/completions"
DB_PATH = Path(__file__).with_name("prompts.db")

# ---------------------------------------------------------------------------
# SQLite helpers
# ---------------------------------------------------------------------------

def init_db(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            base_prompt TEXT,
            variant TEXT,
            latency_ms REAL,
            response_len INTEGER,
            response TEXT,
            ts TEXT
        )
        """
    )
    conn.commit()

def insert_run(conn: sqlite3.Connection, base_prompt: str, variant: str, latency: float, resp_len: int, response: str):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO runs (base_prompt, variant, latency_ms, response_len, response, ts) VALUES (?,?,?,?,?,?)",
        (base_prompt, variant, latency, resp_len, response, datetime.utcnow().isoformat()),
    )
    conn.commit()

def fetch_all(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute("SELECT * FROM runs ORDER BY ts")
    return cur.fetchall()

# ---------------------------------------------------------------------------
# Prompt variation generation
# ---------------------------------------------------------------------------

def generate_variations(prompt: str):
    """Retourne trois variantes : original, version concise, version détaillée.
    Cette fonction est simple mais extensible.
    """
    variations = [
        prompt,
        prompt + "\nPlease give a concise answer.",
        prompt + "\nPlease provide a detailed answer, including examples.",
    ]
    return variations

# ---------------------------------------------------------------------------
# API interaction
# ---------------------------------------------------------------------------

def call_model(variant: str):
    """Envoie le texte au modèle M1 et retourne (latency_ms, response_text)."""
    payload = json.dumps({
        "model": "qwen3-8b",
        "messages": [{"role": "user", "content": variant}],
        "max_tokens": 1024,
    }).encode("utf-8")
    req = urllib.request.Request(API_URL, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)
        latency = (time.time() - start) * 1000.0
        # Extraction du texte brut – les différentes endpoints renvoient légèrement des structures différentes
        if isinstance(data, dict):
            # OLLAMA‑style
            if "message" in data:
                content = data["message"].get("content", "")
            elif "choices" in data:
                content = data["choices"][0]["message"].get("content", "")
            else:
                content = str(data)
        else:
            content = str(data)
        return latency, content
    except Exception as e:
        print(f"[prompt_optimizer] Erreur d'appel API : {e}", file=sys.stderr)
        return None, ""

# ---------------------------------------------------------------------------
# Scoring – simple heuristique (latence faible + longueur élevée)
# ---------------------------------------------------------------------------

def score_variant(latency: float, length: int):
    # On veut minimiser la latence et maximiser la longueur.
    # Une formule simple : length / latency (plus grand = meilleur).
    if latency == 0:
        return 0
    return length / latency

# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def command_test(prompt: str):
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    variations = generate_variations(prompt)
    results = []
    for var in variations:
        lat, resp = call_model(var)
        if lat is None:
            continue
        resp_len = len(resp)
        insert_run(conn, prompt, var, lat, resp_len, resp)
        results.append((var, lat, resp_len))
    conn.close()
    # Affichage des résultats
    print("[prompt_optimizer] Résultats du test :")
    for i, (var, lat, l) in enumerate(results, 1):
        print(f"  Variante {i}: latency={lat:.1f} ms, length={l} chars")
    return results

def command_stats():
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    rows = fetch_all(conn)
    conn.close()
    if not rows:
        print("[prompt_optimizer] Aucune donnée disponible.")
        return
    # Calcul du meilleur score par base_prompt
    best = {}
    for row in rows:
        _, base, variant, latency, resp_len, _, _ = row
        sc = score_variant(latency, resp_len)
        if base not in best or sc > best[base]["score"]:
            best[base] = {"variant": variant, "latency": latency, "len": resp_len, "score": sc}
    print("[prompt_optimizer] Meilleures variantes par prompt :")
    for base, info in best.items():
        print(f"- Prompt: {base}\n  Variante: {info['variant']}\n  latency={info['latency']:.1f} ms, length={info['len']} chars, score={info['score']:.4f}\n")

def command_optimize(prompt: str):
    results = command_test(prompt)
    if not results:
        print("[prompt_optimizer] Aucun résultat – optimisation impossible.")
        return
    # Choisir la variante avec le meilleur score
    best_variant = max(results, key=lambda r: score_variant(r[1], r[2]))
    print("[prompt_optimizer] Variante optimale :")
    print(best_variant[0])

def main():
    parser = argparse.ArgumentParser(description="Optimisation automatique des prompts via A/B‑testing.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--test", metavar="PROMPT", help="Teste 3 variantes du prompt donné")
    group.add_argument("--stats", action="store_true", help="Affiche les meilleures variantes enregistrées")
    group.add_argument("--optimize", metavar="PROMPT", help="Teste et retourne la variante jugée optimale")
    args = parser.parse_args()

    if args.test:
        command_test(args.test)
    elif args.stats:
        command_stats()
    elif args.optimize:
        command_optimize(args.optimize)

if __name__ == "__main__":
    main()
