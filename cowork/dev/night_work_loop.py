#!/usr/bin/env python3
"""JARVIS Night Work Loop — Keep the cluster busy overnight.

Dispatches rotating batches of useful tasks to M1/M2/OL1 every 30 minutes.
Results are saved to etoile.db table 'cluster_night_work'.

Usage:
    python cowork/dev/night_work_loop.py           # single batch
    python cowork/dev/night_work_loop.py --loop     # loop every 30min
    python cowork/dev/night_work_loop.py --results  # show saved results
"""
import io
import json
import os
import random
import sqlite3
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from _paths import TURBO_DIR as TURBO
DB_PATH = TURBO / "data" / "etoile.db"

# ── Task Bank ────────────────────────────────────────────────
TASK_BANK = [
    # ── Architecture (10) ──
    ("M1", "ARCHI", "Propose 5 regles de naming pour un projet Python avec 226 modules. Format: regle | exemple | justification."),
    ("M1", "ARCHI", "Comment organiser un projet Python de 400 scripts utilitaires en categories coherentes? Liste 8 categories avec 3 exemples chacune."),
    ("M1", "ARCHI", "Quels sont les 5 design patterns les plus utiles pour un orchestrateur multi-agent IA? Une phrase par pattern."),
    ("M1", "ARCHI", "Compare microservices vs monolithe pour un orchestrateur IA Python avec 4 noeuds GPU. 5 criteres de choix."),
    ("M1", "ARCHI", "Propose un schema de base de donnees SQLite pour tracker les performances d'un cluster IA: latence, qualite, cout. DDL SQL."),
    ("M1", "ARCHI", "Comment implementer un event bus en Python pour connecter 15 modules independants? Pattern Observer vs Pub/Sub. Code minimal."),
    ("M1", "ARCHI", "Quels sont les 5 anti-patterns les plus dangereux dans un systeme multi-agent IA? Comment les eviter?"),
    ("M1", "ARCHI", "Propose une strategie de migration pour decomposer un module Python de 6000 lignes en sous-modules. Etapes concretes."),
    ("M2", "ARCHI", "Analyse les trade-offs entre consistency et availability pour un cluster IA distribue avec 4 noeuds. Theoreme CAP applique."),
    ("M2", "ARCHI", "Propose un protocole de consensus pour un vote pondere entre 4 agents IA de fiabilite differente (20% a 100%)."),

    # ── Code Generation (15) ──
    ("M1", "CODE", "Ecris une classe Python CircuitBreaker avec etats CLOSED/OPEN/HALF_OPEN, compteur d'echecs, et timeout de reset. Code complet."),
    ("M1", "CODE", "Ecris un decorateur Python @retry(max_attempts=3, backoff=2) avec exponential backoff. Code complet."),
    ("M1", "CODE", "Ecris une fonction Python async qui fait un health check de 4 URLs en parallele avec asyncio.gather et retourne un dict {url: status}. Code complet."),
    ("M1", "CODE", "Ecris un script Python qui analyse un fichier SQLite et genere un rapport: nb tables, nb rows par table, taille, et integrite. Code complet."),
    ("M1", "CODE", "Ecris une classe Python TokenBucket pour rate limiting avec refill rate et burst capacity. Code complet."),
    ("M1", "CODE", "Ecris un script Python qui monitore nvidia-smi et alerte si temperature GPU > 80C. Output CSV. Code complet."),
    ("M1", "CODE", "Ecris une classe Python LRUCache thread-safe avec TTL expiration. Utilise threading.Lock. Code complet."),
    ("M1", "CODE", "Ecris un serveur WebSocket Python minimal avec asyncio qui broadcast des messages a tous les clients connectes. Code complet."),
    ("M1", "CODE", "Ecris un pipeline ETL Python avec 3 stages (extract SQLite, transform JSON, load new table). Code complet."),
    ("M1", "CODE", "Ecris une classe Python EventEmitter avec on/emit/off, support wildcards, et async handlers. Code complet."),
    ("M1", "CODE", "Ecris un script Python qui genere un rapport HTML de sante systeme (CPU, RAM, disque, GPU). Code complet."),
    ("M1", "CODE", "Ecris un router de requetes Python qui choisit le noeud optimal selon latence, charge, et fiabilite. Code complet."),
    ("M2", "CODE", "Ecris un algorithme de tri topologique en Python pour resoudre les dependances entre 20 agents. Code complet avec tests."),
    ("M2", "CODE", "Ecris un parser de commandes vocales en Python: input texte -> intent + entites. Support francais. Code complet."),
    ("M2", "CODE", "Ecris un systeme de cache distribue en Python avec invalidation par TTL et LRU eviction. Code complet."),

    # ── Trading (12) ──
    ("M1", "TRADING", "Compare les indicateurs RSI, MACD, et Bollinger Bands pour le scalping crypto 1min. Lequel a le meilleur signal-to-noise ratio? 5 lignes."),
    ("M1", "TRADING", "Propose une strategie de gestion de position pour un bot crypto avec 500 USDT capital, 10x levier. Define: entry, TP, SL, sizing. 5 lignes."),
    ("M1", "TRADING", "Quels sont les 3 pieges les plus courants en trading algorithmique sur crypto? Comment les eviter? Une ligne par piege."),
    ("M1", "TRADING", "Compare les strategies Grid Trading vs DCA vs Momentum pour un bot sur BTC/ETH/SOL. Tableau comparatif."),
    ("M1", "TRADING", "Ecris la formule du Sharpe Ratio et du Sortino Ratio. Lequel est meilleur pour evaluer un bot crypto? Justifie en 3 lignes."),
    ("M1", "TRADING", "Propose 5 regles de risk management pour un bot de scalping crypto 10x levier. Chiffres precis."),
    ("M1", "TRADING", "Comment detecter un faux breakout vs un vrai breakout sur un chart crypto 1min? 3 criteres techniques."),
    ("M1", "TRADING", "Quel est le meilleur timeframe pour le scalping crypto: 15s, 1min, 5min? Avantages/inconvenients de chaque."),
    ("M2", "TRADING", "Derive mathematiquement le sizing optimal Kelly pour un bot crypto avec winrate variable (45-65%). Formule adaptative."),
    ("M2", "TRADING", "Modelise la volatilite BTC sur 1min avec un modele GARCH(1,1). Donne les equations et l'interpretation."),
    ("M2", "TRADING", "Propose un systeme de scoring multi-facteurs pour evaluer la qualite d'un signal de trading. 10 facteurs avec poids."),
    ("M2", "TRADING", "Compare le backtesting walk-forward vs holdout vs Monte Carlo pour valider un bot crypto. Pros/cons de chaque."),

    # ── System Optimization (8) ──
    ("M1", "SYSTEM", "Comment optimiser les performances d'un serveur LM Studio avec 6 GPU RTX (46GB VRAM)? 5 points d'optimisation concrets."),
    ("M1", "SYSTEM", "Propose un schema de monitoring pour un cluster de 4 machines IA Windows: metriques, alertes, dashboard. 5 points."),
    ("M1", "SYSTEM", "Comment configurer SQLite WAL mode pour un acces concurrent par 10 scripts Python? Donne le code de configuration."),
    ("M1", "SYSTEM", "Ecris un script PowerShell qui optimise Windows pour un serveur IA: desactiver services inutiles, priorite GPU, RAM. 10 commandes."),
    ("M1", "SYSTEM", "Comment reduire la latence reseau entre 3 machines LAN pour des requetes IA? 5 optimisations Windows."),
    ("M1", "SYSTEM", "Propose une strategie de backup automatique pour 4 bases SQLite (total 6MB). Frequence, retention, verification."),
    ("M2", "SYSTEM", "Analyse la degradation de performance d'un modele 8B sur 1 GPU 8GB vs 3 GPU 24GB vs 6 GPU 46GB. Facteurs limitants."),
    ("M2", "SYSTEM", "Propose un algorithme de load balancing adaptatif pour 4 noeuds IA de puissance inegale. Pseudo-code."),

    # ── Security (6) ──
    ("M1", "SECURITY", "Audite ces pratiques: tokens API en clair dans des scripts Python, bases SQLite sans chiffrement, API REST sans auth. Top 5 fixes par priorite."),
    ("M1", "SECURITY", "Ecris une fonction Python qui sanitize une requete SQL pour prevenir l'injection. Montre les cas a traiter."),
    ("M1", "SECURITY", "Comment securiser un cluster IA local (4 machines LAN)? 5 mesures: reseau, auth, chiffrement, audit, backup."),
    ("M1", "SECURITY", "Ecris un audit de securite Python qui scanne un projet pour: tokens hardcodes, SQL injection, imports dangereux. Code complet."),
    ("M2", "SECURITY", "Analyse les vecteurs d'attaque d'un serveur LM Studio expose sur LAN. Propose des mitigations pour chaque."),
    ("M2", "SECURITY", "Compare les methodes de chiffrement pour SQLite: SQLCipher vs AES-256 at rest vs full disk encryption. Tableau comparatif."),

    # ── Learning & AI (10) ──
    ("M1", "LEARN", "Quelles sont les 5 techniques de prompt engineering les plus efficaces pour obtenir du code Python de qualite? Une ligne chacune."),
    ("M1", "LEARN", "Comment implementer un systeme de feedback loop pour ameliorer automatiquement le routage de requetes IA? Pseudo-code en 10 lignes."),
    ("M1", "LEARN", "Compare few-shot vs zero-shot vs chain-of-thought pour des taches de code generation. Quel mode pour quel type de tache?"),
    ("M1", "LEARN", "Propose un systeme de scoring de qualite pour les reponses d'un LLM: 5 criteres avec formule de score combine."),
    ("M1", "LEARN", "Comment fine-tuner un modele 8B avec QLoRA sur 1 GPU 12GB? Etapes, hyperparametres, et pieges a eviter."),
    ("M1", "LEARN", "Ecris un systeme de pattern discovery qui detecte les types de requetes recurrentes a partir de logs. Pseudo-code."),
    ("M2", "LEARN", "Analyse les limites du transfer learning pour des modeles de code: quand ca marche vs quand ca echoue. 5 cas concrets."),
    ("M2", "LEARN", "Propose un curriculum d'apprentissage pour un agent IA autonome: du simple au complexe. 10 etapes avec metriques de progression."),
    ("M2", "LEARN", "Compare les architectures Transformer, Mamba, et RWKV pour l'inference locale sur GPU consumer. Tableau benchmark."),
    ("M2", "LEARN", "Propose un protocole d'evaluation pour comparer 4 modeles IA locaux. Metriques, prompts de test, scoring. Plan detaille."),

    # ── Math & Reasoning (5) ──
    ("M2", "MATH", "Derive la formule du Kelly Criterion pour le dimensionnement de position en trading. Montre les etapes du calcul."),
    ("M2", "MATH", "Resous: optimiser f(x,y) = x*ln(1+y) - y*ln(1+x) sous contrainte x+y=1, x,y>0. Methode de Lagrange."),
    ("M2", "MATH", "Calcule la probabilite de drawdown > 20% pour un bot avec winrate 55%, reward/risk 1.5, apres 100 trades. Monte Carlo."),
    ("M2", "MATH", "Derive la formule de l'Expected Shortfall (CVaR) a 95% pour une distribution de returns non-gaussienne."),
    ("M2", "MATH", "Propose un modele de Markov a 4 etats pour predire la fiabilite d'un noeud IA. Matrice de transition et calcul."),

    # ── DevOps & Infra (5) ──
    ("M1", "DEVOPS", "Ecris un Dockerfile multi-stage pour un serveur Python FastAPI avec CUDA support. Optimise pour taille minimale."),
    ("M1", "DEVOPS", "Propose un pipeline CI/CD pour un projet Python avec 300 tests: lint, test, build, deploy. GitHub Actions YAML."),
    ("M1", "DEVOPS", "Comment mettre en place un reverse proxy Nginx pour load-balancer 4 serveurs LM Studio? Config complete."),
    ("M1", "DEVOPS", "Ecris un script bash qui deploie un cluster de 4 machines IA: sync code, restart services, verify health. Code complet."),
    ("M2", "DEVOPS", "Compare Docker Swarm vs Kubernetes vs Nomad pour orchestrer 4 noeuds IA avec GPU. Tableau pros/cons."),
]


def query_m1(prompt, timeout=30):
    body = json.dumps({
        "model": "qwen3-8b", "input": "/nothink\n" + prompt,
        "temperature": 0.2, "max_output_tokens": 2048,
        "stream": False, "store": False
    })
    r = subprocess.run(
        ["curl", "-s", "--max-time", str(timeout),
         "http://127.0.0.1:1234/api/v1/chat",
         "-H", "Content-Type: application/json", "-d", body],
        capture_output=True, timeout=timeout + 10)
    d = json.loads(r.stdout.decode("utf-8", "replace"))
    for item in reversed(d.get("output", [])):
        if item.get("type") == "message":
            c = item.get("content", "")
            return c.strip() if isinstance(c, str) else str(c)
    return ""


def query_m2(prompt, timeout=90):
    body = json.dumps({
        "model": "deepseek/deepseek-r1-0528-qwen3-8b", "input": prompt,
        "temperature": 0.3, "max_output_tokens": 2048,
        "stream": False, "store": False
    })
    r = subprocess.run(
        ["curl", "-s", "--max-time", str(timeout),
         "http://192.168.1.26:1234/api/v1/chat",
         "-H", "Content-Type: application/json", "-d", body],
        capture_output=True, timeout=timeout + 10)
    d = json.loads(r.stdout.decode("utf-8", "replace"))
    for item in reversed(d.get("output", [])):
        if item.get("type") == "message":
            c = item.get("content", "")
            return c.strip() if isinstance(c, str) else str(c)
    return ""


QUERY_FN = {"M1": query_m1, "M2": query_m2}


def init_db():
    db = sqlite3.connect(str(DB_PATH))
    db.execute("""CREATE TABLE IF NOT EXISTS cluster_night_work (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT, node TEXT, category TEXT,
        prompt TEXT, response TEXT, elapsed_s REAL, error TEXT)""")
    db.commit()
    return db


def pick_batch(size=8):
    """Pick a random batch of tasks. M1 fast + M2 deep."""
    m1_tasks = [t for t in TASK_BANK if t[0] == "M1"]
    m2_tasks = [t for t in TASK_BANK if t[0] == "M2"]
    # 6 M1 tasks (fast) + 2 M2 tasks (deep, parallel)
    batch = random.sample(m1_tasks, min(size - 2, len(m1_tasks)))
    batch += random.sample(m2_tasks, min(2, len(m2_tasks)))
    random.shuffle(batch)
    return batch[:size]


def run_batch(db, batch_num=1):
    """Run a batch of tasks in parallel."""
    batch = pick_batch(6)
    ts = time.strftime("%H:%M:%S")
    print(f"\n{'=' * 50}")
    print(f"  BATCH {batch_num} — {len(batch)} taches — {ts}")
    print(f"{'=' * 50}")

    ok = 0

    def execute(i, node, cat, prompt):
        t0 = time.time()
        try:
            fn = QUERY_FN.get(node)
            if not fn:
                return i, node, cat, prompt, None, 0, f"No query fn for {node}"
            resp = fn(prompt)
            return i, node, cat, prompt, resp, time.time() - t0, None
        except Exception as e:
            return i, node, cat, prompt, None, time.time() - t0, str(e)[:150]

    with ThreadPoolExecutor(max_workers=3) as pool:
        futs = [pool.submit(execute, i, n, c, p) for i, (n, c, p) in enumerate(batch)]
        for f in as_completed(futs):
            i, node, cat, prompt, resp, elapsed, err = f.result()
            status = "OK" if resp and not err else "FAIL"
            if status == "OK":
                ok += 1

            print(f"\n  [{node}/{cat}] {elapsed:.1f}s — {status}")
            if resp:
                for line in resp[:300].splitlines()[:4]:
                    print(f"    {line[:90]}")
            elif err:
                print(f"    ERR: {err[:80]}")

            db.execute(
                "INSERT INTO cluster_night_work (timestamp, node, category, prompt, response, elapsed_s, error) VALUES (?,?,?,?,?,?,?)",
                (time.strftime("%Y-%m-%dT%H:%M:%S"), node, cat, prompt[:200],
                 (resp or "")[:3000], round(elapsed, 2), err))
            db.commit()

    print(f"\n  >> {ok}/{len(batch)} OK")
    return ok, len(batch)


def show_results():
    db = sqlite3.connect(str(DB_PATH))
    rows = db.execute(
        "SELECT timestamp, node, category, elapsed_s, CASE WHEN error IS NULL THEN 'OK' ELSE 'FAIL' END FROM cluster_night_work ORDER BY id DESC LIMIT 20"
    ).fetchall()
    print(f"\n  Derniers {len(rows)} resultats:")
    for ts, node, cat, elapsed, status in rows:
        print(f"    {ts} | {node}/{cat} | {elapsed:.1f}s | {status}")
    total = db.execute("SELECT COUNT(*) FROM cluster_night_work").fetchone()[0]
    ok = db.execute("SELECT COUNT(*) FROM cluster_night_work WHERE error IS NULL").fetchone()[0]
    print(f"\n  Total: {total} tasks | {ok} OK ({ok*100//max(total,1)}%)")
    db.close()


def main():
    if "--results" in sys.argv:
        show_results()
        return

    db = init_db()

    max_cycles = int(sys.argv[sys.argv.index("--cycles") + 1]) if "--cycles" in sys.argv else 0
    pause = int(sys.argv[sys.argv.index("--pause") + 1]) if "--pause" in sys.argv else 10

    if "--loop" in sys.argv:
        limit = max_cycles if max_cycles > 0 else 999999
        print(f"JARVIS Night Work Loop — {limit} cycles, pause {pause}s")
        print("Ctrl+C pour arreter\n")
        batch_num = 1
        total_ok, total_tasks = 0, 0
        while batch_num <= limit:
            try:
                ok, n = run_batch(db, batch_num)
                total_ok += ok
                total_tasks += n
                batch_num += 1
                rate = total_ok * 100 // max(total_tasks, 1)
                print(f"\n  Cumul: {total_ok}/{total_tasks} OK ({rate}%) — cycle {batch_num}/{limit} dans {pause}s...")
                time.sleep(pause)
            except KeyboardInterrupt:
                print(f"\n\nArret. Total: {total_ok}/{total_tasks} taches OK")
                break
        print(f"\n=== TERMINE: {total_ok}/{total_tasks} taches en {batch_num-1} cycles ===")
    else:
        run_batch(db)

    db.close()


if __name__ == "__main__":
    main()
